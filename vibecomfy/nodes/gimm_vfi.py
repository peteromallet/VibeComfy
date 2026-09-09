# vibecomfy:generated
# pack: gimm_vfi
# source: object_info cache ComfyUI-GIMM-VFI@stub.json sha256:572169109f6d
# source_sha256: 81ce75bd508fc803c2dd56e862d9d743bc99cb517f8d9b74b0152f361ce9cdfa
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers gimm_vfi

"""Auto-generated public wrappers for the gimm_vfi custom-node pack.

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

def DownloadAndLoadGIMMVFIModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['GIMMVFI_flow_S.pkl', 'GIMMVFI_flow_M.pkl', 'GIMMVFI_noflow_S.pkl', 'GIMMVFI_noflow_M.pkl'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DownloadAndLoadGIMMVFIModel``.

    Display name: Download And Load GIMM-VFI Model

    Category: video

    Download and load GIMM-VFI model

    Returns: model

    Source: object_info cache ComfyUI-GIMM-VFI@stub.json sha256:572169109f6d
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadGIMMVFIModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadGIMMVFIModel', _id, pass_raw=pass_raw, **_kwargs)

def GIMMVFI_interpolate(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    multiplier: int | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``GIMMVFI_interpolate``.

    Display name: GIMM-VFI Interpolate

    Category: video

    Interpolate frames with GIMM-VFI

    Returns: images

    Source: object_info cache ComfyUI-GIMM-VFI@stub.json sha256:572169109f6d
    """
    if len(args) > 1:
        raise TypeError(f"GIMMVFI_interpolate() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if model is not _UNSET:
        _kwargs['model'] = model
    if multiplier is not _UNSET:
        _kwargs['multiplier'] = multiplier
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    _kwargs.update(_extras)
    return node(wf, 'GIMMVFI_interpolate', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DownloadAndLoadGIMMVFIModel', 'GIMMVFI_interpolate']
__vibecomfy_class_types__ = {'DownloadAndLoadGIMMVFIModel': 'DownloadAndLoadGIMMVFIModel', 'GIMMVFI_interpolate': 'GIMMVFI_interpolate'}
