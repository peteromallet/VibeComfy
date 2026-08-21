"""Tests for vibecomfy.ingest.snapshot.capture_ingest_snapshot.

Covers: keying by uid, widget_values_sig, incoming/outgoing edge sigs,
public_input_binding, and the _ingest_snapshot stash on VibeWorkflow.metadata.
"""
from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import detect_workflow_shape, from_api, from_ui, ingest_workflow_and_ui
from vibecomfy.ingest.snapshot import (
    SEMANTIC_HASH_VERSION,
    SnapshotAuthorityError,
    WorkflowLineage,
    WorkflowSnapshot,
    bind_snapshot_lineage,
    capture_ingest_snapshot,
    compare_snapshot_authority,
    snapshot_of,
)

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


def _ui_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "pos": [0, 0],
                "size": [200, 100],
                "widgets_values": ["example.png"],
                "properties": {"vibecomfy_uid": "load-uid", "frontend_only": {"keep": True}},
                "opaque_custom": {"pack": "UnknownCustomNode", "payload": [1, 2, 3]},
            },
            {
                "id": 2,
                "type": "SaveImage",
                "pos": [300, 0],
                "size": [200, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                "widgets_values": ["out/"],
                "properties": {"vibecomfy_uid": "save-uid"},
            },
            {
                "id": 99,
                "type": "UnknownCustomNode",
                "pos": [600, 0],
                "size": [180, 80],
                "widgets_values": [{"secret": "opaque"}],
                "properties": {"vibecomfy_uid": "unknown-uid", "customUI": {"tab": "extra"}},
                "opaque_custom": {"pack": "UnknownCustomNode", "payload": [1, 2, 3]},
            },
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        "extra": {"ui_only": {"sidebar": True}},
    }


def test_shape_dispatch_detects_ui_api_and_prompt_api_once() -> None:
    ui = _ui_graph()
    api = _simple_api()
    wrapped = {"prompt": api, "client_id": "c1"}
    unknown = {"not": "a-graph", "nodes": "nope"}

    assert detect_workflow_shape(ui) == "ui"
    assert detect_workflow_shape(api) == "api"
    assert detect_workflow_shape(wrapped) == "prompt_api"
    assert detect_workflow_shape(unknown) == "unknown"

    ingest_workflow_and_ui(ui)
    ingest_workflow_and_ui(api)
    ingest_workflow_and_ui(wrapped)
    with pytest.raises(ValueError, match="unsupported workflow shape"):
        ingest_workflow_and_ui(unknown)


def test_ingest_never_mutates_caller_inputs() -> None:
    ui = _ui_graph()
    before_ui = copy.deepcopy(ui)
    workflow, detached = ingest_workflow_and_ui(ui)
    ui["nodes"][0]["widgets_values"][0] = "mutated-by-caller.png"
    ui["nodes"][0]["opaque_custom"]["payload"].append(4)
    assert ui != before_ui
    assert detached["nodes"][0]["widgets_values"][0] == "example.png"
    assert list(snapshot_of(workflow).raw_sidecar["nodes"][0]["opaque_custom"]["payload"]) == [1, 2, 3]

    api = _simple_api()
    before_api = copy.deepcopy(api)
    ingest_workflow_and_ui(api)
    api["1"]["inputs"]["image"] = "mutated.png"
    assert api != before_api
    assert before_api["1"]["inputs"]["image"] == "example.png"

    wrapped = {"prompt": _simple_api(), "client_id": "keep-me"}
    before_wrapped = copy.deepcopy(wrapped)
    ingest_workflow_and_ui(wrapped)
    wrapped["prompt"]["1"]["inputs"]["image"] = "mutated.png"
    wrapped["client_id"] = "changed"
    assert wrapped != before_wrapped


def test_workflow_snapshot_is_frozen_copy_with_canonical_hash() -> None:
    import hashlib

    from vibecomfy.comfy_nodes.agent._canonical_contract_primitives import canonical_json_bytes_v1
    from vibecomfy.ingest.snapshot import _semantic_preimage

    ui = _ui_graph()
    workflow, _detached = ingest_workflow_and_ui(ui)
    snapshot = snapshot_of(workflow)
    assert isinstance(snapshot, WorkflowSnapshot)
    assert snapshot.semantic_hash_version == SEMANTIC_HASH_VERSION
    assert snapshot.source_representation == "ui"
    assert snapshot.layout.kind == "ingest_geometry_ref"
    assert snapshot.layout.digest
    assert "load-uid" in snapshot.identity
    assert any(edge[0] == "load-uid" and edge[2] == "save-uid" for edge in snapshot.topology)
    assert snapshot.workflow is not workflow
    workflow.nodes["1"].widgets["image"] = "live-mutated.png"
    assert snapshot.workflow.nodes["1"].widgets.get("image") != "live-mutated.png"
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.source_representation = "mutated"  # type: ignore[misc]
    recomputed = hashlib.sha256(
        canonical_json_bytes_v1(
            _semantic_preimage(
                identity=snapshot.identity,
                topology=snapshot.topology,
                field_snapshot=snapshot.field_snapshot,
            ),
            ensure_ascii=False,
        )
    ).hexdigest()
    assert snapshot.semantic_digest == recomputed
    second, _ = ingest_workflow_and_ui(copy.deepcopy(ui))
    assert snapshot_of(second).semantic_digest == snapshot.semantic_digest
    assert snapshot_of(second).source_digest == snapshot.source_digest
    layout_changed = copy.deepcopy(ui)
    layout_changed["nodes"][0]["pos"] = [99, 99]
    laid, _ = ingest_workflow_and_ui(layout_changed)
    laid_snap = snapshot_of(laid)
    assert laid_snap.layout.digest != snapshot.layout.digest
    assert laid_snap.semantic_digest == snapshot.semantic_digest


