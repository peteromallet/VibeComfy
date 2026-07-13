"""Obligation ledger vocabulary for agent-edit turns.

Each obligation declares a structural condition that must (or should) hold
in the candidate graph for a task to be considered satisfied.  The ledger
aggregates obligations, reports their status, and serializes deterministically
so that replayed turns produce identical audit hashes.

Obligation kinds
----------------
* ``class_present``       — a node of a given class-type must exist.
* ``class_absent``        — a node of a given class-type must NOT exist.
* ``value_match``         — a specific field/input value must equal an expected value.
* ``edge_exists``         — a directed edge (link) between two node references must exist.
* ``terminal_output_domain`` — the terminal (output) node must produce a specific output domain.
* ``scope_preserved``     — the scope/session graph must not lose nodes/edges that were present before the turn.
* ``obligation_declared`` — a meta-obligation: the obligation itself is declared but not yet evaluated.

Obligation statuses
-------------------
* ``satisfied``       — the condition is met in the candidate graph.
* ``unsatisfied``     — the condition is NOT met.
* ``unknown``         — the condition could not be evaluated (fail-closed default).
* ``not_evaluated``   — the obligation was intentionally skipped.
* ``unsupported``     — the kind of obligation is not supported by the current runtime.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

# -- Obligation kinds --------------------------------------------------------

OBLIGATION_KIND_CLASS_PRESENT: str = "class_present"
OBLIGATION_KIND_CLASS_ABSENT: str = "class_absent"
OBLIGATION_KIND_VALUE_MATCH: str = "value_match"
OBLIGATION_KIND_EDGE_EXISTS: str = "edge_exists"
OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN: str = "terminal_output_domain"
OBLIGATION_KIND_SCOPE_PRESERVED: str = "scope_preserved"
OBLIGATION_KIND_OBLIGATION_DECLARED: str = "obligation_declared"

OBLIGATION_KINDS: tuple[str, ...] = (
    OBLIGATION_KIND_CLASS_PRESENT,
    OBLIGATION_KIND_CLASS_ABSENT,
    OBLIGATION_KIND_VALUE_MATCH,
    OBLIGATION_KIND_EDGE_EXISTS,
    OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN,
    OBLIGATION_KIND_SCOPE_PRESERVED,
    OBLIGATION_KIND_OBLIGATION_DECLARED,
)

# -- Obligation statuses -----------------------------------------------------

OBLIGATION_STATUS_SATISFIED: str = "satisfied"
OBLIGATION_STATUS_UNSATISFIED: str = "unsatisfied"
OBLIGATION_STATUS_UNKNOWN: str = "unknown"
OBLIGATION_STATUS_NOT_EVALUATED: str = "not_evaluated"
OBLIGATION_STATUS_UNSUPPORTED: str = "unsupported"

OBLIGATION_STATUSES: tuple[str, ...] = (
    OBLIGATION_STATUS_SATISFIED,
    OBLIGATION_STATUS_UNSATISFIED,
    OBLIGATION_STATUS_UNKNOWN,
    OBLIGATION_STATUS_NOT_EVALUATED,
    OBLIGATION_STATUS_UNSUPPORTED,
)

# -- Obligation severity (criticality) ---------------------------------------

OBLIGATION_SEVERITY_REQUIRED: str = "required"
OBLIGATION_SEVERITY_RECOMMENDED: str = "recommended"
OBLIGATION_SEVERITY_OPTIONAL: str = "optional"

OBLIGATION_SEVERITIES: tuple[str, ...] = (
    OBLIGATION_SEVERITY_REQUIRED,
    OBLIGATION_SEVERITY_RECOMMENDED,
    OBLIGATION_SEVERITY_OPTIONAL,
)

# Plan states referenced by obligations --------------------------------------

PLAN_STATE_NOT_REQUIRED: str = "not_required"
PLAN_STATE_REQUIRED_SUPPORTED: str = "required_supported"
PLAN_STATE_REQUIRED_UNSUPPORTED: str = "required_unsupported"

PLAN_STATES: tuple[str, ...] = (
    PLAN_STATE_NOT_REQUIRED,
    PLAN_STATE_REQUIRED_SUPPORTED,
    PLAN_STATE_REQUIRED_UNSUPPORTED,
)

# Contract version -----------------------------------------------------------

OBLIGATION_LEDGER_CONTRACT_VERSION: str = "obligation_ledger_v1"

# -- Helpers -----------------------------------------------------------------


def _validate_kind(kind: str) -> None:
    """Raise ``ValueError`` when *kind* is not a recognised obligation kind."""
    if kind not in OBLIGATION_KINDS:
        raise ValueError(
            f"Obligation kind {kind!r} must be one of {OBLIGATION_KINDS}."
        )


def _validate_status(status: str) -> None:
    """Raise ``ValueError`` when *status* is not a recognised obligation status."""
    if status not in OBLIGATION_STATUSES:
        raise ValueError(
            f"Obligation status {status!r} must be one of {OBLIGATION_STATUSES}."
        )


def _validate_severity(severity: str) -> None:
    """Raise ``ValueError`` when *severity* is not a recognised severity."""
    if severity not in OBLIGATION_SEVERITIES:
        raise ValueError(
            f"Obligation severity {severity!r} must be one of {OBLIGATION_SEVERITIES}."
        )


def _validate_plan_state(plan_state: str | None) -> None:
    """Raise ``ValueError`` when *plan_state* is not a recognised plan state."""
    if plan_state is not None and plan_state not in PLAN_STATES:
        raise ValueError(
            f"Plan state {plan_state!r} must be one of {PLAN_STATES} or None."
        )


def is_satisfied(status: str) -> bool:
    """Return ``True`` when *status* is ``satisfied``."""
    return status == OBLIGATION_STATUS_SATISFIED


def is_unsatisfied(status: str) -> bool:
    """Return ``True`` when *status* is ``unsatisfied``."""
    return status == OBLIGATION_STATUS_UNSATISFIED


def is_unknown(status: str) -> bool:
    """Return ``True`` when *status* is ``unknown``."""
    return status == OBLIGATION_STATUS_UNKNOWN


def is_not_evaluated(status: str) -> bool:
    """Return ``True`` when *status* is ``not_evaluated``."""
    return status == OBLIGATION_STATUS_NOT_EVALUATED


def is_unsupported(status: str) -> bool:
    """Return ``True`` when *status* is ``unsupported``."""
    return status == OBLIGATION_STATUS_UNSUPPORTED


def is_required(severity: str) -> bool:
    """Return ``True`` when *severity* is ``required``."""
    return severity == OBLIGATION_SEVERITY_REQUIRED


# -- Structural target reference ----------------------------------------------


@dataclass(frozen=True)
class StructuralTarget:
    """Stable reference to a node, input, output, or edge in a graph.

    Used to identify *what* an obligation applies to without embedding
    mutable graph payloads.
    """

    node_id: str | None = None
    class_type: str | None = None
    input_name: str | None = None
    output_name: str | None = None
    field: str | None = None
    source_node_id: str | None = None
    source_output: str | None = None
    target_node_id: str | None = None
    target_input: str | None = None
    role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        ``None`` values are omitted to keep payloads compact and
        deterministic.
        """
        return _omit_none({
            "node_id": self.node_id,
            "class_type": self.class_type,
            "input_name": self.input_name,
            "output_name": self.output_name,
            "field": self.field,
            "source_node_id": self.source_node_id,
            "source_output": self.source_output,
            "target_node_id": self.target_node_id,
            "target_input": self.target_input,
            "role": self.role,
        })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StructuralTarget":
        """Deserialize from a JSON-compatible dictionary."""
        return cls(
            node_id=data.get("node_id"),
            class_type=data.get("class_type"),
            input_name=data.get("input_name"),
            output_name=data.get("output_name"),
            field=data.get("field"),
            source_node_id=data.get("source_node_id"),
            source_output=data.get("source_output"),
            target_node_id=data.get("target_node_id"),
            target_input=data.get("target_input"),
            role=data.get("role"),
        )

    @classmethod
    def class_ref(cls, class_type: str) -> "StructuralTarget":
        """Shortcut: target that references a class type presence."""
        return cls(class_type=class_type)

    @classmethod
    def node_ref(cls, node_id: str, *, class_type: str | None = None) -> "StructuralTarget":
        """Shortcut: target that references a specific node."""
        return cls(node_id=node_id, class_type=class_type)

    @classmethod
    def edge_ref(
        cls,
        source_node_id: str,
        target_node_id: str,
        *,
        source_output: str | None = None,
        target_input: str | None = None,
    ) -> "StructuralTarget":
        """Shortcut: target that references an edge between two nodes."""
        return cls(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            source_output=source_output,
            target_input=target_input,
        )

    @classmethod
    def value_ref(
        cls, node_id: str, *, field: str | None = None, input_name: str | None = None
    ) -> "StructuralTarget":
        """Shortcut: target that references a field or input value."""
        return cls(node_id=node_id, field=field, input_name=input_name)


