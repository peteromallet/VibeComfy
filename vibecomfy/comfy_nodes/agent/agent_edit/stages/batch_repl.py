from __future__ import annotations

import json
import time
from typing import Any, Mapping

from ...audit import write_json_artifact
from ...contracts import StageResult, TurnContext, repair_field_changes
from ...provider import MalformedModelJSON, MissingRequiredField
from ..budget import _field_changes_payload, _json_safe
from ..clarify import (
    _BATCH_EXIT_BUDGET,
    _BATCH_EXIT_DONE,
    _BATCH_EXIT_EDIT_CLARIFY,
    _BATCH_EXIT_NOOP,
    _BATCH_EXIT_PURE_CLARIFY,
    _build_premature_clarify_turn_record,
    _compute_premature_clarify_feedback,
    split_terminal_clarify,
)
from ..client import DeepSeekClient
from ..fields import _noop_field_changes, _real_field_changes
from ..labels import (
    _format_available_node_names,
    _format_node_variable_index,
    _present_class_types,
)
from ..messages import (
    _batch_candidate_graph_changed,
    _batch_research_memory_summary,
    _discovery_stop_message,
    _format_batch_report,
    _format_batch_report_json,
    _format_research_brief_for_prompt,
    _lint_issue_to_dict,
    _render_batch_diff,
    _revision_candidate_retry_hint,
)
from ..responses import (
    _enrich_schema_provider_from_resolver_candidates,
    _resolver_candidates_from_batch_result,
    _workflow_schema_candidates_from_batch_result,
)
from ..runtime_schema import (
    _effective_implementation_task,
    _focus_types_from_research_brief,
    _seed_focus_types_for_authoring,
)
from ..state import AgentEditState
from ..websocket import _emit_agent_edit_turn_event
from .batch_repl_support import (
    _append_jsonl,
    _batch_artifact_map,
    _build_adapt_scoped_research_context,
    _build_prefetch_research_summary,
    _budget_exhausted_result,
    _done_result,
    _done_validation_failure,
    _duration_ms,
    _invoke_batch_turn,
    _lint_batch_result,
    _pure_clarify_result,
    _record_batch_response,
    _resolve_edit_attr,
    _update_batch_budget_state,
    _write_model_response,
)
from .revision import (
    _finalize_revision_evidence_with_candidate,
    _revision_evidence_prompt_json,
)


