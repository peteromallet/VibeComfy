# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionEncode, CLIPVisionLoader, CreateVideo, GetVideoComponents, GrowMask, ImageFromBatch, ImageScale, KSampler, LoadImage, LoadVideo, LoraLoaderModelOnly, ModelSamplingSD3, PixelPerfectResolution, SaveVideo, TrimVideoLatent, UNETLoader, VAEDecode, VAELoader, WanAnimateToVideo
from vibecomfy.nodes.kjnodes import BlockifyMask, DrawMaskOnImage, PointsEditor
from vibecomfy.nodes.sam2 import DownloadAndLoadSAM2Model, Sam2Segmentation


BBOX_DETECTOR_NAME = 'yolox_l.onnx'
CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
CLIP_NAME_2 = 'clip_vision_h.safetensors'
DEFAULT_FPS = 16
DEFAULT_FRAMES = 81
DEFAULT_FRAMES_2 = 4096
DEFAULT_PROMPT = 'a person moving naturally, cinematic motion'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
LORA_NAME = 'lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
LORA_NAME_2 = 'WanAnimate_relight_lora_fp16.safetensors'
MODEL_NAME = 'sam2_hiera_base_plus.safetensors'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
SCALE_STICK_FOR_XINSR_CN = 'disable'
UNET_NAME = 'Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'
VAE_NAME = 'wan_2.1_vae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors', sha256='2936b31473a967e7a429a6646bba60e7862d0938e178b58b2a140f391dd5b8e6', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=18401760586, subdir='diffusion_models'),
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', subdir='checkpoints'),
    'lora': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors', sha256='fc646c74c73f4b251f5fd9bc440ef21b03b27305f499966c68b2b3aa31498561', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=1436672440, subdir='loras'),
    'checkpoint_2': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors', hf_revision='main', subdir='checkpoints'),
    'checkpoint_3': ModelAsset(url='https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors', subdir='checkpoints'),
    'checkpoint_4': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors', hf_revision='main', subdir='checkpoints'),
    'checkpoint_5': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors', subdir='checkpoints'),
    'checkpoint_6': ModelAsset(url='https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.onnx', subdir='checkpoints'),
    'checkpoint_7': ModelAsset(url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt', hf_revision='main', subdir='checkpoints'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='animate_character',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'DrawMaskOnImage', 'PointsEditor'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-segment-anything-2': {'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git', 'class_schema_sha256': 'e3640990ce145928d9404234721b4f23fd02717c7f07af03b3d0be0f8a150e9c', 'classes_used': ['DownloadAndLoadSAM2Model', 'Sam2Segmentation'], 'pip_packages': ['opencv-python-headless'], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='Native ComfyUI Wan 2.2 Animate first-stage replacement workflow using DWPose, SAM2 masking, and native WanAnimateToVideo.',
    runtime_note='Worker scratchpads patch reference image, motion video, prompt, negative prompt, seed, steps, width, height, frame count, and output options.',
    source_url='https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_animate.json',
    provenance={'source_workflow': 'ready_templates/video/wan22_animate_native_first_stage.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')
        vaeloader = VAELoader(vae_name=VAE_NAME)
        clipvisionloader = CLIPVisionLoader(clip_name=CLIP_NAME_2)

        # Inputs
        image, mask = LoadImage(image=public('image', default='reference_image.png'))
        unetloader = UNETLoader(unet_name=UNET_NAME)

        downloadandloadsam2model = DownloadAndLoadSAM2Model(
            model=MODEL_NAME,
            segmentor='video',
            device='cuda',
        )

        loadvideo = LoadVideo(file='motion_video.mp4')
        primitiveint = raw_call('PrimitiveInt', '159', value=832)
        primitiveint_2 = raw_call('PrimitiveInt', '160', value=480)

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('prompt', default='low quality, blurry, distorted'),
            clip=cliploader,
        )

        clipvisionencode = CLIPVisionEncode(
            crop='none',
            clip_vision=clipvisionloader,
            image=image,
        )

        loraloadermodelonly = LoraLoaderModelOnly(lora_name=LORA_NAME, model=unetloader)
        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
        images, audio, fps = GetVideoComponents(video=loadvideo)

        loraloadermodelonly_2 = LoraLoaderModelOnly(
            lora_name=LORA_NAME_2,
            model=loraloadermodelonly,
        )

        pixelperfectresolution = PixelPerfectResolution(
            image_gen_height=primitiveint_2,
            image_gen_width=primitiveint,
            original_image=images,
        )

        imagescale = ImageScale(
            upscale_method='lanczos',
            crop='center',
            width=primitiveint,
            height=primitiveint_2,
            image=images,
        )

        dwpreprocessor = raw_call('DWPreprocessor', '100',
            detect_hand='disable',
            detect_body='disable',
            detect_face='enable',
            bbox_detector=BBOX_DETECTOR_NAME,
            pose_estimator=POSE_ESTIMATOR_NAME,
            scale_stick_for_xinsr_cn=SCALE_STICK_FOR_XINSR_CN,
            resolution=pixelperfectresolution,
            image=imagescale,
        )

        dwpreprocessor_2 = raw_call('DWPreprocessor', '101',
            detect_hand='enable',
            detect_body='enable',
            detect_face='disable',
            bbox_detector=BBOX_DETECTOR_NAME,
            pose_estimator=POSE_ESTIMATOR_NAME,
            scale_stick_for_xinsr_cn=SCALE_STICK_FOR_XINSR_CN,
            resolution=pixelperfectresolution,
            image=imagescale,
        )

        modelsamplingsd3 = ModelSamplingSD3(shift=8, model=loraloadermodelonly_2)

        positive_coords, negative_coords, bbox, bbox_mask, cropped_image = PointsEditor(
            points_store='[{}]',
            coordinates='[{"x":320,"y":320}]',
            neg_coordinates='[]',
            bbox_store='[{}]',
            bboxes='[{"startX":160,"startY":96,"endX":480,"endY":544}]',
            bbox_format='xyxy',
            width=public('width', default=640),
            height=public('height', default=640),
            bg_image=imagescale,
        )

        sam2segmentation = Sam2Segmentation(
            keep_model_loaded=True,
            coordinates_positive=positive_coords,
            image=imagescale,
            sam2_model=downloadandloadsam2model,
        )

        growmask = GrowMask(expand=10, mask=sam2segmentation)
        blockifymask = BlockifyMask(masks=growmask)
        drawmaskonimage = DrawMaskOnImage(image=imagescale, mask=blockifymask)

        positive, negative, latent, trim_latent, trim_image, video_frame_offset = WanAnimateToVideo(
            length=public('frames', default=DEFAULT_FRAMES),
            background_video=drawmaskonimage,
            character_mask=blockifymask,
            clip_vision_output=clipvisionencode,
            face_video=dwpreprocessor,
            height=primitiveint_2,
            negative=cliptextencode,
            pose_video=dwpreprocessor_2,
            positive=cliptextencode_2,
            reference_image=image,
            vae=vaeloader,
            width=primitiveint,
        )

        ksampler = KSampler(
            seed=public('seed', default=DEFAULT_SEED),
            steps=public('steps', default=20),
            cfg=public('cfg', default=GUIDE_STRENGTH),
            sampler_name=public('sampler_name', default='euler'),
            latent_image=latent,
            model=modelsamplingsd3,
            negative=negative,
            positive=positive,
        )

        trimvideolatent = TrimVideoLatent(samples=ksampler, trim_amount=trim_latent)

        # Decode
        vaedecode = VAEDecode(samples=trimvideolatent, vae=vaeloader)

        imagefrombatch = ImageFromBatch(
            length=DEFAULT_FRAMES_2,
            batch_index=trim_image,
            image=vaedecode,
        )

        createvideo = CreateVideo(
            fps=public('fps', default=DEFAULT_FPS),
            audio=audio,
            images=imagefrombatch,
        )

        # Outputs
        savevideo = SaveVideo(video=createvideo)


        wf.register_input('model', unetloader.node.id, 'unet_name', UNET_NAME)
        return wf.finalize({}, spec=OUTPUT_SPEC)

