from __future__ import annotations

import builtins
from copy import deepcopy
import importlib.util
import json
import sys
import types
import warnings
from pathlib import Path

import pytest

from vibecomfy.ingest.index import index_workflows
from vibecomfy.ingest.normalize import (
    from_api,
    from_envelope,
    from_ui,
    normalize_to_api,
)
from vibecomfy.registry.library import load_workflow_reference, workflow_from_id
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.handles import Handle
from vibecomfy.workflow import (
    NodeMode,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowCompileError,
    WorkflowRequirements,
    WorkflowSource,
)
import vibecomfy.workflow as workflow_module


class _FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def test_api_workflow_converts_to_vibe_workflow() -> None:
    raw = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }

    workflow = from_api(raw, workflow_id="sample")

    assert workflow.id == "sample"
    assert "positive" not in workflow.nodes["2"].inputs
    assert "images" not in workflow.nodes["3"].inputs
    assert workflow.edges == [
        VibeEdge("1", "0", "2", "positive"),
        VibeEdge("2", "0", "3", "images"),
    ]
    assert workflow.validate().ok
    assert "prompt" in workflow.inputs
    workflow.set_prompt("new").set_seed(42).set_steps(8)
    api = workflow.compile()
    assert api["1"]["inputs"]["text"] == "new"
    assert api["2"]["inputs"]["seed"] == 42
    assert api["2"]["inputs"]["steps"] == 8
    assert api["2"]["inputs"]["positive"] == ["1", 0]
    assert workflow.export_to_json(format="api") == api
    with pytest.raises(ValueError, match="Unsupported workflow JSON export format"):
        workflow.export_to_json(format="ui")


def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
    workflow = VibeWorkflow("edge-only", WorkflowSource("edge-only"))
    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
    workflow.nodes["2"] = VibeNode(
        "2",
        "Sink",
        inputs={
            "literal_pair": [640, 480],
            "label_pair": ["alpha", 0],
            "boolean_pair": ["1", False],
        },
        uid="uid-2",
    )
    workflow.edges.append(VibeEdge("1", "0", "2", "image"))
    before = workflow.copy()

    expected = {
        "1": {"class_type": "Source", "inputs": {}},
        "2": {
            "class_type": "Sink",
            "inputs": {
                "literal_pair": [640, 480],
                "label_pair": ["alpha", 0],
                "boolean_pair": ["1", False],
                "image": ["1", 0],
            },
        },
    }
    assert workflow.compile("api") == expected
    assert workflow == before

    envelope = workflow.to_envelope()
    assert envelope["nodes"]["2"]["inputs"] == {
        "literal_pair": [640, 480],
        "label_pair": ["alpha", 0],
        "boolean_pair": ["1", False],
    }
    restored = from_envelope(envelope)
    assert restored.compile("api") == expected


def test_to_envelope_rejects_edge_with_missing_source_node() -> None:
    workflow = VibeWorkflow("missing-source", WorkflowSource("missing-source"))
    workflow.nodes["2"] = VibeNode("2", "CustomSink", uid="uid-2")
    workflow.edges.append(VibeEdge("1", "0", "2", "image"))

    report = workflow.validate()
    issue = next(issue for issue in report.issues if issue.code == "missing_edge_source")
    assert issue.message == "edge 0: endpoint node ids '1'/'2' must exist in nodes"
    assert issue.detail == {
        "edge_index": 0,
        "source_node_id": "1",
        "target_node_id": "2",
        "missing_source": True,
        "missing_target": False,
    }

    with pytest.raises(
        ValueError,
        match=r"edge 0: endpoint node ids '1'/'2' must exist in nodes",
    ):
        workflow.to_envelope()


def test_to_envelope_rejects_edge_with_missing_destination_node() -> None:
    workflow = VibeWorkflow("missing-destination", WorkflowSource("missing-destination"))
    workflow.nodes["1"] = VibeNode("1", "CustomSource", uid="uid-1")
    workflow.edges.append(VibeEdge("1", "0", "2", "image"))

    with pytest.raises(
        ValueError,
        match=r"edge 0: endpoint node ids '1'/'2' must exist in nodes",
    ):
        workflow.to_envelope()