def _stage_agent_batch_repl_impl(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from vibecomfy.porting.edit import session as edit_session_module

    build_batch_messages = _resolve_edit_attr("build_batch_messages")
    ensure_sentence_message = _resolve_edit_attr("ensure_sentence_message")
    run_agent_turn_batch = _resolve_edit_attr("run_agent_turn_batch")
    canonical_route_fn = _resolve_edit_attr("_canonical_agent_edit_route")
    batch_repl_enabled = _resolve_edit_attr("_agent_edit_batch_repl_enabled")
    read_only_discovery_turn_count = _resolve_edit_attr("_read_only_discovery_turn_count")
    is_code_node_intent = _resolve_edit_attr("_is_code_node_intent")
    build_graph_report = _resolve_edit_attr("_build_graph_report")
    build_precedent_adaptation_prompt = _resolve_edit_attr("_build_precedent_adaptation_prompt")

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    session = edit_session_module.EditSession(prepared_ui, schema_provider=state.schema_provider)
    state.batch_session = session
    initial_render = session.render()
    focus_types = set(_present_class_types(session))
    effective_task = _effective_implementation_task(state)
    focus_types.update(_seed_focus_types_for_authoring(state))
    focus_types.update(_focus_types_from_research_brief(state.executor_research_brief))
    if is_code_node_intent(effective_task):
        focus_types.add("vibecomfy.exec")
    signature_catalog = session.search(focus_types=sorted(focus_types), formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

    classification = (
        state.request_payload.get("executor_classification")
        if isinstance(state.request_payload, dict)
        else None
    )
    intent = classification.get("intent") if isinstance(classification, dict) else ""
    prefetch_explain = not intent and _resolve_edit_attr("_is_graph_explain_intent")(effective_task)
    prefetch_research_summary = _build_prefetch_research_summary(state, effective_task)
    research_brief_prompt = _format_research_brief_for_prompt(state.executor_research_brief)
    prefetch_graph_report = build_graph_report(state.graph) if prefetch_explain else ""

    precedent_adaptation_prompt = ""
    adapt_scoped_research_context = ""
    canonical_route = canonical_route_fn(state.route or route)
    research_only_route = canonical_route == "research"
    if canonical_route == "adapt":
        if state.executor_adaptation_plan:
            precedent_adaptation_prompt = build_precedent_adaptation_prompt(
                state.executor_adaptation_plan,
                state.executor_precedent_slices,
            )
        adapt_scoped_research_context = _build_adapt_scoped_research_context(state)

    max_batches = max(1, int(state.batch_max_turns or 1))
    max_consecutive_errors = max(1, int(state.batch_max_consecutive_errors or 1))
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches,
        "remaining_consecutive_errors": max_consecutive_errors,
    }
    state.artifacts = _batch_artifact_map(state)

    current_render = initial_render
    last_diff = ""
    last_report = ""
    last_landed_count: int | None = None
    previous_model_message = ""
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    done_candidate_rejection_nudges = 0
    failed_edit_turns = 0
    last_failed_edit_turn = -1
    last_successful_edit_turn_after_failure = -1
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = _format_node_variable_index(session)
        turn_research_summary = prefetch_research_summary if turn_number == 0 else ""
        research_memory = _batch_research_memory_summary(state)
        if research_memory:
            turn_research_summary = (
                f"{turn_research_summary}\n\nPrior research/query memory:\n{research_memory}"
            ).strip()
        messages = build_batch_messages(
            task=effective_task,
            turn_number=turn_number,
            python_source=(initial_render if turn_number == 0 else current_render)
            if include_full_render
            else "",
            node_variable_index=node_variable_index,
            previous_model_message=previous_model_message,
            signature_catalog=state.batch_signature_catalog if turn_number == 0 else "",
            available_node_names=available_node_names if turn_number == 0 else "",
            diff=last_diff,
            report=last_report,
            budget_remaining=budget_remaining,
            max_batches=max_batches,
            conversation_messages=conversation_messages if turn_number == 0 else None,
            research_only=research_only_route,
            research_brief=research_brief_prompt if turn_number == 0 else "",
            research_summary=turn_research_summary,
            graph_report=prefetch_graph_report if turn_number == 0 else "",
            precedent_adaptation_plan=(
                (precedent_adaptation_prompt + "\n\n" + adapt_scoped_research_context).strip()
                if turn_number == 0
                else ""
            ),
            revision_evidence_json=_revision_evidence_prompt_json(state)
            if turn_number == 0
            else "",
        )
        request_log.append(
            {
                "turn_number": turn_number,
                "messages": messages,
                "budget_remaining": budget_remaining,
                "node_variable_index": node_variable_index,
                "included_full_render": include_full_render,
            }
        )
        write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        try:
            turn_result = _invoke_batch_turn(
                state=state,
                turn_number=turn_number,
                messages=messages,
                deepseek_client=deepseek_client,
                route=route,
                model=model,
                response_log=response_log,
                max_consecutive_errors=max_consecutive_errors,
                consecutive_errors=consecutive_errors,
            )
        except (MalformedModelJSON, MissingRequiredField) as exc:
            if consecutive_errors + 1 >= max_consecutive_errors:
                raise
            last_report = (
                f"Agent response format error: {exc} Respond with one user-facing sentence "
                "followed by exactly one ```batch fenced block."
            )
            previous_model_message = ""
            last_landed_count = 0
            consecutive_errors += 1
            continue

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        previous_model_message = turn_result.message
        clarify_split = split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "status": "received",
            }
        )
        _write_model_response(state, response_log)

        if clarify_message is not None and not editable_batch.strip():
            clarify_feedback = _compute_premature_clarify_feedback(state, clarify_message)
            if clarify_feedback:
                consecutive_errors += 1
                turn_record = _build_premature_clarify_turn_record(
                    turn_number=turn_number,
                    batch=turn_result.batch,
                    message=turn_result.message,
                    route=turn_result.route,
                    model=turn_result.model,
                    provider_metadata=_json_safe(dict(turn_result.audit_metadata or {})),
                    clarify_feedback=clarify_feedback,
                )
                state.batch_turns.append(turn_record)
                state.batch_feedback = clarify_feedback
                state.batch_turn_count = turn_number + 1
                _update_batch_budget_state(
                    state,
                    max_batches=max_batches,
                    max_consecutive_errors=max_consecutive_errors,
                    turn_count=state.batch_turn_count,
                    consecutive_errors=consecutive_errors,
                )
                response_log[-1] = {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "rejected_clarification": turn_record,
                }
                _write_model_response(state, response_log)
                _append_jsonl(
                    state.messages_path,
                    {
                        "turn_number": turn_number,
                        "task": state.task,
                        "message": turn_result.message,
                        "batch": turn_result.batch,
                        "report": clarify_feedback,
                    },
                )
                terminal_rejected_clarify = (
                    _batch_candidate_graph_changed(state)
                    or (
                        last_failed_edit_turn >= 0
                        and last_successful_edit_turn_after_failure < last_failed_edit_turn
                    )
                    or consecutive_errors >= max_consecutive_errors
                    or (turn_number + 1) >= max_batches
                )
                if terminal_rejected_clarify:
                    return _budget_exhausted_result(
                        state,
                        start,
                        turn_record=turn_record,
                        context=context,
                        client_id=client_id,
                    )
                last_report = clarify_feedback
                last_landed_count = 0
                _emit_agent_edit_turn_event(
                    state,
                    context,
                    turn_record,
                    client_id=client_id,
                    status="in_progress",
                )
                continue

            state.batch_turn_count = turn_number + 1
            state.batch_exit_mode = (
                _BATCH_EXIT_EDIT_CLARIFY
                if _batch_candidate_graph_changed(state)
                else _BATCH_EXIT_PURE_CLARIFY
            )
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            _update_batch_budget_state(
                state,
                max_batches=max_batches,
                max_consecutive_errors=max_consecutive_errors,
                turn_count=state.batch_turn_count,
                consecutive_errors=consecutive_errors,
            )
            state.user_message = clarify_message
            state.python_after = current_render
            state.after_py_path.write_text(current_render, encoding="utf-8")
            state.ui_payload = json.loads(json.dumps(session.working_ui))
            write_json_artifact(state.candidate_ui_path, state.ui_payload)
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
            }
            turn_record = {
                "turn_number": turn_number,
                "batch": turn_result.batch,
                "message": turn_result.message,
                "route": turn_result.route,
                "model": turn_result.model,
                "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
                "clarification_required": True,
                "clarification_message": clarify_message,
                "field_changes": [],
            }
            state.batch_turns.append(turn_record)
            response_log[-1] = {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "clarification": turn_record,
            }
            _write_model_response(state, response_log)
            _append_jsonl(
                state.messages_path,
                {
                    "turn_number": turn_number,
                    "task": state.task,
                    "message": turn_result.message,
                    "batch": turn_result.batch,
                    "clarification_required": clarify_message,
                },
            )
            state.artifacts = _batch_artifact_map(state)
            return _pure_clarify_result(
                state,
                start,
                turn_record=turn_record,
                context=context,
                client_id=client_id,
            )

        batch_result = session.apply_batch(editable_batch)
        _enrich_schema_provider_from_resolver_candidates(
            state,
            session,
            [
                *_workflow_schema_candidates_from_batch_result(batch_result),
                *_resolver_candidates_from_batch_result(batch_result),
            ],
        )
        next_render = session.render()
        state.python_after = next_render
        state.after_py_path.write_text(next_render, encoding="utf-8")
        state.ui_payload = json.loads(json.dumps(session.working_ui))
        write_json_artifact(state.candidate_ui_path, state.ui_payload)

        lint_dropped_op_ids, lint_dropped_count, lint_diag_dicts = _lint_batch_result(
            state=state,
            batch_result=batch_result,
            batch_repl_enabled=batch_repl_enabled(),
        )

        raw_landed = len(batch_result.landed_ops)
        effective_landed = raw_landed - lint_dropped_count
        total_landed += effective_landed
        last_landed_count = effective_landed
        turn_has_errors = (
            (not batch_result.ok)
            or bool(batch_result.diagnostics)
            or any(d.get("severity") == "error" for d in lint_diag_dicts)
        )
        consecutive_errors = consecutive_errors + 1 if turn_has_errors else 0
        diff_text = _render_batch_diff(current_render, next_render)
        report_text = _format_batch_report(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
            lint_dropped_count=lint_dropped_count,
            lint_diagnostics=lint_diag_dicts,
        )
        report_json = _format_batch_report_json(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
            lint_dropped_count=lint_dropped_count,
            lint_diagnostics=lint_diag_dicts,
        )
        field_changes = repair_field_changes(state.graph, tuple(batch_result.field_changes))
        real_field_changes = _real_field_changes(
            field_changes,
            lint_dropped_op_ids=lint_dropped_op_ids,
        )
        noop_field_changes = _noop_field_changes(
            field_changes,
            lint_dropped_op_ids=lint_dropped_op_ids,
        )
        state.batch_field_changes = state.batch_field_changes + real_field_changes
        state.batch_noop_field_changes = state.batch_noop_field_changes + noop_field_changes
        turn_record = {
            "turn_number": turn_number,
            "batch": turn_result.batch,
            "message": turn_result.message,
            "route": turn_result.route,
            "model": turn_result.model,
            "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
            "batch_ok": batch_result.ok,
            "statement_count": len(batch_result.statements),
            "landed_op_count": effective_landed,
            "raw_landed_op_count": raw_landed,
            "lint_dropped_op_count": lint_dropped_count,
            "diagnostics": report_json["diagnostics"],
            "statements": report_json["statements"],
            "field_changes": _field_changes_payload(real_field_changes),
            "diff": diff_text,
            "report": report_text,
        }
        if noop_field_changes:
            turn_record["noop_field_changes"] = _field_changes_payload(noop_field_changes)
        if clarify_message is not None:
            turn_record["clarification_required"] = True
            turn_record["clarification_message"] = clarify_message
        state.batch_turns.append(turn_record)
        state.batch_feedback = report_text
        state.batch_turn_count = turn_number + 1
        _update_batch_budget_state(
            state,
            max_batches=max_batches,
            max_consecutive_errors=max_consecutive_errors,
            turn_count=state.batch_turn_count,
            consecutive_errors=consecutive_errors,
        )
        _record_batch_response(
            state=state,
            turn_number=turn_number,
            turn_result=turn_result,
            report_text=report_text,
            response_log=response_log,
            turn_record=turn_record,
        )

        if clarify_message is not None:
            state.batch_exit_mode = (
                _BATCH_EXIT_EDIT_CLARIFY
                if _batch_candidate_graph_changed(state)
                else _BATCH_EXIT_PURE_CLARIFY
            )
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            state.user_message = clarify_message
            state.report = {
                "clarification_required": True,
                "graph_unchanged": state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY,
                "queue_blockers": [],
            }
            return _pure_clarify_result(
                state,
                start,
                turn_record=turn_record,
                context=context,
                client_id=client_id,
            )

        current_render = next_render
        last_diff = diff_text
        last_report = report_text
        done_requested = any(item.ok and str(item.op_kind or "") == "done" for item in batch_result.statements)
        turn_failed_edit = any(
            (not item.ok) and str(item.op_kind or "") not in {"query", "done", "clarify"}
            for item in batch_result.statements
        )
        if turn_failed_edit:
            failed_edit_turns += 1
            last_failed_edit_turn = turn_number
        elif effective_landed > 0 and last_failed_edit_turn >= 0:
            last_successful_edit_turn_after_failure = turn_number
        unresolved_failed_edit = (
            last_failed_edit_turn >= 0
            and last_successful_edit_turn_after_failure < last_failed_edit_turn
        )
        turn_is_read_only = effective_landed == 0 and all(
            str(item.op_kind or "") in {"query", "done", "clarify"}
            for item in batch_result.statements
        )

        refuse_done = False
        hint = ""
        if done_requested and consecutive_errors < max_consecutive_errors and not research_only_route:
            if total_landed == 0 and (turn_has_errors or failed_edit_turns > 0):
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "your edit statement(s) did NOT land (see the diagnostics above) and "
                    "nothing has been applied. Fix the failed statement -- correct the wrong "
                    "field name or supply the required input; call search(focus_types=[\"ClassName\"]) "
                    "for the exact signature -- then call done()."
                    if turn_has_errors
                    else "earlier edit statement(s) failed and no edit has landed. A search() "
                    "is read-only and does NOT fix the failed edit. Use the diagnostics above "
                    "and construct a valid node/wire, or clarify the limitation; do not report "
                    "this as already done."
                )
            elif unresolved_failed_edit and turn_is_read_only:
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "an earlier edit batch failed after partially mutating the graph. A search() "
                    "is read-only and does NOT repair that incomplete candidate. Use the search "
                    "result and diagnostics above to construct and wire the missing node(s), "
                    "then call done()."
                )
            elif (turn_number + 1) < max_batches and total_landed == 0 and done_noop_nudges < 2:
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "you called done() without making any edit, so nothing was applied. A "
                    "search() is read-only and does NOT change the graph. Now CONSTRUCT and "
                    "wire the node(s) the request needs (e.g. `up = NodeType(...)` then "
                    "`consumer.input = up.OUTPUT`), then call done(). If the graph genuinely "
                    "needs no change, call done() again to confirm."
                )
            elif turn_has_errors and done_error_nudges < 2:
                done_error_nudges += 1
                refuse_done = True
                hint = (
                    "some of your edit statements did NOT land (see the diagnostics above), so "
                    "the edit is INCOMPLETE -- nodes the request needs may be left unconnected "
                    "or a consumer's input left dangling. Do NOT stop here. Fix ONLY the failed "
                    "statement(s): use the exact output-slot/field names the diagnostics list "
                    "(e.g. an output is `.UPSCALE_MODEL`, not `.model`), drop any kwarg the "
                    "node does not declare, re-wire the consumer, then call done()."
                )
        if refuse_done:
            last_report = last_report + "\n\nNOTE: done() was NOT accepted -- " + hint
            continue

        if done_requested:
            done_result = session.done()
            state.batch_turn_count = turn_number + 1
            _update_batch_budget_state(
                state,
                max_batches=max_batches,
                max_consecutive_errors=max_consecutive_errors,
                turn_count=state.batch_turn_count,
                consecutive_errors=consecutive_errors,
            )
            state.batch_exit_mode = (
                _BATCH_EXIT_DONE if _batch_candidate_graph_changed(state) else _BATCH_EXIT_NOOP
            )
            state.batch_done_summary = done_result.summary
            state.batch_final_summary = done_result.summary
            if not done_result.ok:
                return StageResult(
                    stage="agent_batch",
                    ok=False,
                    blocking=True,
                    duration_ms=_duration_ms(start),
                    artifacts=_batch_artifacts(state),
                    issues=tuple(_compact_diag_to_dict(item) for item in done_result.diagnostics),
                    value={
                        "failure_kind": FailureKind.VALIDATION_ERROR.value,
                        "turn_count": state.batch_turn_count,
                        "done_summary": done_result.summary,
                    },
                )
            state.user_message = ensure_sentence_message(
                turn_result.message,
                fallback="I made the requested workflow changes.",
            )
            state.report = {"done_summary": done_result.summary, "queue_blockers": []}
            _finalize_revision_evidence_with_candidate(
                state,
                route=state.route,
                conversation_messages=conversation_messages,
            )
            scoped = (
                state.revision_evidence.scoped_diff
                if state.revision_evidence is not None
                else None
            )
            retryable_revise_blockers = (
                set(getattr(scoped, "eligibility_blockers", ()))
                - {"target_mismatch", "target_scope_violation"}
            )
            if (
                canonical_route_fn(state.route) == "revise"
                and state.revision_evidence is not None
                and state.revision_evidence.candidate_eligible is not True
                and retryable_revise_blockers
                and (turn_number + 1) < max_batches
                and done_candidate_rejection_nudges < 2
            ):
                done_candidate_rejection_nudges += 1
                last_report = (
                    last_report
                    + "\n\nNOTE: done() was NOT accepted -- "
                    + _revision_candidate_retry_hint(state)
                )
                continue
            state.artifacts = _batch_artifact_map(state, include_python=True)
            return _done_result(
                state,
                start,
                turn_record=turn_record,
                context=context,
                client_id=client_id,
                done_summary=done_result.summary,
            )

        if total_landed == 0 and read_only_discovery_turn_count(state) >= 6 and not _batch_candidate_graph_changed(state):
            state.batch_exit_mode = _BATCH_EXIT_PURE_CLARIFY
            state.batch_final_summary = (
                f"Stopped after {state.batch_turn_count} discovery-only batch turn(s)."
            )
            state.user_message = _discovery_stop_message(state)
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
                "discovery_stop": {
                    "turn_count": state.batch_turn_count,
                    "reason": "repeated_read_only_discovery",
                },
            }
            _emit_agent_edit_turn_event(
                state,
                context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=_candidate_artifacts(state),
                value={
                    "mode": "discovery_stop",
                    "graph_unchanged": True,
                    "turn_count": state.batch_turn_count,
                },
            )

        _emit_agent_edit_turn_event(
            state,
            context,
            turn_record,
            client_id=client_id,
            status="in_progress",
        )
        if consecutive_errors >= max_consecutive_errors:
            break

    return _budget_exhausted_result(
        state,
        start,
        turn_record=state.batch_turns[-1] if state.batch_turns else None,
        context=context,
        client_id=client_id,
    )
