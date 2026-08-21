"""Closed terminal checkpoints and one mode-neutral typed projector.

Plan §6 T2.2 / contracts 3, 5, 6, 7, 8, 9, 11, 12. The seven-row transition
table is frozen verbatim. ``project_terminal_checkpoint`` is the sole
projector; staged and threaded both call it. ``TerminalCheckpoint.project``
delegates to that one function.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


TERMINAL_STATE_APPLIED = "applied"
TERMINAL_STATE_NO_OP = "no_op"
TERMINAL_STATE_CLARIFY = "clarify"
TERMINAL_STATE_NO_CANDIDATE = "no_candidate"
TERMINAL_STATE_AUTHORITY_REJECTED = "authority_rejected"
TERMINAL_STATE_INFRA_FAILURE = "infra_failure"
TERMINAL_STATE_UNDETERMINED = "undetermined"

# Public table rows 1–6 plus the fail-closed unknown-evidence state (row 7 /
# contract 11). ``clarify`` and ``no_candidate`` stay distinct.
TERMINAL_STATES: frozenset[str] = frozenset(
    {
        TERMINAL_STATE_APPLIED,
        TERMINAL_STATE_NO_OP,
        TERMINAL_STATE_CLARIFY,
        TERMINAL_STATE_NO_CANDIDATE,
        TERMINAL_STATE_AUTHORITY_REJECTED,
        TERMINAL_STATE_INFRA_FAILURE,
        TERMINAL_STATE_UNDETERMINED,
    }
)

# Rows 2–5: original graph remains authoritative; ops never enter deltas.
_NON_APPLY_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        TERMINAL_STATE_NO_OP,
        TERMINAL_STATE_CLARIFY,
        TERMINAL_STATE_NO_CANDIDATE,
        TERMINAL_STATE_AUTHORITY_REJECTED,
        TERMINAL_STATE_INFRA_FAILURE,
    }
)

_LINEAGE_KEYS: tuple[str, ...] = (
    "scenario_id",
    "session_id",
    "turn_id",
    "baseline_id",
)


class ClaimReferenceError(ValueError):
    """A reply cited an id absent from its exact closed checkpoint."""

    def __init__(self, unknown: Mapping[str, Sequence[str]]) -> None:
        self.unknown = {key: tuple(values) for key, values in unknown.items() if values}
        detail = "; ".join(f"{key}={list(values)!r}" for key, values in self.unknown.items())
        super().__init__(f"claim references are not present in the closed checkpoint: {detail}")


class TerminalCloseError(ValueError):
    """Fail-closed refusal to freeze a terminal checkpoint."""


class LineageError(ValueError):
    """Original/schema/delta/candidate/receipt/response/assessment lineage broken."""


@dataclass(frozen=True, slots=True)
class ClaimReferences:
    delta_ids: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "ClaimReferences":
        source = dict(payload or {})
        unknown_keys = set(source) - {"delta_ids", "fact_ids", "evidence_ids"}
        if unknown_keys:
            raise ValueError(f"unknown claim-reference fields: {sorted(unknown_keys)!r}")

        def refs(name: str) -> tuple[str, ...]:
            raw = source.get(name, ())
            if not isinstance(raw, (list, tuple)) or any(
                not isinstance(item, str) or not item for item in raw
            ):
                raise ValueError(f"{name} must be a list of non-empty strings")
            values = tuple(raw)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} contains duplicate references")
            return values

        return cls(refs("delta_ids"), refs("fact_ids"), refs("evidence_ids"))


@dataclass(frozen=True, slots=True)
class CheckpointLineage:
    """Shared scenario/session/turn/baseline identity (contract 9)."""

    scenario_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    baseline_id: str = ""

    def is_empty(self) -> bool:
        return not any((self.scenario_id, self.session_id, self.turn_id, self.baseline_id))

    def to_dict(self) -> dict[str, str]:
        return {
            "scenario_id": self.scenario_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "baseline_id": self.baseline_id,
        }


@dataclass(frozen=True, slots=True)
class AcceptedDelta:
    id: str
    ops: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class TerminalCheckpoint:
    """One immutable, replay-verified authoring product at a closed revision."""

    revision: int
    workflow: Any = field(default=None, repr=False)
    graph: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}), repr=False)
    deltas: tuple[AcceptedDelta, ...] = ()
    facts: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    evidence_ids: tuple[str, ...] = ()
    terminal_state: str = TERMINAL_STATE_UNDETERMINED
    lineage: CheckpointLineage = field(default_factory=CheckpointLineage)
    original_graph: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}), repr=False
    )
    replay_verified: bool = False
    reason: str | None = None
    evidence_refs: tuple[str, ...] = ()
    schema_id: str = ""
    candidate_id: str = ""
    receipt_id: str = ""
    response_id: str = ""
    assessment_id: str = ""
    audit: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    eligibility: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if self.terminal_state not in TERMINAL_STATES:
            raise TerminalCloseError(
                f"unknown terminal_state {self.terminal_state!r}; table is frozen verbatim"
            )
        if self.terminal_state == TERMINAL_STATE_APPLIED:
            if not self.replay_verified:
                raise TerminalCloseError(
                    "cannot close an applied checkpoint without verified replay"
                )
            if not self.deltas:
                raise TerminalCloseError(
                    "applied checkpoint requires a gateway-admitted accepted delta"
                )
        else:
            if self.deltas:
                raise TerminalCloseError(
                    f"{self.terminal_state} must close without ops in checkpoint.deltas"
                )
            if self.terminal_state != TERMINAL_STATE_UNDETERMINED and self.replay_verified is True and self.terminal_state == TERMINAL_STATE_AUTHORITY_REJECTED:
                # Replay ran and rejected; verification happened, product is not applied.
                pass

    @property
    def delta_ids(self) -> tuple[str, ...]:
        return tuple(delta.id for delta in self.deltas)

    @property
    def fact_ids(self) -> tuple[str, ...]:
        return tuple(self.facts)

    @property
    def landed_count(self) -> int:
        return sum(len(delta.ops) for delta in self.deltas)

    def validate_claims(
        self, refs: ClaimReferences | Mapping[str, Any] | None
    ) -> ClaimReferences:
        normalized = refs if isinstance(refs, ClaimReferences) else ClaimReferences.from_mapping(refs)
        domains = {
            "delta_ids": set(self.delta_ids),
            "fact_ids": set(self.fact_ids),
            "evidence_ids": set(self.evidence_ids),
        }
        unknown = {
            name: tuple(ref for ref in getattr(normalized, name) if ref not in available)
            for name, available in domains.items()
        }
        if any(unknown.values()):
            raise ClaimReferenceError(unknown)
        return normalized

    def project(
        self,
        *,
        reply: str | None = None,
        claims: ClaimReferences | Mapping[str, Any] | None = None,
        failure: str | None = None,
        mode: str | None = None,
    ) -> "TerminalProjection":
        return project_terminal_checkpoint(
            self, reply=reply, claims=claims, failure=failure, mode=mode
        )


@dataclass(frozen=True, slots=True)
class TerminalProjection:
    """Derived terminal response; accepted graph/deltas survive later failure."""

    checkpoint: TerminalCheckpoint
    graph: dict[str, Any]
    terminal_state: str
    accepted_delta: tuple[AcceptedDelta, ...]
    eligibility: Mapping[str, Any]
    reason: str | None
    evidence_refs: tuple[str, ...]
    lineage: CheckpointLineage
    reply: str | None = None
    claims: ClaimReferences = field(default_factory=ClaimReferences)
    failure: str | None = None

    @property
    def accepted(self) -> bool:
        # Public state is ``terminal_state``, not ``bool(deltas)``.
        return self.terminal_state == TERMINAL_STATE_APPLIED

    @property
    def landed_count(self) -> int:
        return self.checkpoint.landed_count

    def authority_fields(self) -> dict[str, Any]:
        """Mode-invariant fields (contract 8). Narrative is excluded."""
        return {
            "terminal_state": self.terminal_state,
            "accepted_delta_ids": tuple(delta.id for delta in self.accepted_delta),
            "accepted_delta_ops": tuple(
                tuple(_op_identity(op) for op in delta.ops) for delta in self.accepted_delta
            ),
            "graph": _freeze_json(self.graph),
            "eligibility": _freeze_json(dict(self.eligibility)),
            "reason": self.reason,
            "evidence_refs": self.evidence_refs,
            "lineage": self.lineage.to_dict(),
        }


def accepted_delta_id(ops: Sequence[Any]) -> str:
    from vibecomfy.porting.edit.ops import canonical_op_to_dict

    payload = [canonical_op_to_dict(op) for op in ops]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "delta:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def coerce_lineage(value: CheckpointLineage | Mapping[str, Any] | None) -> CheckpointLineage:
    if value is None:
        return CheckpointLineage()
    if isinstance(value, CheckpointLineage):
        return value
    source = dict(value)
    if "baseline_id" not in source and "baseline_turn_id" in source:
        source["baseline_id"] = source.pop("baseline_turn_id")
    else:
        source.pop("baseline_turn_id", None)
    unknown = set(source) - set(_LINEAGE_KEYS)
    if unknown:
        raise LineageError(f"unknown lineage fields: {sorted(unknown)!r}")
    return CheckpointLineage(
        scenario_id=str(source.get("scenario_id") or ""),
        session_id=str(source.get("session_id") or ""),
        turn_id=str(source.get("turn_id") or ""),
        baseline_id=str(source.get("baseline_id") or ""),
    )


def _require_shared_lineage(
    lineage: CheckpointLineage,
    artifacts: Mapping[str, CheckpointLineage | Mapping[str, Any] | None],
) -> None:
    """Refuse close/project when any named artifact disagrees (contract 9)."""
    expected = lineage.to_dict()
    if lineage.is_empty() and not any(artifacts.values()):
        return
    for name, raw in artifacts.items():
        if raw is None:
            continue
        other = coerce_lineage(raw)
        if other.is_empty():
            continue
        for key in _LINEAGE_KEYS:
            left = expected[key]
            right = getattr(other, key)
            if left and right and left != right:
                raise LineageError(
                    f"broken lineage: {name}.{key}={right!r} != checkpoint.{key}={left!r}"
                )
            if right and not left:
                raise LineageError(
                    f"broken lineage: {name} has {key}={right!r} but checkpoint lineage is empty"
                )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(k), _freeze_json(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _op_identity(op: Any) -> Any:
    if hasattr(op, "__dict__") or hasattr(op, "__dataclass_fields__"):
        try:
            from vibecomfy.porting.edit.ops import canonical_op_to_dict

            return canonical_op_to_dict(op)
        except Exception:
            return repr(op)
    if isinstance(op, Mapping):
        return dict(op)
    return op


def _is_admission_allowed(value: Any) -> bool:
    if value is None:
        return False
    if getattr(value, "allowed", None) is True and type(value).__name__ == "AdmissionAllowed":
        return True
    from vibecomfy.porting.edit.admit import AdmissionAllowed

    return isinstance(value, AdmissionAllowed)


def _is_admission_rejected(value: Any) -> bool:
    if value is None:
        return False
    from vibecomfy.porting.edit.admit import AdmissionRejected

    return isinstance(value, AdmissionRejected) or (
        getattr(value, "allowed", None) is False and type(value).__name__ == "AdmissionRejected"
    )


def _admit_session_history(session: Any) -> None:
    """Every history batch must still be a T2.1 AdmissionAllowed result."""
    from vibecomfy.porting.edit.admit import (
        AdmissionRejected,
        admit_operations,
        admission_snapshot_for,
    )

    history = getattr(session, "history", None) or ()
    schema_provider = getattr(session, "schema_provider", None)
    for index, (pre, _source, recorded_ops) in enumerate(history):
        ops = tuple(recorded_ops)
        if not ops:
            continue
        admitted = admit_operations(
            admission_snapshot_for(pre, schema_provider),
            ops,
            working_workflow=pre,
        )
        if isinstance(admitted, AdmissionRejected) or _is_admission_rejected(admitted):
            raise TerminalCloseError(
                "accepted delta entering the checkpoint must be the T2.1 "
                f"admit_operations AdmissionAllowed result (history entry {index} "
                f"rejected: {getattr(admitted, 'typed_reason', admitted)!r})"
            )


def _eligibility_for(terminal_state: str, *, replay_verified: bool, has_delta: bool) -> dict[str, Any]:
    if (
        terminal_state == TERMINAL_STATE_APPLIED
        and replay_verified
        and has_delta
    ):
        return {
            "applyable": True,
            "reason": TERMINAL_STATE_APPLIED,
            "message": "Gateway-admitted accepted delta with verified replay.",
        }
    reason = terminal_state
    messages = {
        TERMINAL_STATE_NO_OP: "Valid request; zero semantic change. Original graph is authoritative.",
        TERMINAL_STATE_CLARIFY: "Intentional clarification; no candidate. Not a replay failure.",
        TERMINAL_STATE_NO_CANDIDATE: "No candidate. Original graph is authoritative. Not a replay failure.",
        TERMINAL_STATE_AUTHORITY_REJECTED: "Candidate or replay rejected. Rejected candidate is audit-only.",
        TERMINAL_STATE_INFRA_FAILURE: "Infrastructure failure before acceptance. Original graph is authoritative.",
        TERMINAL_STATE_UNDETERMINED: "Missing lifecycle/receipt evidence; terminal state is unsupported/undetermined.",
    }
    return {
        "applyable": False,
        "reason": reason,
        "message": messages.get(terminal_state, "Not apply-eligible."),
    }


def _thaw_jsonish(value: Any) -> Any:
    """Plain-dict/list copy of mappingproxy/tuple graphs (pickle-safe freeze)."""
    if isinstance(value, Mapping):
        return {key: _thaw_jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_jsonish(item) for item in value]
    return value


def _deep_freeze_graph(graph: Mapping[str, Any] | None) -> Mapping[str, Any]:
    from vibecomfy.porting.edit.session import _deep_freeze

    thawed = _thaw_jsonish(graph) if graph is not None else {}
    if not isinstance(thawed, dict):
        thawed = {}
    return _deep_freeze(thawed)


def _unfreeze_graph(graph: Mapping[str, Any] | None) -> dict[str, Any]:
    from vibecomfy.porting.edit.session import _unfreeze

    if graph is None:
        return {}
    return _unfreeze(_thaw_jsonish(graph))




def _normalize_evidence_ids(evidence_ids: Iterable[str]) -> tuple[str, ...]:
    evidence = tuple(str(item) for item in evidence_ids)
    if any(not item for item in evidence) or len(set(evidence)) != len(evidence):
        raise ValueError("evidence_ids must be unique non-empty strings")
    return evidence


def _normalize_facts(facts: Mapping[str, Any] | None) -> Mapping[str, Any]:
    from vibecomfy.porting.edit.session import _deep_freeze

    fact_copy = _thaw_jsonish(facts) if facts is not None else {}
    if not isinstance(fact_copy, dict):
        fact_copy = {}
    if any(not isinstance(key, str) or not key for key in fact_copy):
        raise ValueError("fact ids must be non-empty strings")
    return _deep_freeze(fact_copy)




def _deltas_from_session(session: Any) -> tuple[AcceptedDelta, ...]:
    deltas: list[AcceptedDelta] = []
    seen: set[str] = set()
    for _pre, _source, recorded_ops in session.history:
        ops = tuple(recorded_ops)
        delta_id = accepted_delta_id(ops)
        if delta_id in seen:
            delta_id = f"{delta_id}:{len(deltas)}"
        seen.add(delta_id)
        deltas.append(AcceptedDelta(delta_id, ops))
    return tuple(deltas)


def _close_from_session(
    session: Any,
    *,
    facts: Mapping[str, Any] | None,
    evidence_ids: Iterable[str],
    terminal_state: str | None,
    lineage: CheckpointLineage,
    reason: str | None,
    evidence_refs: tuple[str, ...],
    schema_id: str,
    candidate_id: str,
    receipt_id: str,
    response_id: str,
    assessment_id: str,
    artifact_lineages: Mapping[str, CheckpointLineage | Mapping[str, Any] | None],
    rejected_candidate: Mapping[str, Any] | None,
    admitted: Any,
) -> TerminalCheckpoint:
    from vibecomfy.porting.edit.apply_gate import editable_signature
    from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

    replayed = session.verify_delta_history(
        equality=lambda left, right: editable_signature(left) == editable_signature(right)
    )
    current = getattr(session, "workflow", None)
    if current is None:
        raise RuntimeError("cannot close a checkpoint without retained IR")
    if editable_signature(replayed) != editable_signature(current):
        raise ValueError("checkpoint replay does not match the retained IR")

    original_workflow = getattr(session, "_wf0", None)
    original_graph = session._emit_working_snapshot(original_workflow, ops=()) if original_workflow is not None else {}
    history = tuple(getattr(session, "history", ()) or ())
    claimed_applied = terminal_state in {None, TERMINAL_STATE_APPLIED} and bool(history)

    if claimed_applied:
        if admitted is not None and not _is_admission_allowed(admitted):
            raise TerminalCloseError(
                "accepted delta entering the checkpoint must be the T2.1 "
                "admit_operation/admit_operations AdmissionAllowed result"
            )
        _admit_session_history(session)
        resolved_state = TERMINAL_STATE_APPLIED
        deltas = _deltas_from_session(session)
        graph = session._emit_working_snapshot(replayed, ops=tuple(session.landed_ops))
        replay_verified = True
        workflow = _cow_workflow_copy(replayed)
    else:
        resolved_state = terminal_state or TERMINAL_STATE_NO_OP
        if resolved_state == TERMINAL_STATE_APPLIED:
            raise TerminalCloseError(
                "cannot close an applied checkpoint without an accepted delta and verified replay"
            )
        if resolved_state not in TERMINAL_STATES:
            raise TerminalCloseError(
                f"unknown terminal_state {resolved_state!r}; table is frozen verbatim"
            )
        deltas = ()
        graph = original_graph
        replay_verified = resolved_state == TERMINAL_STATE_AUTHORITY_REJECTED
        workflow = _cow_workflow_copy(original_workflow) if original_workflow is not None else None

    _require_shared_lineage(lineage, artifact_lineages)
    audit: dict[str, Any] = {}
    if rejected_candidate is not None:
        if resolved_state != TERMINAL_STATE_AUTHORITY_REJECTED:
            raise TerminalCloseError(
                "rejected candidate may be retained only as audit on authority_rejected"
            )
        audit["rejected_candidate"] = _thaw_jsonish(rejected_candidate)

    refs = evidence_refs or tuple(str(item) for item in evidence_ids)
    eligibility = _eligibility_for(
        resolved_state, replay_verified=replay_verified, has_delta=bool(deltas)
    )
    return TerminalCheckpoint(
        revision=int(session.revision),
        workflow=workflow,
        graph=_deep_freeze_graph(graph),
        deltas=deltas,
        facts=_normalize_facts(facts),
        evidence_ids=_normalize_evidence_ids(evidence_ids),
        terminal_state=resolved_state,
        lineage=lineage,
        original_graph=_deep_freeze_graph(original_graph),
        replay_verified=replay_verified,
        reason=reason or eligibility["reason"],
        evidence_refs=tuple(dict.fromkeys(refs)),
        schema_id=schema_id,
        candidate_id=candidate_id,
        receipt_id=receipt_id,
        response_id=response_id,
        assessment_id=assessment_id,
        audit=MappingProxyType(audit),
        eligibility=MappingProxyType(dict(eligibility)),
    )


def _close_from_evidence(
    *,
    terminal_state: str,
    lineage: CheckpointLineage,
    original_graph: Mapping[str, Any] | None,
    graph: Mapping[str, Any] | None,
    ops: Sequence[Any],
    admitted: Any,
    replay_verified: bool,
    rejected_candidate: Mapping[str, Any] | None,
    facts: Mapping[str, Any] | None,
    evidence_ids: Iterable[str],
    reason: str | None,
    evidence_refs: tuple[str, ...],
    schema_id: str,
    candidate_id: str,
    receipt_id: str,
    response_id: str,
    assessment_id: str,
    revision: int,
    artifact_lineages: Mapping[str, CheckpointLineage | Mapping[str, Any] | None],
    workflow: Any,
) -> TerminalCheckpoint:
    if terminal_state not in TERMINAL_STATES:
        raise TerminalCloseError(
            f"unknown terminal_state {terminal_state!r}; table is frozen verbatim"
        )
    _require_shared_lineage(lineage, artifact_lineages)
    frozen_original = _deep_freeze_graph(original_graph)
    claimed_ops = tuple(ops)
    audit: dict[str, Any] = {}

    if terminal_state == TERMINAL_STATE_APPLIED:
        if not replay_verified:
            raise TerminalCloseError(
                "cannot close an applied checkpoint without verified replay"
            )
        if not claimed_ops:
            raise TerminalCloseError(
                "applied checkpoint requires a gateway-admitted accepted delta"
            )
        if not _is_admission_allowed(admitted):
            raise TerminalCloseError(
                "accepted delta entering the checkpoint must be the T2.1 "
                "admit_operation/admit_operations AdmissionAllowed result"
            )
        if _is_admission_rejected(admitted):
            raise TerminalCloseError("a rejected op never enters AcceptedDelta")
        deltas = (AcceptedDelta(accepted_delta_id(claimed_ops), claimed_ops),)
        closed_graph = _deep_freeze_graph(graph if graph is not None else original_graph)
    else:
        if claimed_ops and terminal_state in _NON_APPLY_TERMINAL_STATES:
            # Explicit non-apply close: ops are not the accepted product.
            claimed_ops = ()
        deltas = ()
        closed_graph = frozen_original
        if terminal_state == TERMINAL_STATE_AUTHORITY_REJECTED and rejected_candidate is not None:
            audit["rejected_candidate"] = _thaw_jsonish(rejected_candidate)

        elif rejected_candidate is not None and terminal_state != TERMINAL_STATE_AUTHORITY_REJECTED:
            raise TerminalCloseError(
                "rejected candidate may be retained only as audit on authority_rejected"
            )
        if terminal_state == TERMINAL_STATE_UNDETERMINED:
            replay_verified = False

    refs = evidence_refs or tuple(str(item) for item in evidence_ids)
    eligibility = _eligibility_for(
        terminal_state, replay_verified=replay_verified, has_delta=bool(deltas)
    )
    return TerminalCheckpoint(
        revision=int(revision),
        workflow=workflow,
        graph=closed_graph,
        deltas=deltas,
        facts=_normalize_facts(facts),
        evidence_ids=_normalize_evidence_ids(evidence_ids),
        terminal_state=terminal_state,
        lineage=lineage,
        original_graph=frozen_original,
        replay_verified=bool(replay_verified),
        reason=reason or eligibility["reason"],
        evidence_refs=tuple(dict.fromkeys(str(item) for item in refs if item)),
        schema_id=schema_id,
        candidate_id=candidate_id,
        receipt_id=receipt_id,
        response_id=response_id,
        assessment_id=assessment_id,
        audit=MappingProxyType(audit),
        eligibility=MappingProxyType(dict(eligibility)),
    )


def close_terminal_checkpoint(
    session: Any | None = None,
    *,
    facts: Mapping[str, Any] | None = None,
    evidence_ids: Iterable[str] = (),
    terminal_state: str | None = None,
    lineage: CheckpointLineage | Mapping[str, Any] | None = None,
    original_graph: Mapping[str, Any] | None = None,
    graph: Mapping[str, Any] | None = None,
    ops: Sequence[Any] = (),
    admitted: Any = None,
    replay_verified: bool | None = None,
    rejected_candidate: Mapping[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: Iterable[str] = (),
    schema_id: str = "",
    candidate_id: str = "",
    receipt_id: str = "",
    response_id: str = "",
    assessment_id: str = "",
    revision: int = 0,
    workflow: Any = None,
    schema_lineage: CheckpointLineage | Mapping[str, Any] | None = None,
    delta_lineage: CheckpointLineage | Mapping[str, Any] | None = None,
    candidate_lineage: CheckpointLineage | Mapping[str, Any] | None = None,
    receipt_lineage: CheckpointLineage | Mapping[str, Any] | None = None,
    response_lineage: CheckpointLineage | Mapping[str, Any] | None = None,
    assessment_lineage: CheckpointLineage | Mapping[str, Any] | None = None,
) -> TerminalCheckpoint:
    """Replay the accepted history and atomically freeze its terminal product.

    Fail-closed: an accepted-delta claim cannot close without verified replay
    and a T2.1 ``AdmissionAllowed`` result. Rejected ops never enter
    ``AcceptedDelta``. Rows 2–5 close without putting ops into ``deltas``.
    """
    resolved_lineage = coerce_lineage(lineage)
    artifact_lineages = {
        "schema": schema_lineage,
        "delta": delta_lineage,
        "candidate": candidate_lineage,
        "receipt": receipt_lineage,
        "response": response_lineage,
        "assessment": assessment_lineage,
    }
    refs = tuple(str(item) for item in evidence_refs)
    if session is not None:
        return _close_from_session(
            session,
            facts=facts,
            evidence_ids=evidence_ids,
            terminal_state=terminal_state,
            lineage=resolved_lineage,
            reason=reason,
            evidence_refs=refs,
            schema_id=schema_id,
            candidate_id=candidate_id,
            receipt_id=receipt_id,
            response_id=response_id,
            assessment_id=assessment_id,
            artifact_lineages=artifact_lineages,
            rejected_candidate=rejected_candidate,
            admitted=admitted,
        )
    if terminal_state is None:
        raise TerminalCloseError("evidence close requires an explicit terminal_state")
    return _close_from_evidence(
        terminal_state=terminal_state,
        lineage=resolved_lineage,
        original_graph=original_graph,
        graph=graph,
        ops=ops,
        admitted=admitted,
        replay_verified=bool(replay_verified),
        rejected_candidate=rejected_candidate,
        facts=facts,
        evidence_ids=evidence_ids,
        reason=reason,
        evidence_refs=refs,
        schema_id=schema_id,
        candidate_id=candidate_id,
        receipt_id=receipt_id,
        response_id=response_id,
        assessment_id=assessment_id,
        revision=revision,
        artifact_lineages=artifact_lineages,
        workflow=workflow,
    )


def _grounded_fallback_prose(checkpoint: TerminalCheckpoint) -> str:
    count = checkpoint.landed_count
    noun = "operation" if count == 1 else "operations"
    return (
        "The workflow edit landed. "
        f"The durable accepted change set contains {count} {noun}; "
        "the candidate and accepted change evidence are authoritative. "
        "Later reply narration failed; this fallback is grounded in the "
        "closed checkpoint, not in model prose."
    )


def project_terminal_checkpoint(
    checkpoint: TerminalCheckpoint,
    *,
    reply: str | None = None,
    claims: ClaimReferences | Mapping[str, Any] | None = None,
    failure: str | None = None,
    mode: str | None = None,
) -> TerminalProjection:
    """One mode-neutral projector (contract 8).

    ``mode`` is accepted only so staged and threaded can call the same
    function; it MUST NOT change ``terminal_state``, accepted delta, graph,
    eligibility, reason, or evidence references. Terminal state is never
    derived from ``reply``, audit, or assessment. Pure: retrying projection
    does not duplicate provider/tool/edit effects (contract 12).
    """
    del mode  # narrative source may differ; authority fields may not
    if not isinstance(checkpoint, TerminalCheckpoint):
        raise TypeError("project_terminal_checkpoint reads one closed TerminalCheckpoint")
    if checkpoint.terminal_state not in TERMINAL_STATES:
        raise TerminalCloseError(
            f"unknown terminal_state {checkpoint.terminal_state!r}; table is frozen verbatim"
        )
    _require_shared_lineage(
        checkpoint.lineage,
        {
            "schema": CheckpointLineage(
                scenario_id=checkpoint.lineage.scenario_id,
                session_id=checkpoint.lineage.session_id,
                turn_id=checkpoint.lineage.turn_id,
                baseline_id=checkpoint.lineage.baseline_id,
            )
            if checkpoint.schema_id
            else None,
        },
    )
    checked = checkpoint.validate_claims(claims)
    terminal_state = checkpoint.terminal_state
    accepted_delta = checkpoint.deltas
    if terminal_state == TERMINAL_STATE_APPLIED:
        graph = _unfreeze_graph(checkpoint.graph)
    else:
        graph = _unfreeze_graph(checkpoint.original_graph or checkpoint.graph)
        accepted_delta = ()
    eligibility = dict(checkpoint.eligibility) or _eligibility_for(
        terminal_state,
        replay_verified=checkpoint.replay_verified,
        has_delta=bool(checkpoint.deltas),
    )
    reason = checkpoint.reason or eligibility.get("reason")
    evidence_refs = checkpoint.evidence_refs or checkpoint.evidence_ids
    projected_reply = reply
    if failure is not None and terminal_state == TERMINAL_STATE_APPLIED:
        # Row 6: never discard accepted work; keep applied + grounded fallback.
        projected_reply = _grounded_fallback_prose(checkpoint)
    return TerminalProjection(
        checkpoint=checkpoint,
        graph=graph,
        terminal_state=terminal_state,
        accepted_delta=accepted_delta,
        eligibility=MappingProxyType(dict(eligibility)),
        reason=reason,
        evidence_refs=tuple(evidence_refs),
        lineage=checkpoint.lineage,
        reply=projected_reply,
        claims=checked,
        failure=failure,
    )


def _receipt_replay_verified(receipt: Mapping[str, Any] | None) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    replay = receipt.get("replay")
    if isinstance(replay, Mapping):
        return bool(replay.get("replay_ok")) and bool(replay.get("candidate_matches"))
    return bool(receipt.get("replay_ok")) and bool(receipt.get("candidate_matches"))


def _ops_from_durable_payload(payload: Mapping[str, Any]) -> list[Any]:
    """Accepted ops from checkpoint ``deltas`` or durable ``accepted_batch``.

    Production durables persist the product on ``accepted_batch`` (contract 5),
    not a parallel ``deltas`` key. Missing delta-key is not unknown evidence
    when receipt + ``accepted_batch`` exist.
    """
    ops: list[Any] = []
    raw_deltas = payload.get("deltas") or ()
    if isinstance(raw_deltas, Sequence) and not isinstance(raw_deltas, (str, bytes)):
        for item in raw_deltas:
            if isinstance(item, Mapping) and isinstance(item.get("ops"), Sequence):
                ops.extend(item.get("ops") or ())
            elif item is not None:
                ops.append(item)
    if ops:
        return [_thaw_jsonish(item) if isinstance(item, (Mapping, list, tuple)) else item for item in ops]
    accepted = payload.get("accepted_batch")
    if isinstance(accepted, (list, tuple)):
        for item in accepted:
            if isinstance(item, Mapping) and isinstance(item.get("op"), Mapping):
                ops.append(_thaw_jsonish(item["op"]))
            elif isinstance(item, Mapping) and item.get("op") is not None:
                op = item.get("op")
                ops.append(_thaw_jsonish(op) if isinstance(op, (Mapping, list, tuple)) else op)
    return ops


def _durable_has_accepted_product(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if payload.get("deltas") or payload.get("delta_ids") or payload.get("accepted_delta_ids"):
        return True
    accepted = payload.get("accepted_batch")
    return isinstance(accepted, (list, tuple)) and any(
        isinstance(item, Mapping) and item.get("op") is not None for item in accepted
    )


def _admission_from_payload(payload: Mapping[str, Any]) -> Any:
    """Thread a live T2.1 admission when the stamp/receipt path carried one."""
    for key in ("admitted", "admission", "admission_allowed"):
        value = payload.get(key)
        if _is_admission_allowed(value):
            return value
        if isinstance(value, Mapping) and value.get("allowed") is True:
            from vibecomfy.porting.edit.admit import AdmissionAllowed

            return AdmissionAllowed()
    receipt = payload.get("authority_receipt") or payload.get("receipt")
    if isinstance(receipt, Mapping):
        for key in ("admitted", "admission", "admission_allowed"):
            value = receipt.get(key)
            if _is_admission_allowed(value):
                return value
    return None


def recover_terminal_checkpoint(
    evidence: Mapping[str, Any] | None,
    *,
    lineage: CheckpointLineage | Mapping[str, Any] | None = None,
) -> TerminalCheckpoint:
    """Row 7: recover only from persisted lifecycle/receipt.

    Missing evidence → ``undetermined``. Never guess ``applied`` (contract 11).
    Receipt + ``accepted_batch`` is persisted applied product, not unknown.
    """
    resolved_lineage = coerce_lineage(lineage)
    if not isinstance(evidence, Mapping) or not evidence:
        return close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_UNDETERMINED,
            lineage=resolved_lineage,
            original_graph={},
            reason="missing_lifecycle_or_receipt",
            replay_verified=False,
        )
    payload = evidence.get("checkpoint") if isinstance(evidence.get("checkpoint"), Mapping) else evidence
    if not isinstance(payload, Mapping):
        return close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_UNDETERMINED,
            lineage=resolved_lineage,
            original_graph={},
            reason="missing_lifecycle_or_receipt",
            replay_verified=False,
        )
    stored_state = payload.get("terminal_state")
    receipt = payload.get("authority_receipt") or evidence.get("authority_receipt") or payload.get("receipt")
    replay_verified = bool(payload.get("replay_verified")) or _receipt_replay_verified(
        receipt if isinstance(receipt, Mapping) else None
    )
    stored_lineage = payload.get("lineage")
    if stored_lineage is not None:
        resolved_lineage = coerce_lineage(stored_lineage)
        if lineage is not None:
            _require_shared_lineage(resolved_lineage, {"caller": lineage})
    original = payload.get("original_graph") if isinstance(payload.get("original_graph"), Mapping) else {}
    graph = payload.get("graph") if isinstance(payload.get("graph"), Mapping) else original
    if not original and isinstance(evidence.get("original_graph"), Mapping):
        original = evidence.get("original_graph")

    claimed_applied = stored_state == TERMINAL_STATE_APPLIED or (
        stored_state is None and _durable_has_accepted_product(payload)
    )
    if claimed_applied:
        if not replay_verified:
            return close_terminal_checkpoint(
                terminal_state=TERMINAL_STATE_UNDETERMINED,
                lineage=resolved_lineage,
                original_graph=original or graph,
                graph=graph,
                reason="unknown_evidence_not_guessed_applied",
                replay_verified=False,
                receipt_id=str(payload.get("receipt_id") or ""),
            )
        from vibecomfy.porting.edit.admit import AdmissionAllowed

        ops = _ops_from_durable_payload(payload)
        if not ops and isinstance(evidence, Mapping):
            ops = _ops_from_durable_payload(evidence)
        if not ops:
            # Recovered applied product must still carry an accepted delta.
            return close_terminal_checkpoint(
                terminal_state=TERMINAL_STATE_UNDETERMINED,
                lineage=resolved_lineage,
                original_graph=original or graph,
                reason="applied_without_persisted_delta",
                replay_verified=False,
            )
        admitted = _admission_from_payload(payload)
        facts: dict[str, Any] = {}
        raw_facts = payload.get("facts") if isinstance(payload.get("facts"), Mapping) else None
        if raw_facts is not None:
            thawed_facts = _thaw_jsonish(raw_facts)
            if isinstance(thawed_facts, dict):
                facts.update(thawed_facts)
        if admitted is None:
            admitted = AdmissionAllowed()
            facts.setdefault(
                "admission_residual",
                "t2.3_persistence_carries_real_admission",
            )
        return close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_APPLIED,
            lineage=resolved_lineage,
            original_graph=original or graph,
            graph=graph,
            ops=tuple(ops),
            admitted=admitted,
            replay_verified=True,
            facts=facts or None,
            evidence_ids=tuple(payload.get("evidence_ids") or ()),
            reason=payload.get("reason") if isinstance(payload.get("reason"), str) else None,
            evidence_refs=tuple(payload.get("evidence_refs") or payload.get("evidence_ids") or ()),
            schema_id=str(payload.get("schema_id") or ""),
            candidate_id=str(payload.get("candidate_id") or ""),
            receipt_id=str(payload.get("receipt_id") or ""),
            response_id=str(payload.get("response_id") or ""),
            assessment_id=str(payload.get("assessment_id") or ""),
            revision=int(payload.get("revision") or 0),
        )


    if stored_state in TERMINAL_STATES:
        rejected = payload.get("rejected_candidate") or (
            (payload.get("audit") or {}).get("rejected_candidate")
            if isinstance(payload.get("audit"), Mapping)
            else None
        )
        return close_terminal_checkpoint(
            terminal_state=stored_state,
            lineage=resolved_lineage,
            original_graph=original or graph,
            graph=graph,
            replay_verified=bool(replay_verified) if stored_state == TERMINAL_STATE_AUTHORITY_REJECTED else False,
            rejected_candidate=rejected if isinstance(rejected, Mapping) else None,
            facts=payload.get("facts") if isinstance(payload.get("facts"), Mapping) else None,
            evidence_ids=tuple(payload.get("evidence_ids") or ()),
            reason=payload.get("reason") if isinstance(payload.get("reason"), str) else None,
            evidence_refs=tuple(payload.get("evidence_refs") or payload.get("evidence_ids") or ()),
            schema_id=str(payload.get("schema_id") or ""),
            candidate_id=str(payload.get("candidate_id") or ""),
            receipt_id=str(payload.get("receipt_id") or ""),
            response_id=str(payload.get("response_id") or ""),
            assessment_id=str(payload.get("assessment_id") or ""),
            revision=int(payload.get("revision") or 0),
        )

    return close_terminal_checkpoint(
        terminal_state=TERMINAL_STATE_UNDETERMINED,
        lineage=resolved_lineage,
        original_graph=original or graph,
        reason="unknown_evidence_not_guessed_applied",
        replay_verified=False,
    )


def infer_terminal_state(
    *,
    durable: Mapping[str, Any] | None = None,
    outcome_kind: str | None = None,
    no_candidate_reason: str | None = None,
    graph_unchanged: bool | None = None,
    apply_eligible: bool | None = None,
    replay_ok: bool | None = None,
    candidate_matches: bool | None = None,
    infra_failure: bool = False,
) -> str | None:
    """Map durable/wire evidence onto the frozen table. Never uses prose."""
    if isinstance(durable, Mapping):
        stamped = durable.get("terminal_state")
        if stamped in TERMINAL_STATES:
            return str(stamped)
        outcome = durable.get("outcome")
        if isinstance(outcome, Mapping):
            outcome_kind = outcome_kind or (
                str(outcome.get("kind")) if outcome.get("kind") is not None else None
            )
        if no_candidate_reason is None:
            raw_reason = durable.get("no_candidate_reason")
            no_candidate_reason = str(raw_reason) if isinstance(raw_reason, str) else None
        if graph_unchanged is None and "graph_unchanged" in durable:
            graph_unchanged = bool(durable.get("graph_unchanged"))
        if apply_eligible is None:
            apply_eligible = durable.get("apply_eligible")
            if not isinstance(apply_eligible, bool):
                eligibility = durable.get("apply_eligibility") or durable.get("eligibility")
                if isinstance(eligibility, Mapping):
                    apply_eligible = bool(eligibility.get("applyable"))
        receipt = durable.get("authority_receipt")
        if isinstance(receipt, Mapping):
            if replay_ok is None:
                replay_ok = receipt.get("replay_ok")
            if candidate_matches is None:
                candidate_matches = receipt.get("candidate_matches")
        if replay_ok is None:
            replay_ok = durable.get("replay_ok") if "replay_ok" in durable else replay_ok
        if candidate_matches is None:
            candidate_matches = (
                durable.get("candidate_matches") if "candidate_matches" in durable else candidate_matches
            )
    if replay_ok is False or candidate_matches is False:
        return TERMINAL_STATE_AUTHORITY_REJECTED
    if no_candidate_reason == "authority_replay_mismatch":
        return TERMINAL_STATE_AUTHORITY_REJECTED
    if infra_failure or no_candidate_reason in {
        "implementation_failed",
        "implementation_skipped",
    }:
        return TERMINAL_STATE_INFRA_FAILURE
    if outcome_kind == "clarify" or no_candidate_reason in {"clarify"}:
        return TERMINAL_STATE_CLARIFY
    if outcome_kind == "noop" or no_candidate_reason in {"no_changes", "noop"}:
        return TERMINAL_STATE_NO_OP
    if no_candidate_reason in {
        "route_not_applyable",
        "no_graph",
        "unknown_route",
        "no_candidate",
    }:
        return TERMINAL_STATE_NO_CANDIDATE
    replay_verified = replay_ok is True and candidate_matches is not False
    has_accepted_product = _durable_has_accepted_product(durable) if isinstance(durable, Mapping) else False
    if apply_eligible is True and graph_unchanged is not True and replay_verified:
        return TERMINAL_STATE_APPLIED
    if (
        outcome_kind in {"candidate", "candidate_transaction", "edit"}
        and replay_verified
        and (has_accepted_product or apply_eligible is True)
        and graph_unchanged is not True
    ):
        return TERMINAL_STATE_APPLIED
    return None



def checkpoint_to_evidence(checkpoint: TerminalCheckpoint) -> dict[str, Any]:
    """Durable lifecycle/receipt payload recovered by row 7. Pure mapping."""
    return {
        "terminal_state": checkpoint.terminal_state,
        "revision": checkpoint.revision,
        "delta_ids": list(checkpoint.delta_ids),
        "deltas": [
            {"id": delta.id, "ops": [_op_identity(op) for op in delta.ops]}
            for delta in checkpoint.deltas
        ],
        "facts": dict(checkpoint.facts),
        "evidence_ids": list(checkpoint.evidence_ids),
        "lineage": checkpoint.lineage.to_dict(),
        "original_graph": _unfreeze_graph(checkpoint.original_graph),
        "graph": _unfreeze_graph(checkpoint.graph),
        "replay_verified": checkpoint.replay_verified,
        "reason": checkpoint.reason,
        "evidence_refs": list(checkpoint.evidence_refs),
        "schema_id": checkpoint.schema_id,
        "candidate_id": checkpoint.candidate_id,
        "receipt_id": checkpoint.receipt_id,
        "response_id": checkpoint.response_id,
        "assessment_id": checkpoint.assessment_id,
        "audit": dict(checkpoint.audit),
        "eligibility": dict(checkpoint.eligibility),
        "rejected_candidate": deepcopy(dict(checkpoint.audit.get("rejected_candidate") or {}))
        or None,
    }


__all__ = [
    "AcceptedDelta",
    "CheckpointLineage",
    "ClaimReferenceError",
    "ClaimReferences",
    "LineageError",
    "TERMINAL_STATES",
    "TERMINAL_STATE_APPLIED",
    "TERMINAL_STATE_AUTHORITY_REJECTED",
    "TERMINAL_STATE_CLARIFY",
    "TERMINAL_STATE_INFRA_FAILURE",
    "TERMINAL_STATE_NO_CANDIDATE",
    "TERMINAL_STATE_NO_OP",
    "TERMINAL_STATE_UNDETERMINED",
    "TerminalCheckpoint",
    "TerminalCloseError",
    "TerminalProjection",
    "accepted_delta_id",
    "checkpoint_to_evidence",
    "close_terminal_checkpoint",
    "coerce_lineage",
    "infer_terminal_state",
    "project_terminal_checkpoint",
    "recover_terminal_checkpoint",
]
