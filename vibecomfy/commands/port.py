from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from io import StringIO
from pathlib import Path
from typing import Any

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    ConversionWriteError,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.porting.layout_store import read_layout, read_store, store_from_ui_json, write_layout, write_store
from vibecomfy.porting.lint import lint_ready_template
from vibecomfy.porting.manual_repair import repair_manual_template
from vibecomfy.porting.readability_inventory import build_readability_inventory
from vibecomfy.porting.report import PortIssue, PortReport
from vibecomfy.porting.rules_registry import rules_by_category, to_json as rules_to_json
from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.utils import find_repo_root

READY_ROOT = find_repo_root() / "ready_templates"

from vibecomfy.porting.simulate import simulate_rule
from vibecomfy.porting.strict_ready import (
    STRICT_READY_LOAD_FAILED,
    STRICT_READY_MISSING_OUTPUT_CONTRACT,
    STRICT_READY_UNRESOLVED_WIDGETS,
    STRICT_READY_VIOLATION_CODES,
    StrictReadyContext,
    apply_strict_ready_exceptions,
)
from vibecomfy.porting.widget_aliases import widget_alias_analysis
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA
from vibecomfy.porting.ui_emitter import default_output_path, emit_ui_json
from vibecomfy.porting.workbench import analyze_source, load_port_source
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import ConversionSchemaProvider, get_authoring_schema_provider, get_schema_provider, validate_node_call
from vibecomfy.schema.cache import latest_object_info_cache_path
from vibecomfy.commands.nodes import build_nodes_install_plan_payload


PORT_HELP = """Cheap preflight and Python materialization for ComfyUI workflow ports.

Use `port check` before manual template editing or expensive RunPod validation.
Use `port convert` to turn source workflows into Python scratchpads; pass
`--ready-id kind/name` only when intentionally producing a ready-template
candidate. Use `doctor`/`validate` after conversion, `nodes install-plan` for
custom node install planning, and `fetch` for URL-backed models. Use
`--head-check-models` only when you want network HEAD checks for model URLs.
"""


def _cmd_port_check(args: argparse.Namespace) -> int:
    try:
        payload, report = build_port_check_payload(args)
    except Exception as exc:
        return _emit_strict_ready_load_failure(
            args,
            exc,
            operation="check",
            strict_enabled=getattr(args, "strict_ready_template", False),
        )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_check(report))
    return 1 if report.has_errors else 0


def build_port_check_payload(args: argparse.Namespace) -> tuple[dict[str, Any], Any]:
    schema_provider = _build_authoring_provider(args)
    setattr(args, "_schema_provider_name", type(schema_provider).__name__)
    port_mode: str = "strict_ready" if getattr(args, "strict_ready_template", False) else "auto"
    report = analyze_source(
        args.workflow,
        schema_provider=schema_provider,
        head_check_models=args.head_check_models,
        mode=port_mode,
    )
    if getattr(args, "strict_ready_template", False):
        _apply_strict_ready_template_gate(report)
    _inject_schema_source_metadata(report, args)
    payload = report.to_json()
    _attach_contract_fields(payload)
    _attach_report_strict_ready(payload)
    return payload, report


def _cmd_port_convert(args: argparse.Namespace) -> int:
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

    schema_provider = _build_conversion_provider(args)
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
            _apply_strict_ready_template_gate(report)
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

        schema_provider = _build_conversion_provider(args)
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


def _attach_contract_fields(payload: dict[str, Any]) -> None:
    metadata = payload.get("metadata")
    contract = metadata.get("contract") if isinstance(metadata, dict) else None
    if not isinstance(contract, dict):
        return
    payload["contract"] = contract
    payload["contract_shape"] = contract.get("contract_shape")
    payload["public_inputs"] = contract.get("public_inputs", [])
    payload["public_outputs"] = contract.get("public_outputs", [])
    payload["graph_contract"] = contract.get("graph_contract", {})


def _attach_top_level_strict_ready(payload: dict[str, Any]) -> None:
    conversion = payload.get("conversion")
    validation = conversion.get("validation") if isinstance(conversion, dict) else None
    if not isinstance(validation, dict):
        return
    strict_diagnostics = validation.get("strict_ready_diagnostics")
    if strict_diagnostics is None:
        return
    payload["strict_ready_ok"] = validation.get("strict_ready_ok")
    payload["strict_ready_diagnostics"] = strict_diagnostics


def _attach_report_strict_ready(payload: dict[str, Any]) -> None:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return
    metadata = payload.get("metadata")
    strict_metadata = metadata.get("strict_ready") if isinstance(metadata, dict) else None
    strict_diagnostics = [
        item for item in diagnostics
        if isinstance(item, dict)
        and (
            item.get("code") in STRICT_READY_VIOLATION_CODES
            or (isinstance(item.get("detail"), dict) and item["detail"].get("category") == "strict_ready")
        )
    ]
    if not strict_diagnostics and not isinstance(strict_metadata, dict):
        return
    payload["strict_ready_diagnostics"] = strict_diagnostics
    payload["strict_ready_ok"] = (
        bool(strict_metadata.get("ok"))
        if isinstance(strict_metadata, dict) and "ok" in strict_metadata
        else not any(item.get("severity") == "error" for item in strict_diagnostics)
    )


