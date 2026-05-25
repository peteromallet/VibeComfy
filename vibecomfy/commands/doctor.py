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

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands._output import emit
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.contracts import build_contract
from vibecomfy.contracts.surface import build_contract_surface
from vibecomfy.custom_node_refs import check_pack_pin_compatibility
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.model_assets import extract_from_raw_workflow
from vibecomfy.environment_diagnostics import metadata_environment_warnings
from vibecomfy.node_packs_lockfile import read_lockfile
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.format import format_issue
from vibecomfy.workflow import VibeEdge, VibeWorkflow
from vibecomfy.node_packs import resolve_node_packs, unresolved_class_types
from vibecomfy.patches.registry import find_applicable
from vibecomfy.diagnostics.readability import run_readability_checks_for_file, ReadabilityReport

_RAW_REF_RE = re.compile(r"^\w+\.\w+$")


def _cmd_doctor(args: argparse.Namespace) -> int:
    lint = getattr(args, "lint", False)
    allow_drift = getattr(args, "allow_drift", False)
    json_output = getattr(args, "json", False)
    readability = getattr(args, "readability", False)
    schema_provider = get_schema_provider("auto")
    try:
        workflow = load_workflow_any(args.path)
    except Exception as exc:
        print("Layer: Python scratchpad import/build")
        print(f"Error: {type(exc).__name__}: {exc}")
        print("Next: fix the Python file until build() returns a VibeWorkflow.")
        print(f"Port preflight: vibecomfy port check {args.path} --json")
        return 1
    # -- Run readability diagnostics when --readability is requested ---------
    readability_report: ReadabilityReport | None = None
    if readability:
        source_path = _resolve_readability_source_path(args.path)
        if source_path is not None:
            try:
                readability_report = run_readability_checks_for_file(
                    source_path, workflow_id=str(workflow.id)
                )
            except Exception as exc:
                if not json_output:
                    print(f"Readability checks skipped: {type(exc).__name__}: {exc}")
        elif not json_output:
            print("Readability checks: source is not a ready-template .py file; skipped.")
    contract_payload = build_contract(workflow).to_dict()
    if lint:
        for warning in _lint_untyped_raw_refs(Path(args.path)):
            print(f"- untyped_raw_ref: {warning}")
    helper_issues = workflow.helper_diagnostics()
    helper_blockers = [issue for issue in helper_issues if issue.severity != "info"]
    if helper_blockers:
        payload = {
            "status": "error",
            "layer": "Porting helper diagnostics",
            "errors": [issue.message for issue in helper_blockers],
            "recommended_command": f"vibecomfy port check {args.path} --json",
        }
        _attach_contract(payload, contract_payload, workflow)
        _attach_readability(payload, readability_report)
        if json_output:
            emit(payload, json=True, text_renderer=_render_doctor_error)
        else:
            print("Layer: Porting helper diagnostics")
            for issue in helper_issues:
                print(f"- {issue.message}")
            _render_readability_text(readability_report)
            print(f"Next: {payload['recommended_command']}")
        return 1
    suggested_patches = _patch_suggestions(workflow)
    drift_warnings, drift_errors = _nodepack_lockfile_drift()
    pin_issues = check_pack_pin_compatibility(workflow, read_lockfile())
    pin_warnings = [issue.message for issue in pin_issues if issue.severity == "warning"]
    pin_errors = [issue.message for issue in pin_issues if issue.severity == "error"]
    drift_warnings.extend(pin_warnings)
    drift_errors.extend(pin_errors)
    if drift_errors:
        if allow_drift:
            payload = {"status": "warning", "nodepack_drift": [*drift_warnings, *drift_errors], "suggested_patches": suggested_patches}
            _attach_contract(payload, contract_payload, workflow)
            _attach_readability(payload, readability_report)
            return emit(payload, json=json_output, text_renderer=_render_doctor_warning)
        payload = {"status": "error", "layer": "nodepack lockfile drift", "errors": drift_errors, "suggested_patches": suggested_patches}
        _attach_contract(payload, contract_payload, workflow)
        _attach_readability(payload, readability_report)
        return emit(payload, json=json_output, text_renderer=_render_doctor_error) or 1
    if drift_warnings and not json_output:
        print("Nodepack lockfile warnings:")
        for warning in drift_warnings:
            print(f"- {warning}")
    report = workflow.validate(schema_provider=schema_provider)
    if not report.ok:
        validation_issues = [format_issue(issue) for issue in report.issues]
        payload = {
            "status": "error",
            "layer": "VibeWorkflow validation",
            "errors": validation_issues,
            "nodepack_warnings": drift_warnings,
            "suggested_patches": suggested_patches,
            "recommended_command": f"vibecomfy port check {args.path} --json",
        }
        _attach_contract(payload, contract_payload, workflow)
        _attach_readability(payload, readability_report)
        if json_output:
            emit(payload, json=True, text_renderer=_render_doctor_error)
        else:
            print("Layer: VibeWorkflow validation")
            for issue in validation_issues:
                print(f"- {issue}")
            _render_readability_text(readability_report)
            print(f"Next: {payload['recommended_command']}")
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
    warnings = _doctor_warnings(workflow)
    missing_models = _missing_model_warnings(workflow, args.path)
    if missing_models:
        payload = {
            "status": "error",
            "missing_models": missing_models,
            "warnings": warnings,
            "nodepack_warnings": drift_warnings,
            "suggested_patches": suggested_patches,
            "recommended_command": f"vibecomfy port check {args.path} --json",
        }
        _attach_contract(payload, contract_payload, workflow)
        _attach_readability(payload, readability_report)
        emit(payload, json=json_output, text_renderer=_render_missing_models)
        return 1
    if warnings:
        payload = {"status": "warning", "warnings": warnings, "nodepack_warnings": drift_warnings, "suggested_patches": suggested_patches}
        _attach_contract(payload, contract_payload, workflow)
        _attach_readability(payload, readability_report)
        emit(payload, json=json_output, text_renderer=lambda data: _render_list_section("Local checks passed with runtime warnings", data["warnings"], data))
        return 0
    payload = {
        "status": "ok",
        "message": "No local issues found. Runtime/model/node failures require `vibecomfy run` logs.",
        "nodepack_warnings": drift_warnings,
        "suggested_patches": suggested_patches,
    }
    _attach_contract(payload, contract_payload, workflow)
    _attach_readability(payload, readability_report)
    return emit(payload, json=json_output, text_renderer=_render_doctor_ok)


