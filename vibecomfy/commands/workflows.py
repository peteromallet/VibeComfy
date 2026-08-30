from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

import vibecomfy.fetch as fetch_assets
from vibecomfy.commands._diagnostics import Diagnostic, diagnostics_to_json, diagnostics_to_text
from vibecomfy.commands._output import emit
from vibecomfy.commands._index_files import IndexReadError, print_index_error
from vibecomfy.commands._workflow_path import load_workflow_index_rows
from vibecomfy.registry.ready import (
    READY_ROOT,
    dynamic_ready_template_rows,
    repo_ready_template_ids,
    ready_template_source_info,
    workflow_from_ready,
)
from vibecomfy.runtime.session import _model_assets_from_workflow

TEMPLATE_INDEX_PATH = Path("template_index.json")
CONTRACT_SHAPE = "workflow_runtime_contract.v1.public_descriptors.v2"

def _cmd_workflows_list(args: argparse.Namespace) -> int:
    rows = []
    if args.ready:
        index_rows, index_diagnostic = _ready_rows_from_template_index()
        if index_diagnostic is not None:
            if args.json:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "diagnostics": diagnostics_to_json([index_diagnostic]),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(diagnostics_to_text([index_diagnostic]), file=sys.stderr)
            return 1
        if index_rows:
            rows = index_rows[: args.limit]
            if getattr(args, "include_dynamic", False):
                indexed_ids = {str(row["id"]) for row in index_rows if isinstance(row.get("id"), str)}
                rows = [*rows, *_dynamic_ready_rows(indexed_ids)][: args.limit]
        else:
            rows = _ready_rows_without_index()[: args.limit]
        return emit(rows, json=args.json, text_renderer=_render_workflow_rows)
    try:
        rows.extend(load_workflow_index_rows())
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    return emit(rows[: args.limit], json=args.json, text_renderer=_render_workflow_rows)


def _ready_rows_from_template_index() -> tuple[list[dict[str, Any]], Diagnostic | None]:
    if not TEMPLATE_INDEX_PATH.exists():
        return [], None
    try:
        payload = json.loads(TEMPLATE_INDEX_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        return [], _template_index_diagnostic(
            "template_index_unreadable",
            f"template_index.json could not be read: {type(exc).__name__}: {exc}",
            exception=exc,
        )
    except json.JSONDecodeError as exc:
        return [], _template_index_diagnostic(
            "template_index_corrupt",
            f"template_index.json contains invalid JSON: {exc}",
            exception=exc,
            extra_details={"line": exc.lineno, "column": exc.colno},
        )
    templates = payload.get("templates") if isinstance(payload, dict) else None
    if not isinstance(templates, list):
        return [], _template_index_diagnostic(
            "template_index_schema_invalid",
            "template_index.json must be an object with a list field named `templates`.",
        )
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(templates):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            return [], _template_index_diagnostic(
                "template_index_schema_invalid",
                "template_index.json template entries must be objects with string `id` fields.",
                extra_details={"template_index": idx},
            )
        rows.append(
            {
                "media_type": "ready",
                **item,
                "source_scope": item.get("source_scope", "repo"),
                "indexed": item.get("indexed", True),
                "contract_shape": item.get("contract_shape", CONTRACT_SHAPE),
                "public_inputs": item.get("public_inputs") or [],
                "public_outputs": item.get("public_outputs") or [],
                "readiness_class": item.get("readiness_class") or "",
                "coverage_tier": item.get("coverage_tier") or "",
                "app_active": item.get("app_active") is True,
                "blocked": item.get("blocked") is True,
                "reference": item.get("reference") is True,
                "supplemental": item.get("supplemental") is True,
                "model_count": int(item.get("model_count") or 0),
                "custom_nodes": item.get("custom_nodes") or [],
                "custom_node_count": int(item.get("custom_node_count") or len(item.get("custom_nodes") or [])),
                "strict_ready_diagnostic_counts": item.get("strict_ready_diagnostic_counts") or {},
            }
        )
    return rows, None


def _template_index_diagnostic(
    code: str,
    message: str,
    *,
    exception: BaseException | None = None,
    extra_details: dict[str, Any] | None = None,
) -> Diagnostic:
    details: dict[str, Any] = {"path": str(TEMPLATE_INDEX_PATH)}
    if exception is not None:
        details.update({"exception_type": type(exception).__name__, "exception": str(exception)})
    if extra_details:
        details.update(extra_details)
    return Diagnostic(
        code=code,
        message=message,
        severity="error",
        recoverable=False,
        details=details,
    )


def _ready_rows_without_index() -> list[dict[str, Any]]:
    rows = [
        {
            "id": template_id,
            "media_type": "ready",
            "path": str(READY_ROOT / f"{template_id}.py"),
            "source_scope": "repo",
            "indexed": False,
            "contract_shape": CONTRACT_SHAPE,
            "public_inputs": [],
            "public_outputs": [],
            "readiness_class": "",
            "coverage_tier": "",
            "app_active": False,
            "blocked": False,
            "reference": False,
            "supplemental": False,
            "model_count": 0,
            "custom_nodes": [],
            "custom_node_count": 0,
            "strict_ready_diagnostic_counts": {},
        }
        for template_id in repo_ready_template_ids()
    ]
    repo_ids = {row["id"] for row in rows}
    rows.extend(_dynamic_ready_rows(repo_ids))
    return sorted(rows, key=lambda row: str(row["id"]))


def _dynamic_ready_rows(exclude_ids: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "media_type": "ready",
            **row,
            "source_scope": "dynamic",
            "indexed": False,
            "contract_shape": CONTRACT_SHAPE,
            "public_inputs": row.get("public_inputs") or [],
            "public_outputs": row.get("public_outputs") or [],
            "readiness_class": row.get("readiness_class") or "",
            "coverage_tier": row.get("coverage_tier") or "",
            "app_active": row.get("app_active") is True,
            "blocked": row.get("blocked") is True,
            "reference": row.get("reference") is True,
            "supplemental": row.get("supplemental") is True,
            "model_count": int(row.get("model_count") or 0),
            "custom_nodes": row.get("custom_nodes") or [],
            "custom_node_count": int(row.get("custom_node_count") or len(row.get("custom_nodes") or [])),
            "strict_ready_diagnostic_counts": row.get("strict_ready_diagnostic_counts") or {},
        }
        for row in dynamic_ready_template_rows(exclude_ids=exclude_ids)
    ]


