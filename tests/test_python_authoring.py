from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

from vibecomfy.handles import Handle
from vibecomfy.python_authoring import (
    PythonAuthoringError,
    analyze_python_node,
    outputs,
    port,
    python_node,
)
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_analysis_is_static_and_records_deterministic_identity_and_span() -> None:
    calls: list[str] = []

    def declared(value: "IMAGE") -> "IMAGE":
        calls.append("must not run")
        return value

    spec = analyze_python_node(declared)

    assert calls == []
    assert spec.identity.endswith("test_analysis_is_static_and_records_deterministic_identity_and_span.<locals>.declared")
    assert spec.inputs[0].name == "value"
    assert spec.inputs[0].type == "IMAGE"
    assert spec.outputs[0].name == "result"
    assert spec.spans["function"]["start_line"] > 0
    assert spec.emission["class_type"] == "vibecomfy.exec"


@python_node(result=outputs(port("image", "IMAGE")))
def invert(image: "IMAGE") -> "IMAGE":
    return image


def test_call_lowers_to_exec_and_returns_handle_compatible_named_output() -> None:
    workflow = VibeWorkflow("python-node", WorkflowSource("python-node"))
    source = workflow.add_node("Source")
    handles = invert(workflow, image=Handle(source.id, 0, "IMAGE"))

    assert isinstance(handles.image, Handle)
    assert handles.image.output_slot == 0
    node = workflow.nodes[handles.image.node_id]
    assert node.class_type == "vibecomfy.exec"
    assert node.inputs["source"]
    assert node.inputs["io"] == '{"inputs": {"image": "IMAGE"}, "outputs": {"image": "IMAGE"}}'
    assert node.metadata["python_authoring"]["identity"].endswith("invert")
    assert workflow.edges[-1].to_input == "in_0"
    assert "image" not in node.inputs
    assert node.metadata["output_types"] == ["IMAGE"]


@python_node(inputs={"value": "INT", "gain": "INT"}, outputs={"value": "INT"})
def multiply(value: "INT", gain: "INT" = 2) -> "INT":
    raise AssertionError("the authoring proxy must not execute the function body")


def test_two_calls_are_distinct_exec_nodes_and_defaults_are_graph_bindings() -> None:
    workflow = VibeWorkflow("python-node-reuse", WorkflowSource("python-node-reuse"))
    first = multiply(workflow, value=3)
    second = multiply(workflow, value=first.value, gain=4)

    assert first.value.node_id != second.value.node_id
    first_node = workflow.nodes[first.value.node_id]
    second_node = workflow.nodes[second.value.node_id]
    assert first_node.inputs["in_0"] == 3
    assert first_node.inputs["in_1"] == 2
    assert second_node.inputs["in_1"] == 4
    assert [(edge.from_node, edge.to_node, edge.to_input) for edge in workflow.edges] == [
        (first.value.node_id, second.value.node_id, "in_0")
    ]


def test_lowered_exec_node_delivers_physical_slots_at_runtime() -> None:
    from vibecomfy.comfy_nodes.exec_node import VibeComfyExec

    workflow = VibeWorkflow("python-node-runtime", WorkflowSource("python-node-runtime"))
    handles = invert(workflow, image=7)
    node = workflow.nodes[handles.image.node_id]

    result = VibeComfyExec().execute(
        source=node.inputs["source"],
        io=node.inputs["io"],
        in_0=7,
    )
    assert result[0] == 7
    assert all(value is None for value in result[1:])


@python_node(result=outputs(port("left", "INT"), port("right", "INT"), mode="tuple"))
def split(value: "INT") -> tuple["INT", "INT"]:
    return (value, value)


def test_explicit_tuple_result_adapter_is_lowered_without_running_body() -> None:
    workflow = VibeWorkflow("python-node", WorkflowSource("python-node"))
    handles = split(workflow, value=3)
    node = workflow.nodes[handles.left.node_id]

    assert set(handles.as_dict()) == {"left", "right"}
    assert "'left'" in node.inputs["source"]
    assert "'right'" in node.inputs["source"]
    assert node.inputs["io"] == '{"inputs": {"value": "INT"}, "outputs": {"left": "INT", "right": "INT"}}'