def _attach_contract(payload: dict[str, Any], contract: dict[str, Any], workflow: VibeWorkflow) -> None:
    payload["contract"] = contract
    payload.update(build_contract_surface(contract=contract, workflow=workflow))


def _patch_suggestions(workflow: VibeWorkflow) -> list[dict[str, str]]:
    return [{"name": patch.name, "rationale": patch.rationale(workflow)} for patch in find_applicable(workflow)]


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
    lines = [payload["message"]]
    lines.extend(_render_suggested_patches(payload))
    readability_text = _render_readability_from_payload(payload)
    if readability_text:
        lines.append(readability_text)
    return "\n".join(lines)


def _render_doctor_warning(payload: dict[str, Any]) -> str:
    # _render_list_section already includes readability when present in payload
    if "nodepack_drift" in payload:
        return _render_list_section("Nodepack lockfile drift warnings", payload["nodepack_drift"], payload)
    return _render_list_section("Local checks passed with runtime warnings", payload.get("warnings", []), payload)


def _render_doctor_error(payload: dict[str, Any]) -> str:
    lines = [f"Layer: {payload.get('layer', 'doctor')}"]
    lines.extend(f"- {error}" for error in payload.get("errors", []))
    lines.extend(_render_suggested_patches(payload))
    lines.extend(_render_recommended_command(payload))
    readability_text = _render_readability_from_payload(payload)
    if readability_text:
        lines.append(readability_text)
    return "\n".join(lines)


def _render_list_section(title: str, items: list[str], payload: dict[str, Any]) -> str:
    lines = [f"{title}:"]
    lines.extend(f"- {item}" for item in items)
    lines.extend(_render_suggested_patches(payload))
    lines.extend(_render_recommended_command(payload))
    readability_text = _render_readability_from_payload(payload)
    if readability_text:
        lines.append(readability_text)
    return "\n".join(lines)


def _render_missing_models(payload: dict[str, Any]) -> str:
    lines = ["Missing models:"]
    lines.extend(f"- {item}" for item in payload["missing_models"])
    warnings = payload.get("warnings") or []
    if warnings:
        lines.append("Other warnings:")
        lines.extend(f"- {item}" for item in warnings)
    lines.extend(_render_suggested_patches(payload))
    lines.extend(_render_recommended_command(payload))
    readability_text = _render_readability_from_payload(payload)
    if readability_text:
        lines.append(readability_text)
    return "\n".join(lines)


