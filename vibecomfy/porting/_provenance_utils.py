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


def resolve_source_workflow(
    metadata: Mapping[str, Any], row: Mapping[str, Any] | None = None
) -> str | None:
    """Resolve a ready template's source workflow across metadata generations."""
    if row is not None:
        source = row.get("source_workflow")
        if isinstance(source, str) and source:
            return source
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping):
        for key in ("source_workflow", "source_workflow_path", "source_path"):
            source = provenance.get(key)
            if isinstance(source, str) and source:
                return source
    source = metadata.get("source_workflow")
    return source if isinstance(source, str) and source else None


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
