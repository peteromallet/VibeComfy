"""Tests for vibecomfy.porting.layout.delta.compute_field_delta.

Covers: no-change, widget-edit, rewire (incoming edge change), added node
(snapshot-absent), removed node (in snapshot but not in current IR),
and snapshot-absent node omission.
"""
from __future__ import annotations

import copy

from vibecomfy.ingest.normalize import from_api as convert_to_vibe_format
from vibecomfy.ingest.snapshot import capture_ingest_snapshot
from vibecomfy.porting.layout.delta import compute_field_delta
from vibecomfy.porting.lowering import clone_uid
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


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


def test_no_mutation_loop_lowered_workflow_produces_empty_delta():
    """B03 finding 3 oracle: an already-lowered loop workflow compared to its
    own snapshot must yield NO ``semantic_link_set`` deltas.

    Before (snapshot of the lowered graph) holds the loop-clone consumer uids
    ``source/image -> loop:iter0:consumer/images`` and
    ``source/image -> loop:iter1:consumer/images``; the live set collapses both
    clones to ``source/image -> consumer/images``.  The before set must be
    canonicalized with loop-clone aliases corroborated by validated live
    lowering metadata so the
    unchanged workflow compares equal and produces an empty delta.
    """
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["7"] = VibeNode("7", "DynamicRows", uid="source")
    for iteration in range(2):
        node_id = str(20 + iteration)
        lowered_uid = clone_uid("loop", "consumer", iteration)
        wf.nodes[node_id] = VibeNode(
            node_id,
            "SaveImage",
            uid=lowered_uid,
            metadata={
                "vibecomfy.lowering": {
                    "source_uid": "consumer",
                    "loop_uid": "loop",
                    "iteration_index": iteration,
                }
            },
        )
        wf.edges.append(VibeEdge("7", "image", node_id, "images"))

    # Snapshot captured AFTER lowering; the workflow is then left UNCHANGED.
    snap = capture_ingest_snapshot({}, wf)
    delta = compute_field_delta(snap, wf)
    assert delta == {}


# ---------------------------------------------------------------------------
# SetNode-as-source passthrough (B03 rework4: oracle blocking issue)
# ---------------------------------------------------------------------------

def _setnode_passthrough_wf() -> VibeWorkflow:
    """Minimal corpus-shaped passthrough: ``36:0 → SetNode 37 → 40:samples``.

    Mirrors the real corpus case ``36:2 → SetNode 37:LATENT → 40:samples``
    (external_workflows/corpus/011c7ad91694b8c4.json) where the SetNode is the
    unambiguous unique inbound/outbound path between a producer and a consumer.
    """
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["36"] = VibeNode("36", "LTXVCropGuides", uid="36")
    wf.nodes["37"] = VibeNode("37", "SetNode", uid="37", inputs={"name": "croped_latent"})
    wf.nodes["40"] = VibeNode("40", "VAEDecode", uid="40")
    wf.edges = [
        VibeEdge("36", "0", "37", "LATENT"),
        VibeEdge("37", "0", "40", "samples"),
    ]
    return wf


def test_unchanged_setnode_passthrough_source_produces_no_delta():
    """An unchanged ``A → SetNode → B`` passthrough must resolve through the
    SetNode's unique inbound terminal and yield NO delta and no refusal.

    Regression for the B03 oracle finding: the SetNode-as-source case was
    unconditionally reported as ``setnode_as_source``, which fabricated a
    semantic-link delta for every node and refused unrelated pinned nodes.
    """
    wf = _setnode_passthrough_wf()
    snap = capture_ingest_snapshot({}, wf)
    delta = compute_field_delta(snap, wf)
    assert delta == {}


def test_setnode_passthrough_source_change_detected():
    """Rewiring the SetNode's inbound terminal to a different source node must
    surface as a canonical semantic-link delta on the downstream consumer."""
    wf = _setnode_passthrough_wf()
    snap = capture_ingest_snapshot({}, wf)

    wf.nodes["36b"] = VibeNode("36b", "LTXVCropGuides", uid="36b")
    wf.edges = [
        VibeEdge("36b", "0", "37", "LATENT"),
        VibeEdge("37", "0", "40", "samples"),
    ]

    delta = compute_field_delta(snap, wf)
    assert "40" in delta
    semantic = delta["40"]["semantic_link_set"]
    assert semantic["before"] == (("36", "0", "40", "samples"),)
    assert semantic["after"] == (("36b", "0", "40", "samples"),)
    assert semantic["before"] != semantic["after"]
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ()


