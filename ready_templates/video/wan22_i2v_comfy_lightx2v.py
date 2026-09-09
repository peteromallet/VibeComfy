# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CreateVideo, KSamplerAdvanced, LoadImage, LoraLoaderModelOnly, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader, WanImageToVideo


CLIP_NAME = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
DEFAULT_FPS = 16
DEFAULT_PROMPT = 'A felt-style little eagle cashier greeting, waving, and smiling at the camera.'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
EULER = 'euler'
GUIDE_STRENGTH = 1.0000000000000002
GUIDE_STRENGTH_2 = 1
LORA_NAME = 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors'
LORA_NAME_2 = 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors'
UNET_NAME = 'wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors'
UNET_NAME_2 = 'wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors'
VAE_NAME = 'wan_2.1_vae.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors', subdir='diffusion_models'),
    'diffusion_model_2': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors', subdir='diffusion_models'),
    'lora': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', subdir='loras'),
    'lora_2': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', subdir='loras'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors', subdir='vae'),
}


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='4', field='unet_name', default=UNET_NAME),
    'prompt': InputSpec(node='6', field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node='13', field='noise_seed', default=0),
    'steps': InputSpec(node='13', field='steps', default=4),
    'image': InputSpec(node='1', field='image', default='03_video_wan2_2_14B_i2v_subgraphed_input_image.png', aliases=('input_image',)),
    'fps': InputSpec(node='16', field='fps', default=DEFAULT_FPS),
    'width': InputSpec(node='12', field='width', default=720),
    'height': InputSpec(node='12', field='height', default=720),
    'frames': InputSpec(node='12', field='length', default=81),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    source_path='ready_templates/video/wan22_i2v_comfy_lightx2v.py',
    source_id='video/wan22_i2v_comfy_lightx2v',
    upstream_source_id='03_video_wan2_2_14B_i2v_subgraphed',
    source_type='ready_template',
    source_workflow_path='ready_templates/video/wan22_i2v_comfy_lightx2v.py',
    source_ref='ready_templates/video/wan22_i2v_comfy_lightx2v.py',
    source_kind='raw_json',
    workflow_source_id='03_video_wan2_2_14B_i2v_subgraphed',
    workflow_source_type='api',
    raw_workflow_shape='api',
    source_hash='sha256:6d8f09096c1e0817c00184b6b53c0676f155985f4063f59c38100388b43fbd4e',
    workflow_shape={'nodes': 17, 'runtime_nodes': 17, 'helper_nodes': 0, 'edges': 1, 'inputs': 4, 'outputs': 1},
    output_mode='ready_template',
    ready_id='video/wan22_i2v_comfy_lightx2v',
    approach='Native ComfyUI WanImageToVideo Wan 2.2 A14B I2V with fp8_scaled high/low diffusion models and official Lightx2v 4-step LoRAs.',
    runtime_note='Candidate for comparing against the Kijai WanVideoWrapper Wan 2.2 I2V path; uses only Comfy core/runtime node classes after component expansion.',
    smoke_resolution='720x720x81_frames',
    source_component_workflow='ready_templates/video/wan22_i2v_comfy_lightx2v.py',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(
        _id='1',
        image='03_video_wan2_2_14B_i2v_subgraphed_input_image.png',
    )

    # Loaders
    cliploader = CLIPLoader(_id='2', clip_name=CLIP_NAME, type='wan')
    vaeloader = VAELoader(_id='3', vae_name=VAE_NAME)
    unetloader = UNETLoader(_id='4', unet_name=UNET_NAME, weight_dtype='default')
    unetloader_2 = UNETLoader(_id='5', unet_name=UNET_NAME_2, weight_dtype='default')

    # Conditioning
    cliptextencode = CLIPTextEncode(_id='6', text=DEFAULT_PROMPT, clip=cliploader)
    cliptextencode_2 = CLIPTextEncode(_id='7', text=DEFAULT_PROMPT_2, clip=cliploader)

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='8',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    loraloadermodelonly_2 = LoraLoaderModelOnly(
        _id='9',
        lora_name=LORA_NAME_2,
        strength_model=GUIDE_STRENGTH,
        model=unetloader_2,
    )

    modelsamplingsd3 = ModelSamplingSD3(
        _id='10',
        shift=5.000000000000001,
        model=loraloadermodelonly,
    )

    modelsamplingsd3_2 = ModelSamplingSD3(
        _id='11',
        shift=5.000000000000001,
        model=loraloadermodelonly_2,
    )

    positive, negative, latent = WanImageToVideo(
        _id='12',
        height=720,
        length=81,
        width=720,
        negative=cliptextencode_2,
        positive=cliptextencode,
        start_image=image,
        vae=vaeloader,
    )

    # Sampling
    ksampleradvanced = KSamplerAdvanced(
        _id='13',
        add_noise='enable',
        noise_seed=0,
        steps=4,
        cfg=GUIDE_STRENGTH_2,
        sampler_name=EULER,
        scheduler='simple',
        end_at_step=2,
        return_with_leftover_noise='enable',
        latent_image=latent,
        model=modelsamplingsd3,
        negative=negative,
        positive=positive,
    )

    ksampleradvanced_2 = KSamplerAdvanced(
        _id='14',
        add_noise='disable',
        steps=4,
        cfg=GUIDE_STRENGTH_2,
        sampler_name=EULER,
        scheduler='simple',
        start_at_step=2,
        end_at_step=4,
        return_with_leftover_noise='disable',
        latent_image=ksampleradvanced,
        model=modelsamplingsd3_2,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(_id='15', samples=ksampleradvanced_2, vae=vaeloader)
    createvideo = CreateVideo(_id='16', fps=DEFAULT_FPS, images=vaedecode)

    # Outputs
    savevideo = SaveVideo(
        _id='17',
        filename_prefix='video/Wan2.2_image_to_video',
        video=createvideo,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video/Wan2.2_image_to_video')
