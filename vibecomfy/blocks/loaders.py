from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class LoaderNames:
    unet_name: str
    clip_name: str
    vae_name: str
    unet_weight_dtype: str = "default"
    clip_type: str = "wan"
    clip_device: str = "default"


@block
def unet_clip_vae(
    workflow: VibeWorkflow,
    *,
    names: LoaderNames,
    block_id: str | None = None,
) -> Handles:
    unet = add_block_node(
        workflow,
        "vibecomfy.blocks.loaders.unet_clip_vae",
        "UNETLoader",
        block_id=block_id,
        inputs={"unet_name": names.unet_name, "weight_dtype": names.unet_weight_dtype},
    )
    clip = add_block_node(
        workflow,
        "vibecomfy.blocks.loaders.unet_clip_vae",
        "CLIPLoader",
        block_id=block_id,
        inputs={"clip_name": names.clip_name, "type": names.clip_type, "device": names.clip_device},
    )
    vae = add_block_node(
        workflow,
        "vibecomfy.blocks.loaders.unet_clip_vae",
        "VAELoader",
        block_id=block_id,
        inputs={"vae_name": names.vae_name},
    )
    return Handles(
        unet=Handle(node_id=unet.id, output_slot=0, name="unet"),
        model=Handle(node_id=unet.id, output_slot=0, name="model"),
        clip=Handle(node_id=clip.id, output_slot=0, name="clip"),
        vae=Handle(node_id=vae.id, output_slot=0, name="vae"),
    )


@block
def clip_vision(
    workflow: VibeWorkflow,
    *,
    clip_name: str,
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.loaders.clip_vision",
        "CLIPVisionLoader",
        block_id=block_id,
        inputs={"clip_name": clip_name},
    )
    return Handles(clip_vision=Handle(node_id=node.id, output_slot=0, name="clip_vision"))


@block
def load_image(
    workflow: VibeWorkflow,
    *,
    image: str,
    upload: str = "image",
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.loaders.load_image",
        "LoadImage",
        block_id=block_id,
        inputs={"image": image},
    )
    node.metadata["widget_kwargs"]["upload"] = upload
    return Handles(image=Handle(node_id=node.id, output_slot=0, name="image"))
