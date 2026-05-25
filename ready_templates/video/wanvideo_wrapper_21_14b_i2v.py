# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionLoader, LoadImage
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader, WanVideoVRAMManagement


BF16 = 'bf16'
DEFAULT_FRAMES = 81
DEFAULT_SEED = 1057359483639287
GUIDE_STRENGTH = 1
OFFLOAD_DEVICE = 'offload_device'

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json', 'source_id': 'wan21_14b_i2v', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json', 'source_ref': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json', 'source_kind': 'raw_json', 'indexed_id': None, 'workflow_source_id': 'wan21_14b_i2v', 'workflow_source_type': 'api', 'raw_workflow_shape': 'ui', 'source_hash': 'sha256:e9da590389b56825ba61533aa5be3f21d27572328b054384d5fbe4dc775df946', 'workflow_shape': {'nodes': 26, 'runtime_nodes': 21, 'helper_nodes': 5, 'edges': 23, 'inputs': 3, 'outputs': 1}, 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_i2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        model_name='umt5-xxl-enc-bf16.safetensors',
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

    wanvideovaeloader = WanVideoVAELoader(
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
    )

    wanvideoblockswap = WanVideoBlockSwap(blocks_to_swap=10, use_non_blocking=True)
    wanvideovrammanagement = WanVideoVRAMManagement()
    cliploader = CLIPLoader(clip_name='umt5_xxl_fp16.safetensors', type_='wan')

    # Inputs
    image, mask = LoadImage(image='oldman_upscaled.png', unused_widget_1='image')
    clipvisionloader = CLIPVisionLoader(clip_name='clip_vision_h.safetensors')

    wanvideoloraselect = WanVideoLoraSelect(
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        merge_loras="<details><summary><b>Metadata</b></summary><table border='0' cellpadding='3'><tr><td colspan='2'><b>Metadata</b></td></tr><tr><td>No metadata found</td></tr></table></details>",
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn',
        lora=wanvideoloraselect,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader,
    )

    cliptextencode_2 = CLIPTextEncode(
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        width=624,
        height=624,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=16,
        device='cpu',
        image=image,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt='an old man is stroking his beard thoughtfully',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        ratio=0.20000000000000004,
        clip_vision=clipvisionloader,
        image_1=image_image,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        noise_aug_strength=0.030000000000000006,
        fun_or_fl2v_model=False,
        width=width,
        height=height,
        clip_embeds=wanvideoclipvisionencode,
        start_image=image_image,
        vae=wanvideovaeloader,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=4,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        unused_widget_4='fixed',
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideosetblockswap,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideoWrapper_I2V',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_I2V_00709.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_I2V_00709.png', 'fullpath': 'N:\\AI\\ComfyUI\\output\\WanVideoWrapper_I2V_00709.mp4'}},
        images=wanvideodecode,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
        'image': InputSpec(node=image, field='image', default='oldman_upscaled.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'width': InputSpec(node=image_image, field='width', default=624, type='INT'),
        'height': InputSpec(node=image_image, field='height', default=624, type='INT'),
        'prompt': InputSpec(node=cliptextencode, field='text', default="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall", type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_I2V')

