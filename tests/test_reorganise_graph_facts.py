from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts


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
