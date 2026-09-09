# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, ImageScaleBy, KSamplerSelect, LTXVAddGuide, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImagesByLongerEdge, SamplerCustomAdvanced, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.vibecomfy_internal import VibeComfyStripConditioningKeys
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


A = 'a'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LANCZOS = 'lanczos'
LORA_NAME = 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
LTX_SMOKE_GUIDE_MP4 = 'ltx_smoke_guide.mp4'
NEAREST_EXACT = 'nearest-exact'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', subdir='vae'),
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', subdir='checkpoints'),
    'vae_2': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', subdir='diffusion_models'),
    'lora': ModelAsset(filename='LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', subdir='loras'),
}


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='4', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='6', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_raw_video_guide',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    output_prefix='video/ltx2_3_runexx_first_last_frame',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'LTXVAddGuide', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    source_path='ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py',
    source_id='video/ltx2_3_runexx_first_last_raw_video_guide',
    source_type='ready_template',
    source_workflow_path='ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py',
    output_mode='ready_template',
    ready_id='video/ltx2_3_runexx_first_last_raw_video_guide',
    approach='first/last-frame image anchors plus full-length raw video frames into LTXVAddGuide',
    smoke_resolution='256x256x9_frames',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by PathchSageAttentionKJ auto mode for 4090-speed LTX Runexx validation.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use first/last anchors for travel endpoints.', 'Use raw full-length guide frames for VG-style guidance.', 'Keep IC-LoRA union-control modes on the separate IC-LoRA control template.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    runtime_note='Uses non-IC LTXVAddGuide; raw mode intentionally avoids LTXICLoRALoaderModelOnly and LTXAddVideoICLoRAGuide.',
    discord_signal='Matches Wan2GP LTX VG-style full-video guide without IC-LoRA.',
    provenance={'source_path': 'ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py', 'source_id': 'video/ltx2_3_runexx_first_last_raw_video_guide', 'source_type': 'ready_template', 'source_workflow_path': 'ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_first_last_raw_video_guide'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Sampling
    ksamplerselect = KSamplerSelect(_id='1', sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(_id='2', sampler_name='euler_cfg_pp')

    randomnoise = RandomNoise(
        _id='4',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    randomnoise_2 = RandomNoise(
        _id='5',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    # Inputs
    image, _ = LoadImage(_id='6', image='image (6).png')
    image_2, _ = LoadImage(_id='7', image='0 (13).webp')

    # Loaders
    vaeloader = VAELoader(_id='11', vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='12',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    unetloader = UNETLoader(_id='13', unet_name=UNET_NAME)

    dualcliploader = DualCLIPLoader(
        _id='14',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type='ltxv',
        device='default',
    )

    manualsigmas = ManualSigmas(
        _id='15',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(_id='16', sigmas='0.909375, 0.725, 0.421875, 0.0')
    intconstant = INTConstant(_id='17', value=81)
    intconstant_2 = INTConstant(_id='18', value=720)
    intconstant_3 = INTConstant(_id='19', value=1280)

    loadvideo = LoadVideo(
        _id='20',
        file=LTX_SMOKE_GUIDE_MP4,
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
    )

    # Conditioning
    negative = CLIPTextEncode(_id='21', text='', clip=dualcliploader)
    negative_2 = CLIPTextEncode(_id='22', text='', clip=dualcliploader)

    image_3, width, height, _ = ImageResizeKJv2(
        _id='23',
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='24',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='25',
        expression=A,
        variables='a,b',
        b=24.0,
        widget_0='a',
        a=intconstant,
    )

    images, _, _ = GetVideoComponents(_id='26', video=loadvideo)

    positive, negative_3 = LTXVConditioning(
        _id='28',
        frame_rate=24.0,
        negative=negative,
        positive=negative_2,
    )

    imagescaleby = ImageScaleBy(
        _id='29',
        upscale_method=LANCZOS,
        scale_by=0.5,
        image=image_3,
    )

    image_4, _, _, _ = ImageResizeKJv2(
        _id='30',
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=width,
        height=height,
        image=image_2,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        _id='31',
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='32',
        longer_edge=1536,
        images=image_3,
    )

    image_5, _, _, _ = ImageResizeKJv2(
        _id='33',
        upscale_method=LANCZOS,
        keep_proportion='stretch',
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=images,
    )

    width_4, height_4, _ = GetImageSize(_id='34', image=imagescaleby)
    ltxvpreprocess = LTXVPreprocess(_id='36', img_compression=18, image=image_4)
    ltxvchunkfeedforward = LTXVChunkFeedForward(_id='37', model=pathchsageattentionkj)

    ltxvpreprocess_2 = LTXVPreprocess(
        _id='38',
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='39',
        width=width_4,
        height=height_4,
        length=calc_int,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        _id='40',
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        _id='41',
        num_images='2',
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
        **{'num_images.index_1': 0, 'num_images.index_2': -1, 'num_images.strength_1': 1.0, 'num_images.strength_2': 1.0, 'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess},
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        _id='42',
        model=ltx2attentiontunerpatch,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='43',
        video_latent=ltxvimgtovideoinplacekj,
    )

    model, _ = Power_Lora_Loader_rgthree(
        _id='44',
        model=ltx2memoryefficientsageattentionpatch,
    )

    ltx2_nag = LTX2_NAG(
        _id='46',
        model=model,
        nag_cond_audio=negative_3,
        nag_cond_video=negative_3,
    )

    cfgguider = CFGGuider(
        _id='47',
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_3,
        positive=positive,
    )

    output, _ = SamplerCustomAdvanced(
        _id='48',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(_id='49', av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='50',
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    any_output, _, _, _, _ = VRAM_Debug(
        _id='51',
        unload_all_models=True,
        any_input=ltxvlatentupsampler,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        _id='52',
        num_images='1',
        latent=any_output,
        vae=vaeloader,
        **{'num_images.index_1': 0, 'num_images.strength_1': 1.0, 'num_images.image_1': resizeimagesbylongeredge},
    )

    positive_2, negative_4, latent = LTXVAddGuide(
        _id='53',
        image=image_5,
        latent=ltxvimgtovideoinplacekj_2,
        negative=negative_3,
        positive=positive,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(_id='54', video_latent=latent)

    positive_3, negative_5 = VibeComfyStripConditioningKeys(
        _id='55',
        negative=negative_4,
        positive=positive_2,
    )

    cfgguider_2 = CFGGuider(
        _id='56',
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_5,
        positive=positive_3,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='57',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_2, _ = LTXVSeparateAVLatent(_id='58', av_latent=output_2)

    _, _, latent_2 = LTXVCropGuides(
        _id='60',
        latent=video_latent_2,
        negative=negative_5,
        positive=positive_3,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        _id='61',
        temporal_size=4096,
        samples=latent_2,
        vae=vaeloader,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='62',
        frame_rate=24.0,
        filename_prefix='reigh_vibecomfy_ltx_raw_guide',
        format='video/h264-mp4',
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='reigh_vibecomfy_ltx_raw_guide')

