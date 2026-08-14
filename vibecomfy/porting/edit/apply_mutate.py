from __future__ import annotations

from typing import Any, Mapping

from .ledger import EditLedger
from .ops import AddNodeOp, EditOp, LinkSourceRef, LinkTargetRef, RemoveLinkOp, RemoveNodeOp, ReorderOp, SetModeOp, SetNodeFieldOp, UpsertLinkOp
from vibecomfy.porting.edit.apply_links import _ensure_input_slot, _ensure_output_link_reference, _link_endpoints, _link_ids_targeting_input, _new_link_for_scope, _remove_link_from_scope, _remove_node_from_scope, _rewire_link_origin, _set_input_link_reference
from vibecomfy.porting.edit.apply_place import _next_node_order, _node_size, _place_add_node
from vibecomfy.porting.edit.apply_slots import _reorder_names, _widget_name_for_input
from vibecomfy.porting.edit.apply_types import AppliedAddNodeSpec, ResolvedAddNodeSpec, ResolvedFieldRef, ResolvedLinkEndpoint, ResolvedNodeRef, ResolvedOp, ResolvedRemoveLinkRef, ResolvedRemoveNodePlan, VALUE_DEFAULT_FIELDS_MARKER, _issue
from vibecomfy.porting.emit.ui import materialize_litegraph_node
from vibecomfy.porting.endpoint_invariant import assert_source_slot_in_bounds
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _find_named_slot, _normalize_type


def _apply_resolved_op(
    ledger: EditLedger,
    op: EditOp,
    resolved_op: ResolvedOp,
) -> tuple[ResolvedOp, list[PortIssue]]:
    if isinstance(op, SetNodeFieldOp):
        assert isinstance(resolved_op, ResolvedFieldRef)
        return resolved_op, _apply_set_node_field(ledger, resolved_op, op.value)
    if isinstance(op, SetModeOp):
        assert isinstance(resolved_op, ResolvedNodeRef)
        _apply_set_mode(resolved_op, op.mode)
        return resolved_op, []
    if isinstance(op, RemoveLinkOp):
        assert isinstance(resolved_op, ResolvedRemoveLinkRef)
        return resolved_op, _apply_remove_link(ledger, resolved_op)
    if isinstance(op, RemoveNodeOp):
        assert isinstance(resolved_op, ResolvedRemoveNodePlan)
        return resolved_op, _apply_remove_node(ledger, resolved_op)
    if isinstance(op, UpsertLinkOp):
        assert isinstance(resolved_op, tuple)
        source, target = resolved_op
        assert isinstance(source, ResolvedLinkEndpoint)
        assert isinstance(target, ResolvedLinkEndpoint)
        return resolved_op, _apply_upsert_link(ledger, source, target)
    if isinstance(op, AddNodeOp):
        assert isinstance(resolved_op, ResolvedAddNodeSpec)
        return _apply_add_node(ledger, resolved_op)
    assert isinstance(op, ReorderOp)
    assert isinstance(resolved_op, ResolvedNodeRef)
    return resolved_op, _apply_reorder(resolved_op, op)


def _apply_set_mode(node_ref: ResolvedNodeRef, mode: int) -> None:
    node = node_ref.node
    if isinstance(node, dict):
        node["mode"] = mode


def _apply_remove_link(
    ledger: EditLedger,
    link_ref: ResolvedRemoveLinkRef,
) -> list[PortIssue]:
    removed = _remove_link_from_scope(
        ledger,
        scope_path=link_ref.scope_path,
        link_id=link_ref.link_id,
    )
    if removed:
        return []
    return [
        _issue(
            "remove_link_missing_at_apply",
            "Resolved link target was already absent by the time mutation applied.",
            severity="warning",
            detail={"scope_path": link_ref.scope_path, "link_id": link_ref.link_id},
        )
    ]


