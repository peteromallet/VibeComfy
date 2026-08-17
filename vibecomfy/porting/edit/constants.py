"""Shared edit-surface constants used by the interpreter and session mixins."""

from __future__ import annotations

HELPER_NODE_TYPES = frozenset({"Reroute", "GetNode", "SetNode", "Note", "MarkdownNote"})
MODE_LABELS = {0: "enabled", 2: "muted", 4: "bypassed"}

__all__ = ["HELPER_NODE_TYPES", "MODE_LABELS"]
