from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})
BROADCAST_HELPER_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode"})
# Conversion-only: stripped only by the resolver inside port_convert_workflow, never silently
# dropped by generic compile paths (is_helper_class_type / _is_ui_only_node do NOT consult this set).
PASSTHROUGH_HELPER_CLASS_TYPES: frozenset[str] = frozenset({"Reroute", "PrimitiveNode"})
# Conversion-only: stripped only by the resolver inside port_convert_workflow, never silently
# dropped by generic compile paths (is_helper_class_type / _is_ui_only_node do NOT consult this set).
VALUE_HELPER_CLASS_TYPES: frozenset[str] = frozenset(
    {"PrimitiveBoolean", "PrimitiveInt", "PrimitiveFloat", "PrimitiveString", "PrimitiveStringMultiline"}
)
HELPER_CLASS_TYPES: frozenset[str] = UI_ONLY_CLASS_TYPES | BROADCAST_HELPER_CLASS_TYPES
RESOLVABLE_HELPER_CLASS_TYPES: frozenset[str] = (
    BROADCAST_HELPER_CLASS_TYPES | PASSTHROUGH_HELPER_CLASS_TYPES | VALUE_HELPER_CLASS_TYPES
)


@dataclass(frozen=True, slots=True)
class HelperDiagnostic:
    code: str
    message: str
    severity: str = "warning"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def is_ui_only_class_type(class_type: str) -> bool:
    return class_type in UI_ONLY_CLASS_TYPES


def is_broadcast_helper_class_type(class_type: str) -> bool:
    return class_type in BROADCAST_HELPER_CLASS_TYPES


def is_passthrough_helper_class_type(class_type: str) -> bool:
    return class_type in PASSTHROUGH_HELPER_CLASS_TYPES


def is_value_helper_class_type(class_type: str) -> bool:
    return class_type in VALUE_HELPER_CLASS_TYPES


def is_helper_class_type(class_type: str) -> bool:
    return class_type in HELPER_CLASS_TYPES


def helper_stripped_nodes(nodes: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(node_id): node
        for node_id, node in nodes.items()
        if not is_helper_class_type(_node_class_type(node))
    }


def helper_stripped_class_types(nodes: Mapping[str, Any]) -> list[str]:
    return sorted({_node_class_type(node) for node in helper_stripped_nodes(nodes).values()})


def collect_helper_diagnostics(nodes: Mapping[str, Any], edges: Sequence[Any]) -> list[HelperDiagnostic]:
    broadcast_sources = collect_broadcast_sources(nodes, edges)
    diagnostics: list[HelperDiagnostic] = []
    for node_id, node in _sorted_nodes(nodes):
        class_type = _node_class_type(node)
        if class_type in UI_ONLY_CLASS_TYPES:
            diagnostics.append(
                HelperDiagnostic(
                    code="ui_only_node_stripped",
                    message=f"{class_type} node {node_id} is UI-only and will be omitted from runtime prompts.",
                    severity="info",
                    node_id=str(node_id),
                    class_type=class_type,
                )
            )
            continue
        if class_type in PASSTHROUGH_HELPER_CLASS_TYPES:
            diagnostics.append(
                HelperDiagnostic(
                    code="passthrough_helper_source_presence",
                    message=(
                        f"{class_type} node {node_id} is a passthrough helper; "
                        f"expected — will be stripped at conversion."
                    ),
                    severity="info",
                    node_id=str(node_id),
                    class_type=class_type,
                )
            )
            continue
        if class_type in VALUE_HELPER_CLASS_TYPES:
            diagnostics.append(
                HelperDiagnostic(
                    code="value_helper_source_presence",
                    message=(
                        f"{class_type} node {node_id} is a value primitive; "
                        f"expected — will be stripped at conversion."
                    ),
                    severity="info",
                    node_id=str(node_id),
                    class_type=class_type,
                )
            )
            continue
        if class_type not in BROADCAST_HELPER_CLASS_TYPES:
            continue
        name = broadcast_name(node)
        if not name:
            diagnostics.append(
                HelperDiagnostic(
                    code="helper_missing_name",
                    message=f"{class_type} node {node_id} has no broadcast name.",
                    node_id=str(node_id),
                    class_type=class_type,
                )
            )
            continue
        if name in broadcast_sources:
            diagnostics.append(
                HelperDiagnostic(
                    code="helper_broadcast_resolved",
                    message=f"{class_type} node {node_id} broadcast {name!r} resolves to a runtime link.",
                    severity="info",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={"broadcast": name, "source": broadcast_sources[name]},
                )
            )
            continue
        diagnostics.append(
            HelperDiagnostic(
                code="helper_broadcast_unresolved",
                message=f"{class_type} node {node_id} references unresolved broadcast {name!r}.",
                node_id=str(node_id),
                class_type=class_type,
                detail={"broadcast": name},
            )
        )
    return diagnostics


