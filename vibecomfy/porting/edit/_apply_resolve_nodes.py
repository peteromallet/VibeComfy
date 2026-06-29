from __future__ import annotations

import re
from typing import Any, Mapping

from ._apply_common import _issue
from ._apply_graph import (
    _collect_links_for_origin,
    _collect_links_for_target,
    _find_named_slot_index,
    _link_endpoints,
    _link_id,
    _link_ids,
    _node_by_id,
)
from ._apply_layout import _group_index_by_title
from ._apply_types import ResolvedAddNodeSpec, ResolvedFieldRef, ResolvedLinkEndpoint, ResolvedLinkRewire, ResolvedNodeRef, ResolvedOp, ResolvedRemoveNodePlan
from .ledger import EditLedger
from .ops import AddNodeOp, AnchorRef, NodeTarget, SetNodeFieldOp
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _find_named_slot, _normalize_type
from vibecomfy.schema import schema_for, socket_types_compatible


def _resolve_remove_node(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    from ._apply_resolve import _resolve_node

    node_ref, issues = _resolve_node(ledger, target)
    if issues:
        return None, issues
    assert node_ref is not None
    node_id = node_ref.node_id if isinstance(node_ref.node_id, int) else None
    if node_id is None:
        return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=()), []

    scope = ledger.scopes[target.scope_path]
    inbound_links = _collect_links_for_target(scope.graph, node_id)
    outbound_links = _collect_links_for_origin(scope.graph, node_id)
    connected_link_ids = tuple(
        sorted(
            {
                link_id
                for link in [*inbound_links, *outbound_links]
                if (link_id := _link_id(link)) is not None
            }
        )
    )

    if node_ref.class_type == "Reroute":
        source, helper_issues = _resolve_passthrough_source(scope.graph, node_id, target.scope_path)
        if helper_issues:
            return None, helper_issues
        if source is None:
            return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []
        rewires = _build_rewires(
            target.scope_path,
            outbound_links,
            old_origin_id=node_id,
            new_origin_id=source[0],
            new_origin_slot=source[1],
        )
        return ResolvedRemoveNodePlan(
            node_ref=node_ref,
            link_ids_to_remove=_link_ids(inbound_links),
            link_rewires=rewires,
        ), []

    if node_ref.class_type == "GetNode":
        source, helper_issues = _resolve_getnode_source(scope.graph, node_ref.node, target.scope_path)
        if helper_issues:
            return None, helper_issues
        if source is None:
            return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []
        rewires = _build_rewires(
            target.scope_path,
            outbound_links,
            old_origin_id=node_id,
            new_origin_id=source[0],
            new_origin_slot=source[1],
        )
        return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=(), link_rewires=rewires), []

    if node_ref.class_type == "SetNode":
        source, helper_issues = _resolve_passthrough_source(scope.graph, node_id, target.scope_path)
        if helper_issues:
            return None, helper_issues
        if source is None:
            return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []
        rewires = _build_rewires_for_setnode_gets(scope.graph, node_ref.node, target.scope_path, source)
        return ResolvedRemoveNodePlan(
            node_ref=node_ref,
            link_ids_to_remove=_link_ids(inbound_links),
            link_rewires=rewires,
        ), []

    return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []


