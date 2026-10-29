# ported from ready_templates/sources/official/image/z_image_turbo.json (sha256: fd880c78bba7a771d624cd0224a85f5e9b2e000323d285133999fe663a7dbd3e)
"""Z-Image Turbo, preserving the official eight-step Turbo graph settings."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, EmptySD3LatentImage, KSampler, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader

UNET_NAME = 'z_image_turbo_bf16.safetensors'
CLIP_NAME = 'qwen_3_4b.safetensors'
VAE_NAME = 'ae.safetensors'
DEFAULT_PROMPT = 'A compact red cube on a clean white tabletop, product-photo lighting.'
DEFAULT_SEED = 0
MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors', subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors', subdir='vae'),
}
PUBLIC_INPUT_METADATA = {
    'diffusion_model': InputSpec(node='1', field='unet_name', default=UNET_NAME, type='CHOICE'),
    'text_encoder': InputSpec(node='2', field='clip_name', default=CLIP_NAME, type='CHOICE'),
    'vae': InputSpec(node='3', field='vae_name', default=VAE_NAME, type='CHOICE'),
    'prompt': InputSpec(node='5', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='6', field='text', default='', type='STRING', media_semantics='text'),
    'width': InputSpec(node='7', field='width', default=1024, type='INT'),
    'height': InputSpec(node='7', field='height', default=1024, type='INT'),
    'seed': InputSpec(node='8', field='seed', default=DEFAULT_SEED, type='INT'),
    'steps': InputSpec(node='8', field='steps', default=8, type='INT'),
    'guidance': InputSpec(node='8', field='cfg', default=1.0, type='FLOAT'),
}
READY_METADATA = ReadyMetadata.build(
    capability='image',
    inputs=PUBLIC_INPUT_METADATA,
    unbound_inputs={},
    models=MODELS,
    approach='Official Z-Image Turbo weights and eight-step sampling',
    provenance={'source_workflow': 'ready_templates/sources/official/image/z_image_turbo.json'},
)


def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)
    unet = UNETLoader(_id='1', unet_name=UNET_NAME, weight_dtype='default')
    clip = CLIPLoader(_id='2', clip_name=CLIP_NAME, type='lumina2')
    vae = VAELoader(_id='3', vae_name=VAE_NAME)
    model = ModelSamplingAuraFlow(_id='4', shift=3, model=unet)
    positive = CLIPTextEncode(_id='5', text=DEFAULT_PROMPT, clip=clip)
    negative = CLIPTextEncode(_id='6', text='', clip=clip)
    latent = EmptySD3LatentImage(_id='7', width=1024, height=1024, batch_size=1)
    samples = KSampler(
        _id='8', seed=DEFAULT_SEED, steps=8, cfg=1.0,
        sampler_name='res_multistep', scheduler='simple', denoise=1.0,
        model=model, positive=positive, negative=negative, latent_image=latent,
    )
    decoded = VAEDecode(_id='9', samples=samples, vae=vae)
    saved = SaveImage(_id='10', filename_prefix='z-image-turbo', images=decoded)
    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saved, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='z-image-turbo')
