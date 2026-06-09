from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol

from vibecomfy.errors import (
    MODEL_DOCTOR_NEXT_ACTION,
    ModelAssetError,
    QueueError,
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
from .watchdog import Watchdog, _is_disabled, write_report

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
    from vibecomfy.model_assets import _normalise_requirement_entries, resolve_referenced_assets

    def _norm(value: str) -> str:
        return value.replace("\\", "/")

    raw_assets = workflow.metadata.get("model_assets", [])
    authored = _normalise_requirement_entries(raw_assets) if isinstance(raw_assets, list) else []
    resolved, unresolved = resolve_referenced_assets(workflow)
    authored_keys = {
        (_norm(entry["name"]), _norm(entry["subdir"]))
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
        if (_norm(item["value"]), _norm(item["subdir"])) not in authored_keys
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
    seen: set[tuple[str, str]] = set()
    for entry in [*authored, *resolved]:
        key = (entry["name"], entry["subdir"])
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
    def __init__(self, api_dict: dict[str, Any], *, schema_validation_skipped: list[str] | None = None) -> None:
        super().__init__(api_dict)
        self.schema_validation_skipped = schema_validation_skipped or []


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
    ) -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
        if ensure_packs:
            from vibecomfy.custom_node_refs import check_pack_pin_compatibility
            from vibecomfy.node_packs_install import install_required_packs, missing_packs_for_workflow
            from vibecomfy.node_packs_lockfile import read_lockfile

            lockfile_entries = read_lockfile()
            pin_issues = check_pack_pin_compatibility(workflow, lockfile_entries)
            pin_errors = [issue.message for issue in pin_issues if issue.severity == "error"]
            if pin_errors:
                raise RuntimeError("ensure_packs: " + "; ".join(pin_errors))
            # Dev convenience only; production should pre-stage nodepacks with `vibecomfy nodes ensure`.
            try:
                packs, _unresolved = missing_packs_for_workflow(workflow)
            except FileNotFoundError as exc:
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
            return await self._run_untracked(
                workflow,
                backend=backend,
                strict_drift=resolved_strict,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
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
        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=self._schema_provider,
            on_unavailable=self._on_schema_unavailable,
        )
        schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
        timings["prepare_prompt_sec"] = round(time.monotonic() - phase_start, 3)
        fp = model_fingerprint(api_dict)

        phase_start = time.monotonic()
        await _maybe_flush_for_policy(self, fp)
        timings["memory_policy_sec"] = round(time.monotonic() - phase_start, 3)

        run_id = f"run-{int(time.time())}"
        run_dir = Path("out/runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
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
        stop_reason = "completed"
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
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason)
        timings["queue_prompt_sec"] = round(time.monotonic() - phase_start, 3)
        self.last_fingerprint = fp

        phase_start = time.monotonic()
        comfy_outputs = _raw_comfy_outputs(queued)
        outputs = _collect_output_paths(
            comfy_outputs,
            output_directory=_configured_output_directory(self.config),
        )
        timings["collect_outputs_sec"] = round(time.monotonic() - phase_start, 3)
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
            chain_id=chain_id,
            parent_run_id=parent_run_id,
        )
        metadata_path = atomic_write_json(run_dir / "metadata.json", metadata)
        return RunResult(
            run_id=run_id,
            prompt_id=normalize_prompt_id(queued),
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
            return await self._run_untracked(
                workflow,
                backend=backend,
                strict_drift=resolved_strict,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
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
        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=self._schema_provider,
            on_unavailable=self._on_schema_unavailable,
        )
        schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
        timings["prepare_prompt_sec"] = round(time.monotonic() - phase_start, 3)
        fp = model_fingerprint(api_dict)

        phase_start = time.monotonic()
        await _maybe_flush_for_policy(self, fp)
        timings["memory_policy_sec"] = round(time.monotonic() - phase_start, 3)

        run_id = f"run-{int(time.time())}"
        run_dir = Path("out/runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "comfy.log"

        client_id = uuid.uuid4().hex
        watchdog = await _start_watchdog(server_url=self.url, client_id=client_id, api_dict=api_dict)
        stop_reason = "completed"
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
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason)
        timings["queue_prompt_sec"] = round(time.monotonic() - phase_start, 3)
        self.last_fingerprint = fp

        phase_start = time.monotonic()
        prompt_id = normalize_prompt_id(queued)
        history = await _wait_for_server_history(self.url, prompt_id, config=self.config)
        comfy_outputs = _outputs_from_server_history(history, prompt_id)
        outputs = _collect_output_paths(
            comfy_outputs,
            output_directory=_configured_output_directory(self.config),
        )
        timings["collect_outputs_sec"] = round(time.monotonic() - phase_start, 3)
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
            process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=15)
            except asyncio.TimeoutError:
                process.kill()
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
    pid_path = session_dir / "pid"
    url_path = session_dir / "url"
    revision_path = session_dir / "source_revision"
    if not pid_path.exists() or not url_path.exists():
        _cleanup_session_files(session_dir)
        return None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        url = url_path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        _cleanup_session_files(session_dir)
        return None
    if not url:
        _cleanup_session_files(session_dir)
        return None
    current_revision = current_source_revision()
    if current_revision is not None:
        try:
            session_revision = revision_path.read_text(encoding="utf-8").strip()
        except OSError:
            _terminate_session_pid(pid)
            _cleanup_session_files(session_dir)
            return None
        if session_revision != current_revision:
            _terminate_session_pid(pid)
            _cleanup_session_files(session_dir)
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _cleanup_session_files(session_dir)
        return None
    except PermissionError:
        if not _session_url_healthy(url):
            _cleanup_session_files(session_dir)
            return None
    except OSError:
        _cleanup_session_files(session_dir)
        return None
    if not _session_url_healthy(url):
        _terminate_session_pid(pid)
        _cleanup_session_files(session_dir)
        return None
    config = _read_session_config(session_dir)
    return {
        "id": id,
        "pid": pid,
        "url": url,
        "config": config,
        "models_root": config.get("models_root"),
        "models_root_normalized": config.get("models_root_normalized"),
        "locality": config.get("locality"),
    }


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
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _terminate_session_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        return


