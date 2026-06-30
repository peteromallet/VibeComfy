"""Runtime helpers for plan-backed agent edit execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .audit import write_json_artifact
from .contracts import ArtifactRef
from .execution_plan import (
    ExecutionPlan,
    PlanCondition,
    PlanEvaluation,
    PlanStep,
    RoleBinding,
    SocketRef,
    evaluate_execution_plan,
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


def _plan_step_from_payload(value: Any) -> PlanStep:
    payload = _mapping_or_empty(value)
    evidence_refs = payload.get("evidence_refs")
    return PlanStep(
        step_id=str(payload.get("step_id") or payload.get("id") or "unknown_step"),
        kind=str(payload.get("kind") or ""),
        criticality=str(payload.get("criticality") or "required"),
        status=str(payload.get("status") or "planned"),
        class_type=_str_or_none(payload.get("class_type")),
        assign_to=_str_or_none(payload.get("assign_to")),
        schema_source=_str_or_none(payload.get("schema_source")),
        runtime_availability=_str_or_none(payload.get("runtime_availability")),
        inputs=_mapping_or_empty(payload.get("inputs")),
        values=_mapping_or_empty(payload.get("values")),
        conditions=_plan_conditions_from_payload(payload.get("conditions")),
        evidence_refs=tuple(str(ref) for ref in evidence_refs) if isinstance(evidence_refs, list) else (),
    )


def _plan_steps_from_payload(value: Any) -> tuple[PlanStep, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_plan_step_from_payload(item) for item in value)


def _role_binding_from_payload(value: Any) -> RoleBinding:
    payload = _mapping_or_empty(value)
    role = str(payload.get("role") or "unknown_role")
    return RoleBinding(
        role=role,
        node_ref=_socket_ref_from_payload(payload.get("node_ref")) or SocketRef(role=role),
        class_type=_str_or_none(payload.get("class_type")),
        confidence=str(payload.get("confidence") or "unknown"),
        evidence=_mapping_or_empty(payload.get("evidence")),
    )


def _role_bindings_from_payload(value: Any) -> tuple[RoleBinding, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_role_binding_from_payload(item) for item in value)


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
        selected_precedent_id=_str_or_none(value.get("selected_precedent_id")),
        selected_precedent=_mapping_or_empty(value.get("selected_precedent")),
        role_bindings=_role_bindings_from_payload(value.get("role_bindings")),
        required_steps=_plan_steps_from_payload(value.get("required_steps")),
        done_conditions=_plan_conditions_from_payload(value.get("done_conditions")),
        active_path_conditions=_plan_conditions_from_payload(value.get("active_path_conditions")),
        blocked_if=_plan_conditions_from_payload(value.get("blocked_if")),
        schema_provenance=_mapping_or_empty(value.get("schema_provenance")),
        runtime_provenance=_mapping_or_empty(value.get("runtime_provenance")),
        contract_version=contract_version if isinstance(contract_version, str) else "",
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
        selected_precedent_id=plan.selected_precedent_id,
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
    return {
        "plan_id": plan.plan_id,
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
    ok = status["ok"] if status["ok"] is not None else "not_evaluated"
    blocking = status["blocking"] if status["blocking"] is not None else "unknown"
    feedback = status["feedback"] or "plan has not been evaluated yet."
    return (
        f"plan_id={status['plan_id']} ok={ok} blocking={blocking} "
        f"failed_conditions={failed}; {feedback}"
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
    "write_execution_plan_artifact",
    "write_plan_evaluation_artifact",
)
