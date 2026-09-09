from __future__ import annotations

import pytest

from vibecomfy.blocks import Handles, block, block_spec, registered_blocks
from vibecomfy.blocks.decode import vae as decode_vae
from vibecomfy.blocks.encoding import clip_vision as encode_clip_vision, text_pair
from vibecomfy.blocks.latent import HunyuanVideoShape, empty_hunyuan_video
from vibecomfy.blocks.loaders import LoaderNames, clip_vision as load_clip_vision, load_image, unet_clip_vae
from vibecomfy.blocks.save import VideoSaveSettings, image as save_image, video as save_video
from vibecomfy.blocks.sampling import KSamplerSettings, ksampler, model_sampling_sd3
from vibecomfy.blocks.subgraph import opaque, ref
from vibecomfy.blocks.video import VideoCreateSettings, create as create_video
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_block_decorator_registers_metadata() -> None:
    spec = block_spec(load_image)

    assert spec is not None
    assert spec.name == "vibecomfy.blocks.loaders.load_image"
    assert spec.module == "vibecomfy.blocks.loaders"
    assert "workflow" in spec.signature
    assert registered_blocks()[spec.name] is load_image


def test_block_decorator_requires_workflow_first_parameter() -> None:
    with pytest.raises(TypeError, match="workflow as its first parameter"):

        @block
        def missing_workflow(*, value: str) -> Handles:
            return Handles(value=value)


def test_registered_block_remains_callable() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    handles = registered_blocks()["vibecomfy.blocks.loaders.load_image"](
        workflow,
        image="example.png",
    )

    assert handles.image == "1"
    assert workflow.nodes["1"].metadata["block"] == "vibecomfy.blocks.loaders.load_image"


def test_loader_block_uses_grouped_names() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    handles = unet_clip_vae(
        workflow,
        names=LoaderNames(
            unet_name="unet.safetensors",
            clip_name="clip.safetensors",
            vae_name="vae.safetensors",
            clip_type="flux",
        ),
    )

    assert handles.model == "1"
    assert workflow.nodes["1"].inputs["unet_name"] == "unet.safetensors"
    assert workflow.nodes["2"].inputs["type"] == "flux"
    assert workflow.nodes["3"].inputs["vae_name"] == "vae.safetensors"


def test_authoring_dsl_builds_compileable_text_to_image_chain(monkeypatch) -> None:
    from vibecomfy import load_bundle
    from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
    from vibecomfy.schema import get_authoring_schema_provider

    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))
    loaded = unet_clip_vae(workflow, names=LoaderNames(
        unet_name="unet.safetensors", clip_name="clip.safetensors", vae_name="vae.safetensors",
    ))
    encoded = text_pair(workflow, clip=loaded.clip, positive="a red cube", negative="blurry")
    latent = workflow.node("EmptyLatentImage", width=512, height=512, batch_size=1)
    sampled = ksampler(workflow, model=loaded.model, positive=encoded.positive,
                       negative=encoded.negative, latent=latent.id,
                       settings=KSamplerSettings(seed=42, steps=5))
    decoded = decode_vae(workflow, samples=sampled.samples, vae=loaded.vae)
    saved = save_image(workflow, images=decoded.images, filename_prefix="blocks/out")
    provider = get_authoring_schema_provider(on_demand_schemas=False)
    fixture_models = {"unet.safetensors": "diffusion_models", "clip.safetensors": "text_encoders",
                      "vae.safetensors": "vae"}
    entries = tuple(ModelEntry(name, ModelSource("local"), 0,
                              (ModelTarget("comfy_core", f"{subdir}/{name}"),), canonical_name=name)
                    for name, subdir in fixture_models.items())
    monkeypatch.setattr("vibecomfy.registry.models_loader.load_registry", lambda: entries)
    monkeypatch.setattr("vibecomfy.fetch.is_present", lambda ref, **_: (
        fixture_models.get(ref["name"]) == ref["subdir"]
    ))
    bundle = load_bundle(workflow)
    record = bundle.compile(schema_provider=provider)
    api = record.to_dict()["api_projection"]
    assert api == workflow.compile("api")
    assert workflow.nodes[saved.image.node_id].metadata["block"] == "vibecomfy.blocks.save.image"
    assert api[encoded.positive.node_id]["inputs"] == {"text": "a red cube", "clip": [loaded.clip.node_id, 0]}
    assert api[encoded.negative.node_id]["inputs"] == {"text": "blurry", "clip": [loaded.clip.node_id, 0]}
    sampler = api[sampled.samples.node_id]["inputs"]
    assert sampler["model"] == [loaded.model.node_id, 0]
    assert sampler["positive"] == [encoded.positive.node_id, 0]
    assert sampler["negative"] == [encoded.negative.node_id, 0]
    assert sampler["latent_image"] == [latent.id, 0]
    assert sampler["seed"] == 42
    assert sampler["steps"] == 5
    assert "control_after_generate" not in sampler
    assert workflow.nodes[sampled.samples.node_id].metadata["control_after_generate"] == "randomize"
    assert api[decoded.images.node_id]["inputs"] == {
        "samples": [sampled.samples.node_id, 0], "vae": [loaded.vae.node_id, 0],
    }
    assert api[saved.image.node_id]["inputs"] == {
        "filename_prefix": "blocks/out", "images": [decoded.images.node_id, 0],
    }
    assert not any(key.startswith("widget_") for node in api.values() for key in node["inputs"])


