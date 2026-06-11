# S4 agent-context boundary: untrusted node text is wrapped under the marker
# ``{"_taint": "untrusted_data", "value": ...}`` by ``agent_dump_values``; see
# ``docs/security/agent_data_boundary.md``. The legacy ``values()`` shape is
# preserved unchanged for non-agent consumers.
from __future__ import annotations

from copy import deepcopy
from typing import Any

from vibecomfy._compile._graph import is_api_link
from vibecomfy.schema import SchemaProvider, schema_for
from vibecomfy.security import provenance as _provenance
from vibecomfy.workflow import VibeNode, VibeOutput, VibeWorkflow


MAX_PATH_DEPTH = 32
SOURCE_NAME_PARTS = ("load", "loader", "input", "constant", "primitive", "emptylatent")

TAINT_MARKER = "untrusted_data"
TAINT_KEY = "_taint"
SCHEMA_EXEMPT_KEYS: frozenset[str] = frozenset(
    {"output_names", "output_types", "input_aliases", "schema_source"}
)
_UI_USER_CONTROLLED: tuple[str, ...] = ("mode", "flags", "color", "bgcolor")


def analyze(workflow: VibeWorkflow) -> dict[str, Any]:
    fan_in = {node_id: 0 for node_id in workflow.nodes}
    fan_out = {node_id: 0 for node_id in workflow.nodes}
    for edge in workflow.edges:
        fan_out[edge.from_node] = fan_out.get(edge.from_node, 0) + 1
        fan_in[edge.to_node] = fan_in.get(edge.to_node, 0) + 1

    sinks = sorted(node_id for node_id in workflow.nodes if fan_out.get(node_id, 0) == 0)
    return {
        "node_count": len(workflow.nodes),
        "edge_count": len(workflow.edges),
        "fan_in_histogram": _histogram(fan_in.values()),
        "fan_out_histogram": _histogram(fan_out.values()),
        "output_sinks": _output_sinks(workflow, sinks),
        "terminal_inputs": _terminal_inputs(workflow, fan_in),
        "detected_media_type": _detect_media_type(workflow),
    }


def trace(workflow: VibeWorkflow, node_id: str) -> list[VibeNode]:
    ordered = _topological_subset(workflow, upstream(workflow, node_id) | {str(node_id)})
    return [workflow.nodes[current] for current in ordered if current in workflow.nodes]


def upstream(workflow: VibeWorkflow, node_id: str, depth: int | None = None) -> set[str]:
    reverse: dict[str, set[str]] = {}
    for edge in workflow.edges:
        reverse.setdefault(edge.to_node, set()).add(edge.from_node)
    return _walk(reverse, str(node_id), depth)


def downstream(workflow: VibeWorkflow, node_id: str, depth: int | None = None) -> set[str]:
    forward: dict[str, set[str]] = {}
    for edge in workflow.edges:
        forward.setdefault(edge.from_node, set()).add(edge.to_node)
    return _walk(forward, str(node_id), depth)


def path(workflow: VibeWorkflow, src: str, dst: str) -> list[list[str]]:
    src = str(src)
    dst = str(dst)
    forward: dict[str, list[str]] = {}
    for edge in workflow.edges:
        forward.setdefault(edge.from_node, []).append(edge.to_node)

    found: list[list[str]] = []

    def visit(current: str, seen: list[str]) -> None:
        if len(seen) > MAX_PATH_DEPTH:
            return
        if current == dst:
            found.append(list(seen))
            return
        for child in sorted(forward.get(current, [])):
            if child not in seen:
                visit(child, [*seen, child])

    visit(src, [src])
    return found


def subgraph(workflow: VibeWorkflow, node_ids: set[str] | list[str] | tuple[str, ...]) -> VibeWorkflow:
    selected = {str(node_id) for node_id in node_ids}
    nodes = {node_id: deepcopy(node) for node_id, node in workflow.nodes.items() if node_id in selected}
    edges = [
        deepcopy(edge)
        for edge in workflow.edges
        if edge.from_node in selected and edge.to_node in selected
    ]
    inputs = {
        name: deepcopy(input_ref)
        for name, input_ref in workflow.inputs.items()
        if input_ref.node_id in selected
    }
    outputs = [deepcopy(output) for output in workflow.outputs if output.node_id in selected]
    return VibeWorkflow(
        id=f"{workflow.id}:subgraph",
        source=deepcopy(workflow.source),
        nodes=nodes,
        edges=edges,
        inputs=inputs,
        outputs=outputs,
        requirements=deepcopy(workflow.requirements),
        metadata=deepcopy(workflow.metadata),
    )


def values(workflow: VibeWorkflow, node_id: str | None = None) -> dict[str, Any]:
    if node_id is not None:
        node = workflow.nodes[str(node_id)]
        return _node_values(node)
    return {current: _node_values(node) for current, node in workflow.nodes.items()}


