"""Pure validation for already-lowered edit operations.

The Python authoring surface performs these checks while interpreting source.
Typed tool calls bypass that parser, so they must pass the same sort of checks
before reaching the retained :class:`~vibecomfy.porting.edit.EditSession` IR.
Validation is deliberately sequential: a later operation may refer to a node
added by an earlier operation in the same atomic batch.
"""

from __future__ import annotations

import re

from typing import Any, Mapping, Sequence

from vibecomfy.porting.edit._ir_utils import (
    _RECURSIVE_GUIDANCE,
    RecursiveEditError,
    _recursive_field_entries,
    _recursive_field,
    _operation_scope_paths,
    build_recursive_edit_index,
)
from vibecomfy.porting.edit.constants import MODE_LABELS
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    SubgraphInterfaceOp,
    UpsertLinkOp,
)


class ApplyOpsError(ValueError):
    """Stable, typed rejection from the shared transactional edit gateway."""

    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _unsupported_recursive(op: EditOp) -> ApplyOpsError:
    scope = next((path for path in _operation_scope_paths(op) if path), "")
    return ApplyOpsError(
        "unsupported_structural_scope",
        f"{getattr(op, 'op', type(op).__name__)} at scope {scope!r} changes unsupported recursive structure; {_RECURSIVE_GUIDANCE}",
        retryable=False,
    )


_LITERAL_TYPES: dict[str, tuple[type, ...]] = {
    "STRING": (str,),
    "INT": (int,),
    "FLOAT": (int, float),
    "BOOLEAN": (bool,),
}


def _node_by_uid(workflow: Any, uid: str) -> Any | None:
    matches = [
        node
        for node in workflow.nodes.values()
        if str(getattr(node, "uid", "") or "") == str(uid)
    ]
    if len(matches) > 1:
        raise ApplyOpsError(
            "ambiguous_target",
            f"uid {uid!r} resolves to more than one retained IR node.",
            retryable=False,
        )
    return matches[0] if matches else None


def _schema_for(node: Any, provider: Any) -> Any | None:
    if provider is None:
        return None
    from vibecomfy.schema import schema_for

    return schema_for(provider, str(node.class_type))


def _input_spec(node: Any, field: str, provider: Any) -> Any | None:
    schema = _schema_for(node, provider)
    inputs = getattr(schema, "inputs", None) or {}
    return inputs.get(field) if isinstance(inputs, Mapping) else None


def _require_node(workflow: Any, uid: str) -> Any:
    node = _node_by_uid(workflow, uid)
    if node is None:
        raise ApplyOpsError("unknown_target", f"no retained IR node for uid {uid!r}.")
    return node


def _validate_recursive_field(workflow: Any, op: SetNodeFieldOp, provider: Any) -> None:
    try:
        ref = build_recursive_edit_index(workflow).node(op.target.scope_path, op.target.uid)
    except RecursiveEditError as exc:
        raise ApplyOpsError(exc.code, str(exc), retryable=False) from exc
    node = ref.node
    field = str(op.target.field_path)
    resolved = _recursive_field(node, field)
    if resolved is None:
        raise ApplyOpsError(
            "unknown_field",
            f"field {field!r} is not present on {node.get('type', node.get('class_type', 'Unknown'))!r} ({op.target.uid!r}).",
        )
    if resolved[0] == "structural":
        raise ApplyOpsError(
            "unsupported_structural_scope",
            f"field {field!r} changes recursive graph structure; {_RECURSIVE_GUIDANCE}",
            retryable=False,
        )
    if any(
        name == field and linked
        for name, _channel, _value, linked in _recursive_field_entries(node)
    ):
        raise ApplyOpsError(
            "unsupported_structural_scope",
            f"linked recursive field {field!r} requires an authored link transaction; {_RECURSIVE_GUIDANCE}",
            retryable=False,
        )
    unchanged = resolved[1] == op.value
    if unchanged:
        raise ApplyOpsError("no_op", f"{field!r} is already set to that value.")

    class_type = str(node.get("type", node.get("class_type", "")))
    schema = None
    if provider is not None:
        from vibecomfy.schema import schema_for

        schema = schema_for(provider, class_type)
    specs = getattr(schema, "inputs", None) or {}
    spec = specs.get(field) if isinstance(specs, Mapping) else None
    if spec is None:
        return
    from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget

    if not input_spec_is_literal_widget(spec):
        raise ApplyOpsError(
            "wrong_channel",
            f"field {field!r} is a socket; use a supported authored link operation instead of a literal write.",
        )
    from vibecomfy.porting.edit.validate import validate_literal_value

    for issue in validate_literal_value(
        value=op.value,
        spec=spec,
        class_type=class_type,
        input_name=field,
        context="typed edit",
    ):
        if getattr(issue, "severity", "error") == "error":
            raise ApplyOpsError(issue.code, issue.message)
    spec_type = str(getattr(spec, "type", "") or "")
    accepted = _LITERAL_TYPES.get(spec_type)
    if accepted is not None and (
        not isinstance(op.value, accepted)
        or (isinstance(op.value, bool) and spec_type in {"INT", "FLOAT"})
    ):
        raise ApplyOpsError(
            "type_mismatch",
            f"field {field!r} expects {spec_type}, got {type(op.value).__name__}.",
        )


