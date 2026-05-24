# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ComfySwitchNode, EmptySD3LatentImage, KSampler, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
DEFAULT_PROMPT = 'Urban alleyway at dusk. Tall, statuesque high-fashion model striding elegantly, mid distant full body shot from an angular perspective, cinematic/editorial with bold contrasts and tactile materials. They wear a rose-gold metallic trench coat with deconstructed elements over a black long-sleeved turtleneck with subtle texture; paired with forest-green pleated pants with raw hems and a soft texture. Long braided dark hair, medium complexion. They carry a vibrant yellow designer handbag with geometric details and a structured silhouette. White architectural sneakers with bold geometric cutouts. Bold, high-contrast, tactile, urban-grit meets high-fashion impact, extreme clarity, extreme layering, post-processing with transparent light-transmitting ultra-smooth high-definition film effect, removing all noise and grain, removing all blur, removing all vintage feel, removing all roughness, drawn with 32K pixel precision, unparalleled fine line drawing of every single detail, the entire image like a brand new photograph, photorealistic\n'
DEFAULT_PROMPT_2 = '低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲'
DEFAULT_SEED = 1232512
LORA_NAME = 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors'
UNET_NAME = 'qwen_image_2512_fp8_e4m3fn.safetensors'
VAE_NAME = 'qwen_image_vae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors', sha256='5dc80554d5d83390046a2f4a94ece06afb7700bf7b0aaf8bde9769793875876b', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=20430679144, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors', sha256='cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=9384670680, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors', sha256='a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=253806246, subdir='vae'),
    'lora': ModelAsset(url='https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', sha256='ad12117461cb41e2ea637fec8df6392ce8e8550c47fbe2b829ed3deb98262066', hf_revision='a52649c9d0f6e1a248bff13f0df33bb8a2abdb52', size_bytes=1698951104, subdir='loras'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    models=MODELS,
    output_prefix='Qwen-Image-2512',
    smoke_resolution='768x768',
    runtime_variant='qwen-image-2512-lightning-4step-768px',
    approach='official Qwen-Image-2512 text-to-image workflow using the 4-step Lightning LoRA path for smoke/runtime validation',
    provenance={'source_workflow': 'workflow_corpus/official/image/qwen_image_2512.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='qwen_image')
        vaeloader = VAELoader(vae_name=VAE_NAME)
        unetloader = UNETLoader(unet_name=UNET_NAME)

        emptysd3latentimage = EmptySD3LatentImage(
            width=public('width', default=768),
            height=public('height', default=768),
        )

        # Inputs
        primitivefloat = raw_call('PrimitiveFloat', '238:218', value=1.0)
        primitivefloat_2 = raw_call('PrimitiveFloat', '238:223', value=1)
        primitiveint = raw_call('PrimitiveInt', '238:224', value=4)
        primitiveint_2 = raw_call('PrimitiveInt', '238:225', value=4)
        primitiveboolean = raw_call('PrimitiveBoolean', '238:229', value=public('use_lora', default=True))
        loraloadermodelonly = LoraLoaderModelOnly(lora_name=LORA_NAME, model=unetloader)

        # Conditioning
        positive = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=cliploader,
        )

        negative = CLIPTextEncode(
            text=public('negative_prompt', default=DEFAULT_PROMPT_2),
            clip=cliploader,
        )

        comfyswitchnode = ComfySwitchNode(
            on_false=primitiveint,
            on_true=primitiveint_2,
            switch=primitiveboolean,
        )

        comfyswitchnode_2 = ComfySwitchNode(
            on_false=primitivefloat_2,
            on_true=primitivefloat,
            switch=primitiveboolean,
        )

        comfyswitchnode_3 = ComfySwitchNode(
            on_false=unetloader,
            on_true=loraloadermodelonly,
            switch=primitiveboolean,
        )

        modelsamplingauraflow = ModelSamplingAuraFlow(
            shift=3.1,
            model=comfyswitchnode_3,
        )

        ksampler = KSampler(
            seed=public('seed', default=DEFAULT_SEED),
            sampler_name=public('sampler_name', default='euler'),
            steps=comfyswitchnode,
            cfg=comfyswitchnode_2,
            latent_image=emptysd3latentimage,
            model=modelsamplingauraflow,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(filename_prefix='Qwen-Image-2512', images=vaedecode)


        wf.register_input('model', unetloader.node.id, 'unet_name', UNET_NAME)
        return wf.finalize({}, spec=OUTPUT_SPEC)

