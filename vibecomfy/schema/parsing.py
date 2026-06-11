from __future__ import annotations

from typing import Any

from .types import InputSpec, NodeSchema, OutputSpec


def schema_from_object_info(class_type: str, info: dict[str, Any]) -> NodeSchema:
    inputs: dict[str, InputSpec] = {}
    input_groups = info.get("input", {})
    if isinstance(input_groups, dict):
        for group_name, group in input_groups.items():
            required = group_name == "required"
            if isinstance(group, dict):
                for name, spec in group.items():
                    inputs[str(name)] = parse_input_spec(spec, required=required)
    outputs = parse_outputs(info)
    pack = first_string(info, "pack", "package", "category")
    return NodeSchema(class_type=class_type, pack=pack, inputs=inputs, outputs=outputs)


def schema_from_index_row(row: dict[str, Any]) -> NodeSchema | None:
    class_type = first_string(row, "class_type", "class_name", "name", "id", "node", "display_name")
    if not class_type:
        return None
    pack = first_string(row, "pack", "package", "source", "category")
    inputs: dict[str, InputSpec] = {}
    raw_inputs = row.get("inputs") or row.get("input")
    if isinstance(raw_inputs, dict):
        if "required" in raw_inputs or "optional" in raw_inputs:
            for group_name, group in raw_inputs.items():
                if isinstance(group, dict):
                    for name, spec in group.items():
                        inputs[str(name)] = parse_input_spec(spec, required=group_name == "required")
        else:
            for name, spec in raw_inputs.items():
                inputs[str(name)] = parse_input_spec(spec, required=False)
    elif isinstance(raw_inputs, list):
        for item in raw_inputs:
            if isinstance(item, str):
                inputs[item] = InputSpec(required=False)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                inputs[item["name"]] = parse_input_spec(item, required=bool(item.get("required", False)))
    return NodeSchema(class_type=class_type, pack=pack, inputs=inputs, outputs=parse_index_outputs(row))


def parse_index_outputs(row: dict[str, Any]) -> list[OutputSpec]:
    output_types = row.get("output_types") or row.get("outputs") or row.get("output")
    if isinstance(output_types, str):
        parts = [part.strip() for part in output_types.split(",")]
        return [OutputSpec(type=part) for part in parts if part]
    if isinstance(output_types, list):
        outputs: list[OutputSpec] = []
        for item in output_types:
            if isinstance(item, dict):
                outputs.append(OutputSpec(type=first_string(item, "type"), name=first_string(item, "name")))
            elif item is not None:
                outputs.append(OutputSpec(type=str(item)))
        return outputs
    return []


def parse_input_spec(raw: Any, *, required: bool) -> InputSpec:
    typ: Any = None
    attrs: dict[str, Any] = {}
    choices: list[Any] | None = None
    if isinstance(raw, (list, tuple)) and raw:
        typ = raw[0]
        if isinstance(typ, list):
            choices = list(typ)
            typ = "CHOICE"
        if len(raw) > 1 and isinstance(raw[1], dict):
            attrs = raw[1]
    elif isinstance(raw, dict):
        typ = raw.get("type")
        attrs = raw
        if isinstance(raw.get("choices"), list):
            choices = list(raw["choices"])
    elif isinstance(raw, str):
        typ = raw
    return InputSpec(
        type=str(typ) if typ is not None else None,
        required=required,
        default=attrs.get("default"),
        choices=choices,
        min=attrs.get("min"),
        max=attrs.get("max"),
    )


def parse_outputs(info: dict[str, Any]) -> list[OutputSpec]:
    raw_outputs = info.get("output") or []
    names = info.get("output_name") or info.get("output_names") or []
    outputs: list[OutputSpec] = []
    if isinstance(raw_outputs, (list, tuple)):
        for index, raw in enumerate(raw_outputs):
            name = names[index] if isinstance(names, (list, tuple)) and index < len(names) else None
            outputs.append(OutputSpec(type=str(raw) if raw is not None else None, name=str(name) if name else None))
    return outputs


def first_string(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None
