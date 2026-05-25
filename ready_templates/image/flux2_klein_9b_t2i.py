# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors', gated=True, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    models=MODELS,
    approach='official Flux.2 Klein 9B text-to-image safetensors workflow',
    provenance={'source_workflow': 'workflow_corpus/official/image/flux2_klein_9b_t2i.json'},
)

# === Subgraph functions ===

def text_to_image_flux2_klein_9b(
    *,
    width: int,
    height: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
):
    """Text to Image (Flux.2 Klein 9B).

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/image/flux2_klein_9b_t2i.json.
    # vibecomfy source hash: sha256:721943a21357209f79de4ff8d50740647e3575b1ef0cc12831e79830f80decfb
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, CLIPTextEncodex2, PrimitiveIntx2, RandomNoise, UNETLoader, CLIPLoader, VAELoader.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    primitiveint = raw_call('PrimitiveInt', '68', control_after_generate='fixed', value=width)
    primitiveint_2 = raw_call('PrimitiveInt', '69', control_after_generate='fixed', value=height)
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=653844576367526,
        control_after_generate='randomize',
    )

    flux2scheduler = Flux2Scheduler(width=primitiveint, height=primitiveint_2)

    emptyflux2latentimage = EmptyFlux2LatentImage(
        width=primitiveint,
        height=primitiveint_2,
    )

    negative = CLIPTextEncode(text='', clip=cliploader)
    positive = CLIPTextEncode(text=prompt, clip=cliploader)

    cfgguider = CFGGuider(
        cfg=5,
        model=unetloader,
        negative=negative,
        positive=positive,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    vaedecode = VAEDecode(samples=output, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    edited = text_to_image_flux2_klein_9b(
        width=1024,
        height=1024,
        unet_name='flux-2-klein-base-9b-fp8.safetensors',
        clip_name='qwen_3_8b_fp8mixed.safetensors',
        vae_name='full_encoder_small_decoder.safetensors',
        prompt='',
    )
    saveimage = SaveImage(filename_prefix='Flux2-Klein', images=edited)

    return wf.finalize({}, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

