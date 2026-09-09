from __future__ import annotations

import warnings

import pytest

from vibecomfy import Handle, VibeWorkflow, WorkflowSource
from vibecomfy.blocks import Handles


def test_handle_string_equality_and_hash() -> None:
    handle = Handle("12", 0)

    assert str(handle) == "12.0"
    assert handle == "12.0"
    assert handle == "12"
    assert handle == Handle("12", "0")
    assert hash(handle) == hash(Handle("12", "0"))


def test_handle_output_type_preserves_identity_equality_and_hash() -> None:
    typed = Handle("12", 0, output_type="IMAGE", name="image")
    untyped = Handle("12", "0")

    assert str(typed) == "12.0"
    assert typed.output_type == "IMAGE"
    assert typed.name == "image"
    assert typed == untyped
    assert typed == "12.0"
    assert typed == "12"
    assert hash(typed) == hash(untyped)


def test_handles_coerces_raw_string_once_per_source_location() -> None:
    from vibecomfy.blocks import _RAW_HANDLE_WARNING_SITES

    _RAW_HANDLE_WARNING_SITES.clear()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        first = Handles({"x": "12.0"}); second = Handles({"x": "12.0"})

    assert isinstance(first["x"], Handle)
    assert isinstance(second["x"], Handle)
    assert str(first["x"]) == "12.0"
    assert [item.category for item in caught].count(DeprecationWarning) == 1


def test_public_handle_import_path() -> None:
    from vibecomfy import Handle as PublicHandle

    assert PublicHandle is Handle


def test_workflow_node_out_compile_and_connect_with_handle() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))

    clip = workflow.node("CLIPTextEncode", text="hello")
    conditioning = clip.out(0)
    consumer = workflow.node("PreviewImage")
    workflow.connect(conditioning, f"{consumer.id}.images")

    assert isinstance(conditioning, Handle)
    api = workflow.compile("api")
    assert api[clip.id]["inputs"]["text"] == "hello"
    assert api[consumer.id]["inputs"]["images"] == [clip.id, 0]


def test_node_builder_iteration_preserves_schema_output_types() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))

    loader = workflow.node("CheckpointLoaderSimple", ckpt_name="model.safetensors")
    model, clip, vae = list(loader)

    assert (model.output_type, clip.output_type, vae.output_type) == ("MODEL", "CLIP", "VAE")
    assert (model.name, clip.name, vae.name) == ("MODEL", "CLIP", "VAE")


def test_default_off_strict_types_does_not_warn_for_incompatible_known_types() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))
    image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
    sampler = workflow.node("KSampler")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        workflow.connect(image.out(0), f"{sampler.id}.latent_image")

    assert caught == []


def test_strict_types_warns_for_incompatible_known_types() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"), strict_types=True)
    image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
    sampler = workflow.node("KSampler")

    with pytest.warns(RuntimeWarning, match="IMAGE.*LATENT"):
        workflow.connect(image.out(0), f"{sampler.id}.latent_image")


def test_strict_types_does_not_warn_for_compatible_or_unknown_types() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"), strict_types=True)
    latent = workflow.node("EmptyLatentImage", width=8, height=8, batch_size=1)
    sampler = workflow.node("KSampler")
    unknown = workflow.node("UnknownProducer")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        workflow.connect(latent.out(0), f"{sampler.id}.latent_image")
        workflow.connect(unknown.out(0), f"{sampler.id}.latent_image")

    assert caught == []


def test_named_output_uses_retained_schema_and_unknown_name_fails_closed() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))

    conditioning = workflow.node("CLIPTextEncode", text="hello").out("CONDITIONING")
    assert conditioning.output_slot == 0
    assert conditioning.output_type == "CONDITIONING"

    with pytest.raises(NotImplementedError, match="Named output"):
        workflow.node("CLIPTextEncode", text="hello").out("NOT_A_REAL_OUTPUT")
