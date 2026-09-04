# vibecomfy:generated
# pack: controlnet_aux
# source: object_info cache comfyui_controlnet_aux@stub.json sha256:e4fec4d3ee5b
# source_sha256: 4308cb85c80cbf6656e2bc83832be74bae0a24ac629c2e90df464a462ff9edb5
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 3

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def CannyEdgePreprocessor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    high_threshold: int | _Omitted = ...,
    low_threshold: int | _Omitted = ...,
    resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DWPreprocessor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    bbox_detector: Literal['yolox_l.onnx', 'yolo_nas_l_fp16.onnx', 'yolo_nas_m_fp16.onnx', 'yolo_nas_s_fp16.onnx'] | _Omitted = ...,
    detect_body: Literal['enable', 'disable'] | _Omitted = ...,
    detect_face: Literal['enable', 'disable'] | _Omitted = ...,
    detect_hand: Literal['enable', 'disable'] | _Omitted = ...,
    pose_estimator: Literal['dw-ll_ucoco_384_bs5.torchscript.pt', 'dw-ll_ucoco_384.onnx', 'dw-ll_ucoco.onnx'] | _Omitted = ...,
    resolution: int | _Omitted = ...,
    scale_stick_for_xinsr_cn: Literal['disable', 'enable'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DepthAnythingPreprocessor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    ckpt_name: Literal['depth_anything_vitl14.pth', 'depth_anything_vitb14.pth', 'depth_anything_vits14.pth'] | _Omitted = ...,
    resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['CannyEdgePreprocessor', 'DWPreprocessor', 'DepthAnythingPreprocessor']
