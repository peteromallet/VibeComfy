from __future__ import annotations

from types import SimpleNamespace

import vibecomfy.ops.image as image_ops
from vibecomfy.blocks.save import image as save_image
from vibecomfy.patches.seed import seed
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_image_op_stamps_origin_metadata(monkeypatch) -> None:
    workflow = _prompt_save_workflow()

    monkeypatch.setattr(
        image_ops,
        "pick",
        lambda *args, **kwargs: SimpleNamespace(template_id="image/test", explicit_patches=[]),
    )
    monkeypatch.setattr(image_ops, "load_workflow_any", lambda template_id: workflow)

    artifact = image_ops._t2i("a fox")

    assert artifact.workflow.metadata["entrypoint"] == "op"
    assert artifact.workflow.metadata["layer"] == "ops/image.py:t2i"
    assert artifact.compile()["2"]["class_type"] == "SaveImage"


def test_block_stamping_preserves_existing_origin() -> None:
    workflow = VibeWorkflow("block-origin", WorkflowSource("block-origin"))
    workflow.metadata["entrypoint"] = "op"
    workflow.metadata["layer"] = "ops/image.py:t2i"
    source = workflow.add_node("Source")

    save_image(workflow, images=source.id, filename_prefix="block/out")

    assert workflow.metadata["entrypoint"] == "op"
    assert workflow.metadata["layer"] == "ops/image.py:t2i"
    assert workflow.compile("api")["2"]["class_type"] == "SaveImage"


def test_patch_stamps_origin_when_missing() -> None:
    workflow = VibeWorkflow("patch-origin", WorkflowSource("patch-origin"))
    sampler = workflow.add_node("KSampler")
    sampler.widgets["widget_0"] = 1

    configured = seed(11)
    configured.apply(workflow)

    assert workflow.metadata["entrypoint"] == "patch"
    assert workflow.metadata["layer"] == "vibecomfy/patches/seed.py:seed:11"
    assert workflow.metadata["patch_applications"] == [
        {
            "name": "seed:11",
            "layer": "patch",
            "called": True,
            "topology_changed": False,
            "nodes_added": [],
            "introduced_edges": [],
            "rewritten_edges": [],
            "value_changed": True,
        }
    ]
    assert workflow.compile("api")["1"]["inputs"]["widget_0"] == 11


def test_patch_preserves_existing_origin() -> None:
    workflow = VibeWorkflow("patch-origin-existing", WorkflowSource("patch-origin-existing"))
    workflow.metadata["entrypoint"] = "op"
    workflow.metadata["layer"] = "ops/video.py:i2v"
    sampler = workflow.add_node("KSampler")
    sampler.widgets["widget_0"] = 3

    seed(5).apply(workflow)

    assert workflow.metadata["entrypoint"] == "op"
    assert workflow.metadata["layer"] == "ops/video.py:i2v"


def _prompt_save_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("op-origin", WorkflowSource("op-origin"))
    prompt = workflow.add_node("CLIPTextEncode", text="initial prompt")
    workflow.add_node("SaveImage", images=prompt.id)
    workflow.finalize_metadata()
    return workflow
