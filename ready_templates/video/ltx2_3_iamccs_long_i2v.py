# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioConcat, CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, DualCLIPLoader, EmptyImage, EmptyLTXVLatentVideo, GetImageSize, ImageScaleBy, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, ManualSigmas, RandomNoise, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVGemmaCLIPModelLoader, LTXVSpatioTemporalTiledVAEDecode
from vibecomfy.nodes.rgthree import Any_Switch_rgthree


ALL_OR_NOTHING = 'all_or_nothing'
AUDIO_VAE_NAME = 'LTX2_audio_vae_bf16.safetensors'
A_1 = 'a-1'
BF16 = 'bf16'
CKPT_NAME = 'ltx-2-19b-distilled.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
CLIP_NAME_2 = 'ltx-2-19b-embeddings_connector_dev_bf16.safetensors'
DEFAULT_FRAMES = 121
DEFAULT_PROMPT = 'Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.'
DEFAULT_PROMPT_2 = 'man runs away from camera. the camera cranes up and show him run into the distance down the street at a busy New York night.'
DEFAULT_PROMPT_3 = 'the camera cranes up and show the whole streets of new york.'
DEFAULT_SEED = 43
H264 = 'h264'
LINEAR_BLEND = 'linear_blend'
MAIN_DEVICE = 'main_device'
MP4 = 'mp4'
NONE = 'none'
SOURCE = 'source'
SPATIAL_UPSCALER_NAME = 'ltx-2-spatial-upscaler-x2-1.0.safetensors'
TARGET_EXTENSION_LTX2 = 'target_extension_ltx2'
UNET_NAME_GGUF = 'LTX-2-dev-Q5_K_S.gguf'
VIDEO_VAE_NAME = 'LTX2_video_vae_2_bf16.safetensors'
WIDGET__NAME = 'ltx-2-19b-distilled-lora-384.safetensors'
WIDGET__NAME_2 = 'ltx-2-19b-lora-camera-control-dolly-right.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='5180', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='3eaa20c4:5111', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'width': InputSpec(node='10955', field='width', default=1332, type='INT'),
    'height': InputSpec(node='10955', field='height', default=720, type='INT'),
    'prompt': InputSpec(node='5174', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX-2-dev-Q5_K_S.gguf', 'LTX2_audio_vae_bf16.safetensors', 'LTX2_video_vae_2_bf16.safetensors', 'ltx-2-19b-distilled.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTXVAudioVAELoader', 'LTXVConditioning', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Any Switch (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json', 'source_id': 'video/ltx2_3_iamccs_long_i2v', 'upstream_source_id': 'IAMCCS_LTX2_I2V_LONG_LENGTH', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_iamccs_long_i2v'},
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

    Materialized from subgraph 3eaa20c4-5842-4fe4-87df-c0a7e83a6a78 in ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json.
    # vibecomfy source hash: sha256:132873f8db6ceceb9df7e74e4bd80f2edde60e8e3fd082d58446d6fc14478012
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

    randomnoise_2 = RandomNoise(
        _id='3eaa20c4:5111',
        control_after_generate='fixed',
        noise_seed=noise_seed,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=length,
        frame_rate=frame_rate,
        audio_vae=audio_vae,
    )

    manualsigmas = ManualSigmas(
        sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')

    impactexecutionordercontroller = raw_call('ImpactExecutionOrderController', '3eaa20c4:5239',
        _outputs=('signal', 'value'),
        signal=positive,
        value=images,
    )

    width, height, _ = GetImageSize(image=imagescaleby)

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

    iamccs_ltx2_ensureframes8nplus1 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '3eaa20c4:10658',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=resizeimagesbylongeredge,
    )

    iamccs_ltx2_ensureframes8nplus1_2 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '3eaa20c4:10659',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=ltxvpreprocess,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        strength=image_strength,
        image=iamccs_ltx2_ensureframes8nplus1_2.out('images'),
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplace_2,
    )

    _, denoised_output_2 = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(av_latent=denoised_output_2)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_2,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=iamccs_ltx2_ensureframes8nplus1.out('images'),
        latent=ltxvlatentupsampler,
        vae=vae,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_2,
        video_latent=ltxvimgtovideoinplace,
    )

    _, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=denoised_output)
    ltxvaudiovaedecode = LTXVAudioVAEDecode(audio_vae=audio_vae, samples=audio_latent)

    ltxvspatiotemporaltiledvaedecode = LTXVSpatioTemporalTiledVAEDecode(
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

    Materialized from subgraph 8b36a85a-087e-4ee5-85ca-cccc69c5c5d0 in ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json.
    # vibecomfy source hash: sha256:9699ebdbc68e61e199aafc96b7d4231d6e992f903cb707c2f2df005f82d14801
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

    impactexecutionordercontroller = raw_call('ImpactExecutionOrderController', '8b36a85a:5239',
        _outputs=('signal', 'value'),
        signal=positive,
        value=images,
    )

    width, height, _ = GetImageSize(image=imagescaleby)

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

    iamccs_ltx2_ensureframes8nplus1 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '8b36a85a:10660',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=resizeimagesbylongeredge,
    )

    iamccs_ltx2_ensureframes8nplus1_2 = raw_call('IAMCCS_LTX2_EnsureFrames8nPlus1', '8b36a85a:10661',
        _outputs=('images', 'frames', 'report'),
        widget_0='pad_repeat_last',
        widget_1='up',
        images=ltxvpreprocess,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        strength=image_strength,
        image=iamccs_ltx2_ensureframes8nplus1_2.out('images'),
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplace_2,
    )

    _, denoised_output_2 = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(av_latent=denoised_output_2)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_2,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=iamccs_ltx2_ensureframes8nplus1.out('images'),
        latent=ltxvlatentupsampler,
        vae=vae,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_2,
        video_latent=ltxvimgtovideoinplace,
    )

    _, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=denoised_output)
    ltxvaudiovaedecode = LTXVAudioVAEDecode(audio_vae=audio_vae, samples=audio_latent)

    ltxvspatiotemporaltiledvaedecode = LTXVSpatioTemporalTiledVAEDecode(
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

    # Loaders
    model, _, vae = CheckpointLoaderSimple(_id='5176', ckpt_name=CKPT_NAME)

    ltxvgemmaclipmodelloader = LTXVGemmaCLIPModelLoader(
        _id='5178',
        gemma_path=CLIP_NAME,
        ltxv_path=CKPT_NAME,
    )

    # Inputs
    image, _ = LoadImage(_id='5180', image='z-image_00255_.png')
    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='5188', ckpt_name=CKPT_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='5210',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    unetloadergguf = UnetLoaderGGUF(_id='5215', unet_name=UNET_NAME_GGUF)

    iamccs_ltx2_lorastackstaged = raw_call('IAMCCS_LTX2_LoRAStackStaged', '5218',
        widget_0=WIDGET__NAME,
        widget_1=1,
        widget_2=1,
        widget_3=WIDGET__NAME_2,
        widget_4=0,
        widget_5=0,
        widget_6='no',
        widget_7=0,
        widget_8=0,
    )

    vaeloaderkj = VAELoaderKJ(
        _id='5220',
        vae_name=VIDEO_VAE_NAME,
        device=MAIN_DEVICE,
        weight_dtype=BF16,
    )

    vaeloaderkj_2 = VAELoaderKJ(
        _id='5221',
        vae_name=AUDIO_VAE_NAME,
        device=MAIN_DEVICE,
        weight_dtype=BF16,
    )

    dualcliploader = DualCLIPLoader(
        _id='5222',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type='ltxv',
        device='default',
    )

    iamccs_ltx2_frameratesync = raw_call('IAMCCS_LTX2_FrameRateSync', '5225', widget_0=24, widget_1='fixed')
    emptyimage = EmptyImage(_id='10955', width=1332, height=720)

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
        widget_0=WIDGET__NAME,
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=model,
    )

    any_switch__rgthree__2 = Any_Switch_rgthree(
        _id='5261',
        any_01=ltxvaudiovaeloader,
        any_02=vaeloaderkj_2,
    )

    any_switch__rgthree__3 = Any_Switch_rgthree(
        _id='5262',
        any_01=ltxvgemmaclipmodelloader,
        any_02=dualcliploader,
    )

    any_switch__rgthree__4 = Any_Switch_rgthree(
        _id='5263',
        any_01=vae,
        any_02=vaeloaderkj,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='5174',
        text=DEFAULT_PROMPT,
        clip=any_switch__rgthree__3,
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='5233',
        text=DEFAULT_PROMPT_2,
        clip=any_switch__rgthree__3,
    )

    cliptextencode_3 = CLIPTextEncode(
        _id='9002',
        text=DEFAULT_PROMPT_3,
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
        _id='5173',
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode,
        positive=cliptextencode,
    )

    positive_2, negative_2 = LTXVConditioning(
        _id='5234',
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode_2,
        positive=cliptextencode_2,
    )

    any_switch__rgthree_ = Any_Switch_rgthree(
        _id='5258',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator.out(0),
    )

    any_switch__rgthree__5 = Any_Switch_rgthree(
        _id='5264',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator_2.out(0),
    )

    positive_3, negative_3 = LTXVConditioning(
        _id='9003',
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode_3,
        positive=cliptextencode_3,
    )

    images_3, audio_3 = samplers(
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
        _id='5190',
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audio_3,
        images=images_3,
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
        images=images_3,
    )

    # Outputs
    savevideo = SaveVideo(
        _id='4958',
        filename_prefix='IAMCCS(LTX2_LL_1',
        format=MP4,
        codec=H264,
        video=createvideo,
    )

    images, audio = samplers_8b36a85a(
        model_stage_1=any_switch__rgthree_,
        model_stage_2=any_switch__rgthree__5,
        upscale_model=latentupscalemodelloader,
        positive=positive_2,
        negative=negative_2,
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
        _id='5236',
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audio,
        images=images,
    )

    audioconcat = AudioConcat(_id='5252', audio1=audio_3, audio2=audio)

    iamccs_ltx2_extensionmodule = raw_call('IAMCCS_LTX2_ExtensionModule', '9015',
        widget_0=10,
        widget_1=SOURCE,
        widget_10='none',
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14=TARGET_EXTENSION_LTX2,
        widget_15=1,
        widget_2=LINEAR_BLEND,
        widget_3=True,
        widget_4=A_1,
        widget_5=NONE,
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=images,
        source_images=images_3,
    )

    savevideo_2 = SaveVideo(
        _id='5237',
        filename_prefix='IAMCCS(LTX2_LL_2',
        format=MP4,
        codec=H264,
        video=createvideo_2,
    )

    images_2, audio_2 = samplers_8b36a85a(
        model_stage_1=any_switch__rgthree_,
        model_stage_2=any_switch__rgthree__5,
        upscale_model=latentupscalemodelloader,
        positive=positive_3,
        negative=negative_3,
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
        _id='9005',
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audio_2,
        images=images_2,
    )

    audioconcat_2 = AudioConcat(_id='9008', audio1=audioconcat, audio2=audio_2)

    iamccs_ltx2_extensionmodule_2 = raw_call('IAMCCS_LTX2_ExtensionModule', '9016',
        widget_0=10,
        widget_1=SOURCE,
        widget_10='none',
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14=TARGET_EXTENSION_LTX2,
        widget_15=1,
        widget_2=LINEAR_BLEND,
        widget_3=True,
        widget_4=A_1,
        widget_5=NONE,
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=images_2,
        source_images=iamccs_ltx2_extensionmodule.out(2),
    )

    createvideo_3 = CreateVideo(
        _id='5254',
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audioconcat_2,
        images=iamccs_ltx2_extensionmodule_2.out(2),
    )

    savevideo_4 = SaveVideo(
        _id='9006',
        filename_prefix='IAMCCS(LTX2_LL_3',
        format=MP4,
        codec=H264,
        video=createvideo_4,
    )

    savevideo_3 = SaveVideo(
        _id='5255',
        filename_prefix='IAMCCS(LTX2_LL_FULL',
        format=MP4,
        codec=H264,
        video=createvideo_3,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='IAMCCS(LTX2_LL_1')