def collect_broadcast_sources(nodes: Mapping[str, Any], edges: Sequence[Any]) -> dict[str, list[Any]]:
    sources: dict[str, list[Any]] = {}
    edge_sources_by_target: dict[str, list[Any]] = {}
    for edge in edges:
        target_node = nodes.get(str(_edge_attr(edge, "to_node")))
        if target_node is None or _node_class_type(target_node) != "SetNode":
            continue
        if _edge_attr(edge, "to_input") == "widget_0":
            continue
        from_output = _edge_attr(edge, "from_output")
        try:
            output_slot = int(from_output)
        except (TypeError, ValueError):
            output_slot = 0
        edge_sources_by_target[str(_edge_attr(edge, "to_node"))] = [str(_edge_attr(edge, "from_node")), output_slot]

    for node_id, node in nodes.items():
        if _node_class_type(node) != "SetNode":
            continue
        name = broadcast_name(node)
        if not name:
            continue
        direct_source = first_link_input(_compile_helper_inputs(node))
        if direct_source is not None:
            sources[name] = direct_source
        elif str(node_id) in edge_sources_by_target:
            sources[name] = edge_sources_by_target[str(node_id)]
    return sources


def broadcast_name(node: Any) -> str | None:
    inputs = _node_inputs(node)
    widgets = _node_widgets(node)
    name = inputs.get("widget_0", widgets.get("widget_0"))
    # Fall back to ``name`` — the emitter writes SetNode/GetNode channel names
    # as ``name=`` kwargs (e.g. ``_node(wf, 'SetNode', ..., name='LATENT')``).
    if name is None:
        name = inputs.get("name")
    if name is None:
        return None
    return str(name)


def first_link_input(inputs: Mapping[str, Any]) -> list[Any] | None:
    for key, value in inputs.items():
        if key == "widget_0":
            continue
        if is_api_link(value):
            return [str(value[0]), int(value[1])]
    return None


def is_api_link(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    if isinstance(value[1], bool) or not isinstance(value[1], int):
        return False
    return True


def _compile_helper_inputs(node: Any) -> dict[str, Any]:
    inputs = dict(_node_widgets(node))
    inputs.update(_node_inputs(node))
    return inputs


def _sorted_nodes(nodes: Mapping[str, Any]) -> list[tuple[str, Any]]:
    return sorted(nodes.items(), key=lambda item: _node_sort_key(item[0]))


def _node_sort_key(node_id: Any) -> tuple[int, str]:
    try:
        return (int(node_id), str(node_id))
    except (TypeError, ValueError):
        return (10**12, str(node_id))


def _node_class_type(node: Any) -> str:
    class_type = getattr(node, "class_type", None)
    if isinstance(class_type, str):
        return class_type
    if isinstance(node, Mapping):
        for key in ("class_type", "type"):
            value = node.get(key)
            if isinstance(value, str):
                return value
    return ""


def _node_inputs(node: Any) -> Mapping[str, Any]:
    inputs = getattr(node, "inputs", None)
    if isinstance(inputs, Mapping):
        return inputs
    if isinstance(node, Mapping):
        value = node.get("inputs")
        if isinstance(value, Mapping):
            return value
    return {}


def _node_widgets(node: Any) -> Mapping[str, Any]:
    widgets = getattr(node, "widgets", None)
    if isinstance(widgets, Mapping):
        return widgets
    if isinstance(node, Mapping):
        value = node.get("widgets")
        if isinstance(value, Mapping):
            return value
    return {}


def _edge_attr(edge: Any, name: str) -> Any:
    if isinstance(edge, Mapping):
        return edge.get(name)
    return getattr(edge, name)


__all__ = [
    "BROADCAST_HELPER_CLASS_TYPES",
    "HELPER_CLASS_TYPES",
    "HelperDiagnostic",
    "PASSTHROUGH_HELPER_CLASS_TYPES",
    "RESOLVABLE_HELPER_CLASS_TYPES",
    "UI_ONLY_CLASS_TYPES",
    "VALUE_HELPER_CLASS_TYPES",
    "_compile_helper_inputs",
    "_edge_attr",
    "_node_class_type",
    "_node_inputs",
    "_node_sort_key",
    "_node_widgets",
    "_sorted_nodes",
    "broadcast_name",
    "collect_broadcast_sources",
    "collect_helper_diagnostics",
    "first_link_input",
    "helper_stripped_class_types",
    "helper_stripped_nodes",
    "is_api_link",
    "is_broadcast_helper_class_type",
    "is_helper_class_type",
    "is_passthrough_helper_class_type",
    "is_ui_only_class_type",
    "is_value_helper_class_type",
]
