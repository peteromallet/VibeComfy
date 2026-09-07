# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='76', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image',
    inputs=PUBLIC_INPUT_METADATA,
    provenance={'source_path': 'ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json', 'source_id': 'edit/flux2_klein_4b_image_edit_distilled', 'upstream_source_id': 'flux2_klein_4b_image_edit_distilled', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json', 'output_mode': 'ready_template', 'ready_id': 'edit/flux2_klein_4b_image_edit_distilled'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_4b_distilled(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 4B Distilled) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:e532a05f63f1bca6714349dfeb92151f8d66393fe1f88595bed4e404e642b2d6
    Inner nodes: KSamplerSelect, UNETLoader, CLIPLoader, VAELoader, EmptyFlux2LatentImage, ImageScaleToTotalPixels, Flux2Scheduler, CLIPTextEncode, ConditioningZeroOut, ReferenceLatentx2, GetImageSize, VAEEncode, SamplerCustomAdvanced, VAEDecode, RandomNoise, CFGGuider.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=43301611940728,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=image,
    )

    cliptextencode = CLIPTextEncode(text=prompt, clip=cliploader)
    width, height, _ = GetImageSize(image=imagescaletototalpixels)
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

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    vaedecode = VAEDecode(samples=output, vae=vaeloader)

    return vaedecode


def reference_conditioning(
    *,
    positive,
    negative,
    pixels,
    vae,
):
    """Reference Conditioning - single-image variant.

    Materialized from subgraph 27eacb9f-0da2-421d-a0bf-b4b4e5fe5709 in ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:0a54ae9cc50d44681b6bf8ae109ddc6010b6ae19d9222f4581ca22dc967db4b0
    Inner nodes: ReferenceLatentx2, VAEEncode.
    """

    vaeencode = VAEEncode(pixels=pixels, vae=vae)
    referencelatent = ReferenceLatent(conditioning=negative, latent=vaeencode)
    referencelatent_2 = ReferenceLatent(conditioning=positive, latent=vaeencode)

    return referencelatent_2, referencelatent


def reference_conditioning_93041a64(
    *,
    positive,
    negative,
    pixels,
    vae,
):
    """Reference Conditioning - single-image variant.

    Materialized from subgraph 93041a64-452a-477a-9447-40330b7c1136 in ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:b77feaa1986e88bb2b5924db33685bce2c22a9498c9969a3624ae0b7955ff0db
    Inner nodes: ReferenceLatentx2, VAEEncode.
    """

    vaeencode = VAEEncode(pixels=pixels, vae=vae)
    referencelatent = ReferenceLatent(conditioning=negative, latent=vaeencode)
    referencelatent_2 = ReferenceLatent(conditioning=positive, latent=vaeencode)

    return referencelatent_2, referencelatent


def image_edit_flux2_klein_4b_distilled_dual(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 4B Distilled) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:56221cc5c44463fbeff7b13305983b432aea67f150181e0ca528f120ab5daf6a
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncode, VAELoader, ImageScaleToTotalPixelsx2, 27eacb9f-0da2-421d-a0bf-b4b4e5fe5709, 93041a64-452a-477a-9447-40330b7c1136, ConditioningZeroOut, EmptyFlux2LatentImage, GetImageSize.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler')

    randomnoise = RandomNoise(
        noise_seed=786795143695419,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=reference_image1,
    )

    cliptextencode = CLIPTextEncode(text=prompt, clip=cliploader)
    width, height, _ = GetImageSize(image=imagescaletototalpixels_2)
    conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)
    flux2scheduler = Flux2Scheduler(steps=4, width=width, height=height)
    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)

    conditioning, conditioning_1 = reference_conditioning(
        positive=cliptextencode,
        negative=conditioningzeroout,
        pixels=imagescaletototalpixels_2,
        vae=vaeloader,
    )

    conditioning_2, conditioning_1_2 = reference_conditioning_93041a64(
        positive=conditioning,
        negative=conditioning_1,
        pixels=imagescaletototalpixels,
        vae=vaeloader,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=conditioning_1_2,
        positive=conditioning_2,
    )

    output, _ = SamplerCustomAdvanced(
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

    image, _ = LoadImage(_id='76', image='handbag_white.png')
    image_2, _ = LoadImage(_id='81', image='comfy_logo_blue.png')

    edited = image_edit_flux2_klein_4b_distilled(
        unet_name='flux-2-klein-4b-fp8.safetensors',
        clip_name='qwen_3_4b.safetensors',
        vae_name='flux2-vae.safetensors',
        prompt='Change the bag color to blue.',
        image=image,
    )

    edited_dual = image_edit_flux2_klein_4b_distilled_dual(
        unet_name='flux-2-klein-4b-fp8.safetensors',
        clip_name='qwen_3_4b.safetensors',
        vae_name='flux2-vae.safetensors',
        prompt='stylize the handbag in image1 with the colours and logo from image 2',
        reference_image1=image,
        reference_image2=image_2,
    )

    saveimage = SaveImage(_id='9', filename_prefix='Flux2-Klein', images=edited)
    saveimage_2 = SaveImage(_id='94', filename_prefix='Flux2-Klein', images=edited_dual)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

