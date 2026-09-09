# vibecomfy:generated
# pack: melbandroformer
# source: object_info cache ComfyUI-MelBandRoformer@stub.json sha256:9565279ddcfc
# source_sha256: cfdaed03403d8e487f38a8cb81238a3d0d17afc8a6957913fd17ca6e496d8e2b
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def MelBandRoFormerModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt', 'MelBandRoformer.ckpt'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MelBandRoFormerSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    chunk_size: int | _Omitted = ...,
    overlap: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['MelBandRoFormerModelLoader', 'MelBandRoFormerSampler']
