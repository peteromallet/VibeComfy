# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CreateVideo, EmptyHunyuanLatentVideo, KSampler, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
DEFAULT_FPS = 16
DEFAULT_FRAMES = 33
DEFAULT_PROMPT = 'a fox moving quickly in a beautiful winter scenery nature trees mountains daytime tracking camera'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 82628696717253
GUIDE_STRENGTH = 6
UNET_NAME = 'wan2.1_t2v_1.3B_fp16.safetensors'
VAE_NAME = 'wan_2.1_vae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors', sha256='be531024cd9018cb5b48c40cfbb6a6191645b1c792eb8bf4f8c1c6e10f924dc5', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=2838303560, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors', hf_revision='main', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors', hf_revision='main', subdir='vae'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='text_to_video',
    models=MODELS,
    output_prefix='video/ComfyUI',
    provenance={'source_workflow': 'workflow_corpus/official/video/wan_t2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        unetloader = UNETLoader(unet_name=UNET_NAME)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')
        vaeloader = VAELoader(vae_name=VAE_NAME)

        emptyhunyuanlatentvideo = EmptyHunyuanLatentVideo(
            width=public('width', default=832),
            height=public('height', default=480),
            length=public('length', default=DEFAULT_FRAMES, aliases=('frames',)),
        )

        # Conditioning
        positive = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=cliploader,
        )

        negative = CLIPTextEncode(
            text=public('negative_prompt', default=DEFAULT_PROMPT_2),
            clip=cliploader,
        )

        modelsamplingsd3 = ModelSamplingSD3(shift=8, model=unetloader)

        ksampler = KSampler(
            seed=public('seed', default=DEFAULT_SEED),
            steps=public('steps', default=30),
            cfg=public('cfg', default=GUIDE_STRENGTH),
            sampler_name=public('sampler_name', default='uni_pc'),
            latent_image=emptyhunyuanlatentvideo,
            model=modelsamplingsd3,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

        createvideo = CreateVideo(
            fps=public('output_fps', default=DEFAULT_FPS, aliases=('fps',)),
            images=vaedecode,
        )

        # Outputs
        savevideo = SaveVideo(video=createvideo)


        wf.register_input('model', unetloader.node.id, 'unet_name', UNET_NAME)
        return wf.finalize({}, spec=OUTPUT_SPEC)

