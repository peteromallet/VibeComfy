"""
Failure/success response shaping and batch/dev response contracts (T-039 extraction of the edit_response_contract fragment).

Extracted from the edit.py exec-assembled fragments (T-039, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Function bodies resolve their free
names from the assembled edit-module namespace at call time (marked with a
T-039 late import comment) so monkeypatches on edit.* stay visible exactly as
under the old exec assembly; guarded imports stay function-local.
"""
from __future__ import annotations

import dataclasses
import json
from typing import Any, Mapping


import logging

LOGGER = logging.getLogger("vibecomfy.comfy_nodes.agent.edit_response_contract")

from .contracts import _clarification_payload


def _failure_response(
    state: AgentEditState,
    context: TurnContext,
    failure: FailureEnvelope,
    *,
    contract: str = "batch_repl",
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_build_batch_repl_failure_response, _build_dev_failure_response)  # T-039 late import: host namespace lookup; resolved at call time
    if contract != "batch_repl":
        return _build_dev_failure_response(state, context, failure=failure)
    return _build_batch_repl_failure_response(state, context, failure=failure)


def _validated_agent_edit_response(
    response: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, _product_failure_response, ensure_agent_edit_response_contract, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
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


def _canonical_delta_ops_envelope_payload(delta_ops: tuple[Any, ...]) -> dict[str, Any]:
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        ensure_root_scoped_delta_envelope,
        op_to_dict,
    )

    return ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [op_to_dict(op) for op in delta_ops],
        },
        strict=True,
    ).to_dict()


def _build_cumulative_batch_repl_delta_envelope(state: AgentEditState) -> dict[str, Any] | None:
    """Assemble one cumulative normalized V2 delta envelope from landed
    batch_repl operations across all turns.

    Returns ``{schema_version, ops}`` or ``None`` when no ops were landed.
    ``delta_ops`` must only be exposed as a read-only derived compatibility
    view from this canonical envelope.
    """
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        ensure_root_scoped_delta_envelope,
    )

    cumulative_ops: list[dict[str, Any]] = []
    for turn in state.batch_turns:
        if not isinstance(turn, dict):
            continue
        turn_envelope = turn.get("delta_ops_envelope")
        if not isinstance(turn_envelope, dict):
            continue
        turn_ops = turn_envelope.get("ops")
        if isinstance(turn_ops, list):
            cumulative_ops.extend(turn_ops)

    if not cumulative_ops:
        return None

    return ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": cumulative_ops,
        },
        strict=True,
    ).to_dict()


def _product_failure_response(failure: AgentError) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (product_failure_envelope_fields)  # T-039 late import: host namespace lookup; resolved at call time
    response = failure.to_dict()
    response.update(product_failure_envelope_fields(failure))
    return response


def _build_compatibility_response_fields(state: AgentEditState) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (payload_hash, structural_graph_hash)  # T-039 late import: host namespace lookup; resolved at call time
    candidate_graph_hash = payload_hash(state.ui_payload)
    candidate_structural_graph_hash = structural_graph_hash(state.ui_payload)
    return {
        "baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "submitted_client_graph_hash": state.submitted_client_graph_hash,
        "submitted_client_structural_graph_hash": state.submitted_client_structural_graph_hash,
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": candidate_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
    }


def _v2_candidate_mutation_plan_fields(
    *,
    compatibility_fields: Mapping[str, Any],
    delta_ops_envelope: Mapping[str, Any] | None,
) -> dict[str, str | None]:
    from vibecomfy.comfy_nodes.agent.edit import (v2_mutation_plan_hash)  # T-039 late import: host namespace lookup; resolved at call time
    """Bind a reviewable V2 candidate to its canonical mutation evidence.

    The plan identity covers both the canonical delta and the structural graph
    boundary it is expected to cross.  Keeping this derivation on the server
    prevents the browser from inventing an arbitrary transaction identity and
    makes ordinary adapt/revise candidates use the same prepare/finalize path
    as layout candidates.
    """
    if not isinstance(delta_ops_envelope, Mapping):
        return {
            "plan_hash": None,
            "structural_hash_before": None,
            "structural_hash_after": None,
        }
    structural_hash_before = compatibility_fields.get("submit_structural_graph_hash")
    structural_hash_after = compatibility_fields.get("candidate_structural_graph_hash")
    plan_hash = v2_mutation_plan_hash(
        delta_ops_envelope=delta_ops_envelope,
        structural_hash_before=(
            structural_hash_before if isinstance(structural_hash_before, str) else None
        ),
        structural_hash_after=(
            structural_hash_after if isinstance(structural_hash_after, str) else None
        ),
    )
    return {
        "plan_hash": plan_hash,
        "structural_hash_before": (
            structural_hash_before if isinstance(structural_hash_before, str) else None
        ),
        "structural_hash_after": (
            structural_hash_after if isinstance(structural_hash_after, str) else None
        ),
    }


def _build_candidate_payload(
    state: AgentEditState,
    *,
    compatibility_fields: Mapping[str, Any],
    has_candidate: bool,
    turn_identity: TurnIdentity,
    plan_hash: str | None = None,
    structural_hash_before: str | None = None,
    structural_hash_after: str | None = None,
    monotonic_generation: int | None = None,
    lease_nonce: str | None = None,
) -> dict[str, Any] | None:
    from vibecomfy.comfy_nodes.agent.edit import (ApplyCandidate)  # T-039 late import: host namespace lookup; resolved at call time
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
        plan_hash=plan_hash,
        structural_hash_before=structural_hash_before,
        structural_hash_after=structural_hash_after,
        monotonic_generation=monotonic_generation,
        lease_nonce=lease_nonce,
    )
    return candidate.to_dict()


