"""Shared search utilities for CLI and MCP tools."""

from typing import List, Set

# Task aliases map common use-cases to search terms
TASK_ALIASES = {
    # Audio
    "beat detection": ["onset", "bpm", "beat", "drum detector", "audio"],
    "audio reactive": ["audio reactive", "amplitude", "rms", "sound reactive"],
    "fft": ["frequency", "spectral", "spectrum", "fft"],
    # Video generation models
    "ltx": ["ltx", "ltx2", "ltx-2", "lightricks", "ltxvideo", "ltxv", "stg", "gemma", "tiled sampler", "looping"],
    "wan": ["wan", "wan2", "wan2.1", "wan2.2", "wanvideo", "vace"],
    "i2v": ["i2v", "image2video", "image to video", "img2vid", "svd", "stable video"],
    "v2v": ["v2v", "video2video", "video to video", "vid2vid"],
    "t2v": ["t2v", "text2video", "text to video", "txt2vid"],
    "animatediff": ["animatediff", "animate", "motion", "lcm", "hotshotxl"],
    # Image generation
    "controlnet": ["controlnet", "canny", "depth", "pose", "lineart", "openpose"],
    "upscale": ["upscale", "esrgan", "realesrgan", "4x", "super resolution"],
    "interpolation": ["interpolation", "rife", "film", "frame", "tween"],
    "inpaint": ["inpaint", "outpaint", "mask", "fill"],
    "video": ["video", "animate", "animatediff", "frames", "sequence"],
    "lora": ["lora", "loha", "lycoris", "adapter"],
    "flux": ["flux", "bfl", "schnell", "dev", "guidance"],
    "sdxl": ["sdxl", "xl", "1024"],
    "sd15": ["sd15", "sd1.5", "1.5", "512"],
    # Processing
    "face": ["face", "insightface", "faceid", "portrait", "headshot", "reactor"],
    "segmentation": ["segment", "sam", "sam2", "clipseg", "mask", "cutout"],
    "style transfer": ["style", "ipadapter", "ip-adapter", "reference"],
    "text to image": ["txt2img", "text2img", "ksampler", "sampler"],
    "image to image": ["img2img", "image2image", "denoise"],
    "depth": ["depth", "midas", "zoe", "marigold", "depthanything"],
    "pose": ["pose", "openpose", "dwpose", "skeleton"],
    "workflow": ["workflow", "pattern", "pipeline", "recipe"],
    # Effects
    "glitch": ["glitch", "distort", "corrupt", "databend"],
    "dither": ["dither", "halftone", "retro", "pixel"],
    # Klein/Deforum
    "klein": ["klein", "deforum", "flux2", "temporal", "v2v"],
    "deforum": ["deforum", "klein", "motion", "temporal", "warp", "optical flow"],
}


def expand_query(query: str) -> List[str]:
    """Expand query with task aliases.

    Args:
        query: Search query string

    Returns:
        List of expanded search terms
    """
    query_lower = query.lower()
    terms: Set[str] = set(query_lower.split())

    for task, aliases in TASK_ALIASES.items():
        if task in query_lower or any(a in query_lower for a in aliases):
            terms.update(aliases)

    return list(terms)
