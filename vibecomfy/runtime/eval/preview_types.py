"""Preview node injection mapping for runtime eval-node.

Maps ComfyUI output class-type names to the :class:`PreviewInjection`
that should be appended to a subgraph to make its output visualizable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreviewInjection:
    """Describes a preview node to insert into a compiled subgraph."""

    class_type: str
    """The ComfyUI node class_type (e.g. ``\"PreviewImage\"``)."""

    output_input_slot: str = "images"
    """Which input slot of the preview node should receive the output."""

    extra_inputs: dict[str, Any] | None = None
    """Optional static inputs for the preview node."""


#: Mapping from human-readable output category to :class:`PreviewInjection`.
#:
#: IMAGE → `PreviewImage`
#: MASK  → `PreviewMask`
#: VIDEO → `VHS_VideoCombine` (with fallback to `PreviewVideo`)
#: AUDIO → `PreviewAudio`
PREVIEW_MAP: dict[str, PreviewInjection] = {
    "IMAGE": PreviewInjection("PreviewImage", output_input_slot="images"),
    "MASK": PreviewInjection("PreviewMask", output_input_slot="mask"),
    "VIDEO": PreviewInjection(
        "VHS_VideoCombine",
        output_input_slot="images",
        extra_inputs={"frame_rate": 30, "loop_count": 0, "filename_prefix": "eval", "format": "video/h264-mp4"},
    ),
    "AUDIO": PreviewInjection("PreviewAudio", output_input_slot="audio"),
}

#: Fallback for VIDEO when VHS_VideoCombine is not available.
VIDEO_FALLBACK: PreviewInjection = PreviewInjection("PreviewVideo", output_input_slot="video")


#: Node class_types that are known VAE emitters (loaders / handles).
#: Used during LATENT eval to discover upstream VAE handles.
VAE_EMITTER_CLASSES: frozenset[str] = frozenset(
    {
        "VAELoader",
        "CheckpointLoaderSimple",
        "WanVideoVAELoader",
        "LTXVAudioVAELoader",
        "VAEDecode",
        "VAEDecodeTiled",
        "VAEEncode",
        "VAEEncodeTiled",
    }
)


@dataclass(frozen=True)
class PreviewPlan:
    """Result of `preview_plan_for_type` — whether and how a Comfy output type can be previewed."""
    comfy_type: str
    previewable: bool
    injection: PreviewInjection | None = None


def preview_plan_for_type(comfy_type: str, *, has_vae: bool = False) -> PreviewPlan:
    """Plan a preview-node injection for a single Comfy output type.

    IMAGE / MASK / AUDIO / VIDEO fall straight out of PREVIEW_MAP. LATENT becomes
    previewable only when a VAE handle is available upstream. Everything else is
    non-previewable.
    """
    if comfy_type in PREVIEW_MAP:
        return PreviewPlan(comfy_type=comfy_type, previewable=True, injection=PREVIEW_MAP[comfy_type])
    if comfy_type == "LATENT" and has_vae:
        return PreviewPlan(comfy_type=comfy_type, previewable=True, injection=PREVIEW_MAP["IMAGE"])
    return PreviewPlan(comfy_type=comfy_type, previewable=False)
