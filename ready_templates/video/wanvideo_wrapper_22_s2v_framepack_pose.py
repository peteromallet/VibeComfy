# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.controlnet_aux import DWPreprocessor
from vibecomfy.nodes.core import AudioEncoderEncode, AudioEncoderLoader, GetImageRangeFromBatch, LoadImage
from vibecomfy.nodes.kjnodes import ColorMatch, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2, LazySwitchKJ
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness, WanVideoAddS2VEmbeds, WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


AUDIO_ENCODER_NAME = 'wav2vec_xlsr_53_english_fp32.safetensors'
BBOX_DETECTOR_NAME = 'yolox_l.torchscript.pt'
BILINEAR = 'bilinear'
CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_FRAMES = 501
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = '3D animated scene of a young woman singing melancholically'
DEFAULT_SEED = 45
GPU = 'gpu'
GUIDE_STRENGTH = 1
IMAGE = 'image'
LORA__NAME = 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoFormer/MelBandRoformer_fp16.safetensors'
MODEL_NAME = 'WanVideo/S2V/Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
WAN = 'Wan'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='73', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='111', field='width', default=640, type='INT'),
    'height': InputSpec(node='111', field='height', default=640, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json', 'source_id': 'video/wanvideo_wrapper_22_s2v_framepack_pose', 'upstream_source_id': 'wan22_s2v_framepack_pose', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_s2v_framepack_pose'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)

    wanvideoblockswap = WanVideoBlockSwap(
        _id='39',
        blocks_to_swap=32,
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        _id='60',
        lora_0=LORA__NAME,
        strength_0=1.2,
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

    intconstant = INTConstant(_id='131', value=640)
    intconstant_2 = INTConstant(_id='132', value=640)

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
        upscale_method='lanczos',
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        width=intconstant,
        height=intconstant_2,
        image=image_2,
    )

    _, _, audio, _ = VHS_LoadVideo(
        _id='106',
        video='weightoftheworld2.mp4',
        force_rate=16,
        frame_load_cap=501,
        format=WAN,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'weightoftheworld2.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 16, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 501, 'skip_first_frames': 0, 'select_every_nth': 1}},
        custom_width=intconstant,
        custom_height=intconstant_2,
        **{'choose video to upload': IMAGE},
    )

    image_7, _, _, _ = VHS_LoadVideo(
        _id='116',
        video='weight-world-bones_00003-audio.mp4',
        force_rate=16,
        frame_load_cap=501,
        format=WAN,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'weight-world-bones_00003-audio.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 16, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 501, 'skip_first_frames': 0, 'select_every_nth': 1}},
        custom_width=intconstant,
        custom_height=intconstant_2,
        **{'choose video to upload': IMAGE},
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

    melbandroformersampler = MelBandRoFormerSampler(
        _id='82',
        audio=audio,
        model=melbandroformermodelloader.out(0),
    )

    image_5, _, _, _ = ImageResizeKJv2(
        _id='110',
        upscale_method=BILINEAR,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        width=intconstant,
        height=intconstant_2,
        image=image_7,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='56',
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    normalizeaudioloudness = NormalizeAudioLoudness(
        _id='98',
        audio=melbandroformersampler.out(0),
    )

    dwpreprocessor = DWPreprocessor(
        _id='107',
        detect_hand='disable',
        detect_body='disable',
        detect_face='enable',
        resolution=640,
        bbox_detector=BBOX_DETECTOR_NAME,
        pose_estimator=POSE_ESTIMATOR_NAME,
        image=image_5,
    )

    audioencoderencode = AudioEncoderEncode(
        _id='64',
        audio=normalizeaudioloudness,
        audio_encoder=audioencoderloader,
    )

    image_6, _, _, _ = ImageResizeKJv2(
        _id='111',
        width=640,
        height=640,
        upscale_method=BILINEAR,
        keep_proportion='stretch',
        divisible_by=16,
        device=GPU,
        image=dwpreprocessor,
    )

    wanvideoencode_2 = WanVideoEncode(
        _id='109',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=0.5,
        image=image_6,
        vae=wanvideovaeloader,
    )

    image_embeds, _ = WanVideoAddS2VEmbeds(
        _id='117',
        audio_scale=0,
        frame_window_size=1,
        pose_start_percent=1,
        audio_encoder_output=audioencoderencode,
        embeds=wanvideoemptyembeds,
        pose_latent=wanvideoencode_2,
        ref_latent=wanvideoencode,
        vae=wanvideovaeloader,
    )

    samples, _ = WanVideoSampler(
        _id='27',
        steps=4,
        cfg=GUIDE_STRENGTH,
        shift=4,
        seed=DEFAULT_SEED,
        scheduler='lcm',
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

    image_8, _ = GetImageRangeFromBatch(
        _id='143',
        num_frames=DEFAULT_FRAMES,
        images=image,
    )

    colormatch = ColorMatch(
        _id='105',
        widget_0='mkl',
        widget_1=1,
        widget_2=True,
        image_ref=image_3,
        image_target=image_8,
    )

    imageconcatmulti = ImageConcatMulti(
        _id='112',
        unused_3=None,
        image_1=image_6,
        image_2=colormatch,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='127',
        switch=True,
        on_false=colormatch,
        on_true=imageconcatmulti,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='97',
        frame_rate=16,
        filename_prefix='WanVideo2_2_S2V',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_2_S2V_00014-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_2_S2V_00014.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_S2V_00014-audio.mp4'}},
        audio=audio,
        images=lazyswitchkj,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_2_S2V')

