# vibecomfy:generated
# pack: ltxvideo
# source: object_info cache ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
# source_sha256: 8475ebea62cce5427f24e35b59aa1574b2b4c78eebfad0842fbedc88f26bc320
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 75

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def APGGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    eta: float | _Omitted = ...,
    momentum_coefficient: float | _Omitted = ...,
    norm_threshold: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DynamicConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    only_first_frame: bool | _Omitted = ...,
    power: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GemmaAPITextEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    api_key: str | _Omitted = ...,
    ckpt_name: Literal['ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    enhance_prompt: bool | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GuiderParameters(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cfg: float | _Omitted = ...,
    cross_attn: bool | _Omitted = ...,
    modality: Literal['VIDEO', 'AUDIO'] | _Omitted = ...,
    modality_scale: float | _Omitted = ...,
    perturb_attn: bool | _Omitted = ...,
    rescale: float | _Omitted = ...,
    skip_step: int | _Omitted = ...,
    stg: float | _Omitted = ...,
    parameters: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageToCPU(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAddVideoICLoRAGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    crop: Any | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    latent_downscale_factor: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    tile_overlap: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    use_tiled_encode: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAddVideoICLoRAGuideAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    attention_strength: float | _Omitted = ...,
    crop: Any | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    latent_downscale_factor: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    tile_overlap: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    use_tiled_encode: bool | _Omitted = ...,
    attention_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAttentioOverride(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blocks: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAttentionBank(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blocks: str | _Omitted = ...,
    save_steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAttnOverride(
    *args: VibeWorkflow,
    _id: str | None = ...,
    layers: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXFetaEnhance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    feta_weight: float | _Omitted = ...,
    attn_override: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXFloatToInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXFlowEditCFGGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    source_neg: Any | _Omitted = ...,
    source_pos: Any | _Omitted = ...,
    target_neg: Any | _Omitted = ...,
    target_pos: Any | _Omitted = ...,
    source_cfg: float | _Omitted = ...,
    target_cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXFlowEditSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    refine_steps: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    skip_steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXForwardModelSamplingPred(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXICLoRALoaderModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXPerturbedAttention(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    rescale: float | _Omitted = ...,
    scale: float | _Omitted = ...,
    attn_override: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXPrepareAttnInjections(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    attn_bank: Any | _Omitted = ...,
    inject_steps: int | _Omitted = ...,
    key: bool | _Omitted = ...,
    query: bool | _Omitted = ...,
    value: bool | _Omitted = ...,
    blocks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXQ8Patch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    quantization_preset: Literal['0.9.8', 'ltxv2', 'full_bf16', 'custom'] | _Omitted = ...,
    quantize_cross_attn: bool | _Omitted = ...,
    quantize_ffn: bool | _Omitted = ...,
    quantize_self_attn: bool | _Omitted = ...,
    use_fp8_attention: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXRFForwardODESampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_step: int | _Omitted = ...,
    gamma: float | _Omitted = ...,
    gamma_trend: Literal['linear_decrease', 'linear_increase', 'constant'] | _Omitted = ...,
    start_step: int | _Omitted = ...,
    attn_bank: Any | _Omitted = ...,
    order: Literal['first', 'second'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXRFReverseODESampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent_image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    end_step: int | _Omitted = ...,
    eta: float | _Omitted = ...,
    start_step: int | _Omitted = ...,
    attn_inj: Any | _Omitted = ...,
    eta_trend: Literal['linear_decrease', 'linear_increase', 'constant'] | _Omitted = ...,
    order: Literal['first', 'second'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXReverseModelSamplingPred(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAdainLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    reference: Any | _Omitted = ...,
    factor: float | _Omitted = ...,
    per_frame: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuideAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    blur_radius: int | _Omitted = ...,
    crf: int | _Omitted = ...,
    crop: Literal['center', 'disabled'] | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    interpolation: Literal['lanczos', 'bislerp', 'nearest', 'bilinear', 'bicubic', 'area', 'nearest-exact'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuideAdvancedAttention(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    attention_strength: float | _Omitted = ...,
    blur_radius: int | _Omitted = ...,
    crf: int | _Omitted = ...,
    crop: Literal['center', 'disabled'] | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    interpolation: Literal['lanczos', 'bislerp', 'nearest', 'bilinear', 'bicubic', 'area', 'nearest-exact'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    attention_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddLatentGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guiding_latent: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    latent_idx: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents1: Any | _Omitted = ...,
    latents2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVApplySTG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    block_indices: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVBaseSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    width: int | _Omitted = ...,
    blur: int | _Omitted = ...,
    crf: int | _Omitted = ...,
    crop: Literal['center', 'disabled'] | _Omitted = ...,
    optional_cond_images: Any | _Omitted = ...,
    optional_cond_indices: str | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVDilateLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    horizontal_scale: int | _Omitted = ...,
    vertical_scale: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVDilateVideoMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    spatial_radius: int | _Omitted = ...,
    temporal_radius: int | _Omitted = ...,
    image_as_mask: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVDrawTracks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    tracks: str | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVExtendSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    frame_overlap: int | _Omitted = ...,
    num_new_frames: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    cond_image_strength: float | _Omitted = ...,
    optional_cond_images: Any | _Omitted = ...,
    optional_cond_indices: str | _Omitted = ...,
    optional_guiding_latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVGemmaCLIPModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    gemma_path: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    ltxv_path: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    max_length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVGemmaEnhancePrompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    bypass_i2v: bool | _Omitted = ...,
    max_tokens: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVHDRDecodePostprocess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    exposure: float | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    half_precision: bool | _Omitted = ...,
    output_dir: str | _Omitted = ...,
    save_exr: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    blur_radius: int | _Omitted = ...,
    crf: int | _Omitted = ...,
    crop: Literal['center', 'disabled'] | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Literal['lanczos', 'bislerp', 'nearest', 'bilinear', 'bicubic', 'area', 'nearest-exact'] | _Omitted = ...,
    length: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoConditionOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    bypass: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVInContextSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    guiding_latents: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    optional_cond_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVInpaintPreprocess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVLaplacianPyramidBlend(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_a: Any | _Omitted = ...,
    image_b: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    mask_low_res_dilation: int | _Omitted = ...,
    trim_to_shortest: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVLinearOverlapLatentTransition(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    axis: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVLoadConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    device: Any | _Omitted = ...,
    file_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVLoopingSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    cond_image_strength: float | _Omitted = ...,
    guiding_strength: float | _Omitted = ...,
    horizontal_tiles: int | _Omitted = ...,
    spatial_overlap: int | _Omitted = ...,
    temporal_overlap: int | _Omitted = ...,
    temporal_overlap_cond_strength: float | _Omitted = ...,
    temporal_tile_size: int | _Omitted = ...,
    vertical_tiles: int | _Omitted = ...,
    adain_factor: float | _Omitted = ...,
    guiding_end_step: int | _Omitted = ...,
    guiding_start_step: int | _Omitted = ...,
    optional_cond_image_indices: str | _Omitted = ...,
    optional_cond_images: Any | _Omitted = ...,
    optional_guiding_latents: Any | _Omitted = ...,
    optional_negative_index_latents: Any | _Omitted = ...,
    optional_normalizing_latents: Any | _Omitted = ...,
    optional_positive_conditionings: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVMultiPromptProvider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVNormalizingSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    latent_image: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    audio_normalization_factors: str | _Omitted = ...,
    video_normalization_factors: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPatcherVAE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPerStepAdainPatcher(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    reference: Any | _Omitted = ...,
    factors: str | _Omitted = ...,
    per_frame: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPerStepStatNormPatcher(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    clip_outliers: bool | _Omitted = ...,
    factors: str | _Omitted = ...,
    percentile: float | _Omitted = ...,
    target_mean: float | _Omitted = ...,
    target_std: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPreprocessMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    clamp_max: float | _Omitted = ...,
    clamp_min: float | _Omitted = ...,
    grow_mask: int | _Omitted = ...,
    ignore_first_mask: bool | _Omitted = ...,
    invert_input_masks: bool | _Omitted = ...,
    pooling_method: Literal['max', 'mean', 'min'] | _Omitted = ...,
    tapered_corners: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPromptEnhancer(
    *args: VibeWorkflow,
    _id: str | None = ...,
    max_resulting_tokens: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_enhancer: Any | _Omitted = ...,
    image_prompt: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPromptEnhancerLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_captioner_name: str | _Omitted = ...,
    llm_name: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVQ8LoraModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora_name: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSaveConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    dtype: Any | _Omitted = ...,
    filename: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSelectLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    end_index: int | _Omitted = ...,
    start_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSetAudioRefTokens(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSetAudioVideoMaskByTime(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_vae: Any | _Omitted = ...,
    av_latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    end_time: float | _Omitted = ...,
    mask_audio: bool | _Omitted = ...,
    mask_init_value_audio: float | _Omitted = ...,
    mask_init_value_video: float | _Omitted = ...,
    mask_video: bool | _Omitted = ...,
    slope_len: int | _Omitted = ...,
    start_time: float | _Omitted = ...,
    video_fps: float | _Omitted = ...,
    spatial_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSetVideoLatentNoiseMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSparseTrackEditor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    points_store: str | _Omitted = ...,
    points_to_sample: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSpatioTemporalTiledVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    last_frame_fix: bool | _Omitted = ...,
    spatial_overlap: int | _Omitted = ...,
    spatial_tiles: int | _Omitted = ...,
    temporal_overlap: int | _Omitted = ...,
    temporal_tile_length: int | _Omitted = ...,
    working_device: Literal['cpu', 'auto'] | _Omitted = ...,
    working_dtype: Literal['float16', 'float32', 'auto'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVStatNormLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    clip_outliers: bool | _Omitted = ...,
    factor: float | _Omitted = ...,
    percentile: float | _Omitted = ...,
    target_mean: float | _Omitted = ...,
    target_std: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVTiledSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    boost_latent_similarity: bool | _Omitted = ...,
    crop: Literal['center', 'disabled'] | _Omitted = ...,
    horizontal_tiles: int | _Omitted = ...,
    latents_cond_strength: float | _Omitted = ...,
    overlap: int | _Omitted = ...,
    vertical_tiles: int | _Omitted = ...,
    images_cond_strengths: str | _Omitted = ...,
    optional_cond_images: Any | _Omitted = ...,
    optional_cond_indices: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVTiledVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    horizontal_tiles: int | _Omitted = ...,
    last_frame_fix: bool | _Omitted = ...,
    overlap: int | _Omitted = ...,
    vertical_tiles: int | _Omitted = ...,
    working_device: Literal['cpu', 'auto'] | _Omitted = ...,
    working_dtype: Literal['float16', 'float32', 'auto'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LinearOverlapLatentTransition(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    axis: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LowVRAMAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    dependencies: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LowVRAMCheckpointLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = ...,
    dependencies: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LowVRAMLatentUpscaleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['hunyuanvideo15_latent_upsampler_1080p.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltx-2.3-temporal-upscaler-x2-1.0.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModifyLTXModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultiPromptProvider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultimodalGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    parameters: Any | _Omitted = ...,
    skip_blocks: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def STGAdvancedPresets(
    *args: VibeWorkflow,
    _id: str | None = ...,
    preset: Literal['Custom', '13b Dynamic', '13b Balanced', '13b Upscale', '13b Distilled', '2b'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def STGGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    rescale: float | _Omitted = ...,
    stg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def STGGuiderAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg_star_rescale: bool | _Omitted = ...,
    cfg_values: str | _Omitted = ...,
    sigmas: str | _Omitted = ...,
    skip_steps_sigma_threshold: float | _Omitted = ...,
    stg_layers_indices: str | _Omitted = ...,
    stg_rescale_values: str | _Omitted = ...,
    stg_scale_values: str | _Omitted = ...,
    apg_cfg_scale: float | _Omitted = ...,
    apply_apg: bool | _Omitted = ...,
    eta: float | _Omitted = ...,
    norm_threshold: float | _Omitted = ...,
    preset: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def STGGuiderNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    rescale: float | _Omitted = ...,
    stg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Set_VAE_Decoder_Noise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    scale: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    timestep: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['APGGuider', 'DynamicConditioning', 'GemmaAPITextEncode', 'GuiderParameters', 'ImageToCPU', 'LTXAddVideoICLoRAGuide', 'LTXAddVideoICLoRAGuideAdvanced', 'LTXAttentioOverride', 'LTXAttentionBank', 'LTXAttnOverride', 'LTXFetaEnhance', 'LTXFloatToInt', 'LTXFlowEditCFGGuider', 'LTXFlowEditSampler', 'LTXForwardModelSamplingPred', 'LTXICLoRALoaderModelOnly', 'LTXPerturbedAttention', 'LTXPrepareAttnInjections', 'LTXQ8Patch', 'LTXRFForwardODESampler', 'LTXRFReverseODESampler', 'LTXReverseModelSamplingPred', 'LTXVAdainLatent', 'LTXVAddGuideAdvanced', 'LTXVAddGuideAdvancedAttention', 'LTXVAddLatentGuide', 'LTXVAddLatents', 'LTXVApplySTG', 'LTXVBaseSampler', 'LTXVDilateLatent', 'LTXVDilateVideoMask', 'LTXVDrawTracks', 'LTXVExtendSampler', 'LTXVGemmaCLIPModelLoader', 'LTXVGemmaEnhancePrompt', 'LTXVHDRDecodePostprocess', 'LTXVImgToVideoAdvanced', 'LTXVImgToVideoConditionOnly', 'LTXVInContextSampler', 'LTXVInpaintPreprocess', 'LTXVLaplacianPyramidBlend', 'LTXVLinearOverlapLatentTransition', 'LTXVLoadConditioning', 'LTXVLoopingSampler', 'LTXVMultiPromptProvider', 'LTXVNormalizingSampler', 'LTXVPatcherVAE', 'LTXVPerStepAdainPatcher', 'LTXVPerStepStatNormPatcher', 'LTXVPreprocessMasks', 'LTXVPromptEnhancer', 'LTXVPromptEnhancerLoader', 'LTXVQ8LoraModelLoader', 'LTXVSaveConditioning', 'LTXVSelectLatents', 'LTXVSetAudioRefTokens', 'LTXVSetAudioVideoMaskByTime', 'LTXVSetVideoLatentNoiseMasks', 'LTXVSparseTrackEditor', 'LTXVSpatioTemporalTiledVAEDecode', 'LTXVStatNormLatent', 'LTXVTiledSampler', 'LTXVTiledVAEDecode', 'LinearOverlapLatentTransition', 'LowVRAMAudioVAELoader', 'LowVRAMCheckpointLoader', 'LowVRAMLatentUpscaleModelLoader', 'ModifyLTXModel', 'MultiPromptProvider', 'MultimodalGuider', 'STGAdvancedPresets', 'STGGuider', 'STGGuiderAdvanced', 'STGGuiderNode', 'Set_VAE_Decoder_Noise']
