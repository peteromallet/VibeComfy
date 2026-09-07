# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import AudioConcat, BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAEEncode, VAELoader
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageBatchExtendWithOverlap, ImageBatchMulti, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2SamplingPreviewOverride, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine, VHS_VideoInfo
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_FRAMES_2 = 4096
DEFAULT_PROMPT = ' distorted sound, saturated sound, loud sound'
DEFAULT_PROMPT_2 = 'text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 432
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
LORA_NAME = 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'enable_promptenhance': InputSpec(node='6002fb3c:593', field='switch', default=True),
    'seed': InputSpec(node='115', field='noise_seed', default=DEFAULT_SEED_2, type='INT'),
    'prompt': InputSpec(node='110', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='626', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json', 'source_id': 'video/ltx2_3_runexx_video_to_video_extend', 'upstream_source_id': 'LTX-2.3_V2V_Extend_Any_Video', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_video_to_video_extend'},
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch / PathchSageAttentionKJ for memory-efficient attention on compatible GPUs.', 'source': 'SageAttention-ada'}],
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    prompt: str,
    enabled,
):
    """PROMPT ENHANCER - single-image variant.

    Materialized from subgraph 6002fb3c-ab34-4ad8-894e-fccaa60fd8c9 in ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json.
    # vibecomfy source hash: sha256:fb8fc782ba4314ba2a624cfd103b8bc2d82bd239ceae259d6a07016ccad0d45b
    Inner nodes: StringConcatenate, LazySwitchKJ, TextGenerateLTX2Prompt.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='6002fb3c:593',
        switch=enabled,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    randomnoise = RandomNoise(
        _id='115',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    # Sampling
    ksamplerselect = KSamplerSelect(_id='137', sampler_name='euler_ancestral')
    intconstant = INTConstant(_id='211', value=10)

    randomnoise_2 = RandomNoise(
        _id='243',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    ksamplerselect_2 = KSamplerSelect(_id='254', sampler_name='euler')
    intconstant_2 = INTConstant(_id='305', value=3)

    image_2, _, audio, video_info = VHS_LoadVideo(
        _id='319',
        video='joker_therapy.mp4',
        force_rate=24.0,
        format='LTXV',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'joker_therapy.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 24, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
    )

    # Loaders
    vaeloader = VAELoader(_id='463', vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='465',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    dualcliploader = DualCLIPLoader(
        _id='466',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type='ltxv',
        device='default',
    )

    vaeloaderkj = VAELoaderKJ(
        _id='471',
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    vaeloader_2 = VAELoader(_id='473', vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(_id='474', unet_name=UNET_NAME)
    manualsigmas = ManualSigmas(_id='479', sigmas='0.85, 0.7250, 0.4219, 0.0')
    intconstant_3 = INTConstant(_id='497', value=832)

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='110',
        text=DEFAULT_PROMPT_2,
        clip=dualcliploader,
    )

    _, _, _, _, _, loaded_fps_, _, loaded_duration_, _, _ = VHS_VideoInfo(
        _id='382',
        video_info=video_info,
    )

    normalizeaudioloudness = NormalizeAudioLoudness(_id='443', lufs=-16, audio=audio)

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='464',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    _, _, _, _, _, _, _, _, loaded_width__2, loaded_height__2 = VHS_VideoInfo(
        _id='492',
        video_info=video_info,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        _id='505',
        longer_edge=intconstant_3,
        images=image_2,
    )

    _, calc_int_5, _ = SimpleCalculatorKJ(
        _id='605',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.b': 24.0, 'variables.a': intconstant_2},
    )

    cliptextencode_3 = CLIPTextEncode(
        _id='626',
        text=DEFAULT_PROMPT,
        clip=dualcliploader,
    )

    calc_float_2, _, _ = SimpleCalculatorKJ(
        _id='384',
        expression='a / b',
        **{'variables.a': calc_int_5, 'variables.b': loaded_fps_},
    )

    _, _, calc_bool_4 = SimpleCalculatorKJ(
        _id='500',
        expression='(a > c) or (b > c) ',
        **{'variables.a': loaded_width__2, 'variables.b': loaded_height__2, 'variables.c': intconstant_3},
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        _id='520',
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    calc_float, _, _ = SimpleCalculatorKJ(
        _id='357',
        **{'variables.a': intconstant, 'variables.b': calc_float_2},
    )

    calc_float_3, _, _ = SimpleCalculatorKJ(
        _id='386',
        expression='a - b',
        **{'variables.a': loaded_duration_, 'variables.b': calc_float_2},
    )

    lazyswitchkj = LazySwitchKJ(
        _id='504',
        switch=calc_bool_4,
        on_false=image_2,
        on_true=resizeimagesbylongeredge_2,
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        _id='521',
        model=pathchsageattentionkj,
    )

    trimaudioduration = TrimAudioDuration(
        _id='377',
        start_index=calc_float_3,
        duration=calc_float_2,
        audio=normalizeaudioloudness,
    )

    image_5, width, height, _ = GetImageSizeAndCount(_id='506', image=lazyswitchkj)

    ltxvchunkfeedforward = LTXVChunkFeedForward(
        _id='522',
        model=ltx2memoryefficientsageattentionpatch,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='179',
        audio=trimaudioduration,
        audio_vae=vaeloaderkj,
    )

    image_6, _, _, _ = ImageResizeKJv2(
        _id='512',
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=64,
        device='cpu',
        width=width,
        height=height,
        image=image_5,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        _id='523',
        model=ltxvchunkfeedforward,
    )

    ltx2samplingpreviewoverride = LTX2SamplingPreviewOverride(
        _id='368',
        model=ltx2attentiontunerpatch,
        vae=vaeloader_2,
    )

    image_3, _ = GetImageRangeFromBatch(
        _id='379',
        start_index=-1,
        num_frames=calc_int_5,
        images=image_6,
    )

    image_4, _ = GetImageRangeFromBatch(_id='440', images=image_6)

    resizeimagemasknode = ResizeImageMaskNode(
        _id='436',
        resize_type='scale by multiplier',
        input=image_3,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='495',
        longer_edge=1536,
        images=image_4,
    )

    modelsamplingsd3 = ModelSamplingSD3(
        _id='526',
        shift=13,
        model=ltx2samplingpreviewoverride,
    )

    ltx2_nag = LTX2_NAG(
        _id='563',
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=cliptextencode_3,
        nag_cond_video=cliptextencode,
    )

    image_8, _ = GetImageRangeFromBatch(_id='566', images=image_3)

    basicscheduler = BasicScheduler(
        _id='164',
        scheduler='linear_quadratic',
        steps=8,
        model=modelsamplingsd3,
    )

    image_7, _ = GetImageRangeFromBatch(
        _id='556',
        start_index=-1,
        images=resizeimagemasknode,
    )

    vaeencode_2 = VAEEncode(_id='565', pixels=resizeimagemasknode, vae=vaeloader)

    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=resizeimagesbylongeredge,
        prompt='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n',
        enabled=True,
    )

    video_latent_2, audio_latent_2 = LTXVAudioVideoMask(
        _id='178',
        video_fps=24.0,
        max_length='pad',
        video_start_time=calc_float_2,
        video_end_time=calc_float,
        audio_start_time=calc_float_2,
        audio_end_time=calc_float,
        audio_latent=ltxvaudiovaeencode,
        video_latent=vaeencode_2,
    )

    vaeencode = VAEEncode(_id='546', pixels=image_7, vae=vaeloader)

    cliptextencode_2 = CLIPTextEncode(
        _id='592',
        text=prompt_enhancer_result,
        clip=dualcliploader,
    )

    positive_2, negative_2, latent = LTXVAddLatentGuide(
        _id='545',
        latent_idx=-1,
        guiding_latent=vaeencode,
        latent=video_latent_2,
        negative=cliptextencode,
        positive=cliptextencode_2,
        vae=vaeloader,
    )

    positive, negative = LTXVConditioning(
        _id='107',
        frame_rate=24.0,
        negative=negative_2,
        positive=positive_2,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='109',
        audio_latent=audio_latent_2,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        _id='129',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    output, _ = SamplerCustomAdvanced(
        _id='113',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=basicscheduler,
    )

    video_latent_3, audio_latent_3 = LTXVSeparateAVLatent(_id='250', av_latent=output)

    positive_3, negative_3, latent_2 = LTXVCropGuides(
        _id='549',
        latent=video_latent_3,
        negative=negative,
        positive=positive,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='245',
        samples=latent_2,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    cfgguider_2 = CFGGuider(
        _id='256',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative_3,
        positive=positive_3,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='438',
        image=image_8,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='251',
        audio_latent=audio_latent_3,
        video_latent=ltxvimgtovideoinplace,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='258',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='125', av_latent=output_2)

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='425',
        audio_vae=vaeloaderkj,
        samples=audio_latent,
    )

    _, _, latent_3 = LTXVCropGuides(
        _id='569',
        latent=video_latent,
        negative=negative,
        positive=positive,
    )

    trimaudioduration_2 = TrimAudioDuration(
        _id='394',
        duration=2048,
        start_index=calc_float_2,
        audio=ltxvaudiovaedecode,
    )

    # Decode
    vaedecode = VAEDecode(_id='527', samples=latent_3, vae=vaeloader)

    image, _ = GetImageRangeFromBatch(
        _id='306',
        num_frames=DEFAULT_FRAMES_2,
        start_index=calc_int_5,
        images=vaedecode,
    )

    audioconcat = AudioConcat(
        _id='393',
        audio1=normalizeaudioloudness,
        audio2=trimaudioduration_2,
    )

    _, _, extended_images = ImageBatchExtendWithOverlap(
        _id='536',
        overlap_mode='perceptual_crossfade',
        overlap=calc_int_5,
        new_images=vaedecode,
        source_images=image_6,
    )

    imagebatchmulti = ImageBatchMulti(
        _id='403',
        widget_1=None,
        image_1=image_6,
        image_2=image,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='578',
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': True, 'params': {'filename': 'LTX-2_00019-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00019.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_0315e009\\LTX-2_00019-audio.mp4'}},
        audio=audioconcat,
        images=extended_images,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        _id='627',
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': True, 'params': {'filename': 'LTX-2_00020-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00020.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_0315e009\\LTX-2_00020-audio.mp4'}},
        audio=audioconcat,
        images=imagebatchmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

