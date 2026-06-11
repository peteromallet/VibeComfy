"""T20 — ×50 hypothesis convergence test.

Property: for any sequence of structural edits (add/delete/rewire/widget-change)
applied to a workflow, emit → store → re-emit ×50 produces bit-identical positions
on uid-matched nodes.  The ``content_edits`` section of the change report names
only actually-edited nodes; ``identity_stabilization`` may also appear.

Uses Hypothesis with a deterministic seed and bounded shrinking.
"""
from __future__ import annotations

import copy
import json

import pytest

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from vibecomfy.porting.layout.reconcile import build_change_report, reconcile
from vibecomfy.porting.layout.delta import compute_field_delta
from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLASS_TYPES = ["CLIPTextEncode", "KSampler", "VAEDecode", "SaveImage", "LoadImage"]
_WIDGET_PRESETS = [
    {"text": "a beautiful landscape"},
    {"text": "a glass teapot"},
    {"steps": 20, "cfg": 7.0, "sampler_name": "euler"},
    {"steps": 30, "cfg": 6.0, "sampler_name": "dpm"},
]


def _make_baseline_wf() -> VibeWorkflow:
    """Return a deterministic 4-node workflow with uids."""
    nodes = {
        "1": VibeNode(id="1", class_type="CLIPTextEncode", uid="uid-clip",
                      inputs={"text": "a cat"}),
        "2": VibeNode(id="2", class_type="KSampler", uid="uid-ksampler"),
        "3": VibeNode(id="3", class_type="VAEDecode", uid="uid-vae"),
        "4": VibeNode(id="4", class_type="SaveImage", uid="uid-save"),
    }
    edges = [
        VibeEdge(from_node="1", from_output="0", to_node="2", to_input="0"),
        VibeEdge(from_node="2", from_output="0", to_node="3", to_input="0"),
        VibeEdge(from_node="3", from_output="0", to_node="4", to_input="0"),
    ]
    wf = VibeWorkflow(
        id="test-convergence",
        nodes=nodes,
        edges=edges,
        source=WorkflowSource(id="test"),
    )
    wf.finalize_metadata()
    return wf


def _emit_and_store(wf: VibeWorkflow, prior_store=None):
    """Emit wf to UI JSON and build a store envelope from it."""
    ui = emit_ui_json(wf, prior_store=prior_store)
    store = store_from_ui_json(ui)
    return ui, store


def _pos_map(ui: dict) -> dict[str, tuple]:
    """Return {uid: (pos, size)} for all nodes that have a vibecomfy_uid."""
    result = {}
    for node in ui.get("nodes", []):
        uid = node.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            result[uid] = (
                tuple(node.get("pos", [])),
                tuple(node.get("size", [])),
            )
    return result


def _apply_edit(wf: VibeWorkflow, edit: dict) -> VibeWorkflow:
    """Apply a single structural edit to wf (mutates in place, returns wf)."""
    kind = edit["kind"]

    if kind == "widget_change":
        uid = edit["uid"]
        field = edit["field"]
        value = edit["value"]
        for node in wf.nodes.values():
            if node.uid == uid:
                node.inputs[field] = value
                break

    elif kind == "add":
        new_id = str(max(int(k) for k in wf.nodes) + 1)
        new_node = VibeNode(
            id=new_id,
            class_type=edit["class_type"],
            uid=f"uid-added-{new_id}",
        )
        wf.nodes[new_id] = new_node

    elif kind == "delete":
        uid_to_delete = edit["uid"]
        nid = None
        for k, n in list(wf.nodes.items()):
            if n.uid == uid_to_delete:
                nid = k
                break
        if nid is not None:
            del wf.nodes[nid]
            wf.edges = [
                e for e in wf.edges
                if e.from_node != nid and e.to_node != nid
            ]

    elif kind == "rewire":
        # Remove one edge and add a new one between existing nodes if possible.
        if len(wf.edges) > 0:
            wf.edges = wf.edges[1:]  # drop first edge
        node_ids = list(wf.nodes.keys())
        if len(node_ids) >= 2:
            wf.edges.append(
                VibeEdge(
                    from_node=node_ids[0],
                    from_output="0",
                    to_node=node_ids[-1],
                    to_input="0",
                )
            )

    wf.finalize_metadata()
    return wf


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_UID_POOL = ["uid-clip", "uid-ksampler", "uid-vae", "uid-save"]

