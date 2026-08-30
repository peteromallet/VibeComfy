"""Utility functions for VibeComfy.

Includes ``atomic_write_json`` for crash-safe JSON writes."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
import tomllib
from typing import Any

from vibecomfy.errors import CheckoutRequiredError


@lru_cache(maxsize=1)
def find_repo_root() -> Path:
    """Return the VibeComfy repository root, or explain how to get one."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if isinstance(project, dict) and project.get("name") == "vibecomfy":
            return candidate
    raise CheckoutRequiredError(
        "VibeComfy ready-template and repository corpus operations require a git checkout. "
        "Clone the VibeComfy repository and install it editable with `pip install -e .`."
    )


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
