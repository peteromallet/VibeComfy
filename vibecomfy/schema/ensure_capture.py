"""Persist on-demand pack schema extracts into the committed object_info cache.

Glue between ``schema/extract.py`` (rungs 1–2) and
``porting/object_info/serialize.build_cache`` plus the ``schemas`` provenance
ledger.  No extraction happens here and no second schema system is introduced:
this module only stamps honest identity, enforces tier ordering, and applies
the two-layer file hygiene that ``build_cache``'s merge semantics require.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecomfy.porting.object_info.consume import CACHE_DIR, reset_cache
from vibecomfy.porting.object_info.serialize import (
    CacheIdentity,
    _read_existing_index,
    build_cache,
    republish_cache_root,
)

# Canonical persist tokens per extraction rung (plan "Canonical tokens").
# Never persist runtime_* / executed_* / workflow_json_stub from this path.
SOURCE_KIND_BY_RUNG = {
    "ast": "on_demand_static",
    "import": "on_demand_import",
    "embedded": "on_demand_embedded",
}

RUNTIME_SOURCE_KINDS = frozenset(
    {"runtime_object_info", "runtime_core_object_info", "executed_object_info"}
)
STUB_SOURCE_KIND = "workflow_json_stub"
STUB_PACK_VERSION = "stub"

# Tier ranking for the never-overwrite-higher guard. Any attested capture that
# is not an on-demand tier is a genuine object_info dump (runtime family or a
# pinned legacy ingest) and outranks every on-demand tier.
_TIER_RANK = {
    "on_demand_static": 0,
    "on_demand_import": 1,
    "on_demand_embedded": 2,
}
_RUNTIME_TIER = 3
_MISSING_TIER = -1

def format_schema_gap(
    manifest_path: str | Path,
    missing_classes: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
    """Human-readable gap text that **ends** with the exact retry command.

    Shared by ``schemas validate-coverage --manifest``, ``doctor``, ensure
    failures, and preflight. Keeping a single helper guarantees the command
    is identical everywhere and avoids drift. The returned string always ends
    with ``vibecomfy schemas ensure --manifest <path>`` (no trailing newline).
    """
    path_str = str(manifest_path)
    command = f"vibecomfy schemas ensure --manifest {path_str}"
    if missing_classes:
        missing = ", ".join(sorted(set(missing_classes)))
        return f"Missing live captures for {missing}; run {command}"
    return command


def format_template_gap(
    template_path: str | Path,
    missing_classes: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
    """Template-scoped companion: ends with ``vibecomfy schemas ensure <template>``."""
    path_str = str(template_path)
    command = f"vibecomfy schemas ensure {path_str}"
    if missing_classes:
        missing = ", ".join(sorted(set(missing_classes)))
        return f"Missing live captures for {missing}; run {command}"
    return command


@dataclass(frozen=True)
class PersistResult:
    """Outcome of one ``persist_on_demand_pack`` call."""

    no_op: bool
    filename: str | None = None
    written_classes: list[str] = field(default_factory=list)
    skipped_classes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache-state readers (index / entry / provenance)
# ---------------------------------------------------------------------------


def _cache_root(cache_dir: str | Path | None) -> Path:
    return Path(cache_dir) if cache_dir is not None else CACHE_DIR


def _load_provenance(cache_root: Path) -> dict[str, Any]:
    from vibecomfy.commands.schemas import _load_provenance as _schemas_load

    return _schemas_load(cache_root)


def _provenance_pack_row(provenance: dict[str, Any], filename: str) -> dict[str, Any] | None:
    packs = provenance.get("packs")
    if not isinstance(packs, dict):
        return None
    row = packs.get(filename)
    return row if isinstance(row, dict) else None


def _is_pinned(row: dict[str, Any] | None) -> bool:
    """A pin (clone remote or locked commit) is minimum capture evidence."""
    return bool(row) and bool(row.get("repo") or row.get("locked_commit"))


def _is_stub_index_row(filename: str, entry: dict[str, Any] | None) -> bool:
    if filename.endswith("@stub.json"):
        return True
    if not isinstance(entry, dict):
        return True
    return (
        entry.get("source_kind") == STUB_SOURCE_KIND
        or entry.get("pack_version") == STUB_PACK_VERSION
    )


def _read_cache_entry(cache_root: Path, filename: str, class_type: str) -> dict[str, Any] | None:
    path = cache_root / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    entry = data.get(class_type)
    return entry if isinstance(entry, dict) else None


def capture_tier(cache_root: Path, class_type: str) -> int:
    """Rank of the existing capture for *class_type*; ``-1`` when a gap.

    A class counts as missing (replaceable) when it is absent from index.json,
    stub-indexed/stub-stamped, unattested in the provenance ledger, or attested
    without any pin.
    """
    index = _read_existing_index(cache_root)
    filename = index.get(class_type)
    if not filename:
        return _MISSING_TIER
    entry = _read_cache_entry(cache_root, filename, class_type)
    if _is_stub_index_row(filename, entry):
        return _MISSING_TIER
    if not _is_pinned(_provenance_pack_row(_load_provenance(cache_root), filename)):
        return _MISSING_TIER
    source_kind = entry.get("source_kind")
    rank = _TIER_RANK.get(source_kind)
    if rank is not None:
        return rank
    return _RUNTIME_TIER


def missing_live_captures(
    class_types: list[str] | set[str],
    *,
    cache_dir: str | Path | None = None,
) -> list[str]:
    """Class types lacking a live (attested, non-stub, pinned) capture.

    ``list_classes()`` alone is not sufficient: indexed-but-stubbed and
    unattested rows are gaps too.  Shared by ensure / validate-coverage /
    doctor / preflight tests.
    """
    cache_root = _cache_root(cache_dir)
    return sorted(ct for ct in class_types if capture_tier(cache_root, ct) < 0)


# ---------------------------------------------------------------------------
# Persist glue
# ---------------------------------------------------------------------------


def _to_raw_dump(entry: dict[str, Any]) -> dict[str, Any]:
    """Adapt one ``extract.normalize_entry`` result to the raw dump shape
    ``build_cache`` expects (``input`` singular, ``output`` type list)."""
    outputs = entry.get("outputs") or []
    outputs = [o for o in outputs if isinstance(o, dict)]
    return {
        "input": entry.get("inputs") or {},
        "input_order": entry.get("input_order") or {},
        "output": [o.get("type") for o in outputs],
        "output_name": [o.get("name", "") for o in outputs],
        "output_is_list": [bool(o.get("is_list")) for o in outputs],
        "python_module": entry.get("python_module", ""),
        "category": entry.get("category", ""),
        "name": entry.get("name", ""),
        "display_name": entry.get("display_name", ""),
        "description": entry.get("description", ""),
        "function": entry.get("function", ""),
    }


def persist_on_demand_pack(
    *,
    pack_slug: str,
    registry_pack_version: str | None,
    repo: str,
    locked_commit: str,
    extraction_rung: str,
    entries: dict[str, OrderedDict[str, Any]],
    cache_dir: str | Path | None = None,
    source: str | None = None,
) -> PersistResult:
    """Persist one on-demand pack extract with honest identity and provenance.

    Merge semantics only (``full_pack_refresh=False``); afterwards the two-layer
    file hygiene strips non-newly-captured classes from the new on-demand file
    and restores pre-existing index mappings, so the on-demand file's keys equal
    exactly this extraction's classes and higher-tier captures are untouched.
    When *registry_pack_version* is ``None`` (registry had no entry) the
    provenance records ``null`` and an optional ``source`` (e.g. ``direct_url``).
    """
    if extraction_rung not in SOURCE_KIND_BY_RUNG:
        raise ValueError(f"unknown extraction rung: {extraction_rung!r}")
    source_kind = SOURCE_KIND_BY_RUNG[extraction_rung]
    new_tier = _TIER_RANK[source_kind]
    sha7 = locked_commit[:7]
    filename = f"{pack_slug}@{source_kind}-{sha7}.json"
    evidence_identity = f"on_demand:{extraction_rung}:{locked_commit}"
    cache_root = _cache_root(cache_dir)

    # --- Tier guard: drop classes already covered at same-or-higher tier ------
    skipped: list[str] = []
    captured: dict[str, OrderedDict[str, Any]] = {}
    for class_type, entry in sorted(entries.items()):
        if capture_tier(cache_root, class_type) >= new_tier:
            skipped.append(class_type)
        else:
            captured[class_type] = entry

    if not captured:
        return PersistResult(no_op=True, skipped_classes=skipped)

    raw_dump = {ct: _to_raw_dump(entry) for ct, entry in captured.items()}

    index_before = _read_existing_index(cache_root)

    # --- build_cache with MERGE semantics ------------------------------------
    cache_root.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".json", dir=cache_root, prefix="on-demand-dump-")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(raw_dump, fh, indent=2, sort_keys=True, ensure_ascii=False)
        build_cache(
            tmp_path,
            f"{source_kind}-{sha7}",
            cache_dir=cache_root,
            identity=CacheIdentity(
                pack_slug=pack_slug,
                pack_version=f"{source_kind}-{sha7}",
                git_commit=locked_commit,
                evidence_identity=evidence_identity,
                source_kind=source_kind,
            ),
            full_pack_refresh=False,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    # --- Hygiene layer (a): strip non-newly-captured classes from the file ---
    # Classes already indexed into THIS same versioned file (a prior extract of
    # the same pack at the same tier+commit) stay — stripping them would orphan
    # their index rows. Everything else (merged in from other files) goes.
    filepath = cache_root / filename
    pack_data = json.loads(filepath.read_text(encoding="utf-8"))
    keep = set(captured) | {ct for ct, f in index_before.items() if f == filename}
    stripped = OrderedDict((ct, e) for ct, e in sorted(pack_data.items()) if ct in keep)
    filepath.write_text(
        json.dumps(stripped, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- Hygiene layer (b): restore pre-existing index mappings --------------
    index_path = cache_root / "index.json"
    index: dict[str, Any] = {}
    try:
        loaded = json.loads(index_path.read_text(encoding="utf-8"))
        index = loaded if isinstance(loaded, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    for class_type, previous_file in index_before.items():
        if class_type not in captured and index.get(class_type) == filename:
            index[class_type] = previous_file
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- Attest provenance ---------------------------------------------------
    from vibecomfy.commands.schemas import _write_provenance as _schemas_write

    provenance = _load_provenance(cache_root)
    packs = provenance.get("packs")
    if not isinstance(packs, dict):
        packs = {}
    row: dict[str, Any] = {
        "pack": pack_slug,
        "repo": repo,
        "locked_commit": locked_commit,
        "schema_sha256": hashlib.sha256(filepath.read_bytes()).hexdigest(),
        "source_kind": source_kind,
        "extraction_rung": extraction_rung,
        "registry_pack_version": registry_pack_version,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
    if source is not None:
        row["source"] = source
    packs[filename] = row
    provenance["packs"] = packs
    provenance["class_count"] = len(index)
    _schemas_write(provenance, cache_root)
    # The hygiene pass edits the compatibility-root artifacts after
    # build_cache's atomic publication. Recommit that final state so readers
    # using CURRENT cannot observe the pre-hygiene merged pack generation.
    republish_cache_root(cache_root)

    reset_cache()
    return PersistResult(
        no_op=False,
        filename=filename,
        written_classes=sorted(captured),
        skipped_classes=skipped,
    )
