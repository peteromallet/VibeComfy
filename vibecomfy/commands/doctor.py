from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from vibecomfy._git_utils import git_head
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands._model_entries import model_entries_for_workflow
from vibecomfy.commands._output import emit
from vibecomfy.contracts import build_contract
from vibecomfy.contracts.surface import build_contract_surface
from vibecomfy.custom_node_refs import check_pack_pin_compatibility
from vibecomfy.diagnostics import (
    DiagnosticFinding,
    PatchSuggestion,
    finding_messages,
    patch_suggestions_payload,
)
from vibecomfy.environment_diagnostics import metadata_environment_warnings
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.model_assets import extract_from_raw_workflow
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.format import format_issue
from vibecomfy.workflow import VibeEdge, VibeWorkflow
from vibecomfy.node_packs import resolve_node_packs, unresolved_class_types
from vibecomfy.patches.registry import find_applicable

_RAW_REF_RE = re.compile(r"^\w+\.\w+$")
_MODELS_ROOT_UNSET_MESSAGE = (
    "VIBECOMFY_MODELS_ROOT not set; cannot check model presence - "
    "set it to your ComfyUI models dir"
)


def _cmd_doctor(args: argparse.Namespace) -> int:
    lint = getattr(args, "lint", False)
    allow_drift = getattr(args, "allow_drift", False)
    json_output = getattr(args, "json", False)
    check_models = getattr(args, "models", False)
    schema_provider = get_schema_provider("auto")
    try:
        workflow = load_workflow_any(args.path)
    except Exception as exc:
        print("Layer: Python scratchpad import/build")
        print(f"Error: {type(exc).__name__}: {exc}")
        print("Next: fix the Python file until build() returns a VibeWorkflow.")
        print(f"Port preflight: vibecomfy port check {args.path} --json")
        return 1
    helper_issues = workflow.helper_diagnostics()
    helper_blockers = [issue for issue in helper_issues if issue.severity != "info"]
    if helper_blockers:
        payload = {
            "status": "error",
            "layer": "Porting helper diagnostics",
            "errors": [issue.message for issue in helper_blockers],
            "recommended_command": f"vibecomfy port check {args.path} --json",
        }
        if json_output:
            emit(payload, json=True, text_renderer=_render_doctor_error)
        else:
            print("Layer: Porting helper diagnostics")
            for issue in helper_issues:
                print(f"- {issue.message}")
            print(f"Next: {payload['recommended_command']}")
        return 1
    if lint:
        for warning in _lint_untyped_raw_refs(Path(args.path)):
            print(f"- untyped_raw_ref: {warning}")
    suggested_patches = patch_suggestions_payload(_patch_suggestions(workflow))
    drift_warning_findings, drift_error_findings = _nodepack_lockfile_drift()
    drift_warnings = finding_messages(drift_warning_findings)
    drift_errors = finding_messages(drift_error_findings)
    pin_issues = check_pack_pin_compatibility(workflow, read_lockfile())
    pin_warnings = [issue.message for issue in pin_issues if issue.severity == "warning"]
    pin_errors = [issue.message for issue in pin_issues if issue.severity == "error"]
    drift_warnings.extend(pin_warnings)
    drift_errors.extend(pin_errors)
    if drift_errors:
        if allow_drift:
            payload = {"status": "warning", "nodepack_drift": [*drift_warnings, *drift_errors], "suggested_patches": suggested_patches}
            return emit(payload, json=json_output, text_renderer=_render_doctor_warning)
        payload = {"status": "error", "layer": "nodepack lockfile drift", "errors": drift_errors, "suggested_patches": suggested_patches}
        return emit(payload, json=json_output, text_renderer=_render_doctor_error) or 1
    if drift_warnings and not json_output:
        print("Nodepack lockfile warnings:")
        for warning in drift_warnings:
            print(f"- {warning}")
    report = workflow.validate(schema_provider=schema_provider)
    if not report.ok:
        validation_findings = _validation_findings(report)
        validation_issues = finding_messages(validation_findings)
        payload = {
            "status": "error",
            "layer": "VibeWorkflow validation",
            "errors": validation_issues,
            "nodepack_warnings": drift_warnings,
            "suggested_patches": suggested_patches,
        }
        if json_output:
            emit(payload, json=True, text_renderer=_render_doctor_error)
        else:
            print("Layer: VibeWorkflow validation")
            for issue in validation_issues:
                print(f"- {issue}")
            print(f"Next: vibecomfy port check {args.path} --json")
        if json_output:
            return 1
        missing_classes = {
            str(issue.detail.get("class_type"))
            for issue in report.issues
            if issue.code == "unknown_class_type" and issue.detail.get("class_type")
        }
        if missing_classes:
            packs = resolve_node_packs(missing_classes)
            if packs:
                print("Suggested custom node packs:")
                for pack in packs:
                    packages = f" (pip: {', '.join(pack.pip_packages)})" if pack.pip_packages else ""
                    print(f"- {pack.name}: {pack.repo}{packages}")
            unresolved = unresolved_class_types(missing_classes)
            if unresolved:
                print("Unmapped node classes:")
                for class_type in unresolved:
                    print(f"- {class_type}")
        return 1
    if check_models and "VIBECOMFY_MODELS_ROOT" not in os.environ:
        payload = {
            "status": "error",
            "layer": "model asset diagnostics",
            "errors": [_MODELS_ROOT_UNSET_MESSAGE],
            "nodepack_warnings": drift_warnings,
            "suggested_patches": suggested_patches,
        }
        emit(payload, json=json_output, text_renderer=_render_doctor_error)
        return 1
    missing_models = finding_messages(_missing_model_findings(workflow, args.path))
    if missing_models:
        payload = {"status": "error", "missing_models": missing_models, "nodepack_warnings": drift_warnings, "suggested_patches": suggested_patches}
        emit(payload, json=json_output, text_renderer=lambda data: _render_list_section("Missing models", data["missing_models"], data))
        return 1
    warnings = _doctor_warnings(workflow)
    if warnings:
        payload = {"status": "warning", "warnings": warnings, "nodepack_warnings": drift_warnings, "suggested_patches": suggested_patches}
        emit(payload, json=json_output, text_renderer=lambda data: _render_list_section("Local checks passed with runtime warnings", data["warnings"], data))
        return 0
    payload = {
        "status": "ok",
        "message": "No local issues found. Runtime/model/node failures require `vibecomfy run` logs.",
        "nodepack_warnings": drift_warnings,
        "suggested_patches": suggested_patches,
    }
    if json_output:
        _attach_contract(payload, build_contract(workflow).to_dict(), workflow)
    return emit(payload, json=json_output, text_renderer=_render_doctor_ok)