def _cmd_workflows_source_info(args: argparse.Namespace) -> int:
    info = ready_template_source_info(args.template_id).to_dict()
    return emit(info, json=args.json, text_renderer=lambda row: json.dumps(row, indent=2, sort_keys=True))


def _cmd_workflows_enrich_targets(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.targets_json).read_text(encoding="utf-8"))
    enriched = enrich_target_manifest(manifest, models_root=args.models_root)
    payload = json.dumps(enriched, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


def _cmd_workflows_onboard(args: argparse.Namespace) -> int:
    plan = build_onboarding_plan(
        source=args.source,
        ready_id=args.ready_id,
        out=args.out,
        public_source=bool(args.public_source),
        description=args.description,
        description_file=args.description_file,
        upload=bool(args.upload),
        verify_upload=bool(args.verify_upload),
        dry_run_upload=bool(args.dry_run_upload),
    )
    return emit(plan, json=args.json, text_renderer=_render_onboarding_plan)


def build_onboarding_plan(
    *,
    source: str,
    ready_id: str,
    out: str,
    public_source: bool = False,
    description: str | None = None,
    description_file: str | None = None,
    upload: bool = False,
    verify_upload: bool = False,
    dry_run_upload: bool = False,
) -> dict[str, Any]:
    """Build the sequenced workflow-onboarding runbook.

    This keeps the human/agent handoff explicit: description enrichment happens
    after conversion/validation has produced a readable Python workflow, but
    before any Hivemind upload envelope is built.
    """
    description = " ".join(str(description or "").split())
    description_file = str(description_file or "").strip()
    has_description = bool(description or description_file)
    template_filter = ready_id
    stages: list[dict[str, Any]] = []

    def command(parts: list[str]) -> str:
        return " ".join(shlex.quote(str(part)) for part in parts if str(part) != "")

    stages.append(
        {
            "id": "preflight",
            "label": "Preflight source workflow",
            "command": command(["vibecomfy", "port", "check", source, "--json"]),
            "blocks_upload": True,
        }
    )
    stages.append(
        {
            "id": "install_plan",
            "label": "Identify required custom node packs",
            "command": command(["vibecomfy", "nodes", "install-plan", source]),
            "blocks_upload": True,
        }
    )
    stages.append(
        {
            "id": "convert",
            "label": "Convert to readable Python ready template",
            "command": command(
                [
                    "vibecomfy",
                    "port",
                    "convert",
                    source,
                    "--ready-id",
                    ready_id,
                    "--out",
                    out,
                    "--json",
                ]
            ),
            "blocks_upload": True,
        }
    )
    stages.append(
        {
            "id": "refresh_index",
            "label": "Refresh template index so upload metadata knows the converted workflow",
            "command": command(["python", "tools/refresh_template_index.py"]),
            "blocks_upload": True,
        }
    )
    stages.append(
        {
            "id": "validate",
            "label": "Validate converted Python workflow",
            "command": command(["vibecomfy", "validate", out]),
            "blocks_upload": True,
        }
    )
    stages.append(
        {
            "id": "describe",
            "label": "Enrich with a human-readable description",
            "status": "ready" if has_description else "needs_input",
            "description": (
                description
                or (f"Read from {description_file}" if description_file else "")
                or "Add a short description of what the workflow does and what is special about it."
            ),
            "blocks_upload": not has_description,
        }
    )

    upload_allowed = upload and public_source and has_description
    upload_blockers: list[str] = []
    if upload and not public_source:
        upload_blockers.append("source must be marked public with --public-source")
    if upload and not has_description:
        upload_blockers.append("description enrichment is required before upload")
    upload_command = [
        "python",
        "scripts/upload_ready_templates_to_hivemind.py",
        "--only",
        template_filter,
    ]
    if dry_run_upload:
        upload_command.append("--dry-run")
    if verify_upload and not dry_run_upload:
        upload_command.append("--verify")
    if description_file:
        upload_command.extend(["--description-file", description_file])
    elif description:
        upload_command.extend(["--description", description])
    stages.append(
        {
            "id": "hivemind_upload",
            "label": "Upload public converted workflow to Hivemind",
            "status": "ready" if upload_allowed else ("blocked" if upload else "optional"),
            "command": command(upload_command) if upload_allowed else None,
            "blockers": upload_blockers,
            "verify_after_upload": bool(verify_upload and not dry_run_upload),
            "blocks_upload": False,
        }
    )

    return {
        "producer": "vibecomfy.workflows.onboard",
        "source": source,
        "ready_id": ready_id,
        "out": out,
        "public_source": public_source,
        "description_ready": has_description,
        "upload_requested": upload,
        "upload_ready": upload_allowed,
        "stages": stages,
    }


def _render_onboarding_plan(plan: dict[str, Any]) -> str:
    lines = [
        f"workflow onboarding: {plan['source']} -> {plan['ready_id']}",
        f"output: {plan['out']}",
    ]
    for idx, stage in enumerate(plan["stages"], start=1):
        status = stage.get("status")
        suffix = f" [{status}]" if status else ""
        lines.append(f"{idx}. {stage['label']}{suffix}")
        command_text = stage.get("command")
        if command_text:
            lines.append(f"   {command_text}")
        if stage.get("blockers"):
            lines.append(f"   blocked: {', '.join(stage['blockers'])}")
        elif stage["id"] == "describe" and stage.get("status") == "needs_input":
            lines.append("   write a short description before upload")
    return "\n".join(lines)


def enrich_target_manifest(
    manifest: dict[str, Any],
    *,
    models_root: str | Path | None = None,
) -> dict[str, Any]:
    """Enrich a Reigh target manifest with VibeComfy source/schema/asset data."""
    root = Path(models_root) if models_root is not None else fetch_assets.models_root()
    targets = manifest.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("target manifest field `targets` must be a list")
    enriched_targets: list[dict[str, Any]] = []
    seen_template_ids: set[str] = set()
    selected_template_ids: list[str] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        template_id = target.get("template_id") or target.get("selected_template_id")
        if not isinstance(template_id, str) or not template_id:
            enriched_targets.append(
                {
                    **target,
                    "enrichment_status": "skipped",
                    "issues": [
                        {
                            "group": "workflow_source",
                            "code": "non_template_target",
                            "severity": "info",
                            "message": "Target does not execute a VibeComfy template directly.",
                        }
                    ],
                }
            )
            continue
        if template_id not in seen_template_ids:
            seen_template_ids.add(template_id)
            selected_template_ids.append(template_id)
        enriched_targets.append(_enrich_target(target, template_id=template_id, models_root=root))
    return {
        "schema_version": 1,
        "source_manifest_schema_version": manifest.get("schema_version"),
        "producer": "vibecomfy.workflows.enrich-targets",
        "models_root": str(root),
        "selector": manifest.get("selector", {}),
        "selection": manifest.get("selection", {}),
        "target_count": len(enriched_targets),
        "template_count": len(selected_template_ids),
        "templates": selected_template_ids,
        "targets": enriched_targets,
    }


def _enrich_target(
    target: dict[str, Any],
    *,
    template_id: str,
    models_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        source_info = ready_template_source_info(template_id).to_dict()
        workflow = workflow_from_ready(template_id)
        validation_issues: list[Any] = []
        try:
            validation_report = workflow.validate()
            validation_issues = list(validation_report.issues)
        except Exception as exc:  # noqa: BLE001 - validation errors belong in the report
            issues.append(
                {
                    "group": "schema",
                    "code": "validation_failed",
                    "severity": "error",
                    "message": str(exc),
                }
            )
        try:
            api = workflow.compile("api")
            schema_summary = {
                "node_count": len(api),
                "class_types": sorted(
                    {
                        node.get("class_type")
                        for node in api.values()
                        if isinstance(node, dict) and isinstance(node.get("class_type"), str)
                    }
                ),
            }
        except Exception as exc:  # noqa: BLE001 - diagnostic payload
            schema_summary = {"compile_error": str(exc)}
            issues.append(
                {
                    "group": "schema",
                    "code": "api_compile_failed",
                    "severity": "error",
                    "message": str(exc),
                }
            )
        assets = [_asset_metadata(entry, models_root=models_root) for entry in _model_assets_from_workflow(workflow)]
        for diagnostic in source_info.get("diagnostics", []):
            issues.append({"group": "workflow_source", **diagnostic})
        for issue in validation_issues:
            issues.append(
                {
                    "group": "schema",
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                    "detail": issue.detail,
                }
            )
        for asset in assets:
            if not asset["present"]:
                issues.append(
                    {
                        "group": "assets",
                        "code": "missing_model_asset",
                        "severity": "error",
                        "message": (
                            f"Missing {asset['name']} in {asset['category']}; "
                            f"looked at {', '.join(asset['paths_checked'])}"
                        ),
                        "detail": {
                            "name": asset["name"],
                            "category": asset["category"],
                            "expected_path": asset["expected_path"],
                            "paths_checked": asset["paths_checked"],
                            "url": asset.get("url"),
                            "remediation": asset.get("remediation"),
                        },
                    }
                )
        return {
            **target,
            "template_id": template_id,
            "enrichment_status": "ok" if not any(i.get("severity") == "error" for i in issues) else "issues",
            "source": source_info,
            "schema": schema_summary,
            "assets": assets,
            "issues": issues,
        }
    except Exception as exc:  # noqa: BLE001 - target-level diagnostics must survive
        return {
            **target,
            "template_id": template_id,
            "enrichment_status": "failed",
            "issues": [
                {
                    "group": "workflow_source",
                    "code": "enrichment_failed",
                    "severity": "error",
                    "message": str(exc),
                }
            ],
        }


def _asset_metadata(entry: dict[str, str], *, models_root: Path) -> dict[str, Any]:
    name = entry["name"]
    subdir = entry.get("subdir") or entry.get("directory") or "checkpoints"
    expected = fetch_assets.local_path(entry, root=models_root)
    if "target_path" in entry:
        relative = Path(entry["target_path"])
    else:
        relative = Path(subdir) / name
    paths_checked = [str(expected)]
    present = expected.exists()
    remediation = None
    url = entry.get("url")
    if url:
        remediation = f"mkdir -p {expected.parent} && curl -L {url} -o {expected}"
    return {
        "name": name,
        "category": subdir,
        "subdir": subdir,
        "url": url,
        "target_path": str(relative).replace("\\", "/"),
        "expected_path": str(expected),
        "paths_checked": paths_checked,
        "present": present,
        "remediation": remediation,
    }


def _render_workflow_rows(rows: list[dict]) -> str:
    return "\n".join(f"{row.get('id')}\t{row.get('media_type', '-')}\t{row.get('path')}" for row in rows)


# ── new lens CLI ─────────────────────────────────────────────────────────────


def _cmd_workflows_lens(args: argparse.Namespace) -> int:
    """Print a semantic lens diagnostic summary for a workflow."""
    from vibecomfy.lens.core import WorkflowLens

    workflow = _resolve_workflow_for_inspection(args.template_or_path)
    lens = WorkflowLens(workflow)
    if args.json:
        nodes_summary = []
        for nid, node in sorted(
            workflow.nodes.items(), key=lambda x: (int(x[0]) if x[0].isdigit() else 0, x[0])
        ):
            nodes_summary.append(
                {
                    "id": nid,
                    "class_type": node.class_type,
                    "pack": node.pack,
                    "upstream": sorted(lens.upstream_nodes(nid)),
                    "downstream": sorted(lens.downstream_nodes(nid)),
                }
            )
        payload = {
            "workflow_id": workflow.id,
            "node_count": len(workflow.nodes),
            "edge_count": len(workflow.edges),
            "inputs": sorted(workflow.inputs.keys()),
            "outputs": [
                {"node_id": o.node_id, "output_type": o.output_type} for o in workflow.outputs
            ],
            "nodes": nodes_summary,
        }
        return emit(payload, json=True, text_renderer=lambda x: None)
    return emit(None, json=False, text_renderer=lambda _: lens.diagnostics())


# ── new contract-validate CLI ────────────────────────────────────────────────


def _cmd_workflows_contract_validate(args: argparse.Namespace) -> int:
    """Validate a workflow against a semantic contract type."""
    from vibecomfy.contracts.ltx_first_last import LTXFirstLastTwoStageContract
    from vibecomfy.contracts.validation import ContractReport

    workflow = _resolve_workflow_for_inspection(args.template_or_path)

    contract_type = args.type
    if contract_type != "ltx-first-last-two-stage":
        print(
            f"Error: unknown contract type {contract_type!r}; "
            "supported: ltx-first-last-two-stage"
        )
        return 1

    contract = LTXFirstLastTwoStageContract(workflow)
    report: ContractReport = contract.validate()

    if args.json:
        payload = {
            "contract_name": report.contract_name,
            "passed": report.passed,
            "issues": [
                {
                    "code": i.code,
                    "message": i.message,
                    "severity": i.severity,
                    "detail": i.detail,
                }
                for i in report.issues
            ],
            "diagnostics": report.diagnostics,
        }
        emit(payload, json=True, text_renderer=lambda x: None)
    else:
        print(report.summary())

    return 0 if report.passed else 1


def _resolve_workflow_for_inspection(template_or_path: str) -> "VibeWorkflow":
    """Resolve a template id or file path to a VibeWorkflow for CLI inspection."""
    from vibecomfy.cli_loader import load_workflow_any

    return load_workflow_any(template_or_path)


# ── argparse registration ────────────────────────────────────────────────────


def register(subparsers) -> None:
    workflows = subparsers.add_parser("workflows")
    workflows_sub = workflows.add_subparsers(dest="subcmd", required=True)

    # list
    workflows_list = workflows_sub.add_parser("list")
    workflows_list.add_argument("--limit", type=int, default=200)
    workflows_list.add_argument("--ready", action="store_true")
    workflows_list.add_argument(
        "--include-dynamic",
        action="store_true",
        help="Include plugin/user ready templates as unindexed dynamic rows.",
    )
    workflows_list.add_argument("--json", action="store_true")
    workflows_list.set_defaults(func=_cmd_workflows_list)

    # source-info
    source_info = workflows_sub.add_parser("source-info")
    source_info.add_argument("template_id")
    source_info.add_argument("--json", action="store_true")
    source_info.set_defaults(func=_cmd_workflows_source_info)

    # enrich-targets
    enrich = workflows_sub.add_parser("enrich-targets")
    enrich.add_argument("--targets-json", required=True)
    enrich.add_argument("--output")
    enrich.add_argument("--models-root", type=Path)
    enrich.set_defaults(func=_cmd_workflows_enrich_targets)

    # onboard
    onboard = workflows_sub.add_parser(
        "onboard",
        help="Plan the conversion, validation, description, and optional Hivemind upload sequence.",
    )
    onboard.add_argument("source", help="Source ComfyUI workflow JSON or existing workflow path")
    onboard.add_argument("--ready-id", required=True, help="Ready template id to produce, e.g. video/my_flow")
    onboard.add_argument("--out", required=True, help="Python ready-template path to write")
    onboard.add_argument("--description", help="Description to attach before Hivemind upload")
    onboard.add_argument("--description-file", help="Text file containing the description to attach")
    onboard.add_argument("--public-source", action="store_true", help="Confirm the source is public and safe to upload")
    onboard.add_argument("--upload", action="store_true", help="Include a Hivemind upload command if gates pass")
    onboard.add_argument("--dry-run-upload", action="store_true", help="Make the upload command a dry run")
    onboard.add_argument("--verify-upload", action="store_true", help="Verify Hivemind read-back after real upload")
    onboard.add_argument("--json", action="store_true")
    onboard.set_defaults(func=_cmd_workflows_onboard)

    # lens
    lens_cmd = workflows_sub.add_parser("lens")
    lens_cmd.add_argument("template_or_path")
    lens_cmd.add_argument("--json", action="store_true")
    lens_cmd.set_defaults(func=_cmd_workflows_lens)

    # contract-validate
    contract_val = workflows_sub.add_parser("contract-validate")
    contract_val.add_argument("template_or_path")
    contract_val.add_argument("--type", required=True, choices=["ltx-first-last-two-stage"])
    contract_val.add_argument("--json", action="store_true")
    contract_val.add_argument("--no-schema", action="store_true")
    contract_val.set_defaults(func=_cmd_workflows_contract_validate)


__all__ = ["enrich_target_manifest", "register"]
