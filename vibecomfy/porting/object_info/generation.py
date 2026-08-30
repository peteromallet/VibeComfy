"""Committed-generation primitives for the structured object_info cache.

The cache keeps its historical root-level files for compatibility, but readers
use ``CURRENT`` when a staged generation has been published.  A generation is
complete only when its manifest, index, provenance, and every referenced pack
file are present and hash-consistent.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from vibecomfy.errors import ObjectInfoCacheCorruptError

CURRENT_FILE = "CURRENT"
GENERATIONS_DIR = "generations"
MANIFEST_FILE = "manifest.json"
GENERATION_FORMAT_VERSION = 1
RESERVED_FILES = frozenset({CURRENT_FILE, MANIFEST_FILE, "index.json", "provenance.json"})


def safe_cache_filename(filename: str) -> bool:
    """Return whether *filename* is a single provider-owned JSON filename."""
    if not isinstance(filename, str) or not filename or filename in RESERVED_FILES:
        return False
    if "\x00" in filename or "/" in filename or "\\" in filename:
        return False
    path = Path(filename)
    return path.name == filename and path.suffix == ".json" and not filename.startswith(".")


def safe_artifact_filename(filename: str) -> bool:
    return filename in {"index.json", "provenance.json"} or safe_cache_filename(filename)


def active_cache_root(cache_root: str | Path) -> Path:
    """Resolve the committed generation, or the legacy root when none exists."""
    root = Path(cache_root)
    marker = root / CURRENT_FILE
    if not marker.exists() and not marker.is_symlink():
        return root
    if marker.is_symlink() or not marker.is_file():
        raise ObjectInfoCacheCorruptError(f"object_info cache marker is not a regular file: {marker}")
    try:
        generation = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ObjectInfoCacheCorruptError(f"cannot read object_info cache marker {marker}: {exc}") from exc
    if not generation or Path(generation).name != generation or "/" in generation or "\\" in generation:
        raise ObjectInfoCacheCorruptError(f"invalid object_info cache generation marker: {marker}")
    generations_root = root / GENERATIONS_DIR
    if generations_root.is_symlink() or not generations_root.is_dir():
        raise ObjectInfoCacheCorruptError(
            f"object_info cache generations directory is not a regular directory: {generations_root}"
        )
    generation_root = generations_root / generation
    if generation_root.is_symlink() or not generation_root.is_dir():
        raise ObjectInfoCacheCorruptError(
            f"object_info cache marker points to missing generation {generation!r}"
        )
    validate_generation(generation_root)
    return generation_root


def validate_generation(generation_root: str | Path) -> dict[str, Any]:
    """Validate one committed generation and return its manifest."""
    root = Path(generation_root)
    _validate_generation_root(root)
    manifest_path = _artifact_path(root, MANIFEST_FILE)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObjectInfoCacheCorruptError(
            f"object_info cache generation has unreadable manifest: {manifest_path} ({exc})"
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != GENERATION_FORMAT_VERSION:
        raise ObjectInfoCacheCorruptError(f"invalid object_info cache manifest: {manifest_path}")
    generation = manifest.get("generation")
    files = manifest.get("files")
    if not isinstance(generation, str) or not generation or not isinstance(files, dict):
        raise ObjectInfoCacheCorruptError(f"incomplete object_info cache manifest: {manifest_path}")
    if generation != root.name:
        raise ObjectInfoCacheCorruptError(f"object_info cache manifest names the wrong generation: {manifest_path}")
    for filename, expected_hash in files.items():
        if not safe_artifact_filename(filename) or not isinstance(expected_hash, str):
            raise ObjectInfoCacheCorruptError(f"invalid artifact name in object_info manifest: {filename!r}")
        artifact = _artifact_path(root, filename)
        if not artifact.is_file():
            raise ObjectInfoCacheCorruptError(f"object_info generation is missing artifact {filename!r}")
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ObjectInfoCacheCorruptError(
                f"object_info generation artifact {filename!r} failed its hash check"
            )
    required = {"index.json", "provenance.json"}
    if not required <= set(files):
        raise ObjectInfoCacheCorruptError("object_info generation is missing index or provenance")
    try:
        index = json.loads(_artifact_path(root, "index.json").read_text(encoding="utf-8"))
        provenance = json.loads(_artifact_path(root, "provenance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObjectInfoCacheCorruptError(f"object_info generation has invalid JSON: {root}") from exc
    if not isinstance(index, dict) or not isinstance(provenance, dict):
        raise ObjectInfoCacheCorruptError("object_info generation index/provenance must be objects")
    packs = provenance.get("packs", {})
    if not isinstance(packs, dict):
        raise ObjectInfoCacheCorruptError("object_info generation provenance.packs must be an object")
    for class_type, filename in index.items():
        if not isinstance(class_type, str) or not safe_cache_filename(filename) or filename not in files:
            raise ObjectInfoCacheCorruptError(
                f"object_info index contains an unsafe or unpublished provider filename for {class_type!r}"
            )
        try:
            pack = json.loads(_artifact_path(root, filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ObjectInfoCacheCorruptError(f"object_info pack {filename!r} is unreadable") from exc
        if not isinstance(pack, dict) or not isinstance(pack.get(class_type), dict):
            raise ObjectInfoCacheCorruptError(
                f"object_info index row {class_type!r} is absent from provider file {filename!r}"
            )
    for filename in packs:
        if not safe_artifact_filename(filename) or filename not in files:
            raise ObjectInfoCacheCorruptError(f"provenance names unpublished provider file {filename!r}")
    return manifest


def read_json(root: str | Path, filename: str, *, required: bool = True) -> Any:
    """Read one cache artifact with absent-versus-corrupt semantics."""
    if not safe_cache_filename(filename) and filename not in {"index.json", "provenance.json"}:
        raise ObjectInfoCacheCorruptError(f"unsafe object_info provider filename: {filename!r}")
    path = _artifact_path(Path(root), filename)
    if not path.exists():
        if required:
            raise ObjectInfoCacheCorruptError(f"object_info cache artifact is missing: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObjectInfoCacheCorruptError(f"object_info cache artifact is corrupt: {path} ({exc})") from exc


def _validate_generation_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ObjectInfoCacheCorruptError(
            f"object_info cache generation root is not a regular directory: {root}"
        )


def _artifact_path(root: Path, filename: str) -> Path:
    """Return a contained, non-symlinked artifact path.

    Cache artifacts are provider-owned bytes. Following a link here would turn
    an otherwise valid hash/index pair into an authorization to read outside the
    committed generation (or legacy cache) root.
    """
    _validate_generation_root(root)
    path = root / filename
    if path.is_symlink():
        raise ObjectInfoCacheCorruptError(f"object_info cache artifact is symlinked: {path}")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=False)
        resolved_path.relative_to(resolved_root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ObjectInfoCacheCorruptError(
            f"object_info cache artifact escapes its root: {path}"
        ) from exc
    return path


def atomic_write_text(path: Path, text: str) -> None:
    """Write a small publication marker without promising power-loss durability."""
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
