from __future__ import annotations

from vibecomfy.ingest.normalize import door_get_nodes
from dataclasses import asdict, dataclass, field
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from vibecomfy.porting.authoring_names import constructor_aliases_for_class_types
from vibecomfy.porting.authoring_surface import (
    input_spec_is_literal_widget,
    input_spec_is_socket_only,
)

READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT = "avoidable_positional_output"
READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY = "output_name_ambiguity"
READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED = "schema_backed_widget_alias_not_resolved"
READABILITY_WARNING_HIDDEN_MODEL_FILENAME = "hidden_model_filename"
READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE = "local_helper_copy_in_strict_template"
READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL = "long_one_line_node_call"
READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED = "generated_template_not_formatted"
READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG = "generated_variable_name_too_long"
READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND = "subgraph_input_unbound"
READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS = "schema_unknown_kwarg_hidden_by_extras"
READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID = "locked_variable_alias_invalid"
READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION = "locked_variable_alias_collision"
READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING = "locked_variable_alias_missing"
READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION = "locked_variable_uid_collision"
READABILITY_WARNING_CODES: frozenset[str] = frozenset(
    {
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
        READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
        READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
        READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
        READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
        READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
        READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
        READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
        READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
    }
)
EmissionSeverity = Literal["error", "warning", "info"]

