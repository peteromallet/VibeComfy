# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ImageScale, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


CLIP_NAME = 'qwen_3_4b.safetensors'
DEFAULT_PROMPT = 'A compact red cube on a clean white tabletop, product-photo lighting.'
DEFAULT_SEED = 770044821593082
GUIDE_STRENGTH = 0.0
UNET_NAME = 'z_image_bf16.safetensors'
VAE_NAME = 'ae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors', subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors', subdir='vae'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='image_to_image',
    models=MODELS,
    approach='Z-Image Turbo img2img via VAEEncode init latent and KSampler denoise strength',
    runtime_note='Intended to match Reigh z_image_turbo_i2i production semantics.',
    smoke_resolution='1024x1024',
    provenance={'source_workflow': 'ready_templates/image/z_image_img2img.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(
            image=public('image', default='image_z_image_img2img_input.png'),
        )

        unetloader = UNETLoader(unet_name=UNET_NAME)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='lumina2')
        vaeloader = VAELoader(vae_name=VAE_NAME)
        modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=unetloader)

        # Conditioning
        positive = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=cliploader,
        )

        negative = CLIPTextEncode(text='', clip=cliploader)

        imagescale = ImageScale(
            upscale_method='lanczos',
            width=public('width', default=1024),
            height=public('height', default=1024),
            crop='center',
            image=image,
        )

        vaeencode = VAEEncode(pixels=imagescale, vae=vaeloader)

        ksampler = KSampler(
            seed=public('seed', default=DEFAULT_SEED),
            steps=public('steps', default=12),
            cfg=GUIDE_STRENGTH,
            sampler_name='res_multistep',
            denoise=0.7,
            latent_image=vaeencode,
            model=modelsamplingauraflow,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(filename_prefix='z-image-img2img', images=vaedecode)


        wf.register_input('model', '2', 'unet_name', UNET_NAME)
        return wf.finalize({}, filename_prefix='z-image-img2img', spec=OUTPUT_SPEC)

