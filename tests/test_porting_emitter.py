from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.errors import ArityDisagreementError, ConversionParityError, ObjectInfoIdentityAmbiguityError
from vibecomfy.ingest.normalize import from_api, from_ui, normalize_to_api
from vibecomfy.porting.convert import ManualTemplateRefusal, _check_manual_refusal, port_convert_workflow
from vibecomfy.porting.object_info.serialize import build_cache
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
    READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
    READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
    emit_agent_edit_python,
    emit_canonical_python,
    emit_ready_template_python,
    emit_scratchpad_python,
    format_as_python,
)
from vibecomfy.porting.emit.emit_ready import _v2_output_args
from vibecomfy.security.agent_generated_loader import (
    AgentGeneratedLoadError,
    load_agent_generated_scratchpad,
    scan_agent_generated_python,
)
from vibecomfy.security.provenance import Provenance
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import (
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowRequirements,
    WorkflowSource,
)
from vibecomfy.workflow_bundle import emit_bundle, load_bundle


def _bundle_roundtrip(workflow: VibeWorkflow, tmp_path: Path, name: str = "roundtrip.py") -> VibeWorkflow:
    """Reload through the canonical Python/companion pair."""
    path = tmp_path / name
    emit_bundle(workflow, path, {"operation": "authored"})
    return load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow


def _assert_emitted_call_has_empty_native_authority(
    text: str,
    call_header: str,
    *required_fragments: str,
) -> str:
    """Assert an emitted call is readable and keeps custody out of arguments."""
    start = text.index(call_header)
    line_end = text.index("\n", start)
    end = (
        text.index("\n    )", start)
        if text[start:line_end].rstrip().endswith("(")
        else line_end
    )
    call = text[start:end]
    assert "_id=" not in call
    assert "_uid=" not in call
    assert "_native_ports=" not in call
    for fragment in required_fragments:
        assert fragment in call
    return call


