# vibecomfy:generated
# pack: sam2
# source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
# source_sha256: 6381b5dd17f3daebd81466a4cb6c9cd57e0b8f9ca3f3f9895662a97ba564f30a
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 6
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers sam2

"""Auto-generated public wrappers for the sam2 custom-node pack.

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

def DownloadAndLoadSAM2Model(
    *args: VibeWorkflow,
    _id: str | None = None,
    device: Literal['cuda', 'cpu', 'mps'] | _Omitted = _UNSET,
    model: Literal['sam2_hiera_base_plus.safetensors', 'sam2_hiera_large.safetensors', 'sam2_hiera_small.safetensors', 'sam2_hiera_tiny.safetensors', 'sam2.1_hiera_base_plus.safetensors', 'sam2.1_hiera_large.safetensors', 'sam2.1_hiera_small.safetensors', 'sam2.1_hiera_tiny.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    segmentor: Literal['single_image', 'video', 'automaskgenerator'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DownloadAndLoadSAM2Model``.

    Category: SAM2

    Returns: sam2_model

    Source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadSAM2Model() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if device is not _UNSET:
        _kwargs['device'] = device
    if model is not _UNSET:
        _kwargs['model'] = model
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if segmentor is not _UNSET:
        _kwargs['segmentor'] = segmentor
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadSAM2Model', _id, pass_raw=pass_raw, **_kwargs)

def Florence2toCoordinates(
    *args: VibeWorkflow,
    _id: str | None = None,
    batch: bool | _Omitted = _UNSET,
    data: Any | _Omitted = _UNSET,
    index: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Florence2toCoordinates``.

    Category: SAM2

    Returns: center_coordinates, bboxes

    Source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
    """
    if len(args) > 1:
        raise TypeError(f"Florence2toCoordinates() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if batch is not _UNSET:
        _kwargs['batch'] = batch
    if data is not _UNSET:
        _kwargs['data'] = data
    if index is not _UNSET:
        _kwargs['index'] = index
    _kwargs.update(_extras)
    return node(wf, 'Florence2toCoordinates', _id, pass_raw=pass_raw, **_kwargs)

def Sam2AutoSegmentation(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    box_nms_thresh: float | _Omitted = _UNSET,
    crop_n_layers: int | _Omitted = _UNSET,
    crop_n_points_downscale_factor: int | _Omitted = _UNSET,
    crop_nms_thresh: float | _Omitted = _UNSET,
    crop_overlap_ratio: float | _Omitted = _UNSET,
    keep_model_loaded: bool | _Omitted = _UNSET,
    mask_threshold: float | _Omitted = _UNSET,
    min_mask_region_area: float | _Omitted = _UNSET,
    points_per_batch: int | _Omitted = _UNSET,
    points_per_side: int | _Omitted = _UNSET,
    pred_iou_thresh: float | _Omitted = _UNSET,
    sam2_model: Any | _Omitted = _UNSET,
    stability_score_offset: float | _Omitted = _UNSET,
    stability_score_thresh: float | _Omitted = _UNSET,
    use_m2m: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Sam2AutoSegmentation``.

    Category: SAM2

    Returns: mask, segmented_image, bbox

    Source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
    """
    if len(args) > 1:
        raise TypeError(f"Sam2AutoSegmentation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if box_nms_thresh is not _UNSET:
        _kwargs['box_nms_thresh'] = box_nms_thresh
    if crop_n_layers is not _UNSET:
        _kwargs['crop_n_layers'] = crop_n_layers
    if crop_n_points_downscale_factor is not _UNSET:
        _kwargs['crop_n_points_downscale_factor'] = crop_n_points_downscale_factor
    if crop_nms_thresh is not _UNSET:
        _kwargs['crop_nms_thresh'] = crop_nms_thresh
    if crop_overlap_ratio is not _UNSET:
        _kwargs['crop_overlap_ratio'] = crop_overlap_ratio
    if keep_model_loaded is not _UNSET:
        _kwargs['keep_model_loaded'] = keep_model_loaded
    if mask_threshold is not _UNSET:
        _kwargs['mask_threshold'] = mask_threshold
    if min_mask_region_area is not _UNSET:
        _kwargs['min_mask_region_area'] = min_mask_region_area
    if points_per_batch is not _UNSET:
        _kwargs['points_per_batch'] = points_per_batch
    if points_per_side is not _UNSET:
        _kwargs['points_per_side'] = points_per_side
    if pred_iou_thresh is not _UNSET:
        _kwargs['pred_iou_thresh'] = pred_iou_thresh
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if stability_score_offset is not _UNSET:
        _kwargs['stability_score_offset'] = stability_score_offset
    if stability_score_thresh is not _UNSET:
        _kwargs['stability_score_thresh'] = stability_score_thresh
    if use_m2m is not _UNSET:
        _kwargs['use_m2m'] = use_m2m
    _kwargs.update(_extras)
    return node(wf, 'Sam2AutoSegmentation', _id, pass_raw=pass_raw, **_kwargs)

def Sam2Segmentation(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    keep_model_loaded: bool | _Omitted = _UNSET,
    sam2_model: Any | _Omitted = _UNSET,
    bboxes: Any | _Omitted = _UNSET,
    coordinates_negative: str | _Omitted = _UNSET,
    coordinates_positive: str | _Omitted = _UNSET,
    individual_objects: bool | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Sam2Segmentation``.

    Category: SAM2

    Returns: mask

    Source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
    """
    if len(args) > 1:
        raise TypeError(f"Sam2Segmentation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if keep_model_loaded is not _UNSET:
        _kwargs['keep_model_loaded'] = keep_model_loaded
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if coordinates_negative is not _UNSET:
        _kwargs['coordinates_negative'] = coordinates_negative
    if coordinates_positive is not _UNSET:
        _kwargs['coordinates_positive'] = coordinates_positive
    if individual_objects is not _UNSET:
        _kwargs['individual_objects'] = individual_objects
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'Sam2Segmentation', _id, pass_raw=pass_raw, **_kwargs)

def Sam2VideoSegmentation(
    *args: VibeWorkflow,
    _id: str | None = None,
    inference_state: Any | _Omitted = _UNSET,
    keep_model_loaded: bool | _Omitted = _UNSET,
    sam2_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Sam2VideoSegmentation``.

    Category: SAM2

    Returns: mask

    Source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
    """
    if len(args) > 1:
        raise TypeError(f"Sam2VideoSegmentation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inference_state is not _UNSET:
        _kwargs['inference_state'] = inference_state
    if keep_model_loaded is not _UNSET:
        _kwargs['keep_model_loaded'] = keep_model_loaded
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    _kwargs.update(_extras)
    return node(wf, 'Sam2VideoSegmentation', _id, pass_raw=pass_raw, **_kwargs)

def Sam2VideoSegmentationAddPoints(
    *args: VibeWorkflow,
    _id: str | None = None,
    coordinates_positive: str | _Omitted = _UNSET,
    frame_index: int | _Omitted = _UNSET,
    object_index: int | _Omitted = _UNSET,
    sam2_model: Any | _Omitted = _UNSET,
    coordinates_negative: str | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    prev_inference_state: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Sam2VideoSegmentationAddPoints``.

    Category: SAM2

    Returns: sam2_model, inference_state

    Source: object_info cache ComfyUI-segment-anything-2@local-0c35fff.json sha256:d2aa67d35f83
    """
    if len(args) > 1:
        raise TypeError(f"Sam2VideoSegmentationAddPoints() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if coordinates_positive is not _UNSET:
        _kwargs['coordinates_positive'] = coordinates_positive
    if frame_index is not _UNSET:
        _kwargs['frame_index'] = frame_index
    if object_index is not _UNSET:
        _kwargs['object_index'] = object_index
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if coordinates_negative is not _UNSET:
        _kwargs['coordinates_negative'] = coordinates_negative
    if image is not _UNSET:
        _kwargs['image'] = image
    if prev_inference_state is not _UNSET:
        _kwargs['prev_inference_state'] = prev_inference_state
    _kwargs.update(_extras)
    return node(wf, 'Sam2VideoSegmentationAddPoints', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DownloadAndLoadSAM2Model', 'Florence2toCoordinates', 'Sam2AutoSegmentation', 'Sam2Segmentation', 'Sam2VideoSegmentation', 'Sam2VideoSegmentationAddPoints']
__vibecomfy_class_types__ = {'DownloadAndLoadSAM2Model': 'DownloadAndLoadSAM2Model', 'Florence2toCoordinates': 'Florence2toCoordinates', 'Sam2AutoSegmentation': 'Sam2AutoSegmentation', 'Sam2Segmentation': 'Sam2Segmentation', 'Sam2VideoSegmentation': 'Sam2VideoSegmentation', 'Sam2VideoSegmentationAddPoints': 'Sam2VideoSegmentationAddPoints'}
