# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, ImageConcatMulti, ImageResizeKJ
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlEmbeds, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoVAELoader


CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = "high quality nature video of a red fox in an autumnal forest, there's a waterfall in the background"
DEFAULT_SEED = 42
DEPTH_ANYTHING_NAME = 'depth_anything_v2_vitl_fp16.safetensors'
MODEL_NAME = 'WanVideo/wan2.1_fun_control_1.3B_bf16.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'width': InputSpec(node='75', field='width', default=640, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoControlEmbeds', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json', 'source_id': 'video/wanvideo_wrapper_21_14b_fun_control', 'upstream_source_id': 'wan21_14b_fun_control', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_fun_control'},
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
        use_coefficients='true',
    )

    image, _, _, _ = VHS_LoadVideo(
        _id='71',
        video='wolf_interpolated.mp4',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': 'image'},
    )

    downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
        _id='73',
        model=DEPTH_ANYTHING_NAME,
    )

    wanvideoexperimentalargs = WanVideoExperimentalArgs(_id='90', cfg_zero_star=True)

    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    image_2, _, _ = ImageResizeKJ(
        _id='75',
        width=640,
        height='lanczos',
        upscale_method=False,
        keep_proportion=16,
        divisible_by=0,
        crop='disabled',
        image=image,
    )

    depthanything_v2 = DepthAnything_V2(
        _id='72',
        da_model=downloadandloaddepthanythingv2model,
        images=image_2,
    )

    image_3, width_2, height_2, count = GetImageSizeAndCount(
        _id='76',
        image=depthanything_v2,
    )

    # Outputs
    vhs_videocombine_2 = VHS_VideoCombine(
        _id='82',
        frame_rate=16,
        filename_prefix='control',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'control_00001.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'control_00001.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\control_00001.mp4'}},
        images=depthanything_v2,
    )

    wanvideoencode = WanVideoEncode(
        _id='77',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image_3,
        vae=wanvideovaeloader,
    )

    wanvideocontrolembeds = WanVideoControlEmbeds(_id='78', latents=wanvideoencode)

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        _id='69',
        width=width_2,
        height=height_2,
        num_frames=count,
        control_embeds=wanvideocontrolembeds,
    )

    samples, _ = WanVideoSampler(
        _id='27',
        steps=25,
        seed=DEFAULT_SEED,
        batched_cfg='',
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=wanvideoemptyembeds,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(_id='28', samples=samples, vae=wanvideovaeloader)

    imageconcatmulti = ImageConcatMulti(
        _id='87',
        unused_3=None,
        image_1=depthanything_v2,
        image_2=wanvideodecode,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_FunControl',
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_FunControl_00013.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_FunControl_00013.png', 'fullpath': 'N:\\AI\\ComfyUI\\output\\WanVideoWrapper_FunControl_00013.mp4'}},
        images=imageconcatmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_FunControl')

