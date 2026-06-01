from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .agent_contracts import ArtifactRef, FailureEnvelope, StageResult, TurnContext

INLINE_LIMIT_BYTES = 4096
PREVIEW_LIMIT_CHARS = 512
REDACTED = "<REDACTED>"
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


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")


def write_json_artifact(path: Path, value: Any) -> ArtifactRef:
    redacted = redact_closed_set(value)
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
) -> ArtifactRef:
    audit_dir.mkdir(parents=True, exist_ok=True)
    redactions: set[str] = set()
    artifact_payload: dict[str, Any] = {}
    for name, artifact in sorted((artifacts or {}).items()):
        if isinstance(artifact, ArtifactRef):
            artifact_payload[name] = artifact.to_dict()
        elif isinstance(artifact, Path):
            artifact_payload[name] = artifact_entry(artifact)
        else:
            redacted = redact_closed_set(dict(artifact))
            redactions.update(redacted.categories)
            artifact_payload[name] = redacted.value

    response_ref = None
    if response is not None:
        redacted_response = redact_closed_set(dict(response))
        redactions.update(redacted_response.categories)
        response_path = audit_dir / "response.json"
        response_path.write_bytes(_json_bytes(redacted_response.value) + b"\n")
        response_ref = artifact_ref_for_path(response_path).to_dict()

    if isinstance(failure, FailureEnvelope):
        redacted_failure = redact_closed_set(failure.to_dict())
        redactions.update(redacted_failure.categories)
        failure_payload: dict[str, Any] | None = redacted_failure.value
    elif failure is not None:
        redacted_failure = redact_closed_set(dict(failure))
        redactions.update(redacted_failure.categories)
        failure_payload = redacted_failure.value
    else:
        failure_payload = None

    redacted_metadata = redact_closed_set(dict(metadata or {}))
    redactions.update(redacted_metadata.categories)
    audit_payload = {
        "schema_version": 1,
        "session_id": context.session_id if context is not None else None,
        "turn_id": context.turn_id if context is not None else None,
        "baseline_turn_id": context.baseline_turn_id if context is not None else None,
        "turn_state": turn_state,
        "created_at": _now(),
        "stage_results": _stage_results_to_dict(stage_results),
        "gates": _gates_to_dict(context),
        "failure": failure_payload,
        "artifacts": artifact_payload,
        "redactions": sorted(redactions),
        "response_ref": response_ref,
        "metadata": redacted_metadata.value,
    }
    audit_path = audit_dir / "audit.json"
    audit_path.write_bytes(_json_bytes(audit_payload) + b"\n")
    return artifact_ref_for_path(audit_path)


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
    "redact_closed_set",
    "write_allocation_failure_audit",
    "write_audit",
    "write_json_artifact",
    "write_text_artifact",
]
