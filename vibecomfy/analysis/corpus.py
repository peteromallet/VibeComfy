"""Reusable ready-template corpus helper.

Provides :func:`build_corpus_snapshot` which imports
``repo_ready_template_paths`` and ``repo_ready_template_id_for_path``
from ``vibecomfy.registry.ready`` and computes aggregate statistics
across all checked-in ready templates without loading plugins.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.registry.ready import repo_ready_template_id_for_path, repo_ready_template_paths
from vibecomfy.utils import find_repo_root


@dataclass
class CorpusSnapshot:
    """Aggregate statistics across all checked-in ready templates."""

    templates_total: int = 0
    templates_regeneratable: int = 0
    templates_deferred: int = 0
    total_loc: int = 0
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)
    node_type_distribution: list[dict[str, Any]] = field(default_factory=list)
    custom_pack_usage: dict[str, int] = field(default_factory=dict)
    uuid_subgraph_instances: int = 0
    uuid_subgraph_templates: int = 0
    templates_with_manual_marker: int = 0
    templates_list: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "templates_total": self.templates_total,
            "templates_regeneratable": self.templates_regeneratable,
            "templates_deferred": self.templates_deferred,
            "total_loc": self.total_loc,
            "by_category": {
                cat: {
                    "templates": info["templates"],
                    "avg_loc": info["avg_loc"],
                }
                for cat, info in sorted(self.by_category.items())
            },
            "node_type_distribution": self.node_type_distribution,
            "custom_pack_usage": dict(
                sorted(self.custom_pack_usage.items(), key=lambda x: (-x[1], x[0]))
            ),
            "uuid_subgraph_instances": self.uuid_subgraph_instances,
            "uuid_subgraph_templates": self.uuid_subgraph_templates,
            "templates_with_manual_marker": self.templates_with_manual_marker,
        }


def build_corpus_snapshot(root: Path | None = None) -> CorpusSnapshot:
    """Build a :class:`CorpusSnapshot` from checked-in ready templates.

    Uses ``repo_ready_template_paths()`` for template discovery — no
    duplication of the template-discovery logic.
    """
    ready_root = root if root is not None else find_repo_root() / "ready_templates"
    paths = repo_ready_template_paths(ready_root)

    snapshot = CorpusSnapshot()
    snapshot.templates_total = len(paths)

    cat_counts: Counter[str] = Counter()
    cat_loc_totals: Counter[str] = Counter()
    node_type_counter: Counter[str] = Counter()
    node_type_template_sets: dict[str, set[str]] = {}
    pack_counter: Counter[str] = Counter()
    uuid_instance_count = 0
    uuid_template_set: set[str] = set()
    manual_count = 0

    for path in paths:
        template_id = repo_ready_template_id_for_path(path, ready_root)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue

        # LOC
        loc = len([l for l in source.splitlines() if l.strip()])
        snapshot.total_loc += loc

        # Category
        category = template_id.split("/")[0] if "/" in template_id else "unknown"
        cat_counts[category] += 1
        cat_loc_totals[category] += loc

        # Marker classification
        first_line = source.splitlines()[0].strip() if source.splitlines() else ""
        if "# vibecomfy: generated" in first_line:
            snapshot.templates_regeneratable += 1
        elif "# vibecomfy: manual" in first_line:
            snapshot.templates_deferred += 1
            manual_count += 1
        else:
            # Check for other markers or treat as deferred
            if "# vibecomfy:" in first_line:
                snapshot.templates_deferred += 1
            else:
                # Not a generated template — could be reference, authored, etc.
                snapshot.templates_deferred += 1

        # Per-template node types — capture from multiple patterns:
        # 1. class_type = 'ClassName' (raw node creation)
        # 2. _node(wf, 'ClassName', ...) (template helper)
        # 3. add_block_node(wf, ..., 'ClassName', ...) (typed wrapper)
        class_types: set[str] = set()
        for pattern in [
            r"class_type\s*=\s*['\"]([^'\"]+)['\"]",
            r"_node\s*\(\s*\w+\s*,\s*['\"]([^'\"]+)['\"]",
            r"add_block_node\s*\([^)]*?['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        ]:
            for ct in re.findall(pattern, source):
                if ct and not ct.startswith("vibecomfy"):
                    class_types.add(ct)
        for ct in class_types:
            node_type_counter[ct] += 1
            node_type_template_sets.setdefault(ct, set()).add(template_id)

        # Custom pack usage: look for `_node(wf, 'ClassName', ...)` where
        # ClassName doesn't look like a core class.
        for ct in class_types:
            # Determine pack by checking if class appears in known pack names
            # We'll aggregate pack usage via class_type -> pack mapping later
            pass

        # Look for custom pack references in READY_REQUIREMENTS['custom_nodes']
        packs_match = re.search(
            r"['\"]custom_nodes['\"]\s*:\s*\[(.*?)\]",
            source,
            re.DOTALL,
        )
        if packs_match:
            packs_text = packs_match.group(1)
            for pack_name in re.findall(r"['\"]([^'\"]+)['\"]", packs_text):
                if pack_name and not pack_name.startswith("_"):
                    pack_counter[pack_name] += 1

        # UUID subgraph instances
        uuid_matches = re.findall(
            r"class_type\s*=\s*['\"]([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})['\"]",
            source,
        )
        if uuid_matches:
            uuid_instance_count += len(uuid_matches)
            uuid_template_set.add(template_id)

        snapshot.templates_list.append(
            {
                "id": template_id,
                "path": str(path),
                "category": category,
                "loc": loc,
                "marker": _classify_marker(source),
            }
        )

    # By-category stats
    snapshot.by_category = {
        cat: {
            "templates": cat_counts[cat],
            "avg_loc": round(cat_loc_totals[cat] / cat_counts[cat]) if cat_counts[cat] else 0,
        }
        for cat in sorted(cat_counts)
    }

    # Top-10 node-type distribution
    snapshot.node_type_distribution = [
        {
            "class_type": ct,
            "occurrences": node_type_counter[ct],
            "templates": len(node_type_template_sets.get(ct, set())),
        }
        for ct, _ in node_type_counter.most_common(10)
    ]

    # Custom pack usage (sorted by template count desc)
    snapshot.custom_pack_usage = dict(
        sorted(pack_counter.items(), key=lambda x: (-x[1], x[0]))
    )

    snapshot.uuid_subgraph_instances = uuid_instance_count
    snapshot.uuid_subgraph_templates = len(uuid_template_set)
    snapshot.templates_with_manual_marker = manual_count

    return snapshot


def _classify_marker(source: str) -> str:
    """Classify the template's marker."""
    first_line = source.splitlines()[0].strip() if source.splitlines() else ""
    if "# vibecomfy: manual" in first_line:
        return "manual"
    if "# vibecomfy: generated" in first_line:
        return "generated"
    if "# vibecomfy:" in first_line:
        return first_line.split("# vibecomfy:")[1].strip().split()[0]
    return "unknown"


__all__ = [
    "CorpusSnapshot",
    "build_corpus_snapshot",
]
