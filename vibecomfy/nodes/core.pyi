# vibecomfy:generated
# pack: core
# source: object_info cache comfy@runpod-snapshot.json sha256:976a9597cc5d; object_info cache comfy_core@object_info_comfyui_0.24.0.1.json sha256:bda0a9f7ebed; object_info cache comfy_core@runpod-snapshot.json sha256:99a6c4f71f2d
# source_sha256: e698cb96605b6e242b65ab0abfbdac5fb59bb403e343cd84a344fcd3ffe6ed6f
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 930

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def APG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    eta: float | _Omitted = ...,
    momentum: float | _Omitted = ...,
    norm_threshold: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ARVideoI2V(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AddLatentGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AddNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent_image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AddTextPrefix(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prefix: str | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AddTextSuffix(
    *args: VibeWorkflow,
    _id: str | None = ...,
    suffix: str | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AdjustBrightness(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    factor: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AdjustContrast(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    factor: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AlignYourStepsScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    denoise: float | _Omitted = ...,
    model_type: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioAdjustVolume(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    volume: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioConcat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio1: Any | _Omitted = ...,
    audio2: Any | _Omitted = ...,
    direction: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioEncoderEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    audio_encoder: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioEncoderLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_encoder_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioEqualizer3Band(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    high_freq: int | _Omitted = ...,
    high_gain_dB: float | _Omitted = ...,
    low_freq: int | _Omitted = ...,
    low_gain_dB: float | _Omitted = ...,
    mid_freq: int | _Omitted = ...,
    mid_gain_dB: float | _Omitted = ...,
    mid_q: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioMerge(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio1: Any | _Omitted = ...,
    audio2: Any | _Omitted = ...,
    merge_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    required: bool | _Omitted = ...,
    default_if_empty: Any | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BasicGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BasicScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    denoise: float | _Omitted = ...,
    scheduler: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchImagesNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchLatentsNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchMasksNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BeebleSwitchXImageEdit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    alpha_mode: Any | _Omitted = ...,
    max_resolution: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BeebleSwitchXVideoEdit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    alpha_mode: Any | _Omitted = ...,
    max_resolution: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BetaSamplingScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    alpha: float | _Omitted = ...,
    beta: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BinaryOperation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lhs: Any | _Omitted = ...,
    op: Literal['__add__', '__and__', '__concat__', '__contains__', '__delitem__', '__eq__', '__floordiv__', '__ge__', '__getitem__', '__gt__', '__iadd__', '__iand__', '__iconcat__', '__ifloordiv__', '__ilshift__', '__imatmul__', '__imod__', '__imul__', '__ior__', '__ipow__', '__irshift__', '__isub__', '__itruediv__', '__ixor__', '__le__', '__lshift__', '__lt__', '__matmul__', '__mod__', '__mul__', '__ne__', '__or__', '__pow__', '__rshift__', '__sub__', '__truediv__', '__xor__', 'add', 'and_', 'concat', 'contains', 'countOf', 'delitem', 'eq', 'floordiv', 'ge', 'getitem', 'gt', 'iadd', 'iand', 'iconcat', 'ifloordiv', 'ilshift', 'imatmul', 'imod', 'imul', 'indexOf', 'ior', 'ipow', 'irshift', 'is_', 'is_not', 'isub', 'itruediv', 'ixor', 'le', 'length_hint', 'lshift', 'lt', 'matmul', 'mod', 'mul', 'ne', 'or_', 'pow', 'rshift', 'sub', 'truediv', 'xor', 'and', 'or'] | _Omitted = ...,
    rhs: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BooleanBinaryOperation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lhs: Any | _Omitted = ...,
    op: Literal['__add__', '__and__', '__concat__', '__contains__', '__delitem__', '__eq__', '__floordiv__', '__ge__', '__getitem__', '__gt__', '__iadd__', '__iand__', '__iconcat__', '__ifloordiv__', '__ilshift__', '__imatmul__', '__imod__', '__imul__', '__ior__', '__ipow__', '__irshift__', '__isub__', '__itruediv__', '__ixor__', '__le__', '__lshift__', '__lt__', '__matmul__', '__mod__', '__mul__', '__ne__', '__or__', '__pow__', '__rshift__', '__sub__', '__truediv__', '__xor__', 'add', 'and_', 'concat', 'contains', 'countOf', 'delitem', 'eq', 'floordiv', 'ge', 'getitem', 'gt', 'iadd', 'iand', 'iconcat', 'ifloordiv', 'ilshift', 'imatmul', 'imod', 'imul', 'indexOf', 'ior', 'ipow', 'irshift', 'is_', 'is_not', 'isub', 'itruediv', 'ixor', 'le', 'length_hint', 'lshift', 'lt', 'matmul', 'mod', 'mul', 'ne', 'or_', 'pow', 'rshift', 'sub', 'truediv', 'xor', 'and', 'or'] | _Omitted = ...,
    rhs: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BooleanRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: bool | _Omitted = ...,
    required: bool | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BooleanUnaryOperation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    op: Literal['__abs__', '__call__', '__index__', '__inv__', '__invert__', '__neg__', '__not__', '__pos__', '_abs', 'abs', 'call', 'index', 'inv', 'invert', 'neg', 'not_', 'pos', 'truth', 'not'] | _Omitted = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BriaImageEditNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    guidance_scale: float | _Omitted = ...,
    model: Any | _Omitted = ...,
    moderation: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    structured_prompt: str | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BriaRemoveImageBackground(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    moderation: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BriaRemoveVideoBackground(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    background_color: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDance2FirstLastFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    first_frame: Any | _Omitted = ...,
    first_frame_asset_id: str | _Omitted = ...,
    last_frame: Any | _Omitted = ...,
    last_frame_asset_id: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDance2ReferenceNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDance2TextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceCreateImageAsset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    group_id: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceCreateVideoAsset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    group_id: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceFirstLastFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_frame: Any | _Omitted = ...,
    last_frame: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    camera_fixed: bool | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    size_preset: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    guidance_scale: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceImageReferenceNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    camera_fixed: bool | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceSeedNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceSeedreamNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    size_preset: Any | _Omitted = ...,
    fail_on_partial: bool | _Omitted = ...,
    height: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    max_images: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    sequential_image_generation: Any | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceSeedreamNodeV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ByteDanceTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    camera_fixed: bool | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGNorm(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pre_cfg: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGOverride(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGZeroStar(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPAttentionMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    k: float | _Omitted = ...,
    out: float | _Omitted = ...,
    q: float | _Omitted = ...,
    v: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = ...,
    type: Literal['stable_diffusion', 'stable_cascade', 'sd3', 'stable_audio', 'mochi', 'ltxv', 'pixart', 'cosmos', 'lumina2', 'wan', 'hidream', 'chroma', 'ace', 'omnigen2', 'qwen_image', 'hunyuan_image', 'flux2', 'ovis', 'longcat_image'] | _Omitted = ...,
    device: Literal['default', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPMergeAdd(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip1: Any | _Omitted = ...,
    clip2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPMergeSimple(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip1: Any | _Omitted = ...,
    clip2: Any | _Omitted = ...,
    ratio: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPMergeSubtract(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip1: Any | _Omitted = ...,
    clip2: Any | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPSave(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPSetLastLayer(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    stop_at_clip_layer: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeControlnet(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    conditioning: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeFlux(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    clip_l: str | _Omitted = ...,
    guidance: float | _Omitted = ...,
    t5xxl: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeHiDream(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    clip_g: str | _Omitted = ...,
    clip_l: str | _Omitted = ...,
    llama: str | _Omitted = ...,
    t5xxl: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeHunyuanDiT(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    bert: str | _Omitted = ...,
    mt5xl: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeKandinsky5(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    clip_l: str | _Omitted = ...,
    qwen25_7b: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeLumina2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    system_prompt: Any | _Omitted = ...,
    user_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodePixArtAlpha(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    text: str | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeSD3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    clip_g: str | _Omitted = ...,
    clip_l: str | _Omitted = ...,
    empty_padding: Any | _Omitted = ...,
    t5xxl: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeSDXL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    crop_h: int | _Omitted = ...,
    crop_w: int | _Omitted = ...,
    height: int | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    text_g: str | _Omitted = ...,
    text_l: str | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncodeSDXLRefiner(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    ascore: float | _Omitted = ...,
    height: int | _Omitted = ...,
    text: str | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPVisionEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    crop: Literal['center', 'none'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPVisionLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name: Literal['CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors', 'clip_vision_g.safetensors', 'clip_vision_h.safetensors', 'llava_llama3_vision.safetensors', 'sigclip_vision_patch14_384.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CM_IntToFloat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Canny(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    high_threshold: float | _Omitted = ...,
    low_threshold: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CaseConverter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mode: Any | _Omitted = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CenterCropImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CheckpointLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = ...,
    config_name: Literal['anything_v3.yaml', 'v1-inference.yaml', 'v1-inference_clip_skip_2.yaml', 'v1-inference_clip_skip_2_fp16.yaml', 'v1-inference_fp16.yaml', 'v1-inpainting-inference.yaml', 'v2-inference-v.yaml', 'v2-inference-v_fp32.yaml', 'v2-inference.yaml', 'v2-inference_fp32.yaml', 'v2-inpainting-inference.yaml'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CheckpointLoaderSimple(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CheckpointSave(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ChromaRadianceOptions(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    end_sigma: float | _Omitted = ...,
    force_sequential_txt_ids: bool | _Omitted = ...,
    nerf_tile_size: int | _Omitted = ...,
    preserve_wrapper: bool | _Omitted = ...,
    start_sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ClaudeNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ColorToRGBInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    color: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ColorTransfer(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_ref: Any | _Omitted = ...,
    image_target: Any | _Omitted = ...,
    method: Any | _Omitted = ...,
    source_stats: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CombineHooks2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    hooks_A: Any | _Omitted = ...,
    hooks_B: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CombineHooks4(
    *args: VibeWorkflow,
    _id: str | None = ...,
    hooks_A: Any | _Omitted = ...,
    hooks_B: Any | _Omitted = ...,
    hooks_C: Any | _Omitted = ...,
    hooks_D: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CombineHooks8(
    *args: VibeWorkflow,
    _id: str | None = ...,
    hooks_A: Any | _Omitted = ...,
    hooks_B: Any | _Omitted = ...,
    hooks_C: Any | _Omitted = ...,
    hooks_D: Any | _Omitted = ...,
    hooks_E: Any | _Omitted = ...,
    hooks_F: Any | _Omitted = ...,
    hooks_G: Any | _Omitted = ...,
    hooks_H: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfyAndNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    values: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfyMathExpression(
    *args: VibeWorkflow,
    _id: str | None = ...,
    expression: str | _Omitted = ...,
    values: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfyNotNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfyNumberConvert(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfyOrNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    values: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfySwitchNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    on_false: Any | _Omitted = ...,
    on_true: Any | _Omitted = ...,
    switch: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CompositeCroppedAndFittedInpaintResult(
    *args: VibeWorkflow,
    _id: str | None = ...,
    inpainted_image: Any | _Omitted = ...,
    source_image: Any | _Omitted = ...,
    source_mask: Any | _Omitted = ...,
    composite_context: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningAverage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning_from: Any | _Omitted = ...,
    conditioning_to: Any | _Omitted = ...,
    conditioning_to_strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning_1: Any | _Omitted = ...,
    conditioning_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningConcat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning_from: Any | _Omitted = ...,
    conditioning_to: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetArea(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetAreaPercentage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    height: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    width: float | _Omitted = ...,
    x: float | _Omitted = ...,
    y: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetAreaPercentageVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    height: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    temporal: float | _Omitted = ...,
    width: float | _Omitted = ...,
    x: float | _Omitted = ...,
    y: float | _Omitted = ...,
    z: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetAreaStrength(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetDefaultCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cond: Any | _Omitted = ...,
    cond_DEFAULT: Any | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetProperties(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cond_NEW: Any | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    timesteps: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetPropertiesAndCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cond: Any | _Omitted = ...,
    cond_NEW: Any | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    timesteps: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetTimestepRange(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    end: float | _Omitted = ...,
    start: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningStableAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    seconds_start: float | _Omitted = ...,
    seconds_total: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningTimestepsRange(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningZeroOut(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ContextWindowsManual(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    causal_window_fix: bool | _Omitted = ...,
    closed_loop: bool | _Omitted = ...,
    cond_retain_index_list: str | _Omitted = ...,
    context_length: int | _Omitted = ...,
    context_overlap: int | _Omitted = ...,
    context_schedule: Any | _Omitted = ...,
    context_stride: int | _Omitted = ...,
    dim: int | _Omitted = ...,
    freenoise: bool | _Omitted = ...,
    fuse_method: Any | _Omitted = ...,
    split_conds_to_windows: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ControlNetApply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    control_net: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ControlNetApplyAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ControlNetApplySD3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ControlNetInpaintingAliMamaApply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ControlNetLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net_name: Literal['ControlNet-Plus-Plus_sd15_ade20k_seg.safetensors', 'ControlNet-Plus-Plus_sd15_canny.safetensors', 'ControlNet-Plus-Plus_sd15_grayscale_depth.safetensors', 'ControlNet-Plus-Plus_sd15_hed.bin', 'ControlNet-Plus-Plus_sd15_lineart.bin', 'OpenPoseXL2.safetensors', 'Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors', 'Qwen-Image-InstantX-ControlNet-Inpainting.safetensors', 'Qwen-Image-InstantX-ControlNet-Union.safetensors', 'Z-Image-Turbo-Fun-Controlnet-Union.safetensors', 'alimama-creative-flux.1-dev-controlnet-inpainting-alpha.safetensors', 'control-lora-openposeXL2-rank256.safetensors', 'control_lora_rank128_v11e_sd15_ip2p_fp16.safetensors', 'control_lora_rank128_v11e_sd15_shuffle_fp16.safetensors', 'control_lora_rank128_v11f1e_sd15_tile_fp16.safetensors', 'control_lora_rank128_v11f1p_sd15_depth_fp16.safetensors', 'control_lora_rank128_v11p_sd15_canny_fp16.safetensors', 'control_lora_rank128_v11p_sd15_inpaint_fp16.safetensors', 'control_lora_rank128_v11p_sd15_lineart_fp16.safetensors', 'control_lora_rank128_v11p_sd15_mlsd_fp16.safetensors', 'control_lora_rank128_v11p_sd15_normalbae_fp16.safetensors', 'control_lora_rank128_v11p_sd15_openpose_fp16.safetensors', 'control_lora_rank128_v11p_sd15_scribble_fp16.safetensors', 'control_lora_rank128_v11p_sd15_seg_fp16.safetensors', 'control_lora_rank128_v11p_sd15_softedge_fp16.safetensors', 'control_lora_rank128_v11p_sd15s2_lineart_anime_fp16.safetensors', 'control_v11e_sd15_ip2p_fp16.safetensors', 'control_v11e_sd15_shuffle_fp16.safetensors', 'control_v11f1e_sd15_tile_fp16.safetensors', 'control_v11f1p_sd15_depth_fp16.safetensors', 'control_v11p_sd15_canny_fp16.safetensors', 'control_v11p_sd15_inpaint_fp16.safetensors', 'control_v11p_sd15_lineart_fp16.safetensors', 'control_v11p_sd15_mlsd_fp16.safetensors', 'control_v11p_sd15_normalbae_fp16.safetensors', 'control_v11p_sd15_openpose_fp16.safetensors', 'control_v11p_sd15_scribble_fp16.safetensors', 'control_v11p_sd15_seg_fp16.safetensors', 'control_v11p_sd15_softedge_fp16.safetensors', 'control_v11p_sd15s2_lineart_anime_fp16.safetensors', 'control_v11u_sd15_tile_fp16.safetensors', 'controlnet-densepose-sdxl.safetensors', 'depth-zoe-xl-v1.0-controlnet.safetensors', 'diffusers_xl_canny_full.safetensors', 'diffusers_xl_canny_mid.safetensors', 'diffusers_xl_canny_small.safetensors', 'diffusers_xl_depth_full.safetensors', 'diffusers_xl_depth_mid.safetensors', 'diffusers_xl_depth_small.safetensors', 'flux-canny-controlnet-v3.safetensors', 'flux-depth-controlnet-v3.safetensors', 'flux-hed-controlnet-v3.safetensors', 'instantx-flux.1-dev-controlnet-canny.safetensors', 'instantx-flux.1-dev-controlnet-union.safetensors', 'ioclab_sd15_recolor.safetensors', 'kohya_controllllite_xl_blur.safetensors', 'kohya_controllllite_xl_blur_anime.safetensors', 'kohya_controllllite_xl_blur_anime_beta.safetensors', 'kohya_controllllite_xl_canny.safetensors', 'kohya_controllllite_xl_canny_anime.safetensors', 'kohya_controllllite_xl_depth.safetensors', 'kohya_controllllite_xl_depth_anime.safetensors', 'kohya_controllllite_xl_openpose_anime.safetensors', 'kohya_controllllite_xl_openpose_anime_v2.safetensors', 'kohya_controllllite_xl_scribble_anime.safetensors', 'mistoLine_rank256.safetensors', 'mistoline_flux.dev_v1.safetensors', 'sai_xl_canny_128lora.safetensors', 'sai_xl_canny_256lora.safetensors', 'sai_xl_depth_128lora.safetensors', 'sai_xl_depth_256lora.safetensors', 'sai_xl_recolor_128lora.safetensors', 'sai_xl_recolor_256lora.safetensors', 'sai_xl_sketch_128lora.safetensors', 'sai_xl_sketch_256lora.safetensors', 'sargezt_xl_depth.safetensors', 'sargezt_xl_depth_faid_vidit.safetensors', 'sargezt_xl_depth_zeed.safetensors', 'sargezt_xl_softedge.safetensors', 'sd3.5_large_controlnet_blur.safetensors', 'sd3.5_large_controlnet_canny.safetensors', 'sd3.5_large_controlnet_depth.safetensors', 'shakker-labs-flux.1-dev-controlnet-depth.safetensors', 'shakker-labs-flux.1-dev-controlnet-union-pro.safetensors', 'stable_cascade_canny.safetensors', 'stable_cascade_inpainting.safetensors', 'stable_cascade_super_resolution.safetensors', 't2i-adapter_diffusers_xl_canny.safetensors', 't2i-adapter_diffusers_xl_depth_midas.safetensors', 't2i-adapter_diffusers_xl_depth_zoe.safetensors', 't2i-adapter_diffusers_xl_lineart.safetensors', 't2i-adapter_diffusers_xl_openpose.safetensors', 't2i-adapter_diffusers_xl_sketch.safetensors', 't2i-adapter_xl_canny.safetensors', 't2i-adapter_xl_openpose.safetensors', 't2i-adapter_xl_sketch.safetensors', 'thibaud_xl_openpose.safetensors', 'thibaud_xl_openpose_256lora.safetensors', 'wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors', 'xinsir-anime-painter-scribble-sdxl-1.0.safetensors', 'xinsir-controlnet-canny-sdxl-1.0.safetensors', 'xinsir-controlnet-canny-sdxl-1.0_V2.safetensors', 'xinsir-controlnet-openpose-sdxl-1.0.safetensors', 'xinsir-controlnet-scribble-sdxl-1.0.safetensors', 'xinsir-controlnet-union-sdxl-1.0-promax.safetensors', 'xinsir-controlnet-union-sdxl-1.0.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ControlNetLoaderWeights(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net_name: Literal['ControlNet-Plus-Plus_sd15_ade20k_seg.safetensors', 'ControlNet-Plus-Plus_sd15_canny.safetensors', 'ControlNet-Plus-Plus_sd15_grayscale_depth.safetensors', 'ControlNet-Plus-Plus_sd15_hed.bin', 'ControlNet-Plus-Plus_sd15_lineart.bin', 'OpenPoseXL2.safetensors', 'Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors', 'Qwen-Image-InstantX-ControlNet-Inpainting.safetensors', 'Qwen-Image-InstantX-ControlNet-Union.safetensors', 'Z-Image-Turbo-Fun-Controlnet-Union.safetensors', 'alimama-creative-flux.1-dev-controlnet-inpainting-alpha.safetensors', 'control-lora-openposeXL2-rank256.safetensors', 'control_lora_rank128_v11e_sd15_ip2p_fp16.safetensors', 'control_lora_rank128_v11e_sd15_shuffle_fp16.safetensors', 'control_lora_rank128_v11f1e_sd15_tile_fp16.safetensors', 'control_lora_rank128_v11f1p_sd15_depth_fp16.safetensors', 'control_lora_rank128_v11p_sd15_canny_fp16.safetensors', 'control_lora_rank128_v11p_sd15_inpaint_fp16.safetensors', 'control_lora_rank128_v11p_sd15_lineart_fp16.safetensors', 'control_lora_rank128_v11p_sd15_mlsd_fp16.safetensors', 'control_lora_rank128_v11p_sd15_normalbae_fp16.safetensors', 'control_lora_rank128_v11p_sd15_openpose_fp16.safetensors', 'control_lora_rank128_v11p_sd15_scribble_fp16.safetensors', 'control_lora_rank128_v11p_sd15_seg_fp16.safetensors', 'control_lora_rank128_v11p_sd15_softedge_fp16.safetensors', 'control_lora_rank128_v11p_sd15s2_lineart_anime_fp16.safetensors', 'control_v11e_sd15_ip2p_fp16.safetensors', 'control_v11e_sd15_shuffle_fp16.safetensors', 'control_v11f1e_sd15_tile_fp16.safetensors', 'control_v11f1p_sd15_depth_fp16.safetensors', 'control_v11p_sd15_canny_fp16.safetensors', 'control_v11p_sd15_inpaint_fp16.safetensors', 'control_v11p_sd15_lineart_fp16.safetensors', 'control_v11p_sd15_mlsd_fp16.safetensors', 'control_v11p_sd15_normalbae_fp16.safetensors', 'control_v11p_sd15_openpose_fp16.safetensors', 'control_v11p_sd15_scribble_fp16.safetensors', 'control_v11p_sd15_seg_fp16.safetensors', 'control_v11p_sd15_softedge_fp16.safetensors', 'control_v11p_sd15s2_lineart_anime_fp16.safetensors', 'control_v11u_sd15_tile_fp16.safetensors', 'controlnet-densepose-sdxl.safetensors', 'depth-zoe-xl-v1.0-controlnet.safetensors', 'diffusers_xl_canny_full.safetensors', 'diffusers_xl_canny_mid.safetensors', 'diffusers_xl_canny_small.safetensors', 'diffusers_xl_depth_full.safetensors', 'diffusers_xl_depth_mid.safetensors', 'diffusers_xl_depth_small.safetensors', 'flux-canny-controlnet-v3.safetensors', 'flux-depth-controlnet-v3.safetensors', 'flux-hed-controlnet-v3.safetensors', 'instantx-flux.1-dev-controlnet-canny.safetensors', 'instantx-flux.1-dev-controlnet-union.safetensors', 'ioclab_sd15_recolor.safetensors', 'kohya_controllllite_xl_blur.safetensors', 'kohya_controllllite_xl_blur_anime.safetensors', 'kohya_controllllite_xl_blur_anime_beta.safetensors', 'kohya_controllllite_xl_canny.safetensors', 'kohya_controllllite_xl_canny_anime.safetensors', 'kohya_controllllite_xl_depth.safetensors', 'kohya_controllllite_xl_depth_anime.safetensors', 'kohya_controllllite_xl_openpose_anime.safetensors', 'kohya_controllllite_xl_openpose_anime_v2.safetensors', 'kohya_controllllite_xl_scribble_anime.safetensors', 'mistoLine_rank256.safetensors', 'mistoline_flux.dev_v1.safetensors', 'sai_xl_canny_128lora.safetensors', 'sai_xl_canny_256lora.safetensors', 'sai_xl_depth_128lora.safetensors', 'sai_xl_depth_256lora.safetensors', 'sai_xl_recolor_128lora.safetensors', 'sai_xl_recolor_256lora.safetensors', 'sai_xl_sketch_128lora.safetensors', 'sai_xl_sketch_256lora.safetensors', 'sargezt_xl_depth.safetensors', 'sargezt_xl_depth_faid_vidit.safetensors', 'sargezt_xl_depth_zeed.safetensors', 'sargezt_xl_softedge.safetensors', 'sd3.5_large_controlnet_blur.safetensors', 'sd3.5_large_controlnet_canny.safetensors', 'sd3.5_large_controlnet_depth.safetensors', 'shakker-labs-flux.1-dev-controlnet-depth.safetensors', 'shakker-labs-flux.1-dev-controlnet-union-pro.safetensors', 'stable_cascade_canny.safetensors', 'stable_cascade_inpainting.safetensors', 'stable_cascade_super_resolution.safetensors', 't2i-adapter_diffusers_xl_canny.safetensors', 't2i-adapter_diffusers_xl_depth_midas.safetensors', 't2i-adapter_diffusers_xl_depth_zoe.safetensors', 't2i-adapter_diffusers_xl_lineart.safetensors', 't2i-adapter_diffusers_xl_openpose.safetensors', 't2i-adapter_diffusers_xl_sketch.safetensors', 't2i-adapter_xl_canny.safetensors', 't2i-adapter_xl_openpose.safetensors', 't2i-adapter_xl_sketch.safetensors', 'thibaud_xl_openpose.safetensors', 'thibaud_xl_openpose_256lora.safetensors', 'wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors', 'xinsir-anime-painter-scribble-sdxl-1.0.safetensors', 'xinsir-controlnet-canny-sdxl-1.0.safetensors', 'xinsir-controlnet-canny-sdxl-1.0_V2.safetensors', 'xinsir-controlnet-openpose-sdxl-1.0.safetensors', 'xinsir-controlnet-scribble-sdxl-1.0.safetensors', 'xinsir-controlnet-union-sdxl-1.0-promax.safetensors', 'xinsir-controlnet-union-sdxl-1.0.safetensors'] | _Omitted = ...,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e5m2', 'fp8_e4m3fn_fast'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CosmosImageToVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    end_image: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CosmosPredict2ImageToVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    end_image: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CosmosPromptUpsamplerLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['nvidia/Cosmos-1.0-Prompt-Upsampler-12B-Text2World'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CosmosText2WorldTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CosmosVideo2WorldTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateCameraInfo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    camera_type: Any | _Omitted = ...,
    fov: float | _Omitted = ...,
    mode: Any | _Omitted = ...,
    roll: float | _Omitted = ...,
    target_x: float | _Omitted = ...,
    target_y: float | _Omitted = ...,
    target_z: float | _Omitted = ...,
    zoom: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookKeyframe(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_percent: float | _Omitted = ...,
    strength_mult: float | _Omitted = ...,
    prev_hook_kf: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookKeyframesFromFloats(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_percent: float | _Omitted = ...,
    floats_strength: Any | _Omitted = ...,
    print_keyframes: bool | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    prev_hook_kf: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookKeyframesInterpolated(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_percent: float | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = ...,
    keyframes_count: int | _Omitted = ...,
    print_keyframes: bool | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    strength_end: float | _Omitted = ...,
    strength_start: float | _Omitted = ...,
    prev_hook_kf: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookLora(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora_name: Literal['Flux2TurboComfyv2.safetensors', 'Flux_2-Turbo-LoRA_comfyui.safetensors', 'GoodHands-beta2.safetensors', 'Hyper-FLUX.1-dev-8steps-lora.safetensors', 'Hyper-SD15-12steps-CFG-lora.safetensors', 'Hyper-SD15-4steps-CFG-lora.safetensors', 'Hyper-SD15-8steps-CFG-lora.safetensors', 'Hyper-SDXL-12steps-CFG-lora.safetensors', 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'PixelArtRedmond15V-PixelArt-PIXARFK.safetensors', 'Qwen-Edit-2509-Multiple-angles.safetensors', 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'Qwen-Image-Edit-2509-Anything2RealAlpha.safetensors', 'Qwen-Image-Edit-2509-Fusion.safetensors', 'Qwen-Image-Edit-2509-Light-Migration.safetensors', 'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Relight.safetensors', 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors', 'Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors', 'Qwen-Image-Lightning-4steps-V2.0.safetensors', 'Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors', 'Qwen-Image-Lightning-8steps-V2.0.safetensors', 'Wuli-Qwen-Image-2512-Turbo-LoRA-2steps-V1.0-bf16.safetensors', 'blur_control_xl_v1.safetensors', 'chronoedit_distill_lora.safetensors', 'dmd2_sdxl_4step_lora_fp16.safetensors', 'flux1-canny-dev-lora.safetensors', 'flux1-depth-dev-lora.safetensors', 'gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors', 'gummycandy_qwen.safetensors', 'illustration-1.0-qwen-image.safetensors', 'ip-adapter-faceid-plus_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sdxl_lora.safetensors', 'ip-adapter-faceid_sd15_lora.safetensors', 'ip-adapter-faceid_sdxl_lora.safetensors', 'lcm_lora_sdxl.safetensors', 'lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors', 'ltx-2-19b-distilled-lora-384.safetensors', 'ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_bf16.safetensors', 'ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_fp8.safetensors', 'ltx-2-19b-ic-lora-canny-control.safetensors', 'ltx-2-19b-ic-lora-depth-control.safetensors', 'ltx-2-19b-ic-lora-pose-control.safetensors', 'ltx-2-19b-lora-camera-control-dolly-left.safetensors', 'ltx-2.3-22b-distilled-lora-384.safetensors', 'ltx-2.3-id-lora-talkvid-3k.safetensors', 'ltx2-squish.safetensors', 'ltx2.3-transition.safetensors', 'ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors', 'openxl_handsfix.safetensors', 'qwen-image-edit-2511-multiple-angles-lora.safetensors', 'qwen_image_union_diffsynth_lora.safetensors', 'uso-flux1-dit-lora-v1.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors', 'wan_alpha_2.1_rgba_lora.safetensors'] | _Omitted = ...,
    strength_clip: float | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    prev_hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookLoraModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora_name: Literal['Flux2TurboComfyv2.safetensors', 'Flux_2-Turbo-LoRA_comfyui.safetensors', 'GoodHands-beta2.safetensors', 'Hyper-FLUX.1-dev-8steps-lora.safetensors', 'Hyper-SD15-12steps-CFG-lora.safetensors', 'Hyper-SD15-4steps-CFG-lora.safetensors', 'Hyper-SD15-8steps-CFG-lora.safetensors', 'Hyper-SDXL-12steps-CFG-lora.safetensors', 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'PixelArtRedmond15V-PixelArt-PIXARFK.safetensors', 'Qwen-Edit-2509-Multiple-angles.safetensors', 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'Qwen-Image-Edit-2509-Anything2RealAlpha.safetensors', 'Qwen-Image-Edit-2509-Fusion.safetensors', 'Qwen-Image-Edit-2509-Light-Migration.safetensors', 'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Relight.safetensors', 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors', 'Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors', 'Qwen-Image-Lightning-4steps-V2.0.safetensors', 'Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors', 'Qwen-Image-Lightning-8steps-V2.0.safetensors', 'Wuli-Qwen-Image-2512-Turbo-LoRA-2steps-V1.0-bf16.safetensors', 'blur_control_xl_v1.safetensors', 'chronoedit_distill_lora.safetensors', 'dmd2_sdxl_4step_lora_fp16.safetensors', 'flux1-canny-dev-lora.safetensors', 'flux1-depth-dev-lora.safetensors', 'gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors', 'gummycandy_qwen.safetensors', 'illustration-1.0-qwen-image.safetensors', 'ip-adapter-faceid-plus_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sdxl_lora.safetensors', 'ip-adapter-faceid_sd15_lora.safetensors', 'ip-adapter-faceid_sdxl_lora.safetensors', 'lcm_lora_sdxl.safetensors', 'lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors', 'ltx-2-19b-distilled-lora-384.safetensors', 'ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_bf16.safetensors', 'ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_fp8.safetensors', 'ltx-2-19b-ic-lora-canny-control.safetensors', 'ltx-2-19b-ic-lora-depth-control.safetensors', 'ltx-2-19b-ic-lora-pose-control.safetensors', 'ltx-2-19b-lora-camera-control-dolly-left.safetensors', 'ltx-2.3-22b-distilled-lora-384.safetensors', 'ltx-2.3-id-lora-talkvid-3k.safetensors', 'ltx2-squish.safetensors', 'ltx2.3-transition.safetensors', 'ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors', 'openxl_handsfix.safetensors', 'qwen-image-edit-2511-multiple-angles-lora.safetensors', 'qwen_image_union_diffsynth_lora.safetensors', 'uso-flux1-dit-lora-v1.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors', 'wan_alpha_2.1_rgba_lora.safetensors'] | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    prev_hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookModelAsLora(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'DasiwaWAN22I2V14BTruevision_boundbiteHighV10.safetensors', 'DasiwaWAN22I2V14BTruevision_boundbiteLowV10.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'SDXLrender_v2.0.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'moodyPornMix_zitV10DPO.safetensors', 'moodyPornMix_zitV10DPOFP8.safetensors', 'moodyWildMix_v3xeasonBASE40STEP.safetensors', 'moodyWildMix_v3xeasonDISTILLED.safetensors', 'mopIllustriousMixtureOf_v20ToonDMD.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sam3.1_multiplex_fp16.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'smoothMixOldVerNoobai_Illustrious2NoobaiV2.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors', 'zimageTurboNSFWBy_xmasBf16.safetensors', 'zimageTurboNSFWBy_xmasFP8.safetensors'] | _Omitted = ...,
    strength_clip: float | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    prev_hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateHookModelAsLoraModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'DasiwaWAN22I2V14BTruevision_boundbiteHighV10.safetensors', 'DasiwaWAN22I2V14BTruevision_boundbiteLowV10.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'SDXLrender_v2.0.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'moodyPornMix_zitV10DPO.safetensors', 'moodyPornMix_zitV10DPOFP8.safetensors', 'moodyWildMix_v3xeasonBASE40STEP.safetensors', 'moodyWildMix_v3xeasonDISTILLED.safetensors', 'mopIllustriousMixtureOf_v20ToonDMD.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sam3.1_multiplex_fp16.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'smoothMixOldVerNoobai_Illustrious2NoobaiV2.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors', 'zimageTurboNSFWBy_xmasBf16.safetensors', 'zimageTurboNSFWBy_xmasFP8.safetensors'] | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    prev_hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    inputs: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    fps: float | _Omitted = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CropAndFitInpaintToDiffusionSize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    margin: str | _Omitted = ...,
    resolutions: Literal['SDXL/SD3/Flux', 'SD1.5', 'LTXV', 'Ideogram', 'Cosmos', 'HunyuanVideo', 'WAN 14b', 'WAN 1.3b', 'WAN 14b with extras', 'HiDream 1 Edit', 'Kontext', 'Unknown', 'Qwen Image'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CropByBBoxes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    keep_aspect: Any | _Omitted = ...,
    output_height: int | _Omitted = ...,
    output_width: int | _Omitted = ...,
    padding: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CropMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CurveEditor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    curve: Any | _Omitted = ...,
    histogram: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CustomCombo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    choice: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DallEGenerate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['dall-e-2', 'dall-e-3'] | _Omitted = ...,
    quality: Literal['standard', 'hd'] | _Omitted = ...,
    size: Literal['256x256', '512x512', '1024x1024', '1792x1024', '1024x1792'] | _Omitted = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DevNullUris(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DiffControlNetLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    control_net_name: Literal['diff_control_sd15_canny_fp16.safetensors', 'diff_control_sd15_depth_fp16.safetensors', 'diff_control_sd15_hed_fp16.safetensors', 'diff_control_sd15_mlsd_fp16.safetensors', 'diff_control_sd15_normal_fp16.safetensors', 'diff_control_sd15_openpose_fp16.safetensors', 'diff_control_sd15_scribble_fp16.safetensors', 'diff_control_sd15_seg_fp16.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DifferentialDiffusion(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DiffusersLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_path: Literal['llava-hf/llava-v1.6-mistral-7b-hf', 'microsoft/Florence-2-large-ft', 'facebook/nllb-200-distilled-1.3B', 'llava-hf/llama3-llava-next-8b-hf', 'microsoft/Florence-2-base', 'gokaygokay/Florence-2-Flux-Large', 'microsoft/Phi-4-mini-instruct', 'roborovski/superprompt-v1', 'JingyeChen22/textdiffuser2_layout_planner', 'PromptEnhancer/PromptEnhancer-32B', 'JingyeChen22/textdiffuser2-full-ft', 'Yanrui95/NormalCrafter', 'microsoft/phi-4', 'Qwen/Qwen2-VL-7B-Instruct', 'appmana/Cosmos-1.0-Prompt-Upsampler-12B-Text2World-hf', 'google/paligemma2-28b-pt-896', 'MiaoshouAI/Florence-2-base-PromptGen-v2.0', 'microsoft/Florence-2-base-ft', 'THUDM/chatglm3-6b', 'ResembleAI/chatterbox', 'gokaygokay/Florence-2-SD3-Captioner', 'MiaoshouAI/Florence-2-large-PromptGen-v1.5', 'google/paligemma2-10b-pt-896', 'llava-hf/llava-onevision-qwen2-7b-si-hf', 'microsoft/Florence-2-large', 'google/paligemma-3b-ft-refcoco-seg-896', 'thwri/CogFlorence-2.1-Large', 'thwri/CogFlorence-2.2-Large', 'MiaoshouAI/Florence-2-large-PromptGen-v2.0', 'ResembleAI/chatterbox-turbo', 'MiaoshouAI/Florence-2-base-PromptGen-v1.5'] | _Omitted = ...,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e5m2', 'fp8_e4m3fn_fast'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DisableNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawBBoxes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bboxes: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DualCFGGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cond1: Any | _Omitted = ...,
    cond2: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    cfg_cond2_negative: float | _Omitted = ...,
    cfg_conds: float | _Omitted = ...,
    style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DualCLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name1: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'flux1-dev-Q4_K_S.gguf', 'flux1-dev-Q8_0.gguf', 'flux1-schnell-Q4_K_S.gguf', 'flux1-schnell-Q8_0.gguf', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5-v1_1-xxl-encoder-Q4_K_M.gguf', 't5-v1_1-xxl-encoder-Q8_0.gguf', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = ...,
    clip_name2: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'flux1-dev-Q4_K_S.gguf', 'flux1-dev-Q8_0.gguf', 'flux1-schnell-Q4_K_S.gguf', 'flux1-schnell-Q8_0.gguf', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5-v1_1-xxl-encoder-Q4_K_M.gguf', 't5-v1_1-xxl-encoder-Q8_0.gguf', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = ...,
    type: Literal['sdxl', 'sd3', 'flux', 'hunyuan_video', 'hidream', 'hunyuan_image', 'hunyuan_video_15', 'kandinsky5', 'kandinsky5_image', 'ltxv', 'newbie', 'ace'] | _Omitted = ...,
    device: Literal['default', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DualModelGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    model_negative: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EasyCache(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    reuse_threshold: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsAudioIsolation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsInstantVoiceClone(
    *args: VibeWorkflow,
    _id: str | None = ...,
    files: Any | _Omitted = ...,
    remove_background_noise: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsSpeechToSpeech(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    output_format: Any | _Omitted = ...,
    remove_background_noise: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    stability: float | _Omitted = ...,
    voice: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsSpeechToText(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    language_code: str | _Omitted = ...,
    model: Any | _Omitted = ...,
    num_speakers: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsTextToDialogue(
    *args: VibeWorkflow,
    _id: str | None = ...,
    apply_text_normalization: Any | _Omitted = ...,
    inputs: Any | _Omitted = ...,
    language_code: str | _Omitted = ...,
    model: Any | _Omitted = ...,
    output_format: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    stability: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsTextToSoundEffects(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    output_format: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsTextToSpeech(
    *args: VibeWorkflow,
    _id: str | None = ...,
    apply_text_normalization: Any | _Omitted = ...,
    language_code: str | _Omitted = ...,
    model: Any | _Omitted = ...,
    output_format: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    stability: float | _Omitted = ...,
    text: str | _Omitted = ...,
    voice: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ElevenLabsVoiceSelector(
    *args: VibeWorkflow,
    _id: str | None = ...,
    voice: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyARVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyAceStep1_5LatentAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyAceStepLatentAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    channels: int | _Omitted = ...,
    duration: float | _Omitted = ...,
    sample_rate: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyChromaRadianceLatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyCosmosLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyFlux2LatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyHiDreamO1LatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyHunyuanImageLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyHunyuanLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyHunyuanVideo15Latent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    color: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLTXVLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLatentAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    seconds: float | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLatentHunyuan3Dv2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyMochiLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyQwenImageLayeredLatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    layers: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptySD3LatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EnhanceContrast(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    clip_limit: float | _Omitted = ...,
    lower_percentile: float | _Omitted = ...,
    method: Literal['Histogram Equalization', 'Adaptive Equalization', 'Contrast Stretching'] | _Omitted = ...,
    upper_percentile: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Epsilon_Scaling(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    scaling_factor: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EvalPython_1_1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pycode: Any | _Omitted = ...,
    value0: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EvalPython_1_List(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pycode: Any | _Omitted = ...,
    value0: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EvalPython_5_5(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pycode: Any | _Omitted = ...,
    value0: Any | _Omitted = ...,
    value1: Any | _Omitted = ...,
    value2: Any | _Omitted = ...,
    value3: Any | _Omitted = ...,
    value4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EvalPython_List_1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pycode: Any | _Omitted = ...,
    value0: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EvalPython_List_List(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pycode: Any | _Omitted = ...,
    value0: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ExponentialScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigma_max: float | _Omitted = ...,
    sigma_min: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ExtendIntermediateSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    end_at_sigma: float | _Omitted = ...,
    spacing: Any | _Omitted = ...,
    start_at_sigma: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FeatherMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    bottom: int | _Omitted = ...,
    left: int | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def File3DToSplat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_3d: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Flatten(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    background_color: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FlipSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatAbs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatAdd(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    value2: float | _Omitted = ...,
    value3: float | _Omitted = ...,
    value4: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatAverage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    value2: float | _Omitted = ...,
    value3: float | _Omitted = ...,
    value4: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatClamp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    max: float | _Omitted = ...,
    min: float | _Omitted = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatDivide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatInverseLerp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: float | _Omitted = ...,
    b: float | _Omitted = ...,
    clamped: bool | _Omitted = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatLerp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: float | _Omitted = ...,
    b: float | _Omitted = ...,
    clamped: bool | _Omitted = ...,
    t: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatMax(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    value2: float | _Omitted = ...,
    value3: float | _Omitted = ...,
    value4: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatMin(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    value2: float | _Omitted = ...,
    value3: float | _Omitted = ...,
    value4: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    value2: float | _Omitted = ...,
    value3: float | _Omitted = ...,
    value4: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatPower(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base: float | _Omitted = ...,
    exponent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatRange1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end: float | _Omitted = ...,
    start: float | _Omitted = ...,
    step: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatRange2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end: float | _Omitted = ...,
    fence_posts: int | _Omitted = ...,
    start: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatRange3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end: float | _Omitted = ...,
    spans: int | _Omitted = ...,
    start: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    required: bool | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatSubtract(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: float | _Omitted = ...,
    value1: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatToInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatToString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2OutputToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    florence2_output: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2PostProcess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    generated_text: str | _Omitted = ...,
    task: Literal['<CAPTION>', '<DETAILED_CAPTION>', '<MORE_DETAILED_CAPTION>', '<OD>', '<DENSE_REGION_CAPTION>', '<REGION_PROPOSAL>', '<CAPTION_TO_PHRASE_GROUNDING>', '<REFERRING_EXPRESSION_SEGMENTATION>', '<REGION_TO_SEGMENTATION>', '<OPEN_VOCABULARY_DETECTION>', '<REGION_TO_CATEGORY>', '<REGION_TO_DESCRIPTION>', '<OCR>', '<OCR_WITH_REGION>'] | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2TaskTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    task: Literal['<CAPTION>', '<DETAILED_CAPTION>', '<MORE_DETAILED_CAPTION>', '<OD>', '<DENSE_REGION_CAPTION>', '<REGION_PROPOSAL>', '<CAPTION_TO_PHRASE_GROUNDING>', '<REFERRING_EXPRESSION_SEGMENTATION>', '<REGION_TO_SEGMENTATION>', '<OPEN_VOCABULARY_DETECTION>', '<REGION_TO_CATEGORY>', '<REGION_TO_DESCRIPTION>', '<OCR>', '<OCR_WITH_REGION>'] | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Flux2ImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Flux2MaxImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    width: int | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Flux2ProImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    width: int | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Flux2Scheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxDisableGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxEraseNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    dilate_pixels: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    guidance: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxKVCache(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxKontextImageScale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxKontextMaxImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: str | _Omitted = ...,
    guidance: float | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    input_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxKontextMultiReferenceLatentMethod(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    reference_latents_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxKontextProImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: str | _Omitted = ...,
    guidance: float | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    input_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxProExpandNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bottom: int | _Omitted = ...,
    guidance: float | _Omitted = ...,
    left: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    right: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    top: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxProFillNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    guidance: float | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxProUltraImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_upsampling: bool | _Omitted = ...,
    raw: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    image_prompt: Any | _Omitted = ...,
    image_prompt_strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxVTONode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    garment: Any | _Omitted = ...,
    person: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FrameInterpolate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    interp_model: Any | _Omitted = ...,
    multiplier: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FrameInterpolationModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FreSca(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    freq_cutoff: int | _Omitted = ...,
    scale_high: float | _Omitted = ...,
    scale_low: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FreeU(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    b1: float | _Omitted = ...,
    b2: float | _Omitted = ...,
    s1: float | _Omitted = ...,
    s2: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FreeU_V2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    b1: float | _Omitted = ...,
    b2: float | _Omitted = ...,
    s1: float | _Omitted = ...,
    s2: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GITSScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    coeff: float | _Omitted = ...,
    denoise: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GLIGENLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    gligen_name: Literal['gligen_sd14_textbox_pruned_fp16.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GLIGENTextBoxApply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    conditioning_to: Any | _Omitted = ...,
    gligen_textbox_model: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    text: str | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GLSLShader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bools: Any | _Omitted = ...,
    curves: Any | _Omitted = ...,
    floats: Any | _Omitted = ...,
    fragment_shader: str | _Omitted = ...,
    images: Any | _Omitted = ...,
    ints: Any | _Omitted = ...,
    size_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GeminiImage2Node(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    response_modalities: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    files: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GeminiImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    files: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    response_modalities: Any | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GeminiInputFiles(
    *args: VibeWorkflow,
    _id: str | None = ...,
    file: Any | _Omitted = ...,
    GEMINI_INPUT_FILES: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GeminiNanoBanana2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    response_modalities: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    thinking_level: Any | _Omitted = ...,
    files: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GeminiNanoBanana2V2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    response_modalities: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GeminiNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    audio: Any | _Omitted = ...,
    files: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    video: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GenerateTracks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bezier: bool | _Omitted = ...,
    end_x: float | _Omitted = ...,
    end_y: float | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Any | _Omitted = ...,
    mid_x: float | _Omitted = ...,
    mid_y: float | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    num_tracks: int | _Omitted = ...,
    start_x: float | _Omitted = ...,
    start_y: float | _Omitted = ...,
    track_spread: float | _Omitted = ...,
    width: int | _Omitted = ...,
    track_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetICLoRAParameters(
    *args: VibeWorkflow,
    _id: str | None = ...,
    iclora_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImageRangeFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    start_index: int | _Omitted = ...,
    images: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImageSize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetSplatCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    splat: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetVideoComponents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokImageEditNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    number_of_images: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokImageEditNodeV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    number_of_images: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokVideoEditNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokVideoExtendNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrokVideoReferenceNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GroupOffload(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrowMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    expand: int | _Omitted = ...,
    tapered_corners: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HappyHorseImageToVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_frame: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HappyHorseReferenceVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HappyHorseTextToVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HappyHorseVideoEditApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HashImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HiDreamO1PatchSeamSmoothing(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    blend: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    passes: Any | _Omitted = ...,
    pattern: Any | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HiDreamO1ReferenceImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HintImageEnchance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    hint_image: Any | _Omitted = ...,
    image_gen_height: int | _Omitted = ...,
    image_gen_width: int | _Omitted = ...,
    resize_mode: Literal['Just Resize', 'Crop and Resize', 'Resize and Fill'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HitPawGeneralImageEnhance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    auto_downscale: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    upscale_factor: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HitPawVideoEnhance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Hunyuan3Dv2Conditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision_output: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Hunyuan3Dv2ConditioningMultiView(
    *args: VibeWorkflow,
    _id: str | None = ...,
    back: Any | _Omitted = ...,
    front: Any | _Omitted = ...,
    left: Any | _Omitted = ...,
    right: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    guidance_type: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanRefinerLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    noise_augmentation: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanVideo15ImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanVideo15LatentUpscaleWithModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    crop: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanVideo15SuperResolution(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    noise_augmentation: float | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HyperTile(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    max_depth: int | _Omitted = ...,
    scale_depth: bool | _Omitted = ...,
    swap_size: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HypernetworkLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    hypernetwork_name: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Ideogram4Scheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    mu: float | _Omitted = ...,
    std: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramDescribe(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    api_key: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramEdit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    model: Literal['V_2', 'V_2_TURBO', 'V_3'] | _Omitted = ...,
    prompt: str | _Omitted = ...,
    api_key: str | _Omitted = ...,
    magic_prompt_option: Literal['AUTO', 'ON', 'OFF'] | _Omitted = ...,
    num_images: int | _Omitted = ...,
    rendering_speed: Literal['DEFAULT', 'TURBO', 'QUALITY'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_reference_images: Any | _Omitted = ...,
    style_type: Literal['AUTO', 'GENERAL', 'REALISTIC', 'DESIGN', 'RENDER_3D', 'ANIME'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramGenerate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    magic_prompt_option: Literal['AUTO', 'ON', 'OFF'] | _Omitted = ...,
    model: Literal['V_2', 'V_2_TURBO', 'V_3'] | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Literal['RESOLUTION_512_1536', 'RESOLUTION_576_1408', 'RESOLUTION_576_1472', 'RESOLUTION_576_1536', 'RESOLUTION_640_1024', 'RESOLUTION_640_1344', 'RESOLUTION_640_1408', 'RESOLUTION_640_1472', 'RESOLUTION_640_1536', 'RESOLUTION_704_1152', 'RESOLUTION_704_1216', 'RESOLUTION_704_1280', 'RESOLUTION_704_1344', 'RESOLUTION_704_1408', 'RESOLUTION_704_1472', 'RESOLUTION_720_1280', 'RESOLUTION_736_1312', 'RESOLUTION_768_1024', 'RESOLUTION_768_1088', 'RESOLUTION_768_1152', 'RESOLUTION_768_1216', 'RESOLUTION_768_1232', 'RESOLUTION_768_1280', 'RESOLUTION_768_1344', 'RESOLUTION_832_960', 'RESOLUTION_832_1024', 'RESOLUTION_832_1088', 'RESOLUTION_832_1152', 'RESOLUTION_832_1216', 'RESOLUTION_832_1248', 'RESOLUTION_864_1152', 'RESOLUTION_896_960', 'RESOLUTION_896_1024', 'RESOLUTION_896_1088', 'RESOLUTION_896_1120', 'RESOLUTION_896_1152', 'RESOLUTION_960_832', 'RESOLUTION_960_896', 'RESOLUTION_960_1024', 'RESOLUTION_960_1088', 'RESOLUTION_1024_640', 'RESOLUTION_1024_768', 'RESOLUTION_1024_832', 'RESOLUTION_1024_896', 'RESOLUTION_1024_960', 'RESOLUTION_1024_1024', 'RESOLUTION_1088_768', 'RESOLUTION_1088_832', 'RESOLUTION_1088_896', 'RESOLUTION_1088_960', 'RESOLUTION_1120_896', 'RESOLUTION_1152_704', 'RESOLUTION_1152_768', 'RESOLUTION_1152_832', 'RESOLUTION_1152_864', 'RESOLUTION_1152_896', 'RESOLUTION_1216_704', 'RESOLUTION_1216_768', 'RESOLUTION_1216_832', 'RESOLUTION_1232_768', 'RESOLUTION_1248_832', 'RESOLUTION_1280_704', 'RESOLUTION_1280_720', 'RESOLUTION_1280_768', 'RESOLUTION_1280_800', 'RESOLUTION_1312_736', 'RESOLUTION_1344_640', 'RESOLUTION_1344_704', 'RESOLUTION_1344_768', 'RESOLUTION_1408_576', 'RESOLUTION_1408_640', 'RESOLUTION_1408_704', 'RESOLUTION_1472_576', 'RESOLUTION_1472_640', 'RESOLUTION_1472_704', 'RESOLUTION_1536_512', 'RESOLUTION_1536_576', 'RESOLUTION_1536_640'] | _Omitted = ...,
    api_key: str | _Omitted = ...,
    aspect_ratio: Literal['disabled', '1x1', '10x16', '9x16', '3x4', '2x3', '16x10', '3x2', '4x3', '16x9'] | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    num_images: int | _Omitted = ...,
    rendering_speed: Literal['DEFAULT', 'TURBO', 'QUALITY'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_reference_images: Any | _Omitted = ...,
    style_type: Literal['AUTO', 'GENERAL', 'REALISTIC', 'DESIGN', 'RENDER_3D', 'ANIME'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramRemix(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    model: Literal['V_2', 'V_2_TURBO', 'V_3'] | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Literal['RESOLUTION_512_1536', 'RESOLUTION_576_1408', 'RESOLUTION_576_1472', 'RESOLUTION_576_1536', 'RESOLUTION_640_1024', 'RESOLUTION_640_1344', 'RESOLUTION_640_1408', 'RESOLUTION_640_1472', 'RESOLUTION_640_1536', 'RESOLUTION_704_1152', 'RESOLUTION_704_1216', 'RESOLUTION_704_1280', 'RESOLUTION_704_1344', 'RESOLUTION_704_1408', 'RESOLUTION_704_1472', 'RESOLUTION_720_1280', 'RESOLUTION_736_1312', 'RESOLUTION_768_1024', 'RESOLUTION_768_1088', 'RESOLUTION_768_1152', 'RESOLUTION_768_1216', 'RESOLUTION_768_1232', 'RESOLUTION_768_1280', 'RESOLUTION_768_1344', 'RESOLUTION_832_960', 'RESOLUTION_832_1024', 'RESOLUTION_832_1088', 'RESOLUTION_832_1152', 'RESOLUTION_832_1216', 'RESOLUTION_832_1248', 'RESOLUTION_864_1152', 'RESOLUTION_896_960', 'RESOLUTION_896_1024', 'RESOLUTION_896_1088', 'RESOLUTION_896_1120', 'RESOLUTION_896_1152', 'RESOLUTION_960_832', 'RESOLUTION_960_896', 'RESOLUTION_960_1024', 'RESOLUTION_960_1088', 'RESOLUTION_1024_640', 'RESOLUTION_1024_768', 'RESOLUTION_1024_832', 'RESOLUTION_1024_896', 'RESOLUTION_1024_960', 'RESOLUTION_1024_1024', 'RESOLUTION_1088_768', 'RESOLUTION_1088_832', 'RESOLUTION_1088_896', 'RESOLUTION_1088_960', 'RESOLUTION_1120_896', 'RESOLUTION_1152_704', 'RESOLUTION_1152_768', 'RESOLUTION_1152_832', 'RESOLUTION_1152_864', 'RESOLUTION_1152_896', 'RESOLUTION_1216_704', 'RESOLUTION_1216_768', 'RESOLUTION_1216_832', 'RESOLUTION_1232_768', 'RESOLUTION_1248_832', 'RESOLUTION_1280_704', 'RESOLUTION_1280_720', 'RESOLUTION_1280_768', 'RESOLUTION_1280_800', 'RESOLUTION_1312_736', 'RESOLUTION_1344_640', 'RESOLUTION_1344_704', 'RESOLUTION_1344_768', 'RESOLUTION_1408_576', 'RESOLUTION_1408_640', 'RESOLUTION_1408_704', 'RESOLUTION_1472_576', 'RESOLUTION_1472_640', 'RESOLUTION_1472_704', 'RESOLUTION_1536_512', 'RESOLUTION_1536_576', 'RESOLUTION_1536_640'] | _Omitted = ...,
    api_key: str | _Omitted = ...,
    aspect_ratio: Literal['disabled', '1x1', '10x16', '9x16', '3x4', '2x3', '16x10', '3x2', '4x3', '16x9'] | _Omitted = ...,
    image_weight: int | _Omitted = ...,
    magic_prompt_option: Literal['AUTO', 'ON', 'OFF'] | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    num_images: int | _Omitted = ...,
    rendering_speed: Literal['DEFAULT', 'TURBO', 'QUALITY'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_reference_images: Any | _Omitted = ...,
    style_type: Literal['AUTO', 'GENERAL', 'REALISTIC', 'DESIGN', 'RENDER_3D', 'ANIME'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramV1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    turbo: bool | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    magic_prompt_option: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    num_images: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    turbo: bool | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    magic_prompt_option: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    num_images: int | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_type: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramV3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    character_image: Any | _Omitted = ...,
    character_mask: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    magic_prompt_option: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    num_images: int | _Omitted = ...,
    rendering_speed: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IdeogramV4(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    rendering_speed: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageAddNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageAndMaskResizeNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    crop: Literal['disabled', 'center', 'top_left', 'top_right', 'bottom_left', 'bottom_right'] | _Omitted = ...,
    height: int | _Omitted = ...,
    mask_blur_radius: int | _Omitted = ...,
    resize_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageApplyColorMap(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    clip_max: bool | _Omitted = ...,
    clip_min: bool | _Omitted = ...,
    colormap: Literal['Grayscale', 'COLORMAP_AUTUMN', 'COLORMAP_BONE', 'COLORMAP_CIVIDIS', 'COLORMAP_COOL', 'COLORMAP_DEEPGREEN', 'COLORMAP_HOT', 'COLORMAP_HSV', 'COLORMAP_INFERNO', 'COLORMAP_JET', 'COLORMAP_MAGMA', 'COLORMAP_OCEAN', 'COLORMAP_PARULA', 'COLORMAP_PINK', 'COLORMAP_PLASMA', 'COLORMAP_RAINBOW', 'COLORMAP_SPRING', 'COLORMAP_SUMMER', 'COLORMAP_TURBO', 'COLORMAP_TWILIGHT', 'COLORMAP_TWILIGHT_SHIFTED', 'COLORMAP_VIRIDIS', 'COLORMAP_WINTER'] | _Omitted = ...,
    gamma: float | _Omitted = ...,
    max_depth: float | _Omitted = ...,
    min_depth: float | _Omitted = ...,
    one_minus: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBlend(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    blend_factor: float | _Omitted = ...,
    blend_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBlur(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    blur_radius: int | _Omitted = ...,
    sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageColorToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    color: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCompare(
    *args: VibeWorkflow,
    _id: str | None = ...,
    compare_view: Any | _Omitted = ...,
    image_a: Any | _Omitted = ...,
    image_b: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCompositeMasked(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    resize_source: bool | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCrop(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCropV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    crop_region: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageDeduplication(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    similarity_threshold: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageExif(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    Artist: str | _Omitted = ...,
    CreationDate: str | _Omitted = ...,
    Description: str | _Omitted = ...,
    ImageNumber: str | _Omitted = ...,
    Rating: str | _Omitted = ...,
    Title: str | _Omitted = ...,
    UserComment: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageExifCreationDateAndBatchNumber(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageExifMerge(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: Any | _Omitted = ...,
    value1: Any | _Omitted = ...,
    value2: Any | _Omitted = ...,
    value3: Any | _Omitted = ...,
    value4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageExifUncommon(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    ApertureValue: str | _Omitted = ...,
    Artist: str | _Omitted = ...,
    BrightnessValue: str | _Omitted = ...,
    CreationDate: str | _Omitted = ...,
    DateTimeOriginal: str | _Omitted = ...,
    Description: str | _Omitted = ...,
    DigitalZoomRatio: str | _Omitted = ...,
    ExposureMode: str | _Omitted = ...,
    ExposureTime: str | _Omitted = ...,
    FNumber: str | _Omitted = ...,
    Flash: str | _Omitted = ...,
    FocalLength: str | _Omitted = ...,
    FocalLengthIn35mmFilm: str | _Omitted = ...,
    GPSAltitude: str | _Omitted = ...,
    GPSLatitude: str | _Omitted = ...,
    GPSLongitude: str | _Omitted = ...,
    GPSTimeStamp: str | _Omitted = ...,
    ISO: str | _Omitted = ...,
    ImageNumber: str | _Omitted = ...,
    LensMake: str | _Omitted = ...,
    LensModel: str | _Omitted = ...,
    Make: str | _Omitted = ...,
    MeteringMode: str | _Omitted = ...,
    Model: str | _Omitted = ...,
    Rating: str | _Omitted = ...,
    SceneCaptureType: str | _Omitted = ...,
    ShutterSpeedValue: str | _Omitted = ...,
    Title: str | _Omitted = ...,
    UserComment: str | _Omitted = ...,
    WhiteBalance: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageFlip(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    flip_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    batch_index: int | _Omitted = ...,
    length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGenResolutionFromImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGenResolutionFromLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGenerateGradient(
    *args: VibeWorkflow,
    _id: str | None = ...,
    direction: Literal['horizontal', 'vertical'] | _Omitted = ...,
    gradient_stops: str | _Omitted = ...,
    height: int | _Omitted = ...,
    tolerance: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGrid(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    cell_height: int | _Omitted = ...,
    cell_width: int | _Omitted = ...,
    columns: int | _Omitted = ...,
    padding: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageHistogram(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageInvert(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageLevels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    black_level: float | _Omitted = ...,
    clip: bool | _Omitted = ...,
    mid_level: float | _Omitted = ...,
    white_level: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageLuminance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageMax(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageMergeTileList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_list: Any | _Omitted = ...,
    final_height: int | _Omitted = ...,
    final_width: int | _Omitted = ...,
    overlap: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageMin(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageOnlyCheckpointLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['stable_zero123.ckpt'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageOnlyCheckpointSave(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePadForOutpaint(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bottom: int | _Omitted = ...,
    feathering: int | _Omitted = ...,
    left: int | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageQuantize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    colors: int | _Omitted = ...,
    dither: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageRGBToYUV(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    required: bool | _Omitted = ...,
    alpha_is_transparency: bool | _Omitted = ...,
    default_if_empty: Any | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageResize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    interpolation: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    resize_mode: Literal['cover', 'contain', 'auto'] | _Omitted = ...,
    resolutions: Literal['SDXL/SD3/Flux', 'SD1.5', 'LTXV', 'Ideogram', 'Cosmos', 'HunyuanVideo', 'WAN 14b', 'WAN 1.3b', 'WAN 14b with extras', 'HiDream 1 Edit', 'Kontext', 'Unknown', 'Qwen Image'] | _Omitted = ...,
    aspect_ratio_tolerance: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageResize1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    resize_mode: Literal['cover', 'contain', 'auto'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageRotate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    rotation: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    height: int | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScaleBy(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    scale_by: float | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScaleToMaxDimension(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    largest_size: int | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScaleToTotalPixels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    megapixels: float | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    resolution_steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageShape(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageSharpen(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    alpha: float | _Omitted = ...,
    sharpen_radius: int | _Omitted = ...,
    sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageStitch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    direction: Any | _Omitted = ...,
    match_image_size: bool | _Omitted = ...,
    spacing_color: Any | _Omitted = ...,
    spacing_width: int | _Omitted = ...,
    image2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    channel: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageToSVG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    color_precision: int | _Omitted = ...,
    colormode: Literal['color', 'binary'] | _Omitted = ...,
    corner_threshold: int | _Omitted = ...,
    filter_speckle: int | _Omitted = ...,
    hierarchical: Literal['stacked', 'cutout'] | _Omitted = ...,
    layer_difference: int | _Omitted = ...,
    length_threshold: float | _Omitted = ...,
    max_iterations: int | _Omitted = ...,
    mode: Literal['spline', 'polygon', 'none'] | _Omitted = ...,
    path_precision: int | _Omitted = ...,
    splice_threshold: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageUpscaleWithModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    upscale_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageYUVToRGB(
    *args: VibeWorkflow,
    _id: str | None = ...,
    U: Any | _Omitted = ...,
    V: Any | _Omitted = ...,
    Y: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InpaintModelConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    pixels: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    noise_mask: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InstructPixToPixConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    pixels: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntAbs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntAdd(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    value2: int | _Omitted = ...,
    value3: int | _Omitted = ...,
    value4: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntAverage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    value2: int | _Omitted = ...,
    value3: int | _Omitted = ...,
    value4: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntClamp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    max: int | _Omitted = ...,
    min: int | _Omitted = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntDivide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntInverseLerp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: int | _Omitted = ...,
    b: int | _Omitted = ...,
    clamped: bool | _Omitted = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntLerp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: int | _Omitted = ...,
    b: int | _Omitted = ...,
    clamped: bool | _Omitted = ...,
    t: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntMax(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    value2: int | _Omitted = ...,
    value3: int | _Omitted = ...,
    value4: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntMin(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    value2: int | _Omitted = ...,
    value3: int | _Omitted = ...,
    value4: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntMod(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    value2: int | _Omitted = ...,
    value3: int | _Omitted = ...,
    value4: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntPower(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base: int | _Omitted = ...,
    exponent: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntRange(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end: int | _Omitted = ...,
    start: int | _Omitted = ...,
    step: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    required: bool | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntSubtract(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: int | _Omitted = ...,
    value1: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntToFloat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IntToString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InvertMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IsNone(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def IterateList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def JoinAudioChannels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_left: Any | _Omitted = ...,
    audio_right: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def JoinImageWithAlpha(
    *args: VibeWorkflow,
    _id: str | None = ...,
    alpha: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def JsonExtractString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    json_string: str | _Omitted = ...,
    key: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent_image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    denoise: float | _Omitted = ...,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSamplerAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent_image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    add_noise: Literal['enable', 'disable'] | _Omitted = ...,
    cfg: float | _Omitted = ...,
    end_at_step: int | _Omitted = ...,
    noise_seed: int | _Omitted = ...,
    return_with_leftover_noise: Literal['disable', 'enable'] | _Omitted = ...,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    start_at_step: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSamplerSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sampler_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Kandinsky5ImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KarrasScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    rho: float | _Omitted = ...,
    sigma_max: float | _Omitted = ...,
    sigma_min: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingAvatarNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    sound_file: Any | _Omitted = ...,
    mode: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingCameraControlI2VNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_frame: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    camera_control: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingCameraControlT2VNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    camera_control: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingCameraControls(
    *args: VibeWorkflow,
    _id: str | None = ...,
    camera_control_type: Any | _Omitted = ...,
    horizontal_movement: float | _Omitted = ...,
    pan: float | _Omitted = ...,
    roll: float | _Omitted = ...,
    tilt: float | _Omitted = ...,
    vertical_movement: float | _Omitted = ...,
    zoom: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingDualCharacterVideoEffectNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_left: Any | _Omitted = ...,
    image_right: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    effect_scene: Any | _Omitted = ...,
    mode: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingFirstLastFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    first_frame: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingImage2VideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_frame: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    duration: Any | _Omitted = ...,
    mode: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingImageGenerationNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    human_fidelity: float | _Omitted = ...,
    image_fidelity: float | _Omitted = ...,
    image_type: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingImageToVideoWithAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_frame: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    mode: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingLipSyncAudioToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    video: Any | _Omitted = ...,
    voice_language: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingLipSyncTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    voice: Any | _Omitted = ...,
    voice_speed: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingMotionControl(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_image: Any | _Omitted = ...,
    reference_video: Any | _Omitted = ...,
    character_orientation: Any | _Omitted = ...,
    keep_original_sound: bool | _Omitted = ...,
    mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingOmniProEditVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    keep_original_sound: bool | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingOmniProFirstLastFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_frame: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    end_frame: Any | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    storyboards: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingOmniProImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    series_amount: Any | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingOmniProImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_images: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    storyboards: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingOmniProTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    storyboards: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingOmniProVideoToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_video: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    keep_original_sound: bool | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingSingleImageVideoEffectNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    effect_scene: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingStartEndFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    start_frame: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    mode: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    mode: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingTextToVideoWithAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    mode: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingVideoExtendNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cfg_scale: float | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    video_id: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    generate_audio: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    multi_shot: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    start_frame: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KlingVirtualTryOnNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cloth_image: Any | _Omitted = ...,
    human_image: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Krea2ImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Krea2StyleReferenceNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    style_reference: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAVTextEncoderLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Any | _Omitted = ...,
    device: Any | _Omitted = ...,
    text_encoder: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    attention_mask: Any | _Omitted = ...,
    iclora_parameters: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuideMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_guides: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuidesFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_vae: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAEEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    audio_vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAELoader1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVConcatAVLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_latent: Any | _Omitted = ...,
    video_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    frame_rate: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVCropGuides(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVEmptyLatentAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    frame_rate: int | _Omitted = ...,
    frames_number: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoInplace(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    bypass: bool | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVLatentUpsampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    upscale_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPreprocess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    img_compression: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVReferenceAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_vae: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    reference_audio: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    identity_guidance_scale: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base_shift: float | _Omitted = ...,
    max_shift: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    stretch: bool | _Omitted = ...,
    terminal: float | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSeparateAVLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    av_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LaplaceScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    beta: float | _Omitted = ...,
    mu: float | _Omitted = ...,
    sigma_max: float | _Omitted = ...,
    sigma_min: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentAdd(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentAddNoiseChannels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    slice_i: int | _Omitted = ...,
    slice_j: int | _Omitted = ...,
    std_dev: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentApplyOperation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    operation: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentApplyOperationCFG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    operation: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentBatchSeedBehavior(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    seed_behavior: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentBlend(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    blend_factor: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentComposite(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples_from: Any | _Omitted = ...,
    samples_to: Any | _Omitted = ...,
    feather: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentCompositeMasked(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    resize_source: bool | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentConcat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    dim: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentCrop(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentCut(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    amount: int | _Omitted = ...,
    dim: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentCutToBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    dim: Any | _Omitted = ...,
    slice_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentFlip(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    flip_method: Literal['x-axis: vertically', 'y-axis: horizontally'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    batch_index: int | _Omitted = ...,
    length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentInterpolate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    ratio: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentOperationSharpen(
    *args: VibeWorkflow,
    _id: str | None = ...,
    alpha: float | _Omitted = ...,
    sharpen_radius: int | _Omitted = ...,
    sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentOperationTonemapReinhard(
    *args: VibeWorkflow,
    _id: str | None = ...,
    multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentRotate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    rotation: Literal['none', '90 degrees', '180 degrees', '270 degrees'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentSubtract(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples1: Any | _Omitted = ...,
    samples2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentUpscale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    height: int | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentUpscaleBy(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    scale_by: float | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentUpscaleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['hunyuanvideo15_latent_upsampler_1080p.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltx-2.3-temporal-upscaler-x2-1.0.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentUpscaleModelLoader1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LayerwiseCast(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    dtype: Literal['float8_e4m3fn', 'float8_e5m2'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LazyCache(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    reuse_threshold: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LazySwitch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    switch: bool | _Omitted = ...,
    on_false: Any | _Omitted = ...,
    on_true: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LegacyOutputURIs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    prefix: str | _Omitted = ...,
    suffix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Load3D(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    model_file: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadAudioFromURL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    default_if_empty: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadBackgroundRemovalModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bg_removal_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImageDataSetFromFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    folder: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImageFromURL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    alpha_is_transparency: bool | _Omitted = ...,
    default_if_empty: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImageMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    channel: Literal['alpha', 'red', 'green', 'blue'] | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImageOutput(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImageTextDataSetFromFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    folder: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadMediaPipeFaceLandmarker(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadMoGeModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadTrainingDataset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    folder_name: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    file: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVideoFromURL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    default_if_empty: Any | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    lora_name: Literal['Flux2TurboComfyv2.safetensors', 'Flux_2-Turbo-LoRA_comfyui.safetensors', 'GoodHands-beta2.safetensors', 'Hyper-SD15-12steps-CFG-lora.safetensors', 'Hyper-SDXL-12steps-CFG-lora.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'PixelArtRedmond15V-PixelArt-PIXARFK.safetensors', 'Qwen-Edit-2509-Multiple-angles.safetensors', 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'Qwen-Image-Edit-2509-Anything2RealAlpha.safetensors', 'Qwen-Image-Edit-2509-Fusion.safetensors', 'Qwen-Image-Edit-2509-Light-Migration.safetensors', 'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Relight.safetensors', 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors', 'Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors', 'Qwen-Image-Lightning-4steps-V2.0.safetensors', 'Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors', 'Qwen-Image-Lightning-8steps-V2.0.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'Wuli-Qwen-Image-2512-Turbo-LoRA-2steps-V1.0-bf16.safetensors', 'blur_control_xl_v1.safetensors', 'chronoedit_distill_lora.safetensors', 'flux1-canny-dev-lora.safetensors', 'flux1-depth-dev-lora.safetensors', 'gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors', 'gummycandy_qwen.safetensors', 'illustration-1.0-qwen-image.safetensors', 'lcm_lora_sdxl.safetensors', 'lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors', 'ltx-2-19b-distilled-lora-384.safetensors', 'ltx-2-19b-ic-lora-canny-control.safetensors', 'ltx-2-19b-ic-lora-depth-control.safetensors', 'ltx-2-19b-ic-lora-pose-control.safetensors', 'ltx-2-19b-lora-camera-control-dolly-left.safetensors', 'ltx-2.3-22b-distilled-lora-384.safetensors', 'ltx-2.3-id-lora-talkvid-3k.safetensors', 'ltx2-squish.safetensors', 'ltx2.3-transition.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'openxl_handsfix.safetensors', 'qwen-image-edit-2511-multiple-angles-lora.safetensors', 'qwen_image_union_diffsynth_lora.safetensors', 'uso-flux1-dit-lora-v1.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors', 'wan_alpha_2.1_rgba_lora.safetensors'] | _Omitted = ...,
    strength_clip: float | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraLoaderBypass(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    strength_clip: float | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraLoaderBypassModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraLoaderModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora_name: Literal['Flux2TurboComfyv2.safetensors', 'Flux_2-Turbo-LoRA_comfyui.safetensors', 'GoodHands-beta2.safetensors', 'Hyper-SD15-12steps-CFG-lora.safetensors', 'Hyper-SDXL-12steps-CFG-lora.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'PixelArtRedmond15V-PixelArt-PIXARFK.safetensors', 'Qwen-Edit-2509-Multiple-angles.safetensors', 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'Qwen-Image-Edit-2509-Anything2RealAlpha.safetensors', 'Qwen-Image-Edit-2509-Fusion.safetensors', 'Qwen-Image-Edit-2509-Light-Migration.safetensors', 'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Relight.safetensors', 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors', 'Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors', 'Qwen-Image-Lightning-4steps-V2.0.safetensors', 'Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors', 'Qwen-Image-Lightning-8steps-V2.0.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'Wuli-Qwen-Image-2512-Turbo-LoRA-2steps-V1.0-bf16.safetensors', 'blur_control_xl_v1.safetensors', 'chronoedit_distill_lora.safetensors', 'flux1-canny-dev-lora.safetensors', 'flux1-depth-dev-lora.safetensors', 'gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors', 'gummycandy_qwen.safetensors', 'illustration-1.0-qwen-image.safetensors', 'ip-adapter-faceid-plus_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sdxl_lora.safetensors', 'ip-adapter-faceid_sd15_lora.safetensors', 'ip-adapter-faceid_sdxl_lora.safetensors', 'lcm_lora_sdxl.safetensors', 'lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors', 'ltx-2-19b-distilled-lora-384.safetensors', 'ltx-2-19b-ic-lora-canny-control.safetensors', 'ltx-2-19b-ic-lora-depth-control.safetensors', 'ltx-2-19b-ic-lora-pose-control.safetensors', 'ltx-2-19b-lora-camera-control-dolly-left.safetensors', 'ltx-2.3-22b-distilled-lora-384.safetensors', 'ltx-2.3-id-lora-talkvid-3k.safetensors', 'ltx2-squish.safetensors', 'ltx2.3-transition.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'openxl_handsfix.safetensors', 'qwen-image-edit-2511-multiple-angles-lora.safetensors', 'qwen_image_union_diffsynth_lora.safetensors', 'uso-flux1-dit-lora-v1.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors', 'wan_alpha_2.1_rgba_lora.safetensors'] | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    bypass: bool | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraSave(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bias_diff: bool | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    lora_type: Any | _Omitted = ...,
    rank: int | _Omitted = ...,
    model_diff: Any | _Omitted = ...,
    text_encoder_diff: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LossGraphNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename_prefix: str | _Omitted = ...,
    loss: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LotusConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LtxvApiImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    fps: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LtxvApiTextToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    duration: Any | _Omitted = ...,
    fps: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaConceptsNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    concept1: Any | _Omitted = ...,
    concept2: Any | _Omitted = ...,
    concept3: Any | _Omitted = ...,
    concept4: Any | _Omitted = ...,
    luma_concepts: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaImageEditNode2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaImageModifyNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    image_weight: float | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_image_weight: float | _Omitted = ...,
    character_image: Any | _Omitted = ...,
    image_luma_ref: Any | _Omitted = ...,
    style_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaImageNode2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    duration: Any | _Omitted = ...,
    loop: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    first_image: Any | _Omitted = ...,
    last_image: Any | _Omitted = ...,
    luma_concepts: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaReferenceNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    weight: float | _Omitted = ...,
    luma_ref: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LumaVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    loop: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    luma_concepts: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MagnificImageRelightNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    advanced_settings: Any | _Omitted = ...,
    change_background: bool | _Omitted = ...,
    interpolate_from_original: bool | _Omitted = ...,
    light_transfer_strength: int | _Omitted = ...,
    preserve_details: bool | _Omitted = ...,
    prompt: str | _Omitted = ...,
    style: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MagnificImageSkinEnhancerNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mode: Any | _Omitted = ...,
    sharpen: int | _Omitted = ...,
    smart_grain: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MagnificImageStyleTransferNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    engine: Any | _Omitted = ...,
    fixed_generation: bool | _Omitted = ...,
    flavor: Any | _Omitted = ...,
    portrait_mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    structure_strength: int | _Omitted = ...,
    style_strength: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MagnificImageUpscalerCreativeNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    auto_downscale: bool | _Omitted = ...,
    creativity: int | _Omitted = ...,
    engine: Any | _Omitted = ...,
    fractality: int | _Omitted = ...,
    hdr: int | _Omitted = ...,
    optimized_for: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resemblance: int | _Omitted = ...,
    scale_factor: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MagnificImageUpscalerPreciseV2Node(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    auto_downscale: bool | _Omitted = ...,
    flavor: Any | _Omitted = ...,
    scale_factor: Any | _Omitted = ...,
    sharpen: int | _Omitted = ...,
    smart_grain: int | _Omitted = ...,
    ultra_detail: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Mahiro(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MakeTrainingDataset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ManualSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskComposite(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    operation: Any | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskToImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MediaPipeFaceLandmarker(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    detector_variant: Any | _Omitted = ...,
    face_detection_model: Any | _Omitted = ...,
    min_confidence: float | _Omitted = ...,
    missing_frame_fallback: Any | _Omitted = ...,
    num_faces: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MediaPipeFaceMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    face_landmarks: Any | _Omitted = ...,
    regions: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MediaPipeFaceMeshVisualize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    color: Any | _Omitted = ...,
    connections: Any | _Omitted = ...,
    face_landmarks: Any | _Omitted = ...,
    point_size: int | _Omitted = ...,
    thickness: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MergeImageLists(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MergeSplat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    splats: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MergeTextLists(
    *args: VibeWorkflow,
    _id: str | None = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyAnimateModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    action_id: int | _Omitted = ...,
    rig_task_id: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyImageToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    pose_mode: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    should_remesh: Any | _Omitted = ...,
    should_texture: Any | _Omitted = ...,
    symmetry_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyMultiImageToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    pose_mode: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    should_remesh: Any | _Omitted = ...,
    should_texture: Any | _Omitted = ...,
    symmetry_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyRefineNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    enable_pbr: bool | _Omitted = ...,
    meshy_task_id: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    texture_prompt: str | _Omitted = ...,
    texture_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyRigModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height_meters: float | _Omitted = ...,
    meshy_task_id: Any | _Omitted = ...,
    texture_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyTextToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pose_mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    should_remesh: Any | _Omitted = ...,
    style: Any | _Omitted = ...,
    symmetry_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MeshyTextureNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    enable_original_uv: bool | _Omitted = ...,
    meshy_task_id: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    pbr: bool | _Omitted = ...,
    text_style_prompt: str | _Omitted = ...,
    image_style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MinimaxHailuoVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_text: str | _Omitted = ...,
    duration: Any | _Omitted = ...,
    first_frame_image: Any | _Omitted = ...,
    prompt_optimizer: bool | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MinimaxImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt_text: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MinimaxTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt_text: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoGeInference(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    apply_mask: bool | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    force_projection: bool | _Omitted = ...,
    fov_x_degrees: float | _Omitted = ...,
    moge_model: Any | _Omitted = ...,
    resolution_level: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoGePanoramaInference(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    merge_resolution: int | _Omitted = ...,
    moge_model: Any | _Omitted = ...,
    resolution_level: int | _Omitted = ...,
    split_resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoGePointMapToMesh(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_index: int | _Omitted = ...,
    decimation: int | _Omitted = ...,
    discontinuity_threshold: float | _Omitted = ...,
    moge_geometry: Any | _Omitted = ...,
    texture: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoGeRender(
    *args: VibeWorkflow,
    _id: str | None = ...,
    moge_geometry: Any | _Omitted = ...,
    output: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelComputeDtype(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    dtype: Literal['default', 'fp32', 'fp16', 'bf16'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeAdd(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeAuraflow(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    cond_seq_linear: float | _Omitted = ...,
    double_layers_0: float | _Omitted = ...,
    double_layers_1: float | _Omitted = ...,
    double_layers_2: float | _Omitted = ...,
    double_layers_3: float | _Omitted = ...,
    final_linear: float | _Omitted = ...,
    init_x_linear: float | _Omitted = ...,
    modF: float | _Omitted = ...,
    positional_encoding: float | _Omitted = ...,
    register_tokens: float | _Omitted = ...,
    single_layers_0: float | _Omitted = ...,
    single_layers_1: float | _Omitted = ...,
    single_layers_10: float | _Omitted = ...,
    single_layers_11: float | _Omitted = ...,
    single_layers_12: float | _Omitted = ...,
    single_layers_13: float | _Omitted = ...,
    single_layers_14: float | _Omitted = ...,
    single_layers_15: float | _Omitted = ...,
    single_layers_16: float | _Omitted = ...,
    single_layers_17: float | _Omitted = ...,
    single_layers_18: float | _Omitted = ...,
    single_layers_19: float | _Omitted = ...,
    single_layers_2: float | _Omitted = ...,
    single_layers_20: float | _Omitted = ...,
    single_layers_21: float | _Omitted = ...,
    single_layers_22: float | _Omitted = ...,
    single_layers_23: float | _Omitted = ...,
    single_layers_24: float | _Omitted = ...,
    single_layers_25: float | _Omitted = ...,
    single_layers_26: float | _Omitted = ...,
    single_layers_27: float | _Omitted = ...,
    single_layers_28: float | _Omitted = ...,
    single_layers_29: float | _Omitted = ...,
    single_layers_3: float | _Omitted = ...,
    single_layers_30: float | _Omitted = ...,
    single_layers_31: float | _Omitted = ...,
    single_layers_4: float | _Omitted = ...,
    single_layers_5: float | _Omitted = ...,
    single_layers_6: float | _Omitted = ...,
    single_layers_7: float | _Omitted = ...,
    single_layers_8: float | _Omitted = ...,
    single_layers_9: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeBlocks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    input: float | _Omitted = ...,
    middle: float | _Omitted = ...,
    out: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeCosmos14B(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    affline_norm: float | _Omitted = ...,
    blocks_block0: float | _Omitted = ...,
    blocks_block1: float | _Omitted = ...,
    blocks_block10: float | _Omitted = ...,
    blocks_block11: float | _Omitted = ...,
    blocks_block12: float | _Omitted = ...,
    blocks_block13: float | _Omitted = ...,
    blocks_block14: float | _Omitted = ...,
    blocks_block15: float | _Omitted = ...,
    blocks_block16: float | _Omitted = ...,
    blocks_block17: float | _Omitted = ...,
    blocks_block18: float | _Omitted = ...,
    blocks_block19: float | _Omitted = ...,
    blocks_block2: float | _Omitted = ...,
    blocks_block20: float | _Omitted = ...,
    blocks_block21: float | _Omitted = ...,
    blocks_block22: float | _Omitted = ...,
    blocks_block23: float | _Omitted = ...,
    blocks_block24: float | _Omitted = ...,
    blocks_block25: float | _Omitted = ...,
    blocks_block26: float | _Omitted = ...,
    blocks_block27: float | _Omitted = ...,
    blocks_block28: float | _Omitted = ...,
    blocks_block29: float | _Omitted = ...,
    blocks_block3: float | _Omitted = ...,
    blocks_block30: float | _Omitted = ...,
    blocks_block31: float | _Omitted = ...,
    blocks_block32: float | _Omitted = ...,
    blocks_block33: float | _Omitted = ...,
    blocks_block34: float | _Omitted = ...,
    blocks_block35: float | _Omitted = ...,
    blocks_block4: float | _Omitted = ...,
    blocks_block5: float | _Omitted = ...,
    blocks_block6: float | _Omitted = ...,
    blocks_block7: float | _Omitted = ...,
    blocks_block8: float | _Omitted = ...,
    blocks_block9: float | _Omitted = ...,
    extra_pos_embedder: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    pos_embedder: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    x_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeCosmos7B(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    affline_norm: float | _Omitted = ...,
    blocks_block0: float | _Omitted = ...,
    blocks_block1: float | _Omitted = ...,
    blocks_block10: float | _Omitted = ...,
    blocks_block11: float | _Omitted = ...,
    blocks_block12: float | _Omitted = ...,
    blocks_block13: float | _Omitted = ...,
    blocks_block14: float | _Omitted = ...,
    blocks_block15: float | _Omitted = ...,
    blocks_block16: float | _Omitted = ...,
    blocks_block17: float | _Omitted = ...,
    blocks_block18: float | _Omitted = ...,
    blocks_block19: float | _Omitted = ...,
    blocks_block2: float | _Omitted = ...,
    blocks_block20: float | _Omitted = ...,
    blocks_block21: float | _Omitted = ...,
    blocks_block22: float | _Omitted = ...,
    blocks_block23: float | _Omitted = ...,
    blocks_block24: float | _Omitted = ...,
    blocks_block25: float | _Omitted = ...,
    blocks_block26: float | _Omitted = ...,
    blocks_block27: float | _Omitted = ...,
    blocks_block3: float | _Omitted = ...,
    blocks_block4: float | _Omitted = ...,
    blocks_block5: float | _Omitted = ...,
    blocks_block6: float | _Omitted = ...,
    blocks_block7: float | _Omitted = ...,
    blocks_block8: float | _Omitted = ...,
    blocks_block9: float | _Omitted = ...,
    extra_pos_embedder: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    pos_embedder: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    x_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeCosmosPredict2_14B(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    blocks_0: float | _Omitted = ...,
    blocks_1: float | _Omitted = ...,
    blocks_10: float | _Omitted = ...,
    blocks_11: float | _Omitted = ...,
    blocks_12: float | _Omitted = ...,
    blocks_13: float | _Omitted = ...,
    blocks_14: float | _Omitted = ...,
    blocks_15: float | _Omitted = ...,
    blocks_16: float | _Omitted = ...,
    blocks_17: float | _Omitted = ...,
    blocks_18: float | _Omitted = ...,
    blocks_19: float | _Omitted = ...,
    blocks_2: float | _Omitted = ...,
    blocks_20: float | _Omitted = ...,
    blocks_21: float | _Omitted = ...,
    blocks_22: float | _Omitted = ...,
    blocks_23: float | _Omitted = ...,
    blocks_24: float | _Omitted = ...,
    blocks_25: float | _Omitted = ...,
    blocks_26: float | _Omitted = ...,
    blocks_27: float | _Omitted = ...,
    blocks_28: float | _Omitted = ...,
    blocks_29: float | _Omitted = ...,
    blocks_3: float | _Omitted = ...,
    blocks_30: float | _Omitted = ...,
    blocks_31: float | _Omitted = ...,
    blocks_32: float | _Omitted = ...,
    blocks_33: float | _Omitted = ...,
    blocks_34: float | _Omitted = ...,
    blocks_35: float | _Omitted = ...,
    blocks_4: float | _Omitted = ...,
    blocks_5: float | _Omitted = ...,
    blocks_6: float | _Omitted = ...,
    blocks_7: float | _Omitted = ...,
    blocks_8: float | _Omitted = ...,
    blocks_9: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    pos_embedder: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    t_embedding_norm: float | _Omitted = ...,
    x_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeCosmosPredict2_2B(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    blocks_0: float | _Omitted = ...,
    blocks_1: float | _Omitted = ...,
    blocks_10: float | _Omitted = ...,
    blocks_11: float | _Omitted = ...,
    blocks_12: float | _Omitted = ...,
    blocks_13: float | _Omitted = ...,
    blocks_14: float | _Omitted = ...,
    blocks_15: float | _Omitted = ...,
    blocks_16: float | _Omitted = ...,
    blocks_17: float | _Omitted = ...,
    blocks_18: float | _Omitted = ...,
    blocks_19: float | _Omitted = ...,
    blocks_2: float | _Omitted = ...,
    blocks_20: float | _Omitted = ...,
    blocks_21: float | _Omitted = ...,
    blocks_22: float | _Omitted = ...,
    blocks_23: float | _Omitted = ...,
    blocks_24: float | _Omitted = ...,
    blocks_25: float | _Omitted = ...,
    blocks_26: float | _Omitted = ...,
    blocks_27: float | _Omitted = ...,
    blocks_3: float | _Omitted = ...,
    blocks_4: float | _Omitted = ...,
    blocks_5: float | _Omitted = ...,
    blocks_6: float | _Omitted = ...,
    blocks_7: float | _Omitted = ...,
    blocks_8: float | _Omitted = ...,
    blocks_9: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    pos_embedder: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    t_embedding_norm: float | _Omitted = ...,
    x_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeFlux1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    double_blocks_0: float | _Omitted = ...,
    double_blocks_1: float | _Omitted = ...,
    double_blocks_10: float | _Omitted = ...,
    double_blocks_11: float | _Omitted = ...,
    double_blocks_12: float | _Omitted = ...,
    double_blocks_13: float | _Omitted = ...,
    double_blocks_14: float | _Omitted = ...,
    double_blocks_15: float | _Omitted = ...,
    double_blocks_16: float | _Omitted = ...,
    double_blocks_17: float | _Omitted = ...,
    double_blocks_18: float | _Omitted = ...,
    double_blocks_2: float | _Omitted = ...,
    double_blocks_3: float | _Omitted = ...,
    double_blocks_4: float | _Omitted = ...,
    double_blocks_5: float | _Omitted = ...,
    double_blocks_6: float | _Omitted = ...,
    double_blocks_7: float | _Omitted = ...,
    double_blocks_8: float | _Omitted = ...,
    double_blocks_9: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    guidance_in: float | _Omitted = ...,
    img_in: float | _Omitted = ...,
    single_blocks_0: float | _Omitted = ...,
    single_blocks_1: float | _Omitted = ...,
    single_blocks_10: float | _Omitted = ...,
    single_blocks_11: float | _Omitted = ...,
    single_blocks_12: float | _Omitted = ...,
    single_blocks_13: float | _Omitted = ...,
    single_blocks_14: float | _Omitted = ...,
    single_blocks_15: float | _Omitted = ...,
    single_blocks_16: float | _Omitted = ...,
    single_blocks_17: float | _Omitted = ...,
    single_blocks_18: float | _Omitted = ...,
    single_blocks_19: float | _Omitted = ...,
    single_blocks_2: float | _Omitted = ...,
    single_blocks_20: float | _Omitted = ...,
    single_blocks_21: float | _Omitted = ...,
    single_blocks_22: float | _Omitted = ...,
    single_blocks_23: float | _Omitted = ...,
    single_blocks_24: float | _Omitted = ...,
    single_blocks_25: float | _Omitted = ...,
    single_blocks_26: float | _Omitted = ...,
    single_blocks_27: float | _Omitted = ...,
    single_blocks_28: float | _Omitted = ...,
    single_blocks_29: float | _Omitted = ...,
    single_blocks_3: float | _Omitted = ...,
    single_blocks_30: float | _Omitted = ...,
    single_blocks_31: float | _Omitted = ...,
    single_blocks_32: float | _Omitted = ...,
    single_blocks_33: float | _Omitted = ...,
    single_blocks_34: float | _Omitted = ...,
    single_blocks_35: float | _Omitted = ...,
    single_blocks_36: float | _Omitted = ...,
    single_blocks_37: float | _Omitted = ...,
    single_blocks_4: float | _Omitted = ...,
    single_blocks_5: float | _Omitted = ...,
    single_blocks_6: float | _Omitted = ...,
    single_blocks_7: float | _Omitted = ...,
    single_blocks_8: float | _Omitted = ...,
    single_blocks_9: float | _Omitted = ...,
    time_in: float | _Omitted = ...,
    txt_in: float | _Omitted = ...,
    vector_in: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeLTXV(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    adaln_single: float | _Omitted = ...,
    caption_projection: float | _Omitted = ...,
    patchify_proj: float | _Omitted = ...,
    proj_out: float | _Omitted = ...,
    scale_shift_table: float | _Omitted = ...,
    transformer_blocks_0: float | _Omitted = ...,
    transformer_blocks_1: float | _Omitted = ...,
    transformer_blocks_10: float | _Omitted = ...,
    transformer_blocks_11: float | _Omitted = ...,
    transformer_blocks_12: float | _Omitted = ...,
    transformer_blocks_13: float | _Omitted = ...,
    transformer_blocks_14: float | _Omitted = ...,
    transformer_blocks_15: float | _Omitted = ...,
    transformer_blocks_16: float | _Omitted = ...,
    transformer_blocks_17: float | _Omitted = ...,
    transformer_blocks_18: float | _Omitted = ...,
    transformer_blocks_19: float | _Omitted = ...,
    transformer_blocks_2: float | _Omitted = ...,
    transformer_blocks_20: float | _Omitted = ...,
    transformer_blocks_21: float | _Omitted = ...,
    transformer_blocks_22: float | _Omitted = ...,
    transformer_blocks_23: float | _Omitted = ...,
    transformer_blocks_24: float | _Omitted = ...,
    transformer_blocks_25: float | _Omitted = ...,
    transformer_blocks_26: float | _Omitted = ...,
    transformer_blocks_27: float | _Omitted = ...,
    transformer_blocks_3: float | _Omitted = ...,
    transformer_blocks_4: float | _Omitted = ...,
    transformer_blocks_5: float | _Omitted = ...,
    transformer_blocks_6: float | _Omitted = ...,
    transformer_blocks_7: float | _Omitted = ...,
    transformer_blocks_8: float | _Omitted = ...,
    transformer_blocks_9: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeMochiPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    blocks_0: float | _Omitted = ...,
    blocks_1: float | _Omitted = ...,
    blocks_10: float | _Omitted = ...,
    blocks_11: float | _Omitted = ...,
    blocks_12: float | _Omitted = ...,
    blocks_13: float | _Omitted = ...,
    blocks_14: float | _Omitted = ...,
    blocks_15: float | _Omitted = ...,
    blocks_16: float | _Omitted = ...,
    blocks_17: float | _Omitted = ...,
    blocks_18: float | _Omitted = ...,
    blocks_19: float | _Omitted = ...,
    blocks_2: float | _Omitted = ...,
    blocks_20: float | _Omitted = ...,
    blocks_21: float | _Omitted = ...,
    blocks_22: float | _Omitted = ...,
    blocks_23: float | _Omitted = ...,
    blocks_24: float | _Omitted = ...,
    blocks_25: float | _Omitted = ...,
    blocks_26: float | _Omitted = ...,
    blocks_27: float | _Omitted = ...,
    blocks_28: float | _Omitted = ...,
    blocks_29: float | _Omitted = ...,
    blocks_3: float | _Omitted = ...,
    blocks_30: float | _Omitted = ...,
    blocks_31: float | _Omitted = ...,
    blocks_32: float | _Omitted = ...,
    blocks_33: float | _Omitted = ...,
    blocks_34: float | _Omitted = ...,
    blocks_35: float | _Omitted = ...,
    blocks_36: float | _Omitted = ...,
    blocks_37: float | _Omitted = ...,
    blocks_38: float | _Omitted = ...,
    blocks_39: float | _Omitted = ...,
    blocks_4: float | _Omitted = ...,
    blocks_40: float | _Omitted = ...,
    blocks_41: float | _Omitted = ...,
    blocks_42: float | _Omitted = ...,
    blocks_43: float | _Omitted = ...,
    blocks_44: float | _Omitted = ...,
    blocks_45: float | _Omitted = ...,
    blocks_46: float | _Omitted = ...,
    blocks_47: float | _Omitted = ...,
    blocks_5: float | _Omitted = ...,
    blocks_6: float | _Omitted = ...,
    blocks_7: float | _Omitted = ...,
    blocks_8: float | _Omitted = ...,
    blocks_9: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    pos_frequencies: float | _Omitted = ...,
    t5_y_embedder: float | _Omitted = ...,
    t5_yproj: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeQwenImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    img_in: float | _Omitted = ...,
    pos_embeds: float | _Omitted = ...,
    proj_out: float | _Omitted = ...,
    time_text_embed: float | _Omitted = ...,
    transformer_blocks_0: float | _Omitted = ...,
    transformer_blocks_1: float | _Omitted = ...,
    transformer_blocks_10: float | _Omitted = ...,
    transformer_blocks_11: float | _Omitted = ...,
    transformer_blocks_12: float | _Omitted = ...,
    transformer_blocks_13: float | _Omitted = ...,
    transformer_blocks_14: float | _Omitted = ...,
    transformer_blocks_15: float | _Omitted = ...,
    transformer_blocks_16: float | _Omitted = ...,
    transformer_blocks_17: float | _Omitted = ...,
    transformer_blocks_18: float | _Omitted = ...,
    transformer_blocks_19: float | _Omitted = ...,
    transformer_blocks_2: float | _Omitted = ...,
    transformer_blocks_20: float | _Omitted = ...,
    transformer_blocks_21: float | _Omitted = ...,
    transformer_blocks_22: float | _Omitted = ...,
    transformer_blocks_23: float | _Omitted = ...,
    transformer_blocks_24: float | _Omitted = ...,
    transformer_blocks_25: float | _Omitted = ...,
    transformer_blocks_26: float | _Omitted = ...,
    transformer_blocks_27: float | _Omitted = ...,
    transformer_blocks_28: float | _Omitted = ...,
    transformer_blocks_29: float | _Omitted = ...,
    transformer_blocks_3: float | _Omitted = ...,
    transformer_blocks_30: float | _Omitted = ...,
    transformer_blocks_31: float | _Omitted = ...,
    transformer_blocks_32: float | _Omitted = ...,
    transformer_blocks_33: float | _Omitted = ...,
    transformer_blocks_34: float | _Omitted = ...,
    transformer_blocks_35: float | _Omitted = ...,
    transformer_blocks_36: float | _Omitted = ...,
    transformer_blocks_37: float | _Omitted = ...,
    transformer_blocks_38: float | _Omitted = ...,
    transformer_blocks_39: float | _Omitted = ...,
    transformer_blocks_4: float | _Omitted = ...,
    transformer_blocks_40: float | _Omitted = ...,
    transformer_blocks_41: float | _Omitted = ...,
    transformer_blocks_42: float | _Omitted = ...,
    transformer_blocks_43: float | _Omitted = ...,
    transformer_blocks_44: float | _Omitted = ...,
    transformer_blocks_45: float | _Omitted = ...,
    transformer_blocks_46: float | _Omitted = ...,
    transformer_blocks_47: float | _Omitted = ...,
    transformer_blocks_48: float | _Omitted = ...,
    transformer_blocks_49: float | _Omitted = ...,
    transformer_blocks_5: float | _Omitted = ...,
    transformer_blocks_50: float | _Omitted = ...,
    transformer_blocks_51: float | _Omitted = ...,
    transformer_blocks_52: float | _Omitted = ...,
    transformer_blocks_53: float | _Omitted = ...,
    transformer_blocks_54: float | _Omitted = ...,
    transformer_blocks_55: float | _Omitted = ...,
    transformer_blocks_56: float | _Omitted = ...,
    transformer_blocks_57: float | _Omitted = ...,
    transformer_blocks_58: float | _Omitted = ...,
    transformer_blocks_59: float | _Omitted = ...,
    transformer_blocks_6: float | _Omitted = ...,
    transformer_blocks_7: float | _Omitted = ...,
    transformer_blocks_8: float | _Omitted = ...,
    transformer_blocks_9: float | _Omitted = ...,
    txt_in: float | _Omitted = ...,
    txt_norm: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSD1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    input_blocks_0: float | _Omitted = ...,
    input_blocks_1: float | _Omitted = ...,
    input_blocks_10: float | _Omitted = ...,
    input_blocks_11: float | _Omitted = ...,
    input_blocks_2: float | _Omitted = ...,
    input_blocks_3: float | _Omitted = ...,
    input_blocks_4: float | _Omitted = ...,
    input_blocks_5: float | _Omitted = ...,
    input_blocks_6: float | _Omitted = ...,
    input_blocks_7: float | _Omitted = ...,
    input_blocks_8: float | _Omitted = ...,
    input_blocks_9: float | _Omitted = ...,
    label_emb: float | _Omitted = ...,
    middle_block_0: float | _Omitted = ...,
    middle_block_1: float | _Omitted = ...,
    middle_block_2: float | _Omitted = ...,
    out: float | _Omitted = ...,
    output_blocks_0: float | _Omitted = ...,
    output_blocks_1: float | _Omitted = ...,
    output_blocks_10: float | _Omitted = ...,
    output_blocks_11: float | _Omitted = ...,
    output_blocks_2: float | _Omitted = ...,
    output_blocks_3: float | _Omitted = ...,
    output_blocks_4: float | _Omitted = ...,
    output_blocks_5: float | _Omitted = ...,
    output_blocks_6: float | _Omitted = ...,
    output_blocks_7: float | _Omitted = ...,
    output_blocks_8: float | _Omitted = ...,
    output_blocks_9: float | _Omitted = ...,
    time_embed: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSD2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    input_blocks_0: float | _Omitted = ...,
    input_blocks_1: float | _Omitted = ...,
    input_blocks_10: float | _Omitted = ...,
    input_blocks_11: float | _Omitted = ...,
    input_blocks_2: float | _Omitted = ...,
    input_blocks_3: float | _Omitted = ...,
    input_blocks_4: float | _Omitted = ...,
    input_blocks_5: float | _Omitted = ...,
    input_blocks_6: float | _Omitted = ...,
    input_blocks_7: float | _Omitted = ...,
    input_blocks_8: float | _Omitted = ...,
    input_blocks_9: float | _Omitted = ...,
    label_emb: float | _Omitted = ...,
    middle_block_0: float | _Omitted = ...,
    middle_block_1: float | _Omitted = ...,
    middle_block_2: float | _Omitted = ...,
    out: float | _Omitted = ...,
    output_blocks_0: float | _Omitted = ...,
    output_blocks_1: float | _Omitted = ...,
    output_blocks_10: float | _Omitted = ...,
    output_blocks_11: float | _Omitted = ...,
    output_blocks_2: float | _Omitted = ...,
    output_blocks_3: float | _Omitted = ...,
    output_blocks_4: float | _Omitted = ...,
    output_blocks_5: float | _Omitted = ...,
    output_blocks_6: float | _Omitted = ...,
    output_blocks_7: float | _Omitted = ...,
    output_blocks_8: float | _Omitted = ...,
    output_blocks_9: float | _Omitted = ...,
    time_embed: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSD35_Large(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    context_embedder: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    joint_blocks_0: float | _Omitted = ...,
    joint_blocks_1: float | _Omitted = ...,
    joint_blocks_10: float | _Omitted = ...,
    joint_blocks_11: float | _Omitted = ...,
    joint_blocks_12: float | _Omitted = ...,
    joint_blocks_13: float | _Omitted = ...,
    joint_blocks_14: float | _Omitted = ...,
    joint_blocks_15: float | _Omitted = ...,
    joint_blocks_16: float | _Omitted = ...,
    joint_blocks_17: float | _Omitted = ...,
    joint_blocks_18: float | _Omitted = ...,
    joint_blocks_19: float | _Omitted = ...,
    joint_blocks_2: float | _Omitted = ...,
    joint_blocks_20: float | _Omitted = ...,
    joint_blocks_21: float | _Omitted = ...,
    joint_blocks_22: float | _Omitted = ...,
    joint_blocks_23: float | _Omitted = ...,
    joint_blocks_24: float | _Omitted = ...,
    joint_blocks_25: float | _Omitted = ...,
    joint_blocks_26: float | _Omitted = ...,
    joint_blocks_27: float | _Omitted = ...,
    joint_blocks_28: float | _Omitted = ...,
    joint_blocks_29: float | _Omitted = ...,
    joint_blocks_3: float | _Omitted = ...,
    joint_blocks_30: float | _Omitted = ...,
    joint_blocks_31: float | _Omitted = ...,
    joint_blocks_32: float | _Omitted = ...,
    joint_blocks_33: float | _Omitted = ...,
    joint_blocks_34: float | _Omitted = ...,
    joint_blocks_35: float | _Omitted = ...,
    joint_blocks_36: float | _Omitted = ...,
    joint_blocks_37: float | _Omitted = ...,
    joint_blocks_4: float | _Omitted = ...,
    joint_blocks_5: float | _Omitted = ...,
    joint_blocks_6: float | _Omitted = ...,
    joint_blocks_7: float | _Omitted = ...,
    joint_blocks_8: float | _Omitted = ...,
    joint_blocks_9: float | _Omitted = ...,
    pos_embed: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    x_embedder: float | _Omitted = ...,
    y_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSD3_2B(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    context_embedder: float | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    joint_blocks_0: float | _Omitted = ...,
    joint_blocks_1: float | _Omitted = ...,
    joint_blocks_10: float | _Omitted = ...,
    joint_blocks_11: float | _Omitted = ...,
    joint_blocks_12: float | _Omitted = ...,
    joint_blocks_13: float | _Omitted = ...,
    joint_blocks_14: float | _Omitted = ...,
    joint_blocks_15: float | _Omitted = ...,
    joint_blocks_16: float | _Omitted = ...,
    joint_blocks_17: float | _Omitted = ...,
    joint_blocks_18: float | _Omitted = ...,
    joint_blocks_19: float | _Omitted = ...,
    joint_blocks_2: float | _Omitted = ...,
    joint_blocks_20: float | _Omitted = ...,
    joint_blocks_21: float | _Omitted = ...,
    joint_blocks_22: float | _Omitted = ...,
    joint_blocks_23: float | _Omitted = ...,
    joint_blocks_3: float | _Omitted = ...,
    joint_blocks_4: float | _Omitted = ...,
    joint_blocks_5: float | _Omitted = ...,
    joint_blocks_6: float | _Omitted = ...,
    joint_blocks_7: float | _Omitted = ...,
    joint_blocks_8: float | _Omitted = ...,
    joint_blocks_9: float | _Omitted = ...,
    pos_embed: float | _Omitted = ...,
    t_embedder: float | _Omitted = ...,
    x_embedder: float | _Omitted = ...,
    y_embedder: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSDXL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    input_blocks_0: float | _Omitted = ...,
    input_blocks_1: float | _Omitted = ...,
    input_blocks_2: float | _Omitted = ...,
    input_blocks_3: float | _Omitted = ...,
    input_blocks_4: float | _Omitted = ...,
    input_blocks_5: float | _Omitted = ...,
    input_blocks_6: float | _Omitted = ...,
    input_blocks_7: float | _Omitted = ...,
    input_blocks_8: float | _Omitted = ...,
    label_emb: float | _Omitted = ...,
    middle_block_0: float | _Omitted = ...,
    middle_block_1: float | _Omitted = ...,
    middle_block_2: float | _Omitted = ...,
    out: float | _Omitted = ...,
    output_blocks_0: float | _Omitted = ...,
    output_blocks_1: float | _Omitted = ...,
    output_blocks_2: float | _Omitted = ...,
    output_blocks_3: float | _Omitted = ...,
    output_blocks_4: float | _Omitted = ...,
    output_blocks_5: float | _Omitted = ...,
    output_blocks_6: float | _Omitted = ...,
    output_blocks_7: float | _Omitted = ...,
    output_blocks_8: float | _Omitted = ...,
    time_embed: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSimple(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    ratio: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeSubtract(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMergeWAN2_1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model1: Any | _Omitted = ...,
    model2: Any | _Omitted = ...,
    blocks_0: float | _Omitted = ...,
    blocks_1: float | _Omitted = ...,
    blocks_10: float | _Omitted = ...,
    blocks_11: float | _Omitted = ...,
    blocks_12: float | _Omitted = ...,
    blocks_13: float | _Omitted = ...,
    blocks_14: float | _Omitted = ...,
    blocks_15: float | _Omitted = ...,
    blocks_16: float | _Omitted = ...,
    blocks_17: float | _Omitted = ...,
    blocks_18: float | _Omitted = ...,
    blocks_19: float | _Omitted = ...,
    blocks_2: float | _Omitted = ...,
    blocks_20: float | _Omitted = ...,
    blocks_21: float | _Omitted = ...,
    blocks_22: float | _Omitted = ...,
    blocks_23: float | _Omitted = ...,
    blocks_24: float | _Omitted = ...,
    blocks_25: float | _Omitted = ...,
    blocks_26: float | _Omitted = ...,
    blocks_27: float | _Omitted = ...,
    blocks_28: float | _Omitted = ...,
    blocks_29: float | _Omitted = ...,
    blocks_3: float | _Omitted = ...,
    blocks_30: float | _Omitted = ...,
    blocks_31: float | _Omitted = ...,
    blocks_32: float | _Omitted = ...,
    blocks_33: float | _Omitted = ...,
    blocks_34: float | _Omitted = ...,
    blocks_35: float | _Omitted = ...,
    blocks_36: float | _Omitted = ...,
    blocks_37: float | _Omitted = ...,
    blocks_38: float | _Omitted = ...,
    blocks_39: float | _Omitted = ...,
    blocks_4: float | _Omitted = ...,
    blocks_5: float | _Omitted = ...,
    blocks_6: float | _Omitted = ...,
    blocks_7: float | _Omitted = ...,
    blocks_8: float | _Omitted = ...,
    blocks_9: float | _Omitted = ...,
    head: float | _Omitted = ...,
    img_emb: float | _Omitted = ...,
    patch_embedding: float | _Omitted = ...,
    text_embedding: float | _Omitted = ...,
    time_embedding: float | _Omitted = ...,
    time_projection: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelNoiseScale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    noise_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelPatchLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingAuraFlow(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    shift: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingContinuousEDM(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    sampling: Literal['v_prediction', 'edm', 'edm_playground_v2.5', 'eps', 'cosmos_rflow'] | _Omitted = ...,
    sigma_max: float | _Omitted = ...,
    sigma_min: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingContinuousV(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    sampling: Literal['v_prediction'] | _Omitted = ...,
    sigma_max: float | _Omitted = ...,
    sigma_min: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingDiscrete(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    sampling: Literal['eps', 'v_prediction', 'lcm', 'x0', 'img_to_img', 'img_to_img_flow'] | _Omitted = ...,
    zsnr: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingFlux(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    base_shift: float | _Omitted = ...,
    height: int | _Omitted = ...,
    max_shift: float | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingLTXV(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    base_shift: float | _Omitted = ...,
    max_shift: float | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingSD3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    shift: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingStableCascade(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    shift: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSave(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoonvalleyImg2VideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_adherence: float | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoonvalleyTxt2VideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    prompt_adherence: float | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MoonvalleyVideo2VideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    control_type: Any | _Omitted = ...,
    motion_intensity: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Morphology(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    kernel_size: int | _Omitted = ...,
    operation: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultiGPU_WorkUnits(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    max_gpus: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NAGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    nag_alpha: float | _Omitted = ...,
    nag_scale: float | _Omitted = ...,
    nag_tau: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NormalizeImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    mean: float | _Omitted = ...,
    std: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NormalizeVideoLatentStart(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    reference_frame_count: int | _Omitted = ...,
    start_frame_count: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OmitThink(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OneShotInstructTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    chat_template: Literal['default', 'amberchat', 'solar-instruct', 'llama-3-instruct', 'llava-v1.6-mistral-7b-hf', 'vicuna', 'falcon-instruct', 'chatml', 'gemma-it', 'saiga', 'chatqa', 'phi-3', 'mistral-instruct', 'mistral-instruct-v0.1', 'openchat', 'llama-2-chat', 'zephyr', 'alpaca'] | _Omitted = ...,
    prompt: str | _Omitted = ...,
    images: Any | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    videos: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIChatConfig(
    *args: VibeWorkflow,
    _id: str | None = ...,
    truncation: Any | _Omitted = ...,
    instructions: str | _Omitted = ...,
    max_output_tokens: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIChatNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    persist_context: bool | _Omitted = ...,
    prompt: str | _Omitted = ...,
    advanced_options: Any | _Omitted = ...,
    files: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIDalle2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    size: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIDalle3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    size: Any | _Omitted = ...,
    style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIGPTImage1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    background: Any | _Omitted = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    quality: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    size: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIGPTImageNodeV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIInputFiles(
    *args: VibeWorkflow,
    _id: str | None = ...,
    file: Any | _Omitted = ...,
    OPENAI_INPUT_FILES: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAILanguageModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenAIVideoSora2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    duration: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    size: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpenRouterLLMNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    system_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OpticalFlowLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OptimalStepsScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    denoise: float | _Omitted = ...,
    model_type: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OutputTensor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    tensor: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Painter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bg_color: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    mask: str | _Omitted = ...,
    width: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PairConditioningCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative_A: Any | _Omitted = ...,
    negative_B: Any | _Omitted = ...,
    positive_A: Any | _Omitted = ...,
    positive_B: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PairConditioningSetDefaultCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    negative_DEFAULT: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    positive_DEFAULT: Any | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PairConditioningSetProperties(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative_NEW: Any | _Omitted = ...,
    positive_NEW: Any | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    timesteps: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PairConditioningSetPropertiesAndCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    negative_NEW: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    positive_NEW: Any | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    timesteps: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PaligemmaOutputToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    paligemma_output: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PaligemmaPostProcess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    generated_text: str | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PatchModelAddDownscale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    block_number: int | _Omitted = ...,
    downscale_after_skip: bool | _Omitted = ...,
    downscale_factor: float | _Omitted = ...,
    downscale_method: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PerpNeg(
    *args: VibeWorkflow,
    _id: str | None = ...,
    empty_conditioning: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    neg_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PerpNegGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    empty_conditioning: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    neg_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PerturbedAttentionGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PhotoMakerEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    photomaker: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PhotoMakerLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    photomaker_model_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PiDConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    degrade_sigma: float | _Omitted = ...,
    latent_format: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixelLatentToImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixelPerfectResolution(
    *args: VibeWorkflow,
    _id: str | None = ...,
    original_image: Any | _Omitted = ...,
    image_gen_height: int | _Omitted = ...,
    image_gen_width: int | _Omitted = ...,
    resize_mode: Literal['Just Resize', 'Crop and Resize', 'Resize and Fill'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixtralTransformersLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['unsloth/Pixtral-12B-2409'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixverseImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    duration_seconds: Any | _Omitted = ...,
    motion_mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pixverse_template: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixverseTemplateNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    template: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixverseTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration_seconds: Any | _Omitted = ...,
    motion_mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pixverse_template: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixverseTransitionVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_frame: Any | _Omitted = ...,
    last_frame: Any | _Omitted = ...,
    duration_seconds: Any | _Omitted = ...,
    motion_mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PolyexponentialScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    rho: float | _Omitted = ...,
    sigma_max: float | _Omitted = ...,
    sigma_min: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PorterDuffImageComposite(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    destination_alpha: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    source_alpha: Any | _Omitted = ...,
    mode: Literal['ADD', 'CLEAR', 'DARKEN', 'DST', 'DST_ATOP', 'DST_IN', 'DST_OUT', 'DST_OVER', 'LIGHTEN', 'MULTIPLY', 'OVERLAY', 'SCREEN', 'SRC', 'SRC_ATOP', 'SRC_IN', 'SRC_OUT', 'SRC_OVER', 'XOR'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PorterDuffImageCompositeV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    mode: Literal['ADD', 'CLEAR', 'DARKEN', 'DST', 'DST_ATOP', 'DST_IN', 'DST_OUT', 'DST_OVER', 'LIGHTEN', 'MULTIPLY', 'OVERLAY', 'SCREEN', 'SRC', 'SRC_ATOP', 'SRC_IN', 'SRC_OUT', 'SRC_OVER', 'XOR'] | _Omitted = ...,
    destination_alpha: Any | _Omitted = ...,
    source_alpha: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Posterize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    levels: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Preview3D(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_file: Any | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    camera_info: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Preview3DAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    model_file: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    camera_info: Any | _Omitted = ...,
    model_3d_info: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewAny(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveBoolean(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveBoundingBox(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveFloat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveStringMultiline(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QuadrupleCLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name1: Any | _Omitted = ...,
    clip_name2: Any | _Omitted = ...,
    clip_name3: Any | _Omitted = ...,
    clip_name4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QuantizeModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    strategy: Literal['torchao', 'torchao-autoquant', 'quanto'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QuiverImageToSVGNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    auto_crop: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QuiverTextToSVGNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    instructions: str | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QwenImageDiffsynthControlnet(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    model_patch: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QwenVL2_5TransformersLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['Qwen/Qwen2.5-VL-3B-Instruct', 'Qwen/Qwen2.5-VL-7B-Instruct', 'Qwen/Qwen2.5-3B-Instruct', 'Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen2.5-14B-Instruct'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RTDETR_detect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    class_name: Any | _Omitted = ...,
    max_detections: int | _Omitted = ...,
    threshold: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RandomCropImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RandomNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    noise_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RebatchImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RebatchLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecordAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftColorRGB(
    *args: VibeWorkflow,
    _id: str | None = ...,
    b: int | _Omitted = ...,
    g: int | _Omitted = ...,
    r: int | _Omitted = ...,
    recraft_color: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftControls(
    *args: VibeWorkflow,
    _id: str | None = ...,
    background_color: Any | _Omitted = ...,
    colors: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftCreateStyleNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftCreativeUpscaleNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftCrispUpscaleNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftImageInpaintingNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    recraft_style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftImageToImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    recraft_controls: Any | _Omitted = ...,
    recraft_style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftRemoveBackgroundNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftReplaceBackgroundNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    recraft_style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftStyleV3DigitalIllustration(
    *args: VibeWorkflow,
    _id: str | None = ...,
    substyle: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftStyleV3InfiniteStyleLibrary(
    *args: VibeWorkflow,
    _id: str | None = ...,
    style_id: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftStyleV3LogoRaster(
    *args: VibeWorkflow,
    _id: str | None = ...,
    substyle: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftStyleV3RealisticImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    substyle: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftTextToImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    n: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    size: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    recraft_controls: Any | _Omitted = ...,
    recraft_style: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftTextToVectorNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    n: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    size: Any | _Omitted = ...,
    substyle: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    recraft_controls: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftV4TextToImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    recraft_controls: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftV4TextToVectorNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    n: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    recraft_controls: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RecraftVectorizeImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReferenceLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReferenceOnlySimple(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    reference: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReferenceTimbreAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Regex(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pattern: str | _Omitted = ...,
    string: str | _Omitted = ...,
    flags: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexExtract(
    *args: VibeWorkflow,
    _id: str | None = ...,
    case_insensitive: bool | _Omitted = ...,
    dotall: bool | _Omitted = ...,
    group_index: int | _Omitted = ...,
    mode: Any | _Omitted = ...,
    multiline: bool | _Omitted = ...,
    regex_pattern: str | _Omitted = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexFlags(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ASCII: bool | _Omitted = ...,
    DOTALL: bool | _Omitted = ...,
    IGNORECASE: bool | _Omitted = ...,
    LOCALE: bool | _Omitted = ...,
    MULTILINE: bool | _Omitted = ...,
    UNICODE: bool | _Omitted = ...,
    VERBOSE: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexMatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    case_insensitive: bool | _Omitted = ...,
    dotall: bool | _Omitted = ...,
    multiline: bool | _Omitted = ...,
    regex_pattern: str | _Omitted = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexMatchExpand(
    *args: VibeWorkflow,
    _id: str | None = ...,
    match: Any | _Omitted = ...,
    template: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexMatchGroupByIndex(
    *args: VibeWorkflow,
    _id: str | None = ...,
    index: int | _Omitted = ...,
    match: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexMatchGroupByName(
    *args: VibeWorkflow,
    _id: str | None = ...,
    match: Any | _Omitted = ...,
    name: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RegexReplace(
    *args: VibeWorkflow,
    _id: str | None = ...,
    regex_pattern: str | _Omitted = ...,
    replace: str | _Omitted = ...,
    string: str | _Omitted = ...,
    case_insensitive: bool | _Omitted = ...,
    count: int | _Omitted = ...,
    dotall: bool | _Omitted = ...,
    multiline: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RemoteLanguageLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['openai:gpt-4o', 'openai:gpt-4o-mini', 'openai:gpt-4.1', 'openai:gpt-4.1-mini', 'openai:gpt-4.1-nano', 'openai:o3-mini', 'anthropic:claude-sonnet-4-5-20250514', 'anthropic:claude-haiku-4-5-20250514', 'anthropic:claude-3-5-haiku-latest', 'google-gla:gemini-2.0-flash', 'google-gla:gemini-2.5-pro', 'google-gla:gemini-2.5-flash', 'groq:llama-3.3-70b-versatile', 'groq:llama-3.1-8b-instant', 'groq:mixtral-8x7b-32768', 'mistral:mistral-large-latest', 'mistral:mistral-small-latest', 'xai:grok-2', 'xai:grok-3', 'cohere:command-r-plus', 'cohere:command-r', 'cerebras:llama-3.3-70b'] | _Omitted = ...,
    custom_model: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RemoveBackground(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bg_removal_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RenderSplat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    background: Any | _Omitted = ...,
    frames: int | _Omitted = ...,
    headlight_shading: float | _Omitted = ...,
    height: int | _Omitted = ...,
    opacity_threshold: float | _Omitted = ...,
    render_style: Any | _Omitted = ...,
    sharpen: float | _Omitted = ...,
    splat: Any | _Omitted = ...,
    splat_scale: float | _Omitted = ...,
    width: int | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    camera_info: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RenormCFG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    cfg_trunc: float | _Omitted = ...,
    renorm_cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RepeatImageBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    amount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RepeatLatentBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    amount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReplaceText(
    *args: VibeWorkflow,
    _id: str | None = ...,
    find: str | _Omitted = ...,
    replace: str | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReplaceVideoLatentFrames(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    source: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RescaleCFG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeAndPadImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    interpolation: Any | _Omitted = ...,
    padding_color: Any | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeImageMaskNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: Any | _Omitted = ...,
    resize_type: Any | _Omitted = ...,
    scale_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeImagesByLongerEdge(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    longer_edge: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeImagesByShorterEdge(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    shorter_edge: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResolutionBucket(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResolutionSelector(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    megapixels: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReveImageCreateNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    remove_background: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    upscale: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReveImageEditNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    edit_instruction: str | _Omitted = ...,
    model: Any | _Omitted = ...,
    remove_background: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    upscale: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReveImageRemixNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    remove_background: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    upscale: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Detail(
    *args: VibeWorkflow,
    _id: str | None = ...,
    Images: Any | _Omitted = ...,
    Material_Type: Any | _Omitted = ...,
    Polygon_count: Any | _Omitted = ...,
    Seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Gen2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    Images: Any | _Omitted = ...,
    TAPose: bool | _Omitted = ...,
    Material_Type: Any | _Omitted = ...,
    Polygon_count: Any | _Omitted = ...,
    Seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Gen25_Image(
    *args: VibeWorkflow,
    _id: str | None = ...,
    geometry_file_format: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    material: Any | _Omitted = ...,
    mode: Any | _Omitted = ...,
    TAPose: bool | _Omitted = ...,
    addon_highpack: bool | _Omitted = ...,
    bbox_height: int | _Omitted = ...,
    bbox_length: int | _Omitted = ...,
    bbox_width: int | _Omitted = ...,
    hd_texture: bool | _Omitted = ...,
    height_cm: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    texture_delight: bool | _Omitted = ...,
    texture_mode: Any | _Omitted = ...,
    use_original_alpha: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Gen25_Text(
    *args: VibeWorkflow,
    _id: str | None = ...,
    geometry_file_format: Any | _Omitted = ...,
    material: Any | _Omitted = ...,
    mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    TAPose: bool | _Omitted = ...,
    addon_highpack: bool | _Omitted = ...,
    bbox_height: int | _Omitted = ...,
    bbox_length: int | _Omitted = ...,
    bbox_width: int | _Omitted = ...,
    hd_texture: bool | _Omitted = ...,
    height_cm: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    texture_delight: bool | _Omitted = ...,
    texture_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Regular(
    *args: VibeWorkflow,
    _id: str | None = ...,
    Images: Any | _Omitted = ...,
    Material_Type: Any | _Omitted = ...,
    Polygon_count: Any | _Omitted = ...,
    Seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Sketch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    Images: Any | _Omitted = ...,
    Seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Rodin3D_Smooth(
    *args: VibeWorkflow,
    _id: str | None = ...,
    Images: Any | _Omitted = ...,
    Material_Type: Any | _Omitted = ...,
    Polygon_count: Any | _Omitted = ...,
    Seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RunwayFirstLastFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    start_frame: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    ratio: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RunwayImageToVideoNodeGen3a(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_frame: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    ratio: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RunwayImageToVideoNodeGen4(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_frame: Any | _Omitted = ...,
    duration: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    ratio: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RunwayTextToImageNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    ratio: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SAM3_Detect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    individual_masks: bool | _Omitted = ...,
    refine_iterations: int | _Omitted = ...,
    threshold: float | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    conditioning: Any | _Omitted = ...,
    negative_coords: str | _Omitted = ...,
    positive_coords: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SAM3_TrackPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    fps: float | _Omitted = ...,
    opacity: float | _Omitted = ...,
    track_data: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SAM3_TrackToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    object_indices: str | _Omitted = ...,
    track_data: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SAM3_VideoTrack(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    detect_interval: int | _Omitted = ...,
    detection_threshold: float | _Omitted = ...,
    max_objects: int | _Omitted = ...,
    conditioning: Any | _Omitted = ...,
    initial_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDPoseDrawKeypoints(
    *args: VibeWorkflow,
    _id: str | None = ...,
    draw_body: bool | _Omitted = ...,
    draw_face: bool | _Omitted = ...,
    draw_feet: bool | _Omitted = ...,
    draw_hands: bool | _Omitted = ...,
    face_point_size: int | _Omitted = ...,
    keypoints: Any | _Omitted = ...,
    score_threshold: float | _Omitted = ...,
    stick_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDPoseFaceBBoxes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    force_square: bool | _Omitted = ...,
    keypoints: Any | _Omitted = ...,
    scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDPoseKeypointExtractor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDTurboScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    denoise: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SD_4XUpscale_Conditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    noise_augmentation: float | _Omitted = ...,
    scale_ratio: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SUPIRApply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    model_patch: Any | _Omitted = ...,
    restore_cfg: float | _Omitted = ...,
    restore_cfg_s_tmin: float | _Omitted = ...,
    strength_end: float | _Omitted = ...,
    strength_start: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SV3D_Conditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    init_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    elevation: float | _Omitted = ...,
    height: int | _Omitted = ...,
    video_frames: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SVD_img2vid_Conditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    init_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    augmentation_level: float | _Omitted = ...,
    fps: int | _Omitted = ...,
    height: int | _Omitted = ...,
    motion_bucket_id: int | _Omitted = ...,
    video_frames: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SVGToImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    scale: float | _Omitted = ...,
    svg: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerARVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frame_per_block: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerCustom(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent_image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    add_noise: bool | _Omitted = ...,
    cfg: float | _Omitted = ...,
    noise_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerCustomAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    guider: Any | _Omitted = ...,
    latent_image: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerDPMAdaptative(
    *args: VibeWorkflow,
    _id: str | None = ...,
    accept_safety: float | _Omitted = ...,
    atol: float | _Omitted = ...,
    dcoeff: float | _Omitted = ...,
    eta: float | _Omitted = ...,
    h_init: float | _Omitted = ...,
    icoeff: float | _Omitted = ...,
    order: int | _Omitted = ...,
    pcoeff: float | _Omitted = ...,
    rtol: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerDPMPP_2M_SDE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    noise_device: Any | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    solver_type: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerDPMPP_2S_Ancestral(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerDPMPP_3M_SDE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    noise_device: Any | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerDPMPP_SDE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    noise_device: Any | _Omitted = ...,
    r: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerER_SDE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    max_stage: int | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    solver_type: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerEulerAncestral(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerEulerAncestralCFGPP(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerEulerCFGpp(
    *args: VibeWorkflow,
    _id: str | None = ...,
    version: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerLCM(
    *args: VibeWorkflow,
    _id: str | None = ...,
    noise_clip_std: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    s_noise_end: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerLCMUpscale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    scale_ratio: float | _Omitted = ...,
    scale_steps: int | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerLMS(
    *args: VibeWorkflow,
    _id: str | None = ...,
    order: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerSASolver(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    corrector_order: int | _Omitted = ...,
    eta: float | _Omitted = ...,
    predictor_order: int | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    sde_end_percent: float | _Omitted = ...,
    sde_start_percent: float | _Omitted = ...,
    simple_order_2: bool | _Omitted = ...,
    use_pece: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerSEEDS2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    r: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    solver_type: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplingPercentToSigma(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    return_actual_sigma: bool | _Omitted = ...,
    sampling_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveAnimatedPNG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    compress_level: int | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    fps: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveAnimatedWEBP(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    fps: float | _Omitted = ...,
    lossless: bool | _Omitted = ...,
    method: Any | _Omitted = ...,
    quality: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveAudioMP3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveAudioOpus(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveGLB(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename_prefix: str | _Omitted = ...,
    mesh: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImageAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    format: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImageDataSetToFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    folder_name: str | _Omitted = ...,
    mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImageTextDataSetToFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    folder_name: str | _Omitted = ...,
    mode: Any | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImagesResponse(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pil_save_format: str | _Omitted = ...,
    uris: Any | _Omitted = ...,
    required: bool | _Omitted = ...,
    bits: Literal['8', '16'] | _Omitted = ...,
    description: str | _Omitted = ...,
    exif: Any | _Omitted = ...,
    local_uris: Any | _Omitted = ...,
    metadata_uris: Any | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveLoRA(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora: Any | _Omitted = ...,
    prefix: str | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveSVGNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename_prefix: str | _Omitted = ...,
    svg: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename_prefix: str | _Omitted = ...,
    value: str | _Omitted = ...,
    extension: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveTrainingDataset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    folder_name: str | _Omitted = ...,
    shard_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    codec: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    format: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveWEBM(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    codec: Any | _Omitted = ...,
    crf: float | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    fps: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ScaleROPE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    scale_t: float | _Omitted = ...,
    scale_x: float | _Omitted = ...,
    scale_y: float | _Omitted = ...,
    shift_t: float | _Omitted = ...,
    shift_x: float | _Omitted = ...,
    shift_y: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SelectCLIPDevice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    device: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SelectModelDevice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    device: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SelectVAEDevice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    device: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SelfAttentionGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    blur_sigma: float | _Omitted = ...,
    scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetClipHooks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    apply_to_conds: bool | _Omitted = ...,
    schedule_clip: bool | _Omitted = ...,
    hooks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetFirstSigma(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetHookKeyframes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    hooks: Any | _Omitted = ...,
    hook_kf: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetLatentNoiseMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetUnionControlNetType(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net: Any | _Omitted = ...,
    type: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ShuffleDataset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ShuffleImageTextDataset(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SimpleMath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    a: Any | _Omitted = ...,
    b: Any | _Omitted = ...,
    c: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SimpleMath_2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    a: Any | _Omitted = ...,
    b: Any | _Omitted = ...,
    c: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SkeletonizeThin(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    approach: Literal['skeletonize', 'thinning'] | _Omitted = ...,
    binary_threshold: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SkipLayerGuidanceDiT(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    double_layers: str | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    rescaling_scale: float | _Omitted = ...,
    scale: float | _Omitted = ...,
    single_layers: str | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SkipLayerGuidanceDiTSimple(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    double_layers: str | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    single_layers: str | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SkipLayerGuidanceSD3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    layers: str | _Omitted = ...,
    scale: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SolidMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    value: float | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SomethingToString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: Any | _Omitted = ...,
    prefix: str | _Omitted = ...,
    suffix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SoniloTextToMusic(
    *args: VibeWorkflow,
    _id: str | None = ...,
    duration: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SoniloVideoToMusic(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplatToFile3D(
    *args: VibeWorkflow,
    _id: str | None = ...,
    format: Any | _Omitted = ...,
    splat: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplatToMesh(
    *args: VibeWorkflow,
    _id: str | None = ...,
    color_sharpen: float | _Omitted = ...,
    kernel: int | _Omitted = ...,
    level: float | _Omitted = ...,
    min_component: int | _Omitted = ...,
    min_opacity: float | _Omitted = ...,
    resolution: int | _Omitted = ...,
    smooth: int | _Omitted = ...,
    splat: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitAudioChannels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitImageToTileList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    tile_height: int | _Omitted = ...,
    tile_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitImageWithAlpha(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    step: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitSigmasDenoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    denoise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityAudioInpaint(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    duration: int | _Omitted = ...,
    mask_end: int | _Omitted = ...,
    mask_start: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityAudioToAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    duration: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityStableImageSD_3_5Node(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_preset: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    image_denoise: float | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityStableImageUltraNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_preset: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    image_denoise: float | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityTextToAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    duration: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityUpscaleConservativeNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    creativity: float | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityUpscaleCreativeNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    creativity: float | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    style_preset: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StabilityUpscaleFastNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableCascade_EmptyLatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    compression: int | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableCascade_StageB_Conditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    stage_c: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableCascade_StageC_VAEEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    compression: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableCascade_SuperResolutionControlnet(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableZero123_Conditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    init_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    azimuth: float | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    elevation: float | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableZero123_Conditioning_Batched(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    init_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    azimuth: float | _Omitted = ...,
    azimuth_batch_increment: float | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    elevation: float | _Omitted = ...,
    elevation_batch_increment: float | _Omitted = ...,
    height: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringCombo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringCompare(
    *args: VibeWorkflow,
    _id: str | None = ...,
    case_sensitive: bool | _Omitted = ...,
    mode: Any | _Omitted = ...,
    string_a: str | _Omitted = ...,
    string_b: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringConcatenate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    delimiter: str | _Omitted = ...,
    string_a: str | _Omitted = ...,
    string_b: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringContains(
    *args: VibeWorkflow,
    _id: str | None = ...,
    case_sensitive: bool | _Omitted = ...,
    string: str | _Omitted = ...,
    substring: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringEnumRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    required: bool | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringFormat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    format: str | _Omitted = ...,
    value0: Any | _Omitted = ...,
    value1: Any | _Omitted = ...,
    value2: Any | _Omitted = ...,
    value3: Any | _Omitted = ...,
    value4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringJoin(
    *args: VibeWorkflow,
    _id: str | None = ...,
    separator: str | _Omitted = ...,
    value0: str | _Omitted = ...,
    value1: str | _Omitted = ...,
    value2: str | _Omitted = ...,
    value3: str | _Omitted = ...,
    value4: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringJoin1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    separator: str | _Omitted = ...,
    value0: Any | _Omitted = ...,
    value1: Any | _Omitted = ...,
    value2: Any | _Omitted = ...,
    value3: Any | _Omitted = ...,
    value4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringLength(
    *args: VibeWorkflow,
    _id: str | None = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringPosixPathJoin(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: str | _Omitted = ...,
    value1: str | _Omitted = ...,
    value2: str | _Omitted = ...,
    value3: str | _Omitted = ...,
    value4: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringReplace(
    *args: VibeWorkflow,
    _id: str | None = ...,
    find: str | _Omitted = ...,
    replace: str | _Omitted = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    required: bool | _Omitted = ...,
    description: str | _Omitted = ...,
    name: str | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringSplit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    delimiter: str | _Omitted = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringSubstring(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end: int | _Omitted = ...,
    start: int | _Omitted = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringToFloat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringToInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringToUri(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch: int | _Omitted = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringTrim(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mode: Any | _Omitted = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StripWhitespace(
    *args: VibeWorkflow,
    _id: str | None = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StyleModelApply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision_output: Any | _Omitted = ...,
    conditioning: Any | _Omitted = ...,
    style_model: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    strength_type: Literal['multiply', 'attn_bias'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StyleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    style_model_name: Literal['flux1-redux-dev.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def T5TokenizerOptions(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    min_length: int | _Omitted = ...,
    min_padding: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TCFG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TemporalScoreRescaling(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    tsr_k: float | _Omitted = ...,
    tsr_sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Tencent3DPartNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_3d: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Tencent3DTextureEditNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_3d: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TencentImageToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    face_count: int | _Omitted = ...,
    generate_type: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    image_back: Any | _Omitted = ...,
    image_left: Any | _Omitted = ...,
    image_right: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TencentModelTo3DUVNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_3d: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TencentSmartTopologyNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    face_level: Any | _Omitted = ...,
    model_3d: Any | _Omitted = ...,
    polygon_type: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TencentTextToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    face_count: int | _Omitted = ...,
    generate_type: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextDiffuserAddTokens(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextDiffuserDecodeLayoutString2ClipString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    layout_model: Any | _Omitted = ...,
    instruct_response: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextDiffuserPrepareInstructPrompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    text_to_render: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeAceStepAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    lyrics: str | _Omitted = ...,
    lyrics_strength: float | _Omitted = ...,
    tags: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeAceStepAudio1_5(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    bpm: int | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    duration: float | _Omitted = ...,
    generate_audio_codes: bool | _Omitted = ...,
    keyscale: Any | _Omitted = ...,
    language: Any | _Omitted = ...,
    lyrics: str | _Omitted = ...,
    min_p: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    tags: str | _Omitted = ...,
    temperature: float | _Omitted = ...,
    timesignature: Any | _Omitted = ...,
    top_k: int | _Omitted = ...,
    top_p: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeHunyuanVideo_ImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    image_interleave: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeQwenImageEdit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeQwenImageEditPlus(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    image3: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeZImageOmni(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    auto_resize_images: bool | _Omitted = ...,
    prompt: str | _Omitted = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    image3: Any | _Omitted = ...,
    image_encoder: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextGenerate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    max_length: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    sampling_mode: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    thinking: bool | _Omitted = ...,
    use_default_template: bool | _Omitted = ...,
    video: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextGenerateLTX2Prompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    max_length: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    sampling_mode: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    thinking: bool | _Omitted = ...,
    use_default_template: bool | _Omitted = ...,
    video: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextToLowercase(
    *args: VibeWorkflow,
    _id: str | None = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextToUppercase(
    *args: VibeWorkflow,
    _id: str | None = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ThresholdMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ToString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TomePatchModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    ratio: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TopazImageEnhance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    color_preservation: bool | _Omitted = ...,
    creativity: int | _Omitted = ...,
    crop_to_fill: bool | _Omitted = ...,
    face_enhancement: bool | _Omitted = ...,
    face_enhancement_creativity: float | _Omitted = ...,
    face_enhancement_strength: float | _Omitted = ...,
    face_preservation: bool | _Omitted = ...,
    output_height: int | _Omitted = ...,
    output_width: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    subject_detection: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TopazVideoEnhance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    upscaler_enabled: bool | _Omitted = ...,
    upscaler_model: Any | _Omitted = ...,
    upscaler_resolution: Any | _Omitted = ...,
    dynamic_compression_level: Any | _Omitted = ...,
    interpolation_duplicate: bool | _Omitted = ...,
    interpolation_duplicate_threshold: float | _Omitted = ...,
    interpolation_enabled: bool | _Omitted = ...,
    interpolation_frame_rate: int | _Omitted = ...,
    interpolation_model: Any | _Omitted = ...,
    interpolation_slowmo: int | _Omitted = ...,
    upscaler_creativity: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TopazVideoEnhanceV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    interpolation_model: Any | _Omitted = ...,
    upscaler_model: Any | _Omitted = ...,
    dynamic_compression_level: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    backend: Literal['inductor', 'torch_tensorrt', 'onnxrt', 'cudagraphs', 'openxla', 'tvm'] | _Omitted = ...,
    dynamic: bool | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'reduce-overhead', 'max-autotune', 'max-autotune-no-cudagraphs'] | _Omitted = ...,
    object_patch: str | _Omitted = ...,
    torch_tensorrt_optimization_level: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TrainLoraNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    algorithm: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    bucket_mode: bool | _Omitted = ...,
    bypass_mode: bool | _Omitted = ...,
    checkpoint_depth: int | _Omitted = ...,
    existing_lora: Any | _Omitted = ...,
    grad_accumulation_steps: int | _Omitted = ...,
    gradient_checkpointing: bool | _Omitted = ...,
    learning_rate: float | _Omitted = ...,
    lora_dtype: Any | _Omitted = ...,
    loss_function: Any | _Omitted = ...,
    offloading: bool | _Omitted = ...,
    optimizer: Any | _Omitted = ...,
    quantized_backward: bool | _Omitted = ...,
    rank: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    training_dtype: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformSplat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    rotate_x: float | _Omitted = ...,
    rotate_y: float | _Omitted = ...,
    rotate_z: float | _Omitted = ...,
    scale_x: float | _Omitted = ...,
    scale_y: float | _Omitted = ...,
    scale_z: float | _Omitted = ...,
    splat: Any | _Omitted = ...,
    translate_x: float | _Omitted = ...,
    translate_y: float | _Omitted = ...,
    translate_z: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerBeamSearchSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    early_stopping: bool | _Omitted = ...,
    num_beams: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerContrastiveSearchSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    penalty_alpha: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerGreedySampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerMergeSamplers(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value0: Any | _Omitted = ...,
    value1: Any | _Omitted = ...,
    value2: Any | _Omitted = ...,
    value3: Any | _Omitted = ...,
    value4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerTemperatureSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    temperature: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerTopKSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    top_k: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformerTopPSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    top_p: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersFlores200LanguageCodes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lang_id: Literal['ace_Arab', 'ace_Latn', 'acm_Arab', 'acq_Arab', 'aeb_Arab', 'afr_Latn', 'ajp_Arab', 'aka_Latn', 'amh_Ethi', 'apc_Arab', 'arb_Arab', 'ars_Arab', 'ary_Arab', 'arz_Arab', 'asm_Beng', 'ast_Latn', 'awa_Deva', 'ayr_Latn', 'azb_Arab', 'azj_Latn', 'bak_Cyrl', 'bam_Latn', 'ban_Latn', 'bel_Cyrl', 'bem_Latn', 'ben_Beng', 'bho_Deva', 'bjn_Arab', 'bjn_Latn', 'bod_Tibt', 'bos_Latn', 'bug_Latn', 'bul_Cyrl', 'cat_Latn', 'ceb_Latn', 'ces_Latn', 'cjk_Latn', 'ckb_Arab', 'crh_Latn', 'cym_Latn', 'dan_Latn', 'deu_Latn', 'dik_Latn', 'dyu_Latn', 'dzo_Tibt', 'ell_Grek', 'eng_Latn', 'epo_Latn', 'est_Latn', 'eus_Latn', 'ewe_Latn', 'fao_Latn', 'pes_Arab', 'fij_Latn', 'fin_Latn', 'fon_Latn', 'fra_Latn', 'fur_Latn', 'fuv_Latn', 'gla_Latn', 'gle_Latn', 'glg_Latn', 'grn_Latn', 'guj_Gujr', 'hat_Latn', 'hau_Latn', 'heb_Hebr', 'hin_Deva', 'hne_Deva', 'hrv_Latn', 'hun_Latn', 'hye_Armn', 'ibo_Latn', 'ilo_Latn', 'ind_Latn', 'isl_Latn', 'ita_Latn', 'jav_Latn', 'jpn_Jpan', 'kab_Latn', 'kac_Latn', 'kam_Latn', 'kan_Knda', 'kas_Arab', 'kas_Deva', 'kat_Geor', 'knc_Arab', 'knc_Latn', 'kaz_Cyrl', 'kbp_Latn', 'kea_Latn', 'khm_Khmr', 'kik_Latn', 'kin_Latn', 'kir_Cyrl', 'kmb_Latn', 'kon_Latn', 'kor_Hang', 'kmr_Latn', 'lao_Laoo', 'lvs_Latn', 'lij_Latn', 'lim_Latn', 'lin_Latn', 'lit_Latn', 'lmo_Latn', 'ltg_Latn', 'ltz_Latn', 'lua_Latn', 'lug_Latn', 'luo_Latn', 'lus_Latn', 'mag_Deva', 'mai_Deva', 'mal_Mlym', 'mar_Deva', 'min_Latn', 'mkd_Cyrl', 'plt_Latn', 'mlt_Latn', 'mni_Beng', 'khk_Cyrl', 'mos_Latn', 'mri_Latn', 'zsm_Latn', 'mya_Mymr', 'nld_Latn', 'nno_Latn', 'nob_Latn', 'npi_Deva', 'nso_Latn', 'nus_Latn', 'nya_Latn', 'oci_Latn', 'gaz_Latn', 'ory_Orya', 'pag_Latn', 'pan_Guru', 'pap_Latn', 'pol_Latn', 'por_Latn', 'prs_Arab', 'pbt_Arab', 'quy_Latn', 'ron_Latn', 'run_Latn', 'rus_Cyrl', 'sag_Latn', 'san_Deva', 'sat_Beng', 'scn_Latn', 'shn_Mymr', 'sin_Sinh', 'slk_Latn', 'slv_Latn', 'smo_Latn', 'sna_Latn', 'snd_Arab', 'som_Latn', 'sot_Latn', 'spa_Latn', 'als_Latn', 'srd_Latn', 'srp_Cyrl', 'ssw_Latn', 'sun_Latn', 'swe_Latn', 'swh_Latn', 'szl_Latn', 'tam_Taml', 'tat_Cyrl', 'tel_Telu', 'tgk_Cyrl', 'tgl_Latn', 'tha_Thai', 'tir_Ethi', 'taq_Latn', 'taq_Tfng', 'tpi_Latn', 'tsn_Latn', 'tso_Latn', 'tuk_Latn', 'tum_Latn', 'tur_Latn', 'twi_Latn', 'tzm_Tfng', 'uig_Arab', 'ukr_Cyrl', 'umb_Latn', 'urd_Arab', 'uzn_Latn', 'vec_Latn', 'vie_Latn', 'war_Latn', 'wol_Latn', 'xho_Latn', 'ydd_Hebr', 'yor_Latn', 'yue_Hant', 'zho_Hans', 'zho_Hant', 'zul_Latn'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersGenerate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    tokens: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersGenerationConfig(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersImageProcessorLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    ckpt_name: Literal['microsoft/Florence-2-large', 'JingyeChen22/textdiffuser2-full-ft', 'Yanrui95/NormalCrafter', 'THUDM/chatglm3-6b', 'microsoft/Phi-4-mini-instruct', 'Qwen/Qwen2-VL-7B-Instruct', 'PromptEnhancer/PromptEnhancer-32B', 'ideogram-ai/ideogram-4-nf4', 'MiaoshouAI/Florence-2-base-PromptGen-v1.5', 'microsoft/Florence-2-large-ft', 'google/paligemma2-28b-pt-896', 'MiaoshouAI/Florence-2-large-PromptGen-v2.0', 'llava-hf/llama3-llava-next-8b-hf', 'thwri/CogFlorence-2.2-Large', 'gokaygokay/Florence-2-SD3-Captioner', 'deepseek-ai/DeepSeek-V3', 'HiDream-ai/HiDream-O1-Image-Dev', 'facebook/nllb-200-distilled-1.3B', 'ideogram-ai/ideogram-4-fp8', 'llava-hf/llava-onevision-qwen2-7b-si-hf', 'ResembleAI/chatterbox', 'gokaygokay/Florence-2-Flux-Large', 'google/paligemma2-10b-pt-896', 'microsoft/Florence-2-base', 'MiaoshouAI/Florence-2-base-PromptGen-v2.0', 'appmana/Cosmos-1.0-Prompt-Upsampler-12B-Text2World-hf', 'MiaoshouAI/Florence-2-large-PromptGen-v1.5', 'ResembleAI/chatterbox-turbo', 'thwri/CogFlorence-2.1-Large', 'JingyeChen22/textdiffuser2_layout_planner', 'HiDream-ai/HiDream-O1-Image', 'google/paligemma-3b-ft-refcoco-seg-896', 'llava-hf/llava-v1.6-mistral-7b-hf', 'roborovski/superprompt-v1', 'microsoft/phi-4', 'microsoft/Florence-2-base-ft'] | _Omitted = ...,
    overwrite_tokenizer: bool | _Omitted = ...,
    subfolder: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['microsoft/Florence-2-large', 'JingyeChen22/textdiffuser2-full-ft', 'Yanrui95/NormalCrafter', 'THUDM/chatglm3-6b', 'microsoft/Phi-4-mini-instruct', 'Qwen/Qwen2-VL-7B-Instruct', 'PromptEnhancer/PromptEnhancer-32B', 'ideogram-ai/ideogram-4-nf4', 'MiaoshouAI/Florence-2-base-PromptGen-v1.5', 'microsoft/Florence-2-large-ft', 'google/paligemma2-28b-pt-896', 'MiaoshouAI/Florence-2-large-PromptGen-v2.0', 'llava-hf/llama3-llava-next-8b-hf', 'thwri/CogFlorence-2.2-Large', 'gokaygokay/Florence-2-SD3-Captioner', 'deepseek-ai/DeepSeek-V3', 'HiDream-ai/HiDream-O1-Image-Dev', 'facebook/nllb-200-distilled-1.3B', 'ideogram-ai/ideogram-4-fp8', 'llava-hf/llava-onevision-qwen2-7b-si-hf', 'ResembleAI/chatterbox', 'gokaygokay/Florence-2-Flux-Large', 'google/paligemma2-10b-pt-896', 'microsoft/Florence-2-base', 'MiaoshouAI/Florence-2-base-PromptGen-v2.0', 'appmana/Cosmos-1.0-Prompt-Upsampler-12B-Text2World-hf', 'MiaoshouAI/Florence-2-large-PromptGen-v1.5', 'ResembleAI/chatterbox-turbo', 'thwri/CogFlorence-2.1-Large', 'JingyeChen22/textdiffuser2_layout_planner', 'HiDream-ai/HiDream-O1-Image', 'google/paligemma-3b-ft-refcoco-seg-896', 'llava-hf/llava-v1.6-mistral-7b-hf', 'roborovski/superprompt-v1', 'microsoft/phi-4', 'microsoft/Florence-2-base-ft'] | _Omitted = ...,
    subfolder: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersLoader1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: str | _Omitted = ...,
    subfolder: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersLoaderQuantized(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: str | _Omitted = ...,
    load_in_4bit: bool | _Omitted = ...,
    load_in_8bit: bool | _Omitted = ...,
    subfolder: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersM2M100LanguageCodes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lang_id: Literal['af', 'am', 'ar', 'ast', 'az', 'ba', 'be', 'bg', 'bn', 'br', 'bs', 'ca', 'ceb', 'cs', 'cy', 'da', 'de', 'el', 'en', 'es', 'et', 'fa', 'ff', 'fi', 'fr', 'fy', 'ga', 'gd', 'gl', 'gu', 'ha', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'ig', 'ilo', 'is', 'it', 'ja', 'jv', 'ka', 'kk', 'km', 'kn', 'ko', 'lb', 'lg', 'ln', 'lo', 'lt', 'lv', 'mg', 'mk', 'ml', 'mn', 'mr', 'ms', 'my', 'ne', 'nl', 'no', 'ns', 'oc', 'or', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'sd', 'si', 'sk', 'sl', 'so', 'sq', 'sr', 'ss', 'su', 'sv', 'sw', 'ta', 'th', 'tl', 'tn', 'tr', 'uk', 'ur', 'uz', 'vi', 'wo', 'xh', 'yi', 'yo', 'zh', 'zu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransformersTranslationTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    src_lang: str | _Omitted = ...,
    tgt_lang: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TrimAudioDuration(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    duration: float | _Omitted = ...,
    start_index: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TrimVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    trim_amount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripleCLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name1: Any | _Omitted = ...,
    clip_name2: Any | _Omitted = ...,
    clip_name3: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoConversionNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    format: Any | _Omitted = ...,
    original_model_task_id: Any | _Omitted = ...,
    animate_in_place: bool | _Omitted = ...,
    bake: bool | _Omitted = ...,
    export_orientation: Any | _Omitted = ...,
    export_vertex_colors: bool | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    fbx_preset: Any | _Omitted = ...,
    flatten_bottom: bool | _Omitted = ...,
    flatten_bottom_threshold: float | _Omitted = ...,
    force_symmetry: bool | _Omitted = ...,
    pack_uv: bool | _Omitted = ...,
    part_names: str | _Omitted = ...,
    pivot_to_center_bottom: bool | _Omitted = ...,
    quad: bool | _Omitted = ...,
    scale_factor: float | _Omitted = ...,
    texture_format: Any | _Omitted = ...,
    texture_size: int | _Omitted = ...,
    with_animation: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoImageToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    geometry_quality: Any | _Omitted = ...,
    model_seed: int | _Omitted = ...,
    model_version: Any | _Omitted = ...,
    orientation: Any | _Omitted = ...,
    pbr: bool | _Omitted = ...,
    quad: bool | _Omitted = ...,
    style: Any | _Omitted = ...,
    texture: bool | _Omitted = ...,
    texture_alignment: Any | _Omitted = ...,
    texture_quality: Any | _Omitted = ...,
    texture_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoMultiviewToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    geometry_quality: Any | _Omitted = ...,
    image_back: Any | _Omitted = ...,
    image_left: Any | _Omitted = ...,
    image_right: Any | _Omitted = ...,
    model_seed: int | _Omitted = ...,
    model_version: Any | _Omitted = ...,
    orientation: Any | _Omitted = ...,
    pbr: bool | _Omitted = ...,
    quad: bool | _Omitted = ...,
    texture: bool | _Omitted = ...,
    texture_alignment: Any | _Omitted = ...,
    texture_quality: Any | _Omitted = ...,
    texture_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoP1ImageToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    output_mode: Any | _Omitted = ...,
    auto_size: bool | _Omitted = ...,
    compress_geometry: bool | _Omitted = ...,
    enable_image_autofix: bool | _Omitted = ...,
    export_uv: bool | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    model_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoP1MultiviewToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    output_mode: Any | _Omitted = ...,
    auto_size: bool | _Omitted = ...,
    compress_geometry: bool | _Omitted = ...,
    export_uv: bool | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    image_back: Any | _Omitted = ...,
    image_left: Any | _Omitted = ...,
    image_right: Any | _Omitted = ...,
    model_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoP1TextToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    output_mode: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    auto_size: bool | _Omitted = ...,
    compress_geometry: bool | _Omitted = ...,
    export_uv: bool | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    image_seed: int | _Omitted = ...,
    model_seed: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoRefineNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_task_id: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoRetargetNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    animation: Any | _Omitted = ...,
    original_model_task_id: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoRigNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    original_model_task_id: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoSplatConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoSplatPreprocessImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    erode_radius: int | _Omitted = ...,
    size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoSplatSamplingPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_gaussians: int | _Omitted = ...,
    octree_level: int | _Omitted = ...,
    pitch: float | _Omitted = ...,
    point_size: int | _Omitted = ...,
    yaw: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoTextToModelNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    face_limit: int | _Omitted = ...,
    geometry_quality: Any | _Omitted = ...,
    image_seed: int | _Omitted = ...,
    model_seed: int | _Omitted = ...,
    model_version: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    pbr: bool | _Omitted = ...,
    quad: bool | _Omitted = ...,
    style: Any | _Omitted = ...,
    texture: bool | _Omitted = ...,
    texture_quality: Any | _Omitted = ...,
    texture_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TripoTextureNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_task_id: Any | _Omitted = ...,
    pbr: bool | _Omitted = ...,
    texture: bool | _Omitted = ...,
    texture_alignment: Any | _Omitted = ...,
    texture_quality: Any | _Omitted = ...,
    texture_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TruncateText(
    *args: VibeWorkflow,
    _id: str | None = ...,
    max_length: int | _Omitted = ...,
    texts: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UNETLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    unet_name: Literal['Chroma1-HD-fp8mixed.safetensors', 'Cosmos-1_0-Diffusion-14B-Text2World.safetensors', 'Cosmos-1_0-Diffusion-14B-Video2World.safetensors', 'Cosmos-1_0-Diffusion-7B-Text2World.safetensors', 'Cosmos-1_0-Diffusion-7B-Video2World.safetensors', 'Hyper-SDXL-1step-Unet-Comfyui.fp16.safetensors', 'NewBie-Image-Exp0.1-bf16.safetensors', 'Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf', 'Wan2.2-T2V-A14B-HighNoise-Q8_0.gguf', 'Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf', 'Wan2.2-T2V-A14B-LowNoise-Q8_0.gguf', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/Wan2.1-Fun-V1.1-1.3B-Control-Camera.safetensors', 'WanVideo/Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors', 'WanVideo/Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors', 'WanVideo/Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors', 'WanVideo/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/Wan2_1-VACE_module_1_3B_bf16.safetensors', 'WanVideo/fp8_scaled_kj/I2V/Wan2_1-I2V-14B-720p_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/fp8_scaled_kj/T2V/Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/wan2.1_fun_control_1.3B_bf16.safetensors', 'WanVideo/wan2.1_t2v_1.3B_fp16.safetensors', 'acestep_v1.5_turbo.safetensors', 'acestep_v1.5_xl_base_bf16.safetensors', 'acestep_v1.5_xl_sft_bf16.safetensors', 'acestep_v1.5_xl_turbo_bf16.safetensors', 'anima-preview.safetensors', 'anima-preview2.safetensors', 'anima-preview3-base.safetensors', 'capybara_v0.1.safetensors', 'chroma-radiance-x0.safetensors', 'chroma-unlocked-v37.safetensors', 'chrono_edit_14B_fp16.safetensors', 'cosmos_predict2_14B_t2i.safetensors', 'cosmos_predict2_2B_t2i.safetensors', 'cosmos_predict2_2B_video2world_480p_16fps.safetensors', 'flux-2-klein-4b.safetensors', 'flux-2-klein-base-4b.safetensors', 'flux.1-fill-dev-OneReward-transformer_fp8.safetensors', 'flux1-canny-dev.safetensors', 'flux1-depth-dev.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-dev-kontext_fp8_scaled.safetensors', 'flux1-dev.safetensors', 'flux1-fill-dev.safetensors', 'flux1-kontext-dev.safetensors', 'flux1-krea-dev_fp8_scaled.safetensors', 'flux1-schnell-fp8.safetensors', 'flux1-schnell.safetensors', 'flux2_dev_fp8mixed.safetensors', 'hidream_e1_1_bf16.safetensors', 'hidream_e1_full_bf16.safetensors', 'hidream_i1_dev_bf16.safetensors', 'hidream_i1_dev_fp8.safetensors', 'hidream_i1_fast_fp8.safetensors', 'hidream_i1_full_fp16.safetensors', 'hidream_i1_full_fp8.safetensors', 'humo_17B_fp8_e4m3fn.safetensors', 'hunyuan_video_image_to_video_720p_bf16.safetensors', 'hunyuan_video_t2v_720p_bf16.safetensors', 'hunyuan_video_v2_replace_image_to_video_720p_bf16.safetensors', 'hunyuanimage2.1_bf16.safetensors', 'hunyuanimage2.1_refiner_bf16.safetensors', 'hunyuanvideo1.5_1080p_sr_distilled_fp16.safetensors', 'hunyuanvideo1.5_720p_i2v_fp16.safetensors', 'hunyuanvideo1.5_720p_t2v_fp16.safetensors', 'longcat_image_bf16.safetensors', 'lotus-depth-g-v1-0-fp16.safetensors', 'lotus-normal-g-v1-0-fp16.safetensors', 'ltx-2-19b-distilled_transformer_only_bf16.safetensors', 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'lumina_2_model_bf16.safetensors', 'mochi_preview_bf16.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'omnigen2_fp16.safetensors', 'ovis_image_bf16.safetensors', 'qwen-image-Q4_K_M.gguf', 'qwen-image-Q8_0.gguf', 'qwen_image_2512_bf16.safetensors', 'qwen_image_2512_fp8_e4m3fn.safetensors', 'qwen_image_bf16.safetensors', 'qwen_image_distill_full_bf16.safetensors', 'qwen_image_distill_full_fp8_e4m3fn.safetensors', 'qwen_image_edit_2509_bf16.safetensors', 'qwen_image_edit_2509_fp8_e4m3fn.safetensors', 'qwen_image_edit_2511_bf16.safetensors', 'qwen_image_edit_bf16.safetensors', 'qwen_image_edit_fp8_e4m3fn.safetensors', 'qwen_image_fp8_e4m3fn.safetensors', 'qwen_image_layered_bf16.safetensors', 'wan2.1_flf2v_720p_14B_fp16.safetensors', 'wan2.1_fun_camera_v1.1_1.3B_bf16.safetensors', 'wan2.1_fun_camera_v1.1_14B_bf16.safetensors', 'wan2.1_fun_control_1.3B_bf16.safetensors', 'wan2.1_fun_inp_1.3B_bf16.safetensors', 'wan2.1_i2v_480p_14B_bf16.safetensors', 'wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors', 'wan2.1_i2v_720p_14B_bf16.safetensors', 'wan2.1_i2v_720p_14B_fp8_e4m3fn.safetensors', 'wan2.1_t2v_1.3B_bf16.safetensors', 'wan2.1_t2v_14B_bf16.safetensors', 'wan2.1_t2v_14B_fp8_e4m3fn.safetensors', 'wan2.1_t2v_14B_fp8_scaled.safetensors', 'wan2.1_vace_1.3B_fp16.safetensors', 'wan2.1_vace_14B_fp16.safetensors', 'wan2.2_fun_camera_high_noise_14B_fp8_scaled.safetensors', 'wan2.2_fun_camera_low_noise_14B_fp8_scaled.safetensors', 'wan2.2_fun_control_5B_bf16.safetensors', 'wan2.2_fun_control_high_noise_14B_fp8_scaled.safetensors', 'wan2.2_fun_control_low_noise_14B_fp8_scaled.safetensors', 'wan2.2_fun_inpaint_5B_bf16.safetensors', 'wan2.2_fun_inpaint_high_noise_14B_fp8_scaled.safetensors', 'wan2.2_fun_inpaint_low_noise_14B_fp8_scaled.safetensors', 'wan2.2_i2v_high_noise_14B_fp16.safetensors', 'wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors', 'wan2.2_i2v_low_noise_14B_fp16.safetensors', 'wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors', 'wan2.2_s2v_14B_fp8_scaled.safetensors', 'wan2.2_t2v_high_noise_14B_fp16.safetensors', 'wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors', 'wan2.2_t2v_low_noise_14B_fp16.safetensors', 'wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors', 'wan2.2_ti2v_5B_fp16.safetensors', 'z_image_bf16.safetensors', 'z_image_turbo_bf16.safetensors'] | _Omitted = ...,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e5m2', 'fp8_e4m3fn_fast'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UNetCrossAttentionMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    k: float | _Omitted = ...,
    out: float | _Omitted = ...,
    q: float | _Omitted = ...,
    v: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UNetSelfAttentionMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    k: float | _Omitted = ...,
    out: float | _Omitted = ...,
    q: float | _Omitted = ...,
    v: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UNetTemporalAttentionMultiply(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    cross_structural: float | _Omitted = ...,
    cross_temporal: float | _Omitted = ...,
    self_structural: float | _Omitted = ...,
    self_temporal: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def USOStyleReference(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision_output: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    model_patch: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UnaryOperation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    op: Literal['__abs__', '__call__', '__index__', '__inv__', '__invert__', '__neg__', '__not__', '__pos__', '_abs', 'abs', 'call', 'index', 'inv', 'invert', 'neg', 'not_', 'pos', 'truth', 'not'] | _Omitted = ...,
    value: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UpscaleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['1xSkinContrast-SuperUltraCompact.pth', '4x-UltraSharp.pth', '4xNomos8kSCHAT-L.pth', '4xNomos8k_atd_jpg.pth', '4xNomos8k_atd_jpg.safetensors', '4x_NMKD-Siax_200k.pth', '4x_NMKD-Superscale-SP_178000_G.pth', '4x_foolhardy_Remacri.pth', 'RealESRGAN_x2plus.pth', 'RealESRGAN_x4plus.pth', 'RealESRGAN_x4plus.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UriFormat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_index_format_name: str | _Omitted = ...,
    image_hash_format_name: str | _Omitted = ...,
    metadata_uri_extension: str | _Omitted = ...,
    output_dir_format_name: str | _Omitted = ...,
    uri_template: str | _Omitted = ...,
    uuid_format_name: str | _Omitted = ...,
    image_hashes: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeAudioTiled(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeHunyuan3D(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_chunks: int | _Omitted = ...,
    octree_resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeTiled(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    temporal_overlap: int | _Omitted = ...,
    temporal_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeTripoSplat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_gaussians: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pixels: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEEncodeAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEEncodeForInpaint(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pixels: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    grow_mask_by: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEEncodeTiled(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pixels: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    temporal_overlap: int | _Omitted = ...,
    temporal_size: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae_name: Literal['LTX23_video_vae_bf16.safetensors', 'Wan2_1_VAE_bf16.safetensors', 'Wan2_2_VAE_bf16.safetensors', 'ace_1.5_vae.safetensors', 'ae.safetensors', 'cosmos_cv8x8x8_1.0.safetensors', 'flux2-vae.safetensors', 'hunyuan_image_2.1_vae_fp16.safetensors', 'hunyuan_image_refiner_vae_fp16.safetensors', 'hunyuan_video_vae_bf16.safetensors', 'hunyuanvideo15_vae_fp16.safetensors', 'lumina_image_2.0-ae.safetensors', 'mochi_vae.safetensors', 'qwen_image_layered_vae.safetensors', 'qwen_image_vae.safetensors', 'sdxl_vae.safetensors', 'taeltx2_3.safetensors', 'vae-ft-mse-840000-ema-pruned.safetensors', 'wan2.2_vae.safetensors', 'wan_2.1_vae.safetensors', 'wan_alpha_2.1_vae_alpha_channel.safetensors', 'wan_alpha_2.1_vae_rgb_channel.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors', 'z_image_turbo_vae.safetensors', 'pixel_space'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAESave(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VOIDInpaintConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    quadmask: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    video: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VOIDQuadmaskPreprocess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    dilate_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VOIDSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VOIDWarpedNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    optical_flow: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VOIDWarpedNoiseSource(
    *args: VibeWorkflow,
    _id: str | None = ...,
    warped_noise: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VPScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    beta_d: float | _Omitted = ...,
    beta_min: float | _Omitted = ...,
    eps_s: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Veo3FirstLastFrameNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_frame: Any | _Omitted = ...,
    last_frame: Any | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Veo3VideoGenerationNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    duration_seconds: int | _Omitted = ...,
    enhance_prompt: bool | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    person_generation: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VeoVideoGenerationNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    duration_seconds: int | _Omitted = ...,
    enhance_prompt: bool | _Omitted = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    person_generation: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VideoLinearCFGGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    min_cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VideoRequestParameter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    required: bool | _Omitted = ...,
    default_if_empty: Any | _Omitted = ...,
    description: str | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    name: str | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_frames: int | _Omitted = ...,
    title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VideoTriangleCFGGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    min_cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Video_Slice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    duration: float | _Omitted = ...,
    start_time: float | _Omitted = ...,
    strict_duration: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu2ImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu2ReferenceVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    audio: bool | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    subjects: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu2StartEndToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    first_frame: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu2TextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    aspect_ratio: Any | _Omitted = ...,
    background_music: bool | _Omitted = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu3ImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu3StartEndToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    first_frame: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Vidu3TextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ViduExtendVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    end_frame: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ViduImageToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ViduMultiFrameVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_image: Any | _Omitted = ...,
    frames: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ViduReferenceVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ViduStartEndToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    first_frame: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ViduTextToVideoNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    aspect_ratio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    movement_amplitude: Any | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VoxelToMesh(
    *args: VibeWorkflow,
    _id: str | None = ...,
    algorithm: Any | _Omitted = ...,
    threshold: float | _Omitted = ...,
    voxel: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VoxelToMeshBasic(
    *args: VibeWorkflow,
    _id: str | None = ...,
    threshold: float | _Omitted = ...,
    voxel: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan22FunControlToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    control_video: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan22ImageToVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan2ImageToVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_frame: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt_extend: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    audio: Any | _Omitted = ...,
    last_frame: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan2ReferenceVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan2TextToVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt_extend: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan2VideoContinuationApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    first_clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt_extend: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    last_frame: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan2VideoEditApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    audio_setting: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanAnimateToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    continue_motion_max_frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    video_frame_offset: int | _Omitted = ...,
    width: int | _Omitted = ...,
    background_video: Any | _Omitted = ...,
    character_mask: Any | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    continue_motion: Any | _Omitted = ...,
    face_video: Any | _Omitted = ...,
    pose_video: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanCameraEmbedding(
    *args: VibeWorkflow,
    _id: str | None = ...,
    camera_pose: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    cx: float | _Omitted = ...,
    cy: float | _Omitted = ...,
    fx: float | _Omitted = ...,
    fy: float | _Omitted = ...,
    speed: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanCameraImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    camera_conditions: Any | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanContextWindowsManual(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    closed_loop: bool | _Omitted = ...,
    context_length: int | _Omitted = ...,
    context_overlap: int | _Omitted = ...,
    context_schedule: Any | _Omitted = ...,
    context_stride: int | _Omitted = ...,
    freenoise: bool | _Omitted = ...,
    fuse_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanDancerEncodeAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    audio_inject_scale: float | _Omitted = ...,
    video_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanDancerPadKeyframes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    segment_index: int | _Omitted = ...,
    segment_length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanDancerPadKeyframesList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    num_segments: int | _Omitted = ...,
    segment_length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanDancerVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    audio_encoder_output: Any | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    clip_vision_output_ref: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanFirstLastFrameToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_end_image: Any | _Omitted = ...,
    clip_vision_start_image: Any | _Omitted = ...,
    end_image: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanFunControlToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    control_video: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanFunInpaintToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    end_image: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanHuMoImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    audio_encoder_output: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanImage2VideoTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanImageToImageApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanImageToVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    audio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt_extend: bool | _Omitted = ...,
    resolution: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    shot_type: Any | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanInfiniteTalkToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    audio_encoder_output_1: Any | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    mode: Any | _Omitted = ...,
    model_patch: Any | _Omitted = ...,
    motion_frame_count: int | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    previous_frames: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanMoveConcatTrack(
    *args: VibeWorkflow,
    _id: str | None = ...,
    tracks_1: Any | _Omitted = ...,
    tracks_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanMoveTrackToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    tracks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanMoveTracksFromCoords(
    *args: VibeWorkflow,
    _id: str | None = ...,
    track_coords: str | _Omitted = ...,
    track_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanMoveVisualizeTracks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    circle_size: int | _Omitted = ...,
    line_resolution: int | _Omitted = ...,
    line_width: int | _Omitted = ...,
    opacity: float | _Omitted = ...,
    tracks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanPhantomSubjectToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanReferenceVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    duration: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    reference_videos: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    shot_type: Any | _Omitted = ...,
    size: Any | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanSCAILToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    pose_end: float | _Omitted = ...,
    pose_start: float | _Omitted = ...,
    pose_strength: float | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    pose_video: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanSoundImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    width: int | _Omitted = ...,
    audio_encoder_output: Any | _Omitted = ...,
    control_video: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    ref_motion: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanSoundImageToVideoExtend(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    video_latent: Any | _Omitted = ...,
    length: int | _Omitted = ...,
    audio_encoder_output: Any | _Omitted = ...,
    control_video: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanText2VideoTokenize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanTextToImageApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    height: int | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt_extend: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanTextToVideoApi(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    audio: Any | _Omitted = ...,
    duration: int | _Omitted = ...,
    generate_audio: bool | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    prompt_extend: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    shot_type: Any | _Omitted = ...,
    size: Any | _Omitted = ...,
    watermark: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanTrackToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    topk: int | _Omitted = ...,
    tracks: str | _Omitted = ...,
    width: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVaceToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    width: int | _Omitted = ...,
    control_masks: Any | _Omitted = ...,
    control_video: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WavespeedFlashVSRNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    target_resolution: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WavespeedImageUpscaleNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    target_resolution: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WebcamCapture(
    *args: VibeWorkflow,
    _id: str | None = ...,
    capture_on_queue: bool | _Omitted = ...,
    height: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ZImageFunControlnet(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    model_patch: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    image: Any | _Omitted = ...,
    inpaint_image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def unCLIPCheckpointLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['LTX23_audio_vae_bf16.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'stable_cascade_stage_c.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def unCLIPConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision_output: Any | _Omitted = ...,
    conditioning: Any | _Omitted = ...,
    noise_augmentation: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def wanBlockSwap(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['APG', 'ARVideoI2V', 'AddLatentGuide', 'AddNoise', 'AddTextPrefix', 'AddTextSuffix', 'AdjustBrightness', 'AdjustContrast', 'AlignYourStepsScheduler', 'AudioAdjustVolume', 'AudioConcat', 'AudioEncoderEncode', 'AudioEncoderLoader', 'AudioEqualizer3Band', 'AudioMerge', 'AudioRequestParameter', 'BasicGuider', 'BasicScheduler', 'BatchImagesNode', 'BatchLatentsNode', 'BatchMasksNode', 'BeebleSwitchXImageEdit', 'BeebleSwitchXVideoEdit', 'BetaSamplingScheduler', 'BinaryOperation', 'BooleanBinaryOperation', 'BooleanRequestParameter', 'BooleanUnaryOperation', 'BriaImageEditNode', 'BriaRemoveImageBackground', 'BriaRemoveVideoBackground', 'ByteDance2FirstLastFrameNode', 'ByteDance2ReferenceNode', 'ByteDance2TextToVideoNode', 'ByteDanceCreateImageAsset', 'ByteDanceCreateVideoAsset', 'ByteDanceFirstLastFrameNode', 'ByteDanceImageNode', 'ByteDanceImageReferenceNode', 'ByteDanceImageToVideoNode', 'ByteDanceSeedNode', 'ByteDanceSeedreamNode', 'ByteDanceSeedreamNodeV2', 'ByteDanceTextToVideoNode', 'CFGGuider', 'CFGNorm', 'CFGOverride', 'CFGZeroStar', 'CLIPAttentionMultiply', 'CLIPLoader', 'CLIPMergeAdd', 'CLIPMergeSimple', 'CLIPMergeSubtract', 'CLIPSave', 'CLIPSetLastLayer', 'CLIPTextEncode', 'CLIPTextEncodeControlnet', 'CLIPTextEncodeFlux', 'CLIPTextEncodeHiDream', 'CLIPTextEncodeHunyuanDiT', 'CLIPTextEncodeKandinsky5', 'CLIPTextEncodeLumina2', 'CLIPTextEncodePixArtAlpha', 'CLIPTextEncodeSD3', 'CLIPTextEncodeSDXL', 'CLIPTextEncodeSDXLRefiner', 'CLIPVisionEncode', 'CLIPVisionLoader', 'CM_IntToFloat', 'Canny', 'CaseConverter', 'CenterCropImages', 'CheckpointLoader', 'CheckpointLoaderSimple', 'CheckpointSave', 'ChromaRadianceOptions', 'ClaudeNode', 'ColorToRGBInt', 'ColorTransfer', 'CombineHooks2', 'CombineHooks4', 'CombineHooks8', 'ComfyAndNode', 'ComfyMathExpression', 'ComfyNotNode', 'ComfyNumberConvert', 'ComfyOrNode', 'ComfySwitchNode', 'CompositeCroppedAndFittedInpaintResult', 'ConditioningAverage', 'ConditioningCombine', 'ConditioningConcat', 'ConditioningSetArea', 'ConditioningSetAreaPercentage', 'ConditioningSetAreaPercentageVideo', 'ConditioningSetAreaStrength', 'ConditioningSetDefaultCombine', 'ConditioningSetMask', 'ConditioningSetProperties', 'ConditioningSetPropertiesAndCombine', 'ConditioningSetTimestepRange', 'ConditioningStableAudio', 'ConditioningTimestepsRange', 'ConditioningZeroOut', 'ContextWindowsManual', 'ControlNetApply', 'ControlNetApplyAdvanced', 'ControlNetApplySD3', 'ControlNetInpaintingAliMamaApply', 'ControlNetLoader', 'ControlNetLoaderWeights', 'CosmosImageToVideoLatent', 'CosmosPredict2ImageToVideoLatent', 'CosmosPromptUpsamplerLoader', 'CosmosText2WorldTokenize', 'CosmosVideo2WorldTokenize', 'CreateCameraInfo', 'CreateHookKeyframe', 'CreateHookKeyframesFromFloats', 'CreateHookKeyframesInterpolated', 'CreateHookLora', 'CreateHookLoraModelOnly', 'CreateHookModelAsLora', 'CreateHookModelAsLoraModelOnly', 'CreateList', 'CreateVideo', 'CropAndFitInpaintToDiffusionSize', 'CropByBBoxes', 'CropMask', 'CurveEditor', 'CustomCombo', 'DallEGenerate', 'DevNullUris', 'DiffControlNetLoader', 'DifferentialDiffusion', 'DiffusersLoader', 'DisableNoise', 'DrawBBoxes', 'DualCFGGuider', 'DualCLIPLoader', 'DualModelGuider', 'EasyCache', 'ElevenLabsAudioIsolation', 'ElevenLabsInstantVoiceClone', 'ElevenLabsSpeechToSpeech', 'ElevenLabsSpeechToText', 'ElevenLabsTextToDialogue', 'ElevenLabsTextToSoundEffects', 'ElevenLabsTextToSpeech', 'ElevenLabsVoiceSelector', 'EmptyARVideoLatent', 'EmptyAceStep1_5LatentAudio', 'EmptyAceStepLatentAudio', 'EmptyAudio', 'EmptyChromaRadianceLatentImage', 'EmptyCosmosLatentVideo', 'EmptyFlux2LatentImage', 'EmptyHiDreamO1LatentImage', 'EmptyHunyuanImageLatent', 'EmptyHunyuanLatentVideo', 'EmptyHunyuanVideo15Latent', 'EmptyImage', 'EmptyLTXVLatentVideo', 'EmptyLatentAudio', 'EmptyLatentHunyuan3Dv2', 'EmptyLatentImage', 'EmptyMochiLatentVideo', 'EmptyQwenImageLayeredLatentImage', 'EmptySD3LatentImage', 'EnhanceContrast', 'Epsilon_Scaling', 'EvalPython_1_1', 'EvalPython_1_List', 'EvalPython_5_5', 'EvalPython_List_1', 'EvalPython_List_List', 'ExponentialScheduler', 'ExtendIntermediateSigmas', 'FeatherMask', 'File3DToSplat', 'Flatten', 'FlipSigmas', 'FloatAbs', 'FloatAdd', 'FloatAverage', 'FloatClamp', 'FloatDivide', 'FloatInverseLerp', 'FloatLerp', 'FloatMax', 'FloatMin', 'FloatMultiply', 'FloatPower', 'FloatRange1', 'FloatRange2', 'FloatRange3', 'FloatRequestParameter', 'FloatSubtract', 'FloatToInt', 'FloatToString', 'Florence2OutputToMask', 'Florence2PostProcess', 'Florence2TaskTokenize', 'Flux2ImageNode', 'Flux2MaxImageNode', 'Flux2ProImageNode', 'Flux2Scheduler', 'FluxDisableGuidance', 'FluxEraseNode', 'FluxGuidance', 'FluxKVCache', 'FluxKontextImageScale', 'FluxKontextMaxImageNode', 'FluxKontextMultiReferenceLatentMethod', 'FluxKontextProImageNode', 'FluxProExpandNode', 'FluxProFillNode', 'FluxProUltraImageNode', 'FluxVTONode', 'FrameInterpolate', 'FrameInterpolationModelLoader', 'FreSca', 'FreeU', 'FreeU_V2', 'GITSScheduler', 'GLIGENLoader', 'GLIGENTextBoxApply', 'GLSLShader', 'GeminiImage2Node', 'GeminiImageNode', 'GeminiInputFiles', 'GeminiNanoBanana2', 'GeminiNanoBanana2V2', 'GeminiNode', 'GenerateTracks', 'GetICLoRAParameters', 'GetImageRangeFromBatch', 'GetImageSize', 'GetSplatCount', 'GetVideoComponents', 'GrokImageEditNode', 'GrokImageEditNodeV2', 'GrokImageNode', 'GrokVideoEditNode', 'GrokVideoExtendNode', 'GrokVideoNode', 'GrokVideoReferenceNode', 'GroupOffload', 'GrowMask', 'HappyHorseImageToVideoApi', 'HappyHorseReferenceVideoApi', 'HappyHorseTextToVideoApi', 'HappyHorseVideoEditApi', 'HashImage', 'HiDreamO1PatchSeamSmoothing', 'HiDreamO1ReferenceImages', 'HintImageEnchance', 'HitPawGeneralImageEnhance', 'HitPawVideoEnhance', 'Hunyuan3Dv2Conditioning', 'Hunyuan3Dv2ConditioningMultiView', 'HunyuanImageToVideo', 'HunyuanRefinerLatent', 'HunyuanVideo15ImageToVideo', 'HunyuanVideo15LatentUpscaleWithModel', 'HunyuanVideo15SuperResolution', 'HyperTile', 'HypernetworkLoader', 'Ideogram4Scheduler', 'IdeogramDescribe', 'IdeogramEdit', 'IdeogramGenerate', 'IdeogramRemix', 'IdeogramV1', 'IdeogramV2', 'IdeogramV3', 'IdeogramV4', 'ImageAddNoise', 'ImageAndMaskResizeNode', 'ImageApplyColorMap', 'ImageBatch', 'ImageBlend', 'ImageBlur', 'ImageColorToMask', 'ImageCompare', 'ImageCompositeMasked', 'ImageCrop', 'ImageCropV2', 'ImageDeduplication', 'ImageExif', 'ImageExifCreationDateAndBatchNumber', 'ImageExifMerge', 'ImageExifUncommon', 'ImageFlip', 'ImageFromBatch', 'ImageGenResolutionFromImage', 'ImageGenResolutionFromLatent', 'ImageGenerateGradient', 'ImageGrid', 'ImageHistogram', 'ImageInvert', 'ImageLevels', 'ImageLuminance', 'ImageMax', 'ImageMergeTileList', 'ImageMin', 'ImageOnlyCheckpointLoader', 'ImageOnlyCheckpointSave', 'ImagePadForOutpaint', 'ImageQuantize', 'ImageRGBToYUV', 'ImageRequestParameter', 'ImageResize', 'ImageResize1', 'ImageRotate', 'ImageScale', 'ImageScaleBy', 'ImageScaleToMaxDimension', 'ImageScaleToTotalPixels', 'ImageShape', 'ImageSharpen', 'ImageStitch', 'ImageToMask', 'ImageToSVG', 'ImageUpscaleWithModel', 'ImageYUVToRGB', 'InpaintModelConditioning', 'InstructPixToPixConditioning', 'IntAbs', 'IntAdd', 'IntAverage', 'IntClamp', 'IntDivide', 'IntInverseLerp', 'IntLerp', 'IntMax', 'IntMin', 'IntMod', 'IntMultiply', 'IntPower', 'IntRange', 'IntRequestParameter', 'IntSubtract', 'IntToFloat', 'IntToString', 'InvertMask', 'IsNone', 'IterateList', 'JoinAudioChannels', 'JoinImageWithAlpha', 'JsonExtractString', 'KSampler', 'KSamplerAdvanced', 'KSamplerSelect', 'Kandinsky5ImageToVideo', 'KarrasScheduler', 'KlingAvatarNode', 'KlingCameraControlI2VNode', 'KlingCameraControlT2VNode', 'KlingCameraControls', 'KlingDualCharacterVideoEffectNode', 'KlingFirstLastFrameNode', 'KlingImage2VideoNode', 'KlingImageGenerationNode', 'KlingImageToVideoWithAudio', 'KlingLipSyncAudioToVideoNode', 'KlingLipSyncTextToVideoNode', 'KlingMotionControl', 'KlingOmniProEditVideoNode', 'KlingOmniProFirstLastFrameNode', 'KlingOmniProImageNode', 'KlingOmniProImageToVideoNode', 'KlingOmniProTextToVideoNode', 'KlingOmniProVideoToVideoNode', 'KlingSingleImageVideoEffectNode', 'KlingStartEndFrameNode', 'KlingTextToVideoNode', 'KlingTextToVideoWithAudio', 'KlingVideoExtendNode', 'KlingVideoNode', 'KlingVirtualTryOnNode', 'Krea2ImageNode', 'Krea2StyleReferenceNode', 'LTXAVTextEncoderLoader', 'LTXVAddGuide', 'LTXVAddGuideMulti', 'LTXVAddGuidesFromBatch', 'LTXVAudioVAEDecode', 'LTXVAudioVAEEncode', 'LTXVAudioVAELoader', 'LTXVAudioVAELoader1', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideo', 'LTXVImgToVideoInplace', 'LTXVLatentUpsampler', 'LTXVPreprocess', 'LTXVReferenceAudio', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LaplaceScheduler', 'LatentAdd', 'LatentAddNoiseChannels', 'LatentApplyOperation', 'LatentApplyOperationCFG', 'LatentBatch', 'LatentBatchSeedBehavior', 'LatentBlend', 'LatentComposite', 'LatentCompositeMasked', 'LatentConcat', 'LatentCrop', 'LatentCut', 'LatentCutToBatch', 'LatentFlip', 'LatentFromBatch', 'LatentInterpolate', 'LatentMultiply', 'LatentOperationSharpen', 'LatentOperationTonemapReinhard', 'LatentRotate', 'LatentSubtract', 'LatentUpscale', 'LatentUpscaleBy', 'LatentUpscaleModelLoader', 'LatentUpscaleModelLoader1', 'LayerwiseCast', 'LazyCache', 'LazySwitch', 'LegacyOutputURIs', 'Load3D', 'LoadAudio', 'LoadAudioFromURL', 'LoadBackgroundRemovalModel', 'LoadImage', 'LoadImageDataSetFromFolder', 'LoadImageFromURL', 'LoadImageMask', 'LoadImageOutput', 'LoadImageTextDataSetFromFolder', 'LoadLatent', 'LoadMediaPipeFaceLandmarker', 'LoadMoGeModel', 'LoadTrainingDataset', 'LoadVideo', 'LoadVideoFromURL', 'LoraLoader', 'LoraLoaderBypass', 'LoraLoaderBypassModelOnly', 'LoraLoaderModelOnly', 'LoraModelLoader', 'LoraSave', 'LossGraphNode', 'LotusConditioning', 'LtxvApiImageToVideo', 'LtxvApiTextToVideo', 'LumaConceptsNode', 'LumaImageEditNode2', 'LumaImageModifyNode', 'LumaImageNode', 'LumaImageNode2', 'LumaImageToVideoNode', 'LumaReferenceNode', 'LumaVideoNode', 'MagnificImageRelightNode', 'MagnificImageSkinEnhancerNode', 'MagnificImageStyleTransferNode', 'MagnificImageUpscalerCreativeNode', 'MagnificImageUpscalerPreciseV2Node', 'Mahiro', 'MakeTrainingDataset', 'ManualSigmas', 'MaskComposite', 'MaskPreview', 'MaskToImage', 'MediaPipeFaceLandmarker', 'MediaPipeFaceMask', 'MediaPipeFaceMeshVisualize', 'MergeImageLists', 'MergeSplat', 'MergeTextLists', 'MeshyAnimateModelNode', 'MeshyImageToModelNode', 'MeshyMultiImageToModelNode', 'MeshyRefineNode', 'MeshyRigModelNode', 'MeshyTextToModelNode', 'MeshyTextureNode', 'MinimaxHailuoVideoNode', 'MinimaxImageToVideoNode', 'MinimaxTextToVideoNode', 'MoGeInference', 'MoGePanoramaInference', 'MoGePointMapToMesh', 'MoGeRender', 'ModelComputeDtype', 'ModelMergeAdd', 'ModelMergeAuraflow', 'ModelMergeBlocks', 'ModelMergeCosmos14B', 'ModelMergeCosmos7B', 'ModelMergeCosmosPredict2_14B', 'ModelMergeCosmosPredict2_2B', 'ModelMergeFlux1', 'ModelMergeLTXV', 'ModelMergeMochiPreview', 'ModelMergeQwenImage', 'ModelMergeSD1', 'ModelMergeSD2', 'ModelMergeSD35_Large', 'ModelMergeSD3_2B', 'ModelMergeSDXL', 'ModelMergeSimple', 'ModelMergeSubtract', 'ModelMergeWAN2_1', 'ModelNoiseScale', 'ModelPatchLoader', 'ModelSamplingAuraFlow', 'ModelSamplingContinuousEDM', 'ModelSamplingContinuousV', 'ModelSamplingDiscrete', 'ModelSamplingFlux', 'ModelSamplingLTXV', 'ModelSamplingSD3', 'ModelSamplingStableCascade', 'ModelSave', 'MoonvalleyImg2VideoNode', 'MoonvalleyTxt2VideoNode', 'MoonvalleyVideo2VideoNode', 'Morphology', 'MultiGPU_WorkUnits', 'NAGuidance', 'NormalizeImages', 'NormalizeVideoLatentStart', 'OmitThink', 'OneShotInstructTokenize', 'OpenAIChatConfig', 'OpenAIChatNode', 'OpenAIDalle2', 'OpenAIDalle3', 'OpenAIGPTImage1', 'OpenAIGPTImageNodeV2', 'OpenAIInputFiles', 'OpenAILanguageModelLoader', 'OpenAIVideoSora2', 'OpenRouterLLMNode', 'OpticalFlowLoader', 'OptimalStepsScheduler', 'OutputTensor', 'Painter', 'PairConditioningCombine', 'PairConditioningSetDefaultCombine', 'PairConditioningSetProperties', 'PairConditioningSetPropertiesAndCombine', 'PaligemmaOutputToMask', 'PaligemmaPostProcess', 'PatchModelAddDownscale', 'PerpNeg', 'PerpNegGuider', 'PerturbedAttentionGuidance', 'PhotoMakerEncode', 'PhotoMakerLoader', 'PiDConditioning', 'PixelLatentToImage', 'PixelPerfectResolution', 'PixtralTransformersLoader', 'PixverseImageToVideoNode', 'PixverseTemplateNode', 'PixverseTextToVideoNode', 'PixverseTransitionVideoNode', 'PolyexponentialScheduler', 'PorterDuffImageComposite', 'PorterDuffImageCompositeV2', 'Posterize', 'Preview3D', 'Preview3DAdvanced', 'PreviewAny', 'PreviewAudio', 'PreviewImage', 'PreviewString', 'PrimitiveBoolean', 'PrimitiveBoundingBox', 'PrimitiveFloat', 'PrimitiveInt', 'PrimitiveString', 'PrimitiveStringMultiline', 'QuadrupleCLIPLoader', 'QuantizeModel', 'QuiverImageToSVGNode', 'QuiverTextToSVGNode', 'QwenImageDiffsynthControlnet', 'QwenVL2_5TransformersLoader', 'RTDETR_detect', 'RandomCropImages', 'RandomNoise', 'RebatchImages', 'RebatchLatents', 'RecordAudio', 'RecraftColorRGB', 'RecraftControls', 'RecraftCreateStyleNode', 'RecraftCreativeUpscaleNode', 'RecraftCrispUpscaleNode', 'RecraftImageInpaintingNode', 'RecraftImageToImageNode', 'RecraftRemoveBackgroundNode', 'RecraftReplaceBackgroundNode', 'RecraftStyleV3DigitalIllustration', 'RecraftStyleV3InfiniteStyleLibrary', 'RecraftStyleV3LogoRaster', 'RecraftStyleV3RealisticImage', 'RecraftTextToImageNode', 'RecraftTextToVectorNode', 'RecraftV4TextToImageNode', 'RecraftV4TextToVectorNode', 'RecraftVectorizeImageNode', 'ReferenceLatent', 'ReferenceOnlySimple', 'ReferenceTimbreAudio', 'Regex', 'RegexExtract', 'RegexFlags', 'RegexMatch', 'RegexMatchExpand', 'RegexMatchGroupByIndex', 'RegexMatchGroupByName', 'RegexReplace', 'RemoteLanguageLoader', 'RemoveBackground', 'RenderSplat', 'RenormCFG', 'RepeatImageBatch', 'RepeatLatentBatch', 'ReplaceText', 'ReplaceVideoLatentFrames', 'RescaleCFG', 'ResizeAndPadImage', 'ResizeImageMaskNode', 'ResizeImagesByLongerEdge', 'ResizeImagesByShorterEdge', 'ResolutionBucket', 'ResolutionSelector', 'ReveImageCreateNode', 'ReveImageEditNode', 'ReveImageRemixNode', 'Rodin3D_Detail', 'Rodin3D_Gen2', 'Rodin3D_Gen25_Image', 'Rodin3D_Gen25_Text', 'Rodin3D_Regular', 'Rodin3D_Sketch', 'Rodin3D_Smooth', 'RunwayFirstLastFrameNode', 'RunwayImageToVideoNodeGen3a', 'RunwayImageToVideoNodeGen4', 'RunwayTextToImageNode', 'SAM3_Detect', 'SAM3_TrackPreview', 'SAM3_TrackToMask', 'SAM3_VideoTrack', 'SDPoseDrawKeypoints', 'SDPoseFaceBBoxes', 'SDPoseKeypointExtractor', 'SDTurboScheduler', 'SD_4XUpscale_Conditioning', 'SUPIRApply', 'SV3D_Conditioning', 'SVD_img2vid_Conditioning', 'SVGToImage', 'SamplerARVideo', 'SamplerCustom', 'SamplerCustomAdvanced', 'SamplerDPMAdaptative', 'SamplerDPMPP_2M_SDE', 'SamplerDPMPP_2S_Ancestral', 'SamplerDPMPP_3M_SDE', 'SamplerDPMPP_SDE', 'SamplerER_SDE', 'SamplerEulerAncestral', 'SamplerEulerAncestralCFGPP', 'SamplerEulerCFGpp', 'SamplerLCM', 'SamplerLCMUpscale', 'SamplerLMS', 'SamplerSASolver', 'SamplerSEEDS2', 'SamplingPercentToSigma', 'SaveAnimatedPNG', 'SaveAnimatedWEBP', 'SaveAudio', 'SaveAudioMP3', 'SaveAudioOpus', 'SaveGLB', 'SaveImage', 'SaveImageAdvanced', 'SaveImageDataSetToFolder', 'SaveImageTextDataSetToFolder', 'SaveImagesResponse', 'SaveLatent', 'SaveLoRA', 'SaveSVGNode', 'SaveString', 'SaveTrainingDataset', 'SaveVideo', 'SaveWEBM', 'ScaleROPE', 'SelectCLIPDevice', 'SelectModelDevice', 'SelectVAEDevice', 'SelfAttentionGuidance', 'SetClipHooks', 'SetFirstSigma', 'SetHookKeyframes', 'SetLatentNoiseMask', 'SetUnionControlNetType', 'ShuffleDataset', 'ShuffleImageTextDataset', 'SimpleMath', 'SimpleMath_2', 'SkeletonizeThin', 'SkipLayerGuidanceDiT', 'SkipLayerGuidanceDiTSimple', 'SkipLayerGuidanceSD3', 'SolidMask', 'SomethingToString', 'SoniloTextToMusic', 'SoniloVideoToMusic', 'SplatToFile3D', 'SplatToMesh', 'SplitAudioChannels', 'SplitImageToTileList', 'SplitImageWithAlpha', 'SplitSigmas', 'SplitSigmasDenoise', 'StabilityAudioInpaint', 'StabilityAudioToAudio', 'StabilityStableImageSD_3_5Node', 'StabilityStableImageUltraNode', 'StabilityTextToAudio', 'StabilityUpscaleConservativeNode', 'StabilityUpscaleCreativeNode', 'StabilityUpscaleFastNode', 'StableCascade_EmptyLatentImage', 'StableCascade_StageB_Conditioning', 'StableCascade_StageC_VAEEncode', 'StableCascade_SuperResolutionControlnet', 'StableZero123_Conditioning', 'StableZero123_Conditioning_Batched', 'StringCombo', 'StringCompare', 'StringConcatenate', 'StringContains', 'StringEnumRequestParameter', 'StringFormat', 'StringJoin', 'StringJoin1', 'StringLength', 'StringPosixPathJoin', 'StringReplace', 'StringRequestParameter', 'StringSplit', 'StringSubstring', 'StringToFloat', 'StringToInt', 'StringToUri', 'StringTrim', 'StripWhitespace', 'StyleModelApply', 'StyleModelLoader', 'T5TokenizerOptions', 'TCFG', 'TemporalScoreRescaling', 'Tencent3DPartNode', 'Tencent3DTextureEditNode', 'TencentImageToModelNode', 'TencentModelTo3DUVNode', 'TencentSmartTopologyNode', 'TencentTextToModelNode', 'TextDiffuserAddTokens', 'TextDiffuserDecodeLayoutString2ClipString', 'TextDiffuserPrepareInstructPrompt', 'TextEncodeAceStepAudio', 'TextEncodeAceStepAudio1_5', 'TextEncodeHunyuanVideo_ImageToVideo', 'TextEncodeQwenImageEdit', 'TextEncodeQwenImageEditPlus', 'TextEncodeZImageOmni', 'TextGenerate', 'TextGenerateLTX2Prompt', 'TextToLowercase', 'TextToUppercase', 'ThresholdMask', 'ToString', 'TomePatchModel', 'TopazImageEnhance', 'TopazVideoEnhance', 'TopazVideoEnhanceV2', 'TorchCompileModel', 'TrainLoraNode', 'TransformSplat', 'TransformerBeamSearchSampler', 'TransformerContrastiveSearchSampler', 'TransformerGreedySampler', 'TransformerMergeSamplers', 'TransformerTemperatureSampler', 'TransformerTopKSampler', 'TransformerTopPSampler', 'TransformersFlores200LanguageCodes', 'TransformersGenerate', 'TransformersGenerationConfig', 'TransformersImageProcessorLoader', 'TransformersLoader', 'TransformersLoader1', 'TransformersLoaderQuantized', 'TransformersM2M100LanguageCodes', 'TransformersTokenize', 'TransformersTranslationTokenize', 'TrimAudioDuration', 'TrimVideoLatent', 'TripleCLIPLoader', 'TripoConversionNode', 'TripoImageToModelNode', 'TripoMultiviewToModelNode', 'TripoP1ImageToModelNode', 'TripoP1MultiviewToModelNode', 'TripoP1TextToModelNode', 'TripoRefineNode', 'TripoRetargetNode', 'TripoRigNode', 'TripoSplatConditioning', 'TripoSplatPreprocessImage', 'TripoSplatSamplingPreview', 'TripoTextToModelNode', 'TripoTextureNode', 'TruncateText', 'UNETLoader', 'UNetCrossAttentionMultiply', 'UNetSelfAttentionMultiply', 'UNetTemporalAttentionMultiply', 'USOStyleReference', 'UnaryOperation', 'UpscaleModelLoader', 'UriFormat', 'VAEDecode', 'VAEDecodeAudio', 'VAEDecodeAudioTiled', 'VAEDecodeHunyuan3D', 'VAEDecodeTiled', 'VAEDecodeTripoSplat', 'VAEEncode', 'VAEEncodeAudio', 'VAEEncodeForInpaint', 'VAEEncodeTiled', 'VAELoader', 'VAESave', 'VOIDInpaintConditioning', 'VOIDQuadmaskPreprocess', 'VOIDSampler', 'VOIDWarpedNoise', 'VOIDWarpedNoiseSource', 'VPScheduler', 'Veo3FirstLastFrameNode', 'Veo3VideoGenerationNode', 'VeoVideoGenerationNode', 'VideoLinearCFGGuidance', 'VideoRequestParameter', 'VideoTriangleCFGGuidance', 'Video_Slice', 'Vidu2ImageToVideoNode', 'Vidu2ReferenceVideoNode', 'Vidu2StartEndToVideoNode', 'Vidu2TextToVideoNode', 'Vidu3ImageToVideoNode', 'Vidu3StartEndToVideoNode', 'Vidu3TextToVideoNode', 'ViduExtendVideoNode', 'ViduImageToVideoNode', 'ViduMultiFrameVideoNode', 'ViduReferenceVideoNode', 'ViduStartEndToVideoNode', 'ViduTextToVideoNode', 'VoxelToMesh', 'VoxelToMeshBasic', 'Wan22FunControlToVideo', 'Wan22ImageToVideoLatent', 'Wan2ImageToVideoApi', 'Wan2ReferenceVideoApi', 'Wan2TextToVideoApi', 'Wan2VideoContinuationApi', 'Wan2VideoEditApi', 'WanAnimateToVideo', 'WanCameraEmbedding', 'WanCameraImageToVideo', 'WanContextWindowsManual', 'WanDancerEncodeAudio', 'WanDancerPadKeyframes', 'WanDancerPadKeyframesList', 'WanDancerVideo', 'WanFirstLastFrameToVideo', 'WanFunControlToVideo', 'WanFunInpaintToVideo', 'WanHuMoImageToVideo', 'WanImage2VideoTokenize', 'WanImageToImageApi', 'WanImageToVideo', 'WanImageToVideoApi', 'WanInfiniteTalkToVideo', 'WanMoveConcatTrack', 'WanMoveTrackToVideo', 'WanMoveTracksFromCoords', 'WanMoveVisualizeTracks', 'WanPhantomSubjectToVideo', 'WanReferenceVideoApi', 'WanSCAILToVideo', 'WanSoundImageToVideo', 'WanSoundImageToVideoExtend', 'WanText2VideoTokenize', 'WanTextToImageApi', 'WanTextToVideoApi', 'WanTrackToVideo', 'WanVaceToVideo', 'WavespeedFlashVSRNode', 'WavespeedImageUpscaleNode', 'WebcamCapture', 'ZImageFunControlnet', 'unCLIPCheckpointLoader', 'unCLIPConditioning', 'wanBlockSwap']
