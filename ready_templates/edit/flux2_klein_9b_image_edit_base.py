# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


CLIP_NAME = 'qwen_3_8b_fp8mixed.safetensors'
CONTROL_AFTER_GENERATE = 'randomize'
DEFAULT_PROMPT = "Change the camera angle to a first-person driver's perspective looking through the steering wheel at the dashboard and windshield, maintaining the same white minimalist interior style and lighting\n"
DEFAULT_PROMPT_2 = 'Apply the yellow "C" logo to the center hub of the steering wheel, and change the steering wheel color to royal blue matching the logo background, while maintaining the same interior style, lighting, camera angle, and all other elements unchanged'
DEFAULT_SEED = 192774551144773
DEFAULT_SEED_2 = 86928255107192
GUIDE_STRENGTH = 5
SAMPLER_NAME = 'euler'
TEXT = ''
TYPE = 'flux2'
UNET_NAME = 'flux-2-klein-base-9b-fp8.safetensors'
UPSCALE_METHOD = 'lanczos'
VAE_NAME = 'full_encoder_small_decoder.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors', gated=True, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    models=MODELS,
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}},
    approach='official Flux.2 Klein 9B base image-edit workflow',
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_9b(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 9B) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json.
    # vibecomfy source hash: sha256:b2d3d67eb296d6e0e41bc55934c4f7c02695f20c73be184bf6fe5349ebefd8af
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncodex2, VAELoader, EmptyFlux2LatentImage, ImageScaleToTotalPixels, GetImageSize, ReferenceLatentx2, VAEEncode.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=192774551144773,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='lanczos',
        image=image,
    )

    negative = CLIPTextEncode(text='', clip=cliploader)
    cliptextencode = CLIPTextEncode(text=prompt, clip=cliploader)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels)
    vaeencode = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)
    flux2scheduler = Flux2Scheduler(width=width, height=height)
    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    referencelatent = ReferenceLatent(conditioning=negative, latent=vaeencode)
    referencelatent_2 = ReferenceLatent(conditioning=cliptextencode, latent=vaeencode)

    cfgguider = CFGGuider(
        cfg=5,
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


def image_edit_flux2_klein_9b_dual(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 9B) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json.
    # vibecomfy source hash: sha256:99bcee3dbb6e2838d7c3275e03f30c27d09b5f53173f2f049a42eff86bbb883c
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, VAELoader, GetImageSize, EmptyFlux2LatentImage, ImageScaleToTotalPixelsx2, CLIPLoader, CLIPTextEncodex2, CFGGuider, Flux2Scheduler, ReferenceLatentx4, VAEEncodex2.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='lanczos',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler')

    randomnoise = RandomNoise(
        noise_seed=86928255107192,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(unet_name=unet_name)
    vaeloader = VAELoader(vae_name=vae_name)

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        upscale_method='lanczos',
        image=reference_image1,
    )

    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    negative = CLIPTextEncode(text='', clip=cliploader)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels_2)
    cliptextencode = CLIPTextEncode(text=prompt, clip=cliploader)
    vaeencode = VAEEncode(pixels=imagescaletototalpixels_2, vae=vaeloader)
    vaeencode_2 = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)
    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    flux2scheduler = Flux2Scheduler(width=width, height=height)
    referencelatent = ReferenceLatent(conditioning=negative, latent=vaeencode)
    referencelatent_2 = ReferenceLatent(conditioning=cliptextencode, latent=vaeencode)

    referencelatent_3 = ReferenceLatent(
        conditioning=referencelatent,
        latent=vaeencode_2,
    )

    referencelatent_4 = ReferenceLatent(
        conditioning=referencelatent_2,
        latent=vaeencode_2,
    )

    cfgguider = CFGGuider(
        cfg=5,
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
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(
            image=public('image', default='car_interior_white.jpeg'),
        )

        image_load, mask_load = LoadImage(image='comfy_logo_blue.png')
        ksamplerselect = KSamplerSelect(sampler_name=SAMPLER_NAME)
        unetloader = UNETLoader(unet_name=UNET_NAME)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_=TYPE)
        vaeloader = VAELoader(vae_name=VAE_NAME)

        randomnoise = RandomNoise(
            noise_seed=public('seed', default=DEFAULT_SEED),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        ksamplerselect_2 = KSamplerSelect(sampler_name=SAMPLER_NAME)

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        unetloader_2 = UNETLoader(unet_name=UNET_NAME)
        vaeloader_2 = VAELoader(vae_name=VAE_NAME)
        cliploader_2 = CLIPLoader(clip_name=CLIP_NAME, type_=TYPE)

        imagescaletototalpixels = ImageScaleToTotalPixels(
            upscale_method=UPSCALE_METHOD,
            image=image,
        )

        # Conditioning
        negative = CLIPTextEncode(text=public('prompt', default=TEXT), clip=cliploader)
        cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)

        imagescaletototalpixels_2 = ImageScaleToTotalPixels(
            upscale_method=UPSCALE_METHOD,
            image=image_load,
        )

        imagescaletototalpixels_3 = ImageScaleToTotalPixels(
            upscale_method=UPSCALE_METHOD,
            image=image,
        )

        negative_2 = CLIPTextEncode(text=TEXT, clip=cliploader_2)
        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader_2)
        width, height, batch_size = GetImageSize(image=imagescaletototalpixels)
        vaeencode = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)

        width_get, height_get, batch_size_get = GetImageSize(
            image=imagescaletototalpixels_3,
        )

        vaeencode_2 = VAEEncode(pixels=imagescaletototalpixels_3, vae=vaeloader_2)
        vaeencode_3 = VAEEncode(pixels=imagescaletototalpixels_2, vae=vaeloader_2)
        flux2scheduler = Flux2Scheduler(width=width, height=height)
        emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
        referencelatent = ReferenceLatent(conditioning=negative, latent=vaeencode)

        referencelatent_2 = ReferenceLatent(
            conditioning=cliptextencode,
            latent=vaeencode,
        )

        emptyflux2latentimage_2 = EmptyFlux2LatentImage(
            width=width_get,
            height=height_get,
        )

        flux2scheduler_2 = Flux2Scheduler(width=width_get, height=height_get)
        referencelatent_3 = ReferenceLatent(conditioning=negative_2, latent=vaeencode_2)

        referencelatent_4 = ReferenceLatent(
            conditioning=cliptextencode_2,
            latent=vaeencode_2,
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=unetloader,
            negative=referencelatent,
            positive=referencelatent_2,
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
            negative=referencelatent_5,
            positive=referencelatent_6,
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
        saveimage = SaveImage(filename_prefix='Flux2-Klein-4b-base', images=vaedecode)

        saveimage_2 = SaveImage(
            filename_prefix='Flux2-Klein-4b-base',
            images=vaedecode_2,
        )


        wf.register_input('model', '4', 'unet_name', UNET_NAME)
        return wf.finalize({}, output_node=saveimage, filename_prefix='Flux2-Klein-4b-base', spec=OUTPUT_SPEC)

