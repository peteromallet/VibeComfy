# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, LoadImage
from vibecomfy.nodes.kjnodes import BlockifyMask, DrawMaskOnImage, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.sam2 import DownloadAndLoadSAM2Model, Sam2Segmentation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wananimatepreprocess import DrawViTPose, OnnxDetectionModelLoader, PoseAndFaceDetection
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoContextOptions, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader

# --- legacy SymbolicNodeRef shim (this template is marked manual; the
# public ``vibecomfy.templates.ref`` symbol is retired) -------------------
class SymbolicNodeRef:
    """Local copy of the retired ``vibecomfy.templates.SymbolicNodeRef``."""

    __slots__ = ("label",)

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return f"SymbolicNodeRef({self.label!r})"

    def __eq__(self, other):
        return isinstance(other, SymbolicNodeRef) and self.label == other.label

    def __hash__(self):
        return hash(("SymbolicNodeRef", self.label))

    def resolve(self, namespace, wf):
        value = namespace.get(self.label)
        node_id = None
        if hasattr(value, "node_id"):
            node_id = str(value.node_id)
        elif hasattr(value, "node") and value.node is not None and hasattr(value.node, "id"):
            node_id = str(value.node.id)
        elif hasattr(value, "id"):
            node_id = str(value.id)
        elif isinstance(value, str):
            node_id = value
        if node_id is None or node_id not in wf.nodes:
            raise ValueError(
                f"SymbolicNodeRef({self.label!r}) could not be resolved to a node "
                f"in workflow {wf.id!r}"
            )
        wf.metadata.setdefault("id_map", {})[self.label] = node_id
        return node_id


def ref(label):
    """Local copy of the retired ``vibecomfy.templates.ref``."""

    return SymbolicNodeRef(label)
# --- end legacy shim -----------------------------------------------------


DEFAULT_FRAMES = 501
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'man is walking, style is soft 3D render style, night time, moonlight'
DEFAULT_SEED = 42
FORMAT = 'video/h264-mp4'
GUIDE_STRENGTH = 1
MODEL_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_3 = 'clip_vision_h.safetensors'
MODEL_NAME_4 = 'sam2.1_hiera_base_plus.safetensors'
MODEL_NAME_5 = 'WanVideo\\WanAnimate_relight_lora_fp16.safetensors'
MODEL_NAME_6 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME_7 = 'vitpose-l-wholebody.onnx'
MODEL_NAME_8 = 'onnx\\yolov10m.onnx'
MODEL_NAME_9 = 'WanVideo\\2_2\\Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'
PIX_FMT = 'yuv420p'
WIDGET_0 = 'background_image'
WIDGET_0_10 = 'frame_count'
WIDGET_0_11 = 'VAE'
WIDGET_0_2 = 'reference_image'
WIDGET_0_3 = 'face_images'
WIDGET_0_4 = 'pose_images'
WIDGET_0_5 = 'mask'
WIDGET_0_6 = 'input_video'
WIDGET_0_7 = 'input_audio'
WIDGET_0_8 = 'width'
WIDGET_0_9 = 'height'


MODELS = {
    'wan2_2_animate_14b_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors', subdir='diffusion_models/WanVideo/2_2'),
    'wananimate_relight_lora_fp16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors', subdir='loras/WanVideo'),
    'clip_vision_h': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors', subdir='clip_vision'),
    'sam2_hiera_base_plus': ModelAsset(url='https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors', subdir='sams'),
    'yolov10m': ModelAsset(url='https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx', subdir='detection'),
    'vitpose_l_wholebody': ModelAsset(url='https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx', subdir='detection'),
    'yolox_l_torchscript': ModelAsset(url='https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.torchscript.pt', subdir='onnx/yolo'),
    'dw_ll_ucoco_384_bs5_torchscript': ModelAsset(url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt', subdir='onnx/dwpose'),
    'wan2_1_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', subdir='vae/wanvideo'),
    'umt5_xxl_enc_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', subdir='text_encoders'),
    'lightx2v_i2v_14b_480p_cfg_step_distill_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', subdir='loras/WanVideo/Lightx2v'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('wanvideovaeloader'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='refer.jpeg'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='refer.jpeg'),
}