def _apply_remove_node(
    ledger: EditLedger,
    plan: ResolvedRemoveNodePlan,
) -> list[PortIssue]:
    node_ref = plan.node_ref
    node_id = node_ref.node_id if isinstance(node_ref.node_id, int) else None
    if node_id is None:
        return [
            _issue(
                "remove_node_missing_numeric_id",
                "Resolved node has no numeric LiteGraph id, so remove_node could not update link substrate safely.",
                severity="warning",
                detail={
                    "scope_path": node_ref.target.scope_path,
                    "uid": node_ref.target.uid,
                    "class_type": node_ref.class_type,
                },
            )
        ]
    scope = ledger.scopes[node_ref.target.scope_path]
    diagnostics: list[PortIssue] = []
    for rewire in plan.link_rewires:
        _rewire_link_origin(
            ledger,
            scope_path=rewire.scope_path,
            link_id=rewire.link_id,
            old_origin_id=rewire.old_origin_id,
            new_origin_id=rewire.new_origin_id,
            new_origin_slot=rewire.new_origin_slot,
        )
        diagnostics.append(
            _issue(
                "remove_node_passthrough_rewire",
                "remove_node re-stitched a helper passthrough link to its resolved source.",
                severity="info",
                detail={
                    "scope_path": rewire.scope_path,
                    "uid": node_ref.target.uid,
                    "class_type": node_ref.class_type,
                    "removed_node_id": node_id,
                    "link_id": rewire.link_id,
                    "old_origin_id": rewire.old_origin_id,
                    "new_origin_id": rewire.new_origin_id,
                    "new_origin_slot": rewire.new_origin_slot,
                },
            )
        )
    for link_id in plan.link_ids_to_remove:
        link = ledger.link_index.get((node_ref.target.scope_path, link_id))
        origin_id, _, target_id, _ = _link_endpoints(link) if link is not None else (None, None, None, None)
        _remove_link_from_scope(ledger, scope_path=node_ref.target.scope_path, link_id=link_id)
        diagnostics.append(
            _issue(
                "remove_node_link_cleanup",
                "remove_node cascade-removed a connected link.",
                severity="info",
                detail={
                    "scope_path": node_ref.target.scope_path,
                    "uid": node_ref.target.uid,
                    "class_type": node_ref.class_type,
                    "node_id": node_id,
                    "link_id": link_id,
                    "origin_id": origin_id,
                    "target_id": target_id,
                },
            )
        )
    _remove_node_from_scope(scope.graph, node_id)
    ledger.node_index.pop((node_ref.target.scope_path, node_ref.target.uid), None)
    return diagnostics


