"""Resolve helpers within subgraph definitions using the top-level broadcast map.

Mutates raw_workflow subgraph definitions in place by processing their
list-format nodes and dict-format links.
"""

from __future__ import annotations

from typing import Any


def _link_origin_id(link: Any) -> str:
    if isinstance(link, dict):
        return str(link.get("origin_id", ""))
    return str(link[1])


def _link_origin_slot(link: Any) -> int:
    if isinstance(link, dict):
        return int(link.get("origin_slot", 0))
    return int(link[2])


def _link_target_id(link: Any) -> str:
    if isinstance(link, dict):
        return str(link.get("target_id", ""))
    return str(link[3])


def _link_target_slot(link: Any) -> int:
    if isinstance(link, dict):
        return int(link.get("target_slot", 0))
    return int(link[4])


def _set_link_origin(link: Any, node_id: str, slot: int) -> None:
    if isinstance(link, dict):
        link["origin_id"] = int(node_id) if node_id.isdigit() else node_id
        link["origin_slot"] = slot
    else:
        link[1] = int(node_id) if node_id.isdigit() else node_id
        link[2] = slot


RESOLVABLE = frozenset({
    "GetNode", "SetNode", "Reroute", "PrimitiveNode",
    "PrimitiveBoolean", "PrimitiveInt", "PrimitiveFloat",
    "PrimitiveString", "PrimitiveStringMultiline",
})


def resolve_subgraph_helpers(
    raw_workflow: dict[str, Any] | None,
    top_level_nodes: dict[str, Any],
    top_level_edges: list[Any],
    pre_collected_broadcasts: dict[str, list[Any]] | None = None,
) -> None:
    if not raw_workflow:
        return
    defs = raw_workflow.get("definitions")
    if not isinstance(defs, dict):
        return
    subgraphs = defs.get("subgraphs")
    if not isinstance(subgraphs, list):
        return

    if pre_collected_broadcasts is not None:
        top_broadcasts = pre_collected_broadcasts
    else:
        from vibecomfy._compile._helpers import collect_broadcast_sources
        top_broadcasts = collect_broadcast_sources(top_level_nodes, top_level_edges)

    for sg in subgraphs:
        if not isinstance(sg, dict):
            continue
        _resolve_one(sg, top_broadcasts)


def _resolve_one(sg: dict, top_broadcasts: dict) -> None:
    nodes_list = sg.get("nodes")
    if not isinstance(nodes_list, list):
        return
    links_list = sg.get("links")
    if not isinstance(links_list, list):
        links_list = []

    # Build lookup dict for nodes
    nodes_dict: dict[str, dict] = {}
    for n in nodes_list:
        if isinstance(n, dict) and "id" in n:
            nodes_dict[str(n["id"])] = n

    # Fixed-point resolution
    for _ in range(100):
        changed = False
        helper_ids = [
            str(n["id"]) for n in nodes_list
            if isinstance(n, dict) and n.get("type") in RESOLVABLE
        ]
        for nid in helper_ids:
            node = nodes_dict.get(nid)
            if node is None:
                continue
            ct = node.get("type", "")
            if ct == "GetNode":
                changed |= _resolve_getnode(nodes_dict, nodes_list, links_list, nid, node, top_broadcasts)
            elif ct in ("Reroute", "PrimitiveNode"):
                changed |= _resolve_passthrough(nodes_dict, nodes_list, links_list, nid, node)
            elif ct.startswith("Primitive"):
                changed |= _resolve_primitive(nodes_dict, nodes_list, links_list, nid, node)
        if not changed:
            break

    # Sync back
    sg["nodes"] = nodes_list
    sg["links"] = links_list


def _get_widget(n: dict, idx: int = 0) -> Any:
    wv = n.get("widgets_values", [])
    if isinstance(wv, list) and idx < len(wv):
        return wv[idx]
    return None


def _resolve_getnode(
    nodes_dict: dict, nodes_list: list, links_list: list,
    nid: str, node: dict, top_broadcasts: dict,
) -> bool:
    name = _get_widget(node, 0)
    if not name or str(name) not in top_broadcasts:
        return False
    source = top_broadcasts[str(name)]
    sid, sslot = str(source[0]), int(source[1])

    outbound = [l for l in links_list if _link_origin_id(l) == nid]
    for link in outbound:
        _set_link_origin(link, sid, sslot)

    nodes_dict.pop(nid, None)
    nodes_list[:] = [n for n in nodes_list if str(n.get("id", "")) != nid]
    return True


def _resolve_passthrough(
    nodes_dict: dict, nodes_list: list, links_list: list,
    nid: str, node: dict,
) -> bool:
    inbound = [l for l in links_list if _link_target_id(l) == nid]
    if not inbound:
        return False

    sid = _link_origin_id(inbound[0])
    sslot = _link_origin_slot(inbound[0])

    outbound = [l for l in links_list if _link_origin_id(l) == nid]
    for link in outbound:
        _set_link_origin(link, sid, sslot)

    nodes_dict.pop(nid, None)
    nodes_list[:] = [n for n in nodes_list if str(n.get("id", "")) != nid]
    links_list[:] = [l for l in links_list if _link_target_id(l) != nid]
    return True


def _resolve_primitive(
    nodes_dict: dict, nodes_list: list, links_list: list,
    nid: str, node: dict,
) -> bool:
    nodes_dict.pop(nid, None)
    nodes_list[:] = [n for n in nodes_list if str(n.get("id", "")) != nid]
    links_list[:] = [l for l in links_list if _link_origin_id(l) != nid and _link_target_id(l) != nid]
    return True
