"""
02_tweak_prompt_seed_steps_run.py — Tweak inputs and run a template
===================================================================

Load a ready template, inspect its public inputs, tweak the prompt/seed/steps,
and (optionally) compile to API JSON for queueing.

All GPU/network work is guarded behind ``if __name__ == '__main__'``.
"""

from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node, public
from vibecomfy.workflow import VibeWorkflow

# ---------------------------------------------------------------------------
# 1. Build a template (just like 01_first_workflow.py)
# ---------------------------------------------------------------------------

# Normally you'd load this from a ready_template file.  Here we build one
# inline so the tutorial is self-contained.  Public inputs are declared
# inline at the kwarg site with ``public(name, default=...)`` — the
# preferred form since v2.7.

METADATA = ReadyMetadata.build(
    capability="image",
    template_id="cookbook/tweak_demo",
    models={},
    output_prefix="image/CookbookTweak",
)


def build() -> VibeWorkflow:
    with new_workflow(METADATA, source_path=__file__) as wf:
        ckpt = node("CheckpointLoaderSimple", ckpt_name="v1-5-pruned-emaonly.safetensors")
        positive = node(
            "CLIPTextEncode",
            text=public("prompt", default="a cat on a cloud"),
            clip=ckpt.out(1),
        )
        negative = node("CLIPTextEncode", text="blurry", clip=ckpt.out(1))
        latent = node("EmptyLatentImage", width=512, height=512, batch_size=1)
        ksampler = node(
            "KSampler",
            seed=public("seed", default=42),
            steps=public("steps", default=20),
            cfg=7.0,
            sampler_name="euler",
            scheduler="normal",
            denoise=1.0,
            model=ckpt.out(0),
            positive=positive.out(0),
            negative=negative.out(0),
            latent_image=latent.out(0),
        )
        decoded = node("VAEDecode", samples=ksampler.out(0), vae=ckpt.out(2))
        node("SaveImage", filename_prefix="CookbookTweak", images=decoded.out(0))
        return wf.finalize({}, output_type="SaveImage")


# ---------------------------------------------------------------------------
# 2. Tweak inputs programmatically
# ---------------------------------------------------------------------------

def tweak_and_inspect(
    prompt: str = "a dog in a spacesuit",
    seed: int = 12345,
    steps: int = 25,
) -> dict:
    """Build the template, override public inputs, and return API JSON."""
    wf = build()

    # Public inputs are stored in wf.inputs — change them before compile.
    if "prompt" in wf.inputs:
        wf.inputs["prompt"].value = prompt
    if "seed" in wf.inputs:
        wf.inputs["seed"].value = seed
    if "steps" in wf.inputs:
        wf.inputs["steps"].value = steps

    # Compile to API format (no GPU required).
    api = wf.compile("api")
    return {"api": api, "inputs": {k: v.value for k, v in wf.inputs.items()}}


# ---------------------------------------------------------------------------
# 3. Run (requires ComfyUI runtime — guarded)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = tweak_and_inspect(prompt="an astronaut riding a dinosaur", seed=42, steps=30)
    print(f"Public inputs: {result['inputs']}")
    print(f"API nodes: {len(result['api'])}")
    print("✓ Tweak-and-inspect workflow validated.")
    print("  To actually run: use `vibecomfy run` or the ComfyUI web UI.")