def test_to_envelope_valid_edge_round_trips_custom_node_payloads() -> None:
    workflow = VibeWorkflow("valid-edge", WorkflowSource("valid-edge"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "VendorSource",
        pack="vendor-pack",
        inputs={"opaque_config": {"levels": [1, {"mode": "custom"}]}},
        widgets={"vendor_widget": ["alpha", {"beta": True}]},
        metadata={"vendor_metadata": {"nested": ["preserve", 7]}},
        uid="uid-1",
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "VendorSink",
        inputs={"literal": {"custom": ["payload", 3]}},
        uid="uid-2",
    )
    workflow.edges.append(VibeEdge("1", "output", "2", "image"))

    envelope = workflow.to_envelope()

    assert envelope["nodes"]["1"]["inputs"] == workflow.nodes["1"].inputs
    assert envelope["nodes"]["1"]["widgets"] == workflow.nodes["1"].widgets
    assert envelope["nodes"]["1"]["metadata"] == workflow.nodes["1"].metadata
    assert from_envelope(envelope).to_envelope() == envelope


def test_to_envelope_empty_graph_round_trips() -> None:
    workflow = VibeWorkflow("empty", WorkflowSource("empty"))

    envelope = workflow.to_envelope()

    assert envelope["nodes"] == {}
    assert envelope["edges"] == []
    assert from_envelope(envelope).to_envelope() == envelope


def test_to_envelope_dangling_edge_rejection_does_not_mutate_workflow() -> None:
    workflow = VibeWorkflow("unchanged", WorkflowSource("unchanged"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "VendorSource",
        inputs={"opaque": {"nested": [1, 2, 3]}},
        uid="uid-1",
    )
    workflow.edges.append(VibeEdge("1", "0", "missing", "image"))
    before = deepcopy(workflow)

    with pytest.raises(ValueError, match="must exist in nodes"):
        workflow.to_envelope()

    assert workflow == before


@pytest.mark.parametrize("edge_source", ["map-key", "internal-id"])
def test_to_envelope_reports_node_identity_mismatch_before_edge_membership(
    edge_source: str,
) -> None:
    workflow = VibeWorkflow("key-wins", WorkflowSource("key-wins"))
    workflow.nodes["map-key"] = VibeNode("internal-id", "Source", uid="u1")
    workflow.nodes["2"] = VibeNode("2", "Sink", uid="u2")
    workflow.edges.append(VibeEdge(edge_source, "0", "2", "image"))
    before = deepcopy(workflow)

    report = workflow.validate()
    identity_issue = next(
        issue for issue in report.issues if issue.code == "node_identity_mismatch"
    )
    assert identity_issue.message == (
        "node mapping key 'map-key' must equal node.id 'internal-id'"
    )
    assert identity_issue.detail == {
        "mapping_key": "map-key",
        "node_id": "internal-id",
    }

    with pytest.raises(
        ValueError,
        match=r"node mapping key 'map-key' must equal node\.id 'internal-id'",
    ):
        workflow.to_envelope()

    assert workflow == before


def test_from_envelope_reports_node_identity_mismatch_before_edge_membership() -> None:
    workflow = VibeWorkflow("key-wins", WorkflowSource("key-wins"))
    workflow.nodes["internal-id"] = VibeNode("internal-id", "Source", uid="u1")
    workflow.nodes["2"] = VibeNode("2", "Sink", uid="u2")
    workflow.edges.append(VibeEdge("internal-id", "0", "2", "image"))
    envelope = workflow.to_envelope()
    envelope["nodes"]["map-key"] = envelope["nodes"].pop("internal-id")
    envelope["edges"][0]["from_node"] = "map-key"

    with pytest.raises(
        ValueError,
        match=r"node mapping key 'map-key' must equal node\.id 'internal-id'",
    ):
        from_envelope(envelope)


def test_duplicate_edge_reorder_changes_fingerprint_and_survives_round_trip() -> None:
    from vibecomfy.ingest.normalize import _door_node_fingerprint

    workflow = VibeWorkflow("dupe-order", WorkflowSource("dupe-order"))
    workflow.nodes["1"] = VibeNode("1", "SourceA", uid="u1")
    workflow.nodes["2"] = VibeNode("2", "SourceB", uid="u2")
    workflow.nodes["3"] = VibeNode("3", "Sink", uid="u3")
    workflow.edges = [
        VibeEdge("1", "0", "3", "image"),
        VibeEdge("2", "0", "3", "image"),
    ]
    decoded = from_envelope(workflow.to_envelope())
    before_fingerprint = _door_node_fingerprint(decoded)
    with pytest.raises(WorkflowCompileError, match="target_input_cardinality"):
        decoded.compile("api")

    decoded.edges.reverse()
    after_fingerprint = _door_node_fingerprint(decoded)
    before_emit = deepcopy(decoded)
    emitted = decoded.to_envelope()

    assert after_fingerprint != before_fingerprint
    assert [edge.from_node for edge in decoded.edges] == ["2", "1"]
    assert [edge["from_node"] for edge in emitted["edges"]] == ["2", "1"]
    assert len(emitted["edges"]) == 2
    with pytest.raises(WorkflowCompileError, match="target_input_cardinality"):
        from_envelope(emitted).compile("api")
    assert decoded == before_emit


def test_untouched_opaque_fields_and_subgraph_payload_are_detached_and_lossless() -> None:
    workflow = VibeWorkflow("opaque", WorkflowSource("opaque"))
    workflow.nodes["1"] = VibeNode("1", "VendorNode", uid="u1")
    envelope = workflow.to_envelope()
    envelope["opaque_top"] = {"nested": ["preserve", 7]}
    envelope["nodes"]["1"]["opaque_node"] = {"vendor": [1, 2, 3]}
    envelope["definitions"] = {
        "subgraphs": [
            {
                "id": "opaque-subgraph",
                "nodes": {"inner-key": {"id": "different-inner-id"}},
                "links": [["missing", "still", "opaque"]],
            }
        ]
    }
    decoded = from_envelope(envelope)

    emitted = decoded.to_envelope()

    assert emitted == envelope
    emitted["opaque_top"]["nested"].append("mutated-return")
    emitted["definitions"]["subgraphs"][0]["links"].append(["mutated"])
    assert decoded.to_envelope() == envelope


def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
    literals = {
        "dimensions": [640, 480],
        "label_and_index": ["alpha", 0],
        "boolean_slot": ["1", False],
    }

    workflow = from_api({"1": {"class_type": "LiteralNode", "inputs": literals}})

    assert workflow.nodes["1"].inputs == literals
    assert workflow.edges == []
    assert workflow.compile("api")["1"]["inputs"] == literals


def test_raw_api_link_input_fails_validation_serialization_and_compile() -> None:
    workflow = VibeWorkflow("raw-link", WorkflowSource("raw-link"))
    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
    workflow.nodes["2"] = VibeNode(
        "2", "Sink", inputs={"image": ["1", 0]}, uid="uid-2"
    )

    report = workflow.validate()
    assert not report.ok
    issue = next(issue for issue in report.issues if issue.code == "embedded_api_link")
    assert issue.detail["edge_collision"] == "none"

    for operation in (workflow.to_envelope, lambda: workflow.compile("api")):
        with pytest.raises(WorkflowCompileError) as exc_info:
            operation()
        assert exc_info.value.code == "embedded_api_link"
        assert exc_info.value.detail["edge_collision"] == "none"


def test_raw_api_link_widget_fails_validation_serialization_and_compile() -> None:
    workflow = VibeWorkflow("raw-widget-link", WorkflowSource("raw-widget-link"))
    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
    workflow.nodes["2"] = VibeNode(
        "2", "Sink", widgets={"image": ["1", 0]}, uid="uid-2"
    )

    report = workflow.validate()
    assert not report.ok
    issue = next(issue for issue in report.issues if issue.code == "embedded_api_link")
    assert issue.detail["storage"] == "widgets"
    assert issue.detail["edge_collision"] == "none"

    for operation in (workflow.to_envelope, lambda: workflow.compile("api")):
        with pytest.raises(WorkflowCompileError) as exc_info:
            operation()
        assert exc_info.value.code == "embedded_api_link"
        assert exc_info.value.detail["storage"] == "widgets"


@pytest.mark.parametrize(
    ("edge", "expected_collision"),
    [
        (VibeEdge("1", "0", "2", "image"), "identical"),
        (VibeEdge("3", "1", "2", "image"), "conflicting"),
    ],
)
def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
    edge: VibeEdge, expected_collision: str
) -> None:
    workflow = VibeWorkflow("collision", WorkflowSource("collision"))
    workflow.nodes["1"] = VibeNode("1", "Source")
    workflow.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
    workflow.nodes["3"] = VibeNode("3", "OtherSource")
    workflow.edges.append(edge)
    before = workflow.copy()

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")

    assert exc_info.value.code == "embedded_api_link"
    assert exc_info.value.detail["edge_collision"] == expected_collision
    assert workflow == before


def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
    workflow = VibeWorkflow("decode", WorkflowSource("decode"))
    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
    workflow.nodes["2"] = VibeNode("2", "Sink", uid="uid-2")
    workflow.edges.append(VibeEdge("1", "0", "2", "image"))
    envelope = workflow.to_envelope()
    envelope["nodes"]["2"]["inputs"]["image"] = ["1", 0]

    with pytest.raises(ValueError, match="embedded_api_link.*identical VibeEdge"):
        from_envelope(envelope)


def test_export_to_json_api_is_compile_api_for_ready_template() -> None:
    from vibecomfy import load_workflow_any

    workflow = load_workflow_any("image/z_image")

    assert workflow.export_to_json(format="api") == workflow.compile("api")


def test_handle_is_generic_for_static_tools() -> None:
    assert Handle[str] is not None


def test_node_builder_handles_include_schema_output_type() -> None:
    workflow = VibeWorkflow("typed", WorkflowSource("typed"))

    image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
    latent = workflow.node("EmptyLatentImage", width=8, height=8, batch_size=1)

    assert image.out(0).output_type == "IMAGE"
    assert latent.out(0).output_type == "LATENT"


def test_strict_types_warns_for_known_incompatible_connections_only() -> None:
    workflow = VibeWorkflow("typed", WorkflowSource("typed"), strict_types=True)
    image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
    latent = workflow.node("EmptyLatentImage", width=8, height=8, batch_size=1)
    sampler = workflow.node("KSampler")
    unknown = workflow.node("UnknownNode")

    with pytest.warns(RuntimeWarning, match="IMAGE.*LATENT"):
        workflow.connect(image.out(0), f"{sampler.id}.latent_image")

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        workflow.connect(latent.out(0), f"{sampler.id}.latent_image")
        workflow.connect(unknown.out(0), f"{sampler.id}.latent_image")

    assert captured == []


def test_api_workflow_import_preserves_schema_output_names() -> None:
    provider = _FakeSchemaProvider(
        {
            "GuideNode": NodeSchema(
                class_type="GuideNode",
                pack=None,
                inputs={},
                outputs=[
                    OutputSpec("CONDITIONING", "positive"),
                    OutputSpec("CONDITIONING", "negative"),
                    OutputSpec("LATENT", "latent"),
                ],
            ),
            "SinkNode": NodeSchema(
                class_type="SinkNode",
                pack=None,
                inputs={"latent": InputSpec("LATENT")},
                outputs=[],
            ),
        }
    )
    workflow = from_api(
        {
            "1": {"class_type": "GuideNode", "inputs": {}},
            "2": {"class_type": "SinkNode", "inputs": {"latent": ["1", 2]}},
        },
        workflow_id="sample",
        schema_provider=provider,
    )

    assert workflow.nodes["1"].metadata["output_names"] == ["positive", "negative", "latent"]
    source = workflow.node("GuideNode")
    source.node.metadata["output_names"] = workflow.nodes["1"].metadata["output_names"]
    assert source.out("latent").output_slot == 2


def test_prompt_override_does_not_bind_conditioning_inputs() -> None:
    raw = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
        "2": {"class_type": "CFGGuider", "inputs": {"positive": {"pooled": []}, "cfg": 5.0}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }

    workflow = from_api(raw, workflow_id="conditioning")

    assert workflow.inputs["prompt"].node_id == "1"
    workflow.set_prompt("new")
    api = workflow.compile()
    assert api["1"]["inputs"]["text"] == "new"
    assert api["2"]["inputs"]["positive"] == {"pooled": []}


def test_register_input_descriptor_default_survives_alias_set_input() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input(
        "filename_prefix",
        "1",
        "filename_prefix",
        "old",
        type="STRING",
        default="old",
        aliases=["prefix"],
        media_semantics="image",
    )

    workflow.set_input("prefix", "new")

    assert workflow.inputs["filename_prefix"].value == "new"
    assert workflow.inputs["filename_prefix"].default == "old"
    assert workflow.inputs["filename_prefix"].media_semantics == "image"
    assert workflow.nodes["1"].inputs["filename_prefix"] == "new"
    assert workflow.compile("api")["1"]["inputs"]["filename_prefix"] == "new"


def test_set_input_rejects_unknown_name_without_unbound_metadata_write() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input(
        "filename_prefix",
        "1",
        "filename_prefix",
        "old",
        aliases=["prefix"],
    )

    with pytest.raises(ValueError) as exc_info:
        workflow.set_input("missing", "new")

    message = str(exc_info.value)
    assert "no registered public input or alias" in message
    assert "Available public inputs: 'filename_prefix'" in message
    assert "'prefix' -> 'filename_prefix'" in message
    assert "unbound_inputs" not in workflow.metadata
    assert workflow.nodes["1"].inputs["filename_prefix"] == "old"


def test_set_input_rejects_unknown_alias() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])

    with pytest.raises(ValueError, match="Available aliases: 'prefix' -> 'filename_prefix'"):
        workflow.set_input("file_prefix", "new")


def test_set_input_rejects_stale_missing_target_node() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])
    workflow.nodes.pop("1")

    with pytest.raises(ValueError) as exc_info:
        workflow.set_input("prefix", "new")

    message = str(exc_info.value)
    assert "target node '1' is missing" in message
    assert "Registered target: 1.filename_prefix" in message
    assert "unbound_inputs" not in workflow.metadata


def test_set_input_rejects_stale_missing_target_field() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "SaveImage",
        inputs={"filename_prefix": "old", "other": "old"},
        widgets={"preview": True},
    )
    workflow.register_input("filename_prefix", "1", "filename_prefix", "old")
    workflow.nodes["1"].inputs.pop("filename_prefix")

    with pytest.raises(ValueError) as exc_info:
        workflow.set_input("filename_prefix", "new")

    message = str(exc_info.value)
    assert "target field 'filename_prefix' is missing" in message
    assert "node '1' (SaveImage)" in message
    assert "Available fields on node '1': 'other', 'preview'" in message
    assert "unbound_inputs" not in workflow.metadata


def test_set_input_rejects_stale_missing_target_field_after_node_replacement() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])
    workflow.nodes["1"] = VibeNode(
        "1",
        "PreviewImage",
        inputs={"images": "placeholder"},
        widgets={"preview": False},
    )

    with pytest.raises(ValueError) as exc_info:
        workflow.set_input("prefix", "new")

    message = str(exc_info.value)
    assert "target field 'filename_prefix' is missing" in message
    assert "node '1' (PreviewImage)" in message
    assert "Available fields on node '1': 'images', 'preview'" in message


