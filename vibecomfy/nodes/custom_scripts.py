# vibecomfy:generated
# pack: custom_scripts
# source: object_info cache ComfyUI-Custom-Scripts@stub.json sha256:f2471b22ff0e
# source_sha256: 27212910da8b4c465d1a80fc3926cf9b36f23ba8217942fbd0e7483f57904c79
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers custom_scripts

"""Auto-generated public wrappers for the custom_scripts custom-node pack.

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

def MathExpression_pysssss(
    *args: VibeWorkflow,
    _id: str | None = None,
    expression: str | _Omitted = _UNSET,
    a: Any | _Omitted = _UNSET,
    b: Any | _Omitted = _UNSET,
    c: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MathExpression|pysssss``.

    Display name: Math Expression 🐍

    Category: utils

    Evaluate a math expression

    Returns: int, float

    Source: object_info cache ComfyUI-Custom-Scripts@stub.json sha256:f2471b22ff0e
    """
    if len(args) > 1:
        raise TypeError(f"MathExpression_pysssss() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if expression is not _UNSET:
        _kwargs['expression'] = expression
    if a is not _UNSET:
        _kwargs['a'] = a
    if b is not _UNSET:
        _kwargs['b'] = b
    if c is not _UNSET:
        _kwargs['c'] = c
    _kwargs.update(_extras)
    return node(wf, 'MathExpression|pysssss', _id, pass_raw=pass_raw, **_kwargs)

def ShowText_pysssss(
    *args: VibeWorkflow,
    _id: str | None = None,
    text: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``ShowText|pysssss``.

    Display name: Show Text 🐍

    Category: text

    Show text output

    Returns: text

    Source: object_info cache ComfyUI-Custom-Scripts@stub.json sha256:f2471b22ff0e
    """
    if len(args) > 1:
        raise TypeError(f"ShowText_pysssss() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    _kwargs.update(_extras)
    return node(wf, 'ShowText|pysssss', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['MathExpression_pysssss', 'ShowText_pysssss']
__vibecomfy_class_types__ = {'MathExpression_pysssss': 'MathExpression|pysssss', 'ShowText_pysssss': 'ShowText|pysssss'}
