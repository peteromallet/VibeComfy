from __future__ import annotations

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@block
def text_pair(
    workflow: VibeWorkflow,
    *,
    clip: str | Handle,
    positive: str,
    negative: str = "",
    block_id: str | None = None,
) -> Handles:
    pos = add_block_node(
        workflow,
        "vibecomfy.blocks.encoding.text_pair",
        "CLIPTextEncode",
        block_id=block_id,
        inputs={"text": positive},
    )
    neg = add_block_node(
        workflow,
        "vibecomfy.blocks.encoding.text_pair",
        "CLIPTextEncode",
        block_id=block_id,
        inputs={"text": negative},
    )
    connect(workflow, clip, pos, "clip")
    connect(workflow, clip, neg, "clip")
    return Handles(
        positive=Handle(node_id=pos.id, output_slot=0, name="positive"),
        negative=Handle(node_id=neg.id, output_slot=0, name="negative"),
    )


@block
def clip_vision(
    workflow: VibeWorkflow,
    *,
    clip_vision: str | Handle,
    image: str | Handle,
    crop: str = "center",
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.encoding.clip_vision",
        "CLIPVisionEncode",
        block_id=block_id,
        inputs={"crop": crop},
    )
    connect(workflow, clip_vision, node, "clip_vision")
    connect(workflow, image, node, "image")
    return Handles(
        clip_vision_output=Handle(node_id=node.id, output_slot=0, name="clip_vision_output"),
        encoded=Handle(node_id=node.id, output_slot=0, name="encoded"),
    )
