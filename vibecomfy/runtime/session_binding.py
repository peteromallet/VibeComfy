"""Durable, non-mutating bindings for already managed runtime targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from vibecomfy.utils import atomic_write_json


def binding_path(session_id: str, runtime_root: str | Path | None = None) -> Path:
    root = Path(runtime_root).expanduser().resolve(strict=False) if runtime_root is not None else Path.cwd().resolve(strict=False)
    return root / "out" / "sessions" / str(session_id) / "binding.json"


def load_binding(session_id: str, runtime_root: str | Path | None = None) -> dict[str, Any] | None:
    path = binding_path(session_id, runtime_root)
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None
    return dict(data) if isinstance(data, Mapping) else None


def write_binding(
    session_id: str,
    binding: Mapping[str, Any],
    runtime_root: str | Path | None = None,
) -> Path:
    path = binding_path(session_id, runtime_root)
    payload = dict(binding)
    payload["schema_version"] = 1
    payload["session_id"] = str(session_id)
    return atomic_write_json(path, payload)


__all__ = ["binding_path", "load_binding", "write_binding"]