READY_METADATA = ReadyMetadata.build(
    capability='animate_character',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanAnimatePreprocess', 'ComfyUI-WanVideoWrapper', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-segment-anything-2': {'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git', 'class_schema_sha256': 'e3640990ce145928d9404234721b4f23fd02717c7f07af03b3d0be0f8a150e9c', 'classes_used': ['DownloadAndLoadSAM2Model', 'Sam2Segmentation'], 'pip_packages': ['opencv-python-headless'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanAnimatePreprocess': {'commit': '1a35b81a418bbba093356ad19b19bf2a76a24f4e', 'url': 'https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git', 'class_schema_sha256': '2037d30d5343a44a9403c928ea18688bb050b9114fc2d3741df2c6b64edaf7f5', 'classes_used': ['DrawViTPose', 'OnnxDetectionModelLoader', 'PoseAndFaceDetection'], 'pip_packages': ['onnx', 'onnxruntime-gpu', 'opencv-python-headless'], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='Kijai WanAnimate preprocessing workflow using reference image, pose video, SAM2/DWPose masking, relight LoRA, and Lightx2v LoRA',
    runtime_note='Worker scratchpads patch reference image, motion video, prompt, seed, and output options.',
    smoke_resolution='832x480_motion_source',
    source_url='https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_WanAnimate_preprocess_example_02.json',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='51',
            blocks_to_swap=25,
            use_non_blocking=True,
            prefetch_blocks=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        # Inputs
        loadimage = LoadImage(_id='57', image='refer.jpeg', _outputs=('IMAGE', 'MASK'))
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id
        wanvideotextencodecached = WanVideoTextEncodeCached(
            _id='65',
            model_name=MODEL_NAME_2,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            use_disk_cache=False,
            _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencodecached'] = wanvideotextencodecached.node.id

        # Loaders
        clipvisionloader = CLIPVisionLoader(_id='71', clip_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['clipvisionloader'] = clipvisionloader.node.id
        downloadandloadsam2model = DownloadAndLoadSAM2Model(
            _id='102',
            model=MODEL_NAME_4,
            segmentor='video',
            device='cuda',
        )
        wf.metadata.setdefault('id_map', {})['downloadandloadsam2model'] = downloadandloadsam2model.node.id

        wanvideocontextoptions = WanVideoContextOptions(
            _id='110',
            context_schedule='static_standard',
            context_overlap=32,
        )
        wf.metadata.setdefault('id_map', {})['wanvideocontextoptions'] = wanvideocontextoptions.node.id

        getnode = raw_call(wf, 'GetNode', '131', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '133', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '134', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        getnode_4 = raw_call(wf, 'GetNode', '137', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '138', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '140', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '141', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '143', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '145', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        getnode_10 = raw_call(wf, 'GetNode', '146', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '149', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        intconstant = INTConstant(_id='150', value=832)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='151', value=480)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        getnode_12 = raw_call(wf, 'GetNode', '155', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '156', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '158', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '162', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '163', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            _id='171',
            lora_0=MODEL_NAME_5,
            lora_1=MODEL_NAME_6,
            strength_1=1.2,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselectmulti'] = wanvideoloraselectmulti.node.id

        onnxdetectionmodelloader = OnnxDetectionModelLoader(
            _id='178',
            vitpose_model=MODEL_NAME_7,
            yolo_model=MODEL_NAME_8,
        )
        wf.metadata.setdefault('id_map', {})['onnxdetectionmodelloader'] = onnxdetectionmodelloader.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_9,
            base_precision='fp16',
            compile_args=wanvideotorchcompilesettings,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        vhs_loadvideo = VHS_LoadVideo(
            _id='63',
            force_rate=16,
            video='raw.mp4',
            videopreview={'hidden': False, 'params': {'custom_height': 544, 'custom_width': 960, 'filename': 'raw.mp4', 'force_rate': 16, 'format': 'video/mp4', 'frame_load_cap': 0, 'select_every_nth': 1, 'skip_first_frames': 0, 'type': 'input'}, 'paused': False},
            custom_height=intconstant_2,
            custom_width=intconstant,
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
            **{'choose video to upload': 'image'},
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='64',
            upscale_method='lanczos',
            keep_proportion='pad_edge_pixel',
            crop_position='top',
            divisible_by=16,
            device='cpu',
            widget_0=832,
            widget_1=480,
            width=intconstant,
            height=intconstant_2,
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            _id='70',
            clip_vision=clipvisionloader,
            image_1=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoclipvisionencode'] = wanvideoclipvisionencode.node.id

        imageconcatmulti_2 = ImageConcatMulti(
            _id='77',
            inputcount=4,
            direction='down',
            match_image_size=True,
            unused_3=None,
            image_1=getnode_3.out(0),
            image_2=getnode_4.out(0),
            image_3=getnode_6.out(0),
            image_4=getnode_9.out(0),
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti_2'] = imageconcatmulti_2.node.id

        setnode_6 = raw_call(wf, 'SetNode', '153', widget_0=WIDGET_0_8, INT=intconstant)
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id
        setnode_7 = raw_call(wf, 'SetNode', '154',
            widget_0=WIDGET_0_9,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        setnode_9 = raw_call(wf, 'SetNode', '161',
            widget_0=WIDGET_0_11,
            WANVAE=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        wanvideosetloras = WanVideoSetLoRAs(
            _id='48',
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras'] = wanvideosetloras.node.id

        wanvideoanimateembeds = raw_call(wf, 'WanVideoAnimateEmbeds', '62',
            force_offload=False,
            unused_8=False,
            widget_0=832,
            widget_1=480,
            widget_2=501,
            width=getnode_12.out(0),
            height=getnode_13.out(0),
            num_frames=getnode_14.out(0),
            bg_images=getnode.out(0),
            clip_embeds=wanvideoclipvisionencode,
            face_images=getnode_5.out(0),
            mask=getnode_8.out(0),
            pose_images=getnode_7.out(0),
            ref_images=getnode_2.out(0),
            vae=getnode_16.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoanimateembeds'] = wanvideoanimateembeds.node.id

        setnode = raw_call(wf, 'SetNode', '128',
            widget_0=WIDGET_0_2,
            IMAGE=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        setnode_4 = raw_call(wf, 'SetNode', '144',
            widget_0=WIDGET_0_6,
            IMAGE=vhs_loadvideo.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        setnode_5 = raw_call(wf, 'SetNode', '148',
            widget_0=WIDGET_0_7,
            AUDIO=vhs_loadvideo.out('AUDIO'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        setnode_8 = raw_call(wf, 'SetNode', '157',
            widget_0=WIDGET_0_10,
            INT=vhs_loadvideo.out('FRAME_COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='50',
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        getimagesizeandcount_2 = GetImageSizeAndCount(
            _id='180',
            image=setnode_4.out(0),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_2'] = getimagesizeandcount_2.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=4,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            batched_cfg='',
            image_embeds=wanvideoanimateembeds,
            model=wanvideosetblockswap,
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        poseandfacedetection = PoseAndFaceDetection(
            _id='172',
            widget_0=832,
            widget_1=480,
            width=getimagesizeandcount_2.out('WIDTH'),
            height=getimagesizeandcount_2.out('HEIGHT'),
            images=getimagesizeandcount_2.out('IMAGE'),
            model=onnxdetectionmodelloader,
            _outputs=('POSE_DATA', 'FACE_IMAGES', 'KEY_FRAME_BODY_POINTS', 'BBOXES', 'FACE_BBOXES'),
        )
        wf.metadata.setdefault('id_map', {})['poseandfacedetection'] = poseandfacedetection.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=getnode_15.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        sam2segmentation = Sam2Segmentation(
            _id='104',
            bboxes=poseandfacedetection.out('BBOXES'),
            image=getimagesizeandcount_2.out('IMAGE'),
            sam2_model=downloadandloadsam2model,
        )
        wf.metadata.setdefault('id_map', {})['sam2segmentation'] = sam2segmentation.node.id

        drawvitpose = DrawViTPose(
            _id='173',
            widget_0=832,
            widget_1=480,
            width=getimagesizeandcount_2.out('WIDTH'),
            height=getimagesizeandcount_2.out('HEIGHT'),
            pose_data=poseandfacedetection.out('POSE_DATA'),
        )
        wf.metadata.setdefault('id_map', {})['drawvitpose'] = drawvitpose.node.id

        setnode_10 = raw_call(wf, 'SetNode', '183',
            widget_0=WIDGET_0_3,
            IMAGE=poseandfacedetection.out('FACE_IMAGES'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='42',
            image=wanvideodecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        # Outputs
        vhs_videocombine_3 = VHS_VideoCombine(
            _id='174',
            frame_rate=16,
            filename_prefix='vitpose',
            format=FORMAT,
            save_output=False,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'params': {'filename': 'vitpose_00004.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\vitpose_00004.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'vitpose_00004.png'}, 'paused': False},
            images=setnode_10.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_3'] = vhs_videocombine_3.node.id

        growmaskwithblur = raw_call(wf, 'GrowMaskWithBlur', '182',
            _outputs=('MASK', 'MASK_INVERTED'),
            expand=10,
            unused_7=False,
            mask=sam2segmentation,
        )
        wf.metadata.setdefault('id_map', {})['growmaskwithblur'] = growmaskwithblur.node.id

        setnode_11 = raw_call(wf, 'SetNode', '184',
            widget_0=WIDGET_0_4,
            IMAGE=drawvitpose,
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        imageconcatmulti = ImageConcatMulti(
            _id='66',
            direction='left',
            match_image_size=True,
            unused_3=None,
            image_1=getimagesizeandcount.out('IMAGE'),
            image_2=imageconcatmulti_2,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti'] = imageconcatmulti.node.id

        blockifymask = BlockifyMask(_id='108', masks=growmaskwithblur.out('MASK'))
        wf.metadata.setdefault('id_map', {})['blockifymask'] = blockifymask.node.id
        vhs_videocombine_4 = VHS_VideoCombine(
            _id='181',
            frame_rate=16,
            filename_prefix='WanVideo2_1_T2V',
            format=FORMAT,
            save_output=False,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_1_T2V_00002.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00002.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_1_T2V_00002.png'}, 'paused': False},
            images=setnode_11.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_4'] = vhs_videocombine_4.node.id

        vhs_videocombine = VHS_VideoCombine(
            _id='30',
            frame_rate=16,
            filename_prefix='Wanimate',
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=True,
            videopreview={'hidden': False, 'params': {'filename': 'Wanimate_00002-audio.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\Wanimate_00002-audio.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'Wanimate_00002.png'}, 'paused': False},
            audio=getnode_11.out(0),
            images=imageconcatmulti,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        setnode_3 = raw_call(wf, 'SetNode', '142',
            widget_0=WIDGET_0_5,
            MASK=blockifymask,
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        drawmaskonimage = DrawMaskOnImage(
            _id='99',
            image=getnode_10.out(0),
            mask=setnode_3.out(0),
        )
        wf.metadata.setdefault('id_map', {})['drawmaskonimage'] = drawmaskonimage.node.id

        setnode_2 = raw_call(wf, 'SetNode', '130',
            widget_0=WIDGET_0,
            IMAGE=drawmaskonimage,
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        vhs_videocombine_2 = VHS_VideoCombine(
            _id='75',
            frame_rate=16,
            filename_prefix='WanVideo2_1_T2V',
            format=FORMAT,
            save_output=False,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_1_T2V_00004.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00004.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_1_T2V_00004.png'}, 'paused': False},
            images=setnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='Wanimate')

