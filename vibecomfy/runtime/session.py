from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shlex
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol

from vibecomfy.comfy_command import comfyui_command
from vibecomfy.errors import (
    MODEL_DOCTOR_NEXT_ACTION,
    ModelAssetError,
    QueueError,
    RuntimeNodeError,
    RuntimeStartupError,
    SchemaValidationError,
    VibeComfyError,
)
from vibecomfy.memory_profile import MemoryProfile, apply_memory_profile_overrides
from vibecomfy.utils import atomic_write_json, find_repo_root
from vibecomfy.workflow import VibeWorkflow

from .attempt import build_attempt_bundle, build_shared_fields, write_attempt_json
from .client import ComfyClient
from .drift import enforce_strict_drift
from .execution import normalize_prompt_id
from .model_policy import apply_model_preflight, resolve_model_preflight_policy
from .watchdog import Watchdog, write_report

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from comfy.cli_args_types import Configuration
else:
    Configuration = Any


OVERRIDES_INCLUDE: set[str] = set()
OVERRIDES_EXCLUDE: set[str] = set()


def _workflow_queue_failure_message(workflow: VibeWorkflow, exc: Exception) -> str:
    mapping = workflow.id_map()
    metadata_id_map = workflow.metadata.get("id_map")
    if isinstance(metadata_id_map, dict):
        mapping.update({str(key): str(value) for key, value in metadata_id_map.items()})
    for node_id, node in workflow.nodes.items():
        source_id = node.metadata.get("source_id")
        if source_id is not None:
            mapping[str(source_id)] = str(node_id)
    return f"Workflow queue failed: {exc}; id_map={mapping}"


def _schema_warn_only(config: SessionConfig | None = None) -> bool:
    if os.environ.get("VIBECOMFY_SCHEMA_WARN_ONLY") == "1":
        return True
    return bool(config is not None and config.extra.get("quiet_schema_degradation") is True)


def _schema_skipped_class_types(api_dict: Mapping[str, Any]) -> list[str]:
    return sorted({
        str(node.get("class_type"))
        for node in api_dict.values()
        if isinstance(node, Mapping) and node.get("class_type")
    })


def _node_packs_from_requirements(workflow: VibeWorkflow):
    from vibecomfy.node_packs import get_known_node_packs, resolve_node_packs

    required = set(workflow.requirements.custom_nodes)
    packs = [pack for pack in get_known_node_packs() if pack.name in required]
    if packs:
        return packs
    class_types = {node.class_type for node in workflow.nodes.values()}
    return resolve_node_packs(class_types)


def _model_assets_from_workflow(workflow: VibeWorkflow) -> list[dict[str, str]]:
    from vibecomfy.model_assets import (
        _asset_entry_key,
        _looks_like_runtime_input,
        _normalise_requirement_entries,
        resolve_referenced_assets,
    )

    def _norm(value: str) -> str:
        return value.replace("\\", "/")

    def _entry_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
        name, subdir, target_marker = _asset_entry_key(entry)
        return _norm(name), _norm(subdir), target_marker

    raw_assets = workflow.metadata.get("model_assets", [])
    authored = _normalise_requirement_entries(raw_assets) if isinstance(raw_assets, list) else []
    resolved, unresolved = resolve_referenced_assets(workflow)
    authored_keys = {
        _entry_key(entry)
        for entry in authored
        if isinstance(entry.get("name"), str) and isinstance(entry.get("subdir"), str)
    }
    authored_paths = {
        f"{_norm(entry['subdir'])}/{_norm(entry['name'])}"
        for entry in authored
        if isinstance(entry.get("name"), str) and isinstance(entry.get("subdir"), str)
    }
    unresolved = [
        item
        for item in unresolved
        if not _looks_like_runtime_input(item["value"])
        and (_norm(item["value"]), _norm(item["subdir"])) not in authored_keys
        and (Path(_norm(item["value"])).name, _norm(item["subdir"])) not in authored_keys
        and f"{_norm(item['subdir'])}/{_norm(item['value'])}" not in authored_paths
    ]
    if unresolved:
        summary = ", ".join(
            f"{item['class_type']} {item['node_id']}.{item['field']}={item['value']!r}"
            for item in unresolved[:8]
        )
        more = "" if len(unresolved) <= 8 else f" (+{len(unresolved) - 8} more)"
        raise ModelAssetError(
            f"unresolved workflow model assets: {summary}{more}",
            next_action=MODEL_DOCTOR_NEXT_ACTION,
        )
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in [*authored, *resolved]:
        key = _entry_key(entry)
        if not isinstance(entry.get("name"), str) or not isinstance(entry.get("subdir"), str):
            # Keep malformed authored metadata visible to the fetch owner;
            # do not let a truthiness fallback or this merge hide it.
            entries.append(entry)
            continue
        if key not in authored_keys and f"{_norm(entry['subdir'])}/{_norm(entry['name'])}" in authored_paths:
            continue
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    return entries


@dataclass(slots=True)
class RunResult:
    run_id: str
    prompt_id: str | None
    outputs: list[str]
    metadata_path: str
    log_path: str


class PreparedPrompt(dict):
    def __init__(
        self,
        api_dict: dict[str, Any],
        *,
        schema_validation_skipped: list[str] | None = None,
        normalization: Any | None = None,
    ) -> None:
        super().__init__(api_dict)
        self.schema_validation_skipped = schema_validation_skipped or []
        #: Applied-and-approved normalization proposal (evidence); None when no
        #: normalization was needed or approved.
        self.normalization = normalization


@dataclass(slots=True)
class SessionConfig:
    memory_profile: MemoryProfile | None = None
    vram_policy: str = "auto"
    reserve_vram_gb: float | None = None
    cache_policy: str = "smart"
    disable_smart_memory: bool = False
    warm_policy: str = "auto"
    auto_flush_vram_threshold_gb: float = 2.0
    port: int | None = None
    strict_drift: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "SessionConfig":
        kwargs, extra = _partition_comfy_config(values)
        return cls(**kwargs, extra=extra)

    @classmethod
    def from_workflow_metadata(cls, workflow: VibeWorkflow) -> "SessionConfig":
        values = workflow.metadata.get("comfy_configuration", {})
        if not isinstance(values, dict):
            values = {}
        return cls.from_dict(values)


def apply_memory_profile_override(
    config: SessionConfig,
    memory_profile: int | MemoryProfile,
) -> SessionConfig:
    profile = MemoryProfile.parse(memory_profile)
    resolved = apply_memory_profile_overrides(config, profile, precedence="profile")
    return replace(resolved, memory_profile=profile)


class VibeSession(Protocol):
    config: SessionConfig
    last_fingerprint: tuple[Any, ...] | None

    async def start(self) -> None:
        ...

    async def run(
        self,
        workflow: VibeWorkflow,
        *,
        backend: str = "api",
        strict_drift: bool | None = None,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> RunResult:
        ...

    async def flush(self) -> None:
        ...

    async def reconfigure(self, config: SessionConfig) -> Any:
        ...

    async def stop(self, wait_for_inflight: bool = True) -> None:
        ...


def _allocate_request_root(prefix: str) -> tuple[str, Path]:
    runs_root = Path("out/runs")
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=runs_root))
    return run_dir.name, run_dir


