"""Tests for vibecomfy.porting.layout.delta.compute_field_delta.

Covers: no-change, widget-edit, rewire (incoming edge change), added node
(snapshot-absent), removed node (in snapshot but not in current IR),
and snapshot-absent node omission.
"""
from __future__ import annotations

import copy

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.ingest.snapshot import capture_ingest_snapshot
from vibecomfy.porting.layout.delta import compute_field_delta
from vibecomfy.workflow import VibeEdge, VibeNode


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _api_ksampler_to_saveimage() -> dict:
    """Minimal two-node API: KSampler (1) → SaveImage (2)."""
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "latent_image": [2, 0],
            },
            "_ui": {"id": 1, "pos": [0, 0], "size": [300, 200],
                    "properties": {"vibecomfy_uid": "sampler-uid"}},
        },
        "2": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
            "_ui": {"id": 2, "pos": [0, 300], "size": [300, 100],
                    "properties": {"vibecomfy_uid": "latent-uid"}},
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_change_produces_empty_delta():
    """Identical snapshot and IR → empty delta."""
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    snap = capture_ingest_snapshot({}, wf)
    delta = compute_field_delta(snap, wf)
    assert delta == {}


def test_widget_edit_detected():
    """Changing a widget value after snapshot produces a widget_values_sig delta."""
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    snap = capture_ingest_snapshot({}, wf)

    # Mutate seed in the IR (post-ingest edit)
    wf.nodes["1"].inputs["seed"] = 999

    delta = compute_field_delta(snap, wf)
    assert "sampler-uid" in delta
    assert "widget_values_sig" in delta["sampler-uid"]
    old_val, new_val = delta["sampler-uid"]["widget_values_sig"]
    assert old_val != new_val


def test_rewire_detected():
    """Changing an incoming edge after snapshot produces an incoming_edge_sig delta."""
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    snap = capture_ingest_snapshot({}, wf)

    # Add a new node and rewire KSampler's latent_image to it
    new_node = VibeNode(id="3", class_type="EmptyLatentImage",
                        inputs={"width": 768, "height": 768, "batch_size": 1},
                        uid="latent-uid-b")
    wf.nodes["3"] = new_node
    # Remove the old edge and add a new one pointing to the new node
    wf.edges = [e for e in wf.edges if not (e.to_node == "1" and e.to_input == "latent_image")]
    wf.edges.append(VibeEdge(from_node="3", from_output="0", to_node="1", to_input="latent_image"))

    delta = compute_field_delta(snap, wf)
    assert "sampler-uid" in delta
    assert "incoming_edge_sig" in delta["sampler-uid"]


def test_unmodified_node_absent_from_delta():
    """A node that was not edited should not appear in the delta."""
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    snap = capture_ingest_snapshot({}, wf)
    # Only mutate KSampler
    wf.nodes["1"].inputs["seed"] = 9999

    delta = compute_field_delta(snap, wf)
    assert "sampler-uid" in delta
    # EmptyLatentImage was not touched
    assert "latent-uid" not in delta


def test_added_node_is_snapshot_absent_and_omitted():
    """A node added to the IR after snapshot is absent from snapshot → not in delta."""
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    snap = capture_ingest_snapshot({}, wf)

    # Add a new node that was not present at ingest time
    wf.nodes["99"] = VibeNode(id="99", class_type="CLIPTextEncode",
                              inputs={"text": "hello"}, uid="new-clip-uid")

    delta = compute_field_delta(snap, wf)
    # New node is snapshot-absent → must be omitted
    assert "new-clip-uid" not in delta


def test_removed_node_omitted_from_delta():
    """A node removed from the IR after snapshot is omitted from delta.

    Callers that need to detect removals diff snapshot keys against the current
    IR uid set directly; compute_field_delta only reports changed fields for
    nodes present in both snapshot and current IR.
    """
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    snap = capture_ingest_snapshot({}, wf)

    # Remove a node from the IR
    del wf.nodes["2"]
    wf.edges = [e for e in wf.edges if e.from_node != "2" and e.to_node != "2"]

    delta = compute_field_delta(snap, wf)
    # Removed node must not appear in delta
    assert "latent-uid" not in delta


