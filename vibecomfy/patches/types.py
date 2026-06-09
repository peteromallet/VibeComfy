from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from vibecomfy.origin import stamp_workflow_origin
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True, slots=True)
class _WorkflowSnapshot:
    nodes: dict[str, str]
    values: dict[str, tuple[str, Any, Any]]
    edges: tuple[tuple[str, str, str, str], ...]
    target_sources: dict[tuple[str, str], tuple[str, str]]


def _stable_node_id_key(node_id: str) -> tuple[int, int | str]:
    return (0, int(node_id)) if node_id.isdigit() else (1, node_id)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((str(key), _freeze(item)) for key, item in sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def _edge_sort_key(edge: tuple[str, str, str, str]) -> tuple[tuple[int, int | str], str, tuple[int, int | str], str]:
    from_node, from_output, to_node, to_input = edge
    return (_stable_node_id_key(to_node), to_input, _stable_node_id_key(from_node), from_output)


def _snapshot_workflow(workflow: VibeWorkflow) -> _WorkflowSnapshot:
    nodes = {
        str(node_id): node.class_type
        for node_id, node in sorted(workflow.nodes.items(), key=lambda item: _stable_node_id_key(str(item[0])))
    }
    values = {
        str(node_id): (
            node.class_type,
            _freeze(node.inputs),
            _freeze(node.widgets),
        )
        for node_id, node in sorted(workflow.nodes.items(), key=lambda item: _stable_node_id_key(str(item[0])))
    }
    edges = tuple(
        sorted(
            (
                (str(edge.from_node), str(edge.from_output), str(edge.to_node), str(edge.to_input))
                for edge in workflow.edges
            ),
            key=_edge_sort_key,
        )
    )
    target_sources = {
        (to_node, to_input): (from_node, from_output)
        for from_node, from_output, to_node, to_input in edges
    }
    return _WorkflowSnapshot(nodes=nodes, values=values, edges=edges, target_sources=target_sources)


def _edge_record(edge: tuple[str, str, str, str]) -> dict[str, str]:
    from_node, from_output, to_node, to_input = edge
    return {
        "from_node": from_node,
        "from_output": from_output,
        "to_node": to_node,
        "to_input": to_input,
    }


def _build_patch_application(
    patch_name: str,
    before: _WorkflowSnapshot,
    after: _WorkflowSnapshot,
) -> dict[str, Any]:
    nodes_added = [
        {"node_id": node_id, "class_type": after.nodes[node_id]}
        for node_id in sorted(set(after.nodes) - set(before.nodes), key=_stable_node_id_key)
    ]
    introduced_edges = [
        _edge_record(edge)
        for edge in sorted(set(after.edges) - set(before.edges), key=_edge_sort_key)
    ]
    rewritten_edges = []
    for target in sorted(set(before.target_sources) & set(after.target_sources), key=lambda item: (_stable_node_id_key(item[0]), item[1])):
        previous = before.target_sources[target]
        current = after.target_sources[target]
        if previous == current:
            continue
        rewritten_edges.append(
            {
                "to_node": target[0],
                "to_input": target[1],
                "previous_from_node": previous[0],
                "previous_from_output": previous[1],
                "new_from_node": current[0],
                "new_from_output": current[1],
            }
        )

    entry: dict[str, Any] = {
        "name": patch_name,
        "layer": "patch",
        "called": True,
        "topology_changed": bool(nodes_added or introduced_edges or rewritten_edges),
        "nodes_added": nodes_added,
        "introduced_edges": introduced_edges,
        "rewritten_edges": rewritten_edges,
    }
    if before.values != after.values:
        entry["value_changed"] = True
    return entry


@dataclass(frozen=True, slots=True)
class Patch:
    """A targeted, idempotent decoration of an existing workflow graph.

    A patch adjusts policy or topology on a graph the caller already has: set
    widget/input values, swap compatible node classes, add support nodes, or
    splice into an existing edge. Construction APIs that create a new reusable
    stage and return public handles belong in blocks or ready workflows, not in
    patches. A patch's public result is always the same
    :class:`VibeWorkflow`; it must not introduce a new handle-producing API.

    ``applies_to`` must be a conservative, side-effect-free predicate that is
    safe to call on any workflow and returns true only when ``apply`` can make
    its supported change. ``apply`` must be idempotent for the same workflow:
    repeated calls should not duplicate support nodes, metadata, requirements,
    or edges. Unsupported direct ``apply`` calls should fail clearly rather
    than silently leaving the graph unchanged.
    """

    name: str
    applies_to: Callable[[VibeWorkflow], bool]
    apply: Callable[[VibeWorkflow], VibeWorkflow]
    rationale: Callable[[VibeWorkflow], str]

    def __post_init__(self) -> None:
        original_apply = self.apply
        layer = f"{original_apply.__module__.replace('.', '/')}.py:{self.name}"

        def wrapped_apply(workflow: VibeWorkflow) -> VibeWorkflow:
            before = _snapshot_workflow(workflow)
            result = original_apply(workflow)
            after = _snapshot_workflow(result)
            stamp_workflow_origin(result, "patch", layer)
            result.metadata.setdefault("patch_applications", []).append(
                _build_patch_application(self.name, before, after)
            )
            return result

        object.__setattr__(self, "apply", wrapped_apply)
