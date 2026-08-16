"""Shared endpoint invariant for resolution, mutation, and projection.

Working-graph ports are authoritative. Schema may enrich a port that already
exists on the node, but it cannot authorize a slot that the node does not
have. A missing port is valid only when the class matches this module's
dynamic-port contract for that exact name.

A port is valid iff it is present in ``node["outputs"]`` / ``node["inputs"]``,
or the class matches the dynamic contract AND any schema-fallback slot is
bounds-verified against the working node before a link is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from vibecomfy.porting.authoring_surface import input_spec_is_socket_only

UNKNOWN_OUTPUT_SLOT = "unknown_output_slot"
UNKNOWN_TARGET_INPUT = "unknown_target_input"
SOURCE_SLOT_OUT_OF_BOUNDS = "source_slot_out_of_bounds"
TARGET_SLOT_OUT_OF_BOUNDS = "target_slot_out_of_bounds"
UNDECLARED_SYNTHETIC_PORT = "undeclared_synthetic_port"
GHOST_SCHEMA_OUTPUT = "ghost_schema_output"
DYNAMIC_PORT_OUT_OF_RANGE = "dynamic_port_out_of_range"
HELPER_DIRECTION_MISMATCH = "helper_direction_mismatch"

_IMAGE_CONCAT_MULTI_INPUT_RE = re.compile(r"^image_(\d+)$")
_LTX_IMAGE_SLOT_RE = re.compile(r"^num_images\.(image|index|strength)_(\d+)$")
_LTX_BARE_SLOT_RE = re.compile(r"^(image|index|strength)_(\d+)$")
_FIXED_SLOT_INPUT_RE = re.compile(r"^in_(\d+)$")
_NUMBERED_PREFIX_RE = re.compile(r"^(\d+)$")

_HELPER_INPUT_ALIASES = frozenset({"", "value", "*"})
_HELPER_OUTPUT_ALIASES = frozenset({"", "value", "*", "INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"})
_HELPER_CLASSES = frozenset({"Reroute", "GetNode", "SetNode", "PrimitiveNode"})


@dataclass(frozen=True, slots=True)
class PortResolution:
    """Result of resolving one named or indexed port against a working node."""

    ok: bool
    slot_index: int | None
    slot_name: str
    socket_type: str | None = None
    code: str | None = None
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    pending_materialize: bool = False


def working_sockets(node: Mapping[str, Any] | None, direction: str) -> list[Any]:
    if not isinstance(node, Mapping):
        return []
    key = "outputs" if direction == "output" else "inputs"
    sockets = node.get(key)
    return sockets if isinstance(sockets, list) else []


def socket_name_at(sockets: list[Any], index: int) -> str | None:
    if not (0 <= index < len(sockets)):
        return None
    socket = sockets[index]
    if isinstance(socket, Mapping):
        name = socket.get("name")
        if isinstance(name, str):
            return name
    return None


def socket_type_at(sockets: list[Any], index: int) -> str | None:
    if not (0 <= index < len(sockets)):
        return None
    socket = sockets[index]
    if isinstance(socket, Mapping):
        value = socket.get("type")
        if value is None:
            return None
        text = str(value).strip()
        return text or None
    return None


def named_socket_index(sockets: list[Any], name: str) -> int | None:
    for index, socket in enumerate(sockets):
        if isinstance(socket, Mapping) and socket.get("name") == name:
            return index
    return None


def class_type_of(node: Mapping[str, Any] | None) -> str:
    if not isinstance(node, Mapping):
        return ""
    return str(node.get("type") or node.get("class_type") or "")


def lookup_field_value(
    name: str,
    *,
    node: Mapping[str, Any] | None = None,
    fields: Mapping[str, Any] | None = None,
    schema: Any = None,
) -> Any:
    if isinstance(fields, Mapping) and name in fields:
        return fields[name]
    if isinstance(node, Mapping):
        widgets = node.get("widgets_values")
        if isinstance(widgets, Mapping) and name in widgets:
            return widgets[name]
        inputs = node.get("inputs")
        if isinstance(inputs, Mapping) and name in inputs:
            return inputs[name]
    spec = _schema_input_spec(schema, name)
    if spec is not None:
        return getattr(spec, "default", None)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _schema_input_spec(schema: Any, name: str) -> Any | None:
    inputs = getattr(schema, "inputs", None)
    if isinstance(inputs, Mapping):
        return inputs.get(name)
    return None


def _schema_inputs(schema: Any) -> Mapping[str, Any]:
    inputs = getattr(schema, "inputs", None)
    return inputs if isinstance(inputs, Mapping) else {}


def _schema_outputs(schema: Any) -> list[Any]:
    outputs = getattr(schema, "outputs", None)
    return list(outputs) if isinstance(outputs, list) else []


def schema_socket_index(schema: Any, direction: str, name: str) -> int | None:
    if direction == "output":
        for index, spec in enumerate(_schema_outputs(schema)):
            if getattr(spec, "name", None) == name:
                return index
        return None
    for index, (input_name, spec) in enumerate(_schema_inputs(schema).items()):
        if input_name == name and input_spec_is_socket_only(spec):
            return _schema_socket_ordinal(schema, name)
    return None


def _schema_socket_ordinal(schema: Any, name: str) -> int | None:
    ordinal = 0
    for input_name, spec in _schema_inputs(schema).items():
        if not input_spec_is_socket_only(spec):
            continue
        if input_name == name:
            return ordinal
        ordinal += 1
    return None


def schema_socket_type(schema: Any, direction: str, name: str) -> str | None:
    if direction == "output":
        for spec in _schema_outputs(schema):
            if getattr(spec, "name", None) == name:
                value = getattr(spec, "type", None)
                return str(value) if value else None
        return None
    spec = _schema_input_spec(schema, name)
    if spec is None:
        return None
    value = getattr(spec, "type", None)
    return str(value) if value else None


def _numbered_suffix(name: str, prefix: str) -> int | None:
    if not name.startswith(prefix):
        return None
    suffix = name[len(prefix):]
    if not _NUMBERED_PREFIX_RE.fullmatch(suffix):
        return None
    return int(suffix)


def _image_concat_index(name: str) -> int | None:
    match = _IMAGE_CONCAT_MULTI_INPUT_RE.fullmatch(name)
    if match is None:
        return None
    index = int(match.group(1))
    return index if index >= 1 else None


def _ltx_image_index(name: str) -> int | None:
    match = _LTX_IMAGE_SLOT_RE.fullmatch(name) or _LTX_BARE_SLOT_RE.fullmatch(name)
    if match is None:
        return None
    index = int(match.group(match.lastindex or 1))
    return index if index >= 1 else None


def _simple_calculator_variables(fields: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(fields, Mapping):
        return set()
    raw = fields.get("variables")
    if not isinstance(raw, str):
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _fixed_slot_index(name: str) -> int | None:
    match = _FIXED_SLOT_INPUT_RE.fullmatch(name)
    if match is None:
        return None
    return int(match.group(1))


def _declared_in_n_count(
    *,
    node: Mapping[str, Any] | None,
    fields: Mapping[str, Any] | None,
    schema: Any,
) -> int | None:
    io = None
    if isinstance(fields, Mapping):
        io = fields.get("io")
    if io is None and isinstance(node, Mapping):
        widgets = node.get("widgets_values")
        if isinstance(widgets, Mapping):
            io = widgets.get("io")
        properties = node.get("properties")
        if io is None and isinstance(properties, Mapping):
            vibe = properties.get("vibecomfy")
            if isinstance(vibe, Mapping):
                io = vibe.get("io")
    parsed = _parse_exec_io(io)
    if parsed is not None:
        return parsed
    existing = 0
    for socket in working_sockets(node, "input"):
        if isinstance(socket, Mapping) and _fixed_slot_index(str(socket.get("name") or "")) is not None:
            existing += 1
    if existing:
        return existing
    count = 0
    for input_name in _schema_inputs(schema):
        if _fixed_slot_index(input_name) is not None:
            count += 1
    return count or None


def _parse_exec_io(value: Any) -> int | None:
    payload = value
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, Mapping):
        return None
    inputs = payload.get("inputs")
    if isinstance(inputs, Mapping):
        return len(inputs)
    if isinstance(inputs, list):
        return len(inputs)
    return None


def helper_direction_allows(class_type: str, direction: str) -> bool:
    if class_type == "GetNode":
        return direction == "output"
    if class_type == "SetNode":
        return direction == "input"
    if class_type == "PrimitiveNode":
        return direction == "output"
    if class_type == "Reroute":
        return True
    return False


def dynamic_port_authorized(
    class_type: str,
    direction: str,
    name: str,
    *,
    node: Mapping[str, Any] | None = None,
    fields: Mapping[str, Any] | None = None,
    schema: Any = None,
) -> tuple[bool, str | None]:
    """Return whether *name* is a legitimate dynamic port for *class_type*.

    This is name-specific, not a class-level carte blanche. ``True`` means the
    exact name matches one concrete family and is inside that family's bound.
    """

    if not class_type or not isinstance(name, str):
        return False, None

    if class_type in _HELPER_CLASSES:
        if not helper_direction_allows(class_type, direction):
            return False, HELPER_DIRECTION_MISMATCH
        aliases = _HELPER_OUTPUT_ALIASES if direction == "output" else _HELPER_INPUT_ALIASES
        if class_type == "PrimitiveNode" and direction == "output":
            if name not in aliases:
                return False, DYNAMIC_PORT_OUT_OF_RANGE
            return True, None
        if name not in aliases:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return True, None

    if direction != "input":
        return False, None

    merged_fields = _merged_fields(node, fields)

    if class_type == "ImageConcatMulti":
        index = _image_concat_index(name)
        if index is None:
            return False, None
        count = _as_int(lookup_field_value("inputcount", node=node, fields=merged_fields, schema=schema))
        if count is None:
            count = 2
        if index > count:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return True, None

    if class_type == "LTXVImgToVideoInplaceKJ":
        index = _ltx_image_index(name)
        if index is None:
            return False, None
        count = _as_int(lookup_field_value("num_images", node=node, fields=merged_fields, schema=schema))
        if count is None:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        if index > count:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return True, None

    if class_type == "SimpleCalculator":
        index = _numbered_suffix(name, "input_")
        if index is None:
            return False, None
        if index < 1:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return True, None

    if class_type == "LTXVAddGuide":
        index = _numbered_suffix(name, "guide_")
        if index is None:
            return False, None
        if index < 1:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return True, None

    if class_type == "SimpleCalculatorKJ":
        variables = _simple_calculator_variables(merged_fields)
        if name in variables:
            return True, None
        if variables:
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return False, None

    fixed_index = _fixed_slot_index(name)
    if fixed_index is not None:
        count = _declared_in_n_count(node=node, fields=merged_fields, schema=schema)
        if count is None:
            return False, None
        if not (0 <= fixed_index < count):
            return False, DYNAMIC_PORT_OUT_OF_RANGE
        return True, None

    return False, None


def _merged_fields(
    node: Mapping[str, Any] | None,
    fields: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(node, Mapping):
        widgets = node.get("widgets_values")
        if isinstance(widgets, Mapping):
            merged.update(widgets)
        inputs = node.get("inputs")
        if isinstance(inputs, Mapping):
            merged.update(inputs)
    if isinstance(fields, Mapping):
        merged.update(fields)
    return merged


def contracted_dynamic_input_names(
    class_type: str,
    *,
    node: Mapping[str, Any] | None = None,
    fields: Mapping[str, Any] | None = None,
    schema: Any = None,
) -> list[str]:
    """Names the dynamic contract requires to exist on a newly built node."""

    merged_fields = _merged_fields(node, fields)
    names: list[str] = []
    if class_type == "ImageConcatMulti":
        count = _as_int(lookup_field_value("inputcount", node=node, fields=merged_fields, schema=schema))
        if count is None:
            count = 2
        names.extend(f"image_{index}" for index in range(1, count + 1))
    elif class_type == "LTXVImgToVideoInplaceKJ":
        count = _as_int(lookup_field_value("num_images", node=node, fields=merged_fields, schema=schema))
        if count is not None:
            for index in range(1, count + 1):
                names.extend(
                    (
                        f"num_images.image_{index}",
                        f"num_images.index_{index}",
                        f"num_images.strength_{index}",
                    )
                )
    elif class_type == "SimpleCalculatorKJ":
        names.extend(sorted(_simple_calculator_variables(merged_fields)))
    elif class_type == "Reroute":
        names.append("")
    elif class_type == "SetNode":
        names.append("value")
    return names


def schema_input_sockets_for_unwired_node(
    schema: Any,
    class_type: str,
    fields: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build declared socket inputs in schema order, excluding literal widgets."""

    sockets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, spec in _schema_inputs(schema).items():
        if not input_spec_is_socket_only(spec):
            continue
        socket_type = getattr(spec, "type", None) or "*"
        sockets.append({"name": name, "type": socket_type or "*", "link": None})
        seen.add(name)
    for name in contracted_dynamic_input_names(class_type, fields=fields, schema=schema):
        if name in seen:
            continue
        authorized, _reason = dynamic_port_authorized(
            class_type,
            "input",
            name,
            fields=fields,
            schema=schema,
        )
        if not authorized:
            continue
        socket_type = schema_socket_type(schema, "input", name) or _dynamic_family_type(class_type, name)
        sockets.append({"name": name, "type": socket_type or "*", "link": None})
        seen.add(name)
    return sockets