def test_ksampler_uses_grouped_settings() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    handles = ksampler(
        workflow,
        model="1",
        positive="2",
        negative="3",
        latent="4",
        settings=KSamplerSettings(seed=123, steps=12, cfg=4.5),
    )

    assert handles.samples == "1"
    assert workflow.nodes["1"].inputs["seed"] == 123
    assert workflow.nodes["1"].inputs["steps"] == 12
    assert workflow.nodes["1"].inputs["cfg"] == 4.5


def test_latent_block_uses_grouped_shape() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    empty_hunyuan_video(workflow, shape=HunyuanVideoShape(width=320, height=192, length=9))

    assert workflow.nodes["1"].inputs == {
        "width": 320, "height": 192, "length": 9, "batch_size": 1,
    }


def test_opaque_uses_explicit_widgets_inputs_and_links() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    source = workflow.add_node("Source")
    handles = opaque(
        workflow,
        class_type="CustomNode",
        widgets_by_name={"widget_0": "literal"},
        inputs={"text": "1.0"},
        links={"image": ref(source, slot=1)},
        outputs=("out", "preview"),
    )

    assert handles.out == "2.0"
    assert handles.preview == "2.1"
    assert workflow.nodes["2"].inputs["text"] == "1.0"
    assert workflow.nodes["2"].widgets["widget_0"] == "literal"
    assert workflow.compile()["2"]["inputs"]["image"] == ["1", 1]


def test_opaque_rejects_ambiguous_widget_sources() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    with pytest.raises(ValueError, match="either widgets_by_name or widget_values"):
        opaque(
            workflow,
            class_type="CustomNode",
            widgets_by_name={"widget_0": "literal"},
            widget_values=["literal"],
        )


