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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.node_packs_lockfile import compute_schema_hash
from vibecomfy.porting.object_info.consume import (
    CACHE_DIR,
    INDEX_PATH,
    _WIDGET_LIKE_TYPES,
)

LEGACY_IMPORT_PACK_VERSION = "legacy-import"
LEGACY_IMPORT_SOURCE_KIND = "legacy_object_info_import"

# ---------------------------------------------------------------------------
# public helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CacheIdentity:
    """Identity metadata stamped onto generated object_info cache entries."""

    pack_slug: str | None = None
    pack_version: str | None = None
    git_commit: str | None = None
    evidence_identity: str | None = None
    source_kind: str = "object_info"


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


def _make_cache_entry(
    raw: dict[str, Any],
    *,
    identity: CacheIdentity,
    schema_hash: str,
) -> dict[str, Any]:
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

    pack_slug = identity.pack_slug or pack_key_from_module(raw.get("python_module", ""))
    pack_version = identity.pack_version or LEGACY_IMPORT_PACK_VERSION

    return OrderedDict({
        "pack": pack_slug,
        "pack_slug": pack_slug,
        "pack_version": pack_version,
        "git_commit": identity.git_commit,
        "evidence_identity": identity.evidence_identity,
        "source_kind": identity.source_kind,
        "schema_hash": schema_hash,
        "class_schema_sha256": schema_hash,
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
    version: str | None = None,
    cache_dir: str | Path | None = None,
    *,
    identity: CacheIdentity | None = None,
    pack_slug: str | None = None,
    pack_version: str | None = None,
    git_commit: str | None = None,
    evidence_identity: str | None = None,
    source_kind: str = LEGACY_IMPORT_SOURCE_KIND,
    full_pack_refresh: bool | set[str] = False,
) -> tuple[int, int]:
    """Parse *source_path* (an object_info JSON dump) and write per-pack files.

    By default this is merge-preserving: classes present in *source_path* are
    refreshed, same-pack classes absent from the source are kept, and packs not
    represented in the source remain indexed unchanged. Pass
    ``full_pack_refresh=True`` (or a set of pack keys) when the source is known
    to be a complete snapshot for the represented pack(s); then stale classes in
    those packs are removed from the rewritten pack file and index.

    Returns ``(class_count, pack_count)``.
    """
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"object_info source not found: {source_path}")

    cache_root = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)

    with open(source_path, "r", encoding="utf-8") as fh:
        raw_data: dict[str, dict[str, Any]] = json.load(fh)

    base_identity = _resolve_identity(
        identity,
        pack_slug=pack_slug,
        pack_version=pack_version or version,
        git_commit=git_commit,
        evidence_identity=evidence_identity or source_path.name,
        source_kind=source_kind,
    )
    effective_version = base_identity.pack_version or LEGACY_IMPORT_PACK_VERSION

    existing_index = _read_existing_index(cache_root)
    existing_entries = _read_existing_entries(cache_root, existing_index)

    # Group by pack
    packs: dict[str, dict[str, dict[str, Any]]] = {}
    raw_packs: dict[str, dict[str, dict[str, Any]]] = {}
    for class_type, entry in sorted(raw_data.items()):
        pk = base_identity.pack_slug or pack_key_from_module(entry.get("python_module", ""))
        raw_packs.setdefault(pk, OrderedDict())[class_type] = entry

    schema_hashes = {
        pack_name: compute_schema_hash(raw_packs[pack_name])
        for pack_name in raw_packs
    }
    for pack_name, raw_entries in sorted(raw_packs.items()):
        pack_identity = _identity_for_pack(base_identity, pack_name)
        packs[pack_name] = OrderedDict(
            (
                class_type,
                _make_cache_entry(
                    entry,
                    identity=pack_identity,
                    schema_hash=schema_hashes[pack_name],
                ),
            )
            for class_type, entry in raw_entries.items()
        )

    # Write per-pack files (deterministically sorted)
    index: dict[str, str] = dict(existing_index)
    for pack_name in sorted(packs):
        filename = f"{pack_name}@{(version or effective_version)}.json"
        pack_entries = _merged_pack_entries(
            pack_name,
            packs[pack_name],
            existing_entries,
            full_refresh=_is_full_pack_refresh(pack_name, full_pack_refresh),
        )
        filepath = cache_root / filename
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(pack_entries, fh, indent=2, sort_keys=True, ensure_ascii=False)
        for class_type, entry in existing_entries.items():
            if entry.get("pack") == pack_name and class_type not in pack_entries:
                index.pop(class_type, None)
        for class_type in sorted(pack_entries):
            index[class_type] = filename

    # Write index
    with open(cache_root / "index.json", "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, sort_keys=True, ensure_ascii=False)

    return len(raw_data), len(packs)


def _read_existing_index(cache_root: Path) -> dict[str, str]:
    index_path = cache_root / "index.json"
    if not index_path.is_file():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(class_type): str(filename) for class_type, filename in data.items()}


