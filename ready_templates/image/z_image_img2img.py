# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ImageScale, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


CLIP_NAME = 'qwen_3_4b.safetensors'
DEFAULT_PROMPT = 'A compact red cube on a clean white tabletop, product-photo lighting.'
DEFAULT_SEED = 770044821593082
GUIDE_STRENGTH = 1.0
UNET_NAME = 'z_image_turbo_bf16.safetensors'
VAE_NAME = 'ae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors', subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors', subdir='vae'),
}


PUBLIC_INPUT_METADATA = {
    'diffusion_model': InputSpec(node='2', field='unet_name', default=UNET_NAME, type='CHOICE'),
    'text_encoder': InputSpec(node='3', field='clip_name', default=CLIP_NAME, type='CHOICE'),
    'vae': InputSpec(node='4', field='vae_name', default=VAE_NAME, type='CHOICE'),
    'steps': InputSpec(node='10', field='steps', default=8, type='INT'),
    'guidance': InputSpec(node='10', field='cfg', default=GUIDE_STRENGTH, type='FLOAT'),
    'strength': InputSpec(node='10', field='denoise', default=0.7, type='FLOAT'),
    'image': InputSpec(node='1', field='image', default='image_z_image_img2img_input.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='8', field='width', default=1024, type='INT'),
    'height': InputSpec(node='8', field='height', default=1024, type='INT'),
    'seed': InputSpec(node='10', field='seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='6', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_image',
    inputs=PUBLIC_INPUT_METADATA,
    unbound_inputs={},
    models=MODELS,
    approach='Z-Image Turbo img2img via VAEEncode init latent and KSampler denoise strength',
    runtime_note='Adapts official Turbo sampling to a VAEEncode init latent with denoise 0.7.',
    smoke_resolution='1024x1024',
    provenance={'source_workflow': 'ready_templates/image/z_image_img2img.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='1', image='image_z_image_img2img_input.png')

    # Loaders
    unetloader = UNETLoader(_id='2', unet_name=UNET_NAME, weight_dtype='default')
    cliploader = CLIPLoader(_id='3', clip_name=CLIP_NAME, type='lumina2')
    vaeloader = VAELoader(_id='4', vae_name=VAE_NAME)
    modelsamplingauraflow = ModelSamplingAuraFlow(_id='5', shift=3, model=unetloader)

    # Conditioning
    positive = CLIPTextEncode(_id='6', text=DEFAULT_PROMPT, clip=cliploader)
    negative = CLIPTextEncode(_id='7', text='', clip=cliploader)

    imagescale = ImageScale(
        _id='8',
        upscale_method='lanczos',
        width=1024,
        height=1024,
        crop='center',
        image=image,
    )

    vaeencode = VAEEncode(_id='9', pixels=imagescale, vae=vaeloader)

    # Sampling
    ksampler = KSampler(
        _id='10',
        seed=DEFAULT_SEED,
        steps=8,
        cfg=GUIDE_STRENGTH,
        sampler_name='res_multistep',
        scheduler='simple',
        denoise=0.7,
        latent_image=vaeencode,
        model=modelsamplingauraflow,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(_id='11', samples=ksampler, vae=vaeloader)

    # Outputs
    saveimage = SaveImage(_id='12', filename_prefix='z-image-img2img', images=vaedecode)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='z-image-img2img')

