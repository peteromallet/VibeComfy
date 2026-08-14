from __future__ import annotations

import re
from typing import Any, Mapping

from .ledger import EditLedger, ScopeState
from .ops import LinkSourceRef, LinkTargetRef, NodeFieldTarget, NodeTarget, RemoveLinkOp, SetNodeFieldOp, UpsertLinkOp
from vibecomfy.porting.edit._ir_utils import (
    _canonical_input_name_for_class,
    _input_spec_for_field,
    _known_core_input_socket_type,
)
from vibecomfy.porting.edit.apply_field_aliases import (
    field_diagnostics_for_node,
    format_valid_field_hint,
    resolve_set_node_field_alias,
    socket_source_hint,
)
from vibecomfy.porting.edit.apply_links import _build_rewires, _build_rewires_for_setnode_gets, _collect_links_for_origin, _collect_links_for_target, _link_id, _link_ids, _resolve_getnode_source, _resolve_passthrough_source, _schema_output_type
from vibecomfy.porting.edit.apply_slots import _canonical_ui_only_widget_field, _find_named_slot_index, _widget_index_for_field, _widget_index_from_input_stubs, _widget_name_for_input
from vibecomfy.porting.edit.apply_types import (
    ResolvedFieldRef,
    ResolvedLinkEndpoint,
    ResolvedNodeRef,
    ResolvedOp,
    ResolvedRemoveLinkRef,
    ResolvedRemoveNodePlan,
    ValueDefaultContext,
    ValueDefaultReceipt,
    _ctx,
    _endpoint_port_issues,
    _issue,
)
from vibecomfy.porting.edit.apply_values import _validate_literal_value
from vibecomfy.porting.authoring_surface import input_spec_is_socket_only
from vibecomfy.porting.endpoint_invariant import assert_source_slot_in_bounds
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import EditLedgerBackend, _find_named_slot
from vibecomfy.schema import schema_for, socket_types_compatible

_CONTROL_AFTER_GENERATE_CHOICES = ("fixed", "randomize", "increment", "decrement")


def _node_resolvable_literal_fields(node: Mapping[str, Any]) -> list[str]:
    """Return the literal field names this node instance can actually set.

    Resolved through the same compact widget-name machinery the setter uses
    (``compact_widget_names_for_node``); raw ``widget_N`` placeholders that
    carry no semantic name are omitted.  Used to explain why a schema-literal
    field is not settable on a specific node (PR-D / Tripo geometry_quality).
    """
    from vibecomfy.porting.widgets.compact_resolver import (  # noqa: PLC0415
        compact_widget_names_for_node,
    )

    try:
        names = compact_widget_names_for_node(node).names
    except Exception:
        return []
    return [
        str(name)
        for name in names
        if isinstance(name, str) and not re.fullmatch(r"widget_\d+", name)
    ]


def _resolve_scope(ledger: EditLedger, scope_path: str) -> tuple[ScopeState | None, list[PortIssue]]:
    scope = ledger.scopes.get(scope_path)
    if scope is None:
        return None, [
            _issue(
                "unknown_scope_path",
                f"Unknown scope_path {scope_path!r}.",
                detail={"scope_path": scope_path},
            )
        ]
    return scope, []


def _resolve_node(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedNodeRef | None, list[PortIssue]]:
    scope, issues = _resolve_scope(ledger, target.scope_path)
    if issues:
        return None, issues
    assert scope is not None
    # Resolve uid with LG-id aliasing (D1 convergence).
    backend = EditLedgerBackend(ledger)
    uid_result = _ctx.resolve_uid(backend, target.scope_path, target.uid)
    if uid_result.value is None:
        return None, [
            _issue(
                "unknown_node_target",
                f"Unknown node target {target.uid!r} in scope {target.scope_path!r}.",
                detail={"scope_path": target.scope_path, "uid": target.uid},
            )
        ]
    resolved_uid = uid_result.value
    resolved_target = (
        NodeTarget(scope_path=target.scope_path, uid=resolved_uid)
        if resolved_uid != target.uid else target
    )
    node = backend.node_for(target.scope_path, resolved_uid)
    if node is None:
        return None, [
            _issue(
                "unknown_node_target",
                f"Unknown node target {resolved_uid!r} in scope {target.scope_path!r}.",
                detail={"scope_path": target.scope_path, "uid": resolved_uid},
            )
        ]
    class_type = str(node.get("type") or node.get("class_type") or "")
    return (
        ResolvedNodeRef(
            target=resolved_target,
            node=node,
            class_type=class_type,
            node_id=node.get("id"),
        ),
        [],
    )


