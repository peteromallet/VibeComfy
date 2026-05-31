from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy import Image, Video, image, video


def test_image_t2i_returns_lazy_image_artifact_with_prompt_input() -> None:
    artifact = image.t2i("hello")

    assert isinstance(artifact, Image)
    workflow = artifact.preview_workflow()
    api = workflow.compile("api")

    assert any(node["class_type"] == "SaveImage" for node in api.values())
    assert workflow.inputs["prompt"].value == "hello"


def test_video_t2v_returns_lazy_video_artifact_with_save_video_output() -> None:
    artifact = video.t2v("hello")

    assert isinstance(artifact, Video)
    workflow = artifact.preview_workflow()

    assert workflow.outputs[0].output_type == "SaveVideo"


def test_video_i2v_binds_image_path_to_workflow_input() -> None:
    image_path = "/tmp/some_frame.png"
    artifact = video.i2v(image_path, "rotate")

    workflow = artifact.preview_workflow()
    api = workflow.compile("api")
    image_input = workflow.inputs["image"]

    assert api[image_input.node_id]["class_type"] == "LoadImage"
    assert api[image_input.node_id]["inputs"]["image"] == image_path
    assert api[image_input.node_id]["inputs"]["image"] != "image_to_video_wan_start_image.png"


def test_video_i2v_accepts_object_with_path_attribute() -> None:
    artifact = video.i2v(SimpleNamespace(path=Path("/tmp/frame_from_result.png")), "rotate")

    workflow = artifact.preview_workflow()
    api = workflow.compile("api")
    image_input = workflow.inputs["image"]

    assert api[image_input.node_id]["inputs"]["image"] == "/tmp/frame_from_result.png"


def test_video_i2v_rejects_unrun_image_artifact() -> None:
    unrun_image = image.t2i("source")

    with pytest.raises(ValueError, match=r"Run the image workflow first.*result\.outputs\[0\]"):
        video.i2v(unrun_image, "rotate")


def test_flux_gguf_t2i_route_is_deferred() -> None:
    with pytest.raises(KeyError):
        image.t2i("hello", model="flux2_klein_9b_gguf")
