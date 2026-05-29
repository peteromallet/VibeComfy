"""Tests for vibecomfy.porting.scope (T8 — sg_key + scoped inner uids)."""
from __future__ import annotations

import itertools

from vibecomfy.porting.scope import (
    compose_scope_path,
    mint_inner_uid,
    sanitize_subgraph_name,
    sg_key,
)
from vibecomfy.porting.uid import parse_uid


def _def(name=None, *, nodes=None, links=None, graph_uuid="uuid-1"):
    d: dict = {"graphUuid": graph_uuid}
    if name is not None:
        d["name"] = name
    d["nodes"] = nodes if nodes is not None else [
        {"id": 1, "type": "LoadImage", "pos": [0, 0], "properties": {"x": 1},
         "widgets_values": ["a.png"], "outputs": [{"name": "IMAGE", "links": [10], "type": "IMAGE"}]},
        {"id": 2, "type": "SaveImage", "pos": [200, 0], "properties": {},
         "widgets_values": ["prefix"], "inputs": [{"name": "images", "link": 10, "type": "IMAGE"}]},
    ]
    d["links"] = links if links is not None else [[10, 1, 0, 2, 0, "IMAGE"]]
    return d


# ---------------------------------------------------------------------------
# sg_key exclusion / inclusion invariants
# ---------------------------------------------------------------------------


def test_sg_key_invariant_to_graph_uuid():
    assert sg_key(_def("sub", graph_uuid="uuid-A")) == sg_key(_def("sub", graph_uuid="uuid-B"))


def test_sg_key_invariant_to_pos_and_widget_values():
    base = _def("sub")
    moved = _def("sub")
    moved["nodes"][0]["pos"] = [999, 999]
    moved["nodes"][0]["widgets_values"] = ["completely-different.png"]
    moved["nodes"][0]["properties"] = {"vibecomfy_uid": "zzz"}
    assert sg_key(base) == sg_key(moved)


def test_sg_key_changes_on_class_type_change():
    base = _def("sub")
    changed = _def("sub")
    changed["nodes"][0]["type"] = "LoadImageMask"
    assert sg_key(base) != sg_key(changed)


def test_sg_key_changes_on_topology_change():
    base = _def("sub")
    rewired = _def("sub", links=[[10, 2, 0, 1, 0, "IMAGE"]])
    assert sg_key(base) != sg_key(rewired)


def test_sg_key_nameless_fallback_does_not_raise():
    key = sg_key(_def(name=None))
    assert isinstance(key, str) and key
    # hash-only: no name prefix, no uid separators
    assert "#" not in key and "/" not in key


def test_sg_key_named_prefix_sanitized():
    key = sg_key(_def("a/b#c"))
    assert key.startswith("a_b_c:")
    assert "#" not in key.split(":", 1)[0]
    assert "/" not in key.split(":", 1)[0]


def test_sanitize_subgraph_name():
    assert sanitize_subgraph_name("a/b#c") == "a_b_c"


# ---------------------------------------------------------------------------
# scope_path composition + cloned-instance distinctness
# ---------------------------------------------------------------------------


def test_compose_scope_path_top_level_empty():
    assert compose_scope_path([]) == ""


def test_compose_scope_path_chain():
    assert compose_scope_path(["outer:aa", "inner:bb"]) == "outer:aa/inner:bb"


def test_two_clones_with_colliding_inner_ids_get_distinct_uids():
    """Two clones of one definition share scope_path but mint distinct uids."""
    definition = _def("sub")
    scope = compose_scope_path([sg_key(definition)])
    counter = itertools.count(1)
    mint = lambda: f"n{next(counter)}"  # noqa: E731 — monotonic, never reused

    # Both clones have an inner node with the same integer id (e.g. "1").
    clone_a_uid = mint_inner_uid(scope, mint)
    clone_b_uid = mint_inner_uid(scope, mint)

    assert clone_a_uid != clone_b_uid
    # Same scope, distinct locals.
    assert parse_uid(clone_a_uid)[0] == parse_uid(clone_b_uid)[0] == scope
    assert parse_uid(clone_a_uid)[1] != parse_uid(clone_b_uid)[1]
