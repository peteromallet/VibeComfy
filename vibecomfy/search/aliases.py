from __future__ import annotations

import re

TASK_ALIASES: dict[str, tuple[str, ...]] = {
    "i2v": ("image to video", "image_to_video", "img2vid", "image2video"),
    "t2v": ("text to video", "text_to_video", "txt2vid", "text2video"),
    "t2i": ("text to image", "text_to_image", "txt2img", "text2image"),
    "controlnet": ("control net", "control_net", "conditioning"),
    "wan": ("wan2.1", "wan2.2", "wan video"),
    "ltx": ("ltxv", "ltx-video", "ltx video", "ltx2", "ltx2.3"),
    "audio_reactive": ("audio reactive", "audio-reactive", "audio", "music reactive"),
    "flux": ("flux.1", "flux2", "flux image"),
    "sdxl": ("stable diffusion xl", "stable-diffusion-xl", "sd xl"),
    "qwen": ("qwen image", "qwen-image", "qwen edit"),
    "hunyuan": ("hunyuan video", "hunyuanvideo", "hunyuan-video"),
    "inpaint": ("inpainting", "fill", "masked edit"),
    "outpaint": ("outpainting", "extend image", "image extend"),
}

ADAPT_PATTERN_ALIASES: dict[str, tuple[str, ...]] = {
    "vace": (
        "vace",
        "wan vace",
        "vace control",
        "vace edit",
        "identity travel",
        "subject travel",
        "travel identity",
    ),
    "lora_chain": (
        "lora chain",
        "lora chaining",
        "control lora",
        "iclora",
        "ic lora",
        "i c lora",
        "motion lora",
        "lora control",
    ),
    "low_vram": ("low vram", "low-vram", "low ram", "low-ram", "blockswap", "block swap"),
    "two_pass_refinement": ("two pass", "two-pass", "two stage", "two-stage", "refinement pass"),
    "audio_lipsync": ("audio latent", "audio guide", "lipsync", "lip sync", "voice driven"),
    "depth_pose_guidance": ("depth guidance", "pose guidance", "dwpose", "controlnet depth", "controlnet pose"),
}

SEARCH_ALIASES: dict[str, tuple[str, ...]] = {
    **TASK_ALIASES,
    **ADAPT_PATTERN_ALIASES,
}


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def tokenize(value: object) -> set[str]:
    return {part for part in normalize_text(value).split() if part}


def alias_terms(alias: str) -> set[str]:
    canonical = normalize_text(alias).replace(" ", "_")
    terms = {canonical, normalize_text(alias)}
    for item in SEARCH_ALIASES.get(canonical, ()):
        terms.add(normalize_text(item))
        terms.update(tokenize(item))
    terms.update(tokenize(canonical))
    return {term for term in terms if term}


def matched_aliases(query: str, task: str | None = None) -> list[str]:
    haystack = f"{normalize_text(query)} {normalize_text(task or '')}"
    tokens = tokenize(haystack)
    matches: list[str] = []
    for canonical in SEARCH_ALIASES:
        terms = alias_terms(canonical)
        if canonical in tokens or any(_term_matches(term, haystack, tokens) for term in terms):
            matches.append(canonical)
    return matches


def matched_adapt_patterns(query: str, task: str | None = None) -> list[str]:
    return [alias for alias in matched_aliases(query, task) if alias in ADAPT_PATTERN_ALIASES]


def expanded_terms(query: str, task: str | None = None) -> set[str]:
    terms = tokenize(query)
    if task:
        terms.update(tokenize(task))
    for alias in matched_aliases(query, task):
        terms.update(alias_terms(alias))
    return {term for term in terms if term}


def _term_matches(term: str, haystack: str, tokens: set[str]) -> bool:
    if not term:
        return False
    if " " in term:
        return term in haystack
    return term in tokens
