"""Validate ready-template node classes against declared structured pack refs."""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.backfill_custom_node_refs import BackfillTarget, _extract_requirements, _select_targets
from tools.validate_templates_against_packs import _is_comfy_core
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.node_packs import get_known_node_packs
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.registry.static_contract import extract_ready_template_contract

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = 1


@dataclass(frozen=True)
class NodeClassUse:
    class_type: str
    node_id: str
    line: int
    call: str


@dataclass(frozen=True)
class PackIndex:
    entries_by_name: dict[str, LockEntry]
    entries_by_slug: dict[str, LockEntry]
    pack_name_by_class: dict[str, str]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when provenance errors are present. Default is report-only.",
    )
    parser.add_argument(
        "--all-ready",
        action="store_true",
        help="Scan every ready_templates/**/*.py file instead of migrated generated/strict-ready targets.",
    )
    args = parser.parse_args(argv)

    report = build_pack_provenance_report(all_ready=args.all_ready)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 1 if args.strict and not report["ok"] else 0


def build_pack_provenance_report(*, all_ready: bool = False) -> dict[str, Any]:
    targets = _all_ready_targets() if all_ready else list(_select_targets())
    index = _pack_index(read_lockfile())
    target_reports = [_check_target(target, index) for target in targets]
    diagnostics = sorted(
        [item for target in target_reports for item in target["diagnostics"]],
        key=lambda item: (item["ready_id"], item["code"], item["target"]),
    )
    return {
        "version": VERSION,
        "ok": not any(item["severity"] == "error" for item in diagnostics),
        "mode": "all_ready" if all_ready else "migrated_generated_and_strict_ready",
        "target_count": len(target_reports),
        "summary": _summary(diagnostics),
        "targets": target_reports,
        "diagnostics": diagnostics,
    }


def diagnostics_for_template(
    *,
    ready_id: str,
    path: Path,
    marker: str,
    strict_ready_protected: bool,
    enforced: bool = False,
    lock_entries: list[LockEntry] | None = None,
) -> list[dict[str, Any]]:
    target = BackfillTarget(ready_id, path, marker, strict_ready_protected)
    index = _pack_index(lock_entries if lock_entries is not None else read_lockfile())
    return _check_target(target, index, enforced=enforced)["diagnostics"]


def extract_node_class_uses(source: str) -> list[NodeClassUse]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    uses: list[NodeClassUse] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        class_type = _class_type_from_call(node)
        if class_type is None:
            continue
        uses.append(
            NodeClassUse(
                class_type=class_type,
                node_id=_node_id_from_call(node),
                line=node.lineno,
                call=_call_name(node),
            )
        )
    return sorted(uses, key=lambda item: (item.line, item.class_type, item.node_id))


def _check_target(target: BackfillTarget, index: PackIndex, *, enforced: bool = False) -> dict[str, Any]:
    relative_path = _display_path(target.path)
    try:
        source = target.path.read_text(encoding="utf-8")
    except OSError as exc:
        diagnostic = _diagnostic(
            code="pack_provenance_unreadable_template",
            message=f"Could not read template: {type(exc).__name__}: {exc}",
            ready_id=target.ready_id,
            target=relative_path,
            severity="error",
            enforced=enforced,
            detail={},
        )
        return _target_payload(target, relative_path, [diagnostic])
    contract = extract_ready_template_contract(target.path)
    requirements = contract.get("requirements") if isinstance(contract.get("requirements"), Mapping) else {}
    if not requirements:
        requirements = _extract_requirements(source) or {}
    normalized, _warnings = normalize_custom_node_requirements(requirements)
    declared_refs = [dict(ref) for ref in normalized.get("custom_node_refs") or [] if isinstance(ref, Mapping)]
    declared_entries = _declared_lock_entries(declared_refs, index)
    declared_classes: dict[str, LockEntry] = {}
    for entry in declared_entries:
        for class_type in entry.class_set:
            declared_classes[class_type] = entry

    diagnostics: list[dict[str, Any]] = []
    for use in extract_node_class_uses(source):
        if _is_comfy_core(use.class_type):
            continue
        declared_entry = declared_classes.get(use.class_type)
        if declared_entry is not None:
            continue
        lock_entry = _lock_entry_for_class(use.class_type, index)
        pack_name = index.pack_name_by_class.get(use.class_type)
        if lock_entry is not None:
            diagnostics.append(
                _diagnostic(
                    code="pack_provenance_missing_declared_ref",
                    message=f"Class {use.class_type!r} is provided by locked pack {lock_entry.name!r} but no declared structured ref covers it.",
                    ready_id=target.ready_id,
                    target=f"{relative_path}:{use.line}",
                    severity="error",
                    enforced=enforced,
                    detail=_use_detail(use, pack=lock_entry.name),
                )
            )
        elif pack_name is not None:
            diagnostics.append(
                _diagnostic(
                    code="pack_provenance_pack_missing_from_lock",
                    message=f"Class {use.class_type!r} maps to known pack {pack_name!r}, but that pack is not in custom_nodes.lock.",
                    ready_id=target.ready_id,
                    target=f"{relative_path}:{use.line}",
                    severity="error",
                    enforced=enforced,
                    detail=_use_detail(use, pack=pack_name),
                )
            )
    return _target_payload(target, relative_path, diagnostics)