class EmbeddedSession:
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self._context: Any | None = None
        self._comfy: Any | None = None
        self._schema_provider: Any | None = None
        self._schema_warning_emitted = False
        self._inflight_run: asyncio.Task[Any] | None = None

    def _on_schema_unavailable(self, msg: str) -> None:
        if self._schema_warning_emitted and "schema validation skipped for class types" not in msg:
            return
        level = logging.WARNING if _schema_warn_only(self.config) else logging.ERROR
        logger.log(level, "vibecomfy schema gate: %s", msg)
        self._schema_warning_emitted = True

    async def start(self) -> None:
        if self._comfy is not None:
            return
        from comfy.client.embedded_comfy_client import Comfy

        self._context = Comfy(configuration=_embedded_configuration_for_session(self.config))
        self._comfy = await self._context.__aenter__()

    async def run(
        self,
        workflow: VibeWorkflow,
        *,
        backend: str = "api",
        ensure_packs: bool = False,
        ensure_models: bool = False,
        strict_drift: bool | None = None,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        normalize_approval: Any | None = None,
    ) -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
        if ensure_packs:
            from vibecomfy.custom_node_refs import check_pack_pin_compatibility
            from vibecomfy.node_packs import install_required_packs, missing_packs_for_workflow
            from vibecomfy.node_packs import read_lockfile

            lockfile_entries = read_lockfile()
            pin_issues = check_pack_pin_compatibility(workflow, lockfile_entries)
            pin_errors = [issue.message for issue in pin_issues if issue.severity == "error"]
            if pin_errors:
                raise RuntimeError("ensure_packs: " + "; ".join(pin_errors))
            # Dev convenience only; production should pre-stage nodepacks with `vibecomfy nodes ensure`.
            try:
                packs, _unresolved = missing_packs_for_workflow(workflow)
            except FileNotFoundError:
                packs = _node_packs_from_requirements(workflow)
                if not packs:
                    logger.warning(
                        "ensure_packs: node index unavailable and workflow declares no custom nodes; continuing"
                    )
                    packs = []
                else:
                    logger.warning(
                        "ensure_packs: node index unavailable; falling back to workflow requirements: %s",
                        ", ".join(pack.name for pack in packs),
                    )
            except ValueError as exc:
                raise RuntimeError("ensure_packs: " + str(exc)) from exc
            if packs:
                lock_entries = {entry.name: entry for entry in lockfile_entries}
                batch = install_required_packs(
                    packs,
                    restore_entries=[entry for pack in packs if (entry := lock_entries.get(pack.name)) is not None],
                )
                if not batch.ok:
                    errors = [
                        f"{result.name}: {result.error or result.status}"
                        for result in batch.results
                        if result.status not in {"installed", "refreshed"}
                    ]
                    if not errors and batch.preflight.error:
                        errors.append(batch.preflight.error)
                    raise RuntimeError("ensure_packs: install failed: " + "; ".join(errors))
                await self.reload_for_nodepack_change(reason="ensure_packs")
        if ensure_models:
            policy = resolve_model_preflight_policy(mode="embedded", ensure_models=True)
            apply_model_preflight(workflow, policy)
        task = asyncio.current_task()
        self._inflight_run = task
        try:
            resolved_strict = strict_drift if strict_drift is not None else self.config.strict_drift
            untracked_kwargs: dict[str, Any] = {}
            if normalize_approval is not None:
                untracked_kwargs["normalize_approval"] = normalize_approval
            return await self._run_untracked(
                workflow,
                backend=backend,
                strict_drift=resolved_strict,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                **untracked_kwargs,
            )
        finally:
            if self._inflight_run is task:
                self._inflight_run = None

    async def _run_untracked(
        self,
        workflow: VibeWorkflow,
        *,
        backend: str = "api",
        strict_drift: bool = False,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        normalize_approval: Any | None = None,
    ) -> RunResult:
        total_start = time.monotonic()
        timings: dict[str, float] = {}
        phase_start = time.monotonic()
        await self.start()
        timings["session_start_sec"] = round(time.monotonic() - phase_start, 3)
        assert self._comfy is not None
        if self._schema_provider is None:
            self._schema_provider = _build_schema_provider(None)
        phase_start = time.monotonic()
        prepare_kwargs: dict[str, Any] = {}
        if normalize_approval is not None:
            prepare_kwargs["normalize_approval"] = normalize_approval
        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=self._schema_provider,
            on_unavailable=self._on_schema_unavailable,
            **prepare_kwargs,
        )
        schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
        normalization = getattr(api_dict, "normalization", None)
        timings["prepare_prompt_sec"] = round(time.monotonic() - phase_start, 3)
        fp = model_fingerprint(api_dict)

        phase_start = time.monotonic()
        await _maybe_flush_for_policy(self, fp)
        timings["memory_policy_sec"] = round(time.monotonic() - phase_start, 3)

        run_id, run_dir = _allocate_request_root("run")
        log_path = run_dir / "embedded.log"

        # Embedded backend: comfy_kitchen does not necessarily expose a server
        # WebSocket. The watchdog will record connection_state=never_connected
        # in that case but VRAM-sampling and timeout-detection still work via
        # /system_stats if the embedded backend exposes one. We pass the local
        # loopback URL with whatever port the SessionConfig requests; if the
        # endpoint is unreachable the watchdog handles it gracefully.
        client_id = uuid.uuid4().hex
        ws_url = _embedded_observation_url(self.config)
        watchdog = await _start_watchdog(server_url=ws_url, client_id=client_id, api_dict=api_dict)
        stop_reason: str | None = None
        phase_start = time.monotonic()
        try:
            try:
                # Write attempt.json BEFORE every queue boundary.
                attempt_bundle = build_attempt_bundle(workflow, api_dict, backend=backend, config=self.config)
                write_attempt_json(run_dir, attempt_bundle)
                if strict_drift:
                    enforce_strict_drift(workflow)
                queued = await self._comfy.queue_prompt_api(api_dict)
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                raise
            except Exception as exc:
                stop_reason = "exception"
                raise QueueError(
                    _workflow_queue_failure_message(workflow, exc),
                    next_action="vibecomfy runtime doctor",
                ) from exc

            prompt_id = normalize_prompt_id(queued)
            _set_watchdog_prompt_id(watchdog, prompt_id)
            timings["queue_prompt_sec"] = round(time.monotonic() - phase_start, 3)
            phase_start = time.monotonic()
            comfy_outputs = _decode_terminal_result(
                queued,
                prompt_id=prompt_id,
                status_required=False,
                allow_list_outputs=True,
            )
            outputs = _collect_output_paths(
                comfy_outputs,
                output_directory=_configured_output_directory(self.config),
            )
            timings["collect_outputs_sec"] = round(time.monotonic() - phase_start, 3)
            stop_reason = "completed"
        except asyncio.TimeoutError:
            stop_reason = "timeout"
            raise
        except RuntimeNodeError:
            stop_reason = "errored"
            raise
        except Exception:
            if stop_reason is None:
                stop_reason = "exception"
            raise
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason or "exception")
        timings["total_inside_vibecomfy_sec"] = round(time.monotonic() - total_start, 3)
        metadata = _run_metadata(
            run_id=run_id,
            workflow=workflow,
            api_dict=api_dict,
            queued=queued,
            comfy_outputs=comfy_outputs,
            outputs=outputs,
            runtime="embedded",
            config=self.config,
            timings=timings,
            schema_validation_skipped=schema_validation_skipped,
            normalization=normalization,
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

    async def flush(self) -> None:
        if self._comfy is None:
            return
        await self._comfy.clear_cache()

    async def reconfigure(self, config: SessionConfig) -> Any:
        self.config = config
        if self._comfy is None:
            return None
        return await self._comfy.reconfigure(_embedded_configuration_for_session(config))

    async def stop(self, wait_for_inflight: bool = True) -> None:
        await _resolve_inflight_before_stop(self, wait_for_inflight)
        if self._context is None:
            return
        try:
            await self._context.__aexit__(None, None, None)
        except Exception as exc:
            if not _is_benign_embedded_cleanup_exception(exc):
                raise
            logger.warning("embedded Comfy cleanup raised after run completion; ignoring: %s", exc)
        finally:
            self._context = None
            self._comfy = None

    async def reload_for_nodepack_change(self, *, reason: str) -> None:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("reload_for_nodepack_change refused: run in flight")
        logger.info("reload_for_nodepack_change: %s", reason)
        if self._context is not None:
            try:
                await self._context.__aexit__(None, None, None)
            except Exception as exc:
                if not _is_benign_embedded_cleanup_exception(exc):
                    raise
                logger.warning("embedded Comfy cleanup raised during reload; ignoring: %s", exc)
        self._comfy = None
        self._context = None
        self._schema_provider = None
        self._schema_warning_emitted = False
        self.last_fingerprint = None
        await self.start()


class ServerSession:
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.url: str | None = None
        self.log_handle: Any | None = None
        self._argv = _comfy_server_argv(self.config)
        self._schema_provider: Any | None = None
        self._schema_warning_emitted = False
        self._inflight_run: asyncio.Task[Any] | None = None

    def _on_schema_unavailable(self, msg: str) -> None:
        if self._schema_warning_emitted and "schema validation skipped for class types" not in msg:
            return
        level = logging.WARNING if _schema_warn_only(self.config) else logging.ERROR
        logger.log(level, "vibecomfy schema gate: %s", msg)
        self._schema_warning_emitted = True

    async def start(self) -> None:
        if self.process is not None and self.process.returncode is None:
            return
        if self.process is not None:
            await self.stop()
        self.process, self.url, self.log_handle = await _spawn_comfy_server(
            self.config,
            log_path=self.config.extra.get("server_log_path"),
        )
        self._argv = _comfy_server_argv(self.config)

    async def run(
        self,
        workflow: VibeWorkflow,
        *,
        backend: str = "api",
        ensure_models: bool = False,
        shared_models_root: str | Path | None = None,
        strict_drift: bool | None = None,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        normalize_approval: Any | None = None,
    ) -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
        policy = resolve_model_preflight_policy(
            mode="managed_local_server",
            ensure_models=ensure_models,
            shared_root=shared_models_root,
        )
        apply_model_preflight(workflow, policy)
        task = asyncio.current_task()
        self._inflight_run = task
        try:
            resolved_strict = strict_drift if strict_drift is not None else self.config.strict_drift
            untracked_kwargs: dict[str, Any] = {}
            if normalize_approval is not None:
                untracked_kwargs["normalize_approval"] = normalize_approval
            return await self._run_untracked(
                workflow,
                backend=backend,
                strict_drift=resolved_strict,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                **untracked_kwargs,
            )
        finally:
            if self._inflight_run is task:
                self._inflight_run = None

    async def _run_untracked(
        self,
        workflow: VibeWorkflow,
        *,
        backend: str = "api",
        strict_drift: bool = False,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        normalize_approval: Any | None = None,
    ) -> RunResult:
        total_start = time.monotonic()
        timings: dict[str, float] = {}
        phase_start = time.monotonic()
        await self.start()
        timings["session_start_sec"] = round(time.monotonic() - phase_start, 3)
        assert self.url is not None
        if self._schema_provider is None:
            self._schema_provider = _build_schema_provider(self.url)
        phase_start = time.monotonic()
        prepare_kwargs: dict[str, Any] = {}
        if normalize_approval is not None:
            prepare_kwargs["normalize_approval"] = normalize_approval
        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=self._schema_provider,
            on_unavailable=self._on_schema_unavailable,
            **prepare_kwargs,
        )
        schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
        normalization = getattr(api_dict, "normalization", None)
        timings["prepare_prompt_sec"] = round(time.monotonic() - phase_start, 3)
        fp = model_fingerprint(api_dict)

        phase_start = time.monotonic()
        await _maybe_flush_for_policy(self, fp)
        timings["memory_policy_sec"] = round(time.monotonic() - phase_start, 3)

        run_id, run_dir = _allocate_request_root("run")
        log_path = run_dir / "comfy.log"

        client_id = uuid.uuid4().hex
        watchdog = await _start_watchdog(server_url=self.url, client_id=client_id, api_dict=api_dict)
        stop_reason: str | None = None
        phase_start = time.monotonic()
        try:
            try:
                # Write attempt.json BEFORE every queue boundary.
                attempt_bundle = build_attempt_bundle(workflow, api_dict, backend=backend, config=self.config)
                write_attempt_json(run_dir, attempt_bundle)
                if strict_drift:
                    enforce_strict_drift(workflow)
                queued = await ComfyClient(self.url).queue_prompt(api_dict)
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                raise
            except Exception as exc:
                stop_reason = "exception"
                raise QueueError(
                    _workflow_queue_failure_message(workflow, exc),
                    next_action="vibecomfy runtime doctor",
                ) from exc

            prompt_id = normalize_prompt_id(queued)
            if not prompt_id:
                raise QueueError(
                    "Comfy queue response did not include a prompt_id; cannot retrieve terminal result",
                    next_action="vibecomfy runtime doctor",
                )
            _set_watchdog_prompt_id(watchdog, prompt_id)
            timings["queue_prompt_sec"] = round(time.monotonic() - phase_start, 3)
            self.last_fingerprint = fp

            phase_start = time.monotonic()
            history = await _wait_for_server_history(self.url, prompt_id, config=self.config)
            comfy_outputs = _outputs_from_server_history(history, prompt_id)
            outputs = _collect_output_paths(
                comfy_outputs,
                output_directory=_configured_output_directory(self.config),
            )
            timings["collect_outputs_sec"] = round(time.monotonic() - phase_start, 3)
            stop_reason = "completed"
        except asyncio.TimeoutError:
            stop_reason = "timeout"
            raise
        except RuntimeNodeError:
            stop_reason = "errored"
            raise
        except Exception:
            if stop_reason is None:
                stop_reason = "exception"
            raise
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason or "exception")

        timings["total_inside_vibecomfy_sec"] = round(time.monotonic() - total_start, 3)
        metadata = _run_metadata(
            run_id=run_id,
            workflow=workflow,
            api_dict=api_dict,
            queued=queued,
            comfy_outputs=comfy_outputs,
            outputs=outputs,
            runtime="server",
            config=self.config,
            timings=timings,
            schema_validation_skipped=schema_validation_skipped,
            normalization=normalization,
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

    async def flush(self) -> None:
        await self.start()
        assert self.url is not None
        await ComfyClient(self.url).free(unload_models=True, free_memory=True)

    async def reconfigure(self, config: SessionConfig) -> bool:
        new_argv = _comfy_server_argv(config)
        if new_argv == self._argv:
            self.config = config
            return False
        await self.stop()
        self.config = config
        self._argv = new_argv
        await self.start()
        return True

    async def stop(self, wait_for_inflight: bool = True) -> None:
        await _resolve_inflight_before_stop(self, wait_for_inflight)
        process = self.process
        if process is not None and process.returncode is None:
            await _stop_managed_process(process)
        elif process is not None:
            await process.wait()
        if self.log_handle:
            self.log_handle.close()
        self.process = None
        self.url = None
        self.log_handle = None

    async def reload_for_nodepack_change(self, *, reason: str) -> None:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("reload_for_nodepack_change refused: run in flight")
        # NOTE: ServerSession external-mode handling (attach to a server VibeComfy didn't spawn) is deferred to MP-5 alongside session-shared multi-stage orchestration. Current production paths route external server URLs through comfy_server(server_url=...) in vibecomfy/runtime/server.py, which already skips spawn/cleanup for external URLs.
        await self.stop()
        await self.start()
        logger.info("reload_for_nodepack_change: %s", reason)


async def _resolve_inflight_before_stop(session: Any, wait_for_inflight: bool) -> None:
    task = getattr(session, "_inflight_run", None)
    if task is None:
        return
    if task.done():
        session._inflight_run = None
        return
    if not wait_for_inflight:
        raise RuntimeError(
            "session.stop() called while a run is in flight; pass wait_for_inflight=True or call after run completes"
        )
    if task is asyncio.current_task():
        raise RuntimeError("session.stop() called from the in-flight run; call after run completes")
    try:
        await task
    except BaseException:
        session._inflight_run = None
        raise
    session._inflight_run = None


def active_session_metadata(id: str = "default") -> dict[str, Any] | None:
    session_dir = Path("out/sessions") / id
    revision_path = session_dir / "source_revision"

    if not _session_ready(session_dir):
        # Process may be alive but unhealthy — attempt graceful termination
        pid_path = session_dir / "pid"
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text(encoding="utf-8").strip())
                os.kill(pid, 0)
                _terminate_session_pid(pid, session_dir=session_dir)
            except (ProcessLookupError, PermissionError, OSError, ValueError):
                pass
        _cleanup_session_files(session_dir)
        return None

    # Read pid and url safely (we know they exist from _session_ready)
    try:
        pid = int((session_dir / "pid").read_text(encoding="utf-8").strip())
        url = (session_dir / "url").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        _cleanup_session_files(session_dir)
        return None

    if not url:
        _cleanup_session_files(session_dir)
        return None

    # source_revision is advisory diagnostic metadata only and must
    # never influence session liveness (SD2).
    current_revision = current_source_revision()
    session_revision: str | None = None
    if revision_path.exists():
        try:
            session_revision = revision_path.read_text(encoding="utf-8").strip()
        except OSError:
            session_revision = None

    config = _read_session_config(session_dir)
    result: dict[str, Any] = {
        "id": id,
        "pid": pid,
        "url": url,
        "config": config,
        "models_root": config.get("models_root"),
        "models_root_normalized": config.get("models_root_normalized"),
        "locality": config.get("locality"),
    }
    if session_revision is not None:
        result["launch_source_revision"] = session_revision
    if current_revision is not None:
        result["current_source_revision"] = current_revision
    return result


