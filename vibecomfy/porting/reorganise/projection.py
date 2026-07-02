from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping, Sequence

from .graph_facts import (
    GraphInventoryFacts,
    ScopeTopologyFacts,
    display_ref,
    extract_graph_facts,
)
from .plan_types import CanonicalNodeRef

DEFAULT_MAX_TOKENS = 8000
DEFAULT_MAX_CANONICAL_REFS = 120
DEFAULT_MAX_NODE_FACTS_PER_SCOPE = 80
DEFAULT_MAX_EDGES_PER_SCOPE = 100
DEFAULT_MAX_TERMINAL_PATHS_PER_SCOPE = 48
DEFAULT_MAX_FURNITURE_FACTS = 80
DEFAULT_MAX_GROUP_FACTS_PER_SCOPE = 32


@dataclass(frozen=True, slots=True)
class LayoutProjectionOptions:
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_canonical_refs: int = DEFAULT_MAX_CANONICAL_REFS
    max_node_facts_per_scope: int = DEFAULT_MAX_NODE_FACTS_PER_SCOPE
    max_edges_per_scope: int = DEFAULT_MAX_EDGES_PER_SCOPE
    max_terminal_paths_per_scope: int = DEFAULT_MAX_TERMINAL_PATHS_PER_SCOPE
    max_furniture_facts: int = DEFAULT_MAX_FURNITURE_FACTS
    max_group_facts_per_scope: int = DEFAULT_MAX_GROUP_FACTS_PER_SCOPE


@dataclass(frozen=True, slots=True)
class LayoutProjectionResult:
    text: str
    token_estimate: int
    scope_count: int
    canonical_ref_count: int
    summarized: bool = False
    truncated: bool = False


def render_layout_projection(
    facts: GraphInventoryFacts,
    *,
    options: LayoutProjectionOptions | None = None,
) -> LayoutProjectionResult:
    """Render graph facts as a read-only layout reasoning view.

    The projection deliberately contains facts, not operations: it is intended
    for planning section ownership and helper placement, while preserving the
    existing LiteGraph/UI substrate as the only source of truth.
    """

    opts = options or LayoutProjectionOptions()
    lines, summarized = _render_lines(facts, opts)
    text = "\n".join(lines).rstrip() + "\n"
    estimate = estimate_tokens(text)
    truncated = False
    if estimate > opts.max_tokens:
        text, estimate = _truncate_to_budget(text, opts.max_tokens)
        truncated = True
        summarized = True
    return LayoutProjectionResult(
        text=text,
        token_estimate=estimate,
        scope_count=len(facts.summary.scopes),
        canonical_ref_count=len(facts.canonical_refs),
        summarized=summarized,
        truncated=truncated,
    )


