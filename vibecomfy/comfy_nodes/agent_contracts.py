from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.security.agent_generated_loader import AgentGeneratedLoadError

DEFAULT_GATE_NAMES: tuple[str, ...] = (
    "python_load_ok",
    "ir_validate_ok",
    "ui_emit_ok",
    "ui_fidelity_ok",
    "ui_load_safe_ok",
    "queue_validate_ok",
    "state_match_ok",
)

CANVAS_APPLY_GATE_NAMES: tuple[str, ...] = (
    "python_load_ok",
    "ir_validate_ok",
    "ui_emit_ok",
    "ui_fidelity_ok",
    "ui_load_safe_ok",
    "state_match_ok",
)


class FailureKind(str, Enum):
    SYNTAX_ERROR = "SyntaxError"
    AST_SCAN_FAILURE = "ASTScanFailure"
    OVERSIZED_PAYLOAD = "OversizedPayload"
    MALFORMED_MODEL_JSON = "MalformedModelJSON"
    MISSING_REQUIRED_FIELD = "MissingRequiredField"
    PROVIDER_ERROR = "ProviderError"
    AUTH_ERROR = "AuthError"
    TIMEOUT_ERROR = "TimeoutError"
    VALIDATION_ERROR = "ValidationError"
    UNSATISFIED_INPUT_ERROR = "UnsatisfiedInputError"
    REFUSED_EMIT = "RefusedEmit"
    EDITOR_AHEAD_CONFLICT = "EditorAheadConflict"
    STALE_STATE_MISMATCH = "StaleStateMismatch"
    UNSUPPORTED_NON_DAG = "UnsupportedNonDAG"
    SCHEMA_LESS_QUEUE_BLOCKER = "SchemaLessQueueBlocker"
    LOW_CONFIDENCE_QUEUE_BLOCKER = "LowConfidenceQueueBlocker"
    EDITOR_ONLY_NODE_QUEUE_BLOCKER = "EditorOnlyNodeQueueBlocker"
    AUDIT_WRITE_WARNING = "AuditWriteWarning"
    AUDIT_WRITE_FAILURE = "AuditWriteFailure"


SCAN_CODE_FAILURE_KIND: Mapping[str, FailureKind] = MappingProxyType(
    {
        "syntax_error": FailureKind.SYNTAX_ERROR,
        "source_too_large": FailureKind.OVERSIZED_PAYLOAD,
        "source_type": FailureKind.VALIDATION_ERROR,
        "forbidden_node": FailureKind.AST_SCAN_FAILURE,
        "forbidden_import": FailureKind.AST_SCAN_FAILURE,
        "forbidden_name": FailureKind.AST_SCAN_FAILURE,
        "forbidden_call": FailureKind.AST_SCAN_FAILURE,
        "dunder_access": FailureKind.AST_SCAN_FAILURE,
    }
)


@dataclass(frozen=True)
class FailureSpec:
    retryable: bool
    next_action: str
    graph_unchanged: bool
    user_facing_message: str


