"""Backfill structured custom-node refs for selected ready templates."""
from __future__ import annotations

import argparse
import ast
import json
import pprint
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from vibecomfy.custom_node_refs import lock_entry_to_ref, normalize_custom_node_requirements
from vibecomfy.node_packs import get_known_node_packs
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.porting.readability_inventory import build_readability_inventory
from vibecomfy.registry.static_contract import extract_ready_template_contract

from tools.refresh_template_index import DEFAULT_OUTPUT, _literal_value, build_template_index

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BackfillTarget:
    ready_id: str
    path: Path
    marker: str
    strict_ready_protected: bool


@dataclass(frozen=True)
class PackLookup:
    refs_by_name: dict[str, dict[str, Any]]
    refs_by_class: dict[str, dict[str, Any]]
    pack_name_by_class: dict[str, str]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill requirements.custom_node_refs in ready templates.")
    parser.add_argument("--write", action="store_true", help="Write template and template_index.json changes.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    parser.add_argument("--template-index", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = backfill_custom_node_refs(write=args.write, template_index=args.template_index)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_report(report))
    return 1 if report["summary"]["errors"] else 0


def backfill_custom_node_refs(*, write: bool, template_index: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    lookup = _pack_lookup(read_lockfile())
    targets = _select_targets()
    rows: list[dict[str, Any]] = []
    buckets: dict[str, list[str]] = {
        "updated": [],
        "unchanged": [],
        "unknown_marker": [],
        "unknown_marker_strict_ready_protected": [],
        "manual_or_authored": [],
        "unresolved_pack_names": [],
        "unsupported_requirements_shape": [],
    }

    for target in targets:
        row = _backfill_one(target, lookup=lookup, write=write)
        rows.append(row)
        status = str(row["status"])
        if status in buckets:
            buckets[status].append(target.ready_id)
        if target.marker == "unknown":
            buckets["unknown_marker"].append(target.ready_id)
            if target.strict_ready_protected:
                buckets["unknown_marker_strict_ready_protected"].append(target.ready_id)
        if target.marker in {"manual", "authored", "reference"}:
            buckets["manual_or_authored"].append(target.ready_id)
        if row.get("unresolved_pack_names"):
            buckets["unresolved_pack_names"].append(target.ready_id)
        if status == "unsupported_requirements_shape":
            buckets["unsupported_requirements_shape"].append(target.ready_id)

    if write:
        refreshed = build_template_index(generated_at=_existing_generated_at(template_index))
        template_index.write_text(json.dumps(refreshed, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    summary = {
        "target_count": len(targets),
        "updated": sum(1 for row in rows if row["status"] == "updated"),
        "unchanged": sum(1 for row in rows if row["status"] == "unchanged"),
        "errors": sum(1 for row in rows if row["status"] == "unsupported_requirements_shape"),
    }
    return {
        "write": write,
        "selection_rule": "marker == generated OR repo-indexed app_active is true OR coverage_tier == required",
        "buckets": {key: sorted(set(value)) for key, value in buckets.items()},
        "summary": summary,
        "templates": rows,
    }


def _select_targets() -> list[BackfillTarget]:
    inventory = build_readability_inventory()
    index = _load_template_index()
    targets: list[BackfillTarget] = []
    for entry in inventory.entries:
        index_row = index.get(entry.ready_id, {})
        protected = index_row.get("app_active") is True or index_row.get("coverage_tier") == "required"
        if entry.marker != "generated" and not protected:
            continue
        targets.append(
            BackfillTarget(
                ready_id=entry.ready_id,
                path=REPO_ROOT / entry.path,
                marker=entry.marker,
                strict_ready_protected=protected,
            )
        )
    return sorted(targets, key=lambda item: item.ready_id)


def _backfill_one(target: BackfillTarget, *, lookup: PackLookup, write: bool) -> dict[str, Any]:
    source = target.path.read_text(encoding="utf-8")
    contract = extract_ready_template_contract(target.path)
    requirements = _extract_requirements(source)
    if requirements is None:
        return {
            "id": target.ready_id,
            "path": _display_path(target.path),
            "marker": target.marker,
            "strict_ready_protected": target.strict_ready_protected,
            "status": "unsupported_requirements_shape",
        }
    refs, unresolved_pack_names = _refs_for_template(source, requirements, lookup)
    existing_normalized, _existing_warnings = normalize_custom_node_requirements(requirements)
    if not refs and not unresolved_pack_names and not existing_normalized.get("custom_nodes"):
        return {
            "id": target.ready_id,
            "path": _display_path(target.path),
            "marker": target.marker,
            "strict_ready_protected": target.strict_ready_protected,
            "status": "unchanged",
            "custom_nodes": [],
            "custom_node_refs": [],
            "unresolved_pack_names": [],
        }
    if not refs and not unresolved_pack_names:
        normalized_custom_nodes = sorted(contract.get("custom_nodes") or [])
    else:
        normalized_custom_nodes = sorted(
            {
                *(str(ref["slug"]) for ref in refs if isinstance(ref.get("slug"), str)),
                *unresolved_pack_names,
            }
        )
    updated_requirements = dict(requirements)
    updated_requirements["custom_nodes"] = normalized_custom_nodes
    if refs:
        updated_requirements["custom_node_refs"] = refs
    else:
        updated_requirements.pop("custom_node_refs", None)
    normalized, _warnings = normalize_custom_node_requirements(updated_requirements)
    normalized["models"] = updated_requirements.get("models", requirements.get("models", []))

    if not _has_ready_requirements_assignment(source) and not normalized.get("custom_nodes") and not normalized.get("custom_node_refs"):
        return {
            "id": target.ready_id,
            "path": target.path.relative_to(REPO_ROOT).as_posix(),
            "marker": target.marker,
            "strict_ready_protected": target.strict_ready_protected,
            "status": "unchanged",
            "custom_nodes": [],
            "custom_node_refs": [],
            "unresolved_pack_names": unresolved_pack_names,
        }

    if _uses_ready_metadata_build(source) and _uses_finalize(source):
        updated_source = _replace_ready_metadata_requirements(source, normalized)
        updated_source = _strip_top_level_assignment(updated_source, "READY_REQUIREMENTS")
    else:
        updated_source = _replace_ready_requirements(source, normalized)
    changed = updated_source != source
    if changed and write:
        target.path.write_text(updated_source, encoding="utf-8")
    status = "updated" if changed else "unchanged"
    return {
        "id": target.ready_id,
        "path": _display_path(target.path),
        "marker": target.marker,
        "strict_ready_protected": target.strict_ready_protected,
        "status": status,
        "custom_nodes": normalized.get("custom_nodes", []),
        "custom_node_refs": normalized.get("custom_node_refs", []),
        "unresolved_pack_names": unresolved_pack_names,
    }


def _refs_for_template(
    source: str,
    requirements: Mapping[str, Any],
    lookup: PackLookup,
) -> tuple[list[dict[str, Any]], list[str]]:
    refs_by_key: dict[str, dict[str, Any]] = {}
    unresolved_pack_names: list[str] = []
    for class_type in _extract_node_class_literals(source):
        ref = lookup.refs_by_class.get(class_type)
        if ref is not None:
            refs_by_key[_ref_key(ref)] = ref
        elif class_type in lookup.pack_name_by_class:
            unresolved_pack_names.append(lookup.pack_name_by_class[class_type])
    normalized, _warnings = normalize_custom_node_requirements(requirements)
    for name in normalized.get("custom_nodes") or []:
        if not isinstance(name, str):
            continue
        ref = lookup.refs_by_name.get(name)
        if ref is None:
            unresolved_pack_names.append(name)
            continue
        refs_by_key[_ref_key(ref)] = ref
    for ref in normalized.get("custom_node_refs") or []:
        if isinstance(ref, Mapping):
            ref_dict = dict(ref)
            known_ref = lookup.refs_by_name.get(str(ref_dict.get("slug") or ref_dict.get("name") or ""))
            if known_ref is not None:
                refs_by_key[_ref_key(known_ref)] = known_ref
    refs = [refs_by_key[key] for key in sorted(refs_by_key)]
    return refs, sorted(set(unresolved_pack_names))


def _pack_lookup(lock_entries: list[LockEntry]) -> PackLookup:
    lock_by_name = {entry.name: entry for entry in lock_entries}
    lock_by_slug = {entry.slug: entry for entry in lock_entries if entry.slug}
    refs_by_name: dict[str, dict[str, Any]] = {}
    refs_by_class: dict[str, dict[str, Any]] = {}
    pack_name_by_class: dict[str, str] = {}

    for pack in get_known_node_packs():
        lock_entry = lock_by_name.get(pack.name) or lock_by_slug.get(pack.name)
        ref = (
            lock_entry_to_ref(lock_entry)
            if lock_entry is not None
            else {"slug": pack.name, "source": "git", "url": pack.repo}
        )
        if ref is not None:
            refs_by_name[pack.name] = ref
            if ref.get("slug"):
                refs_by_name[str(ref["slug"])] = ref
        for class_type in pack.classes:
            pack_name_by_class[class_type] = pack.name
            if ref is not None:
                refs_by_class[class_type] = ref

    for entry in lock_entries:
        ref = lock_entry_to_ref(entry)
        refs_by_name[entry.name] = ref
        if entry.slug:
            refs_by_name[entry.slug] = ref
        for class_type in entry.class_set:
            refs_by_class[class_type] = ref
            pack_name_by_class[class_type] = entry.name
    return PackLookup(refs_by_name=refs_by_name, refs_by_class=refs_by_class, pack_name_by_class=pack_name_by_class)


def _extract_node_class_literals(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    classes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        value = _node_class_from_call(node)
        if value:
            classes.add(value)
    return classes


def _node_class_from_call(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute) and node.func.attr == "node":
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return node.args[0].value
        for keyword in node.keywords:
            if keyword.arg == "class_type" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                return keyword.value.value
    if isinstance(node.func, ast.Name) and node.func.id in {"node", "_node"}:
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
            return node.args[1].value
        for keyword in node.keywords:
            if keyword.arg == "class_type" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                return keyword.value.value
    return None


def _extract_requirements(source: str) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    assignments: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = _literal_value(node.value, assignments)
            if isinstance(target, ast.Name) and target.id == "READY_REQUIREMENTS":
                value = assignments.get("READY_REQUIREMENTS")
                return dict(value) if isinstance(value, dict) else None
    return {"models": [], "custom_nodes": []}


def _has_ready_requirements_assignment(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "READY_REQUIREMENTS" for target in node.targets
        ):
            return True
    return False


def _uses_ready_metadata_build(source: str) -> bool:
    return "ReadyMetadata.build(" in source and "READY_METADATA" in source


def _uses_finalize(source: str) -> bool:
    return "return finalize(" in source


def _replace_ready_metadata_requirements(source: str, requirements: Mapping[str, Any]) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "build"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ReadyMetadata"
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg != "requirements":
                continue
            return _replace_ast_node_source(source, keyword.value, _format_requirements(requirements))
    return source


def _strip_top_level_assignment(source: str, name: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.splitlines(keepends=True)
    drop: set[int] = set()
    for stmt in tree.body:
        targets: list[ast.expr] = []
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
        elif isinstance(stmt, ast.AnnAssign):
            targets = [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        end_lineno = stmt.end_lineno or stmt.lineno
        drop.update(range(stmt.lineno, end_lineno + 1))
        if end_lineno < len(lines) and not lines[end_lineno].strip():
            drop.add(end_lineno + 1)
    if not drop:
        return source
    return "".join(line for lineno, line in enumerate(lines, start=1) if lineno not in drop)


def _replace_ast_node_source(source: str, node: ast.AST, replacement: str) -> str:
    if not hasattr(node, "end_lineno") or node.end_lineno is None:
        return source
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    return source[:start] + replacement + source[end:]


def _format_requirements(requirements: Mapping[str, Any]) -> str:
    return pprint.pformat(dict(requirements), sort_dicts=False, width=88)


def _replace_ready_requirements(source: str, requirements: Mapping[str, Any]) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    replacement = "READY_REQUIREMENTS = " + pprint.pformat(dict(requirements), width=100, sort_dicts=False)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "READY_REQUIREMENTS" for target in node.targets):
            continue
        start = _offset(source, node.lineno, node.col_offset)
        end = _offset(source, node.end_lineno or node.lineno, node.end_col_offset or node.col_offset)
        return source[:start] + replacement + source[end:]
    marker = "\n\ndef build("
    insert_at = source.find(marker)
    if insert_at == -1:
        return source
    return source[:insert_at] + "\n\n" + replacement + source[insert_at:]


def _offset(source: str, lineno: int, col: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(line) for line in lines[: lineno - 1]) + col


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_template_index() -> dict[str, dict[str, Any]]:
    path = DEFAULT_OUTPUT
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: row for row in data.get("templates", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}


def _existing_generated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    value = payload.get("generated_at")
    return value if isinstance(value, str) else None


def _ref_key(ref: Mapping[str, Any]) -> str:
    return f"{ref.get('source', '')}:{ref.get('slug', ref.get('name', ''))}"


def _render_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    return (
        f"targets: {summary['target_count']}\n"
        f"updated: {summary['updated']}\n"
        f"unchanged: {summary['unchanged']}\n"
        f"errors: {summary['errors']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
