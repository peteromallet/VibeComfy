"""Build Hivemind workflow_semantics metadata for VibeComfy uploads."""

from __future__ import annotations

import copy
import re
from typing import Any

WORKFLOW_SEMANTICS_VERSION = 1

_MEDIA_TYPES = {"image", "video", "audio", "3d", "multi", "unknown"}
_TASK_TYPES = {
    "text_to_image",
    "image_to_image",
    "image_to_video",
    "text_to_video",
    "video_to_video",
    "audio_to_video",
    "controlnet",
    "compositing",
    "inpainting",
    "upscale",
    "other",
    "unknown",
}
_MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx")
_MODEL_FAMILY_ALIASES: dict[str, tuple[str, ...]] = {
    "ltx": ("ltx", "ltxv", "ltx-video", "ltx video", "lightricks"),
    "wan": ("wanvideo", "wan2", "wan 2", "wan_2", "wan2.1", "wan2_1", "wan2.2", "wan2_2"),
    "hotshot": ("hotshot", "hotshotxl", "hotshot xl"),
    "animatediff": ("animatediff", "animate diff"),
    "sdxl": ("sdxl", "sd_xl", "sd xl", "stable diffusion xl"),
    "sd3": ("sd3", "sd_3", "stable diffusion 3"),
    "flux": ("flux", "flux1", "flux.1"),
    "qwen": ("qwen", "qwen-image", "qwen image"),
    "hunyuan": ("hunyuan", "hyvideo", "hunyuanvideo", "hunyuan video"),
    "cogvideo": ("cogvideo", "cog video"),
    "controlnet": ("controlnet", "control net"),
}
_TASK_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("image_to_video", ("image_to_video", "image-to-video", "img2vid", "i2v", "image to video")),
    ("text_to_video", ("text_to_video", "text-to-video", "txt2vid", "t2v", "text to video")),
    ("video_to_video", ("video_to_video", "video-to-video", "vid2vid", "v2v", "video to video")),
    ("audio_to_video", ("audio_to_video", "audio-to-video", "audio to video")),
    ("image_to_image", ("image_to_image", "image-to-image", "img2img", "i2i", "image to image")),
    ("text_to_image", ("text_to_image", "text-to-image", "txt2img", "t2i", "text to image")),
    ("inpainting", ("inpaint", "inpainting")),
    ("upscale", ("upscale", "upscaler", "upscaling")),
    ("compositing", ("composite", "compositing")),
    ("controlnet", ("controlnet", "control net")),
)
_TASK_DIRECTIONS: dict[str, tuple[list[str], str]] = {
    "text_to_image": (["text"], "image"),
    "image_to_image": (["image"], "image"),
    "image_to_video": (["image"], "video"),
    "text_to_video": (["text"], "video"),
    "video_to_video": (["video"], "video"),
    "audio_to_video": (["audio"], "video"),
}


