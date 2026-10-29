"""Native boundary binding regressions using byte-exact official Qwen 2.1 sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.native_subgraph import NativeSubgraphError, expand_native_subgraphs
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.commands.templates import _cmd_create
from vibecomfy.porting.import_service import import_workflow_bytes
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import load_bundle


FIXTURES = Path(__file__).parent / "fixtures" / "native_qwen_2_1"


def _boundary_graph(*, named: bool) -> dict:
    # The prompt fans out to both a promoted widget and an ordinary socket.
    # Input order deliberately differs from the named value order.
    instance = {
        "id": "box", "type": "Box",
        "inputs": [{"name": "prompt", "link": None}, {"name": "enabled", "link": None}],
        "outputs": [{"name": "result", "links": [8]}],
        "widgets_values": ["outer prompt", False],
    }
    if named:
        instance["widgets_values"] = [True, "wrong positional prompt"]
        instance["widgets_values_named"] = {"enabled": False, "prompt": "named prompt"}
    return {
        "nodes": [instance, {"id": "save", "type": "Sink", "inputs": [{"name": "value", "link": 8}], "outputs": []}],
        "links": [[8, "box", 0, "save", 0, "STRING"]],
        "definitions": {"subgraphs": [{
            "id": "Box", "name": "Box", "inputNode": {"id": -10}, "outputNode": {"id": -20},
            "inputs": [{"name": "prompt", "linkIds": [1, 2]}, {"name": "enabled", "linkIds": [3]}],
            "outputs": [{"name": "result", "linkIds": [4]}],
            "nodes": [
                {"id": "widget", "type": "Text", "inputs": [{"name": "text", "widget": {"name": "text"}, "link": 1}], "outputs": [], "widgets_values": ["inner"], "widgets_values_named": {"text": "inner"}},
                {"id": "switch", "type": "Switch", "inputs": [{"name": "on_false", "link": 2}, {"name": "switch", "widget": {"name": "switch"}, "link": 3}], "outputs": [{"name": "result", "links": [4]}], "widgets_values": [True], "widgets_values_named": {"switch": True}},
            ],
            "links": [[1, -10, 0, "widget", 0, "STRING"], [2, -10, 0, "switch", 0, "STRING"], [3, -10, 1, "switch", 1, "BOOLEAN"], [4, "switch", 0, -20, 0, "STRING"]],
        }]},
    }


@pytest.mark.parametrize("named,prompt", [(True, "named prompt"), (False, "outer prompt")])
def test_native_boundary_preserves_widget_and_ordinary_socket_fanout(named: bool, prompt: str) -> None:
    raw = _boundary_graph(named=named)
    workflow = from_ui(expand_native_subgraphs(raw), source_path="boundary.json", use_comfy_converter=False)
    assert workflow.nodes["box::widget"].inputs["text"] == prompt
    assert workflow.nodes["box::switch"].inputs["on_false"] == prompt
    assert workflow.nodes["box::switch"].inputs["switch"] is False
    assert any((e.from_node, e.to_node, e.to_input) == ("box::switch", "save", "value") for e in workflow.edges)
    assert raw["definitions"]["subgraphs"][0]["nodes"][0]["widgets_values"] == ["inner"]


def test_partial_named_instance_uses_proven_positional_fallback() -> None:
    raw = _boundary_graph(named=True)
    instance = raw["nodes"][0]
    instance["widgets_values"] = ["positional prompt", True]
    instance["widgets_values_named"] = {"prompt": "named prompt"}

    workflow = from_ui(expand_native_subgraphs(raw), source_path="partial.json", use_comfy_converter=False)
    assert workflow.nodes["box::widget"].inputs["text"] == "named prompt"
    assert workflow.nodes["box::switch"].inputs["on_false"] == "named prompt"
    assert workflow.nodes["box::switch"].inputs["switch"] is True


def test_partial_named_instance_rejects_ambiguous_positional_fallback() -> None:
    raw = _boundary_graph(named=True)
    raw["nodes"][0]["widgets_values"] = ["one", "two", "three"]
    raw["nodes"][0]["widgets_values_named"] = {"prompt": "named prompt"}
    with pytest.raises(NativeSubgraphError, match="ambiguous native widget value roster"):
        expand_native_subgraphs(raw)


@pytest.mark.parametrize("linked", [False, True])
def test_promoted_widget_alias_preserves_socket_name(linked: bool) -> None:
    raw = _boundary_graph(named=True)
    widget = raw["definitions"]["subgraphs"][0]["nodes"][0]
    widget["inputs"][0]["name"] = "input_text"
    if linked:
        raw["nodes"].insert(0, {"id": "source", "type": "Source", "inputs": [], "outputs": [{"name": "value", "links": [9]}]})
        raw["nodes"][1]["inputs"][0]["link"] = 9
        raw["links"].append([9, "source", 0, "box", 0, "STRING"])
    workflow = from_ui(expand_native_subgraphs(raw), source_path="alias.json", use_comfy_converter=False)
    node = workflow.nodes["box::widget"]
    assert "text" not in node.inputs
    if linked:
        assert "input_text" not in node.inputs
        assert any((e.from_node, e.to_node, e.to_input) == ("source", "box::widget", "input_text") for e in workflow.edges)
    else:
        assert node.inputs["input_text"] == "named prompt"


def test_rejects_ambiguous_promoted_widget_alias() -> None:
    raw = _boundary_graph(named=True)
    widget = raw["definitions"]["subgraphs"][0]["nodes"][0]
    widget["inputs"][0]["name"] = "input_text"
    widget["inputs"].append({"name": "text", "link": None})
    with pytest.raises(NativeSubgraphError, match="ambiguous widget alias"):
        expand_native_subgraphs(raw)


def test_inner_named_widget_order_does_not_reassign_neighbor() -> None:
    raw = _boundary_graph(named=True)
    widget = raw["definitions"]["subgraphs"][0]["nodes"][0]
    widget["inputs"].append({"name": "count", "widget": {"name": "count"}, "link": None})
    widget["widgets_values"] = ["inner", 17]
    widget["widgets_values_named"] = {"count": 17, "text": "inner"}

    workflow = from_ui(expand_native_subgraphs(raw), source_path="ordered.json", use_comfy_converter=False)
    assert workflow.nodes["box::widget"].inputs["text"] == "named prompt"
    assert workflow.nodes["box::widget"].inputs["count"] == 17


def test_linked_boundary_overrides_named_literal_for_all_fanout_targets() -> None:
    raw = _boundary_graph(named=True)
    raw["nodes"].insert(0, {"id": "source", "type": "Source", "inputs": [], "outputs": [{"name": "value", "links": [9]}]})
    instance = raw["nodes"][1]
    instance["inputs"][0]["link"] = 9
    raw["links"].append([9, "source", 0, "box", 0, "STRING"])

    workflow = from_ui(expand_native_subgraphs(raw), source_path="linked.json", use_comfy_converter=False)
    edges = {(e.from_node, e.to_node, e.to_input) for e in workflow.edges}
    assert ("source", "box::widget", "text") in edges
    assert ("source", "box::switch", "on_false") in edges
    assert "text" not in workflow.nodes["box::widget"].inputs
    assert "on_false" not in workflow.nodes["box::switch"].inputs
    assert workflow.nodes["box::switch"].inputs["switch"] is False


@pytest.mark.parametrize(
    "filename,digest,text_id,switch_id,seed,dimension_linked",
    [
        ("qwen_image_2_1_turbo_t2i.json", "3eb9cef2866c0186fbe30172701f112b35e574cf3c6575c6e4a6b5dd1e76a403", "471", "474", 447606998181262, True),
        ("qwen_image_2_1_turbo_image_edit.json", "5a9622d550866800414afcb9c70523ec5c6965eb171476e401e243a7fe8d5a4e", "500", "484", 891836227295375, False),
    ],
)
def test_official_qwen_native_import_canonical_bundle_roundtrip(
    filename: str, digest: str, text_id: str, switch_id: str, seed: int, dimension_linked: bool, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source = FIXTURES / filename
    source_bytes = source.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == digest
    raw = json.loads(source_bytes)
    outer = next(node for node in raw["nodes"] if node["id"] == 459)
    prompt = outer["widgets_values_named"]["prompt"]
    workflow = from_ui(raw, source_path=str(source), use_comfy_converter=False)

    def assert_bindings(wf) -> None:
        text = wf.nodes[f"459::{text_id}"].inputs
        switch = wf.nodes[f"459::{switch_id}"].inputs
        assert text["prompt"] == prompt
        assert text["thinking"] is False
        assert text["max_length"] == 4096
        assert text["sampling_mode.seed"] == seed
        assert switch["on_false"] == prompt
        assert switch["switch"] is False
        edges = {(e.from_node, e.from_output, e.to_node, e.to_input) for e in wf.edges}
        assert ("459::457", "0", "461", "images") in edges
        assert any(output.node_id == "461" for output in wf.outputs)
        if dimension_linked:
            assert ("13", "0", "459::456", "width") in edges
            assert ("13", "1", "459::456", "height") in edges
            assert wf.nodes["459::488"].inputs["noise_seed"] == 531123706903762
        else:
            assert wf.nodes["459::456"].inputs["width"] == 1024
            assert wf.nodes["459::456"].inputs["height"] == 1024
            assert wf.nodes["459::504"].inputs["noise_seed"] == seed
            assert ("470", "0", "459::474", "images.image_1") in edges
            assert ("470", "0", "459::485", "images.image0") in edges

    assert_bindings(workflow)
    artifacts = import_workflow_bytes(source_bytes, workflow_id=source.stem)
    bundle_path = tmp_path / "workflow.py"
    bundle_path.write_bytes(artifacts.python_bytes)
    bundle_path.with_suffix(".vibe.json").write_bytes(artifacts.companion_bytes)
    imported = load_bundle(bundle_path, trust=Provenance.USER_CONFIRMED)
    assert artifacts.report["validation"]["structural_and_parity"]["ok"]
    assert imported.semantic_digest == artifacts.report["after"]["semantic_digest"]
    assert_bindings(imported.workflow)
    # API compilation intentionally folds UI-only notes and primitive nodes.
    assert workflow.compile("api") == imported.workflow.compile("api")

    template_id = "image/" + source.stem
    template_path = tmp_path / "ready.py"
    result = _cmd_create(argparse.Namespace(
        template_id=template_id, out=str(template_path), bundle=str(bundle_path),
        dry_run=False, json=True,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert result == 0, payload
    promoted = load_bundle(template_path, trust=Provenance.USER_CONFIRMED)
    assert promoted.semantic_digest == payload["semantic_digest"]
    # Promotion changes the workflow identity, which is part of its digest.
    # Compare against that exact new identity, retaining every other field.
    expected = imported.workflow.copy()
    expected.id = template_id
    expected.source.id = template_id
    assert promoted.semantic_digest == expected.semantic_digest()
    assert_bindings(promoted.workflow)
    assert promoted.workflow.compile("api") == workflow.compile("api")