def _layout_only_reorganise_evidence_changed(state: AgentEditState) -> bool:
    report = getattr(state, "report", None)
    if not isinstance(report, Mapping) or report.get("kind") != "reorganise":
        return False
    evidence = report.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    if evidence.get("candidate_available") is True:
        return True
    if evidence.get("full_ui_payload_hash_changed") is True:
        return True
    if evidence.get("layout_evidence_changed") is True:
        return True
    # Mutation-plan hash signals a non-trivial candidate even when layout-only.
    if evidence.get("plan_hash"):
        return True
    patch_apply = evidence.get("patch_apply")
    if not isinstance(patch_apply, Mapping):
        return False
    return bool(
        patch_apply.get("applied_entry_keys")
        or patch_apply.get("applied_group_scopes")
        or patch_apply.get("candidate_patch_sha256")
    )


def _candidate_full_ui_payload_changed(state: AgentEditState) -> bool:
    from vibecomfy.comfy_nodes.agent.edit import (payload_hash)  # T-039 late import: host namespace lookup; resolved at call time
    if not isinstance(state.ui_payload, Mapping) or not isinstance(state.graph, Mapping):
        return False
    return payload_hash(state.ui_payload) != payload_hash(state.graph)


def _response_contract_candidate_present(state: AgentEditState) -> bool:
    from vibecomfy.comfy_nodes.agent.edit import (_batch_candidate_graph_changed, _candidate_full_ui_payload_changed, _canonical_agent_edit_route, _layout_only_reorganise_evidence_changed)  # T-039 late import: host namespace lookup; resolved at call time
    if _batch_candidate_graph_changed(state):
        return True
    if _canonical_agent_edit_route(state.route) != "reorganise":
        return False
    return _candidate_full_ui_payload_changed(state) or _layout_only_reorganise_evidence_changed(state)


def _plan_validation_allows_candidate(state: AgentEditState, context: TurnContext) -> bool:
    from vibecomfy.comfy_nodes.agent.edit import (PLAN_STATE_NOT_REQUIRED, update_plan_validate_gate)  # T-039 late import: host namespace lookup; resolved at call time
    execution_plan = getattr(state, "execution_plan", None)
    if execution_plan is None:
        update_plan_validate_gate(
            context,
            execution_plan=None,
            plan_evaluation=None,
            has_execution_plan=False,
            plan_state=PLAN_STATE_NOT_REQUIRED,
        )
        return True
    plan_evaluation = getattr(state, "plan_evaluation", None)
    update_plan_validate_gate(
        context,
        execution_plan=execution_plan,
        plan_evaluation=plan_evaluation,
        has_execution_plan=True,
    )
    return bool(plan_evaluation is not None and plan_evaluation.ok)


def _execution_plan_artifact_refs(state: AgentEditState) -> dict[str, dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (_artifact)  # T-039 late import: host namespace lookup; resolved at call time
    refs: dict[str, dict[str, Any]] = {}
    if getattr(state, "execution_plan", None) is not None and state.execution_plan_path.is_file():
        refs["execution_plan"] = _artifact(state.execution_plan_path).to_dict()
    if getattr(state, "plan_evaluation", None) is not None and state.plan_evaluation_path.is_file():
        refs["plan_evaluation"] = _artifact(state.plan_evaluation_path).to_dict()
    return refs


def _response_artifacts_with_execution_plan(state: AgentEditState) -> dict[str, Any]:
    artifacts = dict(state.artifacts or {})
    if getattr(state, "execution_plan", None) is not None and state.execution_plan_path.is_file():
        artifacts["execution_plan"] = str(state.execution_plan_path)
    if getattr(state, "plan_evaluation", None) is not None and state.plan_evaluation_path.is_file():
        artifacts["plan_evaluation"] = str(state.plan_evaluation_path)
    return artifacts


def _execution_plan_response_fields(state: AgentEditState) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_json_safe, format_compact_plan_feedback, format_compact_plan_status)  # T-039 late import: host namespace lookup; resolved at call time
    fields: dict[str, Any] = {}
    dependencies = getattr(state, "runtime_dependencies", ()) or ()
    if dependencies:
        fields["runtime_dependencies"] = _json_safe(list(dependencies))
    execution_plan = getattr(state, "execution_plan", None)
    if execution_plan is None:
        return fields
    plan_evaluation = getattr(state, "plan_evaluation", None)
    fields.update({
        "execution_plan_status": format_compact_plan_status(execution_plan, plan_evaluation),
        "execution_plan_feedback": format_compact_plan_feedback(execution_plan, plan_evaluation),
    })
    return fields


def _execution_plan_debug_fields(state: AgentEditState) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_execution_plan_artifact_refs, _execution_plan_response_fields)  # T-039 late import: host namespace lookup; resolved at call time
    fields = _execution_plan_response_fields(state)
    if not fields:
        return {}
    fields["execution_plan_artifacts"] = _execution_plan_artifact_refs(state)
    return fields


def _narrative_artifact_refs(state: AgentEditState) -> dict[str, dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (_artifact)  # T-039 late import: host namespace lookup; resolved at call time
    refs: dict[str, dict[str, Any]] = {}
    artifact_paths = {
        "narrative_context": state.narrative_context_path,
        "narrative_request": state.narrative_request_path,
        "narrative_response": state.narrative_response_path,
        "narrative_validation": state.narrative_validation_path,
    }
    for name, path in artifact_paths.items():
        if path.is_file():
            refs[name] = _artifact(path).to_dict()
    return refs


def _narrative_debug_fields(state: AgentEditState) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_narrative_artifact_refs)  # T-039 late import: host namespace lookup; resolved at call time
    narrative: dict[str, Any] = {}
    refs = _narrative_artifact_refs(state)
    if refs:
        narrative["artifacts"] = refs
    if state.narrative_validation_path.is_file():
        try:
            payload = json.loads(state.narrative_validation_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = None
        if isinstance(payload, Mapping):
            narrative["attempted"] = bool(payload.get("attempted"))
            selected_source = payload.get("selected_source")
            if isinstance(selected_source, str) and selected_source.strip():
                narrative["selected_source"] = selected_source.strip()
            fallback_reason = payload.get("fallback_reason")
            if isinstance(fallback_reason, str) and fallback_reason.strip():
                narrative["fallback_reason"] = fallback_reason.strip()
            final_validation = payload.get("final_validation")
            if isinstance(final_validation, Mapping):
                narrative["final_validation_ok"] = bool(final_validation.get("ok"))
    return {"narrative": narrative} if narrative else {}


def _record_narrative_artifacts(state: AgentEditState) -> None:
    artifacts = {
        name: str(path)
        for name, path in (
            ("narrative_context", state.narrative_context_path),
            ("narrative_request", state.narrative_request_path),
            ("narrative_response", state.narrative_response_path),
            ("narrative_validation", state.narrative_validation_path),
        )
        if path.is_file()
    }
    if artifacts:
        state.artifacts = {**(state.artifacts or {}), **artifacts}


def _post_edit_reorganisation_public_advisory(decision: Any) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_json_safe)  # T-039 late import: host namespace lookup; resolved at call time
    payload = decision.to_json()
    return {
        **_json_safe(payload),
        "advisory": True,
        "suggested_command": "/reorganise_comfy_workflow",
        "message": (
            "The edit is ready to review, and the canvas may benefit from "
            "/reorganise_comfy_workflow."
        ),
    }


