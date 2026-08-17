"""Runtime helpers for plan-backed agent edit execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .audit import write_json_artifact
from .contracts import ArtifactRef
from .execution_plan import (
    PLAN_PROVENANCE_AGENT_AUTHORED,
    ExecutionPlan,
    PlanCondition,
    PlanEvaluation,
    PlanRevision,
    PlanStep,
    SocketRef,
    evaluate_execution_plan,
    revise_execution_plan,
)


MALFORMED_PLAN_CONDITION_ID = "execution_plan_payload"


@dataclass(frozen=True)
class PlanRuntimeUpdate:
    evaluation: PlanEvaluation | None = None
    execution_plan_ref: ArtifactRef | None = None
    plan_evaluation_ref: ArtifactRef | None = None
    compact_status: Mapping[str, Any] | None = None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _socket_ref_from_payload(value: Any) -> SocketRef | None:
    if not isinstance(value, Mapping):
        return None
    return SocketRef(
        node_id=_str_or_none(value.get("node_id")),
        uid=_str_or_none(value.get("uid")),
        var=_str_or_none(value.get("var")),
        class_type=_str_or_none(value.get("class_type")),
        socket=_str_or_none(value.get("socket")),
        input_name=_str_or_none(value.get("input_name")),
        output_name=_str_or_none(value.get("output_name")),
        index=_int_or_none(value.get("index")),
        role=_str_or_none(value.get("role")),
    )


def _plan_condition_from_payload(value: Any) -> PlanCondition:
    payload = _mapping_or_empty(value)
    return PlanCondition(
        condition_id=str(payload.get("condition_id") or payload.get("id") or "unknown_condition"),
        kind=str(payload.get("kind") or ""),
        criticality=str(payload.get("criticality") or "required"),
        source=_socket_ref_from_payload(payload.get("source")),
        target=_socket_ref_from_payload(payload.get("target")),
        expected=payload.get("expected"),
        class_type=_str_or_none(payload.get("class_type")),
        input_name=_str_or_none(payload.get("input_name")),
        message=_str_or_none(payload.get("message")),
        details=_mapping_or_empty(payload.get("details")),
    )


def _plan_conditions_from_payload(value: Any) -> tuple[PlanCondition, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_plan_condition_from_payload(item) for item in value)


def _plan_revision_from_payload(value: Any) -> PlanRevision:
    payload = _mapping_or_empty(value)
    return PlanRevision(
        revision_id=str(payload.get("revision_id") or "unknown_revision"),
        authored_by=str(payload.get("authored_by") or "unknown"),
        authored_at=str(payload.get("authored_at") or ""),
        reason=str(payload.get("reason") or ""),
        changes=_mapping_or_empty(payload.get("changes")),
        provenance=str(payload.get("provenance") or PLAN_PROVENANCE_AGENT_AUTHORED),
        enforced=bool(payload.get("enforced", False)),
    )


def _plan_revisions_from_payload(value: Any) -> tuple[PlanRevision, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_plan_revision_from_payload(item) for item in value)


def _plan_step_from_payload(value: Any) -> PlanStep:
    payload = _mapping_or_empty(value)
    return PlanStep(
        step_id=str(payload.get("step_id") or payload.get("id") or "unknown_step"),
        kind=str(payload.get("kind") or ""),
        criticality=str(payload.get("criticality") or "required"),
        status=str(payload.get("status") or "planned"),
        class_type=_str_or_none(payload.get("class_type")),
        conditions=_plan_conditions_from_payload(payload.get("conditions")),
    )


def _plan_steps_from_payload(value: Any) -> tuple[PlanStep, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_plan_step_from_payload(item) for item in value)


def extract_execution_plan_payload(protocol_notes: Mapping[str, Any]) -> Mapping[str, Any] | None:
    execution_plan_note = protocol_notes.get("execution_plan")
    if not isinstance(execution_plan_note, Mapping):
        return None
    plan_payload = execution_plan_note.get("plan")
    return plan_payload if isinstance(plan_payload, Mapping) else None


def execution_plan_from_payload(value: Mapping[str, Any]) -> ExecutionPlan:
    contract_version = value.get("contract_version")
    return ExecutionPlan(
        plan_id=str(value.get("plan_id") or "unknown"),
        goal=str(value.get("goal") or ""),
        source_graph_hash=_str_or_none(value.get("source_graph_hash")),
        candidate_graph_hash=_str_or_none(value.get("candidate_graph_hash")),
        research_result_hash=_str_or_none(value.get("research_result_hash")),
        required_steps=_plan_steps_from_payload(value.get("required_steps")),
        done_conditions=_plan_conditions_from_payload(value.get("done_conditions")),
        active_path_conditions=_plan_conditions_from_payload(value.get("active_path_conditions")),
        blocked_if=_plan_conditions_from_payload(value.get("blocked_if")),
        schema_provenance=_mapping_or_empty(value.get("schema_provenance")),
        runtime_provenance=_mapping_or_empty(value.get("runtime_provenance")),
        provenance=str(value.get("provenance") or PLAN_PROVENANCE_AGENT_AUTHORED),
        enforced=bool(value.get("enforced", False)),
        revision_history=_plan_revisions_from_payload(value.get("revision_history")),
        contract_version=contract_version if isinstance(contract_version, str) else "",
    )


def _merge_plan_payload(base: ExecutionPlan, value: Mapping[str, Any]) -> ExecutionPlan:
    """Merge a (possibly partial) revision payload over *base*.

    Keys present in *value* win; absent keys inherit from *base* so an
    agent-authored revision only needs to carry what actually changed.
    """
    def _pick(key: str, default: Any) -> Any:
        return value[key] if key in value else default

    contract_version = _pick("contract_version", base.contract_version)
    return ExecutionPlan(
        plan_id=str(_pick("plan_id", base.plan_id) or "unknown"),
        goal=str(_pick("goal", base.goal) or ""),
        source_graph_hash=_str_or_none(_pick("source_graph_hash", base.source_graph_hash)),
        candidate_graph_hash=_str_or_none(_pick("candidate_graph_hash", base.candidate_graph_hash)),
        research_result_hash=_str_or_none(_pick("research_result_hash", base.research_result_hash)),
        required_steps=_plan_steps_from_payload(
            _pick("required_steps", [step.to_dict() for step in base.required_steps])
        ),
        done_conditions=_plan_conditions_from_payload(
            _pick("done_conditions", [condition.to_dict() for condition in base.done_conditions])
        ),
        active_path_conditions=_plan_conditions_from_payload(
            _pick(
                "active_path_conditions",
                [condition.to_dict() for condition in base.active_path_conditions],
            )
        ),
        blocked_if=_plan_conditions_from_payload(
            _pick("blocked_if", [condition.to_dict() for condition in base.blocked_if])
        ),
        schema_provenance=_mapping_or_empty(_pick("schema_provenance", base.schema_provenance)),
        runtime_provenance=_mapping_or_empty(_pick("runtime_provenance", base.runtime_provenance)),
        provenance=str(_pick("provenance", base.provenance) or PLAN_PROVENANCE_AGENT_AUTHORED),
        enforced=bool(_pick("enforced", base.enforced)),
        revision_history=_plan_revisions_from_payload(
            _pick("revision_history", [revision.to_dict() for revision in base.revision_history])
        ),
        contract_version=(
            contract_version if isinstance(contract_version, str) else base.contract_version
        ),
    )


def write_execution_plan_artifact(state: Any) -> ArtifactRef | None:
    plan = getattr(state, "execution_plan", None)
    if plan is None:
        return None
    return write_json_artifact(state.execution_plan_path, plan.to_dict())


def write_plan_evaluation_artifact(state: Any) -> ArtifactRef | None:
    evaluation = getattr(state, "plan_evaluation", None)
    if evaluation is None:
        return None
    return write_json_artifact(state.plan_evaluation_path, evaluation.to_dict())


def hydrate_execution_plan_from_protocol_notes(
    state: Any,
    protocol_notes: Mapping[str, Any],
) -> PlanRuntimeUpdate | None:
    plan_payload = extract_execution_plan_payload(protocol_notes)
    if plan_payload is None:
        return None
    state.execution_plan = execution_plan_from_payload(plan_payload)
    plan_ref = write_execution_plan_artifact(state)
    return PlanRuntimeUpdate(
        evaluation=getattr(state, "plan_evaluation", None),
        execution_plan_ref=plan_ref,
        compact_status=format_compact_plan_status(state.execution_plan, state.plan_evaluation),
    )


def _plan_has_authority(plan: ExecutionPlan) -> bool:
    if plan.required_steps or plan.done_conditions or plan.active_path_conditions or plan.blocked_if:
        return True
    return False


def malformed_execution_plan_evaluation(
    plan: ExecutionPlan,
    *,
    candidate_graph_hash: str | None = None,
    reason: str | None = None,
) -> PlanEvaluation:
    message = "Execution plan payload has no required steps or evaluation conditions."
    if reason:
        message = f"{message} {reason}"
    return PlanEvaluation(
        plan_id=plan.plan_id,
        ok=False,
        blocking=True,
        source_graph_hash=plan.source_graph_hash,
        candidate_graph_hash=candidate_graph_hash or plan.candidate_graph_hash,
        failed_conditions=(
            {
                "condition_id": MALFORMED_PLAN_CONDITION_ID,
                "kind": "execution_plan_payload",
                "severity": "critical",
                "message": message,
            },
        ),
        feedback="plan evaluation blocked: malformed execution plan payload.",
        schema_provenance=plan.schema_provenance,
        runtime_provenance=plan.runtime_provenance,
    )


def evaluate_execution_plan_for_state(
    state: Any,
    graph: Mapping[str, Any] | None = None,
    *,
    candidate_graph_hash: str | None = None,
) -> PlanRuntimeUpdate:
    plan = getattr(state, "execution_plan", None)
    if plan is None:
        return PlanRuntimeUpdate(compact_status={})

    plan_ref = write_execution_plan_artifact(state)
    if not _plan_has_authority(plan) and plan.supported_contract_version:
        evaluation = malformed_execution_plan_evaluation(
            plan,
            candidate_graph_hash=candidate_graph_hash,
        )
    else:
        candidate_graph = graph if graph is not None else getattr(state, "ui_payload", None)
        # Always inspect the candidate graph through the ingest door.  The
        # retained ingest IR on state.workflow is not the post-edit candidate.
        evaluation = evaluate_execution_plan(
            candidate_graph,
            plan,
            candidate_graph_hash=candidate_graph_hash,
        ).fail_closed_if_unsupported_version()

    state.plan_evaluation = evaluation
    evaluation_ref = write_plan_evaluation_artifact(state)
    return PlanRuntimeUpdate(
        evaluation=evaluation,
        execution_plan_ref=plan_ref,
        plan_evaluation_ref=evaluation_ref,
        compact_status=format_compact_plan_status(plan, evaluation),
    )


def revise_execution_plan_for_state(
    state: Any,
    plan_payload: Mapping[str, Any],
    *,
    authored_by: str,
    reason: str,
    authored_at: str | None = None,
    changes: Mapping[str, Any] | None = None,
) -> PlanRuntimeUpdate | None:
    """Record an agent-authored revision of the state's execution plan.

    Merges *plan_payload* (partial payloads inherit unchanged fields from the
    current plan), stamps ``provenance=agent_authored`` / ``enforced=False``,
    appends an auditable :class:`PlanRevision` to the plan's revision history,
    and persists the plan artifact.  Returns ``None`` when the state carries no
    plan to revise.
    """
    current = getattr(state, "execution_plan", None)
    if current is None:
        return None
    state.execution_plan = revise_execution_plan(
        _merge_plan_payload(current, plan_payload),
        authored_by=authored_by,
        reason=reason,
        authored_at=authored_at,
        changes=changes,
    )
    plan_ref = write_execution_plan_artifact(state)
    return PlanRuntimeUpdate(
        evaluation=getattr(state, "plan_evaluation", None),
        execution_plan_ref=plan_ref,
        compact_status=format_compact_plan_status(state.execution_plan, state.plan_evaluation),
    )


def format_compact_plan_status(
    plan: ExecutionPlan | None,
    evaluation: PlanEvaluation | None,
) -> dict[str, Any]:
    if plan is None:
        return {}
    failed_condition_ids: list[str] = []
    if evaluation is not None:
        failed_condition_ids = [
            str(condition.get("condition_id") or condition.get("id") or "unknown_condition")
            for condition in evaluation.failed_conditions
            if isinstance(condition, Mapping)
        ]
    advisory_miss_ids: list[str] = []
    if evaluation is not None:
        advisory_miss_ids = [
            str(item.get("step_id") or "unknown_step")
            for item in getattr(evaluation, "diagnostics", ()) or ()
            if isinstance(item, Mapping)
            and str(item.get("kind") or "") == "advisory_step_miss"
        ]
    return {
        "plan_id": plan.plan_id,
        "provenance": plan.provenance,
        "enforced": plan.enforced,
        "revision_count": len(plan.revision_history),
        "required_steps": [
            {
                "step_id": step.step_id,
                "kind": step.kind,
                "criticality": step.criticality,
                "status": step.status,
                "class_type": step.class_type,
            }
            for step in plan.required_steps
        ],
        "ok": evaluation.ok if evaluation is not None else None,
        "blocking": evaluation.blocking if evaluation is not None else None,
        "advisory_miss_ids": advisory_miss_ids,
        "failed_condition_ids": failed_condition_ids,
        "feedback": evaluation.feedback if evaluation is not None else "",
    }


def format_compact_plan_feedback(
    plan: ExecutionPlan | None,
    evaluation: PlanEvaluation | None,
) -> str:
    status = format_compact_plan_status(plan, evaluation)
    if not status:
        return ""
    failed = ", ".join(status["failed_condition_ids"]) or "none"
    advisory = ", ".join(status["advisory_miss_ids"]) or "none"
    ok = status["ok"] if status["ok"] is not None else "not_evaluated"
    blocking = status["blocking"] if status["blocking"] is not None else "unknown"
    feedback = status["feedback"] or "plan has not been evaluated yet."
    return (
        f"plan_id={status['plan_id']} ok={ok} blocking={blocking} "
        f"failed_conditions={failed} advisory_step_misses={advisory}; {feedback}"
    )


__all__ = (
    "MALFORMED_PLAN_CONDITION_ID",
    "PlanRuntimeUpdate",
    "evaluate_execution_plan_for_state",
    "execution_plan_from_payload",
    "extract_execution_plan_payload",
    "format_compact_plan_feedback",
    "format_compact_plan_status",
    "hydrate_execution_plan_from_protocol_notes",
    "malformed_execution_plan_evaluation",
    "revise_execution_plan_for_state",
    "write_execution_plan_artifact",
    "write_plan_evaluation_artifact",
)
