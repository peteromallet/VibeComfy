from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.plan_types import (
    LAYOUT_BEHAVIOR_NOTE,
    LAYOUT_BEHAVIOR_PRIMARY,
    LAYOUT_BEHAVIOR_SIDECAR,
    LAYOUT_BEHAVIOR_UNKNOWN,
    LAYOUT_BEHAVIOR_WALL,
    LAYOUT_BEHAVIORS,
    ROLE_HINT_HELPER,
    ROLE_HINT_LOADER,
    ROLE_HINT_OUTPUT,
    ROLE_HINT_SAMPLER,
    ROLE_HINT_UI,
    ROLE_HINT_UNKNOWN,
    ROLE_HINT_UTILITY,
)


def _subgraph_definition() -> dict:
    return {
        "name": "Inner Graph",
        "nodes": [
            {
                "id": 7,
                "type": "KSampler",
                "class_type": "KSampler",
                "pos": [10, 20],
                "size": [300, 100],
                "inputs": [],
                "outputs": [],
            }
        ],
        "links": [],
        "state": {"lastRerouteId": 5},
    }


def test_extract_graph_facts_uses_edit_ledger_scoped_identity_without_mutating_ui_json() -> None:
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "class_type": "CheckpointLoaderSimple",
                "pos": [0, 0],
                "size": [260, 80],
            }
        ],
        "links": [],
        "groups": [],
        "definitions": {"subgraphs": [_subgraph_definition()]},
    }
    before = deepcopy(ui)

    facts = extract_graph_facts(ui)

    assert ui == before
    assert facts.ref_for("", "1") is not None
    subgraph_refs = [
        fact
        for fact in facts.canonical_refs
        if fact.ref.scope_path and fact.ref.uid == "7"
    ]
    assert len(subgraph_refs) == 1
    assert subgraph_refs[0].display.endswith("::7 (KSampler)")
    assert any(scope.scope_path == subgraph_refs[0].ref.scope_path for scope in facts.summary.scopes)


def test_extract_graph_facts_captures_furniture_helpers_virtual_wires_and_last_reroute() -> None:
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "title": "Image In",
                "pos": [11.25, 22.5],
                "size": [315, 98],
                "color": "#112233",
                "bgcolor": "#445566",
                "flags": {"collapsed": True, "pinned": True},
                "mode": 2,
                "properties": {"vibecomfy_uid": "load-image", "custom": "kept"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "SetNode",
                "class_type": "SetNode",
                "properties": {"vibecomfy_uid": "set-latent"},
                "widgets_values": ["LATENT"],
            },
            {
                "id": 3,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "reroute-latent"},
                "inputs": [{"name": "", "type": "*", "link": 10}],
                "outputs": [{"name": "", "type": "*", "links": [11, 12]}],
            },
            {
                "id": 4,
                "type": "MarkdownNote",
                "class_type": "MarkdownNote",
                "properties": {"vibecomfy_uid": "note-1"},
            },
        ],
        "links": [
            [10, 1, 0, 3, 0, "IMAGE"],
            [11, 3, 0, 9, 0, "IMAGE"],
        ],
        "groups": [{"title": "Inputs", "bounding": [0, 0, 400, 200], "nodes": [1, 2]}],
        "extra": {
            "ds": {"scale": 0.9, "offset": [1, 2]},
            "virtual_wires": {
                "vw-ui": {
                    "type": "SetNode",
                    "channel": "LATENT",
                    "endpoints": [2, 3],
                }
            },
        },
        "state": {"lastRerouteId": 42},
    }
    sidecar = {
        "store_version": 2,
        "schema_hash": "test",
        "entries": {
            "load-image": {
                "pos": [11.25, 22.5],
                "size": [315, 98],
                "flags": {"collapsed": True},
            }
        },
        "groups": [{"title": "SidecarGroup"}],
        "extra": {"ds": {"scale": 0.5}},
        "lastRerouteId": 41,
        "definitions": {},
        "virtual_wires": {
            "vw-sidecar": {
                "type": "GetNode",
                "channel": "LATENT",
                "endpoints": ["set-latent", "reroute-latent"],
            }
        },
    }
    before = deepcopy(ui)
    sidecar_before = deepcopy(sidecar)

    facts = extract_graph_facts(ui, sidecar_envelope=sidecar)

    assert ui == before
    assert sidecar == sidecar_before

    furniture = {tuple(fact.ref.to_json()): fact for fact in facts.node_furniture}
    load_furniture = furniture[("", "load-image")]
    assert load_furniture.pos == (11.25, 22.5)
    assert load_furniture.flags["collapsed"] is True
    assert load_furniture.properties["custom"] == "kept"
    assert load_furniture.sidecar_entry_key == "load-image"

    helper_classes = {fact.class_type for fact in facts.helper_nodes}
    assert helper_classes == {"SetNode", "Reroute", "MarkdownNote"}
    assert {fact.helper_kind for fact in facts.helper_nodes} == {
        "virtual-wire",
        "reroute",
        "ui-note",
    }
    reroute = facts.reroutes[0]
    assert reroute.ref.to_json() == ["", "reroute-latent"]
    assert reroute.input_links == (10,)
    assert reroute.output_links == (11, 12)

    root_furniture = next(scope for scope in facts.scope_furniture if scope.scope_path == "")
    assert root_furniture.last_reroute_id == 42
    assert root_furniture.groups[0].title == "Inputs"
    assert root_furniture.groups[0].nodes == (1, 2)
    assert root_furniture.extra["ds"]["scale"] == 0.9

    virtual_wire_keys = {(fact.source, fact.key) for fact in facts.virtual_wires}
    assert virtual_wire_keys == {("sidecar", "vw-sidecar"), ("ui_extra", "vw-ui")}
    assert facts.sidecar_envelope["lastRerouteId"] == 41


