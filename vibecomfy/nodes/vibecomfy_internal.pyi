# vibecomfy:generated
# pack: vibecomfy_internal
# source: object_info cache vibecomfy@runpod-snapshot.json sha256:54bfa7fd55cd
# source_sha256: 17fa357b13f426b373eb06242ce2adc6d526a81759862ef2ab7b2239cb7a06ec
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 1

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def VibeComfyStripConditioningKeys(
    *args: VibeWorkflow,
    _id: str | None = ...,
    negative: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    keys: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['VibeComfyStripConditioningKeys']