def render_layout_projection_from_ui(
    ui_json: Mapping[str, Any],
    *,
    sidecar_envelope: Mapping[str, Any] | None = None,
    options: LayoutProjectionOptions | None = None,
) -> LayoutProjectionResult:
    facts = extract_graph_facts(ui_json, sidecar_envelope=sidecar_envelope)
    return render_layout_projection(facts, options=options)


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _render_lines(
    facts: GraphInventoryFacts,
    opts: LayoutProjectionOptions,
) -> tuple[list[str], bool]:
    summarized = False
    lines: list[str] = [
        "layout_reasoning_view:",
        "  contract:",
        "    kind: read_only_layout_facts",
        "    executable_python: false",
        "    coordinate_plan: false",
        "    refs: canonical arrays shaped [scope_path, uid]",
        "    runtime_mutation: forbidden",
        "  summary:",
        f"    scopes: {len(facts.summary.scopes)}",
        f"    canonical_refs: {len(facts.canonical_refs)}",
        f"    helpers: {len(facts.helper_nodes)}",
        f"    virtual_links: {len(facts.virtual_wires)}",
        f"    graph_facts_truncated: {_bool_text(facts.summary.truncated)}",
        "  canonical_ref_table:",
    ]
    ref_lines, omitted = _canonical_ref_lines(facts, opts.max_canonical_refs)
    summarized = summarized or omitted > 0
    lines.extend(ref_lines)
    if omitted:
        lines.append(f"    - omitted: {omitted} canonical refs; see scope summaries below")

    helper_lines, omitted = _helper_lines(facts, opts.max_canonical_refs)
    lines.extend(["  helper_facts:", *helper_lines])
    summarized = summarized or omitted > 0
    if omitted:
        lines.append(f"    - omitted: {omitted} helper facts")

    virtual_lines, omitted = _virtual_wire_lines(facts, opts.max_canonical_refs)
    lines.extend(["  virtual_link_facts:", *virtual_lines])
    summarized = summarized or omitted > 0
    if omitted:
        lines.append(f"    - omitted: {omitted} virtual link facts")

    furniture_lines, omitted = _node_furniture_lines(facts, opts.max_furniture_facts)
    lines.extend(["  ui_furniture_facts:", *furniture_lines])
    summarized = summarized or omitted > 0
    if omitted:
        lines.append(f"    - omitted: {omitted} node furniture facts")

    scope_lines, scope_summarized = _scope_lines(facts, opts)
    lines.extend(["  scopes:", *scope_lines])
    summarized = summarized or scope_summarized

    if facts.diagnostics:
        lines.append("  diagnostics:")
        for diagnostic in facts.diagnostics:
            detail = _json(diagnostic.detail)
            lines.append(
                "    - "
                f"severity: {diagnostic.severity} "
                f"code: {_json(diagnostic.code)} "
                f"path: {_json(list(diagnostic.path))} "
                f"detail: {detail}"
            )
    return lines, summarized


def _canonical_ref_lines(
    facts: GraphInventoryFacts,
    limit: int,
) -> tuple[list[str], int]:
    rows = sorted(
        facts.canonical_refs,
        key=lambda fact: (_scope_sort_key(fact.ref.scope_path), _natural_key(fact.ref.uid)),
    )
    shown = rows[:limit]
    lines = [
        "    - "
        f"ref: {_ref(fact.ref)} "
        f"display: {_json(fact.display)} "
        f"class_type: {_json(fact.class_type)} "
        f"litegraph_id: {_json(fact.litegraph_id)} "
        f"role_hint: {fact.role_hint} "
        f"helper: {_bool_text(fact.is_helper)}"
        + (f" title: {_json(fact.title)}" if fact.title else "")
        for fact in shown
    ]
    if not lines:
        lines.append("    - none")
    return lines, max(0, len(rows) - len(shown))


def _helper_lines(
    facts: GraphInventoryFacts,
    limit: int,
) -> tuple[list[str], int]:
    rows = sorted(
        facts.helper_nodes,
        key=lambda fact: (_scope_sort_key(fact.ref.scope_path), _natural_key(fact.ref.uid)),
    )
    shown = rows[:limit]
    lines = [
        "    - "
        f"ref: {_ref(fact.ref)} "
        f"class_type: {_json(fact.class_type)} "
        f"helper_kind: {_json(fact.helper_kind)} "
        f"channel: {_json(fact.channel)} "
        f"display: {_json(fact.display)}"
        for fact in shown
    ]
    if not lines:
        lines.append("    - none")
    reroute_lines = [
        "    - "
        f"reroute_ref: {_ref(fact.ref)} "
        f"input_links: {_json(list(fact.input_links))} "
        f"output_links: {_json(list(fact.output_links))}"
        for fact in sorted(
            facts.reroutes,
            key=lambda fact: (_scope_sort_key(fact.ref.scope_path), _natural_key(fact.ref.uid)),
        )[:limit]
    ]
    return [*lines, *reroute_lines], max(0, len(rows) - len(shown))