def test_setnode_passthrough_port_change_detected():
    """Switching the SetNode's inbound terminal to a different output port of
    the same source must surface as a canonical semantic-link delta."""
    wf = _setnode_passthrough_wf()
    snap = capture_ingest_snapshot({}, wf)

    wf.edges = [
        VibeEdge("36", "1", "37", "LATENT"),
        VibeEdge("37", "0", "40", "samples"),
    ]

    delta = compute_field_delta(snap, wf)
    assert "40" in delta
    semantic = delta["40"]["semantic_link_set"]
    assert semantic["before"] == (("36", "0", "40", "samples"),)
    assert semantic["after"] == (("36", "1", "40", "samples"),)
    assert semantic["before"] != semantic["after"]
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ()


def test_ambiguous_setnode_source_fails_closed_with_issue():
    """A SetNode-as-source with TWO inbound candidates is genuinely ambiguous:
    it must fail closed with the ``setnode_as_source`` issue and NO semantic
    link, instead of silently picking one candidate."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["36"] = VibeNode("36", "ProducerA", uid="36")
    wf.nodes["38"] = VibeNode("38", "ProducerB", uid="38")
    wf.nodes["37"] = VibeNode("37", "SetNode", uid="37", inputs={"name": "LATENT"})
    wf.nodes["40"] = VibeNode("40", "Consumer", uid="40")
    wf.edges = [
        VibeEdge("36", "0", "37", "LATENT"),
        VibeEdge("38", "0", "37", "LATENT"),
        VibeEdge("37", "0", "40", "samples"),
    ]
    snap = capture_ingest_snapshot({}, wf)

    delta = compute_field_delta(snap, wf)
    assert "40" in delta
    semantic = delta["40"]["semantic_link_set"]
    assert semantic["before"] == ()
    assert semantic["after"] == ()
    assert any(
        issue.startswith("setnode_as_source:37:2")
        for issue in semantic["before_resolution_issues"]
    )
    assert any(
        issue.startswith("setnode_as_source:37:2")
        for issue in semantic["after_resolution_issues"]
    )


# ---------------------------------------------------------------------------
# GetNode input-chain display edges (B03 rework5: oracle blocking issue)
# ---------------------------------------------------------------------------

def _getnode_chain_wf() -> VibeWorkflow:
    """``source → SetNode → Reroute → GetNode → consumer`` with the channel
    display edge, mirroring tests/test_virtual_wire_round_trip.py:70."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode("1", "CheckpointLoaderSimple", uid="uid-dynamic")
    wf.nodes["10"] = VibeNode("10", "SetNode", uid="10", inputs={"widget_0": "LATENT"})
    wf.nodes["14"] = VibeNode("14", "Reroute", uid="14")
    wf.nodes["11"] = VibeNode("11", "GetNode", uid="11", inputs={"widget_0": "LATENT"})
    wf.nodes["5"] = VibeNode("5", "KSampler", uid="consumer")
    wf.edges = [
        VibeEdge("1", "0", "10", "broadcast_in"),
        VibeEdge("10", "0", "14", "0"),
        VibeEdge("14", "0", "11", "broadcast_out"),
        VibeEdge("11", "0", "5", "model"),
    ]
    return wf


def test_unchanged_getnode_input_chain_produces_no_delta():
    """An unchanged ``source → SetNode → Reroute → GetNode → consumer`` chain
    resolves the GetNode display edge through its channel and yields NO delta
    and NO resolution issues (B03 oracle finding 3 regression).

    Before the fix, the edge entering the GetNode through ``broadcast_out``
    unconditionally emitted ``helper_input_unsupported``, which fabricated a
    semantic-link delta on every snapshot node and refused the unchanged
    workflow.
    """
    wf = _getnode_chain_wf()
    snap = capture_ingest_snapshot({}, wf)
    delta = compute_field_delta(snap, wf)
    assert delta == {}


