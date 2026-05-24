# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'qwen_3_8b_fp8mixed.safetensors'
DEFAULT_SEED = 653844576367526
GUIDE_STRENGTH = 5
TEXT = ''
UNET_NAME = 'flux-2-klein-base-9b-fp8.safetensors'
VAE_NAME = 'full_encoder_small_decoder.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    models=MODELS,
    output_prefix='Flux2-Klein',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        ksamplerselect = KSamplerSelect(sampler_name='euler')
        unetloader = UNETLoader(unet_name=UNET_NAME)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='flux2')
        vaeloader = VAELoader(vae_name=VAE_NAME)
        randomnoise = RandomNoise(noise_seed=public('seed', default=DEFAULT_SEED))

        # Inputs
        primitiveint = raw_call('PrimitiveInt', '75:68', value=public('width', default=1024))
        primitiveint_2 = raw_call('PrimitiveInt', '75:69', value=public('height', default=1024))
        flux2scheduler = Flux2Scheduler(width=primitiveint, height=primitiveint_2)

        emptyflux2latentimage = EmptyFlux2LatentImage(
            width=primitiveint,
            height=primitiveint_2,
        )

        # Conditioning
        negative = CLIPTextEncode(
            text=public('negative_prompt', default=TEXT),
            clip=cliploader,
        )

        positive = CLIPTextEncode(text=public('prompt', default=TEXT), clip=cliploader)

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
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

        # Decode
        vaedecode = VAEDecode(samples=output, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(filename_prefix='Flux2-Klein', images=vaedecode)


        wf.register_input('model', '2', 'unet_name', UNET_NAME)
        return wf.finalize({}, spec=OUTPUT_SPEC)