def _virtual_wire_lines(
    facts: GraphInventoryFacts,
    limit: int,
) -> tuple[list[str], int]:
    rows = sorted(facts.virtual_wires, key=lambda fact: (fact.source, fact.key))
    shown = rows[:limit]
    lines = [
        "    - "
        f"source: {fact.source} "
        f"key: {_json(fact.key)} "
        f"type: {_json(fact.wire_type)} "
        f"channel: {_json(fact.channel)} "
        f"endpoints: {_json(list(fact.endpoints))}"
        for fact in shown
    ]
    if not lines:
        lines.append("    - none")
    return lines, max(0, len(rows) - len(shown))


def _node_furniture_lines(
    facts: GraphInventoryFacts,
    limit: int,
) -> tuple[list[str], int]:
    rows = sorted(
        facts.node_furniture,
        key=lambda fact: (_scope_sort_key(fact.ref.scope_path), _natural_key(fact.ref.uid)),
    )
    shown = rows[:limit]
    lines = [
        "    - "
        f"ref: {_ref(fact.ref)} "
        f"observed_pos: {_json(_thaw(fact.pos))} "
        f"observed_size: {_json(_thaw(fact.size))} "
        f"color: {_json(fact.color)} "
        f"bgcolor: {_json(fact.bgcolor)} "
        f"mode: {_json(fact.mode)} "
        f"flags: {_json(_thaw(fact.flags))} "
        f"sidecar_entry_key: {_json(fact.sidecar_entry_key)}"
        for fact in shown
    ]
    if not lines:
        lines.append("    - none")
    return lines, max(0, len(rows) - len(shown))


def _scope_lines(
    facts: GraphInventoryFacts,
    opts: LayoutProjectionOptions,
) -> tuple[list[str], bool]:
    summarized = False
    refs_by_scope = _refs_by_scope(facts)
    topologies = {topology.scope_path: topology for topology in facts.scope_topologies}
    furniture = {scope.scope_path: scope for scope in facts.scope_furniture}
    scopes = sorted(facts.summary.scopes, key=lambda scope: _scope_sort_key(scope.scope_path))
    lines: list[str] = []
    for scope in scopes:
        indent = "    " + "  " * _scope_depth(scope.scope_path)
        label = "<root>" if scope.scope_path == "" else scope.scope_path
        lines.append(f"{indent}- scope: {_json(label)}")
        lines.append(f"{indent}  scope_path: {_json(scope.scope_path)}")
        lines.append(
            f"{indent}  graph_summary: "
            f"nodes={scope.node_count} edges={scope.edge_count} helpers={scope.helper_count} "
            f"wcc={scope.wcc_count} scc={scope.scc_count} summarized={_bool_text(scope.summarized)}"
        )
        lines.append(
            f"{indent}  terminal_refs: {_json([ref.to_json() for ref in scope.terminal_refs])}"
        )
        lines.append(f"{indent}  sampler_refs: {_json([ref.to_json() for ref in scope.sampler_refs])}")
        scope_refs = refs_by_scope.get(scope.scope_path, ())
        lines.append(f"{indent}  canonical_refs:")
        ref_limit = opts.max_node_facts_per_scope
        shown_refs = scope_refs[:ref_limit]
        for fact in shown_refs:
            lines.append(
                f"{indent}    - ref: {_ref(fact.ref)} "
                f"class_type: {_json(fact.class_type)} role_hint: {fact.role_hint}"
            )
        if len(scope_refs) > len(shown_refs):
            summarized = True
            lines.append(f"{indent}    - omitted: {len(scope_refs) - len(shown_refs)} canonical refs in this scope")

        scope_furniture = furniture.get(scope.scope_path)
        lines.append(f"{indent}  group_facts:")
        groups = scope_furniture.groups if scope_furniture is not None else ()
        shown_groups = tuple(groups[: opts.max_group_facts_per_scope])
        for group in shown_groups:
            lines.append(
                f"{indent}    - index: {group.index} "
                f"title: {_json(group.title)} "
                f"bounding: {_json(_thaw(group.bounding))} "
                f"color: {_json(group.color)} "
                f"nodes: {_json([_thaw(item) for item in group.nodes])}"
            )
        if not shown_groups:
            lines.append(f"{indent}    - none")
        if len(groups) > len(shown_groups):
            summarized = True
            lines.append(f"{indent}    - omitted: {len(groups) - len(shown_groups)} group facts")
        if scope_furniture is not None:
            lines.append(
                f"{indent}  scope_ui_facts: "
                f"definitions_present={_bool_text(scope_furniture.definitions_present)} "
                f"lastRerouteId={_json(scope_furniture.last_reroute_id)} "
                f"extra_keys={_json(sorted(str(key) for key in scope_furniture.extra.keys()))}"
            )

        topology = topologies.get(scope.scope_path)
        if topology is not None:
            topology_lines, topology_summarized = _topology_lines(topology, opts, indent)
            lines.extend(topology_lines)
            summarized = summarized or topology_summarized
    return lines, summarized