def _attach_contract(payload: dict[str, Any], contract: dict[str, Any], workflow: VibeWorkflow) -> None:
    payload["contract"] = contract
    payload.update(build_contract_surface(contract=contract, workflow=workflow))


def _patch_suggestions(workflow: VibeWorkflow) -> list[PatchSuggestion]:
    return [PatchSuggestion(name=patch.name, rationale=patch.rationale(workflow)) for patch in find_applicable(workflow)]


def _render_suggested_patches(payload: dict[str, Any]) -> list[str]:
    suggested = payload.get("suggested_patches") or []
    if not suggested:
        return []
    lines = ["Suggested patches:"]
    lines.extend(f"- {patch['name']}: {patch['rationale']}" for patch in suggested)
    return lines


def _render_recommended_command(payload: dict[str, Any]) -> list[str]:
    command = payload.get("recommended_command")
    return [f"Next: {command}"] if command else []


def _render_doctor_ok(payload: dict[str, Any]) -> str:
    return "\n".join([payload["message"], *_render_suggested_patches(payload)])


def _render_doctor_warning(payload: dict[str, Any]) -> str:
    if "nodepack_drift" in payload:
        return _render_list_section("Nodepack lockfile drift warnings", payload["nodepack_drift"], payload)
    return _render_list_section("Local checks passed with runtime warnings", payload.get("warnings", []), payload)


def _render_doctor_error(payload: dict[str, Any]) -> str:
    lines = [f"Layer: {payload.get('layer', 'doctor')}"]
    lines.extend(f"- {error}" for error in payload.get("errors", []))
    lines.extend(_render_suggested_patches(payload))
    lines.extend(_render_recommended_command(payload))
    return "\n".join(lines)


def _render_list_section(title: str, items: list[str], payload: dict[str, Any]) -> str:
    lines = [f"{title}:"]
    lines.extend(f"- {item}" for item in items)
    lines.extend(_render_suggested_patches(payload))
    lines.extend(_render_recommended_command(payload))
    return "\n".join(lines)


