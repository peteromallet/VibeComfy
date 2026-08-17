from __future__ import annotations

from vibecomfy.ingest.door_access import door_get_links, door_get_nodes, door_get_widgets_values
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from vibecomfy.porting.widgets.compact_resolver import (
    compact_widget_names_for_node,
    missing_widget_value_sentinel,
    widget_index_for_field,
    widget_value_for_field,
)


NodeId = int | str

_MISSING_WIDGET_VALUE = missing_widget_value_sentinel()
_PRIMITIVE_SOURCE_CLASSES = frozenset(
    {
        "PrimitiveBoolean",
        "PrimitiveFloat",
        "PrimitiveInt",
        "PrimitiveNode",
        "PrimitiveString",
        "PrimitiveStringMultiline",
    }
)
_PASSTHROUGH_SOURCE_CLASSES = frozenset({"Reroute"})


@dataclass(frozen=True, slots=True)
class GraphFieldTarget:
    node_id: NodeId
    field_name: str | None = None
    widget_index: int | None = None

    def __post_init__(self) -> None:
        if self.field_name is None and self.widget_index is None:
            raise ValueError("GraphFieldTarget requires field_name or widget_index")


@dataclass(frozen=True, slots=True)
class LinkedSourceFact:
    node_id: NodeId
    class_type: str | None
    output_slot: int
    field_name: str | None = None
    widget_index: int | None = None
    value: Any = None
    value_known: bool = False
    value_source: str = "unknown"
    outgoing_link_count: int = 0


@dataclass(frozen=True, slots=True)
class EffectiveFieldFact:
    node_id: NodeId
    class_type: str | None
    field_name: str
    widget_index: int | None
    widget_name_source: str | None
    raw_value: Any = None
    raw_value_known: bool = False
    effective_value: Any = None
    effective_value_known: bool = False
    overridden: bool = False
    inert_static_edit: bool = False
    link_id: int | None = None
    source: LinkedSourceFact | None = None


@dataclass(frozen=True, slots=True)
class EffectiveValueChange:
    target: GraphFieldTarget
    before: EffectiveFieldFact
    after: EffectiveFieldFact
    raw_changed: bool | None
    effective_changed: bool | None


@dataclass(frozen=True, slots=True)
class _Edge:
    link_id: int | None
    origin_node: NodeId
    origin_slot: int
    target_node: NodeId
    target_slot: int | None = None
    target_input: str | None = None


@dataclass(frozen=True, slots=True)
class _GraphView:
    nodes_by_id: dict[str, Mapping[str, Any]]
    node_ids_by_key: dict[str, NodeId]
    edges: tuple[_Edge, ...]


def widget_field_name_for_index(
    graph: Mapping[str, Any],
    node_id: NodeId,
    widget_index: int,
    *,
    schema_provider: Any | None = None,
) -> str | None:
    """Return the semantic field name for a compact widget index."""

    view = _graph_view(graph)
    node = _node_for_id(view, node_id)
    if node is None:
        return None
    resolution = compact_widget_names_for_node(node, schema_provider=schema_provider)
    if 0 <= widget_index < len(resolution.names):
        return resolution.names[widget_index]
    return None


def inspect_effective_field(
    graph: Mapping[str, Any],
    target: GraphFieldTarget,
    *,
    schema_provider: Any | None = None,
) -> EffectiveFieldFact:
    """Inspect the raw and effective value for a widget-backed graph field."""

    view = _graph_view(graph)
    node = _node_for_id(view, target.node_id)
    if node is None:
        raise KeyError(f"Unknown node id {target.node_id!r}")

    actual_node_id = _actual_node_id(view, target.node_id)
    class_type = _class_type(node)
    field_name, widget_index, widget_name_source = _resolve_target_field(
        node,
        target,
        schema_provider=schema_provider,
    )
    raw_value, raw_known = _raw_value_for_field(
        node,
        field_name,
        widget_index,
        schema_provider=schema_provider,
    )
    link = _incoming_link_for_field(view, node, actual_node_id, field_name, widget_index)
    if link is None:
        return EffectiveFieldFact(
            node_id=actual_node_id,
            class_type=class_type,
            field_name=field_name,
            widget_index=widget_index,
            widget_name_source=widget_name_source,
            raw_value=raw_value,
            raw_value_known=raw_known,
            effective_value=raw_value,
            effective_value_known=raw_known,
        )

    source = _linked_source_fact(view, link, schema_provider=schema_provider)
    return EffectiveFieldFact(
        node_id=actual_node_id,
        class_type=class_type,
        field_name=field_name,
        widget_index=widget_index,
        widget_name_source=widget_name_source,
        raw_value=raw_value,
        raw_value_known=raw_known,
        effective_value=source.value if source.value_known else None,
        effective_value_known=source.value_known,
        overridden=True,
        inert_static_edit=True,
        link_id=link.link_id,
        source=source,
    )