FAILURE_SPECS: Mapping[FailureKind, FailureSpec] = MappingProxyType(
    {
        FailureKind.SYNTAX_ERROR: FailureSpec(
            retryable=True,
            next_action="wait and retry; agent should fix syntax",
            graph_unchanged=True,
            user_facing_message=(
                "The generated Python has a syntax error and was not loaded. "
                "The graph is unchanged."
            ),
        ),
        FailureKind.AST_SCAN_FAILURE: FailureSpec(
            retryable=True,
            next_action="wait and retry; agent must remove forbidden constructs",
            graph_unchanged=True,
            user_facing_message=(
                "The generated Python uses a forbidden operation and was not loaded. "
                "The graph is unchanged."
            ),
        ),
        FailureKind.OVERSIZED_PAYLOAD: FailureSpec(
            retryable=False,
            next_action="reduce scope or split request",
            graph_unchanged=True,
            user_facing_message=(
                "The generated Python is too large to load safely and was rejected. "
                "The graph is unchanged."
            ),
        ),
        FailureKind.MALFORMED_MODEL_JSON: FailureSpec(
            retryable=True,
            next_action="wait and retry; model response did not parse as valid JSON",
            graph_unchanged=True,
            user_facing_message=(
                "The model response could not be parsed. The graph is unchanged."
            ),
        ),
        FailureKind.MISSING_REQUIRED_FIELD: FailureSpec(
            retryable=True,
            next_action="wait and retry; model response is incomplete",
            graph_unchanged=True,
            user_facing_message=(
                "The model response is incomplete. The graph is unchanged."
            ),
        ),
        FailureKind.PROVIDER_ERROR: FailureSpec(
            retryable=True,
            next_action="try again or switch route",
            graph_unchanged=True,
            user_facing_message=(
                "The model provider is temporarily unavailable. The graph is unchanged."
            ),
        ),
        FailureKind.AUTH_ERROR: FailureSpec(
            retryable=False,
            next_action="check credentials in Agent Settings",
            graph_unchanged=True,
            user_facing_message=(
                "The model provider rejected authentication. Check your credentials "
                "in Agent Settings."
            ),
        ),
        FailureKind.TIMEOUT_ERROR: FailureSpec(
            retryable=True,
            next_action="retry with the same request",
            graph_unchanged=True,
            user_facing_message=(
                "The model did not respond in time. The graph is unchanged."
            ),
        ),
        FailureKind.VALIDATION_ERROR: FailureSpec(
            retryable=True,
            next_action="agent should fix structural issues",
            graph_unchanged=True,
            user_facing_message=(
                "The edited workflow has validation errors and was not applied. "
                "See details."
            ),
        ),
        FailureKind.UNSATISFIED_INPUT_ERROR: FailureSpec(
            retryable=True,
            next_action="agent should restore or provide missing required inputs",
            graph_unchanged=True,
            user_facing_message=(
                "Some nodes are missing required inputs. The graph is unchanged."
            ),
        ),
        FailureKind.REFUSED_EMIT: FailureSpec(
            retryable=True,
            next_action="agent must avoid editing protected editor state",
            graph_unchanged=True,
            user_facing_message=(
                "The candidate graph would destroy editor state and was blocked. "
                "The graph is unchanged."
            ),
        ),
        FailureKind.EDITOR_AHEAD_CONFLICT: FailureSpec(
            retryable=False,
            next_action="user must choose keep editor changes or overwrite",
            graph_unchanged=True,
            user_facing_message=(
                "The editor has changes that conflict with the candidate. "
                "Choose keep or overwrite."
            ),
        ),
        FailureKind.STALE_STATE_MISMATCH: FailureSpec(
            retryable=False,
            next_action="resubmit from the current canvas",
            graph_unchanged=True,
            user_facing_message=(
                "The submitted graph no longer matches the current canvas. Resubmit."
            ),
        ),
        FailureKind.UNSUPPORTED_NON_DAG: FailureSpec(
            retryable=False,
            next_action="reformulate as a static graph edit",
            graph_unchanged=True,
            user_facing_message=(
                "This request requires custom code or control flow that is not yet "
                "supported. Try a static graph edit."
            ),
        ),
        FailureKind.SCHEMA_LESS_QUEUE_BLOCKER: FailureSpec(
            retryable=False,
            next_action="inspect candidate on canvas until schema is available",
            graph_unchanged=False,
            user_facing_message=(
                "Some node schemas are unavailable, so Queue is blocked. You can "
                "still inspect the graph."
            ),
        ),
        FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER: FailureSpec(
            retryable=False,
            next_action="inspect candidate on canvas until confidence improves",
            graph_unchanged=False,
            user_facing_message=(
                "Schema or provider confidence is too low for safe queueing. "
                "Canvas Apply may still be available."
            ),
        ),
        FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER: FailureSpec(
            retryable=False,
            next_action="remove or lower editor-only nodes before queueing",
            graph_unchanged=False,
            user_facing_message=(
                "Editor-only nodes are present and block Queue. You can inspect "
                "them on the canvas."
            ),
        ),
        FailureKind.AUDIT_WRITE_WARNING: FailureSpec(
            retryable=False,
            next_action="no action needed",
            graph_unchanged=False,
            user_facing_message=(
                "The audit file was written with warnings. All graph decisions are "
                "preserved."
            ),
        ),
        FailureKind.AUDIT_WRITE_FAILURE: FailureSpec(
            retryable=False,
            next_action="report issue; turn cannot complete without a verifiable audit artifact",
            graph_unchanged=True,
            user_facing_message=(
                "The audit file could not be written and the turn was aborted. "
                "The graph is unchanged."
            ),
        ),
    }
)


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_jsonish(v) for v in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw_jsonish(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(v) for v in value]
    return value


