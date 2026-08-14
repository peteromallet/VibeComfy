from __future__ import annotations

from typing import Any, Mapping

from .ledger import EditLedger
from .ops import AddNodeOp, AnchorRef, ReorderOp
from vibecomfy.porting.authoring_surface import input_spec_is_socket_only
from vibecomfy.porting.edit._ir_utils import _canonical_input_name_for_class, _input_spec_for_field
from vibecomfy.porting.edit.apply_field_aliases import (
    field_diagnostics_for_class,
    format_valid_field_hint,
    resolve_add_node_field_alias,
    socket_source_hint,
)
from vibecomfy.porting.edit.apply_place import _group_index_by_title
from vibecomfy.porting.edit.apply_resolve_base import _resolve_node, _resolve_scope, _resolve_source_endpoint
from vibecomfy.porting.edit.apply_slots import _linked_widget_names, _reorder_names
from vibecomfy.porting.edit.apply_types import (
    ResolvedAddNodeSpec,
    ResolvedLinkEndpoint,
    ResolvedNodeRef,
    ResolvedOp,
    ValueDefaultContext,
    ValueDefaultReceipt,
    ValueDefaultBinding,
    VALUE_DEFAULT_FIELDS_MARKER,
    _issue,
)
from vibecomfy.porting.edit.apply_values import _validate_literal_value
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.endpoint_invariant import (
    assert_source_slot_in_bounds,
    dynamic_port_authorized,
)
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.schema import InputSpec, is_workflow_stub_schema, schema_for, socket_types_compatible