def enrich_resource_data(data: dict[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(data)
    metadata = _as_dict(enriched.get("metadata"))
    payload = _as_dict(enriched.get("payload"))
    semantics = build_workflow_semantics(
        metadata=metadata,
        payload=payload,
        title=str(enriched.get("title") or ""),
        body=str(enriched.get("body") or ""),
    )
    metadata["workflow_semantics_version"] = WORKFLOW_SEMANTICS_VERSION
    metadata["workflow_semantics"] = semantics
    enriched["metadata"] = metadata
    enriched["body"] = append_semantics_to_body(str(enriched.get("body") or ""), semantics)
    return enriched


def build_workflow_semantics(
    *,
    metadata: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    title: str = "",
    body: str = "",
) -> dict[str, Any]:
    metadata = _as_dict(metadata)
    payload = _as_dict(payload)
    summary = _as_dict(metadata.get("summary") or payload.get("summary"))
    derived_from: list[str] = []
    workflow_json = _first_dict(payload, "workflow_json", "workflow")
    compiled_api = _as_dict(payload.get("compiled_api"))
    if workflow_json:
        derived_from.append("workflow_json")
    if compiled_api:
        derived_from.append("compiled_api")
    if summary:
        derived_from.append("summary")
    if title or body:
        derived_from.append("title_body")
    if metadata.get("asset_kind") == "vibecomfy_ready_template":
        derived_from.append("ready_template_manifest")

    parsed_node_class_multiset = _merge_node_multisets(
        extract_node_class_multiset(compiled_api),
        extract_node_class_multiset(workflow_json),
    )
    fallback_node_class_multiset = _merge_node_multisets(
        metadata.get("node_class_multiset"),
        _nested_get(metadata, ("provenance", "node_class_multiset")),
        _nested_get(payload, ("graph_identity", "node_class_multiset")),
    )
    node_class_multiset = parsed_node_class_multiset or fallback_node_class_multiset
    node_types = sorted(node_class_multiset)
    models = _dedupe(
        _strings(metadata.get("models"))
        + _strings(_nested_get(payload, ("requirements", "models")))
        + _strings(_nested_get(workflow_json, ("requirements", "models")))
        + _extract_model_strings(workflow_json)
        + _extract_model_strings(compiled_api)
    )
    haystack = "\n".join(
        [
            title,
            body,
            str(metadata.get("model_family") or ""),
            " ".join(_strings(metadata.get("model_families"))),
            " ".join(_strings(metadata.get("tags"))),
            " ".join(_strings(summary.get("tags"))),
            " ".join(node_types),
            " ".join(models),
        ]
    )
    media_type = _infer_media_type(metadata, payload, summary, haystack)
    task_type = _infer_task_type(metadata, summary, haystack)
    if media_type == "unknown":
        media_type = _media_from_task(task_type)
    model_families = _infer_model_families(metadata, summary, haystack)
    custom_nodes = _dedupe(
        _strings(metadata.get("custom_nodes"))
        + _strings(_nested_get(payload, ("requirements", "custom_nodes")))
        + _strings(_nested_get(workflow_json, ("requirements", "custom_nodes")))
    )
    aliases = _build_searchable_aliases(
        model_families,
        task_type,
        media_type,
        _strings(metadata.get("tags")) + _strings(summary.get("tags")),
    )
    has_workflow_json = bool(workflow_json) or bool(metadata.get("has_workflow_json"))
    has_rich_nodes = (
        bool(metadata.get("has_rich_nodes"))
        or (isinstance(workflow_json, dict) and isinstance(workflow_json.get("nodes"), dict))
    )
    has_python_source = bool(payload.get("python_source")) or bool(metadata.get("has_python_source"))
    has_compiled_api = bool(compiled_api) or bool(metadata.get("has_compiled_api"))
    parseable = bool(node_class_multiset)
    return {
        "media_type": media_type,
        "task_type": task_type,
        "model_families": model_families,
        "adapter_directions": _adapter_directions(task_type),
        "node_types": node_types,
        "node_class_multiset": node_class_multiset,
        "custom_nodes": custom_nodes,
        "models": models,
        "searchable_aliases": aliases,
        "evidence": {
            "derived_from": _dedupe(derived_from),
            "confidence": _confidence(derived_from, media_type, task_type, parseable),
        },
        "promotion_gates": {
            "has_workflow_json": has_workflow_json,
            "has_rich_nodes": has_rich_nodes,
            "has_python_source": has_python_source,
            "has_compiled_api": has_compiled_api,
            "parseable_workflow": parseable,
        },
    }


def append_semantics_to_body(body: str, semantics: dict[str, Any]) -> str:
    if "Workflow semantics" in body:
        return body
    fields: list[str] = []
    for label, key in (("media", "media_type"), ("task", "task_type")):
        value = semantics.get(key)
        if isinstance(value, str) and value:
            fields.append(f"{label}={value}")
    for label, key in (("families", "model_families"), ("aliases", "searchable_aliases"), ("nodes", "node_types"), ("models", "models")):
        values = _strings(semantics.get(key))[:20]
        if values:
            fields.append(f"{label}=" + ", ".join(values))
    return body + ("\n\n" if body and fields else "") + ("Workflow semantics (rule-based): " + "; ".join(fields) + "." if fields else "")


def extract_node_class_multiset(workflow: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(workflow, dict):
        return counts
    nodes = workflow.get("nodes")
    if isinstance(nodes, dict):
        _count_node_dicts(nodes.values(), counts)
    elif isinstance(nodes, list):
        _count_node_dicts(nodes, counts)
    _count_node_dicts(workflow.values(), counts)
    return dict(sorted(counts.items()))


def _count_node_dicts(nodes: Any, counts: dict[str, int]) -> None:
    for node in nodes:
        if isinstance(node, dict):
            class_type = node.get("class_type") or node.get("type")
            if isinstance(class_type, str) and class_type:
                counts[class_type] = counts.get(class_type, 0) + 1


def _infer_media_type(metadata: dict[str, Any], payload: dict[str, Any], summary: dict[str, Any], haystack: str) -> str:
    for value in (metadata.get("media_type"), summary.get("media_type"), metadata.get("media"), metadata.get("capability")):
        normalized = _normalize_media(value)
        if normalized != "unknown":
            return normalized
    outputs = _strings(_nested_get(payload, ("workflow_json", "outputs")))
    text = (haystack + " " + " ".join(outputs)).casefold()
    if _contains_any(text, ("audio", "sound", "music")) and _contains_any(text, ("video", "movie", "mp4")):
        return "multi"
    if _contains_any(text, ("video", "movie", "mp4", "vhs_videocombine")):
        return "video"
    if _contains_any(text, ("audio", "sound", "music", "wav")):
        return "audio"
    if _contains_any(text, ("3d", "mesh", "pointcloud", "point cloud", "obj", "glb")):
        return "3d"
    if _contains_any(text, ("image", "photo", "png", "jpg", "jpeg", "saveimage")):
        return "image"
    return "unknown"


def _infer_task_type(metadata: dict[str, Any], summary: dict[str, Any], haystack: str) -> str:
    for value in (metadata.get("task_type"), metadata.get("task"), summary.get("task_type"), summary.get("task")):
        normalized = _normalize_task(value)
        if normalized != "unknown":
            return normalized
    text = haystack.casefold()
    for task, aliases in _TASK_ALIASES:
        if _contains_any(text, aliases):
            return task
    return "unknown"


def _infer_model_families(metadata: dict[str, Any], summary: dict[str, Any], haystack: str) -> list[str]:
    families: list[str] = []
    for value in _strings(metadata.get("model_families")) + _strings(metadata.get("model_family")):
        low = value.casefold()
        if low in _MODEL_FAMILY_ALIASES and low not in families:
            families.append(low)
    text = haystack.casefold()
    for family, aliases in _MODEL_FAMILY_ALIASES.items():
        if family not in families and any(_alias_in_text(text, alias) for alias in aliases):
            families.append(family)
    for tag in _strings(summary.get("tags")):
        tag_low = tag.casefold()
        if tag_low in _MODEL_FAMILY_ALIASES and tag_low not in families:
            families.append(tag_low)
    return families


def _adapter_directions(task_type: str) -> list[dict[str, Any]]:
    if task_type not in _TASK_DIRECTIONS:
        return []
    sources, target = _TASK_DIRECTIONS[task_type]
    return [{"from": sources, "to": target, "confidence": "deterministic"}]


def _build_searchable_aliases(model_families: list[str], task_type: str, media_type: str, tags: list[str]) -> list[str]:
    aliases: list[str] = []
    for family in model_families:
        aliases.append(family)
        aliases.extend(_MODEL_FAMILY_ALIASES.get(family, ())[:3])
    aliases.extend([task_type, media_type])
    for task, task_aliases in _TASK_ALIASES:
        if task == task_type:
            aliases.extend(task_aliases[:4])
    aliases.extend(tags)
    return _dedupe([a for a in aliases if a and a != "unknown"])


def _confidence(derived_from: list[str], media_type: str, task_type: str, parseable: bool) -> str:
    if parseable and (media_type != "unknown" or task_type != "unknown"):
        return "high"
    if "summary" in derived_from or "ready_template_manifest" in derived_from:
        return "medium"
    return "low"


def _normalize_media(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    low = value.strip().casefold().replace("-", "_")
    low = {"txt2img": "image", "t2i": "image", "i2v": "video", "t2v": "video", "mesh": "3d"}.get(low, low)
    return low if low in _MEDIA_TYPES else "unknown"


def _normalize_task(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    low = value.strip().casefold().replace("-", "_").replace(" ", "_")
    low = {
        "txt2img": "text_to_image",
        "t2i": "text_to_image",
        "img2img": "image_to_image",
        "i2i": "image_to_image",
        "img2vid": "image_to_video",
        "i2v": "image_to_video",
        "txt2vid": "text_to_video",
        "t2v": "text_to_video",
        "vid2vid": "video_to_video",
        "v2v": "video_to_video",
        "inpaint": "inpainting",
        "upscaling": "upscale",
    }.get(low, low)
    return low if low in _TASK_TYPES else "unknown"


def _media_from_task(task_type: str) -> str:
    if task_type in _TASK_DIRECTIONS:
        return _TASK_DIRECTIONS[task_type][1]
    if task_type in {"controlnet", "inpainting", "upscale"}:
        return "image"
    return "unknown"


def _extract_model_strings(value: Any) -> list[str]:
    return _dedupe([item.strip() for item in _walk(value) if isinstance(item, str) and _looks_like_model(item)])


def _looks_like_model(value: str) -> bool:
    return any(value.strip().casefold().endswith(ext) for ext in _MODEL_EXTENSIONS)


def _walk(value: Any) -> list[Any]:
    items: list[Any] = []
    if isinstance(value, dict):
        for child in value.values():
            items.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(_walk(child))
    else:
        items.append(value)
    return items


def _merge_node_multisets(*values: Any) -> dict[str, int]:
    merged: dict[str, int] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        for key, count in value.items():
            if not isinstance(key, str) or not key:
                continue
            try:
                numeric = int(count)
            except (TypeError, ValueError):
                numeric = 1
            if numeric > 0:
                merged[key] = max(merged.get(key, 0), numeric)
    return dict(sorted(merged.items()))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_dict(container: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = container.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _nested_get(container: Any, keys: tuple[str, ...]) -> Any:
    value = container
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_strings(item))
        return strings
    if isinstance(value, (list, tuple)):
        strings = []
        for item in value:
            strings.extend(_strings(item))
        return strings
    return []


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value).split())
        key = normalized.casefold()
        if normalized and key not in seen:
            out.append(normalized)
            seen.add(key)
    return out


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _alias_in_text(text: str, alias: str) -> bool:
    if re.search(r"[^a-z0-9]", alias):
        return alias.casefold() in text
    return re.search(rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])", text) is not None
