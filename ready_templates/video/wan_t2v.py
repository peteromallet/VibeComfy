# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CreateVideo, EmptyHunyuanLatentVideo, KSampler, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
DEFAULT_FPS = 16
DEFAULT_FRAMES = 33
DEFAULT_PROMPT = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT_2 = 'a fox moving quickly in a beautiful winter scenery nature trees mountains daytime tracking camera'
DEFAULT_SEED = 82628696717253
GUIDE_STRENGTH = 6
UNET_NAME = 'wan2.1_t2v_1.3B_fp16.safetensors'
VAE_NAME = 'wan_2.1_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='3', field='seed', default=DEFAULT_SEED, type='INT'),
    'width': InputSpec(node='40', field='width', default=832, type='INT'),
    'height': InputSpec(node='40', field='height', default=480, type='INT', omit_if_schema_default=True),
    'frames': InputSpec(node='40', field='length', default=DEFAULT_FRAMES, type='INT'),
    'fps': InputSpec(node='49', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='6', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='7', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'wan2.1_t2v_1.3B_fp16.safetensors', 'wan_2.1_vae.safetensors']},
    provenance={'source_path': 'ready_templates/sources/official/video/wan_t2v.json', 'source_id': 'wan_t2v', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/video/wan_t2v.json', 'output_mode': 'ready_template', 'ready_id': 'video/wan_t2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    unetloader = UNETLoader(_id='37', unet_name=UNET_NAME)
    cliploader = CLIPLoader(_id='38', clip_name=CLIP_NAME, type_='wan')
    vaeloader = VAELoader(_id='39', vae_name=VAE_NAME)

    # Sampling
    emptyhunyuanlatentvideo = EmptyHunyuanLatentVideo(
        _id='40',
        width=832,
        length=DEFAULT_FRAMES,
    )

    # Conditioning
    positive = CLIPTextEncode(_id='6', text=DEFAULT_PROMPT_2, clip=cliploader)
    negative = CLIPTextEncode(_id='7', text=DEFAULT_PROMPT, clip=cliploader)
    modelsamplingsd3 = ModelSamplingSD3(_id='48', shift=8, model=unetloader)

    ksampler = KSampler(
        _id='3',
        seed=DEFAULT_SEED,
        steps=30,
        cfg=GUIDE_STRENGTH,
        sampler_name='uni_pc',
        latent_image=emptyhunyuanlatentvideo,
        model=modelsamplingsd3,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(_id='8', samples=ksampler, vae=vaeloader)
    createvideo = CreateVideo(_id='49', fps=DEFAULT_FPS, images=vaedecode)

    # Outputs
    savevideo = SaveVideo(_id='50', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video/ComfyUI')

