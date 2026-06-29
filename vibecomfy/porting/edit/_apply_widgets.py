from __future__ import annotations

from typing import Any, Mapping

from ._apply_common import _issue
from ._apply_graph import _find_named_slot_index
from ._apply_types import ResolvedFieldRef
from vibecomfy.porting.object_info.consume import output_names as cached_output_names
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class
from vibecomfy.schema import InputSpec, schema_for


def _widget_name_for_input(slot: Any) -> str | None:
    if not isinstance(slot, Mapping):
        return None
    widget = slot.get("widget")
    if not isinstance(widget, Mapping):
        return None
    name = widget.get("name")
    return str(name) if isinstance(name, str) and name else None


def _widget_index_for_field(class_type: str, field_name: str) -> int | None:
    widget_names = effective_widget_names_for_class(class_type, allow_object_info_fallback=True)
    for index, name in enumerate(widget_names):
        if name == field_name:
            return index
    return None


def _widget_index_from_input_stubs(inputs: Any, field_name: str) -> int | None:
    if not isinstance(inputs, list):
        return None
    widget_index = 0
    for slot in inputs:
        widget_name = _widget_name_for_input(slot)
        if widget_name is None:
            continue
        if widget_name == field_name:
            return widget_index
        widget_index += 1
    return None


def _widget_names_from_input_stubs(inputs: Any) -> list[str]:
    if not isinstance(inputs, list):
        return []
    names: list[str] = []
    for slot in inputs:
        name = _widget_name_for_input(slot)
        if name is not None:
            names.append(name)
    return names


def _linked_widget_names(inputs: Any) -> set[str]:
    if not isinstance(inputs, list):
        return set()
    names: set[str] = set()
    for slot in inputs:
        if not isinstance(slot, Mapping):
            continue
        if not isinstance(slot.get("link"), int):
            continue
        name = _widget_name_for_input(slot)
        if name is not None:
            names.add(name)
    return names


def _reorder_names(node: Mapping[str, Any], class_type: str, axis: str) -> tuple[str, ...] | None:
    if axis == "widgets":
        values = node.get("widgets_values")
        if not isinstance(values, list):
            return None
        names = list(effective_widget_names_for_class(class_type, allow_object_info_fallback=True))
        if len(names) < len(values):
            recovered = _widget_names_from_input_stubs(node.get("inputs"))
            if len(recovered) >= len(values):
                names = recovered
        if len(names) != len(values) or any(not name for name in names):
            return None
        return tuple(names)

    outputs = node.get("outputs")
    if not isinstance(outputs, list):
        return None
    names: list[str] = []
    for output in outputs:
        if not isinstance(output, Mapping):
            return None
        name = output.get("name")
        if not isinstance(name, str) or not name:
            return None
        names.append(name)
    if len(set(names)) != len(names):
        return None
    return tuple(names)


def _write_widget_value(node: dict[str, Any], field_ref: ResolvedFieldRef, value: Any) -> None:
    widgets_values = node.get("widgets_values")
    if field_ref.widget_key is not None:
        if isinstance(widgets_values, dict):
            widgets_values[field_ref.widget_key] = value
            return
        if isinstance(widgets_values, Mapping):
            widgets_values = dict(widgets_values)
            widgets_values[field_ref.widget_key] = value
            node["widgets_values"] = widgets_values
            return
    assert field_ref.widget_index is not None
    if not isinstance(widgets_values, list):
        widgets_values = []
        node["widgets_values"] = widgets_values
    while len(widgets_values) <= field_ref.widget_index:
        widgets_values.append(None)
    widgets_values[field_ref.widget_index] = value


def _clear_linked_input_surface(node: dict[str, Any], field_ref: ResolvedFieldRef) -> None:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return
    if field_ref.input_slot_index is None or field_ref.input_slot_index >= len(inputs):
        return
    slot = inputs[field_ref.input_slot_index]
    if not isinstance(slot, dict):
        return
    if _widget_name_for_input(slot) == field_ref.target.field_path:
        del inputs[field_ref.input_slot_index]
        return
    if "link" in slot:
        slot["link"] = None


_NO_MATCH = object()


def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        for choice in choices:
            if isinstance(choice, str) and choice.replace("\\", "/") == normalized:
                return choice
    return _NO_MATCH


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _primitive_expected_type(value: Any) -> str | None:
    normalized = _normalize_type(value)
    if normalized in {"INT", "INTEGER"}:
        return "INT"
    if normalized in {"FLOAT", "DOUBLE"}:
        return "FLOAT"
    if normalized in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if normalized in {"STR", "STRING", "TEXT"}:
        return "STRING"
    return None


def _matches_primitive_type(value: Any, expected_type: str) -> bool:
    if expected_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "FLOAT":
        return ((isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float))
    if expected_type == "BOOLEAN":
        return isinstance(value, bool)
    if expected_type == "STRING":
        return isinstance(value, str)
    return True


def _validate_literal_value(
    *,
    value: Any,
    spec: InputSpec | None,
    class_type: str,
    input_name: str,
    context: str,
) -> list[PortIssue]:
    if spec is None:
        return []
    issues: list[PortIssue] = []
    choices = getattr(spec, "choices", None) or []
    if choices and value not in choices and _coerce_choice_value(value, choices) is _NO_MATCH:
        issues.append(
            _issue(
                "value_not_in_enum",
                f"{context} rejected {class_type}.{input_name}: value {value!r} is not in the declared enum.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "choices": list(choices),
                },
            )
        )
    min_value = getattr(spec, "min", None)
    max_value = getattr(spec, "max", None)
    if min_value is not None or max_value is not None:
        numeric = _as_number(value)
        if numeric is not None and (
            (min_value is not None and numeric < float(min_value))
            or (max_value is not None and numeric > float(max_value))
        ):
            issues.append(
                _issue(
                    "value_out_of_range",
                    f"{context} rejected {class_type}.{input_name}: value {value!r} is outside the declared range.",
                    detail={
                        "class_type": class_type,
                        "input": input_name,
                        "value": value,
                        "min": min_value,
                        "max": max_value,
                    },
                )
            )
    expected_type = _primitive_expected_type(getattr(spec, "type", None))
    if expected_type is not None and not _matches_primitive_type(value, expected_type):
        issues.append(
            _issue(
                "value_type_mismatch",
                f"{context} rejected {class_type}.{input_name}: expected {expected_type}, got {type(value).__name__}.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
            )
        )
    return issues


def _schema_output_type(
    schema_provider: Any,
    class_type: str,
    slot_index: int | None,
    slot_name: str,
) -> str | None:
    schema = schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    if slot_index is not None and 0 <= slot_index < len(outputs):
        return _normalize_type(getattr(outputs[slot_index], "type", None))
    for output in outputs:
        if getattr(output, "name", None) == slot_name:
            return _normalize_type(getattr(output, "type", None))
    cached_names = cached_output_names(class_type)
    if slot_index is not None and slot_index < len(cached_names):
        return _normalize_type(cached_names[slot_index])
    return None
