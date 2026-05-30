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