def _validation_findings(report: Any) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for issue in report.issues:
        detail = issue.detail or {}
        findings.append(
            DiagnosticFinding(
                code=issue.code,
                message=format_issue(issue),
                severity=issue.severity,
                node_id=str(detail["node_id"]) if "node_id" in detail else None,
                class_type=str(detail["class_type"]) if "class_type" in detail else None,
                detail=detail,
            )
        )
    return findings


def _read_doctor_lockfile() -> list[LockEntry]:
    return read_lockfile()


def _nodepack_lockfile_drift() -> tuple[list[DiagnosticFinding], list[DiagnosticFinding]]:
    warnings: list[DiagnosticFinding] = []
    errors: list[DiagnosticFinding] = []
    for entry in _read_doctor_lockfile():
        pack_dir = _doctor_nodepack_dir(entry.name)
        if pack_dir is None:
            warnings.append(
                DiagnosticFinding(
                    "nodepack_lockfile_missing_pack",
                    f"{entry.name} in lockfile but not installed; skipping drift check",
                    "warning",
                    detail={"pack": entry.name},
                )
            )
            continue
        actual = git_head(pack_dir, runner=subprocess.run)
        if actual is None:
            warnings.append(
                DiagnosticFinding(
                    "nodepack_lockfile_unreadable_head",
                    f"{entry.name} is installed at {pack_dir} but git HEAD could not be read; skipping drift check",
                    "warning",
                    detail={"pack": entry.name, "path": str(pack_dir)},
                )
            )
            continue
        if actual != entry.git_commit_sha:
            errors.append(
                DiagnosticFinding(
                    "nodepack_lockfile_git_head_mismatch",
                    f"{entry.name} git HEAD {actual} does not match lockfile git_commit_sha {entry.git_commit_sha}",
                    "error",
                    detail={"pack": entry.name, "actual": actual, "expected": entry.git_commit_sha},
                )
            )
        for rel_path, expected_hash in entry.source_sha256.items():
            source_path = pack_dir / rel_path
            if not source_path.is_file():
                errors.append(
                    DiagnosticFinding(
                        "nodepack_lockfile_missing_source",
                        f"{entry.name} source {rel_path} is missing; expected sha256 {expected_hash}",
                        "error",
                        detail={"pack": entry.name, "path": rel_path, "expected_sha256": expected_hash},
                    )
                )
                continue
            actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(
                    DiagnosticFinding(
                        "nodepack_lockfile_source_hash_mismatch",
                        f"{entry.name} source {rel_path} sha256 {actual_hash} does not match lockfile {expected_hash}",
                        "error",
                        detail={
                            "pack": entry.name,
                            "path": rel_path,
                            "actual_sha256": actual_hash,
                            "expected_sha256": expected_hash,
                        },
                    )
                )
    return warnings, errors


