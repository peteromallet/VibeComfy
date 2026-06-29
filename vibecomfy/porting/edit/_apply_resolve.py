from __future__ import annotations

from typing import Any

from ._apply_common import _ctx, _issue
from ._apply_types import ResolvedNodeRef, ResolvedOp
from .ledger import EditLedger, ScopeState
from .ops import AddNodeOp, EditOp, NodeTarget, RemoveLinkOp, RemoveNodeOp, ReorderOp, SetModeOp, SetNodeFieldOp, UpsertLinkOp
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import EditLedgerBackend


def _resolve_op(
    ledger: EditLedger,
    op: EditOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    from ._apply_resolve_links import _resolve_remove_link, _resolve_upsert_link
    from ._apply_resolve_nodes import _resolve_add_node, _resolve_remove_node, _resolve_set_node_field

    if isinstance(op, SetNodeFieldOp):
        return _resolve_set_node_field(ledger, op, schema_provider=schema_provider)
    if isinstance(op, SetModeOp):
        return _resolve_node_only(ledger, op.target)
    if isinstance(op, RemoveNodeOp):
        return _resolve_remove_node(ledger, op.target)
    if isinstance(op, UpsertLinkOp):
        return _resolve_upsert_link(ledger, op, schema_provider=schema_provider)
    if isinstance(op, RemoveLinkOp):
        return _resolve_remove_link(ledger, op)
    if isinstance(op, AddNodeOp):
        return _resolve_add_node(ledger, op, schema_provider=schema_provider)
    if isinstance(op, ReorderOp):
        return _resolve_reorder(ledger, op)
    return None, [_issue("unsupported_edit_op", f"Unsupported edit op {type(op).__name__}.")]


def _resolve_scope(ledger: EditLedger, scope_path: str) -> tuple[ScopeState | None, list[PortIssue]]:
    scope = ledger.scopes.get(scope_path)
    if scope is None:
        return None, [
            _issue(
                "unknown_scope_path",
                f"Unknown scope_path {scope_path!r}.",
                detail={"scope_path": scope_path},
            )
        ]
    return scope, []


def _resolve_node(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedNodeRef | None, list[PortIssue]]:
    scope, issues = _resolve_scope(ledger, target.scope_path)
    if issues:
        return None, issues
    assert scope is not None
    backend = EditLedgerBackend(ledger)
    uid_result = _ctx.resolve_uid(backend, target.scope_path, target.uid)
    if uid_result.value is None:
        return None, [
            _issue(
                "unknown_node_target",
                f"Unknown node target {target.uid!r} in scope {target.scope_path!r}.",
                detail={"scope_path": target.scope_path, "uid": target.uid},
            )
        ]
    resolved_uid = uid_result.value
    resolved_target = (
        NodeTarget(scope_path=target.scope_path, uid=resolved_uid)
        if resolved_uid != target.uid else target
    )
    node = backend.node_for(target.scope_path, resolved_uid)
    if node is None:
        return None, [
            _issue(
                "unknown_node_target",
                f"Unknown node target {resolved_uid!r} in scope {target.scope_path!r}.",
                detail={"scope_path": target.scope_path, "uid": resolved_uid},
            )
        ]
    class_type = str(node.get("type") or node.get("class_type") or "")
    return (
        ResolvedNodeRef(
            target=resolved_target,
            node=node,
            class_type=class_type,
            node_id=node.get("id"),
        ),
        [],
    )


def _resolve_node_only(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    resolved, issues = _resolve_node(ledger, target)
    return resolved, issues


def _resolve_reorder(
    ledger: EditLedger,
    op: ReorderOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    from ._apply_widgets import _linked_widget_names, _reorder_names

    if op.axis != "widgets":
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder supports only cosmetic unlinked widget value permutations; structural slot reorder is rejected.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    node_ref, issues = _resolve_node(ledger, op.target)
    if issues:
        return None, issues
    assert node_ref is not None
    raw = node_ref.node.get("widgets_values")
    if not isinstance(raw, list):
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no reorderable widget surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    names = _reorder_names(node_ref.node, node_ref.class_type, op.axis)
    if names is None:
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no named reorderable {op.axis} surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    if tuple(op.order) == tuple(names):
        return node_ref, []
    if len(op.order) != len(names) or set(op.order) != set(names):
        return None, [
            _issue(
                "unsupported_reorder_form",
                "reorder must be a complete permutation of the existing named widget or output slots.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "expected": list(names),
                    "actual": list(op.order),
                },
            )
        ]
    linked_widgets = _linked_widget_names(node_ref.node.get("inputs"))
    linked_ordered_widgets = [name for name in op.order if name in linked_widgets]
    if linked_ordered_widgets:
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder only supports unlinked widget values; linked widget inputs must be edited with link ops first.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "linked_widgets": linked_ordered_widgets,
                },
            )
        ]
    return node_ref, []
