"""Felt-fidelity gate helpers built on top of existing layout drift primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.porting.layout.layout_vector import layout_drift, layout_vector
from vibecomfy.porting.layout.reconcile import ChangeReport


@dataclass(frozen=True)
class FeltDeltaViolation:
    """One preserved-node fidelity failure."""

    uid: str
    reason: str
    prior_pos: list[float] | None
    current_pos: list[float] | None
    delta_px: float | None


@dataclass(frozen=True)
class LatencyBudgetReport:
    """Optional latency metadata carried alongside felt results."""

    elapsed_ms: float
    budget_ms: float
    ok: bool


@dataclass(frozen=True)
class FeltDeltaReport:
    """Summary of whether preserved layout fidelity held for an emit."""

    ok: bool
    violations: list[FeltDeltaViolation] = field(default_factory=list)
    summary: str = ""
    skipped_snapshot_absent: bool = False
    latency: LatencyBudgetReport | None = None


def evaluate_felt_delta(
    prior_store: dict[str, Any] | None,
    emitted_ui: dict[str, Any],
    change_report: ChangeReport,
    *,
    reroute_uids: frozenset[str] = frozenset(),
    position_tolerance_px: float = 0.0,
    latency_report: LatencyBudgetReport | None = None,
) -> FeltDeltaReport:
    """Evaluate whether preserved untouched nodes kept their editor placement."""

    prior_entries = prior_store.get("entries", {}) if isinstance(prior_store, dict) else {}
    preserved = sorted(set(change_report.content_edits.preserved))
    edited = change_report.content_edits.edited

    if prior_store is None:
        return FeltDeltaReport(
            ok=True,
            summary="felt gate skipped: no prior layout store available",
            latency=latency_report,
        )

    if prior_entries and preserved and not edited:
        return FeltDeltaReport(
            ok=True,
            summary="felt gate skipped: ingest snapshot absent; preserved nodes are unclassified",
            skipped_snapshot_absent=True,
            latency=latency_report,
        )

    if not prior_entries or not preserved:
        return FeltDeltaReport(
            ok=True,
            summary="felt gate passed: no preserved nodes required position checks",
            latency=latency_report,
        )

    before_vector = _prior_entries_to_layout_vector(prior_entries)
    after_vector = layout_vector(emitted_ui)

    preserved_before = {
        uid: before_vector[uid]
        for uid in preserved
        if uid in before_vector
    }
    preserved_after = {
        uid: after_vector[uid]
        for uid in preserved
        if uid in after_vector
    }
    drift = layout_drift(preserved_before, preserved_after)

    violations: list[FeltDeltaViolation] = []

    for uid, diff in sorted(drift.per_key_diff.items()):
        pos_delta = float(diff["pos_delta"])
        if pos_delta <= position_tolerance_px:
            continue
        before = diff["before"]["pos"]
        after = diff["after"]["pos"]
        violations.append(
            FeltDeltaViolation(
                uid=uid,
                reason="position_moved",
                prior_pos=[float(before[0]), float(before[1])],
                current_pos=[float(after[0]), float(after[1])],
                delta_px=pos_delta,
            )
        )

    missing_reroutes = sorted(
        uid
        for uid in preserved
        if uid in reroute_uids and uid in before_vector and uid not in after_vector
    )
    for uid in missing_reroutes:
        before = before_vector[uid]["pos"]
        violations.append(
            FeltDeltaViolation(
                uid=uid,
                reason="reroute_disappeared",
                prior_pos=[float(before[0]), float(before[1])],
                current_pos=None,
                delta_px=None,
            )
        )

    violations.sort(key=lambda item: (item.reason, item.uid))
    if violations:
        summary = f"felt gate failed: {len(violations)} preserved-node fidelity violation(s)"
    else:
        checked = len(preserved_before)
        summary = f"felt gate passed: {checked} preserved node(s) kept their layout"

    return FeltDeltaReport(
        ok=not violations,
        violations=violations,
        summary=summary,
        latency=latency_report,
    )


def _prior_entries_to_layout_vector(
    entries: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Normalize prior-store entries into the layout_vector/layout_drift shape."""

    vector: dict[str, dict[str, Any]] = {}
    for uid, entry in entries.items():
        raw_pos = entry.get("pos") or [0.0, 0.0]
        raw_size = entry.get("size") or [0.0, 0.0]
        vector[uid] = {
            "pos": [float(raw_pos[0]), float(raw_pos[1])],
            "size": [float(raw_size[0]), float(raw_size[1])],
            "group": entry.get("group"),
            "mode": int(entry.get("mode", 0)),
            "key_kind": "uid",
        }
    return vector
