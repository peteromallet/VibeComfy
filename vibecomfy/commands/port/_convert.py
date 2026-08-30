from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
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
        return _run_convert_all(args)

    if not getattr(args, "workflow", None):
        print("workflow is required unless using --all.", file=sys.stderr)
        return 1

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


def _run_convert_all(args: argparse.Namespace) -> int:
    """Run dry-run conversion across all ready templates.

    Text output intentionally follows the historical line-oriented format.
    JSON output is a single aggregate envelope so callers never have to parse
    mixed per-template lines, and conversion failures are reflected in both
    the envelope status and the process exit code.
    """
    from vibecomfy.analysis.corpus import build_corpus_snapshot
    from vibecomfy.commands import port as _port

    snapshot = build_corpus_snapshot()
    diff_mode = getattr(args, "diff", False) is True
    json_output = getattr(args, "json", False) is True
    template_results: list[dict[str, Any]] = []

    def _safe_text(value: object, fallback: str | None) -> str | None:
        if value is None:
            return fallback
        try:
            # ``str(value)`` may preserve a hostile ``str`` subclass when its
            # ``__str__`` returns itself.  Call the builtin slot explicitly so
            # envelope strings are exact builtin strings.
            text = str.__str__(value) if isinstance(value, str) else str(value)
            if type(text) is not str:
                text = str.__str__(text)
            return text if type(text) is str else fallback
        except Exception:
            return fallback

    def _strict_changed(result_text: object, original: str) -> bool:
        try:
            comparison = result_text != original
        except Exception as exc:
            raise TypeError("conversion result text comparison failed") from exc
        if type(comparison) is not bool:
            raise TypeError("conversion result text comparison must return bool")
        return comparison

    def _json_native(value: object) -> object:
        """Normalize the aggregate boundary without trusting result objects."""
        value_type = type(value)
        if value is None or value_type in (bool, int, float, str):
            return value
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return float(value)
        if isinstance(value, str):
            return _safe_text(value, "<unserializable>")
        if isinstance(value, Mapping):
            try:
                items = value.items()
                return {
                    _safe_text(key, "<invalid-key>") or "<invalid-key>":
                    _json_native(item)
                    for key, item in items
                }
            except Exception:
                return "<unserializable>"
        if isinstance(value, (list, tuple)):
            try:
                return [_json_native(item) for item in value]
            except Exception:
                return ["<unserializable>"]
        return _safe_text(value, "<unserializable>")

    def failure_result(
        template_id: object,
        tpl_path: object,
        exc: BaseException,
        *,
        fallback_id: str,
    ) -> dict[str, Any]:
        return {
            "id": _safe_text(template_id, fallback_id),
            "path": _safe_text(tpl_path, None),
            "status": "error",
            "parity": None,
            "original_loc": None,
            "emitted_loc": None,
            "line_count_delta": None,
            "changed": None,
            "error": {
                "type": _safe_text(type(exc).__name__, "Exception"),
                "message": _safe_text(exc, "conversion failed"),
            },
        }

    for row_index, tpl in enumerate(snapshot.templates_list):
        fallback_id = f"<row-{row_index}>"
        template_id: object = fallback_id
        tpl_path: object = None
        try:
            if not isinstance(tpl, Mapping):
                raise TypeError("template row must be an object")
            raw_id = tpl.get("id")
            if raw_id is None:
                raise KeyError("id")
            template_id = raw_id
            raw_path = tpl.get("path")
            if raw_path is None:
                raise KeyError("path")
            tpl_path = raw_path
            source_path = Path(raw_path)
            if not source_path.is_file():
                raise FileNotFoundError(
                    f"template source does not exist: {source_path}"
                )
            original = source_path.read_text(encoding="utf-8")
            schema_provider = _port._build_conversion_provider(args)
            loaded = load_port_source(
                str(source_path),
                schema_provider=schema_provider,
            )
            result = port_convert_workflow(
                loaded.workflow,
                source_path=str(source_path),
                schema_provider=schema_provider,
                raw_workflow=loaded.raw_workflow,
            )

            validation = result.validation
            if validation is None:
                parity = "no-validation"
            elif validation.parity_ok is True:
                parity = "ok"
            elif validation.parity_ok is False:
                parity = "failed"
            else:
                parity = "unknown"
            validation_failed = validation is None or (
                getattr(validation, "ok", True) is False
                or getattr(validation, "parity_ok", None) is False
            )
            original_loc = len([line for line in original.splitlines() if line.strip()])
            emitted_loc = len([line for line in result.text.splitlines() if line.strip()])
            delta = emitted_loc - original_loc
            changed = _strict_changed(result.text, original)
            template_status = "error" if validation_failed else "ok"
            if validation is None:
                validation_error = "conversion produced no validation result"
            else:
                validation_error = (
                    getattr(validation, "error", None)
                    or getattr(validation, "parity_error", None)
                    or "conversion validation failed"
                )

            if json_output:
                template_results.append(
                    {
                        "id": _safe_text(template_id, fallback_id),
                        "path": _safe_text(tpl_path, None),
                        "status": template_status,
                        "parity": parity,
                        "original_loc": original_loc,
                        "emitted_loc": emitted_loc,
                        "line_count_delta": delta,
                        "changed": changed,
                        "error": (
                            {
                                "type": "ValidationError",
                                "message": _safe_text(
                                    validation_error,
                                    "conversion validation failed",
                                ),
                            }
                            if validation_failed
                            else None
                        ),
                    }
                )
            else:
                display_id = _safe_text(template_id, fallback_id) or fallback_id
                print(
                    f"{display_id}: parity={parity} LOC "
                    f"{original_loc}→{emitted_loc} "
                    f"({'+' if delta >= 0 else ''}{delta})"
                )

                if diff_mode and changed:
                    import difflib

                    diff_lines = difflib.unified_diff(
                        original.splitlines(keepends=True),
                        result.text.splitlines(keepends=True),
                        fromfile=str(source_path),
                        tofile=f"{source_path} (emitted)",
                    )
                    diff_text = "".join(diff_lines)
                    if diff_text:
                        print(diff_text[:2000])  # Truncate per-template diff
        except Exception as exc:
            if json_output:
                template_results.append(
                    failure_result(
                        template_id,
                        tpl_path,
                        exc,
                        fallback_id=fallback_id,
                    )
                )
            else:
                display_id = _safe_text(template_id, fallback_id) or fallback_id
                print(
                    f"{display_id}: error: {type(exc).__name__}: "
                    f"{_safe_text(exc, 'conversion failed')}"
                )

    if not json_output:
        # Preserve the historical human-mode exit policy: all-mode was a
        # best-effort report even when one template could not be converted.
        return 0

    error_count = sum(1 for item in template_results if item["status"] == "error")
    template_count = len(template_results)
    payload = {
        "status": "error" if error_count else "ok",
        "mode": "convert_all",
        "dry_run": True,
        "templates": template_results,
        "summary": {
            "template_count": template_count,
            "ok_count": template_count - error_count,
            "error_count": error_count,
            "changed_count": sum(
                1
                for item in template_results
                if item["status"] == "ok" and item["changed"] is True
            ),
        },
    }
    print(json.dumps(_json_native(payload), indent=2, sort_keys=True))
    return 1 if error_count else 0
