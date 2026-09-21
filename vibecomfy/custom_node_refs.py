from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from vibecomfy.node_packs import LockEntry
from vibecomfy.workflow import VibeWorkflow


__all__ = [
    "CustomNodeRef",
    "CustomNodeRefConflict",
    "PackPinIssue",
    "check_pack_pin_compatibility",
    "effective_lock_entries",
    "lock_entry_to_ref",
    "normalize_custom_node_requirements",
    "structured_refs_from_lock_entries",
    "workflow_lock_entries",
]


@dataclass(frozen=True)
class PackPinIssue:
    code: str
    message: str
    severity: str
    slug: str
    detail: dict[str, Any]


class CustomNodeRefConflict(ValueError):
    """Two declarations give one custom-node pack incompatible exact facts."""

    def __init__(
        self,
        *,
        selector: str,
        field: str,
        first_value: Any,
        first_location: str,
        second_value: Any,
        second_location: str,
    ) -> None:
        self.selector = selector
        self.field = field
        self.first_value = first_value
        self.first_location = first_location
        self.second_value = second_value
        self.second_location = second_location
        super().__init__(
            f"conflicting exact custom-node ref for {selector!r}: {field} "
            f"{first_value!r} at {first_location} conflicts with "
            f"{second_value!r} at {second_location}"
        )


@dataclass(frozen=True, slots=True)
class CustomNodeRef:
    """Typed view of one canonical custom-node requirement.

    The IR stores the JSON-shaped ``dict`` returned by :meth:`to_dict` for
    compatibility with existing callers.  This small value object gives new
    callers a typed view without introducing a second serialized authority.
    ``extras`` carries schema/source custody fields added by newer producers.
    """

    slug: str
    source: str = "git"
    url: str | None = None
    path: str | None = None
    version: str | None = None
    version_range: str | None = None
    commit: str | None = None
    classes: tuple[str, ...] = ()
    schema_source: Any = None
    source_evidence: Any = None
    extras: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CustomNodeRef":
        classes = raw.get("class_set", raw.get("classes", ()))
        if not isinstance(classes, (list, tuple)):
            classes = ()
        known = {
            "slug", "name", "source", "url", "repository", "repo", "path",
            "version", "version_range", "range", "constraint", "commit", "revision",
            "classes", "class_set", "schema_source", "source_evidence",
        }
        return cls(
            slug=str(raw.get("slug") or raw.get("name") or ""),
            source=str(raw.get("source") or "git"),
            url=raw.get("url") or raw.get("repository") or raw.get("repo"),
            path=raw.get("path"),
            version=raw.get("version"),
            version_range=raw.get("version_range") or raw.get("range") or raw.get("constraint"),
            commit=raw.get("commit") or raw.get("revision"),
            classes=tuple(str(item) for item in classes if isinstance(item, str) and item),
            schema_source=raw.get("schema_source"),
            source_evidence=raw.get("source_evidence"),
            extras=tuple(sorted((str(key), value) for key, value in raw.items() if str(key) not in known)),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"slug": self.slug, "source": self.source}
        for key, value in (
            ("url", self.url), ("path", self.path), ("version", self.version),
            ("version_range", self.version_range), ("commit", self.commit),
            ("schema_source", self.schema_source), ("source_evidence", self.source_evidence),
        ):
            if value is not None:
                result[key] = value
        if self.classes:
            result["class_set"] = list(self.classes)
        result.update(dict(self.extras))
        return result


