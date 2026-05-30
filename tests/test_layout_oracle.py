"""Oracle tests for layout_vector and layout_drift.

Verifies that the oracle catches position perturbations, reports size invariance,
flags unmatched keys, and falls back through the full key-kind chain.
"""
from __future__ import annotations

from vibecomfy.porting.layout import layout_drift, layout_vector


def _make_ui(nodes, groups=None):
    return {"nodes": nodes, "groups": groups or []}


def _node(id_, pos, size=(200, 100), mode=0, uid=None, vid=None):
    props = {}
    if uid:
        props["vibecomfy_uid"] = uid
    if vid:
        props["vibecomfy_id"] = vid
    return {"id": id_, "pos": list(pos), "size": list(size), "mode": mode, "properties": props}


def test_layout_drift_flags_eight_px_perturbation():
    uid = "node-uid-alpha"
    before_ui = _make_ui([_node(1, (100, 200), uid=uid)])
    after_ui = _make_ui([_node(1, (108, 200), uid=uid)])

    before = layout_vector(before_ui)
    after = layout_vector(after_ui)
    report = layout_drift(before, after)

    # max_pos_delta is 8.0 (Euclidean: sqrt((108-100)^2 + (200-200)^2) = 8.0)
    assert report.max_pos_delta == 8.0
    # The perturbation is attributed to the correct uid
    max_key = max(report.per_key_diff, key=lambda k: report.per_key_diff[k]["pos_delta"])
    assert (max_key, report.max_pos_delta) == (uid, 8.0)


def test_max_size_delta_zero_invariance():
    uid = "node-uid-beta"
    before_ui = _make_ui([_node(2, (100, 200), size=(200, 100), uid=uid)])
    # Same size, different position → size_delta must be 0
    after_ui = _make_ui([_node(2, (150, 250), size=(200, 100), uid=uid)])

    report = layout_drift(layout_vector(before_ui), layout_vector(after_ui))
    assert report.max_size_delta == 0.0

    # Symmetric: same position, different size → pos_delta must be 0
    uid2 = "node-uid-gamma"
    before_size = _make_ui([_node(3, (0, 0), size=(100, 100), uid=uid2)])
    after_size = _make_ui([_node(3, (0, 0), size=(200, 300), uid=uid2)])
    report2 = layout_drift(layout_vector(before_size), layout_vector(after_size))
    assert report2.max_pos_delta == 0.0


def test_unmatched_keys_reported():
    uid_a = "node-uid-a"
    uid_b = "node-uid-b"
    uid_c = "node-uid-c"

    # before has A and B; after has B and C → A and C are unmatched
    before_ui = _make_ui([_node(1, (0, 0), uid=uid_a), _node(2, (100, 0), uid=uid_b)])
    after_ui = _make_ui([_node(2, (100, 0), uid=uid_b), _node(3, (200, 0), uid=uid_c)])

    report = layout_drift(layout_vector(before_ui), layout_vector(after_ui))
    assert uid_a in report.unmatched_keys
    assert uid_c in report.unmatched_keys
    assert uid_b not in report.unmatched_keys


def test_layout_vector_falls_back_to_display_id_for_uidless_nodes():
    uid_node = {"id": 1, "pos": [0, 0], "size": [100, 100], "mode": 0,
                "properties": {"vibecomfy_uid": "my-uid"}}
    vid_node = {"id": 2, "pos": [0, 0], "size": [100, 100], "mode": 0,
                "properties": {"vibecomfy_id": "MyNode_0"}}
    int_node = {"id": 3, "pos": [0, 0], "size": [100, 100], "mode": 0,
                "properties": {}}

    ui = _make_ui([uid_node, vid_node, int_node])
    vec = layout_vector(ui)

    # uid path — vibecomfy_uid present
    assert "my-uid" in vec
    assert vec["my-uid"]["key_kind"] == "uid"

    # vid path — vibecomfy_uid absent, vibecomfy_id present
    assert "MyNode_0" in vec
    assert vec["MyNode_0"]["key_kind"] == "vid"

    # int_id path — neither uid nor vid present, fallback to str(id)
    assert "3" in vec
    assert vec["3"]["key_kind"] == "int_id"

    # All three key_kind levels exercised in one vector
    key_kinds = {entry["key_kind"] for entry in vec.values()}
    assert key_kinds == {"uid", "vid", "int_id"}
