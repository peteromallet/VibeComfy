"""Second comparator selection for the two-step comparison harness (B07 Flash).

The two paired lanes are:

1. the 50-scenario lane pinned by ``two_step_50_manifest.json`` (Pro B07), and
2. the 57-id exit-failure ledger lane — ``ledger_scenario_ids()`` from
   ``vibecomfy.intent._ledger`` (the ONLY 57-failure owner ledger).

The ledger lane's run label is resolved here.  The ONLY valid labels are
``current`` (stable alias, what operators should type) and
``ir-everywhere-57-v3`` (the canonical post-migration artifact).  The legacy
labels ``ir-everywhere-57`` (v1: imported the recovery-run package via
cwd-on-sys.path) and ``ir-everywhere-57-v2`` (v2: measured a dirty moving
tree) are INVALID per the ledger module docstring and must never be emitted
or accepted for reconciliation.

This module is Flash-owned so the Pro comparator (``compare_pipeline_modes.py``)
can import the label contract without re-deriving it.
"""

from __future__ import annotations

from vibecomfy.intent._ledger import (
    LEDGER_ID_COUNT,
    assert_ledger_integrity,
    ledger_scenario_ids,
)

LEDGER_LABEL_CURRENT = "current"
"""Operator-facing stable alias for the current ledger artifact."""

LEDGER_ARTIFACT_LABEL = "ir-everywhere-57-v3"
"""The only valid post-migration ledger artifact label."""

INVALID_LEGACY_LEDGER_LABELS = frozenset({"ir-everywhere-57", "ir-everywhere-57-v2"})
"""Legacy labels that must never be used (v1/v2 per the ledger docstring)."""

_VALID_LEDGER_LABELS = frozenset({LEDGER_LABEL_CURRENT, LEDGER_ARTIFACT_LABEL})


class LedgerLabelError(ValueError):
    """Raised when a ledger label is unknown or a legacy invalid label."""


def resolve_ledger_label(label: str | None) -> str:
    """Resolve a ledger label to the canonical artifact label.

    ``None`` and ``"current"`` map to ``"ir-everywhere-57-v3"``;
    ``"ir-everywhere-57-v3"`` is accepted as-is.  The invalid legacy labels
    ``"ir-everywhere-57"`` / ``"ir-everywhere-57-v2"`` and any unknown value
    raise :class:`LedgerLabelError` — an operator typo must fail loudly
    instead of silently reconciling against the wrong artifact.
    """
    if label is None or label == LEDGER_LABEL_CURRENT:
        return LEDGER_ARTIFACT_LABEL
    if label == LEDGER_ARTIFACT_LABEL:
        return label
    if label in INVALID_LEGACY_LEDGER_LABELS:
        raise LedgerLabelError(
            f"ledger label {label!r} is an INVALID legacy label; use "
            f"{LEDGER_LABEL_CURRENT!r} or {LEDGER_ARTIFACT_LABEL!r}."
        )
    raise LedgerLabelError(
        f"unknown ledger label {label!r}; expected {LEDGER_LABEL_CURRENT!r} "
        f"or {LEDGER_ARTIFACT_LABEL!r}."
    )


def ledger_selection_ids() -> tuple[str, ...]:
    """Return the ledger lane's scenario ids: ``ledger_scenario_ids()``.

    The selection is the ledger itself — this re-export exists so the
    comparator and tests import one stable name and the integrity invariants
    (57 unique ids) are enforced at the single source.
    """
    assert_ledger_integrity()
    ids = ledger_scenario_ids()
    assert len(ids) == LEDGER_ID_COUNT, (
        f"ledger_scenario_ids() returned {len(ids)} ids, expected {LEDGER_ID_COUNT}"
    )
    return ids


__all__ = [
    "INVALID_LEGACY_LEDGER_LABELS",
    "LEDGER_ARTIFACT_LABEL",
    "LEDGER_ID_COUNT",
    "LEDGER_LABEL_CURRENT",
    "LedgerLabelError",
    "ledger_scenario_ids",
    "ledger_selection_ids",
    "resolve_ledger_label",
]
