from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from vibecomfy.contracts.intent_nodes import INTENT_NODE_QUEUE_BLOCKER_CODE

from .agent_contracts import (
    CANVAS_APPLY_GATE_NAMES,
    DEFAULT_GATE_NAMES,
    GateResult,
    StageResult,
    TurnContext,
)


EMIT_STAGE_GATE_NAMES: tuple[str, ...] = (
    "ui_emit_ok",
    "ui_fidelity_ok",
    "ui_load_safe_ok",
)

EXPLICIT_QUEUE_BLOCKER_CODES = frozenset(
    {
        INTENT_NODE_QUEUE_BLOCKER_CODE,
        "schema_less_queue_blocker",
        "low_confidence_queue_blocker",
        "editor_only_node_queue_blocker",
    }
)


@dataclass(frozen=True)
class GateDerivation:
    gates: Mapping[str, GateResult]
    canvas_apply_allowed: bool
    queue_allowed: bool
    queue_blockers: tuple[dict[str, Any], ...]


def _evidence(stage: str, *, reason: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = {"stage": stage, "reason": reason}
    payload.update(dict(extra or {}))
    return payload


def _stage_gate_evidence(stage_result: StageResult, gate: str, ok: bool) -> dict[str, Any]:
    return _evidence(
        stage_result.stage,
        reason="stage_gate_update",
        extra={
            "gate": gate,
            "stage_ok": stage_result.ok,
            "blocking": stage_result.blocking,
            "duration_ms": stage_result.duration_ms,
            "issue_count": len(stage_result.issues),
            "artifact_count": len(stage_result.artifacts),
            "ok": ok,
        },
    )


def initialize_gates(context: TurnContext) -> None:
    for name in DEFAULT_GATE_NAMES:
        context.set_gate(name, False, evidence=_evidence("init", reason="fail_closed_default"))


def apply_stage_gate_updates(context: TurnContext, stage_result: StageResult) -> None:
    for name, ok in stage_result.gate_updates.items():
        context.set_gate(name, bool(ok), evidence=_stage_gate_evidence(stage_result, name, bool(ok)))


def update_state_match_gate(
    context: TurnContext,
    *,
    baseline_graph_hash: str | None = None,
    client_graph_hash: str | None = None,
    client_graph_hash_label: str = "client_graph_hash",
) -> None:
    if baseline_graph_hash is None:
        ok = True
        reason = "no_baseline_hash_required"
    else:
        ok = bool(client_graph_hash) and client_graph_hash == baseline_graph_hash
        reason = "hash_match" if ok else "hash_mismatch"
    context.client_graph_hash = client_graph_hash
    context.set_gate(
        "state_match_ok",
        ok,
        evidence=_evidence(
            "ingest",
            reason=reason,
            extra={
                "baseline_graph_hash_present": baseline_graph_hash is not None,
                "client_graph_hash_present": client_graph_hash is not None,
                "baseline_graph_hash": baseline_graph_hash,
                "client_graph_hash": client_graph_hash,
                "client_graph_hash_label": client_graph_hash_label,
            },
        ),
    )


def _queue_blocker_issues(stage_results: Mapping[str, StageResult]) -> tuple[dict[str, Any], ...]:
    blockers: list[dict[str, Any]] = []
    for result in stage_results.values():
        for issue in result.issues:
            if not isinstance(issue, Mapping):
                continue
            code = str(issue.get("code", ""))
            severity = str(issue.get("severity", "error"))
            if severity != "error":
                continue
            if (
                code in EXPLICIT_QUEUE_BLOCKER_CODES
                or "queue_blocker" in code
                or "schema_less" in code
                or "schema-less" in code
                or "editor_only" in code
                or "editor-only" in code
                or "low_confidence" in code
            ):
                blockers.append(dict(issue))
    return tuple(blockers)


def update_queue_gate(
    context: TurnContext,
    *,
    stage_results: Mapping[str, StageResult] | None = None,
    queue_blockers: tuple[dict[str, Any], ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    blockers = queue_blockers
    if blockers is None:
        blockers = _queue_blocker_issues(stage_results or context.stage_results)
    ok = context.gate_results["ir_validate_ok"].ok and not blockers
    context.set_gate(
        "queue_validate_ok",
        ok,
        evidence=_evidence(
            "queue_validate",
            reason="no_queue_blockers" if ok else "queue_blocked",
            extra={"blocker_count": len(blockers), "blockers": list(blockers)},
        ),
    )
    return blockers


def derive_gates(
    context: TurnContext,
    *,
    baseline_graph_hash: str | None = None,
    client_graph_hash: str | None = None,
    queue_blockers: tuple[dict[str, Any], ...] | None = None,
) -> GateDerivation:
    update_state_match_gate(
        context,
        baseline_graph_hash=baseline_graph_hash,
        client_graph_hash=client_graph_hash,
    )
    blockers = update_queue_gate(context, queue_blockers=queue_blockers)
    return GateDerivation(
        gates={name: context.gate_results[name] for name in DEFAULT_GATE_NAMES},
        canvas_apply_allowed=all(context.gate_results[name].ok for name in CANVAS_APPLY_GATE_NAMES),
        queue_allowed=context.queue_allowed,
        queue_blockers=blockers,
    )


__all__ = [
    "EXPLICIT_QUEUE_BLOCKER_CODES",
    "EMIT_STAGE_GATE_NAMES",
    "GateDerivation",
    "apply_stage_gate_updates",
    "derive_gates",
    "initialize_gates",
    "update_queue_gate",
    "update_state_match_gate",
]
