# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEnhanceAVideo, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BF16 = 'bf16'
DEFAULT_FRAMES = 81
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
OFFLOAD_DEVICE = 'offload_device'

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json', 'source_id': 'wan21_14b_t2v', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json', 'source_ref': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json', 'source_kind': 'raw_json', 'indexed_id': None, 'workflow_source_id': 'wan21_14b_t2v', 'workflow_source_type': 'api', 'raw_workflow_shape': 'ui', 'source_hash': 'sha256:241242abd8b5d388cc594e808258b1c551429ac4d0b7785ebf1837c680dac23a', 'workflow_shape': {'nodes': 25, 'runtime_nodes': 18, 'helper_nodes': 7, 'edges': 16, 'inputs': 3, 'outputs': 1}, 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_t2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        model_name='umt5-xxl-enc-bf16.safetensors',
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\fp8_scaled_kj\\T2V\\Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideoemptyembeds = WanVideoEmptyEmbeds(height=480, width=832)

    wanvideovaeloader = WanVideoVAELoader(
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
    )

    wanvideoblockswap = WanVideoBlockSwap()
    cliploader = CLIPLoader(clip_name='umt5_xxl_fp16.safetensors', type_='wan')
    wanvideoenhanceavideo = WanVideoEnhanceAVideo()

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        lora_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors',
        merge_loras=False,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        t5=loadwanvideot5textencoder,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)

    cliptextencode_2 = CLIPTextEncode(
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader,
    )

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=6,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        flowedit_args='',
        unused_widget_4='fixed',
        feta_args=wanvideoenhanceavideo,
        image_embeds=wanvideoemptyembeds,
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
        filename_prefix='WanVideo2_1_T2V',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_1_T2V_00724.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_1_T2V_00724.png', 'fullpath': 'N:\\AI\\ComfyUI\\output\\WanVideo2_1_T2V_00724.mp4'}},
        images=wanvideodecode,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
        'width': InputSpec(node=wanvideoemptyembeds, field='width', default=832, type='INT'),
        'height': InputSpec(node=wanvideoemptyembeds, field='height', default=480, type='INT'),
        'prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_1_T2V')

