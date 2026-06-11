from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands._output import emit
from vibecomfy.errors import SubgraphFreshnessError
from vibecomfy.porting.emitter import _build_subgraph_def, _disambiguated_subgraph_slugs
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.format import format_issue
from vibecomfy.workflow import ValidationIssue, ValidationReport, VibeWorkflow


def _cmd_validate(args: argparse.Namespace) -> int:
    json_output = bool(getattr(args, "json", False))
    try:
        schema_provider = None if args.no_schema else get_schema_provider("auto")
        workflow = load_workflow_any(args.path)
        report = workflow.validate(schema_provider=schema_provider)
        if getattr(args, "check_freshness", False) and report.ok:
            drift = _subgraph_freshness_diagnostics(Path(args.path))
            if drift:
                raise SubgraphFreshnessError(
                    f"Subgraph freshness check failed for {args.path}",
                    next_action="vibecomfy port --reconvert <template>",
                )
    except SubgraphFreshnessError:
        raise
    except Exception as exc:
        if json_output:
            emit(_exception_payload(args.path, exc), json=True, text_renderer=_render_exception_payload)
            return 1
        traceback.print_exc(file=sys.stderr)
        print(f"python_build_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    payload = _report_payload(workflow, report)
    if not report.ok:
        if json_output:
            emit(payload, json=True, text_renderer=_render_report_payload)
            return 1
        for issue in report.issues:
            print(f"{issue.severity}: {format_issue(issue)}", file=sys.stderr)
        return 1
    if json_output:
        return emit(payload, json=True, text_renderer=_render_report_payload)
    print("ok")
    return 0


def build_validate_payload(path: str, *, no_schema: bool = False, check_freshness: bool = False) -> dict[str, object]:
    """Block A back-compat: build the validation payload directly without going through the CLI."""
    schema_provider = None if no_schema else get_schema_provider("auto")
    workflow = load_workflow_any(path)
    report = workflow.validate(schema_provider=schema_provider)
    issues = [
        {
            "code": issue.code,
            "severity": issue.severity,
            "message": format_issue(issue),
            "detail": issue.detail,
        }
        for issue in report.issues
    ]
    if not report.ok:
        return {"status": "error", "path": path, "issues": issues}
    if check_freshness:
        drift = _subgraph_freshness_diagnostics(Path(path))
        if drift:
            raise SubgraphFreshnessError(
                f"Subgraph freshness check failed for {path}",
                next_action="vibecomfy port --reconvert <template>",
            )
    return {"status": "ok", "path": path, "issues": issues}


def _report_payload(workflow: VibeWorkflow, report: ValidationReport) -> dict[str, Any]:
    return {
        "workflow_id": workflow.id,
        "ok": report.ok,
        "status": "ok" if report.ok else "error",
        "issues": [_issue_payload(issue) for issue in report.issues],
    }


def _issue_payload(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity,
        "detail": issue.detail or {},
    }


def _exception_payload(path: str, exc: Exception) -> dict[str, Any]:
    return {
        "path": path,
        "ok": False,
        "status": "error",
        "errors": [
            {
                "code": "workflow_load_error",
                "type": type(exc).__name__,
                "message": str(exc),
            }
        ],
    }


def _render_report_payload(payload: dict[str, Any]) -> str:
    if payload["ok"]:
        return "ok"
    return "\n".join(format_issue(_issue_from_payload(issue)) for issue in payload["issues"])


def _render_exception_payload(payload: dict[str, Any]) -> str:
    return "\n".join(f"{error['type']}: {error['message']}" for error in payload["errors"])


def _issue_from_payload(payload: dict[str, Any]) -> ValidationIssue:
    return ValidationIssue(
        code=payload["code"],
        message=payload["message"],
        severity=payload.get("severity", "error"),
        detail=payload.get("detail") or {},
    )


def register(subparsers) -> None:
    validate = subparsers.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--json", action="store_true")
    validate.add_argument("--no-schema", action="store_true", help="Skip schema validation; run structural-only.")
    validate.add_argument("--check-freshness", action="store_true", help="Check materialized subgraph source hashes against source workflow JSON.")
    validate.set_defaults(func=_cmd_validate)


def _subgraph_freshness_diagnostics(template_path: Path) -> list[str]:
    if not template_path.exists() or template_path.suffix != ".py":
        return []
    source = template_path.read_text(encoding="utf-8")
    expected = dict(re.findall(r"subgraph ([0-9a-fA-F-]{36}).*?\n\s*# vibecomfy source hash: sha256:([0-9a-f]{64})", source))
    if not expected:
        return []
    source_workflow = _source_workflow_from_template(source)
    if source_workflow is None:
        return [f"{template_path}: materialized subgraph hashes present but no source_workflow metadata was found"]
    source_path = (Path.cwd() / source_workflow).resolve()
    if not source_path.exists():
        return [f"{template_path}: source workflow not found: {source_workflow}"]
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    definitions = raw.get("definitions") if isinstance(raw, dict) else None
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if isinstance(subgraphs, dict):
        raw_by_id = {str(item.get("id")): item for item in subgraphs.values() if isinstance(item, dict) and item.get("id")}
    elif isinstance(subgraphs, list):
        raw_by_id = {str(item.get("id")): item for item in subgraphs if isinstance(item, dict) and item.get("id")}
    else:
        return [f"{template_path}: source workflow has no subgraph definitions"]
    slugs = _disambiguated_subgraph_slugs(raw_by_id)
    diagnostics: list[str] = []
    for subgraph_id, expected_hash in sorted(expected.items()):
        raw_subgraph = raw_by_id.get(subgraph_id)
        if raw_subgraph is None:
            diagnostics.append(f"{template_path}: source subgraph missing: {subgraph_id}")
            continue
        actual = _build_subgraph_def(raw_subgraph, slug=slugs.get(subgraph_id, f"subgraph_{subgraph_id[:8]}"), source_path=source_workflow).source_hash
        if actual != expected_hash:
            diagnostics.append(f"{template_path}: subgraph {subgraph_id} source hash changed: {expected_hash} -> {actual}")
    return diagnostics


def _source_workflow_from_template(source: str) -> str | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "build":
            continue
        for kw in node.keywords:
            if kw.arg in {"source_workflow", "provenance"}:
                try:
                    value = ast.literal_eval(kw.value)
                except Exception:
                    continue
                if isinstance(value, str):
                    return value
                if isinstance(value, dict) and isinstance(value.get("source_workflow"), str):
                    return value["source_workflow"]
    return None
