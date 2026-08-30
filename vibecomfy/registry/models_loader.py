from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import yaml

from vibecomfy import fetch as fetch_assets


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("models.yaml")
RESERVED_TAGS = {
    "phase:core",
    "phase:gguf",
    "phase:ltx",
    "phase:wan_wrapper",
    "phase:qwen_image",
    "ltx_lean_excluded",
    "requires_hf_token",
    "excluded_in_public_scope",
}
LTX_LEAN_EXCLUDED_SCOPES = {"ltx_official", "ltx_official_public", "ltx_lightricks", "ltx_iclora", "ltx_iclora_public"}
PUBLIC_SCOPES = {"ltx_official_public", "ltx_iclora_public"}
NODE_PACK_ALIASES = {
    "comfy_gguf": "ComfyUI-GGUF",
    "ltx": "ComfyUI-LTXVideo",
    "wan_wrapper": "ComfyUI-WanVideoWrapper",
}
DOCUMENTED_NODE_PACK_GAPS = frozenset({"ace_step", "comfy_core", "kijai_ltx"})
CANONICAL_MODEL_NODE_PACKS = frozenset(NODE_PACK_ALIASES.values())


@dataclass(frozen=True)
class ModelSource:
    kind: str
    repo: str | None = None
    filename: str | None = None
    url: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class ModelTarget:
    node_pack: str
    path: str


@dataclass(frozen=True)
class ModelFile:
    path: str
    sha256: str | None = None
    size_bytes: int | None = None
    min_size: int | None = None


@dataclass(frozen=True)
class ModelEntry:
    id: str
    source: ModelSource
    min_size: int
    targets: tuple[ModelTarget, ...]
    canonical_name: str | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    gated: bool = False
    files: tuple[ModelFile, ...] = ()
    composite_sha256: str | None = None


_REGISTRY_CACHE: dict[Path, tuple[ModelEntry, ...]] = {}


def load_registry(path: str | Path | None = None) -> tuple[ModelEntry, ...]:
    registry_path = _registry_path(path)
    cached = _REGISTRY_CACHE.get(registry_path)
    if cached is not None:
        return cached
    with registry_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    entries_data = data.get("models", data) if isinstance(data, Mapping) else data
    if not isinstance(entries_data, list):
        raise ValueError(f"{registry_path}: registry must be a list or contain a 'models' list")
    entries = tuple(_parse_entry(raw, registry_path=registry_path) for raw in entries_data)
    _validate_registry(entries, registry_path=registry_path)
    _REGISTRY_CACHE[registry_path] = entries
    return entries


def stage_entry(entry: ModelEntry, *, models_root: Path) -> list[Path]:
    created_paths: list[Path] = []
    try:
        return _stage_entry(entry, models_root=models_root, created_paths=created_paths)
    except BaseException:
        _rollback_created_paths(created_paths)
        raise


def _stage_entry(
    entry: ModelEntry, *, models_root: Path, created_paths: list[Path]
) -> list[Path]:
    _validate_staging_paths(entry, models_root=models_root)
    if entry.files:
        return _stage_composite_entry(
            entry, models_root=models_root, created_paths=created_paths
        )
    source = _existing_source(entry, models_root=models_root)
    if source is None:
        source = _download_source(entry, models_root=models_root)
    _check_size(source, entry.min_size, entry.id)
    _check_pins(source, entry)
    staged_paths: list[Path] = []
    for target in entry.targets:
        staged = _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
        staged.parent.mkdir(parents=True, exist_ok=True)
        _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
        if os.path.lexists(staged):
            _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
            _validate_final_component(
                staged, models_root=models_root, entry_id=entry.id, source=source, entry=entry
            )
            if _existing_target_satisfies(staged, entry):
                staged_paths.append(staged)
                staged_paths.extend(
                    _stage_aliases(
                        entry,
                        source=staged,
                        target=target,
                        models_root=models_root,
                        created_paths=created_paths,
                    )
                )
                continue
            _check_collision(staged, source, entry.id)
            _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
            staged.unlink()
        try:
            _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
            os.link(source, staged)
            created_paths.append(staged)
        except OSError:
            _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
            os.symlink(source, staged)
            created_paths.append(staged)
        _validate_final_component(
            staged, models_root=models_root, entry_id=entry.id, source=source, entry=entry
        )
        _check_size(staged, entry.min_size, entry.id)
        _check_pins(staged, entry)
        staged_paths.append(staged)
        staged_paths.extend(
            _stage_aliases(
                entry,
                source=staged,
                target=target,
                models_root=models_root,
                created_paths=created_paths,
            )
        )
    return staged_paths


