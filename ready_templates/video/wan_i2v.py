# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionEncode, CLIPVisionLoader, CreateVideo, KSampler, LoadImage, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader, WanImageToVideo


CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
CLIP_NAME_2 = 'clip_vision_h.safetensors'
DEFAULT_FPS = 16
DEFAULT_PROMPT = 'a cute anime girl with massive fennec ears and a big fluffy tail wearing a maid outfit turning around'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 987948718394761
GUIDE_STRENGTH = 6
UNET_NAME = 'wan2.1_i2v_480p_14B_fp16.safetensors'
VAE_NAME = 'wan_2.1_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='3', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='52', field='image', default='image_to_video_wan_start_image.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'fps': InputSpec(node='55', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='6', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='7', field='text', default=DEFAULT_PROMPT_2, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'wan2.1_i2v_480p_14B_fp16.safetensors', 'wan_2.1_vae.safetensors']},
    provenance={'source_path': 'ready_templates/sources/official/video/wan_i2v.json', 'source_id': 'video/wan_i2v', 'upstream_source_id': 'wan_i2v', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/video/wan_i2v.json', 'output_mode': 'ready_template', 'ready_id': 'video/wan_i2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    unetloader = UNETLoader(_id='37', unet_name=UNET_NAME, weight_dtype='default')
    cliploader = CLIPLoader(_id='38', clip_name=CLIP_NAME, type='wan', device='default')
    vaeloader = VAELoader(_id='39', vae_name=VAE_NAME)
    clipvisionloader = CLIPVisionLoader(_id='49', clip_name=CLIP_NAME_2)

    # Inputs
    image, _ = LoadImage(_id='52', image='image_to_video_wan_start_image.png')

    # Conditioning
    cliptextencode = CLIPTextEncode(_id='6', text=DEFAULT_PROMPT, clip=cliploader)
    cliptextencode_2 = CLIPTextEncode(_id='7', text=DEFAULT_PROMPT_2, clip=cliploader)

    clipvisionencode = CLIPVisionEncode(
        _id='51',
        crop='none',
        clip_vision=clipvisionloader,
        image=image,
    )

    modelsamplingsd3 = ModelSamplingSD3(_id='54', shift=8, model=unetloader)

    positive, negative, latent = WanImageToVideo(
        _id='50',
        width=512,
        height=512,
        length=33,
        batch_size=1,
        clip_vision_output=clipvisionencode,
        negative=cliptextencode_2,
        positive=cliptextencode,
        start_image=image,
        vae=vaeloader,
    )

    # Sampling
    ksampler = KSampler(
        _id='3',
        seed=DEFAULT_SEED,
        steps=20,
        cfg=GUIDE_STRENGTH,
        sampler_name='uni_pc',
        scheduler='simple',
        denoise=1,
        latent_image=latent,
        model=modelsamplingsd3,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(_id='8', samples=ksampler, vae=vaeloader)
    createvideo = CreateVideo(_id='55', fps=DEFAULT_FPS, images=vaedecode)

    # Outputs
    savevideo = SaveVideo(
        _id='56',
        filename_prefix='video/ComfyUI',
        format='auto',
        codec='auto',
        video=createvideo,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video/ComfyUI')