def _resolve_add_node(
    ledger: EditLedger,
    op: AddNodeOp,
    *,
    schema_provider: Any,
    value_default_context: ValueDefaultContext | None = None,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    scope, issues = _resolve_scope(ledger, op.scope_path)
    if issues:
        return None, issues
    assert scope is not None

    schema = schema_for(schema_provider, op.class_type)
    if schema is None or is_workflow_stub_schema(schema):
        return None, [
            _issue(
                "unknown_add_node_class_type",
                f"Unknown class_type {op.class_type!r} for add_node.",
                detail={"scope_path": op.scope_path, "class_type": op.class_type},
            )
        ]

    schema_inputs = getattr(schema, "inputs", {}) or {}
    fields: dict[str, Any] = {}
    persisted_value_default_fields: tuple[str, ...] = ()
    raw_fields = dict(op.fields)
    raw_marker = raw_fields.pop(VALUE_DEFAULT_FIELDS_MARKER, None)
    if raw_marker is not None:
        if (
            op.uid is None
            or op.node_id is None
            or not isinstance(raw_marker, (list, tuple))
            or not all(isinstance(field, str) and field for field in raw_marker)
        ):
            return None, [
                _issue(
                    "invalid_value_default_replay_marker",
                    "Value-default protection metadata is valid only on a canonical landed add-node op.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type},
                )
            ]
        persisted_value_default_fields = tuple(dict.fromkeys(raw_marker))
    known_field_names: set[str] = set()
    alias_issues: list[PortIssue] = []
    original_by_resolved: dict[str, str] = {}
    for raw_field_name, value in raw_fields.items():
        requested_field = str(raw_field_name)
        canonical = _canonical_input_name_for_class(schema_inputs, op.class_type, requested_field)
        resolved = resolve_add_node_field_alias(
            op.class_type,
            canonical,
            schema_inputs,
            schema_provider=schema_provider,
        )
        if resolved.field_name in fields:
            alias_issues.append(
                _issue(
                    "duplicate_add_node_field_alias",
                    f"{op.class_type} add_node received multiple values for field {resolved.field_name!r}.",
                    detail={
                        "scope_path": op.scope_path,
                        "class_type": op.class_type,
                        "field": resolved.field_name,
                        "first_requested_field": original_by_resolved.get(resolved.field_name),
                        "duplicate_requested_field": requested_field,
                    },
                )
            )
            continue
        fields[resolved.field_name] = value
        original_by_resolved[resolved.field_name] = requested_field
        if resolved.known:
            known_field_names.add(resolved.field_name)
    inputs = {
        _canonical_input_name_for_class(schema_inputs, op.class_type, str(input_name)): source
        for input_name, source in op.inputs.items()
    }
    if fields != dict(op.fields) or inputs != dict(op.inputs):
        op = AddNodeOp(
            op=op.op,
            scope_path=op.scope_path,
            class_type=op.class_type,
            fields=fields,
            inputs=inputs,
            anchor=op.anchor,
            uid=op.uid,
            node_id=op.node_id,
        )
    issues = list(alias_issues)
    value_default_receipts: tuple[ValueDefaultReceipt, ...] = ()
    if value_default_context is not None and value_default_context.active:
        op, value_default_receipts, binding_issues = _bind_value_defaults(
            op,
            schema_inputs=schema_inputs,
            value_default_context=value_default_context,
        )
        issues.extend(binding_issues)
    value_default_fields = (
        tuple(receipt.canonical_field for receipt in value_default_receipts)
        if value_default_receipts
        else persisted_value_default_fields
    )
    for input_name, spec in schema_inputs.items():
        required = bool(getattr(spec, "required", False))
        default = getattr(spec, "default", None)
        if required and input_name not in op.fields and input_name not in op.inputs and default is None:
            issues.append(
                _issue(
                    "missing_required_add_node_input",
                    f"{op.class_type} requires input {input_name!r} for add_node.",
                    # Per the v2 spec, required-input completeness is a queue-validate
                    # WARNING, not a fidelity failure: adding a node and wiring it in a
                    # later step (or after manual review) is a legitimate flow. Surfacing
                    # this as a hard error blocked the natural "add a node, then connect
                    # it" pattern. The node is still added; queue-validate flags the gap.
                    severity="warning",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            )
    for field_name, value in op.fields.items():
        spec = _input_spec_for_field(schema_inputs, field_name)
        if spec is None and field_name not in known_field_names:
            field_detail = field_diagnostics_for_class(
                op.class_type,
                schema_inputs,
                schema_provider=schema_provider,
            )
            hint = format_valid_field_hint(field_detail)
            message = f"{op.class_type} does not declare field {field_name!r}."
            if hint:
                message = f"{message} {hint}"
            issues.append(
                _issue(
                    "unknown_add_node_field",
                    message,
                    detail={
                        "scope_path": op.scope_path,
                        "class_type": op.class_type,
                        "field": field_name,
                        **field_detail,
                    },
                )
            )
            continue
        if input_spec_is_socket_only(spec):
            hint, hint_detail = socket_source_hint(scope.graph, getattr(spec, "type", None))
            issues.append(
                _issue(
                    "socket_input_not_literal_widget",
                    f"{op.class_type}.{field_name} is an input socket, not a widget. {hint}",
                    detail={
                        "scope_path": op.scope_path,
                        "class_type": op.class_type,
                        "field": field_name,
                        **hint_detail,
                    },
                )
            )
            continue
        issues.extend(
            _validate_literal_value(
                value=value,
                spec=spec,
                class_type=op.class_type,
                input_name=field_name,
                context="add_node",
            )
        )
    # Block only on errors; carry warnings (e.g. missing required input) forward so the
    # node is still added and the gap surfaces as a non-blocking queue-validate warning.
    if any(issue.severity == "error" for issue in issues):
        return None, issues

    resolved_inputs: dict[str, ResolvedLinkEndpoint] = {}
    resolved_input_specs: dict[str, InputSpec] = {}
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
        spec = _input_spec_for_field(schema_inputs, input_name) or _dynamic_add_node_input_spec(
            class_type=op.class_type,
            input_name=input_name,
            fields=op.fields,
            schema_inputs=schema_inputs,
            schema=schema,
        )
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
        source_port = assert_source_slot_in_bounds(
            source_ref.node,
            source_ref.slot_index,
            class_type=source_ref.class_type,
            slot_name=source_ref.slot_name,
        )
        if not source_port.ok:
            return None, [
                _issue(
                    source_port.code or "source_slot_out_of_bounds",
                    source_port.message,
                    detail={"to_input": input_name, **source_port.detail},
                )
            ]
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
        resolved_input_specs[input_name] = spec

    anchor_near = None
    anchor_between = None
    anchor_group_index = None
    anchor_group_title = None
    if op.anchor is not None:
        anchor_issues: list[PortIssue] = []
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
            resolved_input_specs=resolved_input_specs,
            value_default_receipts=value_default_receipts,
            value_default_fields=value_default_fields,
            anchor_near=anchor_near,
            anchor_between=anchor_between,
            anchor_group_index=anchor_group_index,
            anchor_group_title=anchor_group_title,
        ),
        list(issues),
    )


