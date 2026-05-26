from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.index import index_workflows
from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape, normalize_to_api
from vibecomfy.registry.library import load_workflow_reference, workflow_from_id
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


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


def test_helper_diagnostics_report_unresolved_broadcasts_before_compile() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "GetNode", inputs={"widget_0": "missing_image"})
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={})
    workflow.connect("2.0", "3.images")

    diagnostics = workflow.helper_diagnostics()
    api = workflow.compile("api")

    assert set(api) == {"1", "3"}
    assert "images" not in api["3"]["inputs"]
    assert [(issue.code, issue.severity, issue.detail["node_id"]) for issue in diagnostics] == [
        ("helper_broadcast_unresolved", "warning", "2")
    ]


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