def diff(workflow_a: VibeWorkflow, workflow_b: VibeWorkflow) -> dict[str, Any]:
    ids_a = set(workflow_a.nodes)
    ids_b = set(workflow_b.nodes)
    shared = ids_a & ids_b
    changed_nodes = sorted(
        node_id
        for node_id in shared
        if _node_signature(workflow_a.nodes[node_id]) != _node_signature(workflow_b.nodes[node_id])
    )
    return {
        "added_nodes": sorted(ids_b - ids_a),
        "removed_nodes": sorted(ids_a - ids_b),
        "changed_nodes": changed_nodes,
        "added_edges": sorted(_edge_set(workflow_b) - _edge_set(workflow_a)),
        "removed_edges": sorted(_edge_set(workflow_a) - _edge_set(workflow_b)),
        "input_value_changes": _input_value_changes(workflow_a, workflow_b, shared),
    }


def unconnected(workflow: VibeWorkflow, schema_provider: SchemaProvider | None = None) -> list[dict[str, Any]]:
    incoming = _incoming_inputs(workflow)
    if schema_provider is not None:
        return _schema_unconnected(workflow, schema_provider, incoming)

    rows: list[dict[str, Any]] = []
    for node_id, node in workflow.nodes.items():
        if incoming.get(node_id) or node.widgets or _looks_like_source(node):
            continue
        rows.append(
            {
                "node_id": node_id,
                "class_type": node.class_type,
                "reason": "no_incoming_edges",
            }
        )
    return rows


def _walk(adjacency: dict[str, set[str]], start: str, depth: int | None) -> set[str]:
    if depth is not None and depth <= 0:
        return set()
    seen: set[str] = set()
    frontier = [(start, 0)]
    while frontier:
        current, current_depth = frontier.pop(0)
        if depth is not None and current_depth >= depth:
            continue
        for next_id in sorted(adjacency.get(current, set())):
            if next_id in seen:
                continue
            seen.add(next_id)
            frontier.append((next_id, current_depth + 1))
    return seen


def _topological_subset(workflow: VibeWorkflow, selected: set[str]) -> list[str]:
    forward: dict[str, list[str]] = {}
    indegree = {node_id: 0 for node_id in selected}
    for edge in workflow.edges:
        if edge.from_node in selected and edge.to_node in selected:
            forward.setdefault(edge.from_node, []).append(edge.to_node)
            indegree[edge.to_node] = indegree.get(edge.to_node, 0) + 1
    ready = sorted(node_id for node_id, count in indegree.items() if count == 0)
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(forward.get(current, [])):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    return ordered + sorted(selected - set(ordered))


def _node_values(node: VibeNode) -> dict[str, Any]:
    merged = {**node.inputs, **node.widgets}
    return {
        key: deepcopy(value)
        for key, value in merged.items()
        if not is_api_link(
            value,
            allow_tuple=False,
            require_string_node_id=False,
            require_numeric_node_id=True,
            require_int_slot=False,
        )
    }


def agent_dump_values(workflow: VibeWorkflow, node_id: str | None = None) -> dict[str, Any]:
    """Agent-facing dump that wraps untrusted text under ``_taint`` markers.

    Same outer shape as :func:`values` but each per-node dict additionally
    carries a ``_metadata`` sub-dict mirroring ``node.metadata`` (including
    ``title`` and the user-controllable ``_ui`` sub-values). For nodes whose
    provenance reads ``untrusted_source`` (fail-closed via
    :func:`vibecomfy.security.provenance.read`), every string value outside the
    schema-exempt set is wrapped as ``{"_taint": "untrusted_data", "value": ...}``
    so the agent system prompt cannot mistake graph data for an instruction.
    """
    if node_id is not None:
        node = workflow.nodes[str(node_id)]
        return _agent_dump_node(node)
    return {current: _agent_dump_node(node) for current, node in workflow.nodes.items()}


def _agent_dump_node(node: VibeNode) -> dict[str, Any]:
    untrusted = _provenance.read(node) == "untrusted_source"
    out: dict[str, Any] = {}
    merged = {**node.inputs, **node.widgets}
    for key, value in merged.items():
        if is_api_link(
            value,
            allow_tuple=False,
            require_string_node_id=False,
            require_numeric_node_id=True,
            require_int_slot=False,
        ):
            continue
        out[key] = _maybe_wrap(key, value, untrusted)
    out["_metadata"] = _agent_dump_metadata(node.metadata, untrusted)
    return out