def find_active_session(id: str = "default") -> str | None:
    metadata = active_session_metadata(id)
    return str(metadata["url"]) if metadata else None


def _read_session_config(session_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((session_dir / "config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _session_url_healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/system_stats", timeout=2) as response:
            if response.status != 200:
                return False
            json.loads(response.read())
            return True
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        return False


def _session_ready(session_dir: Path) -> bool:
    """Shared session readiness: daemon-written pid + url exist and /system_stats returns HTTP 200 with valid JSON."""
    pid_path = session_dir / "pid"
    url_path = session_dir / "url"

    if not pid_path.exists() or not url_path.exists():
        return False

    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        url = url_path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return False

    if not url:
        return False

    launch_marker = _read_launch_marker(session_dir)
    if launch_marker is not None:
        if launch_marker.get("pid") != pid or launch_marker.get("url") != url:
            return False
        if not isinstance(launch_marker.get("launch_token"), str):
            return False

    # Check process is alive (PermissionError is inconclusive — fall through to HTTP check)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except OSError:
        return False

    if launch_marker is not None and not _session_ownership_verified(session_dir, pid):
        return False
    return _session_url_healthy(url)


def _read_launch_marker(session_dir: Path) -> dict[str, Any] | None:
    try:
        marker = json.loads((session_dir / "launch.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return marker if isinstance(marker, dict) else None


def _process_start_identity(pid: int) -> str | None:
    """Return an OS-provided process incarnation value, or fail closed."""
    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        raw = proc_stat.read_text(encoding="utf-8")
    except OSError:
        raw = ""
    if raw:
        closing_paren = raw.rfind(")")
        fields = raw[closing_paren + 2 :].split() if closing_paren >= 0 else []
        if len(fields) > 19:
            return fields[19]

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def _process_commandline(pid: int) -> tuple[str, ...] | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        raw = b""
    if raw:
        return tuple(part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part)
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout
    if not output or "\x00" in output or len(output.splitlines()) != 1:
        return None
    try:
        commandline = tuple(shlex.split(output, comments=False, posix=True))
    except ValueError:
        return None
    launch_flag_positions = [
        index for index, argument in enumerate(commandline) if argument == "--launch-token"
    ]
    if launch_flag_positions and (
        len(launch_flag_positions) != 1
        or launch_flag_positions[0] + 1 >= len(commandline)
    ):
        return None
    return commandline or None


def _launch_token_is_exactly_paired(commandline: tuple[str, ...], token: str) -> bool:
    """Return whether *token* is the sole exact ``--launch-token`` value."""
    flag_positions = [
        index for index, argument in enumerate(commandline) if argument == "--launch-token"
    ]
    if len(flag_positions) != 1:
        return False
    flag_index = flag_positions[0]
    return flag_index + 1 < len(commandline) and commandline[flag_index + 1] == token


def _session_ownership_verified(session_dir: Path, pid: int) -> bool:
    marker = _read_launch_marker(session_dir)
    if marker is None:
        return False
    try:
        marker_pid = int((session_dir / "pid").read_text(encoding="utf-8").strip())
        marker_url = (session_dir / "url").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return False
    token = marker.get("launch_token")
    start_identity = marker.get("process_start_identity")
    if (
        marker.get("pid") != pid
        or marker_pid != pid
        or marker.get("url") != marker_url
        or not isinstance(token, str)
        or not token
    ):
        return False
    if not isinstance(start_identity, str) or not start_identity:
        return False
    if _process_start_identity(pid) != start_identity:
        return False
    commandline = _process_commandline(pid)
    return commandline is not None and _launch_token_is_exactly_paired(commandline, token)


def _terminate_session_pid(pid: int, *, session_dir: Path) -> bool:
    if not _session_ownership_verified(session_dir, pid):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def current_source_revision() -> str | None:
    """Return the current source revision as advisory diagnostic metadata when available."""
    env_revision = os.environ.get("VIBECOMFY_SOURCE_REVISION")
    if env_revision:
        return env_revision.strip() or None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=find_repo_root(),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    revision = result.stdout.strip()
    return revision or None


def _cleanup_session_files(session_dir: Path) -> None:
    for name in ("pid", "url", "config.json", "source_revision", "launch.json"):
        try:
            (session_dir / name).unlink()
        except FileNotFoundError:
            pass


def _write_launch_marker(
    session_dir: Path,
    *,
    pid: int,
    url: str,
    launch_token: str,
) -> None:
    atomic_write_json(
        session_dir / "launch.json",
        {
            "launch_token": launch_token,
            "pid": pid,
            "process_start_identity": _process_start_identity(pid),
            "url": url,
        },
    )


_MANAGED_STARTUP_NEXT_ACTION = (
    "Check the ComfyUI startup log, installed custom nodes, and selected port before retrying."
)
_MANAGED_PROCESS_STOP_TIMEOUT_SEC = 15


def _managed_ready_timeout_sec(config: SessionConfig) -> int:
    raw = (
        config.extra.get("ready_timeout_sec")
        or os.environ.get("VIBECOMFY_SESSION_READY_TIMEOUT_SEC")
        or 300
    )
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeStartupError(
            f"Invalid managed Comfy readiness timeout: {raw!r}",
            next_action=_MANAGED_STARTUP_NEXT_ACTION,
        ) from exc


def _assert_managed_endpoint_available(config: SessionConfig) -> None:
    """Reject an already-owned endpoint before a managed child is spawned.

    ComfyUI has no launch-token handshake in its HTTP protocol.  A short
    loopback bind is therefore the offline ownership boundary: a managed
    launch never treats an endpoint already occupied by a sibling as its own.
    The child-returncode checks in ``_spawn_comfy_server`` cover a failed bind
    after this preflight.
    """
    port = config.port or 8188
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise RuntimeStartupError(
            f"Managed Comfy endpoint 127.0.0.1:{port} is already in use",
            next_action=_MANAGED_STARTUP_NEXT_ACTION,
        ) from exc
    finally:
        probe.close()


def _startup_log_evidence(log_path: str | Path | None, log_handle: Any | None) -> str:
    if log_handle is not None:
        try:
            log_handle.flush()
        except OSError:
            pass
    if log_path is None:
        return "<no startup log configured>"
    try:
        data = Path(log_path).read_bytes()
    except OSError as exc:
        return f"<startup log unavailable: {exc}>"
    text = data.decode("utf-8", errors="replace").strip()
    if len(text) > 2000:
        text = "...<truncated>..." + text[-1985:]
    return text or "<startup log empty>"


async def _stop_managed_process(
    process: asyncio.subprocess.Process,
    *,
    force: bool = False,
    signal_sent: bool = False,
) -> None:
    if process.returncode is not None:
        await process.wait()
        return
    if force:
        process.kill()
        await process.wait()
        return
    if not signal_sent:
        process.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(
            process.wait(),
            timeout=_MANAGED_PROCESS_STOP_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def _cleanup_spawn_failure(
    process: asyncio.subprocess.Process,
    log_handle: Any | None,
    *,
    force: bool = False,
) -> None:
    """Finish ownership cleanup even while the caller is being cancelled."""
    signal_sent = False
    if process.returncode is None:
        if force:
            process.kill()
        else:
            process.send_signal(signal.SIGTERM)
        signal_sent = True
    cleanup_task = asyncio.create_task(
        _stop_managed_process(process, force=force, signal_sent=signal_sent)
    )
    try:
        await asyncio.shield(cleanup_task)
    except asyncio.CancelledError:
        current_task = asyncio.current_task()
        if current_task is not None:
            current_task.uncancel()
        await cleanup_task
        raise
    finally:
        if log_handle is not None:
            log_handle.close()


def _is_benign_embedded_cleanup_exception(exc: Exception) -> bool:
    """Return true for known comfy-kitchen teardown-only failures.

    These are emitted after the prompt has completed and outputs have been
    collected. Treating them as run failures causes successful generations to be
    retried and eventually marked failed, while leaving the next run no better
    off. Unknown cleanup failures still propagate.
    """
    message = str(exc)
    return (
        "model_mmap_residency" in message
        or "cannot cancel futures in this implementation" in message
        or message == "Abnormal termination"
    )


def _partition_comfy_config(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split mixed config into SessionConfig kwargs and raw extra Comfy keys.

    HiddenSwitch keys are translated first, then typed SessionConfig field
    names overwrite translated values when both forms are present.
    """
    typed_fields = {
        "memory_profile",
        "port",
        "vram_policy",
        "cache_policy",
        "warm_policy",
        "reserve_vram_gb",
        "disable_smart_memory",
        "auto_flush_vram_threshold_gb",
    }
    kwargs: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    if "memory_profile" in values and values["memory_profile"] is not None:
        profile = MemoryProfile.parse(values["memory_profile"])
        kwargs["memory_profile"] = profile
        kwargs.update(profile.to_session_overrides())

    for key, value in values.items():
        if key in typed_fields:
            continue
        if key == "reserve_vram":
            kwargs["reserve_vram_gb"] = value
        elif key in {"highvram", "lowvram", "normalvram"}:
            if value:
                kwargs["vram_policy"] = key.removesuffix("vram")
        elif key == "cache_none":
            if value:
                kwargs["cache_policy"] = "none"
        elif key == "cache_classic":
            if value:
                kwargs["cache_policy"] = "classic"
        elif key == "cache_lru":
            if value:
                kwargs["cache_policy"] = f"lru:{value}"
        else:
            extra[key] = value

    for key, value in values.items():
        if key in typed_fields and key != "memory_profile":
            kwargs[key] = value

    return kwargs, extra


def _schema_validate_disabled() -> bool:
    return os.environ.get("VIBECOMFY_SCHEMA_VALIDATE", "1").strip() in {"0", "false", "False", "no", "off"}


def _build_schema_provider(server_url: str | None) -> Any | None:
    if _schema_validate_disabled():
        return None
    from vibecomfy.schema import RuntimeSchemaProvider

    return RuntimeSchemaProvider(server_url=server_url)


async def _warm_schema_provider(
    provider: Any | None,
    *,
    on_unavailable,
    cache_only: bool = False,
) -> Any | None:
    if provider is None:
        return None
    try:
        if getattr(provider, "_object_info", None) is not None:
            return provider
        if cache_only:
            from vibecomfy.schema.cache import load_object_info_cache, validate_object_info_cache

            cached = load_object_info_cache(provider.cache_path)
            if cached is None:
                on_unavailable(f"object_info cache unavailable at {provider.cache_path}; using structural validation only")
                return None
            expected = (
                provider._cache_validation_expected()
                if callable(getattr(provider, "_cache_validation_expected", None))
                else {}
            )
            result = validate_object_info_cache(
                cached,
                expected=expected,
                policy="strict",
                cache_path=provider.cache_path,
            )
            if not result.ok:
                on_unavailable(
                    f"object_info cache rejected at {provider.cache_path}: {result.reason}; "
                    "using structural validation only"
                )
                return None
            setter = getattr(provider, "_set_object_info", None)
            if callable(setter):
                setter(cached)
            else:
                provider._object_info = cached
            return provider

        provider._object_info = await provider.object_info_async()
        return provider
    except (OSError, RuntimeError, TimeoutError) as exc:
        on_unavailable(f"{type(exc).__name__}: {exc}; using structural validation only")
        return None


def _prepare_prompt(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None = None,
    normalize_approval: Any | None = None,
) -> dict[str, Any]:
    try:
        return _prepare_runtime_prompt(
            workflow,
            backend=backend,
            schema_provider=schema_provider,
            normalize_approval=normalize_approval,
        )
    except VibeComfyError:
        # VibeComfyError subclasses carry next_action — re-raise unwrapped
        # so callers can recover the remediation hint.
        raise
    except ValueError as exc:
        raise ValueError(f"Workflow build failed: {exc}") from exc
    except RuntimeError as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc


async def _prepare_prompt_async(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None,
    on_unavailable,
    cache_only: bool = False,
    normalize_approval: Any | None = None,
) -> dict[str, Any]:
    effective = await _warm_schema_provider(
        schema_provider,
        on_unavailable=on_unavailable,
        cache_only=cache_only,
    )
    try:
        api_dict, applied = _prepare_runtime_prompt_with_evidence(
            workflow,
            backend=backend,
            schema_provider=effective,
            normalize_approval=normalize_approval,
        )
        skipped = _schema_skipped_class_types(api_dict) if schema_provider is not None and effective is None else []
        if skipped:
            on_unavailable("schema validation skipped for class types: " + ", ".join(skipped))
        return PreparedPrompt(
            api_dict,
            schema_validation_skipped=skipped,
            normalization=applied,
        )
    except VibeComfyError:
        # VibeComfyError subclasses carry next_action — re-raise unwrapped
        # so callers can recover the remediation hint.
        raise
    except ValueError as exc:
        raise ValueError(f"Workflow build failed: {exc}") from exc
    except RuntimeError as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc


def _validation_failed_message(report: Any) -> str:
    from vibecomfy.schema.validate import format_issue

    return "Workflow validation failed:\n  - " + "\n  - ".join(
        format_issue(issue) for issue in report.issues if issue.severity == "error"
    )


def _prepare_runtime_prompt(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None,
    normalize_approval: Any | None = None,
) -> dict[str, Any]:
    api_dict, _applied = _prepare_runtime_prompt_with_evidence(
        workflow,
        backend=backend,
        schema_provider=schema_provider,
        normalize_approval=normalize_approval,
    )
    return api_dict


def _prepare_runtime_prompt_with_evidence(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None,
    normalize_approval: Any | None = None,
) -> tuple[dict[str, Any], Any | None]:
    """Prepare the queue payload; returns (api_dict, applied_normalization).

    Queue preparation is fail-closed: any change the runtime would need
    (dropping an undeclared input, coercing a portable choice string) is
    computed as a typed :class:`NormalizationProposal` and REFUSED unless the
    caller supplies explicit agent approval binding exactly to that proposal.
    When approved, exactly the proposed operations are applied and returned as
    evidence alongside the payload.
    """
    structural_report = workflow.validate(schema_provider=None)
    if not structural_report.ok:
        raise SchemaValidationError(
            _validation_failed_message(structural_report),
            next_action="vibecomfy validate <template> --no-schema",
        )
    api_dict = workflow.compile(backend=backend)
    if backend == "api" and schema_provider is not None:
        from vibecomfy.schema.validate import (
            SchemaNormalizationRequired,
            apply_schema_normalization,
            propose_schema_normalization,
            validate_api_against_schema,
            validate_api_link_shapes,
        )

        proposal = propose_schema_normalization(api_dict, schema_provider)
        applied: Any | None = None
        if proposal.ops:
            if not proposal.approved_by(normalize_approval):
                raise SchemaNormalizationRequired(proposal)
            api_dict = apply_schema_normalization(api_dict, proposal)
            applied = proposal
        schema_issues = [
            *validate_api_against_schema(api_dict, schema_provider),
            *validate_api_link_shapes(api_dict, schema_provider),
        ]
        if any(issue.severity == "error" for issue in schema_issues):
            from vibecomfy.workflow import ValidationReport

            raise SchemaValidationError(
                _validation_failed_message(ValidationReport(ok=False, issues=schema_issues)),
                next_action="vibecomfy schema refresh",
            )
        return api_dict, applied
    return api_dict, None


def _run_metadata(
    *,
    run_id: str,
    workflow: VibeWorkflow,
    api_dict: dict[str, Any],
    queued: Any,
    outputs: list[str],
    runtime: str,
    comfy_outputs: Any = None,
    config: SessionConfig | None = None,
    timings: dict[str, float] | None = None,
    schema_validation_skipped: list[str] | None = None,
    normalization: Any | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
) -> dict[str, Any]:
    if comfy_outputs is None:
        comfy_outputs = _raw_comfy_outputs(queued)
    serialized = json.dumps(api_dict, sort_keys=True, default=str)
    artifact_manifest = _artifact_manifest(workflow, outputs)
    # Reuse attempt helper for shared fields so metadata.json agrees with attempt.json.
    shared = build_shared_fields(workflow, api_dict, config=config)
    metadata = {
        "run_id": run_id,
        "workflow_id": workflow.id,
        "source": asdict(workflow.source),
        "workflow_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "git_sha": _git_sha(),
        "inputs": {name: item.value for name, item in workflow.inputs.items()},
        "compiled_prompt": api_dict,
        "id_map": shared.get("id_map"),
        "node_lookups": shared.get("node_lookups"),
        "model_manifest": shared.get("model_manifest"),
        "lockfile_snapshot": shared.get("lockfile_snapshot"),
        "runtime_version": shared.get("runtime_version"),
        "comfy_commit": shared.get("comfy_commit"),
        "drift": shared.get("drift"),
        "queued": queued,
        "prompt_id": normalize_prompt_id(queued),
        "comfy_outputs": comfy_outputs,
        "artifact_manifest": artifact_manifest,
        "artifact_paths": outputs,
        "outputs": outputs,
        "runtime": runtime,
        "schema_validation_skipped": schema_validation_skipped or [],
    }
    normalization_ops = getattr(normalization, "ops", None)
    if normalization_ops:
        metadata["schema_normalization"] = [op.to_dict() for op in normalization_ops]
    entrypoint = workflow.metadata.get("entrypoint")
    layer = workflow.metadata.get("layer")
    if isinstance(entrypoint, str) and entrypoint:
        metadata["entrypoint"] = entrypoint
    if isinstance(layer, str) and layer:
        metadata["layer"] = layer
    if chain_id is not None:
        metadata["chain_id"] = chain_id
    if parent_run_id is not None:
        metadata["parent_run_id"] = parent_run_id
    if timings:
        metadata["timings"] = timings
    if config is not None and config.memory_profile is not None:
        metadata.update(MemoryProfile.parse(config.memory_profile).to_telemetry())
    patch_applications = workflow.metadata.get("patch_applications")
    if isinstance(patch_applications, list):
        metadata["patch_applications"] = patch_applications
    reqs = workflow.requirements
    metadata["requirements"] = {
        "models": reqs.models,
        "custom_nodes": reqs.custom_nodes,
        "missing_models": reqs.missing_models,
        "missing_nodes": reqs.missing_nodes,
        "unsupported": reqs.unsupported,
    }
    return metadata


def _artifact_manifest(workflow: VibeWorkflow, outputs: list[str]) -> dict[str, Any]:
    descriptors = [output for output in workflow.outputs if output.name]
    by_output: dict[str, list[str]] = {str(output.name): [] for output in descriptors}
    unmapped: list[str] = []
    attribution: list[dict[str, str]] = []

    single_named_output = descriptors[0] if len(descriptors) == 1 and len(outputs) == 1 else None
    for path in outputs:
        output_name: str | None = None
        method: str | None = None
        prefix_matches = [
            output for output in descriptors if output.filename_prefix and _path_matches_filename_prefix(path, output.filename_prefix)
        ]
        if len(prefix_matches) == 1:
            output_name = str(prefix_matches[0].name)
            method = "filename_prefix"
        elif single_named_output is not None:
            output_name = str(single_named_output.name)
            method = "single_named_output"

        if output_name is None or method is None:
            unmapped.append(path)
            continue
        by_output.setdefault(output_name, []).append(path)
        attribution.append({"path": path, "output": output_name, "method": method})

    return {
        "schema_version": 1,
        "by_output": by_output,
        "unmapped": unmapped,
        "attribution": attribution,
    }


def _path_matches_filename_prefix(path: str, filename_prefix: str) -> bool:
    normalized_path = str(path).replace("\\", "/")
    normalized_prefix = str(filename_prefix).replace("\\", "/").rstrip("/")
    if not normalized_prefix:
        return False
    if normalized_path.startswith(normalized_prefix):
        return True
    path_name = Path(normalized_path).name
    prefix_name = Path(normalized_prefix).name
    return bool(prefix_name and path_name.startswith(prefix_name))


def _raw_comfy_outputs(queued: Any) -> Any:
    if hasattr(queued, "outputs"):
        return getattr(queued, "outputs")
    if isinstance(queued, dict) and "outputs" in queued:
        return queued["outputs"]
    return queued

_MISSING_TERMINAL_FIELD = object()
_TERMINAL_EVIDENCE_LIMIT = 2048
_TERMINAL_FIELD_LIMIT = 384
_TERMINAL_ERROR_FIELDS = (
    "node_id",
    "node_type",
    "exception_type",
    "exception_message",
)


def _terminal_field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, _MISSING_TERMINAL_FIELD)
    return getattr(value, name, _MISSING_TERMINAL_FIELD)


def _malformed_terminal_result(prompt_id: str | None, reason: str) -> QueueError:
    label = _bounded_terminal_value(prompt_id if prompt_id else "<unknown>")
    return QueueError(
        f"Malformed Comfy terminal result for prompt {label}: {_bounded_terminal_value(reason)}",
        next_action="vibecomfy runtime doctor",
    )


def _bounded_terminal_value(value: Any) -> str:
    if value is _MISSING_TERMINAL_FIELD:
        return "<missing>"
    if isinstance(value, str):
        rendered = value
    elif value is None or isinstance(value, (bool, int, float)):
        rendered = str(value)
    else:
        return f"<{type(value).__name__}>"
    if len(rendered) <= _TERMINAL_FIELD_LIMIT:
        return rendered
    head = (_TERMINAL_FIELD_LIMIT - 31) // 2
    tail = _TERMINAL_FIELD_LIMIT - 31 - head
    return rendered[:head] + "...<truncated>..." + rendered[-tail:]


def _bounded_error_details(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return _bounded_terminal_value(value)
    return {
        name: _bounded_terminal_value(value[name])
        for name in _TERMINAL_ERROR_FIELDS
        if name in value
    }


def _bounded_status_message(messages: Any) -> Any:
    if not isinstance(messages, (list, tuple)) or not messages:
        return _bounded_terminal_value(messages)
    selected = messages[-1]
    for message in reversed(messages):
        if (
            isinstance(message, (list, tuple))
            and message
            and message[0] == "execution_error"
        ):
            selected = message
            break
    if isinstance(selected, (list, tuple)) and len(selected) >= 2:
        return [
            _bounded_terminal_value(selected[0]),
            _bounded_error_details(selected[1]),
        ]
    return _bounded_terminal_value(selected)


def _status_has_execution_error(status: Any) -> bool:
    messages = _terminal_field(status, "messages")
    if not isinstance(messages, (list, tuple)):
        return False
    return any(
        isinstance(message, (list, tuple))
        and bool(message)
        and message[0] == "execution_error"
        for message in messages
    )


def _bounded_terminal_evidence(status: Any) -> str:
    evidence: dict[str, Any] = {}
    error_details = _terminal_field(status, "error_details")
    if error_details is not _MISSING_TERMINAL_FIELD:
        evidence["error_details"] = _bounded_error_details(error_details)
    messages = _terminal_field(status, "messages")
    if messages is not _MISSING_TERMINAL_FIELD:
        evidence["message"] = _bounded_status_message(messages)
    if not evidence:
        evidence = {
            "completed": _bounded_terminal_value(_terminal_field(status, "completed")),
            "status_str": _bounded_terminal_value(_terminal_field(status, "status_str")),
        }
    rendered = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    if len(rendered) <= _TERMINAL_EVIDENCE_LIMIT:
        return rendered
    head = (_TERMINAL_EVIDENCE_LIMIT - 31) // 2
    tail = _TERMINAL_EVIDENCE_LIMIT - 31 - head
    return rendered[:head] + "...<truncated>..." + rendered[-tail:]


def _bounded_diagnostic(text: str) -> str:
    if len(text) <= _TERMINAL_EVIDENCE_LIMIT:
        return text
    head = (_TERMINAL_EVIDENCE_LIMIT - 31) // 2
    tail = _TERMINAL_EVIDENCE_LIMIT - 31 - head
    return text[:head] + "...<truncated>..." + text[-tail:]


def _raise_terminal_execution_error(status: Any, prompt_id: str | None) -> None:
    label = _bounded_terminal_value(prompt_id if prompt_id else "<unknown>")
    message = f"Comfy prompt {label} failed: {_bounded_terminal_evidence(status)}"
    raise RuntimeNodeError(
        _bounded_diagnostic(message),
        next_action="vibecomfy runtime doctor",
    )


def _decode_terminal_result(
    result: Any,
    *,
    prompt_id: str | None,
    status_required: bool,
    allow_list_outputs: bool = False,
) -> Any:
    status = _terminal_field(result, "status")
    if status is _MISSING_TERMINAL_FIELD:
        if status_required:
            raise _malformed_terminal_result(prompt_id, "missing status")
        outputs = _terminal_field(result, "outputs")
        if outputs is _MISSING_TERMINAL_FIELD:
            if isinstance(result, Mapping):
                wrapper_fields = {"prompt_id", "number", "node_errors"}
                if not any(field in result for field in wrapper_fields):
                    return result
            elif isinstance(result, list):
                return result
            raise _malformed_terminal_result(prompt_id, "embedded result is missing outputs")
        if not isinstance(outputs, (Mapping, list)):
            raise _malformed_terminal_result(
                prompt_id,
                f"embedded outputs must be an object or list, got {type(outputs).__name__}",
            )
        return outputs

    if _status_has_execution_error(status):
        _raise_terminal_execution_error(status, prompt_id)
    status_str = _terminal_field(status, "status_str")
    completed = _terminal_field(status, "completed")
    if status_str is _MISSING_TERMINAL_FIELD:
        raise _malformed_terminal_result(prompt_id, "missing status_str")
    if status_str == "error":
        _raise_terminal_execution_error(status, prompt_id)
    if isinstance(status_str, str) and status_str in {"pending", "queued", "running"}:
        raise _malformed_terminal_result(
            prompt_id,
            f"nonterminal status {_bounded_terminal_value(status_str)}",
        )
    if status_str != "success":
        raise _malformed_terminal_result(
            prompt_id,
            f"unknown status_str {_bounded_terminal_value(status_str)}",
        )
    if completed is _MISSING_TERMINAL_FIELD:
        raise _malformed_terminal_result(prompt_id, "success status is missing completed")
    if completed is not True:
        raise _malformed_terminal_result(
            prompt_id,
            f"success status requires completed=true, got {_bounded_terminal_value(completed)}",
        )

    outputs = _terminal_field(result, "outputs")
    if outputs is _MISSING_TERMINAL_FIELD:
        raise _malformed_terminal_result(prompt_id, "successful result is missing outputs")
    if not isinstance(outputs, Mapping) and not (allow_list_outputs and isinstance(outputs, list)):
        raise _malformed_terminal_result(
            prompt_id,
            f"outputs must be an object, got {type(outputs).__name__}",
        )
    return outputs


async def _wait_for_server_history(
    server_url: str,
    prompt_id: str | None,
    *,
    config: SessionConfig | None,
) -> dict[str, Any]:
    if not prompt_id:
        raise QueueError(
            "Comfy queue response did not include a prompt_id; cannot retrieve terminal result",
            next_action="vibecomfy runtime doctor",
        )
    raw_timeout = (
        config.extra.get("prompt_timeout_sec")
        if config is not None and "prompt_timeout_sec" in config.extra
        else os.environ.get("VIBECOMFY_PROMPT_TIMEOUT_SEC")
    )
    timeout_sec = float(raw_timeout if raw_timeout not in (None, "") else 3600)
    if not timeout_sec > 0:
        timeout_sec = 0.0
    raw_poll_interval = os.environ.get("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC")
    poll_interval_sec = float(raw_poll_interval if raw_poll_interval not in (None, "") else 1)
    if not poll_interval_sec > 0:
        poll_interval_sec = 0.0
    deadline = time.monotonic() + timeout_sec
    client = ComfyClient(server_url)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # The client has its own transport timeout, but the execution
            # deadline must also bound an already-in-flight HTTP request.
            history = await asyncio.wait_for(client.history(prompt_id), timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Comfy prompt {_bounded_terminal_value(prompt_id)} did not complete "
                f"within {timeout_sec:.3g}s"
            ) from exc
        if not isinstance(history, dict):
            raise _malformed_terminal_result(
                prompt_id,
                f"history response must be an object, got {type(history).__name__}",
            )
        if prompt_id not in history:
            if history:
                raise _malformed_terminal_result(
                    prompt_id,
                    "non-empty history response omitted the requested prompt",
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_interval_sec, remaining))
            continue

        entry = history[prompt_id]
        status = _terminal_field(entry, "status")
        if status is _MISSING_TERMINAL_FIELD:
            _decode_terminal_result(entry, prompt_id=prompt_id, status_required=True)
        if _status_has_execution_error(status):
            _decode_terminal_result(entry, prompt_id=prompt_id, status_required=True)
        status_str = _terminal_field(status, "status_str")
        if isinstance(status_str, str) and status_str in {"pending", "queued", "running"}:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_interval_sec, remaining))
            continue
        _decode_terminal_result(entry, prompt_id=prompt_id, status_required=True)
        return history
    raise TimeoutError(
        f"Comfy prompt {_bounded_terminal_value(prompt_id)} did not complete within {timeout_sec:.3g}s"
    )


def _history_entry(history: Any, prompt_id: str | None) -> dict[str, Any] | None:
    if not isinstance(history, dict):
        return None
    if prompt_id and isinstance(history.get(prompt_id), dict):
        return history[prompt_id]
    if prompt_id is None and len(history) == 1:
        only = next(iter(history.values()))
        return only if isinstance(only, dict) else None
    return None


def _outputs_from_server_history(history: dict[str, Any], prompt_id: str | None) -> Any:
    entry = _history_entry(history, prompt_id)
    if entry is None:
        raise _malformed_terminal_result(prompt_id, "history entry is missing or is not an object")
    return _decode_terminal_result(
        entry,
        prompt_id=prompt_id,
        status_required=True,
    )


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _collect_output_paths(value: Any, *, output_directory: str | Path | None = None) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        filename = value.get("filename")
        if isinstance(filename, str):
            paths.append(_resolve_comfy_output_filename(value, output_directory))
            return paths
        for key, item in value.items():
            if key in {"abs_path", "path", "fullpath", "filename"} and isinstance(item, str):
                paths.append(item)
            else:
                paths.extend(_collect_output_paths(item, output_directory=output_directory))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_collect_output_paths(item, output_directory=output_directory))
    return paths


def _resolve_comfy_output_filename(value: dict[str, Any], output_directory: str | Path | None) -> str:
    filename = str(value["filename"])
    if Path(filename).is_absolute() or output_directory is None:
        return filename
    subfolder = value.get("subfolder")
    if isinstance(subfolder, str) and subfolder.strip():
        return str(Path(output_directory) / subfolder / filename)
    return str(Path(output_directory) / filename)


def _configured_output_directory(config: SessionConfig | None) -> str | None:
    values: dict[str, Any] = {}
    if config is not None:
        values.update(config.extra)
    env_config = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if env_config:
        try:
            parsed = json.loads(env_config)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            values.update(parsed)
    output_directory = values.get("output_directory")
    return str(output_directory) if output_directory else None


def _embedded_configuration_for_session(config: SessionConfig) -> Configuration | None:
    values: dict[str, Any] = {}
    if config.port is not None:
        values["port"] = config.port
    if config.vram_policy in {"high", "low", "normal"}:
        values[f"{config.vram_policy}vram"] = True
    if config.reserve_vram_gb is not None:
        values["reserve_vram"] = config.reserve_vram_gb
    if config.cache_policy == "classic":
        values["cache_classic"] = True
    elif config.cache_policy == "none":
        values["cache_none"] = True
    elif config.cache_policy.startswith("lru:"):
        values["cache_lru"] = int(config.cache_policy.split(":", 1)[1])
    if config.disable_smart_memory:
        values["disable_smart_memory"] = True

    values.update(config.extra)
    if _env_requests_sage_attention() and "use_sage_attention" not in values:
        values["use_sage_attention"] = True
    env_config = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if env_config:
        parsed = json.loads(env_config)
        if not isinstance(parsed, dict):
            raise ValueError("VIBECOMFY_COMFY_CONFIGURATION must be a JSON object")
        values.update(parsed)
    extra_model_paths = Path.cwd() / "extra_model_paths.yaml"
    if extra_model_paths.is_file():
        values.setdefault("extra_model_paths_config", [str(extra_model_paths)])
    if not values:
        return None

    from comfy.client.embedded_comfy_client import default_configuration

    configuration = default_configuration()
    configuration.update(values)
    return configuration


def _embedded_shutdown_timeout_sec() -> float:
    raw = os.environ.get("VIBECOMFY_EMBEDDED_SHUTDOWN_TIMEOUT_SEC", "15")
    try:
        value = float(raw)
    except ValueError:
        return 15.0
    return max(value, 0.1)


def _embedded_configuration(workflow: VibeWorkflow) -> Configuration | None:
    return _embedded_configuration_for_session(SessionConfig.from_workflow_metadata(workflow))


def _comfy_server_argv(config: SessionConfig) -> tuple[str, ...]:
    argv = [*_comfyui_command(), "serve"]
    if config.vram_policy in {"high", "low", "normal"}:
        argv.append(f"--{config.vram_policy}vram")
    if config.reserve_vram_gb is not None:
        argv.extend(["--reserve-vram", str(config.reserve_vram_gb)])
    if config.disable_smart_memory:
        argv.append("--disable-smart-memory")
    if config.cache_policy == "classic":
        argv.append("--cache-classic")
    elif config.cache_policy == "none":
        argv.append("--cache-none")
    elif config.cache_policy.startswith("lru:"):
        argv.extend(["--cache-lru", config.cache_policy.split(":", 1)[1]])
    if _config_requests_sage_attention(config):
        argv.append("--use-sage-attention")
    for key, flag in (
        ("input_directory", "--input-directory"),
        ("output_directory", "--output-directory"),
        ("temp_directory", "--temp-directory"),
    ):
        value = config.extra.get(key)
        if value:
            argv.extend([flag, str(value)])
    argv.extend(["--port", str(config.port or 8188)])
    return tuple(argv)


def _env_requests_sage_attention() -> bool:
    raw = (
        os.environ.get("VIBECOMFY_ATTENTION_PROFILE")
        or os.environ.get("REIGH_VIBECOMFY_ATTENTION_PROFILE")
        or ""
    )
    return raw.strip().lower() in {"sage", "sageattn", "sageattention", "optimized"}


def _config_requests_sage_attention(config: SessionConfig) -> bool:
    if bool(config.extra.get("use_sage_attention")):
        return True
    return _env_requests_sage_attention()


async def _spawn_comfy_server(
    config: SessionConfig, log_path: str | Path | None = None
) -> tuple[asyncio.subprocess.Process, str, Any | None]:
    ready_timeout_sec = _managed_ready_timeout_sec(config)
    _assert_managed_endpoint_available(config)
    log_handle = None
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_handle = Path(log_path).open("ab", buffering=0)
    argv = _comfy_server_argv(config)
    if log_handle:
        log_handle.write(f"[vibecomfy] launching managed Comfy server: {json.dumps(list(argv))}\n".encode())
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=log_handle or asyncio.subprocess.DEVNULL,
            stderr=log_handle or asyncio.subprocess.DEVNULL,
            env=env,
        )
        managed_url = f"http://127.0.0.1:{config.port or 8188}"
        client = ComfyClient(managed_url)
        for second in range(ready_timeout_sec):
            if process.returncode is not None:
                returncode = process.returncode
                await process.wait()
                evidence = _startup_log_evidence(log_path, log_handle)
                raise RuntimeStartupError(
                    f"Managed Comfy server exited during startup with return code "
                    f"{returncode}; log evidence: {evidence}",
                    next_action=_MANAGED_STARTUP_NEXT_ACTION,
                )
            if await client.ready():
                if process.returncode is None:
                    return process, managed_url, log_handle
                returncode = process.returncode
                await process.wait()
                evidence = _startup_log_evidence(log_path, log_handle)
                raise RuntimeStartupError(
                    f"Managed Comfy server exited during startup with return code "
                    f"{returncode}; log evidence: {evidence}",
                    next_action=_MANAGED_STARTUP_NEXT_ACTION,
                )
            if process.returncode is not None:
                returncode = process.returncode
                await process.wait()
                evidence = _startup_log_evidence(log_path, log_handle)
                raise RuntimeStartupError(
                    f"Managed Comfy server exited during startup with return code "
                    f"{returncode}; log evidence: {evidence}",
                    next_action=_MANAGED_STARTUP_NEXT_ACTION,
                )
            if log_handle and second and second % 30 == 0:
                log_handle.write(
                    f"[vibecomfy] waiting for managed Comfy server readiness: "
                    f"{second}/{ready_timeout_sec}s\n".encode()
                )
            await asyncio.sleep(1)
        timeout = TimeoutError(
            f"Managed Comfy server did not become ready within {ready_timeout_sec} seconds"
        )
        await _cleanup_spawn_failure(process, log_handle, force=True)
        log_handle = None
        raise RuntimeStartupError(
            str(timeout),
            next_action=_MANAGED_STARTUP_NEXT_ACTION,
        ) from timeout
    except BaseException:
        if process is not None:
            await _cleanup_spawn_failure(process, log_handle)
        elif log_handle is not None:
            log_handle.close()
        raise


def _comfyui_command() -> tuple[str, ...]:
    return comfyui_command()


async def _maybe_flush_for_policy(session: VibeSession, fp: tuple[Any, ...]) -> None:
    warm_policy = os.environ.get("VIBECOMFY_WARM", session.config.warm_policy).strip().lower()
    if warm_policy == "never":
        await session.flush()
    elif (
        warm_policy == "auto"
        and session.last_fingerprint is not None
        and fp != session.last_fingerprint
        and _free_vram_gb() < session.config.auto_flush_vram_threshold_gb
    ):
        await session.flush()


def _free_vram_gb() -> float:
    try:
        from comfy.model_management import get_free_memory
    except (ImportError, AttributeError):
        return float("inf")

    try:
        return float(get_free_memory()) / (1024**3)
    except (ImportError, AttributeError):
        return float("inf")


def _embedded_observation_url(config: SessionConfig) -> str:
    """Best-guess HTTP base for the embedded backend.

    The embedded backend may or may not expose a server. The watchdog tolerates
    either case: if the URL is unreachable we record connection_state=
    never_connected and continue with VRAM sampling (which will also fail
    silently and be reflected in the diagnosis).
    """
    port = config.port or 8188
    return f"http://127.0.0.1:{port}"


async def _start_watchdog(
    *,
    server_url: str | None,
    client_id: str,
    api_dict: dict[str, Any],
) -> Watchdog | None:
    """Build and start a Watchdog. Returns None if disabled or failed to start.

    The watchdog must NEVER raise into the run path. Any error here is logged
    and ignored. Must be called from inside a running event loop.
    """
    if os.environ.get("VIBECOMFY_WATCHDOG", "1").strip() in {"0", "false", "False", "no", "off"}:
        return None
    if not server_url:
        return None
    try:
        wd = Watchdog(server_url=server_url, client_id=client_id, api_dict=api_dict)
    except Exception:
        logger.exception("watchdog: construction failed; continuing without it")
        return None
    try:
        await wd.start()
    except Exception:
        logger.exception("watchdog: start scheduling failed; continuing without it")
        return None
    return wd


def _set_watchdog_prompt_id(watchdog: Watchdog | None, prompt_id: str | None) -> None:
    if watchdog is None or prompt_id is None:
        return
    try:
        watchdog.state.prompt_id = prompt_id
    except Exception:
        # Observation must never affect execution, including test/in-process
        # watchdog adapters that do not expose Watchdog.state.
        logger.debug("watchdog: could not attach prompt_id", exc_info=True)


async def _finalize_watchdog(
    watchdog: Watchdog | None,
    *,
    run_dir: Path,
    reason: str,
) -> None:
    """Stop the watchdog and write its report. Errors are swallowed."""
    if watchdog is None:
        return
    try:
        await watchdog.stop(reason=reason)
        report = watchdog.dump()
        path = write_report(run_dir, report)
        # Greppable header on the orchestrator log so a single tail shows it.
        logger.info("%s path=%s", report.header_line(), path)
    except Exception:
        logger.exception("watchdog: finalize failed; ignoring")


def model_fingerprint(api_dict: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    triples: list[tuple[str, str, str]] = []
    for node in api_dict.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        include = class_type in OVERRIDES_INCLUDE or (
            "Loader" in class_type and class_type not in OVERRIDES_EXCLUDE
        )
        if not include:
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for slot, value in inputs.items():
            if isinstance(slot, str) and isinstance(value, str):
                triples.append((class_type, slot, value))
    return tuple(sorted(triples))