def test_set_input_rejects_ambiguous_alias_with_matching_public_inputs() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "one"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "two"})
    workflow.register_input("first", "1", "filename_prefix", "one", aliases=["prefix"])
    workflow.inputs["second"] = VibeInput(
        name="second",
        node_id="2",
        field="filename_prefix",
        value="two",
        aliases=("prefix",),
    )

    with pytest.raises(ValueError) as exc_info:
        workflow.set_input("prefix", "new")

    message = str(exc_info.value)
    assert "alias 'prefix' is ambiguous" in message
    assert "first" in message
    assert "second" in message


def test_set_input_updates_primary_name_when_aliases_exist() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])

    workflow.set_input("filename_prefix", "new")

    assert workflow.inputs["filename_prefix"].value == "new"
    assert workflow.nodes["1"].inputs["filename_prefix"] == "new"
    assert workflow.compile("api")["1"]["inputs"]["filename_prefix"] == "new"


def test_register_input_rejects_bad_target() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})

    with pytest.raises(ValueError, match="does not exist"):
        workflow.register_input("missing", "404", "filename_prefix", "old")

    with pytest.raises(ValueError, match="not found"):
        workflow.register_input("bad_field", "1", "missing", "old")


def test_register_input_rejects_alias_collisions() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "one"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "two"})
    workflow.register_input("first", "1", "filename_prefix", "one", aliases=["prefix"])

    with pytest.raises(ValueError, match="existing alias"):
        workflow.register_input("second", "2", "filename_prefix", "two", aliases=["prefix"])
    with pytest.raises(ValueError, match="existing primary input"):
        workflow.register_input("second", "2", "filename_prefix", "two", aliases=["first"])
    with pytest.raises(ValueError, match="existing alias"):
        workflow.register_input("prefix", "2", "filename_prefix", "two")


def test_workflow_copy_deep_copies_mutable_state_and_preserves_original() -> None:
    workflow = VibeWorkflow("original", WorkflowSource("original", provenance={"origin": ["unit"]}))
    workflow.nodes["1"] = VibeNode(
        "1",
        "SourceNode",
        inputs={"seed": {"value": 1}},
        widgets={"steps": [4]},
        metadata={"tags": ["source"]},
        uid="uid-1",
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "SaveImage",
        inputs={"filename_prefix": "orig"},
        metadata={"tags": ["sink"]},
        uid="uid-2",
    )
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    workflow.register_input(
        "seed",
        "1",
        "seed",
        value={"current": 1},
        default={"original": 1},
        aliases=["seed_alias"],
        range={"min": 0},
    )
    workflow.outputs.append(
        VibeOutput(
            node_id="2",
            output_type="IMAGE",
            name="preview",
            expected_cardinality={"count": 1},
        )
    )
    workflow.requirements = WorkflowRequirements(
        models=["base"],
        custom_nodes=["pack-a"],
        missing_models=["missing-a"],
        missing_nodes=["missing-node"],
        unsupported=["unsupported-a"],
    )
    workflow.metadata = {
        "flags": ["original"],
        "nested": {"keep": True},
        "id_map": {"seed_node": "1"},
    }
    workflow._set_id_map({"seed_node": "1"})
    workflow._manual_input_names.add("seed")
    workflow._uid_counter = 7

    cloned = workflow.copy()

    assert cloned is not workflow
    assert cloned.clone() is not cloned
    assert cloned.source is not workflow.source
    assert cloned.nodes["1"] is not workflow.nodes["1"]
    assert cloned.inputs["seed"] is not workflow.inputs["seed"]
    assert cloned.outputs[0] is not workflow.outputs[0]
    assert cloned.requirements is not workflow.requirements
    assert cloned.metadata is not workflow.metadata
    assert cloned.edges[0] is not workflow.edges[0]
    assert cloned.id_map() == {"seed_node": "1"}
    assert cloned._manual_input_names == {"seed"}
    assert cloned._uid_counter == 7

    cloned.nodes["1"].inputs["seed"]["value"] = 99
    cloned.nodes["1"].widgets["steps"].append(8)
    cloned.nodes["1"].metadata["tags"].append("clone")
    cloned.inputs["seed"].value["current"] = 99
    cloned.inputs["seed"].default["original"] = 99
    cloned.inputs["seed"].range["min"] = -1
    cloned.outputs[0].expected_cardinality["count"] = 2
    cloned.requirements.models.append("clone-model")
    cloned.metadata["flags"].append("clone")
    cloned.metadata["nested"]["keep"] = False
    cloned._id_map["seed_node"] = "2"
    cloned._manual_input_names.add("extra")
    cloned._uid_counter = 100
    cloned.source.provenance["origin"].append("clone")
    cloned.edges[0].from_node = "9"

    assert workflow.nodes["1"].inputs["seed"] == {"value": 1}
    assert workflow.nodes["1"].widgets["steps"] == [4]
    assert workflow.nodes["1"].metadata["tags"] == ["source"]
    assert workflow.inputs["seed"].value == {"current": 1}
    assert workflow.inputs["seed"].default == {"original": 1}
    assert workflow.inputs["seed"].range == {"min": 0}
    assert workflow.outputs[0].expected_cardinality == {"count": 1}
    assert workflow.requirements.models == ["base"]
    assert workflow.metadata["flags"] == ["original"]
    assert workflow.metadata["nested"] == {"keep": True}
    assert workflow.id_map() == {"seed_node": "1"}
    assert workflow._manual_input_names == {"seed"}
    assert workflow._uid_counter == 7
    assert workflow.source.provenance == {"origin": ["unit"]}
    assert workflow.edges[0].from_node == "1"


def test_copy_is_derived_and_preserves_mode_and_groups_deeply() -> None:
    """P10: copy() is derived — mode/groups ride along without a hand-list edit,
    and the copy is deep (mutating the clone never touches the original)."""
    workflow = VibeWorkflow("derived", WorkflowSource("derived"))
    workflow.nodes["1"] = VibeNode(
        "1", "KSampler", inputs={"seed": 1}, uid="uid-1", mode=4
    )
    workflow.nodes["2"] = VibeNode(
        "2", "SaveImage", uid="uid-2", mode=0
    )
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    workflow.groups = [
        {"title": "input-group", "nodes": [1, 2], "color": "#3f789e"},
    ]

    cloned = workflow.copy()

    assert cloned.nodes["1"].mode == 4
    assert cloned.nodes["2"].mode == 0
    assert cloned.groups == workflow.groups

    # Deep: mutating the clone's mode/groups leaves the original untouched.
    cloned.nodes["1"].mode = 0
    cloned.groups[0]["color"] = "#000000"
    cloned.groups.append({"title": "extra"})
    assert workflow.nodes["1"].mode == 4
    assert workflow.groups == [
        {"title": "input-group", "nodes": [1, 2], "color": "#3f789e"}
    ]


