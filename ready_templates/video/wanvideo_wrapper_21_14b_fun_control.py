# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionLoader, LoadImage
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, ImageConcatMulti, ImageResizeKJ
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoControlEmbeds, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoExperimentalArgs, WanVideoImageToVideoEncode, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader, WanVideoVRAMManagement


CLIP_NAME = 'umt5_xxl_fp16.safetensors'
CLIP_NAME_2 = 'clip_vision_h.safetensors'
DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = "high quality nature video of a red fox in an autumnal forest, there's a waterfall in the background"
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_3 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 42
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\wan2.1_fun_control_1.3B_bf16.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
WIDGET_0 = 'VAE'
WIDGET_0_2 = 'ControlSignal'
WIDGET_2 = 'lanczos'
WIDGET__NAME = 'depth_anything_v2_vitl_fp16.safetensors'


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='fun_control_video',
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoControlEmbeds', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoImageToVideoEncode', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoFun control workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            model_name=public('model', default=MODEL_NAME),
        )

        wanvideomodelloader = WanVideoModelLoader(model=MODEL_NAME_2)
        wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
        wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_3)
        wanvideoblockswap = WanVideoBlockSwap(blocks_to_swap=10, use_non_blocking=True)
        wanvideovrammanagement = WanVideoVRAMManagement()
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')
        wanvideoteacache = WanVideoTeaCache(rel_l1_thresh=0.08, use_coefficients='true')

        # Inputs
        image, mask = LoadImage(
            image=public('image', default='pasted/image (758).png'),
            widget_2='',
        )

        clipvisionloader = CLIPVisionLoader(clip_name=CLIP_NAME_2)

        image_load, frame_count, audio, video_info = VHS_LoadVideo(
            video='wolf_interpolated.mp4',
        )

        downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
            widget_0=WIDGET__NAME,
        )

        reroute = raw_call('Reroute', '79')
        reroute_2 = raw_call('Reroute', '80')
        getnode = raw_call('GetNode', '84', widget_0=WIDGET_0)
        getnode_2 = raw_call('GetNode', '85', widget_0=WIDGET_0)
        getnode_3 = raw_call('GetNode', '86', widget_0=WIDGET_0)
        getnode_4 = raw_call('GetNode', '89', widget_0=WIDGET_0_2)
        wanvideoexperimentalargs = WanVideoExperimentalArgs(cfg_zero_star=True)
        setnode = raw_call('SetNode', '83', widget_0=WIDGET_0, WANVAE=wanvideovaeloader)

        wanvideotextencode = WanVideoTextEncode(
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            model_to_offload=wanvideomodelloader,
            t5=loadwanvideot5textencoder,
        )

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT_2),
            clip=cliploader,
        )

        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_3, clip=cliploader)

        image_image, width, height = ImageResizeKJ(
            widget_0=640,
            widget_1=640,
            widget_2=WIDGET_2,
            widget_3=False,
            widget_4=16,
            widget_5=0,
            widget_6=0,
            widget_7='disabled',
            image=image_load,
        )

        samples, denoised_samples = WanVideoSampler(
            steps=1,
            seed=public('seed', default=DEFAULT_SEED),
            batched_cfg='',
            cache_args=wanvideoteacache,
            experimental_args=wanvideoexperimentalargs,
            image_embeds=reroute.out(0),
            model=wanvideomodelloader,
            text_embeds=wanvideotextencode,
        )

        wanvideotextembedbridge = WanVideoTextEmbedBridge(
            negative=cliptextencode_2,
            positive=cliptextencode,
        )

        depthanything_v2 = DepthAnything_V2(
            da_model=downloadandloaddepthanythingv2model,
            images=image_image,
        )

        setnode_2 = raw_call('SetNode', '88', widget_0=WIDGET_0_2, IMAGE=depthanything_v2)
        wanvideodecode = WanVideoDecode(samples=samples, vae=getnode_3.out(0))

        image_get, width_get, height_get, count = GetImageSizeAndCount(
            image=depthanything_v2,
        )

        image_image_2, width_image, height_image = ImageResizeKJ(
            widget_0=624,
            widget_1=624,
            widget_2=WIDGET_2,
            widget_3=False,
            widget_4=16,
            widget_5=0,
            widget_6=0,
            widget_7='center',
            height=height_get,
            image=image,
            width=width_get,
        )

        wanvideoencode = WanVideoEncode(
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1,
            image=image_get,
            vae=getnode.out(0),
        )

        # Outputs
        vhs_videocombine = VHS_VideoCombine(images=setnode_2.out(0))

        imageconcatmulti = ImageConcatMulti(
            unused_3=None,
            image_1=getnode_4.out(0),
            image_2=wanvideodecode,
        )

        vhs_videocombine_2 = VHS_VideoCombine(images=imageconcatmulti)

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            ratio=0.2,
            clip_vision=clipvisionloader,
            image_1=image_image_2,
        )

        wanvideocontrolembeds = WanVideoControlEmbeds(latents=wanvideoencode)

        wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
            noise_aug_strength=0.03,
            tiled_vae=True,
            width=width_image,
            height=height_image,
            num_frames=count,
            clip_embeds=wanvideoclipvisionencode,
            control_embeds=wanvideocontrolembeds,
            start_image=image_image_2,
            vae=getnode_2.out(0),
        )

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            widget_0=256,
            widget_1=256,
            widget_2=5,
            control_embeds=wanvideocontrolembeds,
            height=height_get,
            num_frames=count,
            width=width_get,
        )

        return wf.finalize({}, output_node=vhs_videocombine, spec=OUTPUT_SPEC)

