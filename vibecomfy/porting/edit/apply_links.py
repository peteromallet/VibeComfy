from __future__ import annotations

from typing import Any, Mapping

from .ledger import EditLedger, ScopeState
from vibecomfy.porting.edit.apply_slots import _find_named_slot_index
from vibecomfy.porting.edit.apply_types import ResolvedLinkRewire, _issue
from vibecomfy.porting.endpoint_invariant import (
    SOURCE_SLOT_OUT_OF_BOUNDS,
    TARGET_SLOT_OUT_OF_BOUNDS,
    UNDECLARED_SYNTHETIC_PORT,
    dynamic_port_authorized,
    named_socket_index,
)
from vibecomfy.porting.object_info.consume import output_names as cached_output_names
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.schema import schema_for


def _link_ids(links: list[Any]) -> tuple[int, ...]:
    return tuple(sorted(link_id for link in links if (link_id := _link_id(link)) is not None))


def _collect_links_for_origin(scope_graph: Mapping[str, Any], node_id: int) -> list[Any]:
    links = scope_graph.get("links")
    if not isinstance(links, list):
        return []
    return [link for link in links if _link_endpoints(link)[0] == node_id]


def _collect_links_for_target(scope_graph: Mapping[str, Any], node_id: int) -> list[Any]:
    links = scope_graph.get("links")
    if not isinstance(links, list):
        return []
    return [link for link in links if _link_endpoints(link)[2] == node_id]


def _build_rewires(
    scope_path: str,
    links: list[Any],
    *,
    old_origin_id: int,
    new_origin_id: int,
    new_origin_slot: int,
) -> tuple[ResolvedLinkRewire, ...]:
    return tuple(
        ResolvedLinkRewire(
            scope_path=scope_path,
            link_id=link_id,
            old_origin_id=old_origin_id,
            new_origin_id=new_origin_id,
            new_origin_slot=new_origin_slot,
        )
        for link in links
        if (link_id := _link_id(link)) is not None
    )


def _build_rewires_for_setnode_gets(
    scope_graph: Mapping[str, Any],
    set_node: Mapping[str, Any],
    scope_path: str,
    source: tuple[int, int],
) -> tuple[ResolvedLinkRewire, ...]:
    name = _helper_broadcast_name(set_node)
    if not name:
        return ()
    rewires: list[ResolvedLinkRewire] = []
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return ()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or node.get("class_type") or "") != "GetNode":
            continue
        if _helper_broadcast_name(node) != name:
            continue
        get_id = node.get("id")
        if not isinstance(get_id, int):
            continue
        rewires.extend(
            _build_rewires(
                scope_path,
                _collect_links_for_origin(scope_graph, get_id),
                old_origin_id=get_id,
                new_origin_id=source[0],
                new_origin_slot=source[1],
            )
        )
    return tuple(rewires)


def _resolve_getnode_source(
    scope_graph: Mapping[str, Any],
    node: Mapping[str, Any],
    scope_path: str,
) -> tuple[tuple[int, int] | None, list[PortIssue]]:
    name = _helper_broadcast_name(node)
    if not name:
        return None, []
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return None, []
    matches = [
        candidate
        for candidate in nodes
        if isinstance(candidate, dict)
        and str(candidate.get("type") or candidate.get("class_type") or "") == "SetNode"
        and _helper_broadcast_name(candidate) == name
    ]
    if len(matches) > 1:
        return None, [
            _issue(
                "remove_node_getnode_ambiguous_source",
                "GetNode remove_node passthrough requires exactly one matching SetNode source.",
                detail={
                    "scope_path": scope_path,
                    "channel": name,
                    "matching_set_node_ids": [candidate.get("id") for candidate in matches],
                },
            )
        ]
    if len(matches) != 1:
        return None, []
    set_id = matches[0].get("id")
    if not isinstance(set_id, int):
        return None, []
    return _resolve_passthrough_source(scope_graph, set_id, scope_path)


