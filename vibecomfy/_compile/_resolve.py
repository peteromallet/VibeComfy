from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from vibecomfy._compile._helpers import (
    PASSTHROUGH_HELPER_CLASS_TYPES,
    RESOLVABLE_HELPER_CLASS_TYPES,
    VALUE_HELPER_CLASS_TYPES,
    HelperDiagnostic,
    broadcast_name,
    collect_broadcast_sources,
    is_api_link,
    is_helper_class_type,
    _node_sort_key,
    _sorted_nodes,
)


_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class ResolveDiagnostics:
    diagnostics: list[HelperDiagnostic] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class HelperResolveErrorSpec:
    message: str
    next_action: str | None = None


class HelperResolveError(RuntimeError):
    def __init__(self, spec: HelperResolveErrorSpec) -> None:
        super().__init__(spec.message)
        self.next_action = spec.next_action


PrimitiveValueExtractor = Callable[[Any, list[HelperDiagnostic]], Any]
ErrorFactory = Callable[[HelperResolveErrorSpec], Exception]


def resolve_helpers(
    nodes: MutableMapping[str, Any],
    edges: list[Any],
    registered_inputs: MutableMapping[str, tuple[str, str]],
    *,
    primitive_value_extractor: PrimitiveValueExtractor | None = None,
    error_factory: ErrorFactory | None = None,
) -> ResolveDiagnostics:
    """Eliminate conversion-resolvable helper nodes from a workflow-like IR.

    The graph traversal and edge-rewrite semantics live here because they are
    independent of Python-template emission.  Callers inject conversion-specific
    primitive coercion and exception types when needed.
    """
    # This function intentionally accepts only detached projection data.  The
    # authored workflow never crosses the helper-lowering boundary.
    edge_list = edges
    replace_edges = lambda value: edge_list.__setitem__(slice(None), value)
    register_input = None
    allow_legacy_ui_widget_update = False

    diagnostics: list[HelperDiagnostic] = []
    make_error = error_factory or (lambda spec: HelperResolveError(spec))
    extract_primitive_value = primitive_value_extractor or _extract_raw_primitive_value

    for _ in range(10_000):
        changed = False
        changed |= _phase_a_broadcasts(nodes, edge_list, make_error)
        changed |= _phase_b_passthroughs(nodes, edge_list, make_error)
        changed |= _phase_c_value_primitives(
            nodes,
            edge_list,
            registered_inputs,
            diagnostics,
            extract_primitive_value,
            make_error,
            register_input,
            allow_legacy_ui_widget_update,
        )
        if not changed:
            break

    for edge in edge_list:
        node = nodes.get(edge.from_node)
        if node is not None and node.class_type in RESOLVABLE_HELPER_CLASS_TYPES:
            raise make_error(
                HelperResolveErrorSpec(
                    f"Helper node {edge.from_node!r} ({node.class_type}) could not be fully resolved",
                    next_action=f"check node {edge.from_node} ({node.class_type})",
                )
            )

    resolved_ids = frozenset(
        nid
        for nid, node in nodes.items()
        if node.class_type in RESOLVABLE_HELPER_CLASS_TYPES
    )
    for nid in resolved_ids:
        nodes.pop(nid)
    replace_edges([
        edge
        for edge in edge_list
        if edge.from_node not in resolved_ids and edge.to_node not in resolved_ids
    ])

    return ResolveDiagnostics(diagnostics=diagnostics)


def resolve_compile_edge_source(
    edge: Any,
    nodes: Mapping[str, Any],
    broadcast_sources: Mapping[str, list[Any]],
) -> list[Any] | None:
    source_node = nodes.get(str(edge.from_node))
    if source_node is None:
        return [str(edge.from_node), _numeric_or_name(edge.from_output)]
    if source_node.class_type in {"GetNode", "SetNode"}:
        name = broadcast_name(source_node)
        if name is None:
            return None
        return broadcast_sources.get(name)
    if is_helper_class_type(source_node.class_type):
        return None
    return [str(edge.from_node), _numeric_or_name(edge.from_output)]


def resolve_compile_link_value(
    value: Any,
    nodes: Mapping[str, Any],
    broadcast_sources: Mapping[str, list[Any]],
) -> Any:
    if not is_api_link(value):
        return value
    source_node = nodes.get(str(value[0]))
    if source_node is None or source_node.class_type not in {"GetNode", "SetNode"}:
        return value
    name = broadcast_name(source_node)
    if name is None:
        return value
    return broadcast_sources.get(name, value)