def test_getnode_chain_source_change_detected():
    """Rewiring the channel's terminal source must surface as a canonical
    semantic-link delta on the downstream consumer, with no fabricated
    resolution issues."""
    wf = _getnode_chain_wf()
    snap = capture_ingest_snapshot({}, wf)

    wf.nodes["2"] = VibeNode("2", "CheckpointLoaderSimple", uid="uid-dynamic-b")
    wf.edges = [
        VibeEdge("2", "0", "10", "broadcast_in"),
        VibeEdge("10", "0", "14", "0"),
        VibeEdge("14", "0", "11", "broadcast_out"),
        VibeEdge("11", "0", "5", "model"),
    ]

    delta = compute_field_delta(snap, wf)
    assert "consumer" in delta
    semantic = delta["consumer"]["semantic_link_set"]
    assert semantic["before"] == (("uid-dynamic", "0", "consumer", "model"),)
    assert semantic["after"] == (("uid-dynamic-b", "0", "consumer", "model"),)
    assert semantic["before"] != semantic["after"]
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ()


def test_ambiguous_getnode_channel_fails_closed_with_issue():
    """Two SetNodes feeding one GetNode's channel is genuinely ambiguous: it
    must fail closed with the ``broadcast_setter_count`` issue on the nodes
    actually involved (the GetNode and its consumer), and NO silent
    resolution — while unrelated nodes stay out of the delta."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode("1", "ProducerA", uid="1")
    wf.nodes["2"] = VibeNode("2", "ProducerB", uid="2")
    wf.nodes["10"] = VibeNode("10", "SetNode", uid="10", inputs={"widget_0": "LATENT"})
    wf.nodes["12"] = VibeNode("12", "SetNode", uid="12", inputs={"widget_0": "LATENT"})
    wf.nodes["11"] = VibeNode("11", "GetNode", uid="11", inputs={"widget_0": "LATENT"})
    wf.nodes["5"] = VibeNode("5", "Consumer", uid="consumer")
    wf.edges = [
        VibeEdge("1", "0", "10", "broadcast_in"),
        VibeEdge("2", "0", "12", "broadcast_in"),
        VibeEdge("10", "0", "11", "broadcast_out"),
        VibeEdge("12", "0", "11", "broadcast_out"),
        VibeEdge("11", "0", "5", "images"),
    ]
    snap = capture_ingest_snapshot({}, wf)

    delta = compute_field_delta(snap, wf)
    assert "consumer" in delta
    semantic = delta["consumer"]["semantic_link_set"]
    assert semantic["before"] == ()
    assert semantic["after"] == ()
    assert any(
        issue.startswith("broadcast_setter_count:11:LATENT:2")
        for issue in semantic["before_resolution_issues"]
    )
    assert any(
        issue.startswith("broadcast_setter_count:11:LATENT:2")
        for issue in semantic["after_resolution_issues"]
    )
    # The ambiguous junction's own node carries the issue too...
    assert "11" in delta
    assert any(
        issue.startswith("broadcast_setter_count:11:LATENT:2")
        for issue in delta["11"]["semantic_link_set"]["after_resolution_issues"]
    )
    # ...and unrelated nodes are NOT fanned out.
    for unrelated in ("1", "2", "10", "12"):
        assert "semantic_link_set" not in delta.get(unrelated, {})


# ---------------------------------------------------------------------------
# Zero-candidate helper plumbing (B03 rework6: oracle regression)
# ---------------------------------------------------------------------------

def _orphaned_plumbing_wf() -> VibeWorkflow:
    """Mirrors the corpus pattern that refused at B03 HEAD: unbacked GetNode
    (no SetNode for its channel), dangling Reroute (no inbound), and a
    source-less SetNode-as-source all feeding real consumers.  These are
    stable display-plumbing properties of an unchanged workflow — the semantic
    resolution must degenerate them to opaque terminals instead of fabricating
    ``*:0`` resolution issues that refused schema-less dict-row consumers."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["35"] = VibeNode("35", "VHS_VideoCombine", uid="35")
    wf.nodes["56"] = VibeNode("56", "VHS_VideoCombine", uid="56")
    wf.nodes["66"] = VibeNode("66", "ImageScale", uid="66")
    wf.nodes["40"] = VibeNode("40", "Consumer", uid="40")
    wf.nodes["137"] = VibeNode("137", "GetNode", uid="137", inputs={"name": "fps"})
    wf.nodes["158"] = VibeNode("158", "Reroute", uid="158")
    wf.nodes["601"] = VibeNode("601", "SetNode", uid="601", inputs={"name": "LATENT"})
    wf.edges = [
        VibeEdge("137", "0", "35", "frame_rate"),
        VibeEdge("158", "0", "66", "round_to_multiple"),
        VibeEdge("601", "0", "40", "samples"),
    ]
    return wf