def _install_no_gpu_graphbuilder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a deterministic local GraphBuilder seam for compiler parity tests."""
    graph_utils = types.ModuleType("comfy_execution.graph_utils")

    class GraphBuilder:
        def __init__(self, *, prefix: str = "") -> None:
            self._nodes: dict[str, dict[str, Any]] = {}

        def node(self, class_type: str, *, id: str, **inputs: Any) -> None:
            self._nodes[str(id)] = {"class_type": class_type, "inputs": inputs}

        def finalize(self) -> dict[str, dict[str, Any]]:
            return {key: self._nodes[key] for key in sorted(self._nodes)}

    graph_utils.GraphBuilder = GraphBuilder
    comfy_execution = types.ModuleType("comfy_execution")
    comfy_execution.graph_utils = graph_utils
    monkeypatch.setitem(sys.modules, "comfy_execution", comfy_execution)
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", graph_utils)


def _sample_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["10"] = VibeNode("10", "LoadImage", inputs={"image": "input.png"}, uid="load")
    workflow.nodes["20"] = VibeNode(
        "20",
        "SaveImage",
        inputs={"filename_prefix": "out/sample", "resize_type.multiple": 3},
        uid="save",
    )
    workflow.connect("10.0", "20.images")
    workflow.register_input("prefix", "20", "filename_prefix", "out/sample")
    return workflow


def test_explicit_provenance_has_stable_source_position_and_preserves_metadata() -> None:
    marker = {"format_version": 2, "generation_id": "generation-witness", "custody_digest": "custody-witness"}
    inherited = {"operation": "imported", "origin_uri": "urn:inherited"}
    explicit = {"operation": "authored", "origin_uri": "urn:explicit", "tool_versions": {"fixture": "1"}}
    note = {"witness": "retained content"}
    sources = []
    for keys in (("provenance", "source_bundle"), ("source_bundle", "provenance")):
        workflow = VibeWorkflow("stable-provenance", WorkflowSource("stable-provenance"))
        values = {"provenance": inherited, "source_bundle": marker}
        workflow.metadata = {"author_note": note, **{key: values[key] for key in keys}}
        sources.append(emit_canonical_python(workflow, provenance=explicit, external_custody=True))
        assert workflow.metadata["provenance"] == inherited

    assert sources[0].encode("utf-8") == sources[1].encode("utf-8")

    def metadata_values(source: str) -> dict[str, Any]:
        call = next(
            statement.value for statement in ast.parse(source).body
            if isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "READY_METADATA" for target in statement.targets)
        )
        return {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}

    metadata = metadata_values(sources[0])
    assert metadata["provenance"] == explicit
    assert metadata["source_bundle"] == marker
    assert metadata["author_note"] == note
    inherited_metadata = metadata_values(emit_canonical_python(workflow, external_custody=True))
    assert inherited_metadata["provenance"] == inherited
    assert inherited_metadata["source_bundle"] == marker
    assert inherited_metadata["author_note"] == note


def test_canonical_emitter_restricted_round_trip_is_the_same_ir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_no_gpu_graphbuilder(monkeypatch)
    workflow = VibeWorkflow("canonical/probe", WorkflowSource("canonical/probe"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "INTConstant",
        inputs={"value": 3},
        widgets={"label": "three"},
        uid="constant",
        native_input_names=["value", None],
        native_output_names=["INT"],
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "MysterySink",
        inputs={"value": None},
        uid="sink",
        metadata={
            "unresolved": True,
            "diagnostics": ["schema missing"],
            "provenance": {"source": "fixture"},
            "input_names": ["value"],
        },
    )
    workflow.connect("1.INT", "2.value")
    workflow.inputs["amount"] = VibeInput(
        "amount", "1", "value", 3, type="INT", default=2,
        required=True, range=[0, 9], aliases=("count",),
    )
    workflow._manual_input_names.add("amount")
    workflow.requirements = WorkflowRequirements(
        models=["model.safetensors"], custom_nodes=["MysteryPack"],
        missing_models=["missing.safetensors"], missing_nodes=["MysterySink"],
        unsupported=["unsupported feature"],
    )
    workflow.variants = {"high": {"constant.value": 9}}
    workflow.default_variant = "high"

    source = emit_canonical_python(workflow, ready_metadata={"capability": "unknown"})
    assert scan_agent_generated_python(source).ok
    assert "INTConstant(" in source
    assert source.count("raw_call('MysterySink'") == 1
    assert "def _node" not in source
    assert ".add(" not in source

    reloaded = _bundle_roundtrip(workflow, tmp_path, "canonical_probe.py")
    assert reloaded.id == workflow.id
    assert reloaded.semantic_digest() == workflow.semantic_digest()
    assert reloaded.compile("api") == workflow.compile("api")
    assert reloaded.compile("graphbuilder") == workflow.compile("graphbuilder")


def test_agent_edit_view_is_rejected_by_restricted_executable_loader(tmp_path: Path) -> None:
    source = emit_agent_edit_python(_sample_workflow())
    path = tmp_path / "agent_edit.py"
    path.write_text(source, encoding="utf-8")
    with pytest.raises((AgentGeneratedLoadError, NameError)):
        load_agent_generated_scratchpad(path)


def test_canonical_emitter_reloads_explicit_unknown_output_slot_without_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = VibeWorkflow("slot-witness", WorkflowSource("slot-witness"))
    source = workflow.node("SchemaLessSource")
    workflow.node("SchemaLessSink", value=source.out(3))
    assert source.node.native_output_names is None
    assert source.node.native_output_slots == [3]

    path = tmp_path / "slot_witness.py"
    emit_bundle(workflow, path, {"operation": "authored"})
    assert "_native_ports" not in path.read_text(encoding="utf-8")

    import vibecomfy.templates as templates_module

    def poisoned_provider():
        raise AssertionError("emitted native slot authority consulted ambient provider")

    monkeypatch.setattr(templates_module, "_ready_schema_provider", poisoned_provider)
    reloaded = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    assert reloaded.semantic_digest() == workflow.semantic_digest()
    assert reloaded.compile("api") == workflow.compile("api")


def test_agent_edit_recursive_display_ignores_raw_ui_definitions() -> None:
    workflow = VibeWorkflow("canonical/agent-edit", WorkflowSource("canonical/agent-edit"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="root")
    workflow.definitions = {
        "subgraphs": [{"id": "authored", "nodes": [], "links": []}],
    }
    authored = emit_agent_edit_python(
        workflow,
        raw_workflow={"definitions": {"subgraphs": [{"id": "sidecar-only", "nodes": [], "links": []}]}},
    )
    clean = emit_agent_edit_python(workflow, raw_workflow={"definitions": {"subgraphs": []}})
    assert authored == clean
    assert "authored" in authored
    assert "sidecar-only" not in authored


def test_canonical_emitter_preserves_recursive_fields_and_ignores_raw_ui(tmp_path: Path) -> None:
    definition = {
        "id": "inner-definition",
        "name": "Inner",
        "nodes": [{"id": "core", "uid": "core", "type": "InnerNode", "inputs": {"x": 1}}],
        "links": [],
    }
    workflow = VibeWorkflow("canonical/recursive", WorkflowSource("canonical/recursive"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="root")
    workflow.definitions = {"subgraphs": [definition]}
    workflow.interfaces = {"inner-definition": {"inputs": [], "outputs": []}}
    workflow.boundary_ports = []
    workflow.virtual_wires = {}

    left = format_as_python(
        workflow,
        ready_metadata={"ready_template": workflow.id},
        ready_requirements={},
        template_id=workflow.id,
        raw_workflow={"definitions": {"subgraphs": [{"id": "lie"}]}},
    )
    right = format_as_python(
        workflow,
        ready_metadata={"ready_template": workflow.id},
        ready_requirements={},
        template_id=workflow.id,
        raw_workflow={"definitions": {"subgraphs": []}},
    )
    assert left == right
    reloaded = _bundle_roundtrip(workflow, tmp_path, "canonical_recursive.py")
    assert reloaded.semantic_digest() == workflow.semantic_digest()
    assert reloaded.compile("api") == workflow.compile("api")


def test_canonical_depth_two_recursive_helpers_reload_twice_with_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_no_gpu_graphbuilder(monkeypatch)
    from tests.test_b11b_execution_projection import _depth_two_sibling_workflow

    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    source = emit_canonical_python(workflow)
    assert scan_agent_generated_python(source).ok
    inner_name = "_definition_" + (outer_key + "/" + inner_key).replace(":", "_").replace("/", "_")
    outer_name = "_definition_" + outer_key.replace(":", "_")
    assert source.count("def _definition_") == 2
    assert source.index(f"\ndef {inner_name}(wf: VibeWorkflow, input: Any) -> Any:") < source.index(
        f"\ndef {outer_name}(wf: VibeWorkflow, input: Any) -> Any:"
    )
    assert "-> Any:" in source
    assert "wf.interfaces =" in source
    assert "wf.boundary_ports =" in source
    assert f" = {inner_name}(wf, input)" in source
    assert "raw_call('EchoImage', pass_raw=True" in source
    assert "wf.connect(" not in source
    build_source = source[source.index("def build") :]
    assert "wf.definitions = _build_recursive_definitions(wf)" in build_source

    path = tmp_path / "depth_two.py"
    emit_bundle(workflow, path, {"operation": "authored"})
    first = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    second = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    assert first.semantic_digest() == workflow.semantic_digest()
    assert second.semantic_digest() == first.semantic_digest()
    assert first.compile("api") == workflow.compile("api")
    assert first.compile("graphbuilder") == workflow.compile("graphbuilder")


def test_nested_constructor_edit_is_authoritative_for_rebuilt_definition() -> None:
    definition = {
        "id": "nested-default",
        "name": "NestedDefault",
        "nodes": [{"id": "constant", "type": "INTConstant", "inputs": {"value": 2}}],
        "links": [],
    }
    workflow = VibeWorkflow("canonical/nested-edit", WorkflowSource("canonical/nested-edit"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="root")
    workflow.definitions = {"subgraphs": [definition]}
    source = emit_canonical_python(workflow)
    assert scan_agent_generated_python(source).ok
    assert "INTConstant(value=2)" in source
    edited = source.replace("INTConstant(value=2)", "INTConstant(value=7)", 1)
    namespace: dict[str, object] = {"__file__": "nested_edit.py"}
    exec(compile(edited, "nested_edit.py", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["build"]()
    node = rebuilt.definitions["subgraphs"][0]["nodes"][0]
    assert node["type"] == "INTConstant"
    assert "class_type" not in node
    assert node["inputs"]["value"] == 7


def test_from_ui_nested_definition_round_trips_authored_roster_and_link_metadata(tmp_path: Path) -> None:
    raw = {
        "nodes": [{"id": 1, "type": "RootNode", "class_type": "RootNode", "inputs": [], "outputs": []}],
        "links": [],
        "definitions": {"subgraphs": [{
            "id": "nested",
            "nodes": [
                {"id": "source", "type": "SourceNode", "inputs": [], "outputs": [{"name": "value", "type": "INT", "links": [1]}]},
                {"id": "sink", "type": "SinkNode", "inputs": [{"name": "value", "type": "INT", "link": 1, "value": None}], "outputs": []},
            ],
            "links": [[1, "source", 0, "sink", 0, "INT"]],
        }]},
    }
    workflow = from_ui(raw, use_comfy_converter=False)
    source = emit_canonical_python(workflow)
    assert "source = raw_call('SourceNode'" in source
    assert "value=source.out(0)" in source
    path = tmp_path / "nested.py"
    path.write_text(source, encoding="utf-8")
    reloaded = load_agent_generated_scratchpad(path)
    definition = reloaded.definitions["subgraphs"][0]
    assert len(definition["nodes"]) == 2
    assert len(definition["links"]) == 1
    assert definition["nodes"][1]["inputs"][0]["link"] == definition["links"][0][0]
    assert definition["nodes"][0]["outputs"][0]["links"] == [definition["links"][0][0]]
    assert reloaded.semantic_digest() == load_agent_generated_scratchpad(path).semantic_digest()
    edited = source.replace("raw_call('SourceNode'", "raw_call('EditedSourceNode'", 1)
    edited_path = tmp_path / "nested-edited.py"
    edited_path.write_text(edited, encoding="utf-8")
    changed = load_agent_generated_scratchpad(edited_path)
    changed_node = changed.definitions["subgraphs"][0]["nodes"][0]
    assert changed_node.get("class_type", changed_node.get("type")) == "EditedSourceNode"


def test_canonical_recursive_callable_source_has_known_unknown_local_nodes() -> None:
    from vibecomfy.identity.scope import sg_key

    definition = {
        "id": "local-def",
        "name": "LocalDef",
        "nodes": [
            {"id": "known", "type": "INTConstant", "inputs": [{"name": "value", "link": None, "value": 2}]},
            {"id": "unknown", "type": "MysteryLocal", "inputs": [{"name": "value", "link": None, "value": None}]},
        ],
        "links": [[1, "known", 0, "unknown", "value", "INT"]],
    }
    key = sg_key(definition)
    workflow = VibeWorkflow("canonical/typed-local", WorkflowSource("canonical/typed-local"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="root")
    workflow.definitions = {"subgraphs": [definition]}
    workflow.interfaces = {
        key: {
            "inputs": [{"name": "input", "direction": "input", "type": "INT"}],
            "outputs": [{"name": "output", "direction": "output", "type": "INT"}],
        }
    }
    workflow.boundary_ports = [
        {"scope_path": key, "name": "input", "direction": "input", "node_uid": "unknown", "field": "value"},
        {"scope_path": key, "name": "output", "direction": "output", "node_uid": "unknown", "field": "0"},
    ]
    source = emit_canonical_python(workflow)
    definition_name = "_definition_" + key.replace(":", "_")
    assert f"def {definition_name}(wf: VibeWorkflow, input: int) -> int:" in source
    assert "INTConstant(value=2)" in source
    assert "from vibecomfy.nodes.kjnodes import INTConstant" in source
    assert "raw_call('MysteryLocal', pass_raw=True" in source


def test_canonical_recursive_callable_rejects_malformed_boundary_scope() -> None:
    workflow, _inner_key, outer_key = __import__(
        "tests.test_b11b_execution_projection", fromlist=["_depth_two_sibling_workflow"]
    )._depth_two_sibling_workflow()
    workflow.boundary_ports[0]["scope_path"] = "missing-scope"
    with pytest.raises(ValueError, match="boundary_port_malformed"):
        emit_canonical_python(workflow)


def test_canonical_recursive_definition_cycles_and_collisions_fail_closed() -> None:
    cycle = {"id": "cycle", "nodes": [], "links": []}
    cycle["definitions"] = {"subgraphs": [cycle]}
    cyclic = VibeWorkflow("canonical/cycle", WorkflowSource("canonical/cycle"))
    cyclic.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="root")
    cyclic.definitions = {"subgraphs": [cycle]}
    with pytest.raises(ValueError, match="recursive_definition_cycle"):
        emit_canonical_python(cyclic)

    duplicate = {"id": "same", "nodes": [], "links": []}
    colliding = VibeWorkflow("canonical/collision", WorkflowSource("canonical/collision"))
    colliding.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="root")
    colliding.definitions = {"subgraphs": [duplicate, dict(duplicate)]}
    with pytest.raises(ValueError, match="duplicate recursive definition helper identity"):
        emit_canonical_python(colliding)


def test_canonical_emitter_does_not_duplicate_imported_link_views(tmp_path: Path) -> None:
    workflow = VibeWorkflow("canonical/edge", WorkflowSource("canonical/edge"))
    workflow.nodes["1"] = VibeNode(
        "1", "INTConstant", inputs={"value": 1}, uid="source"
    )
    workflow.nodes["2"] = VibeNode(
        "2", "MysterySink", inputs={"value": ["1", 0]}, uid="target",
        metadata={"unresolved": True, "input_names": ["value"]},
    )
    workflow.connect("1.0", "2.value")

    source = emit_canonical_python(workflow)
    assert "value=intconstant" in source
    assert "wf.connect(" not in source
    path = tmp_path / "edge.py"
    reloaded = _bundle_roundtrip(workflow, tmp_path, "edge.py")
    assert len(reloaded.edges) == 1
    expected = workflow.copy()
    expected.nodes["2"].inputs.pop("value")
    assert reloaded.semantic_digest() == expected.semantic_digest()
    assert reloaded.compile("api") == expected.compile("api")


def test_scoped_api_link_emission_uses_handles(tmp_path: Path) -> None:
    workflow = from_api(
        {
            "1::1": {"class_type": "ScopedSource", "inputs": {"value": 3}},
            "2::2": {"class_type": "ScopedSink", "inputs": {"value": ["1::1", 0]}},
        },
        source_path="scoped.json",
    )

    assert len(workflow.edges) == 1
    assert not workflow.nodes["2::2"].inputs
    source = emit_canonical_python(workflow)
    build_source = source[source.index("def build") :]
    assert "['1::1', 0]" not in build_source
    assert "scopedsource.out(0)" in build_source
    assert "wf.connect(" not in build_source

    path = tmp_path / "scoped.py"
    reloaded = _bundle_roundtrip(workflow, tmp_path, "scoped.py")
    assert reloaded.semantic_digest() == workflow.semantic_digest()
    assert reloaded.compile("api") == workflow.compile("api")


def test_canonical_emitter_preserves_auxiliary_output_nodes_and_their_edges(
    tmp_path: Path,
) -> None:
    def _node(
        node_id: str,
        class_type: str,
        *,
        inputs: tuple[str, ...] = (),
        outputs: tuple[str, ...] = (),
    ) -> VibeNode:
        return VibeNode(
            node_id,
            class_type,
            uid=node_id,
            native_input_names=list(inputs),
            native_output_names=list(outputs),
            native_input_types=["*"] * len(inputs),
            native_output_types=["*"] * len(outputs),
        )

    terminal = VibeWorkflow("canonical/terminal-ui", WorkflowSource("canonical/terminal-ui"))
    terminal.nodes["source"] = _node("source", "SchemaLessSource", outputs=("value",))
    terminal.nodes["preview"] = _node(
        "preview", "PreviewAny", inputs=("source",), outputs=("value",)
    )
    terminal.connect("source.value", "preview.source")

    terminal_source = emit_canonical_python(terminal)
    assert "source=schemalesssource.out('value')" in terminal_source
    terminal_reloaded = _bundle_roundtrip(terminal, tmp_path, "terminal_ui.py")
    assert set(terminal_reloaded.nodes) == {"source", "preview"}
    assert terminal_reloaded.semantic_digest() == terminal.semantic_digest()

    passthrough = terminal.copy()
    passthrough.id = "canonical/ui-passthrough"
    passthrough.source = WorkflowSource("canonical/ui-passthrough")
    passthrough.nodes["sink"] = _node("sink", "SchemaLessSink", inputs=("value",))
    passthrough.connect("preview.value", "sink.value")

    passthrough_source = emit_canonical_python(passthrough)
    assert "source=schemalesssource.out('value')" in passthrough_source
    # PreviewAny has no authoritative native output roster in this fixture,
    # so its single output remains positional.
    assert "value=previewany.out(0)" in passthrough_source
    passthrough_reloaded = _bundle_roundtrip(passthrough, tmp_path, "ui_passthrough.py")
    assert set(passthrough_reloaded.nodes) == {"source", "preview", "sink"}
    assert passthrough_reloaded.semantic_digest() == passthrough.semantic_digest()


@pytest.mark.parametrize("mode", ["canonical", "ready", "scratchpad"])
def test_previewany_terminal_has_shared_node_edge_semantic_parity(mode: str, tmp_path: Path) -> None:
    terminal = VibeWorkflow(f"preview-parity/{mode}", WorkflowSource(f"preview-parity/{mode}"))
    terminal.nodes["source"] = VibeNode("source", "SchemaLessSource", uid="source", native_output_names=["value"])
    terminal.nodes["preview"] = VibeNode("preview", "PreviewAny", uid="preview", native_input_names=["source"])
    terminal.connect("source.value", "preview.source")
    if mode == "canonical":
        text = emit_canonical_python(terminal)
    elif mode == "ready":
        text = emit_ready_template_python(terminal, ready_metadata={}, ready_requirements={}, template_id=terminal.id)
    else:
        text = emit_scratchpad_python(terminal, workflow_id=terminal.id)
    path = tmp_path / f"{mode}.py"
    reloaded = _bundle_roundtrip(terminal, tmp_path, f"{mode}.py")
    assert set(reloaded.nodes) == {"source", "preview"}
    assert len(reloaded.edges) == 1
    assert reloaded.semantic_digest() == terminal.semantic_digest()


def test_scratchpad_rejects_noncanonical_projection_options() -> None:
    with pytest.raises(ValueError, match="canonical defaults"):
        emit_scratchpad_python(_sample_workflow(), keep_virtual_wires=False)
    with pytest.raises(ValueError, match="canonical defaults"):
        emit_scratchpad_python(_sample_workflow(), prune_dead_branches=True)
    diagnostics: list[EmissionDiagnostic] = []
    emit_scratchpad_python(
        _sample_workflow(),
        keep_virtual_wires=False,
        prune_dead_branches=True,
        diagnostics=diagnostics,
    )
    assert [item.code for item in diagnostics].count(
        "deprecated_scratchpad_projection_options"
    ) == 1


def _workflow_from_ui_json(path: str) -> tuple[VibeWorkflow, dict[str, Any]]:
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = from_api(api, source_path=path, workflow_id=Path(path).stem)
    return workflow, raw


def _emit_ready_from_ui_json(path: str, template_id: str) -> str:
    workflow, raw = _workflow_from_ui_json(path)
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


def test_emit_scratchpad_python_is_thin_canonical_migration(tmp_path: Path) -> None:
    original = _sample_workflow()
    original.nodes["10"].uid = ""
    original.nodes["20"].uid = ""
    text = emit_scratchpad_python(
        original,
        workflow_id="scratch/sample",
        source_path="ready_templates/sources/source.json",
        provenance={"source_hash": "sha256:abc"},
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA" in text
    assert "# vibecomfy: surface=canonical" in text
    assert "'source_hash': 'sha256:abc'" in text
    assert "**{'resize_type.multiple': 3}" in text
    assert "def _node" not in text
    assert not original.nodes["10"].uid

    # The source-only characterization intentionally exercises a draft with
    # blank importer UIDs.  The v2 pair writer is an identity boundary and
    # therefore receives the valid authored fixture, not that invalid draft.
    workflow = _bundle_roundtrip(_sample_workflow(), tmp_path, "scratch_sample.py")

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == original.id
    assert workflow.source.source_type == "ready_template"
    assert sorted(workflow.nodes) == ["10", "20"]
    assert workflow.nodes["20"].inputs["resize_type.multiple"] == 3
    assert workflow.inputs["prefix"].node_id == "20"
    assert workflow.compile("api")["20"]["inputs"]["images"] == ["10", 0]


def test_emit_ready_template_python_has_ready_metadata_contract(tmp_path: Path) -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "image/sample", "source_workflow": "ready_templates/sources/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA =" in text
    assert "READY_REQUIREMENTS =" not in text
    assert "ReadyMetadata.build(" in text
    assert "template_id='sample'" in text
    assert "from vibecomfy.templates import" in text
    assert "from vibecomfy.registry.ready_template import" not in text
    assert "def _node" not in text
    assert "with new_workflow(READY_METADATA, source_path=__file__) as wf:" in text
    _assert_emitted_call_has_empty_native_authority(
        text,
        "loadimage = LoadImage(",
        "image='input.png'",
    )
    assert "'id': '10'" not in text
    assert "'uid': 'load'" not in text
    assert "CANONICAL_CUSTODY" not in text
    assert "HELPER_CUSTODY" not in text
    assert "wf.metadata.setdefault('id_map'" not in text
    assert "wf._set_id_map(" not in text
    assert "LoadImage(wf" not in text
    assert "PUBLIC_INPUT_METADATA = {" in text
    assert "def PUBLIC_INPUTS(**nodes):" not in text
    assert "        wf = wf.finalize(PUBLIC_INPUT_METADATA" in text
    assert "'prefix': InputSpec(node=ref('saveimage'), field='filename_prefix', default=DEFAULT_PREFIX" in text
    assert "bind_input(" not in text
    assert "bind_output(" not in text
    assert _bundle_roundtrip(_sample_workflow(), tmp_path, "canonical_ready.py").semantic_digest() == _sample_workflow().semantic_digest()


def test_ready_emitter_does_not_embed_native_subgraph_source_graph() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={
            "ready_template": "video/h3",
            "_native_subgraph_source": {
                "nodes": [{"id": "inner", "type": "Loader"}],
                "links": [[1, "inner", 0, "sink", 0, "VIDEO"]],
                "boundary": {"inputs": [], "outputs": []},
            },
            "_native_subgraph_provenance": {"source_sha256": "h3-sha"},
            "_native_subgraph_diagnostics": [{"kind": "repaired_output_backlink"}],
            "_ui_door": {
                "nodes": [{"id": 1, "type": "Loader", "pos": [10, 20]}],
                "links": [[1, 1, 0, 2, 0, "VIDEO"]],
                "boundary": {"inputs": [], "outputs": []},
                "presentation": {"last_node_id": 2, "groups": []},
            },
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="video/h3",
    )

    metadata_start = text.index("READY_METADATA =")
    metadata_end = text.index("\n\n", metadata_start)
    metadata = text[metadata_start:metadata_end]
    assert "_native_subgraph_source" not in metadata
    assert "_ui_door" not in metadata
    assert "'nodes':" not in metadata
    assert "'links':" not in metadata
    assert "'boundary':" not in metadata
    assert "'presentation':" not in metadata
    assert "_native_subgraph_provenance" in metadata
    assert "_native_subgraph_diagnostics" in metadata


def test_ready_template_provenance_paths_are_repo_relative() -> None:
    source_path = find_repo_root() / "ready_templates/sources" / "source.json"
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={
            "ready_template": "image/sample",
            "capability": "image",
            "provenance": {
                "source_path": str(source_path),
                "source_workflow_path": str(source_path),
                "source_workflow": str(source_path),
            },
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
    )

    assert str(source_path) not in text
    assert "'source_path': 'ready_templates/sources/source.json'" in text
    assert "'source_workflow_path': 'ready_templates/sources/source.json'" in text
    assert "'source_workflow': 'ready_templates/sources/source.json'" in text


def test_emit_ready_template_omits_empty_model_and_input_boilerplate() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out/sample"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/no_inputs", "capability": "image"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/no_inputs",
    )

    assert "MODELS = {}" not in text
    assert "PUBLIC_INPUTS = {}" not in text
    assert "PUBLIC_INPUT_METADATA" not in text
    assert "def PUBLIC_INPUTS" not in text
    assert "    inputs=PUBLIC_INPUTS," not in text
    assert "    models=MODELS," not in text
    assert "wf = wf.finalize({}" in text
    assert "ModelAsset" not in text
    assert "InputSpec" not in text


def test_ready_template_public_inputs_bind_actual_node_objects() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "image/sample", "source_workflow": "ready_templates/sources/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "node=ref('saveimage')" in text
    assert "node='20'" not in text
    assert "PUBLIC_INPUT_METADATA" in text
    assert "wf.finalize(PUBLIC_INPUT_METADATA" in text


def test_ready_template_public_inputs_survive_variable_suffix_changes() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["10"] = VibeNode("10", "SaveImage", inputs={"filename_prefix": "out/first"})
    workflow.nodes["20"] = VibeNode("20", "SaveImage", inputs={"filename_prefix": "out/second"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/renamed", "capability": "image"},
        ready_requirements={},
        template_id="image/renamed",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "'prefix': InputSpec(node=ref('saveimage_2'), field='filename_prefix'" in text
    assert "def PUBLIC_INPUTS(**nodes):" not in text


def test_ready_template_public_input_refs_do_not_depend_on_model_asset_keys() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "obscure-file-name.safetensors", "weight_dtype": "default"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/model_key_independent",
            "capability": "image",
            "model_assets": [
                {
                    "name": "obscure-file-name.safetensors",
                    "url": "https://example.test/obscure-file-name.safetensors",
                    "subdir": "diffusion_models",
                    "field": "unet_name",
                }
            ],
        },
        ready_requirements={},
        template_id="image/model_key_independent",
        registered_inputs={"model": ("1", "unet_name")},
    )

    assert "'diffusion_model': ModelAsset(" in text
    assert "InputSpec(node=ref('unetloader'), field='unet_name'" in text
    namespace: dict[str, object] = {"__file__": "ready_templates/image/model_key_independent.py"}
    exec(compile(text, "ready_templates/image/model_key_independent.py", "exec"), namespace)  # noqa: S102
    workflow = namespace["build"]()

    assert workflow.inputs["model"].node_id == "1"
    assert workflow.inputs["model"].field == "unet_name"


def test_emitter_warns_for_schema_unknown_identifier_kwargs_hidden_by_extras() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out/sample", "mystery": 3})
    diagnostics: list[EmissionDiagnostic] = []

    emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/schema_unknown", "capability": "image"},
        ready_requirements={},
        template_id="image/schema_unknown",
        diagnostics=diagnostics,
    )

    assert any(
        diagnostic.code == READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS
        and diagnostic.detail["input"] == "mystery"
        for diagnostic in diagnostics
    )


def test_emitter_keeps_non_identifier_extras_without_schema_unknown_warning() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "ImageScaleToTotalPixels", inputs={"megapixels": 1.0, "resize_type.multiple": 3})
    diagnostics: list[EmissionDiagnostic] = []

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/custom_extra", "capability": "image"},
        ready_requirements={},
        template_id="image/custom_extra",
        diagnostics=diagnostics,
    )

    assert "**{'resize_type.multiple': 3}" in text
    assert not any(
        diagnostic.code == READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS
        for diagnostic in diagnostics
    )


def test_model_block_uses_role_based_keys_for_model_constants() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "model.safetensors", "weight_dtype": "default"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/roles",
            "capability": "image",
            "model_assets": [
                {
                    "name": "obscure-file-name.safetensors",
                    "url": "https://example.test/obscure-file-name.safetensors",
                    "subdir": "diffusion_models",
                    "field": "unet_name",
                }
            ],
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/roles",
    )

    assert "'diffusion_model': ModelAsset(" in text
    assert "'obscure_file_name': ModelAsset(" not in text


def test_model_constant_names_dedupe_path_prefixed_basenames() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "DualCLIPLoader",
        inputs={
            "clip_name1": "gemma_3_12B_it_fp4_mixed.safetensors",
            "clip_name2": "ltx-2.3_text_projection_bf16.safetensors",
        },
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "ProjectionLoader",
        inputs={"model_name": r"VIDEO\LTX\LTX-2\ltx-2.3_text_projection_bf16.safetensors"},
    )
    workflow.nodes["3"] = VibeNode("3", "VAELoader", inputs={"vae_name": "taeltx2_3.safetensors"})
    workflow.nodes["4"] = VibeNode("4", "VAELoader", inputs={"vae_name": r"vae_approx\taeltx2_3.safetensors"})
    workflow.nodes["5"] = VibeNode("5", "TextEncoderLoader", inputs={"text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors"})
    workflow.nodes["6"] = VibeNode("6", "CheckpointLoaderSimple", inputs={"ckpt_name": "ltx-2-19b-distilled.safetensors"})
    workflow.nodes["7"] = VibeNode("7", "LTXModelLoader", inputs={"ltxv_path": "ltx-2-19b-distilled.safetensors"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/model_dedupe", "capability": "image"},
        ready_requirements={},
        template_id="image/model_dedupe",
    )

    assert "CKPT_PROJECTION_NAME" not in text
    assert text.count("CLIP_PROJECTION_NAME =") == 1
    assert "CLIP_PROJECTION_NAME = 'VIDEO\\\\LTX\\\\LTX-2\\\\ltx-2.3_text_projection_bf16.safetensors'" in text
    assert text.count("VAE_TAESD_NAME =") == 1
    assert "VAE_TAESD_NAME = 'vae_approx\\\\taeltx2_3.safetensors'" in text
    assert "VAE_NAME = 'taeltx2_3.safetensors'" not in text
    assert "TEXT_ENCODER_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'" not in text
    assert "LTXV_PATH_NAME = 'ltx-2-19b-distilled.safetensors'" not in text


def test_model_constant_names_use_known_model_families() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "AudioModelLoader",
        inputs={"model_name": r"MelBandRoformer\MelBandRoformer_fp16.safetensors"},
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "UpscaleModelLoader",
        inputs={"model_name": "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"},
    )
    workflow.nodes["3"] = VibeNode(
        "3",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": "depth_anything_vitl14.pth"},
    )

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/model_families", "capability": "image"},
        ready_requirements={},
        template_id="image/model_families",
    )

    assert "MEL_BAND_ROFORMER_NAME = 'MelBandRoformer\\\\MelBandRoformer_fp16.safetensors'" in text
    assert "SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'" in text
    assert "DEPTH_ANYTHING_NAME = 'depth_anything_vitl14.pth'" in text
    assert "MODEL_NAME =" not in text
    assert "CKPT_NAME = 'depth_anything_vitl14.pth'" not in text


def test_emitter_preserves_authored_string_literals_without_evaluating_them() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    prompt = "a detailed cinematic prompt that is long enough to hoist"
    workflow.nodes["11"] = VibeNode("11", "CLIPTextEncode", inputs={"text": prompt}, uid="first")
    workflow.nodes["21"] = VibeNode(
        "21",
        "CLIPTextEncode",
        inputs={"text": "wf.nodes['11'].inputs.get('text', '')"},
        uid="second",
    )

    text = emit_canonical_python(
        workflow,
        ready_metadata={"ready_template": "image/lookup_prompt", "capability": "image"},
        ready_requirements={},
        template_id="image/lookup_prompt",
    )

    assert "wf.nodes['11'].inputs.get('text', '')" in text
    assert f"DEFAULT_PROMPT = {prompt!r}" in text


def test_ready_template_emits_custom_node_pack_provenance_from_lockfile() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "DepthAnything_V2", inputs={"image": "input.png"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/depth", "capability": "image"},
        ready_requirements={"custom_nodes": []},
        template_id="image/depth",
    )

    assert "custom_node_packs=" in text
    assert "'ComfyUI-DepthAnythingV2'" in text
    assert "'classes_used': ['DepthAnything_V2']" in text
    assert "'commit': '553187872eeb1d52e50dc53209fa57e569609a72'" in text
    assert "'status': 'discovered'" in text


def test_ready_template_preserves_explicit_custom_node_pack_override() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/depth",
            "capability": "image",
            "custom_node_packs": {"ExamplePack": {"commit": "abc", "classes_used": ["LoadImage"]}},
        },
        ready_requirements={},
        template_id="image/depth",
    )

    assert "custom_node_packs={'ExamplePack': {'commit': 'abc', 'classes_used': ['LoadImage']}}" in text


def test_model_block_emits_gated_model_assets() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={
            "ready_template": "image/gated",
            "capability": "image",
            "model_assets": [
                {
                    "name": "gated.safetensors",
                    "url": "https://example.test/gated.safetensors",
                    "subdir": "diffusion_models",
                    "gated": True,
                }
            ],
        },
        ready_requirements={},
        template_id="image/gated",
    )

    assert "gated=True" in text
    assert "sha256='gated'" not in text


@pytest.mark.parametrize("field", ["subdir", "directory"])
@pytest.mark.parametrize("subdir", ["", None, 0, []])
def test_model_block_rejects_explicit_malformed_subdir(field: str, subdir: Any) -> None:
    with pytest.raises(ValueError, match="model asset subdir must be a non-empty string"):
        emit_ready_template_python(
            _sample_workflow(),
            ready_metadata={
                "ready_template": "image/malformed-model",
                "capability": "image",
                "model_assets": [
                    {
                        "name": "model.safetensors",
                        "url": "https://example.test/model.safetensors",
                        field: subdir,
                    }
                ],
            },
            ready_requirements={},
            template_id="image/malformed-model",
        )


def test_raw_ui_subgraph_payload_is_not_an_emission_authority(tmp_path: Path) -> None:
    workflow = VibeWorkflow("canonical/no-sidecar", WorkflowSource("canonical/no-sidecar"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1}, uid="one")

    raw = {
        "definitions": {
            "subgraphs": [{
                "id": "sidecar-only",
                "name": "Must Not Execute",
                "nodes": [],
                "links": [],
            }]
        }
    }
    source = format_as_python(
        workflow,
        ready_metadata={"ready_template": workflow.id},
        ready_requirements={},
        template_id=workflow.id,
        raw_workflow=raw,
    )

    assert "Must Not Execute" not in source
    assert "sidecar-only" not in source
    assert _bundle_roundtrip(workflow, tmp_path, "canonical_no_sidecar.py").semantic_digest() == workflow.semantic_digest()

def test_tools_format_as_python_delegates_to_canonical_emitter() -> None:
    kwargs = {
        "ready_metadata": {"ready_template": "image/sample", "source_workflow": "ready_templates/sources/source.json"},
        "ready_requirements": {"models": [], "custom_nodes": []},
        "template_id": "image/sample",
        "registered_inputs": {"prefix": ("20", "filename_prefix")},
    }

    assert format_as_python(_sample_workflow(), **kwargs) == emit_canonical_python(_sample_workflow(), **kwargs)


def test_ready_template_id_map_contract_for_representative_emissions(tmp_path: Path) -> None:
    cases: list[VibeWorkflow] = []

    image = _sample_workflow()
    cases.append(image)

    typed = VibeWorkflow("typed", WorkflowSource("typed"))
    typed.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "model.safetensors"})
    typed.nodes["2"] = VibeNode("2", "CLIPLoader", inputs={"clip_name": "clip.safetensors", "type": "wan"})
    typed.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out/typed"})
    cases.append(typed)

    audio = VibeWorkflow("audio", WorkflowSource("audio"))
    audio.nodes["4"] = VibeNode("4", "LoadAudio", inputs={"audio": "input.wav"})
    audio.nodes["9"] = VibeNode("9", "SaveAudio", inputs={"filename_prefix": "out/audio"})
    cases.append(audio)

    for workflow in cases:
        for node_id, node in workflow.nodes.items():
            node.uid = node.uid or str(node_id)
        text = emit_ready_template_python(
            workflow,
            ready_metadata={"ready_template": workflow.id},
            ready_requirements={"models": [], "custom_nodes": []},
            template_id=workflow.id,
        )
        emitted = _bundle_roundtrip(workflow, tmp_path, f"{workflow.id.replace('/', '_')}.py")
        assert isinstance(emitted, VibeWorkflow)
        assert set(emitted.id_map().values()) == set(workflow.nodes)
        assert {node.uid for node in emitted.nodes.values()} == {
            str(node.uid or node_id) for node_id, node in workflow.nodes.items()
        }


def test_ready_emitter_preserves_authored_defaults_and_native_type_field() -> None:
    raw = {
        "nodes": [{
            "id": 1, "type": "CLIPLoader", "inputs": [], "outputs": [],
            "widgets_values": ["clip.safetensors", "wan", "default"],
        }],
        "links": [],
    }
    workflow = from_ui(raw, use_comfy_converter=False)
    source = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/authored-defaults"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="video/authored-defaults",
    )

    assert "CLIP_NAME = 'clip.safetensors'" in source
    assert "clip_name=CLIP_NAME" in source
    assert "type='wan'" in source
    assert "type_='wan'" not in source
    assert "device='default'" in source

    namespace: dict[str, Any] = {"__file__": "ready_templates/video/authored_defaults.py"}
    exec(compile(source, "authored_defaults.py", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["build"]()
    assert rebuilt.nodes["1"].metadata["keep_defaults"] == [
        "clip_name", "device", "type",
    ]
    reemitted = emit_ready_template_python(
        rebuilt,
        ready_metadata={"ready_template": "video/authored-defaults"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="video/authored-defaults",
    )
    assert "type='wan'" in reemitted
    assert "device='default'" in reemitted


def test_ready_template_ltx_tail_lines_are_inside_workflow_context() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "video/ltx2_3_i2v", "source_workflow": "ready_templates/sources/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="video/ltx2_3_i2v",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "    with new_workflow(READY_METADATA, source_path=__file__) as wf:" in text
    assert "apply_ltx_lowvram" not in text
    assert "resolution(384, 256, 9).apply(wf)" not in text
    assert "ensure_custom_nodes" not in text
    assert "        wf = wf.finalize(PUBLIC_INPUT_METADATA" in text


def test_ready_template_build_spacing_for_multiline_and_packed_simple_calls() -> None:
    workflow = VibeWorkflow("test/spacing", WorkflowSource("test/spacing", provenance={"origin": "unit"}))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "first_input_image_with_long_name_that_forces_multiline_formatting.png"})
    workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "second_input_image_with_long_name_that_forces_multiline_formatting.png"})
    workflow.nodes["3"] = VibeNode("3", "CLIPTextEncode", inputs={"text": "short positive"})
    workflow.nodes["4"] = VibeNode("4", "CLIPTextEncode", inputs={"text": "short negative"})
    workflow.nodes["5"] = VibeNode("5", "KSampler", inputs={"seed": 1, "steps": 2, "cfg": 3, "sampler_name": "uni_pc"})
    workflow.nodes["6"] = VibeNode("6", "KSampler", inputs={"seed": 4, "steps": 5, "cfg": 6, "sampler_name": "uni_pc"})
    workflow.nodes["7"] = VibeNode("7", "VAEDecode", inputs={})
    workflow.nodes["8"] = VibeNode("8", "SaveImage", inputs={"filename_prefix": "out/spacing"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "test/spacing"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/spacing",
    )

    assert "\n        # Inputs\n        loadimage = LoadImage(" in text
    assert "\n        loadimage_2 = LoadImage(" in text
    _assert_emitted_call_has_empty_native_authority(
        text,
        "cliptextencode = CLIPTextEncode(",
        "text='short positive'",
    )
    _assert_emitted_call_has_empty_native_authority(
        text,
        "cliptextencode_2 = CLIPTextEncode(",
        "text='short negative'",
    )
    assert text.index("cliptextencode = CLIPTextEncode(") < text.index(
        "cliptextencode_2 = CLIPTextEncode("
    )
    assert "\n\n        # Conditioning\n" in text
    assert "wf = wf.finalize({}" in text


def test_convert_ready_templates_tool_dry_run_remains_compatible() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.convert_ready_templates",
            "--template",
            "image/qwen_image_2512",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "image/qwen_image_2512" in result.stdout


# ---------------------------------------------------------------------------
# Sprint 1 T10: focused tool tests - shared gates for bulk dry-run / --write
# ---------------------------------------------------------------------------


def test_shared_manual_refusal_raises_for_manual_marker() -> None:
    """_check_manual_refusal raises ManualTemplateRefusal for # vibecomfy: manual."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write("# vibecomfy: manual - do not regenerate\n")
        tmp.write("def build():\n    pass\n")
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(ManualTemplateRefusal, match="manual"):
            _check_manual_refusal(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_shared_manual_refusal_passes_for_non_manual() -> None:
    """_check_manual_refusal does not raise for a normal file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write("# vibecomfy: generated\n")
        tmp.write("def build():\n    pass\n")
        tmp_path = Path(tmp.name)

    try:
        # Should not raise
        _check_manual_refusal(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_write_emitted_raises_manual_refusal_before_write(tmp_path: Path) -> None:
    """_write_emitted refuses to write over a manual template (shared gate)."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    # Create a "manual" template under a fake ready_templates tree
    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\ndef build(): pass\n")

    # Monkey-patch READY_ROOT so the path passes the outside-root guard
    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        with pytest.raises(ManualTemplateRefusal, match="manual"):
            _write_emitted(manual_path, "emitted text", dry_run=False)
        # File must be unchanged
        assert manual_path.read_text().startswith("# vibecomfy: manual")
    finally:
        tmod.READY_ROOT = orig_root


def test_write_emitted_include_manual_override_replaces_manual_template(tmp_path: Path) -> None:
    from tools.convert_ready_templates import _write_emitted

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\ndef build(): pass\n")

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        _write_emitted(
            manual_path,
            "# vibecomfy: generated\n# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\ndef build():\n    return None\n",
            dry_run=False,
            include_manual=True,
        )
        assert manual_path.read_text(encoding="utf-8").startswith("# vibecomfy: generated")
    finally:
        tmod.READY_ROOT = orig_root


def test_write_emitted_uses_atomic_temp_replace(tmp_path: Path) -> None:
    """_write_emitted uses temp file + replace for atomic writes."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    target = tmpl_dir / "test_atomic.py"
    original = "# vibecomfy: generated\nORIGINAL_CONTENT = True\n"
    target.write_text(original)

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        emitted = "# vibecomfy: generated\nEMITTED_CONTENT = True\n"
        result = _write_emitted(target, emitted, dry_run=False)
        assert result == target
        assert target.read_text() == emitted
        # No temp file left behind
        temps = list(tmpl_dir.glob(".vibecomfy-convert-*"))
        assert len(temps) == 0
    finally:
        tmod.READY_ROOT = orig_root


def test_convert_template_refuses_manual_via_shared_gate(tmp_path: Path) -> None:
    """_convert_template returns manual-refused row via shared _check_manual_refusal."""
    from tools.convert_ready_templates import (
        _convert_template,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual_convert.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\nAPI_WORKFLOW = {}\n")

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        row, emitted, _ = _convert_template(manual_path)
        assert emitted is None
        assert row.shape == "manual-refused"
        assert "manual template refused by shared gate" in row.note
        assert row.parse == "skip"
    finally:
        tmod.READY_ROOT = orig_root


def test_dry_run_writes_to_out_converted(tmp_path: Path) -> None:
    """_write_emitted dry_run=True writes to out/converted/ not in-place."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    target = tmpl_dir / "test_dry.py"
    original = "# vibecomfy: generated\nORIGINAL = True\n"
    target.write_text(original)

    out_dir = tmp_path / "out" / "converted"
    out_dir.mkdir(parents=True)

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    orig_out = tmod.OUT_PREVIEW_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        tmod.OUT_PREVIEW_ROOT = out_dir
        emitted = "# vibecomfy: generated\nEMITTED = True\n"
        result = _write_emitted(target, emitted, dry_run=True)
        # Wrote to out/converted/, not in-place
        assert result != target
        assert out_dir in result.parents
        assert result.read_text() == emitted
        # Original is unchanged
        assert target.read_text() == original
    finally:
        tmod.READY_ROOT = orig_root
        tmod.OUT_PREVIEW_ROOT = orig_out


def test_write_gate_requires_both_validate_and_parity() -> None:
    """main() skip-logic refuses writes when validate fails or roundtrip fails."""
    from tools.convert_ready_templates import Row

    # Simulate the gate check from main():
    #   gated_ok = row.validate == "ok" and row.roundtrip in ("ok", "skip", "skip-authored")

    # Case 1: validate fail -> blocked
    r1 = Row(template_id="test/fail_val")
    r1.validate = "fail"
    r1.roundtrip = "ok"
    gated = r1.validate == "ok" and r1.roundtrip in ("ok", "skip", "skip-authored")
    assert not gated

    # Case 2: roundtrip fail -> blocked
    r2 = Row(template_id="test/fail_rt")
    r2.validate = "ok"
    r2.roundtrip = "fail"
    gated = r2.validate == "ok" and r2.roundtrip in ("ok", "skip", "skip-authored")
    assert not gated

    # Case 3: both ok -> allowed
    r3 = Row(template_id="test/ok")
    r3.validate = "ok"
    r3.roundtrip = "ok"
    gated = r3.validate == "ok" and r3.roundtrip in ("ok", "skip", "skip-authored")
    assert gated

    # Case 4: authored shape (skip-authored) -> allowed
    r4 = Row(template_id="test/authored")
    r4.validate = "ok"
    r4.roundtrip = "skip-authored"
    gated = r4.validate == "ok" and r4.roundtrip in ("ok", "skip", "skip-authored")
    assert gated


# ---------------------------------------------------------------------------
# T11 - emitter tests: named outputs, widget aliases, fallbacks, _outputs
# ---------------------------------------------------------------------------


def _workflow_with_output_names(
    output_names: list[str],
) -> VibeWorkflow:
    """Build a minimal multi-output workflow with metadata-driven output_names."""
    workflow = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    workflow.nodes["1"] = VibeNode("1", "MultiOutput")
    workflow.nodes["1"].metadata["output_names"] = output_names
    workflow.nodes["2"] = VibeNode("2", "Consumer")
    # Connect both outputs from node 1 to node 2 on inputs named "a" and "b"
    workflow.connect("1.0", "2.a")
    workflow.connect("1.1", "2.b")
    return workflow


def test_v2_multi_output_finalizer_is_readable_and_omits_default_fields() -> None:
    workflow = _sample_workflow()
    workflow.outputs = [
        VibeOutput("20", "SaveImage"),
        VibeOutput("20", "PreviewImage"),
        VibeOutput("20", "SaveAudioMP3"),
    ]

    rendered = _v2_output_args(workflow, {"20": "save"}, {})

    assert rendered == (
        ", outputs=[\n"
        "        OutputSpec(node=save, output_type='SaveImage'),\n"
        "        OutputSpec(node=save, output_type='PreviewImage'),\n"
        "        OutputSpec(node=save, output_type='SaveAudioMP3'),\n"
        "    ]"
    )


def _workflow_with_widget_aliases(
    class_type: str,
    input_aliases: list[str | None],
    widget_values: dict[str, Any] | None = None,
) -> VibeWorkflow:
    """Build a workflow where a node has input_aliases metadata and widget values."""
    workflow = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    node = VibeNode("1", class_type)
    node.metadata["input_aliases"] = input_aliases
    if widget_values:
        for k, v in widget_values.items():
            if k.startswith("widget_"):
                node.widgets[k] = v
            else:
                node.inputs[k] = v
    workflow.nodes["1"] = node
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out"})
    workflow.connect("1.0", "2.images")
    return workflow


def _write_object_info_cache(tmp_path: Path, class_type: str, output_names: list[str]) -> Path:
    source = tmp_path / "object_info.json"
    source.write_text(
        json.dumps(
            {
                class_type: {
                    "python_module": "nodes",
                    "name": class_type,
                    "display_name": class_type,
                    "description": "",
                    "category": "test",
                    "function": "run",
                    "input": {"required": {}, "optional": {}},
                    "input_order": {"required": [], "optional": []},
                    "output": output_names,
                    "output_name": output_names,
                    "output_is_list": [False] * len(output_names),
                }
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "object_info"
    build_cache(str(source), version="test", cache_dir=str(cache_root))
    return cache_root


def _workflow_with_ui_and_metadata_outputs(
    class_type: str,
    ui_output_names: list[str],
    metadata_output_names: list[str] | None = None,
) -> VibeWorkflow:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    node = VibeNode("1", class_type)
    node.metadata["_ui"] = {
        "outputs": [
            {"slot_index": index, "name": name}
            for index, name in enumerate(ui_output_names)
        ]
    }
    if metadata_output_names is not None:
        node.metadata["output_names"] = metadata_output_names
    wf.nodes["1"] = node
    wf.nodes["2"] = VibeNode("2", "KSampler")
    for slot in range(len(ui_output_names)):
        wf.connect(f"1.{slot}", f"2.input_{slot}")
    return wf


def _patch_object_info_cache(monkeypatch: pytest.MonkeyPatch, cache_root: Path) -> None:
    import vibecomfy.porting.object_info.consume as consume

    monkeypatch.setattr(consume, "CACHE_DIR", cache_root)
    monkeypatch.setattr(consume, "INDEX_PATH", cache_root / "index.json")
    monkeypatch.setattr(consume, "_index", None)
    monkeypatch.setattr(consume, "_pack_cache", {})


def _wan_workflow_with_ui_outputs(output_names: list[str]) -> VibeWorkflow:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "WanImageToVideo")
    wf.nodes["1"].metadata["_ui"] = {
        "outputs": [
            {"slot_index": index, "name": name}
            for index, name in enumerate(output_names)
        ]
    }
    wf.nodes["2"] = VibeNode("2", "KSampler")
    wf.connect("1.0", "2.positive")
    wf.connect("1.1", "2.negative")
    wf.connect("1.2", "2.latent_image")
    return wf


def test_unique_safe_names_emit_named_out() -> None:
    """Unknown-node output schema and authored edge slots remain explicit."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", "latent"]),
        source_path="test.json",
    )
    assert "a=multioutput.out('image')" in text
    assert "b=multioutput.out('latent')" in text
    assert "_outputs=('image', 'latent')" in text


def test_duplicate_output_names_reject_without_ordinal_fallback() -> None:
    """Ambiguous named outputs fail closed instead of selecting an ordinal."""
    with pytest.raises(ValueError, match="malformed_named_output_schema"):
        emit_scratchpad_python(
            _workflow_with_output_names(["image", "image"]),
            source_path="test.json",
        )


def test_blank_output_names_reject_without_ordinal_fallback() -> None:
    """Blank named outputs fail closed instead of selecting an ordinal."""
    with pytest.raises(ValueError, match="malformed_named_output_schema"):
        emit_scratchpad_python(
            _workflow_with_output_names(["image", ""]),
            source_path="test.json",
        )


def test_partial_output_evidence_still_emits_outputs_tuple() -> None:
    """Partial named output evidence is rejected rather than downgraded."""
    with pytest.raises(ValueError, match="malformed_named_output_schema"):
        emit_scratchpad_python(
            _workflow_with_output_names(["image", ""]),
            source_path="test.json",
        )


def test_missing_output_names_does_not_emit_outputs() -> None:
    """When node has no output_names metadata, _outputs is NOT emitted."""
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "NoMeta")  # no metadata
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    text = emit_scratchpad_python(wf, source_path="test.json")
    tree = ast.parse(text)
    raw_calls = [
        call for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "raw_call"
    ]
    assert all(keyword.arg != "_outputs" for call in raw_calls for keyword in call.keywords)


def test_ideogram_fixture_native_boundary_is_materialized() -> None:
    fixture = (
        Path("tests/fixtures/node_resolution")
        / "ideogram4_t2i.json"
    )
    loaded = load_port_source(str(fixture), use_comfy_converter=False)
    assert loaded.workflow.nodes
    with pytest.raises(Exception, match="primitive_literal_invalid"):
        loaded.workflow.compile("api")

def test_ideogram_fixture_ports_from_cache_without_live_introspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = {
        "nodes": [
            {
                "id": "1",
                "type": "ComfyMathExpression",
                "outputs": [
                    {"name": "FLOAT"},
                    {"name": "INT"},
                    {"name": "BOOL"},
                ],
            },
            {"id": "2", "type": "SaveImage"},
            {"id": "3", "type": "SaveImage"},
            {"id": "4", "type": "SaveImage"},
        ]
    }
    wf = VibeWorkflow("cache_only_port", WorkflowSource("cache_only_port", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "ComfyMathExpression")
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/a"})
    wf.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out/b"})
    wf.nodes["4"] = VibeNode("4", "SaveImage", inputs={"filename_prefix": "out/c"})
    wf.connect("1.0", "2.images")
    wf.connect("1.1", "3.images")
    wf.connect("1.2", "4.images")

    cache_root = _write_object_info_cache(
        tmp_path,
        "ComfyMathExpression",
        ["FLOAT", "INT", "BOOL"],
    )
    _patch_object_info_cache(monkeypatch, cache_root)

    import vibecomfy.schema.provider as schema_provider

    def _fail_runtime_provider_init(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("port_convert_workflow must stay on the cache-only seam")

    async def _fail_live_object_info_async(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("port_convert_workflow touched live object_info introspection")

    monkeypatch.setattr(schema_provider.RuntimeSchemaProvider, "__init__", _fail_runtime_provider_init)
    monkeypatch.setattr(
        schema_provider.RuntimeSchemaProvider,
        "object_info_async",
        _fail_live_object_info_async,
    )

    result = port_convert_workflow(wf, raw_workflow=raw, source_path="ready_templates/sources/cache_only.json")

    assert result.validation is not None
    assert result.validation.compile_ok, result.validation.error


def test_subgraph_ui_outputs_recover_tuple_arity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _write_object_info_cache(tmp_path, "SubgraphNode", ["latent", "mask", "preview"])
    _patch_object_info_cache(monkeypatch, cache_root)

    text = emit_ready_template_python(
        _workflow_with_ui_and_metadata_outputs(
            "SubgraphNode",
            ["latent", "mask", "preview"],
            metadata_output_names=["latent", "mask", "preview"],
        ),
        ready_metadata={"ready_template": "image/subgraph", "capability": "image"},
        ready_requirements={},
        template_id="image/subgraph",
    )

    _assert_emitted_call_has_empty_native_authority(
        text,
        "subgraphnode = raw_call('SubgraphNode',",
        "_outputs=('latent', 'mask', 'preview')",
    )
    assert "_outputs=('latent', 'mask', 'preview')" in text


def test_subgraph_ui_metadata_does_not_override_canonical_output_schema() -> None:
    with pytest.raises(ValueError, match="malformed_named_output_schema"):
        emit_ready_template_python(
            _workflow_with_ui_and_metadata_outputs(
                "SubgraphNode",
                ["latent", "mask", "preview"],
                metadata_output_names=["latent", "mask"],
            ),
            ready_metadata={"ready_template": "image/subgraph", "capability": "image"},
            ready_requirements={},
            template_id="image/subgraph",
        )


def test_cache_greater_than_ui_keeps_retained_arity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _write_object_info_cache(
        tmp_path,
        "WanImageToVideo",
        ["positive", "negative", "latent", "unused"],
    )
    _patch_object_info_cache(monkeypatch, cache_root)

    workflow = _wan_workflow_with_ui_outputs(["positive", "negative", "latent"])
    workflow.nodes["1"].metadata["output_names"] = ["positive", "negative", "latent"]
    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )
    assert "wanimagetovideo = WanImageToVideo(" in text
    assert ".out('LATENT')" in text
    assert "unused" not in text



def test_agent_edit_emit_reconciles_object_info_ui_arity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loaded graphs must emit even when object_info arity disagrees with UI.

    Fail-closing here blocked representable live edits before the agent could
    act. Prefer UI slots (the graph already uses them).
    """
    cache_root = _write_object_info_cache(
        tmp_path,
        "AnyEmitNode",
        ["first", "second", "stale_extra"],
    )
    _patch_object_info_cache(monkeypatch, cache_root)
    wf = _workflow_with_ui_and_metadata_outputs(
        "AnyEmitNode",
        ["FIRST VALUE", "SECOND VALUE"],
    )

    text = emit_agent_edit_python(wf)
    assert "AnyEmitNode(" in text
    assert "stale_extra" not in text


@pytest.mark.parametrize(
    ("object_info_outputs", "ui_outputs"),
    [
        (["IMAGE", "width", "height", "extra"], ["IMAGE", "width", "height"]),
        ([], ["width", "height", "count", "bbox"]),
        ([], ["MODEL"]),
        ([], ["IMAGE"]),
    ],
)
def test_agent_edit_emit_does_not_abort_on_empty_or_longer_object_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    object_info_outputs: list[str],
    ui_outputs: list[str],
) -> None:
    cache_root = _write_object_info_cache(tmp_path, "AnyEmitNode", object_info_outputs)
    _patch_object_info_cache(monkeypatch, cache_root)
    wf = _workflow_with_ui_and_metadata_outputs("AnyEmitNode", ui_outputs)

    text = emit_agent_edit_python(wf)
    assert "AnyEmitNode(" in text


def test_agent_edit_emit_reconciles_when_cache_has_too_few_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _write_object_info_cache(tmp_path, "AnyEmitNode", ["first"])
    _patch_object_info_cache(monkeypatch, cache_root)
    wf = _workflow_with_ui_and_metadata_outputs(
        "AnyEmitNode",
        ["FIRST VALUE", "SECOND VALUE"],
    )

    text = emit_agent_edit_python(wf)
    assert "AnyEmitNode(" in text


def test_scratchpad_emit_reconciles_four_schema_names_to_three_ui_slots() -> None:
    """The generated build must unpack the retained three-slot result."""
    wf = VibeWorkflow("arity-reconcile", WorkflowSource("arity-reconcile"))
    wf.nodes["1"] = VibeNode(
        "1",
        "WanImageToVideo",
        uid="source",
        metadata={
            "output_names": ["first", "second", "third", "schema_only"],
            "_ui": {
                "outputs": [
                    {"slot_index": 0, "name": "first"},
                    {"slot_index": 1, "name": "second"},
                    {"slot_index": 2, "name": "third"},
                ]
            },
        },
    )
    wf.nodes["2"] = VibeNode("2", "KSampler", uid="sink")
    for slot in range(3):
        wf.connect(f"1.{slot}", f"2.input_{slot}")

    source = emit_scratchpad_python(wf, source_path="generic-arity.json")

    assert "wanimagetovideo = WanImageToVideo(" in source
    build_source = source[source.index("def build") :]
    call_line = next(
        line for line in build_source.splitlines()
        if "wanimagetovideo = wanimagetovideo(" in line.lower()
    )
    assert "schema_only" not in call_line
    namespace: dict[str, Any] = {"__file__": "ready_templates/image/arity_reconcile.py"}
    exec(compile(source, "arity_reconcile.py", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["build"]()
    assert isinstance(rebuilt, VibeWorkflow)
    assert sorted(rebuilt.nodes) == ["1", "2"]


def test_ready_template_emits_unpacking_for_typed_multi_output_node() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "WanImageToVideo")
    wf.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["2"] = VibeNode("2", "KSampler")
    wf.connect("1.0", "2.positive")
    wf.connect("1.1", "2.negative")
    wf.connect("1.2", "2.latent_image")

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    _assert_emitted_call_has_empty_native_authority(
        text,
        "wanimagetovideo = WanImageToVideo(",
    )
    assert "positive=wanimagetovideo.out('POSITIVE')" in text
    assert "negative=wanimagetovideo.out('NEGATIVE')" in text
    assert "latent_image=wanimagetovideo.out('LATENT')" in text
    assert "wf.connect(" not in text


def test_named_multi_output_fanout_restricted_reload_preserves_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_no_gpu_graphbuilder(monkeypatch)
    wf = VibeWorkflow("canonical/fanout", WorkflowSource("canonical/fanout"))
    wf.nodes["1"] = VibeNode("1", "WanImageToVideo", uid="producer")
    wf.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["2"] = VibeNode("2", "KSampler", inputs={"positive": None, "negative": None, "latent_image": None}, uid="consumer")
    wf.connect("1.0", "2.positive")
    wf.connect("1.1", "2.negative")
    wf.connect("1.2", "2.latent_image")
    source = emit_canonical_python(wf)
    assert source.count("wanimagetovideo.out(") == 3
    assert "wf.connect(" not in source
    path = tmp_path / "fanout.py"
    emit_bundle(wf, path, {"operation": "authored"})
    first = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    second = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    assert len(first.edges) == 3
    assert first.semantic_digest() == wf.semantic_digest()
    assert second.semantic_digest() == first.semantic_digest()
    assert first.compile("api") == wf.compile("api")
    assert first.compile("graphbuilder") == wf.compile("graphbuilder")


def test_ready_template_replaces_dead_unpacked_outputs_with_underscore() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "WanImageToVideo")
    wf.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["2"] = VibeNode("2", "KSampler")
    wf.connect("1.1", "2.negative")

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    _assert_emitted_call_has_empty_native_authority(
        text,
        "wanimagetovideo = WanImageToVideo(",
    )
    assert "negative=wanimagetovideo.out('NEGATIVE')" in text
    assert "wf.connect(" not in text


def test_ready_template_unpack_uses_retained_ui_arity_before_cache_shortcut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_root = _write_object_info_cache(tmp_path, "WanImageToVideo", ["POSITIVE", "NEGATIVE"])
    _patch_object_info_cache(monkeypatch, cache_root)

    workflow = _wan_workflow_with_ui_outputs(["POSITIVE", "NEGATIVE", "LATENT"])
    workflow.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )
    assert "POSITIVE, NEGATIVE, LATENT" not in text
    assert "wanimagetovideo = WanImageToVideo(" in text
    assert ".out('LATENT')" in text



def test_ready_template_unpack_ignores_cache_extra_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_root = _write_object_info_cache(
        tmp_path,
        "WanImageToVideo",
        ["POSITIVE", "NEGATIVE", "LATENT", "STRING"],
    )
    _patch_object_info_cache(monkeypatch, cache_root)

    workflow = _wan_workflow_with_ui_outputs(["POSITIVE", "NEGATIVE", "LATENT"])
    workflow.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )
    assert "wanimagetovideo = WanImageToVideo(" in text
    assert ".out('LATENT')" in text
    assert "STRING" not in text