def test_geometry_copy_and_compile_are_deep_and_execution_invariant() -> None:
    workflow = VibeWorkflow("geometry", WorkflowSource("geometry"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "SaveImage",
        uid="uid-1",
        pos=[10.0, 20.0],
        size=[300.0, 180.0],
    )
    compiled = workflow.compile("api")

    cloned = workflow.copy()
    cloned.nodes["1"].pos[0] = 999.0  # type: ignore[index]
    cloned.nodes["1"].size[1] = 999.0  # type: ignore[index]

    assert workflow.nodes["1"].pos == [10.0, 20.0]
    assert workflow.nodes["1"].size == [300.0, 180.0]
    assert cloned.compile("api") == compiled == workflow.compile("api")


def test_geometry_envelope_new_fields_win_and_legacy_fallback_is_independent() -> None:
    workflow = VibeWorkflow("geometry-envelope", WorkflowSource("geometry-envelope"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "SaveImage",
        uid="uid-1",
        metadata={"_ui": {"pos": [1, 2], "size": [3, 4]}},
        pos=[10.0, 20.0],
        size=[300.0, 180.0],
    )
    envelope = workflow.to_envelope()
    assert envelope["nodes"]["1"]["pos"] == [10.0, 20.0]
    assert envelope["nodes"]["1"]["size"] == [300.0, 180.0]

    restored = from_envelope(envelope)
    assert restored.nodes["1"].pos == [10.0, 20.0]
    assert restored.nodes["1"].size == [300.0, 180.0]

    old_mixed = deepcopy(envelope)
    del old_mixed["nodes"]["1"]["pos"]
    old_mixed["nodes"]["1"]["size"] = [30, 40]
    old_mixed["nodes"]["1"]["metadata"]["_ui"] = {
        "pos": [5, 6],
        "size": [500, 600],
    }
    restored_old = from_envelope(old_mixed)
    assert restored_old.nodes["1"].pos == [5.0, 6.0]
    assert restored_old.nodes["1"].size == [30.0, 40.0]

    explicit_absence = deepcopy(old_mixed)
    explicit_absence["nodes"]["1"]["pos"] = None
    assert from_envelope(explicit_absence).nodes["1"].pos is None


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("pos", [1]),
        ("pos", [1, 2, 3]),
        ("pos", [True, 2]),
        ("size", ["1", 2]),
        ("size", [float("inf"), 2]),
        ("size", [float("nan"), 2]),
    ],
)
def test_versioned_envelope_rejects_malformed_present_geometry(
    field_name: str, value: object
) -> None:
    workflow = VibeWorkflow("bad-geometry", WorkflowSource("bad-geometry"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", uid="uid-1")
    envelope = workflow.to_envelope()
    envelope["nodes"]["1"][field_name] = value

    with pytest.raises(ValueError, match=field_name):
        from_envelope(envelope)


def test_validation_and_envelope_writer_reject_invalid_programmatic_geometry() -> None:
    workflow = VibeWorkflow("bad-geometry", WorkflowSource("bad-geometry"))
    workflow.nodes["1"] = VibeNode(
        "1", "SaveImage", uid="uid-1", pos=[1.0], size=[2.0, 3.0]
    )

    report = workflow.validate()
    assert any(issue.code == "invalid_geometry" for issue in report.issues)
    with pytest.raises(ValueError, match="pos"):
        workflow.to_envelope()


def test_node_mode_and_groups_survive_envelope_round_trip() -> None:
    """P10: node.mode and workflow.groups are serialized by to_envelope and
    restored by from_envelope (dataclass walk — no hand-listed fields)."""
    from vibecomfy.ingest.normalize import from_envelope

    wf = VibeWorkflow("roundtrip", WorkflowSource("roundtrip"))
    wf.nodes["1"] = VibeNode(
        "1", "LoadImage", inputs={"image": "a.png"}, uid="uid-1", mode=4
    )
    wf.nodes["2"] = VibeNode(
        "2", "PreviewImage", uid="uid-2", mode=2
    )
    wf.edges.append(VibeEdge("1", "0", "2", "images"))
    wf.groups = [
        {"title": "g1", "nodes": [1, 2], "color": "#112233"},
        {"title": "g2", "bounding": [0, 0, 100, 100]},
    ]

    envelope = wf.to_envelope()
    assert envelope["groups"] == wf.groups
    assert envelope["nodes"]["1"]["mode"] == 4
    assert envelope["nodes"]["2"]["mode"] == 2

    restored = from_envelope(envelope)
    assert restored.nodes["1"].mode == 4
    assert restored.nodes["2"].mode == 2
    assert restored.groups == wf.groups


def test_semantic_node_mode_survives_envelope_and_json_round_trip() -> None:
    """Python-authored NodeMode values are first-class envelope data.

    ``to_envelope``'s dataclass walk emits the enum; JSON stores the semantic
    string.  Decode must restore that field and must not consult stale
    ``_ui.mode`` furniture when the first-class value is present.
    """
    bypassed = VibeWorkflow("semantic-bypass", WorkflowSource("semantic-bypass"))
    bypassed.nodes["1"] = VibeNode(
        "1", "LoadImage", inputs={"image": "a.png"}, uid="uid-1", mode=NodeMode.BYPASSED
    )
    envelope = bypassed.to_envelope()
    assert envelope["nodes"]["1"]["mode"] is NodeMode.BYPASSED

    restored = from_envelope(envelope)
    assert restored.nodes["1"].mode is NodeMode.BYPASSED
    assert "1" not in restored.compile("api")

    raw = json.loads(json.dumps(envelope))
    assert raw["nodes"]["1"]["mode"] == "bypassed"
    from_json = from_envelope(raw)
    assert from_json.nodes["1"].mode is NodeMode.BYPASSED
    assert "1" not in from_json.compile("api")

    conflict = VibeWorkflow("semantic-enabled", WorkflowSource("semantic-enabled"))
    enabled = VibeNode(
        "1", "LoadImage", inputs={"image": "a.png"}, uid="uid-1", mode=NodeMode.ENABLED
    )
    enabled.metadata["_ui"] = {"mode": 4}
    conflict.nodes["1"] = enabled
    conflict_raw = json.loads(json.dumps(conflict.to_envelope()))
    assert conflict_raw["nodes"]["1"]["mode"] == "enabled"
    conflict_restored = from_envelope(conflict_raw)
    assert conflict_restored.nodes["1"].mode is NodeMode.ENABLED
    assert "1" in conflict_restored.compile("api")


def test_90a1d5_mode_distribution_and_compile_survive_p10() -> None:
    """P10 gate: the 90a1d5 envelope decodes 15 nodes with mode dist {4:9, 0:6};
    compile still emits 2 (bypass rewiring)."""
    from collections import Counter

    from vibecomfy.ingest.normalize import from_envelope

    envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    wf = from_envelope(envelope)

    assert len(wf.nodes) == 15
    assert dict(Counter(node.mode for node in wf.nodes.values())) == {4: 9, 0: 6}
    assert len(wf.compile("api")) == 2


def test_ui_workflow_normalizes_to_api() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "CLIPTextEncode", "widgets_values": ["hello"], "inputs": []},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "link": 1}]},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
    }

    api = normalize_to_api(raw)
    assert api["1"]["class_type"] == "CLIPTextEncode"
    assert api["2"]["inputs"]["images"] == ["1", 0]
    via_named = from_ui(raw)
    assert set(via_named.nodes) == {"1", "2"}
    assert [node.class_type for node in via_named.nodes.values()] == [
        "CLIPTextEncode",
        "SaveImage",
    ]
    assert "images" not in via_named.nodes["2"].inputs
    assert via_named.edges == [VibeEdge("1", "0", "2", "images")]


def test_empty_workflow_shapes_are_valid_authoring_inputs() -> None:
    assert normalize_to_api({}) == {}
    assert normalize_to_api({"nodes": [], "links": []}) == {}
    assert from_api({}).nodes == {}
    assert from_ui({"nodes": [], "links": []}).nodes == {}


@pytest.mark.skipif(
    importlib.util.find_spec("comfy_execution") is None,
    reason="GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.",
)
def test_graphbuilder_backend_matches_api_backend() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SourceNode", inputs={"value": 1})
    workflow.nodes["2"] = VibeNode("2", "SinkNode", inputs={})
    workflow.connect("1.0", "2.input")

    assert workflow.compile("graphbuilder") == workflow.compile("api")


def test_node_builder_named_outputs_use_registered_output_names() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    source = workflow.node("Source")
    source.node.metadata["output_names"] = ["positive", "negative", "latent"]
    sink = workflow.node("Sink", positive=source.out("positive"), latent=source.out("latent"))

    api = workflow.compile("api")

    assert api[sink.id]["inputs"]["positive"] == [source.id, 0]
    assert api[sink.id]["inputs"]["latent"] == [source.id, 2]
    assert source.out("latent").name == "latent"


def test_explicit_inputs_override_imported_widget_values_at_compile_time() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={"widget_0": "scratchpad.png", "image": "scratchpad.png"},
        widgets={"widget_0": "imported.png"},
    )

    api = workflow.compile("api")

    assert "widget_0" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["image"] == "scratchpad.png"


def test_compile_drops_video_preview_ui_payloads() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["2"] = VibeNode("2", "Source")
    workflow.nodes["1"] = VibeNode(
        "1",
        "VHS_VideoCombine",
        inputs={
            "videopreview": {
                "hidden": False,
                "params": {"filename": "preview.mp4"},
                "paused": False,
            },
        },
    )
    workflow.edges.append(VibeEdge("2", "0", "1", "images"))

    api = workflow.compile("api")

    assert "videopreview" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["images"] == ["2", 0]


def test_compile_drops_null_prompt_inputs() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["2"] = VibeNode("2", "Source")
    workflow.nodes["3"] = VibeNode("3", "Source")
    workflow.nodes["1"] = VibeNode(
        "1",
        "ImageConcatMulti",
        inputs={
            "widget_3": None,
        },
    )
    workflow.edges.extend(
        [
            VibeEdge("2", "0", "1", "image_1"),
            VibeEdge("3", "0", "1", "image_2"),
        ]
    )

    api = workflow.compile("api")

    assert "widget_3" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["image_1"] == ["2", 0]


def test_compile_drops_note_nodes_from_api_prompt() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage")
    workflow.nodes["3"] = VibeNode("3", "Source")
    workflow.edges.append(VibeEdge("3", "0", "2", "images"))

    api = workflow.compile("api")

    assert "1" not in api
    assert api["2"]["class_type"] == "SaveImage"


def test_compile_drops_markdown_note_nodes_from_api_prompt() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage")
    workflow.nodes["3"] = VibeNode("3", "Source")
    workflow.edges.append(VibeEdge("3", "0", "2", "images"))

    api = workflow.compile("api")

    assert "1" not in api
    assert api["2"]["class_type"] == "SaveImage"


def test_validate_rejects_opaque_component_class_types() -> None:
    workflow = VibeWorkflow(id="test", source=WorkflowSource(id="test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "19e3f7e8-881c-4a61-a360-1c463734043a",
    )

    report = workflow.validate()

    assert report.ok
    assert [issue.code for issue in report.issues] == ["opaque_component_class_type"]
    assert [issue.severity for issue in report.issues] == ["warning"]


def test_validate_rejects_kj_loader_for_ltx_audio_vae() -> None:
    workflow = VibeWorkflow("ltx-audio", WorkflowSource("ltx-audio"))
    workflow.nodes["175"] = VibeNode(
        "175",
        "VAELoaderKJ",
        inputs={"vae_name": "LTX23_audio_vae_bf16.safetensors"},
    )

    report = workflow.validate()

    assert not report.ok
    assert [issue.code for issue in report.issues] == ["ltx_audio_vae_wrong_loader"]


def test_compile_rewrites_set_get_nodes_to_direct_links() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode(
        "2",
        "SetNode",
        inputs={"widget_0": "reference_image"},
    )
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("3.0", "4.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "4"}
    assert api["4"]["inputs"]["images"] == ["1", 0]


def test_compile_rewrites_edge_fed_set_get_nodes_to_direct_links() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage")
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("3.0", "4.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "4"}
    assert api["4"]["inputs"]["images"] == ["1", 0]


def test_compile_rewrites_set_get_source_through_bypassed_nodes() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "ImageFilter", inputs={}, mode=NodeMode.BYPASSED)
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={})
    workflow.connect("1.0", "2.image")
    workflow.connect("2.0", "3.IMAGE")
    workflow.connect("4.0", "5.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "5"}
    assert api["5"]["inputs"]["images"] == ["1", 0]


def test_stale_ui_mode_does_not_bypass_set_get_when_ir_mode_is_enabled() -> None:
    """Hand-built ``_ui.mode`` furniture is not a compile authority.

    Production ingest copies UI mode into the first-class field. A constructed
    ``VibeNode`` defaults to ENABLED, so leftover LiteGraph furniture must not
    drop the node or rewrite Set/Get around it.
    """
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    live = VibeNode("2", "ImageFilter", inputs={})
    live.metadata["_ui"] = {"mode": 4}
    workflow.nodes["2"] = live
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={})
    workflow.connect("1.0", "2.image")
    workflow.connect("2.0", "3.IMAGE")
    workflow.connect("4.0", "5.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "2", "5"}
    assert api["5"]["inputs"]["images"] == ["2", 0]


@pytest.mark.parametrize(
    ("path", "target_node_id", "target_input", "expected_source"),
    [
        (
            Path("/tmp/runexx-ltx23/LTX-2.3_-_I2V_T2V_Basic_for_checkpoint_models.json"),
            "103",
            "model",
            ["337", 0],
        ),
        (
            Path("/tmp/runexx-ltx23/LTX-2.3_-_I2V_multi-subject-reference_Licon-MSR-lora.json"),
            "10",
            "model",
            ["59", 0],
        ),
    ],
)
def test_compile_original_runexx_ui_with_bypassed_set_get_sources(
    path: Path,
    target_node_id: str,
    target_input: str,
    expected_source: list[object],
) -> None:
    if not path.exists():
        pytest.skip(f"RuneXX regression fixture not present: {path}")

    from vibecomfy import load_workflow_any

    workflow = load_workflow_any(path)

    api = workflow.compile("api")

    assert api[target_node_id]["inputs"][target_input] == expected_source


def test_helper_diagnostics_report_unresolved_broadcasts_before_compile() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "GetNode", inputs={"widget_0": "missing_image"})
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={})
    workflow.connect("2.0", "3.images")

    diagnostics = workflow.helper_diagnostics()
    assert [(issue.code, issue.severity, issue.detail["node_id"]) for issue in diagnostics] == [
        ("helper_broadcast_unresolved", "warning", "2")
    ]

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")
    assert exc_info.value.code == "helper_edge_unresolved"

    report = workflow.validate(schema_provider=None)
    compile_issues = [issue for issue in report.issues if issue.code == "api_compile_failed"]
    assert not report.ok
    assert len(compile_issues) == 1
    assert compile_issues[0].severity == "error"
    assert compile_issues[0].detail["compile_code"] == "helper_edge_unresolved"
    assert compile_issues[0].detail["helper_node_id"] == "2"