def normalize_custom_node_requirements(requirements: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    merged = dict(requirements or {})
    warnings: list[str] = []
    custom_nodes: list[str] = []
    custom_node_refs: list[dict[str, Any]] = []
    declarations: list[tuple[Mapping[str, Any], str]] = []
    for index, ref in enumerate(merged.get("custom_node_refs") or []):
        if isinstance(ref, Mapping):
            declarations.append((ref, f"requirements.custom_node_refs[{index}]"))
    for index, item in enumerate(merged.get("custom_nodes") or []):
        if isinstance(item, Mapping):
            declarations.append((item, f"requirements.custom_nodes[{index}]"))
    for ref, location in declarations:
        normalized = _normalize_ref(ref)
        if normalized is not None:
            normalized["_source_location"] = location
            custom_node_refs.append(normalized)
    # Exact identity fields are never merged by first-wins semantics.  URL/path
    # are repository selectors; commit/revision and exact version are identity
    # witnesses.  Range constraints remain compatible declarations and are
    # retained without declaring one range to be the winner.
    _reject_conflicting_exact_refs(custom_node_refs)
    for item in merged.get("custom_nodes") or []:
        if isinstance(item, Mapping):
            normalized = _normalize_ref(item)
            if normalized is None:
                continue
            slug = str(normalized.get("slug") or normalized.get("name"))
            custom_nodes.append(slug)
            warnings.append("requirements.custom_nodes contained a structured custom-node ref; normalized to string slug and mirrored to custom_node_refs")
        elif isinstance(item, str) and item:
            custom_nodes.append(item)
    merged["custom_nodes"] = sorted(set(custom_nodes))
    if custom_node_refs:
        by_key: dict[str, dict[str, Any]] = {}
        for ref in custom_node_refs:
            location = ref.pop("_source_location", None)
            key = _ref_key(ref)
            existing = by_key.get(key)
            by_key[key] = _merge_refs(existing, ref) if existing is not None else ref
            if location and by_key[key] is ref:
                # Location is diagnostic-only and must not affect semantic
                # identity or leak into generated source.
                pass
        merged["custom_node_refs"] = [by_key[key] for key in sorted(by_key)]
    return merged, warnings


def _reject_conflicting_exact_refs(refs: Iterable[dict[str, Any]]) -> None:
    seen: dict[tuple[str, str], tuple[Any, str]] = {}
    for ref in refs:
        selector = _ref_key(ref)
        location = str(ref.get("_source_location") or "requirements.custom_node_refs")
        for field in ("url", "path", "commit", "version"):
            value = ref.get(field)
            if value in (None, ""):
                continue
            key = (selector, field)
            previous = seen.get(key)
            if previous is not None and str(previous[0]) != str(value):
                raise CustomNodeRefConflict(
                    selector=selector,
                    field=field,
                    first_value=previous[0],
                    first_location=previous[1],
                    second_value=value,
                    second_location=location,
                )
            seen[key] = (value, location)


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


def workflow_lock_entries(workflow: VibeWorkflow) -> list[LockEntry]:
    """Return resolved lock records carried by a workflow's requirements.

    These records are intentionally workflow-scoped: a portable Python bundle
    must not need the VibeComfy checkout's global ``custom_nodes.lock`` to
    recover the pins it was authored against.
    """
    refs = _workflow_custom_node_refs(workflow)
    entries: list[LockEntry] = []
    for ref in refs:
        slug = str(ref.get("slug") or ref.get("name") or "").strip()
        if not slug:
            continue
        classes = ref.get("class_set", ref.get("classes", ()))
        entries.append(
            LockEntry(
                name=str(ref.get("name") or slug),
                slug=slug,
                source=str(ref.get("source") or "git"),
                version=ref.get("version"),
                commit=ref.get("commit"),
                git_commit_sha=ref.get("commit"),
                url=ref.get("url"),
                path=ref.get("path"),
                class_set=tuple(classes) if isinstance(classes, (list, tuple)) else (),
                pip_packages=tuple(ref.get("pip_packages") or ()) if isinstance(ref.get("pip_packages"), (list, tuple)) else (),
                source_sha256=dict(ref.get("source_sha256") or {}) if isinstance(ref.get("source_sha256"), Mapping) else {},
                class_schema_sha256=ref.get("class_schema_sha256"),
                schema_hash=ref.get("schema_hash"),
                semantic_label=ref.get("semantic_label"),
                last_seen_at=ref.get("last_seen_at"),
            )
        )
    return entries


def effective_lock_entries(
    workflow: VibeWorkflow, fallback: list[LockEntry] | None = None
) -> list[LockEntry]:
    """Resolve workflow pins, falling back to legacy external locks only when needed.

    A workflow record carrying an identity (commit/version/source URL/path) is
    authoritative and is never replaced by a same-named external entry.
    """
    carried = workflow_lock_entries(workflow)
    if not carried:
        return list(fallback or ())
    fallback_by_key = {entry.slug or entry.name: entry for entry in (fallback or [])}
    result: list[LockEntry] = []
    used_fallback: set[int] = set()
    for entry in carried:
        key = entry.slug or entry.name
        legacy = fallback_by_key.get(key) or fallback_by_key.get(entry.name)
        if legacy is not None and fallback:
            used_fallback.add(next((index for index, item in enumerate(fallback) if item is legacy), -1))
        # URL/path select a source but do not identify its contents.  They may
        # therefore still be enriched by a legacy lock; commit/version pins
        # are the authoritative workflow identity.
        has_identity = any((entry.commit, entry.version))
        if legacy is not None and not has_identity:
            result.append(legacy)
        else:
            result.append(entry)
    # Mixed workflows may still rely on unrelated legacy packs. Keep those
    # witnesses available; carried pins only supersede their own selector.
    result.extend(entry for index, entry in enumerate(fallback or ()) if index not in used_fallback)
    return result


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
    if entry.pip_packages:
        ref["pip_packages"] = list(entry.pip_packages)
    if entry.source_sha256:
        ref["source_sha256"] = dict(entry.source_sha256)
    if entry.class_schema_sha256 is not None:
        ref["class_schema_sha256"] = entry.class_schema_sha256
    if entry.schema_hash is not None:
        ref["schema_hash"] = entry.schema_hash
    if entry.semantic_label is not None:
        ref["semantic_label"] = entry.semantic_label
    if entry.last_seen_at is not None:
        ref["last_seen_at"] = entry.last_seen_at
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
    admit = getattr(workflow, "_admit_legacy_custom_node_refs_once", None)
    if callable(admit):
        admit()
    typed_requirements = getattr(getattr(workflow, "requirements", None), "custom_node_refs", None)
    if isinstance(typed_requirements, (list, tuple)):
        return [dict(ref) for ref in typed_requirements if isinstance(ref, Mapping)]
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
    for key in (
        "name", "version", "version_range", "range", "constraint", "commit",
        "revision", "path", "repository", "repo", "class_schema_sha256",
        "schema_hash", "semantic_label", "last_seen_at", "schema_source",
        "source_evidence",
    ):
        value = ref.get(key)
        if isinstance(value, str) and value:
            normalized[key] = value
        elif key in {"schema_source", "source_evidence"} and isinstance(value, Mapping):
            normalized[key] = dict(value)
    # Empty URL is meaningful: it is the unresolved, user-editable repository
    # placeholder.  Do not turn it into an absent field or invent a provider.
    if "url" in ref and isinstance(ref.get("url"), str):
        normalized["url"] = ref["url"]
    elif any(key in ref for key in ("repository", "repo")):
        repository = ref.get("repository", ref.get("repo"))
        if isinstance(repository, str):
            normalized["url"] = repository
    for key in ("classes", "class_set"):
        if key not in ref:
            continue
        value = ref.get(key)
        if not isinstance(value, (list, tuple)):
            continue
        values = sorted({item for item in value if isinstance(item, str) and item})
        if values:
            normalized[key] = values
    if isinstance(ref.get("pip_packages"), (list, tuple)):
        normalized["pip_packages"] = sorted({str(item) for item in ref["pip_packages"] if isinstance(item, str) and item})
    if isinstance(ref.get("source_sha256"), Mapping):
        normalized["source_sha256"] = {
            str(key): str(value) for key, value in ref["source_sha256"].items()
            if isinstance(key, str) and isinstance(value, str) and value
        }
    # Keep future evidence fields that are JSON-shaped instead of dropping
    # them at the normalization boundary.  Internal diagnostic keys remain
    # private and are intentionally excluded.
    known = {
        "slug", "name", "source", "url", "version", "version_range", "range",
        "constraint", "commit", "revision", "path", "repository", "repo",
        "classes", "class_set", "pip_packages", "source_sha256",
        "class_schema_sha256", "schema_hash", "semantic_label", "last_seen_at",
        "schema_source", "source_evidence",
    }
    for key, value in ref.items():
        if key in known or str(key).startswith("_"):
            continue
        if isinstance(value, (str, int, float, bool, type(None), list, tuple, Mapping)):
            normalized[str(key)] = value
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
