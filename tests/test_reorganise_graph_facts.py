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


# ---------------------------------------------------------------------------
# Mode 2 (muted) and mode 4 (bypassed) exclusion from effective topology
# ---------------------------------------------------------------------------


def test_effective_topology_excludes_muted_sampler_alternative() -> None:
    """When one parallel sampler branch is muted (mode=2), only the active
    sampler reaches the effective topology. The muted sampler's edges are
    absent from effective_edges but remain in raw_edges."""
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
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample-active"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 100}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [104]}],
            },
            {
                "id": 3,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample-muted"},
                "mode": 2,
                "inputs": [{"name": "image", "type": "IMAGE", "link": 103}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [105]}],
            },
            {
                "id": 4,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save-active"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 104}],
            },
            {
                "id": 5,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": "preview-muted"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 105}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}],
            },
        ],
        "links": [
            [100, 1, 0, 2, 0, "IMAGE"],
            [103, 1, 0, 3, 0, "IMAGE"],
            [104, 2, 0, 4, 0, "IMAGE"],
            [105, 3, 0, 5, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    # Physical (raw) edges still include everything
    raw_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.raw_edges}
    assert ("load", "sample-active") in raw_pairs
    assert ("load", "sample-muted") in raw_pairs
    assert ("sample-active", "save-active") in raw_pairs
    assert ("sample-muted", "preview-muted") in raw_pairs

    # Effective edges exclude the muted sampler and its downstream
    effective_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.effective_edges}
    assert ("load", "sample-active") in effective_pairs
    assert ("sample-active", "save-active") in effective_pairs
    assert ("load", "sample-muted") not in effective_pairs
    assert ("sample-muted", "preview-muted") not in effective_pairs

    # The muted sampler's preview consumer is also disconnected
    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    assert node_topology["sample-muted"].fan_in == 0
    assert node_topology["sample-muted"].fan_out == 0
    assert node_topology["preview-muted"].fan_in == 0

    # The active sampler path is still connected
    assert node_topology["sample-active"].fan_in == 1
    assert node_topology["sample-active"].fan_out == 1
    assert node_topology["save-active"].fan_in == 1


