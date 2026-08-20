"""Closed terminal checkpoints and fail-closed claim-reference validation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from vibecomfy.porting.edit.ops import EditOp, canonical_op_to_dict


class ClaimReferenceError(ValueError):
    """A reply cited an id absent from its exact closed checkpoint."""

    def __init__(self, unknown: Mapping[str, Sequence[str]]) -> None:
        self.unknown = {key: tuple(values) for key, values in unknown.items() if values}
        detail = "; ".join(f"{key}={list(values)!r}" for key, values in self.unknown.items())
        super().__init__(f"claim references are not present in the closed checkpoint: {detail}")


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
class AcceptedDelta:
    id: str
    ops: tuple[EditOp, ...]


@dataclass(frozen=True, slots=True)
class TerminalCheckpoint:
    """One immutable, replay-verified authoring product at a closed revision."""

    revision: int
    workflow: Any = field(repr=False)
    graph: Mapping[str, Any] = field(repr=False)
    deltas: tuple[AcceptedDelta, ...] = ()
    facts: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    evidence_ids: tuple[str, ...] = ()

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
    ) -> "TerminalProjection":
        checked = self.validate_claims(claims)
        from vibecomfy.porting.edit.session import _unfreeze

        return TerminalProjection(
            checkpoint=self,
            graph=_unfreeze(self.graph),
            reply=reply,
            claims=checked,
            failure=failure,
        )


@dataclass(frozen=True, slots=True)
class TerminalProjection:
    """Derived terminal response; accepted graph/deltas survive later failure."""

    checkpoint: TerminalCheckpoint
    graph: dict[str, Any]
    reply: str | None = None
    claims: ClaimReferences = ClaimReferences()
    failure: str | None = None

    @property
    def accepted(self) -> bool:
        return bool(self.checkpoint.deltas)

    @property
    def landed_count(self) -> int:
        return self.checkpoint.landed_count


def accepted_delta_id(ops: Sequence[EditOp]) -> str:
    payload = [canonical_op_to_dict(op) for op in ops]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "delta:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def close_terminal_checkpoint(
    session: Any,
    *,
    facts: Mapping[str, Any] | None = None,
    evidence_ids: Iterable[str] = (),
) -> TerminalCheckpoint:
    """Replay the accepted history and atomically freeze its terminal product."""
    from vibecomfy.porting.edit.apply_gate import editable_signature

    replayed = session.verify_delta_history(
        equality=lambda left, right: editable_signature(left) == editable_signature(right)
    )
    current = getattr(session, "workflow", None)
    if current is None:
        raise RuntimeError("cannot close a checkpoint without retained IR")
    from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
    from vibecomfy.porting.edit.session import _deep_freeze

    if editable_signature(replayed) != editable_signature(current):
        raise ValueError("checkpoint replay does not match the retained IR")
    deltas: list[AcceptedDelta] = []
    seen: set[str] = set()
    for _pre, _source, recorded_ops in session.history:
        ops = tuple(recorded_ops)
        delta_id = accepted_delta_id(ops)
        if delta_id in seen:
            # Repeated identical edits at different revisions must still have
            # distinct durable identities.
            delta_id = f"{delta_id}:{len(deltas)}"
        seen.add(delta_id)
        deltas.append(AcceptedDelta(delta_id, ops))
    fact_copy = deepcopy(dict(facts or {}))
    if any(not isinstance(key, str) or not key for key in fact_copy):
        raise ValueError("fact ids must be non-empty strings")
    evidence = tuple(str(item) for item in evidence_ids)
    if any(not item for item in evidence) or len(set(evidence)) != len(evidence):
        raise ValueError("evidence_ids must be unique non-empty strings")
    graph = session._emit_working_snapshot(replayed, ops=tuple(session.landed_ops))
    return TerminalCheckpoint(
        revision=int(session.revision),
        workflow=_cow_workflow_copy(replayed),
        graph=_deep_freeze(deepcopy(graph)),
        deltas=tuple(deltas),
        facts=_deep_freeze(fact_copy),
        evidence_ids=evidence,
    )


__all__ = [
    "AcceptedDelta",
    "ClaimReferenceError",
    "ClaimReferences",
    "TerminalCheckpoint",
    "TerminalProjection",
    "accepted_delta_id",
    "close_terminal_checkpoint",
]
