# vibecomfy:generated
# pack: vibecomfy_internal
# source: object_info cache vibecomfy@runpod-snapshot.json sha256:54bfa7fd55cd
# source_sha256: 17fa357b13f426b373eb06242ce2adc6d526a81759862ef2ab7b2239cb7a06ec
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 1
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers vibecomfy_internal

"""Auto-generated public wrappers for the vibecomfy_internal custom-node pack.

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

def VibeComfyStripConditioningKeys(
    *args: VibeWorkflow,
    _id: str | None = None,
    negative: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    keys: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VibeComfyStripConditioningKeys``.

    Display name: VibeComfy Strip Conditioning Keys

    Category: conditioning/vibecomfy

    Returns: positive, negative

    Source: object_info cache vibecomfy@runpod-snapshot.json sha256:54bfa7fd55cd
    """
    if len(args) > 1:
        raise TypeError(f"VibeComfyStripConditioningKeys() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if keys is not _UNSET:
        _kwargs['keys'] = keys
    _kwargs.update(_extras)
    return node(wf, 'VibeComfyStripConditioningKeys', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['VibeComfyStripConditioningKeys']
__vibecomfy_class_types__ = {'VibeComfyStripConditioningKeys': 'VibeComfyStripConditioningKeys'}
