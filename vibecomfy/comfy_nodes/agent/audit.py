from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import ArtifactRef, DiagnosticRecord, FailureEnvelope, StageResult, TurnContext

INLINE_LIMIT_BYTES = 4096
PREVIEW_LIMIT_CHARS = 512
REDACTED = "<REDACTED>"
@dataclass(frozen=True)
class AuditArtifactRef(ArtifactRef):
    """ArtifactRef returned by ``write_audit`` with an attached typed diagnostic record."""

    diagnostic_record: DiagnosticRecord | None = None


REDACTION_CATEGORIES = frozenset(
    {
        "api_key",
        "auth_header",
        "bearer_token",
        "credential_payload",
        "env_variable",
        "provider_secret",
    }
)

_CATEGORY_KEYS: dict[str, tuple[str, ...]] = {
    "api_key": ("api_key", "apikey", "deepseek_api_key", "openai_api_key"),
    "auth_header": ("authorization", "auth_header"),
    "bearer_token": ("bearer_token", "access_token"),
    "credential_payload": ("credentials", "credential", "credential_payload"),
    "env_variable": ("env", "env_variable", "environment"),
    "provider_secret": ("provider_secret", "secret", "token"),
}


@dataclass(frozen=True)
class RedactionResult:
    value: Any
    categories: tuple[str, ...]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _category_for_key(key: str) -> str | None:
    normalized = key.lower().replace("-", "_")
    for category, names in _CATEGORY_KEYS.items():
        if normalized in names or any(name in normalized for name in names):
            return category
    return None


def _looks_like_bearer(value: str) -> bool:
    return value.lower().startswith("bearer ")


def redact_closed_set(value: Any) -> RedactionResult:
    categories: set[str] = set()

    def _redact(item: Any, key_hint: str | None = None) -> Any:
        category = _category_for_key(key_hint or "") if key_hint else None
        if category is not None:
            categories.add(category)
            return REDACTED
        if isinstance(item, Mapping):
            return {str(key): _redact(child, str(key)) for key, child in item.items()}
        if isinstance(item, list):
            return [_redact(child) for child in item]
        if isinstance(item, tuple):
            return [_redact(child) for child in item]
        if isinstance(item, str) and _looks_like_bearer(item):
            categories.add("bearer_token")
            return REDACTED
        return item

    return RedactionResult(value=_redact(value), categories=tuple(sorted(categories)))


def _source_digest(source: str) -> dict[str, Any]:
    return {
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "byte_count": len(source.encode("utf-8")),
        "redacted": True,
    }


def _redact_runtime_source(item: Any) -> Any:
    if isinstance(item, Mapping):
        result = {str(key): _redact_runtime_source(child) for key, child in item.items()}
        class_type = result.get("class_type")
        inputs = result.get("inputs")
        if class_type == "vibecomfy.code" and isinstance(inputs, dict) and isinstance(inputs.get("source"), str):
            inputs["source"] = _source_digest(inputs["source"])
        properties = result.get("properties")
        if isinstance(properties, dict):
            _redact_runtime_properties(properties)
        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            _redact_runtime_source(metadata)
        ui = result.get("_ui")
        if isinstance(ui, dict):
            ui_properties = ui.get("properties")
            if isinstance(ui_properties, dict):
                _redact_runtime_properties(ui_properties)
        return result
    if isinstance(item, list):
        return [_redact_runtime_source(child) for child in item]
    if isinstance(item, tuple):
        return [_redact_runtime_source(child) for child in item]
    return item


def _redact_runtime_properties(properties: dict[str, Any]) -> None:
    vibecomfy = properties.get("vibecomfy")
    if not isinstance(vibecomfy, dict):
        return
    runtime = vibecomfy.get("runtime")
    intent = vibecomfy.get("intent")
    if not isinstance(runtime, dict) or runtime.get("runtime_backed") is not True:
        return
    if isinstance(intent, dict) and isinstance(intent.get("source"), str):
        intent["source"] = _source_digest(intent["source"])


def redact_audit_metadata(value: Any) -> RedactionResult:
    """Redact secret-like fields and runtime code source from persisted metadata."""

    return redact_closed_set(_redact_runtime_source(value))


