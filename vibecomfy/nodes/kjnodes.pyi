# vibecomfy:generated
# pack: kjnodes
# source: object_info cache ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
# source_sha256: 668ee21e23665b329f92206d138a3e4d37d4e35549851361a9efa0a0b55b31ae
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 230

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def AddLabel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    direction: Literal['up', 'down', 'left', 'right', 'overlay'] | _Omitted = ...,
    font: Any | _Omitted = ...,
    font_color: str | _Omitted = ...,
    font_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    label_color: str | _Omitted = ...,
    text: str | _Omitted = ...,
    text_x: int | _Omitted = ...,
    text_y: int | _Omitted = ...,
    caption: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AddNoiseToTrackPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    noise_temporal_ratio: float | _Omitted = ...,
    noise_x_ratio: float | _Omitted = ...,
    noise_y_ratio: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    tracks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AppendInstanceDiffusionTracking(
    *args: VibeWorkflow,
    _id: str | None = ...,
    tracking_1: Any | _Omitted = ...,
    tracking_2: Any | _Omitted = ...,
    prompt_1: str | _Omitted = ...,
    prompt_2: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AppendStringsToList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    string1: str | _Omitted = ...,
    string2: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ApplyRifleXRoPE_HunuyanVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    k: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ApplyRifleXRoPE_WanVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    k: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioConcatenate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio1: Any | _Omitted = ...,
    audio2: Any | _Omitted = ...,
    direction: Literal['right', 'left'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BOOLConstant(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchCLIPSeg(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    binary_mask: bool | _Omitted = ...,
    combine_mask: bool | _Omitted = ...,
    text: str | _Omitted = ...,
    threshold: float | _Omitted = ...,
    use_cuda: bool | _Omitted = ...,
    blur_sigma: float | _Omitted = ...,
    image_bg_level: float | _Omitted = ...,
    invert: bool | _Omitted = ...,
    opt_model: Any | _Omitted = ...,
    prev_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchCropFromMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    bbox_smooth_alpha: float | _Omitted = ...,
    crop_size_mult: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchCropFromMaskAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    bbox_smooth_alpha: float | _Omitted = ...,
    crop_size_mult: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchUncrop(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cropped_images: Any | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    border_blending: float | _Omitted = ...,
    border_bottom: bool | _Omitted = ...,
    border_left: bool | _Omitted = ...,
    border_right: bool | _Omitted = ...,
    border_top: bool | _Omitted = ...,
    crop_rescale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BatchUncropAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    combined_crop_mask: Any | _Omitted = ...,
    cropped_images: Any | _Omitted = ...,
    cropped_masks: Any | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    border_blending: float | _Omitted = ...,
    crop_rescale: float | _Omitted = ...,
    use_combined_mask: bool | _Omitted = ...,
    use_square_mask: bool | _Omitted = ...,
    combined_bounding_box: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BboxToInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bboxes: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BboxVisualize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    bbox_format: Literal['xywh', 'xyxy'] | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    line_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BlockifyMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    block_size: int | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGZeroStarAndInit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    use_zero_init: bool | _Omitted = ...,
    zero_init_steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CameraPoseVisualizer(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base_xval: float | _Omitted = ...,
    pose_file_path: str | _Omitted = ...,
    relative_c2w: bool | _Omitted = ...,
    scale: float | _Omitted = ...,
    use_exact_fx: bool | _Omitted = ...,
    use_viewer: bool | _Omitted = ...,
    zval: float | _Omitted = ...,
    cameractrl_poses: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CheckpointLoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    compute_dtype: Literal['default', 'fp16', 'bf16', 'fp32'] | _Omitted = ...,
    enable_fp16_accumulation: bool | _Omitted = ...,
    patch_cublaslinear: bool | _Omitted = ...,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = ...,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp16', 'bf16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CheckpointPerturbWeights(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    final_layer: float | _Omitted = ...,
    joint_blocks: float | _Omitted = ...,
    rest_of_the_blocks: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ColorMatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_ref: Any | _Omitted = ...,
    image_target: Any | _Omitted = ...,
    method: Literal['mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = ...,
    multithread: bool | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ColorMatchV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_ref: Any | _Omitted = ...,
    image_target: Any | _Omitted = ...,
    method: Any | _Omitted = ...,
    multithread: bool | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ColorToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    blue: int | _Omitted = ...,
    green: int | _Omitted = ...,
    invert: bool | _Omitted = ...,
    per_batch: int | _Omitted = ...,
    red: int | _Omitted = ...,
    threshold: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CondPassThrough(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningMultiCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning_1: Any | _Omitted = ...,
    conditioning_2: Any | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    operation: Literal['combine', 'concat'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetMaskAndCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_1: Any | _Omitted = ...,
    mask_2: Any | _Omitted = ...,
    negative_1: Any | _Omitted = ...,
    negative_2: Any | _Omitted = ...,
    positive_1: Any | _Omitted = ...,
    positive_2: Any | _Omitted = ...,
    mask_1_strength: float | _Omitted = ...,
    mask_2_strength: float | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetMaskAndCombine3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_1: Any | _Omitted = ...,
    mask_2: Any | _Omitted = ...,
    mask_3: Any | _Omitted = ...,
    negative_1: Any | _Omitted = ...,
    negative_2: Any | _Omitted = ...,
    negative_3: Any | _Omitted = ...,
    positive_1: Any | _Omitted = ...,
    positive_2: Any | _Omitted = ...,
    positive_3: Any | _Omitted = ...,
    mask_1_strength: float | _Omitted = ...,
    mask_2_strength: float | _Omitted = ...,
    mask_3_strength: float | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetMaskAndCombine4(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_1: Any | _Omitted = ...,
    mask_2: Any | _Omitted = ...,
    mask_3: Any | _Omitted = ...,
    mask_4: Any | _Omitted = ...,
    negative_1: Any | _Omitted = ...,
    negative_2: Any | _Omitted = ...,
    negative_3: Any | _Omitted = ...,
    negative_4: Any | _Omitted = ...,
    positive_1: Any | _Omitted = ...,
    positive_2: Any | _Omitted = ...,
    positive_3: Any | _Omitted = ...,
    positive_4: Any | _Omitted = ...,
    mask_1_strength: float | _Omitted = ...,
    mask_2_strength: float | _Omitted = ...,
    mask_3_strength: float | _Omitted = ...,
    mask_4_strength: float | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningSetMaskAndCombine5(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_1: Any | _Omitted = ...,
    mask_2: Any | _Omitted = ...,
    mask_3: Any | _Omitted = ...,
    mask_4: Any | _Omitted = ...,
    mask_5: Any | _Omitted = ...,
    negative_1: Any | _Omitted = ...,
    negative_2: Any | _Omitted = ...,
    negative_3: Any | _Omitted = ...,
    negative_4: Any | _Omitted = ...,
    negative_5: Any | _Omitted = ...,
    positive_1: Any | _Omitted = ...,
    positive_2: Any | _Omitted = ...,
    positive_3: Any | _Omitted = ...,
    positive_4: Any | _Omitted = ...,
    positive_5: Any | _Omitted = ...,
    mask_1_strength: float | _Omitted = ...,
    mask_2_strength: float | _Omitted = ...,
    mask_3_strength: float | _Omitted = ...,
    mask_4_strength: float | _Omitted = ...,
    mask_5_strength: float | _Omitted = ...,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConsolidateMasksKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    padding: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateAudioMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_path: str | _Omitted = ...,
    frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    invert: bool | _Omitted = ...,
    scale: float | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateFadeMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_level: float | _Omitted = ...,
    frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = ...,
    invert: bool | _Omitted = ...,
    midpoint_frame: int | _Omitted = ...,
    midpoint_level: float | _Omitted = ...,
    start_level: float | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateFadeMaskAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'none', 'default_to_black'] | _Omitted = ...,
    invert: bool | _Omitted = ...,
    points_string: str | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateFluidMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    inflow_count: int | _Omitted = ...,
    inflow_duration: int | _Omitted = ...,
    inflow_padding: int | _Omitted = ...,
    inflow_radius: int | _Omitted = ...,
    inflow_velocity: int | _Omitted = ...,
    invert: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateGradientFromCoords(
    *args: VibeWorkflow,
    _id: str | None = ...,
    coordinates: str | _Omitted = ...,
    end_color: str | _Omitted = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    start_color: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateGradientMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    invert: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateInstanceDiffusionTracking(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bbox_height: int | _Omitted = ...,
    bbox_width: int | _Omitted = ...,
    class_id: int | _Omitted = ...,
    class_name: str | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    height: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    width: int | _Omitted = ...,
    fit_in_frame: bool | _Omitted = ...,
    size_multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateMagicMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    depth: int | _Omitted = ...,
    distortion: float | _Omitted = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    frames: int | _Omitted = ...,
    seed: int | _Omitted = ...,
    transitions: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateShapeImageOnPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bg_color: str | _Omitted = ...,
    blur_radius: float | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    intensity: float | _Omitted = ...,
    shape: Literal['circle', 'square', 'triangle'] | _Omitted = ...,
    shape_color: str | _Omitted = ...,
    shape_height: int | _Omitted = ...,
    shape_width: int | _Omitted = ...,
    border_color: str | _Omitted = ...,
    border_width: int | _Omitted = ...,
    size_multiplier: float | _Omitted = ...,
    trailing: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateShapeMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    frames: int | _Omitted = ...,
    grow: int | _Omitted = ...,
    location_x: int | _Omitted = ...,
    location_y: int | _Omitted = ...,
    shape: Literal['circle', 'square', 'triangle'] | _Omitted = ...,
    shape_height: int | _Omitted = ...,
    shape_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateShapeMaskOnPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    coordinates: str | _Omitted = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    shape: Literal['circle', 'square', 'triangle'] | _Omitted = ...,
    shape_height: int | _Omitted = ...,
    shape_width: int | _Omitted = ...,
    size_multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateTextMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_rotation: int | _Omitted = ...,
    font: Any | _Omitted = ...,
    font_color: str | _Omitted = ...,
    font_size: int | _Omitted = ...,
    frames: int | _Omitted = ...,
    height: int | _Omitted = ...,
    invert: bool | _Omitted = ...,
    start_rotation: int | _Omitted = ...,
    text: str | _Omitted = ...,
    text_x: int | _Omitted = ...,
    text_y: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateTextOnPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    alignment: Literal['left', 'center', 'right'] | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    font: Any | _Omitted = ...,
    font_size: int | _Omitted = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    text: str | _Omitted = ...,
    text_color: str | _Omitted = ...,
    size_multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateVoronoiMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    frames: int | _Omitted = ...,
    line_width: int | _Omitted = ...,
    num_points: int | _Omitted = ...,
    speed: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CrossFadeImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images_1: Any | _Omitted = ...,
    images_2: Any | _Omitted = ...,
    end_level: float | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = ...,
    start_level: float | _Omitted = ...,
    transition_start_index: int | _Omitted = ...,
    transitioning_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CrossFadeImagesMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_1: Any | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = ...,
    transitioning_frames: int | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CustomControlNetWeightsFluxFromList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    list_of_floats: float | _Omitted = ...,
    autosize: Any | _Omitted = ...,
    cn_extras: Any | _Omitted = ...,
    uncond_multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CustomSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    interpolate_to_steps: int | _Omitted = ...,
    sigmas_string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CutAndDragOnPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    frame_height: int | _Omitted = ...,
    frame_width: int | _Omitted = ...,
    inpaint: bool | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DecodeAndSaveVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_latent: Any | _Omitted = ...,
    video_vae: Any | _Omitted = ...,
    codec: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    format: Any | _Omitted = ...,
    fps: float | _Omitted = ...,
    tiling: Any | _Omitted = ...,
    audio_latent: Any | _Omitted = ...,
    audio_vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DiTBlockLoraLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    blocks: Any | _Omitted = ...,
    lora_name: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    opt_lora_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DifferentialDiffusionAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DiffusionModelLoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    compute_dtype: Literal['default', 'fp16', 'bf16', 'fp32'] | _Omitted = ...,
    enable_fp16_accumulation: bool | _Omitted = ...,
    model_name: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    patch_cublaslinear: bool | _Omitted = ...,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = ...,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp16', 'bf16', 'fp32'] | _Omitted = ...,
    extra_state_dict: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DiffusionModelSelector(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DownloadAndLoadCLIPSeg(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['Kijai/clipseg-rd64-refined-fp16', 'CIDAS/clipseg-rd64-refined'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawInstanceDiffusionTracking(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    box_line_width: int | _Omitted = ...,
    draw_text: bool | _Omitted = ...,
    font: Any | _Omitted = ...,
    font_size: int | _Omitted = ...,
    tracking: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawMaskOnImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    color: str | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DummyOut(
    *args: VibeWorkflow,
    _id: str | None = ...,
    any_input: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLatentImageCustomPresets(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    dimensions: Any | _Omitted = ...,
    invert: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLatentImagePresets(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    dimensions: Literal['512 x 512 (1:1)', '768 x 512 (1.5:1)', '960 x 512 (1.875:1)', '1024 x 512 (2:1)', '1024 x 576 (1.778:1)', '1536 x 640 (2.4:1)', '1344 x 768 (1.75:1)', '1216 x 832 (1.46:1)', '1152 x 896 (1.286:1)', '1024 x 1024 (1:1)'] | _Omitted = ...,
    invert: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EncodeVideoComponents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    video: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    keep_proportion: Any | _Omitted = ...,
    max_frames: int | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EndRecordCUDAMemoryHistory(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: Any | _Omitted = ...,
    output_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FastPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    format: Literal['JPEG', 'PNG'] | _Omitted = ...,
    max_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FilterZeroMasksAndCorrespondingImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FlipSigmasAdjusted(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    divide_by: float | _Omitted = ...,
    divide_by_last_sigma: bool | _Omitted = ...,
    offset_by: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatConstant(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    height: int | _Omitted = ...,
    input_values: float | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FloatToSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    float_list: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FluxBlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
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
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GGUFLoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    attention_override: Any | _Omitted = ...,
    dequant_dtype: Any | _Omitted = ...,
    enable_fp16_accumulation: bool | _Omitted = ...,
    extra_model_name: Any | _Omitted = ...,
    model_name: Any | _Omitted = ...,
    patch_dtype: Any | _Omitted = ...,
    patch_on_device: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GLIGENTextBoxApplyBatchCoords(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    conditioning_to: Any | _Omitted = ...,
    gligen_textbox_model: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    height: int | _Omitted = ...,
    text: str | _Omitted = ...,
    width: int | _Omitted = ...,
    size_multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GenerateNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    constant_batch_noise: bool | _Omitted = ...,
    height: int | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    normalize: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    width: int | _Omitted = ...,
    latent_channels: Literal['4', '16'] | _Omitted = ...,
    model: Any | _Omitted = ...,
    shape: Literal['BCHW', 'BCTHW', 'BTCHW'] | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImageSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImagesFromBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    indexes: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetLatentRangeFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    start_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetLatentSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetLatentsFromBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    indexes: str | _Omitted = ...,
    latent_format: Literal['BCHW', 'BTCHW', 'BCTHW'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetMaskSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetTrackRange(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    start_index: int | _Omitted = ...,
    tracks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GradientToFloat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrowMaskWithBlur(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    blur_radius: float | _Omitted = ...,
    decay_factor: float | _Omitted = ...,
    expand: int | _Omitted = ...,
    flip_input: bool | _Omitted = ...,
    incremental_expandrate: float | _Omitted = ...,
    lerp_alpha: float | _Omitted = ...,
    tapered_corners: bool | _Omitted = ...,
    fill_holes: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HDRPreviewKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    exposure: float | _Omitted = ...,
    saturation: float | _Omitted = ...,
    fps: float | _Omitted = ...,
    input_space: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanVideoBlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
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
    double_blocks_19: float | _Omitted = ...,
    double_blocks_2: float | _Omitted = ...,
    double_blocks_3: float | _Omitted = ...,
    double_blocks_4: float | _Omitted = ...,
    double_blocks_5: float | _Omitted = ...,
    double_blocks_6: float | _Omitted = ...,
    double_blocks_7: float | _Omitted = ...,
    double_blocks_8: float | _Omitted = ...,
    double_blocks_9: float | _Omitted = ...,
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
    single_blocks_38: float | _Omitted = ...,
    single_blocks_39: float | _Omitted = ...,
    single_blocks_4: float | _Omitted = ...,
    single_blocks_5: float | _Omitted = ...,
    single_blocks_6: float | _Omitted = ...,
    single_blocks_7: float | _Omitted = ...,
    single_blocks_8: float | _Omitted = ...,
    single_blocks_9: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HunyuanVideoEncodeKeyframesToCond(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_frame: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    start_frame: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    overlap: int | _Omitted = ...,
    temporal_overlap: int | _Omitted = ...,
    temporal_size: int | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    negative: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def INTConstant(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageAddMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_1: Any | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    blend_amount: float | _Omitted = ...,
    blending: Literal['add', 'subtract', 'multiply', 'difference'] | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageAndMaskPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_color: str | _Omitted = ...,
    mask_opacity: float | _Omitted = ...,
    pass_through: bool | _Omitted = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchExtendWithOverlap(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source_images: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    overlap_mode: Literal['cut', 'linear_blend', 'ease_in_out', 'filmic_crossfade', 'perceptual_crossfade'] | _Omitted = ...,
    overlap_side: Literal['source', 'new_images'] | _Omitted = ...,
    new_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchFilter(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    empty_color: str | _Omitted = ...,
    empty_threshold: float | _Omitted = ...,
    replacement_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchJoinWithTransition(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images_1: Any | _Omitted = ...,
    images_2: Any | _Omitted = ...,
    blur_radius: float | _Omitted = ...,
    device: Literal['CPU', 'GPU'] | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = ...,
    reverse: bool | _Omitted = ...,
    start_index: int | _Omitted = ...,
    transition_type: Literal['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade'] | _Omitted = ...,
    transitioning_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_1: Any | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchRepeatInterleaving(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    repeats: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchTestPattern(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    font: Any | _Omitted = ...,
    font_size: int | _Omitted = ...,
    height: int | _Omitted = ...,
    start_from: int | _Omitted = ...,
    text_x: int | _Omitted = ...,
    text_y: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageConcanate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    direction: Literal['right', 'down', 'left', 'up'] | _Omitted = ...,
    match_image_size: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageConcatFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    match_image_size: bool | _Omitted = ...,
    max_resolution: int | _Omitted = ...,
    num_columns: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageConcatMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_1: Any | _Omitted = ...,
    direction: Literal['right', 'down', 'left', 'up'] | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    match_image_size: bool | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCropByMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCropByMaskAndResize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    base_resolution: int | _Omitted = ...,
    max_crop_resolution: int | _Omitted = ...,
    min_crop_resolution: int | _Omitted = ...,
    padding: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageCropByMaskBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    bg_color: str | _Omitted = ...,
    height: int | _Omitted = ...,
    padding: int | _Omitted = ...,
    preserve_size: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGrabPIL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    delay: float | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGridComposite2x2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    image3: Any | _Omitted = ...,
    image4: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGridComposite3x3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    image3: Any | _Omitted = ...,
    image4: Any | _Omitted = ...,
    image5: Any | _Omitted = ...,
    image6: Any | _Omitted = ...,
    image7: Any | _Omitted = ...,
    image8: Any | _Omitted = ...,
    image9: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageGridtoBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    columns: int | _Omitted = ...,
    rows: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageNoiseAugmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    noise_aug_strength: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageNormalize_Neg1_To_1(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePadForOutpaintMasked(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bottom: int | _Omitted = ...,
    feathering: int | _Omitted = ...,
    left: int | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePadForOutpaintTargetSize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    feathering: int | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePadKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bottom: int | _Omitted = ...,
    color: str | _Omitted = ...,
    extra_padding: int | _Omitted = ...,
    left: int | _Omitted = ...,
    pad_mode: Literal['edge', 'edge_pixel', 'color', 'pillarbox_blur'] | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePass(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePrepForICLora(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_image: Any | _Omitted = ...,
    border_width: int | _Omitted = ...,
    output_height: int | _Omitted = ...,
    output_width: int | _Omitted = ...,
    latent_image: Any | _Omitted = ...,
    latent_mask: Any | _Omitted = ...,
    reference_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageResizeKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    divisible_by: int | _Omitted = ...,
    height: int | _Omitted = ...,
    keep_proportion: bool | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    width: int | _Omitted = ...,
    crop: Literal['disabled', 'center', '0'] | _Omitted = ...,
    get_image_size: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageResizeKJv2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    crop_position: Literal['center', 'top', 'bottom', 'left', 'right'] | _Omitted = ...,
    divisible_by: int | _Omitted = ...,
    height: int | _Omitted = ...,
    keep_proportion: Literal['stretch', 'resize', 'pad', 'pad_edge', 'pad_edge_pixel', 'crop', 'pillarbox_blur', 'total_pixels'] | _Omitted = ...,
    pad_color: str | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'nvidia_rtx_vsr'] | _Omitted = ...,
    width: int | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageSharpenKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageTensorList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageTransformByNormalizedAmplitude(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    cumulative: bool | _Omitted = ...,
    normalized_amp: Any | _Omitted = ...,
    x_offset: int | _Omitted = ...,
    y_offset: int | _Omitted = ...,
    zoom_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageTransformKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bboxes: str | _Omitted = ...,
    divisible_by: int | _Omitted = ...,
    extra_padding: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    invert_crop: Any | _Omitted = ...,
    keep_proportion: Any | _Omitted = ...,
    target_height: int | _Omitted = ...,
    target_width: int | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageUncropByMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    bbox: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageUpscaleWithModelBatched(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    upscale_model: Any | _Omitted = ...,
    per_batch: int | _Omitted = ...,
    downscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    downscale_ratio: float | _Omitted = ...,
    precision: Literal['float32', 'float16', 'bfloat16'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InjectNoiseToLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    noise: Any | _Omitted = ...,
    average: bool | _Omitted = ...,
    normalize: bool | _Omitted = ...,
    strength: float | _Omitted = ...,
    mask: Any | _Omitted = ...,
    mix_randn_amount: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InsertImageBatchByIndexes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    images_to_insert: Any | _Omitted = ...,
    insert_indexes: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InsertImagesToBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images_to_insert: Any | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    indexes: str | _Omitted = ...,
    mode: Literal['replace', 'insert'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InsertLatentToIndexed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    destination: Any | _Omitted = ...,
    source: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InterpolateCoords(
    *args: VibeWorkflow,
    _id: str | None = ...,
    coordinates: str | _Omitted = ...,
    interpolation_curve: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Intrinsic_lora_sampling(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    per_batch: int | _Omitted = ...,
    task: Literal['depth map', 'surface normals', 'albedo', 'shading'] | _Omitted = ...,
    text: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    optional_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def JoinStringMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    delimiter: str | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    return_list: bool | _Omitted = ...,
    string_1: str | _Omitted = ...,
    string_2: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def JoinStrings(
    *args: VibeWorkflow,
    _id: str | None = ...,
    delimiter: str | _Omitted = ...,
    string1: str | _Omitted = ...,
    string2: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2AttentionTunerPatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    audio_to_video_scale: float | _Omitted = ...,
    blocks: str | _Omitted = ...,
    triton_kernels: bool | _Omitted = ...,
    video_scale: float | _Omitted = ...,
    video_to_audio_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2AudioLatentNormalizingSampling(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    audio_normalization_factors: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2BlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
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
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2LoraLoaderAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    audio: float | _Omitted = ...,
    audio_to_video: float | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    other: float | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    video: float | _Omitted = ...,
    video_to_audio: float | _Omitted = ...,
    blocks: Any | _Omitted = ...,
    opt_lora_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2MemoryEfficientSageAttentionPatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    triton_kernels: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2SamplingPreviewOverride(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    preview_rate: int | _Omitted = ...,
    latent_upscale_model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2_NAG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    nag_alpha: float | _Omitted = ...,
    nag_scale: float | _Omitted = ...,
    nag_tau: float | _Omitted = ...,
    inplace: bool | _Omitted = ...,
    nag_cond_audio: Any | _Omitted = ...,
    nag_cond_video: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVideoMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_end_time: float | _Omitted = ...,
    audio_start_time: float | _Omitted = ...,
    max_length: Any | _Omitted = ...,
    video_end_time: float | _Omitted = ...,
    video_fps: float | _Omitted = ...,
    video_start_time: float | _Omitted = ...,
    audio_latent: Any | _Omitted = ...,
    existing_mask_mode: Any | _Omitted = ...,
    video_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVChunkFeedForward(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    chunks: int | _Omitted = ...,
    dim_threshold: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVEnhanceAVideoKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    weight: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoInplaceKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    num_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentInpaintTTM(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LazySwitchKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    on_false: Any | _Omitted = ...,
    on_true: Any | _Omitted = ...,
    switch: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LeapfusionHunyuanI2VPatcher(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    index: int | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadAndResizeImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    background_color: str | _Omitted = ...,
    divisible_by: int | _Omitted = ...,
    height: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    keep_proportion: bool | _Omitted = ...,
    mask_channel: Literal['alpha', 'red', 'green', 'blue'] | _Omitted = ...,
    repeat: int | _Omitted = ...,
    resize: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImagesFromFolderKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    folder: str | _Omitted = ...,
    height: int | _Omitted = ...,
    keep_aspect_ratio: Literal['crop', 'pad', 'stretch'] | _Omitted = ...,
    width: int | _Omitted = ...,
    image_load_cap: int | _Omitted = ...,
    include_subfolders: bool | _Omitted = ...,
    start_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadResAdapterNormalization(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    resadapter_path: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVideosFromFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    add_label: bool | _Omitted = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    force_rate: float | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    grid_max_columns: int | _Omitted = ...,
    output_type: Literal['batch', 'grid'] | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_frames: int | _Omitted = ...,
    video: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraExtractKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    adaptive_param: float | _Omitted = ...,
    algorithm: Any | _Omitted = ...,
    bias_diff: bool | _Omitted = ...,
    clamp_quantile: bool | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    finetuned: Any | _Omitted = ...,
    lora_type: Any | _Omitted = ...,
    lowrank_iters: int | _Omitted = ...,
    original: Any | _Omitted = ...,
    output_dtype: Any | _Omitted = ...,
    rank: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraReduceRankKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    dynamic_method: Any | _Omitted = ...,
    dynamic_param: float | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    new_rank: int | _Omitted = ...,
    output_dtype: Any | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskBatchMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_1: Any | _Omitted = ...,
    mask_2: Any | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskOrImageToWeight(
    *args: VibeWorkflow,
    _id: str | None = ...,
    output_type: Literal['list', 'pandas series', 'tensor', 'string'] | _Omitted = ...,
    images: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MergeImageChannels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blue: Any | _Omitted = ...,
    green: Any | _Omitted = ...,
    red: Any | _Omitted = ...,
    alpha: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMemoryUsageFactorOverride(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    memory_usage_factor: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelMemoryUseReportPatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelPassThrough(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelPatchTorchSettings(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    enable_fp16_accumulation: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSaveKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    model_key_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NABLA_AttentionKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    sparsity: float | _Omitted = ...,
    torch_compile: bool | _Omitted = ...,
    window_height: int | _Omitted = ...,
    window_time: int | _Omitted = ...,
    window_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NormalizedAmplitudeToFloatList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    normalized_amp: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NormalizedAmplitudeToMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    color: Literal['white', 'amplitude'] | _Omitted = ...,
    frame_offset: int | _Omitted = ...,
    height: int | _Omitted = ...,
    location_x: int | _Omitted = ...,
    location_y: int | _Omitted = ...,
    normalized_amp: Any | _Omitted = ...,
    shape: Literal['none', 'circle', 'square', 'triangle'] | _Omitted = ...,
    size: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OffsetMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    angle: int | _Omitted = ...,
    duplication_factor: int | _Omitted = ...,
    incremental: bool | _Omitted = ...,
    padding_mode: Literal['empty', 'border', 'reflection'] | _Omitted = ...,
    roll: bool | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OffsetMaskByNormalizedAmplitude(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    angle_multiplier: float | _Omitted = ...,
    normalized_amp: Any | _Omitted = ...,
    rotate: bool | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PadImageBatchInterleaved(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    add_after_last: bool | _Omitted = ...,
    empty_frames_per_image: int | _Omitted = ...,
    pad_frame_value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PatchModelPatcherOrder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    full_load: Literal['enabled', 'disabled', 'auto'] | _Omitted = ...,
    patch_order: Literal['object_patch_first', 'weight_patch_first'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PathchSageAttentionKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = ...,
    allow_compile: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PlaySoundKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_path: str | _Omitted = ...,
    duration: float | _Omitted = ...,
    mode: Any | _Omitted = ...,
    volume: float | _Omitted = ...,
    any_input: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PlotCoordinates(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bbox_height: int | _Omitted = ...,
    bbox_width: int | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    height: int | _Omitted = ...,
    text: str | _Omitted = ...,
    width: int | _Omitted = ...,
    size_multiplier: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PointsEditor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bbox_format: Literal['xyxy', 'xywh'] | _Omitted = ...,
    bbox_store: str | _Omitted = ...,
    bboxes: str | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    height: int | _Omitted = ...,
    neg_coordinates: str | _Omitted = ...,
    normalize: bool | _Omitted = ...,
    points_store: str | _Omitted = ...,
    width: int | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewAnimation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    fps: float | _Omitted = ...,
    images: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewImageOrMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewLatentNoiseMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RemapImageRange(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    clamp: bool | _Omitted = ...,
    max: float | _Omitted = ...,
    min: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RemapMaskRange(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    max: float | _Omitted = ...,
    min: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReplaceImagesInBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_index: int | _Omitted = ...,
    original_images: Any | _Omitted = ...,
    original_masks: Any | _Omitted = ...,
    replacement_images: Any | _Omitted = ...,
    replacement_masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    height: int | _Omitted = ...,
    keep_proportions: bool | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReverseImageBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RoundMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SV3D_BatchSchedule(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    init_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    azimuth_points_string: str | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    elevation_points_string: str | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerSelfRefineVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    certain_percentage: float | _Omitted = ...,
    input_mode: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    uncertainty_threshold: float | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImageKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    output_folder: str | _Omitted = ...,
    caption: str | _Omitted = ...,
    caption_file_extension: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImageWithAlpha(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveStringKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename_prefix: str | _Omitted = ...,
    output_folder: str | _Omitted = ...,
    string: str | _Omitted = ...,
    file_extension: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ScaleBatchPromptSchedule(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input_str: str | _Omitted = ...,
    new_frame_count: int | _Omitted = ...,
    old_frame_count: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ScheduledCFGGuidance(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ScreencapStream(
    *args: VibeWorkflow,
    _id: str | None = ...,
    crop_height: int | _Omitted = ...,
    crop_width: int | _Omitted = ...,
    frame_data: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Screencap_mss(
    *args: VibeWorkflow,
    _id: str | None = ...,
    delay: float | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SeparateMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    max_poly_points: int | _Omitted = ...,
    mode: Literal['convex_polygons', 'area', 'box'] | _Omitted = ...,
    size_threshold_height: int | _Omitted = ...,
    size_threshold_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetShakkerLabsUnionControlNetType(
    *args: VibeWorkflow,
    _id: str | None = ...,
    control_net: Any | _Omitted = ...,
    type: Literal['auto', 'canny', 'tile', 'depth', 'blur', 'pose', 'gray', 'low quality'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ShuffleImageBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SigmasToFloat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SimpleCalculatorKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    expression: str | _Omitted = ...,
    variables: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SkipLayerGuidanceWanVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    blocks: str | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sleep(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: Any | _Omitted = ...,
    minutes: int | _Omitted = ...,
    seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SoundReactive(
    *args: VibeWorkflow,
    _id: str | None = ...,
    end_range_hz: int | _Omitted = ...,
    multiplier: float | _Omitted = ...,
    normalize: bool | _Omitted = ...,
    smoothing_factor: float | _Omitted = ...,
    sound_level: float | _Omitted = ...,
    start_range_hz: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplineEditor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    coordinates: str | _Omitted = ...,
    float_output_type: Literal['list', 'pandas series', 'tensor'] | _Omitted = ...,
    interpolation: Literal['cardinal', 'monotone', 'basis', 'linear', 'step-before', 'step-after', 'polar', 'polar-reverse', 'bezier'] | _Omitted = ...,
    mask_height: int | _Omitted = ...,
    mask_width: int | _Omitted = ...,
    points_store: str | _Omitted = ...,
    points_to_sample: int | _Omitted = ...,
    repeat_output: int | _Omitted = ...,
    sampling_method: Literal['path', 'time', 'controlpoints', 'speed'] | _Omitted = ...,
    tension: float | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    max_value: float | _Omitted = ...,
    min_value: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitBboxes(
    *args: VibeWorkflow,
    _id: str | None = ...,
    bboxes: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplitImageChannels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StableZero123_BatchSchedule(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    init_image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    azimuth_points_string: str | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    elevation_points_string: str | _Omitted = ...,
    height: int | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StartRecordCUDAMemoryHistory(
    *args: VibeWorkflow,
    _id: str | None = ...,
    context: Literal['all', 'state', 'alloc', 'None'] | _Omitted = ...,
    enabled: Literal['all', 'state', 'None'] | _Omitted = ...,
    input: Any | _Omitted = ...,
    max_entries: int | _Omitted = ...,
    stacks: Literal['python', 'all'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringConstant(
    *args: VibeWorkflow,
    _id: str | None = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringConstantMultiline(
    *args: VibeWorkflow,
    _id: str | None = ...,
    string: str | _Omitted = ...,
    strip_newlines: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringToFloatList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    string: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StyleModelApplyAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision_output: Any | _Omitted = ...,
    conditioning: Any | _Omitted = ...,
    style_model: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Superprompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    instruction_prompt: str | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    prompt: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TimerNodeKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    any_input: Any | _Omitted = ...,
    mode: Literal['start', 'stop'] | _Omitted = ...,
    name: str | _Omitted = ...,
    timer: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileControlNet(
    *args: VibeWorkflow,
    _id: str | None = ...,
    controlnet: Any | _Omitted = ...,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileCosmosModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileLTXModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = ...,
    compile_transformer_blocks_only: bool | _Omitted = ...,
    debug_compile_keys: bool | _Omitted = ...,
    dynamic: Literal['auto', 'true', 'false'] | _Omitted = ...,
    dynamo_cache_size_limit: int | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = ...,
    disable_dynamic_vram: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelFluxAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelFluxAdvancedV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = ...,
    double_blocks: bool | _Omitted = ...,
    dynamic: bool | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = ...,
    single_blocks: bool | _Omitted = ...,
    dynamo_cache_size_limit: int | _Omitted = ...,
    force_parameter_static_shapes: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelHyVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelQwenImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelWanVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileModelWanVideoV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = ...,
    compile_transformer_blocks_only: bool | _Omitted = ...,
    dynamic: bool | _Omitted = ...,
    dynamo_cache_size_limit: int | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = ...,
    force_parameter_static_shapes: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TorchCompileVAE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = ...,
    compile_decoder: bool | _Omitted = ...,
    compile_encoder: bool | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransitionImagesInBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    blur_radius: float | _Omitted = ...,
    device: Literal['CPU', 'GPU'] | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = ...,
    reverse: bool | _Omitted = ...,
    transition_type: Literal['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade'] | _Omitted = ...,
    transitioning_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TransitionImagesMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_1: Any | _Omitted = ...,
    blur_radius: float | _Omitted = ...,
    device: Literal['CPU', 'GPU'] | _Omitted = ...,
    inputcount: int | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = ...,
    reverse: bool | _Omitted = ...,
    transition_type: Literal['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade'] | _Omitted = ...,
    transitioning_frames: int | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeLoopKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    overlap_latent_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAELoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    device: Literal['main_device', 'cpu'] | _Omitted = ...,
    vae_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors', 'pixel_space'] | _Omitted = ...,
    weight_dtype: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VRAM_Debug(
    *args: VibeWorkflow,
    _id: str | None = ...,
    empty_cache: bool | _Omitted = ...,
    gc_collect: bool | _Omitted = ...,
    unload_all_models: bool | _Omitted = ...,
    any_input: Any | _Omitted = ...,
    image_pass: Any | _Omitted = ...,
    model_pass: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VisualizeCUDAMemoryHistory(
    *args: VibeWorkflow,
    _id: str | None = ...,
    snapshot_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VisualizeSigmasKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: Any | _Omitted = ...,
    end_step: int | _Omitted = ...,
    start_step: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wan21BlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
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
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanChunkFeedForward(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    chunks: int | _Omitted = ...,
    dim_threshold: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanImageToVideoSVIPro(
    *args: VibeWorkflow,
    _id: str | None = ...,
    anchor_samples: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    length: int | _Omitted = ...,
    motion_latent_count: int | _Omitted = ...,
    prev_samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEnhanceAVideoKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    weight: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoNAG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    nag_alpha: float | _Omitted = ...,
    nag_scale: float | _Omitted = ...,
    nag_tau: float | _Omitted = ...,
    input_type: Literal['default', 'batch'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTeaCacheKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    coefficients: Literal['disabled', '1.3B', '14B', 'i2v_480', 'i2v_720'] | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    rel_l1_thresh: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WebcamCaptureCV2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    cam_index: int | _Omitted = ...,
    height: int | _Omitted = ...,
    release: bool | _Omitted = ...,
    width: int | _Omitted = ...,
    x: int | _Omitted = ...,
    y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WeightScheduleConvert(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input_values: float | _Omitted = ...,
    invert: bool | _Omitted = ...,
    output_type: Literal['match_input', 'list', 'pandas series', 'tensor'] | _Omitted = ...,
    repeat: int | _Omitted = ...,
    interpolation_curve: float | _Omitted = ...,
    remap_max: float | _Omitted = ...,
    remap_min: float | _Omitted = ...,
    remap_to_frames: int | _Omitted = ...,
    remap_values: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WeightScheduleExtend(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input_values_1: float | _Omitted = ...,
    input_values_2: float | _Omitted = ...,
    output_type: Literal['match_input', 'list', 'pandas series', 'tensor'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WidgetToString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    id: int | _Omitted = ...,
    return_all: bool | _Omitted = ...,
    widget_name: str | _Omitted = ...,
    allowed_float_decimals: int | _Omitted = ...,
    any_input: Any | _Omitted = ...,
    node_title: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['AddLabel', 'AddNoiseToTrackPath', 'AppendInstanceDiffusionTracking', 'AppendStringsToList', 'ApplyRifleXRoPE_HunuyanVideo', 'ApplyRifleXRoPE_WanVideo', 'AudioConcatenate', 'BOOLConstant', 'BatchCLIPSeg', 'BatchCropFromMask', 'BatchCropFromMaskAdvanced', 'BatchUncrop', 'BatchUncropAdvanced', 'BboxToInt', 'BboxVisualize', 'BlockifyMask', 'CFGZeroStarAndInit', 'CameraPoseVisualizer', 'CheckpointLoaderKJ', 'CheckpointPerturbWeights', 'ColorMatch', 'ColorMatchV2', 'ColorToMask', 'CondPassThrough', 'ConditioningMultiCombine', 'ConditioningSetMaskAndCombine', 'ConditioningSetMaskAndCombine3', 'ConditioningSetMaskAndCombine4', 'ConditioningSetMaskAndCombine5', 'ConsolidateMasksKJ', 'CreateAudioMask', 'CreateFadeMask', 'CreateFadeMaskAdvanced', 'CreateFluidMask', 'CreateGradientFromCoords', 'CreateGradientMask', 'CreateInstanceDiffusionTracking', 'CreateMagicMask', 'CreateShapeImageOnPath', 'CreateShapeMask', 'CreateShapeMaskOnPath', 'CreateTextMask', 'CreateTextOnPath', 'CreateVoronoiMask', 'CrossFadeImages', 'CrossFadeImagesMulti', 'CustomControlNetWeightsFluxFromList', 'CustomSigmas', 'CutAndDragOnPath', 'DecodeAndSaveVideo', 'DiTBlockLoraLoader', 'DifferentialDiffusionAdvanced', 'DiffusionModelLoaderKJ', 'DiffusionModelSelector', 'DownloadAndLoadCLIPSeg', 'DrawInstanceDiffusionTracking', 'DrawMaskOnImage', 'DummyOut', 'EmptyLatentImageCustomPresets', 'EmptyLatentImagePresets', 'EncodeVideoComponents', 'EndRecordCUDAMemoryHistory', 'FastPreview', 'FilterZeroMasksAndCorrespondingImages', 'FlipSigmasAdjusted', 'FloatConstant', 'FloatToMask', 'FloatToSigmas', 'FluxBlockLoraSelect', 'GGUFLoaderKJ', 'GLIGENTextBoxApplyBatchCoords', 'GenerateNoise', 'GetImageSizeAndCount', 'GetImagesFromBatchIndexed', 'GetLatentRangeFromBatch', 'GetLatentSizeAndCount', 'GetLatentsFromBatchIndexed', 'GetMaskSizeAndCount', 'GetTrackRange', 'GradientToFloat', 'GrowMaskWithBlur', 'HDRPreviewKJ', 'HunyuanVideoBlockLoraSelect', 'HunyuanVideoEncodeKeyframesToCond', 'INTConstant', 'ImageAddMulti', 'ImageAndMaskPreview', 'ImageBatchExtendWithOverlap', 'ImageBatchFilter', 'ImageBatchJoinWithTransition', 'ImageBatchMulti', 'ImageBatchRepeatInterleaving', 'ImageBatchTestPattern', 'ImageConcanate', 'ImageConcatFromBatch', 'ImageConcatMulti', 'ImageCropByMask', 'ImageCropByMaskAndResize', 'ImageCropByMaskBatch', 'ImageGrabPIL', 'ImageGridComposite2x2', 'ImageGridComposite3x3', 'ImageGridtoBatch', 'ImageNoiseAugmentation', 'ImageNormalize_Neg1_To_1', 'ImagePadForOutpaintMasked', 'ImagePadForOutpaintTargetSize', 'ImagePadKJ', 'ImagePass', 'ImagePrepForICLora', 'ImageResizeKJ', 'ImageResizeKJv2', 'ImageSharpenKJ', 'ImageTensorList', 'ImageTransformByNormalizedAmplitude', 'ImageTransformKJ', 'ImageUncropByMask', 'ImageUpscaleWithModelBatched', 'InjectNoiseToLatent', 'InsertImageBatchByIndexes', 'InsertImagesToBatchIndexed', 'InsertLatentToIndexed', 'InterpolateCoords', 'Intrinsic_lora_sampling', 'JoinStringMulti', 'JoinStrings', 'LTX2AttentionTunerPatch', 'LTX2AudioLatentNormalizingSampling', 'LTX2BlockLoraSelect', 'LTX2LoraLoaderAdvanced', 'LTX2MemoryEfficientSageAttentionPatch', 'LTX2SamplingPreviewOverride', 'LTX2_NAG', 'LTXVAudioVideoMask', 'LTXVChunkFeedForward', 'LTXVEnhanceAVideoKJ', 'LTXVImgToVideoInplaceKJ', 'LatentInpaintTTM', 'LazySwitchKJ', 'LeapfusionHunyuanI2VPatcher', 'LoadAndResizeImage', 'LoadImagesFromFolderKJ', 'LoadResAdapterNormalization', 'LoadVideosFromFolder', 'LoraExtractKJ', 'LoraReduceRankKJ', 'MaskBatchMulti', 'MaskOrImageToWeight', 'MergeImageChannels', 'ModelMemoryUsageFactorOverride', 'ModelMemoryUseReportPatch', 'ModelPassThrough', 'ModelPatchTorchSettings', 'ModelSaveKJ', 'NABLA_AttentionKJ', 'NormalizedAmplitudeToFloatList', 'NormalizedAmplitudeToMask', 'OffsetMask', 'OffsetMaskByNormalizedAmplitude', 'PadImageBatchInterleaved', 'PatchModelPatcherOrder', 'PathchSageAttentionKJ', 'PlaySoundKJ', 'PlotCoordinates', 'PointsEditor', 'PreviewAnimation', 'PreviewImageOrMask', 'PreviewLatentNoiseMask', 'RemapImageRange', 'RemapMaskRange', 'ReplaceImagesInBatch', 'ResizeMask', 'ReverseImageBatch', 'RoundMask', 'SV3D_BatchSchedule', 'SamplerSelfRefineVideo', 'SaveImageKJ', 'SaveImageWithAlpha', 'SaveStringKJ', 'ScaleBatchPromptSchedule', 'ScheduledCFGGuidance', 'ScreencapStream', 'Screencap_mss', 'SeparateMasks', 'SetShakkerLabsUnionControlNetType', 'ShuffleImageBatch', 'SigmasToFloat', 'SimpleCalculatorKJ', 'SkipLayerGuidanceWanVideo', 'Sleep', 'SoundReactive', 'SplineEditor', 'SplitBboxes', 'SplitImageChannels', 'StableZero123_BatchSchedule', 'StartRecordCUDAMemoryHistory', 'StringConstant', 'StringConstantMultiline', 'StringToFloatList', 'StyleModelApplyAdvanced', 'Superprompt', 'TimerNodeKJ', 'TorchCompileControlNet', 'TorchCompileCosmosModel', 'TorchCompileLTXModel', 'TorchCompileModelAdvanced', 'TorchCompileModelFluxAdvanced', 'TorchCompileModelFluxAdvancedV2', 'TorchCompileModelHyVideo', 'TorchCompileModelQwenImage', 'TorchCompileModelWanVideo', 'TorchCompileModelWanVideoV2', 'TorchCompileVAE', 'TransitionImagesInBatch', 'TransitionImagesMulti', 'VAEDecodeLoopKJ', 'VAELoaderKJ', 'VRAM_Debug', 'VisualizeCUDAMemoryHistory', 'VisualizeSigmasKJ', 'Wan21BlockLoraSelect', 'WanChunkFeedForward', 'WanImageToVideoSVIPro', 'WanVideoEnhanceAVideoKJ', 'WanVideoNAG', 'WanVideoTeaCacheKJ', 'WebcamCaptureCV2', 'WeightScheduleConvert', 'WeightScheduleExtend', 'WidgetToString']