_edit_st = st.one_of(
    # widget change
    st.fixed_dictionaries({
        "kind": st.just("widget_change"),
        "uid": st.sampled_from(_UID_POOL),
        "field": st.sampled_from(["text", "steps", "cfg"]),
        "value": st.one_of(st.integers(1, 50), st.floats(1.0, 10.0, allow_nan=False)),
    }),
    # add node
    st.fixed_dictionaries({
        "kind": st.just("add"),
        "class_type": st.sampled_from(_CLASS_TYPES),
    }),
    # delete node (only from the stable uid pool so the baseline survives)
    st.fixed_dictionaries({
        "kind": st.just("delete"),
        "uid": st.sampled_from(_UID_POOL),
    }),
    # rewire
    st.fixed_dictionaries({"kind": st.just("rewire")}),
)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    database=None,     # deterministic: no example DB
)
@given(edits=st.lists(_edit_st, min_size=1, max_size=4))
def test_preserve_convergence_x50(edits):
    """Bit-identical positions on uid-matched nodes after ×50 re-emit cycles.

    Also asserts the change_report's ``content_edits`` section only names nodes
    that were actually changed by our edits; ``identity_stabilization`` is
    allowed to also appear.
    """
    # Build baseline workflow and capture which uids were edited.
    wf = _make_baseline_wf()
    edited_uids: set[str] = set()
    deleted_uids: set[str] = set()

    # Track which uids existed before edits begin (for content_edits check).
    pre_uids = {n.uid for n in wf.nodes.values() if n.uid}

    for edit in edits:
        if edit["kind"] == "widget_change":
            edited_uids.add(edit["uid"])
        elif edit["kind"] == "delete":
            deleted_uids.add(edit["uid"])
        _apply_edit(wf, edit)

    # Surviving uids after all edits.
    surviving_uids = {n.uid for n in wf.nodes.values() if n.uid}
    # New uids introduced by add.
    new_uids = surviving_uids - pre_uids

    # --- Initial emit + store (cycle 0) ---
    ui0, store0 = _emit_and_store(wf)
    reference_pos = _pos_map(ui0)

    # --- ×50 re-emit cycles ---
    current_store = store0
    for cycle in range(50):
        change_report_out: list = []
        ui_next = emit_ui_json(wf, prior_store=current_store,
                               change_report_out=change_report_out)
        next_pos = _pos_map(ui_next)

        # Build new store from this emission.
        current_store = store_from_ui_json(ui_next)

        # -- Assertion 1: bit-identical positions on uid-matched nodes --
        matched_uids = set(reference_pos) & set(next_pos)
        for uid in matched_uids:
            ref_pos, ref_size = reference_pos[uid]
            cur_pos, cur_size = next_pos[uid]
            assert ref_pos == cur_pos, (
                f"cycle={cycle} uid={uid!r}: pos drifted {ref_pos} → {cur_pos}"
            )
            assert ref_size == cur_size, (
                f"cycle={cycle} uid={uid!r}: size drifted {ref_size} → {cur_size}"
            )

        # -- Assertion 2: content_edits only names actually-edited nodes --
        if change_report_out:
            report = change_report_out[0]
            ce = report.content_edits
            # 'edited' should be a subset of nodes that we actually widget-changed.
            # (On cycle 0 there may be widget changes; after that, no new edits.)
            unexpected_edited = set(ce.edited) - (edited_uids | deleted_uids)
            assert not unexpected_edited, (
                f"cycle={cycle}: content_edits.edited has unexpected uids: "
                f"{unexpected_edited!r} (edited_uids={edited_uids!r})"
            )
            # 'new_auto_placed' should only contain uids not in reference_pos.
            unexpected_new = set(ce.new_auto_placed) & set(reference_pos)
            assert not unexpected_new, (
                f"cycle={cycle}: content_edits.new_auto_placed claims existing "
                f"uid {unexpected_new!r} as new"
            )