def runtime_intent_metadata_from_api(api_dict: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return source-free runtime-backed intent metadata for audit/run records."""

    entries: list[dict[str, Any]] = []
    for node_id, node in sorted(api_dict.items(), key=lambda item: str(item[0])):
        if not isinstance(node, Mapping) or node.get("class_type") != "vibecomfy.code":
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping) or inputs.get("runtime_backed") is not True:
            continue
        source = inputs.get("source")
        source_hash = _source_digest(source) if isinstance(source, str) else None
        entries.append(
            {
                "node_id": str(node_id),
                "class_type": "vibecomfy.code",
                "vibecomfy_uid": inputs.get("vibecomfy_uid"),
                "kind": inputs.get("kind"),
                "runtime_backed": True,
                "runtime_contract_version": inputs.get("runtime_contract_version"),
                "execution_mode": inputs.get("execution_mode"),
                "policy_version": inputs.get("policy_version"),
                "io": _redact_runtime_source(inputs.get("io")),
                "source_hash": source_hash["sha256"] if source_hash else None,
                "source_byte_count": source_hash["byte_count"] if source_hash else None,
                "source_redacted": source_hash is not None,
                "resource_limits": {
                    "timeout_ms": inputs.get("timeout_ms"),
                    "max_source_bytes": inputs.get("max_source_bytes"),
                },
                "redaction": {
                    "policy": list(inputs.get("redaction_policy") or []),
                    "status": "source_hash_only" if source_hash else "no_source",
                },
            }
        )
    return entries


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")


def write_json_artifact(path: Path, value: Any) -> ArtifactRef:
    redacted = redact_audit_metadata(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(redacted.value) + b"\n")
    return artifact_ref_for_path(path)


def write_text_artifact(path: Path, text: str) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return artifact_ref_for_path(path)


def artifact_ref_for_path(path: Path, *, preview_chars: int = PREVIEW_LIMIT_CHARS) -> ArtifactRef:
    data = path.read_bytes()
    try:
        preview = data[:preview_chars].decode("utf-8", errors="replace")
    except OSError:
        preview = None
    return ArtifactRef(
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        byte_count=len(data),
        preview=preview,
    )


def artifact_entry(path: Path) -> dict[str, Any]:
    ref = artifact_ref_for_path(path)
    entry = ref.to_dict()
    if ref.byte_count is not None and ref.byte_count <= INLINE_LIMIT_BYTES:
        try:
            entry["inline"] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            try:
                entry["inline"] = path.read_text(encoding="utf-8")
            except OSError:
                pass
    return entry


def _stage_results_to_dict(stage_results: Mapping[str, StageResult] | None) -> list[dict[str, Any]]:
    if not stage_results:
        return []
    return [stage_results[name].to_dict() for name in sorted(stage_results)]


def _gates_to_dict(context: TurnContext | None) -> dict[str, bool]:
    return context.gate_snapshot() if context is not None else {}


def normalize_agent_edit_v2_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(value or {})

    # ── typed outcome.changes (FieldChange list) ──────────────────────────
    outcome_changes: list[dict[str, Any]] = []
    outcome = payload.get("outcome")
    if isinstance(outcome, Mapping):
        changes = outcome.get("changes")
        if isinstance(changes, list):
            outcome_changes = [
                {
                    "uid": str(change.get("uid", "")),
                    "field_path": str(change.get("field_path", "")),
                    "old": change.get("old"),
                    "new": change.get("new"),
                }
                for change in changes
                if isinstance(change, Mapping)
            ]

    # ── canonical envelope + audit split (with legacy bridge support) ─────
    delta_envelope = payload.get("delta_ops_envelope")
    legacy_delta_ops = payload.get("delta_ops")
    legacy_delta_ops_mapping = dict(legacy_delta_ops) if isinstance(legacy_delta_ops, Mapping) else {}
    audit_payload = payload.get("delta_audit")
    delta_audit_mapping = dict(audit_payload) if isinstance(audit_payload, Mapping) else legacy_delta_ops_mapping

    normalized_delta_envelope: dict[str, Any] | None = None
    if isinstance(delta_envelope, Mapping):
        raw_ops = delta_envelope.get("ops")
        normalized_delta_envelope = {
            "schema_version": str(delta_envelope.get("schema_version") or "2.0.0"),
            "ops": list(raw_ops) if isinstance(raw_ops, list) else [],
        }
    else:
        raw_ops = legacy_delta_ops_mapping.get("ops")
        if isinstance(raw_ops, list):
            normalized_delta_envelope = {
                "schema_version": "2.0.0",
                "ops": list(raw_ops),
            }

    diagnostics = delta_audit_mapping.get("diagnostics")
    automatic_link_removals = delta_audit_mapping.get("automatic_link_removals")
    re_stitches = delta_audit_mapping.get("re_stitches")
    guard_result = delta_audit_mapping.get("guard_result")
    normalize = delta_audit_mapping.get("normalize")

    normalized_delta_audit = {
        "diagnostics": list(diagnostics) if isinstance(diagnostics, list) else [],
        "automatic_link_removals": (
            list(automatic_link_removals) if isinstance(automatic_link_removals, list) else []
        ),
        "re_stitches": list(re_stitches) if isinstance(re_stitches, list) else [],
        "guard_result": dict(guard_result) if isinstance(guard_result, Mapping) else {"ok": True, "diagnostics": []},
        "normalize": (
            {
                "fallback_used": bool(normalize.get("fallback_used")),
                "allow_list_used": bool(normalize.get("allow_list_used")),
            }
            if isinstance(normalize, Mapping)
            else {"fallback_used": False, "allow_list_used": False}
        ),
    }
    op_count = payload.get("op_count")
    if not isinstance(op_count, int):
        op_count = len(normalized_delta_envelope["ops"]) if normalized_delta_envelope is not None else 0

    result: dict[str, Any] = {
        "enabled": bool(payload.get("enabled")),
        "op_count": op_count,
        "delta_ops_envelope": normalized_delta_envelope,
        "delta_audit": normalized_delta_audit,
    }

    # ── surface typed outcome.changes when present ────────────────────────
    if outcome_changes:
        result["outcome_changes"] = outcome_changes

    # ── skip cleanly when delta data is absent ────────────────────────────
    if normalized_delta_envelope is None and not outcome_changes:
        result.pop("delta_ops_envelope", None)
        result.pop("delta_audit", None)
        result.pop("op_count", None)

    return result


def write_audit(
    audit_dir: Path,
    *,
    context: TurnContext | None,
    turn_state: str | None = None,
    stage_results: Mapping[str, StageResult] | None = None,
    failure: FailureEnvelope | Mapping[str, Any] | None = None,
    response: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Path | ArtifactRef | Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AuditArtifactRef:
    audit_dir.mkdir(parents=True, exist_ok=True)
    redactions: set[str] = set()
    artifact_payload: dict[str, Any] = {}
    for name, artifact in sorted((artifacts or {}).items()):
        if isinstance(artifact, ArtifactRef):
            artifact_payload[name] = artifact.to_dict()
        elif isinstance(artifact, Path):
            artifact_payload[name] = artifact_entry(artifact)
        else:
            redacted = redact_audit_metadata(dict(artifact))
            redactions.update(redacted.categories)
            artifact_payload[name] = redacted.value

    response_ref = None
    if response is not None:
        redacted_response = redact_audit_metadata(dict(response))
        redactions.update(redacted_response.categories)
        response_path = audit_dir / "response.json"
        response_path.write_bytes(_json_bytes(redacted_response.value) + b"\n")
        response_ref = artifact_ref_for_path(response_path).to_dict()

    if isinstance(failure, FailureEnvelope):
        redacted_failure = redact_audit_metadata(failure.to_dict())
        redactions.update(redacted_failure.categories)
        failure_payload: dict[str, Any] | None = redacted_failure.value
    elif failure is not None:
        redacted_failure = redact_audit_metadata(dict(failure))
        redactions.update(redacted_failure.categories)
        failure_payload = redacted_failure.value
    else:
        failure_payload = None

    redacted_metadata = redact_audit_metadata(dict(metadata or {}))
    redactions.update(redacted_metadata.categories)
    if isinstance(redacted_metadata.value, dict):
        agent_edit_v2 = redacted_metadata.value.get("agent_edit_v2")
        if isinstance(agent_edit_v2, Mapping):
            redacted_metadata.value["agent_edit_v2"] = normalize_agent_edit_v2_metadata(agent_edit_v2)
    gates = _gates_to_dict(context)
    audit_payload = {
        "schema_version": 1,
        "session_id": context.session_id if context is not None else None,
        "turn_id": context.turn_id if context is not None else None,
        "baseline_turn_id": context.baseline_turn_id if context is not None else None,
        "turn_state": turn_state,
        "created_at": _now(),
        "stage_results": _stage_results_to_dict(stage_results),
        "gates": gates,
        "failure": failure_payload,
        "artifacts": artifact_payload,
        "redactions": sorted(redactions),
        "response_ref": response_ref,
        "metadata": redacted_metadata.value,
    }
    audit_path = audit_dir / "audit.json"
    audit_path.write_bytes(_json_bytes(audit_payload) + b"\n")
    audit_ref = artifact_ref_for_path(audit_path)

    response_dict = dict(response) if isinstance(response, Mapping) else {}
    failure_kind = None
    if isinstance(failure, FailureEnvelope):
        failure_kind = failure.kind.value
    elif isinstance(failure, Mapping):
        failure_kind = failure.get("kind") or failure.get("failure_kind")
    graph = response_dict.get("graph")
    if not isinstance(graph, Mapping):
        candidate = response_dict.get("candidate")
        graph = candidate.get("graph") if isinstance(candidate, Mapping) else None
    nodes = graph.get("nodes") if isinstance(graph, Mapping) else None
    outcome = response_dict.get("outcome")
    diagnostic = DiagnosticRecord(
        session_id=audit_payload["session_id"] or "",
        turn_id=audit_payload["turn_id"] or "",
        path=str(audit_path),
        mtime=audit_path.stat().st_mtime,
        baseline_turn_id=audit_payload["baseline_turn_id"],
        ok=response_dict.get("ok") if response_dict else (False if failure is not None else None),
        kind=response_dict.get("kind") if response_dict else failure_kind,
        outcome=str(outcome.get("kind")) if isinstance(outcome, Mapping) and outcome.get("kind") is not None else None,
        lifecycle=turn_state,
        fidelity_ok=gates.get("ui_fidelity_ok"),
        state_match_ok=gates.get("state_match_ok"),
        queue_validate_ok=gates.get("queue_validate_ok"),
        canvas_apply_allowed=response_dict.get("canvas_apply_allowed"),
        queue_allowed=response_dict.get("queue_allowed"),
        candidate_nodes=len(nodes) if isinstance(nodes, list) else None,
        task=response_dict.get("task") or response_dict.get("user_facing_message"),
        route=response_dict.get("route"),
        protocol=None,
        summary=response_dict.get("done_summary")
        or response_dict.get("message")
        or response_dict.get("user_facing_message"),
        is_baseline=False,
        accepted_at=None,
        live_token=None,
    )
    return AuditArtifactRef(
        path=audit_ref.path,
        sha256=audit_ref.sha256,
        byte_count=audit_ref.byte_count,
        preview=audit_ref.preview,
        diagnostic_record=diagnostic,
    )


def write_allocation_failure_audit(
    session_dir: Path,
    *,
    session_id: str,
    failure: FailureEnvelope | Mapping[str, Any],
    request: Mapping[str, Any] | None = None,
) -> ArtifactRef:
    digest = hashlib.sha256(_json_bytes(request or failure.to_dict() if isinstance(failure, FailureEnvelope) else failure)).hexdigest()[:12]
    audit_dir = session_dir / "_allocation_failures" / f"{int(time.time())}-{digest}"
    context = TurnContext(session_id=session_id)
    artifacts: dict[str, Mapping[str, Any]] = {}
    if request is not None:
        redacted_request = redact_closed_set(dict(request))
        artifacts["request"] = redacted_request.value
    return write_audit(
        audit_dir,
        context=context,
        turn_state=None,
        failure=failure,
        artifacts=artifacts,
    )


__all__ = [
    "INLINE_LIMIT_BYTES",
    "PREVIEW_LIMIT_CHARS",
    "REDACTED",
    "REDACTION_CATEGORIES",
    "RedactionResult",
    "artifact_entry",
    "artifact_ref_for_path",
    "AuditArtifactRef",
    "DiagnosticRecord",
    "normalize_agent_edit_v2_metadata",
    "redact_closed_set",
    "redact_audit_metadata",
    "runtime_intent_metadata_from_api",
    "write_allocation_failure_audit",
    "write_audit",
    "write_json_artifact",
    "write_text_artifact",
]