def _topology_lines(
    topology: ScopeTopologyFacts,
    opts: LayoutProjectionOptions,
    indent: str,
) -> tuple[list[str], bool]:
    summarized = topology.truncated
    lines: list[str] = [f"{indent}  graph_facts:"]
    node_rows = sorted(
        topology.node_topology,
        key=lambda fact: (_scope_sort_key(fact.ref.scope_path), _natural_key(fact.ref.uid)),
    )
    shown_nodes = node_rows[: opts.max_node_facts_per_scope]
    lines.append(f"{indent}    node_topology:")
    for fact in shown_nodes:
        terminal_types = ",".join(fact.terminal_output_types) if fact.terminal_output_types else "-"
        lines.append(
            f"{indent}      - ref: {_ref(fact.ref)} "
            f"class_type: {_json(fact.class_type)} "
            f"fan_in: {fact.fan_in} fan_out: {fact.fan_out} "
            f"rank: {fact.topological_rank} lane: [{fact.lane_band}, {fact.lane_index}] "
            f"scc: {fact.scc_id} wcc: {fact.wcc_id} "
            f"terminal: {_bool_text(fact.terminal)} terminal_output_types: {_json(terminal_types)}"
        )
    if len(node_rows) > len(shown_nodes):
        summarized = True
        lines.append(f"{indent}      - omitted: {len(node_rows) - len(shown_nodes)} node topology facts")

    for label, edges in (
        ("raw_edges", topology.raw_edges),
        ("effective_edges", topology.effective_edges),
    ):
        sorted_edges = sorted(
            edges,
            key=lambda edge: (
                _scope_sort_key(edge.scope_path),
                _natural_key(edge.source.uid),
                edge.source_slot,
                _natural_key(edge.target.uid),
                edge.target_slot,
                _json(edge.link_id),
            ),
        )
        shown_edges = sorted_edges[: opts.max_edges_per_scope]
        lines.append(f"{indent}    {label}:")
        for edge in shown_edges:
            lines.append(
                f"{indent}      - from: {_ref(edge.source)}:{_json(edge.source_slot)} "
                f"to: {_ref(edge.target)}:{_json(edge.target_slot)} "
                f"type: {_json(edge.socket_type)} "
                f"link_id: {_json(edge.link_id)} "
                f"passthrough_fact: {_bool_text(edge.passthrough)}"
            )
        if not shown_edges:
            lines.append(f"{indent}      - none")
        if len(sorted_edges) > len(shown_edges):
            summarized = True
            lines.append(f"{indent}      - omitted: {len(sorted_edges) - len(shown_edges)} {label} facts")

    paths = sorted(
        topology.terminal_paths,
        key=lambda path: ([ref.uid.zfill(20) for ref in path.path], path.terminal.to_json()),
    )
    shown_paths = paths[: opts.max_terminal_paths_per_scope]
    lines.append(f"{indent}    terminal_path_facts:")
    for path in shown_paths:
        lines.append(
            f"{indent}      - terminal: {_ref(path.terminal)} "
            f"terminal_type: {_json(path.terminal_type)} "
            f"path: {_json([ref.to_json() for ref in path.path])} "
            f"output_types: {_json(list(path.terminal_output_types))} "
            f"truncated: {_bool_text(path.truncated)}"
        )
    if not shown_paths:
        lines.append(f"{indent}      - none")
    if len(paths) > len(shown_paths):
        summarized = True
        lines.append(f"{indent}      - omitted: {len(paths) - len(shown_paths)} terminal path facts")

    branch_rows = sorted(
        topology.parallel_branch_candidates,
        key=lambda candidate: (_natural_key(candidate.source.uid), [ref.uid for ref in candidate.branch_roots]),
    )
    lines.append(f"{indent}    parallel_branch_candidates:")
    if branch_rows:
        for candidate in branch_rows:
            lines.append(
                f"{indent}      - source: {_ref(candidate.source)} "
                f"branch_roots: {_json([ref.to_json() for ref in candidate.branch_roots])} "
                f"terminal_refs: {_json([ref.to_json() for ref in candidate.terminal_refs])}"
            )
    else:
        lines.append(f"{indent}      - none")

    relation_rows = sorted(
        topology.sampler_relation_candidates,
        key=lambda relation: (
            relation.kind,
            [ref.uid.zfill(20) for ref in relation.samplers],
            relation.source.uid if relation.source else "",
            relation.target.uid if relation.target else "",
        ),
    )
    lines.append(f"{indent}    sampler_relation_candidates:")
    if relation_rows:
        for relation in relation_rows:
            lines.append(
                f"{indent}      - kind: {relation.kind} "
                f"samplers: {_json([ref.to_json() for ref in relation.samplers])} "
                f"source: {_json(relation.source.to_json() if relation.source else None)} "
                f"target: {_json(relation.target.to_json() if relation.target else None)} "
                f"reason: {_json(relation.reason)}"
            )
    else:
        lines.append(f"{indent}      - none")
    return lines, summarized


