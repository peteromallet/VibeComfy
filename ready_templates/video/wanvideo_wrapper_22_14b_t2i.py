# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import SaveImage
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoVAELoader


BASE_PRECISION = 'fp16'
BATCHED_CFG = ''
DEFAULT_FRAMES = 1
DEFAULT_NEGATIVE = 'fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted'
DEFAULT_PROMPT = 'A compact cinematic still of a red cube on a clean white tabletop.'
DEFAULT_SEED = 12345
GUIDE_STRENGTH = 3.0
GUIDE_STRENGTH_2 = 1.0
LORA__NAME = 'WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\2_2\\Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'WanVideo\\2_2\\Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
QUANTIZATION = 'fp8_e4m3fn_scaled'
SCHEDULER = 'euler'


MODELS = {
    'wan2_2_t2v_a14b_high_fp8_e4m3fn_scaled_kj': ModelAsset(filename='Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors', sha256='15384a1da9b5aa463464ba50a596b84f6c0929bfb72ec47df6bb48cb2e0b6f0c', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'wan2_2_t2v_a14b_low_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', sha256='ce74fff05e37f995a0ae845f53510e43f98b838f4e75d846eb3e2929e7f555cc', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'lightx2v_t2v_14b_cfg_step_distill_v2_lora_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', sha256='37d49218544b9e0bfb8e831d1399f451fbc5068aff6474f42a90c928363c3573', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=630697104, subdir='loras/WanVideo/Lightx2v'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', sha256='1ab9a32cc2c740f6e39d80d367ce5dcc28db8c71b79b28670546b8973e9d75f9', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=253806278, subdir='vae'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', sha256='4fa971faf306cad919033d5bbe192e571dc08452f800cbf2ec3c73977c01b2cc', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=11361845464, subdir='text_encoders'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image_single_frame',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='Wan 2.2 14B high/low two-phase text-to-video graph decoded as one image frame',
    smoke_resolution='832x480x1_frame',
    runtime_note='Intended to match Reigh wan_2_2_t2i, which forces video_length=1 and returns PNG.',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_t2i.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
            model_name=MODEL_NAME,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
        )

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME_2,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
            widget_1='fp16',
        )

        wanvideovaeloader = WanVideoVAELoader(
            model_name=public('model', default=MODEL_NAME_3),
        )

        wanvideoblockswap = WanVideoBlockSwap(blocks_to_swap=30)

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            height=public('height', default=480),
            num_frames=DEFAULT_FRAMES,
            widget_0=832,
            widget_1=480,
            widget_2=1,
            width=public('width', default=832),
        )

        wanvideomodelloader_2 = WanVideoModelLoader(
            model=MODEL_NAME_4,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
            widget_1='fp16',
        )

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            lora_0=LORA__NAME,
            merge_loras=False,
            widget_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
        )

        wanvideoloraselectmulti_2 = WanVideoLoraSelectMulti(
            lora_0=LORA__NAME,
            merge_loras=False,
            widget_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
        )

        wanvideosetloras = WanVideoSetLoRAs(
            lora=wanvideoloraselectmulti_2,
            model=wanvideomodelloader,
        )

        wanvideosetloras_2 = WanVideoSetLoRAs(
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader_2,
        )

        wanvideosetblockswap = WanVideoSetBlockSwap(
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )

        wanvideosetblockswap_2 = WanVideoSetBlockSwap(
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras_2,
        )

        samples, denoised_samples = WanVideoSampler(
            steps=6,
            cfg=GUIDE_STRENGTH,
            seed=public('seed', default=DEFAULT_SEED),
            scheduler=SCHEDULER,
            batched_cfg=BATCHED_CFG,
            end_step=2,
            image_embeds=wanvideoemptyembeds,
            model=wanvideosetblockswap,
            text_embeds=text_embeds,
        )

        samples_wan, denoised_samples_wan = WanVideoSampler(
            steps=6,
            cfg=GUIDE_STRENGTH_2,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            batched_cfg=BATCHED_CFG,
            start_step=2,
            image_embeds=wanvideoemptyembeds,
            model=wanvideosetblockswap_2,
            samples=samples,
            text_embeds=text_embeds,
        )

        wanvideodecode = WanVideoDecode(
            normalization='default',
            samples=samples_wan,
            vae=wanvideovaeloader,
        )

        # Outputs
        saveimage = SaveImage(filename_prefix='Wan-2-2-T2I', images=wanvideodecode)

        return wf.finalize({}, filename_prefix='Wan-2-2-T2I', spec=OUTPUT_SPEC)

