# vibecomfy:generated
# pack: wananimatepreprocess
# source: object_info cache ComfyUI-WanAnimatePreprocess@local-1a35b81.json sha256:a8b2052fba90
# source_sha256: d43726cafe24180b6416a3ebeead2ff805f53c81476fa9d0a42a602fd309f390
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 5

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DrawViTPose(
    *args: VibeWorkflow,
    _id: str | None = ...,
    body_stick_width: int | _Omitted = ...,
    draw_head: bool | _Omitted = ...,
    hand_stick_width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    pose_data: Any | _Omitted = ...,
    retarget_padding: int | _Omitted = ...,
    width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OnnxDetectionModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    onnx_device: Literal['CUDAExecutionProvider', 'CPUExecutionProvider'] | _Omitted = ...,
    vitpose_model: Any | _Omitted = ...,
    yolo_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PoseAndFaceDetection(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    height: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    face_padding: int | _Omitted = ...,
    retarget_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PoseDetectionOneToAllAnimation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    align_to: Literal['ref', 'pose', 'none'] | _Omitted = ...,
    draw_face_points: Literal['full', 'weak', 'none'] | _Omitted = ...,
    draw_head: Literal['full', 'weak', 'none'] | _Omitted = ...,
    height: int | _Omitted = ...,
    model: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PoseRetargetPromptHelper(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_data: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['DrawViTPose', 'OnnxDetectionModelLoader', 'PoseAndFaceDetection', 'PoseDetectionOneToAllAnimation', 'PoseRetargetPromptHelper']
