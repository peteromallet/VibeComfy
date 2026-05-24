# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import LoadImage
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoVACEEncode, WanVideoVACEModelSelect, WanVideoVACEStartToEndFrame, WanVideoVAELoader


BASE_PRECISION = 'fp16'
DEFAULT_NEGATIVE = 'fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted'
DEFAULT_PROMPT = 'A smooth cinematic transition with consistent identity, lighting, and camera motion.'
DEFAULT_SEED = 12345
GUIDE_STRENGTH = 3.0
GUIDE_STRENGTH_2 = 1.0
LORA__NAME = 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_4 = 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
QUANTIZATION = 'fp8_e4m3fn_scaled'
SCHEDULER = 'euler'
VACE_MODEL_NAME = 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors'


MODELS = {
    'wan2_2_t2v_a14b_high_fp8_e4m3fn_scaled_kj': ModelAsset(filename='Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors', sha256='15384a1da9b5aa463464ba50a596b84f6c0929bfb72ec47df6bb48cb2e0b6f0c', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'wan2_2_t2v_a14b_low_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', sha256='ce74fff05e37f995a0ae845f53510e43f98b838f4e75d846eb3e2929e7f555cc', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'wan2_1_vace_module_14b_fp8_e4m3fn': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', sha256='4e251417a499fcdce54b6cddbd53d85644bcafb4e3d43a7d10c346612cb75501', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=3052113849, subdir='diffusion_models/WanVideo'),
    'lightx2v_t2v_14b_cfg_step_distill_v2_lora_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', sha256='37d49218544b9e0bfb8e831d1399f451fbc5068aff6474f42a90c928363c3573', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=630697104, subdir='loras/WanVideo/Lightx2v'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', sha256='1ab9a32cc2c740f6e39d80d367ce5dcc28db8c71b79b28670546b8973e9d75f9', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=253806278, subdir='vae'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', sha256='4fa971faf306cad919033d5bbe192e571dc08452f800cbf2ec3c73977c01b2cc', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=11361845464, subdir='text_encoders'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='video_vace_travel_join',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='832x480x81_frames',
    approach='Wan 2.2 14B VACE high/high/low cocktail with first/last frame and optional control-video conditioning',
    runtime_note='Matches Reigh Wan2GP VACE baseline shape: 81 frames, 6 Euler steps, CFG 3/1/1, flow shift 5.',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_vace_cocktail.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
            model_name=MODEL_NAME,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
        )

        wanvideovaeloader = WanVideoVAELoader(
            model_name=public('model', default=MODEL_NAME_2),
        )

        wanvideoblockswap = WanVideoBlockSwap(
            blocks_to_swap=30,
            offload_img_emb=True,
            offload_txt_emb=True,
            use_non_blocking=True,
            vace_blocks_to_swap=8,
        )

        # Inputs
        image, mask = LoadImage(image=public('image', default='vace_start.png'))

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            lora_0=LORA__NAME,
            merge_loras=False,
        )

        wanvideoloraselectmulti_2 = WanVideoLoraSelectMulti(
            lora_0=LORA__NAME,
            merge_loras=False,
        )

        image_load, mask_load = LoadImage(image='vace_end.png')

        image_load_2, frame_count, audio, video_info = VHS_LoadVideo(
            custom_height=480,
            custom_width=832,
            force_rate=16,
            frame_load_cap=81,
            video='vace_control.mp4',
            **{'choose video to upload': 'image'},
        )

        wanvideovacemodelselect = WanVideoVACEModelSelect(vace_model=VACE_MODEL_NAME)

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME_3,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
            extra_model=wanvideovacemodelselect,
        )

        wanvideomodelloader_2 = WanVideoModelLoader(
            model=MODEL_NAME_4,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
            extra_model=wanvideovacemodelselect,
        )

        images, masks = WanVideoVACEStartToEndFrame(
            control_images=image_load_2,
            end_image=image_load,
            start_image=image,
        )

        wanvideovaceencode = WanVideoVACEEncode(
            height=public('height', default=480),
            width=public('width', default=832),
            input_frames=images,
            input_masks=masks,
            ref_images=image,
            vae=wanvideovaeloader,
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
            end_step=2,
            image_embeds=wanvideovaceencode,
            model=wanvideosetblockswap,
            text_embeds=text_embeds,
        )

        samples_wan, denoised_samples_wan = WanVideoSampler(
            steps=6,
            cfg=GUIDE_STRENGTH_2,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            start_step=2,
            end_step=4,
            image_embeds=wanvideovaceencode,
            model=wanvideosetblockswap,
            samples=samples,
            text_embeds=text_embeds,
        )

        samples_wan_2, denoised_samples_wan_2 = WanVideoSampler(
            steps=6,
            cfg=GUIDE_STRENGTH_2,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            start_step=4,
            image_embeds=wanvideovaceencode,
            model=wanvideosetblockswap_2,
            samples=samples_wan,
            text_embeds=text_embeds,
        )

        wanvideodecode = WanVideoDecode(
            normalization='default',
            samples=samples_wan_2,
            vae=wanvideovaeloader,
        )

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            frame_rate=16,
            filename_prefix='Wan-2-2-VACE',
            format='video/h264-mp4',
            crf=19,
            pix_fmt='yuv420p',
            save_metadata=True,
            trim_to_audio=False,
            images=wanvideodecode,
        )

        return wf.finalize({}, filename_prefix='Wan-2-2-VACE', spec=OUTPUT_SPEC)

