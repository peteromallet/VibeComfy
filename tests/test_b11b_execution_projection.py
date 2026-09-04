from __future__ import annotations

import copy
import sys
import types

import pytest

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.emit import emit_ready_template_python, emit_scratchpad_python
from vibecomfy.workflow import (
    NodeMode,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowCompileError,
    WorkflowSource,
)


def _chain(mode: object) -> VibeWorkflow:
    workflow = VibeWorkflow("b11b", WorkflowSource("b11b"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Middle", mode=mode)  # type: ignore[arg-type]
    workflow.nodes["3"] = VibeNode("3", "SaveImage")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "2", "in"),
            VibeEdge("2", "0", "3", "images"),
        ]
    )
    return workflow


def _install_fake_graphbuilder(monkeypatch: pytest.MonkeyPatch) -> None:
    graph_utils = types.ModuleType("comfy_execution.graph_utils")

    class FakeGraphBuilder:
        def __init__(self, prefix: str = "") -> None:
            self.nodes: dict[str, dict[str, object]] = {}

        def node(self, class_type: str, id: str, **inputs: object) -> None:
            self.nodes[str(id)] = {"class_type": class_type, "inputs": inputs}

        def finalize(self) -> dict[str, dict[str, object]]:
            return self.nodes

    graph_utils.GraphBuilder = FakeGraphBuilder
    monkeypatch.setitem(sys.modules, "comfy_execution", types.ModuleType("comfy_execution"))
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", graph_utils)


@pytest.mark.parametrize(
    ("label", "mode", "expected_nodes", "expected_sink"),
    [
        ("live", NodeMode.ENABLED, {"1", "2", "3"}, ["2", 0]),
        ("muted", NodeMode.MUTED, {"1", "3"}, None),
        ("bypass", NodeMode.BYPASSED, {"1", "3"}, ["1", 0]),
        ("never", "never", {"1", "3"}, None),
    ],
)
def test_api_and_graphbuilder_share_execution_projection(
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    mode: object,
    expected_nodes: set[str],
    expected_sink: list[object] | None,
) -> None:
    del label
    _install_fake_graphbuilder(monkeypatch)
    workflow = _chain(mode)

    api = workflow.compile("api")
    graph = workflow.compile("graphbuilder")

    assert set(api) == expected_nodes
    assert set(graph) == expected_nodes
    assert graph == api
    assert api["3"]["inputs"].get("images") == expected_sink


def test_projection_resolves_multi_hop_bypass_reroutes() -> None:
    workflow = VibeWorkflow("reroute", WorkflowSource("reroute"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Middle", mode=NodeMode.BYPASSED)
    workflow.nodes["3"] = VibeNode("3", "Middle", mode=NodeMode.BYPASSED)
    workflow.nodes["4"] = VibeNode("4", "SaveImage")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "2", "in"),
            VibeEdge("2", "0", "3", "in"),
            VibeEdge("3", "0", "4", "images"),
        ]
    )

    assert workflow.compile("api")["4"]["inputs"]["images"] == ["1", 0]


def _set_get_bypass_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("b11b-set-get", WorkflowSource("b11b-set-get"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"}, uid="u1")
    workflow.nodes["2"] = VibeNode("2", "ImageFilter", mode=NodeMode.BYPASSED, uid="u2")
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"}, uid="u3")
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"}, uid="u4")
    workflow.nodes["5"] = VibeNode("5", "SaveImage", uid="u5")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "2", "image"),
            VibeEdge("2", "0", "3", "IMAGE"),
            VibeEdge("4", "0", "5", "images"),
        ]
    )
    return workflow