def compare_effective_field(
    before_graph: Mapping[str, Any],
    after_graph: Mapping[str, Any],
    target: GraphFieldTarget,
    *,
    schema_provider: Any | None = None,
) -> EffectiveValueChange:
    """Compare raw and effective values for the same target in two graphs."""

    before = inspect_effective_field(before_graph, target, schema_provider=schema_provider)
    after = inspect_effective_field(after_graph, target, schema_provider=schema_provider)
    return EffectiveValueChange(
        target=target,
        before=before,
        after=after,
        raw_changed=_known_change(before.raw_value_known, before.raw_value, after.raw_value_known, after.raw_value),
        effective_changed=_known_change(
            before.effective_value_known,
            before.effective_value,
            after.effective_value_known,
            after.effective_value,
        ),
    )


def _graph_view(graph: Mapping[str, Any]) -> _GraphView:
    nodes_by_id: dict[str, Mapping[str, Any]] = {}
    node_ids_by_key: dict[str, NodeId] = {}
    for fallback_id, node in _iter_nodes(graph):
        node_id = _node_id(node, fallback_id)
        key = str(node_id)
        nodes_by_id[key] = node
        node_ids_by_key[key] = node_id

    return _GraphView(
        nodes_by_id=nodes_by_id,
        node_ids_by_key=node_ids_by_key,
        edges=tuple(_iter_edges(graph)),
    )


def _iter_nodes(graph: Mapping[str, Any]) -> list[tuple[NodeId, Mapping[str, Any]]]:
    nodes = door_get_nodes(graph)
    if isinstance(nodes, list):
        return [
            (index, node)
            for index, node in enumerate(nodes)
            if isinstance(node, Mapping)
        ]
    if isinstance(nodes, Mapping):
        return [
            (node_id, node)
            for node_id, node in nodes.items()
            if isinstance(node, Mapping)
        ]
    if all(isinstance(value, Mapping) for value in graph.values()):
        return [
            (node_id, node)
            for node_id, node in graph.items()
            if isinstance(node, Mapping) and ("class_type" in node or "inputs" in node)
        ]
    return []


def _iter_edges(graph: Mapping[str, Any]) -> list[_Edge]:
    edges: list[_Edge] = []

    links = door_get_links(graph)
    if isinstance(links, list):
        for index, link in enumerate(links):
            edge = _edge_from_link(link, index)
            if edge is not None:
                edges.append(edge)

    raw_edges = graph.get("edges")
    if isinstance(raw_edges, list):
        for index, edge in enumerate(raw_edges):
            parsed = _edge_from_vibe_edge(edge, index)
            if parsed is not None:
                edges.append(parsed)

    for target_id, node in _iter_nodes(graph):
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for input_name, value in inputs.items():
            api_link = _api_link_value(value)
            if api_link is None:
                continue
            source_id, output_slot = api_link
            edges.append(
                _Edge(
                    link_id=None,
                    origin_node=source_id,
                    origin_slot=output_slot,
                    target_node=_node_id(node, target_id),
                    target_input=str(input_name),
                )
            )
    return edges