def _nodepack_lockfile_drift() -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    for entry in read_lockfile():
        pack_dir = _doctor_nodepack_dir(entry.name)
        if pack_dir is None:
            warnings.append(f"{entry.name} in lockfile but not installed; skipping drift check")
            continue
        actual = _git_head(pack_dir)
        if actual is None:
            warnings.append(f"{entry.name} is installed at {pack_dir} but git HEAD could not be read; skipping drift check")
            continue
        if actual != entry.git_commit_sha:
            errors.append(f"{entry.name} git HEAD {actual} does not match lockfile git_commit_sha {entry.git_commit_sha}")
        for rel_path, expected_hash in entry.source_sha256.items():
            source_path = pack_dir / rel_path
            if not source_path.is_file():
                errors.append(f"{entry.name} source {rel_path} is missing; expected sha256 {expected_hash}")
                continue
            actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(
                    f"{entry.name} source {rel_path} sha256 {actual_hash} does not match lockfile {expected_hash}"
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


def _git_head(pack_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


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
    warnings: list[str] = []
    warnings.extend(_embedded_configuration_warnings())
    warnings.extend(_video_audio_warnings(workflow))
    warnings.extend(_video_frame_cap_warnings(workflow))
    warnings.extend(_ltx_audio_vae_loader_warnings(workflow))
    warnings.extend(metadata_environment_warnings(workflow.metadata))
    return warnings


def _missing_model_warnings(workflow: VibeWorkflow, path: str) -> list[str]:
    import vibecomfy.fetch as fetch_assets

    warnings: list[str] = []
    for entry in _model_asset_entries(workflow, path):
        if fetch_assets.is_present(entry):
            continue
        warnings.append(
            f"missing model {entry['name']}: expected {fetch_assets.local_path(entry)} — fetch from {entry['url']}"
        )
    return warnings


def _model_asset_entries(workflow: VibeWorkflow, workflow_ref: str) -> list[dict]:
    entries = workflow.metadata.get("model_assets", [])
    if entries:
        return [entry for entry in entries if isinstance(entry, dict)]
    path = _json_path_for_reference(workflow_ref)
    if path is None:
        return []
    return extract_from_raw_workflow(load_workflow_json(path))


def _json_path_for_reference(workflow_ref: str) -> str | None:
    path = Path(workflow_ref)
    if path.suffix.lower() == ".json" and path.is_file():
        return str(path)
    try:
        resolved = Path(resolve_workflow_path(workflow_ref))
    except FileNotFoundError:
        return None
    if resolved.suffix.lower() == ".json" and resolved.is_file():
        return str(resolved)
    return None


def _embedded_configuration_warnings() -> list[str]:
    raw = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"VIBECOMFY_COMFY_CONFIGURATION is not valid JSON: {exc}"]
    if not isinstance(parsed, dict):
        return ["VIBECOMFY_COMFY_CONFIGURATION must be a JSON object."]
    try:
        from vibecomfy.runtime.run import _embedded_configuration
        from vibecomfy.workflow import WorkflowSource

        probe = VibeWorkflow(id="doctor", source=WorkflowSource(id="doctor"))
        config = _embedded_configuration(probe)
    except Exception as exc:
        return [f"embedded configuration could not be constructed: {type(exc).__name__}: {exc}"]
    if config is not None and not hasattr(config, "cwd"):
        return ["embedded configuration is not a Comfy Configuration object; embedded runtime will fail before queueing."]
    return []


def _video_audio_warnings(workflow: VibeWorkflow) -> list[str]:
    warnings: list[str] = []
    edges_by_target = {(edge.to_node, edge.to_input): edge for edge in workflow.edges}
    for node_id, node in sorted(workflow.nodes.items()):
        if node.class_type != "CreateVideo":
            continue
        audio_edge = edges_by_target.get((node_id, "audio"))
        if audio_edge is None and _literal_input(node.inputs, "audio") is None:
            continue
        source = _audio_source(workflow, audio_edge, node.inputs.get("audio"))
        warnings.append(
            "CreateVideo node "
            f"{node_id} has optional audio input connected"
            f"{f' from {source}' if source else ''}; for smoke tests, remove this edge if SaveVideo fails with AAC NaN/Inf."
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


def _ltx_audio_vae_loader_warnings(workflow: VibeWorkflow) -> list[str]:
    warnings: list[str] = []
    for node_id, node in sorted(workflow.nodes.items()):
        if node.class_type != "VAELoaderKJ":
            continue
        vae_name = node.inputs.get("vae_name") or node.inputs.get("widget_0")
        if not isinstance(vae_name, str):
            continue
        normalized = vae_name.lower().replace("\\", "/")
        if "ltx" not in normalized or "audio" not in normalized:
            continue
        warnings.append(
            "VAELoaderKJ node "
            f"{node_id} loads {vae_name!r}; current KJNodes may misclassify LTX audio VAE files. "
            "Use LTXVAudioVAELoader with the file staged under checkpoints."
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


# ---------------------------------------------------------------------------
# Readability integration helpers
# ---------------------------------------------------------------------------


def _resolve_readability_source_path(path: str) -> str | None:
    """Resolve *path* to a .py ready-template source file for readability checks.

    Returns ``None`` when *path* does not point to a .py file (e.g. a JSON
    workflow or a workflow ID that resolves to something non-Python).
    """
    p = Path(path)
    if p.suffix.lower() == ".py" and p.is_file():
        return str(p)
    if p.suffix.lower() == ".json":
        return None
    # Try resolving through the workflow index
    try:
        resolved = Path(resolve_workflow_path(path))
    except FileNotFoundError:
        return None
    if resolved.suffix.lower() == ".py" and resolved.is_file():
        return str(resolved)
    return None


def _attach_readability(
    payload: dict[str, Any], readability_report: ReadabilityReport | None
) -> None:
    """Attach a readability report to *payload* if one was produced."""
    if readability_report is None:
        return
    payload["readability"] = readability_report.to_json()


def _render_readability_text(
    readability_report: ReadabilityReport | None, *_args: Any, **_kwargs: Any
) -> None:
    """Print a human-readable summary of the readability report."""
    if readability_report is None:
        return
    text = _format_readability_text(readability_report)
    if text:
        print(text)


def _format_readability_text(
    readability_report: ReadabilityReport | None,
) -> str:
    """Return a human-readable summary string for a readability report."""
    if readability_report is None:
        return ""
    total_findings = sum(len(sc.findings) for sc in readability_report.subchecks)
    if total_findings == 0:
        return "Readability: ok (no findings)"
    lines = [
        f"Readability: {total_findings} finding{'' if total_findings == 1 else 's'}"
    ]
    for sc in readability_report.subchecks:
        if not sc.findings:
            continue
        for finding in sc.findings:
            node = f" node={finding.node_id}" if finding.node_id else ""
            field = f" field={finding.field}" if finding.field else ""
            lines.append(
                f"- {finding.severity}: {finding.code}{node}{field}: {finding.message}"
            )
    return "\n".join(lines)


def _render_readability_from_payload(payload: dict[str, Any]) -> str:
    """Extract readability text from a payload dict for use in text renderers."""
    readability_payload = payload.get("readability")
    if not isinstance(readability_payload, dict):
        return ""
    # Reconstruct a minimal report-like object for formatting
    subchecks = readability_payload.get("subchecks") or []
    total_findings = sum(
        len(sc.get("findings") or []) for sc in subchecks
    )
    if total_findings == 0:
        return "Readability: ok (no findings)"
    lines = [
        f"Readability: {total_findings} finding{'' if total_findings == 1 else 's'}"
    ]
    for sc in subchecks:
        findings = sc.get("findings") or []
        for f in findings:
            node = f" node={f.get('node_id')}" if f.get("node_id") else ""
            field = f" field={f.get('field')}" if f.get("field") else ""
            lines.append(
                f"- {f.get('severity', 'warning')}: {f.get('code', '?')}{node}{field}: {f.get('message', '')}"
            )
    return "\n".join(lines)


def register(subparsers) -> None:
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("path")
    doctor.add_argument("--lint", action="store_true", default=False)
    doctor.add_argument("--allow-drift", action="store_true", default=False)
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument(
        "--readability",
        action="store_true",
        help="Run readability diagnostics on the emitted ready-template source and include the report in the output.",
    )
    doctor.set_defaults(func=_cmd_doctor)
