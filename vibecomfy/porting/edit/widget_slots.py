from __future__ import annotations

import re
from typing import Any, Mapping

from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field

_POSITIONAL_WIDGET_FIELD_RE = re.compile(r"(?:unused_)?widget_(\d+)")


def _find_named_slot_index(slots: Any, name: str) -> int | None:
    if not isinstance(slots, list):
        return None
    for index, item in enumerate(slots):
        if isinstance(item, dict) and item.get("name") == name:
            return index
    return None


def _widget_name_for_input(slot: Any) -> str | None:
    if not isinstance(slot, Mapping):
        return None
    widget = slot.get("widget")
    if not isinstance(widget, Mapping):
        return None
    name = widget.get("name")
    return str(name) if isinstance(name, str) and name else None


def _widget_index_for_field(
    node: Mapping[str, Any],
    field_name: str,
    *,
    schema_provider: Any | None = None,
) -> int | None:
    return widget_index_for_field(node, field_name, schema_provider=schema_provider)


def _canonical_ui_only_widget_field(
    node: Mapping[str, Any],
    field_name: str,
    *,
    schema_provider: Any | None = None,
) -> tuple[str, int] | None:
    """Return a semantic alias for known UI-only widget slots.

    This keeps edit-session compatibility with older scratchpads that exposed
    Comfy's seed randomization control as ``unused_widget_1`` while letting new
    code address the same slot as ``control_after_generate``.
    """
    class_type = str(node.get("type") or node.get("class_type") or "")
    resolution = compact_widget_names_for_node(node, class_type, schema_provider=schema_provider)
    for index, name in enumerate(resolution.names):
        if name != "control_after_generate":
            continue
        if field_name == "control_after_generate":
            return "control_after_generate", index
        match = _POSITIONAL_WIDGET_FIELD_RE.fullmatch(field_name)
        if match is not None and int(match.group(1)) == index:
            return "control_after_generate", index
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
