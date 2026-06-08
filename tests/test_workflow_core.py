from __future__ import annotations

import builtins
import importlib.util
import json
import sys
import types
import warnings
from pathlib import Path

import pytest

from vibecomfy.ingest.index import index_workflows
from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape, normalize_to_api
from vibecomfy.registry.library import load_workflow_reference, workflow_from_id
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.handles import Handle
from vibecomfy.workflow import (
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

    assert detect_workflow_shape(raw) == "api"
    workflow = convert_to_vibe_format(normalize_to_api(raw), workflow_id="sample")

    assert workflow.id == "sample"
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
    workflow = convert_to_vibe_format(
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

    workflow = convert_to_vibe_format(raw, workflow_id="conditioning")

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
        inputs={"images": ["2", 0]},
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
        inputs={"images": ["1", 0], "filename_prefix": "orig"},
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


def test_ui_workflow_normalizes_to_api() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "CLIPTextEncode", "widgets_values": ["hello"], "inputs": []},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "link": 1}]},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
    }

    assert detect_workflow_shape(raw) == "ui"
    api = normalize_to_api(raw)
    assert api["1"]["class_type"] == "CLIPTextEncode"
    assert api["2"]["inputs"]["images"] == ["1", 0]


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
    workflow.nodes["1"] = VibeNode(
        "1",
        "VHS_VideoCombine",
        inputs={
            "images": ["2", 0],
            "videopreview": {
                "hidden": False,
                "params": {"filename": "preview.mp4"},
                "paused": False,
            },
        },
    )

    api = workflow.compile("api")

    assert "videopreview" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["images"] == ["2", 0]


def test_compile_drops_null_prompt_inputs() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "ImageConcatMulti",
        inputs={
            "image_1": ["2", 0],
            "image_2": ["3", 0],
            "widget_3": None,
        },
    )

    api = workflow.compile("api")

    assert "widget_3" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["image_1"] == ["2", 0]


def test_compile_drops_note_nodes_from_api_prompt() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"images": ["3", 0]})

    api = workflow.compile("api")

    assert "1" not in api
    assert api["2"]["class_type"] == "SaveImage"


def test_compile_drops_markdown_note_nodes_from_api_prompt() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"images": ["3", 0]})

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
        inputs={"IMAGE": ["1", 0], "widget_0": "reference_image"},
    )
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
    workflow.connect("3.0", "4.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "4"}
    assert api["4"]["inputs"]["images"] == ["1", 0]


def test_compile_rewrites_edge_fed_set_get_nodes_to_direct_links() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={"images": ["3", 0]})
    workflow.connect("1.0", "2.IMAGE")

    api = workflow.compile("api")

    assert set(api) == {"1", "4"}
    assert api["4"]["inputs"]["images"] == ["1", 0]


def test_compile_rewrites_set_get_source_through_bypassed_nodes() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    bypassed = VibeNode("2", "ImageFilter", inputs={})
    bypassed.metadata["_ui"] = {"mode": 4}
    workflow.nodes["2"] = bypassed
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={})
    workflow.connect("1.0", "2.image")
    workflow.connect("2.0", "3.IMAGE")
    workflow.connect("4.0", "5.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "5"}
    assert api["5"]["inputs"]["images"] == ["1", 0]


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
    workflow.nodes["1"] = VibeNode("1", "vibecomfy.exec", inputs={"in_0": ["9", 0], "source": "return 1"})
    workflow.nodes["2"] = VibeNode("2", "vibecomfy.loop")

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
    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={"images": ["4", 0]})
    workflow.connect("2.0", "3.IMAGE")

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
    workflow.nodes["6"] = VibeNode("6", "SaveImage", inputs={"images": ["5", 0]})

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
            "model": ["2", 0],
            "image_embeds": ["3", 0],
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
    b3 = wf.node("C")
    assert wf._uid_counter == 3  # monotonically incremented, not reset