def _validate_field(workflow: Any, op: SetNodeFieldOp, provider: Any) -> None:
    if op.target.scope_path:
        _validate_recursive_field(workflow, op, provider)
        return
    node = _require_node(workflow, op.target.uid)
    field = str(op.target.field_path)
    # The raw LiteGraph widget row is presentation evidence for the compact
    # widget aliases.  It is not a second schema: use the retained node UI
    # payload only to establish the authored slot/arity, then let the shared
    # lowerer/application write the canonical input channel.
    from vibecomfy.ingest.normalize import door_get_widgets_values
    metadata = getattr(node, "metadata", None) or {}
    raw_ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    ui_values = door_get_widgets_values(raw_ui) if isinstance(raw_ui, Mapping) else None
    if field == "widgets_values" and isinstance(ui_values, list):
        if len(ui_values) > 1 and not isinstance(op.value, (list, tuple)):
            raise ApplyOpsError(
                "type_mismatch",
                "widgets_values requires a complete sequence for a multi-widget node.",
            )
        return
    match = re.fullmatch(r"(?:widgets|widgets_values)\.(\d+)|widget_(\d+)", field)
    if match is not None and isinstance(ui_values, list):
        slot = int(match.group(1) or match.group(2))
        if 0 <= slot < len(ui_values):
            if ui_values[slot] == op.value:
                raise ApplyOpsError("no_op", f"{field!r} is already set to that value.")
            return
    if field.startswith("widget_") and field[7:].isdigit():
        raise ApplyOpsError(
            "invalid_arguments",
            f"field {field!r} is positional; use the render-visible field name.",
        )
    widgets = getattr(node, "widgets", None) or {}
    inputs = getattr(node, "inputs", None) or {}
    spec = _input_spec(node, field, provider)
    positional_index: int | None = None
    if spec is None and field not in widgets and field not in inputs:
        try:
            from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid  # noqa: PLC0415
            from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field

            positional_index = widget_index_for_field(
                node,
                field,
                schema_provider=provider,
                name_authority=frozen_widget_names_by_uid(workflow),
            )
        except Exception:  # noqa: BLE001 - optional schema/name evidence
            positional_index = None
    if spec is None and field not in widgets and field not in inputs and positional_index is None:
        raise ApplyOpsError(
            "unknown_field",
            f"field {field!r} is not present on {node.class_type!r} ({op.target.uid!r}).",
        )

    current = widgets.get(field, inputs.get(field, object()))
    if positional_index is not None:
        key = f"widget_{positional_index}"
        current = widgets.get(key, inputs.get(key, current))
    try:
        unchanged = bool(current == op.value)
    except Exception:  # noqa: BLE001 - exotic values compare unequal
        unchanged = False
    if unchanged:
        raise ApplyOpsError("no_op", f"{field!r} is already set to that value.")

    if spec is None:
        return
    from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget

    spec_type = str(getattr(spec, "type", "") or "")
    if not input_spec_is_literal_widget(spec):
        raise ApplyOpsError(
            "wrong_channel",
            f"field {field!r} is a socket; use upsert_link instead of a literal write.",
        )
    from vibecomfy.porting.edit.validate import validate_literal_value

    issues = validate_literal_value(
        value=op.value,
        spec=spec,
        class_type=str(node.class_type),
        input_name=field,
        context="typed edit",
    )
    for issue in issues:
        if getattr(issue, "severity", "error") == "error":
            raise ApplyOpsError(issue.code, issue.message)
    accepted = _LITERAL_TYPES.get(spec_type)
    if accepted is not None and (
        not isinstance(op.value, accepted)
        or (isinstance(op.value, bool) and spec_type in {"INT", "FLOAT"})
    ):
        raise ApplyOpsError(
            "type_mismatch",
            f"field {field!r} expects {spec_type}, got {type(op.value).__name__}.",
        )


