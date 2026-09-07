# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2SamplingPreviewOverride, LTX2_NAG, LTXVChunkFeedForward, SimpleCalculatorKJ
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud'
DEFAULT_PROMPT_2 = 'Make this image come alive with fluid motion. \n\nA man with an intimidating expression speaks with expressive body language and gesticulations. \n\nHe looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point 3, i will find you.... and i will kill you" '
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 43
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
LORA_NAME = 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer/MelBandRoformer_fp16.safetensors'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='114', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='167', field='image', default='liam-neeson-in-retribution-ra.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'prompt': InputSpec(node='110', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2_NAG', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json', 'source_id': 'video/ltx2_3_runexx_custom_audio', 'upstream_source_id': 'LTX-2.3_Custom_Audio', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_custom_audio'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    randomnoise = RandomNoise(
        _id='114',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    randomnoise_2 = RandomNoise(
        _id='115',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    # Sampling
    ksamplerselect = KSamplerSelect(_id='137', sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(_id='138', sampler_name='euler_cfg_pp')

    # Inputs
    image_2, _ = LoadImage(_id='167', image='liam-neeson-in-retribution-ra.jpg')

    # Loaders
    vaeloader = VAELoader(_id='184', vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='189',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    dualcliploader = DualCLIPLoader(
        _id='190',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='196', ckpt_name=AUDIO_VAE_NAME)
    intconstant = INTConstant(_id='291', value=10)
    intconstant_2 = INTConstant(_id='292', value=1280)
    intconstant_3 = INTConstant(_id='293', value=736)

    _, calc_int_2, _ = SimpleCalculatorKJ(
        _id='311',
        expression='a',
        **{'variables.a': 24.0},
    )

    unetloader = UNETLoader(_id='329', unet_name=UNET_NAME)
    vaeloader_2 = VAELoader(_id='330', vae_name=VAE_TAESD_NAME)

    melbandroformermodelloader = MelBandRoFormerModelLoader(
        _id='370',
        model=MEL_BAND_ROFORMER_NAME,
    )

    loadaudio = LoadAudio(_id='372', audio='ComfyUI_00128_.mp3')
    manualsigmas = ManualSigmas(_id='380', sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_2 = ManualSigmas(
        _id='381',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(_id='110', text=DEFAULT_PROMPT, clip=dualcliploader)

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='134',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    image, _, _, _ = ImageResizeKJv2(
        _id='165',
        upscale_method='nearest-exact',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        width=intconstant_2,
        height=intconstant_3,
        image=image_2,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='287',
        expression='1+ 8*(round(a*b)/8)',
        b=24.0,
        a=intconstant,
    )

    solidmask = SolidMask(
        _id='362',
        value=0,
        width=intconstant_2,
        height=intconstant_3,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='164',
        resize_type='scale by multiplier',
        input=image,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        _id='199',
        frames_number=calc_int,
        frame_rate=calc_int_2,
        audio_vae=ltxvaudiovaeloader,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='246',
        longer_edge=1536,
        images=image,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(_id='332', model=loraloadermodelonly)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='349',
        prompt=DEFAULT_PROMPT_2,
        sampling_mode='off',
        clip=dualcliploader,
        image=image,
    )

    calc_float_3, _, _ = SimpleCalculatorKJ(
        _id='367',
        expression='a/b',
        b=24.0,
        a=calc_int,
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='121',
        text=textgenerateltx2prompt,
        clip=dualcliploader,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='162',
        img_compression=33,
        image=resizeimagesbylongeredge,
    )

    width, height, _ = GetImageSize(_id='163', image=resizeimagemasknode)
    model, _ = Power_Lora_Loader_rgthree(_id='301', model=ltxvchunkfeedforward)

    trimaudioduration = TrimAudioDuration(
        _id='373',
        duration=calc_float_3,
        audio=loadaudio,
    )

    positive, negative = LTXVConditioning(
        _id='107',
        frame_rate=24.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='108',
        width=width,
        height=height,
        length=calc_int,
    )

    ltx2samplingpreviewoverride = LTX2SamplingPreviewOverride(
        _id='337',
        model=model,
        vae=vaeloader_2,
    )

    melbandroformersampler = MelBandRoFormerSampler(
        _id='371',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        _id='161',
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    ltx2_nag = LTX2_NAG(
        _id='342',
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    comfyswitchnode_2 = ComfySwitchNode(
        _id='382',
        switch=False,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    cfgguider = CFGGuider(
        _id='103',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        _id='129',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='364',
        audio=comfyswitchnode_2,
        audio_vae=ltxvaudiovaeloader,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='363',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    comfyswitchnode = ComfySwitchNode(
        _id='376',
        switch=True,
        on_false=ltxvemptylatentaudio,
        on_true=setlatentnoisemask,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='109',
        audio_latent=comfyswitchnode,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output, _ = SamplerCustomAdvanced(
        _id='113',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='116', av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='118',
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='160',
        image=resizeimagesbylongeredge,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='117',
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='119',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_2, _ = LTXVSeparateAVLatent(_id='125', av_latent=output_2)

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        _id='127',
        temporal_size=4096,
        samples=video_latent_2,
        vae=vaeloader,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='140',
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_00796-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00796.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_00796-audio.mp4'}},
        audio=trimaudioduration,
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

