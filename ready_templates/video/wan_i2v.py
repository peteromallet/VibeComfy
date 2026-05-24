# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionEncode, CLIPVisionLoader, CreateVideo, KSampler, LoadImage, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader, WanImageToVideo


CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
CLIP_NAME_2 = 'clip_vision_h.safetensors'
DEFAULT_FPS = 16
DEFAULT_FRAMES = 33
DEFAULT_PROMPT = 'a cute anime girl with massive fennec ears and a big fluffy tail wearing a maid outfit turning around'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 987948718394761
GUIDE_STRENGTH = 6
UNET_NAME = 'wan2.1_i2v_480p_14B_fp16.safetensors'
VAE_NAME = 'wan_2.1_vae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors', sha256='27988f6b510eb8d5fdd7485671b54897f8683f2bba7a772c5671be21d3491253', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=32791377504, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors', sha256='c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=6735906897, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors', sha256='2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=253815318, subdir='vae'),
    'clip_vision': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors', sha256='64a7ef761bfccbadbaa3da77366aac4185a6c58fa5de5f589b42a65bcc21f161', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=1264219396, subdir='clip_vision'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    models=MODELS,
    output_prefix='video/ComfyUI',
    provenance={'source_workflow': 'workflow_corpus/official/video/wan_i2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        unetloader = UNETLoader(unet_name=UNET_NAME)
        cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')
        vaeloader = VAELoader(vae_name=VAE_NAME)
        clipvisionloader = CLIPVisionLoader(clip_name=CLIP_NAME_2)

        # Inputs
        image, mask = LoadImage(
            image=public('start_image', default='image_to_video_wan_start_image.png', aliases=('image', 'input_image')),
        )

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=cliploader,
        )

        cliptextencode_2 = CLIPTextEncode(
            text=public('negative_prompt', default=DEFAULT_PROMPT_2),
            clip=cliploader,
        )

        clipvisionencode = CLIPVisionEncode(
            crop='none',
            clip_vision=clipvisionloader,
            image=image,
        )

        modelsamplingsd3 = ModelSamplingSD3(shift=8, model=unetloader)

        positive, negative, latent = WanImageToVideo(
            height=public('height', default=512),
            length=public('length', default=DEFAULT_FRAMES, aliases=('frames',)),
            width=public('width', default=512),
            clip_vision_output=clipvisionencode,
            negative=cliptextencode_2,
            positive=cliptextencode,
            start_image=image,
            vae=vaeloader,
        )

        ksampler = KSampler(
            seed=public('seed', default=DEFAULT_SEED),
            steps=public('steps', default=20),
            cfg=public('cfg', default=GUIDE_STRENGTH),
            sampler_name=public('sampler_name', default='uni_pc'),
            latent_image=latent,
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


        wf.register_input('model', '1', 'unet_name', UNET_NAME)
        return wf.finalize({}, spec=OUTPUT_SPEC)