# -- Individual obligation ---------------------------------------------------


@dataclass(frozen=True)
class Obligation:
    """A single structural condition that must (or should) hold.

    Parameters
    ----------
    obligation_id:
        Stable identifier for this obligation (used for hashing and audit).
    kind:
        The kind of obligation (one of ``OBLIGATION_KINDS``).
    severity:
        How critical the obligation is: ``required``, ``recommended``, or
        ``optional``.
    status:
        Current evaluation status (one of ``OBLIGATION_STATUSES``).
    target:
        Structural reference to the graph element(s) the obligation applies to.
    expected:
        Expected value for ``value_match`` obligations, or domain name for
        ``terminal_output_domain``.
    message:
        Human-readable description of the obligation.
    evidence:
        Per-obligation evidence payload (e.g. why it passed or failed).
    plan_state:
        The plan obligation state associated with this obligation, if any.
    """

    obligation_id: str
    kind: str
    severity: str = OBLIGATION_SEVERITY_REQUIRED
    status: str = OBLIGATION_STATUS_UNKNOWN
    target: StructuralTarget | None = None
    expected: Any = None
    message: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)
    plan_state: str | None = None

    def __post_init__(self) -> None:
        _validate_kind(self.kind)
        _validate_status(self.status)
        _validate_severity(self.severity)
        _validate_plan_state(self.plan_state)
        object.__setattr__(self, "evidence", _freeze_jsonish(self.evidence))
        object.__setattr__(self, "expected", _freeze_jsonish(self.expected))

    # -- Property helpers ----------------------------------------------------

    @property
    def is_satisfied(self) -> bool:
        """``True`` when this obligation is satisfied."""
        return self.status == OBLIGATION_STATUS_SATISFIED

    @property
    def is_unsatisfied(self) -> bool:
        """``True`` when this obligation is unsatisfied."""
        return self.status == OBLIGATION_STATUS_UNSATISFIED

    @property
    def is_unknown(self) -> bool:
        """``True`` when this obligation status is unknown."""
        return self.status == OBLIGATION_STATUS_UNKNOWN

    @property
    def is_not_evaluated(self) -> bool:
        """``True`` when this obligation was not evaluated."""
        return self.status == OBLIGATION_STATUS_NOT_EVALUATED

    @property
    def is_unsupported(self) -> bool:
        """``True`` when this obligation kind is unsupported."""
        return self.status == OBLIGATION_STATUS_UNSUPPORTED

    @property
    def is_required(self) -> bool:
        """``True`` when severity is ``required``."""
        return self.severity == OBLIGATION_SEVERITY_REQUIRED

    @property
    def is_complete(self) -> bool:
        """``True`` when the obligation is satisfied or explicitly not required.

        ``unknown``, ``unsupported``, and ``not_evaluated`` are *never*
        complete — they represent a gap that prevents certainty.
        """
        return self.status == OBLIGATION_STATUS_SATISFIED

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        payload: dict[str, Any] = {
            "obligation_id": self.obligation_id,
            "kind": self.kind,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
        }
        if self.target is not None:
            payload["target"] = self.target.to_dict()
        if self.expected is not None:
            payload["expected"] = _thaw_jsonish(self.expected)
        if self.evidence:
            payload["evidence"] = _thaw_jsonish(self.evidence)
        if self.plan_state is not None:
            payload["plan_state"] = self.plan_state
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, _coerce: bool = True) -> "Obligation":
        """Deserialize from a JSON-compatible dictionary.

        When *_coerce* is ``True``, unrecognised kind/status/severity values
        are normalised to safe defaults (``obligation_declared`` /
        ``unknown`` / ``required``) rather than raising.
        """
        kind = str(data.get("kind", OBLIGATION_KIND_OBLIGATION_DECLARED))
        if kind not in OBLIGATION_KINDS:
            if _coerce:
                kind = OBLIGATION_KIND_OBLIGATION_DECLARED
            else:
                raise ValueError(f"Unknown obligation kind {kind!r}")

        status = str(data.get("status", OBLIGATION_STATUS_UNKNOWN))
        if status not in OBLIGATION_STATUSES:
            if _coerce:
                status = OBLIGATION_STATUS_UNKNOWN
            else:
                raise ValueError(f"Unknown obligation status {status!r}")

        severity = str(data.get("severity", OBLIGATION_SEVERITY_REQUIRED))
        if severity not in OBLIGATION_SEVERITIES:
            if _coerce:
                severity = OBLIGATION_SEVERITY_REQUIRED
            else:
                raise ValueError(f"Unknown obligation severity {severity!r}")

        target_raw = data.get("target")
        target = (
            StructuralTarget.from_dict(target_raw)
            if isinstance(target_raw, Mapping)
            else None
        )

        plan_state_raw = data.get("plan_state")
        plan_state = plan_state_raw if isinstance(plan_state_raw, str) and plan_state_raw in PLAN_STATES else None

        return cls(
            obligation_id=str(data.get("obligation_id", "")),
            kind=kind,
            severity=severity,
            status=status,
            target=target,
            expected=data.get("expected"),
            message=str(data.get("message", "")),
            evidence=dict(data.get("evidence", {})) if isinstance(data.get("evidence"), Mapping) else {},
            plan_state=plan_state,
        )

    # -- Factory helpers -----------------------------------------------------

    @classmethod
    def class_present(
        cls,
        obligation_id: str,
        class_type: str,
        *,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create a ``class_present`` obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_CLASS_PRESENT,
            "severity": severity,
            "target": StructuralTarget.class_ref(class_type),
            "message": message or f"Node of class {class_type} must be present.",
        }
        base.update(kwargs)
        return cls(**base)

    @classmethod
    def class_absent(
        cls,
        obligation_id: str,
        class_type: str,
        *,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create a ``class_absent`` obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_CLASS_ABSENT,
            "severity": severity,
            "target": StructuralTarget.class_ref(class_type),
            "message": message or f"Node of class {class_type} must NOT be present.",
        }
        base.update(kwargs)
        return cls(**base)

    @classmethod
    def value_match(
        cls,
        obligation_id: str,
        node_id: str,
        expected: Any,
        *,
        field: str | None = None,
        input_name: str | None = None,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create a ``value_match`` obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_VALUE_MATCH,
            "severity": severity,
            "target": StructuralTarget.value_ref(node_id, field=field, input_name=input_name),
            "expected": expected,
            "message": message or f"Value must match expected for node {node_id}.",
        }
        base.update(kwargs)
        return cls(**base)

    @classmethod
    def edge_exists(
        cls,
        obligation_id: str,
        source_node_id: str,
        target_node_id: str,
        *,
        source_output: str | None = None,
        target_input: str | None = None,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create an ``edge_exists`` obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_EDGE_EXISTS,
            "severity": severity,
            "target": StructuralTarget.edge_ref(
                source_node_id, target_node_id,
                source_output=source_output, target_input=target_input,
            ),
            "message": message or f"Edge from {source_node_id} to {target_node_id} must exist.",
        }
        base.update(kwargs)
        return cls(**base)

    @classmethod
    def terminal_output_domain(
        cls,
        obligation_id: str,
        domain: str,
        *,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create a ``terminal_output_domain`` obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN,
            "severity": severity,
            "expected": domain,
            "message": message or f"Terminal output domain must be {domain}.",
        }
        base.update(kwargs)
        return cls(**base)

    @classmethod
    def scope_preserved(
        cls,
        obligation_id: str,
        *,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create a ``scope_preserved`` obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_SCOPE_PRESERVED,
            "severity": severity,
            "message": message or "Scope graph must not lose pre-existing nodes or edges.",
        }
        base.update(kwargs)
        return cls(**base)

    @classmethod
    def obligation_declared(
        cls,
        obligation_id: str,
        *,
        severity: str = OBLIGATION_SEVERITY_REQUIRED,
        message: str = "",
        **kwargs: Any,
    ) -> "Obligation":
        """Create an ``obligation_declared`` meta-obligation."""
        base = {
            "obligation_id": obligation_id,
            "kind": OBLIGATION_KIND_OBLIGATION_DECLARED,
            "severity": severity,
            "message": message or f"Obligation {obligation_id} declared but not yet evaluated.",
        }
        base.update(kwargs)
        return cls(**base)


