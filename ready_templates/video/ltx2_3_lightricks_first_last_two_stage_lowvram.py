# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.kjnodes import LTX2MemoryEfficientSageAttentionPatch, VRAM_Debug
from vibecomfy.nodes.ltxvideo import LTXVTiledVAEDecode, LowVRAMCheckpointLoader


CKPT_NAME = 'ltx-2.3-22b-distilled-fp8.safetensors'
DEFAULT_PROMPT = 'A cinematic first-last frame transition.'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
RESIZE_TYPE = 'scale dimensions'
RESIZE_TYPE_CROP = 'center'
SCALE_METHOD = 'nearest-exact'
TEXT_ENCODER_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'


MODELS = {
    'checkpoint': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors', sha256='d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2', hf_revision='1d756cd27fa11c0896c4dfee093cd1bf36c7f7a1', size_bytes=29531884062, subdir='checkpoints'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors', sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d', hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492', size_bytes=9447702218, subdir='text_encoders'),
    'upscale_model': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors', sha256='5f416311fa8172b65af67530758964708d29a317b830d689a51143b7f91913ed', hf_revision='76730e634e70a28f4e8d51f5e29c08e40e2d8e74', size_bytes=995743560, subdir='latent_upscale_models'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'LTXVAddGuide'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='two-stage first/last-frame route using LowVRAMCheckpointLoader',
    runtime_note="Stage 1 uses Wan2GP's half-resolution long sigma schedule; the latent is spatially upsampled before stage 2 reapplies first/last guides and uses the Wan2GP refine sigma schedule.",
    discord_signal='Use dedicated distilled fp8 + low-VRAM loaders on 24GB GPUs.',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch for the two-stage low-VRAM LTX route.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use LowVRAMCheckpointLoader for 4090 viability.', 'Use the dedicated distilled fp8 checkpoint rather than the dev checkpoint plus LoRA when possible.', "Preserve Wan2GP's two-stage sigma structure for parity checks."],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(
            image=public('first_image', default='example_start.png', aliases=('image', 'input_image')),
        )

        image_load, mask_load = LoadImage(
            image=public('last_image', default='example_end.png'),
        )

        primitiveint = raw_call('PrimitiveInt', '98', value=public('height', default=480))
        randomnoise = RandomNoise(noise_seed=public('seed', default=DEFAULT_SEED))

        randomnoise_2 = RandomNoise(
            noise_seed=public('seed_last', default=DEFAULT_SEED),
        )

        primitiveint_2 = raw_call('PrimitiveInt', '102', value=public('length', default=81))

        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            text_encoder=TEXT_ENCODER_NAME,
            ckpt_name=CKPT_NAME,
            device='default',
        )

        primitiveint_3 = raw_call('PrimitiveInt', '113', value=public('width', default=832))
        primitiveint_4 = raw_call('PrimitiveInt', '114', value=public('fps_int', default=16))
        primitivefloat = raw_call('PrimitiveFloat', '123', value=public('output_fps', default=16))
        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
        model, clip, vae = LowVRAMCheckpointLoader(ckpt_name=CKPT_NAME)
        latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)
        primitiveint_5 = raw_call('PrimitiveInt', '981', value=public('stage1_height', default=480))
        primitiveint_6 = raw_call('PrimitiveInt', '1131', value=public('stage1_width', default=832))
        ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

        manualsigmas = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
        manualsigmas_2 = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('negative_prompt', default='blurry, distorted, low quality'),
            clip=ltxavtextencoderloader,
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=image,
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint, 'resize_type.width': primitiveint_3},
        )

        resizeimagemasknode_2 = ResizeImageMaskNode(
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=image_load,
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint, 'resize_type.width': primitiveint_3},
        )

        cliptextencode_2 = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=ltxavtextencoderloader,
        )

        ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
            model=model,
        )

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            frames_number=primitiveint_2,
            frame_rate=primitiveint_4,
            audio_vae=ltxvaudiovaeloader,
        )

        resizeimagemasknode_3 = ResizeImageMaskNode(
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=image,
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint_5, 'resize_type.width': primitiveint_6},
        )

        resizeimagemasknode_4 = ResizeImageMaskNode(
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=image_load,
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint_5, 'resize_type.width': primitiveint_6},
        )

        ltxvpreprocess = LTXVPreprocess(img_compression=25, image=resizeimagemasknode_2)
        ltxvpreprocess_2 = LTXVPreprocess(img_compression=25, image=resizeimagemasknode)

        positive, negative = LTXVConditioning(
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
        )

        width, height, batch_size = GetImageSize(image=resizeimagemasknode_3)

        ltxvpreprocess_3 = LTXVPreprocess(
            img_compression=25,
            image=resizeimagemasknode_4,
        )

        ltxvpreprocess_4 = LTXVPreprocess(
            img_compression=25,
            image=resizeimagemasknode_3,
        )

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width,
            height=height,
            length=primitiveint_2,
        )

        positive_ltxv, negative_ltxv, latent = LTXVAddGuide(
            strength=public('first_strength', default=1.0),
            image=ltxvpreprocess_4,
            latent=emptyltxvlatentvideo,
            negative=negative,
            positive=positive,
            vae=vae,
        )

        positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVAddGuide(
            frame_idx=-1,
            strength=public('last_strength', default=1.0),
            image=ltxvpreprocess_3,
            latent=latent,
            negative=negative_ltxv,
            positive=positive_ltxv,
            vae=vae,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=ltxvemptylatentaudio,
            video_latent=latent_ltxv,
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=ltx2memoryefficientsageattentionpatch,
            negative=negative_ltxv_2,
            positive=positive_ltxv_2,
        )

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=denoised_output)

        ltxvlatentupsampler = LTXVLatentUpsampler(
            samples=video_latent,
            upscale_model=latentupscalemodelloader,
            vae=vae,
        )

        any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
            unload_all_models=True,
            any_input=ltxvlatentupsampler,
        )

        positive_ltxv_3, negative_ltxv_3, latent_ltxv_2 = LTXVCropGuides(
            latent=any_output,
            negative=negative_ltxv_2,
            positive=positive_ltxv_2,
        )

        positive_ltxv_4, negative_ltxv_4, latent_ltxv_3 = LTXVAddGuide(
            strength=public('first_frame_strength', default=1.0),
            image=ltxvpreprocess_2,
            latent=latent_ltxv_2,
            negative=negative_ltxv_3,
            positive=positive_ltxv_3,
            vae=vae,
        )

        positive_ltxv_5, negative_ltxv_5, latent_ltxv_4 = LTXVAddGuide(
            frame_idx=-1,
            strength=public('last_frame_strength', default=1.0),
            image=ltxvpreprocess,
            latent=latent_ltxv_3,
            negative=negative_ltxv_4,
            positive=positive_ltxv_4,
            vae=vae,
        )

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            audio_latent=audio_latent,
            video_latent=latent_ltxv_4,
        )

        cfgguider_2 = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=ltx2memoryefficientsageattentionpatch,
            negative=negative_ltxv_5,
            positive=positive_ltxv_5,
        )

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
        )

        video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
            av_latent=denoised_output_sampler,
        )

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            audio_vae=ltxvaudiovaeloader,
            samples=audio_latent_ltxv,
        )

        positive_ltxv_6, negative_ltxv_6, latent_ltxv_5 = LTXVCropGuides(
            latent=video_latent_ltxv,
            negative=negative_ltxv_5,
            positive=positive_ltxv_5,
        )

        ltxvtiledvaedecode = LTXVTiledVAEDecode(
            horizontal_tiles=2,
            vertical_tiles=2,
            overlap=6,
            latents=latent_ltxv_5,
            vae=vae,
        )

        createvideo = CreateVideo(
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=ltxvtiledvaedecode,
        )

        # Outputs
        savevideo = SaveVideo(filename_prefix='output', video=createvideo)


        wf.register_input('model', model.node_id, 'ckpt_name', CKPT_NAME)
        return wf.finalize({}, filename_prefix='output', spec=OUTPUT_SPEC)

