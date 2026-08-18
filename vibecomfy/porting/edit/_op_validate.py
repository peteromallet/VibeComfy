"""Typed-op pre-apply validation (schema/port + no-op) for the edit authority.

These checks run BEFORE any copy-on-write mutation so a semantically invalid
candidate (made-up field, wrong value type, unknown port, or a value that is
already current) never reaches ``apply_edits_cow`` / ``verify_apply``.  They
complement the structural + replay + emit/exit gates in
:mod:`vibecomfy.porting.edit.apply_gate` and ``guard_exit_ui``.

The error codes here are part of the stable tool-loop taxonomy:

* ``unknown_target``  — the op names a uid absent from the retained IR.
* ``unknown_field``   — ``set_node_field`` names a field that is neither a
  schema input nor a widget/input already present on the node instance.
* ``unknown_port``    — a link op names an output slot or input field that the
  node does not declare.
* ``type_mismatch``   — the literal value's Python type does not match the
  schema input/widget type.
* ``no_op``           — the edit sets a field to its already-current value.

All functions are pure with respect to the workflow: they read the pre-state
and never mutate it.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)


class ApplyOpsError(ValueError):
    """A typed pre-apply rejection (argument/schema/port/no-op failure)."""

    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


# Value-type name → accepted Python types (best-effort, never over-strict).
_TYPE_ACCEPTORS: dict[str, tuple[type, ...]] = {
    "STRING": (str,),
    "INT": (int,),
    "FLOAT": (int, float),
    "BOOLEAN": (bool,),
}

# Socket types are never literal; setting them by value is a type mismatch.
_SOCKET_TYPES = frozenset(
    {
        "IMAGE",
        "LATENT",
        "CLIP",
        "CONDITIONING",
        "MODEL",
        "VAE",
        "CONTROL_NET",
        "STYLE_MODEL",
        "CLIP_VISION",
        "MASK",
        "AUDIO",
        "GLIGEN",
        "UPSCALE_MODEL",
        "SAMPLER",
        "SIGMAS",
        "NOISE",
        "GUIDER",
        "SCHEDULER",
    }
)


def _schema_input_spec(schema: Any, field: str) -> Any:
    if schema is None:
        return None
    inputs = getattr(schema, "inputs", None) or {}
    if not isinstance(inputs, Mapping):
        return None
    return inputs.get(field)


def _is_literal_widget_spec(spec: Any) -> bool:
    try:
        from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
    except Exception:  # noqa: BLE001 - best-effort classification
        return False
    return input_spec_is_literal_widget(spec)


def _node_by_uid(workflow: Any, uid: str) -> Any:
    if workflow is None:
        return None
    for node in workflow.nodes.values():
        if str(getattr(node, "uid", "") or "") == str(uid):
            return node
    return None


def _validate_set_node_field(workflow: Any, op: SetNodeFieldOp, schema_provider: Any) -> None:
    node = _node_by_uid(workflow, op.target.uid)
    if node is None:
        raise ApplyOpsError(
            "unknown_target",
            f"no IR node for uid {op.target.uid!r}.",
        )
    field = op.target.field_path
    schema = None
    if schema_provider is not None:
        from vibecomfy.schema import schema_for

        schema = schema_for(schema_provider, str(node.class_type))
    spec = _schema_input_spec(schema, field)
    widgets = getattr(node, "widgets", None) or {}
    inputs = getattr(node, "inputs", None) or {}

    # The field is legitimate if the schema declares it (as an input, widget or
    # otherwise) or the instance already carries it in either channel.
    positional_index: int | None = None
    known = spec is not None or field in widgets or field in inputs
    if not known:
        # RC-P1 positional fallback: real graphs store widget values as
        # ``widget_N`` keys (``widgets`` or ``inputs``) + ``raw_widgets``.
        # A named field that maps to a widget position resolves without the
        # schema (schema / object_info / widget-schema name sources).
        try:
            from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field
        except Exception:  # noqa: BLE001 - best-effort name resolution
            widget_index_for_field = None
        if widget_index_for_field is not None:
            try:
                positional_index = widget_index_for_field(
                    node, field, schema_provider=schema_provider
                )
            except Exception:  # noqa: BLE001 - resolution is best-effort
                positional_index = None
            known = positional_index is not None
    if not known:
        raise ApplyOpsError(
            "unknown_field",
            f"field {field!r} is not a schema input/widget of node "
            f"{str(node.class_type)!r} (uid {op.target.uid!r}).",
        )

    # No-op: setting a field to its already-current value produces no Δ.
    current = widgets.get(field, inputs.get(field))
    if positional_index is not None:
        positional_key = f"widget_{positional_index}"
        current = widgets.get(positional_key, inputs.get(positional_key, current))
    if field in widgets and _values_equal(widgets[field], op.value):
        raise ApplyOpsError("no_op", f"{field!r} is already set to that value.")
    if field in inputs and not isinstance(inputs.get(field), (list, tuple)):
        if _values_equal(inputs[field], op.value):
            raise ApplyOpsError("no_op", f"{field!r} is already set to that value.")
    if positional_index is not None:
        positional_key = f"widget_{positional_index}"
        if positional_key in widgets:
            positional_current = widgets[positional_key]
        elif positional_key in inputs:
            positional_current = inputs[positional_key]
        else:
            positional_current = None
        if _values_equal(positional_current, op.value):
            raise ApplyOpsError("no_op", f"{field!r} is already set to that value.")
    if spec is None and field not in widgets and field not in inputs and positional_index is None:
        raise ApplyOpsError("unknown_field", f"field {field!r} is not present on the node.")

    # Type check for literal widget fields only (socket fields are linked, not
    # set literally, so a non-widget socket value is a type mismatch).
    if spec is not None:
        spec_type = _normalized_type(getattr(spec, "type", None))
        if _is_literal_widget_spec(spec):
            _check_type(spec_type, op.value, field)
        elif spec_type in _SOCKET_TYPES or (spec_type and spec_type.isupper()):
            # A socket-typed field set by value is a misuse: reject as a type
            # mismatch rather than silently writing a literal into a wire.
            raise ApplyOpsError(
                "type_mismatch",
                f"field {field!r} is a socket input ({spec_type}); wire it with "
                "upsert_link instead of setting a literal value.",
            )


def _validate_set_mode(workflow: Any, op: SetModeOp, schema_provider: Any) -> None:
    del schema_provider
    node = _node_by_uid(workflow, op.target.uid)
    if node is None:
        raise ApplyOpsError("unknown_target", f"no IR node for uid {op.target.uid!r}.")
    from vibecomfy.workflow import mode_to_litegraph

    if mode_to_litegraph(node.mode) == mode_to_litegraph(op.mode):
        raise ApplyOpsError("no_op", f"node {op.target.uid!r} is already in that mode.")


def _validate_upsert_link(workflow: Any, op: UpsertLinkOp, schema_provider: Any) -> None:
    source = _node_by_uid(workflow, op.source.uid)
    target = _node_by_uid(workflow, op.target.uid)
    if source is None or target is None:
        raise ApplyOpsError(
            "unknown_target",
            f"unresolvable link endpoint uid {op.source.uid!r}/{op.target.uid!r}.",
        )
    _check_output_slot(source, op.source.output_slot, schema_provider)
    _check_input_field(target, op.target.input_field, schema_provider)


def _validate_remove_link(workflow: Any, op: RemoveLinkOp, schema_provider: Any) -> None:
    if op.target is None:
        raise ApplyOpsError("unknown_port", "remove_link requires a named target input.")
    target = _node_by_uid(workflow, op.target.uid)
    if target is None:
        raise ApplyOpsError("unknown_target", f"no IR node for uid {op.target.uid!r}.")
    _check_input_field(target, op.target.input_field, schema_provider)
    # No-op: nothing wired into that input yet.
    if not _input_is_connected(workflow, op.target.uid, op.target.input_field):
        raise ApplyOpsError("no_op", f"input {op.target.input_field!r} has no link to remove.")


def _validate_add_node(workflow: Any, op: AddNodeOp, schema_provider: Any) -> None:
    del workflow
    if schema_provider is not None:
        from vibecomfy.schema import schema_for

        schema = schema_for(schema_provider, op.class_type)
        if schema is None:
            # Unknown-schema class types are only allowed when the provider has
            # no knowledge at all (offline harness); a provider that knows
            # classes but not this one rejects the made-up node type.
            from vibecomfy.schema import schema_registry_empty

            if not schema_registry_empty(schema_provider):
                raise ApplyOpsError(
                    "unknown_field",
                    f"class_type {op.class_type!r} has no known schema.",
                )


def _normalized_type(value: Any) -> str:
    return str(value or "").strip()


def _check_type(spec_type: str, value: Any, field: str) -> None:
    if spec_type == "":
        return
    if isinstance(value, bool) and spec_type in ("INT", "FLOAT"):
        raise ApplyOpsError("type_mismatch", f"field {field!r} expects {spec_type}.")
    acceptors = _TYPE_ACCEPTORS.get(spec_type)
    if acceptors is None:
        return
    if not isinstance(value, acceptors):
        raise ApplyOpsError(
            "type_mismatch",
            f"field {field!r} expects {spec_type}, got {type(value).__name__}.",
        )


def _values_equal(a: Any, b: Any) -> bool:
    try:
        return bool(a == b)
    except Exception:  # noqa: BLE001 - unorderable/NaN-like values compare unequal
        return False


def _check_output_slot(node: Any, output_slot: Any, schema_provider: Any) -> None:
    from vibecomfy.schema import schema_for

    # Resolve the slot against the node's instance metadata first, then schema.
    metadata = getattr(node, "metadata", None) or {}
    names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
    if isinstance(names, (list, tuple)) and names:
        if isinstance(output_slot, int):
            if 0 <= output_slot < len(names) and names[output_slot]:
                return
        elif str(output_slot) in [str(n) for n in names if n]:
            return
        if isinstance(output_slot, int) and 0 <= output_slot < len(names):
            return
    schema = schema_for(schema_provider, str(node.class_type))
    outputs = getattr(schema, "outputs", None) or []
    if isinstance(output_slot, int):
        if 0 <= output_slot < len(outputs):
            return
    else:
        for out in outputs:
            if str(getattr(out, "name", None) or "") == str(output_slot):
                return
    # Fall back to the instance's captured output specs.
    from vibecomfy.porting.edit._ir_utils import _output_specs as _specs_fn

    spec_list = _specs_fn(
        {"outputs": _instance_outputs(node)}, schema_provider, str(node.class_type)
    )
    for spec in spec_list:
        if str(spec.get("name")) == str(output_slot) or spec.get("index") == output_slot:
            return
    raise ApplyOpsError(
        "unknown_port",
        f"output slot {output_slot!r} does not exist on node {str(node.class_type)!r}.",
    )


def _instance_outputs(node: Any) -> list[dict[str, Any]]:
    metadata = getattr(node, "metadata", None) or {}
    if isinstance(metadata, Mapping):
        ui = metadata.get("_ui")
        if isinstance(ui, Mapping):
            outputs = ui.get("outputs")
            if isinstance(outputs, (list, tuple)):
                return [dict(o) if isinstance(o, Mapping) else {"name": str(o)} for o in outputs]
    return []


def _check_input_field(node: Any, input_field: str, schema_provider: Any) -> None:
    inputs = getattr(node, "inputs", None) or {}
    if isinstance(inputs, Mapping):
        if input_field in inputs:
            return
    widgets = getattr(node, "widgets", None) or {}
    if isinstance(widgets, Mapping) and input_field in widgets:
        return
    schema = None
    if schema_provider is not None:
        from vibecomfy.schema import schema_for

        schema = schema_for(schema_provider, str(node.class_type))
    if schema is not None:
        schema_inputs = getattr(schema, "inputs", None) or {}
        if isinstance(schema_inputs, Mapping) and input_field in schema_inputs:
            return
    raise ApplyOpsError(
        "unknown_port",
        f"input field {input_field!r} does not exist on node {str(node.class_type)!r}.",
    )


def _input_is_connected(workflow: Any, uid: str, input_field: str) -> bool:
    from vibecomfy.porting.edit._ir_utils import _workflow_uid_to_node_id

    uid_to_id = _workflow_uid_to_node_id(workflow)
    node_id = uid_to_id.get(str(uid))
    if node_id is None:
        return False
    for edge in workflow.edges:
        if str(edge.to_node) == str(node_id) and str(edge.to_input) == str(input_field):
            return True
    return False


def validate_typed_ops(workflow: Any, ops: Sequence[EditOp], *, schema_provider: Any) -> None:
    """Raise :class:`ApplyOpsError` for the first invalid op in *ops*.

    Pure: reads the pre-state, never mutates it.
    """
    for op in ops:
        if isinstance(op, SetNodeFieldOp):
            _validate_set_node_field(workflow, op, schema_provider)
        elif isinstance(op, SetModeOp):
            _validate_set_mode(workflow, op, schema_provider)
        elif isinstance(op, UpsertLinkOp):
            _validate_upsert_link(workflow, op, schema_provider)
        elif isinstance(op, RemoveLinkOp):
            _validate_remove_link(workflow, op, schema_provider)
        elif isinstance(op, AddNodeOp):
            _validate_add_node(workflow, op, schema_provider)
        # RemoveNodeOp / SubgraphInterfaceOp need no pre-apply schema check.


__all__ = [
    "ApplyOpsError",
    "validate_typed_ops",
]