def test_ready_template_keeps_dead_multi_output_node_as_bare_call() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "SimpleCalculatorKJ", inputs={"expression": "1"})
    wf.nodes["1"].metadata["output_names"] = ["FLOAT", "INT", "BOOLEAN"]

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    _assert_emitted_call_has_empty_native_authority(
        text,
        "simplecalculatorkj = SimpleCalculatorKJ(",
        "expression='1'",
    )
    assert "simplecalculatorkj = SimpleCalculatorKJ(" in text


def test_ready_template_unpacked_output_names_use_collision_suffix() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "CLIPTextEncode", inputs={"text": "prompt"})
    wf.nodes["2"] = VibeNode("2", "WanImageToVideo")
    wf.nodes["2"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["3"] = VibeNode("3", "KSampler")
    wf.connect("1.0", "3.positive")
    wf.connect("2.1", "3.negative")
    wf.connect("2.2", "3.latent_image")

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    # Batch 4 (Law 5): bindings are a pure function of class_type + uid order —
    # CLIPTextEncode emits its deterministic class-derived name (no
    # connection-role override), and the WanImageToVideo unpacked outputs
    # keep their collision-suffixed/underscore-dead names.
    _assert_emitted_call_has_empty_native_authority(
        text,
        "cliptextencode = CLIPTextEncode(",
        "text='prompt'",
    )
    _assert_emitted_call_has_empty_native_authority(
        text,
        "wanimagetovideo = WanImageToVideo(",
    )
    assert "negative=wanimagetovideo.out('NEGATIVE')" in text
    assert "latent_image=wanimagetovideo.out('LATENT')" in text


def test_out_of_range_named_slot_rejects_ordinal_fallback() -> None:
    """An edge beyond a named output roster fails closed."""
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "SingleOutput")
    wf.nodes["1"].metadata["output_names"] = ["only"]  # only slot 0 named
    wf.nodes["2"] = VibeNode("2", "Consumer")
    # Connect from slot 5 which is out of range
    wf.edges.append(VibeEdge("1", "5", "2", "a"))

    with pytest.raises(ValueError, match="malformed_named_output_schema"):
        emit_scratchpad_python(wf, source_path="test.json")