def _resolve_passthrough_source(
    scope_graph: Mapping[str, Any],
    node_id: int,
    scope_path: str,
    *,
    visited: frozenset[int] = frozenset(),
) -> tuple[tuple[int, int] | None, list[PortIssue]]:
    if node_id in visited:
        return None, []
    inbound_links = _collect_links_for_target(scope_graph, node_id)
    if not inbound_links:
        return None, []
    if len(inbound_links) > 1:
        node = _node_by_id(scope_graph, node_id)
        class_type = str(node.get("type") or node.get("class_type") or "") if isinstance(node, dict) else ""
        return None, [
            _issue(
                "remove_node_helper_fan_in_unsupported",
                f"{class_type or 'Helper'} remove_node passthrough only supports a single inbound source.",
                detail={
                    "scope_path": scope_path,
                    "node_id": node_id,
                    "class_type": class_type,
                    "inbound_link_ids": list(_link_ids(inbound_links)),
                },
            )
        ]
    origin_id, origin_slot, _, _ = _link_endpoints(inbound_links[0])
    if not isinstance(origin_id, int):
        return None, []
    origin_node = _node_by_id(scope_graph, origin_id)
    origin_class = str(origin_node.get("type") or origin_node.get("class_type") or "") if isinstance(origin_node, dict) else ""
    if origin_class == "Reroute":
        return _resolve_passthrough_source(scope_graph, origin_id, scope_path, visited=visited | {node_id})
    if origin_class == "GetNode":
        return _resolve_getnode_source(scope_graph, origin_node, scope_path)
    if origin_class == "SetNode":
        return _resolve_passthrough_source(scope_graph, origin_id, scope_path, visited=visited | {node_id})
    return (origin_id, origin_slot or 0), []


def _helper_broadcast_name(node: Mapping[str, Any]) -> str | None:
    widgets_values = node.get("widgets_values")
    if isinstance(widgets_values, list) and widgets_values:
        name = widgets_values[0]
        if isinstance(name, str) and name:
            return name
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        value = inputs.get("widget_0") or inputs.get("name")
        if isinstance(value, str) and value:
            return value
    return None


def _remove_link_from_scope(ledger: EditLedger, *, scope_path: str, link_id: int) -> bool:
    scope = ledger.scopes[scope_path]
    links = scope.graph.get("links")
    if not isinstance(links, list):
        return False
    for index, link in enumerate(list(links)):
        if _link_id(link) != link_id:
            continue
        links.pop(index)
        origin_id, origin_slot, target_id, target_slot = _link_endpoints(link)
        if isinstance(origin_id, int):
            _remove_output_link_reference(scope.graph, origin_id, origin_slot, link_id)
        if isinstance(target_id, int):
            _clear_input_link_reference(scope.graph, target_id, target_slot, link_id)
        ledger.link_index.pop((scope_path, link_id), None)
        return True
    return False


def _link_ids_targeting_input(
    scope: ScopeState,
    target_node_id: int,
    target_slot: int,
) -> list[int]:
    links = scope.graph.get("links")
    if not isinstance(links, list):
        return []
    link_ids: list[int] = []
    for link in links:
        link_id = _link_id(link)
        _, _, found_target_id, found_target_slot = _link_endpoints(link)
        if (
            isinstance(link_id, int)
            and found_target_id == target_node_id
            and found_target_slot == target_slot
        ):
            link_ids.append(link_id)
    return link_ids


def _rewire_link_origin(
    ledger: EditLedger,
    *,
    scope_path: str,
    link_id: int,
    old_origin_id: int,
    new_origin_id: int,
    new_origin_slot: int,
) -> bool:
    scope = ledger.scopes[scope_path]
    links = scope.graph.get("links")
    if not isinstance(links, list):
        return False
    for link in links:
        if _link_id(link) != link_id:
            continue
        old_origin_slot = _link_endpoints(link)[1]
        _remove_output_link_reference(scope.graph, old_origin_id, old_origin_slot, link_id)
        _set_link_origin(link, new_origin_id, new_origin_slot)
        _ensure_output_link_reference(scope.graph, new_origin_id, new_origin_slot, link_id)
        ledger.link_index[(scope_path, link_id)] = link
        return True
    return False


def _set_link_origin(link: Any, node_id: int, slot: int) -> None:
    if isinstance(link, Mapping):
        link["origin_id"] = node_id
        link["origin_slot"] = slot
        return
    if isinstance(link, list) and len(link) >= 3:
        link[1] = node_id
        link[2] = slot