def test_effective_topology_excludes_mode_4_bypassed_node() -> None:
    """A bypassed (mode=4) node is excluded from effective edges, creating
    disconnected islands on either side."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "CLIPTextEncode",
                "class_type": "CLIPTextEncode",
                "properties": {"vibecomfy_uid": "bypass-me"},
                "mode": 4,
                "inputs": [{"name": "text", "type": "STRING", "link": 10}],
                "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [11]}],
            },
            {
                "id": 3,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "inputs": [{"name": "positive", "type": "CONDITIONING", "link": 11}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [12]}],
            },
            {
                "id": 4,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 12}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "STRING"],
            [11, 2, 0, 3, 0, "CONDITIONING"],
            [12, 3, 0, 4, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    # Physical edges are complete
    raw_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.raw_edges}
    assert len(raw_pairs) == 3
    assert ("load", "bypass-me") in raw_pairs
    assert ("bypass-me", "sample") in raw_pairs
    assert ("sample", "save") in raw_pairs

    # Effective edges drop the bypassed node → two disconnected islands
    effective_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.effective_edges}
    assert ("sample", "save") in effective_pairs
    assert ("load", "bypass-me") not in effective_pairs
    assert ("bypass-me", "sample") not in effective_pairs

    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    # load is isolated (no outgoing effective edges)
    assert node_topology["load"].fan_in == 0
    assert node_topology["load"].fan_out == 0
    # bypass-me is isolated
    assert node_topology["bypass-me"].fan_in == 0
    assert node_topology["bypass-me"].fan_out == 0
    # sample→save chain is intact
    assert node_topology["sample"].fan_in == 0
    assert node_topology["sample"].fan_out == 1
    assert node_topology["save"].fan_in == 1

    # WCC count reflects the split
    wcc_ids = {fact.wcc_id for fact in topology.node_topology}
    assert len(wcc_ids) >= 2  # at least two weak components


def test_effective_topology_preserves_reroute_passthrough_around_muted_node() -> None:
    """A muted non-helper node breaks the chain, but Reroute passthrough
    around a *non-muted* reroute still works correctly.

    Graph: load → (muted clip-encode) → reroute → sampler → save
    The clip-encode is muted so its edges are dropped, but reroute passthrough
    from the remaining active nodes still operates.
    """
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10, 20]}],
            },
            {
                "id": 2,
                "type": "VAEDecode",
                "class_type": "VAEDecode",
                "properties": {"vibecomfy_uid": "muted-decode"},
                "mode": 2,
                "inputs": [{"name": "samples", "type": "LATENT", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "rr"},
                "inputs": [{"name": "", "type": "*", "link": 20}],
                "outputs": [{"name": "", "type": "*", "links": [21]}],
            },
            {
                "id": 4,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 21}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [22]}],
            },
            {
                "id": 5,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 22}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [20, 1, 0, 3, 0, "IMAGE"],
            [21, 3, 0, 4, 0, "IMAGE"],
            [22, 4, 0, 5, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    effective_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.effective_edges}
    # Reroute passthrough: load → sample (via non-muted reroute)
    assert ("load", "sample") in effective_pairs
    # Muted decode edges are absent
    assert ("load", "muted-decode") not in effective_pairs
    assert ("muted-decode", "sample") not in effective_pairs
    # Sample → save still connected
    assert ("sample", "save") in effective_pairs

    # Raw edges still show the reroute (passthrough flag distinguishes them)
    passthrough_edges = [edge for edge in topology.effective_edges if edge.passthrough]
    assert any(edge.source.uid == "load" and edge.target.uid == "sample" for edge in passthrough_edges)


def test_effective_topology_set_get_passthrough_preserved_around_muted() -> None:
    """SetNode/GetNode passthrough works correctly even when a muted sampler
    sits between them — the Set/Get channel remains resolved."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [100, 200]}],
            },
            {
                "id": 2,
                "type": "SetNode",
                "class_type": "SetNode",
                "properties": {"vibecomfy_uid": "set-latent"},
                "widgets_values": ["LATENT"],
                "inputs": [{"name": "IMAGE", "type": "IMAGE", "link": 200}],
            },
            {
                "id": 3,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "muted-sampler"},
                "mode": 2,
                "inputs": [{"name": "image", "type": "IMAGE", "link": 100}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [101]}],
            },
            {
                "id": 4,
                "type": "GetNode",
                "class_type": "GetNode",
                "properties": {"vibecomfy_uid": "get-latent"},
                "widgets_values": ["LATENT"],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [201]}],
            },
            {
                "id": 5,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 201}],
            },
        ],
        "links": [
            [100, 1, 0, 3, 0, "IMAGE"],
            [200, 1, 0, 2, 0, "IMAGE"],
            [201, 4, 0, 5, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    effective_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.effective_edges}
    # Set/Get passthrough: load → save (broadcast source → GetNode consumer)
    assert ("load", "save") in effective_pairs
    # Muted sampler edges are excluded
    assert ("load", "muted-sampler") not in effective_pairs
    # Helper nodes (Set/Get) are already excluded by broadcast resolution
    assert ("set-latent", "save") not in effective_pairs

    # Raw edges are complete
    raw_pairs = {(edge.source.uid, edge.target.uid) for edge in topology.raw_edges}
    assert ("load", "muted-sampler") in raw_pairs
    assert ("load", "set-latent") in raw_pairs


def test_all_nodes_muted_produces_empty_effective_topology() -> None:
    """When every node has mode=2, effective edges are empty but raw edges
    and node_topology records are still populated."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "mode": 2,
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "mode": 2,
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "mode": 2,
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    assert len(topology.raw_edges) == 2
    assert len(topology.effective_edges) == 0
    # All nodes still appear in node_topology with zero fan
    assert len(topology.node_topology) == 3
    for fact in topology.node_topology:
        assert fact.fan_in == 0
        assert fact.fan_out == 0


# ---------------------------------------------------------------------------
# SCC feedback tagging — T2
# ---------------------------------------------------------------------------


def test_scc_feedback_tags_mutual_two_node_cycle() -> None:
    """Two nodes with mutual edges (A→B and B→A) form one SCC, and both
    effective edges are tagged as feedback=True."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler-a"},
                "inputs": [{"name": "latent", "type": "LATENT", "link": 10}],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [11]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler-b"},
                "inputs": [{"name": "latent", "type": "LATENT", "link": 11}],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [10]}],
            },
        ],
        "links": [
            [10, 2, 0, 1, 0, "LATENT"],  # B → A
            [11, 1, 0, 2, 0, "LATENT"],  # A → B
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    # Both samplers share one SCC
    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    assert node_topology["sampler-a"].scc_id == node_topology["sampler-b"].scc_id
    assert node_topology["sampler-a"].scc_id.startswith("scc")

    # Both effective edges are feedback
    effective_edges = list(topology.effective_edges)
    assert len(effective_edges) == 2
    for edge in effective_edges:
        assert edge.feedback is True, f"Edge {edge.source.uid}→{edge.target.uid} should be feedback"
        # passthrough=True on all effective edges (distinguishes them from raw edges)

    # SCC count in summary reflects one SCC
    scope_summary = facts.summary.scopes[0]
    assert scope_summary.scc_count == 1


def test_scc_feedback_three_node_cycle_with_entrance_and_exit() -> None:
    """A three-node cycle (A→B→C→A) with entrance (D→A) and exit (C→E):
    the three cycle edges are feedback=True, entrance and exit are not."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "a"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "b"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 11}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [12]}],
            },
            {
                "id": 4,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "c"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 12}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [13, 14]}],
            },
            {
                "id": 5,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 13}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],   # load → a (entrance, not feedback)
            [11, 2, 0, 3, 0, "IMAGE"],   # a → b (cycle edge, feedback)
            [12, 3, 0, 4, 0, "IMAGE"],   # b → c (cycle edge, feedback)
            [14, 4, 0, 2, 0, "IMAGE"],   # c → a (cycle edge, feedback)
            [13, 4, 0, 5, 0, "IMAGE"],   # c → save (exit, not feedback)
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    # a, b, c share the same SCC
    assert node_topology["a"].scc_id == node_topology["b"].scc_id == node_topology["c"].scc_id
    # load and save are in different SCCs
    assert node_topology["load"].scc_id != node_topology["a"].scc_id
    assert node_topology["save"].scc_id != node_topology["c"].scc_id

    # Check feedback tags on effective edges
    edge_feedback = {
        (edge.source.uid, edge.target.uid): edge.feedback
        for edge in topology.effective_edges
    }
    # Cycle edges: a→b, b→c, c→a are feedback
    assert edge_feedback.get(("a", "b")) is True
    assert edge_feedback.get(("b", "c")) is True
    assert edge_feedback.get(("c", "a")) is True
    # Entrance and exit are not feedback
    assert edge_feedback.get(("load", "a")) is False
    assert edge_feedback.get(("c", "save")) is False

    # SCC count: load, (a,b,c), save = 3 SCCs
    scope_summary = facts.summary.scopes[0]
    assert scope_summary.scc_count == 3


def test_scc_feedback_single_node_trivial_scc_no_feedback() -> None:
    """A linear chain load→sample→save has zero feedback edges because
    no edge connects nodes within the same SCC."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    # Every node is its own SCC in a DAG
    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    scc_ids = {fact.scc_id for fact in topology.node_topology}
    assert len(scc_ids) == 3  # three trivial SCCs

    # No edge should be tagged feedback
    for edge in topology.effective_edges:
        assert edge.feedback is False, f"Edge {edge.source.uid}→{edge.target.uid} should not be feedback"

    scope_summary = facts.summary.scopes[0]
    assert scope_summary.scc_count == 3


def test_scc_feedback_cycle_via_passthrough_not_feedback() -> None:
    """Passthrough edges (resolved through helpers) that happen to land
    on the same SCC as the source via a different path should still not
    be tagged feedback if source and target are in different SCCs."""
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10, 30]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "a"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "b"},
                "inputs": [{"name": "image", "type": "IMAGE", "link": 11}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [12]}],
            },
            {
                "id": 4,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "rr"},
                "inputs": [{"name": "", "type": "*", "link": 30}],
                "outputs": [{"name": "", "type": "*", "links": [31]}],
            },
            {
                "id": 5,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 31}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],   # load → a
            [11, 2, 0, 3, 0, "IMAGE"],   # a → b
            [12, 3, 0, 1, 0, "IMAGE"],   # b → load (feedback cycle)
            [30, 1, 0, 4, 0, "IMAGE"],   # load → reroute
            [31, 4, 0, 5, 0, "IMAGE"],   # reroute → save
        ],
    }

    facts = extract_graph_facts(ui)
    topology = facts.scope_topologies[0]

    node_topology = {fact.ref.uid: fact for fact in topology.node_topology}
    # load, a, b form one SCC (cycle)
    scc_cycle = node_topology["load"].scc_id
    assert node_topology["a"].scc_id == scc_cycle
    assert node_topology["b"].scc_id == scc_cycle
    # save is separate
    assert node_topology["save"].scc_id != scc_cycle

    # Effective edges: load→a, a→b, b→load (feedback), load→save (passthrough via reroute)
    edge_feedback = {
        (edge.source.uid, edge.target.uid): edge.feedback
        for edge in topology.effective_edges
    }
    # The passthrough edge load→save crosses SCCs → not feedback
    assert edge_feedback.get(("load", "save")) is False
    # Cycle edges are feedback
    assert edge_feedback.get(("load", "a")) is True
    assert edge_feedback.get(("a", "b")) is True
    assert edge_feedback.get(("b", "load")) is True
