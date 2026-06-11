from __future__ import annotations

from typing import Any


UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})


def is_api_link(
    value: Any,
    *,
    allow_tuple: bool = False,
    require_string_node_id: bool = False,
    require_numeric_node_id: bool = True,
    allow_compound_node_id: bool = False,
    require_int_slot: bool = False,
) -> bool:
    """Return whether ``value`` is a ComfyUI API link pair.

    The defaults match the most common legacy helper in this repo: a list pair
    whose source id is digit-shaped after ``str(...)`` coercion. Flags let
    stricter call sites preserve their existing list/tuple, source-id, and slot
    rules explicitly.
    """

    allowed_types = (list, tuple) if allow_tuple else (list,)
    if not (isinstance(value, allowed_types) and len(value) == 2):
        return False

    source_id, slot = value
    if require_string_node_id and not isinstance(source_id, str):
        return False
    if require_numeric_node_id and not _is_numeric_node_id(source_id, allow_compound=allow_compound_node_id):
        return False
    if require_int_slot and not isinstance(slot, int):
        return False
    return True


def node_id_sort_key(node_id: Any, *, allow_compound: bool = False) -> tuple[Any, ...]:
    """Sort node ids numerically when possible, with a stable text fallback."""

    text = str(node_id)
    parts = text.split(":") if allow_compound else [text]
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, text)


def _is_numeric_node_id(node_id: Any, *, allow_compound: bool) -> bool:
    parts = str(node_id).split(":") if allow_compound else [str(node_id)]
    return all(part.isdigit() for part in parts)


__all__ = ["UI_ONLY_CLASS_TYPES", "is_api_link", "node_id_sort_key"]