def _new_link_for_scope(
    scope: ScopeState,
    *,
    link_id: int,
    origin_id: int,
    origin_slot: int,
    target_id: int,
    target_slot: int,
    link_type: str,
) -> Any:
    if _scope_uses_dict_links(scope):
        return {
            "id": link_id,
            "origin_id": origin_id,
            "origin_slot": origin_slot,
            "target_id": target_id,
            "target_slot": target_slot,
            "type": link_type,
        }
    return [link_id, origin_id, origin_slot, target_id, target_slot, link_type]


def _scope_uses_dict_links(scope: ScopeState) -> bool:
    links = scope.graph.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, Mapping):
                return True
            if isinstance(link, list):
                return False
    return scope.kind == "subgraph"


def _ensure_input_slot(
    node: Mapping[str, Any],
    input_name: str,
    socket_type: str | None,
    *,
    schema: Any = None,
    fields: Mapping[str, Any] | None = None,
) -> tuple[int | None, list[PortIssue]]:
    if not isinstance(node, dict):
        return None, [
            _issue(
                UNDECLARED_SYNTHETIC_PORT,
                f"Cannot materialize input {input_name!r} on a non-object node.",
                detail={"input": input_name},
            )
        ]
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        inputs = []
        node["inputs"] = inputs
    index = _find_named_slot_index(inputs, input_name)
    if index is not None:
        return index, []
    class_type = str(node.get("type") or node.get("class_type") or "")
    authorized, reason = dynamic_port_authorized(
        class_type,
        "input",
        input_name,
        node=node,
        fields=fields,
        schema=schema,
    )
    if not authorized:
        return None, [
            _issue(
                reason or UNDECLARED_SYNTHETIC_PORT,
                f"{class_type or 'Node'} does not declare input {input_name!r}.",
                detail={"class_type": class_type, "input": input_name},
            )
        ]
    helper_index = named_socket_index(inputs, "") if class_type in {"Reroute", "PrimitiveNode"} else None
    if helper_index is not None and class_type == "Reroute":
        return helper_index, []
    inputs.append({"name": input_name, "type": socket_type or "*", "link": None})
    return len(inputs) - 1, []


def _set_input_link_reference(node: Mapping[str, Any], slot_index: int, link_id: int) -> list[PortIssue]:
    if not isinstance(node, dict):
        return [
            _issue(
                TARGET_SLOT_OUT_OF_BOUNDS,
                "Cannot write an input link reference on a non-object node.",
                detail={"slot_index": slot_index, "link_id": link_id},
            )
        ]
    inputs = node.get("inputs")
    if not isinstance(inputs, list) or not (0 <= slot_index < len(inputs)):
        class_type = str(node.get("type") or node.get("class_type") or "")
        return [
            _issue(
                TARGET_SLOT_OUT_OF_BOUNDS,
                f"{class_type or 'Node'} input slot {slot_index} is outside working inputs.",
                detail={
                    "class_type": class_type,
                    "slot_index": slot_index,
                    "link_id": link_id,
                    "working_count": len(inputs) if isinstance(inputs, list) else 0,
                },
            )
        ]
    slot = inputs[slot_index]
    if isinstance(slot, dict):
        slot["link"] = link_id
    return []


def _ensure_output_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int,
    link_id: int,
) -> list[PortIssue]:
    node = _node_by_id(scope_graph, node_id)
    if node is None:
        return [
            _issue(
                SOURCE_SLOT_OUT_OF_BOUNDS,
                f"Cannot write an output link reference; node {node_id} is missing.",
                detail={"node_id": node_id, "slot_index": slot_index, "link_id": link_id},
            )
        ]
    outputs = node.get("outputs")
    if not isinstance(outputs, list) or not (0 <= slot_index < len(outputs)):
        class_type = str(node.get("type") or node.get("class_type") or "")
        return [
            _issue(
                SOURCE_SLOT_OUT_OF_BOUNDS,
                f"{class_type or 'Node'} output slot {slot_index} is outside working outputs.",
                detail={
                    "class_type": class_type,
                    "node_id": node_id,
                    "slot_index": slot_index,
                    "link_id": link_id,
                    "working_count": len(outputs) if isinstance(outputs, list) else 0,
                },
            )
        ]
    output = outputs[slot_index]
    if not isinstance(output, dict):
        return [
            _issue(
                SOURCE_SLOT_OUT_OF_BOUNDS,
                f"Output slot {slot_index} on node {node_id} is not a socket object.",
                detail={"node_id": node_id, "slot_index": slot_index, "link_id": link_id},
            )
        ]
    links = output.get("links")
    if not isinstance(links, list):
        links = []
        output["links"] = links
    if link_id not in links:
        links.append(link_id)
    return []