def _apply_upsert_link(
    ledger: EditLedger,
    source: ResolvedLinkEndpoint,
    target: ResolvedLinkEndpoint,
) -> list[PortIssue]:
    assert isinstance(source.ref, LinkSourceRef)
    assert isinstance(target.ref, LinkTargetRef)
    scope_path = source.ref.scope_path
    scope = ledger.scopes[scope_path]
    diagnostics: list[PortIssue] = []
    source_port = assert_source_slot_in_bounds(
        source.node,
        source.slot_index,
        class_type=source.class_type,
        slot_name=source.slot_name,
    )
    if not source_port.ok:
        return [
            _issue(
                source_port.code or "source_slot_out_of_bounds",
                source_port.message,
                detail=source_port.detail,
            )
        ]
    origin_slot = source_port.slot_index
    assert origin_slot is not None
    target_slot, slot_issues = _ensure_input_slot(target.node, target.slot_name, target.socket_type)
    if slot_issues or target_slot is None:
        return slot_issues
    existing = _find_named_slot(target.node.get("inputs"), target.slot_name)
    duplicate_link_ids = (
        _link_ids_targeting_input(scope, target.node_id, target_slot)
        if isinstance(target.node_id, int)
        else []
    )
    if isinstance(existing, dict) and isinstance(existing.get("link"), int):
        duplicate_link_ids.append(existing["link"])
    removed_link_ids: list[int] = []
    for old_link_id in dict.fromkeys(duplicate_link_ids):
        if _remove_link_from_scope(ledger, scope_path=scope_path, link_id=old_link_id):
            removed_link_ids.append(old_link_id)
    if removed_link_ids:
        detail: dict[str, Any] = {
            "scope_path": scope_path,
            "to_uid": target.ref.uid,
            "to_input": target.slot_name,
            "removed_link_id": removed_link_ids[0],
            "removed_link_ids": removed_link_ids,
        }
        if len(removed_link_ids) == 1:
            diagnostics.append(
                _issue(
                    "upsert_link_replaced_existing",
                    "upsert_link removed the previous incoming link for the target input.",
                    severity="info",
                    detail=detail,
                )
            )
        else:
            diagnostics.append(
                _issue(
                    "upsert_link_replaced_existing",
                    "upsert_link removed previous incoming links for the target input.",
                    severity="info",
                    detail=detail,
                )
            )

    link_id = ledger.mint_link_id(scope_path)
    link_type = source.socket_type or target.socket_type or "*"
    link = _new_link_for_scope(
        scope,
        link_id=link_id,
        origin_id=source.node_id,
        origin_slot=origin_slot,
        target_id=target.node_id,
        target_slot=target_slot,
        link_type=link_type,
    )
    links = scope.graph.get("links")
    if not isinstance(links, list):
        links = []
        scope.graph["links"] = links
    links.append(link)
    ledger.link_index[(scope_path, link_id)] = link
    diagnostics.extend(_ensure_output_link_reference(scope.graph, source.node_id, origin_slot, link_id))
    diagnostics.extend(_set_input_link_reference(target.node, target_slot, link_id))
    return diagnostics