def _resolve_node_only(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    resolved, issues = _resolve_node(ledger, target)
    return resolved, issues


def _resolve_remove_node(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
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
    value_default_context: ValueDefaultContext | None = None,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
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
    field_path = _canonical_input_name_for_class(schema_inputs, class_type, op.target.field_path)
    field_path = resolve_set_node_field_alias(
        node,
        class_type,
        field_path,
        schema_inputs,
        schema_provider=schema_provider,
    )
    ui_only_alias = _canonical_ui_only_widget_field(
        node,
        field_path,
        schema_provider=schema_provider,
    )
    ui_only_widget_index = None
    if ui_only_alias is not None:
        field_path, ui_only_widget_index = ui_only_alias
    target = (
        op.target
        if field_path == op.target.field_path
        else NodeFieldTarget(op.target.scope_path, op.target.uid, field_path)
    )
    schema_input = _input_spec_for_field(schema_inputs, field_path)

    raw_input = _find_named_slot(node.get("inputs"), field_path)
    raw_input_index = _find_named_slot_index(node.get("inputs"), field_path)
    widgets_values = node.get("widgets_values")
    widget_key = field_path if isinstance(widgets_values, Mapping) and field_path in widgets_values else None
    if raw_input is not None:
        input_name = field_path
        if isinstance(raw_input.get("link"), int):
            automatic_link_removal = raw_input["link"]

    widget_index = ui_only_widget_index
    if widget_index is None:
        widget_index = _widget_index_for_field(node, field_path, schema_provider=schema_provider)
    widget_stub_name = _widget_name_for_input(raw_input)
    used_schema_less_widget_recovery = False
    if widget_index is None and widget_stub_name == field_path:
        widget_index = _widget_index_from_input_stubs(node.get("inputs"), field_path)
        used_schema_less_widget_recovery = widget_index is not None
    if widget_index is None and isinstance(widgets_values, list):
        match = re.fullmatch(r"widget_(\d+)", field_path)
        if match is not None:
            positional_index = int(match.group(1))
            if 0 <= positional_index < len(widgets_values):
                widget_index = positional_index

    if input_name is None and widget_index is None and widget_key is None and schema_input is None:
        field_detail = field_diagnostics_for_node(
            node,
            class_type,
            schema_inputs,
            schema_provider=schema_provider,
        )
        hint = format_valid_field_hint(field_detail)
        message = f"{class_type} does not expose field {op.target.field_path!r}."
        if hint:
            message = f"{message} {hint}"
        return None, [
            _issue(
                "unknown_node_field",
                message,
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": field_path,
                    "requested_field_path": op.target.field_path,
                    "class_type": class_type,
                    **field_detail,
                },
            )
        ]
    if widget_index is None and widget_key is None:
        if input_spec_is_socket_only(schema_input):
            input_type = getattr(schema_input, "type", None)
            scope = ledger.scopes[op.target.scope_path]
            hint, hint_detail = socket_source_hint(
                scope.graph,
                input_type,
                target_node=node,
            )
            return None, [
                _issue(
                    "socket_input_not_literal_widget",
                    f"{class_type}.{op.target.field_path} is an input socket, not a widget. {hint}",
                    detail={
                        "scope_path": op.target.scope_path,
                        "uid": op.target.uid,
                        "field_path": field_path,
                        "requested_field_path": op.target.field_path,
                        "class_type": class_type,
                        **hint_detail,
                    },
                )
            ]
        node_literal_fields = _node_resolvable_literal_fields(node)
        hint = (
            "Settable literal fields on this node: "
            + (", ".join(node_literal_fields) if node_literal_fields else "none")
            + "."
        )
        return None, [
            _issue(
                "node_field_not_resolvable",
                f"{class_type}.{op.target.field_path} is advertised as a literal field by the class schema, "
                f"but this node instance has no widget for it (the node may predate the field). {hint}",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": field_path,
                    "requested_field_path": op.target.field_path,
                    "class_type": class_type,
                    "node_literal_fields": node_literal_fields,
                },
            )
        ]

    if field_path == "control_after_generate" and op.value not in _CONTROL_AFTER_GENERATE_CHOICES:
        return None, [
            _issue(
                "value_not_in_enum",
                f"set_node_field rejected {class_type}.{field_path}: value {op.value!r} is not in the declared enum.",
                detail={
                    "class_type": class_type,
                    "input": field_path,
                    "value": op.value,
                    "choices": list(_CONTROL_AFTER_GENERATE_CHOICES),
                },
            )
        ]

    value_issues = _validate_literal_value(
        value=op.value,
        spec=schema_input,
        class_type=class_type,
        input_name=field_path,
        context="set_node_field",
    )
    # Apply-time policy: unavailable checkpoint/model assets are WARNINGS
    # (asset_not_installed), not hard errors — only error-severity issues
    # block the assignment.  Warnings are carried on the resolved op so the
    # caller can surface them without rejecting a justified model-file swap.
    if any(
        getattr(issue, "severity", "error") == "error"
        for issue in value_issues
    ):
        return None, value_issues

    value_default_receipt = None
    node_properties = node.get("properties")
    protected_uid = (
        str(node_properties.get("vibecomfy_uid"))
        if isinstance(node_properties, Mapping)
        and isinstance(node_properties.get("vibecomfy_uid"), str)
        else target.uid
    )
    if (
        value_default_context is not None
        and value_default_context.active
        and value_default_context.protects(
            target.scope_path,
            protected_uid,
            class_type,
            field_path,
        )
    ):
        old_value = None
        if widget_key is not None and isinstance(widgets_values, Mapping):
            old_value = widgets_values.get(widget_key)
        elif (
            widget_index is not None
            and isinstance(widgets_values, list)
            and widget_index < len(widgets_values)
        ):
            old_value = widgets_values[widget_index]
        user_override = (
            value_default_context.explicit_override(class_type, field_path)
            or value_default_context.explicit_request_override(
                class_type,
                field_path,
                schema_input,
            )
        )
        basis = ""
        provenance_label = ""
        receipt_reason = ""
        if old_value == op.value:
            basis = "redundant_existing_value"
            provenance_label = "existing_bound_value"
            receipt_reason = "assignment equals the protected value"
        elif user_override is not None and user_override.thawed_value() == op.value:
            basis = "explicit_user_value"
            provenance_label = "user"
            receipt_reason = "exact structured user edit authority"
        else:
            schema_default = getattr(schema_input, "default", None)
            old_value_issues = _validate_literal_value(
                value=old_value,
                spec=schema_input,
                class_type=class_type,
                input_name=field_path,
                context="protected_value",
            )
            if schema_default is not None and old_value_issues and schema_default == op.value:
                basis = "schema_correction"
                provenance_label = "schema_default"
                receipt_reason = (
                    "protected value invalid under current schema; "
                    "unique declared-default correction"
                )
        if not basis:
            return None, [
                _issue(
                    "unauthorized_set_node_field_override",
                    (
                        f"{class_type}.{field_path} is protected by value-default "
                        "binding; a different value requires an exact user or "
                        "schema-correction receipt."
                    ),
                    detail={
                        "scope_path": target.scope_path,
                        "uid": protected_uid,
                        "class_type": class_type,
                        "field": field_path,
                        "old_value": old_value,
                        "proposed_value": op.value,
                    },
                )
            ]
        value_default_receipt = ValueDefaultReceipt(
            class_type=class_type,
            canonical_field=field_path,
            old_value=old_value,
            new_value=op.value,
            basis=basis,
            provenance=provenance_label,
            validation_result="passed",
            reason=receipt_reason,
        )

    issues = list(value_issues)
    if used_schema_less_widget_recovery:
        issues.append(
            _issue(
                "schema_less_linked_widget_recovery",
                "Recovered widget position from linked input stubs because schema/object_info widget order was unavailable.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": field_path,
                    "requested_field_path": op.target.field_path,
                    "class_type": class_type,
                    "widget_index": widget_index,
                },
            )
        )
    if automatic_link_removal is not None:
        issues.append(
            _issue(
                "automatic_link_removal",
                "Field is linked/overridden; edit the effective source when it is the same semantic control, or refuse/clarify if it is unrelated.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": field_path,
                    "requested_field_path": op.target.field_path,
                    "link_id": automatic_link_removal,
                    "effective_surface": "linked_override",
                    "next_action": "edit_effective_source_or_refuse_if_unrelated",
                },
            )
        )
    return (
        ResolvedFieldRef(
            target=target,
            node=node,
            class_type=class_type,
            node_id=node.get("id"),
            input_name=input_name,
            input_slot_index=raw_input_index,
            widget_index=widget_index,
            widget_key=widget_key,
            schema_input=schema_input,
            automatic_link_removal=automatic_link_removal,
            value_default_receipt=value_default_receipt,
        ),
        issues,
    )


