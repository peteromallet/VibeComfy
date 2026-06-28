"""Response and failure-envelope builders for agent-edit."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Callable, Mapping

from ..contracts import (
    AgentError,
    ApplyCandidate,
    ApplyEligibility,
    FailureKind,
    StageSnapshot,
    TurnIdentity,
    TurnOutcome,
    build_legacy_agent_edit_v1,
    derive_apply_eligibility,
    ensure_agent_edit_response_contract,
    failure_envelope,
    product_failure_envelope_fields,
    public_outcome_from_turn_outcome,
    success_envelope,
    turn_envelope,
)
from ..gates import derive_gates
from ..provider import ensure_sentence_message
from .artifacts import _json_safe
from .budget import (
    _BATCH_EXIT_BUDGET,
    _BATCH_EXIT_DONE,
    _BATCH_EXIT_EDIT_CLARIFY,
    _BATCH_EXIT_NOOP,
    _BATCH_EXIT_PURE_CLARIFY,
    _batch_candidate_graph_changed,
    _real_field_changes,
)
from .clarify import (
    sanitize_pure_clarify_response as _sanitize_pure_clarify_response,
    strip_clarify_forbidden_response_fields as _strip_clarify_forbidden_response_fields,
)
from .messages import (
    _change_details_payload,
    _resolver_candidates_from_batch_turns,
    _synthesize_batch_repl_message,
)
from .state import AgentEditState


def _failure_response(
    state: AgentEditState,
    context: Any,
    failure: AgentError,
    *,
    contract: str = "batch_repl",
    build_dev_failure_response: Callable[..., dict[str, Any]],
    build_batch_repl_failure_response: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if contract != "batch_repl":
        return build_dev_failure_response(state, context, failure=failure)
    return build_batch_repl_failure_response(state, context, failure=failure)


def _validated_agent_edit_response(
    response: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    try:
        return ensure_agent_edit_response_contract(response, stage=stage)
    except Exception as exc:
        fallback = _product_failure_response(
            failure_envelope(
                FailureKind.VALIDATION_ERROR,
                stage,
                agent_failure_context={
                    "explanation": (
                        "Agent edit response contract validation failed before return: "
                        f"{exc}"
                    )
                },
            )
        )
        return ensure_agent_edit_response_contract(fallback, stage=stage)


def _product_failure_response(failure: AgentError) -> dict[str, Any]:
    response = failure.to_dict()
    response.update(product_failure_envelope_fields(failure))
    return response


def _build_candidate_payload(
    state: AgentEditState,
    *,
    compatibility_fields: Mapping[str, Any],
    has_candidate: bool,
    turn_identity: TurnIdentity,
) -> dict[str, Any] | None:
    if not has_candidate:
        return None
    candidate = ApplyCandidate(
        state="candidate",
        graph=state.ui_payload or {},
        graph_hash=compatibility_fields["candidate_graph_hash"],
        structural_graph_hash=compatibility_fields["candidate_structural_graph_hash"],
        baseline_graph_hash=compatibility_fields["baseline_graph_hash"],
        submit_graph_hash=compatibility_fields["submit_graph_hash"],
        submit_structural_graph_hash=compatibility_fields["submit_structural_graph_hash"],
        turn_identity=turn_identity,
    )
    return candidate.to_dict()


def _stage_snapshot_payloads(context: Any) -> list[dict[str, Any]]:
    snapshots = tuple(
        StageSnapshot.from_stage_result(result)
        for result in context.stage_results.values()
    )
    return [snapshot.to_dict() for snapshot in snapshots]


def _legacy_failure_response(
    state: AgentEditState,
    context: Any,
    *,
    failure: AgentError,
    build_compatibility_response_fields: Callable[[AgentEditState], dict[str, Any]],
    stage_audit: Callable[..., Any],
) -> dict[str, Any]:
    derive_gates(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
        client_graph_hash=state.submit_structural_graph_hash,
    )
    failure = dataclasses.replace(
        failure,
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    try:
        audit_ref = stage_audit(state, context, failure=failure)
        failure = dataclasses.replace(failure, audit_ref=audit_ref)
    except Exception as audit_exc:
        failure = dataclasses.replace(failure, audit_error=str(audit_exc))
    response = failure.to_dict()
    if failure.kind is FailureKind.STALE_STATE_MISMATCH:
        eligibility = derive_apply_eligibility(
            context,
            live_structural_graph_hash=state.baseline_graph_hash,
            submit_structural_graph_hash=state.submit_structural_graph_hash,
        )
    else:
        eligibility = derive_apply_eligibility(context, has_candidate=False)
    response.update(
        {
            "eligibility": eligibility.to_dict(),
            "canvas_apply_allowed": context.canvas_apply_allowed,
            "queue_allowed": context.queue_allowed,
        }
    )
    response = build_legacy_agent_edit_v1(response)
    response.update(product_failure_envelope_fields(failure))
    failure_context = response.get("agent_failure_context")
    issues = failure_context.get("issues") if isinstance(failure_context, Mapping) else None
    if isinstance(issues, list):
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            recovery = issue.get("rebaseline_recovery")
            if isinstance(recovery, Mapping):
                response["rebaseline_recovery"] = dict(recovery)
                break
    response["internal_outcome"] = TurnOutcome.from_failure(failure).to_dict()
    response.update(build_compatibility_response_fields(state))
    return response


def _session_artifact_response_fields(state: AgentEditState) -> dict[str, Any]:
    response_path = state.turn_dir / "response.json"
    return {
        "session_path": str(state.session_dir),
        "session_path_resolved": str(state.session_dir.resolve()),
        "detail_json_path": str(response_path),
        "detail_json_path_resolved": str(response_path.resolve()),
    }


def _build_batch_repl_failure_response(
    state: AgentEditState,
    context: Any,
    *,
    failure: AgentError,
    build_compatibility_response_fields: Callable[[AgentEditState], dict[str, Any]],
    stage_audit: Callable[..., Any],
) -> dict[str, Any]:
    response = _legacy_failure_response(
        state,
        context,
        failure=failure,
        build_compatibility_response_fields=build_compatibility_response_fields,
        stage_audit=stage_audit,
    )
    compatibility_fields = build_compatibility_response_fields(state)
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    response["eligibility"] = response["apply_eligibility"]
    response["message"] = _synthesize_batch_repl_message(state, failure=failure)
    response["debug"] = {
        **response["debug"],
        "gates": context.gate_snapshot(),
        "hashes": dict(compatibility_fields),
    }
    return response


def _build_dev_failure_response(
    state: AgentEditState,
    context: Any,
    *,
    failure: AgentError,
    build_compatibility_response_fields: Callable[[AgentEditState], dict[str, Any]],
    stage_audit: Callable[..., Any],
) -> dict[str, Any]:
    response = _legacy_failure_response(
        state,
        context,
        failure=failure,
        build_compatibility_response_fields=build_compatibility_response_fields,
        stage_audit=stage_audit,
    )
    response.update(_session_artifact_response_fields(state))
    return response


def _build_batch_repl_response(
    state: AgentEditState,
    context: Any,
    *,
    build_compatibility_response_fields: Callable[[AgentEditState], dict[str, Any]],
    canonical_route: Callable[[str | None], str | None],
    route_blocks_apply: Callable[[str | None], bool],
    route_change_focus_label: Callable[[str | None], str],
    build_precedent_semantic_check_entries: Callable[[AgentEditState], list[dict[str, Any]]],
) -> dict[str, Any]:
    turn_identity = TurnIdentity.from_context(context)
    stage_snapshots = _stage_snapshot_payloads(context)
    canonical = canonical_route(state.route)
    has_candidate = (
        state.batch_exit_mode in {_BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_DONE}
        and _batch_candidate_graph_changed(state)
    )
    if canonical == "revise" and (
        state.revision_evidence is None
        or state.revision_evidence.scoped_diff is None
        or state.revision_evidence.candidate_eligible is not True
    ):
        has_candidate = False
    if route_blocks_apply(state.route):
        has_candidate = False
    compatibility_fields = build_compatibility_response_fields(state)
    response_apply_eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate",
    )
    if route_blocks_apply(state.route):
        response_apply_eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message=f"Apply is not available for {state.route} routes.",
        )
    elif has_candidate:
        response_apply_eligibility = ApplyEligibility(
            applyable=bool(context.canvas_apply_allowed),
            reason="queue_blocked_warning" if context.canvas_apply_allowed else "server_blocked",
            message=(
                "Apply is allowed, but Queue remains blocked for this candidate."
                if context.canvas_apply_allowed
                else "Server validation gates blocked Apply."
            ),
            warnings=("queue_blocked",) if context.canvas_apply_allowed else (),
        )
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=response_apply_eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed if has_candidate else False,
        queue_allowed=False,
    )
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
    )
    resolver_candidates = _resolver_candidates_from_batch_turns(state)
    missing_custom_nodes_terminal = (
        state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
        and bool(resolver_candidates)
    )
    if missing_custom_nodes_terminal:
        internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    elif route_blocks_apply(state.route) and canonical != "clarify":
        internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY:
        internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY:
        internal_outcome = TurnOutcome.edit_and_clarify(
            changes=_real_field_changes(state.batch_field_changes),
            question=state.user_message or None,
        )
    elif state.batch_exit_mode == _BATCH_EXIT_DONE:
        internal_outcome = TurnOutcome.edit(changes=_real_field_changes(state.batch_field_changes))
    elif state.batch_exit_mode == _BATCH_EXIT_BUDGET:
        internal_outcome = TurnOutcome.budget(reason=state.batch_final_summary or None)
    else:
        internal_outcome = TurnOutcome.noop(
            reason=state.batch_done_summary or state.user_message or None
        )
    if missing_custom_nodes_terminal:
        public_outcome = {
            "kind": "requires_custom_nodes",
            "candidates": resolver_candidates,
            "warnings": [],
        }
    else:
        public_outcome = public_outcome_from_turn_outcome(
            internal_outcome,
            response={"candidate": candidate_payload},
        )
    if internal_outcome.kind == "edit":
        message = ensure_sentence_message(
            state.user_message,
            fallback="I made the requested workflow changes.",
        )
    else:
        message = _synthesize_batch_repl_message(state, outcome=internal_outcome)
    response.update(
        turn_envelope(
            message=message,
            outcome=public_outcome,
            candidate=candidate_payload,
            eligibility=response_apply_eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "turn_identity": turn_identity.to_dict(),
                "stage_snapshots": stage_snapshots,
                "batch_repl": {
                    "turn_count": state.batch_turn_count,
                    "exit_mode": state.batch_exit_mode,
                    "done_summary": state.batch_done_summary,
                    "final_summary": state.batch_final_summary,
                    "budget_state": _json_safe(state.batch_budget_state),
                },
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    response["change_details"] = _change_details_payload(state, context)
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    if canonical:
        response["route"] = canonical
    if canonical == "research":
        response["graph_unchanged"] = True
        response["no_candidate_reason"] = "route_not_applyable"
    if state.batch_exit_mode in {_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY} and not missing_custom_nodes_terminal:
        response["clarification_required"] = True
        response["graph_unchanged"] = state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
    elif missing_custom_nodes_terminal:
        response["graph_unchanged"] = True
        response["no_candidate_reason"] = "route_not_applyable"
    elif state.batch_exit_mode == _BATCH_EXIT_NOOP:
        response["graph_unchanged"] = True
        if state.batch_done_summary:
            response["done_summary"] = state.batch_done_summary
    elif state.batch_done_summary:
        response["done_summary"] = state.batch_done_summary
    response["batch_turns"] = _json_safe(state.batch_turns)
    if canonical == "adapt":
        semantic_entries = build_precedent_semantic_check_entries(state)
        if semantic_entries:
            response.setdefault("task_satisfaction", []).extend(semantic_entries)
    change_focus = route_change_focus_label(state.route)
    if change_focus:
        response["change_focus"] = change_focus
    built_response = build_legacy_agent_edit_v1(
        {
            **response,
            "canvas_apply_allowed": context.canvas_apply_allowed if has_candidate else False,
            "queue_allowed": False,
        }
    )
    built_response["queue_allowed"] = False
    if missing_custom_nodes_terminal:
        return _strip_clarify_forbidden_response_fields(built_response)
    return _sanitize_pure_clarify_response(built_response)


def _build_dev_success_response(
    state: AgentEditState,
    context: Any,
    *,
    contract: str,
    build_compatibility_response_fields: Callable[[AgentEditState], dict[str, Any]],
    canonical_route: Callable[[str | None], str | None],
    route_blocks_apply: Callable[[str | None], bool],
    route_change_focus_label: Callable[[str | None], str],
    build_precedent_semantic_check_entries: Callable[[AgentEditState], list[dict[str, Any]]],
) -> dict[str, Any]:
    turn_identity = TurnIdentity.from_context(context)
    stage_snapshots = _stage_snapshot_payloads(context)
    compatibility_fields = build_compatibility_response_fields(state)
    eligibility = derive_apply_eligibility(
        context,
        has_candidate=True,
        candidate_state="candidate",
    )
    if route_blocks_apply(state.route):
        eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message=f"Apply is not available for {state.route} routes.",
        )
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    if route_blocks_apply(state.route):
        has_candidate = False
        if canonical_route(state.route) == "clarify":
            internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
        else:
            internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    else:
        has_candidate = True
        internal_outcome = TurnOutcome.edit()
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
    )
    response.update(
        turn_envelope(
            message=state.user_message,
            outcome=public_outcome_from_turn_outcome(
                internal_outcome,
                response={"candidate": candidate_payload} if has_candidate else None,
            ),
            candidate=candidate_payload,
            eligibility=eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "turn_identity": turn_identity.to_dict(),
                "stage_snapshots": stage_snapshots,
                "contract": contract,
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    if contract == "delta":
        from vibecomfy.porting.edit.ops import op_to_dict

        response["delta_ops"] = [op_to_dict(op) for op in state.delta_ops]
    if canonical_route(state.route) == "adapt":
        semantic_entries = build_precedent_semantic_check_entries(state)
        if semantic_entries:
            response.setdefault("task_satisfaction", []).extend(semantic_entries)
    change_focus = route_change_focus_label(state.route)
    if change_focus:
        response["change_focus"] = change_focus
    return _sanitize_pure_clarify_response(
        build_legacy_agent_edit_v1(
            {
                **response,
                "canvas_apply_allowed": context.canvas_apply_allowed if has_candidate else False,
                "queue_allowed": False,
            }
        )
    )


__all__ = [
    "_build_batch_repl_failure_response",
    "_build_batch_repl_response",
    "_build_candidate_payload",
    "_build_dev_failure_response",
    "_build_dev_success_response",
    "_failure_response",
    "_legacy_failure_response",
    "_product_failure_response",
    "_session_artifact_response_fields",
    "_stage_snapshot_payloads",
    "_validated_agent_edit_response",
]
