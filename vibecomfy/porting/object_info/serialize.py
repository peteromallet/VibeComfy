"""Serialize a ComfyUI ``object_info`` JSON dump into deterministic per-pack cache files.

The source JSON maps ``class_type`` → dict with ``python_module``, ``input``,
``input_order``, ``output``, ``output_name``, ``output_is_list``, ``category``,
``name``, ``description``, etc.

Output: one file per pack at ``<CACHE_DIR>/<pack>@<version>.json`` plus an
``index.json`` mapping ``class_type`` → cache file basename.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses the single-process fallback.
    fcntl = None  # type: ignore[assignment]

from vibecomfy.node_packs import compute_schema_hash
from vibecomfy.porting.object_info.consume import (
    CACHE_DIR,
    _WIDGET_LIKE_TYPES,
)
from vibecomfy.porting.object_info.generation import (
    CURRENT_FILE,
    GENERATIONS_DIR,
    MANIFEST_FILE,
    active_cache_root,
    atomic_write_text,
    read_json,
    safe_cache_filename,
)
from vibecomfy.errors import ObjectInfoCacheCorruptError

LEGACY_IMPORT_PACK_VERSION = "legacy-import"
LEGACY_IMPORT_SOURCE_KIND = "legacy_object_info_import"
_PACK_SLUG_ERROR = "pack_slug must be a single path-safe component"
INDEX_PATH: Path = CACHE_DIR / "index.json"

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


def validate_pack_slug(pack_slug: str) -> str:
    """Validate the owner-controlled pack slug before deriving any filename."""
    if not isinstance(pack_slug, str) or not pack_slug or "\x00" in pack_slug:
        raise ValueError(_PACK_SLUG_ERROR)
    if pack_slug in {".", ".."} or "/" in pack_slug or "\\" in pack_slug:
        raise ValueError(_PACK_SLUG_ERROR)
    if Path(pack_slug).name != pack_slug or Path(pack_slug).is_absolute():
        raise ValueError(_PACK_SLUG_ERROR)
    return pack_slug


def validate_provider_filename(filename: str) -> str:
    """Validate an index-owned provider filename at the publication boundary."""
    if not safe_cache_filename(filename):
        raise ValueError(f"unsafe object_info provider filename: {filename!r}")
    return filename


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
    try:
        raw_data = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid object_info source: {source_path}") from exc
    if not isinstance(raw_data, dict):
        raise ValueError("object_info source must be a JSON object")

    cache_root = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    with _cache_publish_lock(cache_root):
        existing_index, existing_pack_files, existing_provenance = _read_cache_state(cache_root)
        base_identity = _resolve_identity(
            identity,
            pack_slug=pack_slug,
            pack_version=pack_version or version,
            git_commit=git_commit,
            evidence_identity=evidence_identity or source_path.name,
            source_kind=source_kind,
        )
        effective_version = base_identity.pack_version or LEGACY_IMPORT_PACK_VERSION

        raw_packs: dict[str, dict[str, dict[str, Any]]] = {}
        for class_type, entry in sorted(raw_data.items()):
            if not isinstance(class_type, str) or not isinstance(entry, dict):
                raise ValueError("object_info source entries must map class names to objects")
            pk = base_identity.pack_slug or pack_key_from_module(entry.get("python_module", ""))
            validate_pack_slug(pk)
            raw_packs.setdefault(pk, OrderedDict())[class_type] = entry

        packs: dict[str, dict[str, dict[str, Any]]] = {}
        for pack_name, raw_entries in sorted(raw_packs.items()):
            pack_identity = _identity_for_pack(base_identity, pack_name)
            packs[pack_name] = OrderedDict(
                (
                    class_type,
                    _make_cache_entry(
                        entry,
                        identity=pack_identity,
                        schema_hash=compute_schema_hash(raw_entries),
                    ),
                )
                for class_type, entry in raw_entries.items()
            )

        index: dict[str, str] = dict(existing_index)
        pack_files: dict[str, dict[str, dict[str, Any]]] = dict(existing_pack_files)
        provenance = dict(existing_provenance)
        provenance_packs = dict(provenance.get("packs", {}))
        for pack_name in sorted(packs):
            filename = validate_provider_filename(f"{pack_name}@{(version or effective_version)}.json")
            pack_entries = _merged_pack_entries(
                pack_name,
                packs[pack_name],
                _entries_from_pack_files(existing_pack_files),
                full_refresh=_is_full_pack_refresh(pack_name, full_pack_refresh),
            )
            pack_files[filename] = pack_entries
            for class_type, entry in _entries_from_pack_files(existing_pack_files).items():
                if entry.get("pack") == pack_name and class_type not in pack_entries:
                    index.pop(class_type, None)
            for class_type in sorted(pack_entries):
                index[class_type] = filename
            provenance_packs[filename] = {
                **dict(provenance_packs.get(filename, {})),
                "pack": pack_name,
                "classes": len(pack_entries),
                "schema_sha256": _json_sha256(pack_entries),
                "pack_version": base_identity.pack_version or effective_version,
                "source_kind": base_identity.source_kind,
            }
        provenance["packs"] = provenance_packs
        provenance["class_count"] = len(index)
        _publish_cache_state(cache_root, index=index, pack_files=pack_files, provenance=provenance)

    return len(raw_data), len(packs)


def _read_existing_index(cache_root: Path) -> dict[str, str]:
    return _read_cache_state(cache_root)[0]


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _entries_from_pack_files(pack_files: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for pack in pack_files.values():
        entries.update({class_type: entry for class_type, entry in pack.items() if isinstance(entry, dict)})
    return entries


def _read_cache_state(
    cache_root: Path,
    *,
    use_active_generation: bool = True,
    validate_index_rows: bool = True,
) -> tuple[dict[str, str], dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    """Read one committed/legacy cache state, failing closed on corruption."""
    active_root = active_cache_root(cache_root) if use_active_generation else cache_root
    index_path = active_root / "index.json"
    provenance_path = active_root / "provenance.json"
    index_present = index_path.exists() or index_path.is_symlink()
    provenance_present = provenance_path.exists() or provenance_path.is_symlink()
    if not index_present and not provenance_present:
        return {}, {}, {}
    if index_present and not provenance_present and (cache_root / CURRENT_FILE).exists():
        raise ObjectInfoCacheCorruptError("object_info cache has a partial index/provenance pair")
    index = read_json(active_root, "index.json", required=False) if index_present else {}
    if not isinstance(index, dict):
        raise ObjectInfoCacheCorruptError(f"object_info index must be an object: {index_path}")
    normalized_index: dict[str, str] = {}
    pack_files: dict[str, dict[str, dict[str, Any]]] = {}
    for class_type, filename in index.items():
        if not isinstance(class_type, str) or not isinstance(filename, str):
            raise ObjectInfoCacheCorruptError("object_info index keys and provider filenames must be strings")
        validate_provider_filename(filename)
        if filename not in pack_files:
            path = active_root / filename
            if not path.exists() and not path.is_symlink():
                raise ObjectInfoCacheCorruptError(f"object_info index points to missing provider file: {filename}")
            pack = read_json(active_root, filename)
            if not isinstance(pack, dict):
                raise ObjectInfoCacheCorruptError(f"object_info provider file must be an object: {path}")
            pack_files[filename] = pack
        if validate_index_rows and not isinstance(pack_files[filename].get(class_type), dict):
            raise ObjectInfoCacheCorruptError(
                f"object_info index row {class_type!r} is missing from {filename!r}"
            )
        normalized_index[class_type] = filename
    provenance = read_json(active_root, "provenance.json", required=False) if provenance_present else {}
    if not isinstance(provenance, dict):
        raise ObjectInfoCacheCorruptError(f"object_info provenance must be an object: {provenance_path}")
    provenance_packs = provenance.get("packs", {})
    if provenance_packs is not None and not isinstance(provenance_packs, dict):
        raise ObjectInfoCacheCorruptError("object_info provenance.packs must be an object")
    return normalized_index, pack_files, provenance


@contextmanager
def _cache_publish_lock(cache_root: Path):
    lock_path = cache_root / ".object_info.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _publish_cache_state(
    cache_root: Path,
    *,
    index: dict[str, str],
    pack_files: dict[str, dict[str, dict[str, Any]]],
    provenance: dict[str, Any],
) -> str:
    """Stage and commit a complete pack/index/provenance generation."""
    for filename in pack_files:
        validate_provider_filename(filename)
    provenance = dict(provenance)
    provenance_packs = provenance.get("packs")
    if isinstance(provenance_packs, dict):
        # Legacy-root adapters can leave provenance rows for captures that are
        # no longer present in the final index. Never publish those rows into a
        # manifest that cannot contain their artifacts.
        provenance["packs"] = {
            filename: entry
            for filename, entry in provenance_packs.items()
            if filename in pack_files
        }
    provenance["class_count"] = len(index)
    generation = uuid.uuid4().hex
    generations_root = cache_root / GENERATIONS_DIR
    if generations_root.is_symlink():
        raise ObjectInfoCacheCorruptError(
            f"object_info cache generations directory is symlinked: {generations_root}"
        )
    generations_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".object-info-", dir=generations_root))
    try:
        artifacts: dict[str, str] = {}
        serialized: dict[str, str] = {
            filename: json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False)
            for filename, pack in sorted(pack_files.items())
        }
        serialized["index.json"] = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False)
        serialized["provenance.json"] = json.dumps(provenance, indent=2, sort_keys=True, ensure_ascii=False)
        for filename, text in serialized.items():
            (staging / filename).write_text(text, encoding="utf-8")
            artifacts[filename] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        (staging / MANIFEST_FILE).write_text(
            json.dumps(
                {"format_version": 1, "generation": generation, "files": artifacts},
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        committed = generations_root / generation
        os.replace(staging, committed)
        atomic_write_text(cache_root / CURRENT_FILE, generation + "\n")
        # Keep the old root layout readable to callers that inspect cache files
        # directly.  Readers prefer CURRENT, so an interrupted mirror cannot
        # expose a mixed generation through the supported API.
        for filename in serialized:
            destination = cache_root / filename
            if destination.is_symlink():
                raise ObjectInfoCacheCorruptError(
                    f"object_info cache compatibility artifact is symlinked: {destination}"
                )
            shutil.copyfile(committed / filename, destination)
        return generation
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def republish_cache_root(cache_dir: str | Path) -> str:
    """Commit externally edited legacy-root artifacts as one cache generation."""
    cache_root = Path(cache_dir)
    with _cache_publish_lock(cache_root):
        index, pack_files, provenance = _read_cache_state(
            cache_root,
            use_active_generation=False,
            validate_index_rows=False,
        )
        index = {
            class_type: filename
            for class_type, filename in index.items()
            if isinstance(pack_files.get(filename, {}).get(class_type), dict)
        }
        return _publish_cache_state(
            cache_root,
            index=index,
            pack_files=pack_files,
            provenance=provenance,
        )


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