def test_unchanged_orphaned_helper_plumbing_produces_no_delta():
    """An unchanged workflow with unbacked GetNode / dangling Reroute /
    source-less SetNode plumbing yields NO delta and NO resolution issues.

    Before the fix, each zero-candidate helper emitted ``*:0`` resolution
    issues that were attributed to the consumers, fabricating a
    ``semantic_link_set`` delta and refusing the unchanged schema-less
    VHS_VideoCombine pins (B03 rework6: 6 corpus files refused at HEAD).
    """
    wf = _orphaned_plumbing_wf()
    snap = capture_ingest_snapshot({}, wf)
    delta = compute_field_delta(snap, wf)
    assert delta == {}


def test_adding_setter_to_orphaned_getnode_channel_is_detected():
    """Backing an orphaned GetNode channel with a real SetNode changes the
    canonical terminal from the opaque GetNode uid to the setter's source —
    the downstream consumer must surface a semantic-link delta (fail closed
    on the genuine difference)."""
    wf = _orphaned_plumbing_wf()
    snap = capture_ingest_snapshot({}, wf)

    wf.nodes["1"] = VibeNode("1", "LoadImage", uid="load-image")
    wf.nodes["10"] = VibeNode("10", "SetNode", uid="10", inputs={"widget_0": "fps"})
    wf.edges = [
        VibeEdge("1", "0", "10", "broadcast_in"),
        VibeEdge("10", "0", "137", "broadcast_out"),
        VibeEdge("137", "0", "35", "frame_rate"),
        VibeEdge("158", "0", "66", "round_to_multiple"),
        VibeEdge("601", "0", "40", "samples"),
    ]

    delta = compute_field_delta(snap, wf)
    assert "35" in delta
    semantic = delta["35"]["semantic_link_set"]
    assert semantic["before"] == (("137", "0", "35", "frame_rate"),)
    assert semantic["after"] == (("load-image", "0", "35", "frame_rate"),)
    assert semantic["before"] != semantic["after"]
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ()
    # The GetNode's own incident changed too: it is no longer the opaque
    # terminal of the edge (the channel now resolves past it).
    assert delta["137"]["semantic_link_set"]["before"] == (("137", "0", "35", "frame_rate"),)
    assert delta["137"]["semantic_link_set"]["after"] == ()
    # Unrelated consumers of the other orphaned plumbing stay clean.
    for uid in ("56", "66", "40", "158", "601"):
        assert "semantic_link_set" not in delta.get(uid, {})


# ---------------------------------------------------------------------------
# Ghost endpoints (B03 rework7: oracle blocking issue)
# ---------------------------------------------------------------------------

def test_ghost_source_through_new_reroute_attributes_existing_consumer_issue():
    """A ghost source hidden behind a new Reroute must reach the existing
    terminal consumer instead of disappearing with the snapshot-absent helper.
    """
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["9"] = VibeNode("9", "SaveImage", uid="consumer")
    snap = capture_ingest_snapshot({}, wf)

    wf.nodes["8"] = VibeNode("8", "Reroute", uid="new-reroute")
    wf.edges = [
        VibeEdge("ghost", "0", "8", ""),
        VibeEdge("8", "0", "9", "images"),
    ]

    delta = compute_field_delta(snap, wf)
    semantic = delta["consumer"]["semantic_link_set"]
    assert semantic["before"] == ()
    assert semantic["after"] == ()
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ("unknown_source:ghost",)
    assert semantic["global_after_resolution_issues"] == ()


