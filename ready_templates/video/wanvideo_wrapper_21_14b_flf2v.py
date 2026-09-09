# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPVisionLoader, EmptyImage, LoadImage
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BLACK = 'black'
CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
CLIP_NAME_2 = 'clip_vision_h.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角'
DEFAULT_SEED = 43
FREEMONO_TTF = 'FreeMono.ttf'
GUIDE_STRENGTH = 1.0000000000000002
LANCZOS = 'lanczos'
LORA_NAME = 'Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors'
MODEL_NAME = 'WanVideo/Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors'
UP = 'up'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
WHITE = 'white'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='58', field='image', default='pasted/image (853).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'height': InputSpec(node='95', field='height', default=32, type='INT'),
    'width': InputSpec(node='97', field='width', default=8, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json', 'source_id': 'video/wanvideo_wrapper_21_14b_flf2v', 'upstream_source_id': 'wan21_14b_flf2v', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_flf2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        _id='11',
        model_name=CLIP_NAME,
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)
    wanvideoblockswap = WanVideoBlockSwap(_id='39', use_non_blocking=True)

    # Inputs
    image, _ = LoadImage(_id='58', image='pasted/image (853).png')

    # Loaders
    clipvisionloader = CLIPVisionLoader(_id='59', clip_name=CLIP_NAME_2)
    image_2, _ = LoadImage(_id='63', image='pasted/image (852).png')

    wanvideoloraselect = WanVideoLoraSelect(
        _id='106',
        lora=LORA_NAME,
        strength=1.2000000000000002,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='22',
        model=MODEL_NAME,
        base_precision='fp16_fast',
        quantization='fp8_e4m3fn',
        attention_mode='sageattn',
        block_swap_args=wanvideoblockswap,
        compile_args=wanvideotorchcompilesettings,
        lora=wanvideoloraselect,
    )

    image_4, width_2, height_2, _ = ImageResizeKJv2(
        _id='107',
        width=640,
        height=640,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        image=image_2,
    )

    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    addlabel = AddLabel(
        _id='95',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='start_frame',
        text=UP,
        image=image_4,
    )

    image_5, width_3, height_3, _ = ImageResizeKJv2(
        _id='108',
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        width=width_2,
        height=height_2,
        image=image,
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        _id='88',
        combine_embeds='concat',
        clip_vision=clipvisionloader,
        image_1=image_4,
        image_2=image_5,
    )

    addlabel_2 = AddLabel(
        _id='96',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='end_frame',
        text=UP,
        image=image_5,
    )

    imageconcatmulti = ImageConcatMulti(
        _id='70',
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=addlabel,
        image_2=addlabel_2,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        _id='89',
        tiled_vae=True,
        fun_or_fl2v_model=False,
        width=width_3,
        height=height_3,
        clip_embeds=wanvideoclipvisionencode,
        end_image=image_5,
        start_image=image_4,
        vae=wanvideovaeloader,
    )

    samples, _ = WanVideoSampler(
        _id='27',
        steps=6,
        cfg=GUIDE_STRENGTH,
        shift=5.000000000000001,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        _id='101',
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_3, _, height, _ = GetImageSizeAndCount(_id='68', image=wanvideodecode)
    emptyimage = EmptyImage(_id='97', width=8, height=height)

    imageconcatmulti_2 = ImageConcatMulti(
        _id='71',
        inputcount=3,
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=image_3,
        image_2=emptyimage,
        image_3=imageconcatmulti,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_I2V_endframe',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_I2V_endframe_00008.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_I2V_endframe_00008.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_I2V_endframe_00008.mp4'}},
        images=imageconcatmulti_2,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_I2V_endframe')