def _target_payload(target: BackfillTarget, relative_path: str, diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ready_id": target.ready_id,
        "path": relative_path,
        "marker": target.marker,
        "strict_ready_protected": target.strict_ready_protected,
        "diagnostics": diagnostics,
        "ok": not any(item["severity"] == "error" for item in diagnostics),
    }


def _class_type_from_call(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute) and node.func.attr == "node":
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return node.args[0].value
        return _class_type_from_keyword(node)
    if isinstance(node.func, ast.Name) and node.func.id in {"node", "_node"}:
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
            return node.args[1].value
        return _class_type_from_keyword(node)
    return None


def _class_type_from_keyword(node: ast.Call) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == "class_type" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _node_id_from_call(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute) and node.func.attr == "node":
        index = 1
    else:
        index = 2
    if len(node.args) > index and isinstance(node.args[index], ast.Constant):
        return str(node.args[index].value)
    for keyword in node.keywords:
        if keyword.arg in {"node_id", "id"} and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return ""


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _pack_index(lock_entries: list[LockEntry]) -> PackIndex:
    entries_by_name = {entry.name: entry for entry in lock_entries}
    entries_by_slug = {entry.slug: entry for entry in lock_entries if entry.slug}
    pack_name_by_class: dict[str, str] = {}
    for pack in get_known_node_packs():
        for class_type in pack.classes:
            pack_name_by_class[class_type] = pack.name
    for entry in lock_entries:
        for class_type in entry.class_set:
            pack_name_by_class[class_type] = entry.name
    return PackIndex(entries_by_name, entries_by_slug, pack_name_by_class)


def _declared_lock_entries(refs: list[dict[str, Any]], index: PackIndex) -> list[LockEntry]:
    entries: list[LockEntry] = []
    seen: set[str] = set()
    for ref in refs:
        slug = str(ref.get("slug") or "")
        name = str(ref.get("name") or "")
        entry = index.entries_by_slug.get(slug) or index.entries_by_name.get(name) or index.entries_by_name.get(slug)
        if entry is None or entry.name in seen:
            continue
        seen.add(entry.name)
        entries.append(entry)
    return entries


def _lock_entry_for_class(class_type: str, index: PackIndex) -> LockEntry | None:
    for entry in index.entries_by_name.values():
        if class_type in entry.class_set:
            return entry
    return None


def _all_ready_targets() -> list[BackfillTarget]:
    targets: list[BackfillTarget] = []
    for path in sorted((REPO_ROOT / "ready_templates").rglob("*.py")):
        ready_id = path.relative_to(REPO_ROOT / "ready_templates").with_suffix("").as_posix()
        targets.append(BackfillTarget(ready_id, path, "unknown", False))
    return targets


def _diagnostic(
    *,
    code: str,
    message: str,
    ready_id: str,
    target: str,
    severity: str,
    enforced: bool,
    detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "ready_id": ready_id,
        "target": target,
        "category": "pack_provenance",
        "enforced": enforced,
        "message": message,
        "detail": detail,
    }


def _use_detail(use: NodeClassUse, *, pack: str) -> dict[str, Any]:
    return {
        "class_type": use.class_type,
        "node_id": use.node_id,
        "line": use.line,
        "call": use.call,
        "pack": pack,
    }


def _summary(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_severity: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    enforced_errors = 0
    for item in diagnostics:
        by_code[str(item["code"])] = by_code.get(str(item["code"]), 0) + 1
        severity = str(item["severity"])
        by_severity[severity] = by_severity.get(severity, 0) + 1
        if severity == "error" and item.get("enforced") is True:
            enforced_errors += 1
    return {
        "diagnostics": len(diagnostics),
        "enforced_errors": enforced_errors,
        "by_code": {key: by_code[key] for key in sorted(by_code)},
        "by_severity": by_severity,
    }


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _print_text_report(report: dict[str, Any]) -> None:
    status = "ok" if report["ok"] else "issues"
    print(f"pack provenance {status}: {report['target_count']} target(s), {report['summary']['diagnostics']} diagnostic(s)")
    for item in report["diagnostics"]:
        print(f"{item['severity']}: {item['ready_id']}: {item['code']} ({item['target']})")


__all__ = [
    "build_pack_provenance_report",
    "diagnostics_for_template",
    "extract_node_class_uses",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
