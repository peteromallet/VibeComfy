# vibecomfy:generated
# pack: gimm_vfi
# source: object_info cache ComfyUI-GIMM-VFI@stub.json sha256:572169109f6d
# source_sha256: 81ce75bd508fc803c2dd56e862d9d743bc99cb517f8d9b74b0152f361ce9cdfa
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DownloadAndLoadGIMMVFIModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['GIMMVFI_flow_S.pkl', 'GIMMVFI_flow_M.pkl', 'GIMMVFI_noflow_S.pkl', 'GIMMVFI_noflow_M.pkl'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GIMMVFI_interpolate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    multiplier: int | _Omitted = ...,
    scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['DownloadAndLoadGIMMVFIModel', 'GIMMVFI_interpolate']