# -- Obligation ledger (aggregate) -------------------------------------------


@dataclass(frozen=True)
class ObligationLedger:
    """Aggregate collection of obligations for an agent-edit turn.

    The ledger is immutable, supports deterministic JSON serialization,
    and can compute a content hash for audit/replay verification.

    Parameters
    ----------
    obligations:
        Tuple of ``Obligation`` instances in stable order.
    contract_version:
        Schema version for serialization.
    turn_id:
        Optional turn identifier for cross-referencing.
    """

    obligations: tuple[Obligation, ...] = ()
    contract_version: str = OBLIGATION_LEDGER_CONTRACT_VERSION
    turn_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligations", tuple(self.obligations))

    # -- Queries -------------------------------------------------------------

    @property
    def required_obligations(self) -> tuple[Obligation, ...]:
        """Return only obligations whose severity is ``required``."""
        return tuple(o for o in self.obligations if o.is_required)

    @property
    def satisfied_obligations(self) -> tuple[Obligation, ...]:
        """Return obligations with status ``satisfied``."""
        return tuple(o for o in self.obligations if o.is_satisfied)

    @property
    def unsatisfied_obligations(self) -> tuple[Obligation, ...]:
        """Return obligations with status ``unsatisfied``."""
        return tuple(o for o in self.obligations if o.is_unsatisfied)

    @property
    def unknown_obligations(self) -> tuple[Obligation, ...]:
        """Return obligations with status ``unknown``."""
        return tuple(o for o in self.obligations if o.is_unknown)

    @property
    def not_evaluated_obligations(self) -> tuple[Obligation, ...]:
        """Return obligations with status ``not_evaluated``."""
        return tuple(o for o in self.obligations if o.is_not_evaluated)

    @property
    def unsupported_obligations(self) -> tuple[Obligation, ...]:
        """Return obligations with status ``unsupported``."""
        return tuple(o for o in self.obligations if o.is_unsupported)

    @property
    def all_required_satisfied(self) -> bool:
        """``True`` when every *required* obligation is ``satisfied``.

        ``unknown``, ``unsupported``, ``not_evaluated``, and
        ``unsatisfied`` all prevent this from returning ``True``.
        """
        required = self.required_obligations
        if not required:
            return True
        return all(o.status == OBLIGATION_STATUS_SATISFIED for o in required)

    @property
    def any_required_incomplete(self) -> bool:
        """``True`` when any *required* obligation is not ``satisfied``.

        This includes ``unknown``, ``unsupported``, ``not_evaluated``,
        and ``unsatisfied`` — the fail-closed posture.
        """
        required = self.required_obligations
        if not required:
            return False
        return any(o.status != OBLIGATION_STATUS_SATISFIED for o in required)

    @property
    def any_unknown(self) -> bool:
        """``True`` when any obligation has ``unknown`` status."""
        return any(o.is_unknown for o in self.obligations)

    @property
    def any_unsupported(self) -> bool:
        """``True`` when any obligation has ``unsupported`` status."""
        return any(o.is_unsupported for o in self.obligations)

    @property
    def any_not_evaluated(self) -> bool:
        """``True`` when any obligation has ``not_evaluated`` status."""
        return any(o.is_not_evaluated for o in self.obligations)

    def get(self, obligation_id: str) -> Obligation | None:
        """Return the obligation with *obligation_id*, or ``None``."""
        for o in self.obligations:
            if o.obligation_id == obligation_id:
                return o
        return None

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        payload: dict[str, Any] = {
            "contract_version": self.contract_version,
            "obligations": [o.to_dict() for o in self.obligations],
        }
        if self.turn_id is not None:
            payload["turn_id"] = self.turn_id
        return payload

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        _coerce: bool = True,
    ) -> "ObligationLedger":
        """Deserialize from a JSON-compatible dictionary."""
        raw_obligations = data.get("obligations", [])
        obligations: list[Obligation] = []
        if isinstance(raw_obligations, (list, tuple)):
            for item in raw_obligations:
                if isinstance(item, Mapping):
                    obligations.append(Obligation.from_dict(item, _coerce=_coerce))
        return cls(
            obligations=tuple(obligations),
            contract_version=str(
                data.get("contract_version", OBLIGATION_LEDGER_CONTRACT_VERSION)
            ),
            turn_id=data.get("turn_id") if isinstance(data.get("turn_id"), str) else None,
        )

    # -- Deterministic hashable serialization --------------------------------

    def to_json(self, *, indent: int | None = None, sort_keys: bool = True) -> str:
        """Serialize to a deterministic JSON string.

        Sorted keys guarantee identical output for identical data.
        """
        return json.dumps(self.to_dict(), indent=indent, sort_keys=sort_keys)

    def content_hash(self, *, algorithm: str = "sha256") -> str:
        """Return a deterministic content hash of the ledger.

        The hash covers the entire serialized obligation list in stable
        order, so identical ledgers produce identical hashes.
        """
        payload = self.to_json(sort_keys=True)
        h = hashlib.new(algorithm)
        h.update(payload.encode("utf-8"))
        return h.hexdigest()

    def json_roundtrip_stable(self) -> bool:
        """``True`` when serializing and re-parsing yields the same JSON."""
        first = self.to_json(sort_keys=True)
        reparsed = self.from_dict(json.loads(first))
        second = reparsed.to_json(sort_keys=True)
        return first == second

    # -- Factory helpers -----------------------------------------------------

    @classmethod
    def empty(cls) -> "ObligationLedger":
        """Return an empty ledger (no obligations)."""
        return cls(obligations=())


