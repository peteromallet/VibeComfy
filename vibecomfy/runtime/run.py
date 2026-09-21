from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.errors import QueueError, RuntimeNodeError
from vibecomfy.workflow import VibeWorkflow
from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundle, WorkflowBundleError

from .attempt import build_attempt_bundle, write_attempt_json
from .run_context import RunContext
from .client import ComfyClient
from .dependencies import RuntimeDependencyError
from .execution import queue_server_prompt
from .drift import enforce_strict_drift
from .model_policy import apply_model_preflight, resolve_model_preflight_policy
from .server import comfy_server
from .session import (
    EmbeddedSession,
    RunResult,
    SessionConfig,
    _build_schema_provider,
    _configured_output_directory,
    _normalized_descriptor_path,
    _embedded_configuration,
    _external_log_locator,
    _outputs_from_server_history,
    _declared_outputs_from_server_history,
    _prepare_prompt_async,
    _begin_runtime_lifecycle,
    _commit_queue_witness,
    _complete_runtime_run,
    _artifact_records,
    _persist_runtime_evidence,
    _persist_runtime_failure,
    _runtime_evidence,
    _run_metadata,
    _schema_provider_provenance,
    _schema_warn_only,
    _comfy_server_argv,
    _wait_for_server_history,
    _workflow_queue_failure_message,
    _validate_declared_output_contract,
    _verify_declared_media,
)
from .reconciliation import assert_execution_snapshot, build_execution_snapshot

logger = logging.getLogger(__name__)