def _known_output(node: Any, slot: str | int, provider: Any) -> bool:
    # RRSYN2-4: ONE canonical renderer-alias seam decides admission.  The
    # frozen render may emit ``TYPE_N`` aliases (``AUDIO_0``), integer
    # slots, and ``unknown_N`` fallbacks; the resolver accepts an alias only
    # when its index exists AND its type/name evidence agrees, so admission
    # and authority replay cannot disagree about a rendered endpoint.
    from vibecomfy.porting.edit._interpret import canonical_renderer_output

    return (
        canonical_renderer_output(node, slot, provider=provider) is not None
    )


def _unknown_output_detail(
    node: Any,
    slot: str | int,
    provider: Any,
) -> str:
    """Rejection evidence: node, offered alias, valid slots, evidence source."""
    from vibecomfy.porting.edit._interpret import renderer_output_slots

    valid_slots, sources = renderer_output_slots(node, provider)
    return (
        f"output {str(slot)!r} is not resolvable on {node.class_type!r} "
        f"(node uid={getattr(node, 'uid', '')!r}); "
        f"valid output slots: {list(valid_slots)}; "
        f"evidence source: {list(sources)}"
    )



def _known_input(node: Any, field: str, provider: Any) -> bool:
    if field in (getattr(node, "inputs", None) or {}):
        return True
    # Connected sockets live in the retained edge set rather than the literal
    # ``node.inputs`` mapping.  Preserve the submit graph's named UI socket as
    # valid replay evidence, symmetric with ``_known_output`` above.
    metadata = getattr(node, "metadata", None) or {}
    ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    inputs_ui = ui.get("inputs") if isinstance(ui, Mapping) else None
    if isinstance(inputs_ui, (list, tuple)):
        for item in inputs_ui:
            if isinstance(item, Mapping) and str(item.get("name", "")) == field:
                return True
            if isinstance(item, str) and item == field:
                return True
    schema = _schema_for(node, provider)
    inputs = getattr(schema, "inputs", None) or {}
    return isinstance(inputs, Mapping) and field in inputs


def _validate_link(workflow: Any, op: UpsertLinkOp, provider: Any) -> None:
    from vibecomfy.porting.edit._interpret import canonical_renderer_output

    source = _require_node(workflow, op.source.uid)
    target = _require_node(workflow, op.target.uid)
    resolved_output = canonical_renderer_output(
        source, op.source.output_slot, provider=provider
    )
    if resolved_output is None:
        raise ApplyOpsError(
            "unknown_port",
            _unknown_output_detail(source, op.source.output_slot, provider),
        )
    if not _known_input(target, op.target.input_field, provider):
        raise ApplyOpsError(
            "unknown_port",
            f"input {op.target.input_field!r} is not present on {target.class_type!r}.",
        )
    # Keep typed-op validation on the same socket compatibility rail as the
    # Python surface.  The IR COW layer stores named endpoints, so only the
    # schema/retained metadata type evidence belongs here.
    from vibecomfy.porting.edit._interpret import _input_socket_type, _output_socket_type
    from vibecomfy.schema import socket_types_compatible

    source_type = _output_socket_type(source, op.source.output_slot)
    if source_type is None and resolved_output != op.source.output_slot:
        source_type = _output_socket_type(source, resolved_output)
    if source_type is None:
        metadata = getattr(source, "metadata", None) or {}
        names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
        types = metadata.get("output_types") if isinstance(metadata, Mapping) else None
        if isinstance(names, (list, tuple)) and isinstance(types, (list, tuple)):
            try:
                source_type = str(types[list(names).index(resolved_output)])
            except (ValueError, IndexError):
                source_type = None
    target_type = _input_socket_type(target, op.target.input_field, provider)
    if source_type and target_type and not socket_types_compatible(source_type, target_type):
        raise ApplyOpsError(
            "incompatible_socket_types",
            f"Cannot wire {source_type} into {target_type} on {target.class_type}.{op.target.input_field}.",
        )


