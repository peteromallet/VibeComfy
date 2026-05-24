"""Repo-only readiness inventory scanner for checked-in ready templates.

Walks only ``ready_templates/**/*.py`` with the same include/exclude rules as
``tools/refresh_template_index.py``.  Never calls ``ready_template_ids()`` —
the inventory is a static, deterministic artifact that must not depend on
runtime plugin/cwd/user-global paths.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.registry.ready import repo_ready_template_id_for_path, repo_ready_template_paths

REPO_ROOT = Path(__file__).resolve().parents[2]
READY_ROOT = REPO_ROOT / "ready_templates"
COVERAGE_PATH = REPO_ROOT / "workflow_corpus" / "manifests" / "coverage.json"
TEMPLATE_INDEX_PATH = REPO_ROOT / "template_index.json"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReadabilityCounts:
    """Per-template readability issue counts."""

    positional_outs: int = 0
    widget_n_fields: int = 0
    uuid_class_types: int = 0
    n_uuid_variables: int = 0
    local_node_copies: int = 0
    missing_output_contract: bool = False


@dataclass
class TemplateInventoryEntry:
    """One row in the inventory report."""

    ready_id: str
    path: str
    marker: str  # "generated", "manual", "reference", "authored", "unknown"
    coverage_tier: str  # from coverage.json or READY_METADATA
    capability: str
    source_role: str | None = None
    source_workflow: str | None = None
    app_active: bool = False  # coverage_tier == "required" + source_role presence
    counts: ReadabilityCounts = field(default_factory=ReadabilityCounts)
    missing_source_provenance: bool = True


@dataclass
class ReadabilityInventory:
    """Top-level inventory report."""

    version: int = 1
    generated_from: str = "repo-only ready_templates/**/*.py glob"
    include_rule: str = "find ready_templates -type f -name '*.py' ! -name '_*' ! -name '__init__.py' | sort"
    exclude_rule: str = "exclude __init__.py and files whose basename starts with '_'"
    template_count: int = 0
    entries: list[TemplateInventoryEntry] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_from": self.generated_from,
            "include_rule": self.include_rule,
            "exclude_rule": self.exclude_rule,
            "template_count": self.template_count,
            "entries": [
                {
                    "ready_id": e.ready_id,
                    "path": e.path,
                    "marker": e.marker,
                    "coverage_tier": e.coverage_tier,
                    "capability": e.capability,
                    "source_role": e.source_role,
                    "source_workflow": e.source_workflow,
                    "app_active": e.app_active,
                    "counts": {
                        "positional_outs": e.counts.positional_outs,
                        "widget_n_fields": e.counts.widget_n_fields,
                        "uuid_class_types": e.counts.uuid_class_types,
                        "n_uuid_variables": e.counts.n_uuid_variables,
                        "local_node_copies": e.counts.local_node_copies,
                        "missing_output_contract": e.counts.missing_output_contract,
                    },
                    "missing_source_provenance": e.missing_source_provenance,
                }
                for e in self.entries
            ],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Enumeration — same filter as tools/refresh_template_index.py:70
# ---------------------------------------------------------------------------


def _enumerate_repo_templates() -> list[Path]:
    """Return checked-in ready-template paths, sorted.

    Same include/exclude rule as ``tools/refresh_template_index.py`` line 70:
    ``find ready_templates -type f -name '*.py' ! -name '_*' | sort``
    plus explicit ``__init__.py`` exclusion.
    """
    return repo_ready_template_paths(READY_ROOT)


def _ready_id_for_path(path: Path) -> str:
    return repo_ready_template_id_for_path(path, READY_ROOT)


# ---------------------------------------------------------------------------
# Static metadata extraction (AST, no imports)
# ---------------------------------------------------------------------------


_KNOWN_TOP_LEVEL_NAMES_RI = frozenset({
    "READY_METADATA",
    "READY_REQUIREMENTS",
    "PUBLIC_INPUTS",
    "MODELS",
    "OUTPUT_PREFIX",
    "PRIVATE_KNOBS",
})


def _parse_ready_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse READY_METADATA and READY_REQUIREMENTS from a template file.

    Handles both literal dict assignments and ``ReadyMetadata.build(...)``
    call expressions.  When requirements are embedded in the
    ``ReadyMetadata.build`` call, they are merged into the requirements dict.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return {}, {}
    assignments: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in _KNOWN_TOP_LEVEL_NAMES_RI:
                continue
            assignments[target.id] = _literal_value(node.value, assignments)
    metadata = assignments.get("READY_METADATA")
    requirements = assignments.get("READY_REQUIREMENTS")

    # If READY_METADATA was built via ReadyMetadata.build(...), extract
    # requirements from within it.
    meta_reqs = None
    if isinstance(metadata, dict) and metadata.get("requirements"):
        meta_reqs = metadata["requirements"]
    if meta_reqs is not None and isinstance(meta_reqs, dict):
        if isinstance(requirements, dict):
            merged = dict(meta_reqs)
            merged.update(requirements)
            requirements = merged
        else:
            requirements = dict(meta_reqs)

    if isinstance(metadata, dict):
        try:
            from vibecomfy.registry.static_contract import _metadata_with_static_derivations

            metadata = _metadata_with_static_derivations(
                metadata,
                path,
                path.read_text(encoding="utf-8"),
            )
        except Exception:
            pass
    return (
        metadata if isinstance(metadata, dict) else {},
        requirements if isinstance(requirements, dict) else {},
    )


def _literal_value(node: ast.AST, assignments: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_literal_value(item, assignments) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_value(item, assignments) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _literal_value(key, assignments): _literal_value(value, assignments)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.Name):
        return assignments.get(node.id)
    if isinstance(node, ast.Subscript):
        value = _literal_value(node.value, assignments)
        key = _literal_value(node.slice, assignments)
        if isinstance(value, dict):
            return value.get(key)
    if isinstance(node, ast.Call):
        return _evaluate_known_call_ri(node, assignments)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _evaluate_known_call_ri(node: ast.Call, assignments: dict[str, Any]) -> Any:
    """Evaluate known builder calls (ReadyMetadata.build, InputSpec, ModelAsset)."""
    from vibecomfy.registry.static_contract import _evaluate_call

    return _evaluate_call(node, assignments)


# ---------------------------------------------------------------------------
# Readability scanners
# ---------------------------------------------------------------------------


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _count_positional_outs(source: str) -> int:
    """Count ``.out(<int_literal>)`` positional output accesses."""
    return len(re.findall(r"\.out\(\s*\d+\s*\)", source))


def _count_widget_n_fields(source: str) -> int:
    """Count ``widget_N`` (or ``'widget_N'``) field references."""
    return len(re.findall(r"\bwidget_\d+\b", source))


def _count_uuid_class_types(source: str) -> int:
    """Count UUIDs appearing as ComfyUI class_type literals.

    These appear in legacy NODES tuples like ``('uuid', 'ClassName', {...})``
    where the first element is a UUID string.
    """
    # Find string literals that are UUIDs in the source.
    return len([m for m in _UUID_RE.finditer(source)
                if _is_class_type_context(source, m.start(), m.end())])


def _is_class_type_context(source: str, start: int, end: int) -> bool:
    """Heuristic: is this UUID used as a node id (class_type context)?"""
    # Look for NODES tuple patterns: ('<uuid>', ...
    before = source[max(0, start - 20):start]
    if re.search(r"[([]\s*['\"]\s*$", before):
        after = source[end:end + 30]
        if re.search(r"\s*['\"]\s*,", after):
            return True
    # Also look for VibeNode('<uuid>', ...) patterns
    if re.search(r"VibeNode\(\s*['\"]\s*$", before):
        return True
    return False


def _count_n_uuid_variables(source: str) -> int:
    """Count ``n_<uuid>`` variable name patterns."""
    return len(re.findall(r"\bn_[0-9a-fA-F]{8}[-_]", source))


def _count_local_node_copies(source: str) -> int:
    """Count ``_node`` local variable copies (temporary helper references)."""
    return len(re.findall(r"\b_node\b", source))


def _detect_missing_output_contract(source: str) -> bool:
    """Check if the template is missing an explicit output contract.

    Looks for semantic ``bind_output`` / ``register_output`` descriptors,
    graph-level ``_outputs`` metadata, or ``finalize()`` calls in the source.
    """
    has_output = bool(re.search(r"bind_output|register_output|_outputs\s*=|finalize\(", source))
    return not has_output


def _classify_marker(source: str) -> str:
    """Classify the template's marker.

    Returns one of: "generated", "manual", "broken-regen", "reference", "authored", "unknown".
    """
    first_line = source.splitlines()[0].strip() if source.splitlines() else ""

    if "# vibecomfy: broken-regen" in first_line:
        return "broken-regen"
    if "# vibecomfy: manual" in first_line:
        return "manual"
    if "# vibecomfy: generated" in first_line:
        return "generated"
    if "# vibecomfy: narrative" in first_line:
        return "generated"

    # Check for reference marker
    has_api = bool(re.search(r"^API_WORKFLOW\s*=", source, re.MULTILINE))
    has_nodes = bool(re.search(r"^NODES\s*=", source, re.MULTILINE))

    if has_api:
        if "vibecomfy: broken-regen" in first_line:
            return "broken-regen"
        if "vibecomfy: manual" in first_line:
            return "manual"
        return "reference"  # legacy API_WORKFLOW — reference template
    if "vibecomfy: broken-regen" in first_line:
        return "broken-regen"
    if "vibecomfy: manual" in first_line:
        return "manual"
    if "vibecomfy: generated" in first_line:
        return "generated"
    if "vibecomfy: narrative" in first_line:
        return "generated"
    if has_nodes:
        return "authored"
    return "unknown"


# ---------------------------------------------------------------------------
# Provenance joins
# ---------------------------------------------------------------------------


def _load_coverage_map() -> dict[str, dict[str, Any]]:
    """Load coverage.json keyed by ready_template id."""
    if not COVERAGE_PATH.exists():
        return {}
    try:
        data = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    workflows = data.get("workflows", []) if isinstance(data, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for item in workflows:
        if not isinstance(item, dict):
            continue
        # Key by ready_template field
        rt = item.get("ready_template")
        if isinstance(rt, str):
            result[rt] = item
        # Also key by id for fallback
        wid = item.get("id")
        if isinstance(wid, str) and wid not in result:
            result[wid] = item
    return result


def _load_template_index_map() -> dict[str, dict[str, Any]]:
    """Load template_index.json keyed by template id."""
    if not TEMPLATE_INDEX_PATH.exists():
        return {}
    try:
        data = json.loads(TEMPLATE_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    templates = data.get("templates", []) if isinstance(data, dict) else []
    return {t["id"]: t for t in templates if isinstance(t, dict) and "id" in t}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_readability_inventory() -> ReadabilityInventory:
    """Build the repo-only readability inventory.

    Walks checked-in ``ready_templates/**/*.py``, never calls
    ``ready_template_ids()``.
    """
    paths = _enumerate_repo_templates()
    coverage_map = _load_coverage_map()
    index_map = _load_template_index_map()

    entries: list[TemplateInventoryEntry] = []
    summary_counts: Counter[str] = Counter()
    summary_missing_source = 0

    for path in paths:
        ready_id = _ready_id_for_path(path)
        source = path.read_text(encoding="utf-8")
        metadata, _requirements = _parse_ready_metadata(path)

        # Marker classification
        marker = _classify_marker(source)

        # Coverage tier (coverage.json wins, then READY_METADATA, then index)
        coverage_row = coverage_map.get(ready_id, {})
        index_row = index_map.get(ready_id, {})
        coverage_tier = (
            coverage_row.get("coverage_tier")
            or metadata.get("coverage_tier")
            or index_row.get("coverage_tier")
            or ""
        )

        # Capability
        capability = (
            metadata.get("capability")
            or coverage_row.get("task")
            or index_row.get("capability")
            or ""
        )

        # Source role
        source_role = metadata.get("source_role") or None
        source_workflow = metadata.get("source_workflow") or coverage_row.get("path") or None

        # app-active proxy: coverage_tier == "required" and has source_role
        app_active = coverage_tier == "required" and source_role is not None

        # Readability counts
        # local_node_copies is only tracked for generated strict-ready templates,
        # not for scratchpads or manual/reference/authored templates.
        _local_node_copies = _count_local_node_copies(source) if marker == "generated" else 0
        counts = ReadabilityCounts(
            positional_outs=_count_positional_outs(source),
            widget_n_fields=_count_widget_n_fields(source),
            uuid_class_types=_count_uuid_class_types(source),
            n_uuid_variables=_count_n_uuid_variables(source),
            local_node_copies=_local_node_copies,
            missing_output_contract=_detect_missing_output_contract(source),
        )

        # Missing source provenance: no source_workflow and not manual/reference
        missing_source = (
            source_workflow is None
            and marker not in ("manual", "broken-regen", "reference")
        )

        entry = TemplateInventoryEntry(
            ready_id=ready_id,
            path=path.relative_to(REPO_ROOT).as_posix(),
            marker=marker,
            coverage_tier=coverage_tier,
            capability=capability,
            source_role=source_role,
            source_workflow=source_workflow,
            app_active=app_active,
            counts=counts,
            missing_source_provenance=missing_source,
        )
        entries.append(entry)

        # Summary
        summary_counts["marker_" + marker] += 1
        summary_counts["tier_" + (coverage_tier or "unset")] += 1
        summary_counts["app_active"] += int(app_active)
        summary_counts["positional_outs_total"] += counts.positional_outs
        summary_counts["widget_n_fields_total"] += counts.widget_n_fields
        summary_counts["uuid_class_types_total"] += counts.uuid_class_types
        summary_counts["n_uuid_variables_total"] += counts.n_uuid_variables
        summary_counts["local_node_copies_total"] += counts.local_node_copies
        summary_counts["missing_output_contract"] += int(counts.missing_output_contract)
        if missing_source:
            summary_missing_source += 1

    summary = dict(summary_counts)
    summary["missing_source_provenance"] = summary_missing_source
    summary["templates_with_issues"] = sum(
        1 for e in entries
        if (e.counts.positional_outs > 0
            or e.counts.widget_n_fields > 0
            or e.counts.uuid_class_types > 0
            or e.counts.n_uuid_variables > 0
            or e.counts.local_node_copies > 0
            or e.counts.missing_output_contract)
    )

    return ReadabilityInventory(
        version=1,
        template_count=len(entries),
        entries=entries,
        summary=summary,
    )


__all__ = [
    "ReadabilityCounts",
    "ReadabilityInventory",
    "TemplateInventoryEntry",
    "build_readability_inventory",
]
