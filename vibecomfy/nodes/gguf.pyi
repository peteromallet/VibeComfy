# vibecomfy:generated
# pack: gguf
# source: object_info cache ComfyUI-GGUF@local-6ea2651.json sha256:a4cc46702e38
# source_sha256: 9cbe636a73102fb56d60bacfa3b81696238242b147e0de017cfa758c9077e531
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DualCLIPLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UnetLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = ...,
    unet_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF']
