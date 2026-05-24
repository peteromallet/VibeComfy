from __future__ import annotations

from vibecomfy.blocks.save import image as save_image
from vibecomfy.blocks.subgraph import NodeRef, opaque
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.runtime import run_embedded_sync


def build():
    workflow = load_workflow_any("image/z_image")
    first = workflow.outputs[0]
    upscaled = opaque(
        workflow,
        class_type="vibecomfy.placeholder.upscale",
        links={"image": NodeRef(first.node_id)},
        outputs=("image",),
    )
    save_image(workflow, images=upscaled.image, filename_prefix="dual_pass/upscaled")
    return workflow.finalize_metadata()


if __name__ == "__main__":
    run_embedded_sync(build())