def current_source_revision() -> str | None:
    """Return a stable source revision for stale-session detection when available."""
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
    for name in ("pid", "url", "config.json", "source_revision"):
        try:
            (session_dir / name).unlink()
        except FileNotFoundError:
            pass


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


from .config import (  # noqa: E402
    _comfy_server_argv,
    _comfyui_command,
    _config_requests_sage_attention,
    _env_requests_sage_attention,
    _partition_comfy_config,
    _spawn_comfy_server,
)


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
            from vibecomfy.schema.cache import load_object_info_cache

            cached = load_object_info_cache(provider.cache_path)
            if cached is None:
                on_unavailable(f"object_info cache unavailable at {provider.cache_path}; using structural validation only")
                return None
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
) -> dict[str, Any]:
    try:
        return _prepare_runtime_prompt(workflow, backend=backend, schema_provider=schema_provider)
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
) -> dict[str, Any]:
    effective = await _warm_schema_provider(
        schema_provider,
        on_unavailable=on_unavailable,
        cache_only=cache_only,
    )
    try:
        api_dict = _prepare_runtime_prompt(workflow, backend=backend, schema_provider=effective)
        skipped = _schema_skipped_class_types(api_dict) if schema_provider is not None and effective is None else []
        if skipped:
            on_unavailable("schema validation skipped for class types: " + ", ".join(skipped))
        return PreparedPrompt(api_dict, schema_validation_skipped=skipped)
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
    from vibecomfy.schema.format import format_issue

    return "Workflow validation failed:\n  - " + "\n  - ".join(
        format_issue(issue) for issue in report.issues if issue.severity == "error"
    )


def _prepare_runtime_prompt(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None,
) -> dict[str, Any]:
    structural_report = workflow.validate(schema_provider=None)
    if not structural_report.ok:
        raise SchemaValidationError(
            _validation_failed_message(structural_report),
            next_action="vibecomfy validate <template> --no-schema",
        )
    api_dict = workflow.compile(backend=backend)
    if backend == "api" and schema_provider is not None:
        from vibecomfy.schema.validate import (
            sanitize_api_against_schema,
            validate_api_against_schema,
            validate_api_link_shapes,
        )

        api_dict = sanitize_api_against_schema(api_dict, schema_provider)
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
    return api_dict


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
        "comfy_outputs": comfy_outputs,
        "artifact_manifest": artifact_manifest,
        "artifact_paths": outputs,
        "outputs": outputs,
        "runtime": runtime,
        "schema_validation_skipped": schema_validation_skipped or [],
    }
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


async def _wait_for_server_history(
    server_url: str,
    prompt_id: str | None,
    *,
    config: SessionConfig | None,
) -> dict[str, Any]:
    if not prompt_id:
        return {}
    timeout_sec = float(
        (config.extra.get("prompt_timeout_sec") if config is not None else None)
        or os.environ.get("VIBECOMFY_PROMPT_TIMEOUT_SEC")
        or 3600
    )
    poll_interval_sec = float(os.environ.get("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC") or 1)
    deadline = time.monotonic() + timeout_sec
    client = ComfyClient(server_url)
    while time.monotonic() < deadline:
        history = await client.history(prompt_id)
        entry = _history_entry(history, prompt_id)
        if isinstance(entry, dict):
            return history
        await asyncio.sleep(poll_interval_sec)
    raise TimeoutError(f"Comfy prompt {prompt_id} did not complete within {timeout_sec:.0f}s")


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
    if not isinstance(entry, dict):
        return {}
    return entry.get("outputs") or {}


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




def _embedded_configuration(workflow: VibeWorkflow) -> Configuration | None:
    return _embedded_configuration_for_session(SessionConfig.from_workflow_metadata(workflow))


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
    if _is_disabled():
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
