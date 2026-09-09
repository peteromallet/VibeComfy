# vibecomfy:generated
# pack: florence2
# source: object_info cache ComfyUI-Florence2@stub.json sha256:fefc87f406c2
# source_sha256: 330ad7c50b02ebd06b372a9034b555789648ceec02bea9760a79cf972c334a65
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 2

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DownloadAndLoadFlorence2Model(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['microsoft/Florence-2-base', 'microsoft/Florence-2-large', 'microsoft/Florence-2-base-ft', 'microsoft/Florence-2-large-ft'] | _Omitted = ...,
    attention: Literal['sdpa', 'flash_attention_2', 'eager'] | _Omitted = ...,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2Run(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    florence2_model: Any | _Omitted = ...,
    task: Literal['caption', 'detailed_caption', 'more_detailed_caption', 'caption_to_phrase_grounding', 'referring_expression_segmentation', 'region_to_segmentation', 'open_vocabulary_detection', 'dense_region_caption', 'region_proposal', 'ocr', 'ocr_with_region'] | _Omitted = ...,
    text_input: str | _Omitted = ...,
    fill_mask: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['DownloadAndLoadFlorence2Model', 'Florence2Run']
