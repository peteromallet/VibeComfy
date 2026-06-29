from __future__ import annotations

import copy
from typing import Any, Mapping

from ._apply_execute import _apply_resolved_op, _sync_scope_counters
from ._apply_guard import guard_full_ui
from ._apply_resolve import _resolve_op
from ._apply_types import (
    AppliedAddNodeSpec,
    ApplyResult,
    GuardResult,
    ResolvedAddNodeSpec,
    ResolvedFieldRef,
    ResolvedLinkEndpoint,
    ResolvedNodeRef,
    ResolvedOp,
    ResolvedRemoveLinkRef,
    ResolvedRemoveNodePlan,
    ResolveResult,
)
from .ledger import EditLedger
from vibecomfy.porting.report import PortIssue
from .ops import (
    AddNodeOp,
    EditOp,
)


def resolve_delta(
    original_ui: Mapping[str, Any],
    delta: tuple[EditOp, ...],
    *,
    schema_provider: Any = None,
) -> ResolveResult:
    ledger = EditLedger.ingest(original_ui)
    diagnostics: list[PortIssue] = list(ledger.diagnostics)
    resolved_ops: list[tuple[EditOp, ResolvedOp]] = []

    for op in delta:
        resolved, issues = _resolve_op(ledger, op, schema_provider=schema_provider)
        diagnostics.extend(issues)
        if any(issue.severity == "error" for issue in issues):
            return ResolveResult(
                ok=False,
                ledger=ledger,
                diagnostics=tuple(diagnostics),
                resolved_ops=tuple(resolved_ops),
            )
        assert resolved is not None
        if isinstance(op, AddNodeOp):
            applied_resolved, apply_diagnostics = _apply_resolved_op(ledger, op, resolved)
            diagnostics.extend(apply_diagnostics)
            resolved_ops.append((op, applied_resolved))
            continue
        resolved_ops.append((op, resolved))

    if delta:
        _sync_scope_counters(ledger)

    return ResolveResult(
        ok=True,
        ledger=ledger,
        diagnostics=tuple(diagnostics),
        resolved_ops=tuple(resolved_ops),
    )


def apply_delta(
    original_ui: Mapping[str, Any],
    delta: tuple[EditOp, ...],
    *,
    schema_provider: Any = None,
) -> ApplyResult:
    stamped_before = EditLedger.ingest(original_ui).stamped_copy() if delta else None
    resolved = resolve_delta(original_ui, delta, schema_provider=schema_provider)
    if not resolved.ok:
        return ApplyResult(
            ok=False,
            candidate=None,
            diagnostics=resolved.diagnostics,
            resolved_ops=resolved.resolved_ops,
            mutation_started=False,
        )
    if delta:
        candidate_ledger = resolved.ledger
        diagnostics = list(resolved.diagnostics)
        applied_resolved_ops: list[tuple[EditOp, ResolvedOp]] = []
        for op, resolved_op in resolved.resolved_ops:
            if isinstance(op, AddNodeOp):
                assert isinstance(resolved_op, AppliedAddNodeSpec)
                applied_resolved_ops.append((op, resolved_op))
                continue
            applied_resolved, apply_diagnostics = _apply_resolved_op(candidate_ledger, op, resolved_op)
            diagnostics.extend(apply_diagnostics)
            applied_resolved_ops.append((op, applied_resolved))
        _sync_scope_counters(candidate_ledger)
        assert stamped_before is not None
        guard = guard_full_ui(stamped_before, candidate_ledger.graph, tuple(applied_resolved_ops))
        diagnostics.extend(guard.diagnostics)
        if not guard.ok:
            return ApplyResult(
                ok=False,
                candidate=None,
                diagnostics=tuple(diagnostics),
                resolved_ops=tuple(applied_resolved_ops),
                mutation_started=True,
                guard_result=guard,
            )
        return ApplyResult(
            ok=True,
            candidate=candidate_ledger.graph,
            diagnostics=tuple(diagnostics),
            resolved_ops=tuple(applied_resolved_ops),
            mutation_started=True,
            guard_result=guard,
        )
    return ApplyResult(
        ok=True,
        candidate=copy.deepcopy(dict(original_ui)),
        diagnostics=resolved.diagnostics,
        resolved_ops=resolved.resolved_ops,
        mutation_started=False,
        guard_result=None,
    )


__all__ = [
    "AppliedAddNodeSpec",
    "ApplyResult",
    "GuardResult",
    "ResolvedAddNodeSpec",
    "ResolvedFieldRef",
    "ResolvedLinkEndpoint",
    "ResolvedNodeRef",
    "ResolvedRemoveLinkRef",
    "ResolvedRemoveNodePlan",
    "ResolveResult",
    "apply_delta",
    "guard_full_ui",
    "resolve_delta",
]