def _validate_one(workflow: Any, op: EditOp, provider: Any) -> None:
    if isinstance(op, SetNodeFieldOp):
        _validate_field(workflow, op, provider)
    elif isinstance(op, SetModeOp):
        from vibecomfy.workflow import mode_to_litegraph

        if isinstance(op.mode, bool) or not isinstance(op.mode, int):
            raise ApplyOpsError(
                "type_mismatch",
                f"mode expects an integer, got {type(op.mode).__name__}.",
            )
        if op.mode not in MODE_LABELS:
            raise ApplyOpsError(
                "invalid_mode_value",
                "mode must be one of 0, 2, or 4.",
            )
        if op.target.scope_path:
            try:
                sg_node = build_recursive_edit_index(workflow).node(op.target.scope_path, op.target.uid).node
            except RecursiveEditError as exc:
                raise ApplyOpsError(exc.code, str(exc), retryable=False) from exc
            if int(sg_node.get("mode", 0) or 0) == int(op.mode):
                raise ApplyOpsError("no_op", f"node {op.target.uid!r} already has mode {op.mode}.")
        else:
            node = _require_node(workflow, op.target.uid)
            if mode_to_litegraph(node.mode) == op.mode:
                raise ApplyOpsError("no_op", f"node {op.target.uid!r} already has mode {op.mode}.")
    elif isinstance(op, UpsertLinkOp):
        if op.source.scope_path or op.target.scope_path:
            raise _unsupported_recursive(op)
        _validate_link(workflow, op, provider)
    elif isinstance(op, RemoveLinkOp):
        if op.target is None:
            raise ApplyOpsError("wrong_channel", "IR edits remove links by target input, not link id.")
        if op.target.scope_path:
            raise _unsupported_recursive(op)
        _require_node(workflow, op.target.uid)
        connected = any(
            str(edge.to_node) == str(next(
                node_id
                for node_id, node in workflow.nodes.items()
                if str(getattr(node, "uid", "") or "") == op.target.uid
            ))
            and str(edge.to_input) == op.target.input_field
            for edge in workflow.edges
        )
        if not connected:
            raise ApplyOpsError("no_op", f"input {op.target.input_field!r} has no link to remove.")
    elif isinstance(op, RemoveNodeOp):
        if op.target.scope_path:
            raise _unsupported_recursive(op)
        _require_node(workflow, op.target.uid)
    elif isinstance(op, AddNodeOp):
        anchor = op.anchor
        group_title = getattr(anchor, "group_title", None) if anchor is not None else None
        if group_title and not any(
            isinstance(group, Mapping) and str(group.get("title") or "") == str(group_title)
            for group in (getattr(workflow, "groups", None) or ())
        ):
            raise ApplyOpsError(
                "unsupported_operation",
                f"group {group_title!r} is not present in the retained canvas; "
                "capture the current canvas/export before assigning group placement.",
                retryable=False,
            )
        if any(_operation_scope_paths(op)):
            raise _unsupported_recursive(op)
        if op.uid is not None and _node_by_uid(workflow, op.uid) is not None:
            raise ApplyOpsError("duplicate_identity", f"uid {op.uid!r} already exists.")
        if op.node_id is not None and str(op.node_id) in {
            str(node_id) for node_id in workflow.nodes
        }:
            raise ApplyOpsError("duplicate_identity", f"node id {op.node_id!r} already exists.")
        from vibecomfy.porting.edit._interpret import canonical_renderer_output

        for input_name, source in op.inputs.items():
            source_node = _require_node(workflow, source.uid)
            resolved = canonical_renderer_output(
                source_node, source.output_slot, provider=provider
            )
            if resolved is None:
                raise ApplyOpsError(
                    "unknown_port",
                    _unknown_output_detail(
                        source_node, source.output_slot, provider
                    ),
                )
            if not isinstance(input_name, str) or not input_name:
                raise ApplyOpsError("invalid_arguments", "add_node input names must be non-empty.")
        if provider is not None:
            from vibecomfy.schema import schema_for, schema_registry_empty

            schema = schema_for(provider, op.class_type)
            if schema is None and not schema_registry_empty(provider):
                raise ApplyOpsError(
                    "unknown_schema", f"class_type {op.class_type!r} has no known schema."
                )
            schema_inputs = getattr(schema, "inputs", None) or {}
            if schema is not None and isinstance(schema_inputs, Mapping):
                from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget

                # ``widget_field_names`` is evidence, not authority.  Accept
                # positional/widget carriers only when the retained frozen
                # schema snapshot names the same authored roster; a caller
                # cannot mint an arbitrary field by placing it in the tuple.
                snapshot = getattr(provider, "snapshot", None)
                raw_schema = (
                    snapshot.schemas.get(op.class_type)
                    if snapshot is not None and hasattr(snapshot, "schemas")
                    else None
                )
                roster: set[str] = set()
                if isinstance(raw_schema, Mapping):
                    for key in ("widget_input_order", "widget_names"):
                        values = raw_schema.get(key)
                        if isinstance(values, (list, tuple)):
                            roster.update(str(name) for name in values)
                    values = raw_schema.get("input_order")
                    if isinstance(values, (list, tuple)):
                        roster.update(
                            str(name) for name in values
                            if str(name).startswith("widget_")
                        )
                if not roster and snapshot is not None:
                    authored_order = getattr(snapshot, "input_order", {}).get(op.class_type, ())
                    if isinstance(authored_order, (list, tuple)):
                        roster.update(str(name) for name in authored_order)
                forged = [
                    str(name) for name in op.widget_field_names
                    if str(name) not in roster
                    and str(name) not in schema_inputs
                ]
                if forged:
                    raise ApplyOpsError(
                        "unknown_field",
                        f"widget_field_names are not present in the frozen authored roster: {forged!r}",
                    )

                for field in op.fields:
                    from vibecomfy.porting.edit.value_defaults import VALUE_DEFAULT_FIELDS_MARKER

                    if field == VALUE_DEFAULT_FIELDS_MARKER:
                        marker = op.fields[field]
                        if (
                            op.uid is None
                            or op.node_id is None
                            or not isinstance(marker, (list, tuple))
                            or not all(isinstance(name, str) and name for name in marker)
                            or any(name not in schema_inputs for name in marker)
                        ):
                            raise ApplyOpsError(
                                "invalid_value_default_replay_marker",
                                "value-default protection is valid only on a canonical landed add-node operation",
                            )
                        continue
                    spec = schema_inputs.get(field)
                    if spec is None:
                        # ``widget_N`` is a positional carrier explicitly
                        # retained by the frozen snapshot. Its reconstructed
                        # NodeSchema intentionally omits that raw alias; the
                        # AddNodeOp classification is the sole canonical
                        # evidence that it belongs to the widget channel.
                        if field in op.widget_field_names:
                            continue
                        raise ApplyOpsError(
                            "unknown_field",
                            f"field {field!r} is not present on {op.class_type!r}.",
                        )
                    if not input_spec_is_literal_widget(spec):
                        raise ApplyOpsError(
                            "wrong_channel", f"field {field!r} must be wired through inputs."
                        )
                for field in op.inputs:
                    if field not in schema_inputs:
                        raise ApplyOpsError(
                            "unknown_port", f"input {field!r} is not present on {op.class_type!r}."
                        )
    elif isinstance(op, SubgraphInterfaceOp):
        if op.scope_path:
            raise _unsupported_recursive(op)
        if getattr(workflow, "definitions", None):
            raise _unsupported_recursive(op)


def validate_typed_ops(
    workflow: Any,
    ops: Sequence[EditOp],
    *,
    schema_provider: Any,
) -> Any:
    """Validate *and simulate* an op batch, returning its post-state copy.

    The input IR is never mutated. Any invalid operation aborts the whole batch.
    Sequential simulation is important for add-then-wire batches. Admission is
    the T2.1 ``admit_operation`` gateway.
    """
    from vibecomfy.porting.edit._interpret import _evaluate_operation

    working = workflow
    for op in ops:
        evaluation = _evaluate_operation(
            working,
            op,
            schema_provider=schema_provider,
        )
        if evaluation.outcome == "noop":
            raise ApplyOpsError("no_op", "operation is already applied", retryable=False)
        if evaluation.outcome != "staged":
            diagnostic = evaluation.diagnostics[0] if evaluation.diagnostics else None
            raise ApplyOpsError(
                diagnostic.code if diagnostic is not None else "apply_rejected",
                diagnostic.message if diagnostic is not None else "canonical application rejected",
                retryable=False,
            )
        working = evaluation.workflow
    return working


__all__ = ["ApplyOpsError", "validate_typed_ops"]
