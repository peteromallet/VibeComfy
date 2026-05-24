# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, LTXAVTextEncoderLoader, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SamplerEulerAncestral, SaveVideo, VAEDecodeTiled


CKPT_NAME = 'ltx-2.3-22b-distilled-fp8.safetensors'
DEFAULT_PROMPT = 'A cinematic first-last frame transition.'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
RESIZE_TYPE = 'scale dimensions'
RESIZE_TYPE_CROP = 'center'
SCALE_METHOD = 'nearest-exact'
TEXT_ENCODER_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'


MODELS = {
    'checkpoint': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors', sha256='d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2', hf_revision='1d756cd27fa11c0896c4dfee093cd1bf36c7f7a1', size_bytes=29531884062, subdir='checkpoints'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors', sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d', hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492', size_bytes=9447702218, subdir='text_encoders'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'LTXVAddGuide'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    approach='Official Lightricks distilled fp8 first/last frame route',
    smoke_resolution='256x256x5_frames',
    runtime_note='Patches named inputs for prompt, negative, seed, dimensions, frames, fps, first/last guide strengths, and first/last images.',
    discord_signal='Banodoco LTX notes point to the dedicated distilled fp8/quantized route for 4090 viability; dev+LoRA two-stage routes can OOM at 24GB.',
    ltx_best_practices=['Use the dedicated distilled fp8 checkpoint for first/last workflows on 24GB GPUs.', "Keep guide strengths in Wan2GP's 0..1 range.", 'Use tiled VAE decode for full-size app outputs.', 'Do not force the LTX2 memory-efficient Sage/Triton patch in the portable 4090 profile; LTX 2.3 guide masks must remain on the stable SDPA-compatible path unless a separate optimized profile proves the patch end-to-end.'],
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
        primitiveint_2 = raw_call('PrimitiveInt', '102', value=public('length', default=81))

        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            text_encoder=TEXT_ENCODER_NAME,
            ckpt_name=CKPT_NAME,
            device='default',
        )

        primitiveint_3 = raw_call('PrimitiveInt', '113', value=public('width', default=832))
        primitiveint_4 = raw_call('PrimitiveInt', '114', value=public('fps_int', default=16))
        samplereulerancestral = SamplerEulerAncestral(eta=0)

        manualsigmas = ManualSigmas(
            sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        primitivefloat = raw_call('PrimitiveFloat', '123', value=public('output_fps', default=16))
        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
        model, clip, vae = CheckpointLoaderSimple(ckpt_name=CKPT_NAME)

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            frames_number=primitiveint_2,
            frame_rate=primitiveint_4,
            audio_vae=ltxvaudiovaeloader,
        )

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

        ltxvpreprocess = LTXVPreprocess(img_compression=25, image=resizeimagemasknode_2)
        ltxvpreprocess_2 = LTXVPreprocess(img_compression=25, image=resizeimagemasknode)

        positive, negative = LTXVConditioning(
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
        )

        width, height, batch_size = GetImageSize(image=resizeimagemasknode)

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width,
            height=height,
            length=primitiveint_2,
        )

        positive_ltxv, negative_ltxv, latent = LTXVAddGuide(
            strength=public('first_strength', default=1.0),
            image=ltxvpreprocess_2,
            latent=emptyltxvlatentvideo,
            negative=negative,
            positive=positive,
            vae=vae,
        )

        positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVAddGuide(
            frame_idx=-1,
            strength=public('last_strength', default=1.0),
            image=ltxvpreprocess,
            latent=latent,
            negative=negative_ltxv,
            positive=positive_ltxv,
            vae=vae,
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=model,
            negative=negative_ltxv_2,
            positive=positive_ltxv_2,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=ltxvemptylatentaudio,
            video_latent=latent_ltxv,
        )

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=samplereulerancestral,
            sigmas=manualsigmas,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=denoised_output)

        positive_ltxv_3, negative_ltxv_3, latent_ltxv_2 = LTXVCropGuides(
            latent=video_latent,
            negative=negative_ltxv_2,
            positive=positive_ltxv_2,
        )

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            audio_vae=ltxvaudiovaeloader,
            samples=audio_latent,
        )

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            tile_size=768,
            temporal_size=4096,
            temporal_overlap=64,
            samples=latent_ltxv_2,
            vae=vae,
        )

        createvideo = CreateVideo(
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=vaedecodetiled,
        )

        # Outputs
        savevideo = SaveVideo(filename_prefix='output', video=createvideo)


        wf.register_input('model', '125', 'ckpt_name', CKPT_NAME)
        return wf.finalize({}, filename_prefix='output', spec=OUTPUT_SPEC)

