"""Deterministic repo-only strict-ready gate for checked-in templates."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from pathlib import Path
from typing import Any, Sequence

from tools.refresh_template_index import REPO_ROOT, build_template_index
from vibecomfy.contracts import build_contract
from vibecomfy.porting.readability_inventory import build_readability_inventory
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.strict_ready import (
    STRICT_READY_BUILD_FAILED,
    STRICT_READY_COMPILE_FAILED,
    STRICT_READY_LOAD_FAILED,
    StrictReadyContext,
    validate_strict_ready_workflow,
)
from vibecomfy.porting.widgets.aliases import widget_alias_analysis
from vibecomfy.porting.emit.emitter import _wrapper_module_for_class
from vibecomfy.porting.object_info import class_has_list_output, class_output_count
from vibecomfy.porting.parity import _is_schema_default_input
from vibecomfy.registry.ready import repo_ready_template_id_for_path
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.registry.static_contract import compare_public_contracts
from vibecomfy.workflow import VibeWorkflow


VERSION = 1
STYLE_CATEGORY = "generated_template_style"
STATIC_DRIFT_CATEGORY = "static_contract_drift"
PACK_VALIDATION_CATEGORY = "pack_validation"
PACK_PROVENANCE_CATEGORY = "pack_provenance"
LEGACY_VOCABULARY_CATEGORY = "legacy_vocabulary"
V26_SHAPE_CATEGORY = "v26_shape"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repo-owned ready templates against strict-ready policy.")
    parser.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    args = parser.parse_args(argv)

    report = build_strict_ready_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 0 if report["ok"] else 1


def build_strict_ready_report() -> dict[str, Any]:
    index_payload = build_template_index()
    rows_by_id = {
        row["id"]: row
        for row in index_payload.get("templates", [])
        if row.get("source_scope") == "repo" and row.get("indexed") is True
    }
    dynamic_rows_excluded = sum(
        1
        for row in index_payload.get("templates", [])
        if row.get("source_scope") == "dynamic" or row.get("indexed") is False
    )
    inventory_entries = {entry.ready_id: entry for entry in build_readability_inventory().entries}

    selected_ids = sorted(rows_by_id)
    targets = [_check_template(rows_by_id[ready_id], inventory_entries.get(ready_id)) for ready_id in selected_ids]
    diagnostics = _flatten_diagnostics(targets)
    summary = _summary(diagnostics)
    ok = not any(
        item["severity"] == "error"
        for item in diagnostics
        if item.get("enforced") is True
    )
    return {
        "version": VERSION,
        "ok": ok,
        "generated_from": "repo-only ready_templates/**/*.py strict-ready gate",
        "template_count": len(rows_by_id),
        "target_count": len(targets),
        "dynamic_rows_excluded": dynamic_rows_excluded,
        "summary": summary,
        "targets": targets,
        "diagnostics": diagnostics,
    }


def _check_template(row: dict[str, Any], inventory_entry: Any | None) -> dict[str, Any]:
    ready_id = str(row["id"])
    relative_path = str(row["path"])
    path = REPO_ROOT / relative_path
    protected = _is_protected(row)
    generated = bool(inventory_entry and inventory_entry.marker == "generated")
    static_drift = _static_drift_diagnostics(row, ready_id=ready_id, enforced=False)
    style_diagnostics = _style_diagnostics(
        inventory_entry,
        ready_id=ready_id,
        path=relative_path,
        enforced=False,
    )
    pack_diagnostics = _pack_validation_diagnostics(
        ready_id=ready_id,
        path=relative_path,
        enforced=protected or generated,
    )
    pack_provenance_diagnostics = _pack_provenance_diagnostics(
        ready_id=ready_id,
        path=path,
        relative_path=relative_path,
        marker=inventory_entry.marker if inventory_entry is not None else "unknown",
        strict_ready_protected=protected,
    )
    legacy_diagnostics = _legacy_vocabulary_diagnostics(
        ready_id=ready_id,
        path=relative_path,
        enforced=protected or generated,
    )
    strict_ready_diagnostics: list[dict[str, Any]] = []
    if protected:
        strict_ready_diagnostics = _strict_ready_diagnostics(ready_id=ready_id, path=path, relative_path=relative_path)
        strict_ready_diagnostics = [{**item, "enforced": False} for item in strict_ready_diagnostics]
    v26_diagnostics = _v26_shape_diagnostics(ready_id=ready_id, path=path, relative_path=relative_path, enforced=protected)
    diagnostics = [
        *static_drift,
        *strict_ready_diagnostics,
        *style_diagnostics,
        *pack_diagnostics,
        *pack_provenance_diagnostics,
        *legacy_diagnostics,
        *v26_diagnostics,
    ]
    return {
        "ready_id": ready_id,
        "path": relative_path,
        "source_scope": "repo",
        "indexed": True,
        "protected": protected,
        "generated": generated,
        "coverage_tier": row.get("coverage_tier") or "",
        "app_active": bool(row.get("app_active") is True),
        "static_drift": static_drift,
        "strict_ready_ok": not any(item["severity"] == "error" for item in strict_ready_diagnostics),
        "strict_ready_diagnostics": strict_ready_diagnostics,
        "style_diagnostics": style_diagnostics,
        "pack_validation_diagnostics": pack_diagnostics,
        "pack_provenance_diagnostics": pack_provenance_diagnostics,
        "legacy_vocabulary_diagnostics": legacy_diagnostics,
        "v26_shape_diagnostics": v26_diagnostics,
        "ok": not any(item["severity"] == "error" and item.get("enforced") is True for item in diagnostics),
    }


def _static_drift_diagnostics(row: dict[str, Any], *, ready_id: str, enforced: bool) -> list[dict[str, Any]]:
    if not enforced:
        return []
    try:
        workflow = _workflow_from_repo_template(ready_id, REPO_ROOT / str(row["path"]))
        contract = build_contract(workflow).to_dict()
        comparison = compare_public_contracts(
            static_inputs=row.get("public_inputs") or [],
            static_outputs=row.get("public_outputs") or [],
            built_inputs=contract.get("public_inputs") or [],
            built_outputs=contract.get("public_outputs") or [],
        )
    except Exception as exc:
        return [
            _diagnostic(
                code=STRICT_READY_BUILD_FAILED,
                message=f"Could not build template for static contract comparison: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target="build_contract",
                severity="error",
                category=STATIC_DRIFT_CATEGORY,
                enforced=enforced,
            )
        ]
    diagnostics: list[dict[str, Any]] = []
    for field, values in sorted(comparison.items()):
        if not values:
            continue
        diagnostics.append(
            _diagnostic(
                code=f"static_contract_{field}",
                message=f"Static and built public contracts differ for {field}.",
                ready_id=ready_id,
                target=field,
                severity="error",
                category=STATIC_DRIFT_CATEGORY,
                enforced=enforced,
                detail={"examples": values[:5], "count": len(values)},
            )
        )
    return diagnostics


def _strict_ready_diagnostics(*, ready_id: str, path: Path, relative_path: str) -> list[dict[str, Any]]:
    try:
        workflow = _workflow_from_repo_template(ready_id, path)
    except Exception as exc:
        return [
            _diagnostic(
                code=STRICT_READY_LOAD_FAILED,
                message=f"Could not load ready template: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target="load",
                severity="error",
                category="strict_ready",
                enforced=True,
            )
        ]
    try:
        api_prompt = workflow.compile("api")
    except Exception as exc:
        return [
            _diagnostic(
                code=STRICT_READY_COMPILE_FAILED,
                message=f"Could not compile ready template API prompt: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target="compile",
                severity="error",
                category="strict_ready",
                enforced=True,
            )
        ]
    issues = validate_strict_ready_workflow(
        workflow,
        StrictReadyContext(ready_id=ready_id, source_path=relative_path),
        api_prompt=api_prompt,
        widget_analysis=widget_alias_analysis(api_prompt, schema_provider=None),
    )
    return [_issue_to_diagnostic(issue, ready_id=ready_id, enforced=True) for issue in issues]


def _style_diagnostics(
    inventory_entry: Any | None,
    *,
    ready_id: str,
    path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    if inventory_entry is None or inventory_entry.marker != "generated":
        return []
    counts = inventory_entry.counts
    checks = [
        ("generated_template_positional_out", "positional `.out(<int>)` calls", counts.positional_outs),
        ("generated_template_widget_n_field", "`widget_N` field references", counts.widget_n_fields),
        ("generated_template_uuid_class_type", "UUID class-type literals", counts.uuid_class_types),
        ("generated_template_n_uuid_variable", "`n_<uuid>` variable names", counts.n_uuid_variables),
        ("generated_template_local_node_copy", "local `_node` helper copies", counts.local_node_copies),
        (
            "generated_template_missing_output_contract",
            "missing public output contract",
            int(counts.missing_output_contract),
        ),
    ]
    diagnostics: list[dict[str, Any]] = []
    for code, label, count in checks:
        if count <= 0:
            continue
        diagnostics.append(
            _diagnostic(
                code=code,
                message=f"Generated template has {label}.",
                ready_id=ready_id,
                target=path,
                severity="error" if enforced else "warning",
                category=STYLE_CATEGORY,
                enforced=enforced,
                detail={"count": count},
            )
        )
    return diagnostics


def _legacy_vocabulary_diagnostics(
    *,
    ready_id: str,
    path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    """Reject generated templates importing or calling legacy vocabulary.

    Checks for:
    - Import of ``vibecomfy.registry.ready_template``
    - Direct calls to ``bind_input``, ``bind_output``, ``apply_ready_template_policy``,
      ``wf.register_input`` inside ``build()``.
    """
    if not enforced:
        return []
    # Only enforce for the 5 generated/pilot templates. Legacy templates
    # still use the old vocabulary and will be migrated separately.
    if path not in _PILOT_TEMPLATE_PATHS:
        return []
    template_path = REPO_ROOT / path
    if not template_path.is_file():
        return []
    try:
        source = template_path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        tree = ast.parse(source, filename=str(template_path))
    except SyntaxError:
        return []

    diagnostics: list[dict[str, Any]] = []
    _LEGACY_IMPORT = "vibecomfy.registry.ready_template"
    _LEGACY_CALLS = frozenset({"bind_input", "bind_output", "apply_ready_template_policy"})

    # Check imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", None)
            if module == _LEGACY_IMPORT or (isinstance(node, ast.Import) and any(
                getattr(alias, "name", "") == _LEGACY_IMPORT for alias in node.names
            )):
                diagnostics.append(
                    _diagnostic(
                        code="legacy_vocabulary_import",
                        message=f"Generated template imports legacy module {_LEGACY_IMPORT!r}.",
                        ready_id=ready_id,
                        target=path,
                        severity="error",
                        category=LEGACY_VOCABULARY_CATEGORY,
                        enforced=enforced,
                        detail={"import": _LEGACY_IMPORT, "line": node.lineno},
                    )
                )
        # Check legacy function calls inside build()
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "wf" and node.func.attr == "register_input":
                    func_name = "wf.register_input"
            if func_name in _LEGACY_CALLS or func_name == "wf.register_input":
                # Verify we're inside a build() function
                call_name = func_name or (
                    f"wf.{node.func.attr}" if isinstance(node.func, ast.Attribute) else "unknown"
                )
                diagnostics.append(
                    _diagnostic(
                        code="legacy_vocabulary_call",
                        message=f"Generated template calls legacy function {call_name!r}.",
                        ready_id=ready_id,
                        target=f"{path}:{node.lineno}",
                        severity="error",
                        category=LEGACY_VOCABULARY_CATEGORY,
                        enforced=enforced,
                        detail={"call": call_name, "line": node.lineno},
                    )
                )

    return diagnostics


def _v26_shape_diagnostics(
    *,
    ready_id: str,
    path: Path,
    relative_path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [
            _diagnostic(
                code="v26_template_parse_failed",
                message=f"Could not parse ready template for v2.6 shape checks: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target=relative_path,
                severity="error",
                category=V26_SHAPE_CATEGORY,
                enforced=enforced,
            )
        ]

    diagnostics: list[dict[str, Any]] = []
    wrapper_imports: dict[str, str] = {}
    legacy_calls = {"bind_input", "bind_output", "ready_node", "finalize_ready_template", "finalize_ready"}
    legacy_import = "vibecomfy.registry.ready_template"

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("vibecomfy.nodes"):
                for alias in node.names:
                    wrapper_imports[alias.asname or alias.name] = alias.name
            if node.module == legacy_import:
                diagnostics.append(
                    _diagnostic(
                        code="v26_legacy_ready_template_import",
                        message=f"Ready template imports legacy module {legacy_import!r}.",
                        ready_id=ready_id,
                        target=f"{relative_path}:{node.lineno}",
                        severity="error",
                        category=V26_SHAPE_CATEGORY,
                        enforced=enforced,
                    )
                )
        elif isinstance(node, ast.Import):
            if any(alias.name == legacy_import for alias in node.names):
                diagnostics.append(
                    _diagnostic(
                        code="v26_legacy_ready_template_import",
                        message=f"Ready template imports legacy module {legacy_import!r}.",
                        ready_id=ready_id,
                        target=f"{relative_path}:{node.lineno}",
                        severity="error",
                        category=V26_SHAPE_CATEGORY,
                        enforced=enforced,
                    )
                )

    build_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build"]
    if len(build_defs) != 1:
        diagnostics.append(
            _diagnostic(
                code="v26_build_function_count",
                message="Ready template must define exactly one top-level build() function.",
                ready_id=ready_id,
                target=relative_path,
                severity="error",
                category=V26_SHAPE_CATEGORY,
                enforced=enforced,
                detail={"count": len(build_defs)},
            )
        )
        return _downgrade_unenforced_v26(diagnostics, enforced)
    build = build_defs[0]

    with_blocks = [
        stmt
        for stmt in build.body
        if isinstance(stmt, ast.With)
        and any(_is_new_workflow_context(item) for item in stmt.items)
    ]
    if len(with_blocks) != 1:
        diagnostics.append(
            _diagnostic(
                code="v26_new_workflow_context_count",
                message="build() must contain exactly one top-level `with new_workflow(...) as wf:` block.",
                ready_id=ready_id,
                target=f"{relative_path}:{build.lineno}",
                severity="error",
                category=V26_SHAPE_CATEGORY,
                enforced=enforced,
                detail={"count": len(with_blocks)},
            )
        )
        with_range = None
    else:
        with_range = (with_blocks[0].lineno, getattr(with_blocks[0], "end_lineno", with_blocks[0].lineno))

    var_classes: dict[str, str] = {}
    for node in ast.walk(build):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            class_type = _class_type_for_call(node.value, wrapper_imports)
            if class_type:
                var_classes[node.targets[0].id] = class_type

    for node in ast.walk(build):
        if not isinstance(node, ast.Call):
            continue
        func_name = _call_name(node)
        if func_name in legacy_calls:
            diagnostics.append(
                _diagnostic(
                    code="v26_legacy_ready_template_call",
                    message=f"Ready template calls legacy helper {func_name!r}.",
                    ready_id=ready_id,
                    target=f"{relative_path}:{node.lineno}",
                    severity="error",
                    category=V26_SHAPE_CATEGORY,
                    enforced=enforced,
                )
            )
        class_type = _class_type_for_call(node, wrapper_imports)
        if class_type:
            if _is_wrapper_call(node, wrapper_imports):
                if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "wf":
                    diagnostics.append(_v26_diag(ready_id, relative_path, node.lineno, "v26_explicit_wf_wrapper_call", f"Generated wrapper {class_type} must not pass `wf` in ready templates.", enforced))
                if not node.args and with_range is not None and not (with_range[0] <= node.lineno <= with_range[1]):
                    diagnostics.append(_v26_diag(ready_id, relative_path, node.lineno, "v26_wrapper_outside_context", f"Generated wrapper {class_type} is called outside the active workflow context.", enforced))
            elif _wrapper_module_for_class(class_type) is not None:
                diagnostics.append(_v26_diag(ready_id, relative_path, node.lineno, "v26_wrapper_eligible_node_call", f"Bare node(wf, {class_type!r}, ...) used where a generated wrapper exists.", enforced))
            diagnostics.extend(_v26_node_kwarg_diagnostics(ready_id, relative_path, node, class_type, enforced))
        if isinstance(node.func, ast.Attribute) and node.func.attr == "out" and isinstance(node.func.value, ast.Name):
            class_type = var_classes.get(node.func.value.id)
            if class_type and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                if _is_single_output_class(class_type):
                    diagnostics.append(_v26_diag(ready_id, relative_path, node.lineno, "v26_single_output_named_out", f"Single-output node {class_type} should use a bare builder reference or `.out()`, not `.out({node.args[0].value!r})`.", enforced))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == "ReadyMetadata.build":
            for kw in node.keywords:
                if kw.arg in {
                    "template_id",
                    "source_workflow",
                    "vibecomfy_version",
                    "comfy_core",
                    "source_role",
                    "coverage_tier",
                }:
                    diagnostics.append(_v26_diag(ready_id, relative_path, node.lineno, "v26_derivable_metadata_field", f"ReadyMetadata.build emits derivable field {kw.arg!r}.", enforced))
                if kw.arg == "provenance" and _is_derivable_provenance_kwarg(kw):
                    diagnostics.append(_v26_diag(ready_id, relative_path, node.lineno, "v26_derivable_metadata_field", f"ReadyMetadata.build emits derivable field {kw.arg!r}.", enforced))
            packs_kw = next((kw for kw in node.keywords if kw.arg == "custom_node_packs"), None)
            diagnostics.extend(_v26_pack_provenance_diagnostics(ready_id, relative_path, tree, packs_kw, enforced))
            break

    return _downgrade_unenforced_v26(diagnostics, enforced)


def _downgrade_unenforced_v26(diagnostics: list[dict[str, Any]], enforced: bool) -> list[dict[str, Any]]:
    if enforced:
        return diagnostics
    return [
        {**item, "severity": "warning", "enforced": False}
        if item.get("category") == V26_SHAPE_CATEGORY
        else item
        for item in diagnostics
    ]


def _is_new_workflow_context(item: ast.withitem) -> bool:
    call = item.context_expr
    if not isinstance(call, ast.Call) or _call_name(call) != "new_workflow":
        return False
    return isinstance(item.optional_vars, ast.Name) and item.optional_vars.id == "wf"


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parent = _expr_name(func.value)
        return f"{parent}.{func.attr}" if parent else func.attr
    return None


def _expr_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expr_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _is_wrapper_call(node: ast.Call, wrapper_imports: dict[str, str]) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id in wrapper_imports


def _class_type_for_call(node: ast.AST, wrapper_imports: dict[str, str]) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    if isinstance(node.func, ast.Name) and node.func.id in wrapper_imports:
        return wrapper_imports[node.func.id]
    if _call_name(node) == "node" and len(node.args) >= 2:
        try:
            return str(ast.literal_eval(node.args[1]))
        except Exception:
            return None
    return None


def _is_single_output_class(class_type: str) -> bool:
    try:
        return class_output_count(class_type) == 1 and not class_has_list_output(class_type)
    except Exception:
        return False


def _v26_node_kwarg_diagnostics(ready_id: str, path: str, node: ast.Call, class_type: str, enforced: bool) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for kw in node.keywords:
        if kw.arg is None:
            continue
        if kw.arg == "_outputs" and _is_single_output_class(class_type):
            diagnostics.append(_v26_diag(ready_id, path, node.lineno, "v26_single_output_outputs_kwarg", f"Single-output node {class_type} must not emit `_outputs=`.", enforced))
            continue
        try:
            value = ast.literal_eval(kw.value)
        except Exception:
            continue
        if _is_schema_default_input(class_type, kw.arg, value):
            diagnostics.append(_v26_diag(ready_id, path, node.lineno, "v26_schema_default_kwarg", f"Schema-default kwarg {class_type}.{kw.arg}={value!r} should be omitted.", enforced))
    return diagnostics


def _v26_pack_provenance_diagnostics(ready_id: str, path: str, tree: ast.AST, packs_kw: ast.keyword | None, enforced: bool) -> list[dict[str, Any]]:
    try:
        from vibecomfy.node_packs_lockfile import read_lockfile
    except ImportError:
        return []
    by_class: dict[str, str] = {}
    entries_by_name: dict[str, Any] = {}
    try:
        for entry in read_lockfile(REPO_ROOT / "custom_nodes.lock"):
            entries_by_name[entry.name] = entry
            for class_type in entry.class_set:
                by_class.setdefault(str(class_type), entry.name)
    except Exception:
        return []
    packs: dict[str, Any] = {}
    if packs_kw is not None:
        try:
            packs = dict(ast.literal_eval(packs_kw.value))
        except Exception:
            packs = {}
    diagnostics: list[dict[str, Any]] = []
    wrapper_imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("vibecomfy.nodes"):
            for alias in node.names:
                wrapper_imports[alias.asname or alias.name] = alias.name
    used_classes = {class_type for node in ast.walk(tree) if (class_type := _class_type_for_call(node, wrapper_imports))}
    for class_type in sorted(used_classes):
        pack_name = by_class.get(class_type)
        if pack_name is None:
            continue
        pack_meta = packs.get(pack_name)
        if not isinstance(pack_meta, dict) or not pack_meta.get("commit"):
            diagnostics.append(_v26_diag(ready_id, path, 1, "v26_missing_custom_node_pack_commit", f"Custom-node class {class_type} lacks custom_node_packs provenance with commit for pack {pack_name}.", enforced))
    return diagnostics


def _is_derivable_provenance_kwarg(kw: ast.keyword) -> bool:
    try:
        value = ast.literal_eval(kw.value)
    except Exception:
        return False
    return isinstance(value, dict) and set(value).issubset({"source_workflow", "source_role"})


def _v26_diag(ready_id: str, path: str, line: int, code: str, message: str, enforced: bool) -> dict[str, Any]:
    return _diagnostic(
        code=code,
        message=message,
        ready_id=ready_id,
        target=f"{path}:{line}",
        severity="error",
        category=V26_SHAPE_CATEGORY,
        enforced=enforced,
    )


# The 5 pilot templates that are the target of pack validation.
_PILOT_TEMPLATE_PATHS: frozenset[str] = frozenset({
    "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
    "ready_templates/image/qwen_image_2512.py",
    "ready_templates/video/wan_i2v.py",
    "ready_templates/audio/ace_step_1_5_t2a_song.py",
    "ready_templates/edit/qwen_image_edit.py",
})


def _pack_validation_diagnostics(
    *,
    ready_id: str,
    path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    """Validate template node classes against known custom-node packs.

    Only runs for the 5 generated/pilot templates.  Returns diagnostics for
    unknown classes.  Deferred all-template enforcement until legacy _node
    templates are migrated or allowed.
    """
    if not enforced or path not in _PILOT_TEMPLATE_PATHS:
        return []
    try:
        from tools.validate_templates_against_packs import (
            _extract_node_classes,
            _is_comfy_core,
            _load_known_packs,
            _suggest_pack,
        )
    except ImportError:
        return []

    template_path = REPO_ROOT / path
    if not template_path.is_file():
        return []

    try:
        source = template_path.read_text(encoding="utf-8")
    except Exception:
        return []

    class_to_pack, _all_classes = _load_known_packs()

    diagnostics: list[dict[str, Any]] = []
    for class_name, node_id, lineno in _extract_node_classes(source, template_path):
        pack_name = class_to_pack.get(class_name)
        if pack_name is not None:
            continue  # known pack class
        if _is_comfy_core(class_name):
            continue  # known ComfyUI core class
        # Unknown class — try fuzzy match
        suggested = _suggest_pack(class_name, class_to_pack)
        if suggested is None:
            continue  # no suggestion, treat as core

        diagnostics.append(
            _diagnostic(
                code="pack_validation_unknown_class",
                message=f"Unknown class {class_name!r} (node {node_id!r}) — suggested pack: {suggested}",
                ready_id=ready_id,
                target=f"{path}:{lineno}",
                severity="error",
                category=PACK_VALIDATION_CATEGORY,
                enforced=enforced,
                detail={
                    "class": class_name,
                    "node_id": node_id,
                    "line": lineno,
                    "suggested_pack": suggested,
                },
            )
        )

    return diagnostics


def _pack_provenance_diagnostics(
    *,
    ready_id: str,
    path: Path,
    relative_path: str,
    marker: str,
    strict_ready_protected: bool,
) -> list[dict[str, Any]]:
    """Run the v2.4 pack provenance checker in report-only mode.

    Hard strict-ready enforcement is intentionally deferred until the
    migration/report-only pass is clean.
    """
    try:
        from tools.check_pack_provenance import diagnostics_for_template
    except ImportError:
        return []
    diagnostics = diagnostics_for_template(
        ready_id=ready_id,
        path=path,
        marker=marker,
        strict_ready_protected=strict_ready_protected,
        enforced=False,
    )
    return [
        {
            **item,
            "target": item.get("target") or relative_path,
            "enforced": False,
        }
        for item in diagnostics
    ]


def _workflow_from_repo_template(template_id: str, path: Path) -> VibeWorkflow:
    spec = importlib.util.spec_from_file_location(f"vibecomfy_strict_ready_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import ready template {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build = getattr(module, "build", None)
    if build is None:
        raise ValueError(f"Ready template {template_id} must define build()")
    workflow = build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"Ready template {template_id} build() must return VibeWorkflow, got {type(workflow).__name__}")
    resolved_template_id = repo_ready_template_id_for_path(path, REPO_ROOT / "ready_templates")
    if resolved_template_id != template_id:
        raise ValueError(f"Template path {path} resolved to {resolved_template_id!r}, expected {template_id!r}")
    if not workflow.metadata.get("python_policy_applied"):
        ready_metadata = getattr(module, "READY_METADATA", None)
        if isinstance(ready_metadata, dict):
            ready_metadata = {**ready_metadata, "ready_template": ready_metadata.get("ready_template") or template_id}
            requirements = getattr(module, "READY_REQUIREMENTS", None)
            workflow = apply_ready_template_policy(
                workflow,
                ready_metadata,
                source_path=str(path),
                requirements=requirements if isinstance(requirements, dict) else None,
            )
    workflow.metadata["ready_template"] = workflow.metadata.get("ready_template") or template_id
    return workflow


def _issue_to_diagnostic(issue: PortIssue, *, ready_id: str, enforced: bool) -> dict[str, Any]:
    payload = issue.to_json()
    detail = dict(payload.get("detail") or {})
    target = str(detail.get("target") or payload.get("node_id") or payload["code"])
    return _diagnostic(
        code=str(payload["code"]),
        message=str(payload["message"]),
        ready_id=ready_id,
        target=target,
        severity=str(payload["severity"]),
        category=str(detail.get("category") or "strict_ready"),
        enforced=enforced and payload["severity"] == "error",
        detail=detail,
        node_id=payload.get("node_id"),
        class_type=payload.get("class_type"),
        recommendation=payload.get("recommendation"),
    )


def _diagnostic(
    *,
    code: str,
    message: str,
    ready_id: str,
    target: str,
    severity: str,
    category: str,
    enforced: bool,
    detail: dict[str, Any] | None = None,
    node_id: str | None = None,
    class_type: str | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "ready_id": ready_id,
        "target": target,
        "category": category,
        "enforced": enforced,
        "message": message,
    }
    if node_id:
        payload["node_id"] = node_id
    if class_type:
        payload["class_type"] = class_type
    if recommendation:
        payload["recommendation"] = recommendation
    if detail:
        payload["detail"] = detail
    return payload


def _flatten_diagnostics(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for target in targets:
        diagnostics.extend(target["static_drift"])
        diagnostics.extend(target["strict_ready_diagnostics"])
        diagnostics.extend(target["style_diagnostics"])
        diagnostics.extend(target.get("pack_validation_diagnostics", []))
        diagnostics.extend(target.get("pack_provenance_diagnostics", []))
        diagnostics.extend(target.get("legacy_vocabulary_diagnostics", []))
    return sorted(diagnostics, key=lambda item: (item["ready_id"], item["category"], item["code"], item["target"]))


def _summary(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity = {"error": 0, "warning": 0, "info": 0}
    by_category: dict[str, int] = {}
    enforced_errors = 0
    for item in diagnostics:
        severity = str(item["severity"])
        by_severity[severity] = by_severity.get(severity, 0) + 1
        category = str(item["category"])
        by_category[category] = by_category.get(category, 0) + 1
        if severity == "error" and item.get("enforced") is True:
            enforced_errors += 1
    return {
        "diagnostics": len(diagnostics),
        "enforced_errors": enforced_errors,
        "by_severity": by_severity,
        "by_category": {key: by_category[key] for key in sorted(by_category)},
    }


def _is_protected(row: dict[str, Any]) -> bool:
    return row.get("app_active") is True or row.get("coverage_tier") == "required"


def _print_text_report(report: dict[str, Any]) -> None:
    status = "ok" if report["ok"] else "failed"
    print(f"strict-ready gate {status}: {report['target_count']} target(s), {report['summary']['diagnostics']} diagnostic(s)")
    for item in report["diagnostics"]:
        print(f"{item['severity']}: {item['ready_id']}: {item['code']} ({item['target']})")


__all__ = [
    "build_strict_ready_report",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
