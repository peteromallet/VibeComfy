# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ComfySwitchNode, EmptySD3LatentImage, KSampler, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
DEFAULT_PROMPT = 'Urban alleyway at dusk. Tall, statuesque high-fashion model striding elegantly, mid distant full body shot from an angular perspective, cinematic/editorial with bold contrasts and tactile materials. They wear a rose-gold metallic trench coat with deconstructed elements over a black long-sleeved turtleneck with subtle texture; paired with forest-green pleated pants with raw hems and a soft texture. Long braided dark hair, medium complexion. They carry a vibrant yellow designer handbag with geometric details and a structured silhouette. White architectural sneakers with bold geometric cutouts. Bold, high-contrast, tactile, urban-grit meets high-fashion impact, extreme clarity, extreme layering, post-processing with transparent light-transmitting ultra-smooth high-definition film effect, removing all noise and grain, removing all blur, removing all vintage feel, removing all roughness, drawn with 32K pixel precision, unparalleled fine line drawing of every single detail, the entire image like a brand new photograph, photorealistic\n'
DEFAULT_PROMPT_2 = '低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲'
DEFAULT_SEED = 464857551335368
LORA_NAME = 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors'
UNET_NAME = 'qwen_image_2512_fp8_e4m3fn.safetensors'
VAE_NAME = 'qwen_image_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='238:230', field='seed', default=DEFAULT_SEED, type='INT'),
    'width': InputSpec(node='238:232', field='width', default=1328, type='INT'),
    'height': InputSpec(node='238:232', field='height', default=1328, type='INT'),
    'prompt': InputSpec(node='238:227', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_image_2512_fp8_e4m3fn.safetensors', 'qwen_image_vae.safetensors']},
    provenance={'source_path': 'ready_templates/sources/official/image/qwen_image_2512.json', 'source_id': 'image/qwen_image_2512', 'upstream_source_id': 'qwen_image_2512', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/image/qwen_image_2512.json', 'output_mode': 'ready_template', 'ready_id': 'image/qwen_image_2512'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    cliploader = CLIPLoader(_id='238:219', clip_name=CLIP_NAME, type='qwen_image')
    vaeloader = VAELoader(_id='238:220', vae_name=VAE_NAME)
    unetloader = UNETLoader(_id='238:226', unet_name=UNET_NAME)

    # Sampling
    emptysd3latentimage = EmptySD3LatentImage(_id='238:232', width=1328, height=1328)

    comfyswitchnode_2 = ComfySwitchNode(
        _id='238:240',
        switch=['238:229', 0],
        on_false=['238:224', 0],
        on_true=['238:225', 0],
    )

    comfyswitchnode_3 = ComfySwitchNode(
        _id='238:243',
        switch=['238:229', 0],
        on_false=['238:223', 0],
        on_true=['238:218', 0],
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='238:221',
        lora_name=LORA_NAME,
        model=unetloader,
    )

    # Conditioning
    positive = CLIPTextEncode(_id='238:227', text=DEFAULT_PROMPT, clip=cliploader)
    negative = CLIPTextEncode(_id='238:228', text=DEFAULT_PROMPT_2, clip=cliploader)

    comfyswitchnode = ComfySwitchNode(
        _id='238:233',
        switch=['238:229', 0],
        on_false=unetloader,
        on_true=loraloadermodelonly,
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(
        _id='238:222',
        shift=3.1000000000000005,
        model=comfyswitchnode,
    )

    ksampler = KSampler(
        _id='238:230',
        seed=DEFAULT_SEED,
        sampler_name='euler',
        steps=comfyswitchnode_2,
        cfg=comfyswitchnode_3,
        latent_image=emptysd3latentimage,
        model=modelsamplingauraflow,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(_id='238:231', samples=ksampler, vae=vaeloader)

    # Outputs
    saveimage = SaveImage(_id='60', filename_prefix='Qwen-Image-2512', images=vaedecode)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Qwen-Image-2512')

