# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.controlnet_aux import DWPreprocessor
from vibecomfy.nodes.core import CLIPVisionLoader, GrowMask, LoadImage, PixelPerfectResolution
from vibecomfy.nodes.kjnodes import BlockifyMask, DrawMaskOnImage, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageCropByMaskAndResize, ImageResizeKJv2, PointsEditor
from vibecomfy.nodes.sam2 import DownloadAndLoadSAM2Model, Sam2Segmentation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import FaceMaskFromPoseKeypoints, WanVideoAnimateEmbeds, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


BBOX_DETECTOR_NAME = 'yolox_l.torchscript.pt'
CLIP_NAME = 'clip_vision_h.safetensors'
CLIP_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'man is walking, style is soft 3D render style, night time, moonlight'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
LORA__NAME = 'WanVideo/WanAnimate_relight_lora_fp16.safetensors'
LORA__NAME_2 = 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME = 'sam2_hiera_base_plus.safetensors'
MODEL_NAME_2 = 'WanVideo/2_2/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='57', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='107', field='width', default=832, type='INT'),
    'height': InputSpec(node='107', field='height', default=480, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PointsEditor'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-segment-anything-2': {'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git', 'class_schema_sha256': 'e3640990ce145928d9404234721b4f23fd02717c7f07af03b3d0be0f8a150e9c', 'classes_used': ['DownloadAndLoadSAM2Model', 'Sam2Segmentation'], 'pip_packages': ['opencv-python-headless'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json', 'source_id': 'video/wanvideo_wrapper_wan_animate', 'upstream_source_id': 'wan_animate', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_wan_animate'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)

    wanvideoblockswap = WanVideoBlockSwap(
        _id='51',
        blocks_to_swap=25,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    # Inputs
    image_2, _ = LoadImage(_id='57', image='refer.jpeg')

    text_embeds, _, _ = WanVideoTextEncodeCached(
        _id='65',
        model_name=CLIP_NAME_2,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        use_disk_cache=False,
    )

    # Loaders
    clipvisionloader = CLIPVisionLoader(_id='71', clip_name=CLIP_NAME)

    downloadandloadsam2model = DownloadAndLoadSAM2Model(
        _id='102',
        model=MODEL_NAME,
        segmentor='video',
        device='cuda',
    )

    intconstant = INTConstant(_id='150', value=832)
    intconstant_2 = INTConstant(_id='151', value=480)

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        _id='171',
        lora_0=LORA__NAME,
        lora_1=LORA__NAME_2,
        strength_1=1.2,
        merge_loras=False,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='22',
        model=MODEL_NAME_2,
        base_precision='fp16_fast',
        attention_mode='sageattn',
        compile_args=wanvideotorchcompilesettings,
    )

    image_3, frame_count, audio, _ = VHS_LoadVideo(
        _id='63',
        video='raw.mp4',
        force_rate=16,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'raw.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 16, 'custom_width': 960, 'custom_height': 544, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        custom_width=intconstant,
        custom_height=intconstant_2,
        **{'choose video to upload': 'image'},
    )

    image_4, _, _, _ = ImageResizeKJv2(
        _id='64',
        upscale_method='lanczos',
        keep_proportion='pad_edge_pixel',
        crop_position='top',
        divisible_by=16,
        device='cpu',
        width=intconstant,
        height=intconstant_2,
        image=image_2,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        _id='48',
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader,
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        _id='70',
        clip_vision=clipvisionloader,
        image_1=image_4,
    )

    positive_coords, _, _, _, _ = PointsEditor(
        _id='107',
        points_store='{"positive":[{"x":483.34844284815,"y":333.283583335728},{"x":479.85856239437277,"y":158.78956064686517}],"negative":[{"x":0,"y":0}]}',
        coordinates='[{"x":483.34844284815,"y":333.283583335728},{"x":479.85856239437277,"y":158.78956064686517}]',
        neg_coordinates='[{"x":0,"y":0}]',
        bbox_store='[{}]',
        bboxes='[{}]',
        bbox_format='xyxy',
        width=832,
        height=480,
        widget_10=None,
        widget_9='',
        bg_image=image_3,
    )

    pixelperfectresolution = PixelPerfectResolution(
        _id='152',
        resize_mode=512,
        widget_1=512,
        widget_2='Just Resize',
        image_gen_height=intconstant_2,
        image_gen_width=intconstant,
        original_image=image_3,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='50',
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    dwpreprocessor = DWPreprocessor(
        _id='73',
        _outputs=('IMAGE', 'POSE_KEYPOINT'),
        detect_hand='disable',
        detect_body='enable',
        detect_face='disable',
        bbox_detector=BBOX_DETECTOR_NAME,
        pose_estimator=POSE_ESTIMATOR_NAME,
        scale_stick_for_xinsr_cn='disable',
        resolution=pixelperfectresolution,
        image=image_3,
    )

    sam2segmentation = Sam2Segmentation(
        _id='104',
        coordinates_positive=positive_coords,
        image=image_3,
        sam2_model=downloadandloadsam2model,
    )

    growmask = GrowMask(_id='100', expand=10, mask=sam2segmentation)

    facemaskfromposekeypoints = FaceMaskFromPoseKeypoints(
        _id='120',
        pose_kps=dwpreprocessor.out(1),
    )

    images, _, _ = ImageCropByMaskAndResize(
        _id='96',
        widget_0=512,
        widget_1=0,
        widget_2=128,
        widget_3=512,
        image=image_3,
        mask=facemaskfromposekeypoints,
    )

    blockifymask = BlockifyMask(_id='108', masks=growmask)

    imageconcatmulti_2 = ImageConcatMulti(
        _id='77',
        inputcount=4,
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=image_4,
        image_2=images,
        image_3=dwpreprocessor.out(0),
        image_4=image_3,
    )

    drawmaskonimage = DrawMaskOnImage(_id='99', image=image_3, mask=blockifymask)

    # Outputs
    vhs_videocombine_3 = VHS_VideoCombine(
        _id='112',
        frame_rate=16,
        filename_prefix='WanVideo2_1_T2V',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_1_T2V_00055.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_1_T2V_00055.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00055.mp4'}},
        images=images,
    )

    wanvideoanimateembeds = WanVideoAnimateEmbeds(
        _id='62',
        force_offload=False,
        unused_8=False,
        width=intconstant,
        height=intconstant_2,
        num_frames=frame_count,
        bg_images=drawmaskonimage,
        clip_embeds=wanvideoclipvisionencode,
        face_images=images,
        mask=blockifymask,
        pose_images=dwpreprocessor.out(0),
        ref_images=image_4,
        vae=wanvideovaeloader,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        _id='75',
        frame_rate=16,
        filename_prefix='WanVideo2_1_T2V',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_1_T2V_00054.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_1_T2V_00054.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00054.mp4'}},
        images=drawmaskonimage,
    )

    samples, _ = WanVideoSampler(
        _id='27',
        steps=6,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        image_embeds=wanvideoanimateembeds,
        model=wanvideosetblockswap,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        _id='28',
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image, _, _, _ = GetImageSizeAndCount(_id='42', image=wanvideodecode)

    imageconcatmulti = ImageConcatMulti(
        _id='66',
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=image,
        image_2=imageconcatmulti_2,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=16,
        filename_prefix='Wanimate',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'Wanimate_00015-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'Wanimate_00015.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\Wanimate_00015-audio.mp4'}},
        audio=audio,
        images=imageconcatmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='Wanimate')

