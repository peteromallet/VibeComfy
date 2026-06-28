"""Field-change helpers for agent-edit candidate processing."""

from __future__ import annotations

from typing import Any, Mapping

from vibecomfy.porting.edit.types import FieldChange

from ..contracts import repair_field_changes


def repair_field_changes_from_original_ui(
    graph: Mapping[str, Any],
    changes: tuple[FieldChange, ...],
) -> tuple[FieldChange, ...]:
    return repair_field_changes(graph, changes)


def field_changes_payload(changes: tuple[FieldChange, ...]) -> list[dict[str, Any]]:
    return [change.to_dict() for change in changes]


__all__ = ["field_changes_payload", "repair_field_changes_from_original_ui"]
