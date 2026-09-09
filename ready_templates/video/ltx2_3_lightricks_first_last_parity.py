# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, LTXAVTextEncoderLoader, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SamplerEulerAncestral, SaveVideo, VAEDecodeTiled


CENTER = 'center'
CKPT_NAME = 'ltx-2.3-22b-distilled-fp8.safetensors'
DEFAULT_FPS = 16.0
DEFAULT_FRAMES = 81
DEFAULT_PROMPT = 'A cinematic first-last frame transition.'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
NEAREST_EXACT = 'nearest-exact'
SCALE_DIMENSIONS = 'scale dimensions'
TEXT_ENCODER_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'


MODELS = {
    'checkpoint': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors', sha256='d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2', hf_revision='1d756cd27fa11c0896c4dfee093cd1bf36c7f7a1', size_bytes=29531884062, subdir='checkpoints'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors', sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d', hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492', size_bytes=9447702218, subdir='text_encoders'),
}


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='1', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='3', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'frames': InputSpec(node='18', field='length', default=DEFAULT_FRAMES, type='INT'),
    'fps': InputSpec(node='28', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='13', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'LTXVAddGuide'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    source_path='ready_templates/video/ltx2_3_lightricks_first_last_parity.py',
    source_id='video/ltx2_3_lightricks_first_last_parity',
    source_type='ready_template',
    source_workflow_path='ready_templates/video/ltx2_3_lightricks_first_last_parity.py',
    output_mode='ready_template',
    ready_id='video/ltx2_3_lightricks_first_last_parity',
    approach='Official Lightricks distilled fp8 first/last frame route',
    smoke_resolution='256x256x5_frames',
    runtime_note='Exposes the first image, positive prompt, seed, frames, fps, and model selection for the distilled first/last route.',
    discord_signal='Banodoco LTX notes point to the dedicated distilled fp8/quantized route for 4090 viability; dev+LoRA two-stage routes can OOM at 24GB.',
    ltx_best_practices=['Use the dedicated distilled fp8 checkpoint for first/last workflows on 24GB GPUs.', "Keep guide strengths in Wan2GP's 0..1 range.", 'Use tiled VAE decode for full-size app outputs.', 'Do not force the LTX2 memory-efficient Sage/Triton patch in the portable 4090 profile; LTX 2.3 guide masks must remain on the stable SDPA-compatible path unless a separate optimized profile proves the patch end-to-end.'],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_path': 'ready_templates/video/ltx2_3_lightricks_first_last_parity.py', 'source_id': 'video/ltx2_3_lightricks_first_last_parity', 'source_type': 'ready_template', 'source_workflow_path': 'ready_templates/video/ltx2_3_lightricks_first_last_parity.py', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_first_last_parity'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='1', image='example_start.png')
    image_2, _ = LoadImage(_id='2', image='example_end.png')
    randomnoise = RandomNoise(_id='3', noise_seed=DEFAULT_SEED)

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        _id='4',
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    samplereulerancestral = SamplerEulerAncestral(_id='5', eta=0)

    manualsigmas = ManualSigmas(
        _id='6',
        sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='7', ckpt_name=CKPT_NAME)

    # Loaders
    model, _, vae = CheckpointLoaderSimple(_id='8', ckpt_name=CKPT_NAME)

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='10',
        text='blurry, distorted, low quality',
        clip=ltxavtextencoderloader,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='11',
        resize_type=SCALE_DIMENSIONS,
        scale_method=NEAREST_EXACT,
        input=image,
        **{'resize_type.crop': CENTER, 'resize_type.height': 480, 'resize_type.width': 832},
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        _id='12',
        resize_type=SCALE_DIMENSIONS,
        scale_method=NEAREST_EXACT,
        input=image_2,
        **{'resize_type.crop': CENTER, 'resize_type.height': 480, 'resize_type.width': 832},
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='13',
        text=DEFAULT_PROMPT,
        clip=ltxavtextencoderloader,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='14',
        img_compression=25,
        image=resizeimagemasknode_2,
    )

    ltxvpreprocess_2 = LTXVPreprocess(
        _id='15',
        img_compression=25,
        image=resizeimagemasknode,
    )

    positive, negative = LTXVConditioning(
        _id='16',
        frame_rate=16.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    width, height, _ = GetImageSize(_id='17', image=resizeimagemasknode)

    # Sampling
    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='18',
        length=DEFAULT_FRAMES,
        width=width,
        height=height,
    )

    positive_2, negative_2, latent = LTXVAddGuide(
        _id='19',
        image=ltxvpreprocess_2,
        latent=emptyltxvlatentvideo,
        negative=negative,
        positive=positive,
        vae=vae,
    )

    positive_3, negative_3, latent_2 = LTXVAddGuide(
        _id='20',
        frame_idx=-1,
        image=ltxvpreprocess,
        latent=latent,
        negative=negative_2,
        positive=positive_2,
        vae=vae,
    )

    cfgguider = CFGGuider(
        _id='21',
        cfg=GUIDE_STRENGTH,
        model=model,
        negative=negative_3,
        positive=positive_3,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(_id='22', video_latent=latent_2)

    _, denoised_output = SamplerCustomAdvanced(
        _id='23',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=samplereulerancestral,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(
        _id='24',
        av_latent=denoised_output,
    )

    _, _, latent_3 = LTXVCropGuides(
        _id='25',
        latent=video_latent,
        negative=negative_3,
        positive=positive_3,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='26',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        _id='27',
        tile_size=768,
        temporal_size=4096,
        temporal_overlap=64,
        samples=latent_3,
        vae=vae,
    )

    createvideo = CreateVideo(
        _id='28',
        fps=DEFAULT_FPS,
        audio=ltxvaudiovaedecode,
        images=vaedecodetiled,
    )

    # Outputs
    savevideo = SaveVideo(_id='29', filename_prefix='output', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

