"""Regenerate the canonical ``tests/snapshots/*.{api,class_types,widget_values}.json`` artifacts.

For every committed snapshot stem this script loads the corresponding ready
template via ``vibecomfy.load_workflow_any``, compiles to the ComfyUI API dict,
and rederives the three sidecar artifacts to match the canonicalisation already
present on disk. Use ``--check`` in CI to verify nothing has drifted; use
``--write`` (default) locally after a deliberate snapshot-bearing change.

The canonicalisation helpers and the stem-to-ready-id registry live in
``vibecomfy.testing.snapshot`` and ``vibecomfy.testing.snapshot_registry`` so
this script and the ``vibecomfy test`` CLI share exactly one source of truth.
"""
from __future__ import annotations

import argparse
import difflib
import fnmatch
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from vibecomfy.testing.snapshot import (
    STEM_TO_READY_ID,
    _canonical_api_text,
    _canonical_class_types_text,
    _canonical_widget_values_text,
    _is_link,  # noqa: F401 — re-exported for backwards compat with importers of this script
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO_ROOT / "tests" / "snapshots"


def _atomic_write(target: Path, payload: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(target)


def _build_payloads(ready_id: str) -> dict[str, str]:
    # Imported lazily so ``--help`` works without pulling the full IR stack.
    from vibecomfy import load_workflow_any

    workflow = load_workflow_any(ready_id)
    api = workflow.compile("api")
    return {
        "api.json": _canonical_api_text(api),
        "class_types.json": _canonical_class_types_text(api),
        "widget_values.json": _canonical_widget_values_text(api),
    }


def _summarise(stem: str, ready_id: str, results: dict[str, tuple[str, str]], updated: bool) -> str:
    changed_suffixes = [suffix for suffix, (committed, regenerated) in results.items() if committed != regenerated]
    if not changed_suffixes:
        return f"OK: {ready_id} (3 files unchanged)"
    label = "UPDATED" if updated else "DRIFT"
    parts: list[str] = []
    for suffix in changed_suffixes:
        committed, regenerated = results[suffix]
        plus = sum(1 for line in difflib.ndiff(committed.splitlines(), regenerated.splitlines()) if line.startswith("+ "))
        minus = sum(1 for line in difflib.ndiff(committed.splitlines(), regenerated.splitlines()) if line.startswith("- "))
        parts.append(f"{suffix} +{plus} -{minus}")
    return f"{label}: {ready_id} ({', '.join(parts)})"


def _discover_stems(filter_glob: str | None) -> list[str]:
    stems = sorted({path.name.split(".")[0] for path in SNAPSHOT_DIR.glob("*.api.json")})
    if filter_glob:
        stems = [stem for stem in stems if fnmatch.fnmatchcase(stem, filter_glob)]
    return stems


def _validate_stem_mapping(stems: Iterable[str]) -> None:
    missing = [stem for stem in stems if stem not in STEM_TO_READY_ID]
    if missing:
        raise SystemExit(
            "regenerate_snapshots: unmapped snapshot stem(s) — add an entry to STEM_TO_READY_ID: "
            + ", ".join(missing)
        )


def _diff_text(left: str, right: str, label: str) -> str:
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=f"committed/{label}",
            tofile=f"regenerated/{label}",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Diff against committed snapshots; non-zero exit on drift.")
    mode.add_argument("--write", action="store_true", help="Rewrite committed snapshots atomically (default).")
    parser.add_argument("--filter", dest="filter_glob", default=None, help="Restrict to stems matching this glob.")
    args = parser.parse_args(argv)

    check_mode = bool(args.check)
    write_mode = bool(args.write) or not check_mode

    stems = _discover_stems(args.filter_glob)
    if not stems:
        print("regenerate_snapshots: no snapshot stems matched.")
        return 0
    _validate_stem_mapping(stems)

    drift_detected = False
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        for stem in stems:
            ready_id = STEM_TO_READY_ID[stem]
            payloads = _build_payloads(ready_id)
            comparisons: dict[str, tuple[str, str]] = {}
            stem_has_drift = False
            for suffix, regenerated in payloads.items():
                committed_path = SNAPSHOT_DIR / f"{stem}.{suffix}"
                committed = committed_path.read_text(encoding="utf-8") if committed_path.is_file() else ""
                comparisons[suffix] = (committed, regenerated)
                if committed != regenerated:
                    stem_has_drift = True

            if check_mode:
                if stem_has_drift:
                    drift_detected = True
                    print(_summarise(stem, ready_id, comparisons, updated=False))
                    for suffix, (committed, regenerated) in comparisons.items():
                        if committed != regenerated:
                            diff = _diff_text(committed, regenerated, f"{stem}.{suffix}")
                            if diff:
                                sys.stdout.write(diff)
                    # Also stage the regenerated payload to the tmp dir for any
                    # downstream tooling that wants to inspect the rebuild.
                    for suffix, regenerated in payloads.items():
                        _atomic_write(tmp_root / f"{stem}.{suffix}", regenerated)
                else:
                    print(_summarise(stem, ready_id, comparisons, updated=False))
            else:  # write_mode
                if stem_has_drift:
                    for suffix, regenerated in payloads.items():
                        _atomic_write(SNAPSHOT_DIR / f"{stem}.{suffix}", regenerated)
                    print(_summarise(stem, ready_id, comparisons, updated=True))
                else:
                    print(_summarise(stem, ready_id, comparisons, updated=False))

    if check_mode and drift_detected:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
