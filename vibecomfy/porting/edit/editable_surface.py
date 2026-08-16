"""Instance-hydrated edit surface for one node.

Widgets (literal-editable) and sockets (wiring-only) are separate channels.
Hydration reads the INSTANCE — ``raw_widgets``, ``metadata._ui``, the retained
IR — not only the class schema. Unknown names carry ``name_confidence="none"``
and are never given a positional alias (``widget_0`` / ``output_0``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence

from vibecomfy.porting.authoring_surface import (
    input_spec_is_literal_widget,
    input_spec_is_socket_only,
    normalized_input_type,
)
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.schema import schema_for


SchemaStatus = Literal["known", "provisional", "unknown"]
NameConfidence = Literal["schema", "instance", "none"]
_POSITIONAL_ALIAS = re.compile(r"^(?:widget|output|input|slot)_\d+$")
_PROVISIONAL_PROVIDERS = frozenset(
    {"comfy_registry_provisional", "workflow_json_provisional"}
)

# Closed role map (PARAMETER_TWEAK_TARGET_TERMS + the architecture aliases).
# strength|scale|weight|aggressiveness → strength; seed → seed; rows/cols stay.
_ROLE_BY_NAME: dict[str, str] = {
    "seed": "seed",
    "noise_seed": "seed",
    "strength": "strength",
    "scale": "strength",
    "weight": "strength",
    "aggressiveness": "strength",
    "rows": "rows",
    "cols": "cols",
    "cfg": "cfg",
    "denoise": "denoise",
    "steps": "step",
    "step": "step",
    "width": "width",
    "height": "height",
    "prompt": "prompt",
}


@dataclass(frozen=True, slots=True)
class LiteralField:
    """A widget-backed value the agent may assign as a literal."""

    name: str
    kind: str
    value: Any
    role: str | None
    schema_status: SchemaStatus
    name_confidence: NameConfidence


@dataclass(frozen=True, slots=True)
class InputSocket:
    """A named input that is writable only as wiring."""

    name: str
    socket_type: str | None
    connected: bool
    schema_status: SchemaStatus
    name_confidence: NameConfidence
    writable: Literal["wiring"] = "wiring"


@dataclass(frozen=True, slots=True)
class OutputPort:
    """A named typed output port."""

    name: str
    socket_type: str | None
    schema_status: SchemaStatus
    name_confidence: NameConfidence


@dataclass(frozen=True, slots=True)
class EditableSurface:
    """Per-node projection of what the Python surface can address by name."""

    class_type: str
    schema_status: SchemaStatus
    literals: tuple[LiteralField, ...]
    inputs: tuple[InputSocket, ...]
    outputs: tuple[OutputPort, ...]

    def literal_names(self) -> frozenset[str]:
        return frozenset(field.name for field in self.literals if field.name)

    def socket_names(self) -> frozenset[str]:
        return frozenset(slot.name for slot in self.inputs if slot.name)


def field_role(name: str) -> str | None:
    key = name.strip().casefold()
    if not key:
        return None
    if key in _ROLE_BY_NAME:
        return _ROLE_BY_NAME[key]
    return None


def is_positional_alias(name: str) -> bool:
    return bool(_POSITIONAL_ALIAS.fullmatch(name))


def schema_status_for(node: Any, *, schema_provider: Any = None) -> SchemaStatus:
    """Instance-first status; a live schema provider may refine ``unknown``."""
    from vibecomfy.porting.emit.emit_prepare import _schema_status_from_node

    status = _schema_status_from_node(node)
    if status != "unknown":
        return status
    class_type = _node_class_type(node)
    schema = schema_for(schema_provider, class_type) if schema_provider is not None else None
    if schema is None:
        return "unknown"
    source = str(getattr(schema, "source_provider", "") or "")
    ignored = {str(item) for item in (getattr(schema, "ignored_evidence", ()) or ())}
    if source in _PROVISIONAL_PROVIDERS or "not_runtime_validated" in ignored:
        return "provisional"
    return "known" if source else "unknown"


def editable_surface_for(
    node: Any,
    *,
    schema_provider: Any = None,
    edges: Sequence[Any] | None = None,
) -> EditableSurface:
    """Hydrate the writable surface of *node* from the instance, then schema."""
    class_type = _node_class_type(node)
    status = schema_status_for(node, schema_provider=schema_provider)
    schema = schema_for(schema_provider, class_type) if schema_provider is not None else None
    schema_inputs = getattr(schema, "inputs", None) or {}
    if not isinstance(schema_inputs, Mapping):
        schema_inputs = {}

    connected = _connected_input_names(node, edges)
    socket_names = _instance_socket_names(node, schema_inputs, connected)
    literals = _instance_literals(node, schema_inputs, socket_names, status)
    inputs = _instance_input_sockets(
        node, schema_inputs, socket_names, connected, status
    )
    outputs = _instance_outputs(node, schema, status)
    return EditableSurface(
        class_type=class_type,
        schema_status=status,
        literals=tuple(literals),
        inputs=tuple(inputs),
        outputs=tuple(outputs),
    )


def _node_class_type(node: Any) -> str:
    if isinstance(node, Mapping):
        return str(node.get("type") or node.get("class_type") or "")
    return str(getattr(node, "class_type", "") or getattr(node, "type", "") or "")


def _node_id(node: Any) -> str:
    if isinstance(node, Mapping):
        value = node.get("id")
    else:
        value = getattr(node, "id", None)
    return "" if value is None else str(value)


def _metadata(node: Any) -> Mapping[str, Any]:
    if isinstance(node, Mapping):
        raw = node.get("metadata")
    else:
        raw = getattr(node, "metadata", None)
    return raw if isinstance(raw, Mapping) else {}


def _instance_payload(node: Any) -> Mapping[str, Any]:
    """Retained instance furniture (IR ``metadata['_ui']`` or a mapping node)."""
    metadata = _metadata(node)
    retained = metadata.get("_ui")
    if isinstance(retained, Mapping):
        return retained
    if isinstance(node, Mapping):
        return node
    return {}


def _kind_from_value(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "STRING"
    if isinstance(value, dict):
        return "DICT"
    if isinstance(value, (list, tuple)):
        return "LIST"
    return "UNKNOWN"


def _kind_from_spec(spec: Any, value: Any) -> str:
    if spec is not None:
        choices = getattr(spec, "choices", None)
        if isinstance(choices, (list, tuple)) and choices:
            return "COMBO"
        type_name = normalized_input_type(getattr(spec, "type", None))
        if type_name:
            return type_name
    return _kind_from_value(value)


def _name_confidence(name: str, *, in_schema: bool) -> NameConfidence:
    if not name or is_positional_alias(name):
        return "none"
    if in_schema:
        return "schema"
    return "instance"


def _is_link_value(value: Any) -> bool:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return True
    return False


def _connected_input_names(node: Any, edges: Sequence[Any] | None) -> set[str]:
    names: set[str] = set()
    node_id = _node_id(node)
    if edges:
        for edge in edges:
            to_node = getattr(edge, "to_node", None)
            to_input = getattr(edge, "to_input", None)
            if to_node is None and isinstance(edge, Mapping):
                to_node = edge.get("to_node")
                to_input = edge.get("to_input")
            if node_id and str(to_node) == node_id and to_input:
                names.add(str(to_input))
    payload = _instance_payload(node)
    payload_inputs = payload.get("inputs")
    if isinstance(payload_inputs, list):
        for slot in payload_inputs:
            if not isinstance(slot, Mapping):
                continue
            name = slot.get("name")
            if name and slot.get("link") is not None:
                names.add(str(name))
    if isinstance(node, Mapping):
        raw_inputs = node.get("inputs")
        if isinstance(raw_inputs, list):
            for slot in raw_inputs:
                if not isinstance(slot, Mapping):
                    continue
                name = slot.get("name")
                if name and slot.get("link") is not None:
                    names.add(str(name))
    return names


def _instance_socket_names(
    node: Any,
    schema_inputs: Mapping[str, Any],
    connected: set[str],
) -> set[str]:
    names = set(connected)
    for name, spec in schema_inputs.items():
        if input_spec_is_socket_only(spec):
            names.add(str(name))
    inputs = getattr(node, "inputs", None)
    if isinstance(inputs, Mapping):
        for name, value in inputs.items():
            key = str(name)
            spec = schema_inputs.get(key)
            if spec is not None and input_spec_is_literal_widget(spec):
                continue
            if _is_link_value(value) or (spec is not None and input_spec_is_socket_only(spec)):
                names.add(key)
    payload = _instance_payload(node)
    payload_inputs = payload.get("inputs")
    if isinstance(payload_inputs, list):
        for slot in payload_inputs:
            if not isinstance(slot, Mapping):
                continue
            name = slot.get("name")
            if not name:
                continue
            spec = schema_inputs.get(str(name))
            socket_type = slot.get("type")
            if spec is not None and input_spec_is_literal_widget(spec):
                continue
            if slot.get("link") is not None or (
                spec is not None and input_spec_is_socket_only(spec)
            ):
                names.add(str(name))
                continue
            type_name = normalized_input_type(socket_type)
            if type_name and type_name.isupper() and spec is None:
                # Instance socket with no schema: treat uppercase Comfy types
                # as wiring, never as a guessed widget.
                names.add(str(name))
    return names


def _widget_items(node: Any) -> list[tuple[str, Any, bool]]:
    """Return (name, value, named) pairs. ``named`` is False when the name is unknown."""
    items: list[tuple[str, Any, bool]] = []
    seen: set[str] = set()

    widgets = getattr(node, "widgets", None)
    if isinstance(node, Mapping) and not isinstance(widgets, Mapping):
        widgets = node.get("widgets")
    if isinstance(widgets, Mapping):
        for name, value in widgets.items():
            key = str(name)
            if is_positional_alias(key):
                items.append(("", value, False))
                continue
            seen.add(key)
            items.append((key, value, True))

    raw_widgets = getattr(node, "raw_widgets", None)
    if isinstance(node, Mapping) and raw_widgets is None:
        raw_widgets = node.get("raw_widgets") or node.get("_raw_widgets")
    values = getattr(raw_widgets, "values", None) if raw_widgets is not None else None
    if values is None and isinstance(raw_widgets, Mapping):
        values = raw_widgets.get("values")
    if isinstance(values, Mapping):
        for name, value in values.items():
            key = str(name)
            if key in seen or is_positional_alias(key):
                continue
            seen.add(key)
            items.append((key, value, True))
    elif isinstance(values, list) and not seen:
        resolution = compact_widget_names_for_node(node)
        for index, value in enumerate(values):
            name = resolution.names[index] if index < len(resolution.names) else None
            if isinstance(name, str) and name and not is_positional_alias(name):
                if name in seen:
                    continue
                seen.add(name)
                items.append((name, value, True))
            else:
                items.append(("", value, False))

    payload = _instance_payload(node)
    widget_rows = payload.get("widgets_values")
    if isinstance(widget_rows, list) and not items:
        resolution = compact_widget_names_for_node(node)
        for index, value in enumerate(widget_rows):
            name = resolution.names[index] if index < len(resolution.names) else None
            if isinstance(name, str) and name and not is_positional_alias(name):
                items.append((name, value, True))
            else:
                items.append(("", value, False))
    return items


def _instance_literals(
    node: Any,
    schema_inputs: Mapping[str, Any],
    socket_names: set[str],
    status: SchemaStatus,
) -> list[LiteralField]:
    fields: list[LiteralField] = []
    seen: set[str] = set()
    for name, value, named in _widget_items(node):
        if named and name in socket_names:
            continue
        spec = schema_inputs.get(name) if named else None
        if spec is not None and input_spec_is_socket_only(spec):
            continue
        confidence = _name_confidence(name, in_schema=spec is not None) if named else "none"
        display = name if named and confidence != "none" else ""
        if display:
            if display in seen:
                continue
            seen.add(display)
        fields.append(
            LiteralField(
                name=display,
                kind=_kind_from_spec(spec, value),
                value=value,
                role=field_role(display) if display else None,
                schema_status=status,
                name_confidence=confidence,
            )
        )

    inputs = getattr(node, "inputs", None)
    if isinstance(inputs, Mapping):
        for name, value in inputs.items():
            key = str(name)
            if key in socket_names or key in seen or is_positional_alias(key):
                continue
            if _is_link_value(value):
                continue
            spec = schema_inputs.get(key)
            if spec is not None and input_spec_is_socket_only(spec):
                continue
            if spec is None and key in socket_names:
                continue
            seen.add(key)
            fields.append(
                LiteralField(
                    name=key,
                    kind=_kind_from_spec(spec, value),
                    value=value,
                    role=field_role(key),
                    schema_status=status,
                    name_confidence=_name_confidence(key, in_schema=spec is not None),
                )
            )
    return fields


def _instance_input_sockets(
    node: Any,
    schema_inputs: Mapping[str, Any],
    socket_names: set[str],
    connected: set[str],
    status: SchemaStatus,
) -> list[InputSocket]:
    sockets: list[InputSocket] = []
    seen: set[str] = set()

    def _add(name: str, socket_type: str | None, *, in_schema: bool) -> None:
        if not name or name in seen or is_positional_alias(name):
            if name and is_positional_alias(name) and name not in seen:
                sockets.append(
                    InputSocket(
                        name="",
                        socket_type=socket_type,
                        connected=name in connected,
                        schema_status=status,
                        name_confidence="none",
                    )
                )
                seen.add(name)
            return
        seen.add(name)
        sockets.append(
            InputSocket(
                name=name,
                socket_type=socket_type,
                connected=name in connected,
                schema_status=status,
                name_confidence=_name_confidence(name, in_schema=in_schema),
            )
        )

    payload = _instance_payload(node)
    payload_inputs = payload.get("inputs")
    if isinstance(payload_inputs, list):
        for slot in payload_inputs:
            if not isinstance(slot, Mapping):
                continue
            name = slot.get("name")
            if not name:
                continue
            key = str(name)
            if key not in socket_names:
                continue
            spec = schema_inputs.get(key)
            socket_type = str(slot.get("type") or "") or None
            if spec is not None and getattr(spec, "type", None):
                socket_type = str(spec.type)
            _add(key, socket_type, in_schema=spec is not None)

    if isinstance(node, Mapping):
        raw_inputs = node.get("inputs")
        if isinstance(raw_inputs, list):
            for slot in raw_inputs:
                if not isinstance(slot, Mapping):
                    continue
                name = slot.get("name")
                if not name:
                    continue
                key = str(name)
                if key not in socket_names or key in seen:
                    continue
                spec = schema_inputs.get(key)
                _add(key, str(slot.get("type") or "") or None, in_schema=spec is not None)

    for name in sorted(socket_names):
        if name in seen:
            continue
        spec = schema_inputs.get(name)
        socket_type = str(getattr(spec, "type", "") or "") or None if spec is not None else None
        _add(name, socket_type, in_schema=spec is not None)
    return sockets


def _instance_outputs(
    node: Any,
    schema: Any,
    status: SchemaStatus,
) -> list[OutputPort]:
    from vibecomfy.porting.emit.emit_prepare import _node_output_specs

    ports: list[OutputPort] = []
    seen: set[str] = set()
    specs = _node_output_specs(node)
    if not specs:
        payload_outputs = _instance_payload(node).get("outputs")
        if isinstance(payload_outputs, list):
            specs = []
            for index, output in enumerate(payload_outputs):
                if not isinstance(output, Mapping):
                    continue
                name = output.get("name")
                specs.append(
                    {
                        "index": index,
                        "name": str(name) if isinstance(name, str) and name else "",
                        "type": str(output.get("type") or "").strip() or None,
                    }
                )
    schema_outputs = list(getattr(schema, "outputs", None) or []) if schema is not None else []

    for spec in specs:
        raw_name = spec.get("name") or ""
        socket_type = spec.get("type")
        in_schema = False
        if raw_name:
            in_schema = any(getattr(item, "name", None) == raw_name for item in schema_outputs)
        confidence = _name_confidence(raw_name, in_schema=in_schema)
        display = raw_name if confidence != "none" else ""
        if display:
            if display in seen:
                continue
            seen.add(display)
        ports.append(
            OutputPort(
                name=display,
                socket_type=str(socket_type) if socket_type else None,
                schema_status=status,
                name_confidence=confidence,
            )
        )

    if not ports and schema_outputs:
        for item in schema_outputs:
            name = getattr(item, "name", None)
            if not isinstance(name, str) or not name or is_positional_alias(name):
                continue
            if name in seen:
                continue
            seen.add(name)
            out_type = getattr(item, "type", None)
            ports.append(
                OutputPort(
                    name=name,
                    socket_type=str(out_type) if out_type else None,
                    schema_status=status,
                    name_confidence="schema",
                )
            )
    return ports


def surfaces_for_workflow(
    workflow: Any,
    *,
    schema_provider: Any = None,
) -> dict[str, EditableSurface]:
    """Hydrate every node in a ``VibeWorkflow`` (keyed by node id)."""
    nodes = getattr(workflow, "nodes", None) or {}
    edges = getattr(workflow, "edges", None) or ()
    return {
        str(node_id): editable_surface_for(
            node, schema_provider=schema_provider, edges=edges
        )
        for node_id, node in nodes.items()
    }


def iter_literal_names(surface: EditableSurface) -> Iterable[str]:
    return surface.literal_names()


__all__ = [
    "EditableSurface",
    "InputSocket",
    "LiteralField",
    "NameConfidence",
    "OutputPort",
    "SchemaStatus",
    "editable_surface_for",
    "field_role",
    "is_positional_alias",
    "iter_literal_names",
    "schema_status_for",
    "surfaces_for_workflow",
]
