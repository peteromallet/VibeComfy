"""B06 (Pro) — two-step / full differential harness tests.

Every scenario drives BOTH executor pipeline modes with the SAME locked
:class:`ClassifyDecision` (injected via the test-only ``_run_classify`` seam —
no new production classifier API), then asserts the prose-free invariants:

* the editable quotient ``pi_edit(post)`` is identical across modes;
* the two-step post graph and the accepted-Δ replay BOTH come from the store
  (``TwoStepSessionStore.load`` + ``accepted_delta_refs[].ops`` +
  ``replay_workflow`` / ``retained_workflow``) — never from the fixture;
* the fixture ``scenario.delta_ops`` is used ONLY as an oracle: the ACTUAL
  accepted ops must produce the same quotient (form may differ, quotient may
  not — e.g. typed ``edit_node(field="prompt")`` records a named field while
  the fixture spells ``widgets_values``);
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
from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest, ExecutorResult
from vibecomfy.executor.two_step_session import TwoStepSessionStore
from vibecomfy.intent._ledger import (
    LEDGER_ID_COUNT,
    assert_ledger_integrity,
    ledger_scenario_ids,
)

from tests.executor_mode_harness import (
    SCENARIOS,
    ModeRun,
    Scenario,
    apply_delta,
    run_both,
    run_two_step,
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

    if two.accepted_delta_ops:
        # HONEST triple (Codex verdict §5): the accepted Δ is read from the
        # durable transcript, and the post graph + the Δ replay both come from
        # the store.  π_edit(live emitted / next-turn retained) ==
        # π_edit(Δ replay) — both are the store's revision.
        assert two.replayed_quotient is not None
        assert two.pi_edit_quotient is not None
        assert two.replayed_quotient == two.pi_edit_quotient
        # The fixture Δ is ONLY an oracle: the ACTUAL accepted ops must produce
        # the same quotient the fixture predicts (the typed tool may differ in
        # form — named field vs widgets_values — but never in quotient).
        assert scenario.delta_ops, f"{scenario.name}: accepted Δ without an oracle"
        oracle_quotient = _pi_edit_or_none(
            to_workflow(apply_delta(scenario.base_raw, scenario.delta_ops))
        )
        assert oracle_quotient == full.pi_edit_quotient
        # The ACTUAL accepted ops replay to that same quotient (the store's
        # replay is authoritative; this pins the fixture oracle to it).
        actual_quotient = _pi_edit_or_none(
            to_workflow(apply_delta(scenario.base_raw, two.accepted_delta_ops))
        )
        assert actual_quotient == two.replayed_quotient
    elif scenario.route == "reorganise":
        # Furniture: no typed tool expresses position, so the two-step lands NO
        # edit and the retained revision is the base — same quotient as full.
        assert two.replayed_quotient == full.pi_edit_quotient
        if scenario.delta_ops:
            oracle_quotient = _pi_edit_or_none(
                to_workflow(apply_delta(scenario.base_raw, scenario.delta_ops))
            )
            assert oracle_quotient == full.pi_edit_quotient
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


@pytest.mark.timeout(600)  # 8 full two-mode pipelines; the render path is slow under load
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


def test_edit_batch_applies_both_ops_atomically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ONE ``edit_batch`` tool call lowers to TWO ops under ONE accepted Δ —
    atomic multi-op expressiveness restored (the verdict's add+remove split)."""
    scenario = _scenario_by_name("batch-edit")
    full, two = run_both(scenario, monkeypatch, tmp_path)
    assert full.ok is True and two.ok is True
    assert len(two.accepted_delta_ops) == 2, "batch edit must land both ops"
    assert {op.get("op") for op in two.accepted_delta_ops} == {"set_node_field", "set_mode"}
    assert two.pi_edit_quotient == full.pi_edit_quotient
    assert two.replayed_quotient == full.pi_edit_quotient
    # BOTH effects are visible in the quotient: the widget edit AND the mode.
    node_b = [n for n in two.pi_edit_quotient[0] if n[1] == "2"][0]
    node_c = [n for n in two.pi_edit_quotient[0] if n[1] == "3"][0]
    assert node_b[3] == 2, "batch must mute node B (mode 2)"
    assert ("widget", "widget_0", "batched", "unknown") in node_c[4]


def test_remove_link_drops_the_wire_quotient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``remove_link`` drops the wires into the named input; no connection
    survives in the quotient."""
    scenario = _scenario_by_name("remove-link")
    full, two = run_both(scenario, monkeypatch, tmp_path)
    assert full.ok is True and two.ok is True
    assert len(two.accepted_delta_ops) == 1
    assert two.accepted_delta_ops[0]["op"] == "remove_link"
    assert full.pi_edit_quotient is not None
    assert full.pi_edit_quotient[1] == (), "no connection may survive remove_link"
    assert two.pi_edit_quotient == full.pi_edit_quotient
    assert two.replayed_quotient == full.pi_edit_quotient


def test_set_node_mode_moves_the_mode_quotient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``set_node_mode`` muting is editable: the quotient carries mode 2."""
    scenario = _scenario_by_name("set-node-mode")
    full, two = run_both(scenario, monkeypatch, tmp_path)
    assert full.ok is True and two.ok is True
    node_b = [n for n in full.pi_edit_quotient[0] if n[1] == "2"][0]
    assert node_b[3] == 2, "muted node B must carry LiteGraph mode 2"
    assert two.pi_edit_quotient == full.pi_edit_quotient
    assert two.replayed_quotient == full.pi_edit_quotient


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