def _refs_by_scope(facts: GraphInventoryFacts) -> dict[str, tuple[Any, ...]]:
    rows: dict[str, list[Any]] = {}
    for fact in sorted(
        facts.canonical_refs,
        key=lambda fact: (_scope_sort_key(fact.ref.scope_path), _natural_key(fact.ref.uid)),
    ):
        rows.setdefault(fact.ref.scope_path, []).append(fact)
    return {scope_path: tuple(scope_rows) for scope_path, scope_rows in rows.items()}


def _scope_sort_key(scope_path: str) -> tuple[int, tuple[str, ...], str]:
    if scope_path == "":
        return (0, (), "")
    return (1, tuple(scope_path.split("/")), scope_path)


def _scope_depth(scope_path: str) -> int:
    if not scope_path:
        return 0
    return max(1, scope_path.count("/") + 1)


def _natural_key(value: str) -> str:
    return value.zfill(20) if value.isdigit() else value


def _ref(ref: CanonicalNodeRef) -> str:
    return _json(ref.to_json())


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _truncate_to_budget(text: str, max_tokens: int) -> tuple[str, int]:
    max_chars = max(256, max_tokens * 4)
    suffix = "\n\nprojection_summary: truncated_to_token_budget\n"
    if len(text) <= max_chars:
        return text, estimate_tokens(text)
    truncated = text[: max(0, max_chars - len(suffix))].rstrip() + suffix
    return truncated, estimate_tokens(truncated)


render_layout_reasoning_view = render_layout_projection


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "LayoutProjectionOptions",
    "LayoutProjectionResult",
    "display_ref",
    "estimate_tokens",
    "render_layout_projection",
    "render_layout_projection_from_ui",
    "render_layout_reasoning_view",
]