def _record_post_edit_reorganisation_advisory(
    state: AgentEditState,
    context: TurnContext,
    *,
    has_candidate: bool,
    apply_eligibility: ApplyEligibility,
) -> dict[str, Any] | None:
    from vibecomfy.comfy_nodes.agent.edit import (LOGGER, _canonical_agent_edit_route, _post_edit_reorganisation_public_advisory, _route_blocks_apply)  # T-039 late import: host namespace lookup; resolved at call time
    state.post_edit_reorganisation_advisory = None
    if not has_candidate or not apply_eligibility.applyable:
        return None
    if (
        _route_blocks_apply(state.route)
        or _canonical_agent_edit_route(state.route) == "reorganise"
    ):
        return None
    if not isinstance(state.graph, Mapping) or not isinstance(state.ui_payload, Mapping):
        return None
    try:
        from .layout_reorganisation import decide_post_edit_reorganisation

        decision = decide_post_edit_reorganisation(state.graph, state.ui_payload)
    except Exception:
        LOGGER.debug("post-edit reorganisation advisory decision failed", exc_info=True)
        return None
    decision_result = getattr(decision, "result", None)
    if decision_result == "prepare_candidate":
        try:
            from .reorganise import prepare_post_edit_reorganise_candidate

            metadata = prepare_post_edit_reorganise_candidate(
                state,
                context,
                source_ui=dict(state.ui_payload),
                decision=decision,
            )
        except Exception:
            LOGGER.debug("post-edit reorganisation candidate preparation failed", exc_info=True)
            return None
        state.post_edit_reorganisation_advisory = metadata
        return metadata
    if decision_result != "offer_reorganisation":
        return None
    advisory = _post_edit_reorganisation_public_advisory(decision)
    state.post_edit_reorganisation_advisory = advisory
    return advisory


def _has_enough_grounded_facts_for_dev_narrative(state: AgentEditState) -> bool:
    """Return True when the dev success path has batch-repl-style grounded facts.

    Without landed batch field changes or batch exit state, the helper cannot
    produce a meaningful grounded message and the deterministic executor
    message (state.user_message) is preserved.
    """
    return bool(
        state.batch_field_changes
        or state.batch_exit_mode
        or state.batch_done_summary
    )


def _legacy_narrative_debug_status(
    fallback_reason: str,
    *,
    attempted: bool = False,
) -> dict[str, Any]:
    return {
        "narrative": {
            "attempted": attempted,
            "selected_source": "legacy",
            "fallback_reason": fallback_reason,
        }
    }


def _prepare_narrative_artifact_paths(state: AgentEditState) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (_narrative_artifact_path)  # T-039 late import: host namespace lookup; resolved at call time
    state.narrative_context_path = _narrative_artifact_path(
        state,
        state.narrative_context_path,
    )
    state.narrative_request_path = _narrative_artifact_path(
        state,
        state.narrative_request_path,
    )
    state.narrative_response_path = _narrative_artifact_path(
        state,
        state.narrative_response_path,
    )
    state.narrative_validation_path = _narrative_artifact_path(
        state,
        state.narrative_validation_path,
    )


def _response_apply_eligibility(value: Any) -> ApplyEligibility | None:
    from vibecomfy.comfy_nodes.agent.edit import (ApplyEligibility)  # T-039 late import: host namespace lookup; resolved at call time
    if not isinstance(value, Mapping):
        return None
    warnings = value.get("warnings")
    try:
        return ApplyEligibility(
            applyable=bool(value.get("applyable")),
            reason=str(value.get("reason") or ""),
            message=str(value.get("message") or ""),
            warnings=tuple(
                item for item in warnings if isinstance(item, str)
            ) if isinstance(warnings, list) else (),
        )
    except ValueError:
        return None


