# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import GetImageRangeFromBatch, PreviewImage
from vibecomfy.nodes.florence2 import DownloadAndLoadFlorence2Model, Florence2Run
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageResizeKJ, WidgetToString
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, ReCamMasterPoseVisualizer, WanVideoDecode, WanVideoEncode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoReCamMasterCameraEmbed, WanVideoReCamMasterDefaultCamera, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoVAELoader


CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 42
MODEL_NAME = 'WanVideo/Wan2_1_kwai_recammaster_1_3B_step20000_bf16.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'


PUBLIC_INPUT_METADATA = {
    'width': InputSpec(node='59', field='width', default=480, type='INT'),
    'height': InputSpec(node='122', field='height', default=32, type='INT'),
    'seed': InputSpec(node='155', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json', 'source_id': 'video/wanvideo_wrapper_13b_recammaster', 'upstream_source_id': 'wan13b_recammaster', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_13b_recammaster'},
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
        rel_l1_thresh=0.10000000000000002,
        start_step=6,
        use_coefficients='true',
        mode='e0',
    )

    downloadandloadflorence2model = DownloadAndLoadFlorence2Model(
        _id='124',
        widget_0='MiaoshouAI/Florence-2-base-PromptGen-v2.0',
        widget_1='fp16',
        widget_2='sdpa',
    )

    wanvideoexperimentalargs = WanVideoExperimentalArgs(_id='127', cfg_zero_star=True)

    image_2, _, _, _ = VHS_LoadVideo(
        _id='128',
        video='9.mp4',
        frame_load_cap=81,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': '9.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 81, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': 'image'},
    )

    image_3, _, _, _ = GetImageSizeAndCount(_id='129', image=image_2)

    image, _, _ = ImageResizeKJ(
        _id='59',
        width=480,
        height='lanczos',
        upscale_method=False,
        keep_proportion=16,
        divisible_by='center',
        image=image_3,
    )

    wanvideoencode = WanVideoEncode(
        _id='58',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image,
        vae=wanvideovaeloader,
    )

    image_4, _ = GetImageRangeFromBatch(_id='130', images=image)

    florence2run = Florence2Run(
        _id='123',
        widget_0='',
        widget_1='detailed_caption',
        widget_2=True,
        widget_3=False,
        widget_4=1024,
        widget_5=3,
        widget_6=True,
        widget_7='',
        widget_8=1,
        widget_9='fixed',
        florence2_model=downloadandloadflorence2model.out(0),
        image=image_4,
    )

    # Outputs
    previewimage = PreviewImage(_id='131', images=image_4)

    wanvideorecammasterdefaultcamera = WanVideoReCamMasterDefaultCamera(
        _id='205',
        latents=wanvideoencode,
    )

    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        negative_prompt=DEFAULT_NEGATIVE,
        positive_prompt=florence2run.out(2),
        t5=loadwanvideot5textencoder,
    )

    camera_embeds, camera_poses = WanVideoReCamMasterCameraEmbed(
        _id='56',
        camera_poses=wanvideorecammasterdefaultcamera,
        latents=wanvideoencode,
    )

    widgettostring = WidgetToString(
        _id='74',
        widget_name='camera_type',
        node_title=2,
        any_input=wanvideorecammasterdefaultcamera,
    )

    recammasterposevisualizer = ReCamMasterPoseVisualizer(
        _id='138',
        base_xval=0.20000000000000004,
        zval=0.4000000000000001,
        scale=0.5000000000000001,
        camera_poses=camera_poses,
    )

    samples, _ = WanVideoSampler(
        _id='155',
        steps=20,
        seed=DEFAULT_SEED,
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=camera_embeds,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(_id='28', samples=samples, vae=wanvideovaeloader)
    previewimage_2 = PreviewImage(_id='139', images=recammasterposevisualizer)

    addlabel = AddLabel(
        _id='122',
        text_x=2,
        text_y=48,
        height=32,
        font_size='white',
        font_color='black',
        label_color='FreeMonoBoldOblique.otf',
        font='input',
        text=widgettostring,
        image=wanvideodecode,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=16,
        filename_prefix='WanVideo2_1_ReCamMaster',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_1_T2V_00013.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_1_T2V_00013.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00013.mp4'}},
        images=addlabel,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_1_ReCamMaster')