def _resolve_identity(
    identity: CacheIdentity | None,
    *,
    pack_slug: str | None,
    pack_version: str | None,
    git_commit: str | None,
    evidence_identity: str | None,
    source_kind: str,
) -> CacheIdentity:
    if identity is None and pack_version is None:
        pack_version = LEGACY_IMPORT_PACK_VERSION
        source_kind = LEGACY_IMPORT_SOURCE_KIND
    elif pack_version is None:
        raise ValueError("authoritative object_info cache writes require an explicit pack_version")
    if identity is None:
        return CacheIdentity(
            pack_slug=pack_slug,
            pack_version=pack_version,
            git_commit=git_commit,
            evidence_identity=evidence_identity,
            source_kind=source_kind,
        )
    return CacheIdentity(
        pack_slug=identity.pack_slug if identity.pack_slug is not None else pack_slug,
        pack_version=identity.pack_version if identity.pack_version is not None else pack_version,
        git_commit=identity.git_commit if identity.git_commit is not None else git_commit,
        evidence_identity=(
            identity.evidence_identity if identity.evidence_identity is not None else evidence_identity
        ),
        source_kind=identity.source_kind or source_kind,
    )


def _identity_for_pack(identity: CacheIdentity, pack_name: str) -> CacheIdentity:
    return CacheIdentity(
        pack_slug=identity.pack_slug or pack_name,
        pack_version=identity.pack_version,
        git_commit=identity.git_commit,
        evidence_identity=identity.evidence_identity,
        source_kind=identity.source_kind,
    )


def _read_existing_entries(cache_root: Path, index: dict[str, str]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    pack_cache: dict[str, dict[str, Any]] = {}
    for class_type, filename in sorted(index.items()):
        if filename not in pack_cache:
            path = cache_root / filename
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            pack_cache[filename] = raw if isinstance(raw, dict) else {}
        entry = pack_cache[filename].get(class_type)
        if isinstance(entry, dict):
            entries[class_type] = entry
    return entries


def _is_full_pack_refresh(pack_name: str, full_pack_refresh: bool | set[str]) -> bool:
    if isinstance(full_pack_refresh, set):
        return pack_name in full_pack_refresh
    return bool(full_pack_refresh)


def _merged_pack_entries(
    pack_name: str,
    refreshed_entries: dict[str, dict[str, Any]],
    existing_entries: dict[str, dict[str, Any]],
    *,
    full_refresh: bool,
) -> dict[str, dict[str, Any]]:
    if full_refresh:
        return OrderedDict((class_type, refreshed_entries[class_type]) for class_type in sorted(refreshed_entries))
    merged: dict[str, dict[str, Any]] = {
        class_type: entry
        for class_type, entry in existing_entries.items()
        if entry.get("pack") == pack_name
    }
    merged.update(refreshed_entries)
    return OrderedDict((class_type, merged[class_type]) for class_type in sorted(merged))


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
        version=LEGACY_IMPORT_PACK_VERSION,
        source_kind=LEGACY_IMPORT_SOURCE_KIND,
    )
    return {
        "status": "ok",
        "classes_indexed": class_count,
        "packs_written": pack_count,
        "cache_dir": str(cache_dir or CACHE_DIR),
        "version": LEGACY_IMPORT_PACK_VERSION,
        "pack_version": LEGACY_IMPORT_PACK_VERSION,
        "source_kind": LEGACY_IMPORT_SOURCE_KIND,
        "authoritative": False,
    }
