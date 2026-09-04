# vibecomfy:generated
# pack: rgthree
# source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
# source_sha256: ddd4f597a4881e548aa83aed8f35b6e86745030415221c07d4cff48210af0a9a
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 24

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def Any_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base_ctx: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors'] | _Omitted = ...,
    clip: Any | _Omitted = ...,
    clip_height: int | _Omitted = ...,
    clip_width: int | _Omitted = ...,
    control_net: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    sampler: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    step_refiner: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    text_neg_g: str | _Omitted = ...,
    text_neg_l: str | _Omitted = ...,
    text_pos_g: str | _Omitted = ...,
    text_pos_l: str | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Merge_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Merge_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Switch_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base_ctx: Any | _Omitted = ...,
    clip: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Display_Any_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Display_Int_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_Comparer_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_a: Any | _Omitted = ...,
    image_b: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_Inset_Crop_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bottom: int | _Omitted = ...,
    left: int | _Omitted = ...,
    measurement: Literal['Pixels', 'Percentage'] | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_Resize_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    fit: Literal['crop', 'pad', 'contain'] | _Omitted = ...,
    height: int | _Omitted = ...,
    measurement: Literal['pixels', 'percentage'] | _Omitted = ...,
    method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_or_Latent_Size_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSampler_Config_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cfg: float | _Omitted = ...,
    refiner_step: int | _Omitted = ...,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    steps_total: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Lora_Loader_Stack_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    lora_01: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    lora_02: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    lora_03: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    lora_04: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_01: float | _Omitted = ...,
    strength_02: float | _Omitted = ...,
    strength_03: float | _Omitted = ...,
    strength_04: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Lora_Loader_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Primitive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Prompt_Simple_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Prompt_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_lora: Literal['CHOOSE', 'DISABLE LORAS', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    opt_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Puter_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDXL_Empty_Latent_Image_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    clip_scale: float | _Omitted = ...,
    dimensions: Literal['1536 x 640   (landscape)', '1344 x 768   (landscape)', '1216 x 832   (landscape)', '1152 x 896   (landscape)', '1024 x 1024  (square)', ' 896 x 1152  (portrait)', ' 832 x 1216  (portrait)', ' 768 x 1344  (portrait)', ' 640 x 1536  (portrait)'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDXL_Power_Prompt_Positive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_g: str | _Omitted = ...,
    prompt_l: str | _Omitted = ...,
    crop_height: int | _Omitted = ...,
    crop_width: int | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_lora: Literal['CHOOSE', 'DISABLE LORAS', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    opt_clip_height: int | _Omitted = ...,
    opt_clip_width: int | _Omitted = ...,
    opt_model: Any | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDXL_Power_Prompt_Simple_Negative_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_g: str | _Omitted = ...,
    prompt_l: str | _Omitted = ...,
    crop_height: int | _Omitted = ...,
    crop_width: int | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    opt_clip_height: int | _Omitted = ...,
    opt_clip_width: int | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Seed_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['Any_Switch_rgthree', 'Context_Big_rgthree', 'Context_Merge_Big_rgthree', 'Context_Merge_rgthree', 'Context_Switch_Big_rgthree', 'Context_Switch_rgthree', 'Context_rgthree', 'Display_Any_rgthree', 'Display_Int_rgthree', 'Image_Comparer_rgthree', 'Image_Inset_Crop_rgthree', 'Image_Resize_rgthree', 'Image_or_Latent_Size_rgthree', 'KSampler_Config_rgthree', 'Lora_Loader_Stack_rgthree', 'Power_Lora_Loader_rgthree', 'Power_Primitive_rgthree', 'Power_Prompt_Simple_rgthree', 'Power_Prompt_rgthree', 'Power_Puter_rgthree', 'SDXL_Empty_Latent_Image_rgthree', 'SDXL_Power_Prompt_Positive_rgthree', 'SDXL_Power_Prompt_Simple_Negative_rgthree', 'Seed_rgthree']
