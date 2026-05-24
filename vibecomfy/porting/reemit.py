"""Helpers for the ``port reemit`` CLI verb.

``port reemit`` runs the existing emitter (``port convert``'s IR -> Python
serialization) against an already-checked-in ``ready_templates/**/*.py`` file
so that templates without an importable source JSON can still benefit from
emitter improvements (widget alias resolution, named widgets, blank-line
formatting, etc.).

This module only collects *discovery* and *classification* helpers — the
actual emit path reuses ``port_convert_workflow`` and ``port_convert_and_write``
unchanged.  Templates eligible for ``--all-family-p`` are:

  - any path listed in ``docs/template_provenance_gaps.md``, or
  - any ready template whose body still contains the legacy
    ``WIDGET_N = ...`` module-level constant pattern emitted before the
    named-widget rule landed.
"""
from __future__ import annotations

import re
from pathlib import Path

READY_ROOT = Path(__file__).resolve().parents[2] / "ready_templates"
PROVENANCE_GAPS_DOC = Path(__file__).resolve().parents[2] / "docs" / "template_provenance_gaps.md"

# Legacy emitter shape: ``WIDGET_0 = 'vae'`` (or ``WIDGET_0_3 = ...``) style
# constants hoisted at module level instead of being inlined as named kwargs.
LEGACY_WIDGET_N_PATTERN: re.Pattern[str] = re.compile(
    r"^WIDGET_\d+(?:_\d+)?\s*=", re.MULTILINE
)

# Provenance-gap doc entries are listed under ``### `<ready_id>``` headings.
_PROVENANCE_HEADING_PATTERN: re.Pattern[str] = re.compile(
    r"^###\s+`([^`]+)`\s*$", re.MULTILINE
)


def has_legacy_widget_constants(source: str) -> bool:
    """Return True when *source* still emits the pre-named-widget shape."""
    return bool(LEGACY_WIDGET_N_PATTERN.search(source))


def _provenance_gap_ready_ids(doc_path: Path = PROVENANCE_GAPS_DOC) -> list[str]:
    """Parse ``docs/template_provenance_gaps.md`` for documented ready ids."""
    if not doc_path.exists():
        return []
    text = doc_path.read_text(encoding="utf-8")
    return list(dict.fromkeys(_PROVENANCE_HEADING_PATTERN.findall(text)))


def discover_family_p_paths(
    *,
    ready_root: Path = READY_ROOT,
    doc_path: Path = PROVENANCE_GAPS_DOC,
) -> list[Path]:
    """Discover every template eligible for ``port reemit --all-family-p``.

    Combines (a) ready ids listed in the provenance gaps doc with
    (b) ready templates whose source still contains ``WIDGET_N = ...``
    constants — the legacy emitter shape that this command exists to refresh.
    """
    discovered: dict[Path, None] = {}

    for ready_id in _provenance_gap_ready_ids(doc_path):
        candidate = ready_root / f"{ready_id}.py"
        if candidate.is_file():
            discovered[candidate.resolve()] = None

    for candidate in sorted(ready_root.rglob("*.py")):
        try:
            source = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if has_legacy_widget_constants(source):
            discovered[candidate.resolve()] = None

    return list(discovered)


__all__ = [
    "LEGACY_WIDGET_N_PATTERN",
    "discover_family_p_paths",
    "has_legacy_widget_constants",
]
