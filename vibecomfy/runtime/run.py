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
from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundle, WorkflowBundleError

from .attempt import build_attempt_bundle, write_attempt_json
from .client import ComfyClient
from .execution import queue_server_prompt
from .drift import enforce_strict_drift
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
    _begin_runtime_lifecycle,
    _commit_queue_witness,
    _complete_runtime_run,
    _persist_runtime_evidence,
    _persist_runtime_failure,
    _runtime_evidence,
    _run_metadata,
    _schema_provider_provenance,
    _schema_warn_only,
    _terminal_event_already_written,
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
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
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
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime run requires an ApprovedProjectionRecord and WorkflowBundle")
    workflow = bundle.workflow
    run_id, run_dir = _allocate_run_dir("run")
    log_path = run_dir / "comfy.log"
    resolved_config = config or SessionConfig.from_workflow_metadata(workflow)
    managed_config = resolved_config if server_url is None else None
    policy = resolve_model_preflight_policy(
        mode="managed_local_server" if server_url is None else "explicit_remote_server_unverified",
        ensure_models=ensure_models,
        shared_root=shared_models_root,
    )
    async with comfy_server(server_url=server_url, log_path=log_path, config=managed_config) as active_url:
        adapter_kind = "managed" if server_url is None else "external"
        attempt_bundle, journal_state, journal_generation, initial_evidence = _begin_runtime_lifecycle(
            run_dir=run_dir,
            run_id=run_id,
            record=record,
            adapter_kind=adapter_kind,
            backend=backend,
            endpoint=active_url,
        )
        schema_provenance = _schema_provider_provenance(None)
        queue_acceptance = {"status": "not_attempted", "prompt_id": None}
        warned = {"emitted": False}
        phase = "schema"
        failure_exc: BaseException | None = None

        def on_unavailable(msg: str) -> None:
            if warned["emitted"] and "schema validation skipped for class types" not in msg:
                return
            logger.log(logging.WARNING if _schema_warn_only(resolved_config) else logging.ERROR, "vibecomfy schema gate: %s", msg)
            warned["emitted"] = True

        try:
            apply_model_preflight(workflow, policy)
            provider = _build_schema_provider(active_url)
            api_dict = await _prepare_prompt_async(
                record,
                bundle,
                backend=backend,
                schema_provider=provider,
                on_unavailable=on_unavailable,
            )
            schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
            schema_provenance = dict(getattr(api_dict, "schema_provenance", {})) or _schema_provider_provenance(provider)
            evidence = _runtime_evidence(
                record,
                adapter_kind=adapter_kind,
                backend=backend,
                endpoint=active_url,
                schema_provenance=schema_provenance,
                queue_acceptance=queue_acceptance,
                terminal={"phase": "prepared", "reason_type": "none", "reason": None, "acceptance_known": False},
            )
            attempt_bundle = build_attempt_bundle(
                bundle,
                record,
                backend=backend,
                config=managed_config,
                adapter_kind=adapter_kind,
                adapter_endpoint=active_url,
                schema_provenance=schema_provenance,
                runtime_evidence=evidence,
            )
            _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
            phase = "drift"
            resolved_strict = strict_drift if strict_drift is not None else bool(resolved_config.strict_drift)
            if resolved_strict:
                enforce_strict_drift(workflow)
            phase = "queue"
            try:
                queued = (
                    await queue_server_prompt(record, bundle, client=ComfyClient(active_url))
                ).queued
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                raise QueueError(
                    _workflow_queue_failure_message(workflow, exc), next_action="vibecomfy runtime doctor"
                ) from exc
            phase = "acceptance_witness"
            prompt_id = _commit_queue_witness(
                run_dir=run_dir, attempt_bundle=attempt_bundle, journal_state=journal_state,
                run_id=run_id, record=record, journal_generation=journal_generation,
                adapter_kind=adapter_kind, backend=backend, endpoint=active_url,
                schema_provenance=schema_provenance, queued=queued,
            )
            queue_acceptance = {"status": "accepted", "prompt_id": prompt_id}
            phase = "history"
            history = await _wait_for_server_history(active_url, prompt_id, config=resolved_config)
            comfy_outputs = _outputs_from_server_history(history, prompt_id)
            phase = "output"
            outputs = _collect_output_paths(
                comfy_outputs,
                output_directory=_configured_output_directory(resolved_config),
            )
            phase = "metadata"
            metadata = _run_metadata(
                run_id=run_id,
                bundle=bundle,
                record=record,
                queued=queued,
                comfy_outputs=comfy_outputs,
                outputs=outputs,
                runtime=adapter_kind,
                config=managed_config,
                schema_validation_skipped=schema_validation_skipped,
                schema_provenance=schema_provenance,
                adapter_endpoint=active_url,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
            )
            metadata_path = _complete_runtime_run(
                run_dir=run_dir, attempt_bundle=attempt_bundle, journal_state=journal_state,
                run_id=run_id, record=record, journal_generation=journal_generation,
                adapter_kind=adapter_kind, backend=backend, endpoint=active_url,
                schema_provenance=schema_provenance, queue_acceptance=queue_acceptance,
                metadata=metadata,
            )
            return RunResult(
                run_id=run_id,
                prompt_id=prompt_id,
                outputs=outputs,
                metadata_path=str(metadata_path),
                log_path=str(log_path),
            )
        except asyncio.CancelledError as exc:
            failure_exc, failure_event, failure_interrupted = exc, "superseded", True
        except KeyboardInterrupt as exc:
            failure_exc, failure_event, failure_interrupted = exc, "superseded", True
        except Exception as exc:
            failure_exc, failure_event, failure_interrupted = exc, "discarded", False
        if failure_exc is not None:
            if _terminal_event_already_written(run_dir, record, journal_generation):
                raise failure_exc
            if phase in {"queue", "acceptance_witness", "history", "output", "metadata"} and queue_acceptance["status"] == "not_attempted":
                queue_acceptance = {"status": "unknown", "prompt_id": None}
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                event_type=failure_event, original_error=failure_exc, queue_acceptance=queue_acceptance,
                phase=phase, exc=failure_exc, interrupted=failure_interrupted,
            )
            raise failure_exc


def run_sync(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
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
            record,
            bundle,
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
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_packs: bool = False,
    ensure_models: bool = False,
    strict_drift: bool | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
) -> RunResult:
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime run requires an ApprovedProjectionRecord and WorkflowBundle")
    session = EmbeddedSession(config or SessionConfig.from_workflow_metadata(bundle.workflow))
    try:
        return await session.run(
            record,
            bundle,
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
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
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
            record,
            bundle,
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
