from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    ConversionWriteError,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.porting.layout_store import write_layout
from vibecomfy.porting.workbench import analyze_source, load_port_source

from ._shared import (
    _attach_contract_fields,
    _attach_report_strict_ready,
    _attach_top_level_strict_ready,
    _emit_convert_payload,
    _emit_strict_ready_load_failure,
    _inject_schema_source_metadata,
)


def _cmd_port_convert(args: argparse.Namespace) -> int:
    from vibecomfy.commands import port as _port

    dry_run = getattr(args, "dry_run", False)
    diff_mode = getattr(args, "diff", False)
    all_mode = getattr(args, "all", False)

    # --all mode: refuse any mode that would write files
    if all_mode:
        if not dry_run and not diff_mode:
            print("--all requires --dry-run (or --diff). Refusing to write files in bulk.", file=sys.stderr)
            return 1
        if args.out:
            print("--all with --out is not supported. Use --dry-run --diff for corpus-wide preview.", file=sys.stderr)
            return 1
        _run_convert_all(args)
        return 0

    # --out is required for write mode
    if not args.out and not dry_run and not diff_mode:
        print("--out is required for write mode. Use --dry-run for read-only preview.", file=sys.stderr)
        return 1

    schema_provider = _port._build_conversion_provider(args)
    port_mode: str = (
        "strict_ready"
        if getattr(args, "strict_ready_template", False)
        else "auto"
    )
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=args.head_check_models,
            mode=port_mode,
        )
        _inject_schema_source_metadata(report, args)
        if getattr(args, "strict_ready_template", False):
            _port._apply_strict_ready_template_gate(report)
        if report.has_errors:
            payload = {
                "status": "error",
                "report": report.to_json(),
                "message": "port convert stopped because port check found hard errors.",
            }
            _attach_contract_fields(payload["report"])
            _attach_report_strict_ready(payload["report"])
            _emit_convert_payload(payload, json_output=args.json)
            return 1

        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
        result = port_convert_workflow(
            loaded.workflow,
            ready_id=args.ready_id,
            source_path=loaded.source_path,
            provenance=report.provenance,
            source_hash=report.source_hash,
            workflow_shape=report.workflow_shape,
            schema_provider=schema_provider,
            raw_workflow=loaded.raw_workflow,
            keep_virtual_wires=bool(getattr(args, "keep_virtual_wires", False)),
        )
    except Exception as exc:
        return _emit_strict_ready_load_failure(
            args,
            exc,
            operation="convert",
            strict_enabled=bool(getattr(args, "strict_ready_template", False) or args.ready_id),
        )

    # Derive target path for dry-run diff mode
    if args.out:
        out = Path(args.out)
    elif dry_run or diff_mode:
        # Derive target from ready-template argument
        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
        out = Path(loaded.source_path) if loaded.source_path else Path(args.workflow)
    else:
        print("--out is required for write mode.", file=sys.stderr)
        return 1

    try:
        write_result = port_convert_and_write(
            result,
            out,
            dry_run=dry_run,
            diff=diff_mode,
        )
    except ManualTemplateRefusal as exc:
        # In dry-run mode, skip manual refusal and show the diff anyway
        if dry_run:
            print(f"port convert note: {exc} (showing dry-run diff anyway)")
            # Compute diff directly
            original = out.read_text(encoding="utf-8") if out.exists() else ""
            import difflib
            diff_lines = difflib.unified_diff(
                original.splitlines(keepends=True) if original else [],
                result.text.splitlines(keepends=True),
                fromfile=str(out),
                tofile=f"{out} (emitted)",
            )
            parity = "ok" if result.validation and result.validation.parity_ok is True else (
                "failed" if result.validation and result.validation.parity_ok is False else "unknown"
            )
            print(f"parity: {parity}")
            print(f"LOC: {len(original.splitlines()) if original else 0} → {len(result.text.splitlines())} ({'+' if not original or len(result.text.splitlines()) >= len(original.splitlines()) else ''}{len(result.text.splitlines()) - (len(original.splitlines()) if original else 0)})")
            print("".join(diff_lines))
            return 0

        print(f"port convert refused: {exc}", file=sys.stderr)
        payload = {
            "status": "refused",
            "out": str(out),
            "message": str(exc),
            "conversion": result.to_json(),
            "report": report.to_json(),
        }
        _attach_contract_fields(payload["report"])
        _attach_report_strict_ready(payload["report"])
        _emit_convert_payload(payload, json_output=args.json)
        return 1
    except ConversionWriteError as exc:
        print(f"port convert failed: {exc}", file=sys.stderr)
        payload = {
            "status": "error",
            "out": str(out),
            "message": str(exc),
            "conversion": result.to_json(),
            "report": report.to_json(),
        }
        _attach_top_level_strict_ready(payload)
        _attach_contract_fields(payload["report"])
        _emit_convert_payload(payload, json_output=args.json)
        return 1

    # Emit layout sidecar alongside the .py (skip in dry-run/diff)
    if not dry_run and not diff_mode:
        try:
            write_layout(out, loaded.workflow)
        except Exception:
            pass  # Sidecar write is best-effort; never block the main convert

    payload = {
        "status": "ok" if write_result["written"] or write_result["dry_run"] else "error",
        "out": str(out),
        "conversion": result.to_json(),
        "report": report.to_json(),
        "write": write_result,
    }
    _attach_top_level_strict_ready(payload)
    _attach_contract_fields(payload["report"])
    _attach_report_strict_ready(payload["report"])
    _emit_convert_payload(payload, json_output=args.json)
    return 0


def _run_convert_all(args: argparse.Namespace) -> None:
    """Run dry-run diff across all ready templates."""
    from vibecomfy.analysis.corpus import build_corpus_snapshot
    from vibecomfy.commands import port as _port

    snapshot = build_corpus_snapshot()
    diff_mode = getattr(args, "diff", False)

    for tpl in snapshot.templates_list:
        tpl_path = Path(tpl["path"])
        if not tpl_path.is_file():
            continue
        try:
            original = tpl_path.read_text(encoding="utf-8")
        except OSError:
            continue

        schema_provider = _port._build_conversion_provider(args)
        try:
            loaded = load_port_source(str(tpl_path), schema_provider=schema_provider)
            result = port_convert_workflow(
                loaded.workflow,
                source_path=str(tpl_path),
                schema_provider=schema_provider,
                raw_workflow=loaded.raw_workflow,
            )
        except Exception as exc:
            print(f"{tpl['id']}: error: {type(exc).__name__}: {exc}")
            continue

        parity = "ok" if result.validation and result.validation.parity_ok is True else (
            "failed" if result.validation and result.validation.parity_ok is False else ("unknown" if result.validation else "no-validation")
        )
        original_loc = len([l for l in original.splitlines() if l.strip()])
        emitted_loc = len([l for l in result.text.splitlines() if l.strip()])
        delta = emitted_loc - original_loc

        print(f"{tpl['id']}: parity={parity} LOC {original_loc}→{emitted_loc} ({'+' if delta >= 0 else ''}{delta})")

        if diff_mode and result.text != original:
            import difflib
            diff_lines = difflib.unified_diff(
                original.splitlines(keepends=True),
                result.text.splitlines(keepends=True),
                fromfile=str(tpl_path),
                tofile=f"{tpl_path} (emitted)",
            )
            diff_text = "".join(diff_lines)
            if diff_text:
                print(diff_text[:2000])  # Truncate per-template diff
