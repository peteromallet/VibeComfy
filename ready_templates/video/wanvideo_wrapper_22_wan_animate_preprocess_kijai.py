# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, LoadImage
from vibecomfy.nodes.kjnodes import BlockifyMask, DrawMaskOnImage, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.sam2 import DownloadAndLoadSAM2Model, Sam2Segmentation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wananimatepreprocess import DrawViTPose, OnnxDetectionModelLoader, PoseAndFaceDetection
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoContextOptions, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 501
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
VIDEO_H264_MP4 = 'video/h264-mp4'
YUV420P = 'yuv420p'


MODELS = {
    'wan2_2_animate_14b_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors', subdir='diffusion_models/WanVideo/2_2'),
    'wananimate_relight_lora_fp16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors', subdir='loras/WanVideo'),
    'clip_vision': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors', subdir='clip_vision'),
    'sam2_hiera_base_plus': ModelAsset(url='https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors', subdir='sams'),
    'yolov10m': ModelAsset(url='https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx', subdir='detection'),
    'vitpose_l_wholebody': ModelAsset(url='https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx', subdir='detection'),
    'yolox_l_torchscript': ModelAsset(url='https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.torchscript.pt', subdir='onnx/yolo'),
    'dw_ll_ucoco_384_bs5_torchscript': ModelAsset(url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt', subdir='onnx/dwpose'),
    'wan2_1_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', subdir='vae/wanvideo'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', subdir='text_encoders'),
    'lightx2v_i2v_14b_480p_cfg_step_distill_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', subdir='loras/WanVideo/Lightx2v'),
}