def _agent_dump_metadata(metadata: dict[str, Any], untrusted: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in SCHEMA_EXEMPT_KEYS:
            out[key] = deepcopy(value)
            continue
        if key == "_ui" and isinstance(value, dict):
            ui_out: dict[str, Any] = {}
            for sub_key, sub_value in value.items():
                if untrusted and sub_key in _UI_USER_CONTROLLED:
                    ui_out[sub_key] = _wrap(sub_value)
                else:
                    ui_out[sub_key] = _maybe_wrap(sub_key, sub_value, untrusted)
            out[key] = ui_out
            continue
        out[key] = _maybe_wrap(key, value, untrusted)
    return out


def _maybe_wrap(key: str, value: Any, untrusted: bool) -> Any:
    if not untrusted or key in SCHEMA_EXEMPT_KEYS:
        return deepcopy(value)
    if isinstance(value, str):
        return _wrap(value)
    return deepcopy(value)


def _wrap(value: Any) -> dict[str, Any]:
    return {TAINT_KEY: TAINT_MARKER, "value": deepcopy(value)}


def _node_signature(node: VibeNode) -> dict[str, Any]:
    return {
        "class_type": node.class_type,
        "pack": node.pack,
        "inputs": deepcopy(node.inputs),
        "widgets": deepcopy(node.widgets),
        "metadata": deepcopy(node.metadata),
    }


def _input_value_changes(workflow_a: VibeWorkflow, workflow_b: VibeWorkflow, shared: set[str]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for node_id in sorted(shared):
        values_a = values(workflow_a, node_id)
        values_b = values(workflow_b, node_id)
        keys = set(values_a) | set(values_b)
        node_changes = {
            key: {"from": deepcopy(values_a.get(key)), "to": deepcopy(values_b.get(key))}
            for key in sorted(keys)
            if values_a.get(key) != values_b.get(key)
        }
        if node_changes:
            changes[node_id] = node_changes
    return changes


def _edge_set(workflow: VibeWorkflow) -> set[tuple[str, str, str, str]]:
    return {(edge.from_node, edge.from_output, edge.to_node, edge.to_input) for edge in workflow.edges}


def _incoming_inputs(workflow: VibeWorkflow) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = {}
    for edge in workflow.edges:
        incoming.setdefault(edge.to_node, set()).add(edge.to_input)
    return incoming


def _schema_unconnected(
    workflow: VibeWorkflow,
    schema_provider: SchemaProvider,
    incoming: dict[str, set[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node_id, node in workflow.nodes.items():
        schema = schema_for(schema_provider, node.class_type)
        if schema is None:
            continue
        provided = set(node.inputs) | set(node.widgets) | incoming.get(node_id, set())
        for name, spec in (getattr(schema, "inputs", {}) or {}).items():
            if getattr(spec, "required", False) and name not in provided:
                rows.append(
                    {
                        "node_id": node_id,
                        "class_type": node.class_type,
                        "input": name,
                        "reason": "missing_required_input",
                    }
                )
    return rows


def _histogram(values: Any) -> dict[int, int]:
    histogram: dict[int, int] = {}
    for value in values:
        histogram[int(value)] = histogram.get(int(value), 0) + 1
    return dict(sorted(histogram.items()))


def _output_sinks(workflow: VibeWorkflow, sink_ids: list[str]) -> list[dict[str, str | None]]:
    if workflow.outputs:
        return [_output_row(output) for output in workflow.outputs]
    return [{"node_id": node_id, "output_type": workflow.nodes[node_id].class_type, "name": None} for node_id in sink_ids]


def _output_row(output: VibeOutput) -> dict[str, str | None]:
    return {"node_id": output.node_id, "output_type": output.output_type, "name": output.name}


def _terminal_inputs(workflow: VibeWorkflow, fan_in: dict[str, int]) -> list[dict[str, Any]]:
    if workflow.inputs:
        return [
            {"name": name, "node_id": ref.node_id, "field": ref.field, "value": deepcopy(ref.value)}
            for name, ref in sorted(workflow.inputs.items())
        ]
    return [
        {"node_id": node_id, "class_type": workflow.nodes[node_id].class_type}
        for node_id, count in sorted(fan_in.items())
        if count == 0
    ]


def _detect_media_type(workflow: VibeWorkflow) -> str:
    for source in (workflow.metadata, workflow.source.provenance):
        media_type = source.get("media_type") or source.get("media")
        if isinstance(media_type, str) and media_type:
            return media_type
    text = " ".join([output.output_type for output in workflow.outputs] + [node.class_type for node in workflow.nodes.values()]).lower()
    if any(token in text for token in ("video", "webm", "vhs", "animated")):
        return "video"
    if "audio" in text:
        return "audio"
    if any(token in text for token in ("image", "latent", "vae")):
        return "image"
    return "unknown"


def _looks_like_source(node: VibeNode) -> bool:
    name = node.class_type.lower()
    return any(part in name for part in SOURCE_NAME_PARTS)
