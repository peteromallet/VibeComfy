from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class VideoSaveSettings:
    filename_prefix: str = "video/ComfyUI"
    format: str = "auto"
    codec: str = "auto"


@block
def image(
    workflow: VibeWorkflow,
    *,
    images: str | Handle,
    filename_prefix: str = "ComfyUI",
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.save.image",
        "SaveImage",
        block_id=block_id,
        inputs={"filename_prefix": filename_prefix},
    )
    connect(workflow, images, node, "images")
    return Handles(
        output=Handle(node_id=node.id, output_slot=0, name="output"),
        image=Handle(node_id=node.id, output_slot=0, name="image"),
    )


@block
def video(
    workflow: VibeWorkflow,
    *,
    video: str | Handle,
    settings: VideoSaveSettings | None = None,
    block_id: str | None = None,
) -> Handles:
    settings = settings or VideoSaveSettings()
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.save.video",
        "SaveVideo",
        block_id=block_id,
        inputs={"filename_prefix": settings.filename_prefix, "format": settings.format, "codec": settings.codec},
    )
    connect(workflow, video, node, "video")
    return Handles(
        output=Handle(node_id=node.id, output_slot=0, name="output"),
        video=Handle(node_id=node.id, output_slot=0, name="video"),
    )
