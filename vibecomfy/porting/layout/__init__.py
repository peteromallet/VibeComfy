"""M4 fresh layout engine (Phase 1 primitives → Phase 2 composition).

The public entry-point is :func:`layout`, which accepts the workflow IR and
returns a :class:`LayoutResult` carrying positions and groups.  This module
re-exports :class:`LayoutResult` so callers can import it from here.

M5 additions: :func:`layout_vector` and :func:`layout_drift` for snapshot/diff
of position data in raw UI JSON, keyed by canonical node identity.
"""

from __future__ import annotations

from vibecomfy.porting.layout.engine import layout
from vibecomfy.porting.layout.felt import FeltDeltaReport, FeltDeltaViolation, LatencyBudgetReport, evaluate_felt_delta
from vibecomfy.porting.layout.layout_vector import LayoutDriftReport, layout_drift, layout_vector
from vibecomfy.porting.layout.reconcile import ChangeReport, ContentEdits, IdentityStabilization, build_change_report, inner_node_uid
from vibecomfy.porting.layout.types import LayoutResult

__all__ = [
    "ChangeReport",
    "ContentEdits",
    "FeltDeltaReport",
    "FeltDeltaViolation",
    "IdentityStabilization",
    "LatencyBudgetReport",
    "LayoutDriftReport",
    "LayoutResult",
    "build_change_report",
    "evaluate_felt_delta",
    "inner_node_uid",
    "layout",
    "layout_drift",
    "layout_vector",
]