def _resolve_upsert_link(
    ledger: EditLedger,
    op: UpsertLinkOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.source.scope_path != op.target.scope_path:
        return None, [
            _issue(
                "cross_scope_link_unsupported",
                "Link endpoints must resolve within the same scope.",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "to_scope_path": op.target.scope_path,
                },
            )
        ]
    source, source_issues = _resolve_source_endpoint(ledger, op.source, schema_provider=schema_provider)
    if source_issues:
        return None, source_issues
    target, target_issues = _resolve_target_endpoint(ledger, op.target, schema_provider=schema_provider)
    if target_issues:
        return None, target_issues
    assert source is not None and target is not None
    source_port = assert_source_slot_in_bounds(
        source.node,
        source.slot_index,
        class_type=source.class_type,
        slot_name=source.slot_name,
    )
    if not source_port.ok:
        return None, [
            _issue(
                source_port.code or "source_slot_out_of_bounds",
                source_port.message,
                detail=source_port.detail,
            )
        ]
    if not isinstance(source.node_id, int) or not isinstance(target.node_id, int):
        return None, [
            _issue(
                "non_numeric_link_endpoint",
                "Link endpoints must have numeric LiteGraph node ids.",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "from_uid": op.source.uid,
                    "from_node_id": source.node_id,
                    "to_scope_path": op.target.scope_path,
                    "to_uid": op.target.uid,
                    "to_node_id": target.node_id,
                },
            )
        ]
    if source.socket_type and target.socket_type and not socket_types_compatible(source.socket_type, target.socket_type):
        return None, [
            _issue(
                "incompatible_socket_types",
                f"Cannot connect {source.class_type}.{source.slot_name} ({source.socket_type}) to "
                f"{target.class_type}.{target.slot_name} ({target.socket_type}).",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "from_uid": op.source.uid,
                    "from_slot": source.slot_name,
                    "from_type": source.socket_type,
                    "to_scope_path": op.target.scope_path,
                    "to_uid": op.target.uid,
                    "to_input": target.slot_name,
                    "to_type": target.socket_type,
                },
            )
        ]
    return (source, target), []


