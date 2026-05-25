"""Compatibility shim for the retired narrative codemod.

The v2.6 ready-template migration path is ``tools.convert_ready_templates`` and
``vibecomfy.porting.emitter``. This module remains import-compatible for old
analysis helper tests, but its command-line codemod surface no longer contains
or runs an independent emitter.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

from tools._legacy import narrate_template as _legacy

# Historical helper API used by older unit tests. Keep these imports explicit so
# the active command-line path below cannot accidentally fall back to the old
# codemod emitter.
_add_metadata_invariant = _legacy._add_metadata_invariant
_add_output_slot_comments = _legacy._add_output_slot_comments
_inline_private_knobs = _legacy._inline_private_knobs
_widget_position_to_index = _legacy._widget_position_to_index
run_analyzer = _legacy.run_analyzer
cmd_verify = _legacy.cmd_verify


def __getattr__(name: str) -> Any:
    return getattr(_legacy, name)


def _is_v26_ready_source(source: str) -> bool:
    # Recognize both the legacy v2.6 `with new_workflow(...) as wf:` form and
    # the v2.7 (T7) with-less `wf = new_workflow(...)` form via their common
    # call substring (no codemod logic — this stays a pure compatibility shim).
    return "new_workflow(READY_METADATA, source_path=__file__)" in source


def _emit_existing_v26(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if not _is_v26_ready_source(source):
        raise RuntimeError(
            "tools.narrate_template is retired as a codemod. "
            "Use `python -m tools.convert_ready_templates --all --dry-run` or "
            "the canonical vibecomfy.porting.emitter path."
        )
    return source


def _write_or_print(text: str, *, original: str, out: Path | None, dry_run: bool, diff: bool) -> None:
    if diff:
        sys.stdout.write(
            "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    text.splitlines(keepends=True),
                    fromfile="original",
                    tofile="v2.6-ready",
                )
            )
        )
        return
    if dry_run or out is None:
        sys.stdout.write(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=None, help="Path to an already-v2.6 ready-template .py file")
    parser.add_argument("--out", type=Path, default=None, help="Output path")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing")
    parser.add_argument("--diff", action="store_true", help="Print a unified diff against the original")
    parser.add_argument("--analyze", type=Path, default=None, dest="analyze_path", help="Run legacy static analysis and emit JSON findings")
    parser.add_argument("--json", action="store_true", default=False, help="Accepted for compatibility with --analyze/--verify")
    parser.add_argument("--verify", nargs=2, type=Path, metavar=("ORIGINAL", "CANDIDATE"), help="Verify candidate parity using the legacy verifier")
    parser.add_argument("--mode", type=str, default="restructure", choices=["annotate", "restructure"], help="Accepted for compatibility; codemod emission is retired")
    args = parser.parse_args(argv)

    if args.analyze_path is not None:
        if not args.analyze_path.is_file():
            print(f"error: {args.analyze_path} not found", file=sys.stderr)
            return 2
        json.dump(run_analyzer(args.analyze_path), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.verify:
        orig_path, cand_path = args.verify
        for p in (orig_path, cand_path):
            if not p.is_file():
                print(f"error: {p} not found", file=sys.stderr)
                return 2
        return cmd_verify(orig_path, cand_path)

    if args.input is None:
        parser.error("either provide an input file or use --verify ORIGINAL CANDIDATE")
    if not args.input.is_file():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2

    original = args.input.read_text(encoding="utf-8")
    try:
        emitted = _emit_existing_v26(args.input)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _write_or_print(emitted, original=original, out=args.out, dry_run=args.dry_run, diff=args.diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
