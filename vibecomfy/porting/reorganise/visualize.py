from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont


def render_layout_png(ui_json: Mapping[str, Any], path: Path) -> None:
    """Render an abstract colour-block PNG from final UI JSON node positions/sizes and group bounds."""
    nodes = [node for node in ui_json.get("nodes", []) if isinstance(node, Mapping)]
    groups = [group for group in ui_json.get("groups", []) if isinstance(group, Mapping)]
    rects = [_node_rect(node) for node in nodes]
    rects.extend(_group_rect(group) for group in groups if _group_rect(group) is not None)
    rects = [rect for rect in rects if rect is not None]
    if not rects:
        Image.new("RGB", (1200, 800), "white").save(path)
        return

    min_x = min(rect[0] for rect in rects)
    min_y = min(rect[1] for rect in rects)
    max_x = max(rect[0] + rect[2] for rect in rects)
    max_y = max(rect[1] + rect[3] for rect in rects)
    canvas_w, canvas_h = 1600, 1000
    margin = 48
    scale = min(
        (canvas_w - margin * 2) / max(1.0, max_x - min_x),
        (canvas_h - margin * 2) / max(1.0, max_y - min_y),
    )

    def tx(x: float) -> int:
        return round((x - min_x) * scale + margin)

    def ty(y: float) -> int:
        return round((y - min_y) * scale + margin)

    image = Image.new("RGB", (canvas_w, canvas_h), "#f7f7f4")
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()

    for group in groups:
        rect = _group_rect(group)
        if rect is None:
            continue
        x, y, w, h = rect
        color = _group_color(group)
        is_support = _is_support_group(group)
        draw.rounded_rectangle(
            [tx(x), ty(y), tx(x + w), ty(y + h)],
            radius=8 if is_support else 10,
            fill=(*color, 6 if is_support else 48),
            outline=(*color, 38 if is_support else 220),
            width=1 if is_support else 3,
        )
        draw.text(
            (tx(x) + 8, ty(y) + 7),
            str(group.get("title") or "Group")[:30],
            fill=(*color, 70 if is_support else 255),
            font=font,
        )

    for node in nodes:
        rect = _node_rect(node)
        if rect is None:
            continue
        x, y, w, h = rect
        class_type = str(node.get("type") or node.get("class_type") or "Node")
        color = _node_color(class_type)
        is_support = _is_support_node(class_type)
        draw.rectangle(
            [tx(x), ty(y), tx(x + w), ty(y + h)],
            fill=(*color, 36 if is_support else 190),
            outline=(45, 45, 45, 32 if is_support else 170),
            width=1,
        )

    image.save(path)


# ---------------------------------------------------------------------------
# Immediate helpers for render_layout_png (extracted from the structural harness)
# ---------------------------------------------------------------------------


def _node_rect(node: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    pos = node.get("pos")
    size = node.get("size")
    if not (isinstance(pos, list) and len(pos) >= 2):
        return None
    width, height = 260.0, 100.0
    if isinstance(size, list) and len(size) >= 2:
        width = _number(size[0], width)
        height = _number(size[1], height)
    return (_number(pos[0], 0.0), _number(pos[1], 0.0), width, height)


def _group_rect(group: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    bounding = group.get("bounding")
    if not (isinstance(bounding, list) and len(bounding) >= 4):
        return None
    return (
        _number(bounding[0], 0.0),
        _number(bounding[1], 0.0),
        _number(bounding[2], 0.0),
        _number(bounding[3], 0.0),
    )


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _group_color(group: Mapping[str, Any]) -> tuple[int, int, int]:
    explicit = group.get("color")
    if isinstance(explicit, str):
        parsed = _hex_color(explicit)
        if parsed is not None:
            return parsed
    title = str(group.get("title") or "Group")
    if _is_support_group(group):
        return (168, 173, 180)
    palette = {
        "Loaders": (63, 111, 143),
        "Conditioning": (123, 94, 167),
        "Latent": (107, 143, 90),
        "Sampling": (154, 106, 58),
        "Decode": (79, 127, 114),
        "Output": (138, 95, 104),
        "Postprocess": (122, 117, 96),
        "Utility": (104, 111, 120),
        "Custom": (100, 100, 100),
    }
    return palette.get(title, (80, 120, 150))


def _is_support_group(group: Mapping[str, Any]) -> bool:
    title = str(group.get("title") or "Group").lower()
    return "set / get" in title or "helper" in title or "label" in title or "note" in title


def _hex_color(value: str) -> tuple[int, int, int] | None:
    raw = value.strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6:
        return None
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return None


def _node_color(class_type: str) -> tuple[int, int, int]:
    lowered = class_type.lower()
    if any(token in lowered for token in ("loader", "clip", "vae", "unet", "model", "lora")):
        return (80, 125, 165)
    if any(token in lowered for token in ("sampler", "scheduler", "noise", "sigma")):
        return (180, 120, 70)
    if any(token in lowered for token in ("decode", "save", "combine", "output", "preview")):
        return (100, 145, 120)
    if any(token in lowered for token in ("note", "markdown", "setnode", "getnode")):
        return (130, 130, 138)
    return (150, 120, 165)


def _is_support_node(class_type: str) -> bool:
    lowered = class_type.lower()
    return any(token in lowered for token in ("setnode", "getnode", "reroute"))


__all__ = [
    "render_layout_png",
]
