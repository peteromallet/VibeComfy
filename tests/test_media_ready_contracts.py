from __future__ import annotations

from vibecomfy.registry.ready import workflow_from_ready


def test_video_enhance_ready_template_binds_source_and_preserves_media_metadata() -> None:
    workflow = workflow_from_ready("video/basic_video_enhance")

    assert workflow.validate().ok
    assert {"video_ref", "scale", "upscale_method"} <= set(workflow.inputs)

    workflow.set_input("video_ref", "/cas/source.mp4")
    workflow.set_input("scale", 1.5)
    workflow.set_input("upscale_method", "nearest-exact")
    api = workflow.compile("api")

    assert api["1"]["inputs"]["video"] == "/cas/source.mp4"
    assert api["2"]["inputs"]["scale_by"] == 1.5
    assert api["2"]["inputs"]["upscale_method"] == "nearest-exact"
    assert api["3"]["inputs"]["audio"] == ["1", 2]
    assert api["3"]["inputs"]["frame_rate"] == ["1", 3]


def test_wan_animate_ready_template_binds_two_media_inputs_and_typed_controls() -> None:
    workflow = workflow_from_ready("video/wan22_animate_native_first_stage")

    assert workflow.validate().ok
    assert {
        "image",
        "driving_video",
        "prompt",
        "negative_prompt",
        "seed",
        "steps",
        "width",
        "height",
        "frames",
        "fps",
    } <= set(workflow.inputs)
    assert "mode" not in workflow.inputs

    # ``input_image`` is the materialized alias used by the application
    # boundary; setting the alias also updates the underlying LoadImage node.
    workflow.set_input("input_image", "/cas/reference.png")
    workflow.set_input("driving_video", "/cas/driving.mp4")
    workflow.set_input("prompt", "walk forward")
    workflow.set_input("negative_prompt", "blurry")
    workflow.set_input("seed", 7)
    workflow.set_input("steps", 4)
    workflow.set_input("width", 1280)
    workflow.set_input("height", 720)
    workflow.set_input("frames", 41)
    workflow.set_input("fps", 24)
    api = workflow.compile("api")

    assert api["4"]["inputs"]["image"] == "/cas/reference.png"
    assert api["7"]["inputs"]["file"] == "/cas/driving.mp4"
    assert api["8"]["inputs"]["text"] == "blurry"
    assert api["11"]["inputs"]["text"] == "walk forward"
    assert api["15"]["inputs"]["width"] == 1280
    assert api["15"]["inputs"]["height"] == 720
    assert api["24"]["inputs"]["length"] == 41
    assert api["25"]["inputs"]["seed"] == 7
    assert api["25"]["inputs"]["steps"] == 4
    assert api["29"]["inputs"]["fps"] == 24