def _numeric_or_name(value: Any) -> int | str:
    if isinstance(value, bool):
        return str(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _phase_a_broadcasts(nodes: Mapping[str, Any], edges: list[Any], make_error: ErrorFactory) -> bool:
    get_node_ids = frozenset(
        nid for nid, node in nodes.items() if node.class_type == "GetNode"
    )
    set_node_ids = frozenset(
        nid for nid, node in nodes.items() if node.class_type == "SetNode"
    )
    if not get_node_ids and not set_node_ids:
        return False

    broadcast_sources = collect_broadcast_sources(nodes, edges)
    changed = False

    for edge in _sorted_edges(edges):
        if edge.from_node in get_node_ids:
            node = nodes[edge.from_node]
            name = broadcast_name(node)
            if not name:
                raise make_error(
                    HelperResolveErrorSpec(
                        f"GetNode {edge.from_node!r} has no broadcast name",
                        next_action=f"check node {edge.from_node} (GetNode)",
                    )
                )
            if name not in broadcast_sources:
                raise make_error(
                    HelperResolveErrorSpec(
                        f"GetNode {edge.from_node!r} references unresolved broadcast {name!r}; "
                        "no matching SetNode found",
                        next_action=f"check node {edge.from_node} (GetNode)",
                    )
                )
            source = broadcast_sources[name]
            edge.from_node = str(source[0])
            edge.from_output = str(source[1])
            changed = True
        elif edge.from_node in set_node_ids:
            node = nodes[edge.from_node]
            name = broadcast_name(node)
            if not name or name not in broadcast_sources:
                continue
            source = broadcast_sources[name]
            edge.from_node = str(source[0])
            edge.from_output = str(source[1])
            changed = True

    return changed


def _phase_b_passthroughs(nodes: Mapping[str, Any], edges: list[Any], make_error: ErrorFactory) -> bool:
    passthrough_ids = frozenset(
        nid
        for nid, node in nodes.items()
        if node.class_type in PASSTHROUGH_HELPER_CLASS_TYPES
    )
    if not passthrough_ids:
        return False

    inbound: dict[str, list[Any]] = {}
    for edge in edges:
        inbound.setdefault(edge.to_node, []).append(edge)

    changed = False
    folded_edges: list[Any] = []
    for edge in _sorted_edges(edges):
        if edge.from_node not in passthrough_ids:
            continue
        terminal = _resolve_passthrough_terminal(nodes, edge.from_node, inbound, visited=set())
        if terminal is None:
            node = nodes[edge.from_node]
            if node.class_type == "PrimitiveNode":
                _fold_primitive_node_literal(nodes, edge, node)
                folded_edges.append(edge)
                changed = True
                continue
            raise make_error(
                HelperResolveErrorSpec(
                    f"Passthrough node {edge.from_node!r} ({node.class_type}) "
                    "has no resolvable inbound source (dangling passthrough)",
                    next_action=f"check node {edge.from_node} ({node.class_type})",
                )
            )
        edge.from_node = terminal[0]
        edge.from_output = terminal[1]
        changed = True

    if folded_edges:
        edges[:] = [edge for edge in edges if edge not in folded_edges]

    return changed


def _resolve_passthrough_terminal(
    nodes: Mapping[str, Any],
    node_id: str,
    inbound: Mapping[str, list[Any]],
    visited: set[str],
) -> tuple[str, str] | None:
    if node_id in visited:
        return None
    visited.add(node_id)

    inbound_edges = inbound.get(node_id, [])
    if not inbound_edges:
        return None

    inbound_edge = min(
        inbound_edges,
        key=lambda edge: (_node_sort_key(edge.from_node), edge.from_output),
    )
    source_id = inbound_edge.from_node
    source_node = nodes.get(source_id)
    if source_node is None:
        return None

    if source_node.class_type in PASSTHROUGH_HELPER_CLASS_TYPES:
        return _resolve_passthrough_terminal(nodes, source_id, inbound, visited)

    return (source_id, inbound_edge.from_output)


def _fold_primitive_node_literal(nodes: Mapping[str, Any], edge: Any, node: Any) -> None:
    raw_value = node.inputs.get("value") or node.widgets.get("widget_0")
    target_node = nodes.get(edge.to_node)
    if target_node is not None:
        _fold_literal_into_consumer(target_node, edge.to_input, raw_value)


def _phase_c_value_primitives(
    nodes: Mapping[str, Any],
    edges: list[Any],
    registered_inputs: MutableMapping[str, tuple[str, str]],
    diagnostics: list[HelperDiagnostic],
    extract_primitive_value: PrimitiveValueExtractor,
    make_error: ErrorFactory,
    register_input: Callable[..., Any] | None,
    allow_legacy_ui_widget_update: bool,
) -> bool:
    value_prim_ids = frozenset(
        nid
        for nid, node in nodes.items()
        if node.class_type in VALUE_HELPER_CLASS_TYPES
    )
    if not value_prim_ids:
        return False

    broadcast_sources = collect_broadcast_sources(nodes, edges)
    source_to_broadcast_name: dict[str, str] = {}
    for name in sorted(broadcast_sources.keys()):
        source = broadcast_sources[name]
        source_id = str(source[0])
        if source_id not in value_prim_ids:
            continue
        prim_node = nodes.get(source_id)
        if prim_node is None:
            continue
        if not _is_valid_broadcast_name(name, prim_node.class_type):
            continue
        if source_id not in source_to_broadcast_name:
            source_to_broadcast_name[source_id] = name

    changed = False
    for node_id, node in _sorted_nodes(
        {nid: node for nid, node in nodes.items() if nid in value_prim_ids}
    ):
        outbound = _sorted_edges([edge for edge in edges if edge.from_node == node_id])
        if not outbound:
            continue

        real_consumer_edges = [edge for edge in outbound if not _is_resolvable_helper_node(nodes, edge.to_node)]
        literal = extract_primitive_value(node, diagnostics)
        bname = source_to_broadcast_name.get(node_id)

        if bname and len(real_consumer_edges) == 1:
            edge = real_consumer_edges[0]
            consumer_node = nodes.get(edge.to_node)
            if consumer_node is None:
                raise make_error(_missing_consumer_spec(node_id, node.class_type, edge.to_node))
            _fold_literal_into_consumer(
                consumer_node, edge.to_input, literal,
                allow_legacy_ui_widget_update=allow_legacy_ui_widget_update,
            )
            if register_input is not None:
                register_input(
                    bname,
                    edge.to_node,
                    edge.to_input,
                    value=literal,
                    default=literal,
                )
            registered_inputs[bname] = (edge.to_node, edge.to_input)
        else:
            for edge in real_consumer_edges:
                consumer_node = nodes.get(edge.to_node)
                if consumer_node is None:
                    raise make_error(_missing_consumer_spec(node_id, node.class_type, edge.to_node))
                _fold_literal_into_consumer(
                    consumer_node, edge.to_input, literal,
                    allow_legacy_ui_widget_update=allow_legacy_ui_widget_update,
                )

        outbound_obj_ids = frozenset(id(edge) for edge in outbound)
        edges[:] = [edge for edge in edges if id(edge) not in outbound_obj_ids]
        changed = True

    return changed


def _missing_consumer_spec(node_id: str, class_type: str, consumer_id: str) -> HelperResolveErrorSpec:
    return HelperResolveErrorSpec(
        f"Value primitive {node_id!r} ({class_type}) consumer node {consumer_id!r} "
        "not found in workflow",
        next_action=f"check node {node_id} ({class_type})",
    )


def _fold_literal_into_consumer(
    node: Any, field: str, literal: Any, *, allow_legacy_ui_widget_update: bool = False
) -> None:
    field_name = str(field)
    node.inputs[field_name] = literal
    _update_raw_widget_value(node, field_name, literal, allow_legacy_ui_widget_update=allow_legacy_ui_widget_update)


def _update_raw_widget_value(
    node: Any, field: str, literal: Any, *, allow_legacy_ui_widget_update: bool = False
) -> None:
    """Keep IR widget defaults aligned after folding linked widgets.

    ComfyUI represents widget-as-link fields in ``inputs`` but still carries the
    widget's positional default.  Folded Primitive* literals are stored on the
    IR (``node.inputs`` / ``raw_widgets``).  The emit door rebuilds
    ``widgets_values`` from that IR state — this is not an emit-path write.
    """
    index = _widget_index_for_field(node, field)
    if index is None:
        return
    raw_widgets = getattr(node, "raw_widgets", None)
    values = getattr(raw_widgets, "values", None)
    if isinstance(values, list) and index < len(values):
        values[index] = literal
    elif isinstance(values, dict):
        values[field] = literal
    if allow_legacy_ui_widget_update:
        ui = getattr(node, "metadata", {}).get("_ui")
        if isinstance(ui, Mapping) and isinstance(ui.get("widgets_values"), list) and index < len(ui["widgets_values"]):
            ui["widgets_values"][index] = literal


def _widget_index_for_field(node: Any, field: str) -> int | None:
    if field.startswith("widget_"):
        try:
            return int(field.split("_", 1)[1])
        except ValueError:
            return None

    try:
        from vibecomfy._compile._widgets import widget_names_for_class
    except Exception:
        widget_names_for_class = None  # type: ignore[assignment]

    names = widget_names_for_class(str(node.class_type)) if widget_names_for_class else None
    if names and field in names:
        return list(names).index(field)

    aliases = getattr(node, "metadata", {}).get("input_aliases")
    if isinstance(aliases, (list, tuple)) and field in aliases:
        return list(aliases).index(field)

    return None


def _is_resolvable_helper_node(nodes: Mapping[str, Any], node_id: str) -> bool:
    node = nodes.get(node_id)
    return node is not None and node.class_type in RESOLVABLE_HELPER_CLASS_TYPES


def _is_valid_broadcast_name(name: str, primitive_class_type: str) -> bool:
    if not name:
        return False
    if not _NAME_RE.match(name):
        return False
    if name == primitive_class_type:
        return False
    return True


def _extract_raw_primitive_value(node: Any, diagnostics: list[HelperDiagnostic]) -> Any:
    return node.inputs.get("value", node.widgets.get("widget_0"))


def _sorted_edges(edges: Sequence[Any]) -> list[Any]:
    return sorted(
        edges,
        key=lambda edge: (
            _node_sort_key(edge.from_node),
            _node_sort_key(edge.to_node),
            edge.to_input,
        ),
    )


__all__ = [
    "HelperResolveError",
    "HelperResolveErrorSpec",
    "ResolveDiagnostics",
    "resolve_compile_edge_source",
    "resolve_compile_link_value",
    "resolve_helpers",
]
