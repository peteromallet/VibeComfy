from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.commands.validate import _subgraph_freshness_diagnostics
from vibecomfy.identity.scope import sg_key
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.emit.emit_subgraph import _build_subgraph_def
from vibecomfy.porting.emitter import emit_ready_template_python
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


_FLUX2_READY = Path("ready_templates/edit/flux2_klein_9b_image_edit_base.py")
_SUPPORTED_SUBGRAPH_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _python_owned_recursive_workflow(*, input_name: str, input_type: str) -> VibeWorkflow:
    """Depth-2 Python-owned recursive graph with typed boundary ports."""
    inner = {
        "id": "inner",
        "name": "Inner",
        "nodes": [
            {
                "id": "inner_src",
                "uid": "inner_src",
                "type": "Get",
                "inputs": [{"name": "value", "type": input_type, "link": None, "value": None}],
                "outputs": [{"name": "out", "type": input_type}],
            },
            {
                "id": "inner_core",
                "uid": "inner_core",
                "type": "EchoImage",
                "inputs": [{"name": "in", "type": input_type, "link": None, "value": None}],
                "widgets_values": [1],
                "outputs": [{"name": "out", "type": input_type}],
                "mode": 0,
            },
        ],
        "links": [[1, "inner_src", 0, "inner_core", 0, input_type]],
    }
    inner_key = sg_key(inner)
    outer = {
        "id": "outer",
        "name": "Outer",
        "nodes": [{"id": "inner_occ", "uid": "inner_occ", "type": inner_key, "inputs": [], "outputs": []}],
        "links": [],
        "definitions": {"subgraphs": [inner]},
    }
    outer_key = sg_key(outer)
    source = VibeNode(
        "source",
        "Source",
        uid="source",
        native_output_names=["out"],
        metadata={"output_names": ["out"], "output_types": [input_type]},
    )
    occurrence = VibeNode(
        "outer",
        outer_key,
        uid="outer",
        native_input_names=[input_name],
        native_output_names=["output"],
        metadata={"input_types": [input_type], "output_types": [input_type]},
    )
    sink = VibeNode(
        "sink",
        "Sink",
        uid="sink",
        inputs={"image": None},
        native_input_names=["image"],
        metadata={"input_types": {"image": input_type}},
    )
    return VibeWorkflow(
        "recursive-execution",
        WorkflowSource(id="recursive-execution"),
        nodes={"source": source, "outer": occurrence, "sink": sink},
        edges=[
            VibeEdge("source", "out", "outer", input_name),
            VibeEdge("outer", "output", "sink", "image"),
        ],
        definitions={"subgraphs": [outer]},
        interfaces={
            outer_key: {
                "inputs": [{"name": input_name, "direction": "input", "type": input_type}],
                "outputs": [{"name": "output", "direction": "output", "type": input_type}],
            },
            inner_key: {
                "inputs": [{"name": input_name, "direction": "input", "type": input_type}],
                "outputs": [{"name": "output", "direction": "output", "type": input_type}],
            },
        },
        boundary_ports=[
            {
                "scope_path": outer_key,
                "name": input_name,
                "direction": "input",
                "node_uid": "inner_occ",
                "field": input_name,
            },
            {
                "scope_path": outer_key,
                "name": "output",
                "direction": "output",
                "node_uid": "inner_occ",
                "field": "output",
            },
            {
                "scope_path": inner_key,
                "name": input_name,
                "direction": "input",
                "node_uid": "inner_src",
                "field": "value",
            },
            {
                "scope_path": inner_key,
                "name": "output",
                "direction": "output",
                "node_uid": "inner_core",
                "field": "out",
            },
        ],
    )


def _emit_python_owned(workflow: VibeWorkflow) -> str:
    return emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test"},
        ready_requirements={},
        template_id="video/test",
    )


def _native_boundary_raw() -> dict:
    return {
        "nodes": [{"id": 1, "type": "INTConstant", "widgets_values": [1], "inputs": [], "outputs": []}],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-enable",
                    "name": "Prompt Enhancer",
                    "inputs": [{"name": "", "label": "Enable", "type": "BOOLEAN", "linkIds": [1]}],
                    "outputs": [{"name": "out", "type": "BOOLEAN"}],
                    "nodes": [
                        {
                            "id": 10,
                            "type": "LazySwitchKJ",
                            "inputs": [{"name": "switch", "link": 1}],
                            "outputs": [{"name": "out"}],
                        }
                    ],
                    "links": [
                        {
                            "id": 1,
                            "origin_id": -10,
                            "origin_slot": 0,
                            "target_id": 10,
                            "target_slot": 0,
                            "type": "BOOLEAN",
                        },
                        {
                            "id": 2,
                            "origin_id": 10,
                            "origin_slot": 0,
                            "target_id": -20,
                            "target_slot": 0,
                            "type": "BOOLEAN",
                        },
                    ],
                }
            ]
        },
    }