@pytest.mark.timeout(240)  # two full two-mode pipelines
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


# ── durable sidecar honesty (missing / corrupt / hash-mismatched) ────────────


@pytest.mark.timeout(240)  # one two-mode pipeline + durable-sidecar tampering
def test_missing_or_corrupt_sidecar_falls_back_to_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``retained_workflow`` is authoritative via canonical Δ replay: a
    missing, unparseable, or hash-mismatched sidecar must fall back to the
    replayed revision — never to a stale or corrupt file."""
    scenario = _scenario_by_name("named-field edit")
    full, two = run_both(scenario, monkeypatch, tmp_path)
    assert two.accepted_delta_ops, "the edit must have landed for the sidecar tests"
    store = TwoStepSessionStore(tmp_path / "editor_sessions")
    sid = "win-named-field-edit"
    state = store.load(sid)
    assert state is not None
    replayed = store.replay_workflow(state)
    replayed_quotient = _pi_edit_or_none(to_workflow(replayed))

    # Baseline: the hash-matched sidecar returns the same revision as replay.
    assert store.retained_workflow(sid) == replayed

    # (a) Missing sidecar → replay still reconstructs the retained revision.
    store.workflow_path(sid).unlink(missing_ok=True)
    assert store.retained_workflow(sid) == replayed
    assert _pi_edit_or_none(to_workflow(store.retained_workflow(sid))) == replayed_quotient

    # (b) Corrupt sidecar (unparseable JSON) → falls back to replay.
    store.workflow_path(sid).write_text("{definitely not json", encoding="utf-8")
    assert store.retained_workflow(sid) == replayed

    # (c) Hash-mismatched sidecar (valid JSON, wrong revision) → replay wins.
    store.write_workflow(sid, scenario.base_raw)
    assert store.retained_workflow(sid) == replayed


# ── concurrent edits accumulate on one session ───────────────────────────────


@pytest.mark.timeout(240)  # two sequential two-step messages on one session
def test_concurrent_edits_both_survive_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two sequential messages on ONE session each land an accepted Δ; the
    second must NOT hide the first — both survive in the accumulated replay."""
    first = _scenario_by_name("named-field edit")
    second = _scenario_by_name("rewire")
    shared = "win-shared"
    run_two_step(first, monkeypatch, tmp_path, session_id=shared)
    run_two_step(second, monkeypatch, tmp_path, session_id=shared, delta_id="d2")

    store = TwoStepSessionStore(tmp_path / "editor_sessions")
    state = store.load(shared)
    assert state is not None
    # Both Δ ids are accepted session state a follow-up message may cite.
    assert state.accepted_delta_ids() == ("d1", "d2")
    assert len(state.accepted_delta_refs) == 2

    # The store replay accumulates BOTH edits in acceptance order: the widget
    # edit from message 1 AND the rewire from message 2.
    replayed = store.replay_workflow(state)
    replayed_quotient = _pi_edit_or_none(to_workflow(replayed))
    combined_oracle = _pi_edit_or_none(
        to_workflow(apply_delta(first.base_raw, first.delta_ops + second.delta_ops))
    )
    assert replayed_quotient == combined_oracle

    # The first Δ was NOT hidden: the combined replay differs from a replay of
    # the second Δ alone (the prompt edit would be lost if d1 were dropped).
    second_only = _pi_edit_or_none(
        to_workflow(apply_delta(second.base_raw, second.delta_ops))
    )
    assert replayed_quotient != second_only


# ── failure family is consistent across modes ────────────────────────────────


def test_classify_failure_surfaces_only_in_full_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-step two-step mode has no classify phase: a classify failure is
    unreachable there.  It surfaces (identically typed) in full mode only,
    while two-step dispatches straight to execute and never invokes classify."""

    def failing_classify(request: ExecutorRequest, spec: object, **kwargs: object) -> object:
        del request, spec, kwargs
        raise executor_core._ExecutorPhaseError(
            stage="classify",
            failure_kind="ValidationError",
            message="deterministic classify failure",
        )

    monkeypatch.setattr(executor_core, "_run_classify", failing_classify)
    monkeypatch.setattr(
        two_step_module,
        "_two_step_outcome",
        lambda **kwargs: ExecutorResult.success(reply="one-step execute"),
    )
    full = executor_core.run_executor(
        ExecutorRequest(query="q", graph={"nodes": []}, pipeline_mode="full")
    )
    two = executor_core.run_executor(
        ExecutorRequest(
            query="q",
            graph={"nodes": []},
            pipeline_mode="two_step",
            session_id="win-x",
        )
    )
    assert full.ok is False
    assert full.failure_kind == "ValidationError"
    assert full.failure_stage == "classify"
    # One-step two-step never classifies → the shared classify failure is not
    # reachable there; the execute boundary runs instead.
    assert two.ok is True


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
