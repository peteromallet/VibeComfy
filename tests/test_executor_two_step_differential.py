"""B06 (Pro) — two-step / full differential harness tests.

Every scenario drives BOTH executor pipeline modes with the SAME locked
:class:`ClassifyDecision` (injected via the test-only ``_run_classify`` seam —
no new production classifier API), then asserts the prose-free invariants:

* the editable quotient ``pi_edit(post)`` is identical across modes;
* the two-step accepted-Δ replay reconstructs that same quotient;
* evidence is valid and identical across modes;
* the failure family is consistent when the shared classify phase fails;
* latency / tokens / cost are captured (non-negative / comparable).

Prose (``reply``) is deliberately NEVER compared — the two modes are stubbed
to produce different reply strings, and the invariants still hold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.executor import core as executor_core
from vibecomfy.executor import two_step as two_step_module
from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
from vibecomfy.intent._ledger import (
    LEDGER_ID_COUNT,
    assert_ledger_integrity,
    ledger_scenario_ids,
)

from tests.executor_mode_harness import (
    SCENARIOS,
    ModeRun,
    Scenario,
    run_both,
    to_workflow,
    _pi_edit_or_none,
)

REPO_ROOT = Path(__file__).parents[1]
SCENARIO_MANIFEST = REPO_ROOT / "tests" / "live_agentic_harness" / "scenario_manifest.json"


def _scenario_by_name(name: str) -> Scenario:
    return next(s for s in SCENARIOS if s.name == name)


# ── the core differential invariant ──────────────────────────────────────────


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_both_modes_converge_on_same_editable_quotient(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    full, two = run_both(scenario, monkeypatch, tmp_path)

    # Both modes succeed for these deterministic scenarios.
    assert full.ok is True
    assert two.ok is True

    # NEVER compare prose: the two stubs intentionally produce different reply
    # strings; only the editable quotient (π_edit) is compared below.
    assert full.failure_kind is None and two.failure_kind is None

    # π_edit(post) is invariant across modes.
    assert full.pi_edit_quotient == two.pi_edit_quotient

    # The accepted-Δ replay reconstructs the same quotient as the full-mode
    # hand-authored post graph (the canonical Δ is the two-step authority).
    if scenario.delta_ops:
        assert two.replayed_quotient is not None
        assert two.replayed_quotient == full.pi_edit_quotient
        assert two.accepted_delta_ops == scenario.delta_ops
    else:
        assert two.accepted_delta_ops == ()

    # Evidence validity + cross-mode evidence identity.
    assert full.evidence_ids == two.evidence_ids == scenario.evidence_ids
    assert two.evidence_valid is True

    # Latency / tokens / cost are captured and sane (no prose involved).
    assert full.latency_s >= 0.0
    assert two.latency_s >= 0.0
    assert full.tokens >= 0 and two.tokens >= 0
    assert full.cost_usd is None or full.cost_usd >= 0.0
    assert two.cost_usd is None or two.cost_usd >= 0.0


def test_edit_scenarios_actually_change_the_quotient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Edit scenarios must move π_edit away from the base; furniture must not."""
    for scenario in SCENARIOS:
        if not scenario.delta_ops or scenario.route in {"reorganise"}:
            continue
        full, two = run_both(scenario, monkeypatch, tmp_path)
        base_quotient = _pi_edit_or_none(to_workflow(scenario.base_raw))
        assert full.pi_edit_quotient is not None
        assert full.pi_edit_quotient != base_quotient
        assert two.pi_edit_quotient == full.pi_edit_quotient