def test_compile_rewrites_multi_hop_set_get_edge_chains() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "first"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "first"})
    workflow.nodes["4"] = VibeNode("4", "SetNode", inputs={"widget_0": "second"})
    workflow.nodes["5"] = VibeNode("5", "GetNode", inputs={"widget_0": "second"})
    workflow.nodes["6"] = VibeNode("6", "SaveImage", inputs={})
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("3.0", "4.IMAGE")
    workflow.connect("5.0", "6.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "6"}
    assert api["6"]["inputs"]["images"] == ["1", 0]


def test_graphbuilder_backend_uses_shared_resolved_edge_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    graph_utils = types.ModuleType("comfy_execution.graph_utils")

    class FakeGraphBuilder:
        def __init__(self, prefix: str = "") -> None:
            self.prefix = prefix
            self.nodes: dict[str, dict[str, object]] = {}

        def node(self, class_type: str, id: str, **inputs: object) -> None:
            self.nodes[str(id)] = {"class_type": class_type, "inputs": inputs}

        def finalize(self) -> dict[str, dict[str, object]]:
            return self.nodes

    graph_utils.GraphBuilder = FakeGraphBuilder
    monkeypatch.setitem(sys.modules, "comfy_execution", types.ModuleType("comfy_execution"))
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", graph_utils)

    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "first"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "first"})
    workflow.nodes["4"] = VibeNode("4", "SetNode", inputs={"widget_0": "second"})
    workflow.nodes["5"] = VibeNode("5", "GetNode", inputs={"widget_0": "second"})
    workflow.nodes["6"] = VibeNode("6", "SaveImage", inputs={})
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("3.0", "4.IMAGE")
    workflow.connect("5.0", "6.images")

    assert workflow.compile("graphbuilder") == workflow.compile("api")


def test_compile_raises_stable_code_for_helper_edge_cycles() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SetNode", inputs={"widget_0": "first"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "second"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "first"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
    workflow.connect("2.0", "1.IMAGE")
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("3.0", "4.images")

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")

    assert exc_info.value.code == "helper_edge_cycle"
    assert exc_info.value.detail["target_node_id"] == "4"
    assert exc_info.value.detail["target_input"] == "images"


def test_compile_raises_stable_code_for_missing_edge_endpoint() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={})
    workflow.edges.append(VibeEdge("missing", "0", "1", "images"))

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")

    assert exc_info.value.code == "compiled_edge_missing_endpoint"
    assert exc_info.value.detail["source_node_id"] == "missing"


def test_compile_ignores_stripped_intent_edge_when_target_has_literal_input() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "vibecomfy.loop")
    workflow.nodes["2"] = VibeNode("2", "CLIPTextEncode", inputs={"text": "literal fallback"})
    workflow.connect("1.0", "2.text")

    assert workflow.compile("api") == {
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "literal fallback"},
        }
    }


def test_compile_raises_for_stripped_intent_edge_without_target_literal_input() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "vibecomfy.loop")
    workflow.nodes["2"] = VibeNode("2", "CLIPTextEncode", inputs={})
    workflow.connect("1.0", "2.text")

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")

    assert exc_info.value.code == "compiled_edge_missing_endpoint"
    assert exc_info.value.detail["source_node_id"] == "1"
    assert exc_info.value.detail["target_node_id"] == "2"
    assert exc_info.value.detail["target_input"] == "text"


def test_compile_keeps_non_intent_vibecomfy_nodes_in_api_output() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "vibecomfy.exec", inputs={"source": "return 1"})
    workflow.nodes["2"] = VibeNode("2", "vibecomfy.loop")
    workflow.nodes["9"] = VibeNode("9", "Source")
    workflow.edges.append(VibeEdge("9", "0", "1", "in_0"))

    compiled = workflow.compile("api")

    assert compiled["1"] == {
        "class_type": "vibecomfy.exec",
        "inputs": {"in_0": ["9", 0], "source": "return 1"},
    }
    assert "2" not in compiled


def test_intent_classification_fallback_only_matches_known_vibecomfy_intents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "vibecomfy.contracts.intent_nodes":
            raise ImportError("test fallback")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert workflow_module._is_intent_node_class_type("vibecomfy.code") is True
    assert workflow_module._is_intent_node_class_type("vibecomfy.loop") is True
    assert workflow_module._is_intent_node_class_type("vibecomfy.exec") is False


def test_validate_records_api_compile_failures_without_schema_provider() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={})
    workflow.edges.append(VibeEdge("missing", "0", "1", "images"))

    report = workflow.validate(schema_provider=None)

    compile_issues = [issue for issue in report.issues if issue.code == "api_compile_failed"]
    assert not report.ok
    assert len(compile_issues) == 1
    assert compile_issues[0].severity == "error"
    assert compile_issues[0].detail["compile_code"] == "compiled_edge_missing_endpoint"
    assert compile_issues[0].detail["source_node_id"] == "missing"


def test_validate_keeps_schema_checks_conditional(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.schema import validate as schema_validate

    calls: list[str] = []

    def fake_validate_against_schema(workflow, schema_provider):
        calls.append("schema")
        return []

    def fake_validate_api_link_shapes(api, schema_provider):
        calls.append("links")
        return []

    monkeypatch.setattr(schema_validate, "validate_against_schema", fake_validate_against_schema)
    monkeypatch.setattr(schema_validate, "validate_api_link_shapes", fake_validate_api_link_shapes)

    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={})
    workflow.connect("1.0", "2.images")

    assert workflow.validate(schema_provider=None).ok
    assert calls == []

    provider = _FakeSchemaProvider({})
    assert workflow.validate(schema_provider=provider).ok
    assert calls == ["schema", "links"]


def test_runtime_views_strip_helper_nodes_without_changing_compile_rewrite() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["5"] = VibeNode("5", "SaveImage")
    workflow.connect("2.0", "3.IMAGE")
    workflow.connect("4.0", "5.images")

    api = workflow.compile("api")
    diagnostics = workflow.helper_diagnostics()

    assert sorted(workflow.runtime_nodes()) == ["2", "5"]
    assert workflow.runtime_class_types() == ["LoadImage", "SaveImage"]
    assert set(api) == {"2", "5"}
    assert api["5"]["inputs"]["images"] == ["2", 0]
    assert [(issue.code, issue.severity) for issue in diagnostics] == [
        ("ui_only_node_stripped", "info"),
        ("helper_broadcast_resolved", "info"),
        ("helper_broadcast_resolved", "info"),
    ]


def test_compile_strips_only_ui_and_broadcast_helpers_not_conversion_helpers() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor note"})
    workflow.nodes["2"] = VibeNode("2", "MarkdownNote", inputs={"widget_0": "editor note"})
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "bus"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "bus"})
    workflow.nodes["5"] = VibeNode("5", "Reroute", inputs={})
    workflow.nodes["6"] = VibeNode("6", "PrimitiveNode", inputs={"value": 7})
    workflow.nodes["7"] = VibeNode("7", "PrimitiveInt", inputs={"value": 8})

    api = workflow.compile("api")

    assert set(api) == {"5", "6", "7"}
    assert api["5"]["class_type"] == "Reroute"
    assert api["6"]["class_type"] == "PrimitiveNode"
    assert api["7"]["class_type"] == "PrimitiveInt"


def test_compile_resolves_supported_note_markdown_set_get_helper_chain() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "Note", inputs={"widget_0": "editor note"})
    workflow.nodes["3"] = VibeNode("3", "MarkdownNote", inputs={"widget_0": "## doc"})
    workflow.nodes["4"] = VibeNode("4", "SetNode", inputs={"widget_0": "bus"})
    workflow.nodes["5"] = VibeNode("5", "GetNode", inputs={"widget_0": "bus"})
    workflow.nodes["6"] = VibeNode("6", "SaveImage", inputs={})
    workflow.connect("1.0", "4.IMAGE")
    workflow.connect("5.0", "6.images")

    api = workflow.compile("api")
    report = workflow.validate(schema_provider=None)

    assert set(api) == {"1", "6"}
    assert api["6"]["inputs"]["images"] == ["1", 0]
    assert report.ok
    assert not [issue for issue in report.issues if issue.code == "api_compile_failed"]