def _supported_source_subgraph() -> dict:
    return {
        "id": _SUPPORTED_SUBGRAPH_ID,
        "name": "Prompt Enhancer",
        "inputs": [{"name": "enable", "type": "BOOLEAN"}],
        "outputs": [{"name": "out", "type": "BOOLEAN"}],
        "nodes": [
            {
                "id": 10,
                "type": "INTConstant",
                "inputs": [{"name": "value", "link": None}],
                "outputs": [{"name": "value", "links": []}],
                "widgets_values": [1],
            }
        ],
        "links": [],
    }


def test_materialized_subgraph_contract_includes_call_site_and_source_hash() -> None:
    text = _FLUX2_READY.read_text(encoding="utf-8")

    assert "def image_edit_flux2_klein_9b(" in text
    assert "edited = image_edit_flux2_klein_9b(" in text or "image_edit_flux2_klein_9b(" in text
    assert "raw_call('7b34ab90" not in text
    assert "# vibecomfy source hash: sha256:" in text

    owned = _emit_python_owned(_python_owned_recursive_workflow(input_name="input", input_type="IMAGE"))
    assert "def _definition_" in owned
    assert "Typed recursive definition" in owned


def test_subgraph_freshness_detects_hash_drift(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "ready_templates" / "sources"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "supported_subgraph.json"
    source_path.write_text(
        json.dumps({"definitions": {"subgraphs": [_supported_source_subgraph()]}}),
        encoding="utf-8",
    )
    relative_source = source_path.relative_to(tmp_path).as_posix()
    actual = _build_subgraph_def(
        _supported_source_subgraph(),
        slug="prompt_enhancer",
        source_path=relative_source,
    ).source_hash
    template = tmp_path / "ready_templates" / "video" / "supported.py"
    template.parent.mkdir(parents=True)
    template.write_text(
        (
            "from vibecomfy.templates import ReadyMetadata\n"
            "READY_METADATA = ReadyMetadata.build(\n"
            "    capability='video',\n"
            f"    provenance={{'source_workflow_path': {relative_source!r}}},\n"
            ")\n"
            f"def prompt_enhancer():\n"
            f'    """Materialized from subgraph {_SUPPORTED_SUBGRAPH_ID} in {relative_source}.\n'
            f"    # vibecomfy source hash: sha256:{actual}\n"
            '    """\n'
            "    return None\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert _subgraph_freshness_diagnostics(template) == []

    drifted = template.read_text(encoding="utf-8").replace(
        f"sha256:{actual}",
        "sha256:" + ("0" * 64),
        1,
    )
    template.write_text(drifted, encoding="utf-8")
    diagnostics = _subgraph_freshness_diagnostics(template)
    assert diagnostics
    assert "source hash changed" in diagnostics[0]


def test_native_source_freshness_is_unsupported_boundary() -> None:
    diagnostics = _subgraph_freshness_diagnostics(_FLUX2_READY)
    assert diagnostics
    assert any("unsupported_boundary_encoding" in item for item in diagnostics)


def test_subgraph_blank_labeled_input_matches_normalized_call_site_edge() -> None:
    text = _emit_python_owned(
        _python_owned_recursive_workflow(input_name="enable", input_type="BOOLEAN")
    )
    assert "enable: bool" in text
    assert "def _definition_" in text


def test_native_blank_labeled_subgraph_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(_native_boundary_raw(), source_path="native-enable.json")

    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1})
    workflow.nodes["2"] = VibeNode("2", "sg-enable")
    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test"},
        ready_requirements={},
        template_id="video/test",
        raw_workflow=_native_boundary_raw(),
    )
    assert "def prompt_enhancer(" not in text


def test_subgraph_external_input_edge_becomes_function_parameter() -> None:
    text = _emit_python_owned(
        _python_owned_recursive_workflow(input_name="variables.a", input_type="FLOAT")
    )
    assert "variables_a:" in text
    assert "def _definition_" in text


def test_native_external_input_subgraph_fails_closed() -> None:
    raw = {
        "nodes": [{"id": 1, "type": "INTConstant", "widgets_values": [7], "inputs": [], "outputs": []}],
        "links": [],
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
                            "outputs": [{"name": "FLOAT"}],
                            "widgets_values": ["a + 1"],
                        }
                    ],
                    "links": [
                        {
                            "id": 1,
                            "origin_id": 1,
                            "origin_slot": 0,
                            "target_id": 20,
                            "target_slot": 0,
                            "type": "FLOAT",
                        },
                        {
                            "id": 2,
                            "origin_id": 20,
                            "origin_slot": 0,
                            "target_id": -20,
                            "target_slot": 0,
                            "type": "FLOAT",
                        },
                    ],
                }
            ]
        },
    }
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(raw, source_path="native-total.json")