def _existing_source(entry: ModelEntry, *, models_root: Path) -> Path | None:
    for target in entry.targets:
        staged = _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
        if os.path.lexists(staged) and _existing_target_satisfies(staged, entry):
            resolved = staged.resolve(strict=True)
            if resolved.is_relative_to(models_root.resolve(strict=False)) or _has_content_pins(entry):
                return resolved
            # Without content pins, an external symlink has no known source
            # identity. Defer its authorization until after download.
    return None


def _stage_aliases(
    entry: ModelEntry,
    *,
    source: Path,
    target: ModelTarget,
    models_root: Path,
    created_paths: list[Path],
) -> list[Path]:
    if not entry.aliases:
        return []
    staged_aliases: list[Path] = []
    for alias in entry.aliases:
        alias_path = _authorized_alias_path(
            target, alias, models_root=models_root, entry_id=entry.id
        )
        if os.path.lexists(alias_path):
            _authorized_alias_path(target, alias, models_root=models_root, entry_id=entry.id)
            _validate_final_component(
                alias_path,
                models_root=models_root,
                entry_id=entry.id,
                source=source,
                entry=entry,
            )
            if _existing_target_satisfies(alias_path, entry):
                staged_aliases.append(alias_path)
                continue
            _check_collision(alias_path, source, entry.id)
            _authorized_alias_path(target, alias, models_root=models_root, entry_id=entry.id)
            alias_path.unlink()
        try:
            _authorized_alias_path(target, alias, models_root=models_root, entry_id=entry.id)
            os.link(source, alias_path)
            created_paths.append(alias_path)
        except OSError:
            _authorized_alias_path(target, alias, models_root=models_root, entry_id=entry.id)
            os.symlink(source, alias_path)
            created_paths.append(alias_path)
        _validate_final_component(
            alias_path,
            models_root=models_root,
            entry_id=entry.id,
            source=source,
            entry=entry,
        )
        _check_size(alias_path, entry.min_size, entry.id)
        _check_pins(alias_path, entry)
        staged_aliases.append(alias_path)
    return staged_aliases


def stage_many(entries: Sequence[ModelEntry], *, models_root: Path, ids: Sequence[str] | None = None) -> None:
    selected = _select_by_ids(entries, ids)
    for entry in selected:
        _validate_staging_paths(entry, models_root=models_root)
    created_paths: list[Path] = []
    try:
        for entry in selected:
            _stage_entry(entry, models_root=models_root, created_paths=created_paths)
    except BaseException:
        _rollback_created_paths(created_paths)
        raise


def _rollback_created_paths(created_paths: Sequence[Path]) -> None:
    for path in reversed(created_paths):
        if os.path.lexists(path):
            path.unlink()


def normalize_alias(value: str, *, registry: Sequence[ModelEntry] | None = None, node_pack: str | None = None) -> str | None:
    entries = registry if registry is not None else load_registry()
    for entry in entries:
        if node_pack is not None and all(target.node_pack != node_pack for target in entry.targets):
            continue
        if value in entry.aliases:
            return canonical_filename(entry.id, registry=entries)
    return None


def canonical_filename(model_id: str, *, registry: Sequence[ModelEntry] | None = None) -> str:
    entries = registry if registry is not None else load_registry()
    for entry in entries:
        if entry.id == model_id:
            if entry.canonical_name:
                return entry.canonical_name
            filename = _source_filename(entry.source)
            if filename:
                return filename
            raise ValueError(f"{entry.id}: source filename could not be inferred")
    raise KeyError(f"unknown model id: {model_id}")


def canonical_model_node_pack(name: str) -> str | None:
    if name in CANONICAL_MODEL_NODE_PACKS:
        return name
    return NODE_PACK_ALIASES.get(name)


def _clear_cache() -> None:
    _REGISTRY_CACHE.clear()


def _registry_path(path: str | Path | None) -> Path:
    return (Path(path) if path is not None else DEFAULT_REGISTRY_PATH).expanduser().resolve()


