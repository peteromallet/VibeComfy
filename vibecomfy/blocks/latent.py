from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class HunyuanVideoShape:
    width: int = 832
    height: int = 480
    length: int = 33
    batch_size: int = 1


@block
def empty_hunyuan_video(
    workflow: VibeWorkflow,
    *,
    shape: HunyuanVideoShape | None = None,
    block_id: str | None = None,
) -> Handles:
    shape = shape or HunyuanVideoShape()
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.latent.empty_hunyuan_video",
        "EmptyHunyuanLatentVideo",
        block_id=block_id,
        inputs={"width": shape.width, "height": shape.height, "length": shape.length, "batch_size": shape.batch_size},
    )
    return Handles(latent=Handle(node_id=node.id, output_slot=0, name="latent"))
