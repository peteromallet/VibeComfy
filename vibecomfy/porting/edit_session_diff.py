from __future__ import annotations

import difflib
from typing import Any

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    LinkSourceRef,
    RemoveLinkOp,
    RemoveNodeOp,
    ReorderOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.edit.projection import MODE_LABELS
from vibecomfy.porting.edit_session_types import (
    CompactDiagnostic,
    StatementResult,
    _diag,
)
from vibecomfy.porting.edit.types import FieldChange

_UNRESOLVED_OLD_VALUE = object()


class _DiffMixin:
    """Diff and summarize methods extracted from EditSession."""

    def _summarize_op(self, op: EditOp) -> str:
        """Generate a single-sentence summary for one edit operation."""
        if isinstance(op, SetNodeFieldOp):
            return self._summarize_set_node_field(op)
        if isinstance(op, AddNodeOp):
            return self._summarize_add_node(op)
        if isinstance(op, RemoveNodeOp):
            return self._summarize_remove_node(op)
        if isinstance(op, UpsertLinkOp):
            return self._summarize_upsert_link(op)
        if isinstance(op, RemoveLinkOp):
            return self._summarize_remove_link(op)
        if isinstance(op, SetModeOp):
            return self._summarize_set_mode(op)
        if isinstance(op, ReorderOp):
            return self._summarize_reorder(op)
        return ""

    def _summarize_set_node_field(self, op: SetNodeFieldOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        field = op.target.field_path
        old_value = self._original_node_field_value(op.target.scope_path, op.target.uid, field)
        new_value = op.value
        if old_value is not None:
            return f"Changed {name}.{field} from {old_value!r} to {new_value!r}."
        return f"Set {name}.{field} = {new_value!r}."

    def _summarize_add_node(self, op: AddNodeOp) -> str:
        name = self.name_by_uid.get(
            self._uid_for_scope(op.scope_path, op.class_type), op.class_type
        )
        detail_parts: list[str] = []
        if op.inputs:
            input_parts: list[str] = []
            for field_name, source_ref in op.inputs.items():
                src_name = self._node_display_name(source_ref.scope_path, source_ref.uid)
                socket_type = self._output_socket_type(source_ref.scope_path, source_ref.uid, source_ref.output_slot)
                slot_str = source_ref.output_slot
                if isinstance(slot_str, int):
                    slot_str = str(slot_str)
                type_hint = f" ({socket_type})" if socket_type else ""
                input_parts.append(f"{src_name}.{slot_str}{type_hint}")
                # Check for adjacent same-type inputs
                adj = self._adjacent_same_type_inputs(
                    op.scope_path if op.scope_path else "", field_name
                )
                if adj:
                    input_parts[-1] += f" (adjacent same-type: {adj})"
            detail_parts.append("with inputs: " + ", ".join(input_parts))
        if op.fields:
            field_parts = [f"{k}={v!r}" for k, v in op.fields.items()]
            detail_parts.append("with fields: " + ", ".join(field_parts))
        detail = "; ".join(detail_parts)
        if detail:
            return f"Added {op.class_type} node '{name}' {detail}."
        return f"Added {op.class_type} node '{name}'."

    def _summarize_remove_node(self, op: RemoveNodeOp) -> str:
        name = self.name_by_uid.get(op.target.uid, op.target.uid)
        class_type = self._original_node_class_type(op.target.scope_path, op.target.uid)
        ct_str = f"{class_type} " if class_type else ""
        return f"Removed {ct_str}node '{name}'."

    def _summarize_upsert_link(self, op: UpsertLinkOp) -> str:
        src_name = self._node_display_name(op.source.scope_path, op.source.uid)
        dst_name = self._node_display_name(op.target.scope_path, op.target.uid)
        src_slot = op.source.output_slot
        if isinstance(src_slot, int):
            src_slot = str(src_slot)
        dst_field = op.target.input_field
        socket_type = self._output_socket_type(op.source.scope_path, op.source.uid, op.source.output_slot)
        type_hint = f" ({socket_type})" if socket_type else ""

        # Check original ledger for a pre-existing link to determine new vs rewire
        prev_link = self._find_link_to_target_in_ledger(
            self.original_ledger, op.target.scope_path, op.target.uid, op.target.input_field
        )
        if prev_link is not None:
            # Rewire case: original ledger had a link
            pass
        else:
            # No original link — this is a new connection
            prev_link = None
        if prev_link is not None:
            prev_src_uid, prev_src_slot = prev_link
            prev_name = self._node_display_name(op.target.scope_path, prev_src_uid)
            prev_slot_str = str(prev_src_slot) if isinstance(prev_src_slot, int) else prev_src_slot
            return (
                f"Rewired {dst_name}.{dst_field}{type_hint} "
                f"from {prev_name}.{prev_slot_str} → {src_name}.{src_slot}."
            )
        return (
            f"Connected {src_name}.{src_slot}{type_hint} → "
            f"{dst_name}.{dst_field}."
        )

    def _summarize_remove_link(self, op: RemoveLinkOp) -> str:
        if op.target is None:
            return f"Removed link id={op.link_id}."
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        field = op.target.input_field
        prev_link = self._find_link_to_target(op.target.scope_path, op.target.uid, op.target.input_field)
        if prev_link is not None:
            prev_src_uid, prev_src_slot = prev_link
            prev_name = self._node_display_name(op.target.scope_path, prev_src_uid)
            return f"Disconnected {name}.{field} from {prev_name}.{prev_src_slot}."
        return f"Disconnected {name}.{field}."

    def _summarize_set_mode(self, op: SetModeOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        old_mode = self._original_node_mode(op.target.scope_path, op.target.uid)
        old_label = MODE_LABELS.get(old_mode, f"mode={old_mode}")
        new_label = MODE_LABELS.get(op.mode, f"mode={op.mode}")
        return f"Changed {name} mode from {old_label} to {new_label}."

    def _summarize_reorder(self, op: ReorderOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        return f"Reordered {name} {op.axis}."

    def _build_field_changes(
        self,
        landed_ops: tuple[EditOp, ...],
        statement_results: tuple[StatementResult, ...],
    ) -> tuple[tuple[FieldChange, ...], tuple[StatementResult, ...]]:
        if not landed_ops:
            return (), statement_results

        field_changes: list[FieldChange] = []
        unresolved_by_statement: dict[int, list[CompactDiagnostic]] = {}
        landed_statement_indexes = [i for i, statement in enumerate(statement_results) if statement.landed]

        for op_index, op in enumerate(landed_ops):
            if op_index >= len(landed_statement_indexes):
                break
            statement_index = landed_statement_indexes[op_index]
            change, unresolved = self._field_change_from_landed_op(op)
            if change is not None:
                field_changes.append(change)
            if unresolved is not None:
                unresolved_by_statement.setdefault(statement_index, []).append(unresolved)

        if not unresolved_by_statement:
            return tuple(field_changes), statement_results

        updated_results: list[StatementResult] = list(statement_results)
        for statement_index, extras in unresolved_by_statement.items():
            statement = updated_results[statement_index]
            updated_results[statement_index] = StatementResult(
                statement_index=statement.statement_index,
                source=statement.source,
                ok=statement.ok,
                diagnostics=statement.diagnostics + tuple(extras),
                landed=statement.landed,
                op_kind=statement.op_kind,
                detail=dict(statement.detail),
                touched_uids=statement.touched_uids,
                dependency_cause=statement.dependency_cause,
                teaching_hint=statement.teaching_hint,
            )
        return tuple(field_changes), tuple(updated_results)

    def _field_change_from_landed_op(
        self, op: EditOp
    ) -> tuple[FieldChange | None, CompactDiagnostic | None]:
        if isinstance(op, SetNodeFieldOp):
            old = self._original_node_field_value(
                op.target.scope_path, op.target.uid, op.target.field_path
            )
            new = op.value
            field_path = op.target.field_path
            uid = op.target.uid
        elif isinstance(op, SetModeOp):
            old = self._original_node_mode(op.target.scope_path, op.target.uid)
            new = op.mode
            field_path = "mode"
            uid = op.target.uid
        elif isinstance(op, UpsertLinkOp):
            old = self._original_link_value(
                op.target.scope_path, op.target.uid, op.target.input_field
            )
            new = self._link_ref_value(op.source)
            field_path = op.target.input_field
            uid = op.target.uid
        elif isinstance(op, RemoveLinkOp) and op.target is not None:
            old = self._original_link_value(
                op.target.scope_path, op.target.uid, op.target.input_field
            )
            new = None
            field_path = op.target.input_field
            uid = op.target.uid
        else:
            return None, None

        unresolved = None
        if old is _UNRESOLVED_OLD_VALUE:
            unresolved = _diag(
                "field_change_old_unresolved",
                (
                    f"Could not resolve the original value for {uid}.{field_path}; "
                    "emitting the landed change with old=None."
                ),
                severity="info",
                detail={"uid": uid, "field_path": field_path},
            )
            old = None
        return FieldChange(uid=uid, field_path=field_path, old=old, new=new), unresolved


def _render_op_diff(op: Any, *, old_value: Any = None) -> str:
    """Produce a single-line diff summary for one edit operation.

    Driven by the same pattern as ``_summarize_op`` but kept compact so it is
    suitable for line-by-line agent feedback.

    When *old_value* is supplied for a ``SetNodeFieldOp`` whose *field_path*
    is ``"source"`` and both values are strings, a multi-line unified diff is
    produced so that changed ``vibecomfy.exec`` source bodies are readable.
    """
    if isinstance(op, SetNodeFieldOp):
        field = op.target.field_path
        uid = op.target.uid
        new_val = op.value
        if (
            field == "source"
            and old_value is not None
            and isinstance(old_value, str)
            and isinstance(new_val, str)
        ):
            old_lines = old_value.splitlines(keepends=True)
            new_lines = new_val.splitlines(keepends=True)
            diff_lines = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"{uid}/source (old)",
                    tofile=f"{uid}/source (new)",
                    lineterm="",
                )
            )
            if diff_lines:
                header = f"set_node_field  uid={uid!r} field={field!r}  ({len(old_lines)}→{len(new_lines)} lines)"
                return header + "\n" + "\n".join(diff_lines)
        old = _repr_short(new_val)
        return f"set_node_field  uid={uid!r} field={field!r} → {old}"
    if isinstance(op, AddNodeOp):
        ct = op.class_type
        n_inputs = len(op.inputs) if op.inputs else 0
        n_fields = len(op.fields) if op.fields else 0
        return f"add_node  class_type={ct!r}  inputs={n_inputs}  fields={n_fields}"
    if isinstance(op, RemoveNodeOp):
        return f"remove_node  uid={op.target.uid!r}"
    if isinstance(op, UpsertLinkOp):
        src = f"{op.source.uid}.{op.source.output_slot}"
        tgt = f"{op.target.uid}.{op.target.input_field}"
        return f"upsert_link  {src} → {tgt}"
    if isinstance(op, RemoveLinkOp):
        if op.target is not None:
            return f"remove_link  target={op.target.uid!r}.{op.target.input_field}"
        return f"remove_link  link_id={op.link_id}"
    if isinstance(op, SetModeOp):
        return f"set_mode  uid={op.target.uid!r} → mode={op.mode}"
    if isinstance(op, ReorderOp):
        return f"reorder  uid={op.target.uid!r} axis={op.axis}"
    return repr(type(op).__name__)


def _repr_short(value: Any) -> str:
    """Truncate repr for compact display."""
    s = repr(value)
    if len(s) > 60:
        return s[:57] + "..."
    return s