def _doctor_nodepack_dir(name: str) -> Path | None:
    candidates = (
        Path("vendor") / name,
        Path("custom_nodes") / name,
        Path("vendor") / "ComfyUI" / "custom_nodes" / name,
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _lint_untyped_raw_refs(path: Path) -> list[str]:
    if path.suffix.lower() != ".py" or not path.is_file():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: could not parse Python source: {exc.msg}"]
    visitor = _UntypedRawRefVisitor(path)
    visitor.visit(tree)
    return visitor.warnings


class _UntypedRawRefVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.warnings: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function_body(node.body)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function_body(node.body)

    def _visit_function_body(self, body: list[ast.stmt]) -> None:
        typed_handle_names: set[str] = set()
        for statement in body:
            for child in ast.walk(statement):
                if isinstance(child, ast.Call) and self._is_str_of_typed_handle(child, typed_handle_names):
                    arg = child.args[0]
                    assert isinstance(arg, ast.Name)
                    self.warnings.append(
                        f"{self.path}:{child.lineno}: str({arg.id}) erases typed Handle metadata"
                    )
                if isinstance(child, ast.Call) and self._is_raw_connect_ref(child, typed_handle_names):
                    raw_ref = child.args[0]
                    assert isinstance(raw_ref, ast.Constant)
                    self.warnings.append(
                        f"{self.path}:{child.lineno}: raw string ref {raw_ref.value!r} passed to connect() "
                        "after typed Handle creation"
                    )
            for target in _assigned_names(statement):
                if _contains_out_call(statement):
                    typed_handle_names.add(target)

    @staticmethod
    def _is_str_of_typed_handle(node: ast.Call, typed_handle_names: set[str]) -> bool:
        return (
            isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in typed_handle_names
        )

    @staticmethod
    def _is_raw_connect_ref(node: ast.Call, typed_handle_names: set[str]) -> bool:
        if not typed_handle_names:
            return False
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "connect":
            return False
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            return False
        return bool(_RAW_REF_RE.match(node.args[0].value))


def _assigned_names(statement: ast.stmt) -> set[str]:
    names: set[str] = set()
    if isinstance(statement, ast.Assign):
        for target in statement.targets:
            names.update(_target_names(target))
    elif isinstance(statement, ast.AnnAssign):
        names.update(_target_names(statement.target))
    return names


def _target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names.update(_target_names(element))
        return names
    return set()


def _contains_out_call(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "out" for child in ast.walk(node))


def _doctor_warnings(workflow: VibeWorkflow) -> list[str]:
    return finding_messages(_doctor_warning_findings(workflow))


def _doctor_warning_findings(workflow: VibeWorkflow) -> list[DiagnosticFinding]:
    warnings: list[DiagnosticFinding] = []
    warnings.extend(_embedded_configuration_findings())
    warnings.extend(_video_audio_findings(workflow))
    warnings.extend(
        DiagnosticFinding("video_frame_cap", warning, "warning")
        for warning in _video_frame_cap_warnings(workflow)
    )
    warnings.extend(_ltx_audio_vae_loader_findings(workflow))
    warnings.extend(
        DiagnosticFinding("metadata_environment", warning, "warning")
        for warning in metadata_environment_warnings(workflow.metadata)
    )
    return warnings


def _video_frame_cap_warnings(workflow: VibeWorkflow) -> list[str]:
    unbound_inputs = workflow.metadata.get("unbound_inputs")
    has_generation_frame_binding = isinstance(unbound_inputs, dict) and any(
        str(name) in {"num_frames", "frames", "frame_count", "video_length"}
        for name in unbound_inputs
    )
    if not has_generation_frame_binding:
        return []

    warnings: list[str] = []
    for node_id, node in sorted(workflow.nodes.items()):
        if node.class_type == "LoadVideo":
            warnings.append(
                f"LoadVideo node {node_id} has no frame-load cap, but the workflow exposes a generated frame-count binding; "
                "the caller must cap or normalize source video before runtime if preprocessing should only consume generated frames."
            )
            continue
        if node.class_type in {"VHS_LoadVideo", "VHS_LoadVideoPath", "VHS_LoadVideoFFmpeg"}:
            cap = node.inputs.get("frame_load_cap")
            if cap in (None, 0, "0"):
                warnings.append(
                    f"{node.class_type} node {node_id} has frame_load_cap={cap!r} while the workflow exposes a generated frame-count binding; "
                    "bind frame_load_cap to the same effective frame count or document why the full source clip is required."
                )
    return warnings


def _ltx_audio_vae_loader_findings(workflow: VibeWorkflow) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in sorted(workflow.nodes.items()):
        if node.class_type != "VAELoaderKJ":
            continue
        vae_name = node.inputs.get("vae_name") or node.inputs.get("widget_0")
        if not isinstance(vae_name, str):
            continue
        normalized = vae_name.lower()
        if "ltx" not in normalized or "audio" not in normalized:
            continue
        findings.append(
            DiagnosticFinding(
                "ltx_audio_vae_wrong_loader",
                "VAELoaderKJ node "
                f"{node_id} loads {vae_name!r}; current KJNodes may misclassify LTX audio VAE files. "
                "Use LTXVAudioVAELoader with the file staged under checkpoints.",
                "warning",
                node_id=str(node_id),
                class_type=node.class_type,
                detail={"vae_name": vae_name},
            )
        )
    return findings


def _missing_model_warnings(workflow: VibeWorkflow, path: str) -> list[str]:
    return finding_messages(_missing_model_findings(workflow, path))


def _missing_model_findings(workflow: VibeWorkflow, path: str) -> list[DiagnosticFinding]:
    import vibecomfy.fetch as fetch_assets

    if "VIBECOMFY_MODELS_ROOT" not in os.environ:
        return []

    warnings: list[DiagnosticFinding] = []
    for entry in _model_asset_entries(workflow, path):
        if fetch_assets.is_present(entry):
            continue
        warnings.append(
            DiagnosticFinding(
                "missing_model",
                f"missing model {entry['name']}: expected {fetch_assets.local_path(entry)} — fetch from {entry['url']}",
                "error",
                detail={
                    "name": entry.get("name"),
                    "url": entry.get("url"),
                    "path": str(fetch_assets.local_path(entry)),
                },
            )
        )
    return warnings


def _model_asset_entries(workflow: VibeWorkflow, workflow_ref: str) -> list[dict]:
    return model_entries_for_workflow(workflow, workflow_ref)


def _embedded_configuration_warnings() -> list[str]:
    return finding_messages(_embedded_configuration_findings())


def _embedded_configuration_findings() -> list[DiagnosticFinding]:
    raw = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [
            DiagnosticFinding(
                "embedded_configuration_invalid_json",
                f"VIBECOMFY_COMFY_CONFIGURATION is not valid JSON: {exc}",
                "warning",
            )
        ]
    if not isinstance(parsed, dict):
        return [
            DiagnosticFinding(
                "embedded_configuration_not_object",
                "VIBECOMFY_COMFY_CONFIGURATION must be a JSON object.",
                "warning",
            )
        ]
    try:
        from vibecomfy.runtime.run import _embedded_configuration
        from vibecomfy.workflow import WorkflowSource

        probe = VibeWorkflow(id="doctor", source=WorkflowSource(id="doctor"))
        config = _embedded_configuration(probe)
    except Exception as exc:
        return [
            DiagnosticFinding(
                "embedded_configuration_build_failed",
                f"embedded configuration could not be constructed: {type(exc).__name__}: {exc}",
                "warning",
            )
        ]
    if config is not None and not hasattr(config, "cwd"):
        return [
            DiagnosticFinding(
                "embedded_configuration_invalid_type",
                "embedded configuration is not a Comfy Configuration object; embedded runtime will fail before queueing.",
                "warning",
            )
        ]
    return []


def _video_audio_warnings(workflow: VibeWorkflow) -> list[str]:
    return finding_messages(_video_audio_findings(workflow))


def _video_audio_findings(workflow: VibeWorkflow) -> list[DiagnosticFinding]:
    warnings: list[DiagnosticFinding] = []
    edges_by_target = {(edge.to_node, edge.to_input): edge for edge in workflow.edges}
    for node_id, node in sorted(workflow.nodes.items()):
        if node.class_type != "CreateVideo":
            continue
        audio_edge = edges_by_target.get((node_id, "audio"))
        if audio_edge is None and _literal_input(node.inputs, "audio") is None:
            continue
        source = _audio_source(workflow, audio_edge, node.inputs.get("audio"))
        warnings.append(
            DiagnosticFinding(
                "optional_video_audio",
                "CreateVideo node "
                f"{node_id} has optional audio input connected"
                f"{f' from {source}' if source else ''}; for smoke tests, remove this edge if SaveVideo fails with AAC NaN/Inf.",
                "warning",
                node_id=str(node_id),
                class_type=node.class_type,
                detail={"source": source} if source else None,
            )
        )
    return warnings


def _literal_input(inputs: dict[str, Any], name: str) -> Any:
    value = inputs.get(name)
    if isinstance(value, list) and len(value) == 2:
        return None
    return value


def _audio_source(workflow: VibeWorkflow, edge: VibeEdge | None, literal: Any) -> str | None:
    if edge is not None:
        node = workflow.nodes.get(edge.from_node)
        if node is None:
            return edge.from_node
        return f"{edge.from_node}:{node.class_type}"
    if isinstance(literal, list) and len(literal) == 2:
        node = workflow.nodes.get(str(literal[0]))
        if node is None:
            return str(literal[0])
        return f"{literal[0]}:{node.class_type}"
    return None


def register(subparsers) -> None:
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("path")
    doctor.add_argument("--lint", action="store_true", default=False)
    doctor.add_argument("--allow-drift", action="store_true", default=False)
    doctor.add_argument("--models", action="store_true", default=False)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)