def _dynamic_family_type(class_type: str, name: str) -> str:
    if class_type == "ImageConcatMulti":
        return "IMAGE"
    if class_type == "LTXVImgToVideoInplaceKJ":
        if "index" in name:
            return "INT"
        if "strength" in name:
            return "FLOAT"
        return "IMAGE"
    if class_type == "LTXVAddGuide" and name.startswith("guide_"):
        return "IMAGE"
    if class_type == "SetNode":
        return "*"
    if class_type == "Reroute":
        return "*"
    return "*"


def resolve_working_port(
    node: Mapping[str, Any] | None,
    direction: str,
    name: str,
    *,
    schema: Any = None,
    fields: Mapping[str, Any] | None = None,
    class_type: str | None = None,
) -> PortResolution:
    """Resolve a named port using the working graph, then the dynamic contract.

    Schema never returns an index that is absent from the working node.
    """

    resolved_class = class_type or class_type_of(node)
    sockets = working_sockets(node, direction)
    index = named_socket_index(sockets, name)
    if index is not None:
        socket_type = socket_type_at(sockets, index) or schema_socket_type(schema, direction, name)
        return PortResolution(
            ok=True,
            slot_index=index,
            slot_name=name,
            socket_type=socket_type,
        )

    authorized, reason = dynamic_port_authorized(
        resolved_class,
        direction,
        name,
        node=node,
        fields=fields,
        schema=schema,
    )
    if not authorized:
        if direction == "output":
            schema_index = schema_socket_index(schema, "output", name)
            if schema_index is not None and not (0 <= schema_index < len(sockets)):
                return _fail(
                    GHOST_SCHEMA_OUTPUT,
                    f"{resolved_class} has no working output named {name!r}; schema slot {schema_index} is out of bounds.",
                    name=name,
                    class_type=resolved_class,
                    schema_index=schema_index,
                    working_count=len(sockets),
                )
            if schema_index is not None and 0 <= schema_index < len(sockets):
                working_name = socket_name_at(sockets, schema_index)
                working_is_placeholder = working_name in {name, "", None} or (
                    working_name is not None and _positional_output_alias_index(working_name) is not None
                )
                if working_is_placeholder:
                    return PortResolution(
                        ok=True,
                        slot_index=schema_index,
                        slot_name=name,
                        socket_type=socket_type_at(sockets, schema_index) or schema_socket_type(schema, "output", name),
                    )
            return _fail(
                UNKNOWN_OUTPUT_SLOT,
                f"{resolved_class} has no output named {name!r}.",
                name=name,
                class_type=resolved_class,
            )
        code = reason if reason in {DYNAMIC_PORT_OUT_OF_RANGE, HELPER_DIRECTION_MISMATCH} else UNKNOWN_TARGET_INPUT
        return _fail(
            code,
            f"{resolved_class} has no input named {name!r}.",
            name=name,
            class_type=resolved_class,
        )

    helper_index = _helper_existing_slot(resolved_class, direction, sockets)
    if helper_index is not None:
        return PortResolution(
            ok=True,
            slot_index=helper_index,
            slot_name=socket_name_at(sockets, helper_index) if socket_name_at(sockets, helper_index) is not None else name,
            socket_type=socket_type_at(sockets, helper_index),
        )

    schema_index = schema_socket_index(schema, direction, name)
    if schema_index is not None:
        if 0 <= schema_index < len(sockets):
            working_name = socket_name_at(sockets, schema_index)
            if working_name in {name, "", None}:
                return PortResolution(
                    ok=True,
                    slot_index=schema_index,
                    slot_name=name,
                    socket_type=socket_type_at(sockets, schema_index) or schema_socket_type(schema, direction, name),
                )
            if direction == "output":
                return _fail(
                    GHOST_SCHEMA_OUTPUT,
                    (
                        f"{resolved_class} schema output {name!r} maps to slot {schema_index}, "
                        f"but the working port is {working_name!r}."
                    ),
                    name=name,
                    class_type=resolved_class,
                    schema_index=schema_index,
                    working_name=working_name,
                )
        elif direction == "output":
            return _fail(
                GHOST_SCHEMA_OUTPUT,
                f"{resolved_class} schema output {name!r} is slot {schema_index}, outside working outputs.",
                name=name,
                class_type=resolved_class,
                schema_index=schema_index,
                working_count=len(sockets),
            )

    if direction == "output":
        return _fail(
            UNKNOWN_OUTPUT_SLOT,
            f"{resolved_class} has no output named {name!r}.",
            name=name,
            class_type=resolved_class,
        )

    return PortResolution(
        ok=True,
        slot_index=None,
        slot_name=name,
        socket_type=schema_socket_type(schema, "input", name) or _dynamic_family_type(resolved_class, name),
        pending_materialize=True,
    )


