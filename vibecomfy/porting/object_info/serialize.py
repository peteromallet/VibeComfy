"""Serialize a ComfyUI ``object_info`` JSON dump into deterministic per-pack cache files.

The source JSON maps ``class_type`` → dict with ``python_module``, ``input``,
``input_order``, ``output``, ``output_name``, ``output_is_list``, ``category``,
``name``, ``description``, etc.

Output: one file per pack at ``<CACHE_DIR>/<pack>@<version>.json`` plus an
``index.json`` mapping ``class_type`` → cache file basename.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any

from vibecomfy.porting.object_info.consume import (
    CACHE_DIR,
    INDEX_PATH,
    _WIDGET_LIKE_TYPES,
)

# ---------------------------------------------------------------------------
# public helpers
# ---------------------------------------------------------------------------

def pack_key_from_module(python_module: str) -> str:
    """Derive a deterministic pack key from a ``python_module`` string.

    Examples::

        "ComfyUI-KJNodes.nodes.ltxv_nodes"  → "ComfyUI-KJNodes"
        "ComfyUI-LTXVideo"                  → "ComfyUI-LTXVideo"
        "custom_nodes.some_pack.nodes"      → "custom_nodes.some_pack"
        "nodes"                             → "nodes"
        "."                                 → "comfy_core"
    """
    if not python_module or python_module.strip() == ".":
        return "comfy_core"
    parts = python_module.split(".")
    if parts[0] == "custom_nodes" and len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return parts[0]


def _make_cache_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one object_info entry into the cache format."""
    inp: dict[str, dict[str, list]] = raw.get("input", {})
    input_order: dict[str, list[str]] = raw.get("input_order", {})

    # Build ordered inputs: required first, then optional
    ordered_required = list(input_order.get("required", []))
    ordered_optional = list(input_order.get("optional", []))

    all_ordered = ordered_required + ordered_optional

    # Build object_info_widget_order: filter to widget-like types
    widget_order: list[str | None] = []
    for name in all_ordered:
        # Look up the type from required or optional dicts
        type_info = None
        for section in ("required", "optional"):
            if name in inp.get(section, {}):
                type_info = inp[section][name]
                break
        if type_info is None:
            widget_order.append(name)  # best-effort
            continue

        comfy_type = type_info[0] if isinstance(type_info, list) and type_info else None
        # comfy_type can be a string (e.g. "MODEL", "INT") or a list of strings (enum values).
        # If it's a list, it's widget-like (an enum dropdown).
        if isinstance(comfy_type, list):
            widget_order.append(name)
        elif isinstance(comfy_type, str) and comfy_type not in _WIDGET_LIKE_TYPES:
            widget_order.append(name)
        else:
            widget_order.append(None)

    # Outputs
    outputs: list[dict[str, str]] = []
    out_types = raw.get("output", [])
    out_names = raw.get("output_name", [])
    out_is_list = raw.get("output_is_list", [])
    for i, ot in enumerate(out_types):
        outputs.append({
            "type": ot,
            "name": out_names[i] if i < len(out_names) else "",
            "is_list": out_is_list[i] if i < len(out_is_list) else False,
        })

    return OrderedDict({
        "pack": pack_key_from_module(raw.get("python_module", "")),
        "pack_version": "runpod-snapshot",
        "python_module": raw.get("python_module", ""),
        "category": raw.get("category", ""),
        "name": raw.get("name", ""),
        "display_name": raw.get("display_name", ""),
        "description": raw.get("description", ""),
        "inputs": inp,
        "input_order": input_order,
        "input_order_all": all_ordered,
        "object_info_widget_order": widget_order,
        "outputs": outputs,
        "function": raw.get("function", raw.get("name", "")),
    })


def build_cache(
    source_path: str | Path,
    version: str = "runpod-snapshot",
    cache_dir: str | Path | None = None,
) -> tuple[int, int]:
    """Parse *source_path* (an object_info JSON dump) and write per-pack files.

    Returns ``(class_count, pack_count)``.
    """
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"object_info source not found: {source_path}")

    cache_root = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)

    with open(source_path, "r", encoding="utf-8") as fh:
        raw_data: dict[str, dict[str, Any]] = json.load(fh)

    # Group by pack
    packs: dict[str, dict[str, dict[str, Any]]] = {}
    for class_type, entry in sorted(raw_data.items()):
        pk = pack_key_from_module(entry.get("python_module", ""))
        packs.setdefault(pk, OrderedDict())[class_type] = _make_cache_entry(entry)

    # Write per-pack files (deterministically sorted)
    index: dict[str, str] = {}
    for pack_name in sorted(packs):
        pack_entries = packs[pack_name]
        filename = f"{pack_name}@{version}.json"
        filepath = cache_root / filename
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(pack_entries, fh, indent=2, sort_keys=True, ensure_ascii=False)
        for class_type in pack_entries:
            index[class_type] = filename

    # Write index
    with open(cache_root / "index.json", "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, sort_keys=True, ensure_ascii=False)

    return len(raw_data), len(packs)


# ---------------------------------------------------------------------------
# CLI helpers (used by vibecomfy.commands.schemas)
# ---------------------------------------------------------------------------

def refresh_from_source(source_path: str, cache_dir: str | None = None) -> dict[str, Any]:
    """Entry point for ``schemas refresh --source <path>``.

    Returns a summary dict suitable for JSON output.
    """
    class_count, pack_count = build_cache(
        source_path,
        cache_dir=cache_dir,
    )
    return {
        "status": "ok",
        "classes_indexed": class_count,
        "packs_written": pack_count,
        "cache_dir": str(cache_dir or CACHE_DIR),
        "version": "runpod-snapshot",
    }
