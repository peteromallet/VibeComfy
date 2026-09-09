# vibecomfy:generated
# pack: florence2
# source: object_info cache ComfyUI-Florence2@stub.json sha256:fefc87f406c2
# source_sha256: 330ad7c50b02ebd06b372a9034b555789648ceec02bea9760a79cf972c334a65
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers florence2

"""Auto-generated public wrappers for the florence2 custom-node pack.

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

def DownloadAndLoadFlorence2Model(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['microsoft/Florence-2-base', 'microsoft/Florence-2-large', 'microsoft/Florence-2-base-ft', 'microsoft/Florence-2-large-ft'] | _Omitted = _UNSET,
    attention: Literal['sdpa', 'flash_attention_2', 'eager'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DownloadAndLoadFlorence2Model``.

    Category: florence2

    Download and load Florence-2 model

    Returns: model

    Source: object_info cache ComfyUI-Florence2@stub.json sha256:fefc87f406c2
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadFlorence2Model() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadFlorence2Model', _id, pass_raw=pass_raw, **_kwargs)

def Florence2Run(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    florence2_model: Any | _Omitted = _UNSET,
    task: Literal['caption', 'detailed_caption', 'more_detailed_caption', 'caption_to_phrase_grounding', 'referring_expression_segmentation', 'region_to_segmentation', 'open_vocabulary_detection', 'dense_region_caption', 'region_proposal', 'ocr', 'ocr_with_region'] | _Omitted = _UNSET,
    text_input: str | _Omitted = _UNSET,
    fill_mask: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Florence2Run``.

    Category: florence2

    Run Florence-2 model

    Returns: image, mask, caption

    Source: object_info cache ComfyUI-Florence2@stub.json sha256:fefc87f406c2
    """
    if len(args) > 1:
        raise TypeError(f"Florence2Run() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if florence2_model is not _UNSET:
        _kwargs['florence2_model'] = florence2_model
    if task is not _UNSET:
        _kwargs['task'] = task
    if text_input is not _UNSET:
        _kwargs['text_input'] = text_input
    if fill_mask is not _UNSET:
        _kwargs['fill_mask'] = fill_mask
    _kwargs.update(_extras)
    return node(wf, 'Florence2Run', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DownloadAndLoadFlorence2Model', 'Florence2Run']
__vibecomfy_class_types__ = {'DownloadAndLoadFlorence2Model': 'DownloadAndLoadFlorence2Model', 'Florence2Run': 'Florence2Run'}
