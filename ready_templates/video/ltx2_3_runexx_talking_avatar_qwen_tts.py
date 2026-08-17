# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, PreviewAudio, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2SamplingPreviewOverride, LTX2_NAG, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
FULL_TRACK = 'full_track'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
LORA_NAME = 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer/MelBandRoformer_fp16.safetensors'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'


PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node='a8d7fd9f:1928', field='switch', default=True),
    'image': InputSpec(node='444', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='1832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='1626', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json', 'source_id': 'LTX-2.3_Talking_Avatar_Qwen_TTS', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_talking_avatar_qwen_tts'},
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch / PathchSageAttentionKJ for memory-efficient attention on compatible GPUs.', 'source': 'SageAttention-ada'}],
)

# === Subgraph functions ===

def calculate_frames(
    *,
    audio,
    variables_b,
    variables_a,
    on_false,
):
    """Calculate Frames.

    Materialized from subgraph 63e8c999-0a69-4f62-af3f-8b77f0095971 in ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.
    # vibecomfy source hash: sha256:2ef41fed9231dadf96fb5ca61e4e350fff3cc114bfba0cdf2ecd0558c7845d29
    Inner nodes: Audio Duration (mtb), SimpleCalculatorKJx3, LazySwitchKJ.
    """

    audio_duration__mtb_ = raw_call('Audio Duration (mtb)', '63e8c999:1864', _outputs=('duration_ms',), audio=audio)

    _, calc_int_2, _ = SimpleCalculatorKJ(
        expression='ceil(a/1000)',
        **{'variables.a': audio_duration__mtb_.out('duration_ms')},
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': calc_int_2, 'variables.b': variables_b},
    )

    _, _, calc_bool_3 = SimpleCalculatorKJ(
        expression='a<b ',
        **{'variables.a': variables_a, 'variables.b': calc_int},
    )

    lazyswitchkj = LazySwitchKJ(switch=calc_bool_3, on_false=on_false, on_true=calc_int)

    return lazyswitchkj


