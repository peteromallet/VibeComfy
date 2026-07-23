from __future__ import annotations

import os
from pathlib import Path

from vibecomfy.ingest.sources import sync_sources

REQUIRED_INDEXES = (
    # This is the shipped, tracked baseline corpus. The node/source/external
    # indexes are generated enrichments and are intentionally gitignored; a
    # clean installed checkout must not fail search merely because those
    # optional caches have not been generated yet.
    "template_index.json",
)


class SearchBootstrapError(RuntimeError):
    pass


def _missing_indexes() -> list[str]:
    base = _index_base_dir()
    return [name for name in REQUIRED_INDEXES if not _index_path(name, base=base).exists()]


def _index_base_dir() -> Path:
    for env_name in ("VIBECOMFY_SEARCH_INDEX_ROOT", "REPO_ROOT"):
        raw = os.environ.get(env_name)
        if raw:
            return Path(raw).expanduser()
    cwd = Path.cwd()
    if all((cwd / name).exists() for name in REQUIRED_INDEXES):
        return cwd

    # ComfyUI loads VibeComfy as a custom-node package while keeping the
    # process cwd at the ComfyUI checkout.  Search indexes belong to the
    # VibeComfy checkout, so cwd-only resolution makes an installed/symlinked
    # extension falsely report that its indexes are missing.
    package_root = Path(__file__).resolve().parents[2]
    if all((package_root / name).exists() for name in REQUIRED_INDEXES):
        return package_root
    return cwd


def _index_path(name: str, *, base: Path | None = None) -> Path:
    path = Path(name)
    if path.is_absolute() or path.exists():
        return path
    return (base or _index_base_dir()) / path


def ensure_indexes(*, auto_sync: bool = False) -> None:
    missing = _missing_indexes()
    if not missing:
        return
    if not auto_sync:
        raise SearchBootstrapError("indexes missing; run 'vibecomfy sources sync' first")

    sync_sources()
    missing_after_sync = _missing_indexes()
    if missing_after_sync:
        missing_text = ", ".join(missing_after_sync)
        raise SearchBootstrapError(
            f"indexes missing after auto-sync ({missing_text}); run 'vibecomfy sources sync' first"
        )
