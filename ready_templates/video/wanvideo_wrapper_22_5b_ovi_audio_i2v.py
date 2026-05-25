# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import LoadImage, PreviewAudio
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import OviMMAudioVAELoader, WanVideoBlockSwap, WanVideoDecode, WanVideoDecodeOviAudio, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEmptyMMAudioLatents, WanVideoEncode, WanVideoExtraModelSelect, WanVideoModelLoader, WanVideoOviCFG, WanVideoSLG, WanVideoSampler, WanVideoSetBlockSwap, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 157
DEFAULT_FRAMES_2 = 5
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_NEGATIVE_2 = 'robotic, muffled, echo, distorted'
DEFAULT_PROMPT = 'A tired old man is very sarcastically saying: <S>Oh great, they are making me talk now too.<E>. <AUDCAP>Clear older male voices speaking dialogue, subtle outdoor ambience.<ENDAUDCAP>'
DEFAULT_SEED = 42
EXTRA_MODEL_NAME = 'WanVideo/Ovi/Wan_2_1_Ovi_audio_model_bf16.safetensors'
GUIDE_STRENGTH = 4
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'Wan2_2_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVideo/Ovi/Wan_2_1_Ovi_video_model_bf16.safetensors'
VAE_NAME = 'mmaudio_vae_16k_fp32.safetensors'
VOCODER_NAME = 'mmaudio_vocoder_bigvgan_best_netG_fp32.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='audio_image_to_video',
    requirements={'models': ['Wan2_2_VAE_bf16.safetensors', 'umt5-xxl-enc-bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='Ovi image-to-video with audio',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideoextramodelselect = WanVideoExtraModelSelect(extra_model=EXTRA_MODEL_NAME)

    wanvideoblockswap = WanVideoBlockSwap(
        blocks_to_swap=15,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
        model_name=MODEL_NAME,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        use_disk_cache=False,
    )

    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)

    ovimmaudiovaeloader = OviMMAudioVAELoader(
        precision='fp32',
        vae=VAE_NAME,
        vocoder=VOCODER_NAME,
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideoslg = WanVideoSLG(blocks='11', start_percent=0)

    text_embeds_wan, negative_text_embeds_wan, positive_prompt_wan = WanVideoTextEncodeCached(
        model_name=MODEL_NAME,
        negative_prompt=DEFAULT_NEGATIVE_2,
    )

    # Inputs
    image, mask = LoadImage(image='oldman_upscaled.png')
    wanvideoeasycache = WanVideoEasyCache()
    wanvideoemptymmaudiolatents = WanVideoEmptyMMAudioLatents(length=DEFAULT_FRAMES)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_3,
        compile_args=wanvideotorchcompilesettings,
        extra_model=wanvideoextramodelselect,
    )

    wanvideoovicfg = WanVideoOviCFG(
        widget_0=3,
        original_text_embeds=text_embeds,
        ovi_negative_text_embeds=negative_text_embeds_wan,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        width=256,
        height=256,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        image=image,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader,
    )

    wanvideoencode = WanVideoEncode(
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=image_image,
        vae=wanvideovaeloader,
    )

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        num_frames=DEFAULT_FRAMES_2,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        extra_latents=wanvideoencode,
        height=height,
        width=width,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=1,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        rope_function='default',
        cache_args=wanvideoeasycache,
        image_embeds=wanvideoemptyembeds,
        model=wanvideosetblockswap,
        samples=wanvideoemptymmaudiolatents,
        slg_args=wanvideoslg,
        text_embeds=wanvideoovicfg,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    wanvideodecodeoviaudio = WanVideoDecodeOviAudio(
        mmaudio_vae=ovimmaudiovaeloader,
        samples=samples,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        audio=wanvideodecodeoviaudio,
        images=wanvideodecode,
    )

    previewaudio = PreviewAudio(audio=wanvideodecodeoviaudio)


    PUBLIC_INPUTS = {
        'model': InputSpec(node=text_embeds, field='model_name', default=MODEL_NAME),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED),
        'image': InputSpec(node=image, field='image', default='oldman_upscaled.png'),
        'frames': InputSpec(node=wanvideoemptymmaudiolatents, field='length', default=DEFAULT_FRAMES),
        'width': InputSpec(node=image_image, field='width', default=256),
        'height': InputSpec(node=image_image, field='height', default=256),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

