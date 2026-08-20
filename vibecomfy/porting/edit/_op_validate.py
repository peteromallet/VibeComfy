"""Pure validation for already-lowered edit operations.

The Python authoring surface performs these checks while interpreting source.
Typed tool calls bypass that parser, so they must pass the same sort of checks
before reaching the retained :class:`~vibecomfy.porting.edit.EditSession` IR.
Validation is deliberately sequential: a later operation may refer to a node
added by an earlier operation in the same atomic batch.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from vibecomfy.porting.edit._ir_utils import apply_edit_cow
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)


class ApplyOpsError(ValueError):
    """Stable, typed rejection from the shared transactional edit gateway."""

    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


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


def _validate_field(workflow: Any, op: SetNodeFieldOp, provider: Any) -> None:
    node = _require_node(workflow, op.target.uid)
    field = str(op.target.field_path)
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
            from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field

            positional_index = widget_index_for_field(
                node, field, schema_provider=provider
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
    metadata = getattr(node, "metadata", None) or {}
    names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
    if isinstance(names, (list, tuple)):
        if isinstance(slot, int) and 0 <= slot < len(names):
            return True
    ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    outputs_ui = ui.get("outputs") if isinstance(ui, Mapping) else None
    if isinstance(outputs_ui, (list, tuple)):
        if isinstance(slot, int) and 0 <= slot < len(outputs_ui):
            return True
        for index, item in enumerate(outputs_ui):
            if isinstance(item, Mapping):
                if str(item.get("name", "")) == str(slot) or item.get("slot_index") == slot:
                    return True
            elif str(item) == str(slot) or index == slot:
                return True
        if str(slot) in {str(name) for name in names if name is not None}:
            return True
    schema = _schema_for(node, provider)
    outputs = getattr(schema, "outputs", None) or ()
    if isinstance(slot, int) and 0 <= slot < len(outputs):
        return True
    return any(str(getattr(item, "name", "") or "") == str(slot) for item in outputs)


def _known_input(node: Any, field: str, provider: Any) -> bool:
    if field in (getattr(node, "inputs", None) or {}):
        return True
    schema = _schema_for(node, provider)
    inputs = getattr(schema, "inputs", None) or {}
    return isinstance(inputs, Mapping) and field in inputs


def _validate_link(workflow: Any, op: UpsertLinkOp, provider: Any) -> None:
    source = _require_node(workflow, op.source.uid)
    target = _require_node(workflow, op.target.uid)
    if not _known_output(source, op.source.output_slot, provider):
        raise ApplyOpsError(
            "unknown_port",
            f"output {op.source.output_slot!r} is not present on {source.class_type!r}.",
        )
    if not _known_input(target, op.target.input_field, provider):
        raise ApplyOpsError(
            "unknown_port",
            f"input {op.target.input_field!r} is not present on {target.class_type!r}.",
        )


def _validate_one(workflow: Any, op: EditOp, provider: Any) -> None:
    if isinstance(op, SetNodeFieldOp):
        _validate_field(workflow, op, provider)
    elif isinstance(op, SetModeOp):
        node = _require_node(workflow, op.target.uid)
        from vibecomfy.workflow import mode_to_litegraph

        if mode_to_litegraph(node.mode) == op.mode:
            raise ApplyOpsError("no_op", f"node {op.target.uid!r} already has mode {op.mode}.")
    elif isinstance(op, UpsertLinkOp):
        _validate_link(workflow, op, provider)
    elif isinstance(op, RemoveLinkOp):
        if op.target is None:
            raise ApplyOpsError("wrong_channel", "IR edits remove links by target input, not link id.")
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
        _require_node(workflow, op.target.uid)
    elif isinstance(op, AddNodeOp):
        if op.scope_path:
            raise ApplyOpsError(
                "unsupported_scope", "typed add_node currently supports only the root graph."
            )
        if op.uid is not None and _node_by_uid(workflow, op.uid) is not None:
            raise ApplyOpsError("duplicate_identity", f"uid {op.uid!r} already exists.")
        if op.node_id is not None and str(op.node_id) in {
            str(node_id) for node_id in workflow.nodes
        }:
            raise ApplyOpsError("duplicate_identity", f"node id {op.node_id!r} already exists.")
        for input_name, source in op.inputs.items():
            source_node = _require_node(workflow, source.uid)
            if not _known_output(source_node, source.output_slot, provider):
                raise ApplyOpsError(
                    "unknown_port",
                    f"output {source.output_slot!r} is not present on {source_node.class_type!r}.",
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

                for field in op.fields:
                    spec = schema_inputs.get(field)
                    if spec is None:
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


def validate_typed_ops(
    workflow: Any,
    ops: Sequence[EditOp],
    *,
    schema_provider: Any,
) -> Any:
    """Validate *and simulate* an op batch, returning its post-state copy.

    The input IR is never mutated. Any invalid operation aborts the whole batch.
    Sequential simulation is important for add-then-wire batches.
    """
    working = workflow
    for op in ops:
        _validate_one(working, op, schema_provider)
        try:
            working = apply_edit_cow(working, op, schema_provider=schema_provider)
        except ApplyOpsError:
            raise
        except Exception as exc:
            raise ApplyOpsError("apply_failed", str(exc)) from exc
    return working


__all__ = ["ApplyOpsError", "validate_typed_ops"]
