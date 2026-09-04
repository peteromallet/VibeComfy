# vibecomfy:generated
# pack: melbandroformer
# source: object_info cache ComfyUI-MelBandRoformer@stub.json sha256:9565279ddcfc
# source_sha256: cfdaed03403d8e487f38a8cb81238a3d0d17afc8a6957913fd17ca6e496d8e2b
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers melbandroformer

"""Auto-generated public wrappers for the melbandroformer custom-node pack.

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

def MelBandRoFormerModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt', 'MelBandRoformer.ckpt'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MelBandRoFormerModelLoader``.

    Display name: MelBandRoFormer Model Loader

    Category: audio

    Load MelBandRoFormer audio separation model

    Returns: model

    Source: object_info cache ComfyUI-MelBandRoformer@stub.json sha256:9565279ddcfc
    """
    if len(args) > 1:
        raise TypeError(f"MelBandRoFormerModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'MelBandRoFormerModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def MelBandRoFormerSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    chunk_size: int | _Omitted = _UNSET,
    overlap: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MelBandRoFormerSampler``.

    Display name: MelBandRoFormer Sampler

    Category: audio

    Separate audio using MelBandRoFormer

    Returns: audio, instrumental

    Source: object_info cache ComfyUI-MelBandRoformer@stub.json sha256:9565279ddcfc
    """
    if len(args) > 1:
        raise TypeError(f"MelBandRoFormerSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if model is not _UNSET:
        _kwargs['model'] = model
    if chunk_size is not _UNSET:
        _kwargs['chunk_size'] = chunk_size
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    _kwargs.update(_extras)
    return node(wf, 'MelBandRoFormerSampler', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['MelBandRoFormerModelLoader', 'MelBandRoFormerSampler']
__vibecomfy_class_types__ = {'MelBandRoFormerModelLoader': 'MelBandRoFormerModelLoader', 'MelBandRoFormerSampler': 'MelBandRoFormerSampler'}