def _parse_entry(raw: Any, *, registry_path: Path) -> ModelEntry:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{registry_path}: each model entry must be a mapping")
    entry_id = _required_str(raw, "id", "<unknown>")
    source_raw = raw.get("source")
    if not isinstance(source_raw, Mapping):
        raise ValueError(f"{entry_id}: source must be a mapping")
    source = ModelSource(
        kind=_required_str(source_raw, "kind", entry_id),
        repo=_optional_str(source_raw.get("repo")),
        filename=_optional_str(source_raw.get("filename")),
        url=_optional_str(source_raw.get("url")),
        revision=_optional_str(source_raw.get("revision")),
    )
    if not isinstance(targets_raw := raw.get("targets", []), list) or not targets_raw:
        raise ValueError(f"{entry_id}: targets must be a non-empty list")
    targets = tuple(_parse_target(target, entry_id=entry_id) for target in targets_raw)
    canonical_name = _optional_str(raw.get("canonical_name"))
    aliases = _str_tuple(raw.get("aliases", []), entry_id=entry_id, field="aliases")
    tags = _str_tuple(raw.get("tags", []), entry_id=entry_id, field="tags")
    if not isinstance(min_size := raw.get("min_size"), int) or min_size < 0:
        raise ValueError(f"{entry_id}: min_size must be a non-negative integer")
    size_bytes = raw.get("size_bytes")
    if size_bytes is not None and (not isinstance(size_bytes, int) or size_bytes < 0):
        raise ValueError(f"{entry_id}: size_bytes must be a non-negative integer when set")
    sha256 = _optional_str(raw.get("sha256"))
    gated = bool(raw.get("gated", False))
    files = _parse_files(raw.get("files", []), entry_id=entry_id)
    composite_sha256 = _optional_str(raw.get("composite_sha256"))
    if sha256 == "gated" or source.revision == "gated":
        raise ValueError(f"{entry_id}: use gated: true instead of sha256/source.revision 'gated'")
    if (notes := raw.get("notes")) is not None and not isinstance(notes, str):
        raise ValueError(f"{entry_id}: notes must be a string")
    return ModelEntry(
        id=entry_id,
        source=source,
        min_size=min_size,
        targets=targets,
        sha256=sha256,
        size_bytes=size_bytes,
        gated=gated,
        files=files,
        composite_sha256=composite_sha256,
        canonical_name=canonical_name,
        aliases=aliases,
        tags=tags,
        notes=notes,
    )


def _parse_target(raw: Any, *, entry_id: str) -> ModelTarget:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{entry_id}: target must be a mapping")
    node_pack = _required_str(raw, "node_pack", entry_id)
    path = _required_str(raw, "path", entry_id)
    _validate_target_path(path, entry_id=entry_id)
    return ModelTarget(node_pack=node_pack, path=path)


def _parse_files(raw: Any, *, entry_id: str) -> tuple[ModelFile, ...]:
    if raw in (None, []):
        return ()
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{entry_id}: files must be a non-empty list when set")
    files: list[ModelFile] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError(f"{entry_id}: each files item must be a mapping")
        path = _required_str(item, "path", entry_id)
        _validate_relative_file_path(path, entry_id=entry_id, field="files.path")
        if path in seen:
            raise ValueError(f"{entry_id}: duplicate files.path {path!r}")
        seen.add(path)
        size_bytes = item.get("size_bytes")
        if size_bytes is not None and (not isinstance(size_bytes, int) or size_bytes < 0):
            raise ValueError(f"{entry_id}: files.size_bytes must be a non-negative integer when set")
        min_size = item.get("min_size")
        if min_size is not None and (not isinstance(min_size, int) or min_size < 0):
            raise ValueError(f"{entry_id}: files.min_size must be a non-negative integer when set")
        files.append(
            ModelFile(
                path=path,
                sha256=_optional_str(item.get("sha256")),
                size_bytes=size_bytes,
                min_size=min_size,
            )
        )
    return tuple(files)


