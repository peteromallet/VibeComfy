# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAELoader
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2SamplingPreviewOverride, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, LazySwitchKJ, LoadVideosFromFolder, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ, VRAM_Debug
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
DEFAULT_SEED_3 = 1030
DEFAULT_SEED_4 = 1021
DEFAULT_SEED_5 = 1040
DEFAULT_SEED_6 = 1050
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
LORA_NAME = 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer/MelBandRoformer_fp16.safetensors'
MYNEWVIDEO = 'mynewvideo'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VALUE = '\\'
VIDEO_H264_MP4 = 'video/h264-mp4'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'image_strength': InputSpec(node='2183', field='strength', default=0.7),
    'window_sec_02': InputSpec(node='c4106aee:2324', field='variables.a', default=10.0),
    'enhance_prompt': InputSpec(node='3bd4eeb9:1928', field='switch', default=False),
    'window_sec_03': InputSpec(node='17238add:5041', field='variables.a', default=18.0),
    'window_sec_04': InputSpec(node='a3fb563d:5116', field='variables.a', default=15.0),
    'window_sec_05': InputSpec(node='4acc9924:5191', field='variables.a', default=10.0),
    'image': InputSpec(node='444', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='2169', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='1626', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json', 'source_id': 'LTX-2.3_Music_Video_Creator_Low_RAM', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_music_video_low_ram'},
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch / PathchSageAttentionKJ for memory-efficient attention on compatible GPUs.', 'source': 'SageAttention-ada'}],
)

# === Subgraph functions ===

