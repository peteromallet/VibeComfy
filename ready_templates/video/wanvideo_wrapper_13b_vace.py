# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import EmptyImage, GetImageRangeFromBatch, LoadImage, MaskPreview, PreviewImage
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImagePadKJ, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoDecode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoVACEEncode, WanVideoVACEModelSelect, WanVideoVACEStartToEndFrame, WanVideoVAELoader


BLACK = 'black'
CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
COLOR = 'color'
CROP = 'crop'
DEFAULT_FRAMES_2 = 33
DEFAULT_NEGATIVE = 'colorful, bad quality, blurry, messy, chaotic'
DEFAULT_NEGATIVE_2 = 'bad quality, blurry, messy, chaotic'
DEFAULT_PROMPT = 'black and white cartoon character'
DEFAULT_PROMPT_2 = 'robotic cybernetic wolf turning his head'
DEFAULT_SEED = 18
DEPTH_ANYTHING_NAME = 'depth_anything_v2_vitl_fp16.safetensors'
DOWN = 'down'
FREEMONO_TTF = 'FreeMono.ttf'
GUIDE_STRENGTH = 4.000000000000001
IMAGE = 'image'
LANCZOS = 'lanczos'
LEFT = 'left'
MODEL_NAME = 'WanVideo/wan2.1_t2v_1.3B_fp16.safetensors'
PAD = 'pad'
TRUE = 'true'
UP = 'up'
VACE_MODEL_NAME = 'WanVideo/Wan2_1-VACE_module_1_3B_bf16.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
V_172_172_172 = '172,172,172'
V_255_255_255 = '255,255,255'
V_8 = '8'
WHITE = 'white'
WOLF_INTERPOLATED_MP4 = 'wolf_interpolated.mp4'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='64', field='image', default='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='70', field='seed', default=DEFAULT_SEED, type='INT'),
    'width': InputSpec(node='132', field='width', default=8, type='INT'),
    'height': InputSpec(node='133', field='height', default=32, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json', 'source_id': 'video/wanvideo_wrapper_13b_vace', 'upstream_source_id': 'wan13b_vace', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_13b_vace'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        _id='11',
        model_name=CLIP_NAME,
    )

    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)

    wanvideoteacache = WanVideoTeaCache(
        _id='52',
        rel_l1_thresh=0.10000000000000002,
        start_step=0,
        use_coefficients=TRUE,
    )

    # Inputs
    image, _ = LoadImage(
        _id='64',
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp',
    )

    wanvideoexperimentalargs = WanVideoExperimentalArgs(_id='71', cfg_zero_star=True)

    wanvideoslg = WanVideoSLG(
        _id='72',
        blocks=V_8,
        start_percent=0.30000000000000004,
        end_percent=0.7000000000000002,
    )

    image_3, _ = LoadImage(
        _id='112',
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-3.webp',
    )

    wanvideoteacache_2 = WanVideoTeaCache(
        _id='147',
        rel_l1_thresh=0.10000000000000002,
        start_step=0,
        use_coefficients=TRUE,
    )

    wanvideoslg_2 = WanVideoSLG(
        _id='149',
        blocks=V_8,
        start_percent=0.30000000000000004,
        end_percent=0.7100000000000002,
    )

    wanvideoexperimentalargs_2 = WanVideoExperimentalArgs(_id='150', cfg_zero_star=True)
    image_7, _ = LoadImage(_id='169', image='hunhyuanwolf.png')

    image_8, frame_count, _, _ = VHS_LoadVideo(
        _id='173',
        video=WOLF_INTERPOLATED_MP4,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': IMAGE},
    )

    downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
        _id='175',
        model=DEPTH_ANYTHING_NAME,
    )

    wanvideoslg_3 = WanVideoSLG(
        _id='187',
        blocks=V_8,
        start_percent=0.30000000000000004,
        end_percent=0.7000000000000002,
    )

    wanvideoexperimentalargs_3 = WanVideoExperimentalArgs(_id='188', cfg_zero_star=True)

    image_10, _, _, _ = VHS_LoadVideo(
        _id='199',
        video=WOLF_INTERPOLATED_MP4,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': IMAGE},
    )

    wanvideoteacache_3 = WanVideoTeaCache(
        _id='214',
        rel_l1_thresh=0.10000000000000002,
        start_step=0,
        use_coefficients=TRUE,
    )

    wanvideovacemodelselect = WanVideoVACEModelSelect(
        _id='224',
        vace_model=VACE_MODEL_NAME,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='22',
        model=MODEL_NAME,
        base_precision='fp16',
        vace_model=wanvideovacemodelselect,
    )

    images_2, _ = ImagePadKJ(
        _id='184',
        bottom=128,
        extra_padding=COLOR,
        pad_mode='255,255,255',
        image=image_7,
    )

    image_14, _, _, _ = ImageResizeKJv2(
        _id='226',
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        image=image_10,
    )

    image_15, width_8, height_8, _ = ImageResizeKJv2(
        _id='227',
        width=640,
        height=640,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        image=image,
    )

    image_17, width_10, height_10, _ = ImageResizeKJv2(
        _id='229',
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        image=image_8,
    )

    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    addlabel = AddLabel(
        _id='133',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='start_frame',
        text=UP,
        image=image_15,
    )

    wanvideotextencode_2 = WanVideoTextEncode(
        _id='168',
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt=DEFAULT_NEGATIVE_2,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    depthanything_v2 = DepthAnything_V2(
        _id='174',
        da_model=downloadandloaddepthanythingv2model,
        images=image_17,
    )

    wanvideotextencode_3 = WanVideoTextEncode(
        _id='211',
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt=DEFAULT_NEGATIVE_2,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    images_3, masks_3 = ImagePadKJ(
        _id='216',
        bottom=128,
        extra_padding=COLOR,
        pad_mode='127,127,127',
        image=image_14,
    )

    image_16, _, _, _ = ImageResizeKJv2(
        _id='228',
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        width=width_8,
        height=height_8,
        image=image_3,
    )

    image_18, _, _, _ = ImageResizeKJv2(
        _id='230',
        upscale_method=LANCZOS,
        keep_proportion=PAD,
        pad_color=V_255_255_255,
        divisible_by=16,
        width=width_10,
        height=height_10,
        image=images_2,
    )

    image_19, _, _, _ = ImageResizeKJv2(
        _id='238',
        upscale_method=LANCZOS,
        keep_proportion=PAD,
        pad_color=V_255_255_255,
        divisible_by=16,
        width=width_10,
        height=height_10,
        image=image_7,
    )

    images, masks = WanVideoVACEStartToEndFrame(
        _id='111',
        num_frames=DEFAULT_FRAMES_2,
        empty_frame_level=0.5000000000000001,
        end_image=image_16,
        start_image=image_15,
    )

    addlabel_2 = AddLabel(
        _id='134',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='end_frame',
        text=UP,
        image=image_16,
    )

    addlabel_3 = AddLabel(
        _id='156',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='reference image',
        text=UP,
        image=image_18,
    )

    addlabel_4 = AddLabel(
        _id='157',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='control_video',
        text=UP,
        image=depthanything_v2,
    )

    # Outputs
    vhs_videocombine_3 = VHS_VideoCombine(
        _id='177',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_startendframe',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_startendframe_00001.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_startendframe_00001.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_startendframe_00001.mp4'}},
        images=depthanything_v2,
    )

    addlabel_5 = AddLabel(
        _id='202',
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='input',
        text=UP,
        image=images_3,
    )

    image_11, width_6, height_6, count_6 = GetImageSizeAndCount(
        _id='205',
        image=images_3,
    )

    image_12, _ = GetImageRangeFromBatch(_id='219', images=images_3)
    _, mask_5 = GetImageRangeFromBatch(_id='222', masks=masks_3)

    images_4, masks_4 = WanVideoVACEStartToEndFrame(
        _id='231',
        empty_frame_level=0.5000000000000001,
        num_frames=frame_count,
        control_images=depthanything_v2,
        start_image=image_19,
    )

    previewimage_4 = PreviewImage(_id='237', images=image_18)
    image_2, width, height, count = GetImageSizeAndCount(_id='104', image=images)

    imageconcatmulti_2 = ImageConcatMulti(
        _id='136',
        direction=DOWN,
        match_image_size=True,
        unused_3=None,
        image_1=addlabel,
        image_2=addlabel_2,
    )

    image_5, width_3, height_3, count_3 = GetImageSizeAndCount(
        _id='145',
        image=images_4,
    )

    imageconcatmulti_4 = ImageConcatMulti(
        _id='160',
        direction=DOWN,
        match_image_size=True,
        unused_3=None,
        image_1=addlabel_3,
        image_2=addlabel_4,
    )

    wanvideovaceencode_3 = WanVideoVACEEncode(
        _id='209',
        strength=0,
        vace_start_percent=1,
        vace_end_percent=False,
        width=width_6,
        height=height_6,
        num_frames=count_6,
        input_frames=image_11,
        input_masks=masks_3,
        vae=wanvideovaeloader,
    )

    previewimage_2 = PreviewImage(_id='220', images=image_12)
    previewimage_3 = PreviewImage(_id='232', images=images_4)
    maskpreview = MaskPreview(_id='233', mask=masks_4)
    maskpreview_2 = MaskPreview(_id='234', mask=masks)
    maskpreview_3 = MaskPreview(_id='235', mask=mask_5)

    wanvideovaceencode = WanVideoVACEEncode(
        _id='56',
        strength=0,
        vace_start_percent=1,
        vace_end_percent=False,
        width=width,
        height=height,
        num_frames=count,
        input_frames=image_2,
        input_masks=masks,
        ref_images=image_15,
        vae=wanvideovaeloader,
    )

    previewimage = PreviewImage(_id='113', images=image_2)

    wanvideovaceencode_2 = WanVideoVACEEncode(
        _id='148',
        strength=0,
        vace_start_percent=1,
        vace_end_percent=False,
        width=width_3,
        height=height_3,
        num_frames=count_3,
        input_frames=image_5,
        input_masks=masks_4,
        ref_images=image_18,
        vae=wanvideovaeloader,
    )

    samples_3, _ = WanVideoSampler(
        _id='197',
        steps=20,
        cfg=GUIDE_STRENGTH,
        shift=8.000000000000002,
        seed=DEFAULT_SEED,
        start_step='',
        cache_args=wanvideoteacache_3,
        experimental_args=wanvideoexperimentalargs_3,
        image_embeds=wanvideovaceencode_3,
        model=wanvideomodelloader,
        slg_args=wanvideoslg_3,
        text_embeds=wanvideotextencode_3,
    )

    samples, _ = WanVideoSampler(
        _id='70',
        steps=20,
        cfg=GUIDE_STRENGTH,
        shift=8.000000000000002,
        seed=DEFAULT_SEED,
        start_step='',
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=wanvideovaceencode,
        model=wanvideomodelloader,
        slg_args=wanvideoslg,
        text_embeds=wanvideotextencode,
    )

    samples_2, _ = WanVideoSampler(
        _id='172',
        steps=20,
        cfg=GUIDE_STRENGTH,
        shift=8.000000000000002,
        start_step='',
        cache_args=wanvideoteacache_2,
        experimental_args=wanvideoexperimentalargs_2,
        image_embeds=wanvideovaceencode_2,
        model=wanvideomodelloader,
        slg_args=wanvideoslg_2,
        text_embeds=wanvideotextencode_2,
    )

    wanvideodecode_3 = WanVideoDecode(
        _id='196',
        samples=samples_3,
        vae=wanvideovaeloader,
    )

    wanvideodecode = WanVideoDecode(_id='138', samples=samples, vae=wanvideovaeloader)

    wanvideodecode_2 = WanVideoDecode(
        _id='167',
        samples=samples_2,
        vae=wanvideovaeloader,
    )

    image_9, _, height_5, _ = GetImageSizeAndCount(_id='193', image=wanvideodecode_3)
    image_4, _, height_2, _ = GetImageSizeAndCount(_id='137', image=wanvideodecode)
    image_6, _, height_4, _ = GetImageSizeAndCount(_id='159', image=wanvideodecode_2)
    emptyimage_3 = EmptyImage(_id='191', width=8, height=height_5)
    emptyimage = EmptyImage(_id='132', width=8, height=height_2)
    emptyimage_2 = EmptyImage(_id='155', width=8, height=height_4)

    imageconcatmulti_5 = ImageConcatMulti(
        _id='192',
        inputcount=3,
        direction=LEFT,
        match_image_size=True,
        unused_3=None,
        image_1=image_9,
        image_2=emptyimage_3,
        image_3=addlabel_5,
    )

    imageconcatmulti = ImageConcatMulti(
        _id='135',
        inputcount=3,
        direction=LEFT,
        match_image_size=True,
        unused_3=None,
        image_1=image_4,
        image_2=emptyimage,
        image_3=imageconcatmulti_2,
    )

    imageconcatmulti_3 = ImageConcatMulti(
        _id='158',
        inputcount=3,
        direction=LEFT,
        match_image_size=True,
        unused_3=None,
        image_1=image_6,
        image_2=emptyimage_2,
        image_3=imageconcatmulti_4,
    )

    vhs_videocombine_4 = VHS_VideoCombine(
        _id='213',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_outpaint',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_outpaint_00002.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_outpaint_00002.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_outpaint_00002.mp4'}},
        images=imageconcatmulti_5,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='139',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_startendframe',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_startendframe_00005.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_startendframe_00005.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_startendframe_00005.mp4'}},
        images=imageconcatmulti,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        _id='165',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_startendframe',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_startendframe_00011.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_startendframe_00011.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_startendframe_00011.mp4'}},
        images=imageconcatmulti_3,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=previewimage, output_type='PreviewImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