def _validate_registry(entries: Sequence[ModelEntry], *, registry_path: Path) -> None:
    seen_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for entry in entries:
        if entry.id in seen_ids:
            raise ValueError(f"{registry_path}: duplicate model id {entry.id!r}")
        seen_ids.add(entry.id)
        if entry.source.kind == "huggingface":
            if not entry.source.repo:
                raise ValueError(f"{entry.id}: huggingface source requires repo")
            if not entry.files and not entry.source.filename:
                raise ValueError(f"{entry.id}: huggingface source requires filename for single-file entries")
        elif entry.source.kind == "url":
            if not entry.source.url:
                raise ValueError(f"{entry.id}: url source requires url")
            if entry.files:
                raise ValueError(f"{entry.id}: composite files are only supported for huggingface sources")
        else:
            raise ValueError(f"{entry.id}: unsupported source kind {entry.source.kind!r}")
        if entry.files:
            if not entry.source.revision:
                raise ValueError(f"{entry.id}: composite huggingface entries require source.revision")
            expected = composite_sha256(entry.files)
            if entry.composite_sha256 and entry.composite_sha256.lower() != expected:
                raise ValueError(f"{entry.id}: composite_sha256 {entry.composite_sha256} does not match deterministic child hash {expected}")
        for tag in entry.tags:
            if tag not in RESERVED_TAGS:
                raise ValueError(f"{entry.id}: unknown tag {tag!r}")
        for alias in entry.aliases:
            owner = seen_aliases.get(alias)
            if owner is not None:
                raise ValueError(f"{entry.id}: duplicate alias {alias!r}; already used by {owner}")
            seen_aliases[alias] = entry.id
        for target in entry.targets:
            _validate_target_node_pack(target, entry_id=entry.id, registry_path=registry_path)


def _validate_target_node_pack(target: ModelTarget, *, entry_id: str, registry_path: Path) -> None:
    raw_name = target.node_pack
    if canonical_model_node_pack(raw_name) is not None:
        return
    if raw_name in DOCUMENTED_NODE_PACK_GAPS:
        return
    allowed = sorted((*CANONICAL_MODEL_NODE_PACKS, *NODE_PACK_ALIASES, *DOCUMENTED_NODE_PACK_GAPS))
    raise ValueError(
        f"{registry_path}: {entry_id}: unknown target.node_pack {raw_name!r}; "
        f"expected canonical names, transitional aliases, or documented gaps: {', '.join(allowed)}"
    )


def _validate_target_path(path: str, *, entry_id: str) -> None:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: path must be non-empty")
    if path.startswith("models/") or path.startswith("models\\"):
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: path is relative to models_root and must not start with models/")
    posix, windows = PurePosixPath(path), PureWindowsPath(path)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.root
        or windows.drive
        or "\\" in path
        or path.endswith("/")
        or path.rstrip("/").rsplit("/", 1)[-1] == "."
    ):
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: absolute paths are not allowed")
    if ".." in posix.parts or ".." in windows.parts:
        raise ValueError(f"{entry_id}: invalid target.path {path!r}: '..' segments are not allowed")