def _apply_add_node(
    ledger: EditLedger,
    spec: ResolvedAddNodeSpec,
) -> tuple[AppliedAddNodeSpec, list[PortIssue]]:
    scope_path = spec.op.scope_path
    source_issues: list[PortIssue] = []
    for input_name, source in spec.resolved_inputs.items():
        source_port = assert_source_slot_in_bounds(
            source.node,
            source.slot_index,
            class_type=source.class_type,
            slot_name=source.slot_name,
        )
        if not source_port.ok:
            source_issues.append(
                _issue(
                    source_port.code or "source_slot_out_of_bounds",
                    source_port.message,
                    detail={"to_input": input_name, **source_port.detail},
                )
            )
    if source_issues:
        return (
            AppliedAddNodeSpec(
                op=spec.op,
                scope_path=scope_path,
                uid=spec.op.uid or "",
                node_id=-1,
                link_ids=(),
                source_uids=(),
                value_default_receipts=spec.value_default_receipts,
            ),
            source_issues,
        )
    node_id = ledger.mint_node_id(scope_path)
    uid = ledger.mint_uid(scope_path)
    provisional = materialize_litegraph_node(
        spec.op.class_type,
        spec.op.fields,
        spec.schema,
        node_id,
        uid,
        [0.0, 0.0],
    )
    size = _node_size(provisional)
    pos, group_index, grew_group, group_issues = _place_add_node(ledger, spec, size)
    node = materialize_litegraph_node(
        spec.op.class_type,
        spec.op.fields,
        spec.schema,
        node_id,
        uid,
        pos,
    )
    protected_fields = spec.value_default_fields
    if protected_fields:
        properties = node.setdefault("properties", {})
        if isinstance(properties, dict):
            properties["vibecomfy_value_default_fields"] = list(
                dict.fromkeys(protected_fields)
            )
    node["order"] = _next_node_order(spec.scope.graph)
    nodes = spec.scope.graph.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
        spec.scope.graph["nodes"] = nodes
    nodes.append(node)
    ledger.node_index[(scope_path, uid)] = node

    link_ids: list[int] = []
    diagnostics: list[PortIssue] = list(group_issues)
    # LiteGraph slot indexes are positional runtime ABI, not presentation
    # order.  In particular, alphabetizing KSampler's connected inputs turns
    # latent_image into slot 0 even though the native node owns model at slot
    # 0.  Follow the schema declaration order for known inputs and retain a
    # deterministic fallback only for dynamic/unknown inputs.
    ordered_input_names = [
        input_name for input_name in spec.schema_inputs if input_name in spec.resolved_inputs
    ]
    ordered_input_names.extend(
        sorted(input_name for input_name in spec.resolved_inputs if input_name not in spec.schema_inputs)
    )
    for input_name in ordered_input_names:
        source = spec.resolved_inputs[input_name]
        input_spec = spec.resolved_input_specs.get(input_name) or spec.schema_inputs.get(input_name)
        target_type = _normalize_type(getattr(input_spec, "type", None))
        origin_slot = source.slot_index
        if not isinstance(origin_slot, int):
            diagnostics.append(
                _issue(
                    "source_slot_out_of_bounds",
                    f"{source.class_type} source slot for {input_name!r} is missing.",
                    detail={"to_input": input_name, "from_uid": source.ref.uid if hasattr(source.ref, "uid") else None},
                )
            )
            continue
        target_slot, slot_issues = _ensure_input_slot(
            node,
            input_name,
            target_type,
            schema=spec.schema,
            fields=spec.op.fields,
        )
        if slot_issues or target_slot is None:
            diagnostics.extend(slot_issues)
            continue
        link_id = ledger.mint_link_id(scope_path)
        link = _new_link_for_scope(
            spec.scope,
            link_id=link_id,
            origin_id=source.node_id,
            origin_slot=origin_slot,
            target_id=node_id,
            target_slot=target_slot,
            link_type=source.socket_type or target_type or "*",
        )
        links = spec.scope.graph.get("links")
        if not isinstance(links, list):
            links = []
            spec.scope.graph["links"] = links
        links.append(link)
        ledger.link_index[(scope_path, link_id)] = link
        link_ids.append(link_id)
        diagnostics.extend(_ensure_output_link_reference(spec.scope.graph, source.node_id, origin_slot, link_id))
        diagnostics.extend(_set_input_link_reference(node, target_slot, link_id))

    diagnostics.append(
        _issue(
            "add_node_applied",
            "add_node materialized a new LiteGraph node with deterministic ledger ids and placement.",
            severity="info",
            detail={
                "scope_path": scope_path,
                "class_type": spec.op.class_type,
                "node_id": node_id,
                "uid": uid,
                "pos": list(node.get("pos") or []),
                "group_index": group_index,
                "link_ids": link_ids,
                "value_default_receipts": [
                    receipt.to_dict() for receipt in spec.value_default_receipts
                ],
            },
        )
    )
    if grew_group and group_index is not None:
        diagnostics.append(
            _issue(
                "add_node_group_growth",
                "add_node grew the target group bounding box minimally to contain the new node.",
                severity="info",
                detail={"scope_path": scope_path, "group_index": group_index, "uid": uid},
            )
        )

    landed_fields = dict(spec.op.fields)
    if protected_fields:
        landed_fields[VALUE_DEFAULT_FIELDS_MARKER] = list(protected_fields)
    landed_op = AddNodeOp(
        op=spec.op.op,
        scope_path=spec.op.scope_path,
        class_type=spec.op.class_type,
        fields=landed_fields,
        inputs=dict(spec.op.inputs),
        anchor=spec.op.anchor,
        uid=uid,
        node_id=str(node_id),
    )
    return (
        AppliedAddNodeSpec(
            op=landed_op,
            scope_path=scope_path,
            uid=uid,
            node_id=node_id,
            link_ids=tuple(link_ids),
            source_uids=tuple(source.ref.uid for source in spec.resolved_inputs.values()),
            group_index=group_index if grew_group else None,
            value_default_receipts=spec.value_default_receipts,
            value_default_fields=protected_fields,
        ),
        diagnostics,
    )


