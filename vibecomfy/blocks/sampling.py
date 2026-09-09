from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class KSamplerSettings:
    seed: int = 0
    control_after_generate: str = "randomize"
    steps: int = 30
    cfg: int | float = 6
    sampler_name: str = "uni_pc"
    scheduler: str = "simple"
    denoise: int | float = 1


@block
def model_sampling_sd3(
    workflow: VibeWorkflow,
    *,
    model: str | Handle,
    shift: int | float = 8,
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.sampling.model_sampling_sd3",
        "ModelSamplingSD3",
        block_id=block_id,
        inputs={"shift": shift},
    )
    connect(workflow, model, node, "model")
    return Handles(model=Handle(node_id=node.id, output_slot=0, name="model"))


@block
def ksampler(
    workflow: VibeWorkflow,
    *,
    model: str | Handle,
    positive: str | Handle,
    negative: str | Handle,
    latent: str | Handle,
    settings: KSamplerSettings | None = None,
    block_id: str | None = None,
) -> Handles:
    settings = settings or KSamplerSettings()
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.sampling.ksampler",
        "KSampler",
        block_id=block_id,
        inputs={
            "seed": settings.seed,
            "steps": settings.steps,
            "cfg": settings.cfg,
            "sampler_name": settings.sampler_name,
            "scheduler": settings.scheduler,
            "denoise": settings.denoise,
        },
        metadata={"control_after_generate": settings.control_after_generate},
    )
    connect(workflow, model, node, "model")
    connect(workflow, positive, node, "positive")
    connect(workflow, negative, node, "negative")
    connect(workflow, latent, node, "latent_image")
    return Handles(samples=Handle(node_id=node.id, output_slot=0, name="samples"))