def _sync_scope_counters(ledger: EditLedger) -> None:
    for scope in ledger.scopes.values():
        if scope.kind == "root":
            scope.graph["last_node_id"] = max(scope.node_counter, max(scope.used_node_ids, default=0))
            scope.graph["last_link_id"] = max(scope.link_counter, max(scope.used_link_ids, default=0))
            continue
        state = scope.graph.get("state")
        if not isinstance(state, dict):
            state = {}
            scope.graph["state"] = state
        state["lastNodeId"] = max(scope.node_counter, max(scope.used_node_ids, default=0))
        state["lastLinkId"] = max(scope.link_counter, max(scope.used_link_ids, default=0))


def _link_id(link: Any) -> int | None:
    if isinstance(link, Mapping):
        return link.get("id") if isinstance(link.get("id"), int) else None
    if isinstance(link, list) and link and isinstance(link[0], int):
        return link[0]
    return None


def _link_endpoints(link: Any) -> tuple[int | None, int | None, int | None, int | None]:
    if isinstance(link, Mapping):
        return (
            link.get("origin_id") if isinstance(link.get("origin_id"), int) else None,
            link.get("origin_slot") if isinstance(link.get("origin_slot"), int) else None,
            link.get("target_id") if isinstance(link.get("target_id"), int) else None,
            link.get("target_slot") if isinstance(link.get("target_slot"), int) else None,
        )
    if (
        isinstance(link, list)
        and len(link) >= 5
        and isinstance(link[1], int)
        and isinstance(link[2], int)
        and isinstance(link[3], int)
        and isinstance(link[4], int)
    ):
        return link[1], link[2], link[3], link[4]
    return None, None, None, None


def _node_by_id(scope_graph: Mapping[str, Any], node_id: int) -> dict[str, Any] | None:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    return None


def _remove_node_from_scope(scope_graph: Mapping[str, Any], node_id: int) -> bool:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return False
    for index, node in enumerate(list(nodes)):
        if isinstance(node, dict) and node.get("id") == node_id:
            nodes.pop(index)
            return True
    return False


def _remove_output_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int | None,
    link_id: int,
) -> None:
    if slot_index is None:
        return
    node = _node_by_id(scope_graph, node_id)
    if node is None:
        return
    outputs = node.get("outputs")
    if not isinstance(outputs, list) or not (0 <= slot_index < len(outputs)):
        return
    output = outputs[slot_index]
    if not isinstance(output, dict):
        return
    links = output.get("links")
    if not isinstance(links, list):
        return
    output["links"] = [item for item in links if item != link_id]


def _clear_input_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int | None,
    link_id: int,
) -> None:
    if slot_index is None:
        return
    node = _node_by_id(scope_graph, node_id)
    if node is None:
        return
    inputs = node.get("inputs")
    if not isinstance(inputs, list) or not (0 <= slot_index < len(inputs)):
        return
    input_slot = inputs[slot_index]
    if isinstance(input_slot, dict) and input_slot.get("link") == link_id:
        input_slot["link"] = None


def _schema_output_type(
    schema_provider: Any,
    class_type: str,
    slot_index: int | None,
    slot_name: str,
) -> str | None:
    schema = schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    if slot_index is not None and 0 <= slot_index < len(outputs):
        return _normalize_type(getattr(outputs[slot_index], "type", None))
    for output in outputs:
        if getattr(output, "name", None) == slot_name:
            return _normalize_type(getattr(output, "type", None))
    cached_names = cached_output_names(class_type)
    if slot_index is not None and slot_index < len(cached_names):
        return _normalize_type(cached_names[slot_index])
    return None
