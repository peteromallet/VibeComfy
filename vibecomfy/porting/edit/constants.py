"""Shared edit-surface constants used by the interpreter and session mixins."""

from __future__ import annotations

from typing import Any

HELPER_NODE_TYPES = frozenset({"Reroute", "GetNode", "SetNode", "Note", "MarkdownNote"})
MODE_LABELS = {0: "enabled", 2: "muted", 4: "bypassed"}
# Non-identifier **unpack key for the emit/interpret field roster.  A real
# node field with this raw name is emitted as its identifier encoding, never
# as this unpack, so the roster cannot collide with a field value.
WIDGET_CHANNEL_SIDE_KEY = "__vibe::widget_channel_names"
CHANNEL_SIDE_WIDGETS = "widgets"
CHANNEL_SIDE_ORDER = "order"


def decode_channel_side_payload(
    payload: Any,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Return ``(widget_names, emit_order)`` for a side-channel value.

    Current emit uses ``{widgets: (...), order: (...)}``.  ``order`` is the
    exact raw-name sequence ``encode_slot_names`` saw.  The legacy sequence
    form is widget names only and is still accepted so stored accepted-batch
    source can replay.
    """
    if isinstance(payload, (list, tuple)) and all(isinstance(name, str) for name in payload):
        names = tuple(str(name) for name in payload)
        return names, names
    if not isinstance(payload, dict):
        return None
    extra = set(payload) - {CHANNEL_SIDE_WIDGETS, CHANNEL_SIDE_ORDER}
    if extra:
        return None
    widgets = payload.get(CHANNEL_SIDE_WIDGETS, ())
    order = payload.get(CHANNEL_SIDE_ORDER, widgets)
    if not isinstance(widgets, (list, tuple)) or not all(isinstance(name, str) for name in widgets):
        return None
    if not isinstance(order, (list, tuple)) or not all(isinstance(name, str) for name in order):
        return None
    return tuple(str(name) for name in widgets), tuple(str(name) for name in order)


__all__ = [
    "HELPER_NODE_TYPES",
    "MODE_LABELS",
    "WIDGET_CHANNEL_SIDE_KEY",
    "CHANNEL_SIDE_WIDGETS",
    "CHANNEL_SIDE_ORDER",
    "decode_channel_side_payload",
]