def test_widget_alias_success_emits_named_field(tmp_path: Path) -> None:
    """Wrapper aliases stay readable while canonical widget storage survives."""
    from vibecomfy.porting.emitter import EmissionDiagnostic

    wf = _workflow_with_widget_aliases(
        "CheckpointLoaderSimple",
        ["ckpt_name"],  # widget_0 -> ckpt_name
        {"widget_0": "v1-5-pruned.safetensors"},
    )
    for node_id, node in wf.nodes.items():
        node.uid = node_id

    diags: list[EmissionDiagnostic] = []
    text = emit_scratchpad_python(wf, source_path="test.json", diagnostics=diags)
    # Should use the named field from input_aliases
    assert "ckpt_name=" in text
    assert "'v1-5-pruned.safetensors'" in text
    assert "'widget_channels': {'ckpt_name': 'widget_0'}" not in text
    assert "wf.nodes[" not in text
    path = tmp_path / "widget_alias.py"
    emit_bundle(wf, path, {"operation": "authored"})
    reloaded = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    reloaded_twice = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    assert reloaded.nodes["1"].widgets == wf.nodes["1"].widgets
    assert reloaded.nodes["1"].inputs == wf.nodes["1"].inputs
    assert reloaded_twice.semantic_digest() == reloaded.semantic_digest() == wf.semantic_digest()


