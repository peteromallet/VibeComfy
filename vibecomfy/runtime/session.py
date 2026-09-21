from __future__ import annotations

import asyncio
import ctypes
import datetime
import hashlib
import json
import mimetypes
import re
import logging
import math
import os
import signal
import socket
import struct
import subprocess
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Mapping, Protocol, Sequence

from vibecomfy.comfy_command import comfyui_command
from vibecomfy.errors import (
    MODEL_DOCTOR_NEXT_ACTION,
    ModelAssetError,
    QueueError,
    RuntimeConfigurationError,
    RuntimeNodeError,
    RuntimeStartupError,
    SchemaValidationError,
    WorkflowBuildError,
    VibeComfyError,
    _safe_value_label,
)
from vibecomfy.memory_profile import MemoryProfile, apply_memory_profile_overrides
from vibecomfy.utils import atomic_write_json, find_repo_root
from vibecomfy.workflow import VibeWorkflow
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundle,
    WorkflowBundleError,
    canonical_digest,
)
from .dependencies import RuntimeDependencyError

from .attempt import build_attempt_bundle, build_shared_fields, write_attempt_json
from .run_context import RunContext
from .client import ComfyClient
from .drift import enforce_strict_drift
from .execution import (
    authorized_queue_payload,
    normalize_prompt_id,
    queue_embedded_prompt,
    queue_server_prompt,
)
from .model_policy import apply_model_preflight, resolve_model_preflight_policy
from .watchdog import Watchdog, write_report

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from comfy.cli_args_types import Configuration
else:
    Configuration = Any


OVERRIDES_INCLUDE: set[str] = set()
OVERRIDES_EXCLUDE: set[str] = set()

# These values are schema defaults, not model selections.  They must not
# perturb the runtime model fingerprint when a ready template or ComfyUI
# snapshot happens to materialize the default explicitly.
_MODEL_FINGERPRINT_DEFAULTS: dict[str, dict[str, str]] = {
    "UNETLoader": {"weight_dtype": "default"},
    "CLIPLoader": {"device": "default"},
}


def _require_runtime_boundary(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
) -> VibeWorkflow:
    if not isinstance(record, ApprovedProjectionRecord):
        raise WorkflowBundleError(
            "runtime session requires an ApprovedProjectionRecord"
        )
    if not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime session requires a WorkflowBundle")
    return bundle.workflow


def _schema_provider_provenance(provider: Any | None, *, failure: str | None = None) -> dict[str, Any]:
    """Return deterministic schema evidence without creating a second receipt authority."""
    provenance: dict[str, Any] = {
        "provider": type(provider).__name__ if provider is not None else None,
        "validation": "structural-only" if provider is None else "object-info",
        "authority": getattr(provider, "schema_authority", None) if provider is not None else None,
        "fresh_target": bool(getattr(provider, "requires_fresh_target", False)) if provider is not None else False,
        "object_info_loaded": False,
        "schema_digest": None,
        "digest_algorithm": "sha256",
        "digest_canonicalization": "object_info_payload_checksum",
    }
    if provider is not None:
        approval_diagnostics = getattr(provider, "_approval_diagnostics", None)
        if isinstance(approval_diagnostics, list) and approval_diagnostics:
            provenance["approval_diagnostics"] = [
                dict(item) for item in approval_diagnostics if isinstance(item, Mapping)
            ]
        for key in ("server_url", "cache_path", "log_path"):
            value = getattr(provider, key, None)
            if value is not None:
                provenance[key] = str(value)
        object_info = getattr(provider, "_object_info", None)
        if isinstance(object_info, Mapping):
            from vibecomfy.schema.cache import object_info_payload_checksum

            provenance["object_info_loaded"] = True
            provenance["schema_digest"] = object_info_payload_checksum(dict(object_info))
            active_url = getattr(provider, "_active_server_url", None)
            if active_url is not None:
                provenance["target_server_url"] = str(active_url)
        elif failure is None:
            provenance["validation"] = "object-info-unavailable"
    if failure:
        provenance["failure"] = str(failure)
    return provenance