def _values_equal(left: Any, right: Any) -> bool:
    try:
        return bool(left == right)
    except Exception:
        return repr(left) == repr(right)


def _unique_schema_valid_prior(
    *,
    class_type: str,
    input_name: str,
    spec: InputSpec,
    context: ValueDefaultContext,
) -> tuple[ValueDefaultBinding | None, str]:
    valid: list[ValueDefaultBinding] = []
    refused_invalid = False
    for binding in context.selected_bindings(class_type, input_name):
        validation_issues = _validate_literal_value(
            value=binding.thawed_value(),
            spec=spec,
            class_type=class_type,
            input_name=input_name,
            context="value_default_prior",
        )
        if validation_issues:
            refused_invalid = True
            continue
        valid.append(binding)
    if not valid:
        return None, "invalid_source_prior" if refused_invalid else "no_eligible_source_prior"
    first_value = valid[0].thawed_value()
    if any(not _values_equal(first_value, binding.thawed_value()) for binding in valid[1:]):
        return None, "conflicting_source_priors"
    return valid[0], "unique_schema_valid_source_prior"


def _bind_value_defaults(
    op: AddNodeOp,
    *,
    schema_inputs: Mapping[str, InputSpec],
    value_default_context: ValueDefaultContext,
) -> tuple[AddNodeOp, tuple[ValueDefaultReceipt, ...], list[PortIssue]]:
    """Add qualified defaults without making their absence a construction gate."""
    proposed = dict(op.fields)
    effective = dict(op.fields)
    receipts: list[ValueDefaultReceipt] = []
    issues: list[PortIssue] = []

    for input_name, spec in schema_inputs.items():
        if input_spec_is_socket_only(spec):
            continue

        user_override = (
            value_default_context.explicit_override(op.class_type, input_name)
            or value_default_context.explicit_request_override(
                op.class_type,
                input_name,
                spec,
            )
        )
        prior, prior_reason = _unique_schema_valid_prior(
            class_type=op.class_type,
            input_name=input_name,
            spec=spec,
            context=value_default_context,
        )
        chosen = False
        chosen_value: Any = None
        basis = ""
        provenance = ""
        source_instance_id = ""
        role_label = ""
        reason = ""
        if user_override is not None:
            chosen = True
            chosen_value = user_override.thawed_value()
            basis = "explicit_user_value"
            provenance = "user"
            source_instance_id = user_override.source_instance_id
            role_label = user_override.role_label
            reason = "exact structured user override"
        elif prior is not None:
            chosen = True
            chosen_value = prior.thawed_value()
            basis = "source_prior"
            provenance = prior.provenance
            source_instance_id = prior.source_instance_id
            role_label = prior.role_label
            reason = prior_reason

        if input_name in proposed:
            proposed_value = proposed[input_name]
            if not chosen:
                # No qualified binding applies to this field. Preserve the
                # model-authored literal exactly as the pre-feature constructor
                # did; schema validation below remains authoritative.
                continue
            if not _values_equal(proposed_value, chosen_value):
                issues.append(
                    _issue(
                        "value_default_literal_normalized",
                        (
                            f"{op.class_type}.{input_name} proposed {proposed_value!r}; "
                            f"the qualified {basis} value {chosen_value!r} was applied."
                        ),
                        severity="warning",
                        detail={
                            "scope_path": op.scope_path,
                            "class_type": op.class_type,
                            "field": input_name,
                            "proposed_value": proposed_value,
                            "effective_value": chosen_value if chosen else None,
                            "effective_basis": basis or "unresolved",
                        },
                    )
                )
                reason = f"{reason}; conflicting constructor literal normalized"
            else:
                reason = f"{reason}; redundant constructor literal normalized"

        if chosen:
            effective[input_name] = chosen_value
            receipts.append(ValueDefaultReceipt(
                class_type=op.class_type,
                canonical_field=input_name,
                old_value=None,
                new_value=chosen_value,
                basis=basis,
                provenance=provenance,
                validation_result="passed",
                source_instance_id=source_instance_id,
                role_label=role_label,
                reason=reason,
            ))

    return (
        AddNodeOp(
            op=op.op,
            scope_path=op.scope_path,
            class_type=op.class_type,
            fields=effective,
            inputs=dict(op.inputs),
            anchor=op.anchor,
            uid=op.uid,
            node_id=op.node_id,
        ),
        tuple(receipts),
        issues,
    )