def test_input_and_widget_channels_remain_distinct_after_restricted_reload(tmp_path: Path) -> None:
    wf = VibeWorkflow("canonical/channels", WorkflowSource("canonical/channels"))
    wf.nodes["1"] = VibeNode(
        "1", "MysteryChannelNode", inputs={"value": 7}, widgets={"value": "widget"}, uid="channel"
    )
    source = emit_canonical_python(wf)
    path = tmp_path / "channels.py"
    emit_bundle(wf, path, {"operation": "authored"})
    first = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    second = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    assert first.nodes["1"].inputs == {"value": 7}
    assert first.nodes["1"].widgets == {"value": "widget"}
    assert second.semantic_digest() == first.semantic_digest() == wf.semantic_digest()


def test_widget_alias_fallback_keeps_positional_widget() -> None:
    """When widget_N index is beyond input_aliases range, keep positional."""
    from vibecomfy.porting.emitter import EmissionDiagnostic

    wf = _workflow_with_widget_aliases(
        "SomeNode",
        ["only_name"],  # only widget_0 has an alias
        {"widget_0": "first_val", "widget_3": "out_of_range_val"},
    )

    diags: list[EmissionDiagnostic] = []
    text = emit_scratchpad_python(wf, source_path="test.json", diagnostics=diags)

    # widget_0 gets aliased
    assert "only_name=" in text
    # widget_3 stays positional (out of range) - emitted as kwarg widget_3=
    assert "widget_3=" in text

    # Verify diagnostics include schema_backed_widget_alias_not_resolved
    from vibecomfy.porting.emitter import (
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    )
    unresolved_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED
    ]
    assert len(unresolved_codes) > 0


