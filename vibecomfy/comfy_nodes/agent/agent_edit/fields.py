from __future__ import annotations

from typing import Any, Mapping

from ..contracts import _ABSENT_FIELD_OLD, repair_field_changes
from vibecomfy.porting.edit.types import FieldChange


def _repair_field_changes_from_original_ui(
    graph: Mapping[str, Any],
    changes: tuple[FieldChange, ...],
) -> tuple[FieldChange, ...]:
    return repair_field_changes(graph, changes)


def _field_change_is_noop(
    change: FieldChange,
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> bool:
    if lint_dropped_op_ids is not None:
        key = (change.uid, change.field_path)
        if key in lint_dropped_op_ids:
            return True
    return change.old is not _ABSENT_FIELD_OLD and change.old == change.new


def _real_field_changes(
    changes: tuple[FieldChange, ...],
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> tuple[FieldChange, ...]:
    return tuple(
        change
        for change in changes
        if not _field_change_is_noop(change, lint_dropped_op_ids=lint_dropped_op_ids)
    )


def _noop_field_changes(
    changes: tuple[FieldChange, ...],
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> tuple[FieldChange, ...]:
    return tuple(
        change
        for change in changes
        if _field_change_is_noop(change, lint_dropped_op_ids=lint_dropped_op_ids)
    )
