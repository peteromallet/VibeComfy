from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.porting.edit_types import FieldChange
from vibecomfy.security.agent_generated_loader import AgentGeneratedLoadError

DEFAULT_GATE_NAMES: tuple[str, ...] = (
    "python_load_ok",
    "lower_ok",
    "ir_validate_ok",
    "ui_emit_ok",
    "ui_fidelity_ok",
    "ui_load_safe_ok",
    "queue_validate_ok",
    "state_match_ok",
)

AGENT_EDIT_TURN_CONTRACT_VERSION = "agent_edit_turn_v2"

CANVAS_APPLY_GATE_NAMES: tuple[str, ...] = (
    "python_load_ok",
    "ir_validate_ok",
    "ui_emit_ok",
    "ui_fidelity_ok",
    "ui_load_safe_ok",
    "state_match_ok",
)

APPLY_ELIGIBILITY_REASONS: tuple[str, ...] = (
    "applyable",
    "no_candidate",
    "not_latest",
    "superseded",
    "server_blocked",
    "stale_canvas",
    "queue_blocked_warning",
)

TURN_OUTCOME_KINDS: tuple[str, ...] = (
    "edit",
    "clarify",
    "edit+clarify",
    "failure",
    "noop",
    "budget",
)

PUBLIC_OUTCOME_KINDS: tuple[str, ...] = (
    "candidate",
    "noop",
    "clarify",
    "error",
)

# Canonical snake_case field list for rebaseline-recovery objects.
# Sourced from the JS lifecycle module's _normalizeRebaselineRecovery keys
# (agent_edit_lifecycle.js L1369–1394, snake_case) and cross-checked against
# _stale_rebaseline_recovery_issue (agent_edit.py) and
# _promote_accept_rebaseline_recovery (routes.py).
REBASELINE_RECOVERY_FIELDS: tuple[str, ...] = (
    "action",
    "endpoint",
    "reason",
    "last_known_baseline_graph_hash",
    "submit_graph_hash",
    "submit_structural_graph_hash",
    "client_graph_hash",
    "client_structural_graph_hash",
)

# Maps internal TurnOutcome kinds to their canonical public outcome kind.
# Sourced from public_outcome_from_turn_outcome (this module, L885–925) and
# cross-checked against the JS INTERNAL_OUTCOME_KIND_MAP
# (agent_edit_response_contract.js L8–11).
# "budget" is context-dependent (candidate vs noop) — not in this static map.
INTERNAL_TO_PUBLIC_OUTCOME: Mapping[str, str] = MappingProxyType({
    "edit": "candidate",
    "edit+clarify": "candidate",
    "clarify": "clarify",
    "noop": "noop",
    "failure": "error",
})

# Well-known keys that, when present on a response object, signal a failure.
# Sourced from FAILURE_HINT_KEYS in agent_edit_response_contract.js L13–20.
FAILURE_HINT_KEYS: tuple[str, ...] = (
    "agent_failure_context",
    "failureKind",
    "failure_kind",
    "nextAction",
    "next_action",
    "retryable",
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
    LOWERING_FAILURE = "LoweringFailure"
    SCHEMA_LESS_QUEUE_BLOCKER = "SchemaLessQueueBlocker"
    LOW_CONFIDENCE_QUEUE_BLOCKER = "LowConfidenceQueueBlocker"
    EDITOR_ONLY_NODE_QUEUE_BLOCKER = "EditorOnlyNodeQueueBlocker"
    AUDIT_WRITE_WARNING = "AuditWriteWarning"
    AUDIT_WRITE_FAILURE = "AuditWriteFailure"
    BATCH_BUDGET_EXHAUSTED = "BatchBudgetExhausted"
    CLARIFICATION_REQUIRED = "ClarificationRequired"
    MODEL_MISTAKE = "ModelMistake"
    UNREPRESENTABLE = "Unrepresentable"
    SCHEMA_GAP = "SchemaGap"


@dataclass(frozen=True)
class ApplyEligibility:
    applyable: bool
    reason: str
    message: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason not in APPLY_ELIGIBILITY_REASONS:
            raise ValueError(f"Unknown Apply eligibility reason {self.reason!r}")
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "applyable": self.applyable,
            "reason": self.reason,
            "message": self.message,
            "warnings": list(self.warnings),
        }