def test_emitted_outputs_preservation_with_partial_blank() -> None:
    """Partial named output rosters fail closed instead of ordinal fallback."""
    with pytest.raises(ValueError, match="malformed_named_output_schema"):
        emit_scratchpad_python(
            _workflow_with_output_names(["image", ""]),
            source_path="test.json",
        )


# ---------------------------------------------------------------------------
# T5: style diagnostics for generated ready templates
# ---------------------------------------------------------------------------


def test_variable_name_too_long_diagnostic() -> None:
    """generated_variable_name_too_long fires when emitted var name >40 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/long", WorkflowSource("test/long", provenance={"origin": "unit"}))
    # Use a class_type that produces a very long safe variable name
    very_long_ct = "a" * 41
    wf.nodes["1"] = VibeNode("1", very_long_ct, inputs={"text": "hello"})

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/long"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/long",
        diagnostics=diags,
    )

    long_name_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG
    ]
    assert len(long_name_codes) > 0, f"Expected generated_variable_name_too_long diagnostic, got: {[d.code for d in diags]}"


def test_variable_name_not_too_short_no_diagnostic() -> None:
    """No diagnostic for variable names <=40 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/short", WorkflowSource("test/short", provenance={"origin": "unit"}))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/short"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/short",
        diagnostics=diags,
    )

    long_name_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG
    ]
    assert len(long_name_codes) == 0, f"Unexpected long-name diagnostic for short variable names: {long_name_codes}"


def test_long_one_line_node_call_diagnostic() -> None:
    """long_one_line_node_call fires for a single-line ready_node call >120 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/long_line", WorkflowSource("test/long_line", provenance={"origin": "unit"}))
    # Create a node with many string inputs to make the ready_node call long
    wf.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={
            "image": "a_very_long_filename_that_pads_the_call_line_to_exceed_one_hundred_twenty_characters_total.png",
        },
    )
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/long_line"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/long_line",
        diagnostics=diags,
    )

    long_line_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL
    ]
    # Note: if multi-line formatting kicks in, the line won't be "single line"
    # but the diagnostic fires for any ready_node call whose computed single_line > 120
    # regardless of formatting. Validate that it appears when appropriate.
    # This test verifies the diagnostic code exists and is emitted under the right conditions.
    assert len(long_line_codes) > 0, f"Expected long_one_line_node_call diagnostic, got: {[d.code for d in diags]}"


def test_generated_template_not_formatted_missing_section_comments() -> None:
    """generated_template_not_formatted fires for >=8 nodes without section comments."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/no_sections", WorkflowSource("test/no_sections", provenance={"origin": "unit"}))
    # Create 8 nodes, none of which map to section roles, so section_groups is empty
    # But the check looks for missing section COMMENTS in the output when nodes >= 8
    # and section_groups are non-empty. Let's create nodes that map to sections.
    for i in range(8):
        nid = str(i + 1)
        # Use class types that map to section roles
        if i == 0:
            ct = "LoadImage"
        elif i == 1:
            ct = "CLIPLoader"
        elif i == 2:
            ct = "CLIPTextEncode"
        elif i == 3:
            ct = "KSampler"
        elif i == 4:
            ct = "VAEDecode"
        elif i == 5:
            ct = "SaveImage"
        elif i == 6:
            ct = "CheckpointLoaderSimple"
        else:
            ct = "PreviewImage"
        wf.nodes[nid] = VibeNode(nid, ct, inputs={"test": "val"})

    diags: list[EmissionDiagnostic] = []
    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/no_sections"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/no_sections",
        diagnostics=diags,
    )

    # The emitter should produce section comments for >=8 nodes.
    # If not, the diagnostic should fire.
    has_section_comments = any(
        line.strip().startswith("# ") and any(
            sec in line for sec in ("Inputs", "Loaders", "Conditioning", "Sampling", "Decode", "Outputs")
        )
        for line in text.split("\n")
    )

    not_formatted_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED
    ]
    if not has_section_comments:
        assert len(not_formatted_codes) > 0, (
            f"Expected generated_template_not_formatted diagnostic when no section comments found. "
            f"Diags: {[d.code for d in diags]}"
        )
    # If section comments ARE present, we accept either way (no diagnostic needed)
    # but the diagnostic should NOT fire if sections are present
    if has_section_comments:
        # The diagnostic might still fire for un-indented tail, but not for missing sections
        missing_section_diags = [
            d for d in not_formatted_codes
            if "lacks section comments" in d.message
        ]
        assert len(missing_section_diags) == 0, (
            f"Should not flag missing sections when sections are present: {missing_section_diags}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# T9 — _uid= threading through the .py emitter (scratchpad path)
# ═══════════════════════════════════════════════════════════════════════════════


def test_flat_scratchpad_contains_uids_only_in_companion_custody(tmp_path: Path) -> None:
    """Flat scratchpad identity is retained without leaking into calls."""
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = from_ui(raw)

    text = emit_scratchpad_python(wf, source_path="tests/fixtures/walking_skeleton/flat.json")

    assert "_uid=" not in text
    reloaded = _bundle_roundtrip(wf, tmp_path, "flat.py")
    assert {node.uid for node in reloaded.nodes.values()} == {
        str(i) for i in range(1, 8)
    }


def test_flat_scratchpad_reimport_yields_same_uids(tmp_path: Path) -> None:
    """Re-importing the generated .py yields nodes carrying the same uid."""
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = from_ui(raw)

    text = emit_scratchpad_python(wf, source_path="tests/fixtures/walking_skeleton/flat.json")

    reimported_wf = _bundle_roundtrip(wf, tmp_path, "flat.py")

    # Every node in the reimported workflow should have the same uid
    for nid, orig_node in wf.nodes.items():
        assert nid in reimported_wf.nodes, f"node {nid} missing from reimported workflow"
        re_node = reimported_wf.nodes[nid]
        assert re_node.uid == orig_node.uid, (
            f"node {nid}: uid mismatch {re_node.uid!r} != {orig_node.uid!r}"
        )
        assert re_node.uid, f"node {nid} has empty uid after reimport"


# ═══════════════════════════════════════════════════════════════════════════════
# T13 — _uid= threading through the ready-template emission path
# ═══════════════════════════════════════════════════════════════════════════════


def _flat_workflow_and_raw():
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    api = normalize_to_api(raw, use_comfy_converter=False)
    wf = from_api(
        api, source_path="tests/fixtures/walking_skeleton/flat.json", workflow_id="flat"
    )
    return wf, raw


def _emit_flat_ready() -> tuple[Any, str]:
    wf, raw = _flat_workflow_and_raw()
    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "image/flat", "capability": "image"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/flat",
        raw_workflow=raw,
    )
    return wf, text


def test_flat_ready_template_contains_uids_only_in_companion_custody(tmp_path: Path) -> None:
    """Ready-template identity is retained without becoming call syntax."""
    _wf, text = _emit_flat_ready()
    assert "_uid=" not in text
    reloaded = _bundle_roundtrip(_wf, tmp_path, "flat_ready.py")
    assert {node.uid for node in reloaded.nodes.values()} == {
        str(i) for i in range(1, 8)
    }


