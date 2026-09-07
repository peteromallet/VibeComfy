# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import AudioEncoderEncode, AudioEncoderLoader, LoadImage
from vibecomfy.nodes.gimm_vfi import DownloadAndLoadGIMMVFIModel, GIMMVFI_interpolate
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, ImageResizeKJv2
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudio, VHS_SelectEveryNthImage, VHS_SplitImages, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness, WanVideoAddS2VEmbeds, WanVideoBlockSwap, WanVideoContextOptions, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


AUDIO_ENCODER_NAME = 'wav2vec_xlsr_53_english_fp32.safetensors'
CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_FRAMES = 201
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'a woman is singing passionately'
DEFAULT_SEED = 45
GUIDE_STRENGTH = 1
LORA__NAME = 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoFormer/MelBandRoformer_fp16.safetensors'
MODEL_NAME = 'WanVideo/S2V/Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
WIDGET__NAME = 'gimmvfi_r_arb_lpips_fp32.safetensors'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='73', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='74', field='width', default=960, type='INT'),
    'height': InputSpec(node='74', field='height', default=640, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json', 'source_id': 'video/wanvideo_wrapper_22_s2v_context_window', 'upstream_source_id': 'wan22_s2v_context_window', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_s2v_context_window'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)

    wanvideoblockswap = WanVideoBlockSwap(
        _id='39',
        blocks_to_swap=25,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        _id='60',
        lora_0=LORA__NAME,
        strength_0=1.5,
        merge_loras=False,
    )

    audioencoderloader = AudioEncoderLoader(
        _id='65',
        audio_encoder_name=AUDIO_ENCODER_NAME,
    )

    text_embeds, _, _ = WanVideoTextEncodeCached(
        _id='67',
        model_name=CLIP_NAME,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
    )

    # Inputs
    image_2, _ = LoadImage(_id='73', image='2b.jpg')

    melbandroformermodelloader = MelBandRoFormerModelLoader(
        _id='81',
        model=MEL_BAND_ROFORMER_NAME,
    )

    wanvideocontextoptions = WanVideoContextOptions(
        _id='83',
        context_schedule='uniform_standard',
    )

    audio, _ = VHS_LoadAudio(_id='94', audio_file='input/weightoftheworld2.mp4')

    downloadandloadgimmvfimodel = DownloadAndLoadGIMMVFIModel(
        _id='95',
        widget_0=WIDGET__NAME,
        widget_1='fp16',
        widget_2=False,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='22',
        model=MODEL_NAME,
        base_precision='fp16_fast',
        quantization='fp8_e4m3fn_scaled',
        attention_mode='sageattn',
        compile_args=wanvideotorchcompilesettings,
    )

    image_3, width_2, height_2, _ = ImageResizeKJv2(
        _id='74',
        width=960,
        height=640,
        upscale_method='lanczos',
        keep_proportion='crop',
        device='cpu',
        image=image_2,
    )

    melbandroformersampler = MelBandRoFormerSampler(
        _id='82',
        audio=audio,
        model=melbandroformermodelloader.out(0),
    )

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        _id='37',
        num_frames=DEFAULT_FRAMES,
        width=width_2,
        height=height_2,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        _id='58',
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader,
    )

    wanvideoencode = WanVideoEncode(
        _id='72',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image_3,
        vae=wanvideovaeloader,
    )

    normalizeaudioloudness = NormalizeAudioLoudness(
        _id='98',
        audio=melbandroformersampler.out(0),
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='56',
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    audioencoderencode = AudioEncoderEncode(
        _id='64',
        audio=normalizeaudioloudness,
        audio_encoder=audioencoderloader,
    )

    image_embeds, _ = WanVideoAddS2VEmbeds(
        _id='101',
        audio_scale=0,
        frame_window_size=201,
        pose_end_percent=False,
        pose_start_percent=1,
        widget_1=1,
        audio_encoder_output=audioencoderencode,
        embeds=wanvideoemptyembeds,
        ref_latent=wanvideoencode,
    )

    samples, _ = WanVideoSampler(
        _id='27',
        steps=4,
        cfg=GUIDE_STRENGTH,
        shift=4,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        context_options=wanvideocontextoptions,
        image_embeds=image_embeds,
        model=wanvideosetblockswap,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        _id='28',
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image, _, _, _ = GetImageSizeAndCount(_id='70', image=wanvideodecode)
    _, _, image_b, _ = VHS_SplitImages(_id='80', split_index=3, images=image)

    gimmvfi_interpolate = GIMMVFI_interpolate(
        _id='96',
        widget_0=1,
        widget_1=3,
        widget_2=0,
        widget_3='fixed',
        widget_4=False,
        gimmvfi_model=downloadandloadgimmvfimodel.out(0),
        images=image_b,
    )

    # Outputs
    vhs_videocombine_2 = VHS_VideoCombine(
        _id='97',
        frame_rate=16,
        filename_prefix='WanVideo2_2_S2V',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_2_S2V_00015-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_2_S2V_00015.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_S2V_00015-audio.mp4'}},
        audio=audio,
        images=image_b,
    )

    image_4, _ = VHS_SelectEveryNthImage(
        _id='102',
        select_every_nth=2,
        images=gimmvfi_interpolate.out(0),
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=24,
        filename_prefix='WanVideo2_2_S2V',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_2_S2V_00013-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 32, 'workflow': 'WanVideo2_2_S2V_00013.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_S2V_00013-audio.mp4'}},
        audio=audio,
        images=image_4,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_2_S2V')

