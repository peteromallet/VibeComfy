from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from vibecomfy.contracts.intent_nodes import INTENT_NODE_QUEUE_BLOCKER_CODE

from .contracts import (
    ApplyEligibility,
    CANVAS_APPLY_GATE_NAMES,
    DEFAULT_GATE_NAMES,
    GateResult,
    PLAN_STATE_NOT_REQUIRED,
    PLAN_STATE_REQUIRED_UNSUPPORTED,
    PLAN_VALIDATE_GATE_NAME,
    StageResult,
    TurnContext,
    derive_apply_eligibility,
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

# Evidence tiers considered authoritative for runtime-readiness proof.
# Only these tiers carry direct node-installation or live-schema knowledge;
# every other tier (web, github, hivemind, civitai, external_workflow, …) is
# treated as weak and must not be used to satisfy Queue/runtime readiness.
_RUNTIME_READINESS_STRONG_TIERS: frozenset[str] = frozenset(
    {
        "live_runtime_schema",
        "object_info",
    }
)

# Canonical labels for runtime_availability evidence that signal the caller
# does *not* have an installed, live-schema-backed snapshot.  These are
# treated as weak regardless of the tier that produced them.
_RUNTIME_AVAILABILITY_WEAK_LABELS: frozenset[str] = frozenset(
    {
        "not_available",
        "not_installed",
        "not-installed",
        "provisional",
        "workflow_observed",
        "workflow-observed",
        "stale",
        "untrusted_source",
    }
)


def _is_strong_runtime_evidence_tier(tier: str | None) -> bool:
    """Return True when *tier* is an authoritative source for runtime readiness."""
    if not isinstance(tier, str) or not tier:
        return False
    return tier in _RUNTIME_READINESS_STRONG_TIERS


def _is_weak_runtime_availability_label(label: str | None) -> bool:
    """Return True when *label* signals the runtime snapshot is not installed."""
    if not isinstance(label, str) or not label:
        return True  # absent label → treat as weak
    return label.lower() in _RUNTIME_AVAILABILITY_WEAK_LABELS


def _collect_runtime_evidence_tiers(
    plan: Any | None,
) -> frozenset[str]:
    """Walk *plan* required steps and return the set of evidence tiers used."""
    tiers: set[str] = set()
    if plan is None:
        return frozenset(tiers)
    steps = getattr(plan, "required_steps", None)
    if steps is None and isinstance(plan, Mapping):
        steps = plan.get("required_steps", ())
    if not steps:
        return frozenset(tiers)
    for step in steps:
        tier = None
        if isinstance(step, Mapping):
            tier = step.get("_evidence_tier")
            if tier is None:
                rp = step.get("runtime_provenance") or {}
                if isinstance(rp, Mapping):
                    tier = rp.get("tier") or rp.get("_tier")
        else:
            tier = getattr(step, "_evidence_tier", None)
            if tier is None:
                rp = getattr(step, "runtime_provenance", None)
                if isinstance(rp, Mapping):
                    tier = rp.get("tier") or rp.get("_tier")
        if tier:
            tiers.add(str(tier))
    return frozenset(tiers)


@dataclass(frozen=True)
class GateDerivation:
    gates: Mapping[str, GateResult]
    canvas_apply_allowed: bool
    apply_eligibility: ApplyEligibility
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


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _failed_condition_ids(evaluation: Any) -> list[str]:
    condition_ids: list[str] = []
    failed_conditions = _field(evaluation, "failed_conditions", ())
    if not isinstance(failed_conditions, (list, tuple)):
        return condition_ids
    for condition in failed_conditions:
        condition_id = _field(condition, "condition_id") or _field(condition, "id")
        condition_ids.append(str(condition_id or "unknown_condition"))
    return condition_ids


def update_plan_validate_gate(
    context: TurnContext,
    *,
    execution_plan: Any | None = None,
    plan_evaluation: Any | None = None,
    has_execution_plan: bool | None = None,
    plan_state: str | None = None,
) -> None:
    plan_present = (
        bool(has_execution_plan)
        if has_execution_plan is not None
        else execution_plan is not None or plan_evaluation is not None
    )
    if not plan_present:
        # Only ``not_required`` may pass without a plan.  Any other state
        # (including an absent / unset state) is fail-closed.
        if plan_state == PLAN_STATE_NOT_REQUIRED:
            context.set_gate(
                PLAN_VALIDATE_GATE_NAME,
                True,
                evidence=_evidence(
                    "plan_validate",
                    reason="not_required",
                    extra={"plan_state": PLAN_STATE_NOT_REQUIRED},
                ),
            )
        else:
            resolved = plan_state or PLAN_STATE_REQUIRED_UNSUPPORTED
            context.set_gate(
                PLAN_VALIDATE_GATE_NAME,
                False,
                evidence=_evidence(
                    "plan_validate",
                    reason=resolved,
                    extra={"plan_state": resolved},
                ),
            )
        return

    plan_id = _field(plan_evaluation, "plan_id") or _field(execution_plan, "plan_id")
    if plan_evaluation is None:
        context.set_gate(
            PLAN_VALIDATE_GATE_NAME,
            False,
            evidence=_evidence(
                "plan_validate",
                reason="plan_not_evaluated",
                extra={"plan_id": plan_id},
            ),
        )
        return

    ok = bool(_field(plan_evaluation, "ok", False))
    context.set_gate(
        PLAN_VALIDATE_GATE_NAME,
        ok,
        evidence=_evidence(
            "plan_validate",
            reason="plan_evaluation_passed" if ok else "plan_evaluation_failed",
            extra={
                "plan_id": plan_id,
                "ok": ok,
                "blocking": bool(_field(plan_evaluation, "blocking", False)),
                "failed_condition_ids": _failed_condition_ids(plan_evaluation),
                "feedback": str(_field(plan_evaluation, "feedback", "") or ""),
                "contract_version": _field(plan_evaluation, "contract_version"),
            },
        ),
    )


def initialize_gates(context: TurnContext, *, has_execution_plan: bool = False, plan_state: str | None = None) -> None:
    for name in DEFAULT_GATE_NAMES:
        context.set_gate(name, False, evidence=_evidence("init", reason="fail_closed_default"))
    update_plan_validate_gate(context, has_execution_plan=has_execution_plan, plan_state=plan_state)


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
    evidence_tiers: frozenset[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    results = context.stage_results if stage_results is None else stage_results
    blockers = queue_blockers
    if blockers is None:
        blockers = _queue_blocker_issues(results)
    # Collect weak-evidence queue blockers when evidence tiers are provided
    # but none are from a strong / authoritative runtime source.
    evidence_blockers: list[dict[str, Any]] = []
    if evidence_tiers is not None:
        strong = any(_is_strong_runtime_evidence_tier(t) for t in evidence_tiers)
        if evidence_tiers and not strong:
            evidence_blockers.append(
                {
                    "code": "runtime_readiness_weak_evidence",
                    "severity": "error",
                    "message": (
                        "Queue blocked: runtime readiness evidence tiers "
                        f"{sorted(evidence_tiers)} are not authoritative "
                        "(require live_runtime_schema or object_info)."
                    ),
                    "evidence": {
                        "provided_tiers": sorted(evidence_tiers),
                        "required_tiers": sorted(_RUNTIME_READINESS_STRONG_TIERS),
                    },
                }
            )
    validate_ok = results["validate"].ok if "validate" in results else True
    queue_stage_present = "queue_validate" in results
    explicit_blocker_analysis = queue_blockers is not None
    queue_stage_ok = (
        results["queue_validate"].ok
        if queue_stage_present
        else explicit_blocker_analysis and not blockers
    )
    ok = validate_ok and queue_stage_ok and not blockers and not evidence_blockers
    all_blockers = list(blockers) + evidence_blockers
    context.set_gate(
        "queue_validate_ok",
        ok,
        evidence=_evidence(
            "queue_validate",
            reason="no_queue_blockers" if ok else "queue_blocked",
            extra={
                "blocker_count": len(all_blockers),
                "blockers": all_blockers,
                "validate_stage_present": "validate" in results,
                "validate_ok": validate_ok,
                "queue_validate_stage_present": queue_stage_present,
                "queue_validate_stage_ok": queue_stage_ok,
                "evidence_tiers": sorted(evidence_tiers) if evidence_tiers else None,
                "weak_evidence_blocked": bool(evidence_blockers),
            },
        ),
    )
    return tuple(all_blockers)


def derive_gates(
    context: TurnContext,
    *,
    baseline_graph_hash: str | None = None,
    client_graph_hash: str | None = None,
    queue_blockers: tuple[dict[str, Any], ...] | None = None,
    execution_plan: Any | None = None,
    plan_evaluation: Any | None = None,
    has_execution_plan: bool | None = None,
    plan_state: str | None = None,
    evidence_tiers: frozenset[str] | None = None,
) -> GateDerivation:
    update_plan_validate_gate(
        context,
        execution_plan=execution_plan,
        plan_evaluation=plan_evaluation,
        has_execution_plan=has_execution_plan,
        plan_state=plan_state,
    )
    update_state_match_gate(
        context,
        baseline_graph_hash=baseline_graph_hash,
        client_graph_hash=client_graph_hash,
    )
    blockers = update_queue_gate(context, queue_blockers=queue_blockers, evidence_tiers=evidence_tiers)
    return GateDerivation(
        gates={name: context.gate_results[name] for name in DEFAULT_GATE_NAMES},
        canvas_apply_allowed=all(context.gate_results[name].ok for name in CANVAS_APPLY_GATE_NAMES),
        apply_eligibility=derive_apply_eligibility(context),
        queue_allowed=context.queue_allowed,
        queue_blockers=blockers,
    )


__all__ = [
    "EXPLICIT_QUEUE_BLOCKER_CODES",
    "EMIT_STAGE_GATE_NAMES",
    "GateDerivation",
    "_RUNTIME_READINESS_STRONG_TIERS",
    "_RUNTIME_AVAILABILITY_WEAK_LABELS",
    "_is_strong_runtime_evidence_tier",
    "_is_weak_runtime_availability_label",
    "_collect_runtime_evidence_tiers",
    "apply_stage_gate_updates",
    "derive_gates",
    "derive_apply_eligibility",
    "initialize_gates",
    "update_plan_validate_gate",
    "update_queue_gate",
    "update_state_match_gate",
]
