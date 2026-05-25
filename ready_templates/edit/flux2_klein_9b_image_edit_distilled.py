# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


CLIP_NAME = 'qwen_3_8b_fp8mixed.safetensors'
CONTROL_AFTER_GENERATE = 'randomize'
DEFAULT_PROMPT = 'Replace the background with a quiet coastal cliff at overcast sunset. Remove all buildings and streets. Add wind-shaped grass and a distant ocean horizon. Keep the subject’s pose and framing unchanged.'
DEFAULT_PROMPT_2 = 'Let this character hold the bag with both hands'
DEFAULT_SEED = 26416064315367
DEFAULT_SEED_2 = 583453753589969
GUIDE_STRENGTH = 1
SAMPLER_NAME = 'euler'
TYPE = 'flux2'
UNET_NAME = 'flux-2-klein-9b-fp8.safetensors'
UPSCALE_METHOD = 'lanczos'
VAE_NAME = 'full_encoder_small_decoder.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors', gated=True, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    models=MODELS,
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}},
    approach='official Flux.2 Klein 9B distilled image-edit workflow',
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_9b_distilled(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 9B Distilled) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:0b7a93c4ebae73fabb58354865af446dc745929583f3fafe5b72376fa5da1df4
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, EmptyFlux2LatentImage, CFGGuider, Flux2Scheduler, GetImageSize, ReferenceLatentx2, ImageScaleToTotalPixels, VAELoader, CLIPTextEncode, ConditioningZeroOut, VAEEncode.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=26416064315367,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=image,
    )

    cliptextencode = CLIPTextEncode(text=prompt, clip=cliploader)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels)
    vaeencode = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)
    flux2scheduler = Flux2Scheduler(steps=4, width=width, height=height)
    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)
    referencelatent_2 = ReferenceLatent(conditioning=cliptextencode, latent=vaeencode)

    referencelatent = ReferenceLatent(
        conditioning=conditioningzeroout,
        latent=vaeencode,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=referencelatent,
        positive=referencelatent_2,
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


def image_edit_flux2_klein_9b_distilled_dual(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 9B Distilled) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:e3e88715b6dc65b2dda2734513ba272914a1375e81ddf783dc057743d63912c3
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, GetImageSize, VAEEncodex2, ReferenceLatentx4, VAELoader, ImageScaleToTotalPixelsx2.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='lanczos',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler')

    randomnoise = RandomNoise(
        noise_seed=583453753589969,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        upscale_method='lanczos',
        image=reference_image1,
    )

    cliptextencode = CLIPTextEncode(text=prompt, clip=cliploader)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels_2)
    vaeencode = VAEEncode(pixels=imagescaletototalpixels_2, vae=vaeloader)
    vaeencode_2 = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)
    conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)
    flux2scheduler = Flux2Scheduler(steps=4, width=width, height=height)
    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    referencelatent_2 = ReferenceLatent(conditioning=cliptextencode, latent=vaeencode)

    referencelatent = ReferenceLatent(
        conditioning=conditioningzeroout,
        latent=vaeencode,
    )

    referencelatent_4 = ReferenceLatent(
        conditioning=referencelatent_2,
        latent=vaeencode_2,
    )

    referencelatent_3 = ReferenceLatent(
        conditioning=referencelatent,
        latent=vaeencode_2,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=referencelatent_3,
        positive=referencelatent_4,
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

    # Inputs
    image, mask = LoadImage(image='bold_outfit_woman.jpeg')
    image_load, mask_load = LoadImage(image='handbag_white.png')
    ksamplerselect = KSamplerSelect(sampler_name=SAMPLER_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_=TYPE)
    vaeloader = VAELoader(vae_name=VAE_NAME)

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )

    ksamplerselect_2 = KSamplerSelect(sampler_name=SAMPLER_NAME)

    randomnoise_2 = RandomNoise(
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )

    unetloader_2 = UNETLoader(unet_name=UNET_NAME)
    cliploader_2 = CLIPLoader(clip_name=CLIP_NAME, type_=TYPE)
    vaeloader_2 = VAELoader(vae_name=VAE_NAME)

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=image,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        upscale_method=UPSCALE_METHOD,
        image=image_load,
    )

    imagescaletototalpixels_3 = ImageScaleToTotalPixels(
        upscale_method=UPSCALE_METHOD,
        image=image,
    )

    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader_2)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels)
    vaeencode = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)
    conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)

    width_get, height_get, batch_size_get = GetImageSize(
        image=imagescaletototalpixels_3,
    )

    vaeencode_2 = VAEEncode(pixels=imagescaletototalpixels_3, vae=vaeloader_2)
    vaeencode_3 = VAEEncode(pixels=imagescaletototalpixels_2, vae=vaeloader_2)
    conditioningzeroout_2 = ConditioningZeroOut(conditioning=cliptextencode_2)
    flux2scheduler = Flux2Scheduler(steps=4, width=width, height=height)
    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    referencelatent = ReferenceLatent(conditioning=cliptextencode, latent=vaeencode)

    referencelatent_2 = ReferenceLatent(
        conditioning=conditioningzeroout,
        latent=vaeencode,
    )

    flux2scheduler_2 = Flux2Scheduler(steps=4, width=width_get, height=height_get)
    emptyflux2latentimage_2 = EmptyFlux2LatentImage(width=width_get, height=height_get)

    referencelatent_3 = ReferenceLatent(
        conditioning=cliptextencode_2,
        latent=vaeencode_2,
    )

    referencelatent_4 = ReferenceLatent(
        conditioning=conditioningzeroout_2,
        latent=vaeencode_2,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=unetloader,
        negative=referencelatent_2,
        positive=referencelatent,
    )

    referencelatent_5 = ReferenceLatent(
        conditioning=referencelatent_3,
        latent=vaeencode_3,
    )

    referencelatent_6 = ReferenceLatent(
        conditioning=referencelatent_4,
        latent=vaeencode_3,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=unetloader_2,
        negative=referencelatent_6,
        positive=referencelatent_5,
    )

    # Decode
    vaedecode = VAEDecode(samples=output, vae=vaeloader)

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=emptyflux2latentimage_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=flux2scheduler_2,
    )

    vaedecode_2 = VAEDecode(samples=output_sampler, vae=vaeloader_2)

    # Outputs
    saveimage = SaveImage(filename_prefix='Flux2-Klein', images=vaedecode)
    saveimage_2 = SaveImage(images=vaedecode_2)


    wf.register_input('model', unetloader.node.id, 'unet_name', UNET_NAME)

    PUBLIC_INPUTS = {
        'model': InputSpec(node=unetloader, field='unet_name', default=UNET_NAME),
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED),
        'prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT),
        'image': InputSpec(node=image, field='image', default='bold_outfit_woman.jpeg'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

