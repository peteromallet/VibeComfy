# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, PrimitiveStringMultiline, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'qwen_3_4b.safetensors'
DEFAULT_SEED = 0
GUIDE_STRENGTH = 5
UNET_NAME = 'flux-2-klein-base-4b.safetensors'
VAE_NAME = 'flux2-vae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors', sha256='9c5fed22b76baea749d88fc2abe3ad53245e7b21a0d353a762665eea00043b92', hf_revision='a9e4ca87c16db4c4e1a16406a9ddb300ab0ae246', size_bytes=7751105712, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', sha256='6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a', hf_revision='a9e4ca87c16db4c4e1a16406a9ddb300ab0ae246', size_bytes=8044982048, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors', sha256='d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5', hf_revision='03d6521e6f6a47396b3f951cbea50f7e6c2f482e', size_bytes=336213556, subdir='vae'),
    'diffusion_model_2': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors', sha256='ec3d4e733a771f61c052fb4856c48b336c55eaf2c65487c2a1faeb9bbda7a343', hf_revision='a9e4ca87c16db4c4e1a16406a9ddb300ab0ae246', size_bytes=7751105712, subdir='diffusion_models'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    models=MODELS,
    output_prefix='Flux2-Klein',
    provenance={'source_workflow': 'workflow_corpus/official/image/flux2_klein_4b_t2i.json'},
)

# === Subgraph functions ===

def text_to_image_flux2_klein_4b(
    *,
    value: int,
    value_1: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
):
    """Text to Image (Flux.2 Klein 4B).

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/image/flux2_klein_4b_t2i.json.
    # vibecomfy source hash: sha256:4f6fda27ff63175e29ec1d087b2e157d70f8a682fb4adfd4b97226bbda7bdb01
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, CLIPTextEncodex2, PrimitiveIntx2, RandomNoise, UNETLoader, CLIPLoader, VAELoader.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    primitiveint = raw_call('PrimitiveInt', '68', control_after_generate='fixed', value=value)
    primitiveint_2 = raw_call('PrimitiveInt', '69', control_after_generate='fixed', value=value_1)
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)
    randomnoise = RandomNoise(control_after_generate='randomize')
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


def text_to_image_flux2_klein_4b_distilled(
    *,
    value: int,
    value_1: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
):
    """Text to Image (Flux.2 Klein 4B Distilled).

    Materialized from subgraph a67caa28-5f85-4917-8396-36004960dd30 in workflow_corpus/official/image/flux2_klein_4b_t2i.json.
    # vibecomfy source hash: sha256:97819775f269a73243eadfdb0cb3a1763e929729ceae95bbb2e1dbd751082a72
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, PrimitiveIntx2, RandomNoise, UNETLoader, CLIPLoader, VAELoader, CFGGuider, ConditioningZeroOut, CLIPTextEncode, Flux2Scheduler.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    primitiveint = raw_call('PrimitiveInt', '68', control_after_generate='fixed', value=value)
    primitiveint_2 = raw_call('PrimitiveInt', '69', control_after_generate='fixed', value=value_1)
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=432262096973490,
        control_after_generate='randomize',
    )

    flux2scheduler = Flux2Scheduler(steps=4, width=primitiveint, height=primitiveint_2)

    emptyflux2latentimage = EmptyFlux2LatentImage(
        width=primitiveint,
        height=primitiveint_2,
    )

    positive = CLIPTextEncode(text=prompt, clip=cliploader)
    conditioningzeroout = ConditioningZeroOut(conditioning=positive)

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=conditioningzeroout,
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
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        ksamplerselect = KSamplerSelect(sampler_name='euler')
        unetloader = UNETLoader(unet_name=UNET_NAME)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='flux2')
        vaeloader = VAELoader(vae_name=VAE_NAME)
        randomnoise = RandomNoise(noise_seed=public('seed', default=DEFAULT_SEED))

        primitivestringmultiline = PrimitiveStringMultiline(
            value=public('prompt', default='A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera style, slight noise, flash photography, candid moment, 2000s digicam aesthetic, festive birthday celebration atmosphere\n'),
        )

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
            text=public('negative_prompt', default=''),
            clip=cliploader,
        )

        positive = CLIPTextEncode(text=primitivestringmultiline, clip=cliploader)

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

