from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from vibecomfy.node_packs import LockEntry
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class PackPinIssue:
    code: str
    message: str
    severity: str
    slug: str
    detail: dict[str, Any]


def normalize_custom_node_requirements(requirements: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    merged = dict(requirements or {})
    warnings: list[str] = []
    custom_nodes: list[str] = []
    custom_node_refs: list[dict[str, Any]] = []
    for ref in merged.get("custom_node_refs") or []:
        if isinstance(ref, Mapping):
            normalized = _normalize_ref(ref)
            if normalized is not None:
                custom_node_refs.append(normalized)
    for item in merged.get("custom_nodes") or []:
        if isinstance(item, Mapping):
            normalized = _normalize_ref(item)
            if normalized is None:
                continue
            custom_node_refs.append(normalized)
            slug = str(normalized.get("slug") or normalized.get("name"))
            custom_nodes.append(slug)
            warnings.append("requirements.custom_nodes contained a structured custom-node ref; normalized to string slug and mirrored to custom_node_refs")
        elif isinstance(item, str) and item:
            custom_nodes.append(item)
    merged["custom_nodes"] = sorted(set(custom_nodes))
    if custom_node_refs:
        by_key: dict[str, dict[str, Any]] = {}
        for ref in custom_node_refs:
            key = _ref_key(ref)
            existing = by_key.get(key)
            by_key[key] = _merge_refs(existing, ref) if existing is not None else ref
        merged["custom_node_refs"] = [by_key[key] for key in sorted(by_key)]
    return merged, warnings


def structured_refs_from_lock_entries(names: list[str], entries: list[LockEntry]) -> list[dict[str, Any]]:
    by_name: dict[str, LockEntry] = {}
    by_slug: dict[str, LockEntry] = {}
    for entry in entries:
        by_name[entry.name] = entry
        if entry.slug:
            by_slug[entry.slug] = entry
    refs: list[dict[str, Any]] = []
    for name in names:
        entry = by_name.get(name) or by_slug.get(name)
        if entry is not None:
            refs.append(lock_entry_to_ref(entry))
    return refs


def lock_entry_to_ref(entry: LockEntry) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "slug": entry.slug or entry.name,
        "source": entry.source,
    }
    if entry.version is not None:
        ref["version"] = entry.version
    if entry.commit is not None:
        ref["commit"] = entry.commit
    if entry.url is not None:
        ref["url"] = entry.url
    if entry.path is not None:
        ref["path"] = entry.path
    if entry.class_set:
        ref["class_set"] = list(entry.class_set)
    if entry.name and entry.name != ref["slug"]:
        ref["name"] = entry.name
    return ref


def check_pack_pin_compatibility(workflow: VibeWorkflow, lock_entries: list[LockEntry]) -> list[PackPinIssue]:
    refs = _workflow_custom_node_refs(workflow)
    if not refs:
        if workflow.requirements.custom_nodes:
            return [
                PackPinIssue(
                    code="legacy_custom_nodes_unpinned",
                    message="Workflow declares custom_nodes without structured custom_node_refs; pack pins cannot be verified.",
                    severity="warning",
                    slug=",".join(sorted(workflow.requirements.custom_nodes)),
                    detail={"custom_nodes": sorted(workflow.requirements.custom_nodes)},
                )
            ]
        return []
    entries_by_slug: dict[str, LockEntry] = {}
    entries_by_name: dict[str, LockEntry] = {}
    for entry in lock_entries:
        entries_by_name[entry.name] = entry
        if entry.slug:
            entries_by_slug[entry.slug] = entry
    issues: list[PackPinIssue] = []
    for ref in refs:
        slug = str(ref.get("slug") or ref.get("name") or "")
        name = str(ref.get("name") or "")
        entry = entries_by_slug.get(slug) or entries_by_name.get(name) or entries_by_name.get(slug)
        if entry is None:
            severity = "error" if ref.get("version") or ref.get("commit") else "warning"
            issues.append(
                PackPinIssue(
                    code="custom_node_ref_missing_from_lock",
                    message=f"Custom-node pack {slug!r} is declared by workflow but missing from custom_nodes.lock.",
                    severity=severity,
                    slug=slug,
                    detail={"ref": dict(ref)},
                )
            )
            continue
        for field in ("version", "commit"):
            expected = ref.get(field)
            actual = getattr(entry, field, None)
            if expected and actual and str(expected) != str(actual):
                issues.append(
                    PackPinIssue(
                        code="custom_node_ref_pin_conflict",
                        message=f"Custom-node pack {slug!r} {field} {expected!r} does not match installed lock {actual!r}.",
                        severity="error",
                        slug=slug,
                        detail={"field": field, "expected": expected, "actual": actual, "ref": dict(ref)},
                    )
                )
    return issues


def _workflow_custom_node_refs(workflow: VibeWorkflow) -> list[dict[str, Any]]:
    requirements = workflow.metadata.get("requirements")
    if not isinstance(requirements, Mapping):
        return []
    refs = requirements.get("custom_node_refs")
    if not isinstance(refs, list):
        return []
    return [dict(ref) for ref in refs if isinstance(ref, Mapping)]


def _normalize_ref(ref: Mapping[str, Any]) -> dict[str, Any] | None:
    slug = ref.get("slug") or ref.get("name")
    source = ref.get("source")
    if not isinstance(slug, str) or not slug:
        return None
    if not isinstance(source, str) or not source:
        source = "git" if "url" in ref else "local" if ref.get("path") else "comfy-registry"
    normalized: dict[str, Any] = {"slug": slug, "source": source}
    for key in ("name", "version", "commit", "path"):
        value = ref.get(key)
        if isinstance(value, str) and value:
            normalized[key] = value
    # Empty URL is meaningful: it is the unresolved, user-editable repository
    # placeholder.  Do not turn it into an absent field or invent a provider.
    if "url" in ref and isinstance(ref.get("url"), str):
        normalized["url"] = ref["url"]
    for key in ("classes", "class_set"):
        if key not in ref:
            continue
        value = ref.get(key)
        if not isinstance(value, (list, tuple)):
            continue
        values = sorted({item for item in value if isinstance(item, str) and item})
        if values:
            normalized[key] = values
    return normalized


def _merge_refs(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Merge duplicate refs without losing unresolved URL/class evidence."""
    merged = dict(left)
    for key, value in right.items():
        if key in {"classes", "class_set"}:
            values = set(merged.get(key) or ()) | set(value or ())
            if values:
                merged[key] = sorted(str(item) for item in values)
        elif key == "url" and "url" in merged:
            # A filled URL wins over an empty placeholder; two different
            # non-empty values remain deterministic and visibly conflicted.
            if not merged[key] and value:
                merged[key] = value
        else:
            merged.setdefault(key, value)
    return merged


def _ref_key(ref: Mapping[str, Any]) -> str:
    return f"{ref.get('source', '')}:{ref.get('slug', ref.get('name', ''))}"
