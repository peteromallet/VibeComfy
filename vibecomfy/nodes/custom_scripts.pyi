# vibecomfy:generated
# pack: custom_scripts
# source: object_info cache ComfyUI-Custom-Scripts@stub.json sha256:f2471b22ff0e
# source_sha256: 27212910da8b4c465d1a80fc3926cf9b36f23ba8217942fbd0e7483f57904c79
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def MathExpression_pysssss(
    *args: VibeWorkflow,
    _id: str | None = ...,
    expression: str | _Omitted = ...,
    a: Any | _Omitted = ...,
    b: Any | _Omitted = ...,
    c: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ShowText_pysssss(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['MathExpression_pysssss', 'ShowText_pysssss']
