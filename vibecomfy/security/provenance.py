"""Provenance tagging for VibeNode metadata.

Provenance × Capability is the truth-table the S4 gate evaluates. This module
defines the provenance literal, the metadata key, and pure helpers to read,
tag, and confirm provenance on a node-like object exposing a ``metadata``
mapping. ``read`` is fail-closed: a missing or ``None`` value is treated as
``untrusted_source`` so untagged additions cannot leak as trusted.

This module is intentionally isolated — it does NOT import from
``vibecomfy.analysis``/``runtime``/``porting``/``registry`` (enforced by
``tests/security/test_no_cross_layer_import.py`` and the source-level regex
check in ``tests/security/test_capabilities.py``).
"""

from __future__ import annotations

from typing import Any, Literal, get_args

Provenance = Literal[
    "untrusted_source",
    "agent_authored",
    "agent_generated",
    "user_confirmed",
]

PROVENANCE_KEY = "provenance"

_VALID: frozenset[str] = frozenset(get_args(Provenance))


def read(node: Any) -> Provenance:
    """Return the provenance tag on ``node``.

    Fail-closed: missing key, ``None``, or an unrecognized value all return
    ``"untrusted_source"``. This unifies the gate, taint dump, and doctor
    behavior on untagged nodes per SD3.
    """
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, dict):
        return "untrusted_source"
    value = metadata.get(PROVENANCE_KEY)
    if value in _VALID:
        return value  # type: ignore[return-value]
    return "untrusted_source"


def tag(node: Any, value: Provenance) -> None:
    """Set ``node.metadata[PROVENANCE_KEY] = value``.

    Raises ``ValueError`` for values outside the ``Provenance`` literal so
    callers cannot silently widen the taxonomy.
    """
    if value not in _VALID:
        raise ValueError(
            f"invalid provenance {value!r}; expected one of {sorted(_VALID)}"
        )
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, dict):
        raise TypeError("node.metadata must be a dict to tag provenance")
    metadata[PROVENANCE_KEY] = value


def confirm(node: Any) -> None:
    """Promote ``untrusted_source`` → ``user_confirmed``; never raises.

    Idempotent no-op on trusted or restricted-loader tags that must not be
    silently promoted by confirmation helpers. A node whose metadata is missing
    or non-dict is left untouched.
    """
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, dict):
        return
    current = metadata.get(PROVENANCE_KEY)
    if current in ("user_confirmed", "agent_authored", "agent_generated"):
        return
    metadata[PROVENANCE_KEY] = "user_confirmed"


__all__ = ["Provenance", "PROVENANCE_KEY", "read", "tag", "confirm"]
