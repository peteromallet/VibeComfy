# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import EmptyImage, GetImageRangeFromBatch, LoadImage, MaskPreview, PreviewImage
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImagePadKJ, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVACEEncode, WanVideoVACEModelSelect, WanVideoVACEStartToEndFrame, WanVideoVAELoader


BLACK = 'black'
COLOR = 'color'
CONTROL_VIDEO = 'control_video'
CROP = 'crop'
DEFAULT_FRAMES = 1
DEFAULT_FRAMES_2 = 33
DEFAULT_NEGATIVE_2 = 'bad quality, blurry, messy, chaotic'
DEFAULT_PROMPT_2 = 'robotic cybernetic wolf turning his head'
DEFAULT_SEED = 18
DOWN = 'down'
E = 'e'
END_IMAGE = 'end_image'
FREEMONO_TTF = 'FreeMono.ttf'
GUIDE_STRENGTH = 4.000000000000001
INPUTVIDEO = 'InputVideo'
LANCZOS = 'lanczos'
LEFT = 'left'
OFFLOAD_DEVICE = 'offload_device'
PAD = 'pad'
REFERENCE_IMAGE = 'reference_image'
START_IMAGE = 'start_image'
TRUE = 'true'
UP = 'up'
VALUE = ''
V_172_172_172 = '172,172,172'
V_255_255_255 = '255,255,255'
V_8 = '8'
WANMODEL = 'WanModel'
WANTEXTENCODER = 'WanTextEncoder'
WANVAE = 'WanVAE'
WHITE = 'white'
WOLF_INTERPOLATED_MP4 = 'wolf_interpolated.mp4'