def _dependency_check(
    workflow: VibeWorkflow,
    *,
    config: SessionConfig,
    dependency_mode: str,
    server_url: str | None,
    target: Mapping[str, Any] | None = None,
    dependency_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    from .dependencies import (
        RuntimeDependencyError,
        compare_runtime,
        inspect_external_runtime,
        runtime_requirements_from_workflow,
        sync_runtime,
    )

    if dependency_mode not in {"reuse", "sync"}:
        raise RuntimeDependencyError("dependency mode must be reuse or sync")
    configured_deviation = _normalize_dependency_deviation(
        config.extra.get("dependency_deviation")
    )
    requirements = runtime_requirements_from_workflow(workflow)
    external_target = server_url is not None and not (
        isinstance(target, Mapping) and target.get("managed") is True
    )
    if external_target and requirements is not None:
        target = inspect_external_runtime(server_url)
    if dependency_report is not None:
        report = dict(dependency_report)
        report.setdefault("mode", dependency_mode)
        report.setdefault("changes", [])
        if requirements is not None:
            external_target = server_url is not None and not (
                isinstance(target, Mapping) and target.get("managed") is True
            )
            observed = compare_runtime(
                requirements,
                target=target if target is not None else ({} if external_target else None),
                runtime_root=None if external_target else config.runtime_root,
                strict_external_launch_flags=bool(config.extra.get("strict_external_launch_flags")),
            )
            for key in (
                "mode", "actions", "synced", "managed", "changes",
                "partial", "selected_packages", "remaining_mismatches",
                "attempt_deviation",
            ):
                if key in report:
                    observed[key] = report[key]
            report = observed
    else:
        external_target = server_url is not None and not (
            isinstance(target, Mapping) and target.get("managed") is True
        )
        report = compare_runtime(
            requirements,
            target=target if target is not None else ({} if external_target else None),
            runtime_root=None if external_target else config.runtime_root,
            strict_external_launch_flags=bool(config.extra.get("strict_external_launch_flags")),
        )
    if requirements is not None:
        report = dict(report)
        report.setdefault("mode", dependency_mode)
        report.setdefault("changes", [])
    deviation = configured_deviation
    if deviation is not None:
        report = dict(report)
        report["attempt_deviation"] = deviation
        report["compliance"] = "noncompliant" if report.get("status") != "matching" else "unverified"
        report["execution_policy"] = "advisory_deviation"
        # A deviation can authorize an experiment against a version/pin or an
        # unknown remote observation.  It cannot turn an actually absent node
        # pack into an executable one; compile/schema admission remains the
        # authority for missing classes.
        missing_nodes = [
            item for item in report.get("checks", ())
            if isinstance(item, Mapping)
            and str(item.get("path", "")).startswith("custom_nodes.")
            and item.get("status") == "missing"
        ]
        if missing_nodes:
            report["deviation_rejected"] = "missing_custom_nodes"
            deviation = None
        else:
            report["execution_permitted"] = True
    if dependency_mode == "sync" and requirements is not None:
        if external_target:
            raise RuntimeDependencyError(
                "--deps sync is unavailable for an explicit external server; use --deps reuse"
            )
        if dependency_report is not None:
            # The CLI may have synchronized before preparation/session
            # startup. Never synchronize again through a target that may
            # already be an active managed server; the post-start comparison
            # below is the verification boundary.
            if report.get("mode") != "sync":
                raise RuntimeDependencyError(
                    "--deps sync requires a synchronized dependency report or a managed target"
                )
            if report.get("status") not in {"matching", "unverified"} and configured_deviation is None:
                exc = RuntimeDependencyError(
                    "runtime dependencies are not compatible with this target: "
                    + "; ".join(str(item) for item in report.get("mismatches", ()))
                )
                setattr(exc, "dependency_report", report)
                raise exc
            # Preserve the prior sync actions/receipt fields exactly.
            pass
        else:
            try:
                report = sync_runtime(
                    requirements,
                    runtime_root=config.runtime_root,
                    target=target,
                    offline=os.environ.get("VIBECOMFY_OFFLINE") == "1",
                    launch_flags=(
                        list(requirements.launch_flags)
                        if requirements.launch_flags
                        else (
                            list(config.extra["launch_flags"])
                            if isinstance(config.extra.get("launch_flags"), (list, tuple))
                            else None
                        )
                    ),
                )
            except RuntimeDependencyError as exc:
                failure_report = getattr(exc, "dependency_report", None)
                if not isinstance(failure_report, Mapping):
                    failure_report = report
                setattr(exc, "dependency_report", failure_report)
                raise
    if report.get("warnings"):
        logger.warning("%s", report["warnings"][0])
    if not report.get("ok", True) and not report.get("execution_permitted", False):
        exc = RuntimeDependencyError(
            "runtime dependencies are not compatible with this target: "
            + "; ".join(str(item) for item in report.get("mismatches", ()))
        )
        setattr(exc, "dependency_report", report)
        raise exc
    return report


def _normalize_dependency_deviation(value: Any) -> dict[str, Any] | None:
    """Validate one attempt-scoped advisory deviation record.

    This deliberately stays a record validator, not a second policy engine.
    Canonical requirements are never edited and the compatibility result is
    never changed to ``matching``.
    """
    from .dependencies import RuntimeDependencyError

    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise RuntimeDependencyError("dependency_deviation must be an object")
    scope = value.get("scope")
    reason = value.get("reason")
    if not isinstance(scope, str) or not scope.strip():
        raise RuntimeDependencyError("dependency_deviation.scope must be a nonblank string")
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeDependencyError("dependency_deviation.reason must be a nonblank string")
    return {
        "scope": scope.strip(),
        "reason": reason.strip(),
        "policy": "advisory",
        "authorized_for_attempt": True,
    }


def _allocate_run_dir(
    prefix: str, *, runtime_root: str | Path | None = None
) -> tuple[str, Path]:
    """Allocate a collision-resistant run directory.

    Returns ``(run_id, run_dir)`` where *run_id* carries a stable *prefix*
    and a unique suffix (timestamp + uuid4 hex).  The directory is created
    with ``parents=True, exist_ok=False`` so that a coincident collision
    raises ``FileExistsError`` instead of silently sharing a directory.
    """
    run_id = f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    base = Path(runtime_root).expanduser() if runtime_root is not None else Path.cwd()
    run_dir = base / "out" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _bind_downloaded_lifecycle_artifacts(
    artifacts: list[dict[str, Any]], local_root: Path
) -> int:
    """Attach safe local paths to artifacts pulled by the lifecycle adapter."""
    root = local_root.resolve(strict=False)
    bound = 0
    for artifact in artifacts:
        filename = artifact.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        relative_descriptor = {
            "filename": filename,
            "subfolder": artifact.get("subfolder") or "",
        }
        relative_posix = _normalized_descriptor_path(relative_descriptor)
        relative = Path(*relative_posix.parts)
        for prefix in (Path("output"), Path("out"), Path(".")):
            candidate = (root / prefix / relative).resolve(strict=False)
            try:
                inside_root = candidate.is_relative_to(root)
            except AttributeError:  # pragma: no cover - Python 3.8 compatibility
                inside_root = str(candidate).startswith(str(root) + os.sep)
            if inside_root and candidate.is_file():
                artifact["path"] = str(candidate)
                artifact["downloaded_path"] = str(candidate)
                artifact["download_source"] = "runpod_lifecycle"
                bound += 1
                break
    return bound


def _delivery_failure(
    error: RuntimeError,
    *,
    output_verification: Mapping[str, Any],
    artifacts: list[dict[str, Any]],
    retrieval: Mapping[str, Any],
) -> RuntimeError:
    """Attach recoverable post-generation state to a delivery exception."""
    error.output_verification = dict(output_verification)
    error.delivery_state = {
        "execution": {
            "status": "succeeded",
            "evidence": "declared final artifact was attributed by current prompt history",
        },
        "verification": {"status": "pending"},
        "retrieval": dict(retrieval),
        "artifacts": [dict(item) for item in artifacts],
        "remote_artifacts": [
            item.get("location")
            for item in artifacts
            if isinstance(item.get("location"), str) and item.get("location")
        ],
        "local_artifacts": [
            item.get("path")
            for item in artifacts
            if isinstance(item.get("path"), str) and item.get("path")
        ],
        "retryable": True,
    }
    return error


async def _capture_lifecycle_log(
    lifecycle_adapter: Any,
    *,
    run_dir: Path,
    lifecycle_details: dict[str, Any],
) -> str | None:
    capture_log = getattr(lifecycle_adapter, "capture_log", None)
    if not callable(capture_log):
        return None
    try:
        log_evidence = await capture_log(local_path=run_dir / "runpod-comfy.log")
    except Exception as exc:  # Log capture must not hide the delivery failure.
        log_evidence = {
            "status": "unavailable",
            "local_path": None,
            "reason": str(exc) or type(exc).__name__,
        }
    if not isinstance(log_evidence, Mapping):
        log_evidence = {
            "status": "unavailable",
            "local_path": None,
            "reason": "lifecycle adapter returned an invalid log witness",
        }
    lifecycle_details["logs"] = dict(log_evidence)
    if log_evidence.get("status") == "captured" and log_evidence.get("local_path"):
        return str(log_evidence["local_path"])
    return None


async def retry_delivery(
    attempt_path: str | Path,
    *,
    lifecycle_adapter: Any,
) -> dict[str, Any]:
    """Retry RunPod artifact/log delivery for an accepted prompt without queueing.

    The existing attempt is the authority. This function deliberately has no
    workflow compilation or queue client dependency, so a retry cannot sample a
    second generation by accident.
    """
    path = Path(attempt_path).expanduser().resolve(strict=True)
    attempt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(attempt, dict):
        raise WorkflowBundleError("delivery retry requires a JSON attempt object")
    acceptance = attempt.get("queue_acceptance")
    if not isinstance(acceptance, Mapping) or acceptance.get("status") != "accepted" or not acceptance.get("prompt_id"):
        raise WorkflowBundleError("delivery retry requires an accepted prompt witness")
    artifacts = attempt.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts or not all(
        isinstance(item, Mapping) for item in artifacts
    ):
        raise WorkflowBundleError("delivery retry requires attributed remote artifacts")
    materialized = [dict(item) for item in artifacts]
    attached = await lifecycle_adapter.attach()
    if not isinstance(attached, Mapping):
        raise WorkflowBundleError("lifecycle adapter returned an invalid attach witness")
    local_root = path.parent / "downloaded-artifacts"
    retrieval = await lifecycle_adapter.download_artifacts(local_root=local_root)
    if not isinstance(retrieval, Mapping) or retrieval.get("status") != "retrieved":
        raise RuntimeError("lifecycle adapter did not retrieve the accepted artifact")
    retrieved_root = Path(str(retrieval.get("local_root") or local_root))
    if _bind_downloaded_lifecycle_artifacts(materialized, retrieved_root) < len(materialized):
        raise RuntimeError("retrieved archive did not contain every accepted output artifact")
    lifecycle_details = dict(attached)
    lifecycle_details["retrieval"] = dict(retrieval)
    log_path = await _capture_lifecycle_log(
        lifecycle_adapter, run_dir=path.parent, lifecycle_details=lifecycle_details
    )
    delivery_state = dict(attempt.get("delivery_state") or {})
    delivery_state.update({
        "execution": delivery_state.get("execution") or {
            "status": "succeeded",
            "evidence": "accepted prompt retained from original attempt",
        },
        "verification": delivery_state.get("verification") or {"status": "pending"},
        "retrieval": {**dict(retrieval), "status": "succeeded"},
        "artifacts": materialized,
        "remote_artifacts": [
            item.get("location") for item in materialized if item.get("location")
        ],
        "local_artifacts": [
            item.get("path") for item in materialized if item.get("path")
        ],
        "retryable": False,
    })
    attempt["delivery_state"] = delivery_state
    attempt["artifacts"] = materialized
    attempt["local_artifact_paths"] = list(delivery_state["local_artifacts"])
    attempt["adapter"] = {
        **dict(attempt.get("adapter") or {}),
        "lifecycle": lifecycle_details,
    }
    attempt["lifecycle_retrieval"] = dict(retrieval)
    attempt["log_path"] = log_path
    attempt["log_provenance"] = dict(lifecycle_details.get("logs") or {})
    terminal = dict(attempt.get("terminal") or {})
    terminal.update({
        "phase": "delivery_retry",
        "execution_state": "succeeded",
        "verification_state": str(delivery_state["verification"].get("status", "pending")),
        "retrieval_state": "succeeded",
        "delivery": delivery_state,
        "reason_type": "none",
        "reason": None,
    })
    attempt["terminal"] = terminal
    runtime_evidence = attempt.get("runtime_evidence")
    if isinstance(runtime_evidence, Mapping):
        runtime_evidence = dict(runtime_evidence)
        runtime_evidence["terminal"] = dict(terminal)
        runtime_evidence["adapter"] = dict(attempt["adapter"])
        attempt["runtime_evidence"] = runtime_evidence
    write_attempt_json(path.parent, attempt)
    return {
        "attempt_path": str(path),
        "prompt_id": acceptance["prompt_id"],
        "artifacts": materialized,
        "log_path": log_path,
        "delivery_state": delivery_state,
    }


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
    schema_provider: Any | None = None,
    dependency_mode: str = "reuse",
    runtime_target: Mapping[str, Any] | None = None,
    dependency_report: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> RunResult:
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime run requires an ApprovedProjectionRecord and WorkflowBundle")
    if bundle.is_unresolved and any(
        str(item.get("kind", "")) != "companion" for item in bundle.unresolved
    ):
        bundle.require_canonical_authority("runtime execution")
    elif not bundle.is_unresolved:
        bundle.require_canonical_authority("runtime execution")
    workflow = bundle.workflow
    resolved_config = config or SessionConfig.from_workflow_metadata(workflow)
    run_id, run_dir = (
        (run_context.run_id, run_context.run_dir) if run_context is not None
        else _allocate_run_dir("run", runtime_root=resolved_config.runtime_root)
    )
    # An explicit server owns its process and filesystem.  Do not hand callers
    # a local path that this adapter never created.
    log_path = run_dir / "comfy.log" if server_url is None else None
    managed_config = resolved_config if server_url is None else None
    lifecycle_adapter = None
    lifecycle_details: dict[str, Any] | None = None
    if isinstance(runtime_target, Mapping):
        candidate = runtime_target.get("_runpod_lifecycle_adapter")
        if candidate is not None:
            if not callable(getattr(candidate, "attach", None)):
                raise WorkflowBundleError("bound RunPod lifecycle adapter is invalid")
            lifecycle_adapter = candidate
            describe = getattr(candidate, "describe", None)
            if callable(describe):
                described = describe()
                if isinstance(described, Mapping):
                    lifecycle_details = dict(described)
    runtime_adapter_kind = (
        "runpod_lifecycle"
        if lifecycle_adapter is not None
        else "external"
        if server_url is not None
        else "managed"
    )
    try:
        dependency_report = _dependency_check(
            workflow,
            config=resolved_config,
            dependency_mode=dependency_mode,
            server_url=server_url,
            target=runtime_target,
            dependency_report=dependency_report,
        )
    except RuntimeDependencyError as exc:
        dependency_report = getattr(exc, "dependency_report", None)
        if not isinstance(dependency_report, Mapping):
            dependency_report = {
                "declared": True, "mode": dependency_mode, "status": "error",
                "checks": [], "mismatches": [], "warnings": [], "changes": [],
                "error": str(exc),
            }
        try:
            attempt_bundle, journal_state, journal_generation, _initial = _begin_runtime_lifecycle(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind=runtime_adapter_kind,
                backend=backend, endpoint=server_url,
                dependency_report=dependency_report,
                adapter_details=lifecycle_details,
            )
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc,
                queue_acceptance={"status": "not_attempted", "prompt_id": None},
                phase="dependencies", exc=exc,
            )
        except Exception:
            logger.exception("could not persist dependency failure receipt for %s", run_id)
        raise
    runtime_declared = getattr(workflow.requirements, "runtime", None)
    if runtime_declared is not None and runtime_declared.launch_flags:
        resolved_config.extra["launch_flags"] = list(runtime_declared.launch_flags)
    policy = resolve_model_preflight_policy(
        mode="managed_local_server" if server_url is None else "explicit_remote_server_unverified",
        ensure_models=ensure_models,
        shared_root=shared_models_root,
    )
    async with comfy_server(server_url=server_url, log_path=log_path, config=managed_config) as active_url:
        adapter_kind = runtime_adapter_kind
        attempt_bundle, journal_state, journal_generation, initial_evidence = _begin_runtime_lifecycle(
            run_dir=run_dir,
            run_id=run_id,
            record=record,
            bundle=bundle,
            adapter_kind=adapter_kind,
            backend=backend,
            endpoint=active_url,
            dependency_report=dependency_report,
            adapter_details=lifecycle_details,
        )
        if lifecycle_adapter is not None:
            try:
                attached = await lifecycle_adapter.attach()
                if not isinstance(attached, Mapping):
                    raise RuntimeError("RunPod lifecycle adapter returned an invalid attach witness")
                lifecycle_details = dict(attached)
                attempt_bundle["adapter"] = {
                    **dict(attempt_bundle.get("adapter") or {}),
                    "lifecycle": dict(lifecycle_details),
                }
                attempt_bundle.setdefault("runtime_evidence", {})["adapter"] = dict(
                    attempt_bundle["adapter"]
                )
                write_attempt_json(run_dir, attempt_bundle)
            except Exception as exc:
                _persist_runtime_failure(
                    run_dir=run_dir,
                    attempt_bundle=attempt_bundle,
                    state=journal_state,
                    run_id=run_id,
                    record=record,
                    generation=journal_generation,
                    original_error=exc,
                    queue_acceptance={"status": "not_attempted", "prompt_id": None},
                    phase="target",
                    exc=exc,
                )
                raise
        if runtime_declared is not None and server_url is None:
            from .dependencies import compare_runtime, inspect_runtime_target

            started_target = inspect_runtime_target(
                runtime_root=resolved_config.runtime_root,
                package_names=[name for name, _constraint in runtime_declared.packages],
            )
            # comfy_server uses this exact argv builder for the process it just
            # started; retain the complete argv as the launch observation so
            # declared flags are verified against the selected process.
            started_target["launch_flags"] = list(_comfy_server_argv(resolved_config))
            started_target["managed"] = True
            started_report = compare_runtime(
                runtime_declared,
                target=started_target,
                runtime_root=resolved_config.runtime_root,
            )
            started_report["mode"] = dependency_report.get("mode", dependency_mode)
            started_report["changes"] = list(dependency_report.get("changes", []))
            for key in ("actions", "synced", "managed"):
                if key in dependency_report:
                    started_report[key] = dependency_report[key]
            dependency_report = started_report
            if not started_report.get("ok", True):
                exc = RuntimeDependencyError(
                    "started managed runtime is not compatible with this workflow: "
                    + "; ".join(str(item) for item in started_report.get("mismatches", ()))
                )
                setattr(exc, "dependency_report", started_report)
                _persist_runtime_failure(
                    run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                    run_id=run_id, record=record, generation=journal_generation,
                    original_error=exc,
                    queue_acceptance={"status": "not_attempted", "prompt_id": None},
                    phase="dependencies", exc=exc,
                )
                raise exc
        # Query the actual process generation immediately before the final
        # approval/queue boundary.  This is also the recovery path for a
        # marked source whose presentation companion is stale: the semantic
        # Python draft is retained, the companion is rebuilt transactionally,
        # and the API record is recompiled from that corrected IR.
        from .reconciliation import ReconciliationError, reconcile_before_queue_async

        live_provider = schema_provider
        if live_provider is None or not getattr(live_provider, "requires_fresh_target", False):
            live_provider = _build_schema_provider(active_url)
        can_reconcile = callable(getattr(live_provider, "object_info", None)) or callable(
            getattr(live_provider, "refresh", None)
        ) or callable(getattr(live_provider, "object_info_async", None))
        try:
            reconciliation = (
                await reconcile_before_queue_async(
                    bundle,
                    target_schema_provider=live_provider,
                    publish=True,
                )
                if live_provider is not None and can_reconcile
                else None
            )
        except ReconciliationError as exc:
            # The pre-load lifecycle witness is already allocated above. Keep
            # this failure on that same attempt instead of opening a second
            # receipt/journal generation for one queue attempt.
            attempt_bundle["schema_reconciliation"] = list(exc.diagnostics)
            _persist_runtime_failure(
                run_dir=run_dir,
                attempt_bundle=attempt_bundle,
                state=journal_state,
                run_id=run_id,
                record=record,
                generation=journal_generation,
                original_error=exc,
                queue_acceptance={"status": "not_attempted", "prompt_id": None},
                phase="mapping",
                exc=exc,
            )
            raise
        reconciliation_schema = reconciliation.schema if reconciliation is not None else None
        if reconciliation is not None and reconciliation.bundle is not bundle:
            bundle = reconciliation.bundle
            # The reconciled/reloaded bundle is the immutable execution
            # snapshot. Every later gate must consume this same workflow;
            # retaining the pre-reconciliation local would reintroduce stale
            # model and semantic inputs.
            workflow = bundle.workflow
            record = bundle.compile(
                run_inputs=dict(record.input_binding),
                schema_provider=live_provider,
            )
        execution_snapshot = build_execution_snapshot(
            bundle,
            record,
            schema=reconciliation_schema,
        ).to_dict()
        schema_provider = live_provider
        schema_provenance = _schema_provider_provenance(live_provider)
        queue_acceptance = {"status": "not_attempted", "prompt_id": None}
        warned = {"emitted": False}
        dependency_report = dict(dependency_report)
        phase = "schema"

        def on_unavailable(msg: str) -> None:
            if warned["emitted"] and "schema validation skipped for class types" not in msg:
                return
            logger.log(logging.WARNING if _schema_warn_only(resolved_config) else logging.ERROR, "vibecomfy schema gate: %s", msg)
            warned["emitted"] = True

        try:
            attempt_bundle["dependency_report"] = dependency_report
            write_attempt_json(run_dir, attempt_bundle)
            apply_model_preflight(workflow, policy)
            provider = schema_provider if schema_provider is not None else _build_schema_provider(active_url)
            api_dict = await _prepare_prompt_async(
                record,
                bundle,
                backend=backend,
                schema_provider=provider,
                on_unavailable=on_unavailable,
            )
            assert_execution_snapshot(
                execution_snapshot, bundle, record, schema_provider=provider
            )
            schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
            schema_provenance = dict(getattr(api_dict, "schema_provenance", {})) or _schema_provider_provenance(provider)
            evidence = _runtime_evidence(
                record,
                adapter_kind=adapter_kind,
                backend=backend,
                endpoint=active_url,
                dependency_report=dependency_report,
                schema_provenance=schema_provenance,
                queue_acceptance=queue_acceptance,
                terminal={"phase": "prepared", "reason_type": "none", "reason": None, "acceptance_known": False},
                adapter_details=lifecycle_details,
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
                runtime_compatibility=dependency_report,
            )
            attempt_bundle["execution_snapshot"] = execution_snapshot
            _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
            phase = "drift"
            resolved_strict = strict_drift if strict_drift is not None else bool(resolved_config.strict_drift)
            if resolved_strict:
                enforce_strict_drift(
                    workflow, lockfile_path=resolved_config.extra.get("lockfile")
                )
            phase = "queue"
            try:
                queued = (
                    await queue_server_prompt(record, bundle, client=ComfyClient(active_url))
                ).queued
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                wrapped = QueueError(
                    _workflow_queue_failure_message(workflow, exc), next_action="vibecomfy runtime doctor"
                )
                for attribute in ("diagnostics", "prompt_id", "output_verification", "completion_status"):
                    if hasattr(exc, attribute):
                        setattr(wrapped, attribute, getattr(exc, attribute))
                raise wrapped from exc
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
            output_verification = _validate_declared_output_contract(workflow, history, prompt_id)
            # Keep terminal status/error decoding authoritative even when the
            # declared-sink filter below selects a subset of history outputs.
            _outputs_from_server_history(history, prompt_id)
            comfy_outputs = _declared_outputs_from_server_history(workflow, history, prompt_id)
            phase = "output"
            output_directory = _configured_output_directory(resolved_config)
            artifacts = _artifact_records(
                comfy_outputs,
                adapter_kind=adapter_kind,
                adapter_endpoint=active_url,
                output_directory=output_directory,
            )
            outputs = [artifact["reported_path"] for artifact in artifacts]
            attempt_bundle.update({
                "prompt_id": prompt_id,
                "output_verification": dict(output_verification),
                "artifacts": [dict(item) for item in artifacts],
                "artifact_paths": list(outputs),
            })
            write_attempt_json(run_dir, attempt_bundle)
            if lifecycle_adapter is not None:
                phase = "retrieval"
                lifecycle_details = dict(lifecycle_details or {})
                try:
                    retrieval = await lifecycle_adapter.download_artifacts(
                        local_root=run_dir / "downloaded-artifacts"
                    )
                except Exception as exc:
                    diagnostic = {
                        "code": "runpod_lifecycle_artifact_retrieval_failed",
                        "detail": str(exc),
                    }
                    error = RuntimeNodeError(
                        "RunPod lifecycle artifact retrieval failed after generation was accepted",
                        next_action="inspect the lifecycle SSH/archive evidence and retry retrieval",
                    )
                    error.diagnostics = [diagnostic]
                    retrieval_failure = {"status": "failed", **diagnostic}
                    lifecycle_details["retrieval"] = retrieval_failure
                    log_path = await _capture_lifecycle_log(
                        lifecycle_adapter,
                        run_dir=run_dir,
                        lifecycle_details=lifecycle_details,
                    )
                    attempt_bundle["adapter"] = {
                        **dict(attempt_bundle.get("adapter") or {}),
                        "lifecycle": dict(lifecycle_details),
                    }
                    attempt_bundle["lifecycle_retrieval"] = retrieval_failure
                    attempt_bundle["log_path"] = log_path
                    attempt_bundle["log_provenance"] = dict(lifecycle_details.get("logs") or {})
                    write_attempt_json(run_dir, attempt_bundle)
                    raise _delivery_failure(
                        error,
                        output_verification=output_verification,
                        artifacts=artifacts,
                        retrieval=retrieval_failure,
                    ) from exc
                if not isinstance(retrieval, Mapping) or retrieval.get("status") != "retrieved":
                    diagnostic = {
                        "code": "runpod_lifecycle_artifacts_unavailable",
                        **(dict(retrieval) if isinstance(retrieval, Mapping) else {}),
                    }
                    error = RuntimeNodeError(
                        "RunPod lifecycle did not retrieve the accepted final artifact",
                        next_action="inspect the remote output directory and lifecycle download logs",
                    )
                    error.diagnostics = [diagnostic]
                    retrieval_failure = {"status": "failed", **diagnostic}
                    lifecycle_details["retrieval"] = retrieval_failure
                    log_path = await _capture_lifecycle_log(
                        lifecycle_adapter,
                        run_dir=run_dir,
                        lifecycle_details=lifecycle_details,
                    )
                    attempt_bundle["adapter"] = {
                        **dict(attempt_bundle.get("adapter") or {}),
                        "lifecycle": dict(lifecycle_details),
                    }
                    attempt_bundle["lifecycle_retrieval"] = retrieval_failure
                    attempt_bundle["log_path"] = log_path
                    attempt_bundle["log_provenance"] = dict(lifecycle_details.get("logs") or {})
                    write_attempt_json(run_dir, attempt_bundle)
                    raise _delivery_failure(
                        error,
                        output_verification=output_verification,
                        artifacts=artifacts,
                        retrieval=retrieval_failure,
                    )
                local_artifact_root = Path(str(retrieval.get("local_root")))
                if _bind_downloaded_lifecycle_artifacts(artifacts, local_artifact_root) < len(artifacts):
                    error = RuntimeNodeError(
                        "RunPod lifecycle archive did not contain every accepted output artifact",
                        next_action="inspect the remote output directory and final sink attribution",
                    )
                    error.diagnostics = [{
                        "code": "runpod_lifecycle_artifact_mapping_incomplete",
                        "local_root": str(local_artifact_root),
                        "reported_outputs": list(outputs),
                    }]
                    retrieval_failure = {
                        "status": "failed",
                        "code": "runpod_lifecycle_artifact_mapping_incomplete",
                        "local_root": str(local_artifact_root),
                    }
                    lifecycle_details["retrieval"] = retrieval_failure
                    log_path = await _capture_lifecycle_log(
                        lifecycle_adapter,
                        run_dir=run_dir,
                        lifecycle_details=lifecycle_details,
                    )
                    attempt_bundle["adapter"] = {
                        **dict(attempt_bundle.get("adapter") or {}),
                        "lifecycle": dict(lifecycle_details),
                    }
                    attempt_bundle["lifecycle_retrieval"] = retrieval_failure
                    attempt_bundle["log_path"] = log_path
                    attempt_bundle["log_provenance"] = dict(lifecycle_details.get("logs") or {})
                    write_attempt_json(run_dir, attempt_bundle)
                    raise _delivery_failure(
                        error,
                        output_verification=output_verification,
                        artifacts=artifacts,
                        retrieval=retrieval_failure,
                    )
                lifecycle_details["retrieval"] = dict(retrieval)
                log_path = await _capture_lifecycle_log(
                    lifecycle_adapter,
                    run_dir=run_dir,
                    lifecycle_details=lifecycle_details,
                )
                attempt_bundle["adapter"] = {
                    **dict(attempt_bundle.get("adapter") or {}),
                    "lifecycle": dict(lifecycle_details),
                }
                attempt_bundle["lifecycle_retrieval"] = dict(retrieval)
                attempt_bundle["artifacts"] = [dict(item) for item in artifacts]
                attempt_bundle["local_artifact_paths"] = [
                    item["path"] for item in artifacts if item.get("path")
                ]
                write_attempt_json(run_dir, attempt_bundle)
            phase = "verification"
            media_validation = _verify_declared_media(
                workflow,
                artifacts,
                adapter_kind=adapter_kind,
                output_verification=output_verification,
            )
            output_verification = {**output_verification, "media": media_validation}
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
                log_path=log_path,
                external_log_locator=(
                    _external_log_locator(resolved_config)
                    if adapter_kind == "external"
                    else None
                ),
                artifacts=artifacts,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                dependency_report=dependency_report,
                output_verification=output_verification,
                media_validation=media_validation,
                adapter_details=lifecycle_details,
            )
            metadata_path = _complete_runtime_run(
                run_dir=run_dir, attempt_bundle=attempt_bundle, journal_state=journal_state,
                run_id=run_id, record=record, journal_generation=journal_generation,
                adapter_kind=adapter_kind, backend=backend, endpoint=active_url,
                schema_provenance=schema_provenance, queue_acceptance=queue_acceptance,
                metadata=metadata,
                dependency_report=dependency_report,
                adapter_details=lifecycle_details,
            )
            return RunResult(
                run_id=run_id,
                prompt_id=prompt_id,
                outputs=outputs,
                metadata_path=str(metadata_path),
                log_path=str(log_path) if log_path is not None else None,
                completion_path=str(Path(metadata_path).with_name("completion.json")),
                status=str(metadata.get("status", "completed")),
                media_validated=bool(metadata.get("media_validated", False)),
                artifacts=list(metadata.get("artifacts", [])),
                log_provenance=dict(metadata.get("log_provenance", {})),
            )
        except asyncio.CancelledError as exc:
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        except KeyboardInterrupt as exc:
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        except Exception as exc:
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise


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
    schema_provider: Any | None = None,
    dependency_mode: str = "reuse",
    runtime_target: Mapping[str, Any] | None = None,
    dependency_report: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> RunResult:
    kwargs = {
        "server_url": server_url,
        "backend": backend,
        "config": config,
        "ensure_models": ensure_models,
        "shared_models_root": shared_models_root,
        "strict_drift": strict_drift,
        "chain_id": chain_id,
        "parent_run_id": parent_run_id,
    }
    if schema_provider is not None:
        kwargs["schema_provider"] = schema_provider
    if dependency_mode != "reuse":

        kwargs["dependency_mode"] = dependency_mode
    if runtime_target is not None:
        kwargs["runtime_target"] = runtime_target
    if dependency_report is not None:
        kwargs["dependency_report"] = dependency_report
    if run_context is not None:
        kwargs["run_context"] = run_context
    return asyncio.run(run(record, bundle, **kwargs))

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
    dependency_mode: str = "reuse",
    dependency_report: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> RunResult:
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime run requires an ApprovedProjectionRecord and WorkflowBundle")
    bundle.require_canonical_authority("runtime execution")
    session = EmbeddedSession(config or SessionConfig.from_workflow_metadata(bundle.workflow))
    try:
        kwargs: dict[str, Any] = {
            "backend": backend,
            "ensure_packs": ensure_packs,
            "ensure_models": ensure_models,
            "strict_drift": strict_drift,
            "chain_id": chain_id,
            "parent_run_id": parent_run_id,
        }
        if dependency_mode != "reuse":
            kwargs["dependency_mode"] = dependency_mode
        if dependency_report is not None:
            kwargs["dependency_report"] = dependency_report
        if run_context is not None:
            kwargs["run_context"] = run_context
        return await session.run(record, bundle, **kwargs)
    finally:
        await session.stop()


