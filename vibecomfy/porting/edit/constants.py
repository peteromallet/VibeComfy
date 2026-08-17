"""Shared edit-surface constants used by the interpreter and session mixins."""

from __future__ import annotations

HELPER_NODE_TYPES = frozenset({"Reroute", "GetNode", "SetNode", "Note", "MarkdownNote"})
MODE_LABELS = {0: "enabled", 2: "muted", 4: "bypassed"}
# Non-identifier side-channel key for named widget-channel membership.
# Cannot collide with a node field because it is not a valid Python
# identifier (emit carries it only as ``**{key: (...)}``).
WIDGET_CHANNEL_SIDE_KEY = "__vibe::widget_channel_names"

__all__ = ["HELPER_NODE_TYPES", "MODE_LABELS", "WIDGET_CHANNEL_SIDE_KEY"]