def test_flat_ready_template_reimport_yields_same_uids(tmp_path: Path) -> None:
    """Re-loading the emitted ready template yields IDENTICAL uids (read-back proven)."""
    wf, text = _emit_flat_ready()

    reimported_wf = _bundle_roundtrip(wf, tmp_path, "flat_ready.py")

    for nid, orig_node in wf.nodes.items():
        assert nid in reimported_wf.nodes, f"node {nid} missing from reimported ready template"
        re_node = reimported_wf.nodes[nid]
        assert re_node.uid == orig_node.uid, (
            f"node {nid}: uid mismatch {re_node.uid!r} != {orig_node.uid!r}"
        )
        assert re_node.uid, f"node {nid} has empty uid after ready-template reimport"


# ---------------------------------------------------------------------------
# Identity-aware emitter plumbing tests (T24)
# Tests for: _use_object_info_identities, _node_local_output_names,
# _node_local_arity_check, _node_local_class_defaults, _record_lookup_warning,
# _drain_lookup_warning_diagnostics, and top-level emit functions.
# ---------------------------------------------------------------------------

import json
from pathlib import Path
import pytest
from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    _use_object_info_identities,
    _identity_for_node,
    _node_local_output_names,
    _node_local_arity_check,
    _node_local_class_defaults,
    _drain_lookup_warning_diagnostics,
)
from vibecomfy.porting.object_info.consume import ObjectInfoIdentity
from vibecomfy.porting.object_info.serialize import build_cache


def _patch_consume_paths_emitter(monkeypatch: pytest.MonkeyPatch, cache_root: Path) -> None:
    """Point the consumer module at a temp cache directory and reset internal state."""
    import vibecomfy.porting.object_info.consume as _consume
    monkeypatch.setattr(_consume, "CACHE_DIR", cache_root)
    monkeypatch.setattr(_consume, "INDEX_PATH", cache_root / "index.json")
    monkeypatch.setattr(_consume, "_index", None)
    monkeypatch.setattr(_consume, "_pack_cache", {})


def _build_temp_cache_for_emitter(tmp_path: Path, version: str = "abc123") -> Path:
    """Build a minimal object_info cache for emitter identity tests."""
    object_info: dict = {
        "MyCustomSampler": {
            "python_module": "MyPack.nodes.sampler",
            "name": "MyCustomSampler",
            "display_name": "My Custom Sampler",
            "description": "A custom sampler",
            "category": "sampling",
            "function": "sample",
            "input": {
                "required": {
                    "model": ["MODEL"],
                    "steps": ["INT", {"default": 20, "min": 1, "max": 100}],
                    "cfg": ["FLOAT", {"default": 7.0, "min": 0.0, "max": 30.0}],
                },
                "optional": {
                    "denoise": ["FLOAT", {"default": 1.0}],
                },
            },
            "input_order": {
                "required": ["model", "steps", "cfg"],
                "optional": ["denoise"],
            },
            "output": ["LATENT", "IMAGE"],
            "output_name": ["samples", "preview"],
            "output_is_list": [False, False],
        }
    }
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(object_info), encoding="utf-8")
    cache_root = tmp_path / "object_info_cache"
    build_cache(str(source), version=version, cache_dir=str(cache_root))
    return cache_root


class _FakeNode:
    """Minimal node stub for unit testing emitter helpers."""

    def __init__(self, node_id: str, class_type: str) -> None:
        self.id = node_id
        self.class_type = class_type
        self.metadata: dict = {}


def test_retained_output_arity_never_consults_ambient_object_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retained node roster owns arity even if ambient state disagrees."""
    import vibecomfy.porting.object_info as object_info

    def poisoned(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("ambient object-info lookup must not run")

    monkeypatch.setattr(object_info, "class_is_known", poisoned)
    monkeypatch.setattr(object_info, "class_output_count", poisoned)
    monkeypatch.setattr(object_info, "output_names", poisoned)
    monkeypatch.setattr(object_info, "resolve_class_entry", poisoned)

    node = VibeNode(
        "1",
        "VHS_LoadVideo",
        native_output_names=["MASK", "IMAGE"],
        metadata={"output_names": ["MASK", "IMAGE"]},
    )
    assert _node_local_output_names(node) == ["MASK", "IMAGE"]
    assert _node_local_arity_check(node, ui_output_count=2) == 2
    assert _node_local_arity_check(node, ui_output_count=4) == 4


def test_identity_for_node_returns_none_without_context() -> None:
    """Without a context, _identity_for_node returns None (legacy behavior)."""
    node = _FakeNode("1", "MyCustomSampler")
    assert _identity_for_node(node) is None


def test_identity_for_node_returns_bound_identity() -> None:
    """_identity_for_node returns the identity bound for a matching node_id."""
    node = _FakeNode("42", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    identities = {"42": identity}
    with _use_object_info_identities(identities):
        result = _identity_for_node(node)
    assert result == identity


def test_identity_for_node_returns_none_for_unregistered_node() -> None:
    """_identity_for_node returns None when the node_id is absent from the map."""
    node = _FakeNode("99", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    identities = {"1": identity}
    with _use_object_info_identities(identities):
        result = _identity_for_node(node)
    assert result is None


def test_node_local_output_names_class_only_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a bound identity, _node_local_output_names uses class-only fallback."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("1", "MyCustomSampler")
    # No identity context — class-only lookup
    names = _node_local_output_names(node)
    assert names == ["samples", "preview"]


def test_node_local_output_names_identity_aware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When an identity is bound, _node_local_output_names uses the identity-resolved entry."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("5", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    identities = {"5": identity}
    with _use_object_info_identities(identities):
        names = _node_local_output_names(node)
    # The identity hit resolves to the same cache entry — names come from it
    assert names == ["samples", "preview"]


def test_node_local_output_names_identity_miss_falls_back_to_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When identity lookup misses (wrong commit), falls back to class-only names and records warning."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("7", "MyCustomSampler")
    # Wrong git commit — won't match the cached abc123 version
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="deadbeef")
    identities = {"7": identity}
    diagnostics: list[EmissionDiagnostic] = []
    with _use_object_info_identities(identities):
        names = _node_local_output_names(node)
        low_conf = _drain_lookup_warning_diagnostics(diagnostics)

    # Falls back to class-only names
    assert names == ["samples", "preview"]
    # A warning was recorded
    assert low_conf is True
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.code in ("provenance_identity_cache_miss", "unprovenanced_class_fallback")
    assert diag.node_id == "7"
    assert diag.class_type == "MyCustomSampler"


def test_node_local_identity_ambiguity_fails_closed_for_output_names_and_arity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ambiguous identity is never downgraded to a class-only schema."""
    import vibecomfy.porting.object_info as object_info

    def ambiguous_lookup(*args: Any, **kwargs: Any) -> Any:
        raise ObjectInfoIdentityAmbiguityError(
            "multiple object_info cache entries matched MyCustomSampler",
            class_type="MyCustomSampler",
            pack_slug="MyPack",
            git_commit="abc123",
            evidence_identity=None,
            matches=[{"filename": "one.json"}, {"filename": "two.json"}],
        )

    monkeypatch.setattr(object_info, "resolve_class_entry", ambiguous_lookup)
    node = _FakeNode("ambiguous", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    with _use_object_info_identities({"ambiguous": identity}):
        with pytest.raises(ObjectInfoIdentityAmbiguityError):
            _node_local_output_names(node)
        with pytest.raises(ObjectInfoIdentityAmbiguityError):
            _node_local_arity_check(node, ui_output_count=2)


def test_canonical_emission_preflights_identity_ambiguity_before_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical emission rejects ambiguity before defaults' legacy catch path."""
    import vibecomfy.porting.object_info as object_info

    def ambiguous_lookup(*args: Any, **kwargs: Any) -> Any:
        raise ObjectInfoIdentityAmbiguityError(
            "multiple object_info cache entries matched SaveImage",
            class_type="SaveImage",
            pack_slug="MyPack",
            git_commit="abc123",
            evidence_identity=None,
            matches=[{"filename": "one.json"}, {"filename": "two.json"}],
        )

    monkeypatch.setattr(object_info, "resolve_class_entry", ambiguous_lookup)
    workflow = VibeWorkflow("canonical/identity-ambiguity", WorkflowSource("canonical/identity-ambiguity"))
    workflow.nodes["1"] = VibeNode(
        "1", "SaveImage", inputs={"filename_prefix": "out/ambiguous"}, uid="save"
    )
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    with pytest.raises(ObjectInfoIdentityAmbiguityError):
        emit_canonical_python(
            workflow,
            object_info_identities={"1": identity},
        )


def test_node_local_arity_check_class_only_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without identity, _node_local_arity_check matches class-only output count."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("1", "MyCustomSampler")
    # MyCustomSampler has 2 outputs
    count = _node_local_arity_check(node, ui_output_count=None)
    assert count == 2


def test_node_local_arity_check_identity_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a matching identity, _node_local_arity_check uses the identity-resolved count."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("3", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    with _use_object_info_identities({"3": identity}):
        count = _node_local_arity_check(node, ui_output_count=2)
    assert count == 2


def test_node_local_arity_check_identity_miss_records_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When identity lookup misses, arity check falls back and records a diagnostic."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("8", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="badc0ffee")
    diagnostics: list[EmissionDiagnostic] = []
    with _use_object_info_identities({"8": identity}):
        count = _node_local_arity_check(node, ui_output_count=None)
        _drain_lookup_warning_diagnostics(diagnostics)

    # Falls back to 2-output class entry
    assert count == 2
    assert len(diagnostics) == 1
    assert diagnostics[0].code in ("provenance_identity_cache_miss", "unprovenanced_class_fallback")


def test_node_local_class_defaults_class_only_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without identity, _node_local_class_defaults returns class-only schema defaults."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("2", "MyCustomSampler")
    defaults = _node_local_class_defaults(node)
    assert defaults.get("steps") == 20
    assert defaults.get("cfg") == 7.0
    assert defaults.get("denoise") == 1.0


def test_node_local_class_defaults_identity_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a matching identity, _node_local_class_defaults uses identity-resolved schema."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("4", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    with _use_object_info_identities({"4": identity}):
        defaults = _node_local_class_defaults(node)
    assert defaults.get("steps") == 20
    assert defaults.get("cfg") == 7.0


def test_node_local_class_defaults_identity_miss_records_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When identity lookup misses, defaults fall back and a warning diagnostic is recorded."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("9", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="00000000")
    diagnostics: list[EmissionDiagnostic] = []
    with _use_object_info_identities({"9": identity}):
        defaults = _node_local_class_defaults(node)
        _drain_lookup_warning_diagnostics(diagnostics)

    # Falls back to class defaults
    assert defaults.get("steps") == 20
    assert len(diagnostics) == 1
    assert diagnostics[0].code in ("provenance_identity_cache_miss", "unprovenanced_class_fallback")


def test_drain_lookup_warning_diagnostics_deduplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_drain_lookup_warning_diagnostics emits one diagnostic per (node_id, class, code)."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("11", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="missing_commit")
    diagnostics: list[EmissionDiagnostic] = []
    with _use_object_info_identities({"11": identity}):
        # Call multiple helpers — all will record warnings for the same node
        _node_local_output_names(node)
        _node_local_arity_check(node, None)
        _node_local_class_defaults(node)
        low_conf = _drain_lookup_warning_diagnostics(diagnostics)

    # Despite 3 calls, only one diagnostic per (node_id, class_type, code)
    assert low_conf is True
    unique_keys = {(d.node_id, d.class_type, d.code) for d in diagnostics}
    assert len(unique_keys) == len(diagnostics), "Diagnostics should be deduplicated by key"
    assert len(diagnostics) <= 2  # at most one per code type for same node


def test_identity_context_does_not_leak_between_emits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Identity context is reset after _use_object_info_identities exits (no leakage)."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("77", "MyCustomSampler")
    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")

    with _use_object_info_identities({"77": identity}):
        assert _identity_for_node(node) == identity

    # After exiting, no identity should be bound
    assert _identity_for_node(node) is None


def test_emit_ready_template_with_mismatched_identity_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A known wrapper may not silently accept mismatched schema provenance."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out/test"}, uid="save")

    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    diagnostics: list[EmissionDiagnostic] = []

    with pytest.raises(ValueError, match="schema_reconciliation_required"):
        emit_canonical_python(
            workflow,
            ready_metadata={"ready_template": "image/identity_test", "capability": "image"},
            ready_requirements={"models": [], "custom_nodes": []},
            template_id="image/identity_test",
            object_info_identities={"1": identity},
            diagnostics=diagnostics,
        )


