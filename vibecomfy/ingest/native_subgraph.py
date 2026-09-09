"""Fail-closed expansion of ComfyUI's native (``-10``/``-20``) subgraphs.

This module deliberately operates on the UI wire format.  It is kept separate
from the canonical normalizer so the expansion can be inspected and tested
without importing ComfyUI or a schema provider.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping


class NativeSubgraphError(ValueError):
    """The bounded native form cannot be expanded without guessing."""


def _fail(message: str) -> None:
    raise NativeSubgraphError(f"native_subgraph_expansion: {message}")


def _id(value: Any) -> str:
    return str(value)


def _walk_values(value: Any):
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


def _link(row: Any) -> tuple[Any, str, int, str, int, Any]:
    if isinstance(row, Mapping):
        required = {"id", "origin_id", "origin_slot", "target_id", "target_slot", "type"}
        if set(row) != required:
            _fail("link record has unexpected fields")
        vals = tuple(row[k] for k in ("id", "origin_id", "origin_slot", "target_id", "target_slot", "type"))
    elif isinstance(row, (list, tuple)) and len(row) == 6:
        vals = tuple(row)
    else:
        _fail("malformed link record")
    if isinstance(vals[2], bool) or isinstance(vals[4], bool):
        _fail("link slots must be integers, not booleans")
    try:
        if isinstance(vals[2], bool) or isinstance(vals[4], bool):
            _fail("link socket slot must be an integer")
        if not isinstance(vals[2], int) or not isinstance(vals[4], int):
            _fail("link socket slot must be an integer")
        return vals[0], _id(vals[1]), vals[2], _id(vals[3]), vals[4], vals[5]
    except (TypeError, ValueError):
        _fail("malformed link endpoint")


def _node_inputs(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = node.get("inputs", [])
    if not isinstance(value, list) or any(not isinstance(x, Mapping) for x in value):
        _fail(f"node {_id(node.get('id'))} has malformed inputs")
    return value


def _node_outputs(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = node.get("outputs", [])
    if not isinstance(value, list) or any(not isinstance(x, Mapping) for x in value):
        _fail(f"node {_id(node.get('id'))} has malformed outputs")
    return value


def _set_socket_links(node: dict[str, Any], incoming: Mapping[int, Any], outgoing: Mapping[int, list[Any]]) -> None:
    for i, socket in enumerate(_node_inputs(node)):
        item = dict(socket)
        item["link"] = incoming.get(i)
        node["inputs"][i] = item
    for i, socket in enumerate(_node_outputs(node)):
        item = dict(socket)
        item["links"] = list(outgoing.get(i, []))
        node["outputs"][i] = item


def _widget_target(definition: Mapping[str, Any], native_link: tuple[Any, str, int, str, int, Any], nodes: Mapping[str, dict[str, Any]]) -> tuple[dict[str, Any], int] | None:
    target = nodes.get(native_link[3])
    if target is None or native_link[4] >= len(_node_inputs(target)):
        _fail("native input points at a missing target socket")
    socket = _node_inputs(target)[native_link[4]]
    widget = socket.get("widget")
    if not isinstance(widget, Mapping) or not isinstance(widget.get("name"), str):
        return None
    name = widget["name"]
    values = target.get("widgets_values", [])
    if not isinstance(values, list):
        _fail(f"node {target.get('id')} has malformed widgets_values")
    # ComfyUI widget metadata is represented by input sockets in the node's
    # positional order.  A linked widget still occupies that position.
    positions = [i for i, s in enumerate(_node_inputs(target)) if isinstance(s.get("widget"), Mapping) and isinstance(s["widget"].get("name"), str)]
    matches = [i for i in positions if _node_inputs(target)[i]["widget"]["name"] == name]
    if len(matches) != 1 or positions.index(matches[0]) >= len(values):
        _fail(f"cannot uniquely locate widget {name!r} on node {target.get('id')}")
    return target, positions.index(matches[0])


def _definition_for(instance: Mapping[str, Any], definitions: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidates = [d for d in definitions if _id(d.get("id", d.get("name"))) == _id(instance.get("type")) or _id(d.get("name")) == _id(instance.get("type"))]
    if len(candidates) > 1:
        _fail(f"ambiguous definition for instance {instance.get('id')}")
    return candidates[0] if candidates else None


def expand_native_subgraphs(raw_ui: Mapping[str, Any]) -> dict[str, Any]:
    """Expand supported native definitions into an ordinary flat UI graph.

    The returned mapping contains ``_native_subgraph_diagnostics`` and
    ``_native_subgraph_provenance``.  No input mapping is mutated.
    """
    if not isinstance(raw_ui, Mapping):
        _fail("UI graph must be a mapping")
    result = deepcopy(dict(raw_ui))
    nodes = result.get("nodes")
    defs_payload = result.get("definitions")
    definitions = defs_payload.get("subgraphs", []) if isinstance(defs_payload, Mapping) else []
    if not isinstance(nodes, list) or not isinstance(definitions, list):
        _fail("expected nodes list and definitions.subgraphs list")
    if not any(_definition_for(n, definitions) is not None for n in nodes if isinstance(n, Mapping)):
        return result
    if any(not isinstance(d, Mapping) for d in definitions):
        _fail("malformed subgraph definition")
    root_links = [_link(x) for x in result.get("links", [])]
    root_by_id = {x[0]: x for x in root_links}
    if len(root_by_id) != len(root_links):
        _fail("duplicate root link id")
    next_link = max([int(x[0]) for x in root_links if isinstance(x[0], int)] + [0]) + 1
    rebuilt_nodes: list[dict[str, Any]] = []
    rebuilt_links: list[tuple[Any, str, int, str, int, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    expanded = False

    for original in nodes:
        if not isinstance(original, Mapping):
            _fail("malformed root node")
        definition = _definition_for(original, definitions)
        if definition is None:
            rebuilt_nodes.append(deepcopy(dict(original)))
            continue
        has_input_marker = "inputNode" in definition
        has_output_marker = "outputNode" in definition
        if not (has_input_marker and has_output_marker):
            # Existing Python-owned definitions remain under the canonical
            # recursive normalizer. A definition that mixes the native
            # sentinel form with missing markers is malformed and must not be
            # silently flattened into a different representation.
            has_native_link = any(
                isinstance(link, Mapping)
                and (str(link.get("origin_id")) in {"-10", "-20"} or str(link.get("target_id")) in {"-10", "-20"})
                for link in definition.get("links", ())
            )
            config_extra = (definition.get("config"), definition.get("extra"))
            has_native_marker = any(
                str(value) in {"-10", "-20"}
                for value in _walk_values(config_extra)
            ) or any(
                isinstance(node, Mapping) and str(node.get("id")) in {"-10", "-20"}
                for node in definition.get("nodes", ())
            )
            if has_input_marker or has_output_marker or has_native_link or has_native_marker:
                _fail("native boundary markers require both inputNode and outputNode")
            rebuilt_nodes.append(deepcopy(dict(original)))
            continue
        expanded = True
        if definition.get("definitions") or not isinstance(definition.get("nodes"), list) or not isinstance(definition.get("links"), list):
            _fail(f"unsupported nested or malformed definition {definition.get('name')!r}")
        inner = { _id(n.get("id")): deepcopy(dict(n)) for n in definition["nodes"] if isinstance(n, Mapping) }
        if len(inner) != len(definition["nodes"]):
            _fail("duplicate or malformed inner node id")
        ns = _id(original.get("id")) + "::"
        renamed = {k: ns + k for k in inner}
        for n in inner.values():
            n["id"] = ns + _id(n.get("id"))
        native = [_link(x) for x in definition["links"]]
        native_by_id = {x[0]: x for x in native}
        if len(native_by_id) != len(native):
            _fail("duplicate definition link id")
        # Public input name -> native boundary link and its target.
        boundary_inputs = definition.get("inputs", [])
        boundary_outputs = definition.get("outputs", [])
        if not isinstance(boundary_inputs, list) or not isinstance(boundary_outputs, list):
            _fail("malformed native boundary roster")
        if not boundary_inputs or not boundary_outputs:
            _fail("native boundary roster is empty")
        out_nodes = {k: inner[k] for k in inner}
        outer_inputs = {str(x.get("name")): x for x in original.get("inputs", []) if isinstance(x, Mapping) and x.get("name") is not None}
        outer_values = original.get("widgets_values", [])
        if not isinstance(outer_values, list):
            _fail("outer instance has malformed widgets_values")
        widget_boundary_indices: list[int] = []
        boundary_targets: dict[int, tuple[str, int]] = {}
        boundary_names: dict[Any, str] = {}
        for entry in boundary_inputs:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("linkIds"), list) or not entry["linkIds"]:
                _fail("ambiguous or malformed native input mapping")
            edges = [native_by_id.get(lid) for lid in entry["linkIds"]]
            if any(edge is None or edge[1] != "-10" for edge in edges):
                _fail(f"input {entry.get('name')!r} is not backed by -10")
            for lid in entry["linkIds"]:
                boundary_names[lid] = str(entry["name"])
            widgets: list[tuple[dict[str, Any], int]] = []
            for lid, edge in zip(entry["linkIds"], edges):
                assert edge is not None
                target = out_nodes.get(edge[3])
                if target is None:
                    _fail("native input target is missing")
                boundary_targets[lid] = (edge[3], edge[4])
                widget = _node_inputs(target)[edge[4]].get("widget")
                if isinstance(widget, Mapping) and isinstance(widget.get("name"), str):
                    info = _widget_target(definition, edge, out_nodes)
                    assert info is not None
                    widgets.append(info)
            if widgets:
                if len(edges) > 1:
                    _fail(f"ambiguous widget boundary for {entry.get('name')!r}")
                widget_boundary_indices.append(len(widget_boundary_indices))
                name = str(entry["name"])
                outer = outer_inputs.get(name)
                source_link = outer.get("link") if outer is not None else None
                if source_link is None:
                    if len(widget_boundary_indices) - 1 >= len(outer_values):
                        _fail(f"missing instance widget for {name!r}")
                    for target_node, target_pos in widgets:
                        target_node.setdefault("widgets_values", [])[target_pos] = deepcopy(outer_values[len(widget_boundary_indices) - 1])
                elif source_link not in root_by_id:
                    _fail(f"outer link {source_link!r} is missing")
        # Rewrite all ordinary inner links and boundary inputs.
        for edge in native:
            if edge[3] != "-20":
                target_node = out_nodes.get(edge[3])
                if target_node is None or edge[4] >= len(_node_inputs(target_node)):
                    _fail("link target_slot is outside input roster")
                target_backlink = _node_inputs(target_node)[edge[4]].get("link")
                if target_backlink not in (None, edge[0]):
                    _fail(f"contradictory input backlink for link {edge[0]!r}")
            if edge[1] == "-10" or edge[3] == "-20":
                continue
            origin_node = out_nodes[edge[1]]
            origin_socket = _node_outputs(origin_node)[edge[2]] if edge[2] < len(_node_outputs(origin_node)) else None
            if origin_socket is None:
                _fail("link origin_slot is outside output roster")
            backlinks = origin_socket.get("links")
            if backlinks is None or edge[0] not in backlinks:
                if backlinks in (None, []):
                    diagnostics.append({"kind": "repaired_output_backlink", "link_id": edge[0], "node_id": edge[1], "slot": edge[2]})
                else:
                    _fail(f"contradictory output backlink for link {edge[0]!r}")
            rebuilt_links.append((edge[0], renamed[edge[1]], edge[2], renamed[edge[3]], edge[4], edge[5]))
        # Root links feeding boundary inputs become links into the namespaced target.
        for lid, (target_id, target_slot) in boundary_targets.items():
            edge = native_by_id[lid]
            outer = outer_inputs.get(boundary_names[lid])
            source_link = outer.get("link") if outer is not None else None
            if source_link is None:
                continue
            source = root_by_id.get(source_link)
            assert source is not None
            rebuilt_links.append((source_link, source[1], source[2], renamed[target_id], target_slot, source[5]))
        # Replace output boundary links at their existing root consumer(s).
        for output_index, entry in enumerate(boundary_outputs):
            if not isinstance(entry, Mapping) or not isinstance(entry.get("linkIds"), list) or len(entry["linkIds"]) > 1:
                _fail("ambiguous or malformed native output mapping")
            if not entry["linkIds"]:
                continue
            lid = entry["linkIds"][0]
            edge = native_by_id.get(lid)
            if edge is None or edge[3] != "-20":
                _fail("output is not backed by -20")
            source_node = out_nodes.get(edge[1])
            if source_node is None or edge[2] >= len(_node_outputs(source_node)):
                _fail("native output source is missing")
            backlinks = _node_outputs(source_node)[edge[2]].get("links")
            if backlinks is None or lid not in backlinks:
                if backlinks in (None, []):
                    diagnostics.append({"kind": "repaired_output_backlink", "link_id": lid, "node_id": edge[1], "slot": edge[2]})
                else:
                    _fail(f"contradictory output backlink for link {lid!r}")
            instance_output_ids = original.get("outputs", [])[output_index].get("links", []) if output_index < len(original.get("outputs", [])) and isinstance(original.get("outputs", [])[output_index], Mapping) else []
            root_consumers = [x for x in root_links if x[0] in instance_output_ids and x[1] == _id(original.get("id"))]
            if not root_consumers:
                root_consumers = [x for x in root_links if x[0] in instance_output_ids]
            source_inner = edge[1]
            for root in root_consumers:
                rebuilt_links.append((root[0], ns + source_inner, edge[2], root[3], root[4], root[5]))
        # Native links must all be accounted for; unknown topology is unsafe.
        allowed = {x[0] for x in native if x[1] != "-10" and x[3] != "-20"}
        if any(x[0] not in allowed and x[1] != "-10" and x[3] != "-20" for x in native):
            _fail("unmapped native link")
        rebuilt_nodes.extend(inner.values())
        diagnostics.append({"kind": "expanded_native_subgraph", "instance_id": _id(original.get("id")), "definition": definition.get("name", definition.get("id"))})

    # Keep non-instance root links, then rebuild all socket backlink records.
    instance_ids = {_id(n.get("id")) for n in nodes if isinstance(n, Mapping) and _definition_for(n, definitions) is not None}
    for edge in root_links:
        if edge[1] in instance_ids or edge[3] in instance_ids:
            continue
        rebuilt_links.append(edge)
    # deterministic ids and endpoint validation
    seen = set()
    final_links = []
    for edge in rebuilt_links:
        if edge[0] in seen:
            edge = (next_link, *edge[1:]); next_link += 1
        seen.add(edge[0]); final_links.append(edge)
    node_map = {_id(n.get("id")): n for n in rebuilt_nodes}
    incoming: dict[str, dict[int, Any]] = {k: {} for k in node_map}
    outgoing: dict[str, dict[int, list[Any]]] = {k: {} for k in node_map}
    for edge in final_links:
        if edge[1] not in node_map or edge[3] not in node_map:
            _fail("expanded link points at a missing node")
        if edge[4] in incoming[edge[3]]:
            _fail("multiple links target one input socket")
        incoming[edge[3]][edge[4]] = edge[0]
        outgoing[edge[1]].setdefault(edge[2], []).append(edge[0])
    for n in rebuilt_nodes:
        _set_socket_links(n, incoming[_id(n["id"])], outgoing[_id(n["id"])])
    result["nodes"] = rebuilt_nodes
    result["links"] = [[a, b, c, d, e, f] for a, b, c, d, e, f in final_links]
    if expanded:
        raw_bytes = json.dumps(raw_ui, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        result["_native_subgraph_provenance"] = {"source_sha256": hashlib.sha256(raw_bytes).hexdigest(), "source_kind": "comfyui_native_subgraph"}
        result["_native_subgraph_diagnostics"] = diagnostics
        result.pop("definitions", None)
    return result


__all__ = ["NativeSubgraphError", "expand_native_subgraphs"]