def _emit_strict_ready_load_failure(
    args: argparse.Namespace,
    exc: Exception,
    *,
    operation: str,
    strict_enabled: bool,
) -> int:
    if not strict_enabled:
        print(f"port {operation} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    issue = PortIssue(
        code=STRICT_READY_LOAD_FAILED,
        message=f"Strict ready-template {operation} failed before workflow build: {type(exc).__name__}: {exc}",
        severity="error",
        detail={
            "category": "strict_ready",
            "target": "source",
            "workflow": getattr(args, "workflow", None),
            "exception_type": type(exc).__name__,
        },
        recommendation="Fix source loading/build errors before running strict-ready validation.",
    )
    report = PortReport(
        source=str(getattr(args, "workflow", "")),
        workflow_shape={},
        output_mode=operation,
        diagnostics=[issue],
        metadata={
            "strict_ready": {
                "ok": False,
                "diagnostic_count": 1,
                "error_count": 1,
            }
        },
    )
    payload = report.to_json()
    payload["strict_ready_ok"] = False
    payload["strict_ready_diagnostics"] = [issue.to_json()]
    if operation == "convert":
        convert_payload = {
            "status": "error",
            "message": "port convert stopped because strict-ready source loading failed.",
            "report": payload,
            "strict_ready_ok": False,
            "strict_ready_diagnostics": [issue.to_json()],
        }
        if getattr(args, "json", False):
            print(json.dumps(convert_payload, indent=2, sort_keys=True))
        else:
            print(convert_payload["message"], file=sys.stderr)
            print(f"- error: {issue.code}: {issue.message}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_check(report))
    return 1


def _cmd_port_widgets(args: argparse.Namespace) -> int:
    schema_provider = _build_authoring_provider(args)
    setattr(args, "_schema_provider_name", type(schema_provider).__name__)
    try:
        loaded = load_port_source(
            args.workflow,
            schema_provider=schema_provider,
            use_comfy_converter=False,
        )
    except Exception as exc:
        print(f"port widgets failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    api_prompt = loaded.workflow.compile("api")
    widget_analysis = widget_alias_analysis(
        api_prompt,
        raw_workflow=loaded.raw_workflow,
        schema_provider=schema_provider,
    )
    payload = {
        "source": args.workflow,
        "source_hash": loaded.source_hash,
        **widget_analysis,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_widgets(payload))
    return 0


def _print_change_report(
    report: Any,
    *,
    json_mode: bool = False,
) -> None:
    """Print a ChangeReport to stderr (text) or stdout (JSON)."""
    from dataclasses import asdict  # noqa: PLC0415
    if json_mode:
        print(json.dumps({"change_report": asdict(report)}, indent=2, sort_keys=True))
    else:
        ce = report.content_edits
        ids = report.identity_stabilization
        lines = ["[change-report]"]
        lines.append(
            f"  content: preserved={len(ce.preserved)} edited={len(ce.edited)}"
            f" new={len(ce.new_auto_placed)} removed={len(ce.removed)}"
            f" virtual_wires_degraded={len(ce.virtual_wires_degraded)}"
        )
        if ids.bridge_minted:
            lines.append(f"  identity: bridge_minted={len(ids.bridge_minted)}")
        if ids.unmatched_legacy:
            lines.append(f"  identity: unmatched_legacy={len(ids.unmatched_legacy)}")
        if ids.definition_relayout:
            lines.append(f"  identity: definition_relayout={ids.definition_relayout}")
        print("\n".join(lines), file=sys.stderr)


def _print_from_overrides(
    overrides: dict[str, Any],
    *,
    json_mode: bool = False,
) -> None:
    """Print ``--from`` overrides (conflict resolution) to stderr or stdout.

    Called when both a sidecar and ``--from`` exist and ``--from`` entries
    override specific UIDs.  The sidecar is the base; ``--from`` provides
    explicit per-uid overrides.
    """
    if json_mode:
        print(json.dumps({"from_overrides": sorted(overrides.keys())}, indent=2, sort_keys=True))
    else:
        lines = [f"[from-overrides] {len(overrides)} uid(s) overridden from --from:"]
        for uid in sorted(overrides):
            lines.append(f"  {uid}")
        print("\n".join(lines), file=sys.stderr)


def _print_recovery_report(
    recovery_report: list[dict[str, Any]],
    *,
    json_mode: bool = False,
) -> None:
    """Print a structured recovery report to stderr (text) or stdout (JSON).

    The recovery report is populated by ``emit_ui_json`` only on the non-strict
    warn-and-emit path.  It records per-node provenance for schema-less nodes,
    low-confidence widget-schema-fallback nodes, and any widget-length-check
    warnings encountered during emission.

    Precedence note: ``--strict`` fails *before* the report is populated
    (``emit_ui_json`` raises ``ValueError``) — the except-arm in
    ``_cmd_port_export`` handles that path separately and the recovery report
    is never printed.
    """
    if json_mode:
        orphaned_count = sum(1 for e in recovery_report if e.get("orphaned_route"))
        payload: dict[str, Any] = {
            "recovery_report": {
                "summary": {
                    "total_nodes": len(recovery_report),
                    "schema_less": sum(1 for e in recovery_report if e.get("schema_less")),
                    "low_confidence": sum(
                        1 for e in recovery_report
                        if not e.get("schema_less") and e.get("confidence") is not None and e["confidence"] <= 0.3
                    ),
                    "widget_length_check_warnings": sum(
                        1 for e in recovery_report if e.get("widget_length_check")
                    ),
                    "nodes_with_diagnostic": sum(1 for e in recovery_report if e.get("diagnostic")),
                    "orphaned_routes": orphaned_count,
                },
                "entries": recovery_report,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        lines: list[str] = ["[recovery-report]"]
        schema_less_nodes = [e for e in recovery_report if e.get("schema_less")]
        low_conf_nodes = [
            e for e in recovery_report
            if not e.get("schema_less") and e.get("confidence") is not None and e["confidence"] <= 0.3
        ]
        widget_warn_nodes = [e for e in recovery_report if e.get("widget_length_check")]
        orphaned_nodes = [e for e in recovery_report if e.get("orphaned_route")]

        if schema_less_nodes:
            lines.append(f"  schema-less nodes ({len(schema_less_nodes)}):")
            for e in schema_less_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): schema-less — "
                    f"best-effort slots from link appearance order"
                )
        if low_conf_nodes:
            lines.append(f"  low-confidence nodes ({len(low_conf_nodes)}):")
            for e in low_conf_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): "
                    f"confidence={e['confidence']} (widget_schema_fallback)"
                )
        if widget_warn_nodes:
            lines.append(f"  widget-length-check warnings ({len(widget_warn_nodes)}):")
            for e in widget_warn_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): {e.get('widget_length_check')}"
                )
        if orphaned_nodes:
            lines.append(f"  orphaned virtual-wire routes ({len(orphaned_nodes)}):")
            for e in orphaned_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): "
                    f"broadcast name={e.get('broadcast_name')!r} — "
                    f"no matching SetNode source"
                )
        if not schema_less_nodes and not low_conf_nodes and not widget_warn_nodes and not orphaned_nodes:
            lines.append("  (no issues — all nodes resolved with high confidence)")
        print("\n".join(lines), file=sys.stderr)