def test_new_source_to_ghost_consumer_carries_issue_on_new_source():
    """Issue-only deltas on snapshot-absent known endpoints must be retained."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["7"] = VibeNode("7", "DynamicRows", uid="existing-pin")
    snap = capture_ingest_snapshot({}, wf)

    wf.nodes["8"] = VibeNode("8", "KSampler", uid="new-source")
    wf.edges = [VibeEdge("8", "0", "ghost-consumer", "images")]

    delta = compute_field_delta(snap, wf)
    semantic = delta["new-source"]["semantic_link_set"]
    assert semantic["before"] == ()
    assert semantic["after"] == ()
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == (
        "unknown_consumer:ghost-consumer",
    )
    assert semantic["global_after_resolution_issues"] == ()
    assert "semantic_link_set" not in delta.get("existing-pin", {})


def test_known_source_to_ghost_consumer_edge_carries_attributed_issue():
    """A known source → missing-consumer edge must attribute ``unknown_consumer``
    to the source's uid so the issue lands on a snapshot-present fence target.

    Before the fix the issue was recorded globally but never attributed, and
    the global ``_after_issues`` result was discarded, so the semantic delta
    came back ``{}`` and the pin fence saw nothing (B03 oracle finding 3).
    """
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode("1", "Producer", uid="source")
    snap = capture_ingest_snapshot({}, wf)

    # Edit after snapshot: known source "1" gains an edge to a ghost consumer.
    wf.edges = [VibeEdge("1", "0", "ghost", "input")]

    delta = compute_field_delta(snap, wf)
    assert "source" in delta
    semantic = delta["source"]["semantic_link_set"]
    assert semantic["before"] == ()
    assert semantic["after"] == ()
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ("unknown_consumer:ghost",)
    # The issue is attributed, so it must NOT fan out as a global issue.
    assert semantic["global_before_resolution_issues"] == ()
    assert semantic["global_after_resolution_issues"] == ()


def test_fully_ghost_endpoint_edge_surfaces_global_issue():
    """An edge whose endpoints are BOTH missing has no per-uid attribution
    target; the delta must still surface the unresolved global issues on every
    snapshot-present fence target instead of returning ``{}``.

    The pin fence reads these global issues via ``_has_link_delta`` and refuses
    with a typed ``RefusedEmit`` — never an empty ``{}`` followed by a bare
    ``KeyError`` when the emitter tries to resolve the ghost consumer (B03
    rework7).
    """
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode("1", "Producer", uid="source")
    snap = capture_ingest_snapshot({}, wf)

    # Edit after snapshot: a fully ghost edge — neither endpoint is a node.
    wf.edges = [VibeEdge("ghost-a", "0", "ghost-b", "input")]

    delta = compute_field_delta(snap, wf)
    assert "source" in delta
    semantic = delta["source"]["semantic_link_set"]
    assert semantic["before"] == ()
    assert semantic["after"] == ()
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ()
    assert semantic["global_before_resolution_issues"] == ()
    assert semantic["global_after_resolution_issues"] == (
        "unknown_consumer:ghost-b",
        "unknown_source:ghost-a",
    )


def test_ordinary_clone_shaped_uid_without_lowering_metadata_has_no_delta():
    """A textual ``*:iterN:*`` UID is not lowering provenance by itself."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode("1", "Producer", uid="source")
    wf.nodes["2"] = VibeNode(
        "2", "Consumer", uid="ordinary:iter0:consumer"
    )
    wf.edges = [VibeEdge("1", "image", "2", "images")]

    snap = capture_ingest_snapshot({}, wf)

    assert compute_field_delta(snap, wf) == {}


def test_one_of_two_lowered_clones_repointed_to_new_source_is_attributed():
    """A global canonical change must reach the aliased snapshot fence target."""
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode("1", "Producer", uid="source-a")
    for iteration in range(2):
        node_id = str(20 + iteration)
        lowered_uid = clone_uid("loop", "consumer", iteration)
        wf.nodes[node_id] = VibeNode(
            node_id,
            "Consumer",
            uid=lowered_uid,
            metadata={
                "vibecomfy.lowering": {
                    "source_uid": "consumer",
                    "loop_uid": "loop",
                    "iteration_index": iteration,
                }
            },
        )
        wf.edges.append(VibeEdge("1", "image", node_id, "images"))
    snap = capture_ingest_snapshot({}, wf)

    wf.nodes["2"] = VibeNode("2", "Producer", uid="source-b")
    wf.edges = [
        edge
        for edge in wf.edges
        if not (edge.from_node == "1" and edge.to_node == "20")
    ]
    wf.edges.append(VibeEdge("2", "image", "20", "images"))

    delta = compute_field_delta(snap, wf)

    semantic = delta[clone_uid("loop", "consumer", 0)]["semantic_link_set"]
    assert semantic["before"] == (("source-a", "image", "consumer", "images"),)
    assert semantic["after"] == (
        ("source-a", "image", "consumer", "images"),
        ("source-b", "image", "consumer", "images"),
    )


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
    """Changing an incoming edge produces a canonical semantic-link delta."""
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
    semantic = delta["sampler-uid"]["semantic_link_set"]
    assert semantic["before"] != semantic["after"]
    assert semantic["before_resolution_issues"] == ()
    assert semantic["after_resolution_issues"] == ()


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
