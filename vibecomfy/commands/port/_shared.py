from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.layout_store import read_store, store_from_ui_json, write_layout, write_store
from vibecomfy.porting.report import PortIssue, PortReport
from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.utils import find_repo_root

READY_ROOT = find_repo_root() / "ready_templates"

from vibecomfy.porting.strict_ready import (
    STRICT_READY_LOAD_FAILED,
    STRICT_READY_MISSING_OUTPUT_CONTRACT,
    STRICT_READY_UNRESOLVED_WIDGETS,
    STRICT_READY_VIOLATION_CODES,
    StrictReadyContext,
    apply_strict_ready_exceptions,
)
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA
from vibecomfy.schema import ConversionSchemaProvider, get_authoring_schema_provider
from vibecomfy.schema.cache import latest_object_info_cache_path


PORT_HELP = """Cheap preflight and Python materialization for ComfyUI workflow ports.

Use `port check` before manual template editing or expensive RunPod validation.
Use `port convert` to turn source workflows into Python scratchpads; pass
`--ready-id kind/name` only when intentionally producing a ready-template
candidate. Use `doctor`/`validate` after conversion, `nodes install-plan` for
custom node install planning, and `fetch` for URL-backed models. Use
`--head-check-models` only when you want network HEAD checks for model URLs.
"""


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
        object_info_index_root=Path(__file__).resolve().parents[2] / "porting" / "cache" / "object_info",
        widget_schema=WIDGET_SCHEMA,
        enable_runtime=runtime_enabled,
        runtime_server_url=server_url,
    )


def _build_authoring_provider(args: argparse.Namespace):
    object_info_cache = getattr(args, "object_info_cache", None)
    return get_authoring_schema_provider(
        object_info_cache_path=object_info_cache,
        object_info_index_root=Path(__file__).resolve().parents[2] / "porting" / "cache" / "object_info",
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
