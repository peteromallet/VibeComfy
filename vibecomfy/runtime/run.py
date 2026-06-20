from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from vibecomfy.errors import QueueError
from vibecomfy.workflow import VibeWorkflow

from .attempt import build_attempt_bundle, write_attempt_json
from .client import ComfyClient
from .execution import normalize_prompt_id
from .drift import enforce_strict_drift
from vibecomfy.utils import atomic_write_json
from .model_policy import apply_model_preflight, resolve_model_preflight_policy
from .server import comfy_server
from .session import (
    EmbeddedSession,
    RunResult,
    SessionConfig,
    _build_schema_provider,
    _collect_output_paths,
    _configured_output_directory,
    _embedded_configuration,
    _outputs_from_server_history,
    _prepare_prompt_async,
    _run_metadata,
    _schema_warn_only,
    _wait_for_server_history,
    _workflow_queue_failure_message,
)

logger = logging.getLogger(__name__)


def _allocate_run_dir(prefix: str) -> tuple[str, Path]:
    """Allocate a collision-resistant run directory.

    Returns ``(run_id, run_dir)`` where *run_id* carries a stable *prefix*
    and a unique suffix (timestamp + uuid4 hex).  The directory is created
    with ``parents=True, exist_ok=False`` so that a coincident collision
    raises ``FileExistsError`` instead of silently sharing a directory.
    """
    run_id = f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    run_dir = Path("out/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


async def run(
    workflow: VibeWorkflow,
    *,
    server_url: str | None = None,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_models: bool = False,
    shared_models_root: str | Path | None = None,
    strict_drift: bool | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
) -> RunResult:
    run_id, run_dir = _allocate_run_dir("run")
    log_path = run_dir / "comfy.log"
    resolved_config = config or SessionConfig.from_workflow_metadata(workflow)
    managed_config = resolved_config if server_url is None else None
    policy = resolve_model_preflight_policy(
        mode="managed_local_server" if server_url is None else "explicit_remote_server_unverified",
        ensure_models=ensure_models,
        shared_root=shared_models_root,
    )
    apply_model_preflight(workflow, policy)
    async with comfy_server(server_url=server_url, log_path=log_path, config=managed_config) as active_url:
        provider = _build_schema_provider(active_url)
        warned = {"emitted": False}

        def on_unavailable(msg: str) -> None:
            if warned["emitted"] and "schema validation skipped for class types" not in msg:
                return
            logger.log(logging.WARNING if _schema_warn_only(resolved_config) else logging.ERROR, "vibecomfy schema gate: %s", msg)
            warned["emitted"] = True

        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=provider,
            on_unavailable=on_unavailable,
        )
        schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
        # Write attempt.json BEFORE every queue boundary.
        attempt_bundle = build_attempt_bundle(workflow, api_dict, backend=backend, config=managed_config)
        write_attempt_json(run_dir, attempt_bundle)
        resolved_strict = strict_drift if strict_drift is not None else bool(resolved_config.strict_drift)
        if resolved_strict:
            enforce_strict_drift(workflow)
        try:
            queued = await ComfyClient(active_url).queue_prompt(api_dict)
        except Exception as exc:
            raise QueueError(
                _workflow_queue_failure_message(workflow, exc),
                next_action="vibecomfy runtime doctor",
            ) from exc
        prompt_id = normalize_prompt_id(queued)
        history = await _wait_for_server_history(active_url, prompt_id, config=resolved_config)
        comfy_outputs = _outputs_from_server_history(history, prompt_id)
        outputs = _collect_output_paths(
            comfy_outputs,
            output_directory=_configured_output_directory(resolved_config),
        )
    metadata = _run_metadata(
        run_id=run_id,
        workflow=workflow,
        api_dict=api_dict,
        queued=queued,
        comfy_outputs=comfy_outputs,
        outputs=outputs,
        runtime="server",
        config=managed_config,
        schema_validation_skipped=schema_validation_skipped,
        chain_id=chain_id,
        parent_run_id=parent_run_id,
    )
    metadata_path = atomic_write_json(run_dir / "metadata.json", metadata)
    return RunResult(
        run_id=run_id,
        prompt_id=prompt_id,
        outputs=outputs,
        metadata_path=str(metadata_path),
        log_path=str(log_path),
    )


def run_sync(
    workflow: VibeWorkflow,
    *,
    server_url: str | None = None,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_models: bool = False,
    shared_models_root: str | Path | None = None,
    strict_drift: bool | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
) -> RunResult:
    return asyncio.run(
        run(
            workflow,
            server_url=server_url,
            backend=backend,
            config=config,
            ensure_models=ensure_models,
            shared_models_root=shared_models_root,
            strict_drift=strict_drift,
            chain_id=chain_id,
            parent_run_id=parent_run_id,
        )
    )


async def run_embedded(
    workflow: VibeWorkflow,
    *,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_packs: bool = False,
    ensure_models: bool = False,
    strict_drift: bool | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
) -> RunResult:
    session = EmbeddedSession(config or SessionConfig.from_workflow_metadata(workflow))
    try:
        return await session.run(
            workflow,
            backend=backend,
            ensure_packs=ensure_packs,
            ensure_models=ensure_models,
            strict_drift=strict_drift,
            chain_id=chain_id,
            parent_run_id=parent_run_id,
        )
    finally:
        await session.stop()


def run_embedded_sync(
    workflow: VibeWorkflow,
    *,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_packs: bool = False,
    ensure_models: bool = False,
    strict_drift: bool | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
) -> RunResult:
    return asyncio.run(
        run_embedded(
            workflow,
            backend=backend,
            config=config,
            ensure_packs=ensure_packs,
            ensure_models=ensure_models,
            strict_drift=strict_drift,
            chain_id=chain_id,
            parent_run_id=parent_run_id,
        )
    )


async def smoke_runtime(*, server_url: str | None = None) -> dict[str, Any]:
    run_id, run_dir = _allocate_run_dir("smoke")
    log_path = run_dir / "comfy.log"
    async with comfy_server(server_url=server_url, log_path=log_path) as active_url:
        client = ComfyClient(active_url)
        objects = await client.object_info()
    return {
        "run_id": run_id,
        "server_url": server_url or "managed",
        "node_count": len(objects),
        "log_path": str(log_path),
    }


def smoke_runtime_sync(*, server_url: str | None = None) -> dict[str, Any]:
    return asyncio.run(smoke_runtime(server_url=server_url))