def test_snapshot_absent_node_omitted_matches_add_semantics():
    """Snapshot-absent nodes (in IR but not snapshot) are excluded from delta."""
    wf = convert_to_vibe_format(_api_ksampler_to_saveimage())
    # Take snapshot of only one node by building a partial snapshot manually
    snap_only_sampler = {
        uid: entry
        for uid, entry in wf.metadata["_ingest_snapshot"].items()
        if uid == "sampler-uid"
    }

    # latent-uid is absent from snap_only_sampler but present in wf → snapshot-absent
    delta = compute_field_delta(snap_only_sampler, wf)
    assert "latent-uid" not in delta
    # sampler-uid was not modified → also not in delta
    assert "sampler-uid" not in delta


# ---------------------------------------------------------------------------
# Batch-placement toposort tests (T12: dependency counts + reverse edges)
# ---------------------------------------------------------------------------


def test_toposort_linear_chain_dependency_count_ordering():
    """A→B→C linear chain: in-degree counts produce deterministic A,B,C order."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"A", "B", "C"}
    deps = {"A": set(), "B": {"A"}, "C": {"B"}}
    statement_order = {"A": 0, "B": 1, "C": 2}

    result = _toposort_component(component, deps, statement_order)
    assert result == ["A", "B", "C"]


def test_toposort_deterministic_ready_ordering():
    """Independent nodes A,B,C (no deps) → ordered by statement_order."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"A", "B", "C"}
    deps = {"A": set(), "B": set(), "C": set()}
    statement_order = {"A": 2, "B": 0, "C": 1}

    result = _toposort_component(component, deps, statement_order)
    assert result == ["B", "C", "A"]


def test_toposort_diamond_dependency_count():
    """Diamond: A→B, A→C, B→D, C→D. Verify in-degree counting is correct."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"A", "B", "C", "D"}
    deps = {"A": set(), "B": {"A"}, "C": {"A"}, "D": {"B", "C"}}
    statement_order = {"A": 0, "B": 1, "C": 2, "D": 3}

    result = _toposort_component(component, deps, statement_order)
    # A first (only ready). Then B and C both become ready; B < C by statement_order.
    # After B→C processed, D becomes ready.
    assert result == ["A", "B", "C", "D"]


def test_toposort_cycle_remainder_preserves_partial_order():
    """Cycle A→B→C→A: no node has in-degree 0, remainder appended deterministically."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"A", "B", "C"}
    deps = {"A": {"C"}, "B": {"A"}, "C": {"B"}}
    statement_order = {"A": 2, "B": 1, "C": 0}

    result = _toposort_component(component, deps, statement_order)
    # All three in cycle → all in remainder, sorted by statement_order.
    assert result == ["C", "B", "A"]


def test_toposort_cycle_with_non_cycle_prefix():
    """D→A→B→C→A: D is outside the cycle, so D comes first, then A,B,C appended."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"D", "A", "B", "C"}
    deps = {"D": set(), "A": {"D", "C"}, "B": {"A"}, "C": {"B"}}
    statement_order = {"D": 0, "A": 2, "B": 1, "C": 3}

    result = _toposort_component(component, deps, statement_order)
    # D has in-degree 0 → processed first. A,B,C in cycle → remainder sorted.
    assert result[0] == "D"
    assert set(result[1:]) == {"A", "B", "C"}
    # Remainder sorted by statement_order: B(1), A(2), C(3)
    assert result[1:] == ["B", "A", "C"]


def test_toposort_deterministic_across_runs():
    """Same input 3 times → same output (no non-determinism from hash ordering)."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"X", "Y", "Z", "W"}
    deps = {"W": set(), "X": {"W"}, "Y": {"W"}, "Z": {"X", "Y"}}
    statement_order = {"W": 0, "X": 10, "Y": 5, "Z": 20}

    results = [
        _toposort_component(component, deps, statement_order)
        for _ in range(5)
    ]
    assert all(r == results[0] for r in results)
    # W first, then X(10) vs Y(5): Y comes before X, Z last after both.
    assert results[0] == ["W", "Y", "X", "Z"]


def test_toposort_reverse_edges_not_scanned():
    """When A depends on nothing, its reverse_edges should still be clean (no KeyError)."""
    from vibecomfy.porting.layout.placement import _toposort_component

    component = {"A", "B"}
    deps = {"A": set(), "B": {"A"}}
    statement_order = {"A": 0, "B": 1}

    result = _toposort_component(component, deps, statement_order)
    assert result == ["A", "B"]