def test_compile_strips_standalone_helpers_silently() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "loose note"})
    workflow.nodes["2"] = VibeNode("2", "MarkdownNote", inputs={"widget_0": "## loose doc"})
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "loose_bus"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "loose_bus"})
    workflow.nodes["5"] = VibeNode("5", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["6"] = VibeNode("6", "SaveImage")
    workflow.connect("5.0", "6.images")

    api = workflow.compile("api")
    report = workflow.validate(schema_provider=None)

    assert set(api) == {"5", "6"}
    assert api["6"]["inputs"]["images"] == ["5", 0]
    assert report.ok
    assert not [issue for issue in report.issues if issue.code == "api_compile_failed"]


def test_compile_raises_for_unrewirable_helper_path_through_ui_only_source() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor note"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "bus"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "bus"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("3.0", "4.images")

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")

    assert exc_info.value.code == "helper_edge_unresolved"
    assert exc_info.value.detail["helper_node_id"] == "1"
    assert exc_info.value.detail["class_type"] == "Note"
    assert exc_info.value.detail["target_node_id"] == "4"
    assert exc_info.value.detail["target_input"] == "images"


def test_compile_raises_when_traced_helper_source_missing_from_compiled_api() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SetNode", inputs={"widget_0": "bus"})
    workflow.nodes["2"] = VibeNode("2", "GetNode", inputs={"widget_0": "bus"})
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={})
    workflow.edges.append(VibeEdge("missing", "0", "1", "IMAGE"))
    workflow.connect("2.0", "3.images")

    with pytest.raises(WorkflowCompileError) as exc_info:
        workflow.compile("api")

    assert exc_info.value.code == "compiled_edge_missing_endpoint"
    assert exc_info.value.detail["source_node_id"] == "missing"
    assert exc_info.value.detail["target_node_id"] == "3"
    assert exc_info.value.detail["target_input"] == "images"


def test_compile_backend_parity_for_helper_edge_target_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    graph_utils = types.ModuleType("comfy_execution.graph_utils")

    class FakeGraphBuilder:
        def __init__(self, prefix: str = "") -> None:
            self.prefix = prefix
            self.nodes: dict[str, dict[str, object]] = {}

        def node(self, class_type: str, id: str, **inputs: object) -> None:
            self.nodes[str(id)] = {"class_type": class_type, "inputs": inputs}

        def finalize(self) -> dict[str, dict[str, object]]:
            return self.nodes

    graph_utils.GraphBuilder = FakeGraphBuilder
    monkeypatch.setitem(sys.modules, "comfy_execution", types.ModuleType("comfy_execution"))
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", graph_utils)

    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "Note", inputs={"widget_0": "editor note"})
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "bus"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "bus"})
    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={})
    workflow.connect("1.0", "3.IMAGE")
    workflow.connect("4.0", "5.images")

    api = workflow.compile("api")
    graph = workflow.compile("graphbuilder")

    def target_inputs(compiled: dict[str, dict]) -> dict[str, dict]:
        return {node_id: payload["inputs"] for node_id, payload in compiled.items()}

    assert target_inputs(graph) == target_inputs(api)
    assert target_inputs(api)["5"]["images"] == ["1", 0]


def test_compile_replaces_known_positional_widget_aliases() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "LTXVChunkFeedForward",
        inputs={"widget_0": 2, "widget_1": 4096},
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"] == {"chunks": 2, "dim_threshold": 4096}


def test_compile_replaces_ltx_runtime_positional_widget_aliases() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "LTXVImgToVideoConditionOnly",
        inputs={"widget_0": 1.0, "widget_1": False},
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "LTXAVTextEncoderLoader",
        inputs={"widget_0": "gemma.safetensors", "widget_1": "ltx.safetensors", "widget_2": "default"},
    )
    workflow.nodes["3"] = VibeNode(
        "3",
        "LTXVTiledVAEDecode",
        inputs={"widget_0": 2, "widget_1": 2, "widget_2": 6, "widget_3": False, "widget_4": "auto"},
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"] == {"strength": 1.0, "bypass": False}
    assert api["2"]["inputs"] == {
        "text_encoder": "gemma.safetensors",
        "ckpt_name": "ltx.safetensors",
        "device": "default",
    }
    assert api["3"]["inputs"] == {
        "horizontal_tiles": 2,
        "vertical_tiles": 2,
        "overlap": 6,
        "last_frame_fix": False,
        "working_device": "auto",
    }


def test_compile_rewrites_set_node_passthrough_outputs_to_direct_links() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={})
    workflow.connect("1.0", "2.IMAGE")
    workflow.connect("2.0", "3.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "3"}
    assert api["3"]["inputs"]["images"] == ["1", 0]


def test_compile_adds_named_inputs_for_known_custom_node_widgets() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoImageToVideoEncode",
        inputs={
            "widget_0": 832,
            "widget_1": 480,
            "widget_2": 81,
            "widget_3": 0,
            "widget_4": 1,
            "widget_5": 1,
            "widget_6": True,
        },
    )
    workflow.nodes["2"] = VibeNode("2", "INTConstant", inputs={"widget_0": 6})
    workflow.nodes["3"] = VibeNode(
        "3",
        "WanVideoLoraSelect",
        inputs={
            "widget_0": "WanVideo\\Lightx2v\\example.safetensors",
            "widget_1": 1.0,
            "widget_2": False,
            "widget_3": False,
        },
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"]["width"] == 832
    assert api["1"]["inputs"]["height"] == 480
    assert api["1"]["inputs"]["num_frames"] == 81
    assert api["1"]["inputs"]["noise_aug_strength"] == 0
    assert api["1"]["inputs"]["start_latent_strength"] == 1
    assert api["1"]["inputs"]["end_latent_strength"] == 1
    assert api["1"]["inputs"]["force_offload"] is True
    assert api["2"]["inputs"]["value"] == 6
    assert api["3"]["inputs"]["lora"] == "WanVideo\\Lightx2v\\example.safetensors"
    assert api["3"]["inputs"]["strength"] == 1.0


def test_wan_video_sampler_aliases_skip_seed_control_widget() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoSampler",
        inputs={
            "widget_0": 6,
            "widget_1": 1,
            "widget_2": 8,
            "widget_3": 43,
            "widget_4": "fixed",
            "widget_5": True,
            "widget_6": "dpm++_sde",
            "widget_7": 0,
            "widget_8": 1,
            "widget_9": False,
            "widget_10": "comfy",
            "widget_11": 0,
            "widget_12": 10,
            "widget_13": "",
        },
    )
    workflow.nodes["2"] = VibeNode("2", "ModelSource")
    workflow.nodes["3"] = VibeNode("3", "ImageEmbedsSource")
    workflow.edges.extend(
        [
            VibeEdge("2", "0", "1", "model"),
            VibeEdge("3", "0", "1", "image_embeds"),
        ]
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"]["seed"] == 43
    assert api["1"]["inputs"]["force_offload"] is True
    assert api["1"]["inputs"]["scheduler"] == "dpm++_sde"
    assert api["1"]["inputs"]["batched_cfg"] is False
    assert api["1"]["inputs"]["rope_function"] == "comfy"
    assert api["1"]["inputs"]["start_step"] == 0
    assert api["1"]["inputs"]["end_step"] == 10
    assert "add_noise_to_samples" not in api["1"]["inputs"]


def test_compile_adds_named_inputs_for_wan_animate_helper_widgets() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoAnimateEmbeds",
        inputs={
            "widget_0": 832,
            "widget_1": 480,
            "widget_2": 49,
            "widget_3": True,
            "widget_4": 77,
            "widget_5": "disabled",
            "widget_6": 1,
            "widget_7": 1,
            "widget_8": False,
        },
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "GrowMaskWithBlur",
        inputs={
            "widget_0": 10,
            "widget_1": 0,
            "widget_2": True,
            "widget_3": False,
            "widget_4": 0,
            "widget_5": 1,
            "widget_6": 1,
            "widget_7": False,
        },
    )
    workflow.nodes["3"] = VibeNode("3", "ImageConcatMulti", inputs={"widget_0": 4, "widget_1": "down", "widget_2": True, "widget_3": None})
    workflow.nodes["4"] = VibeNode("4", "BlockifyMask", inputs={"widget_0": 32})
    workflow.nodes["5"] = VibeNode("5", "DrawMaskOnImage", inputs={"widget_0": "0, 0, 0"})

    api = workflow.compile("api")

    assert api["1"]["inputs"]["width"] == 832
    assert api["1"]["inputs"]["height"] == 480
    assert api["1"]["inputs"]["num_frames"] == 49
    assert api["1"]["inputs"]["force_offload"] is True
    assert api["1"]["inputs"]["frame_window_size"] == 77
    assert api["1"]["inputs"]["colormatch"] == "disabled"
    assert api["1"]["inputs"]["face_strength"] == 1
    assert api["1"]["inputs"]["pose_strength"] == 1
    assert "unused_8" not in api["1"]["inputs"]
    assert api["2"]["inputs"]["expand"] == 10
    assert api["2"]["inputs"]["incremental_expandrate"] == 0
    assert api["2"]["inputs"]["tapered_corners"] is True
    assert api["2"]["inputs"]["flip_input"] is False
    assert api["2"]["inputs"]["blur_radius"] == 0
    assert api["2"]["inputs"]["lerp_alpha"] == 1
    assert api["2"]["inputs"]["decay_factor"] == 1
    assert "unused_7" not in api["2"]["inputs"]
    assert api["3"]["inputs"]["inputcount"] == 4
    assert api["3"]["inputs"]["direction"] == "down"
    assert api["3"]["inputs"]["match_image_size"] is True
    assert api["4"]["inputs"]["block_size"] == 32
    assert api["5"]["inputs"]["color"] == "0, 0, 0"


