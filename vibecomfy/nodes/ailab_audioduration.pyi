# vibecomfy:generated
# pack: ailab_audioduration
# source: object_info cache AILab_AudioDuration@runpod-snapshot.json sha256:3f5206f99c88
# source_sha256: ce6f858d1b23e36bb5b5f6ffa10e5443fdf061756afabc128a17f8bedfe38162
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 1

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def Audio_Duration(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    audio_path: str | _Omitted = ...,
    fps: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['Audio_Duration']
