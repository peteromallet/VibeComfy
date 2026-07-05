from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.porting.reorganise import (
    LayoutCompileOptions,
    ReorganisePreviewOptions,
    apply_layout_candidate_patch_to_ui,
    assess_reorganise_workflow,
    load_reorganise_ui_json,
    preview_reorganise_workflow,
)
from vibecomfy.porting.reorganise.visualize import render_layout_png

_SPACING_PRESETS = ("compact", "balanced", "wide")
_GROUPING_POLICIES = ("auto", "none", "preserve_existing", "stage", "wall")
_EXISTING_GROUP_POLICIES = (
    "preserve",
    "rename_only",
    "resize_only",
    "rename_and_resize",
    "semantic_preserve",
    "dissolve_with_warning",
    "force_regroup",
)

_PLAN_ARTIFACT = "reorganisation_plan.json"
_REPORT_ARTIFACT = "reorganisation_report.md"
_METRICS_ARTIFACT = "reorganisation_metrics.json"
_EVIDENCE_ARTIFACT = "structural_noop_evidence.json"
_MANIFEST_ARTIFACT = "reorganisation_preview_manifest.json"
_DEBUG_CANDIDATE_PATCH_ARTIFACT = "candidate.patch.json"
_DEBUG_LAYOUT_BEFORE_ARTIFACT = "layout_before.png"
_DEBUG_LAYOUT_AFTER_ARTIFACT = "layout_after.png"
_DEBUG_LAYOUT_METRICS_ARTIFACT = "layout_metrics.json"
_DEBUG_LAYOUT_TRACE_ARTIFACT = "layout_trace.json"
_DEBUG_MANIFEST_ARTIFACT = "manifest.json"


def _cmd_reorganise(args: argparse.Namespace) -> int:
    modes = [bool(args.assess), bool(args.preview), bool(args.apply)]
    if sum(modes) != 1:
        print(
            "Choose exactly one mode: --assess, --preview, or --apply.",
            file=sys.stderr,
        )
        return 2
    if args.apply:
        return _apply_preview_manifest(args)

    workflow_path = Path(args.workflow)
    sidecar_path = _resolve_sidecar_path(workflow_path, args.sidecar)
    compile_options = _compile_options_from_args(args)

    if args.assess:
        result = assess_reorganise_workflow(
            workflow_path,
            sidecar_envelope=sidecar_path,
        )
        _emit_json(_assessment_payload(result, compile_options))
        return 0

    if not args.out:
        print("--preview requires --out cleaned.json.", file=sys.stderr)
        return 2

    result = preview_reorganise_workflow(
        workflow_path,
        sidecar_envelope=sidecar_path,
        options=ReorganisePreviewOptions(compile_options=compile_options),
    )
    out_path = Path(args.out)
    artifact_dir = out_path.parent if out_path.parent != Path("") else Path(".")
    debug_artifacts = _resolved_debug_artifacts(args)
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        written = _write_preview_artifacts(
            result=result,
            workflow_path=workflow_path,
            sidecar_path=sidecar_path,
            out_path=out_path,
            artifact_dir=artifact_dir,
            debug_artifacts=debug_artifacts,
        )
    except OSError as exc:
        print(f"reorganise preview failed: {exc}", file=sys.stderr)
        return 1
    _emit_json(written)
    return 0 if result.ok and written["status"] == "ok" else 1


def _apply_preview_manifest(args: argparse.Namespace) -> int:
    workflow_path = Path(args.workflow)
    replace_original = bool(getattr(args, "replace_original", False))
    if args.out and replace_original:
        print("--apply accepts either --out DESTINATION.json or --replace-original, not both.", file=sys.stderr)
        return 2
    if not args.out and not replace_original:
        print("--apply requires --out DESTINATION.json or --replace-original.", file=sys.stderr)
        return 2
    manifest_path = _resolve_manifest_path(workflow_path, args.out, args.manifest)
    try:
        manifest = _load_manifest(manifest_path)
        candidate_path = _candidate_path_from_manifest(manifest_path, manifest)
        _verify_manifest_source_freshness(workflow_path, manifest)
        candidate_sha256 = _verify_candidate_artifact(candidate_path, manifest)
        destination_path = workflow_path if replace_original else Path(args.out)
        backup_path = _write_previewed_candidate(
            candidate_path=candidate_path,
            destination_path=destination_path,
            in_place_source_path=workflow_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"reorganise apply refused: {exc}", file=sys.stderr)
        return 1

    _emit_json(
        {
            "status": "ok",
            "mode": "apply",
            "manifest_path": manifest_path.name,
            "source": {
                "label": workflow_path.name,
                "source_bytes_sha256": manifest["source"].get("source_bytes_sha256"),
                "source_canonical_sha256": manifest["source"].get(
                    "source_canonical_sha256"
                ),
            },
            "candidate_ui_json": candidate_path.name,
            "candidate_ui_sha256": candidate_sha256,
            "written": destination_path.name,
            "backup": backup_path.name if backup_path is not None else None,
        }
    )
    return 0


