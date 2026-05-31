"""Falsifiability tests for the felt-fidelity evaluator.

Covers: +8px preserved movement → violation, reroute disappearance →
violation, edited/new movement → no violation, tolerance boundary
behaviour, and snapshot-absent skip.
"""

from __future__ import annotations

import pytest

from vibecomfy.porting.layout import evaluate_felt_delta
from vibecomfy.porting.layout.reconcile import ChangeReport, ContentEdits, IdentityStabilization


# ── helpers ────────────────────────────────────────────────────────────────


def _prior_store(entries: dict | None = None) -> dict:
    """Build a prior-store envelope with the given entries."""
    return {"entries": entries or {}}


def _entry(pos=(0, 0), size=(200, 100), mode=0, group=None) -> dict:
    """Create a single prior-store entry dict."""
    return {
        "pos": list(pos),
        "size": list(size),
        "mode": mode,
        "group": group,
    }


def _emitted_ui(nodes: list | None = None) -> dict:
    """Build an emitted UI JSON dict from node list."""
    return {"nodes": nodes or []}


def _ui_node(id_=1, pos=(100, 200), size=(200, 100), uid=None, vid=None, mode=0) -> dict:
    """Create a single emitted-UI node dict (litegraph shape)."""
    props: dict = {}
    if uid is not None:
        props["vibecomfy_uid"] = uid
    if vid is not None:
        props["vibecomfy_id"] = vid
    return {
        "id": id_,
        "pos": list(pos),
        "size": list(size),
        "mode": mode,
        "properties": props,
    }


def _change_report(
    preserved=None,
    edited=None,
    new_auto_placed=None,
    removed=None,
    virtual_wires_degraded=None,
    removed_named=None,
    stripped_helpers=None,
) -> ChangeReport:
    """Build a minimal ChangeReport for felt tests."""
    return ChangeReport(
        content_edits=ContentEdits(
            preserved=list(preserved or []),
            edited=list(edited or []),
            new_auto_placed=list(new_auto_placed or []),
            removed=list(removed or []),
            virtual_wires_degraded=list(virtual_wires_degraded or []),
            removed_named=list(removed_named or []),
            stripped_helpers=list(stripped_helpers or []),
        ),
        identity_stabilization=IdentityStabilization(
            bridge_minted=[],
            unmatched_legacy=[],
            definition_relayout=[],
        ),
    )


# ── 1. +8px preserved movement → violation with full details ───────────────


def test_eight_px_preserved_movement_fails_with_full_details():
    """+8px preserved-node movement fails with position_moved violation."""
    uid = "node-1"

    prior = _prior_store({"node-1": _entry(pos=(100, 200))})
    emitted = _emitted_ui([_ui_node(1, pos=(108, 200), uid=uid)])

    # edited must be non-empty so we don't take the snapshot-absent skip path
    report = _change_report(preserved=[uid], edited=["other-node"])

    result = evaluate_felt_delta(prior, emitted, report)

    assert result.ok is False
    assert result.skipped_snapshot_absent is False
    assert len(result.violations) == 1

    v = result.violations[0]
    assert v.uid == uid
    assert v.reason == "position_moved"
    assert v.prior_pos == [100.0, 200.0]
    assert v.current_pos == [108.0, 200.0]
    assert v.delta_px == pytest.approx(8.0)


# ── 2. preserved reroute disappearance → violation ─────────────────────────


def test_preserved_reroute_disappearance_fails():
    """A preserved reroute that vanishes from emitted UI triggers a violation."""
    uid = "reroute-1"

    prior = _prior_store({"reroute-1": _entry(pos=(50, 50))})
    # emitted UI does NOT contain the reroute node
    emitted = _emitted_ui([
        _ui_node(1, pos=(0, 0), uid="other-node"),
    ])

    report = _change_report(preserved=[uid], edited=["other-node"])

    result = evaluate_felt_delta(
        prior, emitted, report,
        reroute_uids=frozenset({uid}),
    )

    assert result.ok is False
    assert len(result.violations) == 1

    v = result.violations[0]
    assert v.uid == uid
    assert v.reason == "reroute_disappeared"
    assert v.prior_pos == [50.0, 50.0]
    assert v.current_pos is None
    assert v.delta_px is None


# ── 3. edited / new nodes do not trigger untouched-move violations ─────────


