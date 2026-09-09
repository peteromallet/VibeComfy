# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import LoadImage, PreviewAudio
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import OviMMAudioVAELoader, WanVideoBlockSwap, WanVideoDecode, WanVideoDecodeOviAudio, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEmptyMMAudioLatents, WanVideoEncode, WanVideoExtraModelSelect, WanVideoModelLoader, WanVideoOviCFG, WanVideoSLG, WanVideoSampler, WanVideoSetBlockSwap, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


AUDIO_VAE_NAME = 'mmaudio_vae_16k_fp32.safetensors'
CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_FRAMES = 121
DEFAULT_NEGATIVE = 'robotic, muffled, echo, distorted'
DEFAULT_NEGATIVE_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'A tired old man is very sarcastically saying: <S>Oh great, they are making me talk now too.<E>. <AUDCAP>Clear older male voices speaking dialogue, subtle outdoor ambience.<ENDAUDCAP>'
DEFAULT_SEED = 42
EXTRA_MODEL_NAME = 'WanVideo/Ovi/Wan_2_1_Ovi_audio_model_bf16.safetensors'
GUIDE_STRENGTH = 4
MODEL_NAME = 'WanVideo/Ovi/Wan_2_1_Ovi_video_model_bf16.safetensors'
VAE_NAME = 'Wan2_2_VAE_bf16.safetensors'
VOCODER_NAME = 'mmaudio_vocoder_bigvgan_best_netG_fp32.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='80', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='109', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='110', field='width', default=704, type='INT'),
    'height': InputSpec(node='110', field='height', default=704, type='INT'),
    'frames': InputSpec(node='125', field='length', default=157, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['Wan2_2_VAE_bf16.safetensors', 'umt5-xxl-enc-bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json', 'source_id': 'video/wanvideo_wrapper_22_5b_ovi_audio_i2v', 'upstream_source_id': 'wan22_5b_ovi_audio_i2v', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_5b_ovi_audio_i2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideoextramodelselect = WanVideoExtraModelSelect(
        _id='78',
        extra_model=EXTRA_MODEL_NAME,
    )

    wanvideoblockswap = WanVideoBlockSwap(
        _id='83',
        blocks_to_swap=15,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    text_embeds, _, _ = WanVideoTextEncodeCached(
        _id='85',
        model_name=CLIP_NAME,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE_2,
        use_disk_cache=False,
    )

    wanvideovaeloader = WanVideoVAELoader(_id='87', model_name=VAE_NAME)

    ovimmaudiovaeloader = OviMMAudioVAELoader(
        _id='89',
        precision='fp32',
        vae=AUDIO_VAE_NAME,
        vocoder=VOCODER_NAME,
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='91')
    wanvideoslg = WanVideoSLG(_id='93', blocks='11', start_percent=0)

    _, negative_text_embeds_2, _ = WanVideoTextEncodeCached(
        _id='96',
        model_name=CLIP_NAME,
        negative_prompt=DEFAULT_NEGATIVE,
    )

    # Inputs
    image, _ = LoadImage(_id='109', image='oldman_upscaled.png')
    wanvideoeasycache = WanVideoEasyCache(_id='118')
    wanvideoemptymmaudiolatents = WanVideoEmptyMMAudioLatents(_id='125', length=157)

    wanvideomodelloader = WanVideoModelLoader(
        _id='12',
        model=MODEL_NAME,
        attention_mode='sageattn',
        compile_args=wanvideotorchcompilesettings,
        extra_model=wanvideoextramodelselect,
    )

    wanvideoovicfg = WanVideoOviCFG(
        _id='94',
        original_text_embeds=text_embeds,
        ovi_negative_text_embeds=negative_text_embeds_2,
    )

    image_2, width, height, _ = ImageResizeKJv2(
        _id='110',
        width=704,
        height=704,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        image=image,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='84',
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader,
    )

    wanvideoencode = WanVideoEncode(
        _id='111',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image_2,
        vae=wanvideovaeloader,
    )

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        _id='81',
        num_frames=DEFAULT_FRAMES,
        width=width,
        height=height,
        extra_latents=wanvideoencode,
    )

    samples, _ = WanVideoSampler(
        _id='80',
        steps=50,
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
        _id='86',
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    wanvideodecodeoviaudio = WanVideoDecodeOviAudio(
        _id='90',
        mmaudio_vae=ovimmaudiovaeloader,
        samples=samples,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='88',
        frame_rate=24,
        filename_prefix='WanVideo_Ovi',
        format='video/h264-mp4',
        crf=20,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo_Ovi_00027-audio.webm', 'subfolder': '', 'type': 'temp', 'format': 'video/webm', 'frame_rate': 24, 'workflow': 'WanVideo_Ovi_00027.png', 'fullpath': '/home/kijai/AI/ComfyUI/temp/WanVideo_Ovi_00027-audio.webm'}},
        audio=wanvideodecodeoviaudio,
        images=wanvideodecode,
    )

    previewaudio = PreviewAudio(_id='108', audio=wanvideodecodeoviaudio)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo_Ovi')

