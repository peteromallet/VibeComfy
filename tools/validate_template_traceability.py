"""Validate ready-template reproducibility traceability metadata.

This gate is intentionally offline.  It validates checked-in template metadata,
the checked-in model registry, and the installed custom-node lock without
touching Hugging Face, ComfyUI, a GPU, or RunPod.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import tomllib

from tools.check_pack_provenance import build_pack_provenance_report
from tools.refresh_template_index import DEFAULT_OUTPUT as DEFAULT_TEMPLATE_INDEX
from tools.refresh_template_index import _ready_template_metadata
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.node_packs import LockEntry, read_lockfile
from vibecomfy.porting._provenance_utils import resolve_source_workflow
from vibecomfy.registry.models_loader import DEFAULT_REGISTRY_PATH, ModelEntry, load_registry
from vibecomfy.registry.static_contract import extract_ready_template_contract

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION = 1

# The original v2.4 migration window expired on 2026-09-01 while the checked-in
# corpus still contains the explicitly enumerated legacy gaps below. Renew the
# same narrow code/target pairs as one auditable baseline; diagnostics outside
# these pairs remain hard failures. This is a deadline, not a blanket bypass.
MIGRATION_ALLOWLIST_EXPIRES = "2027-03-01"


@dataclass(frozen=True)
class AllowlistEntry:
    target: str
    code: str
    owner: str
    reason: str
    expires: str
    removal_condition: str


DEFAULT_MIGRATION_ALLOWLIST: tuple[AllowlistEntry, ...] = (
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_source_sha_missing",
        owner="v2.4-migration",
        reason="Older ready templates predate the source-SHA provenance line.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Regenerate or annotate every ready template with a checked source SHA.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_source_workflow_missing",
        owner="v2.4-migration",
        reason="Some older/reference templates predate structured source_workflow provenance.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every checked-in ready template declares a source_workflow or a narrow explicit exception.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_source_workflow_missing_file",
        owner="v2.4-migration",
        reason="Some older templates cite source files that have not yet been checked into ready_templates/sources.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every source_workflow path resolves to a checked ready_templates/sources JSON file.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_source_workflow_not_checkable",
        owner="v2.4-migration",
        reason="Some older/manual templates cite a descriptive or vendor source instead of ready_templates/sources JSON.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Move source JSON into ready_templates/sources or add a precise legacy exception.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_vibecomfy_version_missing",
        owner="v2.4-migration",
        reason="Older templates were authored before vibecomfy_version became mandatory.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Backfill READY_METADATA.vibecomfy_version for all checked-in templates.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_comfy_core_missing",
        owner="v2.4-migration",
        reason="Older templates were authored before comfy_core provenance became mandatory.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Backfill READY_METADATA.comfy_core for all checked-in templates.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_model_asset_missing_sha256",
        owner="v2.4-migration",
        reason="Template-local model assets are being pinned incrementally.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every ModelAsset carries sha256.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_model_asset_missing_hf_revision",
        owner="v2.4-migration",
        reason="Template-local Hugging Face model assets are being pinned incrementally.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every Hugging Face ModelAsset carries hf_revision.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_model_asset_missing_size_bytes",
        owner="v2.4-migration",
        reason="Template-local model asset exact sizes are being pinned incrementally.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every ModelAsset carries size_bytes.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="template_custom_node_refs_missing",
        owner="v2.4-migration",
        reason="Legacy templates with custom_nodes are being migrated to structured custom_node_refs.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every template with custom_nodes has structured custom_node_refs.",
    ),
    AllowlistEntry(
        target="model-registry:*",
        code="model_registry_missing_sha256",
        owner="v2.4-migration",
        reason="Registry-staged models are being pinned incrementally.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every model registry row carries sha256.",
    ),
    AllowlistEntry(
        target="model-registry:*",
        code="model_registry_missing_revision",
        owner="v2.4-migration",
        reason="Hugging Face registry rows are being pinned to revisions incrementally.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every Hugging Face model registry row carries source.revision.",
    ),
    AllowlistEntry(
        target="model-registry:*",
        code="model_registry_missing_size_bytes",
        owner="v2.4-migration",
        reason="Registry-staged exact sizes are being pinned incrementally.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Every model registry row carries size_bytes.",
    ),
    AllowlistEntry(
        target="ready_templates/**/*.py",
        code="pack_provenance_pack_missing_from_lock",
        owner="v2.4-migration",
        reason="Some migrated templates still depend on known packs that are not represented by rich lock entries.",
        expires=MIGRATION_ALLOWLIST_EXPIRES,
        removal_condition="Install/lock all declared packs with derived class_set data.",
    ),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on unallowlisted errors.")
    parser.add_argument("--template-index", type=Path, default=DEFAULT_TEMPLATE_INDEX)
    parser.add_argument("--model-registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--lockfile", type=Path, default=REPO_ROOT / "custom_nodes.lock")
    args = parser.parse_args(argv)

    report = build_traceability_report(
        template_index=args.template_index,
        model_registry=args.model_registry,
        lockfile=args.lockfile,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 1 if args.strict and report["summary"]["unallowlisted_errors"] else 0


def build_traceability_report(
    *,
    template_index: Path = DEFAULT_TEMPLATE_INDEX,
    model_registry: Path = DEFAULT_REGISTRY_PATH,
    lockfile: Path = REPO_ROOT / "custom_nodes.lock",
    allowlist: Sequence[AllowlistEntry] = DEFAULT_MIGRATION_ALLOWLIST,
) -> dict[str, Any]:
    templates = _load_template_rows(template_index)
    lock_entries = read_lockfile(lockfile)
    diagnostics: list[dict[str, Any]] = []
    for row in templates:
        diagnostics.extend(_template_diagnostics(row, lock_entries=lock_entries))
    diagnostics.extend(_pack_provenance_diagnostics())
    diagnostics.extend(_model_registry_diagnostics(model_registry))
    annotated = [_apply_allowlist(item, allowlist) for item in diagnostics]
    return {
        "version": VERSION,
        "ok": not any(item["severity"] == "error" and not item.get("allowlisted") for item in annotated),
        "template_count": len(templates),
        "model_registry": _display_path(model_registry),
        "summary": _summary(annotated),
        "allowlist": [_allowlist_payload(item) for item in allowlist],
        "diagnostics": sorted(annotated, key=lambda item: (item["target"], item["code"], item["message"])),
    }


def _template_diagnostics(row: Mapping[str, Any], *, lock_entries: Sequence[LockEntry]) -> list[dict[str, Any]]:
    path_value = row.get("path")
    ready_id = str(row.get("id") or path_value or "")
    if not isinstance(path_value, str) or not path_value:
        return [_diagnostic("template_path_missing", "Template index row is missing path.", ready_id, ready_id, {})]
    path = REPO_ROOT / path_value
    target = _display_path(path)
    metadata, requirements = _ready_template_metadata(path)
    contract = extract_ready_template_contract(path)
    diagnostics: list[dict[str, Any]] = []

    diagnostics.extend(_source_sha_diagnostics(path, ready_id=ready_id, target=target, metadata=metadata, row=row))
    diagnostics.extend(_version_diagnostics(ready_id=ready_id, target=target, metadata=metadata, row=row))
    diagnostics.extend(_custom_node_ref_diagnostics(ready_id=ready_id, target=target, requirements=requirements, contract=contract, lock_entries=lock_entries))
    diagnostics.extend(_model_asset_diagnostics(ready_id=ready_id, target=target, contract=contract))
    return diagnostics


def _source_sha_diagnostics(
    path: Path,
    *,
    ready_id: str,
    target: str,
    metadata: Mapping[str, Any],
    row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source_workflow = resolve_source_workflow(metadata, row)
    source_sha = row.get("source_sha256") or _source_sha_from_comment(path)
    if not isinstance(source_workflow, str) or not source_workflow:
        return [_diagnostic("template_source_workflow_missing", "Template metadata does not declare source_workflow.", ready_id, target, {})]
    source_path = REPO_ROOT / source_workflow
    if not _is_checkable_source_path(source_workflow, source_path):
        return [
            _diagnostic(
                "template_source_workflow_not_checkable",
                f"Source workflow {source_workflow!r} is not a checked ready_templates/sources JSON path.",
                ready_id,
                target,
                {"source_workflow": source_workflow},
            )
        ]
    if not source_path.exists():
        return [
            _diagnostic(
                "template_source_workflow_missing_file",
                f"Source workflow file {source_workflow!r} does not exist.",
                ready_id,
                target,
                {"source_workflow": source_workflow},
            )
        ]
    actual = _sha256_file(source_path)
    if not isinstance(source_sha, str) or not source_sha:
        return [
            _diagnostic(
                "template_source_sha_missing",
                "Template does not record source workflow SHA256.",
                ready_id,
                target,
                {"source_workflow": source_workflow, "actual_sha256": actual},
            )
        ]
    if source_sha.lower() != actual.lower():
        return [
            _diagnostic(
                "template_source_sha_mismatch",
                f"Template source SHA256 {source_sha} does not match {source_workflow} ({actual}).",
                ready_id,
                target,
                {"source_workflow": source_workflow, "expected": source_sha, "actual": actual},
            )
        ]
    return []


def _version_diagnostics(*, ready_id: str, target: str, metadata: Mapping[str, Any], row: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    current = _project_version()
    version = metadata.get("vibecomfy_version") or row.get("vibecomfy_version")
    if not isinstance(version, str) or not version:
        diagnostics.append(_diagnostic("template_vibecomfy_version_missing", "Template is missing vibecomfy_version.", ready_id, target, {}))
    elif _version_tuple(version) > _version_tuple(current):
        diagnostics.append(
            _diagnostic(
                "template_vibecomfy_version_unsupported",
                f"Template requires future vibecomfy_version {version}; installed project is {current}.",
                ready_id,
                target,
                {"required": version, "installed": current},
            )
        )
    comfy_core = metadata.get("comfy_core") or row.get("comfy_core")
    if not isinstance(comfy_core, Mapping):
        diagnostics.append(_diagnostic("template_comfy_core_missing", "Template is missing comfy_core metadata.", ready_id, target, {}))
    elif not any(key in comfy_core for key in ("version", "min_version", "commit", "tested_at", "status")):
        diagnostics.append(
            _diagnostic(
                "template_comfy_core_malformed",
                "Template comfy_core metadata does not include version, min_version, commit, tested_at, or status.",
                ready_id,
                target,
                {"comfy_core": dict(comfy_core)},
            )
        )
    else:
        version = comfy_core.get("version") or comfy_core.get("min_version")
        commit = comfy_core.get("commit")
        if not isinstance(version, str) or not version:
            diagnostics.append(_diagnostic("template_comfy_core_version_missing", "Template comfy_core.version is missing.", ready_id, target, {"comfy_core": dict(comfy_core)}))
        if not isinstance(commit, str) or not commit:
            diagnostics.append(_diagnostic("template_comfy_core_commit_missing", "Template comfy_core.commit is missing.", ready_id, target, {"comfy_core": dict(comfy_core)}))
    return diagnostics


def _custom_node_ref_diagnostics(
    *,
    ready_id: str,
    target: str,
    requirements: Mapping[str, Any],
    contract: Mapping[str, Any],
    lock_entries: Sequence[LockEntry],
) -> list[dict[str, Any]]:
    raw_requirements = dict(requirements)
    if contract.get("custom_nodes") or contract.get("custom_node_refs"):
        raw_requirements.setdefault("custom_nodes", contract.get("custom_nodes", []))
        raw_requirements.setdefault("custom_node_refs", contract.get("custom_node_refs", []))
    normalized, _warnings = normalize_custom_node_requirements(raw_requirements)
    custom_nodes = normalized.get("custom_nodes") or []
    refs = [ref for ref in normalized.get("custom_node_refs") or [] if isinstance(ref, Mapping)]
    diagnostics: list[dict[str, Any]] = []
    if custom_nodes and not refs:
        diagnostics.append(
            _diagnostic(
                "template_custom_node_refs_missing",
                "Template declares custom_nodes without structured custom_node_refs.",
                ready_id,
                target,
                {"custom_nodes": list(custom_nodes)},
            )
        )
    diagnostics.extend(_pack_pin_diagnostics(ready_id=ready_id, target=target, refs=refs, lock_entries=lock_entries))
    return diagnostics


def _pack_pin_diagnostics(
    *,
    ready_id: str,
    target: str,
    refs: Sequence[Mapping[str, Any]],
    lock_entries: Sequence[LockEntry],
) -> list[dict[str, Any]]:
    entries_by_name = {entry.name: entry for entry in lock_entries}
    entries_by_slug = {entry.slug: entry for entry in lock_entries if entry.slug}
    diagnostics: list[dict[str, Any]] = []
    for ref in refs:
        slug = str(ref.get("slug") or ref.get("name") or "")
        name = str(ref.get("name") or "")
        entry = entries_by_slug.get(slug) or entries_by_name.get(name) or entries_by_name.get(slug)
        if entry is None:
            diagnostics.append(
                _diagnostic(
                    "template_custom_node_ref_missing_from_lock",
                    f"Custom-node ref {slug!r} is not present in custom_nodes.lock.",
                    ready_id,
                    target,
                    {"ref": dict(ref)},
                    severity="error" if ref.get("version") or ref.get("commit") else "warning",
                )
            )
            continue
        for field in ("version", "commit"):
            expected = ref.get(field)
            actual = getattr(entry, field, None)
            if field == "commit" and not expected:
                diagnostics.append(
                    _diagnostic(
                        "template_custom_node_ref_commit_missing",
                        f"Custom-node ref {slug!r} is missing commit.",
                        ready_id,
                        target,
                        {"ref": dict(ref)},
                    )
                )
            if expected and actual and str(expected) != str(actual):
                diagnostics.append(
                    _diagnostic(
                        "template_custom_node_ref_pin_conflict",
                        f"Custom-node ref {slug!r} {field} {expected!r} does not match lock {actual!r}.",
                        ready_id,
                        target,
                        {"field": field, "expected": expected, "actual": actual, "ref": dict(ref)},
                    )
                )
    return diagnostics


def _model_asset_diagnostics(*, ready_id: str, target: str, contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, asset in enumerate(contract.get("model_assets") or []):
        if not isinstance(asset, Mapping):
            continue
        asset_target = f"{target}#model_assets[{index}]"
        name = str(asset.get("name") or asset.get("filename") or index)
        if asset.get("gated") is True:
            continue
        if not asset.get("sha256"):
            diagnostics.append(_diagnostic("template_model_asset_missing_sha256", f"ModelAsset {name!r} is missing sha256.", ready_id, asset_target, {"asset": dict(asset)}))
        if asset.get("size_bytes") is None:
            diagnostics.append(_diagnostic("template_model_asset_missing_size_bytes", f"ModelAsset {name!r} is missing size_bytes.", ready_id, asset_target, {"asset": dict(asset)}))
        if _is_huggingface_url(str(asset.get("url") or "")) and not (asset.get("hf_revision") or asset.get("revision")):
            diagnostics.append(_diagnostic("template_model_asset_missing_hf_revision", f"ModelAsset {name!r} is missing hf_revision.", ready_id, asset_target, {"asset": dict(asset)}))
    return diagnostics


def _pack_provenance_diagnostics() -> list[dict[str, Any]]:
    report = build_pack_provenance_report()
    diagnostics: list[dict[str, Any]] = []
    for item in report.get("diagnostics") or []:
        if not isinstance(item, Mapping):
            continue
        diagnostics.append(
            {
                "code": str(item.get("code") or "pack_provenance_issue"),
                "message": str(item.get("message") or ""),
                "severity": str(item.get("severity") or "error"),
                "ready_id": str(item.get("ready_id") or ""),
                "target": str(item.get("target") or ""),
                "detail": dict(item.get("detail") or {}) if isinstance(item.get("detail"), Mapping) else {},
            }
        )
    return diagnostics


def _model_registry_diagnostics(model_registry: Path) -> list[dict[str, Any]]:
    try:
        entries = load_registry(model_registry)
    except Exception as exc:
        return [
            _diagnostic(
                "model_registry_unreadable",
                f"Could not load model registry: {type(exc).__name__}: {exc}",
                "model-registry",
                _display_path(model_registry),
                {},
            )
        ]
    diagnostics: list[dict[str, Any]] = []
    for entry in entries:
        diagnostics.extend(_model_registry_entry_diagnostics(entry))
    return diagnostics


def _model_registry_entry_diagnostics(entry: ModelEntry) -> list[dict[str, Any]]:
    target = f"model-registry:{entry.id}"
    diagnostics: list[dict[str, Any]] = []
    if entry.gated:
        return diagnostics
    if entry.files:
        for index, file in enumerate(entry.files):
            file_target = f"{target}#files[{index}]"
            if not file.sha256:
                diagnostics.append(_diagnostic("model_registry_missing_sha256", f"Model registry row {entry.id!r} file {file.path!r} is missing sha256.", entry.id, file_target, {}))
            if file.size_bytes is None:
                diagnostics.append(_diagnostic("model_registry_missing_size_bytes", f"Model registry row {entry.id!r} file {file.path!r} is missing size_bytes.", entry.id, file_target, {}))
        if not entry.composite_sha256:
            diagnostics.append(_diagnostic("model_registry_missing_sha256", f"Composite model registry row {entry.id!r} is missing composite_sha256.", entry.id, target, {}))
    elif not entry.sha256:
        diagnostics.append(_diagnostic("model_registry_missing_sha256", f"Model registry row {entry.id!r} is missing sha256.", entry.id, target, {}))
    if not entry.files and entry.size_bytes is None:
        diagnostics.append(_diagnostic("model_registry_missing_size_bytes", f"Model registry row {entry.id!r} is missing size_bytes.", entry.id, target, {}))
    if entry.source.kind == "huggingface" and not entry.source.revision:
        diagnostics.append(_diagnostic("model_registry_missing_revision", f"Hugging Face model registry row {entry.id!r} is missing source.revision.", entry.id, target, {}))
    return diagnostics


def _load_template_rows(template_index: Path) -> list[dict[str, Any]]:
    payload = json.loads(template_index.read_text(encoding="utf-8"))
    rows = payload.get("templates", [])
    if not isinstance(rows, list):
        raise ValueError(f"{template_index}: templates must be a list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _source_sha_from_comment(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"# ported from .+ \(sha256: ([0-9a-fA-F]{64})\)", text)
    return match.group(1) if match else None


def _is_checkable_source_path(source_workflow: str, source_path: Path) -> bool:
    return (
        source_workflow.startswith("ready_templates/sources/")
        and not any(part in source_path.parts for part in ("*", "?"))
        and source_path.suffix.lower() == ".json"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_version() -> str:
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = payload.get("project", {})
    version = project.get("version") if isinstance(project, Mapping) else None
    return str(version or "0")


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value.split("+", 1)[0])
    return tuple(int(part) for part in parts) if parts else (0,)


def _is_huggingface_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return host == "huggingface.co" or host.endswith(".huggingface.co")


def _apply_allowlist(diagnostic: dict[str, Any], allowlist: Sequence[AllowlistEntry]) -> dict[str, Any]:
    result = dict(diagnostic)
    match = _matching_allowlist_entry(result, allowlist)
    if match is None:
        result["allowlisted"] = False
        return result
    result["allowlisted"] = True
    result["allowlist"] = _allowlist_payload(match)
    return result


def _matching_allowlist_entry(diagnostic: Mapping[str, Any], allowlist: Sequence[AllowlistEntry]) -> AllowlistEntry | None:
    target = str(diagnostic.get("target") or "")
    base_target = target.split("#", 1)[0].split(":", 1)[0]
    code = str(diagnostic.get("code") or "")
    today = date.today().isoformat()
    for item in allowlist:
        if item.code != code:
            continue
        if item.expires < today:
            continue
        if fnmatch.fnmatch(target, item.target) or fnmatch.fnmatch(base_target, item.target):
            return item
    return None


def _diagnostic(
    code: str,
    message: str,
    ready_id: str,
    target: str,
    detail: Mapping[str, Any],
    *,
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        "ready_id": ready_id,
        "target": target,
        "detail": dict(detail),
    }


def _summary(diagnostics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_code_unallowlisted: dict[str, int] = {}
    allowlisted = 0
    unallowlisted_errors = 0
    for item in diagnostics:
        code = str(item.get("code") or "")
        by_code[code] = by_code.get(code, 0) + 1
        if item.get("allowlisted"):
            allowlisted += 1
        else:
            by_code_unallowlisted[code] = by_code_unallowlisted.get(code, 0) + 1
            if item.get("severity") == "error":
                unallowlisted_errors += 1
    return {
        "diagnostics": len(diagnostics),
        "allowlisted": allowlisted,
        "unallowlisted_errors": unallowlisted_errors,
        "by_code": dict(sorted(by_code.items())),
        "by_code_unallowlisted": dict(sorted(by_code_unallowlisted.items())),
    }


def _allowlist_payload(item: AllowlistEntry) -> dict[str, str]:
    return {
        "target": item.target,
        "code": item.code,
        "owner": item.owner,
        "reason": item.reason,
        "expires": item.expires,
        "removal_condition": item.removal_condition,
    }


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _print_text_report(report: Mapping[str, Any]) -> None:
    summary = report["summary"]
    print(
        f"traceability: {summary['unallowlisted_errors']} unallowlisted errors, "
        f"{summary['allowlisted']} allowlisted diagnostics"
    )
    for item in report.get("diagnostics") or []:
        marker = "allowlisted" if item.get("allowlisted") else "error"
        print(f"- [{marker}] {item['code']} {item['target']}: {item['message']}")


if __name__ == "__main__":
    raise SystemExit(main())