def test_compile_adds_named_inputs_for_wan_animate_custom_node_widgets() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "DownloadAndLoadSAM2Model",
        inputs={
            "widget_0": "sam2.1_hiera_base_plus.safetensors",
            "widget_1": "video",
            "widget_2": "cuda",
            "widget_3": "fp16",
        },
    )
    workflow.nodes["2"] = VibeNode("2", "Sam2Segmentation", inputs={"widget_0": False, "widget_1": False})
    workflow.nodes["3"] = VibeNode(
        "3",
        "OnnxDetectionModelLoader",
        inputs={
            "widget_0": "vitpose-l-wholebody.onnx",
            "widget_1": "yolov10m.onnx",
            "widget_2": "CUDAExecutionProvider",
        },
    )
    workflow.nodes["4"] = VibeNode(
        "4",
        "WanVideoClipVisionEncode",
        inputs={
            "widget_0": 1.0,
            "widget_1": 1.0,
            "widget_2": "center",
            "widget_3": True,
            "widget_4": False,
        },
    )
    workflow.nodes["5"] = VibeNode(
        "5",
        "DrawViTPose",
        inputs={
            "widget_0": 512,
            "widget_1": 512,
            "widget_2": 32,
            "widget_3": 4,
            "widget_4": 2,
            "widget_5": True,
        },
    )
    workflow.nodes["6"] = VibeNode("6", "CLIPVisionLoader", inputs={"widget_0": "clip_vision_h.safetensors"})

    api = workflow.compile("api")

    assert api["1"]["inputs"]["model"] == "sam2.1_hiera_base_plus.safetensors"
    assert api["1"]["inputs"]["segmentor"] == "video"
    assert api["1"]["inputs"]["device"] == "cuda"
    assert api["1"]["inputs"]["precision"] == "fp16"
    assert api["2"]["inputs"]["keep_model_loaded"] is False
    assert api["3"]["inputs"]["vitpose_model"] == "vitpose-l-wholebody.onnx"
    assert api["3"]["inputs"]["yolo_model"] == "yolov10m.onnx"
    assert api["3"]["inputs"]["onnx_device"] == "CUDAExecutionProvider"
    assert api["4"]["inputs"]["strength_1"] == 1.0
    assert api["4"]["inputs"]["crop"] == "center"
    assert api["4"]["inputs"]["combine_embeds"] is True
    assert api["4"]["inputs"]["force_offload"] is False
    assert api["5"]["inputs"]["retarget_padding"] == 32
    assert api["5"]["inputs"]["body_stick_width"] == 4
    assert api["5"]["inputs"]["hand_stick_width"] == 2
    assert api["5"]["inputs"]["draw_head"] is True
    assert api["6"]["inputs"]["clip_name"] == "clip_vision_h.safetensors"


def test_official_index_uses_package_manifest_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "workflow_templates"
    templates = repo / "templates"
    package = repo / "packages" / "starter"
    templates.mkdir(parents=True)
    package.mkdir(parents=True)
    (templates / "default.json").write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    (package / "manifest.json").write_text(
        json.dumps({"id": "starter-pack", "workflows": ["templates/default.json"]}),
        encoding="utf-8",
    )

    rows = index_workflows(repo)

    assert rows == [
        {
            "id": "default",
            "path": str(templates / "default.json"),
            "source": "official",
            "media_type": "unknown",
            "package_id": "starter-pack",
            "manifest_path": str(package / "manifest.json"),
        }
    ]


def test_workflow_from_id_reads_external_index_when_official_exists(tmp_path: Path, monkeypatch) -> None:
    official = tmp_path / "official.json"
    external = tmp_path / "external_only.json"
    official.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "official"}}}), encoding="utf-8")
    external.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "external"}}}), encoding="utf-8")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "official-only", "path": str(official), "source": "official"}]),
        encoding="utf-8",
    )
    (tmp_path / "external_workflow_index.json").write_text(
        json.dumps([{"id": "external-only", "path": str(external), "source": "external"}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    workflow = workflow_from_id("external-only")

    assert workflow.id == "external-only"
    assert workflow.nodes["1"].inputs["text"] == "external"


def test_load_workflow_reference_handles_json_path_index_id_and_scratchpad(tmp_path: Path, monkeypatch) -> None:
    workflow_json = tmp_path / "workflow.json"
    indexed_json = tmp_path / "indexed.json"
    scratchpad = tmp_path / "scratchpad.py"
    workflow_json.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "path"}}}), encoding="utf-8")
    indexed_json.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "indexed"}}}), encoding="utf-8")
    scratchpad.write_text(
        "\n".join(
            [
                "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
                "def build():",
                "    workflow = VibeWorkflow('scratchpad', WorkflowSource('scratchpad'))",
                "    return workflow",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "indexed", "path": str(indexed_json), "source": "official"}]),
        encoding="utf-8",
    )
    (tmp_path / "external_workflow_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from_path = load_workflow_reference(str(workflow_json), allow_scratchpad=True)
    from_index = load_workflow_reference("indexed", allow_scratchpad=True)
    from_scratchpad = load_workflow_reference(str(scratchpad), allow_scratchpad=True)

    assert from_path.nodes["1"].inputs["text"] == "path"
    assert from_index.id == "indexed"
    assert from_index.nodes["1"].inputs["text"] == "indexed"
    assert from_scratchpad.id == "scratchpad"


# -- lookup_id ----------------------------------------------------------------

class TestLookupId:
    """VibeWorkflow.lookup_id(node_id) returns a rich info dict for a node."""

    def test_absent_node_raises_keyerror(self) -> None:
        """lookup_id raises KeyError for absent nodes, not None."""
        wf = VibeWorkflow("test", WorkflowSource("test"))
        with pytest.raises(KeyError, match="99"):
            wf.lookup_id("99")

    def test_absent_node_raises_keyerror_not_none(self) -> None:
        """KeyError is raised, no None fallback."""
        wf = VibeWorkflow("test", WorkflowSource("test"))
        wf.nodes["1"] = VibeNode(id="1", class_type="Dummy")
        # "2" does not exist
        with pytest.raises(KeyError):
            wf.lookup_id("2")

    def test_basic_fields_for_raw_workflow(self) -> None:
        """Raw workflow (minimal metadata) returns correct basic fields."""
        wf = VibeWorkflow("test", WorkflowSource("test", path="/fake/workflow.json"))
        wf.nodes["1"] = VibeNode(
            id="1",
            class_type="KSampler",
            inputs={"seed": 1, "steps": 4, "cfg": 7.0},
            widgets={"sampler_name": "euler"},
        )

        info = wf.lookup_id("1")

        assert info["variable_name"] is None
        assert info["class_type"] == "KSampler"
        assert info["source_path"] == "/fake/workflow.json"
        assert info["source_line"] is None
        assert info["inputs"] == ["seed", "steps", "cfg"]
        assert info["widgets"] == {"sampler_name": "euler"}
        assert info["public_bindings"] == []
        assert info["outputs"] == []
        assert info["model_assets"] == []

    def test_model_assets_include_registry_and_unresolved_reference_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget

        wf = VibeWorkflow("test", WorkflowSource("test"))
        wf.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "registry.safetensors"})
        wf.nodes["2"] = VibeNode("2", "UNETLoader", inputs={"unet_name": "https://example.test/external.safetensors"})
        registry = [
            ModelEntry(
                id="registry",
                source=ModelSource(kind="url", url="https://example.test/registry.safetensors"),
                min_size=1,
                targets=(ModelTarget(node_pack="comfy_core", path="diffusion_models/registry.safetensors"),),
            )
        ]
        monkeypatch.setattr("vibecomfy.registry.models_loader.load_registry", lambda: registry)

        registry_info = wf.lookup_id("1")["model_assets"]
        external_info = wf.lookup_id("2")["model_assets"]

        assert registry_info == [
            {
                "name": "registry.safetensors",
                "url": "https://example.test/registry.safetensors",
                "subdir": "diffusion_models",
                "node_id": "1",
                "class_type": "UNETLoader",
                "field": "unet_name",
                "value": "registry.safetensors",
                "reference_type": "registry-backed",
                "downloadable": True,
            }
        ]
        assert external_info == [
            {
                "name": "https://example.test/external.safetensors",
                "subdir": "diffusion_models",
                "node_id": "2",
                "class_type": "UNETLoader",
                "field": "unet_name",
                "value": "https://example.test/external.safetensors",
                "reference_type": "external-url",
                "downloadable": False,
                "unresolved": True,
            }
        ]

    def test_variable_name_from_id_map(self) -> None:
        """Reverse lookup from _id_map returns the variable name."""
        wf = VibeWorkflow("test", WorkflowSource("test"))
        wf.nodes["5"] = VibeNode(id="5", class_type="CheckpointLoaderSimple")
        wf._set_id_map({"ckpt": "5"})

        info = wf.lookup_id("5")
        assert info["variable_name"] == "ckpt"

    def test_source_path_from_provenance(self) -> None:
        """source_path prefers node metadata provenance over workflow source."""
        wf = VibeWorkflow("test", WorkflowSource("test", path="/wf/source.json"))
        wf.nodes["1"] = VibeNode(
            id="1",
            class_type="CLIPTextEncode",
            metadata={"provenance": {"source_path": "/wf/ready_template.py", "source_line": 42}},
        )

        info = wf.lookup_id("1")
        assert info["source_path"] == "/wf/ready_template.py"
        assert info["source_line"] == 42

    def test_source_line_null_for_generated_template_nodes(self) -> None:
        """SD4: generated-template nodes without source_line get null."""
        wf = VibeWorkflow("test", WorkflowSource("test"))
        wf.nodes["1"] = VibeNode(
            id="1",
            class_type="KSampler",
            metadata={"provenance": {"source_path": "/wf/gen.py"}},
        )
        # No source_line in provenance → null
        info = wf.lookup_id("1")
        assert info["source_line"] is None

    def test_public_bindings(self) -> None:
        """VibeInput entries targeting this node appear in public_bindings."""
        from vibecomfy.workflow import VibeInput

        wf = VibeWorkflow("test", WorkflowSource("test"))
        wf.nodes["3"] = VibeNode(id="3", class_type="KSampler", inputs={"seed": 0})
        wf.inputs["seed"] = VibeInput(
            name="seed", node_id="3", field="seed", value=42, type="INT", default=0, required=True,
        )

        info = wf.lookup_id("3")
        assert len(info["public_bindings"]) == 1
        binding = info["public_bindings"][0]
        assert binding["name"] == "seed"
        assert binding["field"] == "seed"
        assert binding["value"] == 42
        assert binding["type"] == "INT"

    def test_outputs_filtered(self) -> None:
        """Outputs are filtered to the requested node_id."""
        from vibecomfy.workflow import VibeOutput

        wf = VibeWorkflow("test", WorkflowSource("test"))
        wf.nodes["1"] = VibeNode(id="1", class_type="SaveImage")
        wf.nodes["2"] = VibeNode(id="2", class_type="PreviewImage")
        wf.outputs = [
            VibeOutput(node_id="1", output_type="SaveImage"),
            VibeOutput(node_id="2", output_type="PreviewImage"),
        ]

        info = wf.lookup_id("1")
        assert info["outputs"] == ["SaveImage"]

        info2 = wf.lookup_id("2")
        assert info2["outputs"] == ["PreviewImage"]

    def test_ready_template_workflow_with_provenance(self) -> None:
        """Ready-template workflow with _id_map and metadata provenance."""
        wf = VibeWorkflow(
            "image/z_image",
            WorkflowSource("image/z_image", path="ready_templates/image/z_image.py", source_type="ready_template"),
        )
        wf.nodes["4"] = VibeNode(
            id="4",
            class_type="KSampler",
            inputs={"seed": 42, "steps": 20},
            metadata={"provenance": {"source_path": "ready_templates/image/z_image.py", "source_line": 68}},
        )
        wf._set_id_map({"ksampler": "4"})

        info = wf.lookup_id("4")
        assert info["class_type"] == "KSampler"
        assert info["variable_name"] == "ksampler"
        assert info["source_path"] == "ready_templates/image/z_image.py"
        assert info["source_line"] == 68
        assert "seed" in info["inputs"]
        assert "steps" in info["inputs"]


