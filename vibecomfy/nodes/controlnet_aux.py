# vibecomfy:generated
# pack: controlnet_aux
# source: object_info cache comfyui_controlnet_aux@stub.json sha256:e4fec4d3ee5b
# source_sha256: 4308cb85c80cbf6656e2bc83832be74bae0a24ac629c2e90df464a462ff9edb5
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 3
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers controlnet_aux

"""Auto-generated public wrappers for the controlnet_aux custom-node pack.

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

def CannyEdgePreprocessor(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    high_threshold: int | _Omitted = _UNSET,
    low_threshold: int | _Omitted = _UNSET,
    resolution: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``CannyEdgePreprocessor``.

    Display name: Canny Edge Preprocessor

    Category: ControlNet Preprocessors/Line Extractors

    Canny edge detector

    Returns: IMAGE

    Source: object_info cache comfyui_controlnet_aux@stub.json sha256:e4fec4d3ee5b
    """
    if len(args) > 1:
        raise TypeError(f"CannyEdgePreprocessor() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if high_threshold is not _UNSET:
        _kwargs['high_threshold'] = high_threshold
    if low_threshold is not _UNSET:
        _kwargs['low_threshold'] = low_threshold
    if resolution is not _UNSET:
        _kwargs['resolution'] = resolution
    _kwargs.update(_extras)
    return node(wf, 'CannyEdgePreprocessor', _id, pass_raw=pass_raw, **_kwargs)

def DWPreprocessor(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    bbox_detector: Literal['yolox_l.onnx', 'yolo_nas_l_fp16.onnx', 'yolo_nas_m_fp16.onnx', 'yolo_nas_s_fp16.onnx'] | _Omitted = _UNSET,
    detect_body: Literal['enable', 'disable'] | _Omitted = _UNSET,
    detect_face: Literal['enable', 'disable'] | _Omitted = _UNSET,
    detect_hand: Literal['enable', 'disable'] | _Omitted = _UNSET,
    pose_estimator: Literal['dw-ll_ucoco_384_bs5.torchscript.pt', 'dw-ll_ucoco_384.onnx', 'dw-ll_ucoco.onnx'] | _Omitted = _UNSET,
    resolution: int | _Omitted = _UNSET,
    scale_stick_for_xinsr_cn: Literal['disable', 'enable'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DWPreprocessor``.

    Display name: DWPose Estimator

    Category: ControlNet Preprocessors/Faces and Pose Estimators

    DW Pose Estimation

    Returns: IMAGE, pose_keypoint

    Source: object_info cache comfyui_controlnet_aux@stub.json sha256:e4fec4d3ee5b
    """
    if len(args) > 1:
        raise TypeError(f"DWPreprocessor() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if bbox_detector is not _UNSET:
        _kwargs['bbox_detector'] = bbox_detector
    if detect_body is not _UNSET:
        _kwargs['detect_body'] = detect_body
    if detect_face is not _UNSET:
        _kwargs['detect_face'] = detect_face
    if detect_hand is not _UNSET:
        _kwargs['detect_hand'] = detect_hand
    if pose_estimator is not _UNSET:
        _kwargs['pose_estimator'] = pose_estimator
    if resolution is not _UNSET:
        _kwargs['resolution'] = resolution
    if scale_stick_for_xinsr_cn is not _UNSET:
        _kwargs['scale_stick_for_xinsr_cn'] = scale_stick_for_xinsr_cn
    _kwargs.update(_extras)
    return node(wf, 'DWPreprocessor', _id, pass_raw=pass_raw, **_kwargs)

def DepthAnythingPreprocessor(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    ckpt_name: Literal['depth_anything_vitl14.pth', 'depth_anything_vitb14.pth', 'depth_anything_vits14.pth'] | _Omitted = _UNSET,
    resolution: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DepthAnythingPreprocessor``.

    Display name: Depth Anything Preprocessor

    Category: ControlNet Preprocessors/Normal and Depth Estimators

    Depth Anything preprocessor

    Returns: IMAGE

    Source: object_info cache comfyui_controlnet_aux@stub.json sha256:e4fec4d3ee5b
    """
    if len(args) > 1:
        raise TypeError(f"DepthAnythingPreprocessor() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if resolution is not _UNSET:
        _kwargs['resolution'] = resolution
    _kwargs.update(_extras)
    return node(wf, 'DepthAnythingPreprocessor', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['CannyEdgePreprocessor', 'DWPreprocessor', 'DepthAnythingPreprocessor']
__vibecomfy_class_types__ = {'CannyEdgePreprocessor': 'CannyEdgePreprocessor', 'DWPreprocessor': 'DWPreprocessor', 'DepthAnythingPreprocessor': 'DepthAnythingPreprocessor'}
