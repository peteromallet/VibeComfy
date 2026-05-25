# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioConcat, CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, DualCLIPLoader, EmptyImage, EmptyLTXVLatentVideo, GetImageSize, ImageScaleBy, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVGemmaCLIPModelLoader, LowVRAMAudioVAELoader


AFTER = 'after'
ALL_OR_NOTHING = 'all_or_nothing'
A_1 = 'a-1'
DEFAULT_FPS = 8
GEMMA_3_12B_IT_FP8_E4M3FN_SAFETENSORS = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
H264 = 'h264'
LINEAR_BLEND = 'linear_blend'
LTX_2_19B_DISTILLED_LORA_384_SAFETENSORS = 'ltx-2-19b-distilled-lora-384.safetensors'
LTX_2_19B_DISTILLED_SAFETENSORS = 'ltx-2-19b-distilled.safetensors'
MP4 = 'mp4'
NONE = 'none'
SOURCE = 'source'
TARGET_EXTENSION_LTX2 = 'target_extension_ltx2'

READY_METADATA = ReadyMetadata.build(
    capability='long_image_to_video',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTXVAudioVAELoader', 'LTXVConditioning', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Any Switch (rgthree)', 'Fast Groups Muter (rgthree)'], 'pip_packages': [], 'status': 'pinned'}},
    approach='long low-VRAM image-to-video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json'},
)

# === Subgraph functions ===

def samplers(
    *,
    model_stage_1,
    model_stage_2,
    upscale_model,
    positive,
    negative,
    images,
    vae,
    audio_vae,
    empty_latent_image,
    length: int,
    frame_rate: int,
    image_strength: float,
    noise_seed: int,
):
    """Samplers - two-image variant.

    Materialized from subgraph 3eaa20c4-5842-4fe4-87df-c0a7e83a6a78 in workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json.
    # vibecomfy source hash: sha256:59b13d87adeb306827df97deb599239cefc23b92b7559728dd5484cf18469f34
    Inner nodes: LTXVSeparateAVLatentx2, LTXVConcatAVLatentx2, SamplerCustomAdvancedx2, ManualSigmasx2, KSamplerSelectx2, CFGGuiderx2, LTXVEmptyLatentAudio, GetImageSize, EmptyLTXVLatentVideo, ResizeImagesByLongerEdge, LTXVPreprocess, ImageScaleBy, LTXVImgToVideoInplacex2, RandomNoisex2, ImpactExecutionOrderController, LTXVLatentUpsampler, LTXVSpatioTemporalTiledVAEDecode, LTXVAudioVAEDecode, IAMCCS_LTX2_EnsureFrames8nPlus1x2.
    """

    imagescaleby = ImageScaleBy(
        upscale_method='bicubic',
        scale_by=0.5,
        image=empty_latent_image,
    )

    randomnoise = RandomNoise(noise_seed=420, control_after_generate='fixed')
    ksamplerselect = KSamplerSelect(sampler_name='euler')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler')
    randomnoise_2 = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=length,
        frame_rate=frame_rate,
        audio_vae=audio_vae,
    )

    manualsigmas = ManualSigmas(
        sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')

    impactexecutionordercontroller = raw_call('ImpactExecutionOrderController', '5239',
        _outputs=('signal', 'value'),
        signal=positive,
        value=images,
    )

    width, height, batch_size = GetImageSize(image=imagescaleby)

    cfgguider = CFGGuider(
        cfg=1,
        model=model_stage_2,
        negative=negative,
        positive=impactexecutionordercontroller.out('signal'),
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=model_stage_1,
        negative=negative,
        positive=impactexecutionordercontroller.out('signal'),
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=impactexecutionordercontroller.out('value'),
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=length,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=33, image=resizeimagesbylongeredge)

    iamccs_ltx2_ensureframes8nplus1 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '10658',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=resizeimagesbylongeredge,
    )

    iamccs_ltx2_ensureframes8nplus1_2 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '10659',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=ltxvpreprocess,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        widget_0=0.6,
        widget_1=False,
        image=iamccs_ltx2_ensureframes8nplus1_2.out('images'),
        latent=emptyltxvlatentvideo,
        strength=image_strength,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=denoised_output_sampler,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        image=iamccs_ltx2_ensureframes8nplus1.out('images'),
        latent=ltxvlatentupsampler,
        vae=vae,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplace,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=denoised_output)
    ltxvaudiovaedecode = LTXVAudioVAEDecode(audio_vae=audio_vae, samples=audio_latent)

    ltxvspatiotemporaltiledvaedecode = raw_call('LTXVSpatioTemporalTiledVAEDecode', '5245',
        widget_0=4,
        widget_1=4,
        widget_2=16,
        widget_3=4,
        widget_4=False,
        widget_5='auto',
        widget_6='auto',
        latents=video_latent,
        vae=vae,
    )

    return ltxvspatiotemporaltiledvaedecode, ltxvaudiovaedecode


