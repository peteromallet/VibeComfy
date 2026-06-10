"""Shared provenance path helpers used by both convert.py and emitter.py.

Extracted from convert.py and emitter.py (M2 Step 1) to a single canonical
home so the two callers share one definition.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.utils import repo_relative_path

logger = logging.getLogger(__name__)

_PROVENANCE_PATH_KEYS: frozenset[str] = frozenset(
    {"source_path", "source_workflow_path", "source_workflow"}
)


def _normalize_provenance_paths(provenance: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(provenance)
    for key in _PROVENANCE_PATH_KEYS:
        value = normalized.get(key)
        if isinstance(value, str) and value:
            normalized[key] = _repo_relative_provenance_path(value)
    return normalized


def _repo_relative_provenance_path(path: str) -> str:
    normalized = repo_relative_path(path)
    if Path(normalized).is_absolute():
        logger.warning(
            "provenance path is outside the repo; keeping absolute path: %s",
            normalized,
        )
    return normalized
