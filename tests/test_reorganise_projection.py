from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.projection import (
    LayoutProjectionOptions,
    render_layout_projection,
)


def _subgraph_definition() -> dict:
    return {
        "name": "Inner Graph",
        "nodes": [
            {
                "id": 7,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "inner-sampler"},
                "pos": [10, 20],
                "size": [300, 100],
                "inputs": [],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
            }
        ],
        "links": [],
        "state": {"lastRerouteId": 5},
    }


def test_projection_is_stable_and_renders_canonical_ref_table_in_order() -> None:
    ui = {
        "nodes": [
            {
                "id": 20,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}],
            },
        ],
        "links": [[2, 2, 0, 20, 0, "IMAGE"]],
    }

    first = render_layout_projection(extract_graph_facts(ui))
    second = render_layout_projection(extract_graph_facts(ui))

    assert first.text == second.text
    assert "layout_reasoning_view:" in first.text
    assert "executable_python: false" in first.text
    assert "coordinate_plan: false" in first.text
    sample_index = first.text.index('ref: ["", "sample"]')
    save_index = first.text.index('ref: ["", "save"]')
    assert sample_index < save_index
    assert 'display: "<root>::sample (KSampler)"' in first.text
    assert "class_type: \"SaveImage\"" in first.text
    assert "def " not in first.text
    assert "import " not in first.text


def test_projection_renders_scoped_refs_and_nested_scope_blocks() -> None:
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "Subgraph",
                "class_type": "Subgraph",
                "properties": {"vibecomfy_uid": "container"},
            }
        ],
        "links": [],
        "definitions": {"subgraphs": [_subgraph_definition()]},
    }

    result = render_layout_projection(extract_graph_facts(ui))

    assert 'ref: ["", "container"]' in result.text
    assert "Inner Graph:" in result.text
    assert '"inner-sampler"]' in result.text
    assert "scope: \"<root>\"" in result.text
    assert "scope_path:" in result.text
    assert "scope_ui_facts: definitions_present=true" in result.text


def test_projection_renders_helper_virtual_wire_ui_group_and_terminal_facts() -> None:
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
                "flags": {"collapsed": True},
                "properties": {"vibecomfy_uid": "load-image"},
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "SetNode",
                "class_type": "SetNode",
                "properties": {"vibecomfy_uid": "set-image"},
                "widgets_values": ["IMAGE"],
                "inputs": [{"name": "IMAGE", "type": "IMAGE", "link": 10}],
            },
            {
                "id": 3,
                "type": "GetNode",
                "class_type": "GetNode",
                "properties": {"vibecomfy_uid": "get-image"},
                "widgets_values": ["IMAGE"],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 4,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "reroute-image"},
                "inputs": [{"name": "", "type": "*", "link": 11}],
                "outputs": [{"name": "", "type": "*", "links": [12]}],
            },
            {
                "id": 5,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": 12}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 3, 0, 4, 0, "IMAGE"],
            [12, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [{"title": "Inputs", "bounding": [0, 0, 400, 200], "nodes": [1, 2]}],
        "extra": {
            "virtual_wires": {
                "wire-image": {
                    "type": "SetNode",
                    "channel": "IMAGE",
                    "endpoints": [2, 3],
                }
            }
        },
        "state": {"lastRerouteId": 42},
    }

    result = render_layout_projection(extract_graph_facts(ui))

    assert "helper_facts:" in result.text
    assert 'helper_kind: "virtual-wire"' in result.text
    assert 'helper_kind: "reroute"' in result.text
    assert "virtual_link_facts:" in result.text
    assert 'key: "wire-image"' in result.text
    assert "ui_furniture_facts:" in result.text
    assert 'observed_pos: [11.25, 22.5]' in result.text
    assert "group_facts:" in result.text
    assert 'title: "Inputs"' in result.text
    assert "lastRerouteId=42" in result.text
    assert "terminal_path_facts:" in result.text
    assert 'terminal: ["", "save"]' in result.text
    assert "effective_edges:" in result.text
    assert 'from: ["", "load-image"]:"0" to: ["", "save"]:"0"' in result.text


def test_projection_summarizes_large_graphs_without_mutating_facts() -> None:
    ui = {
        "nodes": [
            {
                "id": index,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": f"preview-{index:02d}"},
                "pos": [index, index + 1],
                "size": [100, 40],
            }
            for index in range(1, 9)
        ],
        "links": [],
    }
    facts = extract_graph_facts(ui)
    before = deepcopy(facts.to_json())

    result = render_layout_projection(
        facts,
        options=LayoutProjectionOptions(
            max_canonical_refs=3,
            max_node_facts_per_scope=3,
            max_furniture_facts=2,
            max_tokens=1000,
        ),
    )

    assert facts.to_json() == before
    assert result.summarized is True
    assert "omitted: 5 canonical refs; see scope summaries below" in result.text
    assert "omitted: 6 node furniture facts" in result.text
    assert "omitted: 5 canonical refs in this scope" in result.text
    assert "nodes=8 edges=0" in result.text
