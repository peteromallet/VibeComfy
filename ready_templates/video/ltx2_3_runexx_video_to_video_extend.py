# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioConcat, BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAEDecodeTiled, VAEEncode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageBatchExtendWithOverlap, ImageBatchMulti, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine, VHS_VideoInfo
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness


DEFAULT_FRAMES = 4096
DEFAULT_FRAMES_2 = 1
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 432
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS = 'ltx-2.3_text_projection_bf16.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='video_to_video_extend',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='video-to-video extension',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json'},
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

    Materialized from subgraph 6002fb3c-ab34-4ad8-894e-fccaa60fd8c9 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json.
    # vibecomfy source hash: sha256:6dcd937b9ce0bc2f4ea792b11fe3e854e0574b92995763a31455926752d865db
    Inner nodes: StringConcatenate, PrimitiveStringMultiline, LazySwitchKJ, easy showAnything, TextGenerateLTX2Prompt, Reroute.
    """

    primitivestringmultiline = PrimitiveStringMultiline(value='')
    reroute = raw_call('Reroute', '598', _outputs=('',))

    stringconcatenate = StringConcatenate(
        widget_0='',
        string_a=primitivestringmultiline,
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    easy_showanything = raw_call('easy showAnything', '486',
        _outputs=('output',),
        widget_0='Style: realistic - cinematic - The Joker looks directly at the camera and speaks in a chilling, unsettling voice, "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3." He stands up, moving towards a hotel kitchen visible in the background. He opens a cabinet, revealing beer cans labeled "LTX." He grabs a can, turns towards the viewer, and holds it up so the "LTX" label is visible. He opens the can and drinks from it. He then says, "Ahhh... with a bit of LTX and Snickers, my mood changed. Lets all be friends. How about a little party at my place?" He laughs, a disturbing and unsettling sound.',
        anything=textgenerateltx2prompt,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=True,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
        switch=reroute.out(0),
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)

    # Decode
    vaedecodetiled = VAEDecodeTiled(temporal_size=4096)
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral')
    intconstant = INTConstant(value=10)

    # Inputs
    primitivefloat = raw_call('PrimitiveFloat', '214', value=8)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler')
    intconstant_2 = INTConstant(value=3)
    vaeloader = VAELoader(vae_name='LTX23_video_vae_bf16.safetensors')

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )

    dualcliploader = DualCLIPLoader(
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )

    vaeloader_2 = VAELoader(vae_name='taeltx2_3.safetensors')

    unetloader = UNETLoader(
        unet_name='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
    )

    unetloadergguf = UnetLoaderGGUF(
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1='gemma-3-12b-it-Q2_K.gguf',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='sdxl',
    )

    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    primitivestringmultiline = PrimitiveStringMultiline(
        value='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n',
    )

    reroute = raw_call('Reroute', '496')
    intconstant_3 = INTConstant(value=832)
    reroute_2 = raw_call('Reroute', '528')
    primitiveboolean = raw_call('PrimitiveBoolean', '594', value=True)
    loadaudio = LoadAudio(audio='speech_smoke.wav', widget_0='speech_smoke.wav')
    primitivestringmultiline_2 = PrimitiveStringMultiline(value='')

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text='text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=dualcliploader,
    )

    image, frame_count, audio, video_info = VHS_LoadVideo(
        file='ltx_smoke_guide.mp4',
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
        force_rate=primitivefloat,
    )

    normalizeaudioloudness = NormalizeAudioLoudness(widget_0=-16, audio=loadaudio)

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=intconstant_3,
        images=reroute.out(0),
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': intconstant_2, 'variables.b': primitivefloat},
    )

    cliptextencode_2 = CLIPTextEncode(
        text=' distorted sound, saturated sound, loud sound',
        clip=dualcliploader,
    )

    stringconcatenate = StringConcatenate(
        widget_0='',
        string_a=primitivestringmultiline_2,
        string_b=primitivestringmultiline,
    )

    image_get, mask = GetImageRangeFromBatch(
        num_frames=DEFAULT_FRAMES,
        widget_0=0,
        images=reroute_2.out(0),
        start_index=int,
    )

    source_fps_, source_frame_count_, source_duration_, source_width_, source_height_, loaded_fps_, loaded_frame_count_, loaded_duration_, loaded_width_, loaded_height_ = VHS_VideoInfo(
        video_info=video_info,
    )

    source_fps__video, source_frame_count__video, source_duration__video, source_width__video, source_height__video, loaded_fps__video, loaded_frame_count__video, loaded_duration__video, loaded_width__video, loaded_height__video = VHS_VideoInfo(
        video_info=video_info,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='disabled',
        model=loraloadermodelonly,
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='a / b',
        **{'variables.a': int, 'variables.b': loaded_fps_},
    )

    float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
        expression='(a > c) or (b > c) ',
        **{'variables.a': loaded_width__video, 'variables.b': loaded_height__video, 'variables.c': intconstant_3},
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

    float_simple_3, int_simple_3, boolean_simple_3 = SimpleCalculatorKJ(
        **{'variables.a': intconstant, 'variables.b': float_simple},
    )

    float_simple_4, int_simple_4, boolean_simple_4 = SimpleCalculatorKJ(
        expression='a - b',
        **{'variables.a': loaded_duration_, 'variables.b': float_simple},
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=resizeimagesbylongeredge,
        switch=boolean_simple_2,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=0,
        widget_1=60,
        audio=normalizeaudioloudness,
        duration=float_simple,
        start_index=float_simple_4,
    )

    image_get_2, width, height, count = GetImageSizeAndCount(image=lazyswitchkj)
    modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2attentiontunerpatch)

    ltx2_nag = LTX2_NAG(
        model=ltx2attentiontunerpatch,
        nag_cond_audio=cliptextencode_2,
        nag_cond_video=cliptextencode,
    )

    basicscheduler = BasicScheduler(
        scheduler=1,
        steps=1,
        widget_1=8,
        model=modelsamplingsd3,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=ltxvaudiovaeloader,
    )

    image_image, width_image, height_image, mask_image = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=64,
        device='cpu',
        width=width,
        height=height,
        image=image_get_2,
    )

    image_get_3, mask_get = GetImageRangeFromBatch(
        start_index=-1,
        widget_1=1,
        images=image_image,
        num_frames=int,
    )

    imagebatchmulti = ImageBatchMulti(image_1=image_image, image_2=image_get)
    image_get_4, mask_get_2 = GetImageRangeFromBatch(images=image_image)

    source_images, start_images, extended_images = ImageBatchExtendWithOverlap(
        widget_0=1,
        widget_1='source',
        widget_2='perceptual_crossfade',
        new_images=reroute_2.out(0),
        overlap=int,
        source_images=image_image,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=image_get_3,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_get_4,
    )

    image_get_5, mask_get_3 = GetImageRangeFromBatch(images=image_get_3)

    ltxvpreprocess = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_2,
    )

    image_get_6, mask_get_4 = GetImageRangeFromBatch(
        start_index=-1,
        images=resizeimagemasknode,
    )

    vaeencode = VAEEncode(pixels=resizeimagemasknode, vae=vaeloader)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        clip=dualcliploader,
        image=resizeimagesbylongeredge_2,
        prompt=stringconcatenate,
    )

    easy_showanything = raw_call('easy showAnything', '486',
        _outputs=('output',),
        widget_0='Style: realistic - cinematic - The Joker looks directly at the camera and speaks in a chilling, unsettling voice, "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3." He stands up, moving towards a hotel kitchen visible in the background. He opens a cabinet, revealing beer cans labeled "LTX." He grabs a can, turns towards the viewer, and holds it up so the "LTX" label is visible. He opens the can and drinks from it. He then says, "Ahhh... with a bit of LTX and Snickers, my mood changed. Lets all be friends. How about a little party at my place?" He laughs, a disturbing and unsettling sound.',
        anything=textgenerateltx2prompt,
    )

    lazyswitchkj_2 = LazySwitchKJ(
        widget_0=True,
        on_false=primitivestringmultiline,
        on_true=textgenerateltx2prompt,
        switch=intconstant,
    )

    video_latent, audio_latent = LTXVAudioVideoMask(
        max_length='pad',
        widget_0=24,
        widget_1=0,
        widget_2=15,
        widget_3=0,
        widget_4=15,
        widget_6='add',
        audio_end_time=float_simple_3,
        audio_latent=ltxvaudiovaeencode,
        audio_start_time=float_simple,
        video_end_time=float_simple_3,
        video_fps=primitivefloat,
        video_latent=vaeencode,
        video_start_time=float_simple,
    )

    vaeencode_2 = VAEEncode(pixels=image_get_6, vae=vaeloader)
    cliptextencode_3 = CLIPTextEncode(text=lazyswitchkj_2, clip=dualcliploader)

    positive, negative, latent = LTXVAddLatentGuide(
        widget_0=-1,
        widget_1=1,
        guiding_latent=vaeencode_2,
        latent=video_latent,
        negative=cliptextencode,
        positive=cliptextencode_3,
        vae=vaeloader,
    )

    positive_ltxv, negative_ltxv = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=negative,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=basicscheduler,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_ltxv_2,
        positive=latent_ltxv,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        image=image_get_5,
        latent=latent_ltxv,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplace,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_ltxv_2, audio_latent_ltxv_2 = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv_2,
    )

    positive_ltxv_3, negative_ltxv_3, latent_ltxv_2 = LTXVCropGuides(
        latent=video_latent_ltxv_2,
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=0,
        widget_1=2048,
        audio=ltxvaudiovaedecode,
        start_index=float_simple,
    )

    vaedecode = VAEDecode(samples=latent_ltxv_2, vae=vaeloader)

    audioconcat = AudioConcat(
        widget_0='after',
        audio1=normalizeaudioloudness,
        audio2=trimaudioduration_2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=primitivefloat,
        audio=audioconcat,
        images=extended_images,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        audio=audioconcat,
        images=imagebatchmulti,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

