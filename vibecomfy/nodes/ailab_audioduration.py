# vibecomfy:generated
# pack: ailab_audioduration
# source: object_info cache AILab_AudioDuration@runpod-snapshot.json sha256:3f5206f99c88
# source_sha256: ce6f858d1b23e36bb5b5f6ffa10e5443fdf061756afabc128a17f8bedfe38162
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 1
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers ailab_audioduration

"""Auto-generated public wrappers for the ailab_audioduration custom-node pack.

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

def Audio_Duration(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    audio_path: str | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Audio Duration``.

    Display name: Audio Duration & Frames

    Category: 🧪AILab/🔊Audio

    Returns: duration_int, duration_float, frames, audio_path

    Source: object_info cache AILab_AudioDuration@runpod-snapshot.json sha256:3f5206f99c88
    """
    if len(args) > 1:
        raise TypeError(f"Audio_Duration() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if audio_path is not _UNSET:
        _kwargs['audio_path'] = audio_path
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    _kwargs.update(_extras)
    return node(wf, 'Audio Duration', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['Audio_Duration']
__vibecomfy_class_types__ = {'Audio_Duration': 'Audio Duration'}
