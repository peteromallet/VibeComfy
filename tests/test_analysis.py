from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from vibecomfy.analysis import analyze, diff, downstream, path, subgraph, trace, unconnected, upstream, values
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.workflow import VibeEdge, VibeInput, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self.schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas.get(class_type)


def _workflow() -> VibeWorkflow:
    workflow = VibeWorkflow(
        id="analysis-test",
        source=WorkflowSource(id="analysis-test", path="analysis-test.json", provenance={"media": "image"}),
    )
    workflow.nodes = {
        "1": VibeNode("1", "LoadImage", inputs={"image": "input.png"}),
        "2": VibeNode("2", "CLIPTextEncode", inputs={"text": "a red cube"}),
        "3": VibeNode("3", "KSampler", inputs={"seed": 7}, widgets={"steps": 4}),
        "4": VibeNode("4", "SaveImage", inputs={"filename_prefix": "out"}),
    }
    workflow.edges = [
        VibeEdge("1", "0", "3", "latent_image"),
        VibeEdge("2", "0", "3", "positive"),
        VibeEdge("3", "0", "4", "images"),
    ]
    workflow.inputs = {"prompt": VibeInput("prompt", "2", "text", "a red cube")}
    workflow.outputs = [VibeOutput("4", "IMAGE", "image")]
    return workflow


def test_analyze_summarizes_workflow_shape() -> None:
    summary = analyze(_workflow())

    assert summary["node_count"] == 4
    assert summary["edge_count"] == 3
    assert summary["fan_in_histogram"] == {0: 2, 1: 1, 2: 1}
    assert summary["fan_out_histogram"] == {0: 1, 1: 3}
    assert summary["output_sinks"] == [{"node_id": "4", "output_type": "IMAGE", "name": "image"}]
    assert summary["terminal_inputs"] == [{"name": "prompt", "node_id": "2", "field": "text", "value": "a red cube"}]
    assert summary["detected_media_type"] == "image"


def test_trace_upstream_downstream_and_path_return_expected_nodes() -> None:
    workflow = _workflow()

    assert [node.id for node in trace(workflow, "4")] == ["1", "2", "3", "4"]
    assert upstream(workflow, "4") == {"1", "2", "3"}
    assert upstream(workflow, "4", depth=1) == {"3"}
    assert downstream(workflow, "1") == {"3", "4"}
    assert downstream(workflow, "1", depth=1) == {"3"}
    assert path(workflow, "1", "4") == [["1", "3", "4"]]
    assert path(workflow, "2", "1") == []


def test_values_returns_literal_inputs_and_widgets() -> None:
    workflow = _workflow()

    assert values(workflow, "3") == {"seed": 7, "steps": 4}
    assert values(workflow)["2"] == {"text": "a red cube"}


def test_subgraph_returns_new_workflow_without_mutating_source() -> None:
    workflow = _workflow()
    before = deepcopy(workflow)

    result = subgraph(workflow, {"1", "3", "4"})
    result.nodes["3"].inputs["seed"] = 99
    result.edges.clear()

    assert set(result.nodes) == {"1", "3", "4"}
    assert [(edge.from_node, edge.to_node) for edge in subgraph(workflow, {"1", "3", "4"}).edges] == [
        ("1", "3"),
        ("3", "4"),
    ]
    assert workflow == before


def test_diff_reports_node_edge_and_value_changes() -> None:
    original = _workflow()
    mutated = deepcopy(original)
    mutated.nodes["2"].inputs["text"] = "a blue cube"
    mutated.nodes["5"] = VibeNode("5", "PreviewImage")
    mutated.edges.append(VibeEdge("3", "0", "5", "images"))
    mutated.edges = [edge for edge in mutated.edges if not (edge.from_node == "1" and edge.to_node == "3")]

    result = diff(original, mutated)

    assert result["added_nodes"] == ["5"]
    assert result["removed_nodes"] == []
    assert result["changed_nodes"] == ["2"]
    assert result["added_edges"] == [("3", "0", "5", "images")]
    assert result["removed_edges"] == [("1", "0", "3", "latent_image")]
    assert result["input_value_changes"] == {"2": {"text": {"from": "a red cube", "to": "a blue cube"}}}


def test_unconnected_reports_without_and_with_schema() -> None:
    workflow = _workflow()
    workflow.nodes["5"] = VibeNode("5", "PromptNode")

    assert unconnected(workflow) == [
        {"node_id": "2", "class_type": "CLIPTextEncode", "reason": "no_incoming_edges"},
        {"node_id": "5", "class_type": "PromptNode", "reason": "no_incoming_edges"},
    ]

    provider = FakeSchemaProvider(
        {
            "PromptNode": NodeSchema(
                class_type="PromptNode",
                pack=None,
                inputs={"text": InputSpec("STRING", required=True)},
                outputs=[],
            )
        }
    )
    assert unconnected(workflow, schema_provider=provider) == [
        {"node_id": "5", "class_type": "PromptNode", "input": "text", "reason": "missing_required_input"}
    ]


def test_analyze_info_cli_smoke_returns_output(tmp_path: Path) -> None:
    fixture = "smoke/empty_image_red"

    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "analyze", "info", str(fixture)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
    assert "nodes: 2" in result.stdout


def test_analyze_names_cli_reports_role_based_preview(tmp_path: Path) -> None:
    fixture = "image/z_image"

    text_result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "analyze", "names", str(fixture), "--strategy", "role-based"],
        check=False,
        capture_output=True,
        text=True,
    )
    json_result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "analyze", "names", str(fixture), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert text_result.returncode == 0, text_result.stderr
    assert "Strategy: role-based" in text_result.stdout
    assert "positive_text" in text_result.stdout
    assert "negative_text" in text_result.stdout
    assert "terminal, no rename" in text_result.stdout
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    from vibecomfy.registry.ready import workflow_from_ready

    workflow = workflow_from_ready(fixture)
    assert payload["summary"]["node_count"] == len(workflow.nodes)
    prompt_row = next(row for row in payload["rows"] if row["reason"] == "PUBLIC_INPUTS['prompt']")
    assert prompt_row["proposed_name"] == "positive_text"
