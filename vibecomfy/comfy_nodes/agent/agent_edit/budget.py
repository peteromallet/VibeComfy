"""Budget and classification helpers for agent-edit batch processing."""

from __future__ import annotations

import time
from typing import Any, Mapping

from vibecomfy.porting.edit.types import FieldChange

from ..contracts import (
    FailureKind,
    _ABSENT_FIELD_OLD,
)
from ..session import structural_graph_hash
from .state import AgentEditState

# Batch exit-mode constants.
_BATCH_EXIT_PURE_CLARIFY = "pure_clarify"
_BATCH_EXIT_EDIT_CLARIFY = "edit_clarify"
_BATCH_EXIT_DONE = "done"
_BATCH_EXIT_BUDGET = "budget"
_BATCH_EXIT_NOOP = "noop"


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _total_landed_edit_count(state: AgentEditState) -> int:
    # Only non-noop field changes count as landed edits.
    real = _real_field_changes(tuple(state.batch_field_changes or ()))
    count = len(real)
    if count > 0:
        return count
    total = 0
    for turn in state.batch_turns:
        # Prefer the actual field changes list; if it exists and is empty,
        # the turn produced no real edits (only no-ops) and should not count.
        field_changes = turn.get("field_changes")
        if isinstance(field_changes, list) and not field_changes:
            continue
        landed = turn.get("landed_op_count")
        if isinstance(landed, int) and landed > 0:
            total += landed
    return total


def _read_only_discovery_turn_count(state: AgentEditState) -> int:
    count = 0
    for turn in state.batch_turns:
        statements = turn.get("statements")
        if not isinstance(statements, list) or not statements:
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            if str(statement.get("op_kind") or "") == "query":
                count += 1
                break
    return count


def _field_change_is_noop(
    change: FieldChange,
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> bool:
    """Return True when *change* is a no-op.

    By default a change is a no-op when the old value is present and
    matches the new value.  When ``lint_dropped_op_ids`` is provided,
    any field change whose ``(uid, field_path)`` appears in that set is
    ALSO classified as a no-op — lint-owned classification wins.
    """
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


def _batch_candidate_graph_changed(state: AgentEditState) -> bool:
    if not isinstance(state.ui_payload, Mapping):
        return False
    return structural_graph_hash(state.ui_payload) != structural_graph_hash(state.graph)


def _batch_has_landed_edits(state: AgentEditState) -> bool:
    return any(
        isinstance(turn, Mapping) and int(turn.get("landed_op_count", 0)) > 0
        for turn in state.batch_turns
    )


def _batch_budget_failure_kind(turns: list[dict[str, Any]]) -> FailureKind:
    schema_gap_markers = (
        "schema",
        "schema-backed",
        "socket type",
        "compatible output",
        "confidence",
    )
    unrepresentable_codes = {
        "statement_not_allowed",
        "call_not_allowed",
        "nested_call_not_allowed",
        "raw_coordinate_kwarg_not_allowed",
        "intent_class_construction_not_allowed",
        "cross_scope_add_node_unsupported",
        "scope_escape_not_allowed",
        "original_virtual_node_immutable",
        "kwargs_unpack_not_allowed",
        "dict_unpack_not_allowed",
        "lambda_not_allowed",
        "comprehension_not_allowed",
        "f_string_not_allowed",
        "for_else_not_allowed",
        "import_not_allowed",
    }
    category_turn_hits = {
        FailureKind.MODEL_MISTAKE: 0,
        FailureKind.UNREPRESENTABLE: 0,
        FailureKind.SCHEMA_GAP: 0,
    }
    for turn in turns:
        turn_categories: set[FailureKind] = set()
        diagnostics = list(turn.get("diagnostics") or [])
        for statement in turn.get("statements") or []:
            diagnostics.extend(statement.get("diagnostics") or [])
        for diagnostic in diagnostics:
            code = str(diagnostic.get("code", "")).lower()
            message = str(diagnostic.get("message", "")).lower()
            teaching_hint = str(diagnostic.get("teaching_hint", "")).lower()
            haystack = " ".join((code, message, teaching_hint))
            if any(marker in haystack for marker in schema_gap_markers):
                turn_categories.add(FailureKind.SCHEMA_GAP)
                continue
            if code in unrepresentable_codes or "not allowed" in haystack or "immutable" in haystack:
                turn_categories.add(FailureKind.UNREPRESENTABLE)
                continue
            turn_categories.add(FailureKind.MODEL_MISTAKE)
        for category in turn_categories:
            category_turn_hits[category] += 1
    ranked = sorted(
        category_turn_hits.items(),
        key=lambda item: (item[1], item[0] == FailureKind.SCHEMA_GAP, item[0] == FailureKind.UNREPRESENTABLE),
        reverse=True,
    )
    if ranked and ranked[0][1] > 0:
        return ranked[0][0]
    return FailureKind.MODEL_MISTAKE


__all__ = [
    "_BATCH_EXIT_BUDGET",
    "_BATCH_EXIT_DONE",
    "_BATCH_EXIT_EDIT_CLARIFY",
    "_BATCH_EXIT_NOOP",
    "_BATCH_EXIT_PURE_CLARIFY",
    "_batch_budget_failure_kind",
    "_batch_candidate_graph_changed",
    "_batch_has_landed_edits",
    "_duration_ms",
    "_field_change_is_noop",
    "_noop_field_changes",
    "_read_only_discovery_turn_count",
    "_real_field_changes",
    "_total_landed_edit_count",
]