def _edge_from_link(link: Any, index: int) -> _Edge | None:
    if isinstance(link, (list, tuple)):
        if len(link) < 5:
            return None
        return _Edge(
            link_id=_coerce_int(link[0], default=index),
            origin_node=link[1],
            origin_slot=_coerce_int(link[2], default=0),
            target_node=link[3],
            target_slot=_coerce_int(link[4], default=0),
        )
    if not isinstance(link, Mapping):
        return None
    origin = link.get("origin_id", link.get("from_node"))
    target = link.get("target_id", link.get("to_node"))
    if origin is None or target is None:
        return None
    target_input = link.get("to_input")
    return _Edge(
        link_id=_coerce_optional_int(link.get("id", link.get("link_id"))),
        origin_node=origin,
        origin_slot=_coerce_int(link.get("origin_slot", link.get("from_output")), default=0),
        target_node=target,
        target_slot=_coerce_optional_int(link.get("target_slot")),
        target_input=str(target_input) if target_input is not None else None,
    )


def _edge_from_vibe_edge(edge: Any, index: int) -> _Edge | None:
    if not isinstance(edge, Mapping):
        return None
    origin = edge.get("from_node", edge.get("origin_id"))
    target = edge.get("to_node", edge.get("target_id"))
    if origin is None or target is None:
        return None
    target_input = edge.get("to_input")
    return _Edge(
        link_id=_coerce_optional_int(edge.get("id", edge.get("link_id"))) or index,
        origin_node=origin,
        origin_slot=_coerce_int(edge.get("from_output", edge.get("origin_slot")), default=0),
        target_node=target,
        target_slot=_coerce_optional_int(edge.get("target_slot")),
        target_input=str(target_input) if target_input is not None else None,
    )


def _node_for_id(view: _GraphView, node_id: NodeId) -> Mapping[str, Any] | None:
    return view.nodes_by_id.get(str(node_id))


def _actual_node_id(view: _GraphView, node_id: NodeId) -> NodeId:
    return view.node_ids_by_key.get(str(node_id), node_id)


def _node_id(node: Mapping[str, Any], fallback: NodeId) -> NodeId:
    raw = node.get("id", fallback)
    return raw if isinstance(raw, (int, str)) else fallback


def _class_type(node: Mapping[str, Any]) -> str | None:
    raw = node.get("class_type") or node.get("type")
    return str(raw) if isinstance(raw, str) and raw else None


def _resolve_target_field(
    node: Mapping[str, Any],
    target: GraphFieldTarget,
    *,
    schema_provider: Any | None,
) -> tuple[str, int | None, str | None]:
    if target.field_name is not None:
        widget_index = target.widget_index
        if widget_index is None:
            widget_index = widget_index_for_field(
                node,
                target.field_name,
                schema_provider=schema_provider,
            )
        return target.field_name, widget_index, None

    assert target.widget_index is not None
    resolution = compact_widget_names_for_node(node, schema_provider=schema_provider)
    if 0 <= target.widget_index < len(resolution.names):
        return resolution.names[target.widget_index], target.widget_index, resolution.source
    return f"widget_{target.widget_index}", target.widget_index, resolution.source


def _raw_value_for_field(
    node: Mapping[str, Any],
    field_name: str,
    widget_index: int | None,
    *,
    schema_provider: Any | None,
) -> tuple[Any, bool]:
    values = _compact_widget_values(node)
    if widget_index is not None and isinstance(values, list) and 0 <= widget_index < len(values):
        return values[widget_index], True

    value = widget_value_for_field(node, field_name, schema_provider=schema_provider)
    if value is not _MISSING_WIDGET_VALUE:
        return value, True

    inputs = node.get("inputs")
    if isinstance(inputs, Mapping) and field_name in inputs:
        input_value = inputs[field_name]
        if _api_link_value(input_value) is None:
            return input_value, True

    return None, False


def _compact_widget_values(node: Mapping[str, Any]) -> Any:
    values = door_get_widgets_values(node)
    if isinstance(values, (list, Mapping)):
        return values
    widgets = node.get("widgets")
    if isinstance(widgets, Mapping):
        indices = _widget_indices(widgets)
        if indices and indices == list(range(max(indices) + 1)):
            return [widgets[f"widget_{index}"] for index in indices]
        if widgets:
            return widgets
    raw_widgets = node.get("raw_widgets") or node.get("_raw_widgets")
    if isinstance(raw_widgets, Mapping):
        values = raw_widgets.get("values")
        if isinstance(values, list):
            return values
    return None