def _runtime_evidence(
    record: ApprovedProjectionRecord,
    *,
    adapter_kind: str,
    backend: str,
    endpoint: str | None,
    schema_provenance: Mapping[str, Any] | None = None,
    queue_acceptance: Mapping[str, Any] | None = None,
    terminal: Mapping[str, Any] | None = None,
    dependency_report: Mapping[str, Any] | None = None,
    adapter_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    approved = record.to_dict()
    acceptance = {
        "status": "not_attempted",
        "prompt_id": None,
    }
    if queue_acceptance is not None:
        acceptance.update(dict(queue_acceptance))
    acceptance_status = acceptance.get("status")
    terminal_default = {
        "phase": "prepared",
        "reason_type": "none",
        "reason": None,
        "acceptance_known": acceptance_status in {"accepted", "rejected"},
    }
    if terminal is not None:
        terminal_default.update(dict(terminal))
    adapter = {
        "kind": adapter_kind,
        "backend": backend,
        "endpoint": endpoint,
    }
    if adapter_details:
        adapter["lifecycle"] = dict(adapter_details)
    evidence = {
        "approved_projection": approved,
        "api_digest": record.api_digest,
        "ui_digest": canonical_digest(approved["ui_projection"]),
        "record_digest": canonical_digest(approved),
        "adapter": adapter,
        "schema_provenance": dict(schema_provenance or _schema_provider_provenance(None)),
        "queue_acceptance": acceptance,
        "terminal": terminal_default,
    }
    if dependency_report and dependency_report.get("declared") is not False:
        evidence["dependency_report"] = dict(dependency_report)
    return evidence


def _session_dependency_target(
    session: Any, *, package_names: Sequence[str] | None = None
) -> dict[str, Any]:
    """Capture the managed session's observable runtime boundary."""
    from .dependencies import inspect_runtime_target

    config = session.config
    target = inspect_runtime_target(
        runtime_root=config.runtime_root, package_names=package_names
    )
    snapshot = getattr(session, "_process_configuration", None)
    argv = getattr(session, "_argv", None)
    if isinstance(argv, (list, tuple)) and argv:
        target["launch_flags"] = list(argv)
    elif snapshot is not None and isinstance(snapshot.values.get("launch_flags"), (list, tuple)):
        # An active embedded session must be compared with the immutable
        # configuration captured when its Comfy context was created.
        target["launch_flags"] = list(snapshot.values["launch_flags"])
    elif isinstance(config.extra.get("launch_flags"), (list, tuple)):
        target["launch_flags"] = list(config.extra["launch_flags"])
    if config.runtime_root is not None:
        target["runtime_root"] = str(config.runtime_root)
    target["managed"] = True
    return target


def _runtime_package_names(workflow: VibeWorkflow) -> list[str]:
    runtime = getattr(workflow.requirements, "runtime", None)
    return [name for name, _constraint in runtime.packages] if runtime is not None else []


def _bind_runtime_launch_flags(config: SessionConfig, workflow: VibeWorkflow) -> None:
    runtime = getattr(workflow.requirements, "runtime", None)
    if runtime is not None and runtime.launch_flags:
        config.extra["launch_flags"] = list(runtime.launch_flags)


def _initial_attempt_bundle(record: ApprovedProjectionRecord, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {"runtime_evidence": dict(evidence)}


def _persist_runtime_evidence(
    run_dir: Path,
    attempt_bundle: dict[str, Any],
    evidence: Mapping[str, Any],
) -> None:
    attempt_bundle["runtime_evidence"] = dict(evidence)
    attempt_bundle["queue_acceptance"] = dict(evidence["queue_acceptance"])
    attempt_bundle["terminal"] = dict(evidence["terminal"])
    attempt_bundle["adapter"] = dict(evidence["adapter"])
    attempt_bundle["schema_provenance"] = dict(evidence["schema_provenance"])
    if evidence.get("dependency_report"):
        attempt_bundle["dependency_report"] = dict(evidence["dependency_report"])
    write_attempt_json(run_dir, attempt_bundle)


def _journal_prepare(
    run_dir: Path,
    run_id: str,
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    from vibecomfy.comfy_nodes.agent import _session_transaction_journal as journal

    state: dict[str, Any] = {}
    event = journal.record_prepared_transaction_impl(
        state=state,
        turn_dir=run_dir,
        turn_id=run_id,
        plan_hash=record.api_digest,
        revision_id=record.revision_id,
        parent_revision=bundle.parent_revision,
        lease_nonce=run_id,
        structural_hash_before=None,
        candidate_payload=None,
        runtime_evidence=evidence,
    )
    state["revision_id"] = record.revision_id
    state["parent_revision"] = bundle.parent_revision
    return state, int(event["generation"])


def _journal_terminal(
    state: dict[str, Any],
    run_dir: Path,
    run_id: str,
    record: ApprovedProjectionRecord,
    generation: int,
    evidence: Mapping[str, Any],
    *,
    event_type: str,
    reason: str | None = None,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent import _session_transaction_journal as journal

    common = {
        "state": state,
        "turn_dir": run_dir,
        "turn_id": run_id,
        "plan_hash": record.api_digest,
        "generation": generation,
        "runtime_evidence": evidence,
    }
    if event_type == "finalized":
        return journal.record_finalized_transaction_impl(
            **common,
            revision_id=record.revision_id,
            parent_revision=state.get("parent_revision"),
            structural_hash_after=None,
            applied_payload=None,
        )
    if event_type == "superseded":
        return journal.record_cancelled_transaction_impl(
            **common,
            reason=reason,
        )
    return journal.record_discarded_transaction_impl(
        **common,
        reason=reason or "runtime_failure",
    )


def _terminal_event_already_written(
    run_dir: Path, record: ApprovedProjectionRecord, generation: int
) -> bool:
    """Detect an append-only terminal event after a derived receipt failure."""
    lifecycle_path = (
        run_dir
        / "transactions"
        / record.api_digest
        / "lifecycle_events.jsonl"
    )
    try:
        lines = lifecycle_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return False
        latest = json.loads(lines[-1])
        return (
            isinstance(latest, Mapping)
            and latest.get("generation") == generation
            and latest.get("event_type") in {"finalized", "discarded", "superseded"}
        )
    except (OSError, ValueError, TypeError):
        return False


def _runtime_failure_evidence(
    record: ApprovedProjectionRecord,
    *,
    adapter_kind: str,
    backend: str,
    endpoint: str | None,
    schema_provenance: Mapping[str, Any] | None,
    queue_acceptance: Mapping[str, Any],
    phase: str,
    exc: BaseException,
    queue_started: bool,
    interrupted: bool = False,
    dependency_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status = str(queue_acceptance.get("status", "not_attempted"))
    prompt_id = queue_acceptance.get("prompt_id")
    if prompt_id is None:
        cursor_for_prompt: BaseException | None = exc
        seen_prompt: set[int] = set()
        while cursor_for_prompt is not None and id(cursor_for_prompt) not in seen_prompt:
            seen_prompt.add(id(cursor_for_prompt))
            candidate_prompt = getattr(cursor_for_prompt, "prompt_id", None)
            if candidate_prompt is not None:
                prompt_id = str(candidate_prompt)
                status = "unknown" if status == "not_attempted" else status
                break
            cursor_for_prompt = cursor_for_prompt.__cause__ or cursor_for_prompt.__context__
    cursor: BaseException | None = exc
    timed_out = False
    while cursor is not None:
        if isinstance(cursor, (asyncio.TimeoutError, TimeoutError)):
            timed_out = True
            break
        cursor = cursor.__cause__
    if interrupted:
        if status != "accepted":
            status = "unknown" if queue_started else "not_attempted"
        terminal_phase = "interrupted" if isinstance(exc, KeyboardInterrupt) else "cancelled"
        reason_type = "KeyboardInterrupt" if isinstance(exc, KeyboardInterrupt) else "CancelledError"
    elif phase == "queue":
        if status != "accepted":
            status = "unknown" if timed_out else "rejected"
        terminal_phase, reason_type = phase, "TimeoutError" if timed_out else type(exc).__name__
    elif phase == "acceptance_witness":
        status, terminal_phase = "unknown", phase
        reason_type = "persistence" if isinstance(exc, OSError) else type(exc).__name__
    else:
        terminal_phase, reason_type = phase, type(exc).__name__
    reason = str(exc) or reason_type
    terminal: dict[str, Any] = {
        "phase": terminal_phase,
        "reason_type": reason_type,
        "reason": reason,
        "acceptance_known": status in {"accepted", "rejected"},
    }
    diagnostics = _exception_diagnostics(exc)
    if diagnostics:
        terminal["diagnostics"] = diagnostics
    output_verification = _exception_output_verification(exc)
    delivery_state = _exception_delivery_state(exc)
    media = output_verification.get("media") if isinstance(output_verification, Mapping) else None
    external_retrieval_failure = bool(
        phase == "output"
        and status == "accepted"
        and isinstance(media, Mapping)
        and media.get("adapter_kind") == "external"
        and media.get("status") != "verified"
    )
    delivery_retrieval = (
        delivery_state.get("retrieval") if isinstance(delivery_state, Mapping) else None
    )
    delivery_retrieval_failure = bool(
        isinstance(delivery_retrieval, Mapping)
        and delivery_retrieval.get("status") == "failed"
    )
    if external_retrieval_failure or delivery_retrieval_failure:
        terminal["completion_status"] = "Incomplete — generation verified but retrieval failed"
    elif output_verification is not None:
        terminal["completion_status"] = "Failed — final output rejected"
    elif phase in {"download", "retrieval", "logs"} or (
        phase == "output" and status == "accepted"
    ):
        terminal["completion_status"] = "Incomplete — generation verified but retrieval failed"
    if delivery_state is not None:
        terminal["delivery"] = delivery_state
        execution = delivery_state.get("execution")
        verification = delivery_state.get("verification")
        retrieval = delivery_state.get("retrieval")
        if isinstance(execution, Mapping):
            terminal["execution_state"] = execution.get("status")
        if isinstance(verification, Mapping):
            terminal["verification_state"] = verification.get("status")
        if isinstance(retrieval, Mapping):
            terminal["retrieval_state"] = retrieval.get("status")
    return _runtime_evidence(
        record, adapter_kind=adapter_kind, backend=backend, endpoint=endpoint,
        schema_provenance=schema_provenance,
        queue_acceptance={"status": status, "prompt_id": prompt_id},
        terminal=terminal,
        dependency_report=dependency_report,
    )


def _exception_diagnostics(exc: BaseException | None) -> list[dict[str, Any]]:
    """Collect bounded structured diagnostics from an exception chain."""
    diagnostics: list[dict[str, Any]] = []
    seen: set[int] = set()
    cursor = exc
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        raw = getattr(cursor, "diagnostics", None)
        if isinstance(raw, (list, tuple)):
            for item in raw:
                if isinstance(item, Mapping):
                    diagnostics.append(dict(item))
        cursor = cursor.__cause__ or cursor.__context__
    return diagnostics[:64]


def _exception_output_verification(exc: BaseException | None) -> dict[str, Any] | None:
    """Return the final-output witness attached anywhere in an exception chain."""
    seen: set[int] = set()
    cursor = exc
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        raw = getattr(cursor, "output_verification", None)
        if isinstance(raw, Mapping):
            return dict(raw)
        cursor = cursor.__cause__ or cursor.__context__
    return None


def _exception_delivery_state(exc: BaseException | None) -> dict[str, Any] | None:
    """Return post-generation delivery evidence from an exception chain."""
    seen: set[int] = set()
    cursor = exc
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        raw = getattr(cursor, "delivery_state", None)
        if isinstance(raw, Mapping):
            return dict(raw)
        cursor = cursor.__cause__ or cursor.__context__
    return None


def _persist_runtime_failure(
    *,
    run_dir: Path,
    attempt_bundle: dict[str, Any],
    state: dict[str, Any],
    run_id: str,
    record: ApprovedProjectionRecord,
    generation: int,
    evidence: Mapping[str, Any] | None = None,
    event_type: str | None = None,
    original_error: BaseException | None = None,
    queue_acceptance: Mapping[str, Any] | None = None,
    phase: str | None = None,
    exc: BaseException | None = None,
    interrupted: bool | None = None,
) -> None:
    if _terminal_event_already_written(run_dir, record, generation):
        return
    exc_for_class = exc or original_error
    if interrupted is None:
        interrupted = isinstance(exc_for_class, (asyncio.CancelledError, KeyboardInterrupt))
    if event_type is None:
        event_type = "superseded" if interrupted else "discarded"
    normalized_acceptance = dict(
        queue_acceptance or {"status": "not_attempted", "prompt_id": None}
    )
    queue_started_phases = {"queue", "acceptance_witness", "history", "output", "metadata"}
    if (
        phase in queue_started_phases
        and normalized_acceptance.get("status") == "not_attempted"
    ):
        normalized_acceptance = {"status": "unknown", "prompt_id": None}
    if evidence is None:
        if exc_for_class is None or phase is None:
            raise TypeError("runtime failure needs evidence or exception context")
        durable = attempt_bundle.get("runtime_evidence", {})
        adapter = attempt_bundle.get("adapter") or durable.get("adapter", {})
        evidence = _runtime_failure_evidence(
            record, adapter_kind=str(adapter.get("kind") or "unknown"),
            backend=str(adapter.get("backend") or "api"), endpoint=adapter.get("endpoint"),
            schema_provenance=attempt_bundle.get("schema_provenance") or durable.get("schema_provenance"),
            queue_acceptance=normalized_acceptance,
            phase=phase, exc=exc_for_class,
            queue_started=phase in queue_started_phases,
            interrupted=interrupted,
            dependency_report=attempt_bundle.get("dependency_report"),
        )
    terminal_evidence = evidence.get("terminal")
    if isinstance(terminal_evidence, Mapping):
        completion_status = terminal_evidence.get("completion_status")
        if completion_status:
            attempt_bundle["status"] = str(completion_status)
            attempt_bundle["completion_status"] = str(completion_status)
    attempt_bundle["prompt_id"] = normalized_acceptance.get("prompt_id")
    attempt_bundle["receipt_path"] = str(run_dir / "attempt.json")
    output_verification = _exception_output_verification(exc_for_class)
    if output_verification is not None:
        attempt_bundle["output_verification"] = output_verification
    delivery_state = _exception_delivery_state(exc_for_class)
    if delivery_state is not None:
        attempt_bundle["delivery_state"] = delivery_state
        artifacts = delivery_state.get("artifacts")
        if isinstance(artifacts, list):
            attempt_bundle["artifacts"] = [
                dict(item) for item in artifacts if isinstance(item, Mapping)
            ]
        remote_artifacts = delivery_state.get("remote_artifacts")
        if isinstance(remote_artifacts, list):
            attempt_bundle["remote_artifact_locations"] = list(remote_artifacts)
        local_artifacts = delivery_state.get("local_artifacts")
        if isinstance(local_artifacts, list):
            attempt_bundle["local_artifact_paths"] = list(local_artifacts)
    attempt_error: Exception | None = None
    try:
        _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
    except Exception as exc:
        # The append-only lifecycle log is the authoritative recovery source;
        # still attempt it when the derived attempt witness cannot be updated.
        attempt_error = exc
    journal_error: Exception | None = None
    try:
        _journal_terminal(
            state, run_dir, run_id, record, generation, evidence, event_type=event_type,
            reason=str(evidence["terminal"].get("reason") or "runtime_failure"),
        )
    except Exception as exc:
        journal_error = exc
    if attempt_error is not None:
        raise QueueError("runtime attempt evidence could not be persisted",
                         next_action="vibecomfy runtime doctor") from (original_error or attempt_error)
    if journal_error is not None:
        raise QueueError("runtime lifecycle evidence could not be persisted",
                         next_action="vibecomfy runtime doctor") from (original_error or journal_error)
    terminal = evidence.get("terminal")
    if exc_for_class is not None and isinstance(terminal, Mapping):
        completion_status = terminal.get("completion_status")
        if completion_status:
            setattr(exc_for_class, "completion_status", str(completion_status))
        setattr(exc_for_class, "receipt_path", str(run_dir / "attempt.json"))
        setattr(exc_for_class, "prompt_id", normalized_acceptance.get("prompt_id"))


def _persist_dependency_failure(
    *,
    run_dir: Path,
    run_id: str,
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    adapter_kind: str,
    backend: str,
    endpoint: str | None,
    dependency_report: Mapping[str, Any] | None,
    exc: BaseException,
) -> None:
    """Create the same durable pre-queue receipt for a dependency refusal."""
    report = dict(dependency_report or {})
    report.setdefault("mode", "reuse")
    report.setdefault("changes", [])
    attempt_bundle, state, generation, _initial = _begin_runtime_lifecycle(
        run_dir=run_dir,
        run_id=run_id,
        record=record,
        bundle=bundle,
        adapter_kind=adapter_kind,
        backend=backend,
        endpoint=endpoint,
        dependency_report=report,
    )
    _persist_runtime_failure(
        run_dir=run_dir,
        attempt_bundle=attempt_bundle,
        state=state,
        run_id=run_id,
        record=record,
        generation=generation,
        original_error=exc,
        queue_acceptance={"status": "not_attempted", "prompt_id": None},
        phase="dependencies",
        exc=exc,
    )


def _commit_queue_witness(
    *,
    run_dir: Path,
    attempt_bundle: dict[str, Any],
    journal_state: dict[str, Any],
    run_id: str,
    record: ApprovedProjectionRecord,
    journal_generation: int,
    adapter_kind: str,
    backend: str,
    endpoint: str | None,
    schema_provenance: Mapping[str, Any],
    queued: Any,
) -> str:
    prompt_id = normalize_prompt_id(queued)
    if prompt_id is not None and not prompt_id.strip():
        prompt_id = None
    usable = bool(prompt_id and prompt_id.strip())
    acceptance = {"status": "accepted" if usable else "unknown", "prompt_id": prompt_id}
    witness_error = QueueError(
        "Comfy queue response did not include a prompt_id; acceptance is ambiguous and must not be retried automatically",
        next_action="vibecomfy runtime doctor",
    )
    evidence = _runtime_evidence(
        record, adapter_kind=adapter_kind, backend=backend, endpoint=endpoint,
        schema_provenance=schema_provenance, queue_acceptance=acceptance,
        terminal={"phase": "accepted" if usable else "ambiguous",
                  "reason_type": "none" if usable else "missing_prompt_id",
                  "reason": None if usable else str(witness_error), "acceptance_known": usable},
    )
    try:
        _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
    except Exception as exc:
        _persist_runtime_failure(
            run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
            run_id=run_id, record=record, generation=journal_generation,
            original_error=exc, queue_acceptance={"status": "unknown", "prompt_id": prompt_id},
            phase="acceptance_witness", exc=exc,
        )
        raise QueueError("Comfy prompt acceptance could not be recorded durably; the run may be in flight and must not be retried automatically",
                         next_action="vibecomfy runtime doctor") from exc
    if not usable:
        _persist_runtime_failure(
            run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
            run_id=run_id, record=record, generation=journal_generation,
            original_error=witness_error, queue_acceptance=acceptance,
            phase="acceptance_witness", exc=witness_error,
        )
        raise witness_error
    return prompt_id  # type: ignore[return-value]


def _complete_runtime_run(
    *,
    run_dir: Path,
    attempt_bundle: dict[str, Any],
    journal_state: dict[str, Any],
    run_id: str,
    record: ApprovedProjectionRecord,
    journal_generation: int,
    adapter_kind: str,
    backend: str,
    endpoint: str | None,
    schema_provenance: Mapping[str, Any],
    queue_acceptance: Mapping[str, Any],
    metadata: dict[str, Any],
    dependency_report: Mapping[str, Any] | None = None,
    adapter_details: Mapping[str, Any] | None = None,
) -> Path:
    output_verification = metadata.get("output_verification")
    if isinstance(output_verification, Mapping):
        attempt_bundle["output_verification"] = dict(output_verification)
    evidence = _runtime_evidence(
        record, adapter_kind=adapter_kind, backend=backend, endpoint=endpoint,
        schema_provenance=schema_provenance, queue_acceptance=queue_acceptance,
        terminal={"phase": "completed", "reason_type": "none", "reason": None,
                  "acceptance_known": True,
                  "completion_status": str(metadata.get("status", "completed"))},
        dependency_report=dependency_report,
        adapter_details=adapter_details,
    )
    completion_path = run_dir / "completion.json"
    metadata_path = run_dir / "metadata.json"
    attempt_bundle.update({
        "status": metadata.get("status", "completed"),
        "completion_status": metadata.get("status", "completed"),
        "prompt_id": metadata.get("prompt_id"),
        "metadata_path": str(metadata_path),
        "completion_path": str(completion_path),
        "outputs": list(metadata.get("outputs", [])) if isinstance(metadata.get("outputs"), list) else [],
        "artifacts": list(metadata.get("artifacts", [])) if isinstance(metadata.get("artifacts"), list) else [],
        "artifact_paths": list(metadata.get("artifact_paths", [])) if isinstance(metadata.get("artifact_paths"), list) else [],
        "log_path": metadata.get("log_path"),
        "log_provenance": dict(metadata.get("log_provenance", {})) if isinstance(metadata.get("log_provenance"), Mapping) else {},
    })
    if isinstance(metadata.get("adapter"), Mapping):
        attempt_bundle["adapter"] = dict(metadata["adapter"])
    try:
        _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
    except Exception as exc:
        raise QueueError(
            "runtime completed attempt evidence could not be persisted",
            next_action="vibecomfy runtime doctor",
        ) from exc
    metadata.update(
        runtime_evidence=dict(evidence),
        queue_acceptance=dict(evidence["queue_acceptance"]),
        terminal=dict(evidence["terminal"]),
        adapter=dict(evidence["adapter"]),
        schema_provenance=dict(evidence["schema_provenance"]),
    )
    metadata["completion_path"] = str(completion_path)
    result_payload, result_unavailable = _build_managed_generation_result(
        run_dir=run_dir,
        metadata=metadata,
        attempt_bundle=attempt_bundle,
        evidence=evidence,
    )
    result_path: Path | None = None
    if result_payload is not None:
        try:
            result_path = atomic_write_json(
                run_dir / "managed-generation-result.json", result_payload
            )
        except Exception as exc:
            raise QueueError(
                "managed generation result could not be persisted",
                next_action="vibecomfy runtime doctor",
            ) from exc
    result_state = (
        {"status": "available", "path": str(result_path)}
        if result_path is not None
        else {"status": "unavailable", **result_unavailable}
    )
    metadata["managed_generation_result"] = result_state
    attempt_bundle["managed_generation_result"] = result_state
    try:
        write_attempt_json(run_dir, attempt_bundle)
        metadata_path = atomic_write_json(run_dir / "metadata.json", metadata)
    except Exception as exc:
        raise QueueError("runtime completion evidence could not be persisted",
                         next_action="vibecomfy runtime doctor") from exc
    try:
        atomic_write_json(completion_path, _completion_record(run_dir, metadata))
    except Exception as exc:
        raise QueueError("runtime completion record could not be persisted",
                         next_action="vibecomfy runtime doctor") from exc
    try:
        _journal_terminal(
            journal_state, run_dir, run_id, record, journal_generation, evidence,
            event_type="finalized",
        )
    except Exception as exc:
        # Do not leave a completed-looking manifest behind when finalization
        # itself failed to become durable.
        try:
            completion_path.unlink()
        except OSError:
            logger.warning("could not remove incomplete completion record %s", completion_path)
        raise QueueError("runtime finalized evidence could not be persisted",
                         next_action="vibecomfy runtime doctor") from exc
    return metadata_path


def _completion_record(run_dir: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Build the concise, user-facing record for a completed run."""
    artifacts = metadata.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []
    outputs = metadata.get("outputs", [])
    if not isinstance(outputs, list):
        outputs = []
    locations: list[Any] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        location = artifact.get("location") or artifact.get("path") or artifact.get("reported_path")
        if location is not None:
            locations.append(location)
    log_provenance = metadata.get("log_provenance", {})
    if not isinstance(log_provenance, Mapping):
        log_provenance = {}
    return {
        "schema_version": 1,
        "record_type": "vibecomfy_completion",
        "run_id": metadata.get("run_id"),
        "prompt_id": metadata.get("prompt_id"),
        "status": metadata.get("status", "completed"),
        "runtime": metadata.get("runtime"),
        "metadata_path": str(run_dir / "metadata.json"),
        "outputs": outputs,
        "artifacts": artifacts,
        "artifact_locations": locations,
        "log_path": metadata.get("log_path"),
        "log_provenance": dict(log_provenance),
        **({"output_verification": dict(metadata["output_verification"])}
           if isinstance(metadata.get("output_verification"), Mapping) else {}),
        **({"runtime_dependency": dict(metadata["runtime_dependency"])}
           if isinstance(metadata.get("runtime_dependency"), Mapping) else {}),
    }


_RESULT_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_RESULT_MIME_RE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+\-]*/[a-z0-9][a-z0-9!#$&^_.+\-]*$")


def _build_managed_generation_result(
    *,
    run_dir: Path,
    metadata: Mapping[str, Any],
    attempt_bundle: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Build the engine-neutral result only from custody-backed artifacts."""
    raw_declared = metadata.get("declared_outputs")
    declared = [dict(item) for item in raw_declared if isinstance(item, Mapping)] if isinstance(raw_declared, list) else []
    raw_artifacts = metadata.get("artifacts")
    artifacts = [dict(item) for item in raw_artifacts if isinstance(item, Mapping)] if isinstance(raw_artifacts, list) else []
    if not declared:
        return None, {"reason": "no declared VibeOutput metadata"}
    if not artifacts:
        return None, {"reason": "no attributed artifacts"}

    attribution_by_path: dict[str, str] = {}
    manifest = metadata.get("artifact_manifest")
    if isinstance(manifest, Mapping) and isinstance(manifest.get("attribution"), list):
        for item in manifest["attribution"]:
            if isinstance(item, Mapping) and isinstance(item.get("path"), str) and isinstance(item.get("output"), str):
                attribution_by_path[item["path"]] = item["output"]

    def declaration_for(artifact: Mapping[str, Any]) -> dict[str, Any] | None:
        reported = str(artifact.get("reported_path") or "")
        output_name = attribution_by_path.get(reported)
        if output_name is not None:
            matches = [item for item in declared if item.get("name") == output_name]
            if len(matches) == 1:
                return matches[0]
            return None
        if len(declared) == 1 and len(artifacts) == 1:
            return declared[0]
        return None

    indexed: list[tuple[int, str, int, Mapping[str, Any], dict[str, Any]]] = []
    for index, artifact in enumerate(artifacts):
        declaration = declaration_for(artifact)
        if declaration is None:
            return None, {
                "reason": "artifact attribution did not resolve to one declared VibeOutput",
                "artifacts": [{"reported_path": item.get("reported_path")} for item in artifacts],
            }
        indexed.append((
            int(declaration.get("declaration_ordinal", 0)),
            str(artifact.get("reported_path") or ""),
            index,
            artifact,
            declaration,
        ))
    indexed.sort(key=lambda item: item[:3])

    output_rows: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    custody_root = run_dir.resolve(strict=False)
    for ordinal, (_declaration_ordinal, _reported, _index, artifact, declaration) in enumerate(indexed):
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            unavailable.append({
                "reported_path": artifact.get("reported_path"),
                "reason": "artifact has no local path",
            })
            continue
        try:
            source = Path(raw_path).expanduser().resolve(strict=True)
            if not source.is_file():
                raise OSError("artifact path is not a file")
            try:
                relative = source.relative_to(custody_root)
            except ValueError:
                descriptor = artifact.get("descriptor")
                if isinstance(descriptor, Mapping):
                    relative_descriptor = _normalized_descriptor_path(dict(descriptor))
                    destination = custody_root / "outputs" / Path(*relative_descriptor.parts)
                else:
                    destination = custody_root / "outputs" / f"{ordinal:04d}-{source.name}"
                destination = destination.resolve(strict=False)
                destination.relative_to(custody_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                relative = destination.relative_to(custody_root)
            staged = custody_root / relative
            size_before = staged.stat().st_size
            digest = hashlib.sha256()
            with staged.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if staged.stat().st_size != size_before:
                raise OSError("artifact changed while hashing")
        except (OSError, ValueError, UnicodeError, RuntimeNodeError) as exc:
            unavailable.append({
                "reported_path": artifact.get("reported_path"),
                "reason": str(exc) or type(exc).__name__,
            })
            continue
        media_type = str(declaration.get("mime_type") or "").strip().lower()
        output_port = str(declaration.get("name") or declaration.get("output_type") or "")
        if not media_type:
            media_type = (mimetypes.guess_type(staged.name)[0] or "").lower()
        if (
            not _RESULT_IDENTIFIER_RE.fullmatch(output_port)
            or _RESULT_MIME_RE.fullmatch(media_type) is None
        ):
            unavailable.append({
                "reported_path": artifact.get("reported_path"),
                "reason": "declared output lacks a valid output port or MIME type",
            })
            continue
        producer_output_id = f"vibecomfy:{output_port}:{ordinal}"
        output_rows.append({
            "producer_output_id": producer_output_id,
            "output_port": output_port,
            "ordinal": ordinal,
            "path": relative.as_posix(),
            "media_type": media_type,
            "bytes": size_before,
            "sha256": digest.hexdigest(),
        })

    if unavailable or len(output_rows) != len(indexed):
        return None, {
            "reason": "one or more artifacts are unavailable for neutral result emission",
            "artifacts": unavailable,
        }

    raw_inputs = metadata.get("inputs")
    inputs = dict(raw_inputs) if isinstance(raw_inputs, Mapping) else {}
    media_validation = metadata.get("media_validation")
    verification_status = (
        "succeeded"
        if not isinstance(media_validation, Mapping)
        or media_validation.get("status") in {"verified", "not_required"}
        else "failed"
    )
    producer_metadata = {
        key: value
        for key, value in metadata.items()
        if key not in {"managed_generation_result"}
    }
    producer = {
        "runtime": dict(evidence),
        "prompt_history": {
            "prompt_id": metadata.get("prompt_id"),
            "queued": metadata.get("queued"),
            "history": metadata.get("comfy_outputs"),
        },
        "attempt": {
            "path": str(run_dir / "attempt.json"),
            "record": dict(attempt_bundle),
        },
        "metadata": {
            "path": str(run_dir / "metadata.json"),
            "record": producer_metadata,
        },
        "artifacts": [dict(item) for item in artifacts],
        "dependency": metadata.get("runtime_dependency"),
        "log": dict(metadata.get("log_provenance") or {}),
        "media_verification": metadata.get("media_validation"),
    }
    return {
        "schema_version": 1,
        "kind": "managed-generation-result.v1",
        "inputs": inputs,
        "outputs": output_rows,
        "created": str(metadata.get("created") or datetime.datetime.now(datetime.timezone.utc).isoformat()),
        "warnings": [],
        "task_id": str(metadata.get("task_id") or metadata.get("workflow_id") or "vibecomfy-task"),
        "attempt_id": str(metadata.get("attempt_id") or metadata.get("run_id")),
        "producer_run_id": str(metadata.get("run_id")),
        "outcomes": {
            "execution": {"status": "succeeded"},
            "retrieval": {"status": "succeeded"},
            "verification": {"status": verification_status},
            "publication": {"status": "not_started"},
        },
        "evidence": {"producer": producer, "transport": {}},
    }, {}


def _managed_generation_identity(
    workflow: VibeWorkflow,
    run_id: str,
    config: SessionConfig | None,
    run_context: RunContext | None,
) -> dict[str, str]:
    sources: list[Mapping[str, Any]] = []
    if run_context is not None:
        sources.append({
            "task_id": run_context.task_id,
            "attempt_id": run_context.attempt_id,
            "execution_id": run_context.execution_id,
        })
    if config is not None:
        sources.append(config.extra)
    if isinstance(workflow.metadata, Mapping):
        sources.append(workflow.metadata)

    def first(*names: str) -> str | None:
        for source in sources:
            for name in names:
                value = source.get(name)
                if value is not None and str(value).strip():
                    return str(value).strip()
        return None

    def identifier(value: str | None, fallback: str) -> str:
        raw = value or fallback
        normalized = re.sub(r"[^A-Za-z0-9._:-]+", "-", raw).strip("-")
        return normalized or fallback

    execution_id = first("execution_id", "execution_identity")
    return {
        "task_id": identifier(first("task_id"), identifier(workflow.id, "vibecomfy-task")),
        "attempt_id": identifier(first("attempt_id", "execution_id", "execution_identity"), run_id),
        **({"execution_id": execution_id} if execution_id is not None else {}),
    }


def _begin_runtime_lifecycle(
    *,
    run_dir: Path,
    run_id: str,
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    adapter_kind: str,
    backend: str,
    endpoint: str | None,
    dependency_report: Mapping[str, Any] | None = None,
    adapter_details: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], int, dict[str, Any]]:
    evidence = _runtime_evidence(
        record,
        adapter_kind=adapter_kind,
        backend=backend,
        endpoint=endpoint,
        schema_provenance=_schema_provider_provenance(None),
        dependency_report=dependency_report,
        adapter_details=adapter_details,
    )
    attempt_bundle = _initial_attempt_bundle(record, evidence)
    try:
        write_attempt_json(run_dir, attempt_bundle)
        state, generation = _journal_prepare(run_dir, run_id, record, bundle, evidence)
    except Exception as exc:
        raise QueueError(
            "runtime approval lifecycle could not be persisted before queueing; "
            "no transport was attempted",
            next_action="vibecomfy runtime doctor",
        ) from exc
    return attempt_bundle, state, generation, evidence


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


async def _ensure_embedded_prerequisites(
    session: Any,
    workflow: VibeWorkflow,
    *,
    ensure_packs: bool,
    ensure_models: bool,
) -> None:
    """Run optional node/model preflight after the prepared lifecycle witness.

    Runtime evidence must exist before these mutable/environment-dependent
    checks.  This helper keeps the legacy preflight behavior in one place
    without making it an approval or queue authority.
    """
    if ensure_packs:
        from vibecomfy.custom_node_refs import check_pack_pin_compatibility, effective_lock_entries
        from vibecomfy.node_packs import install_required_packs, missing_packs_for_workflow
        from vibecomfy.node_packs import read_lockfile

        configured_lockfile = getattr(getattr(session, "config", None), "extra", {}).get("lockfile")
        from vibecomfy.node_packs import resolve_lockfile_path

        lockfile_path = (
            Path("custom_nodes.lock")
            if configured_lockfile is None
            else resolve_lockfile_path(configured_lockfile)
        )
        lockfile_entries = effective_lock_entries(workflow, read_lockfile(lockfile_path))
        pin_issues = check_pack_pin_compatibility(workflow, lockfile_entries)
        pin_errors = [issue.message for issue in pin_issues if issue.severity == "error"]
        if pin_errors:
            raise RuntimeError("ensure_packs: " + "; ".join(pin_errors))
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
            from .dependencies import runtime_requirements_from_workflow
            runtime_decl = runtime_requirements_from_workflow(workflow)
            lock_entries = {
                (entry.name, entry.slug): entry for entry in lockfile_entries
            }
            batch = install_required_packs(
                packs,
                restore_entries=[
                    entry
                    for pack in packs
                    if (entry := next(
                        (
                            candidate
                            for (name, slug), candidate in lock_entries.items()
                            if name == pack.name or slug == pack.name
                        ),
                        None,
                    )) is not None
                ],
                runtime_requirements=(
                    tuple(f"{name}{constraint}" for name, constraint in runtime_decl.packages)
                    if runtime_decl is not None else ()
                ),
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
            await session.reload_for_nodepack_change(reason="ensure_packs")
    if ensure_models:
        policy = resolve_model_preflight_policy(mode="embedded", ensure_models=True)
        apply_model_preflight(workflow, policy)


def _model_assets_from_workflow(
    workflow: VibeWorkflow, *, models_root: str | Path | None = None
) -> list[dict[str, str]]:
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
    local_root = Path(models_root).expanduser().resolve(strict=False) if models_root is not None else None
    from vibecomfy import fetch as fetch_assets
    unresolved_authored = [
        asset
        for asset in raw_assets
        if isinstance(asset, Mapping)
        and asset.get("url") is None
        and isinstance(asset.get("name", asset.get("filename")), str)
        and (
            local_root is None
            or not fetch_assets.is_present(asset, root=local_root)
        )
    ] if isinstance(raw_assets, list) else []
    if unresolved_authored:
        names = ", ".join(
            str(asset.get("name", asset.get("filename")))
            for asset in unresolved_authored[:8]
        )
        more = "" if len(unresolved_authored) <= 8 else f" (+{len(unresolved_authored) - 8} more)"
        raise ModelAssetError(
            f"unresolved authored model assets: {names}{more}",
            next_action=MODEL_DOCTOR_NEXT_ACTION,
        )
    authored = _normalise_requirement_entries(raw_assets) if isinstance(raw_assets, list) else []
    resolved, unresolved = resolve_referenced_assets(workflow)
    authored_keys = {
        (_norm(str(entry.get("name", ""))), _norm(str(entry.get("subdir", ""))))
        for entry in authored
        if isinstance(entry.get("name"), str) and isinstance(entry.get("subdir"), str)
    }
    authored_identity_keys = {
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
        if key not in authored_identity_keys and f"{_norm(entry['subdir'])}/{_norm(entry['name'])}" in authored_paths:
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
    log_path: str | None
    completion_path: str | None = None
    status: str = "completed"
    media_validated: bool = False
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    log_provenance: dict[str, Any] = field(default_factory=dict)
    managed_generation_result_path: str | None = None
    managed_generation_result: dict[str, Any] | None = None



class PreparedPrompt(dict):
    def __init__(
        self,
        api_dict: dict[str, Any],
        *,
        schema_validation_skipped: list[str] | None = None,
        normalization: Any | None = None,
        schema_provenance: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(api_dict)
        self.schema_validation_skipped = schema_validation_skipped or []
        self.schema_provenance = dict(schema_provenance or {})
        #: Applied-and-approved normalization proposal (evidence); None when no
        #: normalization was needed or approved.
        self.normalization = normalization


def _configuration_error(detail: str, exc: Exception | None = None) -> RuntimeConfigurationError:
    error = RuntimeConfigurationError(
        f"Invalid runtime session configuration: {detail}",
        next_action="Fix the runtime configuration and retry.",
    )
    if exc is not None:
        error.__cause__ = exc
    return error


def _duration_seconds(
    raw: Any,
    *,
    name: str,
    default: float,
    allow_zero: bool = False,
) -> float:
    """Parse a configured finite duration, optionally allowing an immediate poll."""
    if raw is None or (type(raw) is str and raw == ""):
        return default
    if isinstance(raw, bool):
        expected = "non-negative" if allow_zero else "positive"
        raise _configuration_error(
            f"{name} must be a {expected} finite number; got a boolean"
        )
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        expected = "non-negative" if allow_zero else "positive"
        raise _configuration_error(
            f"{name} must be a {expected} finite number; got {_safe_value_label(raw)}",
            exc,
        ) from exc
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        expected = "non-negative" if allow_zero else "positive"
        raise _configuration_error(
            f"{name} must be a {expected} finite number; got {_safe_value_label(raw)}"
        )
    return value


def _resolve_runtime_path(value: str | Path | None, *, base: Path, field_name: str) -> Path:
    if value is None:
        return base
    if not isinstance(value, (str, Path)):
        raise _configuration_error(f"{field_name} must be a filesystem path")
    raw = str(value).strip()
    if not raw:
        raise _configuration_error(f"{field_name} must not be empty")
    path = Path(raw).expanduser()
    # Preserve the operator's spelling for absolute paths (notably /tmp on
    # macOS, where it is a symlink to /private/tmp).  Relative paths are
    # anchored to the captured authority and then normalized.
    return path if path.is_absolute() else (base / path).resolve()


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
    # These are captured when the config is constructed.  Runtime paths must
    # not silently follow a later process-wide chdir().  ``cwd`` is the
    # subprocess working directory; ``runtime_root`` is the artifact/config
    # authority.  They intentionally remain separate so callers can run a
    # Comfy child from a different directory without moving VibeComfy output.
    runtime_root: Path | str | None = None
    cwd: Path | str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            if self.memory_profile is not None:
                self.memory_profile = MemoryProfile.parse(self.memory_profile)
            if self.vram_policy not in {"auto", "high", "low", "normal"}:
                raise ValueError("vram_policy must be auto, high, low, or normal")
            if self.cache_policy not in {"smart", "classic", "none"} and not (
                isinstance(self.cache_policy, str)
                and self.cache_policy.startswith("lru:")
                and self.cache_policy[4:].isdigit()
                and int(self.cache_policy[4:]) >= 0
            ):
                raise ValueError("cache_policy must be smart, classic, none, or lru:N")
            if self.warm_policy not in {"auto", "always", "never"}:
                raise ValueError("warm_policy must be auto, always, or never")
            if not isinstance(self.strict_drift, bool):
                raise TypeError("strict_drift must be a boolean")
            for field_name, value in (
                ("disable_smart_memory", self.disable_smart_memory),
            ):
                if not isinstance(value, bool):
                    raise TypeError(f"{field_name} must be a boolean")
            if self.port is not None and (
                isinstance(self.port, bool) or not isinstance(self.port, int)
            ):
                raise TypeError("port must be an integer or null")
            for field_name, value in (
                ("reserve_vram_gb", self.reserve_vram_gb),
                ("auto_flush_vram_threshold_gb", self.auto_flush_vram_threshold_gb),
            ):
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, (int, float))
                ):
                    raise TypeError(f"{field_name} must be a number or null")
            if not isinstance(self.extra, dict):
                raise TypeError("extra must be an object")

            construction_cwd = Path.cwd().resolve()
            root = _resolve_runtime_path(
                self.runtime_root, base=construction_cwd, field_name="runtime_root"
            )
            process_cwd = _resolve_runtime_path(
                self.cwd,
                base=root,
                field_name="cwd",
            ) if self.cwd is not None else root
            self.runtime_root = root
            self.cwd = process_cwd
            # The caller may retain and mutate its input mapping.  A shallow
            # copy is enough here; process-start snapshots copy the values
            # that can affect I/O separately.
            self.extra = dict(self.extra)
        except RuntimeConfigurationError:
            raise
        except (TypeError, ValueError, OSError, RuntimeError) as exc:
            raise _configuration_error(str(exc), exc) from exc

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "SessionConfig":
        if not isinstance(values, dict):
            raise _configuration_error("configuration must be a JSON object")
        try:
            kwargs, extra = _partition_comfy_config(values)
        except RuntimeConfigurationError:
            raise
        except (TypeError, ValueError, OSError, RuntimeError) as exc:
            raise _configuration_error(str(exc), exc) from exc
        return cls(**kwargs, extra=extra)

    @classmethod
    def from_workflow_metadata(cls, workflow: VibeWorkflow) -> "SessionConfig":
        values = workflow.metadata.get("comfy_configuration", {})
        if not isinstance(values, dict):
            raise _configuration_error("comfy_configuration must be a JSON object")
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
        record: ApprovedProjectionRecord,
        bundle: WorkflowBundle,
        *,
        backend: str = "api",
        strict_drift: bool | None = None,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        dependency_mode: str = "reuse",
        dependency_report: Mapping[str, Any] | None = None,
        run_context: RunContext | None = None,
    ) -> RunResult:
        ...

    async def flush(self) -> None:
        ...

    async def reconfigure(self, config: SessionConfig) -> Any:
        ...

    async def stop(self, wait_for_inflight: bool = True) -> None:
        ...


@dataclass(frozen=True, slots=True)
class _RuntimeConfigurationSnapshot:
    """The dynamic configuration observed at one backend process boundary."""

    values: dict[str, Any]
    cwd: Path
    use_sage_attention: bool


_DYNAMIC_PATH_KEYS = {
    "input_directory",
    "output_directory",
    "temp_directory",
    "server_log_path",
}


def _read_environment_configuration() -> dict[str, Any]:
    raw = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _configuration_error("VIBECOMFY_COMFY_CONFIGURATION is not valid JSON", exc) from exc
    if not isinstance(parsed, dict):
        raise _configuration_error("VIBECOMFY_COMFY_CONFIGURATION must be a JSON object")
    return parsed


def _snapshot_runtime_configuration(config: SessionConfig) -> _RuntimeConfigurationSnapshot:
    """Freeze env/config I/O inputs before an embedded or managed process starts."""
    values = dict(config.extra)
    values.update(_read_environment_configuration())
    for key in _DYNAMIC_PATH_KEYS:
        if key in values and values[key] is not None:
            values[key] = str(
                _resolve_runtime_path(values[key], base=config.cwd, field_name=key)
            )
    if "extra_model_paths_config" in values:
        paths = values["extra_model_paths_config"]
        if not isinstance(paths, list):
            raise _configuration_error("extra_model_paths_config must be a list")
        values["extra_model_paths_config"] = [
            str(_resolve_runtime_path(path, base=config.cwd, field_name="extra_model_paths_config"))
            for path in paths
        ]

    profile = (
        os.environ.get("VIBECOMFY_ATTENTION_PROFILE")
        or os.environ.get("REIGH_VIBECOMFY_ATTENTION_PROFILE")
        or ""
    )
    use_sage_attention = bool(values.get("use_sage_attention")) or profile.strip().lower() in {
        "sage",
        "sageattn",
        "sageattention",
        "optimized",
    }
    return _RuntimeConfigurationSnapshot(
        values=values,
        cwd=config.cwd,
        use_sage_attention=use_sage_attention,
    )


def _allocate_request_root(
    prefix: str, *, config: SessionConfig | None = None
) -> tuple[str, Path]:
    runtime_root = config.runtime_root if config is not None else Path.cwd().resolve()
    runs_root = Path(runtime_root) / "out/runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=runs_root))
    return run_dir.name, run_dir


class EmbeddedSession:
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self._process_configuration: _RuntimeConfigurationSnapshot | None = None
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
        _assert_embedded_managed_interpreter(self.config)
        process_configuration = _snapshot_runtime_configuration(self.config)
        from comfy.client.embedded_comfy_client import Comfy

        self._context = Comfy(
            configuration=_embedded_configuration_for_session(
                self.config, runtime_configuration=process_configuration
            )
        )
        self._comfy = await self._context.__aenter__()
        self._process_configuration = process_configuration

    async def run(
        self,
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
        run_context: RunContext | None = None,
    ) -> RunResult:
        workflow = _require_runtime_boundary(record, bundle)
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
        task = asyncio.current_task()
        self._inflight_run = task
        try:
            resolved_strict = strict_drift if strict_drift is not None else self.config.strict_drift
            kwargs: dict[str, Any] = {}
            if ensure_packs:
                kwargs["ensure_packs"] = True
            if run_context is not None:
                kwargs["run_context"] = run_context
            if ensure_models:
                kwargs["ensure_models"] = True
            if dependency_mode != "reuse":
                kwargs["dependency_mode"] = dependency_mode
            if dependency_report is not None:
                kwargs["dependency_report"] = dependency_report
            return await self._run_untracked(
                record,
                bundle,
                backend=backend,
                strict_drift=resolved_strict,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                **kwargs,
            )
        finally:
            if self._inflight_run is task:
                self._inflight_run = None

    async def _run_untracked(
        self,
        record: ApprovedProjectionRecord,
        bundle: WorkflowBundle,
        *,
        backend: str = "api",
        strict_drift: bool = False,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        ensure_packs: bool = False,
        ensure_models: bool = False,
        dependency_mode: str = "reuse",
        dependency_report: Mapping[str, Any] | None = None,
        run_context: RunContext | None = None,
    ) -> RunResult:
        workflow = _require_runtime_boundary(record, bundle)
        run_id, run_dir = (
            (run_context.run_id, run_context.run_dir) if run_context is not None
            else _allocate_request_root("run", config=self.config)
        )
        _assert_embedded_managed_interpreter(self.config)
        if dependency_mode == "sync" and self._comfy is not None:
            exc = RuntimeDependencyError(
                "--deps sync refused while the embedded session is active; "
                "stop/restart the embedded session before synchronization"
            )
            _persist_dependency_failure(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind="embedded", backend=backend, endpoint=None,
                dependency_report={
                    "declared": True, "mode": "sync", "status": "refused",
                    "checks": [], "mismatches": [], "warnings": [], "changes": [],
                    "error": str(exc),
                }, exc=exc,
            )
            raise exc
        _bind_runtime_launch_flags(self.config, workflow)
        total_start = time.monotonic()
        timings: dict[str, float] = {}
        from .run import _dependency_check
        try:
            dependency_report = _dependency_check(
                workflow,
                config=self.config,
                dependency_mode=dependency_mode,
                server_url=None,
                target=_session_dependency_target(
                    self, package_names=_runtime_package_names(workflow)
                ),
                dependency_report=dependency_report,
            )
        except RuntimeDependencyError as exc:
            _persist_dependency_failure(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind="embedded", backend=backend, endpoint=None,
                dependency_report=getattr(exc, "dependency_report", None), exc=exc,
            )
            raise
        phase_start = time.monotonic()
        await self.start()
        timings["session_start_sec"] = round(time.monotonic() - phase_start, 3)
        assert self._comfy is not None
        try:
            dependency_report = _dependency_check(
                workflow,
                config=self.config,
                dependency_mode="reuse",
                server_url=None,
                target=_session_dependency_target(
                    self, package_names=_runtime_package_names(workflow)
                ),
                dependency_report=dependency_report,
            )
        except RuntimeDependencyError as exc:
            _persist_dependency_failure(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind="embedded", backend=backend, endpoint=None,
                dependency_report=getattr(exc, "dependency_report", None), exc=exc,
            )
            raise
        log_path = run_dir / "embedded.log"
        ws_url = _embedded_observation_url(self.config)
        attempt_bundle, journal_state, journal_generation, _initial = _begin_runtime_lifecycle(
            run_dir=run_dir,
            run_id=run_id,
            record=record,
            bundle=bundle,
            adapter_kind="embedded",
            backend=backend,
            endpoint=ws_url,
            dependency_report=dependency_report,
        )
        schema_provenance = _schema_provider_provenance(None)
        queue_acceptance = {"status": "not_attempted", "prompt_id": None}
        phase = "preflight"
        watchdog = None
        stop_reason: str | None = None
        try:
            await _ensure_embedded_prerequisites(
                self,
                workflow,
                ensure_packs=ensure_packs,
                ensure_models=ensure_models,
            )
            phase = "schema"
            if self._schema_provider is None:
                self._schema_provider = _build_schema_provider(None)
            if self._schema_provider is not None and (
                callable(getattr(self._schema_provider, "object_info_async", None))
                or callable(getattr(self._schema_provider, "object_info", None))
            ):
                self._schema_provider = await _warm_schema_provider(
                    self._schema_provider,
                    on_unavailable=self._on_schema_unavailable,
                )
            execution_snapshot: dict[str, Any] | None = None
            reconciliation_schema: Mapping[str, Any] | None = None
            if self._schema_provider is not None and (
                callable(getattr(self._schema_provider, "object_info", None))
                or callable(getattr(self._schema_provider, "refresh", None))
            ):
                from .reconciliation import (
                    ReconciliationError,
                    build_execution_snapshot,
                    reconcile_before_queue_async,
                )

                try:
                    reconciliation = await reconcile_before_queue_async(
                        bundle,
                        target_schema_provider=self._schema_provider,
                        publish=True,
                    )
                except ReconciliationError as exc:
                    _persist_runtime_failure(
                        run_dir=run_dir,
                        attempt_bundle=attempt_bundle,
                        state=journal_state,
                        run_id=run_id,
                        record=record,
                        generation=journal_generation,
                        original_error=exc,
                        queue_acceptance=queue_acceptance,
                        phase="mapping",
                        exc=exc,
                    )
                    raise
                reconciliation_schema = reconciliation.schema
                if reconciliation.bundle is not bundle:
                    bundle = reconciliation.bundle
                    workflow = bundle.workflow
                    record = bundle.compile(
                        run_inputs=dict(record.input_binding),
                        schema_provider=self._schema_provider,
                    )
                execution_snapshot = build_execution_snapshot(
                    bundle,
                    record,
                    schema=reconciliation_schema,
                ).to_dict()
                attempt_bundle["execution_snapshot"] = execution_snapshot
            phase_start = time.monotonic()
            api_dict = await _prepare_prompt_async(
                record,
                bundle,
                backend=backend,
                schema_provider=self._schema_provider,
                on_unavailable=self._on_schema_unavailable,
            )
            if execution_snapshot is not None:
                from .reconciliation import assert_execution_snapshot

                assert_execution_snapshot(
                    execution_snapshot,
                    bundle,
                    record,
                    schema_provider=self._schema_provider,
                )
            schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
            normalization = getattr(api_dict, "normalization", None)
            schema_provenance = dict(getattr(api_dict, "schema_provenance", {})) or _schema_provider_provenance(self._schema_provider)
            timings["prepare_prompt_sec"] = round(time.monotonic() - phase_start, 3)
            evidence = _runtime_evidence(
                record,
                adapter_kind="embedded",
                backend=backend,
                endpoint=ws_url,
                schema_provenance=schema_provenance,
                queue_acceptance=queue_acceptance,
                terminal={"phase": "prepared", "reason_type": "none", "reason": None, "acceptance_known": False},
                dependency_report=dependency_report,
            )
            attempt_bundle = build_attempt_bundle(
                bundle,
                record,
                backend=backend,
                config=self.config,
                adapter_kind="embedded",
                adapter_endpoint=ws_url,
                schema_provenance=schema_provenance,
                runtime_evidence=evidence,
                runtime_compatibility=dependency_report,
            )
            if execution_snapshot is not None:
                attempt_bundle["execution_snapshot"] = execution_snapshot
            _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
            fp = model_fingerprint(api_dict)
            phase_start = time.monotonic()
            await _maybe_flush_for_policy(self, fp)
            timings["memory_policy_sec"] = round(time.monotonic() - phase_start, 3)
            client_id = uuid.uuid4().hex
            watchdog = await _start_watchdog(server_url=ws_url, client_id=client_id, api_dict=api_dict)
            phase = "drift"
            if strict_drift:
                enforce_strict_drift(workflow, lockfile_path=self.config.extra.get("lockfile"))
            phase = "queue"
            phase_start = time.monotonic()
            try:
                queued_execution = await queue_embedded_prompt(self._comfy, record, bundle)
                queued = queued_execution.queued
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
                adapter_kind="embedded", backend=backend, endpoint=ws_url,
                schema_provenance=schema_provenance, queued=queued,
            )
            queue_acceptance = {"status": "accepted", "prompt_id": prompt_id}
            _set_watchdog_prompt_id(watchdog, prompt_id)
            timings["queue_prompt_sec"] = round(time.monotonic() - phase_start, 3)
            phase = "output"
            phase_start = time.monotonic()
            output_verification: dict[str, Any] | None = None
            if workflow.outputs and isinstance(queued, Mapping) and isinstance(queued.get("outputs"), Mapping):
                output_verification = _validate_declared_output_contract(
                    workflow,
                    {
                        prompt_id: {
                            "outputs": queued["outputs"],
                            "status": {"status_str": "success", "completed": True, "messages": []},
                        }
                    },
                    prompt_id,
                )
            comfy_outputs = _decode_terminal_result(
                queued,
                prompt_id=prompt_id,
                status_required=False,
                allow_list_outputs=True,
            )
            output_directory = _configured_output_directory(
                self.config, runtime_configuration=self._process_configuration
            )
            artifacts = _artifact_records(
                comfy_outputs,
                adapter_kind="embedded",
                adapter_endpoint=ws_url,
                output_directory=output_directory,
            )
            outputs = [artifact["reported_path"] for artifact in artifacts]
            media_validation = _verify_declared_media(
                workflow,
                artifacts,
                adapter_kind="embedded",
                output_verification=output_verification,
            )
            if output_verification is not None:
                output_verification = {**output_verification, "media": media_validation}
            timings["collect_outputs_sec"] = round(time.monotonic() - phase_start, 3)
            self.last_fingerprint = fp
            stop_reason = "completed"
            phase = "metadata"
            timings["total_inside_vibecomfy_sec"] = round(time.monotonic() - total_start, 3)
            metadata = _run_metadata(
                run_id=run_id,
                bundle=bundle,
                record=record,
                queued=queued,
                comfy_outputs=comfy_outputs,
                outputs=outputs,
                runtime="embedded",
                config=self.config,
                timings=timings,
                schema_validation_skipped=schema_validation_skipped,
                schema_provenance=schema_provenance,
                normalization=normalization,
                adapter_endpoint=ws_url,
                log_path=log_path,
                artifacts=artifacts,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                dependency_report=dependency_report,
                output_verification=output_verification,
                media_validation=media_validation,
                run_context=run_context,
            )
            metadata_path = _complete_runtime_run(
                run_dir=run_dir, attempt_bundle=attempt_bundle, journal_state=journal_state,
                run_id=run_id, record=record, journal_generation=journal_generation,
                adapter_kind="embedded", backend=backend, endpoint=ws_url,
                schema_provenance=schema_provenance, queue_acceptance=queue_acceptance,
                metadata=metadata,
                dependency_report=dependency_report,
            )
            return RunResult(
                run_id=run_id,
                prompt_id=prompt_id,
                outputs=outputs,
                metadata_path=str(metadata_path),
                log_path=log_path,
                completion_path=str(Path(metadata_path).with_name("completion.json")),
                status=str(metadata.get("status", "completed")),
                media_validated=bool(metadata.get("media_validated", False)),
                artifacts=list(metadata.get("artifacts", [])),
                log_provenance=dict(metadata.get("log_provenance", {})),
                managed_generation_result_path=(
                    str(metadata["managed_generation_result"]["path"])
                    if isinstance(metadata.get("managed_generation_result"), Mapping)
                    and metadata["managed_generation_result"].get("status") == "available"
                    else None
                ),
            )
        except asyncio.CancelledError as exc:
            stop_reason = "cancelled"
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        except KeyboardInterrupt as exc:
            stop_reason = "interrupted"
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        except Exception as exc:
            stop_reason = "errored"
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        finally:
            if watchdog is not None:
                await _finalize_watchdog(
                    watchdog, run_dir=run_dir, reason=stop_reason or "exception",
                )

    async def flush(self) -> None:
        if self._comfy is None:
            return
        await self._comfy.clear_cache()

    async def reconfigure(self, config: SessionConfig) -> Any:
        if self._comfy is None:
            self.config = config
            return None
        process_configuration = _snapshot_runtime_configuration(config)
        result = await self._comfy.reconfigure(
            _embedded_configuration_for_session(
                config, runtime_configuration=process_configuration
            )
        )
        self.config = config
        self._process_configuration = process_configuration
        return result

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
            self._process_configuration = None

    async def reload_for_nodepack_change(
        self, *, reason: str, server_url: str | None = None
    ) -> str:
        if server_url is not None:
            return _nodepack_reload_status(server_url)
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
        self._process_configuration = None
        await self.start()
        return "reloaded"


class ServerSession:
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.url: str | None = None
        self.log_handle: Any | None = None
        self._argv = _comfy_server_argv(self.config)
        self._process_configuration: _RuntimeConfigurationSnapshot | None = None
        self.process_start_identity: str | None = None
        self._schema_provider: Any | None = None
        self._schema_warning_emitted = False
        self._inflight_run: asyncio.Task[Any] | None = None

    def _on_schema_unavailable(self, msg: str) -> None:
        if self._schema_warning_emitted and "schema validation skipped for class types" not in msg:
            return
        level = logging.WARNING if _schema_warn_only(self.config) else logging.ERROR
        logger.log(level, "vibecomfy schema gate: %s", msg)
        self._schema_warning_emitted = True

    def _captured_process_log_path(self) -> str | None:
        """Return the persistent process log owned by this managed session."""
        snapshot = self._process_configuration
        configured = snapshot.values.get("server_log_path") if snapshot is not None else None
        if configured and self.log_handle is not None and Path(configured).is_file():
            return str(configured)
        return None

    async def start(self) -> None:
        if self.process is not None and self.process.returncode is None:
            return
        if self.process is not None:
            await self.stop()
        process_configuration = _snapshot_runtime_configuration(self.config)
        self._argv = _comfy_server_argv(
            self.config, runtime_configuration=process_configuration
        )
        self.process, self.url, self.log_handle = await _spawn_comfy_server(
            self.config,
            log_path=process_configuration.values.get("server_log_path"),
            runtime_configuration=process_configuration,
        )
        self._process_configuration = process_configuration
        if self.process is not None and self.process.pid:
            self.process_start_identity = _process_start_identity(self.process.pid)

    async def run(
        self,
        record: ApprovedProjectionRecord,
        bundle: WorkflowBundle,
        *,
        backend: str = "api",
        ensure_models: bool = False,
        shared_models_root: str | Path | None = None,
        strict_drift: bool | None = None,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        dependency_mode: str = "reuse",
        dependency_report: Mapping[str, Any] | None = None,
        run_context: RunContext | None = None,
    ) -> RunResult:
        workflow = _require_runtime_boundary(record, bundle)
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
        task = asyncio.current_task()
        self._inflight_run = task
        try:
            resolved_strict = strict_drift if strict_drift is not None else self.config.strict_drift
            kwargs: dict[str, Any] = {}
            if ensure_models:
                kwargs.update(ensure_models=True, shared_models_root=shared_models_root)
            if dependency_mode != "reuse":
                kwargs["dependency_mode"] = dependency_mode
            if dependency_report is not None:
                kwargs["dependency_report"] = dependency_report
            if run_context is not None:
                kwargs["run_context"] = run_context
            return await self._run_untracked(
                record, bundle, backend=backend, strict_drift=resolved_strict,
                chain_id=chain_id, parent_run_id=parent_run_id,
                **kwargs,
            )
        finally:
            if self._inflight_run is task:
                self._inflight_run = None

    async def _run_untracked(
        self,
        record: ApprovedProjectionRecord,
        bundle: WorkflowBundle,
        *,
        backend: str = "api",
        strict_drift: bool = False,
        chain_id: str | None = None,
        parent_run_id: str | None = None,
        ensure_models: bool = False,
        shared_models_root: str | Path | None = None,
        dependency_mode: str = "reuse",
        dependency_report: Mapping[str, Any] | None = None,
        run_context: RunContext | None = None,
    ) -> RunResult:
        workflow = _require_runtime_boundary(record, bundle)
        run_id, run_dir = (
            (run_context.run_id, run_context.run_dir)
            if run_context is not None
            else _allocate_request_root("run", config=self.config)
        )
        if dependency_mode == "sync" and self.process is not None and self.process.returncode is None:
            exc = RuntimeDependencyError(
                "--deps sync refused while the managed server is active; stop/restart the managed session first"
            )
            _persist_dependency_failure(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind="managed", backend=backend, endpoint=self.url,
                dependency_report={
                    "declared": True, "mode": "sync", "status": "refused",
                    "checks": [], "mismatches": [], "warnings": [], "changes": [],
                    "error": str(exc),
                }, exc=exc,
            )
            raise exc
        _bind_runtime_launch_flags(self.config, workflow)
        total_start = time.monotonic()
        timings: dict[str, float] = {}
        from .run import _dependency_check
        try:
            dependency_report = _dependency_check(
                workflow,
                config=self.config,
                dependency_mode=dependency_mode,
                server_url=None,
                target=_session_dependency_target(
                    self, package_names=_runtime_package_names(workflow)
                ),
                dependency_report=dependency_report,
            )
        except RuntimeDependencyError as exc:
            _persist_dependency_failure(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind="managed", backend=backend, endpoint=self.url,
                dependency_report=getattr(exc, "dependency_report", None), exc=exc,
            )
            raise
        phase_start = time.monotonic()
        await self.start()
        timings["session_start_sec"] = round(time.monotonic() - phase_start, 3)
        assert self.url is not None
        try:
            dependency_report = _dependency_check(
                workflow,
                config=self.config,
                dependency_mode="reuse",
                server_url=None,
                target=_session_dependency_target(
                    self, package_names=_runtime_package_names(workflow)
                ),
                dependency_report=dependency_report,
            )
        except RuntimeDependencyError as exc:
            _persist_dependency_failure(
                run_dir=run_dir, run_id=run_id, record=record, bundle=bundle,
                adapter_kind="managed", backend=backend, endpoint=self.url,
                dependency_report=getattr(exc, "dependency_report", None), exc=exc,
            )
            raise
        log_path = self._captured_process_log_path()
        attempt_bundle, journal_state, journal_generation, _initial = _begin_runtime_lifecycle(
            run_dir=run_dir,
            run_id=run_id,
            record=record,
            bundle=bundle,
            adapter_kind="managed",
            backend=backend,
            endpoint=self.url,
            dependency_report=dependency_report,
        )
        schema_provenance = _schema_provider_provenance(None)
        queue_acceptance = {"status": "not_attempted", "prompt_id": None}
        phase = "preflight"
        watchdog = None
        stop_reason: str | None = None
        try:
            if ensure_models:
                policy = resolve_model_preflight_policy(
                    mode="managed_local_server",
                    ensure_models=True,
                    shared_root=shared_models_root,
                )
                apply_model_preflight(workflow, policy)
            phase = "schema"
            if self._schema_provider is None:
                self._schema_provider = _build_schema_provider(self.url)
            execution_snapshot: dict[str, Any] | None = None
            if callable(getattr(self._schema_provider, "object_info", None)):
                from .reconciliation import (
                    ReconciliationError,
                    build_execution_snapshot,
                    reconcile_before_queue_async,
                )

                try:
                    reconciliation = await reconcile_before_queue_async(
                        bundle,
                        target_schema_provider=self._schema_provider,
                        target_schema_generation=getattr(self, "process_start_identity", None),
                        publish=True,
                    )
                except ReconciliationError as exc:
                    _persist_runtime_failure(
                        run_dir=run_dir,
                        attempt_bundle=attempt_bundle,
                        state=journal_state,
                        run_id=run_id,
                        record=record,
                        generation=journal_generation,
                        original_error=exc,
                        queue_acceptance=queue_acceptance,
                        phase="mapping",
                        exc=exc,
                    )
                    raise
                if reconciliation.bundle is not bundle:
                    bundle = reconciliation.bundle
                    workflow = bundle.workflow
                    record = bundle.compile(
                        run_inputs=dict(record.input_binding),
                        schema_provider=self._schema_provider,
                    )
                execution_snapshot = build_execution_snapshot(
                    bundle,
                    record,
                    schema=reconciliation.schema,
                ).to_dict()
                attempt_bundle["execution_snapshot"] = execution_snapshot
            phase_start = time.monotonic()
            api_dict = await _prepare_prompt_async(
                record,
                bundle,
                backend=backend,
                schema_provider=self._schema_provider,
                on_unavailable=self._on_schema_unavailable,
            )
            if execution_snapshot is not None:
                from .reconciliation import assert_execution_snapshot

                assert_execution_snapshot(
                    execution_snapshot,
                    bundle,
                    record,
                    schema_provider=self._schema_provider,
                    schema_generation=self.process_start_identity,
                )
            schema_validation_skipped = list(getattr(api_dict, "schema_validation_skipped", []))
            normalization = getattr(api_dict, "normalization", None)
            schema_provenance = dict(getattr(api_dict, "schema_provenance", {})) or _schema_provider_provenance(self._schema_provider)
            timings["prepare_prompt_sec"] = round(time.monotonic() - phase_start, 3)
            evidence = _runtime_evidence(
                record,
                adapter_kind="managed",
                backend=backend,
                endpoint=self.url,
                schema_provenance=schema_provenance,
                queue_acceptance=queue_acceptance,
                terminal={"phase": "prepared", "reason_type": "none", "reason": None, "acceptance_known": False},
                dependency_report=dependency_report,
            )
            attempt_bundle = build_attempt_bundle(
                bundle,
                record,
                backend=backend,
                config=self.config,
                adapter_kind="managed",
                adapter_endpoint=self.url,
                schema_provenance=schema_provenance,
                runtime_evidence=evidence,
                runtime_compatibility=dependency_report,
            )
            if execution_snapshot is not None:
                attempt_bundle["execution_snapshot"] = execution_snapshot
            _persist_runtime_evidence(run_dir, attempt_bundle, evidence)
            fp = model_fingerprint(api_dict)
            phase_start = time.monotonic()
            await _maybe_flush_for_policy(self, fp)
            timings["memory_policy_sec"] = round(time.monotonic() - phase_start, 3)
            client_id = uuid.uuid4().hex
            watchdog = await _start_watchdog(server_url=self.url, client_id=client_id, api_dict=api_dict)
            phase = "drift"
            if strict_drift:
                enforce_strict_drift(workflow, lockfile_path=self.config.extra.get("lockfile"))
            phase = "queue"
            phase_start = time.monotonic()
            try:
                queued_execution = await queue_server_prompt(
                    record,
                    bundle,
                    client=ComfyClient(self.url),
                )
                queued = queued_execution.queued
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
                adapter_kind="managed", backend=backend, endpoint=self.url,
                schema_provenance=schema_provenance, queued=queued,
            )
            queue_acceptance = {"status": "accepted", "prompt_id": prompt_id}
            _set_watchdog_prompt_id(watchdog, prompt_id)
            timings["queue_prompt_sec"] = round(time.monotonic() - phase_start, 3)
            phase = "history"
            phase_start = time.monotonic()
            history = await _wait_for_server_history(self.url, prompt_id, config=self.config)
            output_verification = _validate_declared_output_contract(workflow, history, prompt_id)
            # The declared-output projection must not bypass Comfy's terminal
            # status/error decoder for the current prompt.
            _outputs_from_server_history(history, prompt_id)
            comfy_outputs = _declared_outputs_from_server_history(workflow, history, prompt_id)
            phase = "output"
            output_directory = _configured_output_directory(
                self.config, runtime_configuration=self._process_configuration
            )
            artifacts = _artifact_records(
                comfy_outputs,
                adapter_kind="managed",
                adapter_endpoint=self.url,
                output_directory=output_directory,
            )
            outputs = [artifact["reported_path"] for artifact in artifacts]
            media_validation = _verify_declared_media(
                workflow,
                artifacts,
                adapter_kind="managed",
                output_verification=output_verification,
            )
            output_verification = {**output_verification, "media": media_validation}
            timings["collect_outputs_sec"] = round(time.monotonic() - phase_start, 3)
            self.last_fingerprint = fp
            stop_reason = "completed"
            phase = "metadata"
            timings["total_inside_vibecomfy_sec"] = round(time.monotonic() - total_start, 3)
            metadata = _run_metadata(
                run_id=run_id,
                bundle=bundle,
                record=record,
                queued=queued,
                comfy_outputs=comfy_outputs,
                outputs=outputs,
                runtime="managed",
                config=self.config,
                timings=timings,
                schema_validation_skipped=schema_validation_skipped,
                schema_provenance=schema_provenance,
                normalization=normalization,
                adapter_endpoint=self.url,
                log_path=log_path,
                artifacts=artifacts,
                chain_id=chain_id,
                parent_run_id=parent_run_id,
                dependency_report=dependency_report,
                output_verification=output_verification,
                media_validation=media_validation,
                run_context=run_context,
            )
            metadata_path = _complete_runtime_run(
                run_dir=run_dir, attempt_bundle=attempt_bundle, journal_state=journal_state,
                run_id=run_id, record=record, journal_generation=journal_generation,
                adapter_kind="managed", backend=backend, endpoint=self.url,
                schema_provenance=schema_provenance, queue_acceptance=queue_acceptance,
                metadata=metadata,
                dependency_report=dependency_report,
            )
            return RunResult(
                run_id=run_id,
                prompt_id=prompt_id,
                outputs=outputs,
                metadata_path=str(metadata_path),
                log_path=log_path,
                completion_path=str(Path(metadata_path).with_name("completion.json")),
                status=str(metadata.get("status", "completed")),
                media_validated=bool(metadata.get("media_validated", False)),
                artifacts=list(metadata.get("artifacts", [])),
                log_provenance=dict(metadata.get("log_provenance", {})),
                managed_generation_result_path=(
                    str(metadata["managed_generation_result"]["path"])
                    if isinstance(metadata.get("managed_generation_result"), Mapping)
                    and metadata["managed_generation_result"].get("status") == "available"
                    else None
                ),
            )
        except asyncio.CancelledError as exc:
            stop_reason = "cancelled"
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        except KeyboardInterrupt as exc:
            stop_reason = "interrupted"
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        except Exception as exc:
            stop_reason = "errored"
            _persist_runtime_failure(
                run_dir=run_dir, attempt_bundle=attempt_bundle, state=journal_state,
                run_id=run_id, record=record, generation=journal_generation,
                original_error=exc, queue_acceptance=queue_acceptance, phase=phase, exc=exc,
            )
            raise
        finally:
            if watchdog is not None:
                await _finalize_watchdog(
                    watchdog, run_dir=run_dir, reason=stop_reason or "exception",
                )

    async def flush(self) -> None:
        await self.start()
        assert self.url is not None
        await ComfyClient(self.url).free(unload_models=True, free_memory=True)

    async def reconfigure(self, config: SessionConfig) -> bool:
        process_configuration = _snapshot_runtime_configuration(config)
        new_argv = _comfy_server_argv(
            config, runtime_configuration=process_configuration
        )
        cwd_unchanged = (
            self._process_configuration is None
            or process_configuration.cwd == self._process_configuration.cwd
        )
        if new_argv == self._argv and cwd_unchanged:
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
        self._process_configuration = None

    async def reload_for_nodepack_change(
        self, *, reason: str, server_url: str | None = None
    ) -> str:
        if server_url is not None:
            return _nodepack_reload_status(server_url)
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("reload_for_nodepack_change refused: run in flight")
        await self.stop()
        await self.start()
        logger.info("reload_for_nodepack_change: %s", reason)
        return "reloaded"


def _nodepack_reload_status(server_url: str | None) -> str:
    """Classify URL-only node-pack changes without claiming ownership.

    A supplied URL identifies an externally owned server. This helper is
    intentionally status-only; it never starts, stops, or attaches a child.
    """
    if not isinstance(server_url, str) or not server_url.strip():
        raise ValueError("external server_url must be a non-empty string")
    return "restart_required"


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


def _session_state_dir(id: str = "default", runtime_root: str | Path | None = None) -> Path:
    root = Path(runtime_root).expanduser() if runtime_root is not None else Path.cwd()
    return (root / "out" / "sessions" / id).resolve(strict=False)


def active_session_metadata(
    id: str = "default", *, runtime_root: str | Path | None = None
) -> dict[str, Any] | None:
    session_dir = _session_state_dir(id, runtime_root)
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
    # The daemon writes the child process birth identity after startup. Keep
    # it with the session observation so live schema receipts can bind their
    # generation to the process that will receive the queue.
    for name in ("comfy_process_start_identity", "process_start_identity"):
        marker = session_dir / name
        if marker.is_file():
            try:
                value = marker.read_text(encoding="utf-8").strip()
            except OSError:
                value = ""
            if value:
                result[name] = value
    if session_revision is not None:
        result["launch_source_revision"] = session_revision
    if current_revision is not None:
        result["current_source_revision"] = current_revision
    return result


def find_active_session(
    id: str = "default", *, runtime_root: str | Path | None = None
) -> str | None:
    metadata = active_session_metadata(id, runtime_root=runtime_root)
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

    if launch_marker is not None:
        if launch_marker.get("comfy_pid") is not None:
            if not _session_composite_ownership_verified(session_dir, pid):
                return False
        elif not _session_ownership_verified(session_dir, pid):
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
        raw = None
    if raw is not None:
        if not isinstance(raw, bytes) or not raw or not raw.endswith(b"\0"):
            return None
        parts = raw.split(b"\0")
        if len(parts) < 2 or any(not part for part in parts[:-1]):
            return None
        try:
            commandline = tuple(part.decode("utf-8") for part in parts[:-1])
        except UnicodeDecodeError:
            return None
        launch_flag_positions = [
            index for index, argument in enumerate(commandline) if argument == "--launch-token"
        ]
        if launch_flag_positions and (
            len(launch_flag_positions) != 1
            or launch_flag_positions[0] + 1 >= len(commandline)
        ):
            return None
        return commandline
    if sys.platform != "darwin":
        return None
    return _darwin_process_commandline(pid)


_DARWIN_CTL_KERN = 1
_DARWIN_KERN_PROCARGS2 = 49
_DARWIN_PROCARGS2_MAX_SIZE = 16 * 1024 * 1024


def _parse_darwin_procargs2(raw: bytes) -> tuple[str, ...] | None:
    """Parse the counted argv prefix returned by Darwin ``KERN_PROCARGS2``."""
    if type(raw) is not bytes or not raw or len(raw) > _DARWIN_PROCARGS2_MAX_SIZE:
        return None
    if len(raw) < 5 or not raw.endswith(b"\0"):
        return None

    try:
        argc = struct.unpack_from("=i", raw, 0)[0]
    except struct.error:
        return None
    if argc < 1 or argc > len(raw) - 4:
        return None

    executable_end = raw.find(b"\0", 4)
    if executable_end <= 4:
        return None
    try:
        raw[4:executable_end].decode("utf-8")
    except UnicodeDecodeError:
        return None

    # Darwin places padding NULs between the executable path and argv[0].
    cursor = executable_end + 1
    while cursor < len(raw) and raw[cursor] == 0:
        cursor += 1
    if cursor >= len(raw):
        return None

    commandline: list[str] = []
    for _ in range(argc):
        argument_end = raw.find(b"\0", cursor)
        if argument_end < 0:
            return None
        argument = raw[cursor:argument_end]
        try:
            commandline.append(argument.decode("utf-8"))
        except UnicodeDecodeError:
            return None
        cursor = argument_end + 1
    return tuple(commandline)


def _darwin_process_commandline(pid: int) -> tuple[str, ...] | None:
    if type(pid) is not int or pid <= 0 or pid > 2**31 - 1:
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        sysctl = libc.sysctl
        sysctl.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        sysctl.restype = ctypes.c_int
        mib = (ctypes.c_int * 3)(
            _DARWIN_CTL_KERN,
            _DARWIN_KERN_PROCARGS2,
            pid,
        )
        size = ctypes.c_size_t(0)
        if sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
            return None
        requested_size = size.value
        if requested_size < 5 or requested_size > _DARWIN_PROCARGS2_MAX_SIZE:
            return None

        buffer = (ctypes.c_ubyte * requested_size)()
        returned_size = ctypes.c_size_t(requested_size)
        if sysctl(mib, 3, buffer, ctypes.byref(returned_size), None, 0) != 0:
            return None
        # A changed size means the process raced the two sysctl calls.  Do not
        # parse a possibly truncated or mixed-generation process record.
        if returned_size.value != requested_size:
            return None
        return _parse_darwin_procargs2(bytes(buffer))
    except (
        AttributeError,
        MemoryError,
        OSError,
        OverflowError,
        TypeError,
        ValueError,
        ctypes.ArgumentError,
    ):
        return None


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


def _listener_owner_pid(url: str) -> int | None:
    """Return the sole local TCP listener owner for *url*, or fail closed."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port is None:
        return None
    try:
        result = subprocess.run(
            ["lsof", "-nP", "-t", "-a", "-iTCP:" + str(parsed.port), "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    owners: set[int] = set()
    for line in result.stdout.splitlines():
        try:
            owners.add(int(line.strip()))
        except ValueError:
            return None
    return next(iter(owners)) if len(owners) == 1 else None


def _process_parent_pid(pid: int) -> int | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[-1].split()
        if len(fields) >= 2:
            return int(fields[1])
    except (OSError, ValueError):
        pass
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "ppid="],
            capture_output=True,
            text=True,
            check=False,
            timeout=1,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _session_composite_ownership_verified(session_dir: Path, daemon_pid: int) -> bool:
    """Verify the daemon, its Comfy child, and the listener as one custody unit."""
    marker = _read_launch_marker(session_dir)
    if marker is None or not _session_ownership_verified(session_dir, daemon_pid):
        return False
    try:
        child_pid = int((session_dir / "comfy_pid").read_text(encoding="utf-8").strip())
        child_identity = (session_dir / "comfy_process_start_identity").read_text(encoding="utf-8").strip()
        marker_child_pid = int(marker["comfy_pid"])
        marker_child_identity = marker["comfy_process_start_identity"]
        marker_url = (session_dir / "url").read_text(encoding="utf-8").strip()
    except (KeyError, OSError, TypeError, ValueError):
        return False
    return bool(
        child_pid > 0
        and child_identity
        and marker_child_pid == child_pid
        and marker_child_identity == child_identity
        and _process_start_identity(child_pid) == child_identity
        and _process_parent_pid(child_pid) == daemon_pid
        and _listener_owner_pid(marker_url) == child_pid
    )


def _terminate_session_pid(pid: int, *, session_dir: Path) -> bool:
    if not _session_ownership_verified(session_dir, pid):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def _checkout_git_environment() -> dict[str, str]:
    """Return an environment that cannot redirect Git away from this checkout."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }


def current_source_revision() -> str | None:
    """Return the checkout's actual git revision.

    This identity is deliberately derived from the checkout, never from an
    environment variable supplied by a launcher.  Managed-session admission
    treats an unavailable revision as a failed attestation rather than as
    "unknown" metadata.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=find_repo_root(),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            env=_checkout_git_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    revision = result.stdout.strip()
    return revision or None


def current_source_content_digest() -> str | None:
    """Digest the effective tracked and non-ignored checkout contents.

    A commit id alone does not attest a dirty working tree.  The managed
    Worker and the Astrid adapter both compute this digest from the bytes that
    are actually importable, so a reviewed checkout cannot be replaced by a
    same-revision but modified worktree between launch and admission.
    """
    try:
        root = find_repo_root()
        result = subprocess.run(
            ["git", "ls-files", "-z", "-c", "-o", "--exclude-standard"],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            # Prepared RunPod checkouts can live on a network volume.  Keep
            # the attestation bounded, but allow the content walk to finish
            # instead of turning a slow volume into an unavailable identity.
            timeout=60,
            env=_checkout_git_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    digest = hashlib.sha256()
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            relative = os.fsdecode(raw_path)
            # Bytecode is generated runtime state.  Older prepared checkouts
            # may have tracked stale __pycache__ entries even though source
            # overlays intentionally omit them; they must not invalidate the
            # source attestation when absent.
            parts = PurePosixPath(relative).parts
            if relative.endswith(".pyc") or "__pycache__" in parts:
                continue
            candidate = root / relative
            if candidate.is_symlink() or not candidate.is_file():
                return None
            path = candidate.resolve(strict=True)
            path.relative_to(root.resolve())
            data = path.read_bytes()
        except (OSError, UnicodeError, ValueError):
            return None
        digest.update(raw_path)
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
    return "sha256:" + digest.hexdigest()


def _cleanup_session_files(session_dir: Path) -> None:
    for name in (
        "pid", "comfy_pid", "comfy_process_start_identity", "url",
        "config.json", "source_revision", "source_content_digest", "launch.json",
    ):
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
    comfy_pid: int | None = None,
    comfy_process_start_identity: str | None = None,
) -> None:
    marker = {
        "launch_token": launch_token,
        "pid": pid,
        "process_start_identity": _process_start_identity(pid),
        "url": url,
    }
    if comfy_pid is not None and comfy_process_start_identity is not None:
        marker.update({
            "comfy_pid": comfy_pid,
            "comfy_process_start_identity": comfy_process_start_identity,
        })
    atomic_write_json(
        session_dir / "launch.json",
        marker,
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
        "strict_drift",
        "runtime_root",
        "cwd",
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
    from vibecomfy.schema import RuntimeSchemaProvider, TargetSchemaProvider

    if server_url:
        return TargetSchemaProvider(server_url=server_url)
    return RuntimeSchemaProvider(server_url=server_url)


async def _warm_schema_provider(
    provider: Any | None,
    *,
    on_unavailable,
    cache_only: bool = False,
) -> Any | None:
    if provider is None:
        return None
    from vibecomfy.schema.cache import ObjectInfoPayloadError
    target_provider = bool(getattr(provider, "requires_fresh_target", False))
    if target_provider:
        # Explicit target authority can never use cache-only mode: that would
        # turn historical bytes into proof about the server being queued.
        cache_only = False

    try:
        if getattr(provider, "_object_info", None) is not None:
            return provider
        if cache_only:
            from vibecomfy.schema.cache import (
                load_object_info_cache,
                validate_object_info_cache,
            )

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

        object_info_async = getattr(provider, "object_info_async", None)
        if not callable(object_info_async):
            # A synchronous-only provider is still a valid lookup seam for the
            # later structural gate, but calling it here would risk blocking
            # (or re-entering) the active runtime event loop.
            return provider
        from vibecomfy.schema.cache import validate_object_info_payload_shape

        object_info = await object_info_async()
        validate_object_info_payload_shape(object_info)
        provider._object_info = object_info
        return provider
    except ObjectInfoPayloadError as exc:
        if target_provider:
            raise
        on_unavailable(f"{type(exc).__name__}: {exc}; using structural validation only")
        return None
    except (OSError, RuntimeError, TimeoutError) as exc:
        if target_provider:
            raise
        on_unavailable(f"{type(exc).__name__}: {exc}; using structural validation only")
        return None


def _prepare_prompt(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    backend: str,
    schema_provider: Any | None = None,
) -> dict[str, Any]:
    if backend != "api":
        raise WorkflowBuildError(
            "runtime execution accepts only the approved API projection"
        )
    api_dict, _skipped = _prepare_runtime_prompt_with_evidence(
        record,
        bundle,
        schema_provider=schema_provider,
    )
    return api_dict


async def _prepare_prompt_async(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
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
        if backend != "api":
            raise WorkflowBuildError(
                "runtime execution accepts only the approved API projection"
            )
        api_dict, skipped = _prepare_runtime_prompt_with_evidence(
            record,
            bundle,
            schema_provider=effective,
        )
        if skipped:
            on_unavailable("schema validation skipped for class types: " + ", ".join(skipped))
        return PreparedPrompt(
            api_dict,
            schema_validation_skipped=skipped,
            normalization=None,
            schema_provenance=_schema_provider_provenance(effective),
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
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    backend: str,
    schema_provider: Any | None,
) -> dict[str, Any]:
    api_dict, _skipped = _prepare_runtime_prompt_with_evidence(
        record,
        bundle,
        schema_provider=schema_provider,
    )
    return api_dict


def _prepare_runtime_prompt_with_evidence(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    schema_provider: Any | None,
) -> tuple[dict[str, Any], list[str]]:
    """Validate the already-approved API projection without rewriting it."""
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime preparation requires an approved record and bundle")
    record.assert_matches(
        bundle,
        record.selected_variant,
        record.input_binding,
        api_projection=record.api_projection,
        ui_projection=record.ui_projection,
    )
    api_dict = record.to_dict()["api_projection"]
    if not isinstance(api_dict, dict):
        raise WorkflowBuildError("approved API projection must be a JSON object")
    skipped = _schema_skipped_class_types(api_dict) if schema_provider is None else []
    if schema_provider is not None:
        from vibecomfy.schema.validate import (
            SchemaNormalizationRequired,
            propose_schema_normalization,
            validate_api_against_schema,
            validate_api_link_shapes,
        )

        proposal = propose_schema_normalization(api_dict, schema_provider)
        if proposal.ops:
            raise SchemaNormalizationRequired(proposal)
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
    return api_dict, skipped


def _run_metadata(
    *,
    run_id: str,
    bundle: WorkflowBundle,
    record: ApprovedProjectionRecord,
    queued: Any,
    outputs: list[str],
    runtime: str,
    comfy_outputs: Any = None,
    config: SessionConfig | None = None,
    timings: dict[str, float] | None = None,
    schema_validation_skipped: list[str] | None = None,
    schema_provenance: Mapping[str, Any] | None = None,
    adapter_endpoint: str | None = None,
    log_path: str | Path | None = None,
    external_log_locator: str | Path | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    normalization: Any | None = None,
    chain_id: str | None = None,
    parent_run_id: str | None = None,
    dependency_report: Mapping[str, Any] | None = None,
    output_verification: Mapping[str, Any] | None = None,
    media_validation: Mapping[str, Any] | None = None,
    adapter_details: Mapping[str, Any] | None = None,
    run_context: RunContext | None = None,
    identity_config: SessionConfig | None = None,
) -> dict[str, Any]:
    workflow = _require_runtime_boundary(record, bundle)
    approved = record.to_dict()
    api_dict = approved["api_projection"]
    if comfy_outputs is None:
        comfy_outputs = _raw_comfy_outputs(queued)
    serialized = json.dumps(api_dict, sort_keys=True, default=str)
    if artifacts is None:
        artifacts = _artifact_records(
            comfy_outputs,
            adapter_kind=runtime,
            adapter_endpoint=adapter_endpoint,
            fallback_paths=outputs,
        )
    else:
        artifacts = list(artifacts)
    outputs = [artifact["reported_path"] for artifact in artifacts]
    artifact_manifest = _artifact_manifest(workflow, outputs)
    identity = _managed_generation_identity(
        workflow, run_id, config or identity_config, run_context
    )
    declared_outputs = [
        {
            "declaration_ordinal": ordinal,
            "node_id": str(output.node_id),
            "output_type": str(output.output_type),
            "name": output.name,
            "artifact_kind": output.artifact_kind,
            "mime_type": output.mime_type,
            "filename_prefix": output.filename_prefix,
            "expected_cardinality": output.expected_cardinality,
        }
        for ordinal, output in enumerate(workflow.outputs)
    ]
    log_provenance = _log_provenance(
        log_path,
        runtime,
        external_log_locator=external_log_locator,
    )
    # Reuse attempt helper for shared fields so metadata.json agrees with attempt.json.
    shared = build_shared_fields(
        bundle, record, config=config, adapter_kind=runtime,
        adapter_endpoint=adapter_endpoint, runtime_compatibility=dependency_report,
    )
    media_verified = bool(
        isinstance(media_validation, Mapping)
        and media_validation.get("status") == "verified"
    )
    declared_video = any(
        str(getattr(output, "artifact_kind", "") or "").lower() == "video"
        or str(getattr(output, "mime_type", "") or "").lower().startswith("video/")
        for output in workflow.outputs
    )
    completion_status = (
        "Completed — final video verified"
        if media_verified and declared_video
        else "Completed — final media verified"
        if media_verified
        else "completed"
    )
    adapter = {
        "kind": runtime,
        "backend": "api",
        "endpoint": adapter_endpoint,
    }
    if adapter_details:
        adapter["lifecycle"] = dict(adapter_details)
    metadata = {
        "run_id": run_id,
        "workflow_id": workflow.id,
        **identity,
        "source": asdict(workflow.source),
        "workflow_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "api_digest": approved["api_digest"],
        "adapter": adapter,
        "schema_provenance": dict(schema_provenance or {}),
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
        "declared_outputs": declared_outputs,
        "artifact_paths": outputs,
        "outputs": outputs,
        "artifacts": artifacts,
        "status": completion_status,
        "media_validated": media_verified,
        "media_validation": (
            dict(media_validation) if isinstance(media_validation, Mapping) else "not_performed"
        ),
        "log_path": log_provenance["path"],
        "log_provenance": log_provenance,
        "runtime": runtime,
        "schema_validation_skipped": schema_validation_skipped or [],
    }
    if output_verification is not None:
        metadata["output_verification"] = dict(output_verification)
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
    if getattr(reqs, "runtime", None) is not None:
        metadata["requirements"]["runtime"] = reqs.runtime.to_dict()
    if dependency_report and dependency_report.get("declared") is not False:
        metadata["runtime_dependency"] = dict(dependency_report)
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
    return _bounded_structured_value(value)


def _bounded_structured_value(value: Any, *, depth: int = 0) -> Any:
    """Keep structured Comfy diagnostics useful without persisting unbounded data."""
    if depth >= 4:
        return _bounded_terminal_value(value)
    if isinstance(value, Mapping):
        bounded: dict[str, Any] = {}
        for key, item in list(value.items())[:64]:
            bounded[_bounded_terminal_value(key)] = _bounded_structured_value(
                item, depth=depth + 1
            )
        return bounded
    if isinstance(value, (list, tuple)):
        return [
            _bounded_structured_value(item, depth=depth + 1)
            for item in value[:64]
        ]
    return _bounded_terminal_value(value)


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
    error = RuntimeNodeError(
        _bounded_diagnostic(message),
        next_action="vibecomfy runtime doctor",
    )
    error.diagnostics = [{
        "code": "comfy_execution_error",
        "prompt_id": prompt_id,
        "detail": _bounded_terminal_evidence(status),
    }]
    raise error


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
    timeout_sec = _duration_seconds(
        raw_timeout,
        name="prompt_timeout_sec (VIBECOMFY_PROMPT_TIMEOUT_SEC)",
        default=3600,
    )
    raw_poll_interval = os.environ.get("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC")
    poll_interval_sec = _duration_seconds(
        raw_poll_interval,
        name="history_poll_interval_sec (VIBECOMFY_HISTORY_POLL_INTERVAL_SEC)",
        default=1,
        allow_zero=True,
    )
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


def _declared_outputs_from_server_history(
    workflow: VibeWorkflow,
    history: Mapping[str, Any],
    prompt_id: str | None,
) -> dict[str, Any]:
    """Return only artifacts produced by the workflow's declared final sinks."""
    entry = _history_entry(history, prompt_id)
    raw_outputs = entry.get("outputs") if isinstance(entry, Mapping) else None
    if not isinstance(raw_outputs, Mapping):
        return {}
    if not any(
        getattr(output, "node_id", None) is not None
        for output in workflow.outputs
    ):
        # Workflows without an explicit OutputSpec retain the historical
        # behavior: return the complete Comfy output map.  The strict final
        # sink filter applies only when Python has declared one.
        return dict(raw_outputs)
    return {
        str(output.node_id): raw_outputs[str(output.node_id)]
        for output in workflow.outputs
        if getattr(output, "node_id", None) is not None
        and str(output.node_id) in raw_outputs
    }


def _validate_declared_output_contract(
    workflow: VibeWorkflow,
    history: Mapping[str, Any],
    prompt_id: str | None,
) -> dict[str, Any]:
    """Fail closed when a declared final sink did not produce an artifact.

    A successful Comfy status only means that the accepted execution reached a
    terminal status. It does not guarantee that every executable branch was
    accepted. This check prevents a preview/intermediate branch from being
    reported as the final result when the declared sink was ignored.
    """
    declared = [
        output for output in workflow.outputs
        if getattr(output, "node_id", None) is not None
    ]
    evidence: dict[str, Any] = {
        "prompt_id": prompt_id,
        "declared_final_nodes": [str(output.node_id) for output in declared],
        "events": [],
        "structured_diagnostics": [],
    }
    if not declared:
        evidence["status"] = "not_declared"
        return evidence
    entry = _history_entry(history, prompt_id)
    if entry is None:
        error = RuntimeNodeError(
            f"Comfy history for prompt {prompt_id!r} is missing the current execution entry",
            next_action="inspect the durable Comfy history/log and verify the prompt ID",
        )
        error.diagnostics = [{
            "code": "history_prompt_mismatch",
            "prompt_id": prompt_id,
            "declared_final_nodes": evidence["declared_final_nodes"],
        }]
        raise error
    status = entry.get("status")
    messages = status.get("messages") if isinstance(status, Mapping) else None
    if isinstance(messages, (list, tuple)):
        evidence["events"] = [
            _bounded_terminal_value(message[0] if isinstance(message, (list, tuple)) and message else message)
            for message in messages[-64:]
        ]
    structured: list[dict[str, Any]] = []
    for field_name in ("node_errors", "errors", "execution_errors", "ignored_nodes", "ignored_outputs", "rejected_nodes"):
        value = entry.get(field_name)
        if value:
            structured.append({
                "code": f"comfy_{field_name}",
                "field": field_name,
                "detail": _bounded_error_details(value),
            })
    if isinstance(status, Mapping) and _status_has_execution_error(status):
        structured.append({
            "code": "comfy_execution_error",
            "field": "status.messages",
            "detail": _bounded_status_message(messages),
        })
    evidence["structured_diagnostics"] = structured
    if structured:
        error = RuntimeNodeError(
            f"Comfy reported structured final-output diagnostics for prompt {prompt_id!r}; "
            "a top-level success status is not sufficient",
            next_action="inspect the per-node diagnostics and correct the final output branch",
        )
        error.diagnostics = structured
        error.output_verification = evidence
        raise error
    raw_outputs = entry.get("outputs") if isinstance(entry, Mapping) else None
    if not isinstance(raw_outputs, Mapping):
        error = RuntimeNodeError(
            "Comfy completed without a structured output map for the declared "
            f"final sink(s) {[str(output.node_id) for output in declared]}",
            next_action="inspect the durable Comfy history/log and verify the final output declaration",
        )
        error.diagnostics = [{
            "code": "missing_structured_outputs",
            "declared_final_nodes": evidence["declared_final_nodes"],
        }]
        error.output_verification = evidence
        raise error
    available = {str(node_id) for node_id in raw_outputs}
    evidence["available_output_nodes"] = sorted(available)
    missing = [str(output.node_id) for output in declared if str(output.node_id) not in available]
    if missing:
        error = RuntimeNodeError(
            f"Comfy completed without declared final output node(s) {missing}; "
            f"available output nodes: {sorted(available)}. A preview or intermediate "
            "artifact is not a successful final result.",
            next_action="inspect the Comfy validation diagnostics and correct the final output branch",
        )
        error.diagnostics = [{
            "code": "declared_final_output_missing",
            "missing_nodes": missing,
            "available_output_nodes": sorted(available),
            "preview_or_intermediate_nodes": sorted(
                available - {str(output.node_id) for output in declared}
            ),
        }]
        error.output_verification = evidence
        raise error
    empty = []
    contract_errors: list[dict[str, Any]] = []
    for output in declared:
        node_id = str(output.node_id)
        entries = _collect_output_entries(raw_outputs[node_id])
        if not entries:
            empty.append(node_id)
            continue
        expected_cardinality = getattr(output, "expected_cardinality", None)
        if str(expected_cardinality).lower() in {"one", "1"} and len(entries) != 1:
            contract_errors.append({
                "code": "declared_final_output_cardinality",
                "node_id": node_id,
                "expected": expected_cardinality,
                "actual": len(entries),
            })
        expected_kind = str(getattr(output, "artifact_kind", "") or "").lower()
        expected_mime = str(getattr(output, "mime_type", "") or "").lower()
        for descriptor, path in entries:
            filename = descriptor.get("filename") if isinstance(descriptor, Mapping) else None
            if not isinstance(filename, str) or not filename.strip() or not isinstance(path, str) or not path.strip():
                contract_errors.append({
                    "code": "declared_final_output_empty_descriptor",
                    "node_id": node_id,
                })
                continue
            suffix = Path(filename).suffix.lower()
            if expected_kind == "video" or expected_mime.startswith("video/"):
                if suffix not in {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v", ".gif"}:
                    contract_errors.append({
                        "code": "declared_final_output_not_video",
                        "node_id": node_id,
                        "filename": filename,
                        "expected_mime": expected_mime or None,
                    })
    if empty:
        error = RuntimeNodeError(
            f"Comfy completed but declared final output node(s) {empty} produced no artifact; "
            "an intermediate/preview artifact cannot satisfy the final output contract.",
            next_action="inspect the durable Comfy history/log and correct the final sink inputs",
        )
        error.diagnostics = [{
            "code": "declared_final_output_empty",
            "empty_nodes": empty,
            "available_output_nodes": sorted(available),
        }]
        error.output_verification = evidence
        raise error
    if contract_errors:
        error = RuntimeNodeError(
            f"Comfy completed but declared final output contract was not satisfied for node(s) "
            f"{sorted({item.get('node_id') for item in contract_errors})}",
            next_action="inspect the final artifact descriptors and correct the output sink contract",
        )
        error.diagnostics = contract_errors
        error.output_verification = evidence
        raise error
    evidence["status"] = "final_output_produced"
    evidence["artifact_nodes"] = sorted(
        node_id for node_id in available if _collect_output_entries(raw_outputs[node_id])
    )
    return evidence


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
    return [path for _descriptor, path in _collect_output_entries(value, output_directory=output_directory)]


def _collect_output_entries(
    value: Any,
    *,
    output_directory: str | Path | None = None,
) -> list[tuple[dict[str, Any] | None, str]]:
    """Traverse history once, retaining one entry per physical artifact.

    ComfyUI's video sinks can expose the same saved file in both ``gifs`` and
    ``images``.  Those are alternate descriptor views of one artifact, not two
    final outputs.  Keep the first (usually the richer ``gifs`` descriptor) and
    deduplicate by the descriptor's filename/subfolder/type identity.
    """

    entries: list[tuple[dict[str, Any] | None, str]] = []

    def visit(item: Any, *, source: str | None = None) -> None:
        if isinstance(item, dict):
            filename = item.get("filename")
            if isinstance(filename, str):
                descriptor = dict(item)
                descriptor["descriptor_sources"] = [source or "descriptor"]
                entries.append((descriptor, _resolve_comfy_output_filename(item, output_directory)))
                return
            for key, child in item.items():
                if key in {"abs_path", "path", "fullpath", "filename"} and isinstance(child, str):
                    entries.append((None, child))
                else:
                    visit(child, source=str(key))
        elif isinstance(item, list):
            for child in item:
                visit(child, source=source)

    visit(value)

    unique: list[tuple[dict[str, Any] | None, str]] = []
    index_by_key: dict[tuple[str, ...], int] = {}
    for descriptor, path in entries:
        if descriptor is not None:
            key = (
                "artifact",
                str(descriptor.get("type") or "output").strip().lower(),
                os.path.normcase(os.path.normpath(path)),
            )
        else:
            key = ("artifact", "output", os.path.normcase(os.path.normpath(str(path))))
        existing_index = index_by_key.get(key)
        if existing_index is None:
            index_by_key[key] = len(unique)
            unique.append((descriptor, path))
            continue
        existing_descriptor, existing_path = unique[existing_index]
        if descriptor is None:
            continue
        if existing_descriptor is None:
            unique[existing_index] = (descriptor, path)
            continue
        merged = dict(existing_descriptor)
        sources = list(merged.get("descriptor_sources") or [])
        for source in descriptor.get("descriptor_sources") or []:
            if source not in sources:
                sources.append(source)
        merged["descriptor_sources"] = sources
        for field_name, field_value in descriptor.items():
            if field_name in {"filename", "subfolder", "type", "descriptor_sources"}:
                continue
            if field_name in merged and merged[field_name] != field_value:
                error = RuntimeNodeError(
                    "Comfy history returned contradictory descriptors for one output artifact",
                    next_action="inspect the final sink history and correct the conflicting descriptor metadata",
                )
                error.diagnostics = [{
                    "code": "conflicting_comfy_output_descriptors",
                    "artifact_path": existing_path,
                    "field": field_name,
                    "values": [merged[field_name], field_value],
                    "descriptor_sources": sources,
                }]
                raise error
            merged.setdefault(field_name, field_value)
        unique[existing_index] = (merged, existing_path)
    for index, (descriptor, path) in enumerate(unique):
        if descriptor is not None and len(descriptor.get("descriptor_sources") or []) < 2:
            descriptor = dict(descriptor)
            descriptor.pop("descriptor_sources", None)
            unique[index] = (descriptor, path)
    return unique


def _comfy_view_url(endpoint: str, descriptor: Mapping[str, Any]) -> str | None:
    """Return Comfy's retrievable view URL for a remote output descriptor."""
    filename = descriptor.get("filename")
    if not isinstance(filename, str) or not filename:
        return None
    params = {
        "filename": filename,
        "subfolder": str(descriptor.get("subfolder") or ""),
        "type": str(descriptor.get("type") or "output"),
    }
    return f"{endpoint.rstrip('/')}/view?{urllib.parse.urlencode(params)}"


def _artifact_records(
    comfy_outputs: Any,
    *,
    adapter_kind: str,
    adapter_endpoint: str | None,
    output_directory: str | Path | None = None,
    fallback_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Make output provenance explicit without pretending remote files are local."""
    entries = _collect_output_entries(comfy_outputs, output_directory=output_directory)
    if not entries and fallback_paths:
        entries = [(None, path) for path in fallback_paths]
    records: list[dict[str, Any]] = []
    remote_adapter = adapter_kind in {"external", "runpod_lifecycle"}
    for descriptor, output in entries:
        descriptor = descriptor or {}
        record: dict[str, Any] = {
            "reported_path": output,
            "filename": descriptor.get("filename") or Path(output).name,
            "subfolder": descriptor.get("subfolder") or "",
            "type": descriptor.get("type") or "output",
            "descriptor": dict(descriptor) if descriptor else None,
            "source": (
                "runpod_lifecycle"
                if adapter_kind == "runpod_lifecycle"
                else "external_comfy_server"
                if remote_adapter
                else "local_filesystem"
            ),
        }
        if remote_adapter and adapter_endpoint and descriptor:
            record["location"] = _comfy_view_url(adapter_endpoint, descriptor)
            record["path"] = None
            if output_directory is not None and str(
                descriptor.get("type") or "output"
            ) == "output":
                try:
                    shared_root = Path(output_directory).expanduser().resolve(strict=True)
                    shared_path = Path(output).expanduser().resolve(strict=True)
                    shared_path.relative_to(shared_root)
                    if shared_path.is_file():
                        record["path"] = str(shared_path)
                        record["source"] = "shared_filesystem"
                except (OSError, ValueError):
                    # The server's output may be remote-only.  Keep the
                    # locator while refusing to claim producer custody.
                    pass
        elif remote_adapter:
            record["location"] = None
            record["path"] = None
            record["location_reason"] = (
                "Comfy history returned a path without a retrievable output descriptor."
            )
        else:
            record["location"] = output
            record["path"] = output
        records.append(record)
    return records


def _media_contract(workflow: VibeWorkflow) -> dict[str, Any]:
    """Return the optional, source-authored media expectations."""
    raw = workflow.metadata.get("media_contract")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _probe_media_file(path: Path) -> dict[str, Any]:
    """Run one bounded ffprobe and return only stable media facts."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return {"status": "unavailable", "reason": "ffprobe is not installed"}
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,width,height,duration:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": str(exc) or type(exc).__name__}
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "ffprobe failed").strip()
        return {"status": "invalid", "reason": _bounded_terminal_value(detail)}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "invalid", "reason": f"ffprobe returned invalid JSON: {exc}"}
    streams = payload.get("streams") if isinstance(payload, Mapping) else None
    if not isinstance(streams, list):
        streams = []
    facts: dict[str, Any] = {
        "status": "verified",
        "video_streams": 0,
        "audio_streams": 0,
        "width": None,
        "height": None,
        "duration_sec": None,
    }
    durations: list[float] = []
    for stream in streams:
        if not isinstance(stream, Mapping):
            continue
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            facts["video_streams"] += 1
            if facts["width"] is None and isinstance(stream.get("width"), int):
                facts["width"] = stream["width"]
            if facts["height"] is None and isinstance(stream.get("height"), int):
                facts["height"] = stream["height"]
        elif codec_type == "audio":
            facts["audio_streams"] += 1
        try:
            duration = float(stream.get("duration"))
        except (TypeError, ValueError):
            duration = 0.0
        if math.isfinite(duration) and duration > 0:
            durations.append(duration)
    format_info = payload.get("format") if isinstance(payload, Mapping) else None
    if isinstance(format_info, Mapping):
        try:
            duration = float(format_info.get("duration"))
        except (TypeError, ValueError):
            duration = 0.0
        if math.isfinite(duration) and duration > 0:
            durations.append(duration)
    if durations:
        facts["duration_sec"] = round(max(durations), 6)
    return facts


def _verify_declared_media(
    workflow: VibeWorkflow,
    artifacts: Sequence[Mapping[str, Any]],
    *,
    adapter_kind: str,
    output_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify declared media without treating a filename as a valid artifact."""
    declared = [
        output
        for output in workflow.outputs
        if str(getattr(output, "artifact_kind", "") or "").lower() in {"video", "audio"}
        or str(getattr(output, "mime_type", "") or "").lower().startswith(("video/", "audio/"))
    ]
    if not declared:
        return {"status": "not_required", "required": False, "artifacts": []}
    contract = _media_contract(workflow)
    require_audio = bool(contract.get("require_audio")) or any(
        str(getattr(output, "artifact_kind", "") or "").lower() == "audio"
        or str(getattr(output, "mime_type", "") or "").lower().startswith("audio/")
        for output in declared
    )
    expected_dimensions = contract.get("expected_dimensions")
    if isinstance(expected_dimensions, (list, tuple)) and len(expected_dimensions) == 2:
        expected_width, expected_height = expected_dimensions
    else:
        expected_width = expected_height = None
    expected_min_duration = contract.get("min_duration_sec")
    try:
        expected_min_duration = float(expected_min_duration) if expected_min_duration is not None else None
    except (TypeError, ValueError):
        expected_min_duration = None
    if not artifacts:
        detail = [{"code": "final_media_missing", "reason": "declared media sink produced no artifact"}]
        error = RuntimeNodeError(
            "declared final media could not be verified because no artifact was produced",
            next_action="inspect the final sink history and retrieve the declared artifact",
        )
        error.diagnostics = detail
        error.output_verification = {
            **dict(output_verification or {}),
            "media": {"status": "invalid", "required": True, "diagnostics": detail},
        }
        raise error
    probed: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for artifact in artifacts:
        raw_path = artifact.get("path") or artifact.get("reported_path")
        path = Path(str(raw_path)) if isinstance(raw_path, str) and raw_path.strip() else None
        # An external Comfy server may still share the local filesystem (for
        # example, VibeComfy and ComfyUI running in the same RunPod pod).  Do
        # not probe a filename-only remote artifact, but verify it whenever
        # the caller supplied a concrete path and that path exists locally.
        if path is None or not path.is_file():
            probe = {
                "status": "unavailable",
                "reason": "artifact is not available on the local filesystem",
            }
        else:
            probe = _probe_media_file(path)
        item = {
            "reported_path": artifact.get("reported_path"),
            "path": str(path) if path is not None else None,
            **probe,
        }
        probed.append(item)
        if probe.get("status") != "verified":
            diagnostics.append({"code": "final_media_unverified", **item})
            continue
        expected_video = any(
            str(getattr(output, "artifact_kind", "") or "").lower() == "video"
            or str(getattr(output, "mime_type", "") or "").lower().startswith("video/")
            for output in declared
        )
        expected_audio = require_audio or any(
            str(getattr(output, "artifact_kind", "") or "").lower() == "audio"
            or str(getattr(output, "mime_type", "") or "").lower().startswith("audio/")
            for output in declared
        )
        if expected_video and (probe.get("video_streams", 0) < 1 or not probe.get("width") or not probe.get("height")):
            diagnostics.append({"code": "final_video_stream_missing", **item})
        if expected_audio and probe.get("audio_streams", 0) < 1:
            diagnostics.append({"code": "final_audio_stream_missing", **item})
        if expected_min_duration is not None and (probe.get("duration_sec") or 0) < expected_min_duration:
            diagnostics.append({
                "code": "final_media_duration_too_short",
                "expected_min_duration_sec": expected_min_duration,
                **item,
            })
        if expected_width is not None and probe.get("width") != expected_width:
            diagnostics.append({"code": "final_media_width_mismatch", "expected": expected_width, **item})
        if expected_height is not None and probe.get("height") != expected_height:
            diagnostics.append({"code": "final_media_height_mismatch", "expected": expected_height, **item})
    result = {
        "status": "verified" if not diagnostics else "invalid",
        "required": True,
        "adapter_kind": adapter_kind,
        "require_audio": require_audio,
        "artifacts": probed,
        "diagnostics": diagnostics,
    }
    if diagnostics:
        error = RuntimeNodeError(
            "declared final media could not be verified: decodability or stream-property verification failed",
            next_action="inspect the final media artifact and correct the output branch",
        )
        error.diagnostics = diagnostics
        error.output_verification = {**dict(output_verification or {}), "media": result}
        error.delivery_state = {
            "execution": {
                "status": "succeeded",
                "evidence": "declared final artifact was attributed by current prompt history",
            },
            "verification": {"status": "failed", "diagnostics": diagnostics},
            "retrieval": {
                "status": (
                    "failed"
                    if adapter_kind == "external"
                    else "succeeded"
                    if any(item.get("path") and Path(str(item["path"])).is_file() for item in artifacts)
                    else "not_required"
                )
            },
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
            "retryable": adapter_kind == "external",
        }
        raise error
    return result


def _log_provenance(
    log_path: str | Path | None,
    adapter_kind: str,
    *,
    external_log_locator: str | Path | None = None,
) -> dict[str, Any]:
    """Describe log ownership and availability without returning fake paths."""
    if adapter_kind == "external":
        provenance: dict[str, Any] = {
            "available": False,
            "kind": "external_server",
            "path": None,
            "reason": "Comfy server owns its logs; VibeComfy did not capture them.",
        }
        if external_log_locator is not None and str(external_log_locator).strip():
            provenance["locator"] = str(external_log_locator)
            provenance["locator_kind"] = "configured_external_log"
            provenance["reason"] = (
                "Comfy server owns its logs; VibeComfy did not capture them; "
                "the configured locator is a reference only."
            )
        return provenance
    path = str(log_path) if log_path is not None else None
    return {
        "available": bool(path and Path(path).is_file()),
        "kind": "vibecomfy_captured_file",
        "path": path,
    }


def _external_log_locator(config: SessionConfig | None) -> str | None:
    """Return an operator-supplied reference for logs owned by an external server."""
    configured = config.extra.get("external_log_locator") if config is not None else None
    locator = configured if configured is not None else os.environ.get("VIBECOMFY_EXTERNAL_LOG_LOCATOR")
    if locator is None or not str(locator).strip():
        return None
    return str(locator)


def _unsafe_output_descriptor(
    *, filename: Any, subfolder: Any, reason: str
) -> RuntimeNodeError:
    error = RuntimeNodeError(
        "Comfy history returned an unsafe output descriptor",
        next_action="inspect the final sink descriptor and keep it relative to an approved output root",
    )
    error.diagnostics = [{
        "code": "unsafe_comfy_output_descriptor",
        "filename": filename,
        "subfolder": subfolder,
        "reason": reason,
    }]
    return error


def _normalized_descriptor_path(value: Mapping[str, Any]) -> PurePosixPath:
    filename = value.get("filename")
    subfolder = value.get("subfolder") or ""
    if not isinstance(filename, str) or not filename.strip():
        raise _unsafe_output_descriptor(
            filename=filename, subfolder=subfolder, reason="filename is empty"
        )
    components: list[str] = []
    for field_name, raw in (("subfolder", subfolder), ("filename", filename)):
        if not isinstance(raw, str):
            raise _unsafe_output_descriptor(
                filename=filename,
                subfolder=subfolder,
                reason=f"{field_name} is not a string",
            )
        normalized = raw.replace("\\", "/").strip()
        if not normalized:
            continue
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
            raise _unsafe_output_descriptor(
                filename=filename,
                subfolder=subfolder,
                reason=f"{field_name} is absolute or contains traversal",
            )
        if candidate.parts and candidate.parts[0].endswith(":"):
            raise _unsafe_output_descriptor(
                filename=filename,
                subfolder=subfolder,
                reason=f"{field_name} contains an absolute drive path",
            )
        components.extend(part for part in candidate.parts if part not in {"", "."})
    if not components:
        raise _unsafe_output_descriptor(
            filename=filename, subfolder=subfolder, reason="descriptor has no relative path"
        )
    return PurePosixPath(*components)


def _resolve_comfy_output_filename(
    value: dict[str, Any], output_directory: str | Path | None
) -> str:
    relative = _normalized_descriptor_path(value)
    if output_directory is None:
        return relative.as_posix()
    root = Path(output_directory).expanduser().resolve(strict=False)
    candidate = (root / Path(*relative.parts)).resolve(strict=False)
    try:
        inside_root = candidate.is_relative_to(root)
    except AttributeError:  # pragma: no cover - Python 3.8 compatibility
        inside_root = str(candidate).startswith(str(root) + os.sep)
    if not inside_root:
        raise _unsafe_output_descriptor(
            filename=value.get("filename"),
            subfolder=value.get("subfolder"),
            reason="resolved path escapes the configured output root",
        )
    return str(candidate)


def _configured_output_directory(
    config: SessionConfig | None,
    *,
    runtime_configuration: _RuntimeConfigurationSnapshot | None = None,
) -> str | None:
    if runtime_configuration is not None:
        values = runtime_configuration.values
    else:
        values: dict[str, Any] = {}
        if config is not None:
            values.update(config.extra)
        values.update(_read_environment_configuration())
    output_directory = values.get("output_directory")
    return str(output_directory) if output_directory else None


def _embedded_configuration_for_session(
    config: SessionConfig,
    *,
    runtime_configuration: _RuntimeConfigurationSnapshot | None = None,
) -> Configuration | None:
    runtime_configuration = runtime_configuration or _snapshot_runtime_configuration(config)
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

    values.update(runtime_configuration.values)
    if runtime_configuration.use_sage_attention:
        values["use_sage_attention"] = True
    # Authored S1 configuration binding: when the embedded client is selected,
    # derive the ComfyUI root and its model-path file from the same explicit
    # checkout instead of silently falling back to the worker cwd.  Explicit
    # SessionConfig/configuration values remain authoritative.
    comfyui_path = os.environ.get("COMFYUI_PATH")
    if comfyui_path:
        root = Path(comfyui_path).expanduser()
        if root.is_dir():
            values.setdefault("base_directory", str(root.resolve()))
            extra_from_root = root / "extra_model_paths.yaml"
            if extra_from_root.is_file():
                values.setdefault(
                    "extra_model_paths_config", [str(extra_from_root.resolve())]
                )
    extra_model_paths = runtime_configuration.cwd / "extra_model_paths.yaml"
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


def _comfy_server_argv(
    config: SessionConfig,
    *,
    runtime_configuration: _RuntimeConfigurationSnapshot | None = None,
) -> tuple[str, ...]:
    runtime_configuration = runtime_configuration or _snapshot_runtime_configuration(config)
    values = runtime_configuration.values
    command = _comfyui_command()
    if config.runtime_root is not None:
        from .dependencies import _managed_python

        managed_python = _managed_python(config.runtime_root)
        if managed_python is not None:
            managed_cli = managed_python.with_name("comfyui")
            command = (str(managed_cli),) if managed_cli.is_file() else (
                str(managed_python), "-m", "comfy.cmd.main"
            )
    argv = [*command, "serve"]
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
    if runtime_configuration.use_sage_attention:
        argv.append("--use-sage-attention")
    base_directory = values.get("base_directory")
    if base_directory:
        argv.extend(["--base-directory", str(base_directory)])
    extra_model_paths = values.get("extra_model_paths_config")
    if isinstance(extra_model_paths, str):
        extra_model_paths = [extra_model_paths]
    if isinstance(extra_model_paths, list):
        for path in extra_model_paths:
            if path:
                argv.extend(["--extra-model-paths-config", str(path)])
    for key, flag in (
        ("input_directory", "--input-directory"),
        ("output_directory", "--output-directory"),
        ("temp_directory", "--temp-directory"),
    ):
        value = values.get(key)
        if value:
            argv.extend([flag, str(value)])
    argv.extend(["--port", str(config.port or 8188)])
    declared_flags = values.get("launch_flags")
    if isinstance(declared_flags, (list, tuple)):
        argv.extend(str(flag) for flag in declared_flags if str(flag).strip())
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
    config: SessionConfig,
    log_path: str | Path | None = None,
    *,
    runtime_configuration: _RuntimeConfigurationSnapshot | None = None,
) -> tuple[asyncio.subprocess.Process, str, Any | None]:
    runtime_configuration = runtime_configuration or _snapshot_runtime_configuration(config)
    ready_timeout_sec = _managed_ready_timeout_sec(config)
    _assert_managed_endpoint_available(config)
    log_handle = None
    if log_path:
        log_path = _resolve_runtime_path(
            log_path, base=config.runtime_root, field_name="server_log_path"
        )
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_handle = Path(log_path).open("ab", buffering=0)
    argv = _comfy_server_argv(config, runtime_configuration=runtime_configuration)
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
            cwd=str(runtime_configuration.cwd),
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


def _assert_embedded_managed_interpreter(config: SessionConfig) -> None:
    """Embedded Comfy runs in this interpreter; reject a different managed env."""
    from .dependencies import _managed_python

    managed_python = _managed_python(config.runtime_root)
    if managed_python is None:
        return
    managed_root = managed_python.parent.parent
    if Path(sys.prefix).resolve(strict=False) != managed_root.resolve(strict=False):
        raise RuntimeConfigurationError(
            "embedded execution cannot use a different managed interpreter; "
            f"selected {managed_python}, current environment {sys.executable}. "
            "Use managed server execution or invoke VibeComfy from the selected environment."
        )


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
                if _MODEL_FINGERPRINT_DEFAULTS.get(class_type, {}).get(slot) == value:
                    continue
                triples.append((class_type, slot, value))
    return tuple(sorted(triples))
