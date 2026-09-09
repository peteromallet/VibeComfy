# vibecomfy:generated
# pack: depthanythingv2
# source: object_info cache ComfyUI-DepthAnythingV2@local-5531878.json sha256:a4be95cffb29
# source_sha256: 428403e019f2532a2baeafe410239296f96c3d5130101d843800ac4cd888f3e6
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 5
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers depthanythingv2

"""Auto-generated public wrappers for the depthanythingv2 custom-node pack.

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

def DepthAnything_V2(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    da_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DepthAnything_V2``.

    Display name: https://depth-anything-v2.github.io

    Category: DepthAnythingV2

    Returns: image

    Source: object_info cache ComfyUI-DepthAnythingV2@local-5531878.json sha256:a4be95cffb29
    """
    if len(args) > 1:
        raise TypeError(f"DepthAnything_V2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if da_model is not _UNSET:
        _kwargs['da_model'] = da_model
    _kwargs.update(_extras)
    return node(wf, 'DepthAnything_V2', _id, pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadDepthAnythingV2Model(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['depth_anything_v2_vits_fp16.safetensors', 'depth_anything_v2_vits_fp32.safetensors', 'depth_anything_v2_vitb_fp16.safetensors', 'depth_anything_v2_vitb_fp32.safetensors', 'depth_anything_v2_vitl_fp16.safetensors', 'depth_anything_v2_vitl_fp32.safetensors', 'depth_anything_v2_vitg_fp32.safetensors', 'depth_anything_v2_metric_hypersim_vitl_fp32.safetensors', 'depth_anything_v2_metric_vkitti_vitl_fp32.safetensors'] | _Omitted = _UNSET,
    precision: Literal['auto', 'bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DownloadAndLoadDepthAnythingV2Model``.

    Display name: Models autodownload to `ComfyUI/models/depthanything` from
    https://huggingface.co/Kijai/DepthAnythingV2-safetensors/tree/main

    fp16 reduces quality by a LOT, not recommended.

    Category: DepthAnythingV2

    Returns: da_v2_model

    Source: object_info cache ComfyUI-DepthAnythingV2@local-5531878.json sha256:a4be95cffb29
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadDepthAnythingV2Model() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadDepthAnythingV2Model', _id, pass_raw=pass_raw, **_kwargs)

def LoadVideoDepthAnythingModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['v2-vits', 'v2-vitb', 'v2-vitl'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LoadVideoDepthAnythingModel``.

    Display name: Load Video Depth Anything Model

    Category: depth

    Load video depth anything model

    Returns: model

    Source: object_info cache ComfyUI-DepthAnythingV2@local-5531878.json sha256:a4be95cffb29
    """
    if len(args) > 1:
        raise TypeError(f"LoadVideoDepthAnythingModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'LoadVideoDepthAnythingModel', _id, pass_raw=pass_raw, **_kwargs)

def VideoDepthAnythingOutput(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VideoDepthAnythingOutput``.

    Display name: Video Depth Anything Output

    Category: depth

    Output video depth

    Returns: depth_image

    Source: object_info cache ComfyUI-DepthAnythingV2@local-5531878.json sha256:a4be95cffb29
    """
    if len(args) > 1:
        raise TypeError(f"VideoDepthAnythingOutput() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'VideoDepthAnythingOutput', _id, pass_raw=pass_raw, **_kwargs)

def VideoDepthAnythingProcess(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VideoDepthAnythingProcess``.

    Display name: Video Depth Anything Process

    Category: depth

    Process video frames with Depth Anything V2

    Returns: depth

    Source: object_info cache ComfyUI-DepthAnythingV2@local-5531878.json sha256:a4be95cffb29
    """
    if len(args) > 1:
        raise TypeError(f"VideoDepthAnythingProcess() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'VideoDepthAnythingProcess', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model', 'LoadVideoDepthAnythingModel', 'VideoDepthAnythingOutput', 'VideoDepthAnythingProcess']
__vibecomfy_class_types__ = {'DepthAnything_V2': 'DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model': 'DownloadAndLoadDepthAnythingV2Model', 'LoadVideoDepthAnythingModel': 'LoadVideoDepthAnythingModel', 'VideoDepthAnythingOutput': 'VideoDepthAnythingOutput', 'VideoDepthAnythingProcess': 'VideoDepthAnythingProcess'}