def _resolve_remove_link(
    ledger: EditLedger,
    op: RemoveLinkOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.link_id is not None:
        matches = [
            ResolvedRemoveLinkRef(scope_path=scope_path, link_id=link_id, link=link)
            for (scope_path, link_id), link in ledger.link_index.items()
            if link_id == op.link_id
        ]
        if not matches:
            return None, [
                _issue(
                    "unknown_link_id",
                    f"Unknown link id {op.link_id}.",
                    detail={"link_id": op.link_id},
                )
            ]
        if len(matches) > 1:
            return None, [
                _issue(
                    "ambiguous_link_id",
                    f"Link id {op.link_id} exists in multiple scopes.",
                    detail={"link_id": op.link_id, "scope_paths": [item.scope_path for item in matches]},
                )
            ]
        return matches[0], []

    assert op.target is not None
    node_ref, issues = _resolve_node(ledger, NodeTarget(op.target.scope_path, op.target.uid))
    if issues:
        return None, issues
    assert node_ref is not None
    raw_input = _find_named_slot(node_ref.node.get("inputs"), op.target.input_field)
    if raw_input is None:
        return None, [
            _issue(
                "unknown_link_target_input",
                f"{node_ref.class_type} does not expose input {op.target.input_field!r}.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "input": op.target.input_field,
                },
            )
        ]
    link_id = raw_input.get("link")
    if not isinstance(link_id, int):
        return None, [
            _issue(
                "missing_link_to_remove",
                f"{node_ref.class_type}.{op.target.input_field} has no incoming link to remove.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "input": op.target.input_field,
                },
            )
        ]
    link = ledger.resolve_link(op.target.scope_path, link_id)
    if link is None:
        return None, [
            _issue(
                "dangling_link_reference",
                f"Input {op.target.input_field!r} references missing link id {link_id}.",
                detail={"scope_path": op.target.scope_path, "link_id": link_id},
            )
        ]
    return ResolvedRemoveLinkRef(scope_path=op.target.scope_path, link_id=link_id, link=link), []


