from __future__ import annotations

from typing import Any

from .ledger import EditLedger
from .ops import AddNodeOp, EditOp, RemoveLinkOp, RemoveNodeOp, SetModeOp, SetNodeFieldOp, UpsertLinkOp
from vibecomfy.porting.edit.apply_resolve_add import _resolve_add_node
from vibecomfy.porting.edit.apply_resolve_base import _resolve_node_only, _resolve_remove_link, _resolve_remove_node, _resolve_set_node_field, _resolve_upsert_link
from vibecomfy.porting.edit.apply_types import ResolvedOp, ValueDefaultContext, _issue
from vibecomfy.porting.report import PortIssue


def _resolve_op(
    ledger: EditLedger,
    op: EditOp,
    *,
    schema_provider: Any,
    value_default_context: ValueDefaultContext | None = None,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if isinstance(op, SetNodeFieldOp):
        return _resolve_set_node_field(
            ledger,
            op,
            schema_provider=schema_provider,
            value_default_context=value_default_context,
        )
    if isinstance(op, SetModeOp):
        return _resolve_node_only(ledger, op.target)
    if isinstance(op, RemoveNodeOp):
        return _resolve_remove_node(ledger, op.target)
    if isinstance(op, UpsertLinkOp):
        return _resolve_upsert_link(ledger, op, schema_provider=schema_provider)
    if isinstance(op, RemoveLinkOp):
        return _resolve_remove_link(ledger, op)
    if isinstance(op, AddNodeOp):
        return _resolve_add_node(
            ledger,
            op,
            schema_provider=schema_provider,
            value_default_context=value_default_context,
        )
    return None, [_issue("unsupported_edit_op", f"Unsupported edit op {type(op).__name__}.")]
