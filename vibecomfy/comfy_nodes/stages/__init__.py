from __future__ import annotations

from typing import TYPE_CHECKING

from ..agent_contracts import StageResult, TurnContext
from ..agent_gates import apply_stage_gate_updates

if TYPE_CHECKING:
    pass


def _record(context: TurnContext, result: StageResult) -> StageResult:
    context.stage_results[result.stage] = result
    apply_stage_gate_updates(context, result)
    return result
