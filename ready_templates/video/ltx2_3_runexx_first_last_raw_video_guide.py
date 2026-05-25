# vibecomfy: manual
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, ImageScaleBy, KSamplerSelect, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImagesByLongerEdge, SamplerCustomAdvanced, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = "wf.nodes['11'].inputs.get('text', '')"
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEVICE = 'cpu'
EXPRESSION = 'a'
FILE = 'ltx_smoke_guide.mp4'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
KEEP_PROPORTION = 'crop'
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
SIGMAS = '0.909375, 0.725, 0.421875, 0.0'
UNET_NAME = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UPSCALE_METHOD = 'nearest-exact'
UPSCALE_METHOD_2 = 'lanczos'
VAE_NAME = 'taeltx2_3.safetensors'
VAE_NAME_2 = 'LTX23_video_vae_bf16.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', subdir='vae'),
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', subdir='checkpoints'),
    'vae_2': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', subdir='diffusion_models'),
    'lora': ModelAsset(filename='LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', subdir='loras'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_raw_video_guide',
    models=MODELS,
    output_prefix='video/ltx2_3_runexx_first_last_frame',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'LTXVAddGuide', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='first/last-frame image anchors plus full-length raw video frames into LTXVAddGuide',
    smoke_resolution='256x256x9_frames',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by PathchSageAttentionKJ auto mode for 4090-speed LTX Runexx validation.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use first/last anchors for travel endpoints.', 'Use raw full-length guide frames for VG-style guidance.', 'Keep IC-LoRA union-control modes on the separate IC-LoRA control template.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    runtime_note='Uses non-IC LTXVAddGuide; raw mode intentionally avoids LTXICLoRALoaderModelOnly and LTXAddVideoICLoRAGuide.',
    discord_signal='Matches Wan2GP LTX VG-style full-video guide without IC-LoRA.',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    manualsigmas = ManualSigmas(sigmas=SIGMAS)

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )

    randomnoise_2 = RandomNoise(
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )

    # Inputs
    image, mask = LoadImage(image='image (6).png')
    image_load, mask_load = LoadImage(image='0 (13).webp')
    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
    vaeloader = VAELoader(vae_name=VAE_NAME)
    vaeloader_2 = VAELoader(vae_name=VAE_NAME_2)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type_='ltxv',
        device='default',
    )

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_3 = ManualSigmas(sigmas=SIGMAS)
    primitivefloat = raw_call('PrimitiveFloat', '2076', value=24)
    intconstant = INTConstant(value=81)
    intconstant_2 = INTConstant(value=720)
    intconstant_3 = INTConstant(value=1280)
    primitiveboolean = raw_call('PrimitiveBoolean', '2082', value=True)

    primitivestringmultiline = PrimitiveStringMultiline(
        value="wf.nodes['2103'].inputs.get('value', '')",
    )

    primitivefloat_2 = raw_call('PrimitiveFloat', '2108', value=1.0)
    primitivefloat_3 = raw_call('PrimitiveFloat', '2110', value=1.0)

    loadvideo = LoadVideo(
        file=FILE,
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
    )

    primitivefloat_4 = raw_call('PrimitiveFloat', '6102', value=1)

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    cliptextencode_2 = CLIPTextEncode(
        text=primitivestringmultiline,
        clip=dualcliploader,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        divisible_by=32,
        device=DEVICE,
        width=intconstant_3,
        height=intconstant_2,
        image=image,
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression=EXPRESSION,
        variables='a',
        a=primitivefloat,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression=EXPRESSION,
        variables='a,b',
        widget_0='a',
        a=intconstant,
        b=primitivefloat,
    )

    images, audio, fps = GetVideoComponents(video=loadvideo)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=int_simple,
        frame_rate=int,
        audio_vae=ltxvaudiovaeloader,
    )

    positive, negative = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    imagescaleby = ImageScaleBy(
        upscale_method=UPSCALE_METHOD_2,
        scale_by=0.5,
        image=image_image,
    )

    image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        divisible_by=32,
        device=DEVICE,
        width=width,
        height=height,
        image=image_load,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    image_image_3, width_image_2, height_image_2, mask_image_3 = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD_2,
        keep_proportion='stretch',
        divisible_by=32,
        device=DEVICE,
        width=intconstant_3,
        height=intconstant_2,
        image=images,
    )

    width_get, height_get, batch_size = GetImageSize(image=imagescaleby)

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image_2,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image_2)
    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

    ltxvpreprocess_2 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width_get,
        height=height_get,
        length=int_simple,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='2',
        latent=emptyltxvlatentvideo,
        vae=vaeloader_2,
        **{'num_images.index_1': 0, 'num_images.index_2': -1, 'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess, 'num_images.strength_1': primitivefloat_3, 'num_images.strength_2': primitivefloat_2},
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        model=ltx2attentiontunerpatch,
    )

    power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '2107',
        _outputs=('MODEL', 'CLIP'),
        model=ltx2memoryefficientsageattentionpatch,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplacekj,
    )

    ltxvscheduler = LTXVScheduler(steps=1, latent=ltxvconcatavlatent)

    ltx2_nag = LTX2_NAG(
        model=power_lora_loader__rgthree_.out('MODEL'),
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader_2,
    )

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        unload_all_models=True,
        any_input=ltxvlatentupsampler,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        latent=any_output,
        vae=vaeloader_2,
        **{'num_images.index_1': 0, 'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': primitivefloat_3},
    )

    positive_ltxv, negative_ltxv, latent = LTXVAddGuide(
        strength=primitivefloat_4,
        image=image_image_3,
        latent=ltxvimgtovideoinplacekj_2,
        negative=negative,
        positive=positive,
        vae=vaeloader_2,
    )

    vibecomfystripconditioningkeys = raw_call('VibeComfyStripConditioningKeys', '2292',
        _outputs=('POSITIVE', 'NEGATIVE'),
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=latent,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=vibecomfystripconditioningkeys.out('NEGATIVE'),
        positive=vibecomfystripconditioningkeys.out('POSITIVE'),
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_3,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=vibecomfystripconditioningkeys.out('NEGATIVE'),
        positive=vibecomfystripconditioningkeys.out('POSITIVE'),
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=latent_ltxv,
        vae=vaeloader_2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        filename_prefix='reigh_vibecomfy_ltx_raw_guide',
        format='video/h264-mp4',
        frame_rate=primitivefloat,
        images=vaedecodetiled,
    )


    wf.register_input('model', ltxvaudiovaeloader.node.id, 'ckpt_name', CKPT_NAME)

    PUBLIC_INPUTS = {
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED),
        'model': InputSpec(node=ltxvaudiovaeloader, field='ckpt_name', default=CKPT_NAME),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default="wf.nodes['2103'].inputs.get('value', '')"),
        'first_image': InputSpec(node=image, field='image', default='image (6).png', aliases=('start_image',)),
        'last_image': InputSpec(node=image_load, field='image', default='0 (13).webp', aliases=('end_image',)),
        'fps': InputSpec(node=primitivefloat, field='value', default=24),
        'frames': InputSpec(node=intconstant, field='value', default=81),
        'height': InputSpec(node=intconstant_2, field='value', default=720),
        'width': InputSpec(node=intconstant_3, field='value', default=1280),
        'last_frame_strength': InputSpec(node=primitivefloat_2, field='value', default=1.0),
        'first_frame_strength': InputSpec(node=primitivefloat_3, field='value', default=1.0),
        'control_video': InputSpec(node=loadvideo, field='video', default='ltx_smoke_guide.mp4'),
        'strength': InputSpec(node=primitivefloat_4, field='value', default=1),
        'negative_prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT, aliases=('negative',)),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='reigh_vibecomfy_ltx_raw_guide')

