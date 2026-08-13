"""Canonically migrate serialized VibeWorkflow corpus envelopes.

Only three schema changes are permitted: add a missing top-level ``groups``
list, remove top-level ``compiled_api``, and add a missing integer first-class
``mode`` to each node. Every output is staged and validated before write mode
replaces a single source file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from vibecomfy.ingest import from_envelope
from vibecomfy.testing.canonical import canonical_form


def _json_pointer(parts: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def _diff_keys(
    before: Any,
    after: Any,
    parts: tuple[str, ...] = (),
) -> tuple[list[str], list[str], list[str]]:
    """Return recursively added, removed, and changed JSON-pointer keys."""
    if isinstance(before, dict) and isinstance(after, dict):
        added: list[str] = []
        removed: list[str] = []
        changed: list[str] = []
        before_keys = set(before)
        after_keys = set(after)
        added.extend(_json_pointer(parts + (str(key),)) for key in sorted(after_keys - before_keys))
        removed.extend(_json_pointer(parts + (str(key),)) for key in sorted(before_keys - after_keys))
        for key in sorted(before_keys & after_keys):
            child_added, child_removed, child_changed = _diff_keys(
                before[key], after[key], parts + (str(key),)
            )
            added.extend(child_added)
            removed.extend(child_removed)
            changed.extend(child_changed)
        return added, removed, changed
    if before != after:
        return [], [], [_json_pointer(parts)]
    return [], [], []


def _canonical_hash(api: dict[str, Any]) -> str:
    canonical = canonical_form(api)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _execution_hash(raw: dict[str, Any], *, prefer_stored: bool) -> tuple[str, str]:
    """Hash stored pre-migration evidence when present, otherwise compile fresh."""
    if prefer_stored and "compiled_api" in raw:
        api = raw["compiled_api"]
        if not isinstance(api, dict):
            raise ValueError("compiled_api must be a mapping when present")
        return _canonical_hash(api), "compiled_api"
    return _canonical_hash(from_envelope(raw).compile("api")), "compile(api)"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corpus_files(corpus_dir: Path) -> tuple[list[Path], list[Path]]:
    if corpus_dir.name.endswith(".layout.json"):
        raise ValueError(f"layout sidecar cannot be migrated explicitly: {corpus_dir}")
    if not corpus_dir.exists():
        raise FileNotFoundError(f"corpus directory does not exist: {corpus_dir}")
    if not corpus_dir.is_dir():
        raise NotADirectoryError(f"corpus path is not a directory: {corpus_dir}")
    json_paths = sorted(corpus_dir.glob("*.json"))
    sidecars = [path for path in json_paths if path.name.endswith(".layout.json")]
    envelopes = [path for path in json_paths if not path.name.endswith(".layout.json")]
    if not envelopes:
        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
    return envelopes, sidecars


def _migrate_envelope(raw: dict[str, Any], *, filename: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError(f"{filename}: envelope must be a JSON object")
    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, dict) or "vibecomfy_format_version" not in raw:
        raise ValueError(f"{filename}: JSON file is not a serialized VibeWorkflow envelope")

    workflow = from_envelope(raw)

    # The external-ingest boundary deliberately stamps provenance and an ingest
    # snapshot. Corpus migration is schema-only, so restore all raw metadata
    # before the sole serializer walks the IR.
    workflow.metadata = deepcopy(raw.get("metadata") or {})
    for node_id, node in workflow.nodes.items():
        node.metadata = deepcopy(raw_nodes[node_id]["metadata"])

    migrated = workflow.to_envelope()

    # Batch A's migration contract permits only groups/mode additions and
    # compiled_api removal. Newer optional IR fields must not make the already
    # migrated corpus non-idempotent or force another corpus rewrite.
    for node_id, raw_entry in raw_nodes.items():
        for field_name in ("pos", "size"):
            if field_name not in raw_entry:
                migrated["nodes"][node_id].pop(field_name, None)

    if migrated.get("metadata") != raw.get("metadata"):
        raise ValueError(f"{filename}: top-level metadata changed during serialization")
    for node_id, entry in raw_nodes.items():
        if migrated["nodes"][node_id].get("metadata") != entry.get("metadata"):
            raise ValueError(f"{filename}: node {node_id!r} metadata/_ui changed")

    added, removed, changed = _diff_keys(raw, migrated)
    allowed_added = {"/groups"}
    allowed_added.update(
        _json_pointer(("nodes", str(node_id), "mode"))
        for node_id, entry in raw_nodes.items()
        if "mode" not in entry
    )
    allowed_removed = {"/compiled_api"} if "compiled_api" in raw else set()

    unexpected_added = sorted(set(added) - allowed_added)
    unexpected_removed = sorted(set(removed) - allowed_removed)
    if unexpected_added or unexpected_removed or changed:
        raise ValueError(
            f"{filename}: serializer produced forbidden delta: "
            f"added={unexpected_added}, removed={unexpected_removed}, changed={changed}"
        )
    if "/groups" in added and migrated.get("groups") != []:
        raise ValueError(f"{filename}: missing groups must migrate to []")
    if "/compiled_api" in removed and "compiled_api" in migrated:
        raise ValueError(f"{filename}: compiled_api was not removed")

    modes_added = 0
    modes_defaulted = 0
    mode_values: dict[str, int] = {}
    for node_id, entry in migrated["nodes"].items():
        mode = entry.get("mode")
        if not isinstance(mode, int) or isinstance(mode, bool):
            raise ValueError(f"{filename}: node {node_id!r} mode is not an integer: {mode!r}")
        if "mode" not in raw_nodes[node_id]:
            modes_added += 1
            old_metadata = raw_nodes[node_id].get("metadata") or {}
            old_ui = old_metadata.get("_ui") if isinstance(old_metadata, dict) else None
            ui_mode = old_ui.get("mode") if isinstance(old_ui, dict) else None
            metadata_mode = old_metadata.get("mode") if isinstance(old_metadata, dict) else None
            has_legacy_mode = (
                isinstance(ui_mode, int) and not isinstance(ui_mode, bool)
            ) or (
                isinstance(metadata_mode, int) and not isinstance(metadata_mode, bool)
            )
            if not has_legacy_mode:
                modes_defaulted += 1
        mode_values[str(mode)] = mode_values.get(str(mode), 0) + 1

    canonical_hash_before, canonical_hash_before_source = _execution_hash(
        raw, prefer_stored=True
    )
    canonical_hash_after, canonical_hash_after_source = _execution_hash(
        migrated, prefer_stored=False
    )
    if canonical_hash_before != canonical_hash_after:
        raise ValueError(f"{filename}: canonical execution hash changed")

    delta = {
        "file": filename,
        "added_keys": added,
        "removed_keys": removed,
        "changed_keys": changed,
        "counts": {
            "added_keys": len(added),
            "removed_keys": len(removed),
            "changed_keys": len(changed),
            "nodes": len(raw_nodes),
            "node_modes_added": modes_added,
            "node_modes_defaulted_to_zero": modes_defaulted,
            "node_mode_values_after": mode_values,
        },
        "transformations": {
            "add_groups": int("/groups" in added),
            "remove_compiled_api": int("/compiled_api" in removed),
            "add_node_mode": modes_added,
        },
        "canonical_hash_before": canonical_hash_before,
        "canonical_hash_after": canonical_hash_after,
        "canonical_hash_before_source": canonical_hash_before_source,
        "canonical_hash_after_source": canonical_hash_after_source,
        "metadata_unchanged": True,
        "ui_unchanged": True,
        "permitted_transformations_only": True,
        "would_change": bool(added or removed or changed),
    }
    return migrated, delta


def _stage_report(report_path: Path, report_text: str) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{report_path.name}.", dir=report_path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(report_text)
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    return staged


def migrate_corpus(
    corpus_dir: str | Path,
    *,
    write: bool,
    report_path: str | Path | None = None,
    expected_count: int | None = None,
) -> dict[str, Any]:
    root = Path(corpus_dir).resolve()
    envelopes, sidecars = _corpus_files(root)
    if expected_count is not None and len(envelopes) != expected_count:
        raise ValueError(
            f"expected {expected_count} envelopes, found {len(envelopes)} in {root}"
        )
    resolved_report = Path(report_path).resolve() if report_path is not None else None
    if resolved_report is not None and resolved_report.parent == root:
        raise ValueError("delta report must be written outside the corpus directory")

    sidecar_hashes = {path.name: _file_hash(path) for path in sidecars}
    stage_dir: Path | None = None
    backup_dir: Path | None = None
    staged_report: Path | None = None
    write_committed = False
    deltas: list[dict[str, Any]] = []
    total_nodes = 0
    modes_before = 0
    modes_after = 0
    modes_added = 0
    modes_defaulted = 0
    mode_values_after: dict[str, int] = {}

    if write:
        stage_dir = Path(tempfile.mkdtemp(prefix=".vibecomfy-corpus-stage-", dir=root.parent))

    try:
        for path in envelopes:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw_nodes = raw.get("nodes") if isinstance(raw, dict) else None
            if isinstance(raw_nodes, dict):
                total_nodes += len(raw_nodes)
                modes_before += sum("mode" in entry for entry in raw_nodes.values() if isinstance(entry, dict))
            migrated, delta = _migrate_envelope(raw, filename=path.name)
            modes_after += len(migrated["nodes"])
            modes_added += delta["counts"]["node_modes_added"]
            modes_defaulted += delta["counts"]["node_modes_defaulted_to_zero"]
            for mode, count in delta["counts"]["node_mode_values_after"].items():
                mode_values_after[mode] = mode_values_after.get(mode, 0) + count
            deltas.append(delta)
            if stage_dir is not None:
                serialized = json.dumps(migrated, indent=2, sort_keys=True) + "\n"
                (stage_dir / path.name).write_text(serialized, encoding="utf-8")

        report = {
            "schema_version": 1,
            "mode": "write" if write else "check",
            "corpus_dir": str(root),
            "ok": True,
            "summary": {
                "envelopes": len(envelopes),
                "expected_count": expected_count,
                "count_matches": expected_count is None or len(envelopes) == expected_count,
                "sidecars_untouched": len(sidecars),
                "files_would_change": sum(delta["would_change"] for delta in deltas),
                "nodes": total_nodes,
                "node_modes_before": modes_before,
                "node_modes_added": modes_added,
                "node_modes_defaulted_to_zero": modes_defaulted,
                "node_modes_after": modes_after,
                "node_mode_values_after": mode_values_after,
                "groups_added": sum(delta["transformations"]["add_groups"] for delta in deltas),
                "compiled_api_removed": sum(
                    delta["transformations"]["remove_compiled_api"] for delta in deltas
                ),
                "canonical_hashes_unchanged": sum(
                    delta["canonical_hash_before"] == delta["canonical_hash_after"]
                    for delta in deltas
                ),
                "filenames_unchanged": True,
                "metadata_unchanged": sum(delta["metadata_unchanged"] for delta in deltas),
                "ui_unchanged": sum(delta["ui_unchanged"] for delta in deltas),
                "permitted_transformations_only": all(
                    delta["permitted_transformations_only"] for delta in deltas
                ),
            },
            "sidecars": [
                {
                    "file": path.name,
                    "sha256_before": sidecar_hashes[path.name],
                    "sha256_after": sidecar_hashes[path.name],
                    "untouched": True,
                }
                for path in sidecars
            ],
            "files": deltas,
        }
        report_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if resolved_report is not None:
            staged_report = _stage_report(resolved_report, report_text)

        if write:
            assert stage_dir is not None
            staged_names = sorted(path.name for path in stage_dir.glob("*.json"))
            source_names = sorted(path.name for path in envelopes)
            if staged_names != source_names:
                raise RuntimeError("staged output filenames do not exactly match corpus envelopes")

            # Hard-linked originals make the entire set recoverable if any
            # replacement fails, without duplicating another 466 MB.
            backup_dir = Path(tempfile.mkdtemp(prefix=".vibecomfy-corpus-backup-", dir=root.parent))
            for path in envelopes:
                os.link(path, backup_dir / path.name)
            try:
                for path in envelopes:
                    os.replace(stage_dir / path.name, path)
            except Exception:
                for path in envelopes:
                    backup = backup_dir / path.name
                    if backup.exists():
                        os.replace(backup, path)
                raise

            for path in sidecars:
                if _file_hash(path) != sidecar_hashes[path.name]:
                    raise RuntimeError(f"layout sidecar changed unexpectedly: {path.name}")

        if resolved_report is not None:
            assert staged_report is not None
            os.replace(staged_report, resolved_report)
            staged_report = None
        else:
            sys.stdout.write(report_text)
        write_committed = write
        return report
    finally:
        if backup_dir is not None and not write_committed:
            for path in envelopes:
                backup = backup_dir / path.name
                if backup.exists():
                    os.replace(backup, path)
        if staged_report is not None:
            staged_report.unlink(missing_ok=True)
        if stage_dir is not None:
            shutil.rmtree(stage_dir, ignore_errors=True)
        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", required=True, help="explicit corpus directory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report changes without writing")
    mode.add_argument("--write", action="store_true", help="transactionally replace all envelopes")
    parser.add_argument("--report", help="write the JSON delta report outside the corpus directory")
    parser.add_argument(
        "--expected-count",
        type=int,
        help="fail before staging unless exactly this many envelopes exist",
    )
    args = parser.parse_args(argv)
    try:
        migrate_corpus(
            args.corpus_dir,
            write=args.write,
            report_path=args.report,
            expected_count=args.expected_count,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