def _sync_narrated_clarify_outcome(
    message: str,
    *,
    internal_outcome: TurnOutcome,
    public_outcome: Mapping[str, Any],
) -> tuple[TurnOutcome, dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (TurnOutcome, _clarification_payload, _format_clarify_markdown_message)  # T-039 late import: host namespace lookup; resolved at call time
    if internal_outcome.kind not in {"clarify", "edit+clarify"}:
        return internal_outcome, dict(public_outcome)
    if internal_outcome.kind == "edit+clarify":
        # For edit+clarify the public message includes the edit lead; the
        # clarify question must remain the original question, not the full
        # narrated message.
        question = _format_clarify_markdown_message(
            internal_outcome.question
            if isinstance(internal_outcome.question, str) and internal_outcome.question.strip()
            else message
        )
    else:
        question = _format_clarify_markdown_message(message)
    if internal_outcome.kind == "clarify":
        synced_internal = TurnOutcome.clarify(question=question)
    else:
        synced_internal = TurnOutcome.edit_and_clarify(
            changes=internal_outcome.changes,
            question=question,
        )
    synced_public = dict(public_outcome)
    synced_public.update(_clarification_payload(question))
    return synced_internal, synced_public


def _execution_plan_task_satisfaction_entries(state: AgentEditState) -> list[dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (format_compact_plan_status)  # T-039 late import: host namespace lookup; resolved at call time
    execution_plan = getattr(state, "execution_plan", None)
    if execution_plan is None:
        return []
    plan_evaluation = getattr(state, "plan_evaluation", None)
    status = format_compact_plan_status(execution_plan, plan_evaluation)
    failed_condition_ids = list(status.get("failed_condition_ids") or [])
    ok = status.get("ok")
    if ok is True:
        satisfaction = "pass"
        description = "Execution plan validation passed."
    elif ok is False:
        satisfaction = "fail"
        description = "Execution plan validation failed."
    else:
        satisfaction = "not_evaluated"
        description = "Execution plan has not been evaluated for this candidate."
    return [
        {
            "check": "execution_plan",
            "status": satisfaction,
            "satisfaction": satisfaction,
            "description": description,
            "plan_id": status.get("plan_id"),
            "blocking": status.get("blocking"),
            "failed_condition_ids": failed_condition_ids,
            "feedback": status.get("feedback") or "",
        }
    ]


def _stage_snapshot_payloads(context: TurnContext) -> list[dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (StageSnapshot)  # T-039 late import: host namespace lookup; resolved at call time
    snapshots = tuple(
        StageSnapshot.from_stage_result(result)
        for result in context.stage_results.values()
    )
    return [snapshot.to_dict() for snapshot in snapshots]


_CLARIFY_FORBIDDEN_RESPONSE_KEYS = {
    "candidate",
    "graph",
    "candidate_graph",
    "apply_eligible",
    "apply_eligibility",
    "eligibility",
    "apply_allowed",
    "canvas_apply_allowed",
    "queue_allowed",
}


def _validate_delta_evidence_for_apply(
    state: AgentEditState,
    *,
    has_candidate: bool,
) -> tuple[bool, dict[str, Any], dict[str, Any] | None]:
    from vibecomfy.comfy_nodes.agent.edit import (_build_cumulative_batch_repl_delta_envelope, _json_safe)  # T-039 late import: host namespace lookup; resolved at call time
    """Validate cumulative delta evidence for Apply eligibility.

    Assembles the cumulative delta envelope and runs
    ``validate_apply_delta_evidence``.  For edit turns where a candidate
    would otherwise be produced, absent delta evidence is fail-closed:
    a canonical empty V2 envelope is synthesized so that identity/no-op
    apply carries explicit (empty) evidence rather than silently
    accepting absent evidence.  Malformed or corrupted evidence blocks
    Apply unconditionally.

    Returns ``(delta_evidence_valid, diagnostics, validated_envelope)``
    where *validated_envelope* is the canonical envelope to emit in the
    response (the real envelope, the synthesized empty envelope, or
    ``None`` when no candidate is being considered).
    """
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        validate_apply_delta_evidence,
    )

    diagnostics: dict[str, Any] = {}
    cumulative = _build_cumulative_batch_repl_delta_envelope(state)
    validated_envelope: dict[str, Any] | None = cumulative

    # When a candidate would otherwise be produced, absent cumulative delta
    # evidence is fail-closed: synthesize a canonical empty V2 envelope so
    # that identity/no-op apply carries explicit (empty) evidence rather
    # than silently accepting absent evidence.
    if has_candidate and cumulative is None:
        cumulative = {"schema_version": DELTA_SCHEMA_VERSION, "ops": []}
        validated_envelope = cumulative
        diagnostics["delta_evidence_synthesized_empty"] = True

    # Absent evidence is acceptable only for non-applyable turns (no
    # candidate).  When a candidate exists, the synthesized empty envelope
    # ensures the payload is never None, so allow_absent=False is enforced.
    allow_absent = not has_candidate

    valid, code, detail = validate_apply_delta_evidence(
        cumulative,
        allow_absent=allow_absent,
    )
    diagnostics["delta_evidence_valid"] = valid
    diagnostics["delta_evidence_code"] = code
    if detail:
        diagnostics["delta_evidence_detail"] = _json_safe(detail)
    if cumulative is not None:
        diagnostics["delta_evidence_present"] = True
        diagnostics["delta_evidence_ops_count"] = len(cumulative.get("ops", []))
    else:
        diagnostics["delta_evidence_present"] = False
        diagnostics["delta_evidence_ops_count"] = 0

    # Only return the envelope for response emission when validation passed.
    if not valid:
        validated_envelope = None

    return valid, diagnostics, validated_envelope


def _format_clarify_markdown_message(message: Any) -> str:
    text = message.strip() if isinstance(message, str) else ""
    if not text:
        text = "What detail should I use before continuing?"
    return text


def _strip_clarify_forbidden_response_fields(value: Any) -> Any:
    from vibecomfy.comfy_nodes.agent.edit import (_CLARIFY_FORBIDDEN_RESPONSE_KEYS, _strip_clarify_forbidden_response_fields)  # T-039 late import: host namespace lookup; resolved at call time
    if isinstance(value, dict):
        stripped: dict[str, Any] = {}
        for key, item in value.items():
            if key in _CLARIFY_FORBIDDEN_RESPONSE_KEYS or key.startswith("candidate_"):
                continue
            stripped[key] = _strip_clarify_forbidden_response_fields(item)
        return stripped
    if isinstance(value, list):
        return [_strip_clarify_forbidden_response_fields(item) for item in value]
    return value


def _sanitize_pure_clarify_response(response: dict[str, Any]) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_format_clarify_markdown_message, _strip_clarify_forbidden_response_fields)  # T-039 late import: host namespace lookup; resolved at call time
    outcome = response.get("outcome")
    if not isinstance(outcome, Mapping) or outcome.get("kind") != "clarify":
        return response
    message = response.get("message") or outcome.get("question")
    markdown = _format_clarify_markdown_message(message)
    response = dict(response)
    response["message"] = markdown
    response["outcome"] = {
        "kind": "clarify",
        "question": markdown,
        "clarification": {"message": markdown},
    }
    internal_outcome = response.get("internal_outcome")
    if isinstance(internal_outcome, Mapping) and internal_outcome.get("kind") == "clarify":
        response["internal_outcome"] = {"kind": "clarify", "question": markdown}
    response["clarification_required"] = True
    response["clarification_message"] = markdown
    return _strip_clarify_forbidden_response_fields(response)


def _resolver_candidates_from_batch_turns(state: AgentEditState) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for turn in state.batch_turns:
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            for key_name in ("resolver_candidates", "workflow_schema_candidates"):
                raw_candidates = detail.get(key_name)
                if not isinstance(raw_candidates, list):
                    continue
                for raw_candidate in raw_candidates:
                    if not isinstance(raw_candidate, Mapping):
                        continue
                    candidate = dict(raw_candidate)
                    key = (
                        str(candidate.get("stable_install_hash") or "")
                        or json.dumps(candidate, sort_keys=True, default=str)
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(candidate)
    return candidates


def _resolver_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        detail = getattr(statement, "detail", None)
        if not isinstance(detail, Mapping):
            continue
        for key_name in ("resolver_candidates", "workflow_schema_candidates"):
            raw_candidates = detail.get(key_name)
            if not isinstance(raw_candidates, list):
                continue
            for raw_candidate in raw_candidates:
                if isinstance(raw_candidate, Mapping):
                    candidates.append(dict(raw_candidate))
    return candidates


def _workflow_schema_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        detail = getattr(statement, "detail", None)
        if not isinstance(detail, Mapping):
            continue
        raw_candidates = detail.get("workflow_schema_candidates")
        if not isinstance(raw_candidates, list):
            continue
        for raw_candidate in raw_candidates:
            if isinstance(raw_candidate, Mapping):
                candidates.append(dict(raw_candidate))
    return candidates


def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
    return (
        str(candidate.get("stable_install_hash") or "")
        or json.dumps(dict(candidate), sort_keys=True, default=str)
    )


def _enrich_schema_provider_from_resolver_candidates(
    state: AgentEditState,
    session: Any,
    candidates: list[dict[str, Any]],
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (_candidate_stable_key)  # T-039 late import: host namespace lookup; resolved at call time
    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return
    from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider

    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    enriched = CompositeSchemaProvider(provisional, session.schema_provider)
    session.schema_provider = enriched
    state.schema_provider = enriched


def _legacy_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, TurnOutcome, _stage_audit, build_legacy_agent_edit_v1, derive_apply_eligibility, derive_gates, product_failure_envelope_fields)  # T-039 late import: host namespace lookup; resolved at call time
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
        audit_ref = _stage_audit(state, context, failure=failure)
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
    return response


def _build_batch_repl_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (LOGGER, _build_compatibility_response_fields, _fallback_narrative_message, _legacy_failure_response, _legacy_narrative_debug_status, _narrate_final_message, _narrative_debug_fields, _prepare_narrative_artifact_paths, _record_narrative_artifacts, _response_apply_eligibility, _response_artifacts_with_execution_plan, _session_artifact_response_fields)  # T-039 late import: host namespace lookup; resolved at call time
    response = _legacy_failure_response(state, context, failure=failure)
    compatibility_fields = _build_compatibility_response_fields(state)
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    response["eligibility"] = response["apply_eligibility"]
    apply_eligibility = _response_apply_eligibility(response.get("apply_eligibility"))
    public_outcome_kind = (
        response["outcome"].get("kind")
        if isinstance(response.get("outcome"), Mapping)
        else None
    )
    _prepare_narrative_artifact_paths(state)
    try:
        message = _narrate_final_message(
            state,
            context,
            failure=failure,
            public_outcome=public_outcome_kind,
            apply_eligibility=apply_eligibility,
        )
        narrative_debug = _narrative_debug_fields(state)
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.warning("Narrative synthesis failed for batch failure response: %s", exc)
        message = _fallback_narrative_message(state, failure=failure) or failure.user_facing_message
        narrative_debug = _legacy_narrative_debug_status(
            "narrative_synthesis_error",
            attempted=True,
        )
        narrative_debug["narrative"]["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    response["message"] = message
    _record_narrative_artifacts(state)
    response["artifacts"] = {
        **dict(response.get("artifacts") or {}),
        **_response_artifacts_with_execution_plan(state),
    }
    response["debug"] = {
        **response["debug"],
        "gates": context.gate_snapshot(),
        "hashes": dict(compatibility_fields),
        **narrative_debug,
    }
    return response


def _build_dev_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_build_compatibility_response_fields, _legacy_failure_response, _session_artifact_response_fields)  # T-039 late import: host namespace lookup; resolved at call time
    response = _legacy_failure_response(state, context, failure=failure)
    response.update(_build_compatibility_response_fields(state))
    response.update(_session_artifact_response_fields(state))
    return response


def _session_artifact_response_fields(state: AgentEditState) -> dict[str, Any]:
    response_path = state.turn_dir / "response.json"
    return {
        "session_path": str(state.session_dir),
        "session_path_resolved": str(state.session_dir.resolve()),
        "detail_json_path": str(response_path),
        "detail_json_path_resolved": str(response_path.resolve()),
    }


def _build_batch_repl_response(
    state: AgentEditState,
    context: TurnContext,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (ApplyEligibility, LOGGER, TurnIdentity, TurnOutcome, _BATCH_EXIT_BUDGET, _BATCH_EXIT_DONE, _BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_NOOP, _BATCH_EXIT_PURE_CLARIFY, _build_candidate_payload, _build_compatibility_response_fields, _build_precedent_semantic_check_entries, _canonical_agent_edit_route, _change_details_payload, _execution_plan_debug_fields, _execution_plan_response_fields, _execution_plan_task_satisfaction_entries, _fallback_narrative_message, _json_safe, _legacy_narrative_debug_status, _narrate_final_message, _narrative_debug_fields, _net_field_changes, _plan_validation_allows_candidate, _prepare_narrative_artifact_paths, _record_narrative_artifacts, _record_post_edit_reorganisation_advisory, _resolver_candidate_is_authoring_capability, _resolver_candidates_from_batch_turns, _response_artifacts_with_execution_plan, _response_contract_candidate_present, _route_blocks_apply, _route_change_focus_label, _sanitize_pure_clarify_response, _session_artifact_response_fields, _stage_snapshot_payloads, _strip_clarify_forbidden_response_fields, _sync_narrated_clarify_outcome, _v2_candidate_mutation_plan_fields, _validate_delta_evidence_for_apply, build_legacy_agent_edit_v1, derive_apply_eligibility, format_compact_plan_feedback, public_outcome_from_turn_outcome, success_envelope, turn_envelope)  # T-039 late import: host namespace lookup; resolved at call time
    turn_identity = TurnIdentity.from_context(context)
    canonical_route = _canonical_agent_edit_route(state.route)
    route_blocks_apply = _route_blocks_apply(state.route)
    has_candidate = (
        state.batch_exit_mode in {_BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_DONE}
        and _response_contract_candidate_present(state)
    )
    if (
        _canonical_agent_edit_route(state.route) == "revise"
        and (
            state.revision_evidence is None
            or state.revision_evidence.scoped_diff is None
            or state.revision_evidence.candidate_eligible is not True
        )
    ):
        has_candidate = False
    if route_blocks_apply:
        has_candidate = False
    plan_allows_candidate = _plan_validation_allows_candidate(state, context)
    if not plan_allows_candidate:
        has_candidate = False
    # ── Delta evidence validation (fail-closed for applyable turns) ─────────
    _had_candidate_before_delta = has_candidate
    delta_evidence_valid, delta_evidence_diagnostics, delta_evidence_envelope = _validate_delta_evidence_for_apply(
        state,
        has_candidate=has_candidate,
    )
    if has_candidate and not delta_evidence_valid:
        has_candidate = False
    response_apply_eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate",
    )
    # inspect and clarify routes cannot be Apply-eligible.
    if route_blocks_apply:
        response_apply_eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message=f"Apply is not available for {state.route} routes.",
        )
    _record_post_edit_reorganisation_advisory(
        state,
        context,
        has_candidate=has_candidate,
        apply_eligibility=response_apply_eligibility,
    )
    stage_snapshots = _stage_snapshot_payloads(context)
    compatibility_fields = _build_compatibility_response_fields(state)
    candidate_plan_fields = _v2_candidate_mutation_plan_fields(
        compatibility_fields=compatibility_fields,
        delta_ops_envelope=delta_evidence_envelope if has_candidate else None,
    )
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
        **candidate_plan_fields,
    )
    resolver_candidates = _resolver_candidates_from_batch_turns(state)
    # A run that landed an edit AND still flagged unresolved schema-backed
    # external evidence is not a success: the edit cannot satisfy the request
    # with only the partial graph change. Weak registry/code-search leads are
    # not authoring capability and should not force a special product route.
    unresolved_schema_terminal = (
        state.batch_exit_mode in (_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY)
        and any(
            _resolver_candidate_is_authoring_capability(candidate)
            for candidate in resolver_candidates
            if isinstance(candidate, Mapping)
        )
    )
    if unresolved_schema_terminal:
        internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
    elif not plan_allows_candidate and state.execution_plan is not None:
        internal_outcome = TurnOutcome.noop(
            reason=format_compact_plan_feedback(state.execution_plan, state.plan_evaluation)
        )
    elif route_blocks_apply and canonical_route != "clarify":
        internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY:
        internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY:
        question = state.user_message or None
        internal_outcome = TurnOutcome.edit_and_clarify(
            changes=_net_field_changes(state.batch_field_changes),
            question=question,
        )
    elif state.batch_exit_mode == _BATCH_EXIT_DONE:
        internal_outcome = TurnOutcome.edit(changes=_net_field_changes(state.batch_field_changes))
    elif state.batch_exit_mode == _BATCH_EXIT_BUDGET:
        internal_outcome = TurnOutcome.budget(reason=state.batch_final_summary or None)
    else:
        internal_outcome = TurnOutcome.noop(
            reason=state.batch_done_summary or state.user_message or None
        )
    public_outcome = public_outcome_from_turn_outcome(
        internal_outcome,
        response={"candidate": candidate_payload},
    )
    change_details = _change_details_payload(state, context)
    _prepare_narrative_artifact_paths(state)
    try:
        message = _narrate_final_message(
            state,
            context,
            outcome=internal_outcome,
            public_outcome=public_outcome.get("kind") if isinstance(public_outcome, Mapping) else None,
            apply_eligibility=response_apply_eligibility,
        )
        narrative_debug = _narrative_debug_fields(state)
    except Exception as exc:
        LOGGER.warning("Narrative synthesis failed for batch_repl response: %s", exc)
        message = _fallback_narrative_message(
            state,
            outcome=internal_outcome,
            fallback_reason="narrative_synthesis_error",
        )
        narrative_debug = _legacy_narrative_debug_status(
            "narrative_synthesis_error",
            attempted=True,
        )
        narrative_debug["narrative"]["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    _record_narrative_artifacts(state)
    internal_outcome, public_outcome = _sync_narrated_clarify_outcome(
        message,
        internal_outcome=internal_outcome,
        public_outcome=public_outcome,
    )
    gate_snapshot = context.gate_snapshot()
    response = success_envelope(
        context,
        message=message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=_response_artifacts_with_execution_plan(state),
        apply_eligibility=response_apply_eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed if has_candidate else False,
        queue_allowed=context.queue_allowed if has_candidate else False,
    )
    response.update(
        turn_envelope(
            message=message,
            outcome=public_outcome,
            candidate=candidate_payload,
            eligibility=response_apply_eligibility,
            audit_ref=None,
            debug={
                "gates": gate_snapshot,
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
                "delta_evidence": delta_evidence_diagnostics,
                **narrative_debug,
                **_execution_plan_debug_fields(state),
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    response["change_details"] = change_details
    response.update(compatibility_fields)
    response.update(_execution_plan_response_fields(state))
    response.update(_session_artifact_response_fields(state))
    if canonical_route:
        response["route"] = canonical_route
    if canonical_route == "research":
        response["graph_unchanged"] = True
        response["no_candidate_reason"] = "route_not_applyable"
    if _had_candidate_before_delta and not delta_evidence_valid:
        response["no_candidate_reason"] = "delta_evidence_invalid"
        response["delta_evidence_diagnostic"] = delta_evidence_diagnostics.get(
            "delta_evidence_code"
        )
    if state.batch_exit_mode in {_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY} and not unresolved_schema_terminal:
        response["clarification_required"] = True
        response["graph_unchanged"] = state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
    elif unresolved_schema_terminal:
        response["clarification_required"] = True
        response["graph_unchanged"] = True
        response["no_candidate_reason"] = "route_not_applyable"
    elif state.batch_exit_mode == _BATCH_EXIT_NOOP:
        response["graph_unchanged"] = True
        if state.batch_done_summary:
            response["done_summary"] = state.batch_done_summary
    elif state.batch_done_summary:
        response["done_summary"] = state.batch_done_summary
    if state.post_edit_reorganisation_advisory is not None:
        response["layout_reorganisation"] = _json_safe(
            dict(state.post_edit_reorganisation_advisory)
        )
    response["batch_turns"] = _json_safe(state.batch_turns)
    # ── Cumulative V2 delta envelope from landed batch_repl operations ──────
    # Use the envelope validated by _validate_delta_evidence_for_apply rather
    # than rebuilding it here.  For applyable turns with a candidate, the
    # validated envelope includes any synthesized empty V2 envelope so that
    # identity/no-op apply carries explicit evidence.  When delta evidence
    # validation failed (has_candidate cleared), the envelope is None.
    cumulative_delta_envelope = delta_evidence_envelope
    if cumulative_delta_envelope is not None:
        response["agent_edit_protocol"] = "v2_delta"
        response["delta_ops_envelope"] = cumulative_delta_envelope
        # delta_ops is a read-only derived compatibility view from the canonical envelope.
        response["delta_ops"] = list(cumulative_delta_envelope["ops"])
    # adapt carries semantic checks as advisory/not_evaluated.
    if _canonical_agent_edit_route(state.route) == "adapt":
        semantic_entries = _build_precedent_semantic_check_entries(state)
        if semantic_entries:
            response.setdefault("task_satisfaction", []).extend(semantic_entries)
    plan_satisfaction_entries = _execution_plan_task_satisfaction_entries(state)
    if plan_satisfaction_entries:
        response.setdefault("task_satisfaction", []).extend(plan_satisfaction_entries)
    # revise reports change focus.
    change_focus = _route_change_focus_label(state.route)
    if change_focus:
        response["change_focus"] = change_focus
    built_response = build_legacy_agent_edit_v1(
        {
            **response,
            "canvas_apply_allowed": context.canvas_apply_allowed if has_candidate else False,
            "queue_allowed": context.queue_allowed if has_candidate else False,
        }
    )
    if unresolved_schema_terminal:
        return _strip_clarify_forbidden_response_fields(built_response)
    return _sanitize_pure_clarify_response(built_response)


def _build_dev_success_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    contract: str,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (ApplyEligibility, LOGGER, TurnIdentity, TurnOutcome, _build_candidate_payload, _build_compatibility_response_fields, _build_precedent_semantic_check_entries, _canonical_agent_edit_route, _canonical_delta_ops_envelope_payload, _execution_plan_debug_fields, _execution_plan_response_fields, _execution_plan_task_satisfaction_entries, _has_enough_grounded_facts_for_dev_narrative, _json_safe, _legacy_narrative_debug_status, _narrate_final_message, _narrative_debug_fields, _plan_validation_allows_candidate, _prepare_narrative_artifact_paths, _record_narrative_artifacts, _record_post_edit_reorganisation_advisory, _response_artifacts_with_execution_plan, _route_blocks_apply, _route_change_focus_label, _sanitize_pure_clarify_response, _session_artifact_response_fields, _stage_snapshot_payloads, _sync_narrated_clarify_outcome, _v2_candidate_mutation_plan_fields, build_legacy_agent_edit_v1, derive_apply_eligibility, format_compact_plan_feedback, public_outcome_from_turn_outcome, success_envelope, turn_envelope)  # T-039 late import: host namespace lookup; resolved at call time
    turn_identity = TurnIdentity.from_context(context)
    plan_allows_candidate = _plan_validation_allows_candidate(state, context)
    eligibility = derive_apply_eligibility(
        context,
        has_candidate=plan_allows_candidate,
        candidate_state="candidate",
    )
    # inspect and clarify routes cannot be Apply-eligible.
    if _route_blocks_apply(state.route):
        eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message=f"Apply is not available for {state.route} routes.",
        )
    # No-candidate routes (inspect, clarify) must not produce a
    # candidate outcome or candidate payload even in dev/delta paths.
    if _route_blocks_apply(state.route):
        has_candidate = False
        if _canonical_agent_edit_route(state.route) == "clarify":
            internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
        else:
            internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    elif not plan_allows_candidate and state.execution_plan is not None:
        has_candidate = False
        internal_outcome = TurnOutcome.noop(
            reason=format_compact_plan_feedback(state.execution_plan, state.plan_evaluation)
        )
    else:
        has_candidate = True
        internal_outcome = TurnOutcome.edit()
    public_outcome = public_outcome_from_turn_outcome(
        internal_outcome,
        response=None,
    )
    _record_post_edit_reorganisation_advisory(
        state,
        context,
        has_candidate=has_candidate,
        apply_eligibility=eligibility,
    )
    stage_snapshots = _stage_snapshot_payloads(context)
    compatibility_fields = _build_compatibility_response_fields(state)
    delta_envelope = (
        _canonical_delta_ops_envelope_payload(state.delta_ops)
        if contract == "delta" and has_candidate
        else None
    )
    candidate_plan_fields = _v2_candidate_mutation_plan_fields(
        compatibility_fields=compatibility_fields,
        delta_ops_envelope=delta_envelope,
    )
    public_outcome_kind = public_outcome.get("kind") if isinstance(public_outcome, Mapping) else None
    if _has_enough_grounded_facts_for_dev_narrative(state):
        _prepare_narrative_artifact_paths(state)
        try:
            message = _narrate_final_message(
                state,
                context,
                outcome=internal_outcome,
                public_outcome=public_outcome_kind,
                apply_eligibility=eligibility,
            )
            narrative_debug = _narrative_debug_fields(state)
        except Exception as exc:  # pragma: no cover - defensive fallback
            LOGGER.warning("Narrative synthesis failed for dev success response: %s", exc)
            message = state.user_message
            narrative_debug = _legacy_narrative_debug_status(
                "narrative_synthesis_error",
                attempted=True,
            )
            narrative_debug["narrative"]["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
    else:
        message = state.user_message
        narrative_debug = _legacy_narrative_debug_status("insufficient_grounded_facts")
    _record_narrative_artifacts(state)
    internal_outcome, public_outcome = _sync_narrated_clarify_outcome(
        message,
        internal_outcome=internal_outcome,
        public_outcome=public_outcome,
    )
    response = success_envelope(
        context,
        message=message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=_response_artifacts_with_execution_plan(state),
        apply_eligibility=eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed if plan_allows_candidate else False,
        queue_allowed=context.queue_allowed if plan_allows_candidate else False,
    )
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
        **candidate_plan_fields,
    )
    public_outcome = public_outcome_from_turn_outcome(
        internal_outcome,
        response={"candidate": candidate_payload} if has_candidate else None,
    )
    response.update(
        turn_envelope(
            message=message,
            outcome=public_outcome,
            candidate=candidate_payload,
            eligibility=eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "turn_identity": turn_identity.to_dict(),
                "stage_snapshots": stage_snapshots,
                "contract": contract,
                **narrative_debug,
                **_execution_plan_debug_fields(state),
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    response.update(_execution_plan_response_fields(state))
    if state.post_edit_reorganisation_advisory is not None:
        response["layout_reorganisation"] = _json_safe(
            dict(state.post_edit_reorganisation_advisory)
        )
    if delta_envelope is not None:
        response["agent_edit_protocol"] = "v2_delta"
        response["delta_ops_envelope"] = delta_envelope
        response["delta_ops"] = list(delta_envelope["ops"])
    # adapt carries semantic checks as advisory/not_evaluated.
    if _canonical_agent_edit_route(state.route) == "adapt":
        semantic_entries = _build_precedent_semantic_check_entries(state)
        if semantic_entries:
            response.setdefault("task_satisfaction", []).extend(semantic_entries)
    plan_satisfaction_entries = _execution_plan_task_satisfaction_entries(state)
    if plan_satisfaction_entries:
        response.setdefault("task_satisfaction", []).extend(plan_satisfaction_entries)
    # revise reports change focus.
    change_focus = _route_change_focus_label(state.route)
    if change_focus:
        response["change_focus"] = change_focus
    return _sanitize_pure_clarify_response(
        build_legacy_agent_edit_v1(
            {
                **response,
                "canvas_apply_allowed": context.canvas_apply_allowed if has_candidate else False,
                "queue_allowed": context.queue_allowed if has_candidate else False,
            }
        )
    )


__all__ = (
    "LOGGER",
    "_CLARIFY_FORBIDDEN_RESPONSE_KEYS",
    "_build_batch_repl_failure_response",
    "_build_batch_repl_response",
    "_build_candidate_payload",
    "_build_compatibility_response_fields",
    "_build_cumulative_batch_repl_delta_envelope",
    "_build_dev_failure_response",
    "_build_dev_success_response",
    "_candidate_full_ui_payload_changed",
    "_candidate_stable_key",
    "_canonical_delta_ops_envelope_payload",
    "_clarification_payload",
    "_enrich_schema_provider_from_resolver_candidates",
    "_execution_plan_artifact_refs",
    "_execution_plan_debug_fields",
    "_execution_plan_response_fields",
    "_execution_plan_task_satisfaction_entries",
    "_failure_response",
    "_format_clarify_markdown_message",
    "_has_enough_grounded_facts_for_dev_narrative",
    "_layout_only_reorganise_evidence_changed",
    "_legacy_failure_response",
    "_legacy_narrative_debug_status",
    "_narrative_artifact_refs",
    "_narrative_debug_fields",
    "_plan_validation_allows_candidate",
    "_post_edit_reorganisation_public_advisory",
    "_prepare_narrative_artifact_paths",
    "_product_failure_response",
    "_record_narrative_artifacts",
    "_record_post_edit_reorganisation_advisory",
    "_resolver_candidates_from_batch_result",
    "_resolver_candidates_from_batch_turns",
    "_response_apply_eligibility",
    "_response_artifacts_with_execution_plan",
    "_response_contract_candidate_present",
    "_sanitize_pure_clarify_response",
    "_session_artifact_response_fields",
    "_stage_snapshot_payloads",
    "_strip_clarify_forbidden_response_fields",
    "_sync_narrated_clarify_outcome",
    "_v2_candidate_mutation_plan_fields",
    "_validate_delta_evidence_for_apply",
    "_validated_agent_edit_response",
    "_workflow_schema_candidates_from_batch_result",
)