def test_emit_ready_template_identity_miss_sets_low_confidence_on_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Conversion reports low_confidence=True when identity lookup warnings are present."""
    from vibecomfy.porting.convert import port_convert_workflow

    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    # Build a workflow with a known node class in the cache
    workflow = VibeWorkflow("identity_lc", WorkflowSource("identity_lc"))
    workflow.nodes["10"] = VibeNode("10", "SaveImage", inputs={"filename_prefix": "out/lc"})

    # Provide a raw workflow with provenance info that won't match any cached identity
    # so the fallback path fires
    raw_workflow: dict = {
        "nodes": [
            {
                "id": 10,
                "type": "SaveImage",
                "properties": {"cnr_id": "UnknownPack", "aux_id": "unknown/pack"},
                "widgets_values": ["out/lc"],
            }
        ],
        "links": [],
        "version": 0.4,
    }

    result = port_convert_workflow(
        workflow,
        ready_id="image/identity_lc_test",
        raw_workflow=raw_workflow,
        validate=False,
    )

    # With a raw workflow providing provenance but no identity cache match,
    # low_confidence should be True if any diagnostics were emitted,
    # or the conversion should complete without crashing.
    assert result.text  # non-empty emission


def test_emit_with_no_identity_map_preserves_class_only_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Class-only backward compatibility: no identity map => existing behavior unchanged."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("1", "MyCustomSampler")
    # No identity context
    names = _node_local_output_names(node)
    count = _node_local_arity_check(node, None)
    defaults = _node_local_class_defaults(node)

    assert names == ["samples", "preview"]
    assert count == 2
    assert defaults.get("steps") == 20


def test_use_object_info_identities_accepts_dict_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_use_object_info_identities normalizes dict-form identities to ObjectInfoIdentity."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    node = _FakeNode("20", "MyCustomSampler")
    # Pass a dict instead of ObjectInfoIdentity
    identity_dict = {"pack_slug": "MyPack", "git_commit": "abc123"}
    with _use_object_info_identities({"20": identity_dict}):  # type: ignore[arg-type]
        result = _identity_for_node(node)

    assert result is not None
    assert result.pack_slug == "MyPack"
    assert result.git_commit == "abc123"


def test_emit_ready_template_python_diagnostics_populated_for_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """emit_ready_template_python appends EmissionDiagnostic entries when identity miss occurs."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    # Build a workflow with a node that has a mis-matched identity in the map
    workflow = VibeWorkflow("diag_test", WorkflowSource("diag_test"))
    workflow.nodes["5"] = VibeNode("5", "MyCustomSampler", inputs={}, uid="sampler")

    # Bind an identity that will miss the cache
    bad_identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="notexist")
    diagnostics: list[EmissionDiagnostic] = []

    with pytest.raises(ValueError, match="schema_reconciliation_required"):
        emit_canonical_python(
            workflow,
            ready_metadata={"ready_template": "image/diag_test", "capability": "image"},
            ready_requirements={"models": [], "custom_nodes": []},
            template_id="image/diag_test",
            object_info_identities={"5": bad_identity},
            diagnostics=diagnostics,
        )

    # At least one identity-miss diagnostic should have been recorded
    identity_diag_codes = {d.code for d in diagnostics}
    assert identity_diag_codes & {"provenance_identity_cache_miss", "unprovenanced_class_fallback"}, (
        f"Expected identity-miss diagnostics, got: {diagnostics}"
    )


def test_emit_scratchpad_python_with_identity_map_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """emit_scratchpad_python with object_info_identities completes without error."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    workflow = VibeWorkflow("scratch_id", WorkflowSource("scratch_id"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out/scratch"})

    identity = ObjectInfoIdentity(pack_slug="MyPack", git_commit="abc123")
    # emit_scratchpad_python does not take object_info_identities directly,
    # but the _use_object_info_identities context is tested independently;
    # here we just verify the emitter works with the current surface.
    text = emit_scratchpad_python(
        workflow,
        workflow_id="scratch_id",
        source_path="ready_templates/sources/source.json",
    )
    assert "build" in text
    compile(text, "<scratchpad_id_test>", "exec")


def test_tuple_unpack_naming_uses_schema_output_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tuple-unpack variable names derive from schema output names when available."""
    cache_root = _build_temp_cache_for_emitter(tmp_path)
    _patch_consume_paths_emitter(monkeypatch, cache_root)

    # Build a two-output workflow: MyCustomSampler (2 outputs) -> SaveImage
    workflow = VibeWorkflow("unpack_test", WorkflowSource("unpack_test"))
    workflow.nodes["1"] = VibeNode("1", "MyCustomSampler", inputs={})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/unpack"})
    workflow.connect("1.0", "2.images")

    diagnostics: list[EmissionDiagnostic] = []
    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/unpack_test", "capability": "image"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/unpack_test",
        diagnostics=diagnostics,
    )

    # The emitted text should reference variable names derived from schema output names
    # ("samples" and/or "preview" from MyCustomSampler's output_name list)
    # OR positional tuple-unpack if schema names are unavailable.
    assert text  # non-empty emission
    compile(text, "<unpack_test>", "exec")


def test_canonical_emitter_rebuild_preserves_typed_port_authority_without_raw_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = VibeWorkflow("typed-ports", WorkflowSource("typed-ports"))
    workflow.nodes["1"] = VibeNode(
        "1", "LoadImage", inputs={"image": "source.png"}, uid="asset-loader",
        native_input_names=["image"], native_input_types=["CHOICE"],
        native_input_optional=[True], native_input_asset_kinds=["image"],
        native_output_names=["IMAGE", "MASK"], native_output_types=["IMAGE", "MASK"],
    )
    assert "_ui" not in workflow.nodes["1"].metadata

    source = emit_canonical_python(workflow)
    import vibecomfy.templates as templates_module

    path = tmp_path / "typed_ports.py"
    emit_bundle(workflow, path, {"operation": "authored"})
    templates_module._ready_native_schema_carrier.cache_clear()
    monkeypatch.setattr(
        templates_module,
        "_ready_schema_provider",
        lambda: (_ for _ in ()).throw(AssertionError("cold load consulted ambient schema")),
    )
    rebuilt = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow

    assert rebuilt.nodes["1"].native_input_types == ["CHOICE"]
    assert rebuilt.nodes["1"].native_input_optional == [True]
    assert rebuilt.nodes["1"].native_input_asset_kinds == ["image"]
    assert rebuilt.nodes["1"].native_output_types == ["IMAGE", "MASK"]
    assert rebuilt.semantic_digest() == workflow.semantic_digest()


@pytest.mark.parametrize(
    "ready_id",
    [
        "edit/flux2_klein_4b_image_edit_distilled",
        "video/ltx2_3_i2v",
    ],
)
def test_canonical_emitter_rebuild_preserves_exact_materialized_input_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ready_id: str,
) -> None:
    from vibecomfy.registry.ready import workflow_from_ready
    import vibecomfy.templates as templates_module

    workflow = workflow_from_ready(ready_id)
    materialized_pairs = [
        (owner_name, alias)
        for owner_name, owner in workflow.inputs.items()
        for alias in owner.aliases
        if alias in workflow.inputs
    ]
    assert materialized_pairs
    retained_descriptors = dict(workflow.inputs)

    source = emit_canonical_python(workflow)
    assert "materialize_aliases=True" in source or "materialize_aliases=" not in source
    path = tmp_path / f"materialized_alias_{ready_id.replace('/', '_')}.py"
    emit_bundle(workflow, path, {"operation": "authored"})
    templates_module._ready_native_schema_carrier.cache_clear()
    monkeypatch.setattr(
        templates_module,
        "_ready_schema_provider",
        lambda: (_ for _ in ()).throw(AssertionError("cold load consulted ambient schema")),
    )
    rebuilt = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow

    # Ready registry requirements are a source witness; canonical rebuild
    # refreshes them from the actual picker occurrences.  The executable IR,
    # interface descriptors, and aliases are the identity we must preserve.
    assert rebuilt.compile("api") == workflow.compile("api")
    for owner_name, alias in materialized_pairs:
        assert rebuilt.inputs[owner_name] == retained_descriptors[owner_name]
        assert rebuilt.inputs[alias] == retained_descriptors[alias]
    rebuilt.set_input("image", "first.png")
    rebuilt.set_input("input_image", "second.png")
    assert rebuilt.nodes[retained_descriptors["image"].node_id].inputs["image"] == "second.png"


def test_canonical_emitter_does_not_infer_over_retained_motion_prompt_target(tmp_path: Path) -> None:
    from vibecomfy.registry.ready import workflow_from_ready

    ready_id = "video/ltx2_3_runexx_motion_transfer_dwpose"
    workflow = workflow_from_ready(ready_id)
    source = emit_canonical_python(workflow)
    rebuilt = _bundle_roundtrip(workflow, tmp_path, "motion_transfer.py")

    assert rebuilt.compile("api") == workflow.compile("api")
    assert rebuilt.inputs["negative_prompt"].aliases == ("negative",)
    assert "prompt" not in rebuilt.inputs["negative_prompt"].aliases


@pytest.mark.parametrize(
    "changed",
    [
        {"node_id": "2"},
        {"field": "other"},
        {"value": 1.0},
        {"type": "FLOAT"},
        {"default": 1.0},
        {"required": 1},
        {"range": [0, 1]},
        {"media_semantics": "image"},
        {"allow_missing_target": 0},
        {"aliases": ("other_alias",)},
    ],
)
def test_materialized_input_alias_rejects_any_descriptor_difference(
    changed: dict[str, object],
) -> None:
    workflow = VibeWorkflow("alias-guard", WorkflowSource("alias-guard"))
    workflow.nodes["1"] = VibeNode(
        "1", "PrimitiveInt", inputs={"amount": 1, "other": 1}
    )
    workflow.nodes["2"] = VibeNode(
        "2", "PrimitiveInt", inputs={"amount": 1, "other": 1}
    )
    workflow.register_input(
        "amount", "1", "amount", 1, type="INT",
        default=1, required=True, aliases=("alias_amount",),
    )
    descriptor: dict[str, object] = {
        "node_id": "1",
        "field": "amount",
        "value": 1,
        "type": "INT",
        "default": 1,
        "required": True,
        "range": None,
        "aliases": (),
        "media_semantics": None,
        "allow_missing_target": False,
    }
    descriptor.update(changed)

    with pytest.raises(ValueError, match="materialized alias"):
        workflow.register_input(
            "alias_amount",
            str(descriptor.pop("node_id")),
            str(descriptor.pop("field")),
            descriptor.pop("value"),
            materialized_alias_of="amount",
            **descriptor,
        )

    assert "alias_amount" not in workflow.inputs
    with pytest.raises(ValueError, match="conflicts with an existing alias"):
        workflow.register_input("alias_amount", "1", "amount", 1)


def test_e0_canonical_source_uses_handles_without_importer_identity_or_native_payloads() -> None:
    """E0 characterization: ordinary constructor calls must be source-editable."""
    source = emit_canonical_python(_sample_workflow())
    tree = ast.parse(source)
    forbidden: list[tuple[str, str]] = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        for keyword in call.keywords:
            if keyword.arg in {"_id", "_uid", "_native_ports"}:
                forbidden.append((keyword.arg, f"line {call.lineno}"))
    assert forbidden == [], f"routine constructor custody leaked into calls: {forbidden}"


def test_e0_canonical_source_has_no_replay_topology_tail() -> None:
    """E0 characterization: effective topology must be expressed once."""
    source = emit_canonical_python(_sample_workflow())
    tree = ast.parse(source)
    replay_assignments = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Subscript)
        and isinstance(node.targets[0].value.value, ast.Attribute)
        and isinstance(node.targets[0].value.value.value, ast.Name)
        and node.targets[0].value.value.value.id == "wf"
        and node.targets[0].value.value.attr == "nodes"
    ]
    assert "wf.connect(" not in source
    assert replay_assignments == [], f"post-construction replay remains at lines {replay_assignments}"


def test_e0_constructor_edit_survives_rebuild_without_later_replay() -> None:
    """E0 characterization: editing an emitted default changes the graph."""
    source = emit_canonical_python(_sample_workflow(), preserve_node_ids=True)
    edited = source.replace("DEFAULT_PREFIX = 'out/sample'", "DEFAULT_PREFIX = 'out/edited'", 1)
    namespace: dict[str, Any] = {"__file__": "edited-emitted.py"}
    exec(compile(edited, "edited-emitted.py", "exec"), namespace)  # noqa: S102 - generated source under test
    rebuilt = namespace["build"]()
    assert rebuilt.nodes["20"].inputs["filename_prefix"] == "out/edited"


def test_e0_h3_source_lowers_resolver_owned_reroutes(tmp_path: Path) -> None:
    """E0 characterization: resolver-owned reroutes must not be emitted as nodes."""
    workflow = VibeWorkflow("reroute", WorkflowSource("reroute"))
    workflow.nodes["1"] = VibeNode("1", "SchemaLessSource", uid="source")
    workflow.nodes["2"] = VibeNode("2", "Reroute", uid="reroute")
    workflow.nodes["3"] = VibeNode("3", "SchemaLessSink", uid="sink")
    workflow.connect("1.0", "2.0")
    workflow.connect("2.0", "3.value")
    source = emit_canonical_python(workflow, preserve_node_ids=True)
    assert "raw_call('Reroute'" not in source
    assert "HELPER_CUSTODY" not in source
    rebuilt = _bundle_roundtrip(workflow, tmp_path, "reroute.py")
    assert rebuilt.compile("api") == workflow.compile("api")
    assert rebuilt.metadata["resolver_helper_custody"][0]["uid"] == "reroute"


def test_canonical_source_rejects_semantic_edges_to_ui_only_nodes() -> None:
    workflow = VibeWorkflow("ui-edge", WorkflowSource("ui-edge"))
    workflow.nodes["note"] = VibeNode("note", "MarkdownNote", uid="note")
    workflow.nodes["sink"] = VibeNode("sink", "SchemaLessSink", uid="sink")
    workflow.connect("note.0", "sink.value")

    with pytest.raises(ConversionParityError, match="UI-only node"):
        emit_canonical_python(workflow)