def _resolve_preserve_source(
    args: argparse.Namespace,
    py_path: Path,
    workflow: Any,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    """Resolve the preserve source for ``port export --to ui``.

    Precedence (highest first):
    1. ``--fresh`` → no preserve (returns ``None, None, None``).
    2. ``--from <path>`` + sidecar conflict → sidecar wins as base;
       ``--from`` entries are per-uid overrides surfaced in the change report.
    3. ``--from <path>`` only → load via ``store_from_ui_json``.
    4. Sidecar only → ``read_store(py_path)``.
    5. Breadcrumb auto-discovery → look for a prior emitted UI JSON at the
       default output path, check ``extra.vibecomfy.prior_path`` matches
       ``py_path``, and if so load it via ``store_from_ui_json``.
    6. No source → fresh (returns ``None, None, None``).

    Returns ``(store_envelope | None, prior_path_str | None, from_overrides | None)``.
    ``from_overrides`` is a dict ``{uid: entry}`` listing UIDs explicitly
    overridden from ``--from`` when both sidecar and ``--from`` exist, else ``None``.
    """
    # 1. --fresh overrides everything
    if getattr(args, "fresh", False):
        return None, None, None

    # 2. Check for both --from and sidecar (conflict case)
    from_path = getattr(args, "from_path", None)
    sidecar_store = read_store(py_path)

    if from_path and sidecar_store:
        # Conflict policy: sidecar wins as base; --from provides per-uid overrides
        from_store = store_from_ui_json(from_path)
        from_entries = from_store.get("entries", {})
        base_entries = sidecar_store.get("entries", {})

        # Identify overridden UIDs: keys present in both that differ
        overrides: dict[str, Any] = {}
        for uid, from_entry in from_entries.items():
            if uid in base_entries and from_entry != base_entries[uid]:
                overrides[uid] = from_entry
            elif uid not in base_entries:
                # New UIDs from --from that aren't in sidecar are also overrides
                overrides[uid] = from_entry

        if overrides:
            # Merge: base = sidecar, apply --from overrides on top
            merged = dict(sidecar_store)
            merged_entries = dict(base_entries)
            merged_entries.update(overrides)
            merged["entries"] = merged_entries
            return merged, str(py_path), overrides
        else:
            # No differences — sidecar is authoritative
            return sidecar_store, str(py_path), None

    # 3. --from <path> only
    if from_path:
        store = store_from_ui_json(from_path)
        return store, str(from_path), None

    # 4. Sidecar only
    if sidecar_store:
        return sidecar_store, str(py_path), None

    # 5. Breadcrumb auto-discovery: look for a prior emitted UI JSON at the
    #    default output path and check its extra.vibecomfy.prior_path.
    candidate_path = default_output_path(workflow, source_template=py_path.stem)
    if candidate_path.exists():
        try:
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            extra_vc = candidate.get("extra", {}).get("vibecomfy", {})
            breadcrumb_prior = extra_vc.get("prior_path")
            if breadcrumb_prior and Path(breadcrumb_prior).resolve() == py_path.resolve():
                store = store_from_ui_json(candidate_path)
                return store, str(candidate_path), None
        except (json.JSONDecodeError, OSError):
            pass

    # 6. No source → fresh
    return None, None, None


def _cmd_port_export(args: argparse.Namespace) -> int:
    if args.to == "json":
        try:
            schema_provider = _build_authoring_provider(args)
            workflow = load_workflow_reference(
                args.workflow,
                schema_provider=schema_provider,
                allow_scratchpad=True,
                ready=getattr(args, "ready", False),
            )
            payload = {
                "status": "ok",
                "workflow": args.workflow,
                "format": "api",
                "api": workflow.export_to_json(format="api"),
            }
        except Exception as exc:
            print(f"port export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload["api"], indent=2, sort_keys=True))
        return 0

    if args.to == "ui":
        recovery_report: list[dict[str, Any]] = []
        change_report_out: list = []
        try:
            schema_provider = _build_conversion_provider(args)
            workflow = load_workflow_reference(
                args.workflow,
                schema_provider=schema_provider,
                allow_scratchpad=True,
                ready=getattr(args, "ready", False),
            )
            py_path = Path(args.workflow)
            store, prior_path_str, from_overrides = _resolve_preserve_source(args, py_path, workflow)

            # M5 Step 16: when the preserve source is a UI JSON on disk (--from
            # or breadcrumb auto-discovery), load it as the guard's "original"
            # so refuse.guard_emit can refuse a corrupted re-emit.
            guard_original_ui: dict[str, Any] | None = None
            if prior_path_str and prior_path_str != str(py_path):
                try:
                    _prior_text = Path(prior_path_str).read_text(encoding="utf-8")
                    _candidate = json.loads(_prior_text)
                    if isinstance(_candidate, dict) and isinstance(_candidate.get("nodes"), list):
                        guard_original_ui = _candidate
                except Exception:
                    guard_original_ui = None

            # Extract sidecar sections for explicit kwargs (for callers that pre-resolved them)
            sidecar_groups = store.get("groups") if store else None
            sidecar_extra = store.get("extra") if store else None
            sidecar_definitions = store.get("definitions") if store else None
            ui_payload = emit_ui_json(
                workflow,
                schema_provider=schema_provider,
                prior_store=store,
                prior_path=prior_path_str,
                strict=getattr(args, "strict", False),
                include_main_positions=getattr(args, "main_positions", False),
                include_virtual_wires=not getattr(args, "no_virtual_wires", False),
                recovery_report=recovery_report,
                groups=sidecar_groups,
                extra=sidecar_extra,
                definitions=sidecar_definitions,
                change_report_out=change_report_out,
                guard_original_ui=guard_original_ui,
            )
            if args.out:
                out_path = Path(args.out)
            else:
                out_path = default_output_path(workflow, source_template=py_path.stem)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(ui_payload, indent=2, sort_keys=True))
            print(f"wrote {out_path}")

            # Emit layout sidecar alongside the UI JSON (best-effort).
            # Build the store from the freshly-emitted ui_payload (which carries
            # correct positions in properties['vibecomfy_uid']).  Do NOT call
            # write_layout(py_path, workflow) here: a workflow loaded from a .py
            # file has no _ui metadata so write_layout would overwrite the valid
            # convert-time sidecar with empty entries.
            try:
                write_store(py_path, store_from_ui_json(ui_payload))
            except Exception:
                pass  # Sidecar write is best-effort; never block the main export

            # --- Change report ---
            if change_report_out:
                _print_change_report(change_report_out[0], json_mode=bool(getattr(args, "json", False)))

            # --- From-overrides report (conflict: --from over sidecar) ---
            if from_overrides:
                _print_from_overrides(from_overrides, json_mode=bool(getattr(args, "json", False)))

            # --- Recovery report (non-strict path) ---
            if recovery_report:
                _print_recovery_report(recovery_report, json_mode=bool(getattr(args, "json", False)))
        except ValueError as exc:
            # Strict-mode failure: schema-less or low-confidence nodes.
            # emit_ui_json raises ValueError BEFORE populating recovery_report,
            # so we report the failure message directly.
            print(f"port export strict failed: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            # M5 Step 16: refusal-spine surfaces RefusedEmit as a typed failure.
            # Detect by class name to avoid an import cycle on the cold path.
            if type(exc).__name__ == "RefusedEmit":
                diff = getattr(exc, "diff", {})
                print(
                    f"port export refused: {exc}",
                    file=sys.stderr,
                )
                if diff:
                    print(
                        json.dumps({"refused_emit": diff}, indent=2, sort_keys=True, default=repr),
                        file=sys.stderr,
                    )
                return 3
            print(f"port export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0

    print(f"unsupported export target: {args.to!r}; supported values: json, ui", file=sys.stderr)
    return 2


def _cmd_port_validate_call(args: argparse.Namespace) -> int:
    try:
        kwargs = json.loads(args.kwargs)
    except json.JSONDecodeError as exc:
        payload = {
            "status": "error",
            "class_type": args.class_type,
            "ok": False,
            "errors": [
                {
                    "code": "invalid_kwargs_json",
                    "message": str(exc),
                    "input": None,
                    "detail": {"position": exc.pos},
                }
            ],
            "provider": None,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"invalid --kwargs JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(kwargs, dict):
        payload = {
            "status": "error",
            "class_type": args.class_type,
            "ok": False,
            "errors": [
                {
                    "code": "invalid_kwargs_json",
                    "message": "--kwargs must decode to a JSON object",
                    "input": None,
                    "detail": {"decoded_type": type(kwargs).__name__},
                }
            ],
            "provider": None,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("--kwargs must decode to a JSON object", file=sys.stderr)
        return 2
    provider = _build_validate_call_provider(args)
    report = validate_node_call(args.class_type, kwargs, provider=provider)
    payload = report.to_json()
    payload["status"] = "ok" if report.ok else "error"
    payload["provider"] = type(provider).__name__
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if report.ok:
            print("ok")
        else:
            for issue in report.issues:
                print(f"{issue.code}: {issue.message}", file=sys.stderr)
    return 0 if report.ok else 1


def _cmd_port_doctor_all(args: argparse.Namespace) -> int:
    if not getattr(args, "json", False):
        print("port doctor-all currently emits machine-readable output; pass --json", file=sys.stderr)
        return 2
    sections = [
        _doctor_all_port_check,
        _doctor_all_nodes_install_plan,
        _doctor_all_validate,
        _doctor_all_doctor,
        _doctor_all_runtime_doctor,
    ]
    started = time.perf_counter()
    results = [section(args) for section in sections]
    findings = [finding for result in results for finding in result.get("findings", [])]
    payload = {
        "status": "ok" if not any(result["status"] == "error" for result in results) else "error",
        "workflow": args.workflow,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "sections": results,
        "summary": {
            "section_count": len(results),
            "ok_sections": sum(1 for result in results if result["status"] == "ok"),
            "warning_sections": sum(1 for result in results if result["status"] == "warning"),
            "error_sections": sum(1 for result in results if result["status"] == "error"),
            "finding_count": len(findings),
        },
        "findings": findings,
        "next_action": _first_next_action(findings) or f"vibecomfy port check {args.workflow} --json",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["status"] == "error" else 0


def _doctor_all_section(name: str, func) -> dict[str, Any]:
    started = time.perf_counter()
    stdout = StringIO()
    stderr = StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            payload, exit_code = func()
        status = "ok" if exit_code == 0 else "error"
        if isinstance(payload, dict) and payload.get("status") == "warning":
            status = "warning"
        return {
            "name": name,
            "status": status,
            "exit_code": exit_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "payload": payload,
            "findings": _normalize_findings(name, payload),
            "stderr": stderr.getvalue(),
            "captured_stdout": stdout.getvalue(),
            "next_action": _payload_next_action(payload),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "error",
            "exit_code": 1,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "payload": None,
            "findings": [
                {
                    "section": name,
                    "severity": "error",
                    "code": "section_exception",
                    "message": f"{type(exc).__name__}: {exc}",
                    "next_action": None,
                }
            ],
            "stderr": stderr.getvalue(),
            "captured_stdout": stdout.getvalue(),
            "next_action": None,
        }


def _doctor_all_port_check(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        payload, report = build_port_check_payload(
            argparse.Namespace(
                workflow=args.workflow,
                json=True,
                head_check_models=False,
                strict_ready_template=False,
                runtime_object_info=False,
                object_info_cache=getattr(args, "object_info_cache", None),
                no_object_info_cache=False,
                server_url=None,
            )
        )
        return payload, 1 if report.has_errors else 0

    return _doctor_all_section(
        "port_check",
        run,
    )


def _doctor_all_nodes_install_plan(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        import vibecomfy.node_packs_install as node_packs_install

        workflow = load_workflow_reference(args.workflow, schema_provider=get_schema_provider("auto"), allow_scratchpad=True, ready=getattr(args, "ready", False))
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        authoring_provider = get_authoring_schema_provider()
        missing_classes = {
            class_type
            for class_type in missing_classes
            if authoring_provider.get_schema(str(class_type)) is None
        }
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
        unresolved = [class_type for class_type in unresolved if class_type in missing_classes]
        packs = [pack for pack in packs if missing_classes & pack.classes]
        payload = {
            "status": "ok" if not unresolved else "error",
            **build_nodes_install_plan_payload(
                args.workflow,
                missing_classes,
                packs,
                unresolved,
            ),
        }
        return payload, 1 if unresolved else 0

    return _doctor_all_section("nodes_install_plan", run)


def _doctor_all_validate(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        from vibecomfy.commands.validate import build_validate_payload

        payload = build_validate_payload(args.workflow)
        return payload, 0 if payload.get("status") == "ok" else 1

    return _doctor_all_section("validate", run)


def _doctor_all_doctor(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        from vibecomfy.commands.doctor import _cmd_doctor

        stdout = StringIO()
        stderr = StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = _cmd_doctor(argparse.Namespace(path=args.workflow, json=True, lint=False, allow_drift=False))
        text = stdout.getvalue().strip()
        payload = json.loads(text) if text else {"status": "error", "errors": ["doctor emitted no JSON"]}
        payload["_captured_stderr"] = stderr.getvalue()
        return payload, exit_code

    return _doctor_all_section("doctor", run)


def _doctor_all_runtime_doctor(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        from vibecomfy.commands.runtime import build_runtime_doctor_payload

        payload = build_runtime_doctor_payload()
        return payload, 0 if payload.get("status") == "ok" else 1

    return _doctor_all_section("runtime_doctor", run)


def _normalize_findings(section: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    findings: list[dict[str, Any]] = []
    for item in payload.get("diagnostics") or []:
        if isinstance(item, dict):
            findings.append(
                {
                    "section": section,
                    "severity": item.get("severity", "warning"),
                    "code": item.get("code", "diagnostic"),
                    "message": item.get("message", ""),
                    "next_action": item.get("recommendation") or payload.get("recommended_command"),
                }
            )
    for key, severity in (("errors", "error"), ("warnings", "warning"), ("missing_models", "error"), ("nodepack_warnings", "warning")):
        for item in payload.get(key) or []:
            findings.append(
                {
                    "section": section,
                    "severity": severity,
                    "code": key.rstrip("s"),
                    "message": str(item),
                    "next_action": payload.get("recommended_command"),
                }
            )
    for item in payload.get("issues") or []:
        if isinstance(item, dict):
            findings.append(
                {
                    "section": section,
                    "severity": item.get("severity", "error"),
                    "code": item.get("code", "issue"),
                    "message": item.get("message", ""),
                    "next_action": payload.get("recommended_command"),
                }
            )
    return findings


def _payload_next_action(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("recommended_command") or payload.get("next_action")


def _first_next_action(findings: list[dict[str, Any]]) -> str | None:
    for finding in findings:
        action = finding.get("next_action")
        if action:
            return str(action)
    return None


def _cmd_port_inventory(args: argparse.Namespace) -> int:
    """Repo-only readability inventory for checked-in ready templates.

    ``port inventory --ready --json`` emits a deterministic, versioned JSON
    report built from the static ``ready_templates/**/*.py`` glob.  The report
    never consults plugin/cwd/user-global paths.
    """
    inventory = build_readability_inventory()
    if args.json:
        print(json.dumps(inventory.to_json(), indent=2, sort_keys=True))
    else:
        print(_render_inventory(inventory))
    return 0


def _cmd_port_repair(args: argparse.Namespace) -> int:
    dry_run = not bool(getattr(args, "write", False))
    try:
        result = repair_manual_template(
            args.workflow,
            mode=args.mode,
            dry_run=dry_run,
            write=bool(getattr(args, "write", False)),
            review_out=args.review_out,
        )
    except Exception as exc:
        print(f"port repair failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    payload = result.to_json()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"port repair: {payload['mode']} {'dry-run' if payload['dry_run'] else 'write'} "
            f"for {payload['path']}"
        )
        print(f"findings: {len(payload['findings'])}; edits: {len(payload['edits'])}")
        if payload.get("review_packet"):
            print(f"review packet: {payload['review_packet']}")
    return 0


def _render_inventory(inventory) -> str:
    entries = inventory.entries
    summary = inventory.summary
    flag_count = sum(1 for e in entries if e.missing_source_provenance)

    lines = [
        f"port inventory: {inventory.template_count} checked-in ready templates",
        f"missing source provenance: {flag_count}",
        f"markers: "
        + " ".join(
            f"{k.split('_', 1)[1]}={v}"
            for k, v in sorted(summary.items())
            if k.startswith("marker_")
        ),
    ]
    # Summary counts
    lines.append(
        f"issues: "
        + ", ".join(
            f"{key}={summary.get(key, 0)}"
            for key in [
                "positional_outs_total",
                "widget_n_fields_total",
                "uuid_class_types_total",
                "n_uuid_variables_total",
                "local_node_copies_total",
                "missing_output_contract",
            ]
        )
    )
    lines.append(f"app_active: {summary.get('app_active', 0)}")
    lines.append(f"templates_with_issues: {summary.get('templates_with_issues', 0)}")

    # Flagged entries
    flagged = [e for e in entries if e.missing_source_provenance]
    if flagged:
        lines.append("")
        lines.append("Flagged (no source provenance):")
        for e in flagged[:20]:
            lines.append(f"  {e.ready_id} ({e.marker})")
        if len(flagged) > 20:
            lines.append(f"  ... {len(flagged) - 20} more flagged entries; rerun with --json for full list")

    return "\n".join(lines)


def _apply_strict_ready_template_gate(report: Any) -> None:
    diagnostics: list[PortIssue] = []
    widget_analysis = (report.metadata or {}).get("widget_analysis") or {}
    unresolved = widget_analysis.get("unresolved_widget_aliases") or []
    schema_backed_classes = {
        str(group.get("class_type"))
        for group in widget_analysis.get("suggestions", [])
        if group.get("schema_source") != "unavailable" or group.get("suggested_schema_entry") is not None
    }
    blocked = [alias for alias in unresolved if str(alias.get("class_type")) in schema_backed_classes]
    if blocked:
        diagnostics.append(PortIssue(
            STRICT_READY_UNRESOLVED_WIDGETS,
            (
                f"Strict ready-template gate found {len(blocked)} unresolved schema-backed positional widget alias"
                f"{'' if len(blocked) == 1 else 'es'}."
            ),
            severity="error",
            detail={
                "category": "strict_ready",
                "target": "widget_aliases",
                "count": len(blocked),
                "examples": blocked[:20],
                "unresolved_total": len(unresolved),
            },
            recommendation=(
                "Run `vibecomfy port widgets <workflow> --json`, add schema aliases, or rewrite the template "
                "with named inputs before RunPod validation."
            ),
        ))
    # Escalate any opaque_component_node_class diagnostics that are still warnings
    # (e.g. when analyze_source ran in scratchpad mode but the gate was invoked
    # separately).  Workbench strict_ready/app_active mode already emits these as
    # errors, so this is defense-in-depth.
    for issue in list(report.diagnostics):
        if issue.code != "opaque_component_node_class":
            continue
        if issue.severity == "warning":
            issue.severity = "error"
            issue.detail = dict(issue.detail or {})
            issue.detail["gate_escalation"] = "strict_ready"
            if "promotion" not in (issue.recommendation or ""):
                issue.recommendation = (
                    "Inline component/subgraph definitions with graphbuilder or ComfyUI's converter before "
                    "materializing a ready template. Do not wrap an opaque UUID runtime node in a Python "
                    "name; promotion requires real workflow-builder code with a known first-class replacement node."
                )
    if int((report.workflow_shape or {}).get("outputs") or 0) < 1:
        diagnostics.append(PortIssue(
            STRICT_READY_MISSING_OUTPUT_CONTRACT,
            "Strict ready-template gate requires at least one public output contract.",
            severity="error",
            detail={"category": "strict_ready", "target": "public_outputs"},
            recommendation="Register the expected artifact with `bind_output(...)` so `public_outputs` describes the pre-run artifact contract before RunPod validation.",
        ))
    report.diagnostics.extend(
        apply_strict_ready_exceptions(
            diagnostics,
            StrictReadyContext(
                ready_id=(report.workflow_id or (report.provenance or {}).get("indexed_id")),
                source_path=(report.provenance or {}).get("source_path"),
            ),
        )
    )


def _render_check(report: Any) -> str:
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in report.diagnostics:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    lines = [
        f"port check: {'ok' if report.ok else 'errors found'}",
        f"source: {report.source}",
        f"nodes: {report.workflow_shape.get('runtime_nodes', 0)} runtime, {report.workflow_shape.get('helper_nodes', 0)} helper",
        f"diagnostics: {counts['error']} error, {counts['warning']} warning, {counts['info']} info",
    ]
    for issue in report.diagnostics[:12]:
        location = f" node {issue.node_id}" if issue.node_id else ""
        class_type = f" ({issue.class_type})" if issue.class_type else ""
        lines.append(f"- {issue.severity}: {issue.code}{location}{class_type}: {issue.message}")
    if len(report.diagnostics) > 12:
        lines.append(f"- ... {len(report.diagnostics) - 12} more diagnostics; rerun with --json for full details")
    if report.node_pack_suggestions:
        lines.append("Suggested custom node packs:")
        for pack in report.node_pack_suggestions:
            packages = f" (pip: {', '.join(pack.pip_packages)})" if pack.pip_packages else ""
            lines.append(f"- {pack.pack_name}: {pack.repo}{packages}")
    if report.asset_candidates:
        lines.append(f"Model asset candidates: {len(report.asset_candidates)}")
    if report.asset_checks:
        failed = sum(1 for check in report.asset_checks if not check.ok)
        lines.append(f"Model URL HEAD checks: {len(report.asset_checks) - failed} ok, {failed} failed")
    if report.recommendations:
        lines.append("Recommended next steps:")
        lines.extend(f"- {item}" for item in report.recommendations[:6])
    return "\n".join(lines)


def _build_conversion_provider(args: argparse.Namespace) -> ConversionSchemaProvider:
    runtime_enabled = getattr(args, "runtime_object_info", False)
    server_url: str | None = getattr(args, "server_url", None)
    object_info_cache = getattr(args, "object_info_cache", None)
    if object_info_cache is None and not getattr(args, "no_object_info_cache", False):
        latest = latest_object_info_cache_path()
        object_info_cache = str(latest) if _object_info_cache_is_useful(latest) else None
    return ConversionSchemaProvider(
        object_info_cache_path=object_info_cache,
        object_info_index_root=Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info",
        widget_schema=WIDGET_SCHEMA,
        enable_runtime=runtime_enabled,
        runtime_server_url=server_url,
    )


def _build_authoring_provider(args: argparse.Namespace):
    object_info_cache = getattr(args, "object_info_cache", None)
    return get_authoring_schema_provider(
        object_info_cache_path=object_info_cache,
        object_info_index_root=Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info",
    )


def _build_validate_call_provider(args: argparse.Namespace):
    """Provider hook for the schema-only ``port validate-call`` command."""

    return _build_authoring_provider(args)


def _object_info_cache_is_useful(path: Path | None) -> bool:
    """Avoid letting tiny focused runtime caches shadow deterministic fallbacks."""
    if path is None:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    core_hits = {"KSampler", "SaveImage", "CLIPLoader"} & set(data)
    return len(core_hits) >= 2 or len(data) >= 50


def _inject_schema_source_metadata(report: Any, args: argparse.Namespace) -> None:
    runtime_enabled = getattr(args, "runtime_object_info", False)
    server_url: str | None = getattr(args, "server_url", None)
    report.metadata["schema_source"] = {
        "provider": getattr(args, "_schema_provider_name", "ConversionSchemaProvider"),
        "runtime_enabled": runtime_enabled,
        "server_url": server_url,
        "object_info_cache": getattr(args, "object_info_cache", None)
        or (
            None
            if getattr(args, "no_object_info_cache", False)
            else str(latest_object_info_cache_path() or "")
        ),
    }


def _emit_convert_payload(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload["status"] == "ok":
        print(payload["out"])
        validation = payload["conversion"].get("validation")
        if validation:
            print(
                "validated emitted module: "
                f"import={validation['import_ok']} build={validation['build_ok']} "
                f"compile={validation['compile_ok']} schema={validation['schema_ok']}"
            )
        return
    print(payload.get("message", "port convert failed"), file=sys.stderr)
    report = payload.get("report") or {}
    for issue in (report.get("diagnostics") or [])[:12]:
        print(f"- {issue['severity']}: {issue['code']}: {issue['message']}", file=sys.stderr)


def _render_widgets(payload: dict[str, Any]) -> str:
    unresolved = payload.get("unresolved_widget_aliases") or []
    suggestions = payload.get("suggestions") or []
    lines = [
        f"port widgets: {len(unresolved)} unresolved positional widget alias"
        f"{'' if len(unresolved) == 1 else 'es'}",
        f"source: {payload.get('source')}",
    ]
    if not unresolved:
        return "\n".join(lines)
    for group in suggestions:
        lines.append(f"- {group['class_type']}: {len(group['nodes'])} node(s), source={group['schema_source']}")
        if group.get("python"):
            lines.append(f"  schema: {group['python']}")
        else:
            lines.append("  schema: unavailable from local object_info/node_index")
        for node in group["nodes"][:5]:
            inputs = ", ".join(node["unresolved_inputs"])
            lines.append(f"  node {node['node_id']}: {inputs}")
    return "\n".join(lines)


def _cmd_port_rules(args: argparse.Namespace) -> int:
    """Codemod rule introspection."""
    explain = getattr(args, "explain", False)
    if args.json:
        print(json.dumps(rules_to_json(), indent=2, sort_keys=True))
        return 0

    cat_map = rules_by_category()
    lines = ["The codemod (vibecomfy/porting/emitter.py) applies these rules:"]
    for cat, rules in sorted(cat_map.items()):
        lines.append("")
        lines.append(cat)
        for rule in rules:
            partial = " (partial coverage)" if rule.partial_coverage else ""
            lines.append(f"  {rule.id}: {rule.description}{partial}")
            if explain:
                lines.append(f"    {rule.behavior}")
                if rule.note:
                    lines.append(f"    Note: {rule.note}")

    lines.append("")
    lines.append("(Read vibecomfy/porting/emitter.py for exact implementation.)")
    lines.append("(This registry has partial coverage; some rules may be undocumented.)")
    print("\n".join(lines))
    return 0


def _cmd_port_lint(args: argparse.Namespace) -> int:
    """Convention enforcer over generated templates."""
    all_mode = getattr(args, "all", False)
    json_mode = getattr(args, "json", False)

    if all_mode:
        ready_root = find_repo_root() / "ready_templates"
        paths = list(ready_root.rglob("*.py"))
    else:
        wf_path = Path(args.workflow)
        if wf_path.is_file():
            paths = [wf_path]
        else:
            # Try as ready template ID
            ready_root = find_repo_root() / "ready_templates"
            candidate = ready_root / f"{args.workflow}.py"
            if candidate.is_file():
                paths = [candidate]
            else:
                print(f"Workflow not found: {args.workflow}", file=sys.stderr)
                return 1

    all_diags: list[Any] = []
    has_errors = False

    for path in sorted(paths):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        diags = lint_ready_template(source, str(path))
        if json_mode:
            all_diags.extend(
                {
                    "severity": d.severity,
                    "path": d.path,
                    "line": d.line,
                    "code": d.code,
                    "message": d.message,
                    "detail": d.detail,
                }
                for d in diags
            )
        else:
            if diags:
                print(f"{path}:")
                for d in diags:
                    marker = {"error": "error", "warning": "warning", "info": "info"}.get(d.severity, d.severity)
                    print(f"  L{d.line}: {marker}: {d.message}")
                sev_counts = {"error": 0, "warning": 0, "info": 0}
                for d in diags:
                    sev_counts[d.severity] = sev_counts.get(d.severity, 0) + 1
                print(f"  {sev_counts['warning']} warnings, {sev_counts['info']} info, {sev_counts['error']} errors")
                print()
            if any(d.severity == "error" for d in diags):
                has_errors = True

    if json_mode:
        payload = {
            "diagnostics": all_diags,
            "total": len(all_diags),
            "has_errors": has_errors,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if has_errors else 0

    return 1 if has_errors else 0


def _cmd_port_simulate(args: argparse.Namespace) -> int:
    """Sandbox simulation of an experimental emitter rule."""
    rule_spec: str = args.rule
    all_mode = getattr(args, "all", False)
    json_mode = getattr(args, "json", False)

    schema_provider = get_schema_provider("auto")

    # Resolve template IDs: without --all, use None (regeneratable in simulate_rule);
    # with --all, explicitly gather all template IDs from the corpus.
    template_ids = None
    if all_mode:
        snapshot = build_corpus_snapshot(READY_ROOT)
        template_ids = [t["id"] for t in snapshot.templates_list]

    result = simulate_rule(
        rule_spec,
        template_ids=template_ids,
        schema_provider=schema_provider,
    )

    if result.error:
        print(f"Simulation error: {result.error}", file=sys.stderr)
        return 1

    if json_mode:
        print(json.dumps(result.to_json(), indent=2, sort_keys=True))
        return 0

    print(f"\nCorpus simulation: {rule_spec}")
    print(f"  templates affected: {result.templates_affected}")
    if result.templates_total > 0:
        pct = abs(result.loc_delta_total) / max(1, sum(
            pt.get("original_loc", 0) for pt in result.per_template
        )) * 100
        print(f"  LOC delta: {result.loc_delta_total:+d} lines total ({pct:+.1f}% corpus)")
    print(f"  canonical parity: {result.parity_preserved}/{result.parity_preserved + result.parity_broken} preserved {'✅' if result.parity_broken == 0 else '❌'}")
    print(f"  no broken outputs" if result.parity_broken == 0 else f"  {result.parity_broken} broken outputs")

    # Per-template top 5
    affected = [pt for pt in result.per_template if pt.get("changed")]
    if affected:
        print("\nPer-template (top 5):")
        for pt in sorted(affected, key=lambda x: x["loc_delta"])[:5]:
            print(f"  {pt['template_id']}: {pt['original_loc']} → {pt['emitted_loc']} ({pt['loc_delta']:+d})")

    if result.sample_diff:
        print(f"\nSample diff ({affected[0]['template_id'] if affected else 'N/A'}):")
        print(result.sample_diff[:2000])

    return 0


def register(subparsers) -> None:
    port = subparsers.add_parser(
        "port",
        description=PORT_HELP,
        epilog=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    port_subparsers = port.add_subparsers(dest="port_cmd", required=True)

    check = port_subparsers.add_parser(
        "check",
        help="Preflight a workflow before manual editing or RunPod validation.",
        description=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check.add_argument("workflow")
    check.add_argument("--json", action="store_true")
    check.add_argument("--head-check-models", action="store_true", help="Opt in to non-downloading HEAD checks for model URLs.")
    check.add_argument(
        "--strict-ready-template",
        action="store_true",
        help="Escalate unresolved positional widget aliases to errors before promotion or RunPod validation.",
    )
    check.add_argument(
        "--runtime-object-info",
        action="store_true",
        help="Opt in to live /object_info schema evidence from a running ComfyUI server.",
    )
    check.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file as offline schema evidence. Defaults to the newest out/cache/object_info*.json when present.",
    )
    check.add_argument(
        "--no-object-info-cache",
        action="store_true",
        help="Do not use cached /object_info schema evidence.",
    )
    check.add_argument(
        "--server-url",
        help="ComfyUI server URL for live /object_info (requires --runtime-object-info).",
    )
    check.set_defaults(func=_cmd_port_check)

    convert = port_subparsers.add_parser(
        "convert",
        help="Emit an importable Python scratchpad, or a ready-template candidate with --ready-id.",
        description=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    convert.add_argument("workflow")
    convert.add_argument("--out", required=False, help="Destination file path (required for writes; optional with --dry-run)")
    convert.add_argument("--all", action="store_true", help="Run across all ready templates (dry-run diff mode only)")
    convert.add_argument("--ready-id", help="Emit ready-template candidate mode; must have kind/name shape.")
    convert.add_argument("--json", action="store_true")
    convert.add_argument("--dry-run", action="store_true", help="Emit conversion payload and evidence without writing target file.")
    convert.add_argument("--diff", action="store_true", help="Produce unified diff + JSON diff metadata (implies dry-run).")
    convert.add_argument("--head-check-models", action="store_true", help="Opt in to non-downloading HEAD checks for model URLs.")
    convert.add_argument(
        "--strict-ready-template",
        action="store_true",
        help="Escalate unresolved positional widget aliases to errors. Ready-template conversion enables this by default.",
    )
    convert.add_argument(
        "--runtime-object-info",
        action="store_true",
        help="Opt in to live /object_info schema evidence from a running ComfyUI server.",
    )
    convert.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file as offline schema evidence. Defaults to the newest out/cache/object_info*.json when present.",
    )
    convert.add_argument(
        "--no-object-info-cache",
        action="store_true",
        help="Do not use cached /object_info schema evidence.",
    )
    convert.add_argument(
        "--server-url",
        help="ComfyUI server URL for live /object_info (requires --runtime-object-info).",
    )
    convert.set_defaults(func=_cmd_port_convert)

    widgets = port_subparsers.add_parser(
        "widgets",
        help="Suggest widget-only schema entries for unresolved positional aliases.",
        description=(
            "Report widget_alias_unresolved diagnostics grouped by class and suggest "
            "widget-only schema entries from local node_index/object_info data when available."
        ),
    )
    widgets.add_argument("workflow")
    widgets.add_argument("--json", action="store_true")
    widgets.set_defaults(func=_cmd_port_widgets)

    export = port_subparsers.add_parser("export", help="Export a loaded workflow as API JSON.")
    export.add_argument("workflow")
    export.add_argument("--ready", action="store_true")
    export.add_argument("--to", default="json")
    export.add_argument("--json", action="store_true")
    export.add_argument("--object-info-cache")
    export.add_argument("--out", default=None, help="Output file path (required for --to ui).")
    export.add_argument("--strict", action="store_true", help="Raise ValueError on schema-less or low-confidence node class types.")
    export.add_argument("--main-positions", action="store_true", help="Include main positions in emitted UI JSON (no-op, wired for future use).")
    export.add_argument("--no-virtual-wires", action="store_true", help="Omit SetNode/GetNode virtual wire resolution.")
    export.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any prior store (sidecar, --from, breadcrumb) and emit a fresh layout.",
    )
    export.add_argument(
        "--from",
        dest="from_path",
        default=None,
        help="Path to a prior emitted UI JSON to use as the preserve source (loaded via store_from_ui_json).",
    )
    export.set_defaults(func=_cmd_port_export)

    validate_call = port_subparsers.add_parser("validate-call", help="Validate one node call against authoring schema.")
    validate_call.add_argument("class_type")
    validate_call.add_argument("--kwargs", required=True, help="JSON object of node kwargs to validate.")
    validate_call.add_argument("--json", action="store_true")
    validate_call.add_argument("--object-info-cache")
    validate_call.set_defaults(func=_cmd_port_validate_call)

    doctor_all = port_subparsers.add_parser("doctor-all", help="Run port, install-plan, validate, doctor, and runtime doctor sections.")
    doctor_all.add_argument("workflow")
    doctor_all.add_argument("--ready", action="store_true")
    doctor_all.add_argument("--json", action="store_true")
    doctor_all.add_argument("--object-info-cache")
    doctor_all.set_defaults(func=_cmd_port_doctor_all)

    inventory = port_subparsers.add_parser(
        "inventory",
        help="Repo-only readability inventory for checked-in ready templates.",
        description=(
            "Emit a deterministic, versioned JSON report built from the static "
            "ready_templates/**/*.py glob. Never consults plugin/cwd/user-global paths."
        ),
    )
    inventory.add_argument("--ready", action="store_true", default=True, help=argparse.SUPPRESS)
    inventory.add_argument("--json", action="store_true")
    inventory.set_defaults(func=_cmd_port_inventory)

    repair = port_subparsers.add_parser(
        "repair",
        help="Dry-run marker-aware manual-template repair analysis and review packets.",
        description=(
            "Analyze a checked-in manual ready template in mechanical or semantic mode. "
            "Dry-run is the default; pass --write to allow edits."
        ),
    )
    repair.add_argument("workflow")
    repair.add_argument("--mode", choices=("mechanical", "semantic"), required=True)
    repair.add_argument("--json", action="store_true")
    repair.add_argument("--review-out", default="out/review_packets")
    repair.add_argument("--write", action="store_true")
    repair.set_defaults(func=_cmd_port_repair)

    rules = port_subparsers.add_parser(
        "rules",
        help="Codemod rule introspection.",
    )
    rules.add_argument("--explain", action="store_true", help="Show detailed rule behavior descriptions")
    rules.add_argument("--json", action="store_true")
    rules.set_defaults(func=_cmd_port_rules)

    lint = port_subparsers.add_parser(
        "lint",
        help="Convention enforcer over generated templates.",
    )
    lint.add_argument("workflow", nargs="?", help="Ready template file path or ID")
    lint.add_argument("--all", action="store_true", help="Lint all ready_templates/**/*.py")
    lint.add_argument("--json", action="store_true")
    lint.set_defaults(func=_cmd_port_lint)

    simulate = port_subparsers.add_parser(
        "simulate",
        help="Sandbox simulation of an experimental emitter rule.",
    )
    simulate.add_argument("--rule", required=True, help="Rule spec (e.g. drop_set_id_map=true)")
    simulate.add_argument("--all", action="store_true", help="Simulate corpus-wide")
    simulate.add_argument("--json", action="store_true")
    simulate.set_defaults(func=_cmd_port_simulate)



__all__ = [
    "register",
    "_cmd_port_check",
    "_cmd_port_convert",
    "_cmd_port_export",
    "_cmd_port_inventory",
    "_cmd_port_repair",
    "_cmd_port_widgets",
    "_cmd_port_validate_call",
    "_cmd_port_doctor_all",
    "_cmd_port_lint",
    "_cmd_port_rules",
    "_cmd_port_simulate",
]