def test_extract_graph_facts_orders_canonical_refs_and_json_stably() -> None:
    ui = {
        "nodes": [
            {
                "id": 20,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
            },
        ],
        "links": [[1, 2, 0, 20, 0, "IMAGE"]],
    }

    first = extract_graph_facts(ui)
    second = extract_graph_facts(ui)

    assert [fact.ref.to_json() for fact in first.canonical_refs] == [
        ["", "sample"],
        ["", "save"],
    ]
    assert first.canonical_refs[0].display == "<root>::sample (KSampler)"
    assert first.to_json() == second.to_json()
    assert first.summary.scopes[0].edge_count == 1
    assert first.summary.scopes[0].terminal_refs[0].to_json() == ["", "save"]


def test_extract_graph_facts_derives_effective_topology_with_helper_passthroughs() -> None:
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [100, 103]}],
            },
            {
                "id": 2,
                "type": "SetNode",
                "class_type": "SetNode",
                "properties": {"vibecomfy_uid": "set-image"},
                "widgets_values": ["shared-image"],
                "inputs": [{"name": "IMAGE", "type": "IMAGE", "link": 100}],
            },
            {
                "id": 3,
                "type": "GetNode",
                "class_type": "GetNode",
                "properties": {"vibecomfy_uid": "get-image"},
                "widgets_values": ["shared-image"],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [101]}],
            },
            {
                "id": 4,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "reroute-image"},
                "inputs": [{"name": "", "type": "*", "link": 101}],
                "outputs": [{"name": "", "type": "*", "links": [102]}],
            },
            {
                "id": 5,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample-a"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 102}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [104]}],
            },
            {
                "id": 6,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample-b"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 103}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [105]}],
            },
            {
                "id": 7,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 104}],
            },
            {
                "id": 8,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": "preview"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 105}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}],
            },
        ],
        "links": [
            [100, 1, 0, 2, 0, "IMAGE"],
            [101, 3, 0, 4, 0, "IMAGE"],
            [102, 4, 0, 5, 0, "IMAGE"],
            [103, 1, 0, 6, 0, "IMAGE"],
            [104, 5, 0, 7, 0, "IMAGE"],
            [105, 6, 0, 8, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    assert [(edge.source.uid, edge.target.uid) for edge in topology.effective_edges] == [
        ("load", "sample-a"),
        ("load", "sample-b"),
        ("sample-a", "save"),
        ("sample-b", "preview"),
    ]
    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    assert node_topology["load"].fan_out == 2
    assert node_topology["sample-a"].fan_in == 1
    assert node_topology["sample-a"].topological_rank == 1
    assert node_topology["sample-a"].wcc_id == node_topology["sample-b"].wcc_id
    assert node_topology["set-image"].fan_in == 0
    assert node_topology["reroute-image"].fan_out == 0
    assert node_topology["preview"].terminal_output_types == ("IMAGE",)

    assert [tuple(ref.uid for ref in path.path) for path in topology.terminal_paths] == [
        ("load", "sample-a", "save"),
        ("load", "sample-b", "preview"),
    ]
    assert [tuple(ref.uid for ref in topology.parallel_branch_candidates[0].branch_roots)] == [
        ("sample-a", "sample-b")
    ]
    assert topology.parallel_branch_candidates[0].source.uid == "load"
    assert [candidate.kind for candidate in topology.sampler_relation_candidates] == [
        "parallel_sampler_branch"
    ]
    assert facts.summary.scopes[0].wcc_count >= 1
    assert facts.summary.scopes[0].scc_count >= 1
    assert [candidate.kind for candidate in facts.summary.sampler_relation_candidates] == [
        "parallel_sampler_branch"
    ]


# ---------------------------------------------------------------------------
# LayoutBehavior on canonical refs
# ---------------------------------------------------------------------------


def test_canonical_refs_layout_behavior_loaders_primary() -> None:
    """Resource loaders derive layout_behavior=primary in graph facts."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "class_type": "CheckpointLoaderSimple",
                "properties": {"vibecomfy_uid": "ckpt"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["ckpt"].role_hint == ROLE_HINT_LOADER
    assert ref_map["ckpt"].layout_behavior == LAYOUT_BEHAVIOR_PRIMARY
    assert ref_map["ckpt"].is_helper is False


def test_canonical_refs_layout_behavior_output_wall() -> None:
    """Output nodes (SaveImage) derive layout_behavior=wall in graph facts."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["save"].role_hint == ROLE_HINT_OUTPUT
    assert ref_map["save"].layout_behavior == LAYOUT_BEHAVIOR_WALL
    assert ref_map["save"].is_helper is False


def test_canonical_refs_layout_behavior_helpers() -> None:
    """Helper nodes (SetNode, GetNode, Reroute, Note, MarkdownNote) get correct layout_behavior."""
    ui = {
        "nodes": [
            {"id": 1, "type": "SetNode", "class_type": "SetNode", "properties": {"vibecomfy_uid": "set-a"}, "widgets_values": ["ch1"]},
            {"id": 2, "type": "GetNode", "class_type": "GetNode", "properties": {"vibecomfy_uid": "get-a"}, "widgets_values": ["ch1"]},
            {"id": 3, "type": "Reroute", "class_type": "Reroute", "properties": {"vibecomfy_uid": "rr-a"}},
            {"id": 4, "type": "Note", "class_type": "Note", "properties": {"vibecomfy_uid": "note-a"}},
            {"id": 5, "type": "MarkdownNote", "class_type": "MarkdownNote", "properties": {"vibecomfy_uid": "md-a"}},
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}

    # SetNode / GetNode / Reroute → helper → sidecar
    assert ref_map["set-a"].role_hint == ROLE_HINT_HELPER
    assert ref_map["set-a"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR
    assert ref_map["set-a"].is_helper is True

    assert ref_map["get-a"].role_hint == ROLE_HINT_HELPER
    assert ref_map["get-a"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR
    assert ref_map["get-a"].is_helper is True

    assert ref_map["rr-a"].role_hint == ROLE_HINT_HELPER
    assert ref_map["rr-a"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR
    assert ref_map["rr-a"].is_helper is True

    # Note / MarkdownNote → ui → note
    assert ref_map["note-a"].role_hint == ROLE_HINT_UI
    assert ref_map["note-a"].layout_behavior == LAYOUT_BEHAVIOR_NOTE
    assert ref_map["note-a"].is_helper is True

    assert ref_map["md-a"].role_hint == ROLE_HINT_UI
    assert ref_map["md-a"].layout_behavior == LAYOUT_BEHAVIOR_NOTE
    assert ref_map["md-a"].is_helper is True


def test_canonical_refs_layout_behavior_sampler_primary() -> None:
    """Samplers derive layout_behavior=primary."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["sample"].role_hint == ROLE_HINT_SAMPLER
    assert ref_map["sample"].layout_behavior == LAYOUT_BEHAVIOR_PRIMARY
    assert ref_map["sample"].is_helper is False


def test_canonical_refs_layout_behavior_unknown_unknown() -> None:
    """Truly unknown class_type → unknown layout_behavior."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "TotallyUnknownNode",
                "class_type": "TotallyUnknownNode",
                "properties": {"vibecomfy_uid": "unk"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["unk"].role_hint == ROLE_HINT_UNKNOWN
    assert ref_map["unk"].layout_behavior == LAYOUT_BEHAVIOR_UNKNOWN
    assert ref_map["unk"].is_helper is False


def test_canonical_refs_layout_behavior_preview_substring_output_wall() -> None:
    """Class_type containing 'preview' substring → OUTPUT role, WALL layout_behavior.

    In graph_facts, _role_hint catches 'preview' in class name as OUTPUT,
    and _derive_layout_behavior maps OUTPUT→WALL.
    """
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "MyPreviewHelper",
                "class_type": "MyPreviewHelper",
                "properties": {"vibecomfy_uid": "preview-helper"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["preview-helper"].role_hint == ROLE_HINT_OUTPUT
    assert ref_map["preview-helper"].layout_behavior == LAYOUT_BEHAVIOR_WALL


def test_canonical_refs_layout_behavior_unknown_setnode_substring_sidecar() -> None:
    """Unknown class_type containing 'SetNode' → sidecar via class_type fallback."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "CustomSetNodePlus",
                "class_type": "CustomSetNodePlus",
                "properties": {"vibecomfy_uid": "csp"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["csp"].role_hint == ROLE_HINT_UNKNOWN
    assert ref_map["csp"].layout_behavior == LAYOUT_BEHAVIOR_SIDECAR


def test_canonical_refs_layout_behavior_unknown_note_substring_note() -> None:
    """Unknown class_type containing 'note' → note via class_type fallback."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "CustomNoteThing",
                "class_type": "CustomNoteThing",
                "properties": {"vibecomfy_uid": "cnt"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    ref_map = {fact.ref.uid: fact for fact in facts.canonical_refs}
    assert ref_map["cnt"].role_hint == ROLE_HINT_UNKNOWN
    assert ref_map["cnt"].layout_behavior == LAYOUT_BEHAVIOR_NOTE


def test_canonical_refs_json_includes_layout_behavior() -> None:
    """Every canonical ref JSON includes layout_behavior field."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
            },
            {
                "id": 2,
                "type": "SetNode",
                "class_type": "SetNode",
                "properties": {"vibecomfy_uid": "set-a"},
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
            },
            {
                "id": 4,
                "type": "Note",
                "class_type": "Note",
                "properties": {"vibecomfy_uid": "note-a"},
            },
            {
                "id": 5,
                "type": "CustomUnknown",
                "class_type": "CustomUnknown",
                "properties": {"vibecomfy_uid": "unk"},
            },
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    payload = facts.to_json()
    for ref_json in payload["canonical_refs"]:
        assert "layout_behavior" in ref_json
        assert ref_json["layout_behavior"] in LAYOUT_BEHAVIORS

    # Spot-check specific behaviors
    by_uid = {ref["ref"][1]: ref for ref in payload["canonical_refs"]}
    assert by_uid["sample"]["layout_behavior"] == LAYOUT_BEHAVIOR_PRIMARY
    assert by_uid["set-a"]["layout_behavior"] == LAYOUT_BEHAVIOR_SIDECAR
    assert by_uid["save"]["layout_behavior"] == LAYOUT_BEHAVIOR_WALL
    assert by_uid["note-a"]["layout_behavior"] == LAYOUT_BEHAVIOR_NOTE
    assert by_uid["unk"]["layout_behavior"] == LAYOUT_BEHAVIOR_UNKNOWN
