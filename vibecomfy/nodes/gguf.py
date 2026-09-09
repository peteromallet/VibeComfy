# vibecomfy:generated
# pack: gguf
# source: object_info cache ComfyUI-GGUF@local-6ea2651.json sha256:a4cc46702e38
# source_sha256: 9cbe636a73102fb56d60bacfa3b81696238242b147e0de017cfa758c9077e531
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers gguf

"""Auto-generated public wrappers for the gguf custom-node pack.

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

def DualCLIPLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DualCLIPLoaderGGUF``.

    Returns: None

    Source: object_info cache ComfyUI-GGUF@local-6ea2651.json sha256:a4cc46702e38
    """
    if len(args) > 1:
        raise TypeError(f"DualCLIPLoaderGGUF() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'DualCLIPLoaderGGUF', _id, pass_raw=pass_raw, **_kwargs)

def UnetLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = None,
    unet_name: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``UnetLoaderGGUF``.

    Category: bootleg

    Returns: MODEL

    Source: object_info cache ComfyUI-GGUF@local-6ea2651.json sha256:a4cc46702e38
    """
    if len(args) > 1:
        raise TypeError(f"UnetLoaderGGUF() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if unet_name is not _UNSET:
        _kwargs['unet_name'] = unet_name
    _kwargs.update(_extras)
    return node(wf, 'UnetLoaderGGUF', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF']
__vibecomfy_class_types__ = {'DualCLIPLoaderGGUF': 'DualCLIPLoaderGGUF', 'UnetLoaderGGUF': 'UnetLoaderGGUF'}
