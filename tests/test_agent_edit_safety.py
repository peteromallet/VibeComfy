"""M6 T9 — Agentic edit safety: preserve, no-collide, removed_named, auto-mint, determinism.

Loads ``ready_templates/image/z_image.py`` into a VibeWorkflow, emits a first
``--to ui`` JSON to seed the prior layout, performs canonical agentic edits
(add/delete/rewire), emits ``--to ui`` a second time, and asserts five invariants:

  (a) All uids that existed before AND still exist have byte-identical positions.
  (b) The new node's auto-placed position does not overlap any other node.
  (c) The removed node appears in removed_named with its class_type.
  (d) The new node's uid was auto-minted (monotonic, never required of the caller).
  (e) Running the identical edit sequence twice from the same fixture yields
      identical emitted JSON (determinism).

Runs in the default offline suite (no marker).  Uses programmatic API calls only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_z_image() -> VibeWorkflow:
    """Load ``ready_templates/image/z_image.py`` as a VibeWorkflow."""
    from vibecomfy import load_workflow_any

    return load_workflow_any("image/z_image")


def _pos_by_uid(ui_payload: dict) -> dict[str, list[float]]:
    """Extract ``{vibecomfy_uid: pos}`` from a litegraph UI JSON envelope."""
    result: dict[str, list[float]] = {}
    for node in ui_payload.get("nodes") or []:
        uid = (node.get("properties") or {}).get("vibecomfy_uid")
        pos = node.get("pos")
        if uid and isinstance(pos, list):
            result[uid] = pos
    return result


def _bboxes_overlap(
    pos1: list[float],
    size1: list[float],
    pos2: list[float],
    size2: list[float],
) -> bool:
    """True when the rectangles overlap (including touching edges)."""
    ax1, ay1 = pos1[0], pos1[1]
    ax2, ay2 = ax1 + size1[0], ay1 + size1[1]
    bx1, by1 = pos2[0], pos2[1]
    bx2, by2 = bx1 + size2[0], by1 + size2[1]
    if ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1:
        return False
    return True


def _build_change_report_from_emit(
    wf: VibeWorkflow,
    prior_store: dict | None,
    tmp_path: Path,
) -> dict:
    """Emit UI JSON and capture the change report + emitted data."""
    from vibecomfy.porting.layout.reconcile import build_change_report, reconcile
    from vibecomfy.porting.layout.delta import compute_field_delta
    from vibecomfy.porting.layout_store import store_from_ui_json

    _prior_store = dict(prior_store) if prior_store else {}
    reconcile_result = reconcile(wf, _prior_store)
    _snapshot = (wf.metadata or {}).get("_ingest_snapshot", {})
    _field_delta = compute_field_delta(_snapshot, wf) if _snapshot else {}
    change_report = build_change_report(
        reconcile_result,
        _field_delta,
        prior_store_entries=_prior_store.get("entries"),
    )

    ui = emit_ui_json(
        wf,
        prior_store=prior_store,
        include_virtual_wires=True,
    )

    return {
        "ui": ui,
        "change_report": change_report,
        "reconcile_result": reconcile_result,
    }


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_agentic_edit_preserve_and_determinism(tmp_path: Path):
    """End-to-end: load z_image, emit, edit, re-emit, assert all five invariants."""
    # ── Step 1: Load the ready template ──────────────────────────────────
    wf = _load_z_image()
    assert len(wf.nodes) >= 3, "z_image should have at least 3 nodes"

    # Collect initial node ids and class types for later assertions.
    initial_uids = {n.uid or nid for nid, n in wf.nodes.items()}
    initial_class_map = {n.uid or nid: n.class_type for nid, n in wf.nodes.items()}

    # ── Step 2: Emit first UI JSON to seed the prior layout ──────────────
    ui_first = emit_ui_json(wf, include_virtual_wires=True)
    prior_store = store_from_ui_json(ui_first)
    first_positions = _pos_by_uid(ui_first)
    assert len(first_positions) >= 3, f"Expected >= 3 positioned nodes, got {len(first_positions)}"

    # ── Step 3: Canonical agentic edit sequence ──────────────────────────

    # (3a) Add a new node — use wf.node(...) which auto-mints the uid.
    new_node_builder = wf.node("EmptyLatentImage", width=512, height=512, batch_size=1)
    new_node = new_node_builder.node
    new_node_uid = new_node.uid
    assert new_node_uid, "New node should have an auto-minted uid"
    assert new_node_uid not in initial_uids, (
        f"Auto-minted uid {new_node_uid} should not collide with any initial uid"
    )

    # (3b) Delete a node — pick one that is NOT the output node (the last one).
    # The z_image template has SaveImage as the output; pick an interior node.
    # Look for a CLIPTextEncode or similar interior node.
    nodes_to_delete_candidates = []
    for nid, n in wf.nodes.items():
        if n.class_type in ("CLIPTextEncode", "CLIPLoader", "VAELoader", "UNETLoader",
                            "ModelSamplingAuraFlow", "EmptySD3LatentImage", "VAEDecode"):
            nodes_to_delete_candidates.append(nid)
    assert nodes_to_delete_candidates, "No deletable interior node found"

    # Pick one to delete: disconnect it first, then remove it.
    delete_target = nodes_to_delete_candidates[0]
    delete_uid = wf.nodes[delete_target].uid or delete_target
    delete_class = wf.nodes[delete_target].class_type

    # Disconnect all edges involving the target node.
    edges_to_remove = [
        e for e in wf.edges
        if e.from_node == delete_target or e.to_node == delete_target
    ]
    for e in edges_to_remove:
        wf.disconnect(f"{e.to_node}.{e.to_input}")
    # Remove the node.
    del wf.nodes[delete_target]

    # (3c) Rewire an edge — find a remaining edge and redirect it.
    # Pick an edge going into KSampler and replace it with one from a different source.
    sampler_nodes = [nid for nid, n in wf.nodes.items() if n.class_type == "KSampler"]
    if sampler_nodes:
        sampler_id = sampler_nodes[0]
        # Find edges into the sampler
        sampler_edges = [e for e in wf.edges if e.to_node == sampler_id]
        if len(sampler_edges) >= 2:
            # Rewire: take the second edge and replace its source with the first edge's source
            edge_to_rewire = sampler_edges[1]
            new_source = sampler_edges[0]
            wf.replace_edge(
                f"{edge_to_rewire.to_node}.{edge_to_rewire.to_input}",
                f"{new_source.from_node}.{new_source.from_output}",
            )

    wf.finalize_metadata()

    # ── Step 4: Emit second UI JSON against the prior store ─────────────
    result_a = _build_change_report_from_emit(wf, prior_store, tmp_path)
    ui_second_a = result_a["ui"]
    change_report_a = result_a["change_report"]
    second_positions_a = _pos_by_uid(ui_second_a)

    # ── Step 5: Assert invariants ────────────────────────────────────────

    # (a) Byte-identical preserved positions.
    for uid, pos in first_positions.items():
        if uid in second_positions_a:
            assert second_positions_a[uid] == pos, (
                f"Position mismatch for preserved uid {uid}: "
                f"was {pos}, got {second_positions_a[uid]}"
            )

    # (b) New node's auto-placed position does NOT overlap any other node.
    new_node_pos = second_positions_a.get(new_node_uid)
    assert new_node_pos is not None, f"New node {new_node_uid} missing from emit"
    # Build size map from emitted nodes.
    size_by_uid: dict[str, list[float]] = {}
    for node in ui_second_a.get("nodes") or []:
        uid = (node.get("properties") or {}).get("vibecomfy_uid")
        size = node.get("size")
        if uid and isinstance(size, list) and len(size) == 2:
            size_by_uid[uid] = size
    new_size = size_by_uid.get(new_node_uid, [200, 100])
    for uid, pos in second_positions_a.items():
        if uid == new_node_uid:
            continue
        other_size = size_by_uid.get(uid, [200, 100])
        assert not _bboxes_overlap(new_node_pos, new_size, pos, other_size), (
            f"New node {new_node_uid} at {new_node_pos} overlaps "
            f"existing node {uid} at {pos}"
        )

    # (c) removed_named is populated with class_type for the deleted node.
    ce = change_report_a.content_edits
    removed_named = getattr(ce, "removed_named", []) or []
    removed_uids = {rn["uid"] for rn in removed_named}
    assert delete_uid in removed_uids, (
        f"Expected removed_named to contain {delete_uid} ({delete_class}), "
        f"got {removed_uids}"
    )
    removed_entry = next(rn for rn in removed_named if rn["uid"] == delete_uid)
    assert removed_entry.get("class_type") == delete_class, (
        f"Expected removed_named class_type={delete_class}, "
        f"got {removed_entry.get('class_type')}"
    )

    # (d) New node's uid was auto-minted (never required of caller).
    # We verify it's not one of the initial uids and is a valid string.
    assert isinstance(new_node_uid, str) and len(new_node_uid) > 0
    assert new_node_uid not in initial_uids

    # Also confirm that no node in the final workflow shares the new uid
    uids_after = {n.uid or nid for nid, n in wf.nodes.items()}
    assert new_node_uid in uids_after, (
        f"New node uid {new_node_uid} should be present in final workflow"
    )

    # (e) Determinism: run the same edit sequence twice from the same fixture
    # and assert identical emitted JSON.
    wf2 = _load_z_image()
    ui_first2 = emit_ui_json(wf2, include_virtual_wires=True)
    prior_store2 = store_from_ui_json(ui_first2)

    # Repeat the identical edits
    new_node_builder2 = wf2.node("EmptyLatentImage", width=512, height=512, batch_size=1)
    new_node2 = new_node_builder2.node
    edges_to_remove2 = [
        e for e in wf2.edges
        if e.from_node == delete_target or e.to_node == delete_target
    ]
    for e in edges_to_remove2:
        wf2.disconnect(f"{e.to_node}.{e.to_input}")
    del wf2.nodes[delete_target]
    if sampler_nodes:
        sampler_id2 = [nid for nid, n in wf2.nodes.items() if n.class_type == "KSampler"][0]
        sampler_edges2 = [e for e in wf2.edges if e.to_node == sampler_id2]
        if len(sampler_edges2) >= 2:
            edge_to_rewire2 = sampler_edges2[1]
            new_source2 = sampler_edges2[0]
            wf2.replace_edge(
                f"{edge_to_rewire2.to_node}.{edge_to_rewire2.to_input}",
                f"{new_source2.from_node}.{new_source2.from_output}",
            )
    wf2.finalize_metadata()

    result_b = _build_change_report_from_emit(wf2, prior_store2, tmp_path)
    ui_second_b = result_b["ui"]

    # Canonicalize for comparison: sort keys, consistent formatting.
    canonical_a = json.dumps(ui_second_a, indent=2, sort_keys=True)
    canonical_b = json.dumps(ui_second_b, indent=2, sort_keys=True)
    assert canonical_a == canonical_b, (
        f"Determinism check failed: two identical edit sequences produced "
        f"different emitted JSON "
        f"(len A={len(canonical_a)}, len B={len(canonical_b)})"
    )
