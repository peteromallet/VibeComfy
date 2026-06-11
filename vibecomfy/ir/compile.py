from __future__ import annotations

from typing import Any

from vibecomfy._compile import _graph as graph_utils
from vibecomfy._compile import _resolve as helper_resolve
from vibecomfy._compile import _widgets as widget_aliases
from vibecomfy._compile import _helpers as workflow_helpers
from vibecomfy.ir.types import VibeEdge, VibeNode, WorkflowCompileError


def _node_output_type(node: VibeNode | None, output_slot: int | str) -> str | None:
    if node is None:
        return None
    output_types = node.metadata.get("output_types")
    try:
        index = int(str(output_slot))
    except (TypeError, ValueError):
        index = None
    if isinstance(output_types, (list, tuple)) and index is not None and 0 <= index < len(output_types):
        value = output_types[index]
        return str(value) if value is not None else None
    schema = _schema_for_node(node)
    outputs = getattr(schema, "outputs", None) or []
    if index is not None and 0 <= index < len(outputs):
        value = getattr(outputs[index], "type", None)
        return str(value) if value is not None else None
    for output in outputs:
        if getattr(output, "name", None) == output_slot:
            value = getattr(output, "type", None)
            return str(value) if value is not None else None
    return None


def _node_output_names(node: VibeNode) -> list[str | None]:
    output_names = node.metadata.get("output_names")
    if isinstance(output_names, (list, tuple)) and output_names:
        return [str(name) if name is not None else None for name in output_names]
    schema = _schema_for_node(node)
    outputs = getattr(schema, "outputs", None) or []
    return [
        str(getattr(output, "name", "")) if getattr(output, "name", None) else None
        for output in outputs
    ]


def _node_input_type(node: VibeNode | None, input_name: str) -> str | None:
    if node is None:
        return None
    schema = _schema_for_node(node)
    inputs = getattr(schema, "inputs", {}) or {}
    spec = inputs.get(input_name)
    if spec is None:
        return None
    value = getattr(spec, "type", None)
    return str(value) if value is not None else None


def _schema_for_node(node: VibeNode) -> object | None:
    schema = node.metadata.get("schema")
    if schema is not None:
        return schema
    try:
        from vibecomfy.schema import get_authoring_schema_provider

        return get_authoring_schema_provider().get_schema(node.class_type)
    except Exception:
        return None


def _compile_node_inputs(node: VibeNode) -> dict[str, Any]:
    inputs = dict(node.widgets)
    inputs.update(node.inputs)
    _apply_positional_widget_aliases(inputs, node)
    _drop_unused_positional_aliases(inputs)
    return {
        key: value
        for key, value in inputs.items()
        if not _is_ui_only_prompt_input(key, value)
    }


