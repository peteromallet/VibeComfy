# vibecomfy:generated
# pack: videohelpersuite
# source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
# source_sha256: 77d8fc8c4abaf3c904b367f3e232ec42b4e262a14d40f97060e1c9e22da683f2
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 40
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers videohelpersuite

"""Auto-generated public wrappers for the videohelpersuite custom-node pack.

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

def VHS_AudioToVHSAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_AudioToVHSAudio``.

    Display name: Audio to legacy VHS_AUDIO🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/audio

    Audio to legacy VHS_AUDIO 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>utility function for compatibility with external nodes</div></div><div style="font-size: 0.8em">VHS used to use an internal VHS_AUDIO format for routing audio between inputs and outputs. This format was intended to only be used internally and was designed with a focus on performance over ease of use. Since ComfyUI now has an internal AUDIO format, VHS now uses this format. However, some custom node packs were made that are external to both ComfyUI and VHS that use VHS_AUDIO. This node was added so that those external nodes can still function</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: An input in the standardized AUDIO format</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="vhs_audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vhs_audio: An output in the legacy VHS_AUDIO format for use with external nodes</div></div></div></div></div>

    Returns: vhs_audio

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_AudioToVHSAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'VHS_AudioToVHSAudio', _id, pass_raw=pass_raw, **_kwargs)

def VHS_BatchManager(
    *args: VibeWorkflow,
    _id: str | None = None,
    frames_per_batch: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_BatchManager``.

    Display name: Meta Batch Manager 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Meta Batch Manager 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Split the processing of a very long video into sets of smaller Meta Batches</div></div><div style="font-size: 0.8em">The Meta Batch Manager allows for extremely long input videos to be processed when all other methods for fitting the content in RAM fail. It does not effect VRAM usage.</div><div style="font-size: 0.8em">It must be connected to at least one Input (a Load Video or Load Images) AND at least one Video Combine</div><div style="font-size: 0.8em"><img src=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/assets/4284322/7cb3fb7e-59d8-4cb2-a09f-9c6698de8b1f loading=lazy style="width: 0px; min-width: 100%"></div><div style="font-size: 0.8em">It functions by holding both the inputs and ouputs open between executions, and automatically requeue's the workflow until one of the inputs is unable to provide additional images.</div><div style="font-size: 0.8em">Because each sub execution only contains a subset of the total frames, each sub execution creates a hard window which temporal smoothing can not be applied across. This results in jumps in the output.</div><div style="font-size: 0.8em"><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: Add all connected nodes to this Meta Batch</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="frames_per_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frames_per_batch: How many frames to process for each sub execution. If loading as image, each frame will use about 50MB of RAM (not VRAM), and this can safely be set in the 100-1000 range, depending on available memory. When loading and combining from latent space (no blue image noodles exist), this value can be much higher, around the 2,000 to 20,000 range</div></div></div></div></div>

    Returns: meta_batch

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_BatchManager() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if frames_per_batch is not _UNSET:
        _kwargs['frames_per_batch'] = frames_per_batch
    _kwargs.update(_extras)
    return node(wf, 'VHS_BatchManager', _id, pass_raw=pass_raw, **_kwargs)

def VHS_DuplicateImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    multiply_by: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_DuplicateImages``.

    Display name: Repeat Images 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/image

    Repeat Images 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Append copies of a image to itself so it repeats</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="IMAGES" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGES: The image to be repeated</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The image with repeats</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of image in the output. Equal to the length of the input image * multiply_by</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="multiply_by" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">multiply_by: Controls the number of times the mask should repeat. 1, the default, means no change.</div></div></div></div></div>

    Returns: IMAGE, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_DuplicateImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if multiply_by is not _UNSET:
        _kwargs['multiply_by'] = multiply_by
    _kwargs.update(_extras)
    return node(wf, 'VHS_DuplicateImages', _id, pass_raw=pass_raw, **_kwargs)

def VHS_DuplicateLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    multiply_by: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_DuplicateLatents``.

    Display name: Repeat Latents 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/latent

    Repeat Latents 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Append copies of a latent to itself so it repeats</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="latents" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">latents: The latents to be repeated</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The latent with repeats</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of latents in the output. Equal to the length of the input latent * multiply_by</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="multiply_by" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">multiply_by: Controls the number of times the latent should repeat. 1, the default, means no change.</div></div></div></div></div>

    Returns: LATENT, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_DuplicateLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if multiply_by is not _UNSET:
        _kwargs['multiply_by'] = multiply_by
    _kwargs.update(_extras)
    return node(wf, 'VHS_DuplicateLatents', _id, pass_raw=pass_raw, **_kwargs)

def VHS_DuplicateMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    multiply_by: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_DuplicateMasks``.

    Display name: Repeat Masks 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/mask

    Repeat Masks 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Append copies of a mask to itself so it repeats</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="masks" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">masks: The masks to be repeated</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The mask with repeats</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of mask in the output. Equal to the length of the input mask * multiply_by</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="multiply_by" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">multiply_by: Controls the number of times the mask should repeat. 1, the default, means no change.</div></div></div></div></div>

    Returns: MASK, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_DuplicateMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if multiply_by is not _UNSET:
        _kwargs['multiply_by'] = multiply_by
    _kwargs.update(_extras)
    return node(wf, 'VHS_DuplicateMasks', _id, pass_raw=pass_raw, **_kwargs)

def VHS_GetImageCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_GetImageCount``.

    Display name: Get Image Count 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/image

    Get Image Count 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Return the number of images in an input as an INT</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="images" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">images: The input image</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of images in the input</div></div></div></div></div>

    Returns: count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_GetImageCount() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'VHS_GetImageCount', _id, pass_raw=pass_raw, **_kwargs)

def VHS_GetLatentCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_GetLatentCount``.

    Display name: Get Latent Count 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/latent

    Get Latent Count 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Return the number of latents in an input as an INT</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="latents" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">latents: The input latent</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of latents in the input</div></div></div></div></div>

    Returns: count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_GetLatentCount() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'VHS_GetLatentCount', _id, pass_raw=pass_raw, **_kwargs)

def VHS_GetMaskCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_GetMaskCount``.

    Display name: Get Mask Count 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/mask

    Get Mask Count 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Return the number of masks in an input as an INT</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="masks" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">masks: The input mask</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of masks in the input</div></div></div></div></div>

    Returns: count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_GetMaskCount() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'VHS_GetMaskCount', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_file: str | _Omitted = _UNSET,
    duration: float | _Omitted = _UNSET,
    seek_seconds: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadAudio``.

    Display name: Load Audio (Path)🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/audio

    Load Audio (Path) 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads an audio file from an arbitrary path</div></div><div style="font-size: 0.8em"><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The loaded audio</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="audio_file" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio_file: The audio file to be loaded.<div style="font-size: 1em">This is a VHS_PATH input. When edited, it provides a list of possible valid files or directories</div><div style="font-size: 1em"><video preload="none" src=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/assets/4284322/729b7185-1fca-41d8-bc8d-a770bb2a5ce6 muted loop controls controlslist="nodownload noremoteplayback noplaybackrate" style="width: 0px; min-width: 100%" class="VHS_loopedvideo"></div><div style="font-size: 1em">The current top-most completion may be selected with Tab</div><div style="font-size: 1em">You can navigate up a directory by pressing Ctrl+B (or Ctrl+W if supported by browser)</div><div style="font-size: 1em">The filter on suggested file types can be disabled by pressing Ctrl+G.</div><div style="font-size: 1em">If converted to an input, this functions as a string</div></div></div><div vhs_title="seek_seconds" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">seek_seconds: An offset from the start of the sound file that the audio should start from</div></div></div></div></div>

    Returns: audio, duration

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_file is not _UNSET:
        _kwargs['audio_file'] = audio_file
    if duration is not _UNSET:
        _kwargs['duration'] = duration
    if seek_seconds is not _UNSET:
        _kwargs['seek_seconds'] = seek_seconds
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadAudio', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadAudioUpload(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    duration: float | _Omitted = _UNSET,
    start_time: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadAudioUpload``.

    Display name: Load Audio (Upload)🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/audio

    Load Audio (Upload) 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads an audio file from the input directory</div></div><div style="font-size: 0.8em">Very similar in functionality to the built-in LoadAudio. It was originally added before VHS swapped to use Comfy's internal AUDIO format, but provides the additional options for start time and duration</div><div style="font-size: 0.8em"><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The loaded audio</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The audio file to be loaded.</div></div><div vhs_title="start_time" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">start_time: An offset from the start of the sound file that the audio should start from</div></div><div vhs_title="duration" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">duration: A maximum limit for the audio. Disabled if 0</div></div><div vhs_title="choose audio to upload" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">choose audio to upload: An upload button is provided to upload an audio file to the input folder</div></div></div></div></div>

    Returns: audio, duration

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadAudioUpload() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if duration is not _UNSET:
        _kwargs['duration'] = duration
    if start_time is not _UNSET:
        _kwargs['start_time'] = start_time
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadAudioUpload', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadImagePath(
    *args: VibeWorkflow,
    _id: str | None = None,
    custom_height: int | _Omitted = _UNSET,
    custom_width: int | _Omitted = _UNSET,
    image: str | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadImagePath``.

    Display name: Load Image (Path) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Image (Path) 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Load a single image from a given path</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: (optional) If provided the node will output latents instead of images.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="MASK" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK: The alpha channel of the loaded images.</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="image" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">image: The image file to be loaded.<div style="font-size: 1em">This is a VHS_PATH input. When edited, it provides a list of possible valid files or directories</div><div style="font-size: 1em"><video preload="none" src=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/assets/4284322/729b7185-1fca-41d8-bc8d-a770bb2a5ce6 muted loop controls controlslist="nodownload noremoteplayback noplaybackrate" style="width: 0px; min-width: 100%" class="VHS_loopedvideo"></div><div style="font-size: 1em">The current top-most completion may be selected with Tab</div><div style="font-size: 1em">You can navigate up a directory by pressing Ctrl+B (or Ctrl+W if supported by browser)</div><div style="font-size: 1em">The filter on suggested file types can be disabled by pressing Ctrl+G.</div><div style="font-size: 1em">If converted to an input, this functions as a string</div></div></div><div vhs_title="force_size" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_size: Allows for conveniently scaling the input without requiring an additional node. Provides options to maintain aspect ratio or conveniently target common training formats for Animate Diff<div style="font-size: 1em"><div vhs_title="custom_width" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_width: Allows for an arbitrary width to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="custom_height" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_height: Allows for an arbitrary height to be entered, cropping to maintain aspect ratio if both are set</div></div></div></div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. Will only be shown if Advanced Previews is enabled. This preview will reflect the image_load_cap, skip_first_images, and select_every_nth values chosen. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, mask

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadImagePath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if custom_height is not _UNSET:
        _kwargs['custom_height'] = custom_height
    if custom_width is not _UNSET:
        _kwargs['custom_width'] = custom_width
    if image is not _UNSET:
        _kwargs['image'] = image
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadImagePath', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    directory: Literal['3d'] | _Omitted = _UNSET,
    image_load_cap: int | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_images: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadImages``.

    Display name: Load Images (Upload) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Images 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads a sequence of images from a subdirectory of the input folder</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long sequences into sub batches. See the documentation for Meta Batch Manager</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="MASK" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK: The alpha channel of the loaded images.</div></div><div vhs_title="frame_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_count: The length of images just returned</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="directory" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">directory: The directory images will be loaded from. Filtered to process jpg, png, ppm, bmp, tif, and webp files</div></div><div vhs_title="image_load_cap" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">image_load_cap: The maximum number of images to load. If 0, all images are loaded.</div></div><div vhs_title="start_time" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">start_time: A timestamp, in seconds from the start of the video, to start loading frames from. </div></div><div vhs_title="choose folder to upload" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">choose folder to upload: An upload button is provided to upload a local folder containing images to the input folder</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. Will only be shown if Advanced Previews is enabled. This preview will reflect the image_load_cap, skip_first_images, and select_every_nth values chosen. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, MASK, frame_count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if directory is not _UNSET:
        _kwargs['directory'] = directory
    if image_load_cap is not _UNSET:
        _kwargs['image_load_cap'] = image_load_cap
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_images is not _UNSET:
        _kwargs['skip_first_images'] = skip_first_images
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadImages', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadImagesPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    directory: str | _Omitted = _UNSET,
    image_load_cap: int | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_images: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadImagesPath``.

    Display name: Load Images (Path) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Images (Path) 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads a sequence of images from an arbitrary path</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long sequences into sub batches. See the documentation for Meta Batch Manager</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="MASK" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK: The alpha channel of the loaded images.</div></div><div vhs_title="frame_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_count: The length of images just returned</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="directory" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">directory: The directory images will be loaded from. Filtered to process jpg, png, ppm, bmp, tif, and webp files<div style="font-size: 1em">This is a VHS_PATH input. When edited, it provides a list of possible valid files or directories</div><div style="font-size: 1em"><video preload="none" src=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/assets/4284322/729b7185-1fca-41d8-bc8d-a770bb2a5ce6 muted loop controls controlslist="nodownload noremoteplayback noplaybackrate" style="width: 0px; min-width: 100%" class="VHS_loopedvideo"></div><div style="font-size: 1em">The current top-most completion may be selected with Tab</div><div style="font-size: 1em">You can navigate up a directory by pressing Ctrl+B (or Ctrl+W if supported by browser)</div><div style="font-size: 1em">The filter on suggested file types can be disabled by pressing Ctrl+G.</div><div style="font-size: 1em">If converted to an input, this functions as a string</div></div></div><div vhs_title="image_load_cap" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">image_load_cap: The maximum number of images to load. If 0, all images are loaded.</div></div><div vhs_title="skip_first_images" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_images: A number of images which are discarded before producing output.</div></div><div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: Keeps only the first of every n frames and discard the rest.</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. Will only be shown if Advanced Previews is enabled. This preview will reflect the image_load_cap, skip_first_images, and select_every_nth values chosen. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, MASK, frame_count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadImagesPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if directory is not _UNSET:
        _kwargs['directory'] = directory
    if image_load_cap is not _UNSET:
        _kwargs['image_load_cap'] = image_load_cap
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_images is not _UNSET:
        _kwargs['skip_first_images'] = skip_first_images
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadImagesPath', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    custom_height: int | _Omitted = _UNSET,
    custom_width: int | _Omitted = _UNSET,
    force_rate: float | _Omitted = _UNSET,
    frame_load_cap: int | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_frames: int | _Omitted = _UNSET,
    video: Any | _Omitted = _UNSET,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadVideo``.

    Display name: Load Video (Upload) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Video 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads a video from the input folder</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long sequences into sub batches. See the documentation for Meta Batch Manager</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: (optional) If provided the node will output latents instead of images. This drastically reduces the required RAM (not VRAM) when working with long (100+ frames) sequences<div style="font-size: 1em">Using this is strongly encouraged unless connecting to a node that requires a blue image connection such as Apply Controllnet</div></div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="frame_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_count: The length of images just returned</div></div><div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The audio from the loaded video</div></div><div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: Exposes additional info about the video such as the source frame rate, or the total length</div></div><div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The loaded images pre-converted to latents. Only available when a vae is connected</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="video" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video: The video file to be loaded. Lists all files with a video extension in the ComfyUI/Input folder</div></div><div vhs_title="force_rate" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_rate: Drops or duplicates frames so that the produced output has the target frame rate. Many motion models are trained on videos of a specific frame rate and will give better results if input matches that frame rate. If set to 0, all frames are returned. May give unusual results with inputs that have a variable frame rate like animated gifs. Reducing this value can also greatly reduce the execution time and memory requirements.</div></div><div vhs_title="force_size" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_size: Previously was used to provide suggested resolutions. Instead, custom_width and custom_height can be disabled by setting to 0.</div></div><div vhs_title="custom_width" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_width: Allows for an arbitrary width to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="custom_height" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_height: Allows for an arbitrary height to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="frame_load_cap" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_load_cap: The maximum number of frames to load. If 0, all frames are loaded.</div></div><div vhs_title="skip_first_frames" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_frames: A number of frames which are discarded before producing output.</div></div><div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: Similar to frame rate. Keeps only the first of every n frames and discard the rest. Has better compatibility with variable frame rate inputs such as gifs. When combined with force_rate, select_every_nth_applies after force_rate so the resulting output has a frame rate equivalent to force_rate/select_every_nth. select_every_nth does not apply to skip_first_frames</div></div><div vhs_title="format" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">format: Updates other widgets so that only values supported by the given format can be entered and provides recommended defaults.</div></div><div vhs_title="choose video to upload" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">choose video to upload: An upload button is provided to upload local files to the input folder</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. If advanced previews is enabled, this preview will reflect the frame_load_cap, force_rate, skip_first_frames, and select_every_nth values chosen. If the video has audio, it will also be previewed when moused over. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, frame_count, audio, video_info

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if custom_height is not _UNSET:
        _kwargs['custom_height'] = custom_height
    if custom_width is not _UNSET:
        _kwargs['custom_width'] = custom_width
    if force_rate is not _UNSET:
        _kwargs['force_rate'] = force_rate
    if frame_load_cap is not _UNSET:
        _kwargs['frame_load_cap'] = frame_load_cap
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_frames is not _UNSET:
        _kwargs['skip_first_frames'] = skip_first_frames
    if video is not _UNSET:
        _kwargs['video'] = video
    if format is not _UNSET:
        _kwargs['format'] = format
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadVideo', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadVideoFFmpeg(
    *args: VibeWorkflow,
    _id: str | None = None,
    custom_height: int | _Omitted = _UNSET,
    custom_width: int | _Omitted = _UNSET,
    force_rate: float | _Omitted = _UNSET,
    frame_load_cap: int | _Omitted = _UNSET,
    start_time: float | _Omitted = _UNSET,
    video: Any | _Omitted = _UNSET,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadVideoFFmpeg``.

    Display name: Load Video FFmpeg (Upload) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Video FFmpeg 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads a video from the input folder using ffmpeg instead of opencv</div></div><div style="font-size: 0.8em">Provides faster execution speed, transparency support, and allows specifying start time in seconds</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long sequences into sub batches. See the documentation for Meta Batch Manager</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: (optional) If provided the node will output latents instead of images. This drastically reduces the required RAM (not VRAM) when working with long (100+ frames) sequences<div style="font-size: 1em">Using this is strongly encouraged unless connecting to a node that requires a blue image connection such as Apply Controllnet</div></div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="mask" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">mask: Transparency data from the loaded video</div></div><div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The audio from the loaded video</div></div><div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: Exposes additional info about the video such as the source frame rate, or the total length</div></div><div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The loaded images pre-converted to latents. Only available when a vae is connected</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="video" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video: The video file to be loaded. Lists all files with a video extension in the ComfyUI/Input folder</div></div><div vhs_title="force_rate" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_rate: Drops or duplicates frames so that the produced output has the target frame rate. Many motion models are trained on videos of a specific frame rate and will give better results if input matches that frame rate. If set to 0, all frames are returned. May give unusual results with inputs that have a variable frame rate like animated gifs. Reducing this value can also greatly reduce the execution time and memory requirements.</div></div><div vhs_title="force_size" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_size: Previously was used to provide suggested resolutions. Instead, custom_width and custom_height can be disabled by setting to 0.</div></div><div vhs_title="custom_width" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_width: Allows for an arbitrary width to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="custom_height" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_height: Allows for an arbitrary height to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="frame_load_cap" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_load_cap: The maximum number of frames to load. If 0, all frames are loaded.</div></div><div vhs_title="start_time" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">start_time: A timestamp, in seconds from the start of the video, to start loading frames from. </div></div><div vhs_title="format" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">format: Updates other widgets so that only values supported by the given format can be entered and provides recommended defaults.</div></div><div vhs_title="choose video to upload" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">choose video to upload: An upload button is provided to upload local files to the input folder</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. If advanced previews is enabled, this preview will reflect the frame_load_cap, force_rate, skip_first_frames, and select_every_nth values chosen. If the video has audio, it will also be previewed when moused over. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, mask, audio, video_info

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadVideoFFmpeg() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if custom_height is not _UNSET:
        _kwargs['custom_height'] = custom_height
    if custom_width is not _UNSET:
        _kwargs['custom_width'] = custom_width
    if force_rate is not _UNSET:
        _kwargs['force_rate'] = force_rate
    if frame_load_cap is not _UNSET:
        _kwargs['frame_load_cap'] = frame_load_cap
    if start_time is not _UNSET:
        _kwargs['start_time'] = start_time
    if video is not _UNSET:
        _kwargs['video'] = video
    if format is not _UNSET:
        _kwargs['format'] = format
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadVideoFFmpeg', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadVideoFFmpegPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    custom_height: int | _Omitted = _UNSET,
    custom_width: int | _Omitted = _UNSET,
    force_rate: float | _Omitted = _UNSET,
    frame_load_cap: int | _Omitted = _UNSET,
    start_time: float | _Omitted = _UNSET,
    video: str | _Omitted = _UNSET,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadVideoFFmpegPath``.

    Display name: Load Video FFmpeg (Path) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Video FFmpeg (Path) 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads a video from an arbitrary path using ffmpeg instead of opencv</div></div><div style="font-size: 0.8em">Provides faster execution speed, transparency support, and allows specifying start time in seconds</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long sequences into sub batches. See the documentation for Meta Batch Manager</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: (optional) If provided the node will output latents instead of images. This drastically reduces the required RAM (not VRAM) when working with long (100+ frames) sequences<div style="font-size: 1em">Using this is strongly encouraged unless connecting to a node that requires a blue image connection such as Apply Controllnet</div></div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="mask" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">mask: Transparency data from the loaded video</div></div><div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The audio from the loaded video</div></div><div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: Exposes additional info about the video such as the source frame rate, or the total length</div></div><div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The loaded images pre-converted to latents. Only available when a vae is connected</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="video" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video: The video file to be loaded.<div style="font-size: 1em">You can also select an image to load it as a single frame</div><div style="font-size: 1em">This is a VHS_PATH input. When edited, it provides a list of possible valid files or directories</div><div style="font-size: 1em"><video preload="none" src=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/assets/4284322/729b7185-1fca-41d8-bc8d-a770bb2a5ce6 muted loop controls controlslist="nodownload noremoteplayback noplaybackrate" style="width: 0px; min-width: 100%" class="VHS_loopedvideo"></div><div style="font-size: 1em">The current top-most completion may be selected with Tab</div><div style="font-size: 1em">You can navigate up a directory by pressing Ctrl+B (or Ctrl+W if supported by browser)</div><div style="font-size: 1em">The filter on suggested file types can be disabled by pressing Ctrl+G.</div><div style="font-size: 1em">If converted to an input, this functions as a string</div></div></div><div vhs_title="force_rate" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_rate: Drops or duplicates frames so that the produced output has the target frame rate. Many motion models are trained on videos of a specific frame rate and will give better results if input matches that frame rate. If set to 0, all frames are returned. May give unusual results with inputs that have a variable frame rate like animated gifs. Reducing this value can also greatly reduce the execution time and memory requirements.</div></div><div vhs_title="force_size" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_size: Previously was used to provide suggested resolutions. Instead, custom_width and custom_height can be disabled by setting to 0.</div></div><div vhs_title="custom_width" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_width: Allows for an arbitrary width to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="custom_height" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_height: Allows for an arbitrary height to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="frame_load_cap" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_load_cap: The maximum number of frames to load. If 0, all frames are loaded.</div></div><div vhs_title="skip_first_frames" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_frames: A number of frames which are discarded before producing output.</div></div><div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: Similar to frame rate. Keeps only the first of every n frames and discard the rest. Has better compatibility with variable frame rate inputs such as gifs. When combined with force_rate, select_every_nth_applies after force_rate so the resulting output has a frame rate equivalent to force_rate/select_every_nth. select_every_nth does not apply to skip_first_frames</div></div><div vhs_title="format" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">format: Updates other widgets so that only values supported by the given format can be entered and provides recommended defaults.</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. Will only be shown if Advanced Previews is enabled. This preview will reflect the frame_load_cap, force_rate, skip_first_frames, and select_every_nth values chosen. If the video has audio, it will also be previewed when moused over. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, mask, audio, video_info

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadVideoFFmpegPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if custom_height is not _UNSET:
        _kwargs['custom_height'] = custom_height
    if custom_width is not _UNSET:
        _kwargs['custom_width'] = custom_width
    if force_rate is not _UNSET:
        _kwargs['force_rate'] = force_rate
    if frame_load_cap is not _UNSET:
        _kwargs['frame_load_cap'] = frame_load_cap
    if start_time is not _UNSET:
        _kwargs['start_time'] = start_time
    if video is not _UNSET:
        _kwargs['video'] = video
    if format is not _UNSET:
        _kwargs['format'] = format
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadVideoFFmpegPath', _id, pass_raw=pass_raw, **_kwargs)

def VHS_LoadVideoPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    custom_height: int | _Omitted = _UNSET,
    custom_width: int | _Omitted = _UNSET,
    force_rate: float | _Omitted = _UNSET,
    frame_load_cap: int | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_frames: int | _Omitted = _UNSET,
    video: str | _Omitted = _UNSET,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_LoadVideoPath``.

    Display name: Load Video (Path) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Load Video (Path) 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Loads a video from an arbitrary path</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long sequences into sub batches. See the documentation for Meta Batch Manager</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: (optional) If provided the node will output latents instead of images. This drastically reduces the required RAM (not VRAM) when working with long (100+ frames) sequences<div style="font-size: 1em">Using this is strongly encouraged unless connecting to a node that requires a blue image connection such as Apply Controllnet</div></div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The loaded images</div></div><div vhs_title="frame_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_count: The length of images just returned</div></div><div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: The audio from the loaded video</div></div><div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: Exposes additional info about the video such as the source frame rate, or the total length</div></div><div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The loaded images pre-converted to latents. Only available when a vae is connected</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="video" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video: The video file to be loaded.<div style="font-size: 1em">You can also select an image to load it as a single frame</div><div style="font-size: 1em">This is a VHS_PATH input. When edited, it provides a list of possible valid files or directories</div><div style="font-size: 1em"><video preload="none" src=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/assets/4284322/729b7185-1fca-41d8-bc8d-a770bb2a5ce6 muted loop controls controlslist="nodownload noremoteplayback noplaybackrate" style="width: 0px; min-width: 100%" class="VHS_loopedvideo"></div><div style="font-size: 1em">The current top-most completion may be selected with Tab</div><div style="font-size: 1em">You can navigate up a directory by pressing Ctrl+B (or Ctrl+W if supported by browser)</div><div style="font-size: 1em">The filter on suggested file types can be disabled by pressing Ctrl+G.</div><div style="font-size: 1em">If converted to an input, this functions as a string</div></div></div><div vhs_title="force_rate" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_rate: Drops or duplicates frames so that the produced output has the target frame rate. Many motion models are trained on videos of a specific frame rate and will give better results if input matches that frame rate. If set to 0, all frames are returned. May give unusual results with inputs that have a variable frame rate like animated gifs. Reducing this value can also greatly reduce the execution time and memory requirements.</div></div><div vhs_title="force_size" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">force_size: Previously was used to provide suggested resolutions. Instead, custom_width and custom_height can be disabled by setting to 0.</div></div><div vhs_title="custom_width" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_width: Allows for an arbitrary width to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="custom_height" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">custom_height: Allows for an arbitrary height to be entered, cropping to maintain aspect ratio if both are set</div></div><div vhs_title="frame_load_cap" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_load_cap: The maximum number of frames to load. If 0, all frames are loaded.</div></div><div vhs_title="skip_first_frames" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_frames: A number of frames which are discarded before producing output.</div></div><div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: Similar to frame rate. Keeps only the first of every n frames and discard the rest. Has better compatibility with variable frame rate inputs such as gifs. When combined with force_rate, select_every_nth_applies after force_rate so the resulting output has a frame rate equivalent to force_rate/select_every_nth. select_every_nth does not apply to skip_first_frames</div></div><div vhs_title="format" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">format: Updates other widgets so that only values supported by the given format can be entered and provides recommended defaults.</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the selected video input. Will only be shown if Advanced Previews is enabled. This preview will reflect the frame_load_cap, force_rate, skip_first_frames, and select_every_nth values chosen. If the video has audio, it will also be previewed when moused over. Additional preview options can be accessed with right click.</div></div></div></div></div>

    Returns: IMAGE, frame_count, audio, video_info

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_LoadVideoPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if custom_height is not _UNSET:
        _kwargs['custom_height'] = custom_height
    if custom_width is not _UNSET:
        _kwargs['custom_width'] = custom_width
    if force_rate is not _UNSET:
        _kwargs['force_rate'] = force_rate
    if frame_load_cap is not _UNSET:
        _kwargs['frame_load_cap'] = frame_load_cap
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_frames is not _UNSET:
        _kwargs['skip_first_frames'] = skip_first_frames
    if video is not _UNSET:
        _kwargs['video'] = video
    if format is not _UNSET:
        _kwargs['format'] = format
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VHS_LoadVideoPath', _id, pass_raw=pass_raw, **_kwargs)

def VHS_MergeImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    images_A: Any | _Omitted = _UNSET,
    images_B: Any | _Omitted = _UNSET,
    crop: Literal['disabled', 'center'] | _Omitted = _UNSET,
    merge_strategy: Literal['match A', 'match B', 'match smaller', 'match larger'] | _Omitted = _UNSET,
    scale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_MergeImages``.

    Display name: Merge Images 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/image

    Merge Images 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Combine two groups of images into a single group of images</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="images_A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">images_A: The first group of images</div></div><div vhs_title="images_B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">images_B: The first group of images</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The combined group of images</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The length of the combined group</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="merge_strategy" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">merge_strategy: Determines what the output resolution will be if input resolutions don't match<div style="font-size: 1em"><div vhs_title="match A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match A: Always use the resolution for A</div></div><div vhs_title="match B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match B: Always use the resolution for B</div></div><div vhs_title="match smaller" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match smaller: Pick the smaller resolution by area</div></div><div vhs_title="match larger" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match larger: Pick the larger resolution by area</div></div></div></div></div><div vhs_title="scale_method" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">scale_method: Determines what method to use if scaling is required</div></div><div vhs_title="crop" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">crop: When sizes don't match, should the resized image have it's aspect ratio changed, or be cropped to maintain aspect ratio</div></div></div></div></div>

    Returns: IMAGE, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_MergeImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images_A is not _UNSET:
        _kwargs['images_A'] = images_A
    if images_B is not _UNSET:
        _kwargs['images_B'] = images_B
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if merge_strategy is not _UNSET:
        _kwargs['merge_strategy'] = merge_strategy
    if scale_method is not _UNSET:
        _kwargs['scale_method'] = scale_method
    _kwargs.update(_extras)
    return node(wf, 'VHS_MergeImages', _id, pass_raw=pass_raw, **_kwargs)

def VHS_MergeLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents_A: Any | _Omitted = _UNSET,
    latents_B: Any | _Omitted = _UNSET,
    crop: Literal['disabled', 'center'] | _Omitted = _UNSET,
    merge_strategy: Literal['match A', 'match B', 'match smaller', 'match larger'] | _Omitted = _UNSET,
    scale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_MergeLatents``.

    Display name: Merge Latents 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/latent

    Merge Latents 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Combine two groups of latents into a single group of latents</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="latents_A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">latents_A: The first group of latents</div></div><div vhs_title="latents_B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">latents_B: The first group of latents</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The combined group of latents</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The length of the combined group</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="merge_strategy" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">merge_strategy: Determines what the output resolution will be if input resolutions don't match<div style="font-size: 1em"><div vhs_title="match A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match A: Always use the resolution for A</div></div><div vhs_title="match B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match B: Always use the resolution for B</div></div><div vhs_title="match smaller" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match smaller: Pick the smaller resolution by area</div></div><div vhs_title="match larger" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match larger: Pick the larger resolution by area</div></div></div></div></div><div vhs_title="scale_method" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">scale_method: Determines what method to use if scaling is required</div></div><div vhs_title="crop" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">crop: When sizes don't match, should the resized image have it's aspect ratio changed, or be cropped to maintain aspect ratio</div></div></div></div></div>

    Returns: LATENT, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_MergeLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents_A is not _UNSET:
        _kwargs['latents_A'] = latents_A
    if latents_B is not _UNSET:
        _kwargs['latents_B'] = latents_B
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if merge_strategy is not _UNSET:
        _kwargs['merge_strategy'] = merge_strategy
    if scale_method is not _UNSET:
        _kwargs['scale_method'] = scale_method
    _kwargs.update(_extras)
    return node(wf, 'VHS_MergeLatents', _id, pass_raw=pass_raw, **_kwargs)

def VHS_MergeMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask_A: Any | _Omitted = _UNSET,
    mask_B: Any | _Omitted = _UNSET,
    crop: Literal['disabled', 'center'] | _Omitted = _UNSET,
    merge_strategy: Literal['match A', 'match B', 'match smaller', 'match larger'] | _Omitted = _UNSET,
    scale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_MergeMasks``.

    Display name: Merge Masks 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/mask

    Merge Masks 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Combine two groups of masks into a single group of masks</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="mask_A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">mask_A: The first group of masks</div></div><div vhs_title="mask_B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">mask_B: The first group of masks</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="MASK" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK: The combined group of masks</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The length of the combined group</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="merge_strategy" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">merge_strategy: Determines what the output resolution will be if input resolutions don't match<div style="font-size: 1em"><div vhs_title="match A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match A: Always use the resolution for A</div></div><div vhs_title="match B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match B: Always use the resolution for B</div></div><div vhs_title="match smaller" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match smaller: Pick the smaller resolution by area</div></div><div vhs_title="match larger" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">match larger: Pick the larger resolution by area</div></div></div></div></div><div vhs_title="scale_method" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">scale_method: Determines what method to use if scaling is required</div></div><div vhs_title="crop" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">crop: When sizes don't match, should the resized image have it's aspect ratio changed, or be cropped to maintain aspect ratio</div></div></div></div></div>

    Returns: MASK, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_MergeMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask_A is not _UNSET:
        _kwargs['mask_A'] = mask_A
    if mask_B is not _UNSET:
        _kwargs['mask_B'] = mask_B
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if merge_strategy is not _UNSET:
        _kwargs['merge_strategy'] = merge_strategy
    if scale_method is not _UNSET:
        _kwargs['scale_method'] = scale_method
    _kwargs.update(_extras)
    return node(wf, 'VHS_MergeMasks', _id, pass_raw=pass_raw, **_kwargs)

def VHS_PruneOutputs(
    *args: VibeWorkflow,
    _id: str | None = None,
    filenames: Any | _Omitted = _UNSET,
    options: Literal['Intermediate', 'Intermediate and Utility'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_PruneOutputs``.

    Display name: Prune Outputs 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Prune Outputs 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Automates deletion of undesired outputs from a Video Combine node.</div></div><div style="font-size: 0.8em">Video Combine produces a number of file outputs in addition to the final output. Some of these, such as a video file without audio included, are implementation limitations and are not feasible to solve. As an alternative, the Prune Outputs node is added to automate the deletion of these file outputs if they are not desired</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="filenames" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">filenames: A connection from a Video Combine node to indicate which outputs should be pruned</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="options" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">options: Which files should be deleted<div style="font-size: 1em"><div vhs_title="Intermediate" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Intermediate: Delete any files that were required for intermediate processing but are not the final output, like the no-audio output file when audio is included</div></div><div vhs_title="Intermediate and Utility" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Intermediate and Utility: Delete all produced files that aren't the final output, including the first frame png</div></div></div></div></div></div></div></div>

    Returns: None

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_PruneOutputs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if filenames is not _UNSET:
        _kwargs['filenames'] = filenames
    if options is not _UNSET:
        _kwargs['options'] = options
    _kwargs.update(_extras)
    return node(wf, 'VHS_PruneOutputs', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectEveryNthImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_images: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectEveryNthImage``.

    Display name: Select Every Nth Image 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/image

    Select Every Nth Image 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Keep only 1 image for every interval</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="images" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">images: The input image</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The output images</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of images in the input</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: The interval from which one frame is kept. 1 means no frames are skipped.</div></div><div vhs_title="skip_first_images" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_images: A number of frames which that is skipped from the start. This applies before select_every_nth. As a result, multiple copies of the node can each have a different skip_first_frames to divide the image into groups</div></div></div></div></div>

    Returns: IMAGE, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectEveryNthImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_images is not _UNSET:
        _kwargs['skip_first_images'] = skip_first_images
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectEveryNthImage', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectEveryNthLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_latents: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectEveryNthLatent``.

    Display name: Select Every Nth Latent 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/latent

    Select Every Nth Latent 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Keep only 1 latent for every interval</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="latents" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">latents: The input latent</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The output latents</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of latents in the input</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: The interval from which one frame is kept. 1 means no frames are skipped.</div></div><div vhs_title="skip_first_latents" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_latents: A number of frames which that is skipped from the start. This applies before select_every_nth. As a result, multiple copies of the node can each have a different skip_first_frames to divide the latent into groups</div></div></div></div></div>

    Returns: LATENT, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectEveryNthLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_latents is not _UNSET:
        _kwargs['skip_first_latents'] = skip_first_latents
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectEveryNthLatent', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectEveryNthMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    skip_first_masks: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectEveryNthMask``.

    Display name: Select Every Nth Mask 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/mask

    Select Every Nth Mask 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Keep only 1 mask for every interval</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="mask" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">mask: The input mask</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="MASK" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK: The output mask</div></div><div vhs_title="count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">count: The number of mask in the input</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="select_every_nth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">select_every_nth: The interval from which one frame is kept. 1 means no frames are skipped.</div></div><div vhs_title="skip_first_mask" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">skip_first_mask: A number of frames which that is skipped from the start. This applies before select_every_nth. As a result, multiple copies of the node can each have a different skip_first_frames to divide the mask into groups</div></div></div></div></div>

    Returns: MASK, count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectEveryNthMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if skip_first_masks is not _UNSET:
        _kwargs['skip_first_masks'] = skip_first_masks
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectEveryNthMask', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectFilename(
    *args: VibeWorkflow,
    _id: str | None = None,
    filenames: Any | _Omitted = _UNSET,
    index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectFilename``.

    Display name: Select Filename 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    VAE Select Filename 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Select a single filename from the VHS_FILENAMES output by a Video Combine and return it as a string</div></div><div style="font-size: 0.8em">Take care when combining this node with Prune Outputs. The VHS_FILENAMES object is immutable and will always contain the full list of output files, but execution order is undefined behavior (currently, Prune Outputs will generally execute first) and SelectFilename may return a path to a file that no longer exists.</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="filenames" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">filenames: A VHS_FILENAMES from a Video Combine node</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="filename" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">filename: A string representation of the full output path for the chosen file</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="index" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">index: The index of which file should be selected. The default, -1, chooses the most complete output</div></div></div></div></div>

    Returns: Filename

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectFilename() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if filenames is not _UNSET:
        _kwargs['filenames'] = filenames
    if index is not _UNSET:
        _kwargs['index'] = index
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectFilename', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    err_if_empty: bool | _Omitted = _UNSET,
    err_if_missing: bool | _Omitted = _UNSET,
    indexes: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectImages``.

    Display name: Select Images 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/image

    Use comma-separated indexes to select items in the given order.

    Returns: IMAGE

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if err_if_empty is not _UNSET:
        _kwargs['err_if_empty'] = err_if_empty
    if err_if_missing is not _UNSET:
        _kwargs['err_if_missing'] = err_if_missing
    if indexes is not _UNSET:
        _kwargs['indexes'] = indexes
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectImages', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    latent: Any | _Omitted = _UNSET,
    err_if_empty: bool | _Omitted = _UNSET,
    err_if_missing: bool | _Omitted = _UNSET,
    indexes: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectLatents``.

    Display name: Select Latents 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/latent

    Use comma-separated indexes to select items in the given order.

    Returns: LATENT

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if err_if_empty is not _UNSET:
        _kwargs['err_if_empty'] = err_if_empty
    if err_if_missing is not _UNSET:
        _kwargs['err_if_missing'] = err_if_missing
    if indexes is not _UNSET:
        _kwargs['indexes'] = indexes
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectLatents', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectLatest(
    *args: VibeWorkflow,
    _id: str | None = None,
    filename_postfix: str | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectLatest``.

    Display name: Select Latest 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Select Latest 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Experimental virtual node to select the most recently modified file from a given folder</div></div><div style="font-size: 0.8em">Assists in the creation of workflows where outputs from one execution are used elsewhere in subsequent executions.</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="filename_prefix" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">filename_prefix: A path which can consist of a combination of folders and a prefix which candidate files must match</div></div><div vhs_title="filename_postfix" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">filename_postfix: A string which chich the selected file must end with. Useful for limiting to a target extension.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="Filename" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Filename: A string representing a file path to the most recently modified file.</div></div></div></div></div>

    Returns: Filename

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectLatest() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if filename_postfix is not _UNSET:
        _kwargs['filename_postfix'] = filename_postfix
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectLatest', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SelectMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    err_if_empty: bool | _Omitted = _UNSET,
    err_if_missing: bool | _Omitted = _UNSET,
    indexes: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SelectMasks``.

    Display name: Select Masks 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/mask

    Use comma-separated indexes to select items in the given order.

    Returns: MASK

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SelectMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if err_if_empty is not _UNSET:
        _kwargs['err_if_empty'] = err_if_empty
    if err_if_missing is not _UNSET:
        _kwargs['err_if_missing'] = err_if_missing
    if indexes is not _UNSET:
        _kwargs['indexes'] = indexes
    _kwargs.update(_extras)
    return node(wf, 'VHS_SelectMasks', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SplitImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    split_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SplitImages``.

    Display name: Split Images 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/image

    Split Images 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Split a set of images into two groups</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="images" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">images: The images to be split.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE_A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE_A: The first group of images</div></div><div vhs_title="A_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">A_count: The number of images in group A. This will be equal to split_index unless the images input has length less than split_index</div></div><div vhs_title="IMAGE_B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE_B: The second group of images</div></div><div vhs_title="B_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">B_count: The number of images in group B</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="split_index" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">split_index: The index of the first latent that will be in the second output groups.</div></div></div></div></div>

    Returns: IMAGE_A, A_count, IMAGE_B, B_count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SplitImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if split_index is not _UNSET:
        _kwargs['split_index'] = split_index
    _kwargs.update(_extras)
    return node(wf, 'VHS_SplitImages', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SplitLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    split_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SplitLatents``.

    Display name: Split Latents 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/latent

    Split Latents 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Split a set of latents into two groups</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="latents" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">latents: The latents to be split.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="LATENT_A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT_A: The first group of latents</div></div><div vhs_title="A_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">A_count: The number of latents in group A. This will be equal to split_index unless the latents input has length less than split_index</div></div><div vhs_title="LATENT_B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT_B: The second group of latents</div></div><div vhs_title="B_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">B_count: The number of latents in group B</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="split_index" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">split_index: The index of the first latent that will be in the second output groups.</div></div></div></div></div>

    Returns: LATENT_A, A_count, LATENT_B, B_count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SplitLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if split_index is not _UNSET:
        _kwargs['split_index'] = split_index
    _kwargs.update(_extras)
    return node(wf, 'VHS_SplitLatents', _id, pass_raw=pass_raw, **_kwargs)

def VHS_SplitMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    split_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_SplitMasks``.

    Display name: Split Masks 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/mask

    Split Masks 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Split a set of masks into two groups</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="mask" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">mask: The masks to be split.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="MASK_A" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK_A: The first group of masks</div></div><div vhs_title="A_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">A_count: The number of masks in group A. This will be equal to split_index unless the mask input has length less than split_index</div></div><div vhs_title="MASK_B" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">MASK_B: The second group of masks</div></div><div vhs_title="B_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">B_count: The number of masks in group B</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="split_index" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">split_index: The index of the first latent that will be in the second output groups.</div></div></div></div></div>

    Returns: MASK_A, A_count, MASK_B, B_count

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_SplitMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if split_index is not _UNSET:
        _kwargs['split_index'] = split_index
    _kwargs.update(_extras)
    return node(wf, 'VHS_SplitMasks', _id, pass_raw=pass_raw, **_kwargs)

def VHS_Unbatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    batched: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_Unbatch``.

    Display name: Unbatch 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Unbatch 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Unbatch a list of items into a single concatenated item</div></div><div style="font-size: 0.8em">Useful for when you want a single video output from a complex workflow</div><div style="font-size: 0.8em">Has no relation to the Meta Batch system of VHS</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="batched" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">batched: Any input which may or may not be batched</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="unbatched" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">unbatched: A single output element. Torch tensors are concatenated across dim 0, all other types are added which functions as concatenation for strings and arrays, but may give undesired results for other types</div></div></div></div></div>

    Returns: unbatched

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_Unbatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if batched is not _UNSET:
        _kwargs['batched'] = batched
    _kwargs.update(_extras)
    return node(wf, 'VHS_Unbatch', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VAEDecodeBatched(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    per_batch: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VAEDecodeBatched``.

    Display name: VAE Decode Batched 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/batched nodes

    VAE Decode Batched 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Decode latents to images with a manually specified batch size</div></div><div style="font-size: 0.8em">Some people have ran into VRAM issues when encoding or decoding large batches of images. As a workaround, this node lets you manually set a batch size when decoding latents.</div><div style="font-size: 0.8em">Unless these issues have been encountered, it is simpler to use the native VAE Decode or to decode from a Video Combine directly</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="samples" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">samples: The latents to be decoded.</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: The VAE to use when decoding.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="IMAGE" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">IMAGE: The decoded images.</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="per_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">per_batch: The maximum number of images to decode in each batch.</div></div></div></div></div>

    Returns: IMAGE

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VAEDecodeBatched() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if per_batch is not _UNSET:
        _kwargs['per_batch'] = per_batch
    _kwargs.update(_extras)
    return node(wf, 'VHS_VAEDecodeBatched', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VAEEncodeBatched(
    *args: VibeWorkflow,
    _id: str | None = None,
    pixels: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    per_batch: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VAEEncodeBatched``.

    Display name: VAE Encode Batched 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/batched nodes

    VAE Encode Batched 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Encode images as latents with a manually specified batch size.</div></div><div style="font-size: 0.8em">Some people have ran into VRAM issues when encoding or decoding large batches of images. As a workaround, this node lets you manually set a batch size when encoding images.</div><div style="font-size: 0.8em">Unless these issues have been encountered, it is simpler to use the native VAE Encode or to encode directly from a Load Video</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="pixels" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">pixels: The images to be encoded.</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: The VAE to use when encoding.</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="LATENT" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">LATENT: The encoded latents.</div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="per_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">per_batch: The maximum number of images to encode in each batch.</div></div></div></div></div>

    Returns: LATENT

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VAEEncodeBatched() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pixels is not _UNSET:
        _kwargs['pixels'] = pixels
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if per_batch is not _UNSET:
        _kwargs['per_batch'] = per_batch
    _kwargs.update(_extras)
    return node(wf, 'VHS_VAEEncodeBatched', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VHSAudioToAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    vhs_audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VHSAudioToAudio``.

    Display name: Legacy VHS_AUDIO to Audio🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢/audio

    Legacy VHS_AUDIO to Audio 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>utility function for compatibility with external nodes</div></div><div style="font-size: 0.8em">VHS used to use an internal VHS_AUDIO format for routing audio between inputs and outputs. This format was intended to only be used internally and was designed with a focus on performance over ease of use. Since ComfyUI now has an internal AUDIO format, VHS now uses this format. However, some custom node packs were made that are external to both ComfyUI and VHS that use VHS_AUDIO. This node was added so that those external nodes can still function</div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="vhs_audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vhs_audio: An input in the legacy VHS_AUDIO format produced by an external node</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="vhs_audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vhs_audio: An output in the standardized AUDIO format</div></div></div></div></div>

    Returns: audio

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VHSAudioToAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vhs_audio is not _UNSET:
        _kwargs['vhs_audio'] = vhs_audio
    _kwargs.update(_extras)
    return node(wf, 'VHS_VHSAudioToAudio', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VideoCombine(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    format: Literal['image/gif', 'image/webp', 'video/16bit-png', 'video/8bit-png', 'video/ProRes', 'video/av1-webm', 'video/ffmpeg-gif', 'video/ffv1-mkv', 'video/h264-mp4', 'video/h265-mp4', 'video/nvenc_av1-mp4', 'video/nvenc_h264-mp4', 'video/nvenc_hevc-mp4', 'video/webm'] | _Omitted = _UNSET,
    frame_rate: float | _Omitted = _UNSET,
    loop_count: int | _Omitted = _UNSET,
    pingpong: bool | _Omitted = _UNSET,
    save_output: bool | _Omitted = _UNSET,
    audio: Any | _Omitted = _UNSET,
    meta_batch: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VideoCombine``.

    Display name: Video Combine 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Video Combine 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Combine an image sequence into a video</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="images" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">images: The images to be turned into a video</div></div><div vhs_title="audio" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">audio: (optional) audio to add to the video</div></div><div vhs_title="meta_batch" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">meta_batch: (optional) Connect to a Meta Batch manager to divide extremely long image sequences into sub batches. See the documentation for Meta Batch Manager</div></div><div vhs_title="vae" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">vae: (optional) If provided, the node will take latents as input instead of images. This drastically reduces the required RAM (not VRAM) when working with long (100+ frames) sequences<div style="font-size: 1em">Unlike on Load Video, this isn't always a strict upgrade over using a standalone VAE Decode.</div><div style="font-size: 1em">If you have multiple Video Combine outputs, then the VAE decode will be performed for each output node increasing execution time</div><div style="font-size: 1em">If you make any change to output settings on the Video Combine (such as changing the output format), the VAE decode will be performed again as the decoded result is (by design) not cached</div></div></div></div></div><div vhs_title="Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Widgets: <div vhs_title="frame_rate" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">frame_rate: The frame rate which will be used for the output video. Consider converting this to an input and connecting this to a Load Video with Video Info(Loaded)->fps. When including audio, failure to properly set this will result in audio desync</div></div><div vhs_title="loop_count" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loop_count: The number of additional times the video should repeat. Can cause performance issues when used with long (100+ frames) sequences</div></div><div vhs_title="filename_prefix" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">filename_prefix: A prefix to add to the name of the output filename. This can include subfolders or format strings.</div></div><div vhs_title="format" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">format: The output format to use. Formats starting with, 'image' are saved with PIL, but formats starting with 'video' utilize the video_formats system. 'video' options require ffmpeg and selecting one frequently adds additional options to the node.</div></div><div vhs_title="pingpong" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">pingpong: Play the video normally, then repeat the video in reverse so that it 'pingpongs' back and forth. This is frequently used to minimize the appearance of skips on very short animations.</div></div><div vhs_title="save_output" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">save_output: Specifies if output files should be saved to the output folder, or the temporary output folder</div></div><div vhs_title="videopreview" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">videopreview: Displays a preview for the processed result. If advanced previews is enabled, the output is always converted to a format viewable from the browser. If the video has audio, it will also be previewed when moused over. Additional preview options can be accessed with right click.</div></div></div></div><div vhs_title="Common Format Widgets" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Common Format Widgets: <div vhs_title="crf" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">crf: Determines how much to prioritize quality over filesize. Numbers vary between formats, but on each format that includes it, the default value provides visually loss less output</div></div><div vhs_title="pix_fmt" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">pix_fmt: The pixel format to use for output. Alternative options will often have higher quality at the cost of increased file size and reduced compatibility with external software.<div style="font-size: 1em"><div vhs_title="yuv420p" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">yuv420p: The most common and default format</div></div><div vhs_title="yuv420p10le" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">yuv420p10le: Use 10 bit color depth. This can improve color quality when combined with 16bit input color depth</div></div><div vhs_title="yuva420p" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">yuva420p: Include transparency in the output video</div></div></div></div></div><div vhs_title="input_color_depth" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">input_color_depth: VHS supports outputting 16bit images. While this produces higher quality output, the difference usually isn't visible without postprocessing and it significantly increases file size and processing time.</div></div><div vhs_title="save_metadata" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">save_metadata: Determines if metadata for the workflow should be included in the output video file</div></div></div></div></div>

    Returns: Filenames

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VideoCombine() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if format is not _UNSET:
        _kwargs['format'] = format
    if frame_rate is not _UNSET:
        _kwargs['frame_rate'] = frame_rate
    if loop_count is not _UNSET:
        _kwargs['loop_count'] = loop_count
    if pingpong is not _UNSET:
        _kwargs['pingpong'] = pingpong
    if save_output is not _UNSET:
        _kwargs['save_output'] = save_output
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if meta_batch is not _UNSET:
        _kwargs['meta_batch'] = meta_batch
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VHS_VideoCombine', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VideoInfo(
    *args: VibeWorkflow,
    _id: str | None = None,
    video_info: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VideoInfo``.

    Display name: Video Info 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Video Info 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Splits information on a video into a numerous outputs</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: A connection to a Load Video node</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="source_fps🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_fps🟨: The frame rate of the video</div></div><div vhs_title="source_frame_count🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_frame_count🟨: How many total frames the video contains before accounting for frame rate or select_every_nth</div></div><div vhs_title="source_duration🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_duration🟨: The length of images just returned in seconds</div></div><div vhs_title="source_width🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_width🟨: The width</div></div><div vhs_title="source_height🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_height🟨: The height</div></div><div vhs_title="loaded_fps🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_fps🟦: The frame rate after accounting for force_rate and select_every_nth. This output is of particular use as it can be connected to the converted frame_rate input of a Video Combine node to ensure audio remains synchronized.</div></div><div vhs_title="loaded_frame_count🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_frame_count🟦: The number of frames returned by the current execution. Identical to the frame_count returned by the node itself</div></div><div vhs_title="loaded_duration🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_duration🟦: The duration in seconds of returned images after accounting for frame_load_cap</div></div><div vhs_title="loaded_width🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_width🟦: The width of the video after scaling. These coordinates are in image space even if loading to latent space</div></div><div vhs_title="loaded_height🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_height🟦: The height of the video after scaling. These coordinates are in image space even if loading to latent space</div></div></div></div></div>

    Returns: source_fps🟨, source_frame_count🟨, source_duration🟨, source_width🟨, source_height🟨, loaded_fps🟦, loaded_frame_count🟦, loaded_duration🟦, loaded_width🟦, loaded_height🟦

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VideoInfo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video_info is not _UNSET:
        _kwargs['video_info'] = video_info
    _kwargs.update(_extras)
    return node(wf, 'VHS_VideoInfo', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VideoInfoLoaded(
    *args: VibeWorkflow,
    _id: str | None = None,
    video_info: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VideoInfoLoaded``.

    Display name: Video Info (Loaded) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Video Info Loaded 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Splits information on a video into a numerous outputs describing the file itself after accounting for load options</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: A connection to a Load Video node</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="loaded_fps🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_fps🟦: The frame rate after accounting for force_rate and select_every_nth. This output is of particular use as it can be connected to the converted frame_rate input of a Video Combine node to ensure audio remains synchronized.</div></div><div vhs_title="loaded_frame_count🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_frame_count🟦: The number of frames returned by the current execution. Identical to the frame_count returned by the node itself</div></div><div vhs_title="loaded_duration🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_duration🟦: The duration in seconds of returned images after accounting for frame_load_cap</div></div><div vhs_title="loaded_width🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_width🟦: The width of the video after scaling. This is the dimension of the corresponding image even if loading as a latent directly</div></div><div vhs_title="loaded_height🟦" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">loaded_height🟦: The height of the video after scaling. This is the dimension of the corresponding image even if loading as a latent directly</div></div></div></div></div>

    Returns: fps🟦, frame_count🟦, duration🟦, width🟦, height🟦

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VideoInfoLoaded() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video_info is not _UNSET:
        _kwargs['video_info'] = video_info
    _kwargs.update(_extras)
    return node(wf, 'VHS_VideoInfoLoaded', _id, pass_raw=pass_raw, **_kwargs)

def VHS_VideoInfoSource(
    *args: VibeWorkflow,
    _id: str | None = None,
    video_info: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``VHS_VideoInfoSource``.

    Display name: Video Info (Source) 🎥🅥🅗🅢

    Category: Video Helper Suite 🎥🅥🅗🅢

    Video Info Source 🎥🅥🅗🅢<div style="font-size: 0.8em"><div id=VHS_shortdesc>Splits information on a video into a numerous outputs describing the file itself without accounting for load options</div></div><div style="font-size: 0.8em"><div vhs_title="Inputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Inputs: <div vhs_title="video_info" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">video_info: A connection to a Load Video node</div></div></div></div><div vhs_title="Outputs" style="display: flex; font-size: 0.8em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">Outputs: <div vhs_title="source_fps🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_fps🟨: The frame rate of the video</div></div><div vhs_title="source_frame_count🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_frame_count🟨: How many total frames the video contains before accounting for frame rate or select_every_nth</div></div><div vhs_title="source_duration🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_duration🟨: The length of images just returned in seconds</div></div><div vhs_title="source_width🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_width🟨: The original width</div></div><div vhs_title="source_height🟨" style="display: flex; font-size: 1em" class="VHS_collapse"><div style="color: #AAA; height: 1.5em;">[<span style="font-family: monospace">-</span>]</div><div style="width: 100%">source_height🟨: The original height</div></div></div></div></div>

    Returns: fps🟨, frame_count🟨, duration🟨, width🟨, height🟨

    Source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
    """
    if len(args) > 1:
        raise TypeError(f"VHS_VideoInfoSource() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video_info is not _UNSET:
        _kwargs['video_info'] = video_info
    _kwargs.update(_extras)
    return node(wf, 'VHS_VideoInfoSource', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['VHS_AudioToVHSAudio', 'VHS_BatchManager', 'VHS_DuplicateImages', 'VHS_DuplicateLatents', 'VHS_DuplicateMasks', 'VHS_GetImageCount', 'VHS_GetLatentCount', 'VHS_GetMaskCount', 'VHS_LoadAudio', 'VHS_LoadAudioUpload', 'VHS_LoadImagePath', 'VHS_LoadImages', 'VHS_LoadImagesPath', 'VHS_LoadVideo', 'VHS_LoadVideoFFmpeg', 'VHS_LoadVideoFFmpegPath', 'VHS_LoadVideoPath', 'VHS_MergeImages', 'VHS_MergeLatents', 'VHS_MergeMasks', 'VHS_PruneOutputs', 'VHS_SelectEveryNthImage', 'VHS_SelectEveryNthLatent', 'VHS_SelectEveryNthMask', 'VHS_SelectFilename', 'VHS_SelectImages', 'VHS_SelectLatents', 'VHS_SelectLatest', 'VHS_SelectMasks', 'VHS_SplitImages', 'VHS_SplitLatents', 'VHS_SplitMasks', 'VHS_Unbatch', 'VHS_VAEDecodeBatched', 'VHS_VAEEncodeBatched', 'VHS_VHSAudioToAudio', 'VHS_VideoCombine', 'VHS_VideoInfo', 'VHS_VideoInfoLoaded', 'VHS_VideoInfoSource']
__vibecomfy_class_types__ = {'VHS_AudioToVHSAudio': 'VHS_AudioToVHSAudio', 'VHS_BatchManager': 'VHS_BatchManager', 'VHS_DuplicateImages': 'VHS_DuplicateImages', 'VHS_DuplicateLatents': 'VHS_DuplicateLatents', 'VHS_DuplicateMasks': 'VHS_DuplicateMasks', 'VHS_GetImageCount': 'VHS_GetImageCount', 'VHS_GetLatentCount': 'VHS_GetLatentCount', 'VHS_GetMaskCount': 'VHS_GetMaskCount', 'VHS_LoadAudio': 'VHS_LoadAudio', 'VHS_LoadAudioUpload': 'VHS_LoadAudioUpload', 'VHS_LoadImagePath': 'VHS_LoadImagePath', 'VHS_LoadImages': 'VHS_LoadImages', 'VHS_LoadImagesPath': 'VHS_LoadImagesPath', 'VHS_LoadVideo': 'VHS_LoadVideo', 'VHS_LoadVideoFFmpeg': 'VHS_LoadVideoFFmpeg', 'VHS_LoadVideoFFmpegPath': 'VHS_LoadVideoFFmpegPath', 'VHS_LoadVideoPath': 'VHS_LoadVideoPath', 'VHS_MergeImages': 'VHS_MergeImages', 'VHS_MergeLatents': 'VHS_MergeLatents', 'VHS_MergeMasks': 'VHS_MergeMasks', 'VHS_PruneOutputs': 'VHS_PruneOutputs', 'VHS_SelectEveryNthImage': 'VHS_SelectEveryNthImage', 'VHS_SelectEveryNthLatent': 'VHS_SelectEveryNthLatent', 'VHS_SelectEveryNthMask': 'VHS_SelectEveryNthMask', 'VHS_SelectFilename': 'VHS_SelectFilename', 'VHS_SelectImages': 'VHS_SelectImages', 'VHS_SelectLatents': 'VHS_SelectLatents', 'VHS_SelectLatest': 'VHS_SelectLatest', 'VHS_SelectMasks': 'VHS_SelectMasks', 'VHS_SplitImages': 'VHS_SplitImages', 'VHS_SplitLatents': 'VHS_SplitLatents', 'VHS_SplitMasks': 'VHS_SplitMasks', 'VHS_Unbatch': 'VHS_Unbatch', 'VHS_VAEDecodeBatched': 'VHS_VAEDecodeBatched', 'VHS_VAEEncodeBatched': 'VHS_VAEEncodeBatched', 'VHS_VHSAudioToAudio': 'VHS_VHSAudioToAudio', 'VHS_VideoCombine': 'VHS_VideoCombine', 'VHS_VideoInfo': 'VHS_VideoInfo', 'VHS_VideoInfoLoaded': 'VHS_VideoInfoLoaded', 'VHS_VideoInfoSource': 'VHS_VideoInfoSource'}