def test_block_compile_smoke_widget_keys() -> None:
    workflow = VibeWorkflow("block-smoke", WorkflowSource("block-smoke"))

    loaded = unet_clip_vae(
        workflow,
        names=LoaderNames(
            unet_name="unet.safetensors",
            clip_name="clip.safetensors",
            vae_name="vae.safetensors",
            clip_type="wan",
        ),
    )
    vision = load_clip_vision(workflow, clip_name="clip_vision.safetensors")
    image = load_image(workflow, image="example.png")
    encoded = text_pair(workflow, clip=loaded.clip, positive="prompt", negative="negative")
    vision_encoded = encode_clip_vision(workflow, clip_vision=vision.clip_vision, image=image.image)
    latent = empty_hunyuan_video(workflow, shape=HunyuanVideoShape(width=320, height=192, length=9))
    sampled_model = model_sampling_sd3(workflow, model=loaded.model)
    sampled = ksampler(workflow, model=sampled_model.model, positive=encoded.positive, negative=encoded.negative, latent=latent.latent)
    decoded = decode_vae(workflow, samples=sampled.samples, vae=loaded.vae)
    video = create_video(workflow, images=decoded.images, settings=VideoCreateSettings(fps=12))
    save_image(workflow, images=decoded.images, filename_prefix="smoke/image")
    save_video(workflow, video=video.video, settings=VideoSaveSettings(filename_prefix="smoke/video"))

    api = workflow.compile("api")

    assert len(api) == 15
    assert api["1"]["inputs"].keys() == {"unet_name", "weight_dtype"}
    assert api["2"]["inputs"].keys() == {"clip_name", "type", "device"}
    assert api["4"]["class_type"] == "CLIPVisionLoader"
    assert api["6"]["inputs"]["text"] == "prompt"
    assert api["8"]["class_type"] == "CLIPVisionEncode"
    assert api["9"]["inputs"].keys() == {"width", "height", "length", "batch_size"}
    assert api["14"]["class_type"] == "SaveImage"
    assert api["15"]["class_type"] == "SaveVideo"
    assert workflow.nodes["5"].metadata["widget_kwargs"]["upload"] == "image"
    assert not any(key.startswith("widget_") for node in api.values() for key in node["inputs"])
    from vibecomfy.schema import get_authoring_schema_provider
    from vibecomfy.schema.validate import validate_api_against_schema, validate_api_link_shapes

    provider = get_authoring_schema_provider(on_demand_schemas=False)
    assert not [issue for issue in [*validate_api_against_schema(api, provider),
                                    *validate_api_link_shapes(api, provider)]
                if issue.severity == "error"]


@pytest.mark.parametrize("media_class,asset_field,save_fn,input_field", [
    ("LoadImage", "image", save_image, "images"),
    ("LoadVideo", "file", save_video, "video"),
])
def test_public_save_blocks_compile_named_inputs_in_approved_bundle(
    media_class, asset_field, save_fn, input_field, monkeypatch,
) -> None:
    from vibecomfy import load_bundle
    from vibecomfy.schema import get_authoring_schema_provider

    provider = get_authoring_schema_provider(on_demand_schemas=False)

    workflow = VibeWorkflow("save-block-approved", WorkflowSource("save-block-approved"))
    workflow.node(media_class, _id="media", **{asset_field: "fixture"})
    source = workflow.nodes["media"]
    kwargs = {input_field: f"{source.id}.0"}
    if media_class == "LoadImage":
        kwargs["filename_prefix"] = "approved/image"
    else:
        kwargs["settings"] = VideoSaveSettings(filename_prefix="approved/video")
    saved = save_fn(workflow, **kwargs)
    workflow.nodes[saved.output.node_id].uid = "save"
    bundle = load_bundle(workflow)

    def ambient_lookup_forbidden(*args, **kwargs):
        raise AssertionError("save block replay attempted ambient schema lookup")

    monkeypatch.setattr("vibecomfy.schema.get_authoring_schema_provider", ambient_lookup_forbidden)
    record = bundle.compile(schema_provider=provider)
    api = record.to_dict()["api_projection"]
    inputs = api[saved.output.node_id]["inputs"]
    assert inputs[input_field] == [source.id, 0]
    assert inputs["filename_prefix"] == f"approved/{'image' if media_class == 'LoadImage' else 'video'}"
    assert not any(key.startswith("widget_") for key in inputs)
    if media_class == "LoadVideo":
        assert inputs["format"] == "auto"
        assert inputs["codec"] == "auto"