def _resolve_set_node_field(
    ledger: EditLedger,
    op: SetNodeFieldOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    from ._apply_resolve import _resolve_node

    from ._apply_widgets import (
        _validate_literal_value,
        _widget_index_for_field,
        _widget_index_from_input_stubs,
        _widget_name_for_input,
    )

    resolved_node, issues = _resolve_node(ledger, NodeTarget(op.target.scope_path, op.target.uid))
    if issues:
        return None, issues
    assert resolved_node is not None
    if op.target.field_path == "mode":
        return None, [
            _issue(
                "set_mode_requires_set_mode_op",
                "Node mode must be edited with set_mode, not set_node_field.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid},
            )
        ]

    node = resolved_node.node
    class_type = resolved_node.class_type
    input_name = None
    widget_index = None
    automatic_link_removal = None

    schema = schema_for(schema_provider, class_type)
    schema_inputs = getattr(schema, "inputs", {}) or {}
    schema_input = schema_inputs.get(op.target.field_path)

    raw_input = _find_named_slot(node.get("inputs"), op.target.field_path)
    raw_input_index = _find_named_slot_index(node.get("inputs"), op.target.field_path)
    widgets_values = node.get("widgets_values")
    widget_key = op.target.field_path if isinstance(widgets_values, Mapping) and op.target.field_path in widgets_values else None
    if raw_input is not None:
        input_name = op.target.field_path
        if isinstance(raw_input.get("link"), int):
            automatic_link_removal = raw_input["link"]

    widget_index = _widget_index_for_field(class_type, op.target.field_path)
    widget_stub_name = _widget_name_for_input(raw_input)
    used_schema_less_widget_recovery = False
    if widget_index is None and widget_stub_name == op.target.field_path:
        widget_index = _widget_index_from_input_stubs(node.get("inputs"), op.target.field_path)
        used_schema_less_widget_recovery = widget_index is not None
    if widget_index is None and isinstance(widgets_values, list):
        match = re.fullmatch(r"widget_(\d+)", op.target.field_path)
        if match is not None:
            positional_index = int(match.group(1))
            if 0 <= positional_index < len(widgets_values):
                widget_index = positional_index

    if input_name is None and widget_index is None and widget_key is None and schema_input is None:
        return None, [
            _issue(
                "unknown_node_field",
                f"{class_type} does not expose field {op.target.field_path!r}.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "class_type": class_type,
                },
            )
        ]
    if widget_index is None and widget_key is None:
        return None, [
            _issue(
                "non_widget_field_not_editable",
                f"{class_type}.{op.target.field_path} is not editable through set_node_field because it has no widget-backed literal surface.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "class_type": class_type,
                },
            )
        ]

    value_issues = _validate_literal_value(
        value=op.value,
        spec=schema_input,
        class_type=class_type,
        input_name=op.target.field_path,
        context="set_node_field",
    )
    if value_issues:
        return None, value_issues

    resolved_issues = []
    if used_schema_less_widget_recovery:
        resolved_issues.append(
            _issue(
                "schema_less_linked_widget_recovery",
                "Recovered widget position from linked input stubs because schema/object_info widget order was unavailable.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "class_type": class_type,
                    "widget_index": widget_index,
                },
            )
        )
    if automatic_link_removal is not None:
        resolved_issues.append(
            _issue(
                "automatic_link_removal",
                "set_node_field will remove the overriding input link before applying the widget value.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "link_id": automatic_link_removal,
                },
            )
        )
    return (
        ResolvedFieldRef(
            target=op.target,
            node=node,
            class_type=class_type,
            node_id=node.get("id"),
            input_name=input_name,
            input_slot_index=raw_input_index,
            widget_index=widget_index,
            widget_key=widget_key,
            schema_input=schema_input,
            automatic_link_removal=automatic_link_removal,
        ),
        resolved_issues,
    )


