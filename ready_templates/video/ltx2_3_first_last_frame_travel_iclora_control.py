# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetVideoComponents, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, SamplerCustomAdvanced, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


BBOX_DETECTOR_NAME = 'yolox_l.onnx'
CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles'
DEFAULT_PROMPT_2 = 'A cinematic first-to-last-frame travel shot with smooth continuous camera motion, coherent subject motion, realistic lighting, and natural temporal consistency.'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEVICE = 'cpu'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
GUIDE_STRENGTH_3 = 1
KEEP_PROPORTION = 'crop'
KEEP_PROPORTION_2 = 'stretch'
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
LORA_NAME_2 = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors'
MODEL_NAME = 'depth_anything_v2_vits_fp32.safetensors'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
UNET_NAME = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UPSCALE_METHOD = 'nearest-exact'
UPSCALE_METHOD_2 = 'lanczos'
VAE_NAME = 'taeltx2_3.safetensors'
VAE_NAME_2 = 'LTX23_video_vae_bf16.safetensors'


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


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_control_video',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'comfyui_controlnet_aux']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor', 'DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x9_frames',
    approach='first/last-frame image anchors plus full-length raw/pose/depth/canny IC-LoRA guide branches',
    runtime_note='Default guide branch is Canny. Patch node 5012 input image to select raw, pose, or depth branches.',
    discord_signal='Combines recurring LTX first/last travel and full-length control-guide workflows.',
    ltx_best_practices=['Use first/last anchors for travel endpoints.', 'Use a full-length guide video with IC-LoRA union-control conditioning.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loader settings.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'manual'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')

        randomnoise = RandomNoise(
            noise_seed=public('seed', default=DEFAULT_SEED),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        randomnoise_2 = RandomNoise(
            noise_seed=public('seed_refine', default=DEFAULT_SEED_2),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        # Inputs
        image, mask = LoadImage(
            image=public('start_image', default='example.png', aliases=('image', 'input_image')),
        )

        image_load, mask_load = LoadImage(
            image=public('end_image', default='egyptian_queen.png'),
        )

        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
        vaeloader = VAELoader(vae_name=VAE_NAME)
        vaeloader_2 = VAELoader(vae_name=VAE_NAME_2)
        unetloader = UNETLoader(unet_name=UNET_NAME)

        dualcliploader = DualCLIPLoader(
            clip_name1=CLIP_NAME,
            clip_name2=CLIP_NAME_2,
            type_='ltxv',
            device='default',
        )

        manualsigmas = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
        primitivefloat = raw_call('PrimitiveFloat', '2076', value=public('output_fps', default=8))
        intconstant = INTConstant(value=public('length', default=9))
        intconstant_2 = INTConstant(value=public('height', default=256))
        intconstant_3 = INTConstant(value=public('width', default=256))
        primitivefloat_2 = raw_call('PrimitiveFloat', '2108', value=0.8)
        primitivefloat_3 = raw_call('PrimitiveFloat', '2110', value=0.8)

        loadvideo = LoadVideo(
            file='ltx_smoke_guide.mp4',
            video=public('control_video', default='ltx_smoke_guide.mp4'),
        )

        downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
            model=MODEL_NAME,
            precision='fp32',
        )

        primitivestring = raw_call('PrimitiveString', '6000', value=public('control_mode', default='canny'))

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('negative_prompt', default=DEFAULT_PROMPT),
            clip=dualcliploader,
        )

        cliptextencode_2 = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT_2),
            clip=dualcliploader,
        )

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=intconstant_3,
            height=intconstant_2,
            length=intconstant,
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

        image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
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
        images, audio, fps = GetVideoComponents(video=loadvideo)
        ltxfloattoint = LTXFloatToInt(rounding=0, a=primitivefloat)

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            frames_number=intconstant,
            frame_rate=ltxfloattoint,
            audio_vae=ltxvaudiovaeloader,
        )

        positive, negative = LTXVConditioning(
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
        )

        ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image_2)

        pathchsageattentionkj = PathchSageAttentionKJ(
            sage_attention='disabled',
            model=loraloadermodelonly,
        )

        ltxvpreprocess_2 = LTXVPreprocess(img_compression=18, image=image_image)

        image_image_3, width_image_2, height_image_2, mask_image_3 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
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
            high_threshold=200,
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
            **{'num_images.index_1': 0, 'num_images.index_2': -1, 'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess, 'num_images.strength_1': primitivefloat_3, 'num_images.strength_2': primitivefloat_2},
        )

        ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

        depthanything_v2 = DepthAnything_V2(
            da_model=downloadandloaddepthanythingv2model,
            images=image_image_3,
        )

        image_image_4, width_image_3, height_image_3, mask_image_4 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=image_image_3,
        )

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )

        image_image_5, width_image_4, height_image_4, mask_image_5 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=cannyedgepreprocessor,
        )

        image_image_6, width_image_5, height_image_5, mask_image_6 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=dwpreprocessor,
        )

        image_image_7, width_image_6, height_image_6, mask_image_7 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=depthanything_v2,
        )

        model, latent_downscale_factor = LTXICLoRALoaderModelOnly(
            lora_name=LORA_NAME_2,
            strength_model=public('ic_lora_strength', default=GUIDE_STRENGTH_3),
            model=ltx2attentiontunerpatch,
        )

        positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
            strength=public('guide_strength', default=1),
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

        output, denoised_output = SamplerCustomAdvanced(
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

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
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

        positive_ltxv, negative_ltxv, latent_ltxv = LTXVCropGuides(
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
            frame_rate=primitivefloat,
            images=vaedecodetiled,
        )


        wf.register_input('model', '7', 'ckpt_name', CKPT_NAME)
        wf.register_input('ic_lora_filename', '6025', 'lora_name', LORA_NAME_2)
        return wf.finalize({}, filename_prefix='reigh_vibecomfy_ltx_control_first_last', spec=OUTPUT_SPEC)

