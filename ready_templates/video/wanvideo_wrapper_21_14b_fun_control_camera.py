# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, LoadImage, PreviewImage
from vibecomfy.nodes.kjnodes import CameraPoseVisualizer, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoExperimentalArgs, WanVideoFunCameraEmbeds, WanVideoImageToVideoEncode, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'high quality video of an old man'
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_3 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 43
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\Wan2.1-Fun-V1.1-1.3B-Control-Camera.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='camera_control_video',
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoImageToVideoEncode', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='WanVideoFun camera-control workflow',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json'},
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
        wanvideoblockswap = WanVideoBlockSwap(blocks_to_swap=15, use_non_blocking=True)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')

        wanvideoteacache = WanVideoTeaCache(
            mode='e0',
            rel_l1_thresh=0.08,
            start_step=6,
            use_coefficients='true',
        )

        # Inputs
        image, mask = LoadImage(image=public('image', default='oldman_upscaled.png'))
        reroute = raw_call('Reroute', '80')

        wanvideoexperimentalargs = WanVideoExperimentalArgs(
            cfg_zero_star=True,
            use_fresca=True,
        )

        intconstant = INTConstant(value=81)

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

        image_image, width, height, mask_image = ImageResizeKJv2(
            width=public('width', default=256),
            height=public('height', default=256),
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=16,
            image=image,
        )

        ade_cameraposebasic = raw_call('ADE_CameraPoseBasic', '99',
            widget_0='Zoom Out',
            widget_1=0.1,
            widget_2=40,
            frame_length=intconstant,
        )

        samples, denoised_samples = WanVideoSampler(
            steps=1,
            seed=public('seed', default=DEFAULT_SEED),
            batched_cfg='',
            start_step='',
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

        cameraposevisualizer = CameraPoseVisualizer(
            cameractrl_poses=ade_cameraposebasic.out(0),
        )

        wanvideofuncameraembeds = WanVideoFunCameraEmbeds(
            start_percent=1,
            strength=0,
            widget_0=832,
            widget_1=480,
            widget_2=1,
            height=height,
            poses=ade_cameraposebasic.out(0),
            width=width,
        )

        wanvideodecode = WanVideoDecode(samples=samples, vae=wanvideovaeloader)

        wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
            noise_aug_strength=0.03,
            tiled_vae=True,
            width=width,
            height=height,
            num_frames=intconstant,
            control_embeds=wanvideofuncameraembeds,
            start_image=image_image,
            vae=wanvideovaeloader,
        )

        # Outputs
        previewimage = PreviewImage(images=cameraposevisualizer)

        imageconcatmulti = ImageConcatMulti(
            inputcount=3,
            direction='left',
            match_image_size=True,
            unused_3=None,
            image_1=wanvideodecode,
            image_2=image_image,
            image_3=cameraposevisualizer,
        )

        vhs_videocombine = VHS_VideoCombine(images=imageconcatmulti)

        return wf.finalize({}, output_node=previewimage, spec=OUTPUT_SPEC)