def samplers_8b36a85a(
    *,
    model_stage_1,
    model_stage_2,
    upscale_model,
    positive,
    negative,
    images,
    vae,
    audio_vae,
    empty_latent_image,
    length: int,
    frame_rate: int,
    image_strength: float,
    noise_seed: int,
):
    """Samplers - two-image variant.

    Materialized from subgraph 8b36a85a-087e-4ee5-85ca-cccc69c5c5d0 in workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json.
    # vibecomfy source hash: sha256:46a8f92960546c8edd6e0b122ca3db236bba4f001b7d824d9b1f009f27d3be0a
    Inner nodes: LTXVSeparateAVLatentx2, LTXVConcatAVLatentx2, SamplerCustomAdvancedx2, ManualSigmasx2, KSamplerSelectx2, CFGGuiderx2, LTXVEmptyLatentAudio, GetImageSize, EmptyLTXVLatentVideo, ResizeImagesByLongerEdge, LTXVPreprocess, ImageScaleBy, LTXVImgToVideoInplacex2, RandomNoisex2, ImpactExecutionOrderController, LTXVLatentUpsampler, LTXVSpatioTemporalTiledVAEDecode, LTXVAudioVAEDecode, IAMCCS_LTX2_EnsureFrames8nPlus1x2.
    """

    imagescaleby = ImageScaleBy(
        upscale_method='bicubic',
        scale_by=0.5,
        image=empty_latent_image,
    )

    randomnoise = RandomNoise(noise_seed=420, control_after_generate='fixed')
    ksamplerselect = KSamplerSelect(sampler_name='euler')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler')
    randomnoise_2 = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=length,
        frame_rate=frame_rate,
        audio_vae=audio_vae,
    )

    manualsigmas = ManualSigmas(
        sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')

    impactexecutionordercontroller = raw_call('ImpactExecutionOrderController', '5239',
        _outputs=('signal', 'value'),
        signal=positive,
        value=images,
    )

    width, height, batch_size = GetImageSize(image=imagescaleby)

    cfgguider = CFGGuider(
        cfg=1,
        model=model_stage_2,
        negative=negative,
        positive=impactexecutionordercontroller.out('signal'),
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=model_stage_1,
        negative=negative,
        positive=impactexecutionordercontroller.out('signal'),
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=impactexecutionordercontroller.out('value'),
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=length,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=33, image=resizeimagesbylongeredge)

    iamccs_ltx2_ensureframes8nplus1 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '10660',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=resizeimagesbylongeredge,
    )

    iamccs_ltx2_ensureframes8nplus1_2 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '10661',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=ltxvpreprocess,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        widget_0=0.6,
        widget_1=False,
        image=iamccs_ltx2_ensureframes8nplus1_2.out('images'),
        latent=emptyltxvlatentvideo,
        strength=image_strength,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=denoised_output_sampler,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        image=iamccs_ltx2_ensureframes8nplus1.out('images'),
        latent=ltxvlatentupsampler,
        vae=vae,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplace,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=denoised_output)
    ltxvaudiovaedecode = LTXVAudioVAEDecode(audio_vae=audio_vae, samples=audio_latent)

    ltxvspatiotemporaltiledvaedecode = raw_call('LTXVSpatioTemporalTiledVAEDecode', '5245',
        widget_0=4,
        widget_1=4,
        widget_2=16,
        widget_3=4,
        widget_4=False,
        widget_5='auto',
        widget_6='auto',
        latents=video_latent,
        vae=vae,
    )

    return ltxvspatiotemporaltiledvaedecode, ltxvaudiovaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    primitivestringmultiline = PrimitiveStringMultiline(
        value='Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.',
    )

    model, clip, vae = CheckpointLoaderSimple(ckpt_name=LTX_2_19B_DISTILLED_SAFETENSORS)

    ltxvgemmaclipmodelloader = LTXVGemmaCLIPModelLoader(
        gemma_path=GEMMA_3_12B_IT_FP8_E4M3FN_SAFETENSORS,
        ltxv_path=LTX_2_19B_DISTILLED_SAFETENSORS,
    )

    # Inputs
    image, mask = LoadImage(image='z-image_00255_.png')

    lowvramaudiovaeloader = LowVRAMAudioVAELoader(
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2-spatial-upscaler-x2-1.0.safetensors',
    )

    unetloadergguf = UnetLoaderGGUF(unet_name='LTX-2-dev-Q5_K_S.gguf')

    iamccs_ltx2_lorastackstaged = raw_call('IAMCCS_LTX2_LoRAStackStaged', '5218',
        widget_0=LTX_2_19B_DISTILLED_LORA_384_SAFETENSORS,
        widget_1=1,
        widget_2=1,
        widget_3='ltx-2-19b-lora-camera-control-dolly-right.safetensors',
        widget_4=0,
        widget_5=0,
        widget_6='no',
        widget_7=0,
        widget_8=0,
    )

    vaeloaderkj = VAELoaderKJ(
        vae_name='LTX2_video_vae_2_bf16.safetensors',
        device='main_device',
        weight_dtype='bf16',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )

    dualcliploader = DualCLIPLoader(
        clip_name1=GEMMA_3_12B_IT_FP8_E4M3FN_SAFETENSORS,
        clip_name2='ltx-2-19b-embeddings_connector_dev_bf16.safetensors',
        type_='ltxv',
        device='default',
    )

    iamccs_ltx2_frameratesync = raw_call('IAMCCS_LTX2_FrameRateSync', '5225', widget_0=24, widget_1='fixed')

    primitivestringmultiline_2 = PrimitiveStringMultiline(
        value='man runs away from camera. the camera cranes up and show him run into the distance down the street at a busy New York night.',
    )

    fast_groups_muter__rgthree_ = raw_call('Fast Groups Muter (rgthree)', '5265')

    primitivestringmultiline_3 = PrimitiveStringMultiline(
        value='the camera cranes up and show the whole streets of new york.',
    )

    iamccs_autolinkarguments = raw_call('IAMCCS_AutoLinkArguments', '9026',
        widget_0=False,
        widget_1=False,
        widget_10='Red',
        widget_11='Orange',
        widget_12='Black',
        widget_13='',
        widget_14='',
        widget_15='both',
        widget_17='',
        widget_19='',
        widget_2=False,
        widget_3=True,
        widget_4='None',
        widget_5='',
        widget_6='TopToDown',
        widget_7='AvoidAll',
        widget_8='',
        widget_9=True,
    )

    emptyimage = EmptyImage(height=720, width=1332)

    iamccs_ltx2_timeframecount = raw_call('IAMCCS_LTX2_TimeFrameCount', '10956',
        widget_0=10,
        widget_1=241,
        widget_2='fixed',
    )

    iamccs_modelwithlora_ltx2_staged = raw_call('IAMCCS_ModelWithLoRA_LTX2_Staged', '5219',
        lora_stage1=iamccs_ltx2_lorastackstaged.out(0),
        lora_stage2=iamccs_ltx2_lorastackstaged.out(1),
        model=unetloadergguf,
        model_stage2=unetloadergguf,
    )

    iamccs_ltx2_lorastackmodelio = raw_call('IAMCCS_LTX2_LoRAStackModelIO', '5259',
        widget_0=LTX_2_19B_DISTILLED_LORA_384_SAFETENSORS,
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=model,
    )

    any_switch__rgthree__2 = raw_call('Any Switch (rgthree)', '5261',
        any_01=lowvramaudiovaeloader,
        any_02=ltxvaudiovaeloader,
    )

    any_switch__rgthree__3 = raw_call('Any Switch (rgthree)', '5262',
        any_01=ltxvgemmaclipmodelloader,
        any_02=dualcliploader,
    )

    any_switch__rgthree__4 = raw_call('Any Switch (rgthree)', '5263', any_01=vae, any_02=vaeloaderkj)
    iamccs_autolinkconverter = raw_call('IAMCCS_AutoLinkConverter', '9025', arg=iamccs_autolinkarguments.out(0))

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text=primitivestringmultiline,
        clip=any_switch__rgthree__3,
    )

    cliptextencode_2 = CLIPTextEncode(
        text=primitivestringmultiline_2,
        clip=any_switch__rgthree__3,
    )

    cliptextencode_3 = CLIPTextEncode(
        text=primitivestringmultiline_3,
        clip=any_switch__rgthree__3,
    )

    iamccs_gguf_accelerator = raw_call('IAMCCS_GGUF_accelerator', '9684',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5=ALL_OR_NOTHING,
        widget_6=1024,
        model=iamccs_modelwithlora_ltx2_staged.out(1),
    )

    iamccs_gguf_accelerator_2 = raw_call('IAMCCS_GGUF_accelerator', '9685',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5=ALL_OR_NOTHING,
        widget_6=1024,
        model=iamccs_modelwithlora_ltx2_staged.out(1),
    )

    positive, negative = LTXVConditioning(
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode,
        positive=cliptextencode,
    )

    positive_ltxv, negative_ltxv = LTXVConditioning(
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode_2,
        positive=cliptextencode_2,
    )

    any_switch__rgthree_ = raw_call('Any Switch (rgthree)', '5258',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator.out(0),
    )

    any_switch__rgthree__5 = raw_call('Any Switch (rgthree)', '5264',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator_2.out(0),
    )

    positive_ltxv_2, negative_ltxv_2 = LTXVConditioning(
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode_3,
        positive=cliptextencode_3,
    )

    images, audio = samplers(
        model_stage_1=any_switch__rgthree_,
        model_stage_2=any_switch__rgthree__5,
        upscale_model=latentupscalemodelloader,
        positive=positive,
        negative=negative,
        images=image,
        vae=any_switch__rgthree__4,
        audio_vae=any_switch__rgthree__2,
        empty_latent_image=emptyimage,
        length=iamccs_ltx2_timeframecount.out(0),
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_strength=0.6,
        noise_seed=43,
    )

    createvideo = CreateVideo(
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audio,
        images=images,
    )

    iamccs_ltx2_getimagefrombatch = raw_call('IAMCCS_LTX2_GetImageFromBatch', '9014',
        widget_0='from_end',
        widget_1=10,
        widget_2='none',
        widget_3='none',
        widget_4='none',
        widget_5='native_workflow_safe',
        widget_6=10,
        widget_7=0,
        widget_8=10,
        images=images,
    )

    # Outputs
    savevideo = SaveVideo(
        filename_prefix='output',
        format=MP4,
        codec=H264,
        video=createvideo,
    )

    images_2, audio_2 = samplers_8b36a85a(
        model_stage_1=any_switch__rgthree_,
        model_stage_2=any_switch__rgthree__5,
        upscale_model=latentupscalemodelloader,
        positive=positive_ltxv,
        negative=negative_ltxv,
        images=iamccs_ltx2_getimagefrombatch.out(0),
        vae=any_switch__rgthree__4,
        audio_vae=any_switch__rgthree__2,
        empty_latent_image=emptyimage,
        length=iamccs_ltx2_timeframecount.out(0),
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_strength=0.6,
        noise_seed=43,
    )

    createvideo_2 = CreateVideo(
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audio_2,
        images=images_2,
    )

    audioconcat = AudioConcat(widget_0=AFTER, audio1=audio, audio2=audio_2)

    iamccs_ltx2_extensionmodule = raw_call('IAMCCS_LTX2_ExtensionModule', '9015',
        widget_0=10,
        widget_1=SOURCE,
        widget_10=NONE,
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14=TARGET_EXTENSION_LTX2,
        widget_15=1,
        widget_2=LINEAR_BLEND,
        widget_3=True,
        widget_4=A_1,
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=images_2,
        source_images=images,
    )

    savevideo_2 = SaveVideo(
        filename_prefix='output',
        format=MP4,
        codec=H264,
        video=createvideo_2,
    )

    images_3, audio_3 = samplers_8b36a85a(
        model_stage_1=any_switch__rgthree_,
        model_stage_2=any_switch__rgthree__5,
        upscale_model=latentupscalemodelloader,
        positive=positive_ltxv_2,
        negative=negative_ltxv_2,
        images=iamccs_ltx2_extensionmodule.out(1),
        vae=any_switch__rgthree__4,
        audio_vae=any_switch__rgthree__2,
        empty_latent_image=emptyimage,
        length=iamccs_ltx2_timeframecount.out(0),
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_strength=0.6,
        noise_seed=43,
    )

    createvideo_4 = CreateVideo(
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audio_3,
        images=images_3,
    )

    audioconcat_2 = AudioConcat(widget_0=AFTER, audio1=audioconcat, audio2=audio_3)

    iamccs_ltx2_extensionmodule_2 = raw_call('IAMCCS_LTX2_ExtensionModule', '9016',
        widget_0=10,
        widget_1=SOURCE,
        widget_10=NONE,
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14=TARGET_EXTENSION_LTX2,
        widget_15=1,
        widget_2=LINEAR_BLEND,
        widget_3=True,
        widget_4=A_1,
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=images_3,
        source_images=iamccs_ltx2_extensionmodule.out(2),
    )

    createvideo_3 = CreateVideo(
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audioconcat_2,
        images=iamccs_ltx2_extensionmodule_2.out(2),
    )

    savevideo_4 = SaveVideo(
        filename_prefix='output',
        format=MP4,
        codec=H264,
        video=createvideo_4,
    )

    savevideo_3 = SaveVideo(
        filename_prefix='output',
        format=MP4,
        codec=H264,
        video=createvideo_3,
    )


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='z-image_00255_.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'width': InputSpec(node=emptyimage, field='width', default=1332, type='INT'),
        'height': InputSpec(node=emptyimage, field='height', default=720, type='INT'),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default='Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