def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph a8d7fd9f-52aa-447a-9766-53cb91c0ef18 in ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.
    # vibecomfy source hash: sha256:c3ac2697c91666dfd93673caf11e1a81fd3692528b555ec9e1aa02ffc8d8ec4e
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
        _id='a8d7fd9f:1928',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='444', image='17745317855d08.png')

    # Loaders
    vaeloader = VAELoader(_id='1559', vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='1561',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    dualcliploader = DualCLIPLoader(
        _id='1562',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='1567', ckpt_name=AUDIO_VAE_NAME)
    vaeloader_2 = VAELoader(_id='1569', vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(_id='1570', unet_name=UNET_NAME)
    intconstant = INTConstant(_id='1591', value=960)
    intconstant_2 = INTConstant(_id='1606', value=544)

    randomnoise = RandomNoise(
        _id='1832',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    randomnoise_2 = RandomNoise(
        _id='1842',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    manualsigmas = ManualSigmas(_id='1851', sigmas='0.85, 0.7250, 0.4219, 0.0')

    # Sampling
    ksamplerselect = KSamplerSelect(_id='1852', sampler_name='euler_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(_id='1853', sampler_name='euler_ancestral_cfg_pp')

    manualsigmas_2 = ManualSigmas(
        _id='1857',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    melbandroformermodelloader = MelBandRoFormerModelLoader(
        _id='1937',
        model=MEL_BAND_ROFORMER_NAME,
    )

    loadaudio = LoadAudio(_id='1941', audio='d1b26d5a32db420183fa17af9c699278.mp3')

    image_2, _, _, _ = ImageResizeKJv2(
        _id='445',
        upscale_method='lanczos',
        keep_proportion='crop',
        device='cpu',
        width=intconstant_2,
        height=intconstant,
        image=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='1560',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    # Conditioning
    cliptextencode_2 = CLIPTextEncode(
        _id='1626',
        text=DEFAULT_PROMPT,
        clip=dualcliploader,
    )

    solidmask = SolidMask(
        _id='1890',
        value=0,
        width=intconstant_2,
        height=intconstant,
    )

    trimaudioduration = TrimAudioDuration(_id='1939', duration=15, audio=loadaudio)

    pathchsageattentionkj = PathchSageAttentionKJ(
        _id='268',
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    ltxvpreprocess = LTXVPreprocess(_id='446', img_compression=18, image=image_2)

    resizeimagemasknode = ResizeImageMaskNode(
        _id='1630',
        resize_type='scale by multiplier',
        input=image_2,
    )

    melbandroformersampler = MelBandRoFormerSampler(
        _id='1936',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(_id='504', model=pathchsageattentionkj)
    width_2, height_2, _ = GetImageSize(_id='1631', image=resizeimagemasknode)

    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=resizeimagemasknode,
        enable=True,
        prompt="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n",
    )

    ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
        _id='1944',
        target_text='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
        x_vector_only=True,
        voice=986337553816914,
        unload_models=116899311982882,
        seed='randomize',
        reference_audio=melbandroformersampler.out(0),
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        _id='1523',
        model=ltxvchunkfeedforward,
    )

    cliptextencode = CLIPTextEncode(
        _id='1621',
        text=prompt_enhancer_result,
        clip=dualcliploader,
    )

    audionormalizelufs = raw_call('AudioNormalizeLUFS', '1916',
        target_lufs=-20,
        start_time=0,
        end_time=0,
        apply_to=FULL_TRACK,
        audio=ailab_qwen3ttsvoiceclone,
    )

    positive, negative = LTXVConditioning(
        _id='164',
        frame_rate=24.0,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    model, _ = Power_Lora_Loader_rgthree(_id='1627', model=ltx2attentiontunerpatch)

    audioenhancementnode = raw_call('AudioEnhancementNode', '1904',
        enhancement_mode='manual',
        enhancement_strength=0.7,
        harmonic_intensity=0.6,
        stereo_width=1.3,
        dynamic_enhancement=1.2,
        bass_boost=1,
        presence_boost=1,
        warmth=0.5,
        target_sample_rate='keep_original',
        enable_noise_reduction=False,
        noise_reduction_level=5,
        start_time=0,
        end_time=0,
        apply_to=FULL_TRACK,
        audio=audionormalizelufs.out(0),
    )

    ltx2samplingpreviewoverride = LTX2SamplingPreviewOverride(
        _id='1858',
        model=model,
        vae=vaeloader_2,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='1893',
        audio=audioenhancementnode.out(0),
        audio_vae=ltxvaudiovaeloader,
    )

    calculate_frames_result = calculate_frames(
        audio=audioenhancementnode.out(0),
        variables_b=24.0,
        variables_a=241,
        on_false=241,
    )

    previewaudio = PreviewAudio(_id='1943', audio=audioenhancementnode.out(0))

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='344',
        width=width_2,
        height=height_2,
        length=calculate_frames_result,
    )

    ltx2_nag = LTX2_NAG(
        _id='1844',
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='1892',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    cfgguider = CFGGuider(
        _id='1836',
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        _id='1856',
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        _id='1934',
        strength=0.7,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='350',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='1845',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='1827', av_latent=output_2)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='1826',
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='1825',
        image=image_2,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='1819',
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace,
    )

    output, _ = SamplerCustomAdvanced(
        _id='1838',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(_id='1839', av_latent=output)

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        _id='1818',
        temporal_size=4096,
        samples=video_latent_2,
        vae=vaeloader,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='1847',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_2,
    )

    _, image_pass, _, _, _ = VRAM_Debug(
        _id='1915',
        unload_all_models=True,
        image_pass=vaedecodetiled,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='1837',
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_01250-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_01250.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_01250-audio.mp4'}},
        audio=ltxvaudiovaedecode,
        images=image_pass,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

