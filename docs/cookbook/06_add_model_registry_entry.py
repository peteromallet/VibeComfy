"""
06_add_model_registry_entry.py — Register a model asset for a template
=======================================================================

Show how to define a ``ModelAsset`` and wire it into a ready template's
MODELS dict and PUBLIC_INPUTS so the framework can download, cache, and
validate the model file.

Build-only by default — no network calls at module level.
"""

from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node, public

# ---------------------------------------------------------------------------
# 1. Define a ModelAsset
# ---------------------------------------------------------------------------
# A ModelAsset records the download URL, expected hash, subdirectory, and
# file size.  The framework uses this to:
#   - Download the model on first use (``vibecomfy fetch``)
#   - Validate integrity (SHA-256)
#   - Place it in the correct ComfyUI models/ subdirectory

MY_MODEL = ModelAsset(
    url="https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors",
    sha256="cc6cb27103417325ff94f52b7a5d2dde45a7515b25c255d8e396c90014281516",
    subdir="checkpoints",
    size_bytes=4265380512,
)

# ---------------------------------------------------------------------------
# 2. Wire it into the template
# ---------------------------------------------------------------------------
# The MODELS dict maps a key (used throughout the template) to the ModelAsset.
# PUBLIC_INPUTS lets users override the model filename at runtime.

MODELS = {
    "checkpoint": MY_MODEL,
}

# Public inputs are declared inline at the kwarg site with
# ``public(name, default=...)`` — the preferred form since v2.7.

METADATA = ReadyMetadata.build(
    capability="image",
    template_id="cookbook/model_registry_demo",
    models=MODELS,
    output_prefix="image/ModelRegistryDemo",
)


def build() -> "VibeWorkflow":
    """Build a workflow that uses the registered model (build-only)."""
    from vibecomfy.workflow import VibeWorkflow

    with new_workflow(METADATA, source_path=__file__) as wf:
        ckpt = node(
            "CheckpointLoaderSimple",
            ckpt_name=public("model", default=MY_MODEL.filename),
        )
        positive = node(
            "CLIPTextEncode",
            text=public("prompt", default="a painting of a robot"),
            clip=ckpt.out(1),
        )
        negative = node("CLIPTextEncode", text="blurry", clip=ckpt.out(1))
        latent = node("EmptyLatentImage", width=512, height=512, batch_size=1)
        ksampler = node(
            "KSampler",
            seed=public("seed", default=42),
            steps=20,
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
        node("SaveImage", filename_prefix="ModelRegistryDemo", images=decoded.out(0))
        return wf.finalize({}, output_type="SaveImage")


# ---------------------------------------------------------------------------
# 3. Inspect the model registry entry (no network)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Model Asset:")
    print(f"  Filename:  {MY_MODEL.filename}")
    print(f"  URL:       {MY_MODEL.url}")
    print(f"  SHA-256:   {MY_MODEL.sha256}")
    print(f"  Subdir:    {MY_MODEL.subdir}")
    print(f"  Size:      {MY_MODEL.size_bytes:,} bytes")

    wf = build()
    print(f"\nWorkflow: {wf.id}")
    print(f"  Nodes: {len(wf.nodes)}")
    print(f"  Public inputs: {list(wf.inputs.keys())}")
    print("✓ Model registry entry validated — no download required.")
    print("  Use `vibecomfy fetch` to download models when ready.")