def _normalize_input_aliases(aliases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if aliases is None:
        return ()
    return tuple(str(alias) for alias in aliases)


def _format_available_names(names: Any) -> str:
    values = sorted(str(name) for name in names)
    return ", ".join(repr(value) for value in values) if values else "<none>"


def _is_ui_only_prompt_input(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key == "control_after_generate":
        return True
    if key == "add_noise_to_samples" and value == "":
        return True
    if key in {"videopreview", "preview", "preview_image"} and isinstance(value, dict):
        return True
    return False


def _is_ui_only_node(node: VibeNode) -> bool:
    return workflow_helpers.is_helper_class_type(node.class_type)


def _is_compile_stripped_node(node: VibeNode) -> bool:
    if _is_ui_only_node(node):
        return True
    if not _is_intent_node_class_type(node.class_type):
        return False
    return not _is_runtime_backed_code_intent_node(node)


def _is_intent_node_class_type(class_type: str) -> bool:
    try:
        from vibecomfy.contracts.intent_nodes import is_intent_class_type

        return is_intent_class_type(class_type)
    except Exception:
        return str(class_type) in {
            "vibecomfy.code",
            "vibecomfy.loop",
            "vibecomfy.branch",
            "vibecomfy.workflowref",
        }


def _is_runtime_backed_code_intent_node(node: VibeNode) -> bool:
    try:
        from vibecomfy.contracts.intent_nodes import (
            KIND_TO_CLASS_TYPE,
            intent_node_payload_from_metadata,
            validate_runtime_code_contract,
        )
    except Exception:
        return False
    if node.class_type != KIND_TO_CLASS_TYPE["code"]:
        return False
    payload = intent_node_payload_from_metadata(node.metadata)
    runtime_result = validate_runtime_code_contract(
        class_type=node.class_type,
        payload=payload,
        require_runtime=True,
    )
    return runtime_result.ok


def _compile_intent_runtime_inputs(node: VibeNode) -> dict[str, Any]:
    try:
        from vibecomfy.contracts.intent_nodes import (
            KIND_TO_CLASS_TYPE,
            intent_node_payload_from_metadata,
            validate_intent_node_contract,
            validate_runtime_code_contract,
        )
    except Exception:
        return {}
    if node.class_type != KIND_TO_CLASS_TYPE["code"]:
        return {}
    payload = intent_node_payload_from_metadata(node.metadata)
    runtime_result = validate_runtime_code_contract(
        class_type=node.class_type,
        payload=payload,
        require_runtime=True,
    )
    if not runtime_result.ok or payload is None or runtime_result.normalized is None:
        return {}
    intent_result = validate_intent_node_contract(
        node_id=node.id,
        class_type=node.class_type,
        metadata=node.metadata,
    )
    intent = payload.get("intent")
    intent = intent if isinstance(intent, dict) else {}
    compiled: dict[str, Any] = {
        "runtime_backed": True,
        **runtime_result.normalized.as_dict(),
        "vibecomfy_uid": node.uid or intent_result.vibecomfy_uid,
        "kind": payload.get("kind"),
        "io": payload.get("io"),
    }
    source = intent.get("source")
    spec = intent.get("spec")
    if isinstance(source, str):
        compiled["source"] = source
    if isinstance(spec, str):
        compiled["spec"] = spec
    return compiled


_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)


def _get_node_mode(node: VibeNode) -> int:
    """Read the litegraph mode (0/2/4) from _ui metadata; defaults to 0."""
    ui = node.metadata.get("_ui")
    if not isinstance(ui, dict):
        return 0
    mode = ui.get("mode", 0)
    return mode if isinstance(mode, int) else 0


def _compute_dropped_bypassed_ids(
    nodes: dict[str, VibeNode],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return (dropped_ids, bypassed_ids) for compile(api) mode filtering.

    dropped_ids: node ids with mode 2 (muted) or mode 4 (bypassed) — excluded from output.
    bypassed_ids: subset of dropped_ids with mode 4 — edges are rewired around them.
    """
    dropped: set[str] = set()
    bypassed: set[str] = set()
    for node_id, node in nodes.items():
        mode = _get_node_mode(node)
        if mode in (_MODE_MUTED, _MODE_BYPASS):
            dropped.add(str(node_id))
        if mode == _MODE_BYPASS:
            bypassed.add(str(node_id))
    return frozenset(dropped), frozenset(bypassed)


def _resolve_bypass_edges(
    edges: list[VibeEdge],
    dropped_ids: frozenset[str],
    bypassed_ids: frozenset[str],
) -> list[VibeEdge]:
    """Rewrite the edge list to remove muted/bypassed nodes.

    Mirrors ComfyUI workflow_convert.py _MODE_NEVER/_MODE_BYPASS semantics:
    - Edges targeting any dropped node are removed.
    - Edges sourcing from muted (mode=2) nodes are removed.
    - Edges sourcing from bypassed (mode=4) nodes are resolved to their bypass
      source using same-slot index matching (output slot N maps to the N-th
      incoming edge, or slot 0 if N is out of range).

    Returns edges unchanged when dropped_ids is empty (byte-identical fast path).
    """
    if not dropped_ids:
        return edges

    incoming: dict[str, list[VibeEdge]] = {}
    for edge in edges:
        incoming.setdefault(str(edge.to_node), []).append(edge)

    def _follow(node_id: str, from_out: str, seen: frozenset[str]) -> tuple[str, str] | None:
        if node_id in seen:
            return None
        if node_id not in dropped_ids:
            return (node_id, from_out)
        if node_id not in bypassed_ids:
            return None  # muted: dead end
        try:
            slot = int(from_out)
        except (TypeError, ValueError):
            slot = 0
        feeds = incoming.get(node_id, [])
        if not feeds:
            return None
        feed = feeds[slot] if slot < len(feeds) else feeds[0]
        return _follow(str(feed.from_node), feed.from_output, seen | {node_id})

    result: list[VibeEdge] = []
    for edge in edges:
        from_id = str(edge.from_node)
        to_id = str(edge.to_node)
        if to_id in dropped_ids:
            continue
        if from_id in dropped_ids:
            if from_id not in bypassed_ids:
                continue
            resolved = _follow(from_id, edge.from_output, frozenset())
            if resolved is None:
                continue
            nf, no = resolved
            result.append(VibeEdge(nf, no, edge.to_node, edge.to_input))
        else:
            result.append(edge)
    return result


def _rewrite_broadcast_links(
    inputs: dict[str, Any],
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> dict[str, Any]:
    return {
        key: _resolve_link_value(value, nodes, broadcast_sources)
        for key, value in inputs.items()
    }


def _resolve_edge_source(
    edge: VibeEdge,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> list[Any] | None:
    return helper_resolve.resolve_compile_edge_source(edge, nodes, broadcast_sources)


def _compile_resolved_edge_inputs(
    nodes: dict[str, VibeNode],
    edges: list[VibeEdge],
    broadcast_sources: dict[str, list[Any]],
    *,
    dropped_ids: frozenset[str] = frozenset(),
) -> dict[str, dict[str, list[Any]]]:
    """Build target->input resolved edge mapping shared by compile backends."""
    resolved: dict[str, dict[str, list[Any]]] = {}
    compiled_node_ids = {
        str(node_id)
        for node_id, node in nodes.items()
        if not _is_compile_stripped_node(node) and str(node_id) not in dropped_ids
    }
    for edge in edges:
        target_node_id = str(edge.to_node)
        target_node = nodes.get(target_node_id)
        if target_node is None:
            raise WorkflowCompileError(
                "compiled_edge_missing_endpoint",
                f"Edge target node {target_node_id!r} for input {edge.to_input!r} is missing.",
                detail={"target_node_id": target_node_id, "target_input": edge.to_input},
                next_action="Remove the dangling edge or restore the target node before compiling.",
            )
        if target_node_id not in compiled_node_ids:
            continue
        edge_source = _resolve_compiled_source_ref(
            str(edge.from_node),
            edge.from_output,
            nodes,
            broadcast_sources,
            visited=set(),
            target_node_id=target_node_id,
            target_input=edge.to_input,
        )
        if str(edge_source[0]) not in compiled_node_ids:
            if _can_ignore_compile_stripped_edge(edge, nodes):
                continue
            raise WorkflowCompileError(
                "compiled_edge_missing_endpoint",
                (
                    f"Edge {edge.from_node!r}.{edge.from_output!r} -> "
                    f"{target_node_id!r}.{edge.to_input!r} resolves to stripped or missing "
                    f"source node {edge_source[0]!r}."
                ),
                detail={
                    "source_node_id": str(edge_source[0]),
                    "target_node_id": target_node_id,
                    "target_input": edge.to_input,
                },
                next_action="Reconnect the target input to a runtime node before compiling.",
            )
        resolved.setdefault(target_node_id, {})[edge.to_input] = edge_source
    return resolved


def _can_ignore_compile_stripped_edge(edge: VibeEdge, nodes: dict[str, VibeNode]) -> bool:
    source_node = nodes.get(str(edge.from_node))
    target_node = nodes.get(str(edge.to_node))
    if source_node is None or target_node is None:
        return False
    if not _is_compile_stripped_node(source_node):
        return False
    if _is_ui_only_node(source_node):
        return False
    compiled_inputs = _compile_node_inputs(target_node)
    return str(edge.to_input) in compiled_inputs


def _resolve_compiled_source_ref(
    source_node_id: str,
    source_output: Any,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
    *,
    visited: set[str],
    target_node_id: str,
    target_input: str,
) -> list[Any]:
    source_node = nodes.get(str(source_node_id))
    if source_node is None:
        raise WorkflowCompileError(
            "compiled_edge_missing_endpoint",
            (
                f"Edge source node {source_node_id!r} for "
                f"{target_node_id!r}.{target_input!r} is missing."
            ),
            detail={
                "source_node_id": str(source_node_id),
                "target_node_id": target_node_id,
                "target_input": target_input,
            },
            next_action="Remove the dangling edge or restore the source node before compiling.",
        )

    if not _is_ui_only_node(source_node):
        try:
            output_slot = int(source_output)
        except (TypeError, ValueError) as exc:
            raise WorkflowCompileError(
                "compiled_edge_missing_endpoint",
                (
                    f"Edge source {source_node_id!r}.{source_output!r} for "
                    f"{target_node_id!r}.{target_input!r} has a non-numeric output slot."
                ),
                detail={
                    "source_node_id": str(source_node_id),
                    "source_output": str(source_output),
                    "target_node_id": target_node_id,
                    "target_input": target_input,
                },
                next_action="Use an explicit numeric output slot before compiling.",
            ) from exc
        return [str(source_node_id), output_slot]

    if source_node.class_type in {"Note", "MarkdownNote"}:
        raise WorkflowCompileError(
            "helper_edge_unresolved",
            (
                f"{source_node.class_type} node {source_node_id!r} is compile-stripped "
                f"but feeds runtime input {target_node_id!r}.{target_input!r}."
            ),
            detail={
                "helper_node_id": str(source_node_id),
                "class_type": source_node.class_type,
                "target_node_id": target_node_id,
                "target_input": target_input,
            },
            next_action="Remove the UI-only helper edge or reconnect the input to a runtime node.",
        )

    if source_node_id in visited:
        raise WorkflowCompileError(
            "helper_edge_cycle",
            (
                f"Helper edge cycle while resolving {source_node_id!r} for "
                f"{target_node_id!r}.{target_input!r}."
            ),
            detail={
                "helper_node_id": str(source_node_id),
                "target_node_id": target_node_id,
                "target_input": target_input,
                "visited": sorted(visited),
            },
            next_action="Break the SetNode/GetNode broadcast cycle before compiling.",
        )
    visited.add(source_node_id)

    name = workflow_helpers.broadcast_name(source_node)
    if not name or name not in broadcast_sources:
        raise WorkflowCompileError(
            "helper_edge_unresolved",
            (
                f"{source_node.class_type} node {source_node_id!r} feeding "
                f"{target_node_id!r}.{target_input!r} has no resolved broadcast source."
            ),
            detail={
                "helper_node_id": str(source_node_id),
                "class_type": source_node.class_type,
                "broadcast": name,
                "target_node_id": target_node_id,
                "target_input": target_input,
            },
            next_action="Add a matching SetNode source or reconnect the input to a runtime node.",
        )
    source = broadcast_sources[name]
    return _resolve_compiled_source_ref(
        str(source[0]),
        source[1],
        nodes,
        broadcast_sources,
        visited=visited,
        target_node_id=target_node_id,
        target_input=target_input,
    )


def _resolve_link_value(
    value: Any,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> Any:
    return helper_resolve.resolve_compile_link_value(value, nodes, broadcast_sources)


def _is_api_link(value: Any) -> bool:
    return graph_utils.is_api_link(value, require_numeric_node_id=False, require_int_slot=True)


def _apply_positional_widget_aliases(inputs: dict[str, Any], node: VibeNode) -> None:
    widget_aliases.apply_positional_widget_aliases(
        inputs,
        node.class_type,
        input_aliases=node.metadata.get("input_aliases"),
    )


def _drop_unused_positional_aliases(inputs: dict[str, Any]) -> None:
    for key in list(inputs):
        if key.startswith("unused_"):
            inputs.pop(key, None)