def _widget_indices(values: Mapping[Any, Any]) -> list[int]:
    indices: list[int] = []
    for key in values:
        text = str(key)
        if not text.startswith("widget_"):
            continue
        suffix = text.split("_", 1)[1]
        if suffix.isdigit():
            indices.append(int(suffix))
    return sorted(indices)


def _incoming_link_for_field(
    view: _GraphView,
    node: Mapping[str, Any],
    node_id: NodeId,
    field_name: str,
    widget_index: int | None,
) -> _Edge | None:
    input_slot = _input_slot_for_field(node, field_name, widget_index)
    if input_slot is not None:
        slot_index, slot_name, link_id, api_link = input_slot
        if api_link is not None:
            source_id, output_slot = api_link
            return _Edge(
                link_id=None,
                origin_node=source_id,
                origin_slot=output_slot,
                target_node=node_id,
                target_slot=slot_index,
                target_input=slot_name,
            )
        if link_id is not None:
            by_id = _edge_by_link_id(view, link_id)
            if by_id is not None:
                return by_id
            return _Edge(
                link_id=link_id,
                origin_node="",
                origin_slot=0,
                target_node=node_id,
                target_slot=slot_index,
                target_input=slot_name,
            )

    for edge in view.edges:
        if str(edge.target_node) != str(node_id):
            continue
        if edge.target_input == field_name:
            return edge
        if input_slot is not None and edge.target_slot == input_slot[0]:
            return edge
    return None


def _input_slot_for_field(
    node: Mapping[str, Any],
    field_name: str,
    widget_index: int | None,
) -> tuple[int | None, str | None, int | None, tuple[NodeId, int] | None] | None:
    inputs = node.get("inputs")
    if isinstance(inputs, Mapping):
        value = inputs.get(field_name)
        if field_name not in inputs:
            return None
        return None, field_name, None, _api_link_value(value)

    if not isinstance(inputs, list):
        return None

    matched_by_widget_index: tuple[int | None, str | None, int | None, tuple[NodeId, int] | None] | None = None
    widget_position = 0
    for slot_index, slot in enumerate(inputs):
        if not isinstance(slot, Mapping):
            continue
        slot_name = _slot_name(slot)
        slot_widget_name = _slot_widget_name(slot)
        link_id = _coerce_optional_int(slot.get("link"))
        api_link = _api_link_value(slot.get("link"))
        candidate = (slot_index, slot_name or slot_widget_name, link_id, api_link)
        if slot_name == field_name or slot_widget_name == field_name:
            return candidate
        if slot_widget_name is not None:
            if widget_index is not None and widget_position == widget_index:
                matched_by_widget_index = candidate
            widget_position += 1
    return matched_by_widget_index


def _edge_by_link_id(view: _GraphView, link_id: int) -> _Edge | None:
    for edge in view.edges:
        if edge.link_id == link_id:
            return edge
    return None


def _linked_source_fact(
    view: _GraphView,
    link: _Edge,
    *,
    schema_provider: Any | None,
) -> LinkedSourceFact:
    return _linked_source_fact_inner(
        view,
        link,
        schema_provider=schema_provider,
        seen=frozenset(),
    )


def _linked_source_fact_inner(
    view: _GraphView,
    link: _Edge,
    *,
    schema_provider: Any | None,
    seen: frozenset[tuple[str, int]],
) -> LinkedSourceFact:
    source_node = _node_for_id(view, link.origin_node)
    if source_node is None:
        return LinkedSourceFact(
            node_id=link.origin_node,
            class_type=None,
            output_slot=link.origin_slot,
        )

    class_type = _class_type(source_node)
    source_key = (str(link.origin_node), link.origin_slot)
    if class_type in _PASSTHROUGH_SOURCE_CLASSES and source_key not in seen:
        upstream_link = _first_incoming_link(view, link.origin_node)
        if upstream_link is not None:
            upstream = _linked_source_fact_inner(
                view,
                upstream_link,
                schema_provider=schema_provider,
                seen=seen | {source_key},
            )
            return replace(
                upstream,
                outgoing_link_count=max(
                    upstream.outgoing_link_count,
                    _outgoing_link_count(view, link.origin_node, link.origin_slot),
                ),
            )

    field_name, widget_index, value, known, source = _static_source_value(
        source_node,
        link.origin_slot,
        schema_provider=schema_provider,
    )
    return LinkedSourceFact(
        node_id=_actual_node_id(view, link.origin_node),
        class_type=class_type,
        output_slot=link.origin_slot,
        field_name=field_name,
        widget_index=widget_index,
        value=value,
        value_known=known,
        value_source=source,
        outgoing_link_count=_outgoing_link_count(view, link.origin_node, link.origin_slot),
    )