def _helper_existing_slot(class_type: str, direction: str, sockets: list[Any]) -> int | None:
    if class_type not in _HELPER_CLASSES or len(sockets) != 1:
        return None
    return 0


def _fail(code: str, message: str, **detail: Any) -> PortResolution:
    return PortResolution(
        ok=False,
        slot_index=None,
        slot_name=str(detail.get("name") or ""),
        code=code,
        message=message,
        detail=detail,
    )


def assert_source_slot_in_bounds(
    node: Mapping[str, Any] | None,
    slot_index: int | None,
    *,
    class_type: str | None = None,
    slot_name: str | None = None,
) -> PortResolution:
    resolved_class = class_type or class_type_of(node)
    outputs = working_sockets(node, "output")
    if not isinstance(slot_index, int) or not (0 <= slot_index < len(outputs)):
        return _fail(
            SOURCE_SLOT_OUT_OF_BOUNDS,
            f"{resolved_class} source slot {slot_index!r} is outside working outputs.",
            name=slot_name or "",
            class_type=resolved_class,
            slot_index=slot_index,
            working_count=len(outputs),
        )
    return PortResolution(
        ok=True,
        slot_index=slot_index,
        slot_name=slot_name or socket_name_at(outputs, slot_index) or str(slot_index),
        socket_type=socket_type_at(outputs, slot_index),
    )