# ── T2: Monotonic uid counter tests ──────────────────────────────────────────


def _make_empty_wf() -> VibeWorkflow:
    return VibeWorkflow(id="test", source=WorkflowSource(id="test"))


def test_uid_counter_is_independent_of_next_node_id() -> None:
    """_uid_counter increments monotonically; _next_node_id gap-fills int ids."""
    wf = _make_empty_wf()
    # node() mints uid via counter
    b1 = wf.node("Foo")
    assert wf._uid_counter == 1
    b2 = wf.node("Bar")
    assert wf._uid_counter == 2
    # Both have distinct uids
    assert b1.node.uid != b2.node.uid
    # Int ids are gap-filled (start at 1)
    assert b1.node.id == "1"
    assert b2.node.id == "2"


def test_add_delete_add_reuses_int_id_but_fresh_uid() -> None:
    """add→delete→add reuses the lowest gap int id but mints a fresh non-colliding uid."""
    wf = _make_empty_wf()
    b1 = wf.node("Foo")
    uid_first = b1.node.uid
    node_id_first = b1.node.id  # e.g. "1"
    # Delete the node
    del wf.nodes[node_id_first]
    # Add again — should get the same int id via gap-fill
    b2 = wf.node("Bar")
    assert b2.node.id == node_id_first, "expected gap-fill to reuse the vacated int id"
    # But uid must be fresh and non-colliding
    assert b2.node.uid != uid_first, "uid must not be reused after delete→add"


def test_uid_survives_finalize_metadata() -> None:
    """VibeNode.uid is preserved through finalize_metadata (not rebuilt)."""
    wf = _make_empty_wf()
    b = wf.node("SaveImage")
    uid_before = b.node.uid
    assert uid_before  # must have been minted
    wf.finalize_metadata()
    assert wf.nodes[b.node.id].uid == uid_before


def test_add_node_uid_kwarg_sets_verbatim() -> None:
    """add_node(uid=...) sets node.uid verbatim without minting."""
    wf = _make_empty_wf()
    counter_before = wf._uid_counter
    node = wf.add_node("Foo", uid="explicit-uid-value")
    assert node.uid == "explicit-uid-value"
    # Counter unchanged — add_node does not mint
    assert wf._uid_counter == counter_before


def test_node_with_explicit_id_seeds_uid_from_id() -> None:
    """node(_id=...) seeds the uid from the explicit id, not the counter value alone."""
    wf = _make_empty_wf()
    b = wf.node("Foo", _id="42")
    assert b.node.id == "42"
    # uid should encode the explicit id as seed
    assert "42" in b.node.uid


def test_uid_counter_monotonic_never_resets() -> None:
    """_uid_counter never decreases; deletion does not reset it."""
    wf = _make_empty_wf()
    b1 = wf.node("A")
    b2 = wf.node("B")
    del wf.nodes[b1.node.id]
    del wf.nodes[b2.node.id]
    wf.node("C")
    assert wf._uid_counter == 3  # monotonically incremented, not reset


def _ir_projection(workflow) -> dict:
    return {
        "ids": sorted(workflow.nodes),
        "classes": {nid: node.class_type for nid, node in workflow.nodes.items()},
        "uids": {nid: node.uid for nid, node in workflow.nodes.items()},
        "inputs": {nid: node.inputs for nid, node in workflow.nodes.items()},
        "widgets": {nid: node.widgets for nid, node in workflow.nodes.items()},
        "edges": [
            (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
            for edge in workflow.edges
        ],
    }


def test_from_api_matches_fixture_invariants() -> None:
    """from_api decodes an API dict with stable IDs, classes, inputs, and edges."""
    raw = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }
    wf = from_api(raw, workflow_id="sample")
    assert _ir_projection(wf) == {
        "ids": ["1", "2", "3"],
        "classes": {
            "1": "CLIPTextEncode",
            "2": "KSampler",
            "3": "SaveImage",
        },
        "uids": {"1": "1", "2": "2", "3": "3"},
        "inputs": {
            "1": {"text": "old"},
            "2": {"seed": 1, "steps": 4},
            "3": {},
        },
        "widgets": {"1": {}, "2": {}, "3": {}},
        "edges": [
            ("1", "0", "2", "positive"),
            ("2", "0", "3", "images"),
        ],
    }


def test_from_ui_matches_fixture_invariants() -> None:
    """from_ui decodes litegraph with stable IDs, classes, inputs, and edges."""
    raw = {
        "nodes": [
            {"id": 1, "type": "CLIPTextEncode", "widgets_values": ["hello"], "inputs": []},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "link": 1}]},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
    }
    wf = from_ui(raw)
    assert _ir_projection(wf) == {
        "ids": ["1", "2"],
        "classes": {"1": "CLIPTextEncode", "2": "SaveImage"},
        "uids": {"1": "1", "2": "2"},
        "inputs": {"1": {"text": "hello"}, "2": {}},
        "widgets": {"1": {}, "2": {}},
        "edges": [("1", "0", "2", "images")],
    }


def test_named_importers_match_fixture_invariants() -> None:
    """from_ui / from_api / from_envelope decode fixtures with stable invariants."""
    ui_path = Path("tests/fixtures/reorganise/simple_text_to_image.json")
    ui_raw = json.loads(ui_path.read_text(encoding="utf-8"))
    from_ui_wf = from_ui(ui_raw)
    assert from_ui_wf.nodes
    assert all(node.uid for node in from_ui_wf.nodes.values())

    api = normalize_to_api(ui_raw, use_comfy_converter=False)
    from_api_wf = from_api(api)
    assert set(from_api_wf.nodes) == set(from_ui_wf.nodes)
    assert {
        nid: node.class_type for nid, node in from_api_wf.nodes.items()
    } == {nid: node.class_type for nid, node in from_ui_wf.nodes.items()}

    envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    via_named = from_envelope(envelope)
    via_class = VibeWorkflow.from_envelope(envelope)
    assert _ir_projection(via_named) == _ir_projection(via_class)
    assert len(via_named.nodes) == 15
    assert len(via_named.compile("api")) == 2


def test_detect_workflow_shape_is_not_a_public_ingest_export() -> None:
    import vibecomfy.ingest as ingest

    assert "detect_workflow_shape" not in ingest.__all__
    assert "from_envelope" in ingest.__all__
    assert "from_ui" in ingest.__all__
    assert "from_api" in ingest.__all__
    assert not hasattr(ingest, "detect_workflow_shape")


def test_convert_to_vibe_format_is_not_a_public_ingest_export() -> None:
    """The public dispatcher is deleted; only the named importers remain."""
    import vibecomfy.ingest as ingest

    assert "convert_to_vibe_format" not in ingest.__all__
    assert not hasattr(ingest, "convert_to_vibe_format")


def test_agent_edit_ingest_uses_nodes_is_list_not_shape_sniff() -> None:
    """edit_ingest successor: list-nodes pass through; no detect_workflow_shape."""
    frag = Path("vibecomfy/comfy_nodes/agent/_frag_ingest.py").read_text(encoding="utf-8")
    assert "detect_workflow_shape" not in frag
    assert 'isinstance(graph.get("nodes"), list)' in frag
