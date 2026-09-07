# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, ImagePadForOutpaint, ImageScaleBy, ImageStitch, KSamplerSelect, LTXVAddGuide, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2SamplingPreviewOverride, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
LORA_NAME = 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
NEAREST_EXACT = 'nearest-exact'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'


PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node='8fa4f93a:2002', field='switch', default=True),
    'lastframe_strength': InputSpec(node='2152', field='strength', default=1.0),
    'firstframe_strength': InputSpec(node='2105', field='num_images.strength_1', default=0.5),
    'seed': InputSpec(node='14', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='45', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'prompt': InputSpec(node='11', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'LTXVAddGuide', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json', 'source_id': 'video/ltx2_3_runexx_first_last_frame', 'upstream_source_id': 'LTX-2.3_FLF2V_First_Last_Frame', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_first_last_frame'},
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch / PathchSageAttentionKJ for memory-efficient attention on compatible GPUs.', 'source': 'SageAttention-ada'}],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    enabled,
    prompt,
):
    """PROMPT ENHANCER - single-image variant.

    Materialized from subgraph 8fa4f93a-67ee-463f-ba43-249580c0bfb1 in ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json.
    # vibecomfy source hash: sha256:0f8159ebf8aa4a4c3a5e6b80f1b2ee0f64d219acd682c3d5e21076202df94076
    Inner nodes: StringConcatenate, ComfySwitchNode, TextGenerateLTX2Prompt.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    comfyswitchnode = ComfySwitchNode(
        _id='8fa4f93a:2002',
        switch=enabled,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return comfyswitchnode


def frames_split_view(
    *,
    input,
    input_2,
):
    """Frames split view.

    Materialized from subgraph 19e3f7e8-881c-4a61-a360-1c463734043a in ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json.
    # vibecomfy source hash: sha256:0be36a8fa15cc208b8fd3aef62fc7f9487e01520636775ef7158656ed4f367c0
    Inner nodes: ResizeImageMaskNodex2, ImagePadForOutpaintx2, ImageStitch.
    """

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=input,
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=input_2,
    )

    image, _ = ImagePadForOutpaint(
        left=16,
        top=16,
        right=16,
        bottom=16,
        feathering=0,
        image=resizeimagemasknode,
    )

    image_2, _ = ImagePadForOutpaint(
        left=16,
        top=16,
        right=16,
        bottom=16,
        feathering=0,
        image=resizeimagemasknode_2,
    )

    imagestitch = ImageStitch(image1=image_2, image2=image)

    return imagestitch

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Sampling
    ksamplerselect = KSamplerSelect(_id='1', sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(_id='4', sampler_name='euler_cfg_pp')

    randomnoise = RandomNoise(
        _id='14',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    randomnoise_2 = RandomNoise(
        _id='15',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    # Inputs
    image_2, _ = LoadImage(_id='45', image='image (6).png')
    image_3, _ = LoadImage(_id='47', image='0 (13).webp')

    # Loaders
    vaeloader = VAELoader(_id='180', vae_name=VAE_TAESD_NAME)
    vaeloader_2 = VAELoader(_id='181', vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='182',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    unetloader = UNETLoader(_id='187', unet_name=UNET_NAME)

    dualcliploader = DualCLIPLoader(
        _id='190',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type='ltxv',
        device='default',
    )

    manualsigmas = ManualSigmas(
        _id='215',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(_id='216', sigmas='0.85, 0.7250, 0.4219, 0.0')
    intconstant = INTConstant(_id='2078', value=10)
    intconstant_2 = INTConstant(_id='2079', value=720)
    intconstant_3 = INTConstant(_id='2080', value=1280)

    # Conditioning
    cliptextencode = CLIPTextEncode(_id='11', text=DEFAULT_PROMPT, clip=dualcliploader)

    image, width_2, height_2, _ = ImageResizeKJv2(
        _id='44',
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image_2,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='186',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='2077',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        b=24.0,
        a=intconstant,
    )

    imagescaleby = ImageScaleBy(
        _id='26',
        upscale_method='lanczos',
        scale_by=0.5,
        image=image,
    )

    image_4, _, _, _ = ImageResizeKJv2(
        _id='48',
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=width_2,
        height=height_2,
        image=image_3,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        _id='226',
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        _id='2083',
        longer_edge=1536,
        images=image,
    )

    width, height, _ = GetImageSize(_id='28', image=imagescaleby)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='49',
        longer_edge=1536,
        images=image_4,
    )

    ltxvpreprocess = LTXVPreprocess(_id='50', img_compression=18, image=image_4)

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        _id='227',
        model=pathchsageattentionkj,
    )

    ltxvpreprocess_2 = LTXVPreprocess(
        _id='2084',
        img_compression=18,
        image=resizeimagesbylongeredge_2,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='32',
        width=width,
        height=height,
        length=calc_int,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(
        _id='228',
        model=ltx2memoryefficientsageattentionpatch,
    )

    frames_split_view_result = frames_split_view(
        input=resizeimagesbylongeredge,
        input_2=resizeimagesbylongeredge_2,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        _id='210',
        num_images='2',
        strength_1=0.7,
        index_1=0.7,
        widget_3=0,
        widget_4=-1,
        latent=emptyltxvlatentvideo,
        vae=vaeloader_2,
        **{'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess},
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        _id='229',
        model=ltxvchunkfeedforward,
    )

    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=frames_split_view_result,
        enabled=True,
        prompt="Make this image come alive with cinematic motion, smooth animation. \n\nA foggy night in in 1700's Amsterdam. The fog is thick and swirling, illuminating by streetlights. we see a bridge over a canal, cobblestone streets, canal buildings lining the canal The vibe is uneasy, moody, slightly dangerous.\n\nThe camera crane down high angle to a low angle ending with a close up of a vampire's hand with leather gloves on holding a walking cane.  Single continuous camera shot ",
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='16',
        text=prompt_enhancer_result,
        clip=dualcliploader,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='24',
        video_latent=ltxvimgtovideoinplacekj,
    )

    model, _ = Power_Lora_Loader_rgthree(_id='2107', model=ltx2attentiontunerpatch)

    positive, negative = LTXVConditioning(
        _id='10',
        frame_rate=24.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    ltx2samplingpreviewoverride = LTX2SamplingPreviewOverride(
        _id='198',
        model=model,
        vae=vaeloader,
    )

    ltx2_nag = LTX2_NAG(
        _id='197',
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    cfgguider = CFGGuider(
        _id='8',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        _id='36',
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    output, _ = SamplerCustomAdvanced(
        _id='13',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(_id='18', av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='25',
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader_2,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        _id='2105',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vaeloader_2,
        **{'num_images.strength_1': 0.5, 'num_images.image_1': resizeimagesbylongeredge_2},
    )

    positive_2, negative_2, latent = LTXVAddGuide(
        _id='2152',
        frame_idx=-1,
        strength=1.0,
        image=resizeimagesbylongeredge,
        latent=ltxvimgtovideoinplacekj_2,
        negative=negative,
        positive=positive,
        vae=vaeloader_2,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(_id='34', video_latent=latent)

    output_2, _ = SamplerCustomAdvanced(
        _id='21',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_2, _ = LTXVSeparateAVLatent(_id='146', av_latent=output_2)

    _, _, latent_2 = LTXVCropGuides(
        _id='2156',
        latent=video_latent_2,
        negative=negative_2,
        positive=positive_2,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        _id='149',
        temporal_size=4096,
        samples=latent_2,
        vae=vaeloader_2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='43',
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_01574-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_01574.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_01574-audio.mp4'}},
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

