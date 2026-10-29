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

from vibecomfy.ingest.normalize import (
    canonical_definition_links,
    canonical_definition_nodes,
    door_get_links,
    door_get_nodes,
    door_get_widgets_values,
    door_links,
    door_nodes,
    door_setdefault_links,
    door_setdefault_widgets_values,
)


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
        door_setdefault_links(item, list(outgoing.get(i, [])))
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
    values = door_get_widgets_values(target, [])
    if not isinstance(values, list):
        _fail(f"node {target.get('id')} has malformed widgets_values")
    # ComfyUI widget metadata is represented by input sockets in the node's
    # positional order.  A linked widget still occupies that position.
    positions = [i for i, s in enumerate(_node_inputs(target)) if isinstance(s.get("widget"), Mapping) and isinstance(s["widget"].get("name"), str)]
    matches = [i for i in positions if _node_inputs(target)[i]["widget"]["name"] == name]
    if len(matches) != 1 or positions.index(matches[0]) >= len(values):
        _fail(f"cannot uniquely locate widget {name!r} on node {target.get('id')}")
    return target, positions.index(matches[0])


def _definition_entries(raw: Any) -> list[Mapping[str, Any]]:
    """Return definitions in lexical order, including nested definitions."""
    if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), list):
        entries = raw["subgraphs"]
    elif isinstance(raw, Mapping):
        entries = list(raw.values())
    elif isinstance(raw, (list, tuple)):
        entries = list(raw)
    else:
        return []
    result: list[Mapping[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        result.append(entry)
        result.extend(_definition_entries(entry.get("definitions")))
    return result


def _is_native_definition(definition: Mapping[str, Any]) -> bool:
    """Identify a definition whose boundary is owned by Comfy's native form."""
    links = canonical_definition_links(definition, ()) or ()
    return "inputNode" in definition or "outputNode" in definition or any(
        isinstance(link, Mapping)
        and (str(link.get("origin_id")) in {"-10", "-20"} or str(link.get("target_id")) in {"-10", "-20"})
        for link in links
    ) or any(
        isinstance(link, (list, tuple))
        and len(link) == 6
        and (str(link[1]) in {"-10", "-20"} or str(link[3]) in {"-10", "-20"})
        for link in links
    )


def _definition_for(instance: Mapping[str, Any], definitions: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidates = [d for d in definitions if _id(d.get("id", d.get("name"))) == _id(instance.get("type")) or _id(d.get("name")) == _id(instance.get("type"))]
    if len(candidates) > 1:
        _fail(f"ambiguous definition for instance {instance.get('id')}")
    return candidates[0] if candidates else None


def expand_native_subgraphs(
    raw_ui: Mapping[str, Any],
    *,
    _retain_definitions: bool = False,
    _consumed_definition_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Expand supported native definitions into an ordinary flat UI graph.

    The returned mapping contains ``_native_subgraph_diagnostics`` and
    ``_native_subgraph_provenance``.  No input mapping is mutated.
    """
    if not isinstance(raw_ui, Mapping):
        _fail("UI graph must be a mapping")
    consumed_definition_keys = (
        _consumed_definition_keys
        if _consumed_definition_keys is not None
        else set()
    )
    result = deepcopy(dict(raw_ui))
    nodes = door_get_nodes(result)
    defs_payload = result.get("definitions")
    definitions = _definition_entries(defs_payload)
    if not isinstance(nodes, list) or not isinstance(definitions, list):
        _fail("expected nodes list and definitions.subgraphs list")
    if not any(_definition_for(n, definitions) is not None for n in nodes if isinstance(n, Mapping)):
        return result
    if any(not isinstance(d, Mapping) for d in definitions):
        _fail("malformed subgraph definition")
    root_links = [_link(x) for x in door_get_links(result, [])]
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
                for link in canonical_definition_links(definition, ())
            )
            has_native_marker = any(
                isinstance(node, Mapping) and str(node.get("id")) in {"-10", "-20"}
                for node in canonical_definition_nodes(definition, ())
            )
            if has_input_marker or has_output_marker or has_native_link or has_native_marker:
                _fail("native boundary markers require both inputNode and outputNode")
            rebuilt_nodes.append(deepcopy(dict(original)))
            continue
        expanded = True
        consumed_definition_keys.add(
            str(definition.get("id", definition.get("name")))
        )
        definition_nodes = canonical_definition_nodes(definition)
        definition_links = canonical_definition_links(definition)
        if not isinstance(definition_nodes, list) or not isinstance(definition_links, list):
            _fail(f"malformed definition {definition.get('name')!r}")
        inner = { _id(n.get("id")): deepcopy(dict(n)) for n in definition_nodes if isinstance(n, Mapping) }
        if len(inner) != len(definition_nodes):
            _fail("duplicate or malformed inner node id")
        ns = _id(original.get("id")) + "::"
        renamed = {k: ns + k for k in inner}
        for n in inner.values():
            n["id"] = ns + _id(n.get("id"))
        native = [_link(x) for x in definition_links]
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
        outer_values = door_get_widgets_values(original, [])
        if not isinstance(outer_values, list):
            _fail("outer instance has malformed widgets_values")
        widget_boundaries: list[tuple[str, list[tuple[dict[str, Any], int]]]] = []
        boundary_sockets: dict[str, list[tuple[dict[str, Any], str]]] = {}
        boundary_targets: dict[int, tuple[str, int]] = {}
        boundary_names: dict[Any, str] = {}
        for entry in boundary_inputs:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("linkIds"), list) or not entry["linkIds"]:
                _fail("ambiguous or malformed native input mapping")
            edges = [native_by_id.get(lid) for lid in entry["linkIds"]]
            if any(edge is None or edge[1] != "-10" for edge in edges):
                _fail(f"input {entry.get('name')!r} is not backed by -10")
            if len({edge[2] for edge in edges if edge is not None}) != 1:
                _fail(f"ambiguous native input mapping for {entry.get('name')!r}")
            for lid in entry["linkIds"]:
                boundary_names[lid] = str(entry["name"])
            name = str(entry["name"])
            if name in boundary_sockets:
                _fail(f"duplicate native input name {name!r}")
            boundary_sockets[name] = []
            widgets: list[tuple[dict[str, Any], int]] = []
            for lid, edge in zip(entry["linkIds"], edges):
                assert edge is not None
                target = out_nodes.get(edge[3])
                if target is None:
                    _fail("native input target is missing")
                if edge[4] < 0 or edge[4] >= len(_node_inputs(target)):
                    _fail("native input points at a missing target socket")
                socket = _node_inputs(target)[edge[4]]
                socket_name = socket.get("name")
                if not isinstance(socket_name, str) or not socket_name:
                    _fail("native input target has no socket name")
                boundary_sockets[name].append((target, socket_name))
                boundary_targets[lid] = (edge[3], edge[4])
                widget = socket.get("widget")
                if isinstance(widget, Mapping) and isinstance(widget.get("name"), str):
                    widget_name = widget["name"]
                    if widget_name != socket_name and any(
                        other is not socket and (
                            other.get("name") == widget_name
                            or (isinstance(other.get("widget"), Mapping)
                                and other["widget"].get("name") == widget_name)
                        )
                        for other in _node_inputs(target)
                    ):
                        _fail(f"ambiguous widget alias {widget_name!r} on node {target.get('id')}")
                    if not original.get("widgets_values_named"):
                        info = _widget_target(definition, edge, out_nodes)
                        assert info is not None
                        widgets.append(info)
                    else:
                        # Named instance values do not require guessing the
                        # target widget list position from a partial roster.
                        widgets.append((target, -1))
            outer = outer_inputs.get(name)
            source_link = outer.get("link") if outer is not None else None
            if source_link is not None and source_link not in root_by_id:
                _fail(f"outer link {source_link!r} is missing")
            if widgets:
                # A public input can fan out to multiple widget and ordinary
                # sockets (for example a model filename feeding three
                # loaders, or a prompt feeding a concatenator and a bypass
                # switch).  The common native origin slot check above proves
                # that these are one public value with fan-out, not competing
                # boundary meanings.
                widget_boundaries.append((str(entry["name"]), widgets))
        # Older native serializations carry effective proxy values on the
        # instance.  Newer ones omit that redundant list and retain the
        # authored values on the inner widget nodes.  Consume the instance
        # roster only when it is complete and therefore positionally
        # authoritative; an absent roster is an explicit "use inner values"
        # case, not a missing-widget error.
        named_values = original.get("widgets_values_named")
        if "widgets_values_named" in original and not isinstance(named_values, Mapping):
            _fail("outer instance has malformed widgets_values_named")
        fallback_named: dict[str, Any] = {}
        need_positional = bool(outer_values) and (
            not named_values
            or len(named_values) < len(outer_values)
            or any(name not in named_values for name, _ in widget_boundaries)
        )
        if need_positional:
            proxy_widgets = (
                original.get("properties", {}).get("proxyWidgets")
                if isinstance(original.get("properties"), Mapping)
                else None
            )
            proxy_positions: dict[str, int] = {}
            if isinstance(proxy_widgets, list):
                proxy_positions = {
                    str(item[1]): index
                    for index, item in enumerate(proxy_widgets)
                    if isinstance(item, (list, tuple))
                    and len(item) >= 2
                    and str(item[0]) == "-1"
                    and isinstance(item[1], str)
                }
                if len(proxy_positions) != sum(
                    1
                    for item in proxy_widgets
                    if isinstance(item, (list, tuple))
                    and len(item) >= 2
                    and str(item[0]) == "-1"
                    and isinstance(item[1], str)
                ):
                    _fail("ambiguous native proxy widget roster")
            if proxy_positions:
                if len(outer_values) <= max(proxy_positions.values()):
                    _fail("ambiguous native widget value roster")
                if any(name not in proxy_positions for name, _ in widget_boundaries):
                    _fail("native widget value has no declared proxy identity")
                widget_map = dict(widget_boundaries)
                assignments = [
                    (name, outer_values[proxy_positions[name]], widget_map.get(name, []))
                    for name in boundary_sockets if name in proxy_positions
                ]
            else:
                if len(outer_values) == len(widget_boundaries):
                    assignments = [
                        (name, value, widgets)
                        for value, (name, widgets) in zip(outer_values, widget_boundaries)
                    ]
                elif len(outer_values) == len(boundary_sockets):
                    widget_map = dict(widget_boundaries)
                    assignments = [
                        (name, value, widget_map.get(name, []))
                        for name, value in zip(boundary_sockets, outer_values)
                    ]
                else:
                    _fail("ambiguous native widget value roster")
            for name, value, widgets in assignments:
                if named_values:
                    # A partial named roster overlays the proven positional
                    # roster. Carry fallback values by name rather than
                    # guessing positions in each target's widget list.
                    fallback_named[name] = value
                    continue
                for target_node, target_pos in widgets:
                    target_values = door_setdefault_widgets_values(target_node, [])
                    target_values[target_pos] = deepcopy(value)
                for target_node, socket_name in boundary_sockets[name]:
                    if any(target_node is widget_node for widget_node, _ in widgets):
                        # The widget list already carries this assignment.
                        socket = next((s for s in _node_inputs(target_node) if s.get("name") == socket_name), {})
                        if isinstance(socket.get("widget"), Mapping):
                            target_named = target_node.get("widgets_values_named")
                            widget_name = socket["widget"].get("name")
                            if isinstance(target_named, dict) and widget_name in target_named:
                                target_named[widget_name] = deepcopy(value)
                            if widget_name == socket_name:
                                continue
                    target_named = target_node.setdefault("_native_subgraph_boundary_values", {})
                    if not isinstance(target_named, dict):
                        _fail("target has malformed native boundary values")
                    target_named[socket_name] = deepcopy(value)
        # In nested instances an outer expansion may have supplied additional
        # boundary values; those take precedence over the instance's own
        # authored named/positional values.
        inherited_values = original.get("_native_subgraph_boundary_values", {})
        if not isinstance(inherited_values, Mapping):
            _fail("outer instance has malformed native boundary values")
        effective_named = fallback_named
        effective_named.update(named_values or {})
        effective_named.update(inherited_values)
        for name, sockets in boundary_sockets.items():
            if name not in effective_named:
                continue
            for target_node, socket_name in sockets:
                target_named = target_node.setdefault("_native_subgraph_boundary_values", {})
                if not isinstance(target_named, dict):
                    _fail("target has malformed native boundary values")
                target_named[socket_name] = deepcopy(effective_named[name])
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
            backlinks = door_get_links(origin_socket)
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
            # A graph-level native boundary is a public input marker, not a
            # real executable node.  Once the instance is flattened, retain
            # the inner authored/default value and do not leak ``-10`` into
            # the ordinary UI graph.
            if source[1] in {"-10", "-20"}:
                continue
            rebuilt_links.append((source_link, source[1], source[2], renamed[target_id], target_slot, source[5]))
        # Replace output boundary links at their existing root consumer(s).
        for output_index, entry in enumerate(boundary_outputs):
            if not isinstance(entry, Mapping) or not isinstance(entry.get("linkIds"), list):
                _fail("ambiguous or malformed native output mapping")
            if not entry["linkIds"]:
                continue
            # Some ComfyUI frontend versions serialize one boundary output's
            # link id once per presentation occurrence.  Exact repetition is
            # still one semantic link record and is safe to canonicalize;
            # distinct ids would represent competing sources and remain a
            # fail-closed ambiguity.
            if len(set(entry["linkIds"])) != 1:
                _fail("ambiguous or malformed native output mapping")
            lid = entry["linkIds"][0]
            edge = native_by_id.get(lid)
            if edge is None or edge[3] != "-20":
                _fail("output is not backed by -20")
            source_node = out_nodes.get(edge[1])
            if source_node is None or edge[2] >= len(_node_outputs(source_node)):
                _fail("native output source is missing")
            backlinks = door_get_links(_node_outputs(source_node)[edge[2]])
            if backlinks is None or lid not in backlinks:
                if backlinks in (None, []):
                    diagnostics.append({"kind": "repaired_output_backlink", "link_id": lid, "node_id": edge[1], "slot": edge[2]})
                else:
                    _fail(f"contradictory output backlink for link {lid!r}")
            instance_output = original.get("outputs", [])[output_index] if output_index < len(original.get("outputs", [])) else None
            instance_output_ids = door_get_links(instance_output, []) if isinstance(instance_output, Mapping) else []
            root_consumers = [x for x in root_links if x[0] in instance_output_ids and x[1] == _id(original.get("id"))]
            if not root_consumers:
                root_consumers = [x for x in root_links if x[0] in instance_output_ids]
            source_inner = edge[1]
            for root in root_consumers:
                # A graph-level native output marker is a presentation
                # boundary, not an executable sink in the flattened graph.
                if root[3] in {"-10", "-20"}:
                    continue
                rebuilt_links.append((root[0], ns + source_inner, edge[2], root[3], root[4], root[5]))
        # Native links must all be accounted for; unknown topology is unsafe.
        allowed = {x[0] for x in native if x[1] != "-10" and x[3] != "-20"}
        if any(x[0] not in allowed and x[1] != "-10" and x[3] != "-20" for x in native):
            _fail("unmapped native link")
        rebuilt_nodes.extend(inner.values())
        diagnostics.append({"kind": "expanded_native_subgraph", "instance_id": _id(original.get("id")), "definition": definition.get("name", definition.get("id"))})

    # Keep non-instance root links, then rebuild all socket backlink records.
    instance_ids = {
        _id(n.get("id"))
        for n in nodes
        if isinstance(n, Mapping)
        and (definition := _definition_for(n, definitions)) is not None
        and _is_native_definition(definition)
    }
    for edge in root_links:
        if edge[1] in instance_ids or edge[3] in instance_ids:
            continue
        rebuilt_links.append(edge)
    # deterministic ids and endpoint validation
    seen = set()
    final_links = []
    for edge in rebuilt_links:
        if edge[0] in seen:
            while next_link in seen:
                next_link += 1
            edge = (next_link, *edge[1:]); next_link += 1
        seen.add(edge[0]); final_links.append(edge)
    node_map = {_id(n.get("id")): n for n in rebuilt_nodes}
    incoming: dict[str, dict[int, Any]] = {k: {} for k in node_map}
    outgoing: dict[str, dict[int, list[Any]]] = {k: {} for k in node_map}
    for edge in final_links:
        if edge[1] not in node_map or edge[3] not in node_map:
            _fail(
                f"expanded link points at a missing node: {edge[1]!r}->{edge[3]!r}; "
                f"available nodes={sorted(node_map)}"
            )
        if edge[4] in incoming[edge[3]]:
            _fail("multiple links target one input socket")
        incoming[edge[3]][edge[4]] = edge[0]
        outgoing[edge[1]].setdefault(edge[2], []).append(edge[0])
    for n in rebuilt_nodes:
        _set_socket_links(n, incoming[_id(n["id"])], outgoing[_id(n["id"])])
    door_nodes(result)[:] = rebuilt_nodes
    door_links(result)[:] = [[a, b, c, d, e, f] for a, b, c, d, e, f in final_links]
    if expanded:
        # A supported native definition may contain another native instance.
        # Run the same bounded materializer again over the newly namespaced
        # graph.  Each pass consumes one occurrence layer, so this is
        # terminating for an acyclic finite definition tree; the existing
        # identity/topology checks remain the refusal boundary.
        nested_instances = any(
            isinstance(node, Mapping)
            and (definition := _definition_for(node, definitions)) is not None
            and _is_native_definition(definition)
            for node in rebuilt_nodes
        )
        if nested_instances:
            nested_result = expand_native_subgraphs(
                result,
                _retain_definitions=True,
                _consumed_definition_keys=consumed_definition_keys,
            )
            prior_diagnostics = diagnostics
            nested_diagnostics = nested_result.get("_native_subgraph_diagnostics", [])
            if isinstance(nested_diagnostics, list):
                nested_result["_native_subgraph_diagnostics"] = [
                    *prior_diagnostics,
                    *nested_diagnostics,
                ]
            nested_result["_native_subgraph_provenance"] = {
                "source_sha256": hashlib.sha256(
                    json.dumps(raw_ui, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                ).hexdigest(),
                "source_kind": "comfyui_native_subgraph",
            }
            result = nested_result

        def retain_unconsumed_definitions(raw_definitions: Any) -> Any:
            """Drop only consumed native definitions; preserve safe extras."""
            if isinstance(raw_definitions, Mapping) and isinstance(raw_definitions.get("subgraphs"), list):
                entries = raw_definitions["subgraphs"]
                kept: list[dict[str, Any]] = []
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        _fail("malformed subgraph definition")
                    key = str(entry.get("id", entry.get("name")))
                    if _is_native_definition(entry):
                        if key not in consumed_definition_keys:
                            _fail(f"unused native definition {key!r}")
                        continue
                    item = deepcopy(dict(entry))
                    if "definitions" in item:
                        nested = retain_unconsumed_definitions(item["definitions"])
                        if nested in (None, {}, {"subgraphs": []}):
                            item.pop("definitions", None)
                        else:
                            item["definitions"] = nested
                    kept.append(item)
                return {"subgraphs": kept}
            if isinstance(raw_definitions, Mapping):
                result_mapping: dict[str, Any] = {}
                for name, entry in raw_definitions.items():
                    if not isinstance(entry, Mapping):
                        _fail("malformed subgraph definition")
                    key = str(entry.get("id", entry.get("name", name)))
                    if _is_native_definition(entry):
                        if key not in consumed_definition_keys:
                            _fail(f"unused native definition {key!r}")
                        continue
                    item = deepcopy(dict(entry))
                    if "definitions" in item:
                        nested = retain_unconsumed_definitions(item["definitions"])
                        if nested in (None, {}, {"subgraphs": []}):
                            item.pop("definitions", None)
                        else:
                            item["definitions"] = nested
                    result_mapping[str(name)] = item
                return result_mapping
            if isinstance(raw_definitions, (list, tuple)):
                return retain_unconsumed_definitions({"subgraphs": list(raw_definitions)})
            return raw_definitions

        retained = retain_unconsumed_definitions(result.get("definitions"))
        if retained in (None, {}, {"subgraphs": []}):
            result.pop("definitions", None)
        else:
            result["definitions"] = retained
        if _retain_definitions:
            return result
        raw_bytes = json.dumps(raw_ui, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        result["_native_subgraph_provenance"] = {"source_sha256": hashlib.sha256(raw_bytes).hexdigest(), "source_kind": "comfyui_native_subgraph"}
        result["_native_subgraph_diagnostics"] = diagnostics
        result.pop("definitions", None)
    return result


__all__ = ["NativeSubgraphError", "expand_native_subgraphs"]