def test_edited_node_movement_does_not_trigger_violation():
    """An edited node that moves should NOT produce a felt violation."""
    uid = "edited-node"
    preserved_uid = "stay-put"

    prior = _prior_store({
        "edited-node": _entry(pos=(100, 100)),
        "stay-put": _entry(pos=(200, 200)),
    })
    # edited node moved drastically but is classified as *edited*, not preserved
    emitted = _emitted_ui([
        _ui_node(1, pos=(500, 500), uid=uid),
        _ui_node(2, pos=(200, 200), uid=preserved_uid),
    ])

    report = _change_report(preserved=["stay-put"], edited=[uid])

    result = evaluate_felt_delta(prior, emitted, report)

    assert result.ok is True
    assert len(result.violations) == 0


def test_new_node_does_not_trigger_violation():
    """A node that is new_auto_placed shouldn't trigger movement violations."""
    preserved_uid = "preserved-1"
    new_uid = "new-node"

    prior = _prior_store({"preserved-1": _entry(pos=(50, 50))})
    emitted = _emitted_ui([
        _ui_node(1, pos=(50, 50), uid=preserved_uid),
        _ui_node(2, pos=(999, 999), uid=new_uid),
    ])

    # new_auto_placed won't be in preserved, so no check applies
    report = _change_report(
        preserved=[preserved_uid],
        edited=["other-edited"],
        new_auto_placed=[new_uid],
    )

    result = evaluate_felt_delta(prior, emitted, report)

    assert result.ok is True
    # only preserved nodes get checked; the new node is ignored
    assert len(result.violations) == 0


# ── 4. tolerance: accepts 0.5 px, rejects 2 px ─────────────────────────────


def test_tolerance_accepts_05px_rejects_2px():
    """With tolerance=1.0, 0.5 px is tolerated but 2 px is not."""
    uid = "node-tol"

    prior = _prior_store({"node-tol": _entry(pos=(100, 200))})

    report = _change_report(preserved=[uid], edited=["other"])

    # --- 0.5 px: within tolerance ---
    emitted_05 = _emitted_ui([_ui_node(1, pos=(100.5, 200), uid=uid)])
    result_05 = evaluate_felt_delta(prior, emitted_05, report, position_tolerance_px=1.0)
    assert result_05.ok is True
    assert len(result_05.violations) == 0

    # --- 2 px: exceeds tolerance ---
    emitted_2 = _emitted_ui([_ui_node(1, pos=(102, 200), uid=uid)])
    result_2 = evaluate_felt_delta(prior, emitted_2, report, position_tolerance_px=1.0)
    assert result_2.ok is False
    assert len(result_2.violations) == 1
    assert result_2.violations[0].delta_px == pytest.approx(2.0)


# ── 5. snapshot-absent skip ────────────────────────────────────────────────


def test_snapshot_absent_reports_skipped_and_ok():
    """When preserved nodes exist but edited is empty → snapshot-absent skip."""
    uid = "node-skip"

    prior = _prior_store({"node-skip": _entry(pos=(10, 20))})
    emitted = _emitted_ui([_ui_node(1, pos=(999, 999), uid=uid)])

    # edited is empty → triggers the snapshot-absent early-return
    report = _change_report(preserved=[uid], edited=[])

    result = evaluate_felt_delta(prior, emitted, report)

    assert result.ok is True
    assert result.skipped_snapshot_absent is True
    assert len(result.violations) == 0
    assert "skipped" in result.summary.lower()
    assert "snapshot" in result.summary.lower()


# ── 6. latency measurement baseline (informational) ────────────────────────

@pytest.mark.info
def test_latency_measure_baseline_informational() -> None:
    """Measure emit_ui_json latency on a real large template; skip if unavailable."""
    import os

    from vibecomfy.porting.latency import measure_emit_latency
    from vibecomfy.schema import get_schema_provider

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ready_templates",
        "video",
        "ltx2_3_runexx_music_video_low_ram.py",
    )

    # Skip if the template file doesn't exist
    if not os.path.isfile(template_path):
        pytest.skip(
            "ltx2_3_runexx_music_video_low_ram.py not found; "
            "template loading unavailable"
        )

    # Try to load the template and check object_info availability
    try:
        from vibecomfy import load_workflow_any
        wf = load_workflow_any(template_path)
    except Exception as exc:
        pytest.skip(
            f"Failed to load ltx2_3_runexx_music_video_low_ram.py: {exc}"
        )

    # Verify object_info / schema provider is available
    try:
        provider = get_schema_provider("auto")
        # Quick sanity: at least one node class should resolve
        wf.finalize_metadata()
    except Exception as exc:
        pytest.skip(
            f"object_info / schema_provider unavailable: {exc}"
        )

    # Measure
    report = measure_emit_latency(wf, schema_provider=provider)
    assert report.ok is True
    assert report.budget_ms == float("inf")
    assert report.elapsed_ms >= 0.0
    # Print informational baseline to stdout
    print(f"\n[info] emit_ui_json latency: {report.elapsed_ms:.1f} ms "
          f"for ltx2_3_runexx_music_video_low_ram.py")