def _dynamic_add_node_input_spec(
    *,
    class_type: str,
    input_name: str,
    fields: Mapping[str, Any],
    schema_inputs: Mapping[str, Any],
    schema: Any = None,
) -> InputSpec | None:
    """Return a narrow schema spec for runtime-expanded add_node inputs."""

    if class_type in {"PreviewImage", "SaveImage", "SaveImageWebsocket"} and input_name == "images":
        return InputSpec(type="IMAGE", required=True)
    authorized, _reason = dynamic_port_authorized(
        class_type,
        "input",
        input_name,
        fields=fields,
        schema=schema,
    )
    if not authorized:
        return None
    existing = schema_inputs.get(input_name)
    if existing is not None:
        return existing
    socket_type = "IMAGE" if class_type in {"ImageConcatMulti", "LTXVAddGuide"} else "*"
    if class_type == "LTXVImgToVideoInplaceKJ":
        if "index" in input_name:
            socket_type = "INT"
        elif "strength" in input_name:
            socket_type = "FLOAT"
        else:
            socket_type = "IMAGE"
    return InputSpec(type=socket_type, required=True)


def _resolve_reorder(
    ledger: EditLedger,
    op: ReorderOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.axis != "widgets":
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder supports only cosmetic unlinked widget value permutations; structural slot reorder is rejected.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    node_ref, issues = _resolve_node(ledger, op.target)
    if issues:
        return None, issues
    assert node_ref is not None
    raw = node_ref.node.get("widgets_values")
    if not isinstance(raw, list):
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no reorderable widget surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    names = _reorder_names(node_ref.node, node_ref.class_type, op.axis)
    if names is None:
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no named reorderable {op.axis} surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    if tuple(op.order) == tuple(names):
        return node_ref, []
    if len(op.order) != len(names) or set(op.order) != set(names):
        return None, [
            _issue(
                "unsupported_reorder_form",
                "reorder must be a complete permutation of the existing named widget or output slots.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "expected": list(names),
                    "actual": list(op.order),
                },
            )
        ]
    linked_widgets = _linked_widget_names(node_ref.node.get("inputs"))
    linked_ordered_widgets = [name for name in op.order if name in linked_widgets]
    if linked_ordered_widgets:
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder only supports unlinked widget values; linked widget inputs must be edited with link ops first.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "linked_widgets": linked_ordered_widgets,
                },
            )
        ]
    return node_ref, []


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
