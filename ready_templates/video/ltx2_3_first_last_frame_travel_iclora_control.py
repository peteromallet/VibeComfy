# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetVideoComponents, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, SamplerCustomAdvanced, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16.safetensors'
BBOX_DETECTOR_NAME = 'yolox_l.onnx'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles'
DEFAULT_PROMPT_2 = 'A cinematic first-to-last-frame travel shot with smooth continuous camera motion, coherent subject motion, realistic lighting, and natural temporal consistency.'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEPTH_ANYTHING_NAME = 'depth_anything_v2_vits_fp32.safetensors'
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LANCZOS = 'lanczos'
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
LORA_NAME_2 = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors'
NEAREST_EXACT = 'nearest-exact'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
STRETCH = 'stretch'
UNET_NAME = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
VAE_TAESD_NAME = 'taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', sha256='911d59bb4cb7708179c9a0045ea0fe41212ecfb77aed3a02702b7c0a8274911f', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=2312149072, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', sha256='01ea62d09bc139f95c5dee7b5c062ad6a3e6cd8be910a1983ac02e7eb5b8ee3b', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=1452258578, subdir='vae'),
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', sha256='5bc10fa4adecf99dda132d916e23048cbd56797702c5fa50eb5d2079048a38c3', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=364855188, subdir='checkpoints'),
    'vae_2': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', sha256='f0773b4e3e57318e6aa4dd4a35e1d16213a5f160fbc0376163f06888bbcbe246', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=23531296, subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', sha256='0a1d7aac2b338e8ec7e832149f1dcf11c9323272482b1cca0673d229702370f0', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=25226571988, subdir='diffusion_models'),
    'lora': ModelAsset(filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', sha256='31e0c0195fb841bf31af78e8b60858f489e87ddcea4a5239abc80943da65e3ac', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=2741024390, subdir='loras'),
    'depth_anything_v2_vits_fp32': ModelAsset(url='https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vits_fp32.safetensors', sha256='cb2d537ed6e45921f27f61f0b605dcfafb6b97c7d1a15e551280bdd867605c86', hf_revision='5aa7ab578df757d94c743998b157a0204ff29215', size_bytes=99165460, subdir='depthanything'),
    'yolox_l': ModelAsset(url='https://huggingface.co/yzd-v/DWPose/resolve/main/yolox_l.onnx', target_path='custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx', sha256='7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411', hf_revision='1a7144101628d69ee7a3768d1ee3a094070dc388', size_bytes=216746733, subdir='controlnet_aux'),
    'dw_ll_ucoco_384_bs5_torchscript': ModelAsset(url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt', target_path='custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt', sha256='d86a0b2b59fddc0901a7076e9f59c9f8602602133ed72511c693fd11eea23d91', hf_revision='359d662a9b33b73f6d0f21732baf8845f17bb4be', size_bytes=135059124, subdir='controlnet_aux'),
}


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='3', field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node='7', field='ckpt_name', default=AUDIO_VAE_NAME),
    'prompt': InputSpec(node='20', field='text', default=DEFAULT_PROMPT),
    'image': InputSpec(node='5', field='image', default='example.png', aliases=('input_image',)),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_control_video',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'comfyui_controlnet_aux']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor', 'DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x9_frames',
    approach='first/last-frame image anchors plus full-length raw/pose/depth/canny IC-LoRA guide branches',
    runtime_note='Default guide branch is Canny. Patch node 5012 input image to select raw, pose, or depth branches.',
    discord_signal='Combines recurring LTX first/last travel and full-length control-guide workflows.',
    ltx_best_practices=['Use first/last anchors for travel endpoints.', 'Use a full-length guide video with IC-LoRA union-control conditioning.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loader settings.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)

    # Inputs
    image, _ = LoadImage(image='example.png')
    image_load, _ = LoadImage(image='egyptian_queen.png')
    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=AUDIO_VAE_NAME)

    # Loaders
    vaeloader = VAELoader(vae_name=VAE_TAESD_NAME)
    vaeloader_2 = VAELoader(vae_name=VIDEO_VAE_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device='default',
    )

    manualsigmas = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    intconstant = INTConstant(value=9)
    intconstant_2 = INTConstant(value=256)
    intconstant_3 = INTConstant(value=256)
    loadvideo = LoadVideo(file='ltx_smoke_guide.mp4', video='ltx_smoke_guide.mp4')

    downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
        model=DEPTH_ANYTHING_NAME,
        precision='fp32',
    )

    ltxfloattoint = LTXFloatToInt(rounding=0, a=8.0)

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=dualcliploader)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=intconstant_3,
        height=intconstant_2,
        length=intconstant,
    )

    image_image, _, _, _ = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image,
    )

    image_image_2, _, _, _ = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image_load,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    ltx2_nag = LTX2_NAG(model=unetloader)
    images, _, _ = GetVideoComponents(video=loadvideo)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=intconstant,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    positive, negative = LTXVConditioning(
        frame_rate=8.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image_2)

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='disabled',
        model=loraloadermodelonly,
    )

    ltxvpreprocess_2 = LTXVPreprocess(img_compression=18, image=image_image)

    image_image_3, _, _, _ = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=STRETCH,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=images,
    )

    dwpreprocessor = raw_call('DWPreprocessor', '4986',
        detect_hand='enable',
        detect_body='enable',
        detect_face='enable',
        resolution=256,
        bbox_detector=BBOX_DETECTOR_NAME,
        pose_estimator=POSE_ESTIMATOR_NAME,
        scale_stick_for_xinsr_cn='disable',
        image=image_image_3,
    )

    cannyedgepreprocessor = raw_call('CannyEdgePreprocessor', '4991',
        low_threshold=92,
        resolution=256,
        image=image_image_3,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='2',
        latent=emptyltxvlatentvideo,
        vae=vaeloader_2,
        **{'num_images.index_1': 0, 'num_images.index_2': -1, 'num_images.strength_1': 0.8, 'num_images.strength_2': 0.8, 'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess},
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

    depthanything_v2 = DepthAnything_V2(
        da_model=downloadandloaddepthanythingv2model,
        images=image_image_3,
    )

    ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=STRETCH,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image_image_3,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    image_image_5, _, _, _ = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=STRETCH,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=cannyedgepreprocessor,
    )

    ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=STRETCH,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=dwpreprocessor,
    )

    ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=STRETCH,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=depthanything_v2,
    )

    model, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        lora_name=LORA_NAME_2,
        model=ltx2attentiontunerpatch,
    )

    positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
        crop='center',
        use_tiled_encode='disabled',
        tile_size=128,
        tile_overlap=32,
        image=image_image_5,
        latent=ltxvimgtovideoinplacekj,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vaeloader_2,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=model,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=latent,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=video_latent,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    _, _, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=latent_ltxv,
        vae=vaeloader_2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        filename_prefix='reigh_vibecomfy_ltx_control_first_last',
        format='video/h264-mp4',
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='reigh_vibecomfy_ltx_control_first_last')