def _resolve_source_endpoint(
    ledger: EditLedger,
    ref: LinkSourceRef,
    *,
    schema_provider: Any,
) -> tuple[ResolvedLinkEndpoint | None, list[PortIssue]]:
    backend = EditLedgerBackend(ledger)
    result = _ctx.resolve_source_endpoint(backend, ref, schema_provider=schema_provider)
    if result.value is None:
        return None, _endpoint_port_issues(result)
    ep = result.value
    socket_type = ep.socket_type
    if socket_type is None:
        socket_type = _schema_output_type(schema_provider, ep.class_type, ep.slot_index, ep.slot_name)
    return (
        ResolvedLinkEndpoint(
            ref=ref,
            node=ep.node,
            class_type=ep.class_type,
            node_id=ep.node_id,
            slot_index=ep.slot_index,
            slot_name=ep.slot_name,
            socket_type=socket_type,
        ),
        [],
    )


def _resolve_target_endpoint(
    ledger: EditLedger,
    ref: LinkTargetRef,
    *,
    schema_provider: Any,
) -> tuple[ResolvedLinkEndpoint | None, list[PortIssue]]:
    backend = EditLedgerBackend(ledger)
    result = _ctx.resolve_target_endpoint(backend, ref, schema_provider=schema_provider)
    if result.value is None:
        return None, _endpoint_port_issues(result)
    ep = result.value
    socket_type = ep.socket_type
    if socket_type is None or socket_type == "UNKNOWN":
        socket_type = _known_core_input_socket_type(ep.class_type, ep.slot_name) or socket_type
    return (
        ResolvedLinkEndpoint(
            ref=ref,
            node=ep.node,
            class_type=ep.class_type,
            node_id=ep.node_id,
            slot_index=ep.slot_index,
            slot_name=ep.slot_name,
            socket_type=socket_type,
        ),
        [],
    )
