"""Node signature catalog support for agent-edit surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InputSignatureField:
    """A single input field described by a schema for agent-edit catalog display."""

    name: str
    type: str | None = None
    required: bool = False
    default: Any = None
    choices: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class OutputSignatureField:
    """A single output slot described by a schema for agent-edit catalog display."""

    name: str | None = None
    type: str | None = None


@dataclass(frozen=True, slots=True)
class NodeSignatureRow:
    """A structured row describing one node type for the agent-edit catalog.

    Rows are produced by ``emit_available_node_signatures(...)`` from a
    ``SchemaProvider`` and may be filtered by socket-type compatibility.
    """

    class_type: str
    inputs: list[InputSignatureField]
    outputs: list[OutputSignatureField]
    source_confidence: float = 1.0
    pack: str | None = None


def emit_available_node_signatures(
    schema_provider: Any,
    *,
    focus_types: list[str] | None = None,
    compatible_input_type: str | None = None,
    compatible_output_type: str | None = None,
) -> list[NodeSignatureRow]:
    """Return structured rows for every known node type in *schema_provider*.

    Two query paths are supported:

    * **Enumeration** — when *focus_types* is ``None``, calls
      ``schema_provider.schemas()`` (or the protocol equivalent via
      ``schemas_for``) to enumerate every schema the provider knows.
    * **Focused / per-node** — when *focus_types* is a list of class-type
      strings, calls ``schema_provider.get_schema(...)`` for each entry.

    Optional compatibility filtering:

    * *compatible_input_type* — keep only rows that have at **least one
      output** socket type compatible with the given type (``MODEL`` →
      nodes whose output sockets can feed a ``MODEL`` input).
    * *compatible_output_type* — keep only rows that have at **least one
      input** socket type compatible with the given type (``MODEL`` →
      nodes that can consume a ``MODEL`` output).

    Both filters can be combined; when both are supplied a row must
    satisfy both.

    Unknown socket types (``None`` or ``"*"``) are treated as
    **compatible with everything** (the same contract as
    ``socket_types_compatible`` in ``vibecomfy.schema.validate``).

    Rows are always sorted by ``class_type`` for determinism.
    """
    from vibecomfy.schema import schema_for, schemas_for
    from vibecomfy.schema.validate import socket_types_compatible

    schemas_map: dict[str, Any] = {}

    if focus_types is not None:
        for class_type in focus_types:
            if not isinstance(class_type, str):
                continue
            schema = schema_for(schema_provider, class_type)
            if schema is not None:
                schemas_map[class_type] = schema
    else:
        raw = schemas_for(schema_provider)
        if raw is not None:
            schemas_map.update(
                {str(key): value for key, value in raw.items() if isinstance(key, str)}
            )

    rows: list[NodeSignatureRow] = []
    for class_type in sorted(schemas_map):
        schema = schemas_map[class_type]
        inputs = _build_input_signature_fields(schema)
        outputs = _build_output_signature_fields(schema)
        confidence = float(getattr(schema, "confidence", 1.0) or 1.0)
        pack = getattr(schema, "pack", None) or None

        if compatible_input_type is not None:
            if not any(
                socket_types_compatible(output.type, compatible_input_type)
                for output in outputs
            ):
                continue

        if compatible_output_type is not None:
            if not any(
                socket_types_compatible(compatible_output_type, input_.type)
                for input_ in inputs
            ):
                continue

        rows.append(
            NodeSignatureRow(
                class_type=class_type,
                inputs=inputs,
                outputs=outputs,
                source_confidence=confidence,
                pack=pack,
            )
        )

    if compatible_output_type is not None:
        rows.sort(
            key=lambda row: (
                _compatible_output_signature_rank(row, compatible_output_type),
                row.class_type,
            )
        )

    return rows


def _compatible_output_signature_rank(row: NodeSignatureRow, compatible_output_type: str) -> int:
    compatible_type = str(compatible_output_type).upper()
    input_types = {str(field.type or "").upper() for field in row.inputs}
    output_types = {str(field.type or "").upper() for field in row.outputs}
    auth_gated = any(type_name.startswith("AUTH_") for type_name in input_types)

    if compatible_type == "IMAGE" and not auth_gated:
        if output_types & {"VIDEO", "AUDIO"}:
            return 0
        if not row.outputs and row.class_type.lower().startswith("save"):
            return 1

    if output_types and compatible_type in output_types:
        return 3
    if auth_gated:
        return 4
    return 2


def _build_input_signature_fields(schema: Any) -> list[InputSignatureField]:
    inputs = getattr(schema, "inputs", None) or {}
    fields: list[InputSignatureField] = []
    for name, spec in inputs.items():
        if not isinstance(name, str):
            continue
        spec_type = getattr(spec, "type", None) if hasattr(spec, "type") else None
        spec_required = bool(getattr(spec, "required", False)) if hasattr(spec, "required") else False
        spec_default = getattr(spec, "default", None) if hasattr(spec, "default") else None
        spec_choices = getattr(spec, "choices", None) or ()
        spec_choices_tuple = tuple(str(c) for c in spec_choices) if spec_choices else None
        fields.append(
            InputSignatureField(
                name=name,
                type=str(spec_type) if spec_type is not None else None,
                required=spec_required,
                default=spec_default,
                choices=spec_choices_tuple,
            )
        )
    return fields


def _build_output_signature_fields(schema: Any) -> list[OutputSignatureField]:
    outputs = getattr(schema, "outputs", None) or []
    fields: list[OutputSignatureField] = []
    for output in outputs:
        out_type = getattr(output, "type", None) if hasattr(output, "type") else None
        out_name = getattr(output, "name", None) if hasattr(output, "name") else None
        fields.append(
            OutputSignatureField(
                name=str(out_name) if out_name is not None else None,
                type=str(out_type) if out_type is not None else None,
            )
        )
    return fields


_SIGNATURE_ENUM_LIMIT = 40


def format_signature_rows(
    rows: list[NodeSignatureRow],
    *,
    show_pack: bool = False,
    show_confidence: bool = False,
) -> str:
    """Format a list of ``NodeSignatureRow`` as a deterministic text catalog.

    Each row is rendered as a Python-like function signature::

        def CheckpointLoaderSimple(ckpt_name: COMBO = ...) -> MODEL, CLIP, VAE:

    The output is sorted by ``class_type``.

    If *show_pack* is ``True``, a ``# pack: ...`` comment line precedes
    each signature.  If *show_confidence* is ``True``, a ``# confidence:
    0.XX`` suffix is appended.
    """
    from vibecomfy.identity.codec import to_python_identifier

    lines: list[str] = []
    for row in sorted(rows, key=lambda r: r.class_type):
        prefix_parts: list[str] = []
        if show_pack and row.pack:
            prefix_parts.append(f"# pack: {row.pack}")
        suffix_parts: list[str] = []
        if show_confidence and row.source_confidence < 1.0:
            suffix_parts.append(f"confidence: {row.source_confidence:.2f}")

        param_parts: list[str] = []
        for field in row.inputs:
            has_default = field.default is not None
            default_str = " = ..." if has_default else ""
            type_str = f": {field.type}" if field.type else ""
            name_ident = to_python_identifier(field.name)
            if field.choices is not None:
                choices = field.choices
                if len(choices) > _SIGNATURE_ENUM_LIMIT:
                    shown = choices[:_SIGNATURE_ENUM_LIMIT]
                    extra = len(choices) - _SIGNATURE_ENUM_LIMIT
                    rendered = ", ".join(f'"{c}"' for c in shown)
                    type_str += f'[{rendered}, … ({_SIGNATURE_ENUM_LIMIT} shown), … +{extra} more — ask the user for an exact name if you need one not listed]'
                else:
                    rendered = ", ".join(f'"{c}"' for c in choices)
                    type_str += f"[{rendered}]"
            param_parts.append(f"{name_ident}{type_str}{default_str}")

        return_parts: list[str] = []
        for output in row.outputs:
            out_name = output.name
            out_type = output.type
            if out_name and out_type and out_name != out_type:
                return_parts.append(f"{out_name}:{out_type}")
            elif out_type:
                return_parts.append(out_type)
            elif out_name:
                return_parts.append(out_name)
            else:
                return_parts.append("Any")

        params = ", ".join(param_parts)
        returns = ", ".join(return_parts) if return_parts else "None"
        sig = f"def {row.class_type}({params}) -> {returns}:"

        comment_parts = prefix_parts + suffix_parts
        if comment_parts:
            sig = "  ".join(comment_parts) + f"\n{sig}"

        lines.append(sig)

    return "\n".join(lines) + "\n"


__all__ = [
    "InputSignatureField",
    "OutputSignatureField",
    "NodeSignatureRow",
    "emit_available_node_signatures",
    "format_signature_rows",
]