def prompt_enhancer_3bd4eeb9(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:2d0dc3ed6d0c2a03de0305f15253f33dd30611c205abd2e7e3c0c63e010bf8b3
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='3bd4eeb9:1928',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 2413a8aa-1f77-466f-8508-ed07fa6ac302 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:19a6af25c0629d69f9a8f32abaaca0da5690f4b1d5f343983d6aaa3665559463
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video_c4106aee(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    sampler,
    sigmas,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph c4106aee-ad7a-4925-972b-6f5b3d34db6e in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:cbf37f5017a5530871597dcd4b5d008c9ea29dde34de0757fec85749b6b65546
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SamplerCustomAdvancedx2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 2413a8aa-1f77-466f-8508-ed07fa6ac302, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2.
    """

    comfy_float, _, _ = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    solidmask = SolidMask(value=0)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='c4106aee:2324',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=ref_image,
    )

    trimaudioduration = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    prompt_enhancer_result = prompt_enhancer(
        clip=['-10', 19],
        image=resizeimagemasknode,
        enable=['-10', 20],
        prompt=['-10', 1],
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=calc_int,
    )

    trimaudioduration_2 = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    positive = CLIPTextEncode(text=prompt_enhancer_result, clip=clip)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_2,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_2,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_2, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(av_latent=output_2)
    vaedecode = VAEDecode(samples=video_latent, vae=vae_2)
    _, image_pass, _, _, _ = VRAM_Debug(image_pass=vaedecode)
    _, _, _, count = GetImageSizeAndCount(image=image_pass)

    _, calc_int_2, _ = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int_2, vaedecode, trimaudioduration_2


def total_duration(
    *,
    variables_a,
    variables_b,
    variables_c,
    variables_d,
    variables_e,
):
    """Total duration.

    Materialized from subgraph 5e410bb1-405a-4d3d-808b-8f5f29426943 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:499d1097b28fe35bbf263370c1665c25ad008f551cb2fc33f04b8e0c5df2c383
    Inner nodes: SimpleCalculatorKJ.
    """

    calc_float, _, _ = SimpleCalculatorKJ(
        expression='a + b + c + d + e + 2\n',
        **{'variables.a': variables_a, 'variables.b': variables_b, 'variables.c': variables_c, 'variables.d': variables_d, 'variables.e': variables_e},
    )

    return calc_float


def prompt_enhancer_97b9884d(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 97b9884d-4a32-4b0d-ad19-be662c1c2002 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:36dbf4b3119343559cc3c2b629aed447d88526100f83b417258078b290ff28aa
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler,
    sigmas,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 17238add-9973-482f-8fa3-248d4ed29886 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:28643b6c64068643a90cd88b40ab7b216aa3728cbc287a2d0c67a24484f18244
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 97b9884d-4a32-4b0d-ad19-be662c1c2002, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(value=0)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    comfy_float, _, _ = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    _, calc_int_2, _ = SimpleCalculatorKJ(
        _id='17238add:5041',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=calc_int_2,
    )

    trimaudioduration = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    prompt_enhancer_97b9884d_result = prompt_enhancer_97b9884d(
        clip=['-10', 17],
        image=resizeimagemasknode,
        enable=['-10', 18],
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    positive = CLIPTextEncode(text=prompt_enhancer_97b9884d_result, clip=clip)

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_2, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_2, _ = LTXVSeparateAVLatent(av_latent=output_2)
    vaedecode = VAEDecode(samples=video_latent_2, vae=vae_2)
    _, image_pass, _, _, _ = VRAM_Debug(image_pass=vaedecode)
    _, _, _, count = GetImageSizeAndCount(image=image_pass)

    _, calc_int, _ = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int, vaedecode, trimaudioduration_2


def prompt_enhancer_cc5ea718(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph cc5ea718-db6a-47c7-83cf-7d9a8442ba99 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:8ce010c65ed2457df2de94406016a7eee37b5fb7a7cb0a3a41246a5e9c74f342
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video_a3fb563d(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler,
    sigmas,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph a3fb563d-4711-4225-9210-fbe61b1bd79d in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:238dc4a8d04df1c8b62437cb86819e13f8c09a55b0c565dbd9a2982b277aa858
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, cc5ea718-db6a-47c7-83cf-7d9a8442ba99, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(value=0)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    comfy_float, _, _ = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    _, calc_int_2, _ = SimpleCalculatorKJ(
        _id='a3fb563d:5116',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=calc_int_2,
    )

    trimaudioduration = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    prompt_enhancer_cc5ea718_result = prompt_enhancer_cc5ea718(
        clip=['-10', 17],
        image=resizeimagemasknode,
        enable=['-10', 18],
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    positive = CLIPTextEncode(text=prompt_enhancer_cc5ea718_result, clip=clip)

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_2, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_2, _ = LTXVSeparateAVLatent(av_latent=output_2)
    vaedecode = VAEDecode(samples=video_latent_2, vae=vae_2)
    _, image_pass, _, _, _ = VRAM_Debug(image_pass=vaedecode)
    _, _, _, count = GetImageSizeAndCount(image=image_pass)

    _, calc_int, _ = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int, vaedecode, trimaudioduration_2


def prompt_enhancer_50a3ed96(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 50a3ed96-aa61-4734-97cb-28cb47d171be in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:106b8c1e1f848de09ddc31f53b525c819c6acea35ef8cb989b287387898d3fed
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video_4acc9924(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler,
    sigmas,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 4acc9924-c0bd-470a-b000-46c75e61d004 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:15e1174c0eeb3e4b46f8553675deed8c2ed2828151886bf61a1a1df15272cabf
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 50a3ed96-aa61-4734-97cb-28cb47d171be, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(value=0)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    comfy_float, _, _ = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    _, calc_int_2, _ = SimpleCalculatorKJ(
        _id='4acc9924:5191',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=calc_int_2,
    )

    trimaudioduration = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    prompt_enhancer_50a3ed96_result = prompt_enhancer_50a3ed96(
        clip=['-10', 17],
        image=resizeimagemasknode,
        enable=['-10', 18],
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    positive = CLIPTextEncode(text=prompt_enhancer_50a3ed96_result, clip=clip)

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_2, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_2, _ = LTXVSeparateAVLatent(av_latent=output_2)
    vaedecode = VAEDecode(samples=video_latent_2, vae=vae_2)
    _, image_pass, _, _, _ = VRAM_Debug(image_pass=vaedecode)
    _, _, _, count = GetImageSizeAndCount(image=image_pass)

    _, calc_int, _ = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int, vaedecode, trimaudioduration_2

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='444', image='download (8).png')

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

    vaeloaderkj = VAELoaderKJ(
        _id='1567',
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    vaeloader_2 = VAELoader(_id='1569', vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(_id='1570', unet_name=UNET_NAME)
    intconstant = INTConstant(_id='1591', value=480)
    loadaudio = LoadAudio(_id='1594', audio='ComfyUI_00152_.mp3')

    melbandroformermodelloader = MelBandRoFormerModelLoader(
        _id='1600',
        model=MEL_BAND_ROFORMER_NAME,
    )

    intconstant_2 = INTConstant(_id='1606', value=832)

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='1651',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': 11.0, 'variables.b': 25.0},
    )

    randomnoise = RandomNoise(
        _id='2169',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    # Sampling
    ksamplerselect = KSamplerSelect(_id='2174', sampler_name='euler_cfg_pp')
    manualsigmas = ManualSigmas(_id='2176', sigmas='0.85, 0.7250, 0.4219, 0.0')

    randomnoise_2 = RandomNoise(
        _id='2179',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    ksamplerselect_2 = KSamplerSelect(_id='2180', sampler_name='euler_ancestral_cfg_pp')

    manualsigmas_2 = ManualSigmas(
        _id='2187',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    total_duration_result = total_duration(
        variables_a=['2012', 0],
        variables_b=['1997', 0],
        variables_c=['5071', 0],
        variables_d=['5146', 0],
        variables_e=['5221', 0],
    )

    stringconcatenate = StringConcatenate(
        _id='4164',
        string_a='MusicVideo',
        string_b=MYNEWVIDEO,
        delimiter=VALUE,
    )

    stringconcatenate_3 = StringConcatenate(
        _id='4743',
        string_a='output\\MusicVideo',
        string_b=MYNEWVIDEO,
        delimiter=VALUE,
    )

    image_4, _ = LoadImage(_id='4750', image='download (1).png')
    image_5, _ = LoadImage(_id='5074', image='download (6).png')
    image_6, _ = LoadImage(_id='5149', image='download (2).png')
    image_7, _ = LoadImage(_id='5224', image='download (12).png')

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

    trimaudioduration = TrimAudioDuration(
        _id='1598',
        start_index=11,
        duration=total_duration_result,
        audio=loadaudio,
    )

    solidmask = SolidMask(
        _id='1604',
        value=0,
        width=intconstant_2,
        height=intconstant,
    )

    # Conditioning
    cliptextencode_2 = CLIPTextEncode(
        _id='1626',
        text=DEFAULT_PROMPT,
        clip=dualcliploader,
    )

    stringconcatenate_2 = StringConcatenate(
        _id='4735',
        string_b='MusicVideo',
        delimiter=VALUE,
        string_a=stringconcatenate,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        _id='268',
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    melbandroformersampler = MelBandRoFormerSampler(
        _id='1599',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='1630',
        resize_type='scale by multiplier',
        input=image_2,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='2189',
        longer_edge=1536,
        images=image_2,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='446',
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(_id='504', model=pathchsageattentionkj)

    comfyswitchnode = ComfySwitchNode(
        _id='1616',
        switch=True,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    width_2, height_2, _ = GetImageSize(_id='1631', image=resizeimagemasknode)

    prompt_enhancer_3bd4eeb9_result = prompt_enhancer_3bd4eeb9(
        clip=dualcliploader,
        image=resizeimagesbylongeredge,
        enable=False,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='344',
        width=width_2,
        height=height_2,
        length=calc_int,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        _id='1523',
        model=ltxvchunkfeedforward,
    )

    cliptextencode = CLIPTextEncode(
        _id='1621',
        text=prompt_enhancer_3bd4eeb9_result,
        clip=dualcliploader,
    )

    trimaudioduration_2 = TrimAudioDuration(
        _id='1653',
        duration=11.0,
        audio=comfyswitchnode,
    )

    positive, negative = LTXVConditioning(
        _id='164',
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='1605',
        audio=trimaudioduration_2,
        audio_vae=vaeloaderkj,
    )

    model, _ = Power_Lora_Loader_rgthree(
        _id='2150',
        lora_1={'on': False, 'lora': 'LTX\\LTX-2\\LTX-2-Image2Vid-Adapter.safetensors', 'strength': 0.3, 'strengthTwo': None},
        lora_2={'on': False, 'lora': 'LTX\\v2\\ltx-2-19b-lora-camera-control-dolly-out.safetensors', 'strength': 0.3, 'strengthTwo': None},
        model=ltx2attentiontunerpatch,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        _id='4109',
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='1603',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    ltx2samplingpreviewoverride = LTX2SamplingPreviewOverride(
        _id='2188',
        model=model,
        vae=vaeloader_2,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='350',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace_2,
    )

    ltx2_nag = LTX2_NAG(
        _id='2178',
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    cfgguider = CFGGuider(
        _id='2170',
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=positive,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        _id='2177',
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    output, _ = SamplerCustomAdvanced(
        _id='2181',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(_id='2159', av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='2158',
        samples=video_latent_2,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='2183',
        strength=0.7,
        image=resizeimagesbylongeredge,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='2153',
        audio_latent=audio_latent_2,
        video_latent=ltxvimgtovideoinplace,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='2182',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(_id='245', av_latent=output_2)

    # Decode
    vaedecode = VAEDecode(_id='1318', samples=video_latent, vae=vaeloader)
    _, image_pass, _, _, _ = VRAM_Debug(_id='4184', image_pass=vaedecode)

    # Outputs
    vhs_videocombine_3 = VHS_VideoCombine(
        _id='4730',
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00004-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00004.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00004-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=trimaudioduration,
        images=vaedecode,
    )

    _, _, _, count = GetImageSizeAndCount(_id='4199', image=image_pass)

    int_2, output_1_2, audio_2 = generate_video_c4106aee(
        noise_seed=1021,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=10.0,
        frames_count=count,
        ref_image=image_4,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_2,
        height=height_2,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler_2=ksamplerselect_2,
        sigmas_2=manualsigmas_2,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='4709',
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00002-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00002.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00002-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio_2,
        images=output_1_2,
    )

    int, output_1, audio = generate_video(
        noise_seed=1030,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=18.0,
        frames_count=int_2,
        ref_image=image_5,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_2,
        height=height_2,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
        sampler_2=ksamplerselect,
        sigmas_2=manualsigmas,
    )

    vhs_videocombine_4 = VHS_VideoCombine(
        _id='5069',
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00003-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00003.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00003-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio,
        images=output_1,
    )

    int_3, output_1_3, audio_3 = generate_video_a3fb563d(
        noise_seed=1040,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=15.0,
        frames_count=int,
        ref_image=image_6,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_2,
        height=height_2,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
        sampler_2=ksamplerselect,
        sigmas_2=manualsigmas,
    )

    vhs_videocombine_5 = VHS_VideoCombine(
        _id='5144',
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00004-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00004.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00004-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio_3,
        images=output_1_3,
    )

    int_4, output_1_4, audio_4 = generate_video_4acc9924(
        noise_seed=1050,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=10.0,
        frames_count=int_3,
        ref_image=image_7,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_2,
        height=height_2,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
        sampler_2=ksamplerselect,
        sigmas_2=manualsigmas,
    )

    vhs_videocombine_6 = VHS_VideoCombine(
        _id='5219',
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00005-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00005.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00005-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio_4,
        images=output_1_4,
    )

    _, calc_int_2, _ = SimpleCalculatorKJ(
        _id='5228',
        expression='a + 100',
        **{'variables.a': int_4},
    )

    loadvideosfromfolder = LoadVideosFromFolder(
        _id='4708',
        video=stringconcatenate_3,
        frame_load_cap=calc_int_2,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        _id='4725',
        frame_rate=25.0,
        filename_prefix='LTX-MusicVideo-Final',
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-MusicVideo-Final_00003-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'LTX-MusicVideo-Final_00003.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-MusicVideo-Final_00003-audio.mp4'}},
        audio=trimaudioduration,
        images=loadvideosfromfolder,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')