def test_canonical_emitter_writes_readable_definition_and_reloads_it(tmp_path: Path) -> None:
    from vibecomfy.porting.emitter import emit_scratchpad_python

    workflow = VibeWorkflow("python-node-emission", WorkflowSource("python-node-emission"))
    first = multiply(workflow, value=3)
    second = multiply(workflow, value=first.value, gain=4)
    emitted = emit_scratchpad_python(workflow, workflow_id=workflow.id)

    assert "from vibecomfy import python_node" in emitted
    assert "@python_node(inputs={'value': 'INT', 'gain': 'INT'}, outputs={'value': 'INT'})" in emitted
    assert "raw_call('vibecomfy.exec'" not in emitted
    ast.parse(emitted)

    path = tmp_path / "workflow.py"
    path.write_text(emitted, encoding="utf-8")
    module_spec = importlib.util.spec_from_file_location("emitted_python_node", path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    rebuilt = module.build()
    assert [node.class_type for node in rebuilt.nodes.values()] == [
        "vibecomfy.exec",
        "vibecomfy.exec",
    ]
    assert len(rebuilt.edges) == 1
    assert rebuilt.nodes[first.value.node_id].inputs["in_1"] == 2
    assert rebuilt.nodes[second.value.node_id].inputs["in_1"] == 4


def test_canonical_emitter_uses_named_python_handle_for_downstream_wrapper(tmp_path: Path) -> None:
    from vibecomfy.nodes.core import SaveImage
    from vibecomfy.porting.emitter import emit_scratchpad_python

    workflow = VibeWorkflow("python-node-downstream", WorkflowSource("python-node-downstream"))
    image = invert(workflow, image=7)
    SaveImage(workflow, images=image.image, filename_prefix="python-node-downstream")

    emitted = emit_scratchpad_python(workflow, workflow_id=workflow.id)
    assert ".image" in emitted
    assert ".out('image')" not in emitted
    ast.parse(emitted)

    path = tmp_path / "workflow.py"
    path.write_text(emitted, encoding="utf-8")
    module_spec = importlib.util.spec_from_file_location("emitted_python_node_downstream", path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    rebuilt = module.build()
    save_node = next(node for node in rebuilt.nodes.values() if node.class_type == "SaveImage")
    assert [(edge.from_node, edge.from_output, edge.to_node, edge.to_input) for edge in rebuilt.edges] == [
        ("1", "0", save_node.id, "images")
    ]


def test_invalid_variadic_declaration_is_rejected_during_decoration() -> None:
    with pytest.raises(PythonAuthoringError, match="variadic"):

        @python_node
        def invalid(*values: "IMAGE") -> "IMAGE":
            return values[0]


def test_complete_source_snapshot_preserves_relative_imports_and_is_inert_until_queue(tmp_path: Path) -> None:
    package = tmp_path / "image_tools"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helpers.py").write_text("FACTOR = 3\n", encoding="utf-8")
    (package / "pipeline.py").write_text(
        "from .helpers import FACTOR\n"
        "def process(image):\n"
        "    return {'image': image * FACTOR}\n",
        encoding="utf-8",
    )

    process = python_node.from_source(
        str(package),
        entrypoint="pipeline:process",
        inputs={"image": "INT"},
        outputs={"image": "INT"},
    )
    workflow = VibeWorkflow("source-snapshot", WorkflowSource("source-snapshot"))
    handles = process(workflow, image=4)
    node = workflow.nodes[handles.image.node_id]
    payload = json.loads(node.inputs["source"])
    assert payload["format"] == "vibecomfy.python_capsule/v1"
    assert {item["path"] for item in payload["manifest"]["files"]} == {
        "image_tools/__init__.py",
        "image_tools/helpers.py",
        "image_tools/pipeline.py",
    }
    from vibecomfy.comfy_nodes.exec_node import VibeComfyExec

    result = VibeComfyExec().execute(source=node.inputs["source"], io=node.inputs["io"], in_0=4)
    assert result[0] == 12

    from vibecomfy.porting.emitter import emit_scratchpad_python

    emitted = emit_scratchpad_python(workflow, workflow_id=workflow.id)
    assert "python_node.from_source(" in emitted
    assert "raw_call('vibecomfy.exec'" not in emitted
    ast.parse(emitted)
    generated_path = tmp_path / "generated.py"
    generated_path.write_text(emitted, encoding="utf-8")
    generated_spec = importlib.util.spec_from_file_location("generated_source_snapshot", generated_path)
    assert generated_spec is not None and generated_spec.loader is not None
    generated_module = importlib.util.module_from_spec(generated_spec)
    generated_spec.loader.exec_module(generated_module)
    generated = generated_module.build()
    assert len(generated.nodes) == 1
    generated_node = next(iter(generated.nodes.values()))
    assert VibeComfyExec().execute(
        source=generated_node.inputs["source"],
        io=generated_node.inputs["io"],
        in_0=4,
    )[0] == 12


def test_installed_entrypoint_is_declared_without_import_and_runs_with_normal_name(tmp_path, monkeypatch) -> None:
    package = tmp_path / "installed_tools"
    package.mkdir()
    marker = tmp_path / "imported"
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "pipeline.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n"
        "def process(value):\n    return {'value': value + 1}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    process = python_node.from_installed(
        entrypoint="installed_tools.pipeline:process",
        inputs={"value": "INT"},
        outputs={"value": "INT"},
    )
    assert not marker.exists()
    workflow = VibeWorkflow("installed-source", WorkflowSource("installed-source"))
    handles = process(workflow, value=4)
    node = workflow.nodes[handles.value.node_id]
    assert not marker.exists()
    from vibecomfy.comfy_nodes.exec_node import VibeComfyExec

    result = VibeComfyExec().execute(source=node.inputs["source"], io=node.inputs["io"], in_0=4)
    assert result[0] == 5
    assert marker.exists()