def test_reorganise_is_furniture_and_does_not_change_quotient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pure layout reorganisation (positional furniture) changes the raw
    bytes but never the editable quotient."""
    scenario = _scenario_by_name("reorganise")
    full, two = run_both(scenario, monkeypatch, tmp_path)
    base_quotient = _pi_edit_or_none(to_workflow(scenario.base_raw))
    assert full.pi_edit_quotient == base_quotient
    assert two.pi_edit_quotient == base_quotient
    # The raw graph DID change (the position moved) — only the quotient is stable.
    assert full.post_workflow is not None
    assert two.post_workflow is not None


def test_non_edit_routes_produce_no_graph_in_either_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("inspect", "research"):
        scenario = _scenario_by_name(name)
        full, two = run_both(scenario, monkeypatch, tmp_path)
        assert full.post_workflow is None
        assert two.post_workflow is None
        assert full.pi_edit_quotient is None
        assert two.pi_edit_quotient is None


# ── failure family is consistent across modes ────────────────────────────────


def test_shared_classify_failure_surfaces_identical_failure_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the SHARED classify phase fails, both modes report the same
    failure kind + stage (the failure family is mode-independent)."""

    def failing_classify(request: ExecutorRequest, spec: object, **kwargs: object) -> object:
        del request, spec, kwargs
        raise executor_core._ExecutorPhaseError(
            stage="classify",
            failure_kind="ValidationError",
            message="deterministic classify failure",
        )

    monkeypatch.setattr(executor_core, "_run_classify", failing_classify)
    # Classify fails before any mode dispatch; both modes must fail identically.
    results = {
        mode: executor_core.run_executor(
            ExecutorRequest(
                query="q",
                graph={"nodes": []},
                pipeline_mode=mode,
                session_id="win-x" if mode == "two_step" else None,
            )
        )
        for mode in ("full", "two_step")
    }
    kinds = {r.failure_kind for r in results.values()}
    stages = {r.failure_stage for r in results.values()}
    assert results["full"].ok is False
    assert results["two_step"].ok is False
    assert kinds == {"ValidationError"}
    assert stages == {"classify"}


# ── 57-id ledger resolution + inventory ──────────────────────────────────────


def _manifest_entries() -> list[dict]:
    raw = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))
    entries = raw.get("entries")
    assert isinstance(entries, list), "scenario manifest must carry an `entries` list"
    return [e for e in entries if isinstance(e, dict)]


def test_ledger_57_ids_are_unique_and_manifested() -> None:
    """Resolve + inventory all 57 ledger ids; refuse duplicate/missing/
    unmanifested ids."""
    assert_ledger_integrity()
    ids = ledger_scenario_ids()
    assert len(ids) == LEDGER_ID_COUNT == 57
    # Refuse duplicates.
    assert len(ids) == len(set(ids)), "ledger scenario ids must be unique"

    entries = _manifest_entries()
    # Refuse duplicate manifest ids.
    manifest_ids = [e.get("id") for e in entries if e.get("id")]
    assert len(manifest_ids) == len(set(manifest_ids)), "manifest ids must be unique"
    manifest_by_id = {e["id"]: e for e in entries if e.get("id")}

    # Refuse missing (not in manifest) and unmanifested (path absent) ids.
    missing = sorted(set(ids) - set(manifest_by_id))
    assert missing == [], f"ledger ids missing from the scenario manifest: {missing}"

    unmanifested: list[str] = []
    for sid in ids:
        entry = manifest_by_id[sid]
        path = entry.get("path")
        if not isinstance(path, str) or not (REPO_ROOT / path).is_file():
            unmanifested.append(sid)
    assert unmanifested == [], f"ledger ids without a scenario artifact: {unmanifested}"


def test_ledger_ids_do_not_overlap_across_families() -> None:
    """Every ledger id is owned by exactly one family row (no cross-family dup)."""
    from vibecomfy.intent._ledger import EXIT_FAILURE_LEDGER

    seen: dict[str, str] = {}
    for row in EXIT_FAILURE_LEDGER:
        for sid in row.scenario_ids:
            if sid in seen:
                pytest.fail(f"ledger id {sid!r} owned by {seen[sid]!r} and {row.family!r}")
            seen[sid] = row.family
    assert len(seen) == 57
