"""Tests for vibecomfy.ingest.snapshot.capture_ingest_snapshot.

Covers: keying by uid, widget_values_sig, incoming/outgoing edge sigs,
public_input_binding, and the _ingest_snapshot stash on VibeWorkflow.metadata.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import from_api, from_ui
from vibecomfy.ingest.snapshot import capture_ingest_snapshot


_R5_FIXTURES = Path(__file__).parent / "fixtures" / "workflow_execution_spine_r5"


@pytest.mark.xfail(
    strict=True,
    reason="T0.1 freeze: UI/API source lineage is currently collapsed at ingest",
)
def test_r5_mixed_ui_api_fixture_cannot_pair_representations_or_fabricate_removals() -> None:
    fixture = json.loads(
        (_R5_FIXTURES / "mixed_ui_api_assessment.json").read_text(encoding="utf-8")
    )

    ui_workflow = from_ui(
        fixture["original"]["graph"],
        use_comfy_converter=False,
        comfy_converter_strict=False,
    )
    api_workflow = from_api(fixture["final"]["graph"])

    assert ui_workflow.source.source_type == "ui"
    assert api_workflow.source.source_type == "api"
    assert fixture["expected"]["fabricated_removals"] == []


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _api_wf(nodes: dict) -> dict:
    """Wrap raw node dicts into a minimal ComfyUI API dict."""
    return {str(k): v for k, v in nodes.items()}


def _simple_api() -> dict:
    """Two-node API workflow: LoadImage (1) → SaveImage (2), no widget values."""
    return _api_wf({
        1: {
            "class_type": "LoadImage",
            "inputs": {"image": "example.png"},
            "_ui": {"id": 1, "pos": [0, 0], "size": [200, 100], "properties": {"vibecomfy_uid": "load-uid"}},
        },
        2: {
            "class_type": "SaveImage",
            "inputs": {"images": [1, 0], "filename_prefix": "out/"},
            "_ui": {"id": 2, "pos": [300, 0], "size": [200, 100], "properties": {"vibecomfy_uid": "save-uid"}},
        },
    })


def _api_with_widget() -> dict:
    """KSampler node carrying widget values."""
    return _api_wf({
        1: {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
            "_ui": {"id": 1, "pos": [0, 0], "size": [300, 200], "properties": {"vibecomfy_uid": "ksampler-uid"}},
        },
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_snapshot_keyed_by_uid():
    wf = from_api(_simple_api())
    snap = capture_ingest_snapshot({}, wf)
    assert "load-uid" in snap
    assert "save-uid" in snap


def test_snapshot_class_type_recorded():
    wf = from_api(_simple_api())
    snap = capture_ingest_snapshot({}, wf)
    assert snap["load-uid"]["class_type"] == "LoadImage"
    assert snap["save-uid"]["class_type"] == "SaveImage"


def test_snapshot_widget_values_sig_captures_non_link_inputs():
    wf = from_api(_api_with_widget())
    snap = capture_ingest_snapshot({}, wf)
    sig = snap["ksampler-uid"]["widget_values_sig"]
    # Should be a sorted tuple of (field, repr(value)) pairs
    assert isinstance(sig, tuple)
    field_names = {item[0] for item in sig}
    assert "seed" in field_names
    assert "steps" in field_names
    assert "cfg" in field_names


def test_snapshot_incoming_edge_sig_captured():
    wf = from_api(_simple_api())
    snap = capture_ingest_snapshot({}, wf)
    # SaveImage receives an incoming edge from LoadImage
    incoming = snap["save-uid"]["incoming_edge_sig"]
    assert isinstance(incoming, tuple)
    assert len(incoming) == 1
    to_input, (source_uid, _slot) = incoming[0]
    assert to_input == "images"
    assert source_uid == "load-uid"


def test_snapshot_outgoing_edge_sig_captured():
    wf = from_api(_simple_api())
    snap = capture_ingest_snapshot({}, wf)
    # LoadImage has one outgoing edge to SaveImage
    outgoing = snap["load-uid"]["outgoing_edge_sig"]
    assert isinstance(outgoing, tuple)
    assert len(outgoing) == 1
    _slot, (target_uid, to_input) = outgoing[0]
    assert target_uid == "save-uid"
    assert to_input == "images"


def test_snapshot_no_edges_produces_empty_sigs():
    api = _api_wf({
        1: {
            "class_type": "LoadImage",
            "inputs": {"image": "x.png"},
            "_ui": {"id": 1, "pos": [0, 0], "size": [200, 100], "properties": {"vibecomfy_uid": "solo-uid"}},
        },
    })
    wf = from_api(api)
    snap = capture_ingest_snapshot({}, wf)
    assert snap["solo-uid"]["incoming_edge_sig"] == ()
    assert snap["solo-uid"]["outgoing_edge_sig"] == ()


def test_snapshot_stashed_on_workflow_metadata():
    """_ingest_snapshot is stored on the workflow metadata after from_api."""
    wf = from_api(_simple_api())
    assert "_ingest_snapshot" in wf.metadata
    snap = wf.metadata["_ingest_snapshot"]
    assert "load-uid" in snap
    assert "save-uid" in snap


def test_snapshot_survives_ir_mutation():
    """_ingest_snapshot captures the state AT INGEST TIME; later mutations don't alter it."""
    wf = from_api(_api_with_widget())
    snap_before = dict(wf.metadata["_ingest_snapshot"])
    # Mutate a widget value in the IR
    wf.nodes["1"].widgets["seed"] = 999
    # The stored snapshot is unchanged
    assert wf.metadata["_ingest_snapshot"]["ksampler-uid"]["widget_values_sig"] == snap_before["ksampler-uid"]["widget_values_sig"]