def _validate_relative_file_path(path: str, *, entry_id: str, field: str) -> None:
    if not isinstance(path, str) or "\x00" in path:
        raise ValueError(f"{entry_id}: invalid {field} {path!r}: must be a relative file path")
    posix, windows = PurePosixPath(path), PureWindowsPath(path)
    if (
        not path
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.root
        or windows.drive
        or "\\" in path
        or path.endswith("/")
        or path.rstrip("/").rsplit("/", 1)[-1] == "."
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise ValueError(f"{entry_id}: invalid {field} {path!r}: must be a relative file path")


def _validate_alias(alias: str, *, entry_id: str) -> None:
    if (
        not isinstance(alias, str)
        or not alias
        or "\x00" in alias
        or "/" in alias
        or "\\" in alias
        or PureWindowsPath(alias).is_absolute()
        or PureWindowsPath(alias).root
        or PureWindowsPath(alias).drive
        or alias in {".", ".."}
    ):
        raise ValueError(f"{entry_id}: invalid alias {alias!r}: must be a single relative filename")


def _authorized_staging_path(
    models_root: Path, relative: str, *, entry_id: str, field: str
) -> Path:
    candidate = models_root / relative
    try:
        resolved_root = models_root.resolve(strict=False)
        resolved_parent = candidate.parent.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValueError(
            f"{entry_id}: {field} could not be resolved safely: {relative!r}"
        ) from exc
    if not resolved_parent.is_relative_to(resolved_root):
        raise ValueError(
            f"{entry_id}: {field} resolves outside models_root {resolved_root}: {relative!r}"
        )
    return candidate


def _has_content_pins(entry: ModelEntry, file: ModelFile | None = None) -> bool:
    if file is not None:
        return file.size_bytes is not None or bool(file.sha256)
    return entry.size_bytes is not None or bool(entry.sha256)


def _validate_final_component(
    path: Path,
    *,
    models_root: Path,
    entry_id: str,
    source: Path,
    entry: ModelEntry,
    file: ModelFile | None = None,
) -> None:
    """Allow only an in-root or source/pin-authorized final symlink."""
    root = models_root.resolve(strict=False)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(root):
            raise ValueError(
                f"{entry_id}: final staging path resolves outside models_root {root}: {path}"
            ) from exc
        raise ValueError(
            f"{entry_id}: final staging path could not be resolved safely: {path}"
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise ValueError(
            f"{entry_id}: final staging path could not be resolved safely: {path}"
        ) from exc
    if resolved.is_relative_to(root):
        return
    try:
        source_resolved = source.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise ValueError(f"{entry_id}: source could not be resolved safely: {source}") from exc
    if resolved == source_resolved:
        return
    if _has_content_pins(entry, file):
        try:
            if file is None:
                _check_pins(path, entry)
            else:
                _check_model_file_pins(path, entry=entry, file=file)
            return
        except (OSError, RuntimeError):
            pass
    raise ValueError(
        f"{entry_id}: final staging path resolves outside models_root {root}: {path}"
    )


def _authorized_target_path(
    target: ModelTarget, *, models_root: Path, entry_id: str
) -> Path:
    _validate_target_path(target.path, entry_id=entry_id)
    return _authorized_staging_path(
        models_root, target.path, entry_id=entry_id, field="target.path"
    )


def _authorized_alias_path(
    target: ModelTarget, alias: str, *, models_root: Path, entry_id: str
) -> Path:
    _validate_target_path(target.path, entry_id=entry_id)
    _validate_alias(alias, entry_id=entry_id)
    relative = PurePosixPath(target.path).parent / alias
    return _authorized_staging_path(
        models_root, str(relative), entry_id=entry_id, field="alias"
    )


def _authorized_composite_path(
    target: ModelTarget, file: ModelFile, *, models_root: Path, entry_id: str
) -> Path:
    _validate_target_path(target.path, entry_id=entry_id)
    _validate_relative_file_path(file.path, entry_id=entry_id, field="files.path")
    relative = PurePosixPath(target.path) / PurePosixPath(file.path)
    return _authorized_staging_path(
        models_root, str(relative), entry_id=entry_id, field="files.path"
    )


def _validate_staging_paths(entry: ModelEntry, *, models_root: Path) -> None:
    if not entry.targets:
        raise ValueError(f"{entry.id}: targets must be a non-empty list")
    for target in entry.targets:
        _authorized_target_path(target, models_root=models_root, entry_id=entry.id)
        if entry.files:
            for file in entry.files:
                _authorized_composite_path(
                    target, file, models_root=models_root, entry_id=entry.id
                )
        else:
            for alias in entry.aliases:
                _authorized_alias_path(
                    target, alias, models_root=models_root, entry_id=entry.id
                )


def _download_source(entry: ModelEntry, *, models_root: Path) -> Path:
    if entry.source.kind == "huggingface":
        from huggingface_hub import hf_hub_download

        kwargs = {"repo_id": entry.source.repo, "filename": entry.source.filename}
        if entry.source.revision is not None:
            kwargs["revision"] = entry.source.revision
        path = hf_hub_download(**kwargs)
        return Path(path).resolve(strict=True)
    if entry.source.kind == "url":
        filename = _source_filename(entry.source)
        downloaded = fetch_assets.download(
            {
                "name": filename,
                "subdir": "_registry",
                "url": entry.source.url,
                **({"sha256": entry.sha256} if entry.sha256 else {}),
                **({"size_bytes": entry.size_bytes} if entry.size_bytes is not None else {}),
                **({"gated": True} if entry.gated else {}),
            },
            root=models_root,
        )
        return downloaded.resolve(strict=True)
    raise ValueError(f"{entry.id}: unsupported source kind {entry.source.kind!r}")


def _download_model_file(entry: ModelEntry, file: ModelFile) -> Path:
    from huggingface_hub import hf_hub_download

    kwargs = {"repo_id": entry.source.repo, "filename": file.path}
    if entry.source.revision is not None:
        kwargs["revision"] = entry.source.revision
    return Path(hf_hub_download(**kwargs)).resolve(strict=True)


def _stage_composite_entry(
    entry: ModelEntry, *, models_root: Path, created_paths: list[Path]
) -> list[Path]:
    staged_paths: list[Path] = []
    for file in entry.files:
        source = _download_model_file(entry, file)
        _check_model_file_pins(source, entry=entry, file=file)
        for target in entry.targets:
            staged = _authorized_composite_path(
                target, file, models_root=models_root, entry_id=entry.id
            )
            staged.parent.mkdir(parents=True, exist_ok=True)
            _authorized_composite_path(target, file, models_root=models_root, entry_id=entry.id)
            if os.path.lexists(staged):
                _authorized_composite_path(target, file, models_root=models_root, entry_id=entry.id)
                _validate_final_component(
                    staged,
                    models_root=models_root,
                    entry_id=entry.id,
                    source=source,
                    entry=entry,
                    file=file,
                )
                if _existing_model_file_satisfies(staged, entry=entry, file=file):
                    staged_paths.append(staged)
                    continue
                _check_collision(staged, source, entry.id)
                _authorized_composite_path(target, file, models_root=models_root, entry_id=entry.id)
                staged.unlink()
            try:
                _authorized_composite_path(target, file, models_root=models_root, entry_id=entry.id)
                os.link(source, staged)
                created_paths.append(staged)
            except OSError:
                _authorized_composite_path(target, file, models_root=models_root, entry_id=entry.id)
                os.symlink(source, staged)
                created_paths.append(staged)
            _validate_final_component(
                staged,
                models_root=models_root,
                entry_id=entry.id,
                source=source,
                entry=entry,
                file=file,
            )
            _check_model_file_pins(staged, entry=entry, file=file)
            staged_paths.append(staged)
    return staged_paths


def _check_collision(staged: Path, source: Path, entry_id: str) -> None:
    if staged.is_symlink():
        return
    try:
        if staged.stat().st_ino == source.stat().st_ino and staged.stat().st_dev == source.stat().st_dev:
            return
    except FileNotFoundError:
        return
    raise RuntimeError(f"{entry_id}: refusing to overwrite unrelated existing file at {staged}")


def _existing_target_satisfies(staged: Path, entry: ModelEntry) -> bool:
    if not staged.exists():
        return False
    try:
        _check_size(staged, entry.min_size, entry.id)
        _check_pins(staged, entry)
    except RuntimeError:
        return False
    return True


def _existing_model_file_satisfies(staged: Path, *, entry: ModelEntry, file: ModelFile) -> bool:
    if not staged.exists():
        return False
    try:
        _check_model_file_pins(staged, entry=entry, file=file)
    except RuntimeError:
        return False
    return True


def _check_size(path: Path, min_size: int, entry_id: str) -> None:
    size = path.stat().st_size
    if size < min_size:
        raise RuntimeError(f"{entry_id}: {path} is too small ({size} bytes < {min_size} bytes)")


def _check_pins(path: Path, entry: ModelEntry) -> None:
    if entry.size_bytes is not None and path.stat().st_size != entry.size_bytes:
        raise RuntimeError(f"{entry.id}: {path} size {path.stat().st_size} does not match pinned size_bytes {entry.size_bytes}")
    if entry.sha256:
        if entry.gated:
            return
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual.lower() != entry.sha256.lower():
            raise RuntimeError(f"{entry.id}: {path} sha256 {actual} does not match pinned sha256 {entry.sha256}")


def _check_model_file_pins(path: Path, *, entry: ModelEntry, file: ModelFile) -> None:
    min_size = entry.min_size if file.min_size is None else file.min_size
    _check_size(path, min_size, entry.id)
    if file.size_bytes is not None and path.stat().st_size != file.size_bytes:
        raise RuntimeError(f"{entry.id}: {file.path} size {path.stat().st_size} does not match pinned size_bytes {file.size_bytes}")
    if file.sha256 and not entry.gated:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual.lower() != file.sha256.lower():
            raise RuntimeError(f"{entry.id}: {file.path} sha256 {actual} does not match pinned sha256 {file.sha256}")


def composite_sha256(files: Sequence[ModelFile]) -> str:
    payload = [
        {
            "path": file.path,
            "sha256": file.sha256,
            "size_bytes": file.size_bytes,
        }
        for file in sorted(files, key=lambda item: item.path)
    ]
    rendered = yaml.safe_dump(payload, sort_keys=True, allow_unicode=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _select_by_ids(entries: Sequence[ModelEntry], ids: Sequence[str] | None) -> tuple[ModelEntry, ...]:
    if ids is None:
        return tuple(entries)
    by_id = {entry.id: entry for entry in entries}
    missing = [model_id for model_id in ids if model_id not in by_id]
    if missing:
        raise KeyError(f"unknown model id(s): {', '.join(missing)}")
    return tuple(by_id[model_id] for model_id in ids)


def _filter_entries(entries: Sequence[ModelEntry], *, ids: Sequence[str] | None, select_phase: str | None) -> tuple[ModelEntry, ...]:
    selected = _select_by_ids(entries, ids)
    if select_phase is not None:
        selected = tuple(entry for entry in selected if f"phase:{select_phase}" in entry.tags)
    scope = os.environ.get("VIBECOMFY_MATRIX_SCOPE")
    if scope in LTX_LEAN_EXCLUDED_SCOPES:
        selected = tuple(entry for entry in selected if "ltx_lean_excluded" not in entry.tags)
    if scope in PUBLIC_SCOPES:
        selected = tuple(entry for entry in selected if "excluded_in_public_scope" not in entry.tags)
    if not os.environ.get("HF_TOKEN"):
        selected = tuple(entry for entry in selected if "requires_hf_token" not in entry.tags)
    return selected


def _print_dry_run(entries: Sequence[ModelEntry], *, models_root: Path) -> None:
    for entry in entries:
        source = _source_label(entry.source)
        pins = _pin_status(entry)
        print(f"{entry.id}: {source}{f' [{pins}]' if pins else ''}")
        for target in entry.targets:
            staged = models_root / target.path
            if staged.exists():
                size = staged.stat().st_size
                status = "ok" if size >= entry.min_size else f"too-small ({size} < {entry.min_size})"
            else:
                status = "missing"
            print(f"  -> {staged.absolute()} [{status}]")


def _source_filename(source: ModelSource) -> str:
    if source.filename:
        return Path(source.filename).name
    if source.url:
        name = Path(urlsplit(source.url).path).name
        if name:
            return name
    return ""


def _source_label(source: ModelSource) -> str:
    if source.kind == "huggingface":
        revision = f"@{source.revision}" if source.revision else ""
        return f"hf://{source.repo}/{source.filename}{revision}"
    return source.url or "url:<missing>"


def _pin_status(entry: ModelEntry) -> str:
    parts: list[str] = []
    if entry.source.revision:
        parts.append(f"revision={entry.source.revision}")
    if entry.sha256:
        parts.append(f"sha256={entry.sha256}")
    if entry.files:
        parts.append(f"files={len(entry.files)}")
        parts.append(f"composite_sha256={entry.composite_sha256 or composite_sha256(entry.files)}")
    if entry.gated:
        parts.append("gated=True")
    if entry.size_bytes is not None:
        parts.append(f"size_bytes={entry.size_bytes}")
    return ", ".join(parts)


def _required_str(raw: Mapping[str, Any], key: str, entry_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{entry_id}: {key} must be a non-empty string")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("optional string fields must be non-empty strings when set")
    return value


def _str_tuple(value: Any, *, entry_id: str, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{entry_id}: {field} must be a list of non-empty strings")
    return tuple(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m vibecomfy.registry.models_loader")
    subparsers = parser.add_subparsers(dest="action", required=True)
    stage = subparsers.add_parser("stage")
    stage.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    stage.add_argument("--models-root", type=Path, required=True)
    stage.add_argument("--ids", nargs="+")
    stage.add_argument("--select-phase", choices=("core", "gguf", "ltx", "wan_wrapper", "qwen_image"))
    stage.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    entries = load_registry(args.registry)
    selected = _filter_entries(entries, ids=args.ids, select_phase=args.select_phase)
    if args.dry_run:
        _print_dry_run(selected, models_root=args.models_root)
    else:
        stage_many(selected, models_root=args.models_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