@dataclass(slots=True)
class EmissionDiagnostic:
    """A readability diagnostic recorded during emission.

    These are always *warnings* (or info) - hard errors are surfaced through
    `PortConvertValidation` parity / schema failures, not here.
    """

    code: str
    message: str
    severity: EmissionSeverity = "warning"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

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
    status: str = "installed"

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

    Unknown socket types (``None`` or ``\"*\"``) are treated as
    **compatible with everything** (the same contract as
    ``socket_types_compatible`` in ``vibecomfy.schema.validate``).

    Rows are always sorted by ``class_type`` for determinism.
    """
    from vibecomfy.schema import is_workflow_stub_schema, schema_for, schemas_for
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
            if bool(getattr(schema_provider, "listing_only", False)):
                # Index providers intentionally enumerate IDs without reading
                # every pack.  Signature generation is an explicit full-schema
                # request, so fetch each exact class here, one at a time.
                for key in raw:
                    if not isinstance(key, str):
                        continue
                    schema = schema_for(schema_provider, key)
                    if schema is not None:
                        schemas_map[key] = schema
            else:
                schemas_map.update(
                    {
                        str(key): value
                        for key, value in raw.items()
                        if isinstance(key, str) and value is not None
                    }
                )

    rows: list[NodeSignatureRow] = []
    for class_type in sorted(schemas_map):
        schema = schemas_map[class_type]
        # A listing-only surface may be composed with a materialized provider;
        # unresolved entries must never become fake empty signatures.
        if schema is None:
            continue
        if is_workflow_stub_schema(schema):
            continue
        inputs = _build_input_signature_fields(schema)
        outputs = _build_output_signature_fields(schema)
        confidence = float(getattr(schema, "confidence", 1.0) or 1.0)
        pack = getattr(schema, "pack", None) or None
        source_provider = str(getattr(schema, "source_provider", "") or "")
        ignored = {str(item) for item in (getattr(schema, "ignored_evidence", ()) or ())}
        status = (
            "schema_placeholder"
            if source_provider == "comfy_registry_class_map" or "schema_backed_resolution_required" in ignored
            else "provisional_schema"
            if "not_runtime_validated" in ignored
            else "installed"
        )

        # Compatibility filtering
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
                status=status,
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


def signature_row_from_surface(surface: Any, *, pack: str | None = None) -> NodeSignatureRow:
    """Build a catalog row from an instance-hydrated ``EditableSurface``.

    Literals and sockets are already split by the surface; this does not
    reclassify them from class schema alone.
    """
    inputs = [
        InputSignatureField(name=field.name, type=field.kind, required=False, default=field.value)
        for field in surface.literals
        if field.name
    ]
    inputs.extend(
        InputSignatureField(name=slot.name, type=slot.socket_type, required=False)
        for slot in surface.inputs
        if slot.name
    )
    outputs = [
        OutputSignatureField(name=port.name or None, type=port.socket_type)
        for port in surface.outputs
    ]
    status = (
        "installed"
        if surface.schema_status == "known"
        else "provisional_schema"
        if surface.schema_status == "provisional"
        else "schema_placeholder"
    )
    return NodeSignatureRow(
        class_type=surface.class_type,
        inputs=inputs,
        outputs=outputs,
        source_confidence=1.0 if surface.schema_status == "known" else 0.0,
        pack=pack,
        status=status,
    )


def _iter_graph_nodes(nodes: Any):
    """Yield node mappings or IR nodes from a UI graph or retained workflow."""
    ir_nodes = getattr(nodes, "nodes", None)
    if ir_nodes is not None and not isinstance(nodes, Mapping) and isinstance(ir_nodes, Mapping):
        yield from ir_nodes.values()
        return
    if isinstance(nodes, Mapping):
        raw = door_get_nodes(nodes)
        if isinstance(raw, (list, tuple, Mapping)):
            nodes = raw
        elif isinstance(nodes, Mapping) and all(
            not isinstance(v, Mapping) or "class_type" in v or "type" in v
            for v in nodes.values()
        ):
            nodes = list(nodes.values())
        else:
            return
    if isinstance(nodes, Mapping):
        yield from nodes.values()
    elif isinstance(nodes, (list, tuple)):
        yield from (
            node
            for node in nodes
            if isinstance(node, Mapping) or getattr(node, "class_type", None) is not None
        )


def _frozen_widget_names_by_uid(nodes: Any) -> Mapping[str, tuple[str, ...]]:
    """Sealed per-uid widget-name roster (P0 ``WorkflowSnapshot.field_snapshot``).

    Empty for graphs that carry no seal — plain UI dicts and unsealed
    workflows resolve through the live surface alone.
    """
    try:
        from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid  # noqa: PLC0415

        return frozen_widget_names_by_uid(nodes)
    except Exception:  # noqa: BLE001 - filtering must not fail on exotic graphs
        return {}


def _sealed_roster_for_node(
    frozen_names: Mapping[str, tuple[str, ...]], node: Any
) -> Sequence[str]:
    """Names the frozen table seals onto *node* (uid first, then raw id)."""
    uid = getattr(node, "uid", None)
    if not uid and isinstance(node, Mapping):
        uid = node.get("uid") or node.get("id")
    if not uid:
        return ()
    return frozen_names.get(str(uid), ())


def filter_signature_rows_to_in_graph_nodes(
    rows: list[NodeSignatureRow],
    nodes: Any,
    *,
    schema_provider: Any = None,
) -> list[NodeSignatureRow]:
    """Restrict literal inputs to fields the in-graph nodes can actually resolve.

    PR-D (Tripo): a class schema may advertise literal fields (from the current
    ComfyUI object_info) that a *specific* node instance cannot resolve because
    it was saved against an older schema (e.g. ``TripoTextToModelNode`` gained
    ``geometry_quality`` in a later version; old nodes lack the widget).  For
    classes with nodes in the graph, literal fields that NONE of those nodes
    can resolve are dropped from the row so the catalog does not advertise
    them as writable; socket inputs are never dropped.  Classes without
    in-graph nodes keep their full schema (they may be added new).
    P3-SIGNATURE-LITERALS: *schema_provider* — the frozen
    ``SchemaSnapshot``/``FrozenSchemaSnapshotProvider`` domain of record when
    one is bound — reaches editable-surface resolution, and the sealed
    per-uid widget-name roster from ``WorkflowSnapshot.field_snapshot``
    (P0-WIDGET-CANON) is the name authority.  Two invariants on top of PR-D:

    * a literal field sealed onto an in-graph node by the frozen roster is
      NEVER dropped, even when the live provider/object_info disagrees
      (stale-live must not erase a real field); positional ``widget_N``
      carriers therefore keep their snapshot-backed names discoverable;
    * rows are only ever restricted, never extended — no signature row is
      invented for a field absent from both the snapshot and the provider.
    """

    from vibecomfy.porting.edit.editable_surface import editable_surface_for

    frozen_names = _frozen_widget_names_by_uid(nodes)

    nodes_by_class: dict[str, list[Any]] = {}
    for node in _iter_graph_nodes(nodes):
        if isinstance(node, Mapping):
            class_type = str(node.get("type") or node.get("class_type") or "")
        else:
            class_type = str(getattr(node, "class_type", "") or getattr(node, "type", "") or "")
        if class_type:
            nodes_by_class.setdefault(class_type, []).append(node)

    filtered: list[NodeSignatureRow] = []
    for row in rows:
        nodes_of_class = nodes_by_class.get(row.class_type)
        if not nodes_of_class:
            filtered.append(row)
            continue
        resolvable: set[str] = set()
        for node in nodes_of_class:
            try:
                surface = editable_surface_for(
                    node,
                    schema_provider=schema_provider,
                    name_authority=frozen_names,
                )
            except Exception:
                continue
            resolvable.update(surface.literal_names())
            # Snapshot wins over live drift: a sealed name is never stripped,
            # independent of surface-hydration quirks.
            resolvable.update(_sealed_roster_for_node(frozen_names, node))
        inputs: list[InputSignatureField] = [
            field
            for field in row.inputs
            if input_spec_is_socket_only(field)
            or not input_spec_is_literal_widget(field)
            or field.name in resolvable
        ]
        if len(inputs) == len(row.inputs):
            filtered.append(row)
            continue
        filtered.append(
            NodeSignatureRow(
                class_type=row.class_type,
                inputs=inputs,
                outputs=row.outputs,
                source_confidence=row.source_confidence,
                pack=row.pack,
                status=row.status,
            )
        )
    return filtered


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
    class_type_aliases: Mapping[str, str] | None = None,
) -> str:
    """Format a list of ``NodeSignatureRow`` as a deterministic text catalog.

    Each row is rendered as a Python-like function signature::

        def CheckpointLoaderSimple(ckpt_name: COMBO = ...) -> model:MODEL, clip:CLIP, vae:VAE:

    The output is sorted by ``class_type``.

    If *show_pack* is ``True``, a ``# pack: ...`` comment line precedes
    each signature.  If *show_confidence* is ``True``, a ``# confidence:
    0.XX`` suffix is appended.
    """
    from vibecomfy.identity.codec import to_python_identifier

    aliases = dict(class_type_aliases or constructor_aliases_for_class_types(row.class_type for row in rows))
    lines: list[str] = []
    for row in sorted(rows, key=lambda r: r.class_type):
        prefix_parts: list[str] = []
        if show_pack and row.pack:
            prefix_parts.append(f"# pack: {row.pack}")
        if row.status != "installed":
            prefix_parts.append(f"# status: {row.status}")
        suffix_parts: list[str] = []
        if show_confidence and row.source_confidence < 1.0:
            suffix_parts.append(f"confidence: {row.source_confidence:.2f}")

        param_parts: list[str] = []
        literal_fields: list[str] = []
        socket_inputs: list[str] = []
        for input_field in row.inputs:
            # Optional socket inputs commonly have a semantic default of None,
            # which means callers may omit them. Rendering only non-None
            # defaults made optional sockets look mandatory to the authoring
            # model (for example IPAdapterAdvanced.image_negative/attn_mask).
            has_default = input_field.default is not None or not input_field.required
            default_str = " = ..." if has_default else ""
            type_str = f": {input_field.type}" if input_field.type else ""
            name_ident = to_python_identifier(input_field.name)
            if input_spec_is_literal_widget(input_field):
                literal_fields.append(name_ident)
            elif input_spec_is_socket_only(input_field) or not input_spec_is_literal_widget(input_field):
                socket_inputs.append(name_ident)
            if input_field.choices is not None:
                choices = input_field.choices
                if len(choices) > _SIGNATURE_ENUM_LIMIT:
                    shown = choices[:_SIGNATURE_ENUM_LIMIT]
                    extra = len(choices) - _SIGNATURE_ENUM_LIMIT
                    rendered = ", ".join(f'"{c}"' for c in shown)
                    type_str += f'[{rendered}, \u2026 ({_SIGNATURE_ENUM_LIMIT} shown), \u2026 +{extra} more \u2014 ask the user for an exact name if you need one not listed]'
                else:
                    rendered = ", ".join(f'"{c}"' for c in choices)
                    type_str += f"[{rendered}]"
            param_parts.append(f"{name_ident}{type_str}{default_str}")

        if literal_fields or socket_inputs:
            note_parts: list[str] = []
            if literal_fields:
                note_parts.append(f"literal fields: {', '.join(literal_fields)}")
            if socket_inputs:
                note_parts.append(f"socket inputs: {', '.join(socket_inputs)}")
            prefix_parts.append("# authoring: " + "; ".join(note_parts))

        return_parts: list[str] = []
        for output in row.outputs:
            out_name = output.name
            out_type = output.type
            if out_name and out_type:
                return_parts.append(f"{to_python_identifier(out_name)}:{out_type}")
            elif out_type:
                return_parts.append(out_type)
            elif out_name:
                return_parts.append(to_python_identifier(out_name))
            else:
                return_parts.append("Any")

        params = ", ".join(param_parts)
        returns = ", ".join(return_parts) if return_parts else "None"
        constructor_name = aliases.get(row.class_type) or constructor_aliases_for_class_types(
            [row.class_type]
        )[row.class_type]
        if constructor_name != row.class_type:
            prefix_parts.append(f"# class_type: {row.class_type}")
        sig = f"def {constructor_name}({params}) -> {returns}:"

        comment_parts = prefix_parts + suffix_parts
        if comment_parts:
            sig = "  ".join(comment_parts) + f"\n{sig}"

        lines.append(sig)

    return "\n".join(lines) + "\n"

__all__ = [
    'READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT',
    'READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY',
    'READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED',
    'READABILITY_WARNING_HIDDEN_MODEL_FILENAME',
    'READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE',
    'READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL',
    'READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED',
    'READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG',
    'READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND',
    'READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS',
    'READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID',
    'READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION',
    'READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING',
    'READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION',
    'READABILITY_WARNING_CODES',
    'EmissionSeverity',
    'EmissionDiagnostic',
    'InputSignatureField',
    'OutputSignatureField',
    'NodeSignatureRow',
    'emit_available_node_signatures',
    'filter_signature_rows_to_in_graph_nodes',
    'format_signature_rows',
    'signature_row_from_surface',
]