def _apply_reorder(node_ref: ResolvedNodeRef, op: ReorderOp) -> list[PortIssue]:
    names = _reorder_names(node_ref.node, node_ref.class_type, op.axis)
    if names is None or tuple(names) == tuple(op.order):
        return []
    if op.axis == "widgets":
        values = node_ref.node.get("widgets_values")
        if not isinstance(values, list):
            return []
        index_by_name = {name: index for index, name in enumerate(names)}
        node_ref.node["widgets_values"] = [values[index_by_name[name]] for name in op.order]
        return [
            _issue(
                "reorder_widgets_applied",
                "Reordered widget values by the requested complete field-name permutation.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "order": list(op.order),
                },
            )
        ]

    outputs = node_ref.node.get("outputs")
    if not isinstance(outputs, list):
        return []
    index_by_name = {name: index for index, name in enumerate(names)}
    node_ref.node["outputs"] = [outputs[index_by_name[name]] for name in op.order]
    for index, output in enumerate(node_ref.node["outputs"]):
        if isinstance(output, dict):
            output["slot_index"] = index
    return [
        _issue(
            "reorder_slots_applied",
            "Reordered output slots by the requested complete slot-name permutation.",
            severity="info",
            detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "order": list(op.order)},
        )
    ]


def _apply_set_node_field(
    ledger: EditLedger,
    field_ref: ResolvedFieldRef,
    value: Any,
) -> list[PortIssue]:
    diagnostics: list[PortIssue] = []
    node = field_ref.node
    if not isinstance(node, dict):
        return diagnostics
    if field_ref.automatic_link_removal is not None:
        removed = _remove_link_from_scope(
            ledger,
            scope_path=field_ref.target.scope_path,
            link_id=field_ref.automatic_link_removal,
        )
        if not removed:
            diagnostics.append(
                _issue(
                    "automatic_link_removal_missing_link",
                    "Linked widget override referenced a missing link during apply; cleared the target slot anyway.",
                    severity="warning",
                    detail={
                        "scope_path": field_ref.target.scope_path,
                        "uid": field_ref.target.uid,
                        "field_path": field_ref.target.field_path,
                        "link_id": field_ref.automatic_link_removal,
                    },
                )
        )
        _clear_linked_input_surface(node, field_ref)
    _write_widget_value(node, field_ref, value)
    if field_ref.value_default_receipt is not None:
        diagnostics.append(
            _issue(
                "value_default_edit_receipt",
                "Protected widget edit applied with an authority receipt.",
                severity="info",
                detail=field_ref.value_default_receipt.to_dict(),
            )
        )
    return diagnostics


def _clear_linked_input_surface(node: dict[str, Any], field_ref: ResolvedFieldRef) -> None:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return
    if field_ref.input_slot_index is None or field_ref.input_slot_index >= len(inputs):
        return
    slot = inputs[field_ref.input_slot_index]
    if not isinstance(slot, dict):
        return
    if _widget_name_for_input(slot) == field_ref.target.field_path:
        del inputs[field_ref.input_slot_index]
        return
    if "link" in slot:
        slot["link"] = None


def _write_widget_value(node: dict[str, Any], field_ref: ResolvedFieldRef, value: Any) -> None:
    widgets_values = node.get("widgets_values")
    if field_ref.widget_key is not None:
        if isinstance(widgets_values, dict):
            widgets_values[field_ref.widget_key] = value
            return
        if isinstance(widgets_values, Mapping):
            widgets_values = dict(widgets_values)
            widgets_values[field_ref.widget_key] = value
            node["widgets_values"] = widgets_values
            return
    assert field_ref.widget_index is not None
    if not isinstance(widgets_values, list):
        widgets_values = []
        node["widgets_values"] = widgets_values
    while len(widgets_values) <= field_ref.widget_index:
        widgets_values.append(None)
    widgets_values[field_ref.widget_index] = value