def _coerce_failure_kind(value: FailureKind | str) -> FailureKind:
    if isinstance(value, FailureKind):
        return value
    return FailureKind(value)


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    sha256: str | None = None
    byte_count: int | None = None
    preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "preview": self.preview,
        }


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool = False
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", _freeze_jsonish(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "evidence": _thaw_jsonish(self.evidence),
        }


@dataclass(frozen=True)
class StageResult:
    stage: str
    ok: bool
    blocking: bool
    duration_ms: int | None = None
    value: Any = None
    artifacts: tuple[ArtifactRef, ...] = ()
    issues: tuple[Any, ...] = ()
    gate_updates: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "gate_updates", MappingProxyType(dict(self.gate_updates)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "blocking": self.blocking,
            "duration_ms": self.duration_ms,
            "value": _thaw_jsonish(_freeze_jsonish(self.value)),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "issues": [_thaw_jsonish(_freeze_jsonish(issue)) for issue in self.issues],
            "gate_updates": dict(self.gate_updates),
        }


def _default_gate_results() -> dict[str, GateResult]:
    return {name: GateResult(name=name, ok=False) for name in DEFAULT_GATE_NAMES}


@dataclass
class TurnContext:
    session_id: str
    turn_id: str | None = None
    baseline_turn_id: str | None = None
    client_graph_hash: str | None = None
    idempotency_key: str | None = None
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    gate_results: dict[str, GateResult] = field(default_factory=_default_gate_results)

    def __post_init__(self) -> None:
        merged = _default_gate_results()
        for name, gate in self.gate_results.items():
            merged[name] = gate if isinstance(gate, GateResult) else GateResult(name=name, ok=bool(gate))
        self.gate_results = merged

    @property
    def canvas_apply_allowed(self) -> bool:
        return all(self.gate_results[name].ok for name in CANVAS_APPLY_GATE_NAMES)

    @property
    def apply_allowed(self) -> bool:
        return self.canvas_apply_allowed

    @property
    def queue_allowed(self) -> bool:
        return self.canvas_apply_allowed and self.gate_results["queue_validate_ok"].ok

    def set_gate(self, name: str, ok: bool, *, evidence: Mapping[str, Any] | None = None) -> None:
        if name not in self.gate_results:
            raise KeyError(f"Unknown gate {name!r}")
        self.gate_results[name] = GateResult(name=name, ok=ok, evidence=evidence or {})

    def record_stage(self, result: StageResult) -> StageResult:
        self.stage_results[result.stage] = result
        for name, ok in result.gate_updates.items():
            self.set_gate(name, ok)
        return result

    def gate_snapshot(self) -> dict[str, bool]:
        return {name: gate.ok for name, gate in self.gate_results.items()}


@dataclass(frozen=True)
class FailureEnvelope:
    kind: FailureKind
    stage: str
    retryable: bool
    next_action: str
    graph_unchanged: bool
    user_facing_message: str
    agent_failure_context: Mapping[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    turn_id: str | None = None
    baseline_turn_id: str | None = None
    canvas_apply_allowed: bool = False
    queue_allowed: bool = False
    audit_ref: ArtifactRef | None = None
    audit_error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agent_failure_context",
            _freeze_jsonish(self.agent_failure_context),
        )

    @property
    def ok(self) -> bool:
        return False

    @property
    def apply_allowed(self) -> bool:
        return self.canvas_apply_allowed

    @property
    def message(self) -> str:
        return self.user_facing_message

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "kind": self.kind.value,
            "stage": self.stage,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "baseline_turn_id": self.baseline_turn_id,
            "canvas_apply_allowed": self.canvas_apply_allowed,
            "apply_allowed": self.apply_allowed,
            "queue_allowed": self.queue_allowed,
            "graph_unchanged": self.graph_unchanged,
            "retryable": self.retryable,
            "next_action": self.next_action,
            "message": self.user_facing_message,
            "user_facing_message": self.user_facing_message,
            "agent_failure_context": _thaw_jsonish(self.agent_failure_context),
            "audit_ref": self.audit_ref.to_dict() if self.audit_ref is not None else None,
            "audit_error": self.audit_error,
        }
        if self.turn_id is None:
            payload.pop("turn_id")
        return payload


