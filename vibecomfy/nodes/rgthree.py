# vibecomfy:generated
# pack: rgthree
# source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
# source_sha256: ddd4f597a4881e548aa83aed8f35b6e86745030415221c07d4cff48210af0a9a
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 24
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers rgthree

"""Auto-generated public wrappers for the rgthree custom-node pack.

Each function wraps one ComfyUI node class and delegates through the
public ``vibecomfy.templates.node`` ABI.
"""

from __future__ import annotations

from typing import Any, Literal

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

class _Omitted:
    pass

_UNSET = _Omitted()

def Any_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Any Switch (rgthree)``.

    Category: rgthree

    Returns: *

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Any_Switch_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Any Switch (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_ctx: Any | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors'] | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    clip_height: int | _Omitted = _UNSET,
    clip_width: int | _Omitted = _UNSET,
    control_net: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    sampler: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = _UNSET,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    step_refiner: int | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    text_neg_g: str | _Omitted = _UNSET,
    text_neg_l: str | _Omitted = _UNSET,
    text_pos_g: str | _Omitted = _UNSET,
    text_pos_l: str | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Context Big (rgthree)``.

    Category: rgthree

    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Context_Big_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_ctx is not _UNSET:
        _kwargs['base_ctx'] = base_ctx
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if clip_height is not _UNSET:
        _kwargs['clip_height'] = clip_height
    if clip_width is not _UNSET:
        _kwargs['clip_width'] = clip_width
    if control_net is not _UNSET:
        _kwargs['control_net'] = control_net
    if images is not _UNSET:
        _kwargs['images'] = images
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if model is not _UNSET:
        _kwargs['model'] = model
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if step_refiner is not _UNSET:
        _kwargs['step_refiner'] = step_refiner
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if text_neg_g is not _UNSET:
        _kwargs['text_neg_g'] = text_neg_g
    if text_neg_l is not _UNSET:
        _kwargs['text_neg_l'] = text_neg_l
    if text_pos_g is not _UNSET:
        _kwargs['text_pos_g'] = text_pos_g
    if text_pos_l is not _UNSET:
        _kwargs['text_pos_l'] = text_pos_l
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'Context Big (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Merge_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Context Merge Big (rgthree)``.

    Category: rgthree

    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Context_Merge_Big_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Merge Big (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Merge_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Context Merge (rgthree)``.

    Category: rgthree

    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Context_Merge_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Merge (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Switch_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Context Switch Big (rgthree)``.

    Category: rgthree

    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Context_Switch_Big_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Switch Big (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Context Switch (rgthree)``.

    Category: rgthree

    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Context_Switch_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Switch (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_ctx: Any | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Context (rgthree)``.

    Category: rgthree

    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Context_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_ctx is not _UNSET:
        _kwargs['base_ctx'] = base_ctx
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if images is not _UNSET:
        _kwargs['images'] = images
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if model is not _UNSET:
        _kwargs['model'] = model
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'Context (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Display_Any_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    source: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Display Any (rgthree)``.

    Category: rgthree

    Returns: None

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Display_Any_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if source is not _UNSET:
        _kwargs['source'] = source
    _kwargs.update(_extras)
    return node(wf, 'Display Any (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Display_Int_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Display Int (rgthree)``.

    Category: rgthree

    Returns: None

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Display_Int_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    _kwargs.update(_extras)
    return node(wf, 'Display Int (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_Comparer_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_a: Any | _Omitted = _UNSET,
    image_b: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Image Comparer (rgthree)``.

    Category: rgthree

    Compares two images with a hover slider, or click from properties.

    Returns: None

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Image_Comparer_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image_a is not _UNSET:
        _kwargs['image_a'] = image_a
    if image_b is not _UNSET:
        _kwargs['image_b'] = image_b
    _kwargs.update(_extras)
    return node(wf, 'Image Comparer (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_Inset_Crop_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    bottom: int | _Omitted = _UNSET,
    left: int | _Omitted = _UNSET,
    measurement: Literal['Pixels', 'Percentage'] | _Omitted = _UNSET,
    right: int | _Omitted = _UNSET,
    top: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Image Inset Crop (rgthree)``.

    Category: rgthree

    Returns: IMAGE

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Image_Inset_Crop_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if bottom is not _UNSET:
        _kwargs['bottom'] = bottom
    if left is not _UNSET:
        _kwargs['left'] = left
    if measurement is not _UNSET:
        _kwargs['measurement'] = measurement
    if right is not _UNSET:
        _kwargs['right'] = right
    if top is not _UNSET:
        _kwargs['top'] = top
    _kwargs.update(_extras)
    return node(wf, 'Image Inset Crop (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_Resize_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    fit: Literal['crop', 'pad', 'contain'] | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    measurement: Literal['pixels', 'percentage'] | _Omitted = _UNSET,
    method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Image Resize (rgthree)``.

    Category: rgthree

    Resize the image.

    Returns: IMAGE, WIDTH, HEIGHT

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Image_Resize_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if fit is not _UNSET:
        _kwargs['fit'] = fit
    if height is not _UNSET:
        _kwargs['height'] = height
    if measurement is not _UNSET:
        _kwargs['measurement'] = measurement
    if method is not _UNSET:
        _kwargs['method'] = method
    if width is not _UNSET:
        _kwargs['width'] = width
    _kwargs.update(_extras)
    return node(wf, 'Image Resize (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_or_Latent_Size_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Image or Latent Size (rgthree)``.

    Category: rgthree

    Returns: WIDTH, HEIGHT

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Image_or_Latent_Size_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Image or Latent Size (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def KSampler_Config_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    cfg: float | _Omitted = _UNSET,
    refiner_step: int | _Omitted = _UNSET,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = _UNSET,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = _UNSET,
    steps_total: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``KSampler Config (rgthree)``.

    Category: rgthree

    Returns: STEPS, REFINER_STEP, CFG, SAMPLER, SCHEDULER

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"KSampler_Config_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if refiner_step is not _UNSET:
        _kwargs['refiner_step'] = refiner_step
    if sampler_name is not _UNSET:
        _kwargs['sampler_name'] = sampler_name
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if steps_total is not _UNSET:
        _kwargs['steps_total'] = steps_total
    _kwargs.update(_extras)
    return node(wf, 'KSampler Config (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Lora_Loader_Stack_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    lora_01: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_02: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_03: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_04: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_01: float | _Omitted = _UNSET,
    strength_02: float | _Omitted = _UNSET,
    strength_03: float | _Omitted = _UNSET,
    strength_04: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Lora Loader Stack (rgthree)``.

    Category: rgthree

    Returns: MODEL, CLIP

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Lora_Loader_Stack_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora_01 is not _UNSET:
        _kwargs['lora_01'] = lora_01
    if lora_02 is not _UNSET:
        _kwargs['lora_02'] = lora_02
    if lora_03 is not _UNSET:
        _kwargs['lora_03'] = lora_03
    if lora_04 is not _UNSET:
        _kwargs['lora_04'] = lora_04
    if strength_01 is not _UNSET:
        _kwargs['strength_01'] = strength_01
    if strength_02 is not _UNSET:
        _kwargs['strength_02'] = strength_02
    if strength_03 is not _UNSET:
        _kwargs['strength_03'] = strength_03
    if strength_04 is not _UNSET:
        _kwargs['strength_04'] = strength_04
    _kwargs.update(_extras)
    return node(wf, 'Lora Loader Stack (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Lora_Loader_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Power Lora Loader (rgthree)``.

    Category: rgthree

    Returns: MODEL, CLIP

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Power_Lora_Loader_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'Power Lora Loader (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Primitive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Power Primitive (rgthree)``.

    Category: rgthree

    Returns: *

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Power_Primitive_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Power Primitive (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Prompt_Simple_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: str | _Omitted = _UNSET,
    insert_embedding: Literal['CHOOSE'] | _Omitted = _UNSET,
    insert_saved: Literal['CHOOSE'] | _Omitted = _UNSET,
    opt_clip: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Power Prompt - Simple (rgthree)``.

    Category: rgthree

    Returns: CONDITIONING, TEXT

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Power_Prompt_Simple_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    _kwargs.update(_extras)
    return node(wf, 'Power Prompt - Simple (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Prompt_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: str | _Omitted = _UNSET,
    insert_embedding: Literal['CHOOSE'] | _Omitted = _UNSET,
    insert_lora: Literal['CHOOSE', 'DISABLE LORAS', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16'] | _Omitted = _UNSET,
    insert_saved: Literal['CHOOSE'] | _Omitted = _UNSET,
    opt_clip: Any | _Omitted = _UNSET,
    opt_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Power Prompt (rgthree)``.

    Category: rgthree

    Returns: CONDITIONING, MODEL, CLIP, TEXT

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Power_Prompt_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_lora is not _UNSET:
        _kwargs['insert_lora'] = insert_lora
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if opt_model is not _UNSET:
        _kwargs['opt_model'] = opt_model
    _kwargs.update(_extras)
    return node(wf, 'Power Prompt (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Puter_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Power Puter (rgthree)``.

    Category: rgthree

    Returns: *

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Power_Puter_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Power Puter (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def SDXL_Empty_Latent_Image_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    batch_size: int | _Omitted = _UNSET,
    clip_scale: float | _Omitted = _UNSET,
    dimensions: Literal['1536 x 640   (landscape)', '1344 x 768   (landscape)', '1216 x 832   (landscape)', '1152 x 896   (landscape)', '1024 x 1024  (square)', ' 896 x 1152  (portrait)', ' 832 x 1216  (portrait)', ' 768 x 1344  (portrait)', ' 640 x 1536  (portrait)'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``SDXL Empty Latent Image (rgthree)``.

    Category: rgthree

    Returns: LATENT, CLIP_WIDTH, CLIP_HEIGHT

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"SDXL_Empty_Latent_Image_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if clip_scale is not _UNSET:
        _kwargs['clip_scale'] = clip_scale
    if dimensions is not _UNSET:
        _kwargs['dimensions'] = dimensions
    _kwargs.update(_extras)
    return node(wf, 'SDXL Empty Latent Image (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def SDXL_Power_Prompt_Positive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt_g: str | _Omitted = _UNSET,
    prompt_l: str | _Omitted = _UNSET,
    crop_height: int | _Omitted = _UNSET,
    crop_width: int | _Omitted = _UNSET,
    insert_embedding: Literal['CHOOSE'] | _Omitted = _UNSET,
    insert_lora: Literal['CHOOSE', 'DISABLE LORAS', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16'] | _Omitted = _UNSET,
    insert_saved: Literal['CHOOSE'] | _Omitted = _UNSET,
    opt_clip: Any | _Omitted = _UNSET,
    opt_clip_height: int | _Omitted = _UNSET,
    opt_clip_width: int | _Omitted = _UNSET,
    opt_model: Any | _Omitted = _UNSET,
    target_height: int | _Omitted = _UNSET,
    target_width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``SDXL Power Prompt - Positive (rgthree)``.

    Category: rgthree

    Returns: CONDITIONING, MODEL, CLIP, TEXT_G, TEXT_L

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"SDXL_Power_Prompt_Positive_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt_g is not _UNSET:
        _kwargs['prompt_g'] = prompt_g
    if prompt_l is not _UNSET:
        _kwargs['prompt_l'] = prompt_l
    if crop_height is not _UNSET:
        _kwargs['crop_height'] = crop_height
    if crop_width is not _UNSET:
        _kwargs['crop_width'] = crop_width
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_lora is not _UNSET:
        _kwargs['insert_lora'] = insert_lora
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if opt_clip_height is not _UNSET:
        _kwargs['opt_clip_height'] = opt_clip_height
    if opt_clip_width is not _UNSET:
        _kwargs['opt_clip_width'] = opt_clip_width
    if opt_model is not _UNSET:
        _kwargs['opt_model'] = opt_model
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    _kwargs.update(_extras)
    return node(wf, 'SDXL Power Prompt - Positive (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def SDXL_Power_Prompt_Simple_Negative_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt_g: str | _Omitted = _UNSET,
    prompt_l: str | _Omitted = _UNSET,
    crop_height: int | _Omitted = _UNSET,
    crop_width: int | _Omitted = _UNSET,
    insert_embedding: Literal['CHOOSE'] | _Omitted = _UNSET,
    insert_saved: Literal['CHOOSE'] | _Omitted = _UNSET,
    opt_clip: Any | _Omitted = _UNSET,
    opt_clip_height: int | _Omitted = _UNSET,
    opt_clip_width: int | _Omitted = _UNSET,
    target_height: int | _Omitted = _UNSET,
    target_width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``SDXL Power Prompt - Simple / Negative (rgthree)``.

    Category: rgthree

    Returns: CONDITIONING, TEXT_G, TEXT_L

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"SDXL_Power_Prompt_Simple_Negative_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt_g is not _UNSET:
        _kwargs['prompt_g'] = prompt_g
    if prompt_l is not _UNSET:
        _kwargs['prompt_l'] = prompt_l
    if crop_height is not _UNSET:
        _kwargs['crop_height'] = crop_height
    if crop_width is not _UNSET:
        _kwargs['crop_width'] = crop_width
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if opt_clip_height is not _UNSET:
        _kwargs['opt_clip_height'] = opt_clip_height
    if opt_clip_width is not _UNSET:
        _kwargs['opt_clip_width'] = opt_clip_width
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    _kwargs.update(_extras)
    return node(wf, 'SDXL Power Prompt - Simple / Negative (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Seed_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Seed (rgthree)``.

    Category: rgthree

    Returns: SEED

    Source: object_info cache rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
    """
    if len(args) > 1:
        raise TypeError(f"Seed_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Seed (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['Any_Switch_rgthree', 'Context_Big_rgthree', 'Context_Merge_Big_rgthree', 'Context_Merge_rgthree', 'Context_Switch_Big_rgthree', 'Context_Switch_rgthree', 'Context_rgthree', 'Display_Any_rgthree', 'Display_Int_rgthree', 'Image_Comparer_rgthree', 'Image_Inset_Crop_rgthree', 'Image_Resize_rgthree', 'Image_or_Latent_Size_rgthree', 'KSampler_Config_rgthree', 'Lora_Loader_Stack_rgthree', 'Power_Lora_Loader_rgthree', 'Power_Primitive_rgthree', 'Power_Prompt_Simple_rgthree', 'Power_Prompt_rgthree', 'Power_Puter_rgthree', 'SDXL_Empty_Latent_Image_rgthree', 'SDXL_Power_Prompt_Positive_rgthree', 'SDXL_Power_Prompt_Simple_Negative_rgthree', 'Seed_rgthree']
__vibecomfy_class_types__ = {'Any_Switch_rgthree': 'Any Switch (rgthree)', 'Context_Big_rgthree': 'Context Big (rgthree)', 'Context_Merge_Big_rgthree': 'Context Merge Big (rgthree)', 'Context_Merge_rgthree': 'Context Merge (rgthree)', 'Context_Switch_Big_rgthree': 'Context Switch Big (rgthree)', 'Context_Switch_rgthree': 'Context Switch (rgthree)', 'Context_rgthree': 'Context (rgthree)', 'Display_Any_rgthree': 'Display Any (rgthree)', 'Display_Int_rgthree': 'Display Int (rgthree)', 'Image_Comparer_rgthree': 'Image Comparer (rgthree)', 'Image_Inset_Crop_rgthree': 'Image Inset Crop (rgthree)', 'Image_Resize_rgthree': 'Image Resize (rgthree)', 'Image_or_Latent_Size_rgthree': 'Image or Latent Size (rgthree)', 'KSampler_Config_rgthree': 'KSampler Config (rgthree)', 'Lora_Loader_Stack_rgthree': 'Lora Loader Stack (rgthree)', 'Power_Lora_Loader_rgthree': 'Power Lora Loader (rgthree)', 'Power_Primitive_rgthree': 'Power Primitive (rgthree)', 'Power_Prompt_Simple_rgthree': 'Power Prompt - Simple (rgthree)', 'Power_Prompt_rgthree': 'Power Prompt (rgthree)', 'Power_Puter_rgthree': 'Power Puter (rgthree)', 'SDXL_Empty_Latent_Image_rgthree': 'SDXL Empty Latent Image (rgthree)', 'SDXL_Power_Prompt_Positive_rgthree': 'SDXL Power Prompt - Positive (rgthree)', 'SDXL_Power_Prompt_Simple_Negative_rgthree': 'SDXL Power Prompt - Simple / Negative (rgthree)', 'Seed_rgthree': 'Seed (rgthree)'}
