# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


CLIP_NAME = 'qwen_3_4b.safetensors'
CONTROL_AFTER_GENERATE = 'randomize'
DEFAULT_PROMPT = "Change the background to a cozy, softly lit interior space with warm beige tones, soft natural window light filtering through, and a relaxed, intimate atmosphere similar to the original image's mood. Keep the person in the exact same position, scale, and pose. Maintain identical camera angle, framing, and perspective. The lighting should be soft, even, and warm - not harsh or bright. Only replace the room environment, preserving all facial features, hairstyle, expression, clothing, and pose exactly as they are."
DEFAULT_PROMPT_2 = "A stylish young woman with dark skin wearing a plush deep emerald green bathrobe, light pink towel turban, and red heart-shaped sunglasses, seated on a light-colored rattan chair with soft pink cushions, positioned in front of a textured dusty rose pink wall with an arched alcove, large tropical plants with broad dark green leaves framing both sides, woven straw baskets on the floor, remove any existing shoes from the background, only the woman's beige woven sandals visible in the foreground, soft natural lighting casting gentle shadows, warm bohemian chic aesthetic, professional fashion photography"
DEFAULT_SEED = 1111443136920027
DEFAULT_SEED_2 = 133932424540642
GUIDE_STRENGTH = 5
SAMPLER_NAME = 'euler'
TEXT = ''
TYPE = 'flux2'
UNET_NAME = 'flux-2-klein-base-4b-fp8.safetensors'
UPSCALE_METHOD = 'nearest-exact'
VAE_NAME = 'full_encoder_small_decoder.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4b-fp8/resolve/main/flux-2-klein-base-4b-fp8.safetensors', sha256='44bab3a86fe98b85d21dd2a4729ebdc3ae51fb8a39f76e457e18c724219e6840', hf_revision='103db268c10d4d3921101b46057671f9ac460da6', size_bytes=4089498488, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', sha256='6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a', hf_revision='2f862278568d3f0a83167a16e5f11094da6dee72', size_bytes=8044982048, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    models=MODELS,
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}},
    approach='official Flux.2 Klein 4B base image-edit workflow',
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_4b(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 4B) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json.
    # vibecomfy source hash: sha256:93485ad599c8953cdc6bfb19a765b319305d8f31faef9dea11b21cf8d0d61953
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncodex2, VAELoader, EmptyFlux2LatentImage, ImageScaleToTotalPixels, GetImageSize, ReferenceLatentx2, VAEEncode.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=1111443136920027,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
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


def image_edit_flux2_klein_9b(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 9B) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json.
    # vibecomfy source hash: sha256:9865b964bc214fb9bbe16fb67ea685334baa13e88d122a7abc41e3eee75af6a3
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, VAELoader, GetImageSize, EmptyFlux2LatentImage, ImageScaleToTotalPixelsx2, CLIPLoader, CLIPTextEncodex2, CFGGuider, Flux2Scheduler, ReferenceLatentx4, VAEEncodex2.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler')

    randomnoise = RandomNoise(
        noise_seed=133932424540642,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(unet_name=unet_name)
    vaeloader = VAELoader(vae_name=vae_name)

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
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
        image, mask = LoadImage(image=public('image', default='robed_women.png'))
        image_load, mask_load = LoadImage(image='pink_tone_chair.png')
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

