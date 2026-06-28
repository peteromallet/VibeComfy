"""Session-root and path utilities for agent-edit sessions."""

from __future__ import annotations

from pathlib import Path

from ..audit import artifact_ref_for_path
from ..contracts import ArtifactRef
from ..session import normalize_session_id


def safe_session_id(value: str | None = None) -> str:
    """Normalize a session id to a safe path component."""
    return normalize_session_id(value)


def artifact(path: Path) -> ArtifactRef:
    return artifact_ref_for_path(path)


__all__ = ["artifact", "safe_session_id"]
