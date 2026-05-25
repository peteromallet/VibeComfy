# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionLoader, EmptyImage, LoadImage
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoClipTextEncoder, LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BLACK = 'black'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_FRAMES = 5
DEFAULT_PROMPT = 'CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角'
DEFAULT_SEED = 43
FREEMONO_TTF = 'FreeMono.ttf'
GUIDE_STRENGTH = 1.0000000000000002
LANCZOS = 'lanczos'
UP = 'up'
WHITE = 'white'

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'version': 'unknown', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoWrapper first/last-frame video',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json'},
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

    wanvideoblockswap = WanVideoBlockSwap(use_non_blocking=True)
    cliploader = CLIPLoader(clip_name='umt5_xxl_fp16.safetensors', type_='wan')

    loadwanvideocliptextencoder = LoadWanVideoClipTextEncoder(
        model_name='open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors',
    )

    # Inputs
    image, mask = LoadImage(image='pasted/image (853).png')
    clipvisionloader = CLIPVisionLoader(clip_name='clip_vision_h.safetensors')
    image_load, mask_load = LoadImage(image='pasted/image (852).png')

    wanvideoloraselect = WanVideoLoraSelect(
        lora='Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors',
        strength=1.2,
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn',
        block_swap_args=wanvideoblockswap,
        compile_args=wanvideotorchcompilesettings,
        lora=wanvideoloraselect,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)

    cliptextencode_2 = CLIPTextEncode(
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        width=256,
        height=256,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        image=image_load,
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
        image=image_image,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        width=width,
        height=height,
        image=image,
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
        image=image_image_2,
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        combine_embeds='concat',
        clip_vision=clipvisionloader,
        image_1=image_image,
        image_2=image_image_2,
    )

    imageconcatmulti = ImageConcatMulti(
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=addlabel,
        image_2=addlabel_2,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        num_frames=DEFAULT_FRAMES,
        tiled_vae=True,
        fun_or_fl2v_model=False,
        width=width_image,
        height=height_image,
        clip_embeds=wanvideoclipvisionencode,
        end_image=image_image_2,
        start_image=image_image,
        vae=wanvideovaeloader,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=1,
        cfg=GUIDE_STRENGTH,
        shift=5.000000000000001,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=wanvideodecode)
    emptyimage = EmptyImage(widget_1=512, width=8, height=height_get)

    imageconcatmulti_2 = ImageConcatMulti(
        inputcount=3,
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=image_get,
        image_2=emptyimage,
        image_3=imageconcatmulti,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(images=imageconcatmulti_2)


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='pasted/image (853).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'width': InputSpec(node=image_image, field='width', default=256, type='INT'),
        'height': InputSpec(node=image_image, field='height', default=256, type='INT'),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

