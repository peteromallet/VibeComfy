"""Latency helpers for emit_ui_json-based gates and instrumentation."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any

from vibecomfy.porting.layout import LatencyBudgetReport
from vibecomfy.porting.emit.ui import emit_ui_json

FALLBACK_LATENCY_BUDGET_MS = 5000.0


def measure_emit_latency(
    wf: Any,
    schema_provider: Any,
) -> LatencyBudgetReport:
    """Measure one emit_ui_json call without enforcing a latency budget."""

    start = perf_counter()
    emit_ui_json(wf, schema_provider=schema_provider)
    elapsed_ms = (perf_counter() - start) * 1000.0
    return LatencyBudgetReport(
        elapsed_ms=elapsed_ms,
        budget_ms=math.inf,
        ok=True,
    )


def measure_emit_latency_gated(
    wf: Any,
    schema_provider: Any,
    budget_ms: float,
) -> LatencyBudgetReport:
    """Measure one emit_ui_json call and evaluate it against *budget_ms*."""

    start = perf_counter()
    emit_ui_json(wf, schema_provider=schema_provider)
    elapsed_ms = (perf_counter() - start) * 1000.0
    return LatencyBudgetReport(
        elapsed_ms=elapsed_ms,
        budget_ms=float(budget_ms),
        ok=elapsed_ms <= float(budget_ms),
    )
