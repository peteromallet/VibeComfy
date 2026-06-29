from __future__ import annotations

from typing import Any, Mapping

from .ledger import EditLedger, ScopeState


def _find_named_slot_index(slots: Any, name: str) -> int | None:
    if not isinstance(slots, list):
        return None
    for index, item in enumerate(slots):
        if isinstance(item, dict) and item.get("name") == name:
            return index
    return None


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


def _link_ids(links: list[Any]) -> tuple[int, ...]:
    return tuple(sorted(link_id for link in links if (link_id := _link_id(link)) is not None))


def _links_by_id(links: Any) -> dict[int, Any]:
    if not isinstance(links, list):
        return {}
    result: dict[int, Any] = {}
    for link in links:
        link_id = _link_id(link)
        if link_id is not None:
            result[link_id] = link
    return result


def _scope_uses_dict_links(scope: ScopeState) -> bool:
    links = scope.graph.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, Mapping):
                return True
            if isinstance(link, list):
                return False
    return scope.kind == "subgraph"


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


def _set_link_origin(link: Any, node_id: int, slot: int) -> None:
    if isinstance(link, Mapping):
        link["origin_id"] = node_id
        link["origin_slot"] = slot
        return
    if isinstance(link, list) and len(link) >= 3:
        link[1] = node_id
        link[2] = slot


def _ensure_output_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int,
    link_id: int,
) -> None:
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
        links = []
        output["links"] = links
    if link_id not in links:
        links.append(link_id)


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


def _ensure_input_slot(node: Mapping[str, Any], input_name: str, socket_type: str | None) -> int:
    if not isinstance(node, dict):
        return 0
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        inputs = []
        node["inputs"] = inputs
    index = _find_named_slot_index(inputs, input_name)
    if index is not None:
        return index
    inputs.append({"name": input_name, "type": socket_type or "*", "link": None})
    return len(inputs) - 1


def _set_input_link_reference(node: Mapping[str, Any], slot_index: int, link_id: int) -> None:
    if not isinstance(node, dict):
        return
    inputs = node.get("inputs")
    if not isinstance(inputs, list) or not (0 <= slot_index < len(inputs)):
        return
    slot = inputs[slot_index]
    if isinstance(slot, dict):
        slot["link"] = link_id


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