def assert_target_slot_in_bounds(
    node: Mapping[str, Any] | None,
    slot_index: int | None,
    *,
    class_type: str | None = None,
    slot_name: str | None = None,
) -> PortResolution:
    resolved_class = class_type or class_type_of(node)
    inputs = working_sockets(node, "input")
    if not isinstance(slot_index, int) or not (0 <= slot_index < len(inputs)):
        return _fail(
            TARGET_SLOT_OUT_OF_BOUNDS,
            f"{resolved_class} target slot {slot_index!r} is outside working inputs.",
            name=slot_name or "",
            class_type=resolved_class,
            slot_index=slot_index,
            working_count=len(inputs),
        )
    return PortResolution(
        ok=True,
        slot_index=slot_index,
        slot_name=slot_name or socket_name_at(inputs, slot_index) or str(slot_index),
        socket_type=socket_type_at(inputs, slot_index),
    )


def projection_port_name(
    node: Mapping[str, Any] | None,
    direction: str,
    slot: Any,
    *,
    preferred_name: str | None = None,
) -> str | None:
    """Resolve a projection port by canonical name, then a validated index."""

    sockets = working_sockets(node, "output" if direction == "from" else "input")
    if isinstance(preferred_name, str) and preferred_name:
        index = named_socket_index(sockets, preferred_name)
        if index is not None:
            return preferred_name
    if isinstance(slot, str) and slot:
        index = named_socket_index(sockets, slot)
        if index is not None:
            return slot
        alias = _positional_output_alias_index(slot) if direction == "from" else None
        if alias is not None and 0 <= alias < len(sockets):
            name = socket_name_at(sockets, alias)
            if name:
                return name
    if isinstance(slot, int) and 0 <= slot < len(sockets):
        name = socket_name_at(sockets, slot)
        if isinstance(name, str) and name:
            return name
        if name == "":
            return ""
    return None


def _positional_output_alias_index(output_slot: Any) -> int | None:
    if not isinstance(output_slot, str):
        return None
    match = re.fullmatch(r"output_(\d+)", output_slot)
    if match is None:
        return None
    return int(match.group(1))


__all__ = [
    "DYNAMIC_PORT_OUT_OF_RANGE",
    "GHOST_SCHEMA_OUTPUT",
    "HELPER_DIRECTION_MISMATCH",
    "PortResolution",
    "SOURCE_SLOT_OUT_OF_BOUNDS",
    "TARGET_SLOT_OUT_OF_BOUNDS",
    "UNDECLARED_SYNTHETIC_PORT",
    "UNKNOWN_OUTPUT_SLOT",
    "UNKNOWN_TARGET_INPUT",
    "assert_source_slot_in_bounds",
    "assert_target_slot_in_bounds",
    "class_type_of",
    "contracted_dynamic_input_names",
    "dynamic_port_authorized",
    "helper_direction_allows",
    "named_socket_index",
    "projection_port_name",
    "resolve_working_port",
    "schema_input_sockets_for_unwired_node",
    "schema_socket_index",
    "working_sockets",
]
