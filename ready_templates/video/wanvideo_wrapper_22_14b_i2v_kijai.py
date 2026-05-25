# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, LoadImage
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import CreateCFGScheduleFloatList, LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoVAELoader


ADD_NOISE_TO_SAMPLES = ''
BASE_PRECISION = 'fp16'
CLIP_NAME = 'umt5_xxl_fp16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'old man gets up and jumps into the lake'
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_3 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 43
GUIDE_STRENGTH = 1
LORA_NAME = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\2_2\\Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'WanVideo\\2_2\\Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
QUANTIZATION = 'fp8_e4m3fn_scaled'
SCHEDULER = 'dpm++_sde'


MODELS = {
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', subdir='checkpoints'),
    'checkpoint_2': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', subdir='checkpoints'),
    'checkpoint_3': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', subdir='checkpoints'),
    'checkpoint_4': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', subdir='checkpoints'),
    'checkpoint_5': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors', subdir='checkpoints'),
    'checkpoint_6': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', subdir='checkpoints'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['CreateCFGScheduleFloatList', 'LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='Kijai WanVideoWrapper Wan 2.2 A14B I2V high/low two-phase workflow with Lightx2v LoRA',
    smoke_resolution='832x480x81_frames',
    runtime_note='Worker scratchpads patch image, prompt, seed, resolution, frame count, and force VHS output saving.',
    source_url='https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_2_2_I2V_A14B_example_WIP.json',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_i2v_kijai.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_2,
        base_precision=BASE_PRECISION,
        quantization=QUANTIZATION,
    )

    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_3)
    wanvideoblockswap = WanVideoBlockSwap(vace_blocks_to_swap=1)
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')

    wanvideoloraselect = WanVideoLoraSelect(
        lora=LORA_NAME,
        strength=3,
        merge_loras=False,
    )

    # Inputs
    image, mask = LoadImage(image='oldman_upscaled.png')

    wanvideomodelloader_2 = WanVideoModelLoader(
        model=MODEL_NAME_4,
        base_precision=BASE_PRECISION,
        quantization=QUANTIZATION,
    )

    intconstant = INTConstant(value=3)
    intconstant_2 = INTConstant(value=6)
    wanvideoloraselect_2 = WanVideoLoraSelect(lora=LORA_NAME, merge_loras=False)

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        t5=loadwanvideot5textencoder,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_3, clip=cliploader)

    image_image, width, height, mask_image = ImageResizeKJv2(
        width=720,
        height=720,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        image=image,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader,
    )

    wanvideosetblockswap_2 = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader_2,
    )

    createcfgschedulefloatlist = CreateCFGScheduleFloatList(
        cfg_scale_start=2,
        cfg_scale_end=2,
        end_percent=0.01,
        steps=intconstant_2,
    )

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        lora=wanvideoloraselect_2,
        model=wanvideosetblockswap_2,
    )

    wanvideosetloras_2 = WanVideoSetLoRAs(
        lora=wanvideoloraselect,
        model=wanvideosetblockswap,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        fun_or_fl2v_model=False,
        width=width,
        height=height,
        start_image=image_image,
        vae=wanvideovaeloader,
    )

    samples, denoised_samples = WanVideoSampler(
        shift=8,
        seed=DEFAULT_SEED,
        scheduler=SCHEDULER,
        add_noise_to_samples=ADD_NOISE_TO_SAMPLES,
        steps=intconstant_2,
        cfg=createcfgschedulefloatlist,
        end_step=intconstant,
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideosetloras_2,
        text_embeds=wanvideotextencode,
    )

    samples_wan, denoised_samples_wan = WanVideoSampler(
        cfg=GUIDE_STRENGTH,
        shift=8,
        seed=DEFAULT_SEED,
        scheduler=SCHEDULER,
        add_noise_to_samples=ADD_NOISE_TO_SAMPLES,
        steps=intconstant_2,
        start_step=intconstant,
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideosetloras,
        samples=samples,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples_wan,
        vae=wanvideovaeloader,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=wanvideodecode)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideo2_2_I2V',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_2_I2V_00006.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_I2V_00006.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_2_I2V_00006.png'}, 'paused': False},
        images=image_get,
    )


    PUBLIC_INPUTS = {
        'model': InputSpec(node=loadwanvideot5textencoder, field='model_name', default=MODEL_NAME),
        'prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT_2),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED),
        'image': InputSpec(node=image, field='image', default='oldman_upscaled.png'),
        'width': InputSpec(node=image_image, field='width', default=720),
        'height': InputSpec(node=image_image, field='height', default=720),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_2_I2V')