# -- Internal helpers --------------------------------------------------------


def _freeze_jsonish(value: Any) -> Any:
    """Recursively freeze JSON-like values to immutable forms."""
    from types import MappingProxyType

    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze_jsonish(value[key])
            for key in sorted(value, key=lambda item: str(item))
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_jsonish(item) for item in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    """Recursively thaw immutable frozen values back to JSON-safe types."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_jsonish(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, tuple):
        return [_thaw_jsonish(item) for item in value]
    if isinstance(value, list):
        return [_thaw_jsonish(item) for item in value]
    return value


def _omit_none(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return *payload* with ``None`` values removed."""
    return {key: value for key, value in payload.items() if value is not None}


__all__ = [
    "OBLIGATION_KIND_CLASS_PRESENT",
    "OBLIGATION_KIND_CLASS_ABSENT",
    "OBLIGATION_KIND_VALUE_MATCH",
    "OBLIGATION_KIND_EDGE_EXISTS",
    "OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN",
    "OBLIGATION_KIND_SCOPE_PRESERVED",
    "OBLIGATION_KIND_OBLIGATION_DECLARED",
    "OBLIGATION_KINDS",
    "OBLIGATION_STATUS_SATISFIED",
    "OBLIGATION_STATUS_UNSATISFIED",
    "OBLIGATION_STATUS_UNKNOWN",
    "OBLIGATION_STATUS_NOT_EVALUATED",
    "OBLIGATION_STATUS_UNSUPPORTED",
    "OBLIGATION_STATUSES",
    "OBLIGATION_SEVERITY_REQUIRED",
    "OBLIGATION_SEVERITY_RECOMMENDED",
    "OBLIGATION_SEVERITY_OPTIONAL",
    "OBLIGATION_SEVERITIES",
    "OBLIGATION_LEDGER_CONTRACT_VERSION",
    "Obligation",
    "ObligationLedger",
    "StructuralTarget",
    "is_satisfied",
    "is_unsatisfied",
    "is_unknown",
    "is_not_evaluated",
    "is_unsupported",
    "is_required",
]
