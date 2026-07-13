from __future__ import annotations

from typing import Any

_LITERAL_WIDGET_TYPES: frozenset[str] = frozenset(
    {
        "BOOLEAN",
        "BOOL",
        "CHOICE",
        "COMBO",
        "DICT",
        "DOUBLE",
        "ENUM",
        "FLOAT",
        "INT",
        "INTEGER",
        "JSON",
        "STRING",
        "STR",
        "TEXT",
    }
)
_NON_LITERAL_TYPES: frozenset[str] = frozenset({"", "HIDDEN", "UNKNOWN"})


def normalized_input_type(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def input_spec_is_literal_widget(spec: Any) -> bool:
    """Return whether a schema input is a widget-backed literal field."""

    if spec is None:
        return False
    choices = getattr(spec, "choices", None)
    if isinstance(choices, (list, tuple)) and choices:
        return True
    input_type = normalized_input_type(getattr(spec, "type", None))
    if input_type in _LITERAL_WIDGET_TYPES:
        return True
    if input_type in _NON_LITERAL_TYPES:
        return False
    return not input_type.isupper()


def input_spec_is_socket_only(spec: Any) -> bool:
    """Return whether a schema input should be connected, not set literally."""

    if spec is None or input_spec_is_literal_widget(spec):
        return False
    return normalized_input_type(getattr(spec, "type", None)) not in _NON_LITERAL_TYPES


__all__ = [
    "input_spec_is_literal_widget",
    "input_spec_is_socket_only",
    "normalized_input_type",
]
