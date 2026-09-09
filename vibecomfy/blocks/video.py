from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class VideoCreateSettings:
    fps: int | float = 16
    audio: str | Handle | None = None
    fps_source: str | Handle | None = None


@block
def create(
    workflow: VibeWorkflow,
    *,
    images: str | Handle,
    settings: VideoCreateSettings | None = None,
    block_id: str | None = None,
) -> Handles:
    settings = settings or VideoCreateSettings()
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.video.create",
        "CreateVideo",
        block_id=block_id,
        inputs={"fps": settings.fps},
    )
    connect(workflow, images, node, "images")
    connect(workflow, settings.audio, node, "audio")
    connect(workflow, settings.fps_source, node, "fps")
    return Handles(video=Handle(node_id=node.id, output_slot=0, name="video"))