def _first_incoming_link(view: _GraphView, node_id: NodeId) -> _Edge | None:
    matches = [
        edge
        for edge in view.edges
        if str(edge.target_node) == str(node_id)
        and (edge.target_slot in (None, 0) or edge.target_input in (None, "", "input"))
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _outgoing_link_count(view: _GraphView, origin_node: NodeId, origin_slot: int) -> int:
    return sum(
        1
        for edge in view.edges
        if str(edge.origin_node) == str(origin_node) and edge.origin_slot == origin_slot
    )


def _static_source_value(
    node: Mapping[str, Any],
    output_slot: int,
    *,
    schema_provider: Any | None,
) -> tuple[str | None, int | None, Any, bool, str]:
    if output_slot != 0:
        return None, None, None, False, "nonzero_output_slot"
    class_type = _class_type(node)
    if class_type not in _PRIMITIVE_SOURCE_CLASSES:
        return None, None, None, False, "source_not_known_constant"

    inputs = node.get("inputs")
    if isinstance(inputs, Mapping):
        if "value" in inputs and _api_link_value(inputs["value"]) is None:
            return "value", None, inputs["value"], True, "primitive_input_value"
        literal_inputs = [
            (str(name), value)
            for name, value in inputs.items()
            if _api_link_value(value) is None
        ]
        if len(literal_inputs) == 1:
            name, value = literal_inputs[0]
            return name, None, value, True, "single_literal_input"

    values = _compact_widget_values(node)
    if isinstance(values, list) and values:
        resolution = compact_widget_names_for_node(
            node,
            schema_provider=schema_provider,
            value_count=len(values),
        )
        names = tuple(resolution.names)
        preferred_index = None
        for index, name in enumerate(names):
            if name == "value":
                preferred_index = index
                break
        if preferred_index is None:
            preferred_index = 0
        if 0 <= preferred_index < len(values):
            field_name = names[preferred_index] if preferred_index < len(names) else f"widget_{preferred_index}"
            return field_name, preferred_index, values[preferred_index], True, "primitive_widget_value"
    if isinstance(values, Mapping):
        if "value" in values:
            return "value", None, values["value"], True, "primitive_widget_mapping_value"
        if len(values) == 1:
            name, value = next(iter(values.items()))
            return str(name), None, value, True, "single_widget_mapping"
    return None, None, None, False, "not_static_constant"


def _api_link_value(value: Any) -> tuple[NodeId, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    source_id, output_slot = value
    if isinstance(output_slot, bool) or not isinstance(output_slot, int):
        return None
    if not isinstance(source_id, (int, str)):
        return None
    return source_id, output_slot


def _slot_name(slot: Mapping[str, Any]) -> str | None:
    name = slot.get("name")
    return str(name) if isinstance(name, str) and name else None


def _slot_widget_name(slot: Mapping[str, Any]) -> str | None:
    widget = slot.get("widget")
    if not isinstance(widget, Mapping):
        return None
    name = widget.get("name")
    return str(name) if isinstance(name, str) and name else None


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _known_change(
    before_known: bool,
    before_value: Any,
    after_known: bool,
    after_value: Any,
) -> bool | None:
    if not before_known or not after_known:
        return None
    try:
        return before_value != after_value
    except Exception:
        return True


__all__ = [
    "EffectiveFieldFact",
    "EffectiveValueChange",
    "GraphFieldTarget",
    "LinkedSourceFact",
    "compare_effective_field",
    "inspect_effective_field",
    "widget_field_name_for_index",
]
