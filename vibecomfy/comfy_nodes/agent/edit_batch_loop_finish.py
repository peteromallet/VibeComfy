# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Batch REPL clarify/done/discovery/budget exits.

SOURCE = r'''

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
            _emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={
                    "mode": "clarification_required",
                    "graph_unchanged": state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY,
                },
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                }
                if state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY
                else {},
            )

        current_render = next_render
        last_diff = diff_text
        last_report = report_text
        done_requested = any(
            item.ok and str(item.op_kind or "") == "done"
            for item in batch_result.statements
        )
        turn_failed_edit = any(
            (not item.ok)
            and str(item.op_kind or "") not in {"query", "done", "clarify"}
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
        # Don't honor a premature done(): feed guidance back and let the model
        # self-correct. Two distinct cases, each separately bounded so a genuine
        # no-change request still commits and we can't loop forever:
        #  (1) NOTHING ever landed — committing would be an empty no-op. Causes:
        #      a wrong node signature, or a read-only search() then done().
        #  (2) Something landed but THIS (final) batch errored — some intended
        #      statements failed to land (e.g. a wrong output-slot name), so the
        #      edit is half-applied and likely broken (floating node / dangling
        #      wire). The diagnostics name the fix; force one more turn.
        refuse_done = False
        hint = ""
        if (
            done_requested
            and consecutive_errors < max_consecutive_errors
            and not research_only_route
        ):
            if total_landed == 0 and (turn_has_errors or failed_edit_turns > 0):
                done_noop_nudges += 1
                refuse_done = True
                if turn_has_errors:
                    hint = (
                        "your edit statement(s) did NOT land (see the diagnostics above)"
                        " and nothing has been applied. Fix the failed statement — correct"
                        " the wrong field name or supply the required input;"
                        " call search(focus_types=[\"ClassName\"]) for the exact signature —"
                        " then call done()."
                    )
                elif failed_edit_turns > 0:
                    hint = (
                        "earlier edit statement(s) failed and no edit has landed. A search()"
                        " is read-only and does NOT fix the failed edit. Use the diagnostics"
                        " above and construct a valid node/wire, or clarify the limitation;"
                        " do not report this as already done."
                    )
                else:
                    hint = (
                        "you called done() without making any edit, so nothing was applied."
                        " A search() is read-only and does NOT change the graph. Now CONSTRUCT"
                        " and wire the node(s) the request needs (e.g. `up = NodeType(...)` then"
                        " `consumer.input = up.OUTPUT`), then call done(). If the graph"
                        " genuinely needs no change, call done() again to confirm."
                    )
            elif unresolved_failed_edit and turn_is_read_only:
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "an earlier edit batch failed after partially mutating the graph."
                    " A search() is read-only and does NOT repair that incomplete"
                    " candidate. Use the search result and diagnostics above to"
                    " construct and wire the missing node(s), then call done()."
                )
            elif (
                (turn_number + 1) < max_batches
                and total_landed == 0
                and done_noop_nudges < 2
            ):
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "you called done() without making any edit, so nothing was applied."
                    " A search() is read-only and does NOT change the graph. Now CONSTRUCT"
                    " and wire the node(s) the request needs (e.g. `up = NodeType(...)` then"
                    " `consumer.input = up.OUTPUT`), then call done(). If the graph"
                    " genuinely needs no change, call done() again to confirm."
                )
            elif turn_has_errors and done_error_nudges < 2:
                done_error_nudges += 1
                refuse_done = True
                hint = (
                    "some of your edit statements did NOT land (see the diagnostics above),"
                    " so the edit is INCOMPLETE — nodes the request needs may be left"
                    " unconnected or a consumer's input left dangling. Do NOT stop here."
                    " Fix ONLY the failed statement(s): use the exact output-slot/field names"
                    " the diagnostics list (e.g. an output is `.UPSCALE_MODEL`, not `.model`),"
                    " drop any kwarg the node does not declare, re-wire the consumer, then"
                    " call done()."
                )
        if (
            done_requested
            and not refuse_done
            and not research_only_route
            and getattr(state, "execution_plan", None) is not None
        ):
            candidate_graph = (
                state.ui_payload
                if isinstance(state.ui_payload, Mapping)
                else session.working_ui
            )
            update = evaluate_execution_plan_for_state(
                state,
                candidate_graph,
                candidate_graph_hash=structural_graph_hash(candidate_graph),
            )
            execution_plan_status = dict(update.compact_status or {})
            if execution_plan_status:
                turn_record["execution_plan_status"] = execution_plan_status
                if response_log and isinstance(response_log[-1], dict):
                    batch_response_record = response_log[-1].get("batch_result")
                    if isinstance(batch_response_record, dict):
                        batch_response_record["execution_plan_status"] = execution_plan_status
                    write_json_artifact(state.model_response_path, {"turns": response_log})
            evaluation = getattr(state, "plan_evaluation", None)
            if (
                getattr(evaluation, "ok", True) is False
                and getattr(evaluation, "blocking", False) is True
            ):
                refuse_done = True
                hint = _execution_plan_done_refusal_hint(state)
        if refuse_done:
            last_report = last_report + "\n\nNOTE: done() was NOT accepted — " + hint
            continue
        if done_requested:
            done_result = session.done()
            state.batch_turn_count = turn_number + 1
            state.batch_budget_state = {
                "max_batches": max_batches,
                "max_consecutive_errors": max_consecutive_errors,
                "remaining_batches": max_batches - state.batch_turn_count,
                "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                "consecutive_errors": consecutive_errors,
            }
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
                    artifacts=(
                        _artifact(state.before_py_path),
                        _artifact(state.after_py_path),
                        _artifact(state.model_request_path),
                        _artifact(state.model_response_path),
                        _artifact(state.candidate_ui_path),
                        _artifact(state.messages_path),
                    ),
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
            state.report = {
                "done_summary": done_result.summary,
                "queue_blockers": [],
            }
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
                _canonical_agent_edit_route(state.route) == "revise"
                and state.revision_evidence is not None
                and state.revision_evidence.candidate_eligible is not True
                and retryable_revise_blockers
                and (turn_number + 1) < max_batches
                and done_candidate_rejection_nudges < 2
            ):
                done_candidate_rejection_nudges += 1
                last_report = (
                    last_report
                    + "\n\nNOTE: done() was NOT accepted — "
                    + _revision_candidate_retry_hint(state)
                )
                continue
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "revision_evidence": str(state.revision_evidence_path),
                "messages": str(state.messages_path),
            }
            _emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="done",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.before_py_path),
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={"mode": "done", "done_summary": done_result.summary},
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                },
            )
        if (
            total_landed == 0
            and _read_only_discovery_turn_count(state) >= 6
            and not _batch_candidate_graph_changed(state)
        ):
            direct_tweak_feedback = _direct_existing_parameter_tweak_feedback(state)
            if direct_tweak_feedback and turn_number + 1 < max_batches:
                last_report = direct_tweak_feedback
                last_landed_count = 0
                _emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="in_progress",
                )
                continue
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
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={
                    "mode": "discovery_stop",
                    "graph_unchanged": True,
                    "turn_count": state.batch_turn_count,
                },
            )
        _emit_agent_edit_turn_event(
            state,
            _context,
            turn_record,
            client_id=client_id,
            status="in_progress",
        )
        if consecutive_errors >= max_consecutive_errors:
            break

    failure_kind = _batch_budget_failure_kind(state.batch_turns)
    artifixer_report = _batch_budget_artifixer_report(state, failure_kind)
    state.batch_exit_mode = _BATCH_EXIT_BUDGET
    state.batch_final_summary = (
        f"Stopped after {state.batch_turn_count} turn(s); "
        f"{state.batch_budget_state.get('remaining_batches', 0)} turn(s) remaining."
    )
    if state.batch_turns:
        _emit_agent_edit_turn_event(
            state,
            _context,
            state.batch_turns[-1],
            client_id=client_id,
            status="budget_exhausted",
        )
    return StageResult(
        stage="agent_batch",
        ok=False,
        blocking=True,
        duration_ms=_duration_ms(start),
        artifacts=(
            _artifact(state.before_py_path),
            _artifact(state.after_py_path),
            _artifact(state.model_request_path),
            _artifact(state.model_response_path),
            _artifact(state.candidate_ui_path),
            _artifact(state.messages_path),
        ),
        issues=(
            {
                "code": "batch_budget_exhausted",
                "severity": "error",
                "failure_kind": failure_kind.value,
                "message": state.batch_final_summary,
                "detail": {
                    "turn_count": state.batch_turn_count,
                    "budget_state": dict(state.batch_budget_state),
                    "budget_classification": failure_kind.value,
                    "artifixer": artifixer_report,
                },
            },
        ),
        value={
            "failure_kind": failure_kind.value,
            "turn_count": state.batch_turn_count,
            "budget_state": dict(state.batch_budget_state),
            "budget_classification": failure_kind.value,
            "diagnostics": (
                {
                    "code": "artifixer_not_attempted",
                    "severity": "info",
                    "message": "Artifact repair was not attempted for this terminal batch stop.",
                    "detail": artifixer_report,
                },
            ),
        },
    )


'''