def apply_eligibility_payload(
    eligibility: ApplyEligibility,
    *,
    canvas_apply_allowed: bool,
    queue_allowed: bool,
) -> dict[str, Any]:
    eligibility_payload = eligibility.to_dict()
    return {
        "canvas_apply_allowed": bool(canvas_apply_allowed),
        "apply_allowed": eligibility.applyable,
        "queue_allowed": bool(queue_allowed),
        "eligibility": eligibility_payload,
        "apply_eligibility": eligibility_payload,
    }


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
        FailureKind.LOWERING_FAILURE: FailureSpec(
            retryable=True,
            next_action="agent should simplify or fix the loop before lowering",
            graph_unchanged=True,
            user_facing_message=(
                "The edited workflow could not be lowered into a static graph. "
                "The graph is unchanged."
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
                "Editor-only nodes, including VibeComfy intent nodes, are present "
                "and block Queue. You can inspect them on the canvas."
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
        FailureKind.BATCH_BUDGET_EXHAUSTED: FailureSpec(
            retryable=False,
            next_action="manual intervention or resubmit with narrower scope",
            graph_unchanged=True,
            user_facing_message=(
                "The agent used its budget of batch edit turns without completing "
                "the task. Try a narrower scope or manual edits."
            ),
        ),
        FailureKind.CLARIFICATION_REQUIRED: FailureSpec(
            retryable=False,
            next_action="answer the agent's question and resubmit",
            graph_unchanged=True,
            user_facing_message=(
                "The agent needs clarification before it can continue."
            ),
        ),
        FailureKind.MODEL_MISTAKE: FailureSpec(
            retryable=True,
            next_action="retry or restate the request more concretely",
            graph_unchanged=True,
            user_facing_message=(
                "The agent exhausted its batch budget on fixable edit mistakes. "
                "The graph is unchanged."
            ),
        ),
        FailureKind.UNREPRESENTABLE: FailureSpec(
            retryable=False,
            next_action="reformulate the request as a supported static graph edit",
            graph_unchanged=True,
            user_facing_message=(
                "The request could not be represented in the supported edit surface. "
                "The graph is unchanged."
            ),
        ),
        FailureKind.SCHEMA_GAP: FailureSpec(
            retryable=False,
            next_action="add the missing schema coverage or inspect the graph manually",
            graph_unchanged=True,
            user_facing_message=(
                "The agent exhausted its budget because required schema information is missing. "
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
        return self.apply_eligibility.applyable

    @property
    def queue_allowed(self) -> bool:
        return self.canvas_apply_allowed and self.gate_results["queue_validate_ok"].ok

    @property
    def apply_eligibility(self) -> ApplyEligibility:
        return derive_apply_eligibility(self)

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


def derive_apply_eligibility(
    context: TurnContext,
    *,
    has_candidate: bool = True,
    is_latest_candidate: bool = True,
    candidate_state: str | None = "candidate",
    live_structural_graph_hash: str | None = None,
    submit_structural_graph_hash: str | None = None,
) -> ApplyEligibility:
    if not has_candidate:
        return ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message="No candidate is available to apply.",
        )
    if not is_latest_candidate:
        return ApplyEligibility(
            applyable=False,
            reason="not_latest",
            message="Only the latest candidate can be applied.",
        )
    if candidate_state in {"unknown", "rejected", "accepted", "superseded"}:
        return ApplyEligibility(
            applyable=False,
            reason="superseded",
            message="This candidate has been superseded.",
        )
    if (
        isinstance(live_structural_graph_hash, str)
        and isinstance(submit_structural_graph_hash, str)
        and live_structural_graph_hash != submit_structural_graph_hash
    ):
        return ApplyEligibility(
            applyable=False,
            reason="stale_canvas",
            message="The live canvas no longer matches the submitted candidate baseline.",
        )
    if not context.canvas_apply_allowed:
        return ApplyEligibility(
            applyable=False,
            reason="server_blocked",
            message="Server validation gates blocked Apply.",
        )
    if not context.queue_allowed:
        return ApplyEligibility(
            applyable=True,
            reason="queue_blocked_warning",
            message="Apply is allowed, but Queue remains blocked for this candidate.",
            warnings=("queue_blocked",),
        )
    return ApplyEligibility(
        applyable=True,
        reason="applyable",
        message="Apply is allowed.",
    )


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
        return self.apply_eligibility.applyable

    @property
    def apply_eligibility(self) -> ApplyEligibility:
        if not self.canvas_apply_allowed:
            return ApplyEligibility(
                applyable=False,
                reason="server_blocked",
                message="Server validation gates blocked Apply.",
            )
        if not self.queue_allowed:
            return ApplyEligibility(
                applyable=True,
                reason="queue_blocked_warning",
                message="Apply is allowed, but Queue remains blocked for this candidate.",
                warnings=("queue_blocked",),
            )
        return ApplyEligibility(
            applyable=True,
            reason="applyable",
            message="Apply is allowed.",
        )

    @property
    def message(self) -> str:
        return self.user_facing_message

    def to_dict(self) -> dict[str, Any]:
        eligibility = self.apply_eligibility
        payload: dict[str, Any] = {
            "ok": False,
            "kind": self.kind.value,
            "stage": self.stage,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "baseline_turn_id": self.baseline_turn_id,
            "graph_unchanged": self.graph_unchanged,
            "retryable": self.retryable,
            "next_action": self.next_action,
            "message": self.user_facing_message,
            "user_facing_message": self.user_facing_message,
            "agent_failure_context": _thaw_jsonish(self.agent_failure_context),
            "audit_ref": self.audit_ref.to_dict() if self.audit_ref is not None else None,
            "audit_error": self.audit_error,
        }
        payload.update(
            apply_eligibility_payload(
                eligibility,
                canvas_apply_allowed=self.canvas_apply_allowed,
                queue_allowed=self.queue_allowed,
            )
        )
        payload["outcome"] = failure_outcome_payload(self)
        recovery = _extract_rebaseline_recovery(payload)
        if recovery is not None:
            payload["rebaseline_recovery"] = recovery
        if self.turn_id is None:
            payload.pop("turn_id")
        return payload


@dataclass(frozen=True)
class TurnOutcome:
    kind: str
    changes: tuple[FieldChange, ...] = ()
    question: str | None = None
    failure_kind: FailureKind | None = None
    stage: str | None = None
    retryable: bool | None = None
    next_action: str | None = None
    graph_unchanged: bool | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in TURN_OUTCOME_KINDS:
            raise ValueError(f"Unknown TurnOutcome kind {self.kind!r}")
        object.__setattr__(self, "changes", tuple(self.changes))
        if self.failure_kind is not None:
            object.__setattr__(self, "failure_kind", _coerce_failure_kind(self.failure_kind))
        if self.kind == "failure":
            required = {
                "failure_kind": self.failure_kind,
                "stage": self.stage,
                "retryable": self.retryable,
                "next_action": self.next_action,
                "graph_unchanged": self.graph_unchanged,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(
                    "Failure TurnOutcome requires "
                    + ", ".join(sorted(missing))
                )
        else:
            failure_fields = (
                self.failure_kind,
                self.stage,
                self.retryable,
                self.next_action,
                self.graph_unchanged,
            )
            if any(value is not None for value in failure_fields):
                raise ValueError(
                    "Only failure TurnOutcome values may carry failure metadata"
                )
        if self.kind not in {"edit", "edit+clarify"} and self.changes:
            raise ValueError(
                "Only edit TurnOutcome values may carry field changes"
            )

    @classmethod
    def edit(cls, *, changes: tuple[FieldChange, ...] = ()) -> "TurnOutcome":
        return cls(kind="edit", changes=changes)

    @classmethod
    def clarify(cls, *, question: str | None = None) -> "TurnOutcome":
        return cls(kind="clarify", question=question)

    @classmethod
    def edit_and_clarify(
        cls,
        *,
        changes: tuple[FieldChange, ...] = (),
        question: str | None = None,
    ) -> "TurnOutcome":
        return cls(kind="edit+clarify", changes=changes, question=question)

    @classmethod
    def noop(cls, *, reason: str | None = None) -> "TurnOutcome":
        return cls(kind="noop", reason=reason)

    @classmethod
    def budget(cls, *, reason: str | None = None) -> "TurnOutcome":
        return cls(kind="budget", reason=reason)

    @classmethod
    def from_failure(cls, failure: FailureEnvelope) -> "TurnOutcome":
        return cls(
            kind="failure",
            failure_kind=failure.kind,
            stage=failure.stage,
            retryable=failure.retryable,
            next_action=failure.next_action,
            graph_unchanged=failure.graph_unchanged,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind}
        if self.kind in {"edit", "edit+clarify"}:
            payload["changes"] = [change.to_dict() for change in self.changes]
        if self.kind in {"clarify", "edit+clarify"} and self.question is not None:
            payload["question"] = self.question
        if self.kind == "failure":
            payload.update(
                {
                    "failure_kind": self.failure_kind.value,
                    "stage": self.stage,
                    "retryable": self.retryable,
                    "next_action": self.next_action,
                    "graph_unchanged": self.graph_unchanged,
                }
            )
        if self.kind in {"noop", "budget"} and self.reason is not None:
            payload["reason"] = self.reason
        return payload


def _response_has_candidate_payload(response: Mapping[str, Any] | None) -> bool:
    if not isinstance(response, Mapping):
        return False
    candidate = response.get("candidate")
    graph = response.get("graph")
    return isinstance(candidate, Mapping) or isinstance(graph, Mapping)


def _clarification_payload(question: Any) -> dict[str, Any]:
    if not isinstance(question, str):
        return {}
    text = question.strip()
    if not text:
        return {}
    return {
        "question": text,
        "clarification": {"message": text},
    }


def _extract_rebaseline_recovery(response: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    top_level = response.get("rebaseline_recovery")
    if isinstance(top_level, Mapping):
        return dict(top_level)
    contexts: list[Any] = [response.get("agent_failure_context")]
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        contexts.append(outcome.get("agent_failure_context"))
    debug = response.get("debug")
    if isinstance(debug, Mapping):
        failure_debug = debug.get("failure")
        if isinstance(failure_debug, Mapping):
            contexts.append(failure_debug.get("agent_failure_context"))
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        issues = context.get("issues")
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            recovery = issue.get("rebaseline_recovery")
            if isinstance(recovery, Mapping):
                return dict(recovery)
    return None


def _public_error_outcome_from_response(
    response: Mapping[str, Any],
    *,
    default_stage: str | None = None,
) -> dict[str, Any]:
    failure_kind = response.get("failure_kind")
    if not isinstance(failure_kind, str):
        kind_value = response.get("kind")
        if isinstance(kind_value, str) and kind_value in {kind.value for kind in FailureKind}:
            failure_kind = kind_value
    payload: dict[str, Any] = {
        "kind": "error",
        "failure_kind": failure_kind,
        "stage": response.get("stage") if isinstance(response.get("stage"), str) else default_stage,
        "retryable": response.get("retryable") if isinstance(response.get("retryable"), bool) else None,
        "next_action": response.get("next_action") if isinstance(response.get("next_action"), str) else None,
        "graph_unchanged": response.get("graph_unchanged") if isinstance(response.get("graph_unchanged"), bool) else None,
    }
    failure_context = response.get("agent_failure_context")
    if isinstance(failure_context, Mapping):
        payload["agent_failure_context"] = _thaw_jsonish(_freeze_jsonish(failure_context))
    recovery = _extract_rebaseline_recovery(response)
    if recovery is not None:
        payload["rebaseline_recovery"] = recovery
    return {key: value for key, value in payload.items() if value is not None}


def _failure_response_contract_fields(failure: FailureEnvelope) -> dict[str, Any]:
    payload = {
        "kind": failure.kind.value,
        "stage": failure.stage,
        "retryable": failure.retryable,
        "next_action": failure.next_action,
        "graph_unchanged": failure.graph_unchanged,
        "agent_failure_context": _thaw_jsonish(failure.agent_failure_context),
    }
    recovery = _extract_rebaseline_recovery(payload)
    if recovery is not None:
        payload["rebaseline_recovery"] = recovery
    return payload


def public_outcome_from_turn_outcome(
    internal_outcome: TurnOutcome | Mapping[str, Any],
    *,
    response: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    is_internal_turn_outcome = isinstance(internal_outcome, TurnOutcome)
    outcome = internal_outcome.to_dict() if is_internal_turn_outcome else dict(internal_outcome)
    kind = outcome.get("kind")
    if not isinstance(kind, str):
        raise ValueError("Turn outcome is missing a string kind.")
    if kind in PUBLIC_OUTCOME_KINDS and not is_internal_turn_outcome:
        public = dict(outcome)
        recovery = _extract_rebaseline_recovery(response)
        if public["kind"] == "error" and recovery is not None and "rebaseline_recovery" not in public:
            public["rebaseline_recovery"] = recovery
        return public
    if kind == "edit":
        return {
            "kind": "candidate",
            "changes": list(outcome.get("changes", [])),
        }
    if kind == "edit+clarify":
        public = {
            "kind": "candidate",
            "changes": list(outcome.get("changes", [])),
        }
        public.update(_clarification_payload(outcome.get("question")))
        return public
    if kind == "clarify":
        public = {"kind": "clarify"}
        public.update(_clarification_payload(outcome.get("question")))
        return public
    if kind == "noop":
        public = {"kind": "noop"}
        if isinstance(outcome.get("reason"), str) and outcome["reason"].strip():
            public["reason"] = outcome["reason"].strip()
        return public
    if kind == "budget":
        public_kind = "candidate" if _response_has_candidate_payload(response) else "noop"
        public = {
            "kind": public_kind,
            "budget_exhausted": True,
        }
        if isinstance(outcome.get("reason"), str) and outcome["reason"].strip():
            public["reason"] = outcome["reason"].strip()
        if public_kind == "candidate":
            public["changes"] = list(outcome.get("changes", []))
        return public
    if kind == "failure":
        return _public_error_outcome_from_response(
            {
                **outcome,
                "agent_failure_context": response.get("agent_failure_context") if isinstance(response, Mapping) else None,
                "rebaseline_recovery": _extract_rebaseline_recovery(response),
            },
            default_stage=outcome.get("stage") if isinstance(outcome.get("stage"), str) else None,
        )
    raise ValueError(f"Unknown TurnOutcome kind {kind!r}")


def failure_outcome_payload(failure: FailureEnvelope) -> dict[str, Any]:
    return public_outcome_from_turn_outcome(
        TurnOutcome.from_failure(failure),
        response=_failure_response_contract_fields(failure),
    )


def product_failure_envelope_fields(failure: FailureEnvelope) -> dict[str, Any]:
    message = failure.message.strip() if failure.message.strip() else failure.user_facing_message
    eligibility = failure.apply_eligibility
    internal_outcome = TurnOutcome.from_failure(failure).to_dict()
    envelope = turn_envelope(
        message=message,
        outcome=failure_outcome_payload(failure),
        candidate=None,
        eligibility=eligibility,
        audit_ref=failure.audit_ref,
        debug={
            "failure": {
                "kind": failure.kind.value,
                "stage": failure.stage,
                "agent_failure_context": _thaw_jsonish(failure.agent_failure_context),
                "audit_error": failure.audit_error,
            }
        },
    )
    envelope["internal_outcome"] = internal_outcome
    return envelope


def turn_envelope(
    *,
    message: str,
    outcome: TurnOutcome | Mapping[str, Any],
    candidate: Mapping[str, Any] | None,
    eligibility: ApplyEligibility | Mapping[str, Any],
    audit_ref: ArtifactRef | Mapping[str, Any] | None = None,
    debug: Mapping[str, Any] | None = None,
    contract_version: str = AGENT_EDIT_TURN_CONTRACT_VERSION,
) -> dict[str, Any]:
    text = message.strip()
    outcome_payload = outcome.to_dict() if isinstance(outcome, TurnOutcome) else dict(outcome)
    if not text:
        text = "The agent edit turn completed."
    if isinstance(eligibility, ApplyEligibility):
        eligibility_payload = eligibility.to_dict()
    else:
        eligibility_payload = dict(eligibility)
    if isinstance(audit_ref, ArtifactRef):
        audit_payload = audit_ref.to_dict()
    elif isinstance(audit_ref, Mapping):
        audit_payload = dict(audit_ref)
    else:
        audit_payload = None
    return {
        "contract_version": contract_version,
        "message": text,
        "outcome": outcome_payload,
        "candidate": dict(candidate) if candidate is not None else None,
        "eligibility": eligibility_payload,
        "audit_ref": audit_payload,
        "debug": _thaw_jsonish(_freeze_jsonish(debug or {})),
    }


def ensure_agent_edit_response_contract(
    response: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    payload = dict(response)
    raw_outcome = payload.get("outcome")
    if isinstance(raw_outcome, Mapping) or isinstance(raw_outcome, TurnOutcome):
        outcome = public_outcome_from_turn_outcome(raw_outcome, response=payload)
    elif payload.get("ok") is False or any(
        key in payload
        for key in ("agent_failure_context", "retryable", "next_action", "failure_kind")
    ):
        outcome = _public_error_outcome_from_response(payload, default_stage=stage)
    else:
        raise ValueError(f"Agent edit response for {stage!r} is missing outcome.")
    kind = outcome.get("kind")
    if kind not in PUBLIC_OUTCOME_KINDS:
        raise ValueError(
            f"Agent edit response for {stage!r} has invalid public outcome kind {kind!r}."
        )
    payload["outcome"] = outcome
    if outcome["kind"] == "error":
        recovery = _extract_rebaseline_recovery(payload)
        if recovery is not None:
            payload["rebaseline_recovery"] = recovery
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

    if stage == "lower":
        return failure_envelope(
            FailureKind.LOWERING_FAILURE,
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
    apply_eligibility: ApplyEligibility | None = None,
    canvas_apply_allowed: bool | None = None,
    queue_allowed: bool | None = None,
    version: int = 1,
) -> dict[str, Any]:
    eligibility = apply_eligibility or context.apply_eligibility
    canvas_allowed = (
        context.canvas_apply_allowed
        if canvas_apply_allowed is None
        else bool(canvas_apply_allowed)
    )
    queue_ok = context.queue_allowed if queue_allowed is None else bool(queue_allowed)
    payload = {
        "ok": True,
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "baseline_turn_id": context.baseline_turn_id,
        "gates": context.gate_snapshot(),
        "message": message,
        "graph": graph,
        "report": report or {},
        "artifacts": dict(artifacts or {}),
        "audit_ref": audit_ref.to_dict() if audit_ref is not None else None,
        "version": version,
    }
    payload.update(
        apply_eligibility_payload(
            eligibility,
            canvas_apply_allowed=canvas_allowed,
            queue_allowed=queue_ok,
        )
    )
    return payload


__all__ = [
    "AGENT_EDIT_TURN_CONTRACT_VERSION",
    "ArtifactRef",
    "APPLY_ELIGIBILITY_REASONS",
    "ApplyEligibility",
    "CANVAS_APPLY_GATE_NAMES",
    "DEFAULT_GATE_NAMES",
    "FAILURE_HINT_KEYS",
    "FAILURE_SPECS",
    "FailureEnvelope",
    "FailureKind",
    "GateResult",
    "INTERNAL_TO_PUBLIC_OUTCOME",
    "PUBLIC_OUTCOME_KINDS",
    "REBASELINE_RECOVERY_FIELDS",
    "SCAN_CODE_FAILURE_KIND",
    "StageResult",
    "TURN_OUTCOME_KINDS",
    "TurnContext",
    "TurnOutcome",
    "apply_eligibility_payload",
    "classify_failure",
    "derive_apply_eligibility",
    "ensure_agent_edit_response_contract",
    "failure_envelope",
    "public_outcome_from_turn_outcome",
    "product_failure_envelope_fields",
    "success_envelope",
    "turn_envelope",
]
