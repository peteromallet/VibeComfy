from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.porting.emit.emitter import emit_ready_template_python
from vibecomfy.commands.validate import _subgraph_freshness_diagnostics
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_materialized_subgraph_contract_includes_call_site_and_source_hash() -> None:
    path = "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json"
    text = _emit_ready_from_ui_json(path, "edit/flux2_klein_9b_image_edit_base")

    assert "def image_edit_flux2_klein_9b(" in text
    assert "edited = image_edit_flux2_klein_9b(" in text
    assert "raw_call('7b34ab90" not in text
    assert "# vibecomfy source hash: sha256:" in text


def test_subgraph_freshness_detects_hash_drift(tmp_path: Path) -> None:
    path = "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json"
    text = _emit_ready_from_ui_json(path, "edit/flux2_klein_9b_image_edit_base")
    template = tmp_path / "template.py"
    template.write_text(text.replace("# vibecomfy source hash: sha256:", "# vibecomfy source hash: sha256:" + "0" * 64 + "X", 1), encoding="utf-8")

    diagnostics = _subgraph_freshness_diagnostics(template)

    assert diagnostics
    assert "source hash changed" in diagnostics[0]


def test_subgraph_blank_labeled_input_matches_normalized_call_site_edge() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1})
    workflow.nodes["2"] = VibeNode("2", "sg-enable", metadata={"_ui": {"inputs": [{"name": "", "label": "Enable", "link": 99}]}})
    workflow.edges.append(VibeEdge("1", "0", "2", "_un99"))
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-enable",
                    "name": "Prompt Enhancer",
                    "inputs": [{"name": "", "label": "Enable", "type": "BOOLEAN", "linkIds": [1]}],
                    "outputs": [{"name": "out", "type": "BOOLEAN"}],
                    "nodes": [{"id": 10, "type": "LazySwitchKJ", "inputs": [{"name": "switch", "link": 1}], "outputs": [{"name": "out"}]}],
                    "links": [
                        {"id": 1, "origin_id": -10, "origin_slot": 0, "target_id": 10, "target_slot": 0, "type": "BOOLEAN"},
                        {"id": 2, "origin_id": 10, "origin_slot": 0, "target_id": -20, "target_slot": 0, "type": "BOOLEAN"},
                    ],
                }
            ]
        }
    }

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test"},
        ready_requirements={},
        template_id="video/test",
        raw_workflow=raw,
    )

    assert "def prompt_enhancer(\n    *,\n    enable" in text
    assert "enable=intconstant" in text
    assert "enable=None" not in text


def test_subgraph_external_input_edge_becomes_function_parameter() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 7})
    workflow.nodes["2"] = VibeNode("2", "sg-total")
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-total",
                    "name": "Total duration",
                    "inputs": [],
                    "outputs": [{"name": "FLOAT", "type": "FLOAT"}],
                    "nodes": [
                        {
                            "id": 20,
                            "type": "SimpleCalculatorKJ",
                            "inputs": [{"name": "variables.a", "link": 1}],
                            "outputs": [{"name": "FLOAT"}, {"name": "INT"}, {"name": "BOOLEAN"}],
                            "widgets_values": ["a + 1"],
                        }
                    ],
                    "links": [
                        {"id": 1, "origin_id": 1, "origin_slot": 0, "target_id": 20, "target_slot": 0, "type": "FLOAT"},
                        {"id": 2, "origin_id": 20, "origin_slot": 0, "target_id": -20, "target_slot": 0, "type": "FLOAT"},
                    ],
                }
            ]
        }
    }

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test"},
        ready_requirements={},
        template_id="video/test",
        raw_workflow=raw,
    )

    assert "def total_duration(\n    *,\n    variables_a" in text
    assert "'variables.a': variables_a" in text
    assert "variables_a=intconstant" in text


def _emit_ready_from_ui_json(path: str, template_id: str) -> str:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = convert_to_vibe_format(api, source_path=path, workflow_id=Path(path).stem)
    return emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": template_id,
            "capability": "image_edit",
            "provenance": {"source_workflow": path},
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id=template_id,
        raw_workflow=raw,
    )
