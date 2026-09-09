# vibecomfy:generated
# pack: sam2
# source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
# source_sha256: 6381b5dd17f3daebd81466a4cb6c9cd57e0b8f9ca3f3f9895662a97ba564f30a
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 6

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DownloadAndLoadSAM2Model(
    *args: VibeWorkflow,
    _id: str | None = ...,
    device: Literal['cuda', 'cpu', 'mps'] | _Omitted = ...,
    model: Literal['sam2_hiera_base_plus.safetensors', 'sam2_hiera_large.safetensors', 'sam2_hiera_small.safetensors', 'sam2_hiera_tiny.safetensors', 'sam2.1_hiera_base_plus.safetensors', 'sam2.1_hiera_large.safetensors', 'sam2.1_hiera_small.safetensors', 'sam2.1_hiera_tiny.safetensors'] | _Omitted = ...,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = ...,
    segmentor: Literal['single_image', 'video', 'automaskgenerator'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2toCoordinates(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch: bool | _Omitted = ...,
    data: Any | _Omitted = ...,
    index: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2AutoSegmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    box_nms_thresh: float | _Omitted = ...,
    crop_n_layers: int | _Omitted = ...,
    crop_n_points_downscale_factor: int | _Omitted = ...,
    crop_nms_thresh: float | _Omitted = ...,
    crop_overlap_ratio: float | _Omitted = ...,
    keep_model_loaded: bool | _Omitted = ...,
    mask_threshold: float | _Omitted = ...,
    min_mask_region_area: float | _Omitted = ...,
    points_per_batch: int | _Omitted = ...,
    points_per_side: int | _Omitted = ...,
    pred_iou_thresh: float | _Omitted = ...,
    sam2_model: Any | _Omitted = ...,
    stability_score_offset: float | _Omitted = ...,
    stability_score_thresh: float | _Omitted = ...,
    use_m2m: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2Segmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    keep_model_loaded: bool | _Omitted = ...,
    sam2_model: Any | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    coordinates_negative: str | _Omitted = ...,
    coordinates_positive: str | _Omitted = ...,
    individual_objects: bool | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2VideoSegmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    inference_state: Any | _Omitted = ...,
    keep_model_loaded: bool | _Omitted = ...,
    sam2_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2VideoSegmentationAddPoints(
    *args: VibeWorkflow,
    _id: str | None = ...,
    coordinates_positive: str | _Omitted = ...,
    frame_index: int | _Omitted = ...,
    object_index: int | _Omitted = ...,
    sam2_model: Any | _Omitted = ...,
    coordinates_negative: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    prev_inference_state: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['DownloadAndLoadSAM2Model', 'Florence2toCoordinates', 'Sam2AutoSegmentation', 'Sam2Segmentation', 'Sam2VideoSegmentation', 'Sam2VideoSegmentationAddPoints']
