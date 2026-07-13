"""Independent completion proof artifacts for agent-edit turns.

Each proof domain reports its own four-state result independently so
that callers never treat missing or absent proof as success.

Proof domains
-------------
* ``transformation_safety`` — whether the candidate graph is safe to
  apply (no forbidden nodes, no broken connections, no data loss).
* ``graph_validity`` — whether the candidate graph is structurally
  valid (DAG, no cycles, all links resolvable).
* ``task_satisfaction`` — whether the candidate graph satisfies the
  declared task obligations (required nodes present, conditions met).
* ``runtime_readiness`` — whether all required node types are
  installed and compatible with the current runtime.

Proof states
------------
* ``pass`` — the proof was evaluated and the domain is satisfied.
* ``fail`` — the proof was evaluated and the domain is not satisfied.
* ``not_run`` — the proof was intentionally skipped (e.g. non-applyable
  route where the check is not applicable).
* ``unknown`` — the proof was expected but not available; this is the
  fail-closed default.  Missing proof is *never* success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# -- Proof states -----------------------------------------------------------

PROOF_STATE_PASS: str = "pass"
PROOF_STATE_FAIL: str = "fail"
PROOF_STATE_NOT_RUN: str = "not_run"
PROOF_STATE_UNKNOWN: str = "unknown"

PROOF_STATES: tuple[str, ...] = (
    PROOF_STATE_PASS,
    PROOF_STATE_FAIL,
    PROOF_STATE_NOT_RUN,
    PROOF_STATE_UNKNOWN,
)

# -- Proof domains ----------------------------------------------------------

PROOF_DOMAIN_TRANSFORMATION_SAFETY: str = "transformation_safety"
PROOF_DOMAIN_GRAPH_VALIDITY: str = "graph_validity"
PROOF_DOMAIN_TASK_SATISFACTION: str = "task_satisfaction"
PROOF_DOMAIN_RUNTIME_READINESS: str = "runtime_readiness"

PROOF_DOMAINS: tuple[str, ...] = (
    PROOF_DOMAIN_TRANSFORMATION_SAFETY,
    PROOF_DOMAIN_GRAPH_VALIDITY,
    PROOF_DOMAIN_TASK_SATISFACTION,
    PROOF_DOMAIN_RUNTIME_READINESS,
)

# -- Contract version -------------------------------------------------------

COMPLETION_PROOF_CONTRACT_VERSION: str = "completion_proof_v1"

# -- Domain label mappings (human-readable) ----------------------------------

PROOF_DOMAIN_LABELS: Mapping[str, str] = {
    PROOF_DOMAIN_TRANSFORMATION_SAFETY: "transformation_safety",
    PROOF_DOMAIN_GRAPH_VALIDITY: "graph_validity",
    PROOF_DOMAIN_TASK_SATISFACTION: "task_satisfaction",
    PROOF_DOMAIN_RUNTIME_READINESS: "runtime_readiness",
}

# -- Helpers ----------------------------------------------------------------


def _validate_state(state: str, domain: str) -> None:
    """Raise ``ValueError`` when *state* is not a recognised proof state."""
    if state not in PROOF_STATES:
        raise ValueError(
            f"Proof state {state!r} for domain {domain!r} must be one of "
            f"{PROOF_STATES}."
        )


def is_pass(state: str) -> bool:
    """Return ``True`` when *state* is ``pass``."""
    return state == PROOF_STATE_PASS


def is_fail(state: str) -> bool:
    """Return ``True`` when *state* is ``fail``."""
    return state == PROOF_STATE_FAIL


def is_not_run(state: str) -> bool:
    """Return ``True`` when *state* is ``not_run``."""
    return state == PROOF_STATE_NOT_RUN


def is_unknown(state: str) -> bool:
    """Return ``True`` when *state* is ``unknown``."""
    return state == PROOF_STATE_UNKNOWN


def is_success(state: str) -> bool:
    """Return ``True`` only when *state* is an explicit ``pass``.

    Missing / ``unknown`` / ``not_run`` / ``fail`` are *never* success.
    """
    return state == PROOF_STATE_PASS


# -- CompletionProof dataclass ----------------------------------------------


@dataclass(frozen=True)
class CompletionProof:
    """Independent four-domain completion proof for an agent-edit turn.

    Every domain reports exactly one of ``pass``, ``fail``, ``not_run``,
    or ``unknown``.  Missing or absent proof is represented as
    ``unknown`` — the fail-closed default.

    Parameters
    ----------
    transformation_safety:
        Whether the candidate graph is safe to apply.
    graph_validity:
        Whether the candidate graph is structurally valid.
    task_satisfaction:
        Whether declared task obligations are satisfied.
    runtime_readiness:
        Whether required node types are installed and compatible.
    contract_version:
        Schema version for serialization.
    evidence:
        Optional per-domain evidence payloads (e.g. failure reasons).
    """

    transformation_safety: str = PROOF_STATE_UNKNOWN
    graph_validity: str = PROOF_STATE_UNKNOWN
    task_satisfaction: str = PROOF_STATE_UNKNOWN
    runtime_readiness: str = PROOF_STATE_UNKNOWN
    contract_version: str = COMPLETION_PROOF_CONTRACT_VERSION
    evidence: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for domain in PROOF_DOMAINS:
            _validate_state(getattr(self, domain), domain)
        if self.evidence is not None and not isinstance(self.evidence, Mapping):
            object.__setattr__(self, "evidence", dict(self.evidence))

    # -- Domain accessors ---------------------------------------------------

    @property
    def transformation_safety_pass(self) -> bool:
        """True when transformation safety proof is ``pass``."""
        return self.transformation_safety == PROOF_STATE_PASS

    @property
    def transformation_safety_fail(self) -> bool:
        """True when transformation safety proof is ``fail``."""
        return self.transformation_safety == PROOF_STATE_FAIL

    @property
    def graph_validity_pass(self) -> bool:
        """True when graph validity proof is ``pass``."""
        return self.graph_validity == PROOF_STATE_PASS

    @property
    def graph_validity_fail(self) -> bool:
        """True when graph validity proof is ``fail``."""
        return self.graph_validity == PROOF_STATE_FAIL

    @property
    def task_satisfaction_pass(self) -> bool:
        """True when task satisfaction proof is ``pass``."""
        return self.task_satisfaction == PROOF_STATE_PASS

    @property
    def task_satisfaction_fail(self) -> bool:
        """True when task satisfaction proof is ``fail``."""
        return self.task_satisfaction == PROOF_STATE_FAIL

    @property
    def runtime_readiness_pass(self) -> bool:
        """True when runtime readiness proof is ``pass``."""
        return self.runtime_readiness == PROOF_STATE_PASS

    @property
    def runtime_readiness_fail(self) -> bool:
        """True when runtime readiness proof is ``fail``."""
        return self.runtime_readiness == PROOF_STATE_FAIL

    # -- Aggregate queries --------------------------------------------------

    @property
    def all_pass(self) -> bool:
        """True when every domain is ``pass``."""
        return all(
            getattr(self, domain) == PROOF_STATE_PASS for domain in PROOF_DOMAINS
        )

    @property
    def any_fail(self) -> bool:
        """True when any domain is ``fail``."""
        return any(
            getattr(self, domain) == PROOF_STATE_FAIL for domain in PROOF_DOMAINS
        )

    @property
    def any_unknown(self) -> bool:
        """True when any domain is ``unknown`` (including missing)."""
        return any(
            getattr(self, domain) == PROOF_STATE_UNKNOWN for domain in PROOF_DOMAINS
        )

    @property
    def any_not_run(self) -> bool:
        """True when any domain is ``not_run``."""
        return any(
            getattr(self, domain) == PROOF_STATE_NOT_RUN for domain in PROOF_DOMAINS
        )

    def domain_state(self, domain: str) -> str:
        """Return the proof state for *domain* (one of ``PROOF_DOMAINS``)."""
        if domain not in PROOF_DOMAINS:
            raise ValueError(
                f"Unknown proof domain {domain!r}; expected one of {PROOF_DOMAINS}."
            )
        return getattr(self, domain)

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        payload: dict[str, Any] = {
            "contract_version": self.contract_version,
            "transformation_safety": self.transformation_safety,
            "graph_validity": self.graph_validity,
            "task_satisfaction": self.task_satisfaction,
            "runtime_readiness": self.runtime_readiness,
        }
        if self.evidence is not None:
            payload["evidence"] = dict(self.evidence)
        return payload

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        _coerce: bool = True,
    ) -> "CompletionProof":
        """Deserialize from a JSON-compatible dictionary.

        When *_coerce* is ``True`` (default), unknown or absent state
        values are normalized to ``unknown`` rather than raising.
        Missing domains also default to ``unknown``.
        """
        states: dict[str, str] = {}
        for domain in PROOF_DOMAINS:
            raw = data.get(domain)
            if isinstance(raw, str) and raw in PROOF_STATES:
                states[domain] = raw
            elif _coerce:
                states[domain] = PROOF_STATE_UNKNOWN
            else:
                raw_str = str(raw) if raw is not None else "None"
                raise ValueError(
                    f"Invalid proof state {raw_str!r} for domain {domain!r}; "
                    f"expected one of {PROOF_STATES}."
                )
        evidence = data.get("evidence")
        return cls(
            transformation_safety=states[PROOF_DOMAIN_TRANSFORMATION_SAFETY],
            graph_validity=states[PROOF_DOMAIN_GRAPH_VALIDITY],
            task_satisfaction=states[PROOF_DOMAIN_TASK_SATISFACTION],
            runtime_readiness=states[PROOF_DOMAIN_RUNTIME_READINESS],
            contract_version=str(
                data.get("contract_version", COMPLETION_PROOF_CONTRACT_VERSION)
            ),
            evidence=dict(evidence) if isinstance(evidence, Mapping) else None,
        )

    @classmethod
    def fail_closed_default(cls) -> "CompletionProof":
        """Return a proof with all domains set to ``unknown``.

        This is the fail-closed default: missing proof is never success.
        """
        return cls(
            transformation_safety=PROOF_STATE_UNKNOWN,
            graph_validity=PROOF_STATE_UNKNOWN,
            task_satisfaction=PROOF_STATE_UNKNOWN,
            runtime_readiness=PROOF_STATE_UNKNOWN,
        )

    @classmethod
    def all_not_run(cls) -> "CompletionProof":
        """Return a proof with all domains set to ``not_run``.

        Useful for non-applyable routes where proof is intentionally skipped.
        """
        return cls(
            transformation_safety=PROOF_STATE_NOT_RUN,
            graph_validity=PROOF_STATE_NOT_RUN,
            task_satisfaction=PROOF_STATE_NOT_RUN,
            runtime_readiness=PROOF_STATE_NOT_RUN,
        )

    @classmethod
    def create_all_pass(cls) -> "CompletionProof":
        """Return a proof with all domains set to ``pass``."""
        return cls(
            transformation_safety=PROOF_STATE_PASS,
            graph_validity=PROOF_STATE_PASS,
            task_satisfaction=PROOF_STATE_PASS,
            runtime_readiness=PROOF_STATE_PASS,
        )


__all__ = [
    "COMPLETION_PROOF_CONTRACT_VERSION",
    "CompletionProof",
    "PROOF_DOMAIN_GRAPH_VALIDITY",
    "PROOF_DOMAIN_RUNTIME_READINESS",
    "PROOF_DOMAIN_TASK_SATISFACTION",
    "PROOF_DOMAIN_TRANSFORMATION_SAFETY",
    "PROOF_DOMAIN_LABELS",
    "PROOF_DOMAINS",
    "PROOF_STATE_FAIL",
    "PROOF_STATE_NOT_RUN",
    "PROOF_STATE_PASS",
    "PROOF_STATE_UNKNOWN",
    "PROOF_STATES",
    "is_fail",
    "is_not_run",
    "is_pass",
    "is_success",
    "is_unknown",
]