def _compile_options_from_args(args: argparse.Namespace) -> LayoutCompileOptions:
    existing_group_policy = args.existing_group_policy
    force_regroup = bool(args.force_regroup)
    if force_regroup:
        existing_group_policy = "force_regroup"
    return LayoutCompileOptions(
        spacing_preset=args.spacing,
        existing_group_policy=existing_group_policy,
        grouping_policy=getattr(args, "grouping_policy", "auto"),
        force_regroup=force_regroup,
        minimize_setget_helpers=not bool(getattr(args, "no_minimize_setget_helpers", False)),
    )


def _resolved_debug_artifacts(args: argparse.Namespace) -> dict[str, bool]:
    debug_layout = bool(getattr(args, "debug_layout", False))
    visualize = debug_layout or bool(getattr(args, "visualize", False))
    metrics = debug_layout or bool(getattr(args, "metrics", False))
    trace_layout = debug_layout or bool(getattr(args, "trace_layout", False))
    return {
        "visualize": visualize,
        "metrics": metrics,
        "trace_layout": trace_layout,
        "debug_layout": debug_layout,
    }


def _resolve_sidecar_path(workflow_path: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    sibling = workflow_path.with_suffix(".layout.json")
    return sibling if sibling.exists() else None


def _resolve_manifest_path(
    workflow_path: Path,
    out: str | None,
    explicit: str | None,
) -> Path:
    if explicit:
        manifest_path = Path(explicit)
    elif out:
        manifest_path = Path(out).parent / _MANIFEST_ARTIFACT
    else:
        manifest_path = workflow_path.parent / _MANIFEST_ARTIFACT
    if not manifest_path.is_file():
        raise ValueError(f"preview manifest not found: {manifest_path}")
    return manifest_path


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("preview manifest must be a JSON object")
    if manifest.get("version") != 1 or manifest.get("mode") != "preview":
        raise ValueError("preview manifest must be version 1 preview output")
    if manifest.get("status") != "ok":
        raise ValueError("preview manifest status is not ok")
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("preview manifest is missing source hashes")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("preview manifest is missing artifacts")
    if not isinstance(artifacts.get("candidate_ui_json"), str):
        raise ValueError("preview manifest is missing candidate UI artifact")
    if not isinstance(manifest.get("candidate_ui_sha256"), str):
        raise ValueError("preview manifest is missing candidate UI hash")
    apply_data = manifest.get("apply_data")
    if not isinstance(apply_data, dict):
        raise ValueError("preview manifest is missing apply data")
    if apply_data.get("layout_only_structural_noop") is not True:
        raise ValueError("preview manifest is not a layout-only structural no-op")
    return manifest


def _candidate_path_from_manifest(
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> Path:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("preview manifest is missing artifacts")
    candidate_name = artifacts.get("candidate_ui_json")
    if not isinstance(candidate_name, str) or not candidate_name:
        raise ValueError("preview manifest is missing candidate UI artifact")
    candidate_path = Path(candidate_name)
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise ValueError("candidate UI artifact must be relative to the preview manifest")
    resolved = manifest_path.parent / candidate_path
    if not resolved.is_file():
        raise ValueError(f"candidate UI artifact not found: {candidate_name}")
    return resolved


def _verify_manifest_source_freshness(
    workflow_path: Path,
    manifest: Mapping[str, Any],
) -> None:
    loaded = load_reorganise_ui_json(workflow_path)
    source = manifest.get("source")
    apply_data = manifest.get("apply_data")
    if not isinstance(source, Mapping) or not isinstance(apply_data, Mapping):
        raise ValueError("preview manifest is missing source freshness data")

    expected_canonical = source.get("source_canonical_sha256") or apply_data.get(
        "source_canonical_sha256"
    )
    expected_bytes = source.get("source_bytes_sha256") or apply_data.get(
        "source_bytes_sha256"
    )
    if not isinstance(expected_canonical, str) or not expected_canonical:
        raise ValueError("preview manifest is missing source canonical hash")
    if loaded.source_canonical_sha256 != expected_canonical:
        raise ValueError(
            "stale preview manifest: source canonical hash changed "
            f"{expected_canonical} -> {loaded.source_canonical_sha256}"
        )
    if isinstance(expected_bytes, str) and loaded.source_bytes_sha256 != expected_bytes:
        raise ValueError(
            "stale preview manifest: source bytes hash changed "
            f"{expected_bytes} -> {loaded.source_bytes_sha256}"
        )


def _verify_candidate_artifact(
    candidate_path: Path,
    manifest: Mapping[str, Any],
) -> str:
    expected = manifest.get("candidate_ui_sha256")
    if not isinstance(expected, str) or not expected:
        raise ValueError("preview manifest is missing candidate UI hash")
    actual = _file_sha256(candidate_path)
    if actual != expected:
        raise ValueError(
            "previewed candidate hash mismatch "
            f"{expected} -> {actual}"
        )
    return actual


def _write_previewed_candidate(
    *,
    candidate_path: Path,
    destination_path: Path,
    in_place_source_path: Path,
) -> Path | None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if destination_path.resolve() == in_place_source_path.resolve():
        backup_path = in_place_source_path.with_name(in_place_source_path.name + ".bak")
        backup_path.write_bytes(in_place_source_path.read_bytes())
    destination_path.write_bytes(candidate_path.read_bytes())
    return backup_path


def _assessment_payload(result: Any, compile_options: LayoutCompileOptions) -> dict[str, Any]:
    payload = result.to_json()
    payload["mode"] = "assess"
    payload["status"] = result.assessment.verdict
    payload["options"] = {"compile_options": compile_options.to_json()}
    return payload


def _write_preview_artifacts(
    *,
    result: Any,
    workflow_path: Path,
    sidecar_path: Path | None,
    out_path: Path,
    artifact_dir: Path,
    debug_artifacts: Mapping[str, bool],
) -> dict[str, Any]:
    plan_path = artifact_dir / _PLAN_ARTIFACT
    report_path = artifact_dir / _REPORT_ARTIFACT
    metrics_path = artifact_dir / _METRICS_ARTIFACT
    evidence_path = artifact_dir / _EVIDENCE_ARTIFACT
    manifest_path = artifact_dir / _MANIFEST_ARTIFACT
    debug_manifest_path = artifact_dir / _DEBUG_MANIFEST_ARTIFACT
    debug_patch_path = artifact_dir / _DEBUG_CANDIDATE_PATCH_ARTIFACT
    debug_before_path = artifact_dir / _DEBUG_LAYOUT_BEFORE_ARTIFACT
    debug_after_path = artifact_dir / _DEBUG_LAYOUT_AFTER_ARTIFACT
    debug_metrics_path = artifact_dir / _DEBUG_LAYOUT_METRICS_ARTIFACT
    debug_trace_path = artifact_dir / _DEBUG_LAYOUT_TRACE_ARTIFACT

    candidate_patch = result.candidate_patch
    patch_apply = None
    candidate_sha256 = None
    if result.ok and candidate_patch is not None:
        patch_apply = apply_layout_candidate_patch_to_ui(workflow_path, candidate_patch)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_artifact(out_path, patch_apply.ui_json)
        candidate_sha256 = _file_sha256(out_path)

    _write_json_artifact(plan_path, _plan_payload(result))
    metrics_payload = _metrics_payload(result)
    _write_json_artifact(metrics_path, metrics_payload)
    evidence_payload = _evidence_payload(result, patch_apply)
    _write_json_artifact(evidence_path, evidence_payload)
    report_text = _render_report(
        result=result,
        candidate_filename=out_path.name,
        metrics_filename=metrics_path.name,
        evidence_filename=evidence_path.name,
    )
    _write_text_artifact(report_path, report_text)

    debug_artifact_names: dict[str, str | None] = {}
    if any(debug_artifacts.values()):
        if candidate_patch is not None:
            _write_json_artifact(debug_patch_path, candidate_patch)
            debug_artifact_names["candidate_patch_json"] = debug_patch_path.name
        else:
            debug_artifact_names["candidate_patch_json"] = None
    if debug_artifacts.get("visualize"):
        _render_png_artifact(debug_before_path, result.loaded.ui_json)
        if patch_apply is not None:
            _render_png_artifact(debug_after_path, patch_apply.ui_json)
            debug_artifact_names["layout_after_png"] = debug_after_path.name
        else:
            debug_artifact_names["layout_after_png"] = None
        debug_artifact_names["layout_before_png"] = debug_before_path.name
    if debug_artifacts.get("metrics"):
        _write_json_artifact(debug_metrics_path, metrics_payload)
        debug_artifact_names["layout_metrics_json"] = debug_metrics_path.name
    if debug_artifacts.get("trace_layout"):
        _write_json_artifact(debug_trace_path, _trace_payload(result))
        debug_artifact_names["layout_trace_json"] = debug_trace_path.name

    manifest = {
        "version": 1,
        "mode": "preview",
        "status": "ok" if result.ok and candidate_sha256 is not None else "failed",
        "source": {
            "label": workflow_path.name,
            "sidecar_label": sidecar_path.name if sidecar_path is not None else None,
            "source_bytes_sha256": result.loaded.source_bytes_sha256,
            "source_canonical_sha256": result.loaded.source_canonical_sha256,
        },
        "artifacts": {
            "candidate_ui_json": out_path.name if candidate_sha256 is not None else None,
            "reorganisation_plan": plan_path.name,
            "reorganisation_report": report_path.name,
            "reorganisation_metrics": metrics_path.name,
            "structural_noop_evidence": evidence_path.name,
            **debug_artifact_names,
        },
        "candidate_ui_sha256": candidate_sha256,
        "apply_data": result.apply_data.to_json(),
        "options": result.options.to_json(),
        "plan_source": result.plan_source,
        "sanitized_report_text": report_text,
    }
    if any(debug_artifacts.values()):
        manifest["artifacts"]["manifest_json"] = debug_manifest_path.name
    _write_json_artifact(manifest_path, manifest)
    if any(debug_artifacts.values()):
        _write_json_artifact(debug_manifest_path, manifest)

    return {
        "status": manifest["status"],
        "manifest": manifest,
        "manifest_path": manifest_path.name,
        "artifacts": manifest["artifacts"],
    }


def _plan_payload(result: Any) -> dict[str, Any]:
    return {
        "status": "ok" if result.ok else "failed",
        "plan_source": result.plan_source,
        "plan": result.plan.to_json() if result.plan is not None else None,
        "parse_diagnostics": [
            diagnostic.to_json() if hasattr(diagnostic, "to_json") else diagnostic
            for diagnostic in result.parse_diagnostics
        ],
        "validation_report": (
            result.validation_report.to_json()
            if result.validation_report is not None
            else None
        ),
        "provider_diagnostics": [
            diagnostic.to_json() for diagnostic in result.provider_diagnostics
        ],
        "compile_diagnostics": [
            diagnostic.to_json() for diagnostic in result.compile_diagnostics
        ],
        "second_stage_results": [
            second_stage.to_json() for second_stage in result.second_stage_results
        ],
    }


def _metrics_payload(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "assessment": result.assessment.to_json(),
        "graph_summary": result.graph_summary.to_json(),
        "projection": {
            "token_estimate": result.projection.token_estimate,
            "scope_count": result.projection.scope_count,
            "canonical_ref_count": result.projection.canonical_ref_count,
            "summarized": result.projection.summarized,
            "truncated": result.projection.truncated,
        },
        "compile": None,
    }
    if result.compile_result is not None and result.compile_result.ok:
        payload["compile"] = {
            "ok": result.compile_result.ok,
            "options": result.compile_result.options.to_json(),
            "report": result.compile_result.report.to_json(),
            "node_layout_count": len(result.compile_result.node_layouts),
            "group_layout_count": len(result.compile_result.group_layouts),
        }
    return payload


def _trace_payload(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok" if result.ok else "failed",
        "plan_source": result.plan_source,
        "entries": list(getattr(result, "layout_trace", ())),
        "compile": None,
    }
    if result.compile_result is not None:
        payload["compile"] = {
            "ok": result.compile_result.ok,
            "diagnostics": [
                diagnostic.to_json() for diagnostic in result.compile_diagnostics
            ],
            "validation_report": result.compile_result.validation_report.to_json(),
        }
    return payload


def _evidence_payload(result: Any, patch_apply: Any | None) -> dict[str, Any]:
    return {
        "apply_data": result.apply_data.to_json(),
        "patch_apply": (
            patch_apply.to_json(include_ui_json=False) if patch_apply is not None else None
        ),
        "layout_only_structural_noop": result.apply_data.layout_only_structural_noop
        and (patch_apply.layout_only_structural_noop if patch_apply is not None else False),
    }


def _render_report(
    *,
    result: Any,
    candidate_filename: str,
    metrics_filename: str,
    evidence_filename: str,
) -> str:
    assessment = result.assessment.to_json()
    lines = [
        "# Reorganisation Report",
        "",
        f"- Status: {'ok' if result.ok else 'failed'}",
        f"- Source: {result.loaded.source_label or '<memory>'}",
        f"- Plan source: {result.plan_source}",
        f"- Candidate: {candidate_filename if result.ok else 'not written'}",
        f"- Metrics: {metrics_filename}",
        f"- Structural no-op evidence: {evidence_filename}",
        f"- Layout-only structural no-op: {str(result.apply_data.layout_only_structural_noop).lower()}",
        "",
        "## Assessment",
        "",
        f"- Verdict: {assessment['verdict']}",
        f"- Issues: {len(assessment['issues'])}",
        f"- Diagnostics: {len(assessment['diagnostics'])}",
        "",
        "## Compile Options",
        "",
    ]
    for key, value in sorted(result.options.compile_options.to_json().items()):
        lines.append(f"- {key}: {json.dumps(value, sort_keys=True)}")
    if assessment["issues"]:
        lines.extend(["", "## Issues", ""])
        for issue in assessment["issues"][:20]:
            lines.append(f"- {issue['severity']}: {issue['code']} - {issue['message']}")
    if result.compile_diagnostics:
        lines.extend(["", "## Compile Diagnostics", ""])
        for diagnostic in result.compile_diagnostics[:20]:
            lines.append(
                f"- {diagnostic.severity}: {diagnostic.code} - {diagnostic.message}"
            )
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, payload: Mapping[str, Any] | list[Any]) -> None:
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_json_artifact(path: Path, payload: Mapping[str, Any] | list[Any]) -> None:
    try:
        _write_json(path, payload)
    except OSError as exc:
        raise OSError(f"failed to write preview artifact {path}: {exc}") from exc


def _write_text_artifact(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise OSError(f"failed to write preview artifact {path}: {exc}") from exc


def _render_png_artifact(path: Path, ui_json: Mapping[str, Any]) -> None:
    try:
        render_layout_png(ui_json, path)
    except Exception as exc:
        raise OSError(f"failed to write preview artifact {path}: {exc}") from exc


def _emit_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(_json_safe(payload), indent=2, sort_keys=True, ensure_ascii=True))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "reorganise",
        help="Assess or preview deterministic layout-only workflow reorganisation.",
    )
    parser.add_argument("workflow", help="Workflow UI JSON to assess or preview.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--assess",
        action="store_true",
        help="Emit a deterministic assessment JSON report.",
    )
    modes.add_argument(
        "--preview",
        action="store_true",
        help="Write a deterministic layout-only preview.",
    )
    modes.add_argument(
        "--apply",
        action="store_true",
        help="Apply an existing preview manifest.",
    )
    parser.add_argument(
        "--out",
        help=(
            "Candidate UI JSON path for --preview, or destination path for "
            "--apply."
        ),
    )
    parser.add_argument(
        "--replace-original",
        action="store_true",
        help=(
            "With --apply, replace the source workflow in place using the exact "
            "previewed candidate and create a sibling .bak backup."
        ),
    )
    parser.add_argument(
        "--manifest",
        help=(
            "Preview manifest JSON for --apply. Defaults to "
            "reorganisation_preview_manifest.json beside --out or the workflow."
        ),
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Also emit layout_before.png and layout_after.png during --preview.",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Also emit layout_metrics.json during --preview.",
    )
    parser.add_argument(
        "--trace-layout",
        action="store_true",
        dest="trace_layout",
        help="Also emit layout_trace.json during --preview.",
    )
    parser.add_argument(
        "--debug-layout",
        action="store_true",
        help="Equivalent to --visualize --metrics --trace-layout during --preview.",
    )
    parser.add_argument(
        "--sidecar",
        help="Optional layout-store sidecar JSON. Defaults to a sibling .layout.json when present.",
    )
    parser.add_argument(
        "--spacing",
        choices=_SPACING_PRESETS,
        default="balanced",
        help="Compiler spacing preset for preview layout.",
    )
    parser.add_argument(
        "--existing-group-policy",
        choices=_EXISTING_GROUP_POLICIES,
        default="semantic_preserve",
        help="How the compiler should treat existing UI groups.",
    )
    parser.add_argument(
        "--grouping-policy",
        choices=_GROUPING_POLICIES,
        default="auto",
        help="When to generate layout groups; auto avoids over-grouping small clean graphs.",
    )
    parser.add_argument(
        "--force-regroup",
        action="store_true",
        help="Force existing groups to be rebuilt by the layout compiler.",
    )
    parser.add_argument(
        "--no-minimize-setget-helpers",
        action="store_true",
        help="Keep Set/Get helper nodes at normal size in large workflow layouts.",
    )
    parser.set_defaults(func=_cmd_reorganise)