READY_METADATA = ReadyMetadata.build(
    capability='vace_video_control',
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-DepthAnythingV2', 'source': 'git', 'version': 'unknown', 'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'version': 'unknown', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='VACE control/edit workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json'},
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

    wanvideoblockswap = WanVideoBlockSwap(
        blocks_to_swap=0,
        use_non_blocking=True,
        vace_blocks_to_swap=15,
    )

    wanvideoteacache = WanVideoTeaCache(
        rel_l1_thresh=0.1,
        start_step=0,
        use_coefficients='true',
    )

    # Inputs
    image, mask = LoadImage(
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp',
    )

    wanvideoexperimentalargs = WanVideoExperimentalArgs(cfg_zero_star=True)
    wanvideoslg = WanVideoSLG(blocks='8', end_percent=0.7, start_percent=0.3)

    image_load, mask_load = LoadImage(
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-3.webp',
    )

    wanvideoteacache_2 = WanVideoTeaCache(
        rel_l1_thresh=0.1,
        start_step=0,
        use_coefficients='true',
    )

    wanvideoslg_2 = WanVideoSLG(blocks='8', end_percent=0.71, start_percent=0.3)
    wanvideoexperimentalargs_2 = WanVideoExperimentalArgs(cfg_zero_star=True)
    image_load_2, mask_load_2 = LoadImage(image='hunhyuanwolf.png')

    image_load_3, frame_count, audio, video_info = VHS_LoadVideo(
        video=WOLF_INTERPOLATED_MP4,
    )

    downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
        model='depth_anything_v2_vitl_fp16.safetensors',
    )

    wanvideoslg_3 = WanVideoSLG(blocks='8', end_percent=0.7, start_percent=0.3)
    wanvideoexperimentalargs_3 = WanVideoExperimentalArgs(cfg_zero_star=True)

    image_load_4, frame_count_load, audio_load, video_info_load = VHS_LoadVideo(
        video=WOLF_INTERPOLATED_MP4,
    )

    wanvideoteacache_3 = WanVideoTeaCache(
        rel_l1_thresh=0.1,
        start_step=0,
        use_coefficients='true',
    )

    wanvideovacemodelselect = WanVideoVACEModelSelect(
        vace_model='WanVideo\\Wan2_1-VACE_module_1_3B_bf16.safetensors',
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors',
        base_precision='fp16',
        vace_model=wanvideovacemodelselect,
    )

    images_image, masks_image = ImagePadKJ(
        widget_0=0,
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=128,
        widget_5=COLOR,
        widget_6='255,255,255',
        image=image_load_2,
    )

    image_image, width_image, height_image, mask_image = ImageResizeKJv2(
        width=256,
        height=256,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        image=image_load_4,
    )

    image_image_2, width_image_2, height_image_2, mask_image_2 = ImageResizeKJv2(
        width=256,
        height=256,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        image=image,
    )

    image_image_4, width_image_4, height_image_4, mask_image_4 = ImageResizeKJv2(
        width=256,
        height=256,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        image=image_load_3,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt='black and white cartoon character',
        negative_prompt='colorful, bad quality, blurry, messy, chaotic',
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    addlabel = AddLabel(
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4=WHITE,
        widget_5=BLACK,
        widget_6=FREEMONO_TTF,
        widget_7='start_frame',
        widget_8=UP,
        image=image_image_2,
    )

    wanvideotextencode_2 = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt=DEFAULT_NEGATIVE_2,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    depthanything_v2 = DepthAnything_V2(
        da_model=downloadandloaddepthanythingv2model,
        images=image_image_4,
    )

    wanvideotextencode_3 = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt=DEFAULT_NEGATIVE_2,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    images_image_2, masks_image_2 = ImagePadKJ(
        widget_0=0,
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=128,
        widget_5=COLOR,
        widget_6='127,127,127',
        image=image_image,
    )

    image_image_3, width_image_3, height_image_3, mask_image_3 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        width=width_image_2,
        height=height_image_2,
        image=image_load,
    )

    image_image_5, width_image_5, height_image_5, mask_image_5 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=PAD,
        pad_color=V_255_255_255,
        divisible_by=16,
        width=width_image_4,
        height=height_image_4,
        image=images_image,
    )

    image_image_6, width_image_6, height_image_6, mask_image_6 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=PAD,
        pad_color=V_255_255_255,
        divisible_by=16,
        width=width_image_4,
        height=height_image_4,
        image=image_load_2,
    )

    images, masks = WanVideoVACEStartToEndFrame(
        num_frames=DEFAULT_FRAMES_2,
        end_image=image_image_3,
        start_image=image_image_2,
    )

    addlabel_2 = AddLabel(
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4=WHITE,
        widget_5=BLACK,
        widget_6=FREEMONO_TTF,
        widget_7='end_frame',
        widget_8=UP,
        image=image_image_3,
    )

    addlabel_3 = AddLabel(
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4=WHITE,
        widget_5=BLACK,
        widget_6=FREEMONO_TTF,
        widget_7='reference image',
        widget_8=UP,
        image=image_image_5,
    )

    addlabel_4 = AddLabel(
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4=WHITE,
        widget_5=BLACK,
        widget_6=FREEMONO_TTF,
        widget_7='control_video',
        widget_8=UP,
        image=depthanything_v2,
    )

    # Outputs
    vhs_videocombine_3 = VHS_VideoCombine(images=depthanything_v2)

    addlabel_5 = AddLabel(
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4=WHITE,
        widget_5=BLACK,
        widget_6=FREEMONO_TTF,
        widget_7='input',
        widget_8=UP,
        image=images_image_2,
    )

    image_get_6, width_get_5, height_get_5, count_get_5 = GetImageSizeAndCount(
        image=images_image_2,
    )

    image_get_7, mask_get = GetImageRangeFromBatch(images=images_image_2)
    image_get_8, mask_get_2 = GetImageRangeFromBatch(masks=masks_image_2)

    images_wan, masks_wan = WanVideoVACEStartToEndFrame(
        widget_0=33,
        control_images=depthanything_v2,
        num_frames=frame_count,
        start_image=image_image_6,
    )

    previewimage_4 = PreviewImage(images=image_image_5)
    image_get, width, height, count = GetImageSizeAndCount(image=images)

    imageconcatmulti_2 = ImageConcatMulti(
        direction=DOWN,
        match_image_size=True,
        unused_3=None,
        image_1=addlabel,
        image_2=addlabel_2,
    )

    image_get_3, width_get_2, height_get_2, count_get_2 = GetImageSizeAndCount(
        image=images_wan,
    )

    imageconcatmulti_4 = ImageConcatMulti(
        direction=DOWN,
        match_image_size=True,
        unused_3=None,
        image_1=addlabel_3,
        image_2=addlabel_4,
    )

    wanvideovaceencode_3 = WanVideoVACEEncode(
        strength=0,
        vace_end_percent=False,
        vace_start_percent=1,
        widget_0=480,
        widget_1=832,
        widget_2=29,
        widget_3=1.0000000000000002,
        height=height_get_5,
        input_frames=image_get_6,
        input_masks=masks_image_2,
        num_frames=count_get_5,
        vae=wanvideovaeloader,
        width=width_get_5,
    )

    previewimage_2 = PreviewImage(images=image_get_7)
    previewimage_3 = PreviewImage(images=images_wan)
    maskpreview = MaskPreview(mask=masks_wan)
    maskpreview_2 = MaskPreview(mask=masks)
    maskpreview_3 = MaskPreview(mask=mask_get_2)

    wanvideovaceencode = WanVideoVACEEncode(
        strength=0,
        vace_end_percent=False,
        vace_start_percent=1,
        widget_0=480,
        widget_1=832,
        widget_2=29,
        widget_3=1.0000000000000002,
        height=height,
        input_frames=image_get,
        input_masks=masks,
        num_frames=count,
        vae=wanvideovaeloader,
        width=width,
    )

    previewimage = PreviewImage(images=image_get)

    wanvideovaceencode_2 = WanVideoVACEEncode(
        strength=0,
        vace_end_percent=False,
        vace_start_percent=1,
        widget_0=480,
        widget_1=832,
        widget_2=29,
        widget_3=1.0000000000000002,
        height=height_get_2,
        input_frames=image_get_3,
        input_masks=masks_wan,
        num_frames=count_get_2,
        vae=wanvideovaeloader,
        width=width_get_2,
    )

    samples_wan_2, denoised_samples_wan_2 = WanVideoSampler(
        steps=1,
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

    samples, denoised_samples = WanVideoSampler(
        steps=1,
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

    samples_wan, denoised_samples_wan = WanVideoSampler(
        steps=1,
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

    wanvideodecode_3 = WanVideoDecode(samples=samples_wan_2, vae=wanvideovaeloader)
    wanvideodecode = WanVideoDecode(samples=samples, vae=wanvideovaeloader)
    wanvideodecode_2 = WanVideoDecode(samples=samples_wan, vae=wanvideovaeloader)

    image_get_5, width_get_4, height_get_4, count_get_4 = GetImageSizeAndCount(
        image=wanvideodecode_3,
    )

    image_get_2, width_get, height_get, count_get = GetImageSizeAndCount(
        image=wanvideodecode,
    )

    image_get_4, width_get_3, height_get_3, count_get_3 = GetImageSizeAndCount(
        image=wanvideodecode_2,
    )

    emptyimage_3 = EmptyImage(widget_1=512, width=8, height=height_get_4)
    emptyimage = EmptyImage(widget_1=512, width=8, height=height_get)
    emptyimage_2 = EmptyImage(widget_1=512, width=8, height=height_get_3)

    imageconcatmulti_5 = ImageConcatMulti(
        inputcount=3,
        direction=LEFT,
        match_image_size=True,
        unused_3=None,
        image_1=image_get_5,
        image_2=emptyimage_3,
        image_3=addlabel_5,
    )

    imageconcatmulti = ImageConcatMulti(
        inputcount=3,
        direction=LEFT,
        match_image_size=True,
        unused_3=None,
        image_1=image_get_2,
        image_2=emptyimage,
        image_3=imageconcatmulti_2,
    )

    imageconcatmulti_3 = ImageConcatMulti(
        inputcount=3,
        direction=LEFT,
        match_image_size=True,
        unused_3=None,
        image_1=image_get_4,
        image_2=emptyimage_2,
        image_3=imageconcatmulti_4,
    )

    vhs_videocombine_4 = VHS_VideoCombine(images=imageconcatmulti_5)
    vhs_videocombine = VHS_VideoCombine(images=imageconcatmulti)
    vhs_videocombine_2 = VHS_VideoCombine(images=imageconcatmulti_3)


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
        'width': InputSpec(node=emptyimage, field='width', default=8, type='INT'),
        'height': InputSpec(node=image_image, field='height', default=256, type='INT'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=previewimage, output_type='PreviewImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

