# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, GrowMask, LoadImage, PixelPerfectResolution
from vibecomfy.nodes.kjnodes import BlockifyMask, DrawMaskOnImage, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2, PointsEditor
from vibecomfy.nodes.sam2 import DownloadAndLoadSAM2Model, Sam2Segmentation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoContextOptions, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


BBOX_DETECTOR_NAME = 'yolox_l.torchscript.pt'
CLIP_NAME = 'clip_vision_h.safetensors'
DEFAULT_FRAMES = 501
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'man is walking, style is soft 3D render style, night time, moonlight'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
LORA__NAME = 'WanVideo\\WanAnimate_relight_lora_fp16.safetensors'
LORA__NAME_2 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_3 = 'sam2_hiera_base_plus.safetensors'
MODEL_NAME_4 = 'WanVideo\\2_2\\Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'

READY_METADATA = ReadyMetadata.build(
    capability='animate_reference_video',
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PointsEditor'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-segment-anything-2': {'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git', 'class_schema_sha256': 'e3640990ce145928d9404234721b4f23fd02717c7f07af03b3d0be0f8a150e9c', 'classes_used': ['DownloadAndLoadSAM2Model', 'Sam2Segmentation'], 'pip_packages': ['opencv-python-headless'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='WanAnimate reference animation',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME)

    wanvideoblockswap = WanVideoBlockSwap(
        blocks_to_swap=25,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    # Inputs
    image, mask = LoadImage(image='refer.jpeg')

    text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
        model_name=MODEL_NAME_2,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        use_disk_cache=False,
    )

    clipvisionloader = CLIPVisionLoader(clip_name=CLIP_NAME)

    downloadandloadsam2model = DownloadAndLoadSAM2Model(
        model=MODEL_NAME_3,
        segmentor='video',
        device='cuda',
    )

    wanvideocontextoptions = WanVideoContextOptions(
        context_schedule='static_standard',
        context_overlap=32,
    )

    reroute = raw_call('Reroute', '147')
    intconstant = INTConstant(value=832)
    intconstant_2 = INTConstant(value=480)

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        lora_0=LORA__NAME,
        lora_1=LORA__NAME_2,
        strength_1=1.2,
        merge_loras=False,
    )

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_4,
        base_precision='fp16',
        compile_args=wanvideotorchcompilesettings,
    )

    image_load, frame_count, audio, video_info = VHS_LoadVideo(
        video='wolf_interpolated.mp4',
        custom_height=intconstant_2,
        custom_width=intconstant,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='pad_edge_pixel',
        crop_position='top',
        divisible_by=16,
        device='cpu',
        widget_0=256,
        widget_1=256,
        width=intconstant,
        height=intconstant_2,
        image=image,
    )

    pixelperfectresolution = PixelPerfectResolution(
        resize_mode=512,
        widget_1=512,
        widget_2='Just Resize',
        image_gen_height=intconstant_2,
        image_gen_width=intconstant,
        original_image=reroute.out(0),
    )

    dwpreprocessor = raw_call('DWPreprocessor', '73',
        detect_hand='disable',
        detect_body='enable',
        detect_face='disable',
        bbox_detector=BBOX_DETECTOR_NAME,
        pose_estimator=POSE_ESTIMATOR_NAME,
        scale_stick_for_xinsr_cn='disable',
        widget_3=960,
        resolution=pixelperfectresolution,
        image=reroute.out(0),
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        clip_vision=clipvisionloader,
        image_1=image_image,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader,
    )

    positive_coords, negative_coords, bbox, bbox_mask, cropped_image = PointsEditor(
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
        bg_image=image_load,
    )

    facemaskfromposekeypoints = raw_call('FaceMaskFromPoseKeypoints', '120', widget_0=0, pose_kps=dwpreprocessor.out(1))

    wanvideosetblockswap = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    sam2segmentation = Sam2Segmentation(
        coordinates_positive=positive_coords,
        image=image_load,
        sam2_model=downloadandloadsam2model,
    )

    imagecropbymaskandresize = raw_call('ImageCropByMaskAndResize', '96',
        _outputs=('IMAGES', 'MASKS', 'BBOX'),
        widget_0=512,
        widget_1=0,
        widget_2=128,
        widget_3=512,
        image=reroute.out(0),
        mask=facemaskfromposekeypoints,
    )

    growmask = GrowMask(expand=10, mask=sam2segmentation)

    imageconcatmulti = ImageConcatMulti(
        inputcount=4,
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=image_image,
        image_2=imagecropbymaskandresize.out('IMAGES'),
        image_3=dwpreprocessor,
        image_4=image_load,
    )

    blockifymask = BlockifyMask(masks=growmask)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(images=imagecropbymaskandresize.out('IMAGES'))
    drawmaskonimage = DrawMaskOnImage(image=image_load, mask=blockifymask)

    wanvideoanimateembeds = raw_call('WanVideoAnimateEmbeds', '62',
        force_offload=False,
        unused_8=False,
        widget_0=832,
        widget_1=480,
        widget_2=501,
        width=intconstant,
        height=intconstant_2,
        num_frames=frame_count,
        bg_images=drawmaskonimage,
        clip_embeds=wanvideoclipvisionencode,
        face_images=imagecropbymaskandresize.out('IMAGES'),
        mask=blockifymask,
        pose_images=dwpreprocessor,
        ref_images=image_image,
        vae=wanvideovaeloader,
    )

    vhs_videocombine_2 = VHS_VideoCombine(images=drawmaskonimage)

    samples, denoised_samples = WanVideoSampler(
        steps=1,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        widget_0=1,
        image_embeds=wanvideoanimateembeds,
        model=wanvideosetblockswap,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=wanvideodecode)

    imageconcatmulti_2 = ImageConcatMulti(
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=image_get,
        image_2=imageconcatmulti,
    )

    vhs_videocombine_3 = VHS_VideoCombine(audio=audio, images=imageconcatmulti_2)


    PUBLIC_INPUTS = {
        'model': InputSpec(node=wanvideovaeloader, field='model_name', default=MODEL_NAME),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED),
        'image': InputSpec(node=image, field='image', default='refer.jpeg'),
        'width': InputSpec(node=positive_coords, field='width', default=832),
        'height': InputSpec(node=positive_coords, field='height', default=480),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