async def run_embedded_with_session(
    session: EmbeddedSession,
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    backend: str = "api",
    ensure_packs: bool = False,
    ensure_models: bool = False,
    strict_drift: bool | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
    dependency_mode: str = "reuse",
    dependency_report: Mapping[str, Any] | None = None,
) -> RunResult:
    """Run one task on a caller-owned embedded session without stopping it."""
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime run requires an ApprovedProjectionRecord and WorkflowBundle")
    bundle.require_canonical_authority("runtime execution")
    kwargs: dict[str, Any] = {
        "backend": backend,
        "ensure_packs": ensure_packs,
        "ensure_models": ensure_models,
        "strict_drift": strict_drift,
        "chain_id": chain_id,
        "parent_run_id": parent_run_id,
    }
    if dependency_mode != "reuse":
        kwargs["dependency_mode"] = dependency_mode
    if dependency_report is not None:
        kwargs["dependency_report"] = dependency_report
    return await session.run(record, bundle, **kwargs)

class EmbeddedSessionOwner:
    """Host-owned serial ``EmbeddedSession`` with one persistent event loop.

    A persistent async session cannot safely be driven by repeated
    ``asyncio.run`` calls because its Comfy context belongs to one event loop.
    This owner therefore keeps one private loop/thread, serializes all task
    calls through it, and stops the session only at explicit owner shutdown.
    ``EmbeddedSession`` remains the real runtime session class; this is only
    its lifetime/loop owner.
    """

    def __init__(self, config: SessionConfig | None = None) -> None:
        self._config = config or SessionConfig()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._thread_error: BaseException | None = None
        self._session: EmbeddedSession | None = None
        self._closed = False
        self._operation_lock = threading.Lock()
        self._incarnation_id = uuid.uuid4().hex
        self._thread = threading.Thread(
            target=self._thread_main,
            name="vibecomfy-embedded-session-owner",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait()
        if self._thread_error is not None:
            raise RuntimeError("embedded session owner event loop failed to start") from self._thread_error

    @property
    def incarnation_id(self) -> str:
        return self._incarnation_id

    @property
    def closed(self) -> bool:
        return self._closed

    def _thread_main(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            loop.run_forever()
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except BaseException as exc:  # pragma: no cover - startup/runtime fatal path
            self._thread_error = exc
            self._ready.set()

    def _submit(self, coroutine: Any) -> Any:
        with self._operation_lock:
            if self._closed:
                coroutine.close()
                raise RuntimeError("embedded session owner is closed")
            if self._loop is None:
                coroutine.close()
                raise RuntimeError("embedded session owner event loop is unavailable")
            future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
            try:
                return future.result()
            except concurrent.futures.CancelledError as exc:
                raise RuntimeError("embedded session owner task was cancelled") from exc

    @staticmethod
    def _verify_rebound_output(session: EmbeddedSession, config: SessionConfig) -> None:
        expected = config.extra.get("output_directory")
        if expected is None:
            return
        snapshot = getattr(session, "_process_configuration", None)
        if snapshot is None or "output_directory" not in snapshot.values:
            raise RuntimeError("embedded output rebind was not independently observable")
        expected_path = Path(expected).expanduser()
        if not expected_path.is_absolute():
            expected_path = Path(config.cwd) / expected_path
        if Path(snapshot.values["output_directory"]).resolve() != expected_path.resolve():
            raise RuntimeError("embedded output rebind did not match the requested spool")

    async def _run(
        self,
        record: ApprovedProjectionRecord,
        bundle: WorkflowBundle,
        *,
        config: SessionConfig | None,
        backend: str,
        ensure_packs: bool,
        ensure_models: bool,
        strict_drift: bool | None,
        chain_id: str | None,
        parent_run_id: str | None,
        dependency_mode: str,
        dependency_report: Mapping[str, Any] | None,
    ) -> RunResult:
        selected = config or self._config
        if self._session is None:
            self._session = EmbeddedSession(selected)
            await self._session.start()
        elif config is not None:
            await self._session.reconfigure(selected)
        self._config = selected
        self._verify_rebound_output(self._session, selected)
        return await run_embedded_with_session(
            self._session,
            record,
            bundle,
            backend=backend,
            ensure_packs=ensure_packs,
            ensure_models=ensure_models,
            strict_drift=strict_drift,
            chain_id=chain_id,
            parent_run_id=parent_run_id,
            dependency_mode=dependency_mode,
            dependency_report=dependency_report,
        )

    def run(
        self,
        record: ApprovedProjectionRecord,
        bundle: WorkflowBundle,
        *,
        config: SessionConfig | None = None,
        backend: str = "api",
        ensure_packs: bool = False,
        ensure_models: bool = False,
        strict_drift: bool | None = None,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        dependency_mode: str = "reuse",
        dependency_report: Mapping[str, Any] | None = None,
    ) -> RunResult:
        return self._submit(
            self._run(
                record,
                bundle,
                config=config,
                backend=backend,
                ensure_packs=ensure_packs,
                ensure_models=ensure_models,
                strict_drift=strict_drift,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                dependency_mode=dependency_mode,
                dependency_report=dependency_report,
            )
        )

    async def _close(self) -> None:
        if self._session is not None:
            await self._session.stop()
            self._session = None

    def close(self) -> None:
        with self._operation_lock:
            if self._closed:
                return
            if self._loop is not None:
                future = asyncio.run_coroutine_threadsafe(self._close(), self._loop)
                future.result()
                self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                raise RuntimeError("embedded session owner event loop did not stop")
            self._closed = True

    def __enter__(self) -> "EmbeddedSessionOwner":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


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
    dependency_mode: str = "reuse",
    dependency_report: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
) -> RunResult:
    kwargs: dict[str, Any] = {
        "backend": backend,
        "config": config,
        "ensure_packs": ensure_packs,
        "ensure_models": ensure_models,
        "strict_drift": strict_drift,
        "chain_id": chain_id,
        "parent_run_id": parent_run_id,
    }
    if dependency_mode != "reuse":
        kwargs["dependency_mode"] = dependency_mode
    if dependency_report is not None:
        kwargs["dependency_report"] = dependency_report
    if run_context is not None:
        kwargs["run_context"] = run_context
    return asyncio.run(run_embedded(record, bundle, **kwargs))


async def smoke_runtime(*, server_url: str | None = None) -> dict[str, Any]:
    run_id, run_dir = _allocate_run_dir("smoke")
    log_path = run_dir / "comfy.log" if server_url is None else None
    async with comfy_server(server_url=server_url, log_path=log_path) as active_url:
        client = ComfyClient(active_url)
        objects = await client.object_info()
    return {
        "run_id": run_id,
        "server_url": server_url or "managed",
        "node_count": len(objects),
        "log_path": str(log_path) if log_path is not None else None,
    }


def smoke_runtime_sync(*, server_url: str | None = None) -> dict[str, Any]:
    return asyncio.run(smoke_runtime(server_url=server_url))
