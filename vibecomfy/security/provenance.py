"""Provenance tagging for VibeNode metadata — closed lattice (Law 5, batch 5).

Provenance × Capability is the truth-table the S4 gate evaluates. This module
defines the closed provenance taxonomy as a typed :class:`Provenance` enum, a
**monotone ordering** (which provenance dominates which — the taint order) and
a **join** (max-taint of inputs), plus pure helpers to read, tag, and confirm
provenance on a node-like object exposing a ``metadata`` mapping. ``read`` is
fail-closed: a missing or ``None`` value is treated as ``untrusted_source`` so
untagged additions cannot leak as trusted.

The lattice semantics (Law 5, batch 5):

* **Closed set** — ``Provenance`` is the exhaustive taxonomy; ``tag`` rejects
  anything outside it, so callers cannot silently widen the set.
* **Monotone ordering** — ``dominates(a, b)`` is the taint partial order
  (here a total order). ``untrusted_source`` is the TOP (max taint): any input
  tainted untrusted keeps the whole result untrusted, so taint can never be
  laundered by an agent edit.
* **Join (max-taint)** — ``join(*values)`` returns the most tainted operand.
  Edits compose the provenance of their operands through ``join``, so a node
  edited from an untrusted-source graph by an agent stays untrusted — it is
  never silently downgraded. ``confirm`` remains the ONLY explicit promotion
  (``untrusted_source`` → ``user_confirmed``) and is idempotent on every other
  tag, exactly as the S4 promotion table requires.

This module is intentionally isolated — it does NOT import from
``vibecomfy.analysis``/``runtime``/``porting``/``registry`` (enforced by
``tests/security/test_no_cross_layer_import.py`` and the source-level regex
check in ``tests/security/test_capabilities.py``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

PROVENANCE_KEY = "provenance"

# Agent edit-tag: the provenance an agent edit contributes when it composes an
# IR node (used by the copy-on-write edit helpers in ``porting.edit``).
_AGENT_EDIT_TAG = "agent_generated"


class Provenance(str, Enum):
    """Closed provenance taxonomy (S4), ordered by taint (ascending).

    Members compare equal to their plain-string values (``str`` enum), so
    existing ``read(node) == "untrusted_source"`` assertions keep working.
    Iterating the class yields members in declaration order.
    """

    USER_CONFIRMED = "user_confirmed"
    AGENT_AUTHORED = "agent_authored"
    AGENT_GENERATED = "agent_generated"
    UNTRUSTED_SOURCE = "untrusted_source"


# Taint order: index 0 is the least tainted, the highest index is the max
# taint. ``untrusted_source`` is deliberately the TOP so max-taint joins can
# never wash untrusted input through a trusted tag (fail-closed S4 semantics).
_TAINT_ORDER: dict[Provenance, int] = {
    Provenance.USER_CONFIRMED: 0,
    Provenance.AGENT_AUTHORED: 1,
    Provenance.AGENT_GENERATED: 2,
    Provenance.UNTRUSTED_SOURCE: 3,
}

_VALID: frozenset[Provenance] = frozenset(Provenance)
_VALID_STRINGS: frozenset[str] = frozenset(member.value for member in Provenance)


def coerce(value: Any) -> Provenance:
    """Normalize a raw value (string, enum member, ``None``) to ``Provenance``.

    Fail-closed: anything unrecognized — including ``None`` and hostile
    strings — maps to ``untrusted_source`` so unknown tags can never gain an
    implicit trust path.
    """
    if isinstance(value, Provenance):
        return value
    if isinstance(value, str) and value in _VALID_STRINGS:
        return Provenance(value)
    return Provenance.UNTRUSTED_SOURCE


def dominates(a: Any, b: Any) -> bool:
    """Return whether provenance ``a`` dominates ``b`` in the taint order.

    ``a`` dominates ``b`` when ``a`` is at least as tainted as ``b``
    (``taint(a) >= taint(b)``). The ordering is a partial order (here a total
    order over the closed set): reflexive, antisymmetric, transitive.
    """
    return _TAINT_ORDER[coerce(a)] >= _TAINT_ORDER[coerce(b)]


def join(*values: Any) -> Provenance:
    """Join (max-taint) of the operand provenances.

    Returns the most tainted operand; the empty join fails closed to
    ``untrusted_source``. ``join`` is idempotent, commutative, associative,
    and monotone — the laws the edit engine relies on: an edit that combines
    inputs of different provenances tags its result with ``join`` of the
    operands and never downgrades any operand's taint.
    """
    if not values:
        return Provenance.UNTRUSTED_SOURCE
    return max((coerce(value) for value in values), key=_TAINT_ORDER.__getitem__)


def read(node: Any) -> Provenance:
    """Return the provenance tag on ``node`` as a typed ``Provenance`` member.

    Fail-closed: missing key, ``None``, or an unrecognized value all return
    ``Provenance.UNTRUSTED_SOURCE``. This unifies the gate, taint dump, and
    doctor behavior on untagged nodes per SD3. The member compares equal to
    its string value, so ``read(node) == "untrusted_source"`` still holds.
    """
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, dict):
        return Provenance.UNTRUSTED_SOURCE
    return coerce(metadata.get(PROVENANCE_KEY))


def tag(node: Any, value: Any) -> None:
    """Set ``node.metadata[PROVENANCE_KEY]`` to the typed provenance.

    Raises ``ValueError`` for values outside the closed ``Provenance`` set so
    callers cannot silently widen the taxonomy. Accepts plain strings of a
    known provenance (normalized to the enum member).
    """
    if isinstance(value, str) and value in _VALID_STRINGS:
        value = Provenance(value)
    if not isinstance(value, Provenance):
        raise ValueError(
            f"invalid provenance {value!r}; expected one of {sorted(_VALID_STRINGS)}"
        )
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, dict):
        raise TypeError("node.metadata must be a dict to tag provenance")
    metadata[PROVENANCE_KEY] = value


def confirm(node: Any) -> None:
    """Promote ``untrusted_source`` → ``user_confirmed``; never raises.

    Idempotent no-op on trusted or restricted-loader tags that must not be
    silently promoted by confirmation helpers. A node whose metadata is missing
    or non-dict is left untouched. ``confirm`` is the only explicit promotion;
    it is NOT the lattice join (agent edits compose via :func:`join`).
    """
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, dict):
        return
    current = metadata.get(PROVENANCE_KEY)
    if current in (
        Provenance.USER_CONFIRMED,
        Provenance.AGENT_AUTHORED,
        Provenance.AGENT_GENERATED,
        "user_confirmed",
        "agent_authored",
        "agent_generated",
    ):
        return
    metadata[PROVENANCE_KEY] = Provenance.USER_CONFIRMED


__all__ = [
    "PROVENANCE_KEY",
    "Provenance",
    "_AGENT_EDIT_TAG",
    "coerce",
    "confirm",
    "dominates",
    "join",
    "read",
    "tag",
]
