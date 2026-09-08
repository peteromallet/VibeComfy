"""Utility functions for VibeComfy.

Includes ``atomic_write_json`` for crash-safe JSON writes."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def find_repo_root() -> Path:
    """Return the checkout root, or the installed package root.

    The latter keeps import-time resource discovery relocatable for wheel
    installs. Callers that specifically require repository-only tooling should
    check for the resource they need rather than assuming a checkout exists.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    # A wheel has no pyproject.toml beside the installed package. When runtime
    # resources are bundled under ``vibecomfy/`` use that package root; without
    # bundled resources retain the historical parent fallback for lightweight
    # installs and harmlessly absent checkout-only paths.
    package_root = Path(__file__).resolve().parent
    if (package_root / "ready_templates").is_dir():
        return package_root
    return package_root.parent


def repo_relative_path(path: str | Path) -> str:
    """Return *path* relative to the repo root when possible.

    Paths outside the checkout are returned as resolved absolute paths.
    """
    raw_path = Path(path)
    resolved = (raw_path if raw_path.is_absolute() else find_repo_root() / raw_path).resolve()
    try:
        return resolved.relative_to(find_repo_root()).as_posix()
    except ValueError:
        return str(resolved)


def atomic_write_json(path: str | Path, data: Any) -> Path:
    """Atomically write *data* as JSON to *path*.

    Writes to a temporary sibling file (same directory, ``.tmp`` suffix),
    ``json.dump``\\s with ``indent=2, default=str``, flushes, ``os.fsync``\\s
    the file descriptor, then atomically replaces the target via
    ``Path.replace()``.

    If a stale temp file exists from a prior crash it is removed before
    writing.

    Returns the final ``Path``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")

    # Remove stale temp file from a prior crash.
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        # Clean up the temp file on any failure so it doesn't linger.
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    tmp_path.replace(target)
    return target