def test_prompt_api_wrapper_is_retained_as_sidecar() -> None:
    wrapped = {"prompt": _simple_api(), "client_id": "c1", "extra_meta": {"keep": 1}}
    workflow, _canonical = ingest_workflow_and_ui(wrapped)
    snapshot = snapshot_of(workflow)
    assert snapshot.source_representation == "prompt_api"
    assert snapshot.raw_sidecar["client_id"] == "c1"
    assert snapshot.raw_sidecar["extra_meta"]["keep"] == 1
    assert "1" in snapshot.raw_sidecar["prompt"]


def test_unknown_node_opaque_data_survives_unrelated_projection() -> None:
    from vibecomfy.porting.emit.ui import pin_untouched_ui

    ui = _ui_graph()
    workflow, detached = ingest_workflow_and_ui(ui)
    snapshot = snapshot_of(workflow)
    unknown = next(node for node in detached["nodes"] if node["id"] == 99)
    assert unknown["type"] == "UnknownCustomNode"
    assert unknown["properties"]["customUI"]["tab"] == "extra"
    assert unknown["widgets_values"][0]["secret"] == "opaque"
    sidecar_unknown = next(
        node
        for node in snapshot.raw_sidecar["nodes"]
        if str(node.get("id")) == "99"
    )
    assert sidecar_unknown["properties"]["customUI"]["tab"] == "extra"
    assert sidecar_unknown["opaque_custom"]["pack"] == "UnknownCustomNode"
    sidecar_load = next(
        node
        for node in snapshot.raw_sidecar["nodes"]
        if str(node.get("id")) == "1"
    )
    assert sidecar_load["opaque_custom"]["pack"] == "UnknownCustomNode"

    candidate = copy.deepcopy(detached)
    save = next(node for node in candidate["nodes"] if node["id"] == 2)
    save["widgets_values"] = ["edited-prefix/"]
    pinned = pin_untouched_ui(detached, candidate, ops=())
    pinned_unknown = next(node for node in pinned["nodes"] if node["id"] == 99)
    assert pinned_unknown["properties"]["customUI"] == {"tab": "extra"}
    assert pinned_unknown["widgets_values"][0]["secret"] == "opaque"


def test_session_turn_lineage_and_mixed_representation_reject() -> None:
    ui_wf, _ = ingest_workflow_and_ui(_ui_graph())
    api_wf, _ = ingest_workflow_and_ui(_simple_api())
    ui_snap = bind_snapshot_lineage(ui_wf, session_id="sess-a", turn_id="0001", baseline_id="b1")
    api_snap = bind_snapshot_lineage(api_wf, session_id="sess-a", turn_id="0002", baseline_id="b1")
    assert ui_snap.lineage == WorkflowLineage(session_id="sess-a", turn_id="0001", baseline_id="b1")
    with pytest.raises(SnapshotAuthorityError) as mixed:
        compare_snapshot_authority(ui_snap, api_snap)
    assert mixed.value.code == "mixed_representation"
    later = bind_snapshot_lineage(ui_wf, session_id="sess-a", turn_id="0002")
    with pytest.raises(SnapshotAuthorityError) as cross_turn:
        compare_snapshot_authority(ui_snap, later)
    assert cross_turn.value.code == "cross_turn_lineage"
    prompt_wf, _ = ingest_workflow_and_ui({"prompt": _simple_api(), "client_id": "x"})
    compare_snapshot_authority(snapshot_of(api_wf), snapshot_of(prompt_wf))


def test_model_python_render_uses_retained_snapshot_ir() -> None:
    from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python

    workflow, _ = ingest_workflow_and_ui(_ui_graph())
    snapshot = snapshot_of(workflow)
    rendered = emit_agent_edit_python(snapshot.workflow)
    assert "LoadImage" in rendered
    assert "SaveImage" in rendered
    assert "UnknownCustomNode" in rendered
    workflow.nodes["1"].class_type = "MutatedLive"
    again = emit_agent_edit_python(snapshot.workflow)
    assert "MutatedLive" not in again
    assert "LoadImage" in again


def test_recovered_ensure_ingest_uses_retained_snapshot() -> None:
    from vibecomfy.comfy_nodes.agent._frag_ingest import _ensure_ingest_workflow
    from vibecomfy.comfy_nodes.agent._frag_state import AgentEditState

    workflow, graph = ingest_workflow_and_ui(_ui_graph())
    snapshot = snapshot_of(workflow)
    state = AgentEditState(
        task="edit",
        graph={"nodes": "poisoned-raw-must-not-be-redecoded"},
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=Path("/tmp/unused"),
        turn_dir=Path("/tmp/unused"),
        request_path=Path("/tmp/unused"),
        original_ui_path=Path("/tmp/unused"),
        before_py_path=Path("/tmp/unused"),
        after_py_path=Path("/tmp/unused"),
        projection_path=Path("/tmp/unused"),
        model_request_path=Path("/tmp/unused"),
        model_response_path=Path("/tmp/unused"),
        candidate_ui_path=Path("/tmp/unused"),
        messages_path=Path("/tmp/unused"),
        workflow=None,
        workflow_snapshot=snapshot,
    )
    recovered = _ensure_ingest_workflow(state)
    assert recovered is snapshot.workflow
    assert state.graph == {"nodes": "poisoned-raw-must-not-be-redecoded"}