READY_METADATA = ReadyMetadata.build(
    capability='animate_character',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanAnimatePreprocess', 'ComfyUI-WanVideoWrapper', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanAnimatePreprocess', 'source': 'git', 'version': 'unknown', 'commit': '1a35b81a418bbba093356ad19b19bf2a76a24f4e', 'url': 'https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'version': 'unknown', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'ComfyUI-segment-anything-2', 'source': 'git', 'version': 'unknown', 'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git'}, {'slug': 'comfyui_controlnet_aux', 'source': 'git', 'version': 'unknown', 'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-segment-anything-2': {'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git', 'class_schema_sha256': 'e3640990ce145928d9404234721b4f23fd02717c7f07af03b3d0be0f8a150e9c', 'classes_used': ['DownloadAndLoadSAM2Model', 'Sam2Segmentation'], 'pip_packages': ['opencv-python-headless'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanAnimatePreprocess': {'commit': '1a35b81a418bbba093356ad19b19bf2a76a24f4e', 'url': 'https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git', 'class_schema_sha256': '2037d30d5343a44a9403c928ea18688bb050b9114fc2d3741df2c6b64edaf7f5', 'classes_used': ['DrawViTPose', 'OnnxDetectionModelLoader', 'PoseAndFaceDetection'], 'pip_packages': ['onnx', 'onnxruntime-gpu', 'opencv-python-headless'], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    source_path='/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/ready_templates/video/wanvideo_wrapper_22_wan_animate_preprocess_kijai.py',
    source_id='video/wanvideo_wrapper_22_wan_animate_preprocess_kijai',
    source_type='ready_template',
    source_workflow_path='/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/ready_templates/video/wanvideo_wrapper_22_wan_animate_preprocess_kijai.py',
    source_hash='sha256:e4d082285505be0612f1ef54afddf89daf4edc67c3b3c9c91c2600e37c6b8303',
    output_mode='ready_template',
    ready_id='video/wanvideo_wrapper_22_wan_animate_preprocess_kijai',
    approach='Kijai WanAnimate preprocessing workflow using reference image, pose video, SAM2/DWPose masking, relight LoRA, and Lightx2v LoRA',
    runtime_note='Worker scratchpads patch reference image, motion video, prompt, seed, and output options.',
    smoke_resolution='832x480_motion_source',
    source_url='https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_WanAnimate_preprocess_example_02.json',
    provenance={'source_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/ready_templates/video/wanvideo_wrapper_22_wan_animate_preprocess_kijai.py', 'source_id': 'video/wanvideo_wrapper_22_wan_animate_preprocess_kijai', 'source_type': 'ready_template', 'source_workflow_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/ready_templates/video/wanvideo_wrapper_22_wan_animate_preprocess_kijai.py', 'source_hash': 'sha256:e4d082285505be0612f1ef54afddf89daf4edc67c3b3c9c91c2600e37c6b8303', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_wan_animate_preprocess_kijai'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

    wanvideovaeloader = WanVideoVAELoader(
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
    )

    wanvideoblockswap = WanVideoBlockSwap(
        blocks_to_swap=25,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    # Inputs
    image, mask = LoadImage(image='refer.jpeg')

    text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
        model_name='umt5-xxl-enc-bf16.safetensors',
        positive_prompt='man is walking, style is soft 3D render style, night time, moonlight',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        use_disk_cache=False,
    )

    clipvisionloader = CLIPVisionLoader(clip_name='clip_vision_h.safetensors')

    downloadandloadsam2model = DownloadAndLoadSAM2Model(
        model='sam2.1_hiera_base_plus.safetensors',
        segmentor='video',
        device='cuda',
    )

    wanvideocontextoptions = WanVideoContextOptions(
        context_schedule='static_standard',
        context_overlap=32,
    )

    intconstant = INTConstant(value=832)
    intconstant_2 = INTConstant(value=480)

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        lora_0='WanVideo\\WanAnimate_relight_lora_fp16.safetensors',
        lora_1='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength_1=1.2,
        merge_loras=False,
    )

    onnxdetectionmodelloader = OnnxDetectionModelLoader(
        vitpose_model='vitpose-l-wholebody.onnx',
        yolo_model='onnx\\yolov10m.onnx',
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\2_2\\Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        compile_args=wanvideotorchcompilesettings,
    )

    image_load, frame_count, audio, video_info = VHS_LoadVideo(
        force_rate=16,
        video='raw.mp4',
        videopreview={'hidden': False, 'params': {'custom_height': 544, 'custom_width': 960, 'filename': 'raw.mp4', 'force_rate': 16, 'format': 'video/mp4', 'frame_load_cap': 0, 'select_every_nth': 1, 'skip_first_frames': 0, 'type': 'input'}, 'paused': False},
        custom_height=intconstant_2,
        custom_width=intconstant,
        **{'choose video to upload': 'image'},
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='pad_edge_pixel',
        crop_position='top',
        divisible_by=16,
        device='cpu',
        widget_0=832,
        widget_1=480,
        width=intconstant,
        height=intconstant_2,
        image=image,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader,
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        clip_vision=clipvisionloader,
        image_1=image_image,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=image_load)

    wanvideosetblockswap = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    pose_data, face_images, key_frame_body_points, bboxes, face_bboxes = PoseAndFaceDetection(
        widget_0=832,
        widget_1=480,
        width=width_get,
        height=height_get,
        images=image_get,
        model=onnxdetectionmodelloader,
    )

    sam2segmentation = Sam2Segmentation(
        bboxes=bboxes,
        image=image_get,
        sam2_model=downloadandloadsam2model,
    )

    drawvitpose = DrawViTPose(
        widget_0=832,
        widget_1=480,
        width=width_get,
        height=height_get,
        pose_data=pose_data,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='vitpose',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'vitpose_00004.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\vitpose_00004.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'vitpose_00004.png'}, 'paused': False},
        images=face_images,
    )

    imageconcatmulti = ImageConcatMulti(
        inputcount=4,
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=image_image,
        image_2=face_images,
        image_3=drawvitpose,
        image_4=image_load,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideo2_1_T2V',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_1_T2V_00002.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00002.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_1_T2V_00002.png'}, 'paused': False},
        images=drawvitpose,
    )

    growmaskwithblur = raw_call('GrowMaskWithBlur', '182',
        _outputs=('MASK', 'MASK_INVERTED'),
        expand=10,
        unused_7=False,
        mask=sam2segmentation,
    )

    blockifymask = BlockifyMask(masks=growmaskwithblur.out('MASK'))
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
        face_images=face_images,
        mask=blockifymask,
        pose_images=drawvitpose,
        ref_images=image_image,
        vae=wanvideovaeloader,
    )

    vhs_videocombine_3 = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideo2_1_T2V',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_1_T2V_00004.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00004.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_1_T2V_00004.png'}, 'paused': False},
        images=drawmaskonimage,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=4,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        image_embeds=wanvideoanimateembeds,
        model=wanvideosetblockswap,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_get_2, width_get_2, height_get_2, count_get = GetImageSizeAndCount(
        image=wanvideodecode,
    )

    imageconcatmulti_2 = ImageConcatMulti(
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=image_get_2,
        image_2=imageconcatmulti,
    )

    vhs_videocombine_4 = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='Wanimate',
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=True,
        videopreview={'hidden': False, 'params': {'filename': 'Wanimate_00002-audio.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\Wanimate_00002-audio.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'Wanimate_00002.png'}, 'paused': False},
        audio=audio,
        images=imageconcatmulti_2,
    )


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='refer.jpeg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='vitpose')

