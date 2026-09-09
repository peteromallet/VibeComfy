# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import LoadImage, PreviewImage
from vibecomfy.nodes.kjnodes import CameraPoseVisualizer, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoDecode, WanVideoExperimentalArgs, WanVideoFunCameraEmbeds, WanVideoImageToVideoEncode, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoVAELoader


CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'high quality video of an old man'
DEFAULT_SEED = 43
MODEL_NAME = 'WanVideo/Wan2.1-Fun-V1.1-1.3B-Control-Camera.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='58', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='97', field='width', default=624, type='INT'),
    'height': InputSpec(node='97', field='height', default=624, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoImageToVideoEncode', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json', 'source_id': 'video/wanvideo_wrapper_21_14b_fun_control_camera', 'upstream_source_id': 'wan21_14b_fun_control_camera', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_fun_control_camera'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        _id='11',
        model_name=CLIP_NAME,
    )

    wanvideomodelloader = WanVideoModelLoader(_id='22', model=MODEL_NAME)
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)

    wanvideoteacache = WanVideoTeaCache(
        _id='52',
        rel_l1_thresh=0.08000000000000002,
        start_step=6,
        use_coefficients='true',
        mode='e0',
    )

    # Inputs
    image, _ = LoadImage(_id='58', image='oldman_upscaled.png')

    wanvideoexperimentalargs = WanVideoExperimentalArgs(
        _id='90',
        cfg_zero_star=True,
        use_fresca=True,
    )

    intconstant = INTConstant(_id='105', value=81)

    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    image_2, width, height, _ = ImageResizeKJv2(
        _id='97',
        width=624,
        height=624,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=16,
        image=image,
    )

    ade_cameraposebasic = raw_call('ADE_CameraPoseBasic', '99',
        widget_0='Zoom Out',
        widget_1=0.10000000000000002,
        widget_2=40,
        frame_length=intconstant,
    )

    cameraposevisualizer = CameraPoseVisualizer(
        _id='102',
        cameractrl_poses=ade_cameraposebasic.out(0),
    )

    wanvideofuncameraembeds = WanVideoFunCameraEmbeds(
        _id='104',
        start_percent=1,
        strength=0,
        height=height,
        poses=ade_cameraposebasic.out(0),
        width=width,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        _id='63',
        noise_aug_strength=0.030000000000000006,
        tiled_vae=True,
        width=width,
        height=height,
        num_frames=intconstant,
        control_embeds=wanvideofuncameraembeds,
        start_image=image_2,
        vae=wanvideovaeloader,
    )

    # Outputs
    previewimage = PreviewImage(_id='103', images=cameraposevisualizer)

    samples, _ = WanVideoSampler(
        _id='27',
        seed=DEFAULT_SEED,
        batched_cfg='',
        start_step='',
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(_id='28', samples=samples, vae=wanvideovaeloader)

    imageconcatmulti = ImageConcatMulti(
        _id='87',
        inputcount=3,
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=wanvideodecode,
        image_2=image_2,
        image_3=cameraposevisualizer,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_FunControlCamera',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_FunControl_00318.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_FunControl_00318.png', 'fullpath': 'N:\\AI\\ComfyUI\\output\\WanVideoWrapper_FunControl_00318.mp4'}},
        images=imageconcatmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_FunControlCamera')

