# vibecomfy:generated
# pack: wananimatepreprocess
# source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
# source_sha256: d43726cafe24180b6416a3ebeead2ff805f53c81476fa9d0a42a602fd309f390
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 5
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers wananimatepreprocess

"""Auto-generated public wrappers for the wananimatepreprocess custom-node pack.

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

def DrawViTPose(
    *args: VibeWorkflow,
    _id: str | None = None,
    body_stick_width: int | _Omitted = _UNSET,
    draw_head: bool | _Omitted = _UNSET,
    hand_stick_width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pose_data: Any | _Omitted = _UNSET,
    retarget_padding: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DrawViTPose``.

    Display name: Draws pose images from pose data.

    Category: WanAnimatePreprocess

    Returns: pose_images

    Source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
    """
    if len(args) > 1:
        raise TypeError(f"DrawViTPose() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if body_stick_width is not _UNSET:
        _kwargs['body_stick_width'] = body_stick_width
    if draw_head is not _UNSET:
        _kwargs['draw_head'] = draw_head
    if hand_stick_width is not _UNSET:
        _kwargs['hand_stick_width'] = hand_stick_width
    if height is not _UNSET:
        _kwargs['height'] = height
    if pose_data is not _UNSET:
        _kwargs['pose_data'] = pose_data
    if retarget_padding is not _UNSET:
        _kwargs['retarget_padding'] = retarget_padding
    if width is not _UNSET:
        _kwargs['width'] = width
    _kwargs.update(_extras)
    return node(wf, 'DrawViTPose', _id, pass_raw=pass_raw, **_kwargs)

def OnnxDetectionModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    onnx_device: Literal['CUDAExecutionProvider', 'CPUExecutionProvider'] | _Omitted = _UNSET,
    vitpose_model: Any | _Omitted = _UNSET,
    yolo_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``OnnxDetectionModelLoader``.

    Display name: Loads ONNX models for pose and face detection. ViTPose for pose estimation and YOLO for object detection.

    Category: WanAnimatePreprocess

    Returns: model

    Source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
    """
    if len(args) > 1:
        raise TypeError(f"OnnxDetectionModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if onnx_device is not _UNSET:
        _kwargs['onnx_device'] = onnx_device
    if vitpose_model is not _UNSET:
        _kwargs['vitpose_model'] = vitpose_model
    if yolo_model is not _UNSET:
        _kwargs['yolo_model'] = yolo_model
    _kwargs.update(_extras)
    return node(wf, 'OnnxDetectionModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def PoseAndFaceDetection(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    face_padding: int | _Omitted = _UNSET,
    retarget_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``PoseAndFaceDetection``.

    Display name: Detects human poses and face images from input images. Optionally retargets poses based on a reference image.

    Category: WanAnimatePreprocess

    Returns: pose_data, face_images, key_frame_body_points, bboxes, face_bboxes

    Source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
    """
    if len(args) > 1:
        raise TypeError(f"PoseAndFaceDetection() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if height is not _UNSET:
        _kwargs['height'] = height
    if model is not _UNSET:
        _kwargs['model'] = model
    if width is not _UNSET:
        _kwargs['width'] = width
    if face_padding is not _UNSET:
        _kwargs['face_padding'] = face_padding
    if retarget_image is not _UNSET:
        _kwargs['retarget_image'] = retarget_image
    _kwargs.update(_extras)
    return node(wf, 'PoseAndFaceDetection', _id, pass_raw=pass_raw, **_kwargs)

def PoseDetectionOneToAllAnimation(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    align_to: Literal['ref', 'pose', 'none'] | _Omitted = _UNSET,
    draw_face_points: Literal['full', 'weak', 'none'] | _Omitted = _UNSET,
    draw_head: Literal['full', 'weak', 'none'] | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    ref_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``PoseDetectionOneToAllAnimation``.

    Display name: Specialized pose detection and alignment for OneToAllAnimation model https://github.com/ssj9596/One-to-All-Animation. Detects poses from input images and aligns them based on a reference image if provided.

    Category: WanAnimatePreprocess

    Returns: pose_images, ref_pose_image, ref_image, ref_mask

    Source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
    """
    if len(args) > 1:
        raise TypeError(f"PoseDetectionOneToAllAnimation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if align_to is not _UNSET:
        _kwargs['align_to'] = align_to
    if draw_face_points is not _UNSET:
        _kwargs['draw_face_points'] = draw_face_points
    if draw_head is not _UNSET:
        _kwargs['draw_head'] = draw_head
    if height is not _UNSET:
        _kwargs['height'] = height
    if model is not _UNSET:
        _kwargs['model'] = model
    if width is not _UNSET:
        _kwargs['width'] = width
    if ref_image is not _UNSET:
        _kwargs['ref_image'] = ref_image
    _kwargs.update(_extras)
    return node(wf, 'PoseDetectionOneToAllAnimation', _id, pass_raw=pass_raw, **_kwargs)

def PoseRetargetPromptHelper(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_data: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``PoseRetargetPromptHelper``.

    Display name: Generates text prompts for pose retargeting based on visibility of arms and legs in the template pose. Originally used for Flux Kontext

    Category: WanAnimatePreprocess

    Returns: prompt, retarget_prompt

    Source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
    """
    if len(args) > 1:
        raise TypeError(f"PoseRetargetPromptHelper() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_data is not _UNSET:
        _kwargs['pose_data'] = pose_data
    _kwargs.update(_extras)
    return node(wf, 'PoseRetargetPromptHelper', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DrawViTPose', 'OnnxDetectionModelLoader', 'PoseAndFaceDetection', 'PoseDetectionOneToAllAnimation', 'PoseRetargetPromptHelper']
__vibecomfy_class_types__ = {'DrawViTPose': 'DrawViTPose', 'OnnxDetectionModelLoader': 'OnnxDetectionModelLoader', 'PoseAndFaceDetection': 'PoseAndFaceDetection', 'PoseDetectionOneToAllAnimation': 'PoseDetectionOneToAllAnimation', 'PoseRetargetPromptHelper': 'PoseRetargetPromptHelper'}
