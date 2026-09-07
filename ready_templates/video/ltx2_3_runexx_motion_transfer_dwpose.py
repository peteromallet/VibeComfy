# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.controlnet_aux import DWPreprocessor, DepthAnythingPreprocessor
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyAudio, EmptyLTXVLatentVideo, GetImageSize, ImageBlend, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SimpleMath_2, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2SamplingPreviewOverride, LTX2_NAG, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
BBOX_DETECTOR_NAME = 'yolox_l.onnx'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_PROMPT = 'low contrast, washed out, text, subtitles, logo, still image, still video, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 43
DEPTH_ANYTHING_NAME = 'depth_anything_vitl14.pth'
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
GUIDE_STRENGTH_3 = 0.71
LANCZOS = 'lanczos'
LORA_NAME = 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors'
LORA_NAME_2 = 'LTX/LTX-2/IC-Lora/ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors'
NEAREST_EXACT = 'nearest-exact'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
SCALE_BY_MULTIPLIER = 'scale by multiplier'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node='94e8f3a0:1928', field='switch', default=False),
    'ref_strength': InputSpec(node='5012', field='strength', default=0.7),
    'image': InputSpec(node='2004', field='image', default='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='4832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'negative_prompt': InputSpec(node='2612', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'LTX/LTX-2/IC-Lora/ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors', 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'depth_anything_vitl14.pth', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json', 'source_id': 'video/ltx2_3_runexx_motion_transfer_dwpose', 'upstream_source_id': 'LTX-2.3_Motion_Transfer_DWPose', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_motion_transfer_dwpose'},
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch / PathchSageAttentionKJ for memory-efficient attention on compatible GPUs.', 'source': 'SageAttention-ada'}],
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 94e8f3a0-557f-4580-93a0-f762c7b0d076 in ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json.
    # vibecomfy source hash: sha256:9b87e1609cd7c39143350d5d1b01d46d32893ae6cff239a98409ee3ed824096e
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='94e8f3a0:1928',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(
        _id='2004',
        image='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg',
    )

    # Sampling
    ksamplerselect = KSamplerSelect(_id='4831', sampler_name='euler_ancestral_cfg_pp')

    randomnoise = RandomNoise(
        _id='4832',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    manualsigmas = ManualSigmas(
        _id='5025',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    randomnoise_2 = RandomNoise(
        _id='5068',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    ksamplerselect_2 = KSamplerSelect(_id='5070', sampler_name='euler_cfg_pp')
    manualsigmas_2 = ManualSigmas(_id='5071', sigmas='0.85, 0.7250, 0.4219, 0.0')

    # Loaders
    vaeloader = VAELoader(_id='5125', vae_name=VIDEO_VAE_NAME)

    dualcliploader = DualCLIPLoader(
        _id='5126',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type='ltxv',
        device='default',
    )

    vaeloaderkj = VAELoaderKJ(
        _id='5127',
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    vaeloader_2 = VAELoader(_id='5129', vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(_id='5130', unet_name=UNET_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='5132',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    intconstant = INTConstant(_id='5205', value=10)
    intconstant_2 = INTConstant(_id='5206', value=736)
    intconstant_3 = INTConstant(_id='5207', value=1280)

    _, calc_int_2, _ = SimpleCalculatorKJ(
        _id='5247',
        expression='a',
        **{'variables.a': 24.0},
    )

    loadaudio = LoadAudio(_id='5263', audio='(Verse).mp3')

    # Conditioning
    cliptextencode_2 = CLIPTextEncode(
        _id='2612',
        text=DEFAULT_PROMPT,
        clip=dualcliploader,
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        _id='5035',
        resize_type='scale longer dimension',
        scale_method=LANCZOS,
        input=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='5131',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='5202',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.b': 24.0, 'variables.a': intconstant},
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='3336',
        img_compression=18,
        image=resizeimagemasknode_2,
    )

    model, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        _id='5011',
        lora_name=LORA_NAME_2,
        strength_model=GUIDE_STRENGTH_3,
        model=loraloadermodelonly,
    )

    image_2, _, audio, _ = VHS_LoadVideoFFmpeg(
        _id='5192',
        force_rate=24.0,
        video='m2-res_1890p.mp4',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'm2-res_1890p.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'start_time': 0}},
        frame_load_cap=calc_int,
    )

    resizeimagemasknode_4 = ResizeImageMaskNode(
        _id='5241',
        resize_type=SCALE_BY_MULTIPLIER,
        input=resizeimagemasknode_2,
    )

    math_int, _ = SimpleMath_2(_id='5034', value='a*32', a=latent_downscale_factor)

    image_3, _, _, _ = ImageResizeKJv2(
        _id='5211',
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        device=CPU,
        width=intconstant_2,
        height=intconstant_3,
        image=image_2,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        _id='5231',
        sage_attention='auto',
        model=model,
    )

    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=resizeimagemasknode_4,
        enable=False,
        prompt='highly detailed, monochrime colors. Make this image come alive with fluid motion. \n\nA make boxer. \n\nHe is dancing in sync to the music ',
    )

    cliptextencode = CLIPTextEncode(
        _id='2483',
        text=prompt_enhancer_result,
        clip=dualcliploader,
    )

    resizeimagemasknode_3 = ResizeImageMaskNode(
        _id='5214',
        resize_type=SCALE_BY_MULTIPLIER,
        input=image_3,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(_id='5232', model=pathchsageattentionkj)

    positive, negative = LTXVConditioning(
        _id='1241',
        frame_rate=24.0,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='5026',
        resize_type='scale shorter dimension',
        scale_method=LANCZOS,
        input=resizeimagemasknode_3,
    )

    width_3, height_3, _ = GetImageSize(_id='5219', image=resizeimagemasknode_3)

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        _id='5233',
        model=ltxvchunkfeedforward,
    )

    dwpreprocessor = DWPreprocessor(
        _id='4986',
        detect_hand='enable',
        detect_body='enable',
        detect_face='enable',
        resolution=576,
        bbox_detector=BBOX_DETECTOR_NAME,
        pose_estimator=POSE_ESTIMATOR_NAME,
        scale_stick_for_xinsr_cn='disable',
        image=resizeimagemasknode,
    )

    depthanythingpreprocessor = DepthAnythingPreprocessor(
        _id='5114',
        ckpt_name=DEPTH_ANYTHING_NAME,
        image=resizeimagemasknode,
    )

    model_2, _ = Power_Lora_Loader_rgthree(_id='5275', model=ltx2attentiontunerpatch)

    imageblend = ImageBlend(
        _id='5115',
        blend_mode='multiply',
        image1=dwpreprocessor,
        image2=depthanythingpreprocessor.out(0),
    )

    ltx2samplingpreviewoverride = LTX2SamplingPreviewOverride(
        _id='5187',
        model=model_2,
        vae=vaeloader_2,
    )

    ltx2_nag = LTX2_NAG(
        _id='5251',
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    comfyswitchnode_3 = ComfySwitchNode(
        _id='5272',
        switch=False,
        on_false=dwpreprocessor,
        on_true=imageblend,
    )

    cfgguider_2 = CFGGuider(
        _id='5069',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    image_4, _, _, _ = ImageResizeKJv2(
        _id='5221',
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        device=CPU,
        width=width_3,
        height=height_3,
        divisible_by=math_int,
        image=comfyswitchnode_3,
    )

    width, height, batch_size = GetImageSize(_id='5029', image=image_4)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='5120',
        frame_rate=24,
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'AnimateDiff_00011.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'AnimateDiff_00011.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_17ddc38e\\AnimateDiff_00011.mp4'}},
        images=image_4,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='3059',
        width=width,
        height=height,
        length=batch_size,
    )

    solidmask = SolidMask(
        _id='5080',
        value=0,
        width=width,
        height=height,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        _id='5243',
        frames_number=batch_size,
        frame_rate=calc_int_2,
        audio_vae=vaeloaderkj,
    )

    calc_float_3, _, _ = SimpleCalculatorKJ(
        _id='5284',
        expression='a / b ',
        **{'variables.b': 24.0, 'variables.a': batch_size},
    )

    calc_float_4, _, _ = SimpleCalculatorKJ(
        _id='5290',
        expression='a / b',
        **{'variables.b': 24.0, 'variables.a': batch_size},
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        _id='3159',
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    trimaudioduration = TrimAudioDuration(
        _id='5283',
        duration=calc_float_3,
        audio=loadaudio,
    )

    emptyaudio = EmptyAudio(_id='5289', duration=calc_float_4)

    positive_2, negative_2, latent = LTXAddVideoICLoRAGuide(
        _id='5012',
        strength=0.7,
        crop=1,
        use_tiled_encode='disabled',
        image=image_4,
        latent=ltxvimgtovideoconditiononly,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vaeloader,
    )

    comfyswitchnode_4 = ComfySwitchNode(
        _id='5273',
        switch=True,
        on_false=emptyaudio,
        on_true=audio,
    )

    cfgguider = CFGGuider(
        _id='4828',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative_2,
        positive=positive_2,
    )

    comfyswitchnode_5 = ComfySwitchNode(
        _id='5274',
        switch=False,
        on_false=comfyswitchnode_4,
        on_true=trimaudioduration,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='5079',
        audio=comfyswitchnode_5,
        audio_vae=vaeloaderkj,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='5081',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    comfyswitchnode = ComfySwitchNode(
        _id='5256',
        switch=True,
        on_false=ltxvemptylatentaudio,
        on_true=setlatentnoisemask,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='4528',
        audio_latent=comfyswitchnode,
        video_latent=latent,
    )

    output, _ = SamplerCustomAdvanced(
        _id='4829',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='4845', av_latent=output)

    _, _, latent_2 = LTXVCropGuides(
        _id='5013',
        latent=video_latent,
        negative=negative_2,
        positive=positive_2,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='5065',
        samples=latent_2,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='5067',
        strength=0.7,
        image=resizeimagemasknode_2,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='5072',
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='5073',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(
        _id='5074',
        av_latent=output_2,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='5076',
        audio_vae=vaeloaderkj,
        samples=audio_latent_2,
    )

    _, _, latent_3 = LTXVCropGuides(
        _id='5082',
        latent=video_latent_2,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        _id='5075',
        tile_size=544,
        temporal_size=4096,
        temporal_overlap=4,
        samples=latent_3,
        vae=vaeloader,
    )

    comfyswitchnode_2 = ComfySwitchNode(
        _id='5264',
        switch=True,
        on_false=ltxvaudiovaedecode,
        on_true=comfyswitchnode_5,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        _id='5208',
        frame_rate=24.0,
        filename_prefix='LTX',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX_00013-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX_00013.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_17ddc38e\\LTX_00013-audio.mp4'}},
        audio=comfyswitchnode_2,
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='AnimateDiff')