# ── 7. latency gated pass under conservative budget ────────────────────────

def test_latency_gated_pass_under_conservative_budget() -> None:
    """measure_emit_latency_gated passes under a conservative 5000ms budget."""
    import os

    from vibecomfy.porting.latency import (
        FALLBACK_LATENCY_BUDGET_MS,
        measure_emit_latency_gated,
    )
    from vibecomfy.schema import get_schema_provider

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ready_templates",
        "video",
        "ltx2_3_runexx_music_video_low_ram.py",
    )

    if not os.path.isfile(template_path):
        pytest.skip(
            "ltx2_3_runexx_music_video_low_ram.py not found; "
            "template loading unavailable"
        )

    try:
        from vibecomfy import load_workflow_any
        wf = load_workflow_any(template_path)
    except Exception as exc:
        pytest.skip(
            f"Failed to load ltx2_3_runexx_music_video_low_ram.py: {exc}"
        )

    try:
        provider = get_schema_provider("auto")
        wf.finalize_metadata()
    except Exception as exc:
        pytest.skip(
            f"object_info / schema_provider unavailable: {exc}"
        )

    report = measure_emit_latency_gated(wf, provider, budget_ms=FALLBACK_LATENCY_BUDGET_MS)
    assert report.ok is True, (
        f"Expected ok=True under budget {FALLBACK_LATENCY_BUDGET_MS} ms, "
        f"but elapsed_ms={report.elapsed_ms:.1f}"
    )
    assert report.budget_ms == FALLBACK_LATENCY_BUDGET_MS
    assert report.elapsed_ms >= 0.0
    print(f"\n[gated] elapsed={report.elapsed_ms:.1f} ms "
          f"budget={report.budget_ms:.0f} ms ok={report.ok}")


# ── 8. monkeypatched slow-path failure ─────────────────────────────────────

def test_latency_gated_monkeypatched_slow_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """measure_emit_latency_gated returns ok=False when emit is artificially slow."""
    import time

    from vibecomfy.porting.latency import measure_emit_latency_gated

    # Create a fake workflow and schema provider — we only care about timing.
    class _FakeWF:
        def finalize_metadata(self) -> None:
            pass

    class _FakeProvider:
        pass

    wf = _FakeWF()
    provider = _FakeProvider()

    # Simulate a 200ms call inside the timing window.
    call_count = 0

    def _fake_emit(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        return {}

    monkeypatch.setattr(
        "vibecomfy.porting.latency.emit_ui_json",
        _fake_emit,
    )

    # Make perf_counter return values that span 200ms.
    t0 = time.perf_counter()
    times = iter([t0, t0 + 0.200])

    monkeypatch.setattr(
        "vibecomfy.porting.latency.perf_counter",
        lambda: next(times),
    )

    # With a 100ms budget, 200ms should fail.
    report = measure_emit_latency_gated(wf, provider, budget_ms=100.0)

    assert call_count == 1, "emit_ui_json should be called exactly once"
    assert report.ok is False, (
        f"Expected ok=False with 100ms budget, "
        f"got ok={report.ok} elapsed_ms={report.elapsed_ms:.1f}"
    )
    assert report.budget_ms == 100.0
    assert report.elapsed_ms == pytest.approx(200.0, rel=0.01)

    # With a 500ms budget, 200ms should pass.
    times2 = iter([t0, t0 + 0.200])
    monkeypatch.setattr(
        "vibecomfy.porting.latency.perf_counter",
        lambda: next(times2),
    )
    call_count = 0
    report2 = measure_emit_latency_gated(wf, provider, budget_ms=500.0)
    assert report2.ok is True
    assert report2.elapsed_ms == pytest.approx(200.0, rel=0.01)