def test_set_get_bypass_projection_agrees_across_api_graphbuilder_and_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_graphbuilder(monkeypatch)
    workflow = _set_get_bypass_workflow()
    expected = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    api = workflow.compile("api")
    assert api == expected
    assert workflow.compile("graphbuilder") == expected

    converted = port_convert_workflow(workflow, validate=True, prune_dead_branches=False)
    assert converted.validation is not None
    assert converted.validation.parity_ok is True
    namespace: dict[str, object] = {"__file__": "b11b_set_get.py"}
    exec(compile(converted.text, "b11b set/get emitted", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["build"]()
    assert rebuilt.nodes["2"].mode is NodeMode.BYPASSED
    assert rebuilt.compile("api") == expected


def test_target_cardinality_fails_execution_but_preserves_duplicate_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_graphbuilder(monkeypatch)
    workflow = VibeWorkflow("cardinality", WorkflowSource("cardinality"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Source")
    workflow.nodes["3"] = VibeNode("3", "SaveImage")
    workflow.edges.extend(
        [
            VibeEdge("1", "0", "3", "images"),
            VibeEdge("2", "0", "3", "images"),
        ]
    )

    for backend in ("api", "graphbuilder"):
        with pytest.raises(WorkflowCompileError, match="target_input_cardinality"):
            workflow.compile(backend)

    report = workflow.validate(schema_provider=None)
    assert not report.ok
    assert any(
        issue.code == "api_compile_failed"
        and issue.detail["compile_code"] == "target_input_cardinality"
        for issue in report.issues
    )
    envelope = workflow.to_envelope()
    assert len(envelope["edges"]) == 2


def test_custom_json_socket_values_are_not_reinterpreted() -> None:
    workflow = VibeWorkflow("opaque", WorkflowSource("opaque"))
    payload = {"socket": "custom", "rows": [{"value": 1}, {"value": [2, 3]}]}
    workflow.nodes["1"] = VibeNode("1", "OpaqueNode", inputs={"payload": payload})

    assert workflow.compile("api")["1"]["inputs"]["payload"] == payload


def test_bypass_uses_socket_compatibility_and_rejects_no_match() -> None:
    workflow = VibeWorkflow("typed-bypass", WorkflowSource("typed-bypass"))
    workflow.nodes["image"] = VibeNode(
        "image", "Source", metadata={"output_types": ["IMAGE"]}, native_output_names=["image"]
    )
    workflow.nodes["mask"] = VibeNode(
        "mask", "Source", metadata={"output_types": ["MASK"]}, native_output_names=["mask"]
    )
    workflow.nodes["bypass"] = VibeNode(
        "bypass", "Filter", mode=NodeMode.BYPASSED,
        native_input_names=["mask", "image"], native_output_names=["image"],
        metadata={"input_types": ["MASK", "IMAGE"], "output_types": ["IMAGE"]},
    )
    workflow.nodes["sink"] = VibeNode(
        "sink", "Sink", inputs={"image": None}, metadata={"input_types": {"image": "IMAGE"}}
    )
    workflow.edges = [
        VibeEdge("mask", "0", "bypass", "mask"),
        VibeEdge("image", "0", "bypass", "image"),
        VibeEdge("bypass", "0", "sink", "image"),
    ]
    assert workflow.compile()["sink"]["inputs"]["image"] == ["image", 0]

    workflow.nodes["sink"].metadata["input_types"] = {"image": "AUDIO"}
    with pytest.raises(WorkflowCompileError, match="bypass_no_match"):
        workflow.compile()


def test_bypass_cycle_and_dangling_helper_fail_closed() -> None:
    workflow = VibeWorkflow("cycle", WorkflowSource("cycle"))
    workflow.nodes["a"] = VibeNode("a", "A", mode=NodeMode.BYPASSED)
    workflow.nodes["b"] = VibeNode("b", "B", mode=NodeMode.BYPASSED)
    workflow.nodes["sink"] = VibeNode("sink", "Sink", inputs={"x": None})
    workflow.edges = [VibeEdge("a", "0", "b", "x"), VibeEdge("b", "0", "a", "x"), VibeEdge("a", "0", "sink", "x")]
    with pytest.raises(WorkflowCompileError, match="bypass_cycle"):
        workflow.compile()

    dangling = VibeWorkflow("dangling", WorkflowSource("dangling"))
    dangling.nodes["r"] = VibeNode("r", "Reroute")
    dangling.nodes["sink"] = VibeNode("sink", "Sink", inputs={"x": None})
    dangling.edges = [VibeEdge("r", "0", "sink", "x")]
    with pytest.raises(WorkflowCompileError, match="helper_edge_unresolved"):
        dangling.compile()


def test_helper_cycles_and_malformed_typed_literals_fail_at_projection() -> None:
    cycle = VibeWorkflow("primitive-cycle", WorkflowSource("primitive-cycle"))
    cycle.nodes["p"] = VibeNode("p", "PrimitiveNode", inputs={"value": 1})
    cycle.nodes["r"] = VibeNode("r", "Reroute")
    cycle.nodes["sink"] = VibeNode("sink", "Sink", inputs={"x": None})
    cycle.edges = [VibeEdge("p", "0", "r", "0"), VibeEdge("r", "0", "p", "0"), VibeEdge("r", "0", "sink", "x")]
    with pytest.raises(WorkflowCompileError) as exc:
        cycle.compile()
    assert exc.value.code == "helper_edge_cycle"

    invalid = VibeWorkflow("typed-literal", WorkflowSource("typed-literal"))
    invalid.nodes["p"] = VibeNode("p", "PrimitiveInt", inputs={"value": "not-an-int"})
    invalid.nodes["sink"] = VibeNode("sink", "Sink", inputs={"x": None})
    invalid.edges = [VibeEdge("p", "0", "sink", "x")]
    with pytest.raises(WorkflowCompileError) as exc:
        invalid.compile()
    assert exc.value.code == "primitive_literal_invalid"


def test_virtual_wire_occurrences_are_grouped_by_semantic_leg() -> None:
    workflow = VibeWorkflow("wire-multiplicity", WorkflowSource("wire-multiplicity"))
    workflow.nodes["source"] = VibeNode("source", "Source")
    workflow.nodes["left"] = VibeNode("left", "Sink", inputs={"x": None})
    workflow.nodes["right"] = VibeNode("right", "Sink", inputs={"x": None})
    workflow.virtual_wires = {
        "route": {
            "legs": [
                {"leg_index": 0, "occurrence_index": 0, "from_node": "source", "to_node": "left", "to_input": "x"},
                {"leg_index": 0, "occurrence_index": 1, "from_node": "source", "to_node": "left", "to_input": "x"},
                {"leg_index": 1, "occurrence_index": 0, "from_node": "source", "to_node": "right", "to_input": "x"},
                # Distinct semantic legs may share endpoints, but the executable
                # projection collapses the exact endpoint tuple once.
                {"leg_index": 2, "occurrence_index": 0, "from_node": "source", "to_node": "left", "to_input": "x"},
            ]
        }
    }
    projection = workflow._execution_projection()
    assert [(edge.to_node, edge.to_input) for edge in projection.edges] == [
        ("left", "x"), ("right", "x")
    ]
    workflow.virtual_wires["route"]["legs"][1]["occurrence_index"] = 2
    with pytest.raises(WorkflowCompileError, match="occurrence indexes"):
        workflow.compile()


def test_shared_projection_lowers_primitive_and_named_outputs_without_mutation() -> None:
    workflow = VibeWorkflow("helpers", WorkflowSource("helpers"))
    workflow.nodes["source"] = VibeNode("source", "Source", native_output_names=["image", "mask"])
    workflow.nodes["primitive"] = VibeNode("primitive", "PrimitiveInt", inputs={"value": 7})
    workflow.nodes["sink"] = VibeNode("sink", "Sink", inputs={"value": None, "image": None})
    workflow.edges = [
        VibeEdge("primitive", "0", "sink", "value"),
        VibeEdge("source", "mask", "sink", "image"),
    ]
    before = workflow.copy()
    api = workflow.compile()
    assert api["sink"]["inputs"] == {"value": 7, "image": ["source", 1]}
    assert workflow.nodes["primitive"].class_type == before.nodes["primitive"].class_type
    assert workflow.nodes["primitive"].inputs == before.nodes["primitive"].inputs
    assert workflow.edges[1].from_output == before.edges[1].from_output == "mask"


def test_scoped_variant_and_explicit_virtual_wire_are_projection_inputs() -> None:
    workflow = VibeWorkflow("scoped", WorkflowSource("scoped"))
    workflow.nodes["source"] = VibeNode("source", "Source")
    workflow.nodes["sink"] = VibeNode("sink", "Sink", inputs={"x": None})
    definition = {"name": "inner", "nodes": [{"id": "n", "type": "Inner", "inputs": {"x": 1}}], "links": []}
    from vibecomfy.identity.scope import sg_key

    scope = sg_key(definition)
    workflow.definitions = {"subgraphs": [definition]}
    workflow.variants = {"alt": {f"{scope}#n.x": 9}}
    assert workflow._with_selection("alt", None).definitions["subgraphs"][0]["nodes"][0]["inputs"]["x"] == 9
    workflow.virtual_wires = {"route": {"legs": [{"leg_index": 0, "occurrence_index": 0, "from_node": "source", "from_output": 0, "to_node": "sink", "to_input": "x"}]}}
    assert workflow.compile()["sink"]["inputs"]["x"] == ["source", 0]


def test_virtual_wire_contract_rejects_legacy_and_noncontiguous_occurrences() -> None:
    workflow = VibeWorkflow("wire-contract", WorkflowSource("wire-contract"))
    workflow.nodes["source"] = VibeNode("source", "Source")
    workflow.nodes["sink"] = VibeNode("sink", "Sink", inputs={"x": None})
    workflow.virtual_wires = {
        "route": {
            "legs": [
                {"leg_index": 0, "occurrence_index": 0, "from_node": "source", "to_node": "sink", "to_input": "x"},
                {"leg_index": 2, "occurrence_index": 2, "from_node": "source", "to_node": "sink", "to_input": "x"},
            ]
        }
    }
    with pytest.raises(WorkflowCompileError, match="contiguous"):
        workflow.compile()
    workflow.virtual_wires = {"route": {"channel": "route", "endpoints": []}}
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "legacy_virtual_wire"


def test_public_io_type_and_cardinality_are_closed_over_declared_sockets() -> None:
    workflow = VibeWorkflow("public-contract", WorkflowSource("public-contract"))
    workflow.nodes["source"] = VibeNode(
        "source", "Source", metadata={"output_names": ["image"], "output_types": ["IMAGE"]}
    )
    workflow.nodes["sink"] = VibeNode(
        "sink", "Sink", inputs={"image": None}, metadata={"input_types": {"image": "IMAGE"}}
    )
    workflow.inputs["bad"] = VibeInput(
        "bad", "sink", "image", type="AUDIO"
    )
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "public_input_incompatible"
    workflow.inputs.clear()
    workflow.outputs.append(
        VibeOutput(
            "source", "Source", name="image", expected_cardinality=3
        )
    )
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "public_output_cardinality"


def test_public_input_defaults_and_named_nonzero_output_are_shared_by_backends() -> None:
    workflow = VibeWorkflow("public-values", WorkflowSource("public-values"))
    workflow.nodes["source"] = VibeNode(
        "source", "Source", native_output_names=["ignored", "image"],
        metadata={"output_types": ["MASK", "IMAGE"]},
    )
    workflow.nodes["sink"] = VibeNode(
        "sink", "Sink", inputs={"value": None, "image": None},
        metadata={"input_types": {"value": "INT", "image": "IMAGE"}},
    )
    workflow.edges = [VibeEdge("source", "image", "sink", "image")]
    workflow.inputs["count"] = VibeInput("count", "sink", "value", default=7, type="INT")
    workflow.outputs.append(VibeOutput("source", "Source", name="image"))
    api = workflow.compile("api")
    graph = workflow.compile("graphbuilder")
    assert api == graph
    assert api["sink"]["inputs"]["value"] == 7
    assert api["sink"]["inputs"]["image"] == ["source", 1]
    assert workflow.nodes["sink"].inputs["value"] is None

    workflow.outputs[:] = [VibeOutput("source", "IMAGE")]
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "public_output_incompatible"


def _depth_two_sibling_workflow() -> tuple[VibeWorkflow, str, str]:
    """Existing-field recursive fixture: two outer occurrences, one nested."""
    from vibecomfy.identity.scope import sg_key

    inner = {
        "id": "native-inner", "name": "InnerEcho",
        "nodes": [{
            "id": "inner_core", "type": "EchoImage",
            "inputs": [{"name": "in", "type": "IMAGE", "link": None, "value": None}],
            "outputs": [{"name": "out", "type": "IMAGE"}],
        }],
        "links": [],
    }
    inner_key = sg_key(inner)
    outer = {
        "id": "native-outer", "name": "OuterBox",
        "nodes": [{
            "id": "inner_a", "type": "native-inner",
            "inputs": [{"name": "input", "type": "IMAGE", "link": None, "value": None}],
            "outputs": [{"name": "output", "type": "IMAGE"}],
        }],
        "links": [], "definitions": {"subgraphs": [inner]},
    }
    outer_key = sg_key(outer)

    def source(node_id: str, value: str) -> VibeNode:
        return VibeNode(
            node_id, "Source", inputs={"value": value}, uid=node_id,
            native_output_names=["out"], metadata={"output_names": ["out"], "output_types": ["IMAGE"]},
        )

    def instance(node_id: str) -> VibeNode:
        return VibeNode(
            node_id, "native-outer", uid=node_id,
            native_input_names=["input"], native_output_names=["output"],
            metadata={"input_types": ["IMAGE"], "output_types": ["IMAGE"]},
        )

    def sink(node_id: str) -> VibeNode:
        return VibeNode(node_id, "Sink", inputs={"image": None}, uid=node_id, metadata={"input_types": {"image": "IMAGE"}})

    workflow = VibeWorkflow(
        "t05-depth2-siblings", WorkflowSource("t05-depth2-siblings"),
        nodes={
            "source_a": source("source_a", "A"), "outer_a": instance("outer_a"), "sink_a": sink("sink_a"),
            "source_b": source("source_b", "B"), "outer_b": instance("outer_b"), "sink_b": sink("sink_b"),
        },
        edges=[
            VibeEdge("source_a", "out", "outer_a", "input"), VibeEdge("outer_a", "output", "sink_a", "image"),
            VibeEdge("source_b", "out", "outer_b", "input"), VibeEdge("outer_b", "output", "sink_b", "image"),
        ],
        definitions={"subgraphs": [outer]},
        interfaces={
            outer_key: {
                "inputs": [{"name": "input", "direction": "input", "type": "IMAGE"}],
                "outputs": [{"name": "output", "direction": "output", "type": "IMAGE"}],
            },
            inner_key: {
                "inputs": [{"name": "input", "direction": "input", "type": "IMAGE"}],
                "outputs": [{"name": "output", "direction": "output", "type": "IMAGE"}],
            },
        },
        boundary_ports=[
            {"scope_path": outer_key, "name": "input", "direction": "input", "node_uid": "inner_a", "field": "input"},
            {"scope_path": outer_key, "name": "output", "direction": "output", "node_uid": "inner_a", "field": "output"},
            {"scope_path": inner_key, "name": "input", "direction": "input", "node_uid": "inner_core", "field": "in"},
            {"scope_path": inner_key, "name": "output", "direction": "output", "node_uid": "inner_core", "field": "out"},
        ],
    )
    return workflow, inner_key, outer_key


def test_recursive_occurrences_expand_depth_two_and_isolate_siblings() -> None:
    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    before = workflow.to_envelope()
    api = workflow.compile("api")
    graph = workflow.compile("graphbuilder")
    a = f"{outer_key}:outer_a/{inner_key}:inner_a#inner_core"
    b = f"{outer_key}:outer_b/{inner_key}:inner_a#inner_core"
    assert api == graph
    assert set(api) == {"source_a", "sink_a", "source_b", "sink_b", a, b}
    assert "outer_a" not in api and "outer_b" not in api and "native-outer" not in api
    assert api[a]["inputs"]["in"] == ["source_a", 0]
    assert api[b]["inputs"]["in"] == ["source_b", 0]
    assert api["sink_a"]["inputs"]["image"] == [a, 0]
    assert api["sink_b"]["inputs"]["image"] == [b, 0]
    assert workflow.to_envelope() == before


def test_global_definition_alias_expands_sibling_store_and_preserves_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_graphbuilder(monkeypatch)
    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    outer = workflow.definitions["subgraphs"][0]
    inner = outer["definitions"]["subgraphs"][0]
    del outer["definitions"]
    workflow.definitions = {"subgraphs": [outer, inner]}
    before = copy.deepcopy(workflow.to_envelope())

    api = workflow.compile("api")
    graph = workflow.compile("graphbuilder")
    expected_a = f"{outer_key}:outer_a/{inner_key}:inner_a#inner_core"
    expected_b = f"{outer_key}:outer_b/{inner_key}:inner_a#inner_core"
    assert api == graph
    assert {expected_a, expected_b} <= set(api)
    assert not {"outer_a", "outer_b", "native-inner", "native-outer"} & set(api)
    assert api[expected_a]["inputs"]["in"] == ["source_a", 0]
    assert api[expected_b]["inputs"]["in"] == ["source_b", 0]
    assert api["sink_a"]["inputs"]["image"] == [expected_a, 0]
    assert api["sink_b"]["inputs"]["image"] == [expected_b, 0]
    assert workflow.to_envelope() == before
    assert workflow.compile("api") == api
    assert workflow.to_envelope() == before


def test_nested_blank_uid_falls_back_to_existing_id() -> None:
    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    workflow.definitions["subgraphs"][0]["nodes"][0]["uid"] = ""
    api = workflow.compile("api")
    expected = f"{outer_key}:outer_a/{inner_key}:inner_a#inner_core"
    assert expected in api
    assert ":/" not in expected


@pytest.mark.parametrize("kind", ["self", "mutual"])
def test_recursive_definition_cycles_fail_closed(kind: str) -> None:
    first = {"id": "cycle-a", "name": "CycleA", "nodes": []}
    if kind == "self":
        first["definitions"] = {"subgraphs": [first]}
    else:
        second = {"id": "cycle-b", "name": "CycleB", "nodes": []}
        first["definitions"] = {"subgraphs": [second]}
        second["definitions"] = {"subgraphs": [first]}
    workflow = VibeWorkflow(
        "recursive-cycle", WorkflowSource("recursive-cycle"),
        nodes={"root": VibeNode("root", "Source")},
        definitions={"subgraphs": [first]},
    )
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile("api")
    assert exc.value.code == "recursive_definition_cycle"
    if kind == "self":
        assert first["definitions"]["subgraphs"][0] is first
    else:
        second = first["definitions"]["subgraphs"][0]
        assert second["definitions"]["subgraphs"][0] is first


def test_definition_aliases_are_globally_unique() -> None:
    first = {"id": "duplicate-native", "name": "First", "nodes": []}
    nested = {"id": "duplicate-native", "name": "Nested", "nodes": [{"id": "n", "type": "Sink"}]}
    first["definitions"] = {"subgraphs": [nested]}
    workflow = VibeWorkflow(
        "duplicate-alias", WorkflowSource("duplicate-alias"),
        nodes={"root": VibeNode("root", "Source")},
        definitions={"subgraphs": [first]},
    )
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile("api")
    assert exc.value.code == "definition_alias_duplicate"


def test_unknown_interface_and_boundary_scope_fail_closed() -> None:
    definition = {"id": "native", "name": "Known", "nodes": []}
    workflow = VibeWorkflow(
        "unknown-contract", WorkflowSource("unknown-contract"),
        nodes={"root": VibeNode("root", "Source")},
        definitions={"subgraphs": [definition]},
        interfaces={"not-indexed": {"inputs": []}},
    )
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile("api")
    assert exc.value.code == "interface_unknown"

    workflow.interfaces = {}
    workflow.boundary_ports = [{"scope_path": "not-indexed", "name": "x", "direction": "input", "node_uid": "n", "field": "x"}]
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile("api")
    assert exc.value.code == "boundary_scope_unknown"


def test_mapping_socket_descriptor_is_rejected_before_execution() -> None:
    definition = {
        "id": "native-sink", "name": "SinkDefinition",
        "nodes": [{"id": "inner", "type": "Sink", "inputs": {"in": {"type": "IMAGE", "value": None}}}],
    }
    workflow = VibeWorkflow(
        "mapping-socket", WorkflowSource("mapping-socket"),
        nodes={"root": VibeNode("root", "native-sink", uid="root")},
        definitions={"subgraphs": [definition]},
    )
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile("api")
    assert exc.value.code == "boundary_port_untyped"


def test_virtual_wires_are_grouped_by_scope_name_and_leg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_graphbuilder(monkeypatch)
    workflow = VibeWorkflow("scoped-wires", WorkflowSource("scoped-wires"))
    for scope in ("left", "right"):
        workflow.nodes[f"{scope}#source"] = VibeNode(f"{scope}#source", "Source", uid="source")
        workflow.nodes[f"{scope}#sink"] = VibeNode(f"{scope}#sink", "Sink", uid="sink", inputs={"image": None})
    workflow.virtual_wires = {
        "route": {"legs": [
            {"scope_path": "left", "leg_index": 0, "occurrence_index": 0, "from_node": "source", "from_output": 0, "to_node": "sink", "to_input": "image"},
            {"scope_path": "right", "leg_index": 0, "occurrence_index": 0, "from_node": "source", "from_output": 0, "to_node": "sink", "to_input": "image"},
        ]}
    }
    api = workflow.compile("api")
    assert api == workflow.compile("graphbuilder")
    assert api["left#sink"]["inputs"]["image"] == ["left#source", 0]
    assert api["right#sink"]["inputs"]["image"] == ["right#source", 0]


def test_recursive_occurrence_contract_rejects_collisions_and_bad_bindings() -> None:
    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    workflow.nodes["outer_b"].uid = "outer_a"
    with pytest.raises(WorkflowCompileError, match="occurrence_collision"):
        workflow.compile()
    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    workflow.boundary_ports[0] = {**workflow.boundary_ports[0], "direction": "output"}
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code in {"boundary_port_duplicate", "interface_unbound", "boundary_port_missing"}
    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    workflow.boundary_ports[2] = {**workflow.boundary_ports[2], "scope_path": outer_key}
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code in {"interface_unbound", "boundary_port_unbound", "boundary_port_missing", "boundary_port_duplicate"}


def test_public_artifact_output_is_outside_prompt_and_handles_are_separate() -> None:
    from vibecomfy.handles import Handle

    workflow = VibeWorkflow("artifact", WorkflowSource("artifact"))
    workflow.nodes["source"] = VibeNode(
        "source", "Source", uid="source", native_output_names=["mask", "image"],
        metadata={"output_types": ["MASK", "IMAGE"]},
    )
    workflow.nodes["sink"] = VibeNode("sink", "Sink", uid="sink", inputs={"image": None}, metadata={"input_types": {"image": "IMAGE"}})
    workflow.nodes["save"] = VibeNode("save", "SaveImage", uid="save", inputs={"images": None})
    workflow.connect(Handle("source", 1, name="image"), "sink.image")
    workflow.edges.append(VibeEdge("sink", "0", "save", "images"))
    workflow.outputs.append(VibeOutput("save", "SaveImage", name="image", artifact_kind="image", mime_type="image/png"))
    api = workflow.compile("api")
    assert workflow.compile("graphbuilder") == api
    assert api["sink"]["inputs"]["image"] == ["source", 1]
    assert set(api) == {"source", "sink", "save"}
    assert "outputs" not in api and "name" not in api
    workflow.outputs.append(VibeOutput("save", "SaveImage", name="image"))
    with pytest.raises(WorkflowCompileError, match="public_output_duplicate"):
        workflow.compile()
    workflow.outputs[:] = [VibeOutput("save", "SaveImage", name="image")]
    workflow.nodes["save"].mode = NodeMode.MUTED
    with pytest.raises(WorkflowCompileError, match="public_output_missing"):
        workflow.compile()


def test_conversion_primitive_parity_uses_coherent_lens() -> None:
    workflow = VibeWorkflow("primitive-parity", WorkflowSource("primitive-parity"))
    workflow.nodes["p"] = VibeNode("p", "PrimitiveInt", inputs={"value": 7})
    workflow.nodes["s"] = VibeNode("s", "Sink", inputs={"x": 1})
    workflow.edges = [VibeEdge("p", "0", "s", "x")]
    expected = workflow.compile("api")
    default = port_convert_workflow(workflow, validate=True, prune_dead_branches=False, keep_virtual_wires=False)
    assert default.validation and default.validation.parity_ok
    assert "PrimitiveInt" not in default.text
    ns: dict[str, object] = {"__file__": "primitive_parity.py"}
    exec(compile(default.text, "primitive parity", "exec"), ns)  # noqa: S102
    assert ns["build"]().compile("api") == expected

    kept = port_convert_workflow(workflow, validate=True, prune_dead_branches=False, keep_virtual_wires=True)
    assert "PrimitiveInt" in kept.text
    ns = {"__file__": "primitive_parity_keep.py"}
    exec(compile(kept.text, "primitive parity keep", "exec"), ns)  # noqa: S102
    assert ns["build"]().compile("api") == expected
    ready = emit_ready_template_python(workflow, ready_metadata={"ready_template": "test/primitive"}, ready_requirements={}, template_id="test/primitive")
    assert "PrimitiveInt" not in ready
    ns = {"__file__": "primitive_parity_ready.py"}
    exec(compile(ready, "primitive parity ready", "exec"), ns)  # noqa: S102
    assert ns["build"]().compile("api") == expected


def test_conversion_channel_collision_keeps_semantic_input_over_widget_and_ui() -> None:
    workflow = VibeWorkflow("channel-collision", WorkflowSource("channel-collision"))
    workflow.nodes["sink"] = VibeNode(
        "sink", "Sink", inputs={"x": 7}, widgets={"x": 1},
        metadata={"_ui": {"widgets_values": [99], "x": 100}},
    )
    expected = workflow.compile("api")
    assert expected["sink"]["inputs"]["x"] == 7

    scratchpad = port_convert_workflow(
        workflow, validate=True, prune_dead_branches=False, keep_virtual_wires=False
    )
    assert scratchpad.validation and scratchpad.validation.parity_ok
    ns: dict[str, object] = {"__file__": "channel_collision.py"}
    exec(compile(scratchpad.text, "channel collision", "exec"), ns)  # noqa: S102
    assert ns["build"]().compile("api") == expected
    ready = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "test/channel-collision"},
        ready_requirements={},
        template_id="test/channel-collision",
    )
    ns = {"__file__": "channel_collision_ready.py"}
    exec(compile(ready, "channel collision ready", "exec"), ns)  # noqa: S102
    assert ns["build"]().compile("api") == expected


def test_ready_emission_ignores_raw_ui_widget_aliases() -> None:
    def build(ui_names: list[str]) -> tuple[dict[str, dict[str, object]], str]:
        workflow = VibeWorkflow("ui-independent", WorkflowSource("ui-independent"))
        workflow.nodes["s"] = VibeNode(
            "s", "UnknownSink", widgets={"widget_0": 1},
            metadata={"_ui": {"widget_names": ui_names}},
        )
        ready = emit_ready_template_python(
            workflow,
            ready_metadata={"ready_template": "test/primitive"},
            ready_requirements={},
            template_id="test/primitive",
        )
        namespace: dict[str, object] = {"__file__": "ui-independent.py"}
        exec(compile(ready, "ui-independent", "exec"), namespace)  # noqa: S102
        return namespace["build"]().compile("api"), ready

    first, first_text = build(["x"])
    second, second_text = build(["y"])
    assert first == second == {"s": {"class_type": "UnknownSink", "inputs": {"widget_0": 1}}}
    assert "widget_0=1" in first_text
    assert "widget_0=1" in second_text

def test_real_graphbuilder_uses_the_same_detached_projection() -> None:
    workflow = _chain(NodeMode.ENABLED)
    before = workflow.copy()
    assert workflow.compile("graphbuilder") == workflow.compile("api")
    assert workflow.to_envelope() == before.to_envelope()


def test_ui_mode_evidence_does_not_change_execution_projection() -> None:
    workflow = _chain(NodeMode.ENABLED)
    workflow.nodes["2"].metadata["_ui"] = {"mode": 4, "widgets_values": ["misleading"]}
    assert set(workflow.compile("api")) == {"1", "2", "3"}


def test_native_boundary_sentinel_fails_at_projection_boundary() -> None:
    workflow = VibeWorkflow("boundary", WorkflowSource("boundary"))
    workflow.nodes["root"] = VibeNode("root", "Source")
    workflow.definitions = {
        "subgraphs": [{"name": "inner", "nodes": [{"id": "n", "type": "Sink"}], "links": [[1, "-10", 0, "n", 0, "IMAGE"]]}]
    }
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "unsupported_boundary_encoding"


def test_recursive_instance_ambiguity_and_unbound_interface_fail_closed() -> None:
    workflow = VibeWorkflow("recursive-closed", WorkflowSource("recursive-closed"))
    workflow.nodes["root"] = VibeNode("root", "Source")
    workflow.definitions = {"subgraphs": [{"name": "inner", "instances": [{"id": "a"}], "nodes": []}]}
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "recursive_instance_unsupported"

    workflow.definitions = {"subgraphs": [{"name": "inner", "nodes": [{"id": "n", "type": "Sink", "inputs": {"x": None}}], "links": []}]}
    workflow.interfaces = {"inner": {"inputs": [{"name": "input", "type": "IMAGE"}]}}
    workflow.boundary_ports = []
    with pytest.raises(WorkflowCompileError) as exc:
        workflow.compile()
    assert exc.value.code == "interface_unknown"


@pytest.mark.parametrize("emitter", [emit_scratchpad_python, emit_ready_template_python])
def test_emitted_python_preserves_mode_and_execution_projection(emitter) -> None:
    workflow = _chain(NodeMode.BYPASSED)
    kwargs = {}
    if emitter is emit_scratchpad_python:
        kwargs.update(prune_dead_branches=False)
    else:
        kwargs.update(
            ready_metadata={"ready_template": "test/b11b"},
            ready_requirements={"models": [], "custom_nodes": []},
            template_id="test/b11b",
        )

    source = emitter(workflow, **kwargs)
    assert "_mode=4" in source
    namespace: dict[str, object] = {"__file__": "b11b_emitted.py"}
    exec(compile(source, "b11b emitted", "exec"), namespace)  # noqa: S102
    rebuilt = namespace["build"]()

    assert rebuilt.nodes["2"].mode is NodeMode.BYPASSED
    assert rebuilt.compile("api") == workflow.compile("api")
