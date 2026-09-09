from __future__ import annotations

import copy

import pytest

from vibecomfy.ingest.native_subgraph import NativeSubgraphError, expand_native_subgraphs


def _graph() -> dict:
    definition = {
        "id": "Box", "name": "Box",
        "inputNode": {"id": -10}, "outputNode": {"id": -20},
        "inputs": [
            {"name": "prompt", "type": "STRING", "linkIds": [1]},
            {"name": "video", "type": "VIDEO", "linkIds": [2, 3]},
        ],
        "outputs": [{"name": "result", "type": "VIDEO", "linkIds": [4]}],
        "nodes": [
            {"id": "loader", "type": "Loader", "inputs": [{"name": "prompt", "type": "STRING", "widget": {"name": "prompt"}, "link": 1}], "outputs": [{"name": "out", "links": [2, 3]}], "widgets_values": ["inner default"]},
            {"id": "a", "type": "Sink", "inputs": [{"name": "video", "type": "VIDEO", "link": 2}], "outputs": []},
            {"id": "b", "type": "Sink", "inputs": [{"name": "video", "type": "VIDEO", "link": 3}], "outputs": [{"name": "out", "links": [4]}]},
        ],
        "links": [
            [1, -10, 0, "loader", 0, "STRING"],
            [2, -10, 1, "a", 0, "VIDEO"],
            [3, -10, 1, "b", 0, "VIDEO"],
            [4, "b", 0, -20, 0, "VIDEO"],
        ],
    }
    return {
        "nodes": [
            {"id": "source", "type": "Source", "inputs": [], "outputs": [{"name": "out", "links": [10]}]},
            {"id": "box-1", "type": "Box", "inputs": [{"name": "prompt", "widget": {"name": "prompt"}, "link": None}, {"name": "video", "link": 10}], "outputs": [{"name": "result", "links": [11]}], "widgets_values": ["outer override"]},
            {"id": "sink", "type": "Sink", "inputs": [{"name": "video", "link": 11}], "outputs": []},
        ],
        "links": [[10, "source", 0, "box-1", 1, "VIDEO"], [11, "box-1", 0, "sink", 0, "VIDEO"]],
        "definitions": {"subgraphs": [definition]},
    }


def test_expands_fanout_and_instance_widget_override() -> None:
    raw = _graph()
    expanded = expand_native_subgraphs(raw)
    assert raw["nodes"][1]["widgets_values"] == ["outer override"]
    assert "definitions" not in expanded
    assert {n["id"] for n in expanded["nodes"]} >= {"box-1::loader", "box-1::a", "box-1::b"}
    loader = next(n for n in expanded["nodes"] if n["id"] == "box-1::loader")
    assert loader["widgets_values"] == ["outer override"]
    assert sum(link[3] == "box-1::a" for link in expanded["links"]) == 1
    assert sum(link[3] == "box-1::b" for link in expanded["links"]) == 1
    output = next(link for link in expanded["links"] if link[0] == 11)
    assert output[1:3] == ["box-1::b", 0]


def test_repairs_missing_output_backlink_and_retains_provenance() -> None:
    raw = _graph()
    raw["definitions"]["subgraphs"][0]["nodes"][2]["outputs"][0]["links"] = []
    expanded = expand_native_subgraphs(raw)
    assert any(d["kind"] == "repaired_output_backlink" and d["link_id"] == 4 for d in expanded["_native_subgraph_diagnostics"])
    assert expanded["_native_subgraph_provenance"]["source_kind"] == "comfyui_native_subgraph"


def test_rejects_contradictory_backlink_and_ambiguous_boundary() -> None:
    raw = _graph()
    raw["definitions"]["subgraphs"][0]["nodes"][2]["outputs"][0]["links"] = [999]
    with pytest.raises(NativeSubgraphError, match="contradictory"):
        expand_native_subgraphs(raw)
    raw = _graph()
    raw["definitions"]["subgraphs"][0]["inputs"][0]["linkIds"] = [1, 2]
    with pytest.raises(NativeSubgraphError, match="widget|outer link|ambiguous"):
        expand_native_subgraphs(raw)