def _lookup_status_code(value: Any) -> int | None:
    if isinstance(value, Mapping):
        status = value.get("http_status") or value.get("status_code")
        return status if isinstance(status, int) else None
    response = getattr(value, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _scan_failure_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = {
            key: getattr(value, key)
            for key in ("code", "message", "line", "column", "phase")
            if hasattr(value, key)
        }
    return {key: item for key, item in payload.items() if item is not None}


def _scan_failure_from_issue(value: Any) -> dict[str, Any] | None:
    if isinstance(value, AgentGeneratedLoadError):
        failures = value.report.failures
        if failures:
            return _scan_failure_payload(failures[0])
        return None
    code = None
    if isinstance(value, Mapping):
        code = value.get("code")
    else:
        code = getattr(value, "code", None)
    if isinstance(code, str) and code in SCAN_CODE_FAILURE_KIND:
        return _scan_failure_payload(value)
    return None


def _context_ids(context: TurnContext | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(context, TurnContext):
        return {
            "session_id": context.session_id,
            "turn_id": context.turn_id,
            "baseline_turn_id": context.baseline_turn_id,
        }
    if isinstance(context, Mapping):
        return {
            "session_id": context.get("session_id"),
            "turn_id": context.get("turn_id"),
            "baseline_turn_id": context.get("baseline_turn_id"),
        }
    return {"session_id": None, "turn_id": None, "baseline_turn_id": None}


def classify_failure(
    stage: str,
    exc_or_issue: Any,
    context: TurnContext | Mapping[str, Any] | None = None,
) -> FailureEnvelope:
    scan_issue = _scan_failure_from_issue(exc_or_issue)
    if scan_issue is not None:
        kind = SCAN_CODE_FAILURE_KIND[scan_issue["code"]]
        failure_context = {
            "explanation": scan_issue.get("message", "scan failure"),
            "scan_code": scan_issue["code"],
        }
        for key in ("line", "column", "phase"):
            if key in scan_issue:
                failure_context[key] = scan_issue[key]
        return failure_envelope(kind, stage, context, agent_failure_context=failure_context)

    status_code = _lookup_status_code(exc_or_issue)
    if status_code in {401, 403}:
        return failure_envelope(
            FailureKind.AUTH_ERROR,
            stage,
            context,
            agent_failure_context={
                "explanation": str(exc_or_issue),
                "http_status": status_code,
            },
        )

    exc_name = type(exc_or_issue).__name__
    lower_message = str(exc_or_issue).lower()
    if exc_name == "RefusedEmit":
        return failure_envelope(
            FailureKind.REFUSED_EMIT,
            stage,
            context,
            agent_failure_context={
                "explanation": str(exc_or_issue),
                "refused_items": _thaw_jsonish(_freeze_jsonish(getattr(exc_or_issue, "diff", {}))),
            },
        )
    if exc_name == "EditorAheadError":
        return failure_envelope(
            FailureKind.EDITOR_AHEAD_CONFLICT,
            stage,
            context,
            agent_failure_context={
                "explanation": str(exc_or_issue),
                "conflicting_items": _thaw_jsonish(
                    _freeze_jsonish(getattr(exc_or_issue, "editor_only_uids", ()))
                ),
            },
        )
    if isinstance(exc_or_issue, TimeoutError) or "timeout" in exc_name.lower():
        return failure_envelope(
            FailureKind.TIMEOUT_ERROR,
            stage,
            context,
            agent_failure_context={"explanation": str(exc_or_issue)},
        )

    if stage == "agent_response":
        if exc_name == "AuthError":
            return failure_envelope(
                FailureKind.AUTH_ERROR,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        if exc_name == "MissingRequiredField":
            return failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        if exc_name == "MalformedModelJSON":
            return failure_envelope(
                FailureKind.MALFORMED_MODEL_JSON,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        if "missing" in lower_message and ("python" in lower_message or "message" in lower_message):
            return failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        if isinstance(exc_or_issue, (json.JSONDecodeError, TypeError, ValueError)):
            return failure_envelope(
                FailureKind.MALFORMED_MODEL_JSON,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        return failure_envelope(
            FailureKind.PROVIDER_ERROR,
            stage,
            context,
            agent_failure_context={
                "explanation": str(exc_or_issue),
                "http_status": status_code,
            },
        )

    if stage == "ingest":
        if "stale" in lower_message or "hash" in lower_message or "baseline" in lower_message:
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        if "non-dag" in lower_message or "control flow" in lower_message or "unsupported" in lower_message:
            return failure_envelope(
                FailureKind.UNSUPPORTED_NON_DAG,
                stage,
                context,
                agent_failure_context={"explanation": str(exc_or_issue)},
            )
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            stage,
            context,
            agent_failure_context={"explanation": str(exc_or_issue)},
        )

    if stage == "validate":
        kind = (
            FailureKind.UNSATISFIED_INPUT_ERROR
            if "missing input" in lower_message or "required input" in lower_message
            else FailureKind.VALIDATION_ERROR
        )
        return failure_envelope(
            kind,
            stage,
            context,
            agent_failure_context={"explanation": str(exc_or_issue)},
        )

    if stage == "queue_validate":
        if "schema" in lower_message:
            kind = FailureKind.SCHEMA_LESS_QUEUE_BLOCKER
        elif "editor-only" in lower_message or "editor only" in lower_message:
            kind = FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER
        else:
            kind = FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER
        return failure_envelope(
            kind,
            stage,
            context,
            agent_failure_context={"explanation": str(exc_or_issue)},
        )

    if stage == "audit":
        kind = (
            FailureKind.AUDIT_WRITE_WARNING
            if "warning" in lower_message
            else FailureKind.AUDIT_WRITE_FAILURE
        )
        return failure_envelope(
            kind,
            stage,
            context,
            agent_failure_context={"explanation": str(exc_or_issue)},
        )

    return failure_envelope(
        FailureKind.VALIDATION_ERROR,
        stage,
        context,
        agent_failure_context={"explanation": str(exc_or_issue)},
    )


def failure_envelope(
    kind: FailureKind | str,
    stage: str,
    context: TurnContext | Mapping[str, Any] | None = None,
    *,
    agent_failure_context: Mapping[str, Any] | None = None,
    audit_ref: ArtifactRef | None = None,
    audit_error: str | None = None,
    canvas_apply_allowed: bool | None = None,
    queue_allowed: bool | None = None,
) -> FailureEnvelope:
    failure_kind = _coerce_failure_kind(kind)
    spec = FAILURE_SPECS[failure_kind]
    ids = _context_ids(context)
    return FailureEnvelope(
        kind=failure_kind,
        stage=stage,
        retryable=spec.retryable,
        next_action=spec.next_action,
        graph_unchanged=spec.graph_unchanged,
        user_facing_message=spec.user_facing_message,
        agent_failure_context=agent_failure_context or {"explanation": spec.user_facing_message},
        session_id=ids["session_id"],
        turn_id=ids["turn_id"],
        baseline_turn_id=ids["baseline_turn_id"],
        canvas_apply_allowed=bool(canvas_apply_allowed) if canvas_apply_allowed is not None else False,
        queue_allowed=bool(queue_allowed) if queue_allowed is not None else False,
        audit_ref=audit_ref,
        audit_error=audit_error,
    )


def success_envelope(
    context: TurnContext,
    *,
    message: str,
    graph: dict[str, Any] | None = None,
    report: dict[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    audit_ref: ArtifactRef | None = None,
    version: int = 1,
) -> dict[str, Any]:
    return {
        "ok": True,
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "baseline_turn_id": context.baseline_turn_id,
        "canvas_apply_allowed": context.canvas_apply_allowed,
        "apply_allowed": context.apply_allowed,
        "queue_allowed": context.queue_allowed,
        "gates": context.gate_snapshot(),
        "message": message,
        "graph": graph,
        "report": report or {},
        "artifacts": dict(artifacts or {}),
        "audit_ref": audit_ref.to_dict() if audit_ref is not None else None,
        "version": version,
    }


__all__ = [
    "ArtifactRef",
    "CANVAS_APPLY_GATE_NAMES",
    "DEFAULT_GATE_NAMES",
    "FAILURE_SPECS",
    "FailureEnvelope",
    "FailureKind",
    "GateResult",
    "SCAN_CODE_FAILURE_KIND",
    "StageResult",
    "TurnContext",
    "classify_failure",
    "failure_envelope",
    "success_envelope",
]