def _resolve_add_node(
    ledger: EditLedger,
    op: AddNodeOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    from ._apply_resolve import _resolve_scope
    from ._apply_resolve_links import _resolve_source_endpoint
    from ._apply_widgets import _validate_literal_value

    scope, issues = _resolve_scope(ledger, op.scope_path)
    if issues:
        return None, issues
    assert scope is not None

    schema = schema_for(schema_provider, op.class_type)
    if schema is None:
        return None, [
            _issue(
                "unknown_add_node_class_type",
                f"Unknown class_type {op.class_type!r} for add_node.",
                detail={"scope_path": op.scope_path, "class_type": op.class_type},
            )
        ]

    schema_inputs = getattr(schema, "inputs", {}) or {}
    resolved_issues = []
    for input_name, spec in schema_inputs.items():
        required = bool(getattr(spec, "required", False))
        default = getattr(spec, "default", None)
        if required and input_name not in op.fields and input_name not in op.inputs and default is None:
            resolved_issues.append(
                _issue(
                    "missing_required_add_node_input",
                    f"{op.class_type} requires input {input_name!r} for add_node.",
                    severity="warning",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            )
    for field_name, value in op.fields.items():
        spec = schema_inputs.get(field_name)
        if spec is None:
            resolved_issues.append(
                _issue(
                    "unknown_add_node_field",
                    f"{op.class_type} does not declare field {field_name!r}.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "field": field_name},
                )
            )
            continue
        resolved_issues.extend(
            _validate_literal_value(
                value=value,
                spec=spec,
                class_type=op.class_type,
                input_name=field_name,
                context="add_node",
            )
        )
    if any(issue.severity == "error" for issue in resolved_issues):
        return None, resolved_issues

    resolved_inputs: dict[str, ResolvedLinkEndpoint] = {}
    for input_name, source in op.inputs.items():
        if source.scope_path != op.scope_path:
            return None, [
                _issue(
                    "cross_scope_link_unsupported",
                    "add_node input endpoints must resolve within the same scope.",
                    detail={
                        "from_scope_path": source.scope_path,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                    },
                )
            ]
        spec = schema_inputs.get(input_name)
        if spec is None:
            return None, [
                _issue(
                    "unknown_add_node_input",
                    f"{op.class_type} does not declare input {input_name!r}.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            ]
        source_ref, source_issues = _resolve_source_endpoint(ledger, source, schema_provider=schema_provider)
        if source_issues:
            return None, source_issues
        assert source_ref is not None
        if not isinstance(source_ref.node_id, int):
            return None, [
                _issue(
                    "non_numeric_link_endpoint",
                    "add_node input sources must have numeric LiteGraph node ids.",
                    detail={
                        "from_scope_path": source.scope_path,
                        "from_uid": source.uid,
                        "from_node_id": source_ref.node_id,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                    },
                )
            ]
        target_type = _normalize_type(getattr(spec, "type", None))
        if source_ref.socket_type and target_type and not socket_types_compatible(source_ref.socket_type, target_type):
            return None, [
                _issue(
                    "incompatible_socket_types",
                    f"Cannot connect {source_ref.class_type}.{source_ref.slot_name} ({source_ref.socket_type}) to "
                    f"{op.class_type}.{input_name} ({target_type}).",
                    detail={
                        "from_scope_path": source.scope_path,
                        "from_uid": source.uid,
                        "from_slot": source_ref.slot_name,
                        "from_type": source_ref.socket_type,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                        "to_type": target_type,
                    },
                )
            ]
        resolved_inputs[input_name] = source_ref

    anchor_near = None
    anchor_between = None
    anchor_group_index = None
    anchor_group_title = None
    if op.anchor is not None:
        anchor_near, anchor_between, anchor_group_index, anchor_group_title, anchor_issues = _resolve_add_node_anchor(
            ledger,
            op.scope_path,
            op.anchor,
        )
        if anchor_issues:
            return None, anchor_issues

    return (
        ResolvedAddNodeSpec(
            op=op,
            scope=scope,
            schema=schema,
            schema_inputs=schema_inputs,
            resolved_inputs=resolved_inputs,
            anchor_near=anchor_near,
            anchor_between=anchor_between,
            anchor_group_index=anchor_group_index,
            anchor_group_title=anchor_group_title,
        ),
        list(resolved_issues),
    )


def _resolve_add_node_anchor(
    ledger: EditLedger,
    scope_path: str,
    anchor: AnchorRef,
) -> tuple[
    ResolvedNodeRef | None,
    tuple[ResolvedNodeRef, ResolvedNodeRef] | None,
    int | None,
    str | None,
    list[PortIssue],
]:
    from ._apply_resolve import _resolve_node

    if anchor.group_title is not None:
        group_index = _group_index_by_title(ledger.scopes[scope_path].graph, anchor.group_title)
        if group_index is None:
            return None, None, None, None, [
                _issue(
                    "unknown_group_anchor",
                    f"Unknown group title {anchor.group_title!r} for add_node anchor.",
                    detail={"scope_path": scope_path, "group_title": anchor.group_title},
                )
            ]
    else:
        group_index = None

    near_ref = None
    if anchor.near is not None:
        if anchor.near.scope_path != scope_path:
            return None, None, None, None, [
                _issue(
                    "cross_scope_anchor_unsupported",
                    "add_node anchors must reference nodes in the same scope.",
                    detail={"scope_path": scope_path, "anchor_scope_path": anchor.near.scope_path},
                )
            ]
        near_ref, issues = _resolve_node(ledger, anchor.near)
        if issues:
            return None, None, None, None, issues

    between_ref = None
    if anchor.between is not None:
        resolved: list[ResolvedNodeRef] = []
        for target in anchor.between:
            if target.scope_path != scope_path:
                return None, None, None, None, [
                    _issue(
                        "cross_scope_anchor_unsupported",
                        "add_node anchors must reference nodes in the same scope.",
                        detail={"scope_path": scope_path, "anchor_scope_path": target.scope_path},
                    )
                ]
            node_ref, issues = _resolve_node(ledger, target)
            if issues:
                return None, None, None, None, issues
            assert node_ref is not None
            resolved.append(node_ref)
        between_ref = (resolved[0], resolved[1])

    return near_ref, between_ref, group_index, anchor.group_title, []


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
