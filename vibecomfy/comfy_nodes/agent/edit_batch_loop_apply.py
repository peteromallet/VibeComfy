# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Batch REPL clarify handling, apply/lint pass, and turn-record capture.

SOURCE = r'''
                            "report": clarify_feedback,
                        },
                        sort_keys=True,
                    )
                    + "\n"
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
                    failure_kind = _batch_budget_failure_kind(state.batch_turns)
                    state.batch_exit_mode = _BATCH_EXIT_BUDGET
                    state.batch_final_summary = (
                        f"Stopped after {state.batch_turn_count} turn(s); "
                        f"{state.batch_budget_state.get('remaining_batches', 0)} turn(s) remaining."
                    )
                    _emit_agent_edit_turn_event(
                        state,
                        _context,
                        turn_record,
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
                                },
                            },
                        ),
                        value={
                            "failure_kind": failure_kind.value,
                            "turn_count": state.batch_turn_count,
                            "budget_state": dict(state.batch_budget_state),
                            "budget_classification": failure_kind.value,
                        },
                    )
                last_report = clarify_feedback
                last_landed_count = 0
                _emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="in_progress",
                )
                continue
        if clarify_message is not None and not editable_batch.strip():
            state.batch_turn_count = turn_number + 1
            state.batch_exit_mode = (
                _BATCH_EXIT_EDIT_CLARIFY
                if _batch_candidate_graph_changed(state)
                else _BATCH_EXIT_PURE_CLARIFY
            )
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            state.batch_budget_state = {
                "max_batches": max_batches,
                "max_consecutive_errors": max_consecutive_errors,
                "remaining_batches": max_batches - state.batch_turn_count,
                "remaining_consecutive_errors": max_consecutive_errors,
                "consecutive_errors": consecutive_errors,
            }
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
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(
                    {
                        "turn_number": turn_number,
                        "task": state.task,
                        "message": turn_result.message,
                        "batch": turn_result.batch,
                        "clarification_required": clarify_message,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
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
                value={"mode": "clarification_required", "graph_unchanged": True},
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

        batch_result = session.apply_batch(editable_batch)
        _enrich_schema_provider_from_resolver_candidates(
            state,
            session,
            _resolver_candidates_from_batch_result(batch_result),
        )
        next_render = session.render()
        state.python_after = next_render
        state.after_py_path.write_text(next_render, encoding="utf-8")
        state.ui_payload = json.loads(json.dumps(session.working_ui))
        write_json_artifact(state.candidate_ui_path, state.ui_payload)
        execution_plan_status = _evaluate_execution_plan_after_candidate_update(state)

        # ── lint gate: post-apply no-op detection on landed ops ──────────
        lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None
        lint_dropped_count = 0
        lint_diag_dicts: tuple[dict[str, Any], ...] = ()
        persisted_landed_ops = batch_result.landed_ops
        if (
            _edit_lint_enabled()
            and batch_result.landed_ops
            and _agent_edit_batch_repl_enabled()
        ):
            from vibecomfy.porting.edit.lint import LintIndex, lint_delta
            from vibecomfy.porting.edit.ops import (
                RemoveLinkOp,
                SetModeOp,
                SetNodeFieldOp,
                UpsertLinkOp,
            )

            index = LintIndex.build(state.graph)
            lint_result = lint_delta(
                batch_result.landed_ops,
                index,
                schema_provider=state.schema_provider,
            )

            landed_add_uids = {
                str(item.detail.get("minted_uid"))
                for item in batch_result.statements
                if item.ok
                and str(item.op_kind or "") == "node_call"
                and isinstance(item.detail, Mapping)
                and item.detail.get("minted_uid") is not None
            }

            # Build (uid, field_path) identities for lint-dropped ops.
            _dropped_keys: list[tuple[str, str]] = []
            for norm in lint_result.normalizations:
                if norm.disposition != "dropped_noop":
                    continue
                op = norm.op
                key: tuple[str, str] | None = None
                if isinstance(op, SetNodeFieldOp):
                    key = (op.target.uid, op.target.field_path)
                elif isinstance(op, SetModeOp):
                    key = (op.target.uid, "mode")
                elif isinstance(op, UpsertLinkOp):
                    key = (op.target.uid, op.target.input_field)
                elif isinstance(op, RemoveLinkOp) and op.target is not None:
                    key = (op.target.uid, op.target.input_field)
                if key is not None:
                    _dropped_keys.append(key)
            lint_dropped_op_ids = frozenset(_dropped_keys)
            lint_dropped_count = lint_result.dropped_count

            # Accumulate human-readable lint no-op messages
            _turn_noop_msgs: list[str] = []
            for norm in lint_result.normalizations:
                if norm.disposition == "dropped_noop" and norm.issue is not None:
                    _turn_noop_msgs.append(norm.issue.message)
            state.lint_noop_messages = state.lint_noop_messages + tuple(_turn_noop_msgs)

            def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
                return {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                    "op_index": getattr(issue, "op_index", None),
                    "op_kind": getattr(issue, "op_kind", None),
                    "source": "lint",
                }

            lint_issues = tuple(
                issue
                for issue in lint_result.issues
                if not (
                    issue.code == "unknown_target"
                    and issue.uid in landed_add_uids
                )
            )
            lint_diag_dicts = tuple(
                _lint_issue_to_dict(issue) for issue in lint_issues
            )
            persisted_landed_ops = lint_result.surviving

        raw_landed = len(batch_result.landed_ops)
        effective_landed = raw_landed - lint_dropped_count
        landed_count = effective_landed
        total_landed += effective_landed
        last_landed_count = effective_landed
        if batch_result.landed_ops:
            from vibecomfy.porting.edit.ops import (
                DELTA_SCHEMA_VERSION,
                ensure_root_scoped_delta_envelope,
                op_to_dict,
            )

            delta_envelope_payload = ensure_root_scoped_delta_envelope(
                {
                    "schema_version": DELTA_SCHEMA_VERSION,
                    "ops": [op_to_dict(op) for op in persisted_landed_ops],
                },
                strict=True,
            ).to_dict()
        else:
            delta_envelope_payload = None
        turn_is_read_only = effective_landed == 0 and all(
            str(item.op_kind or "") in {"query", "done", "clarify"}
            for item in batch_result.statements
        )

        turn_has_errors = (
            (not batch_result.ok)
            or bool(batch_result.diagnostics)
            or any(
                d.get("severity") == "error" for d in lint_diag_dicts
            )
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
        direct_tweak_feedback = (
            _direct_existing_parameter_tweak_feedback(state)
            if turn_is_read_only
            else ""
        )
        hardening_feedback = _targeted_edit_hardening_feedback(state) if turn_is_read_only else ""
        extra_feedback = "\n\n".join(
            note for note in (direct_tweak_feedback, hardening_feedback) if note
        )
        if extra_feedback:
            report_text = f"{report_text}\n{extra_feedback}"
        report_json = _format_batch_report_json(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
            lint_dropped_count=lint_dropped_count,
            lint_diagnostics=lint_diag_dicts,
        )
        field_changes = repair_field_changes(
            state.graph,
            tuple(batch_result.field_changes),
        )
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
        if execution_plan_status:
            turn_record["execution_plan_status"] = execution_plan_status
        if delta_envelope_payload is not None:
            turn_record["delta_ops_envelope"] = delta_envelope_payload
            turn_record["delta_ops"] = list(delta_envelope_payload["ops"])
        if noop_field_changes:
            turn_record["noop_field_changes"] = _field_changes_payload(noop_field_changes)
        if clarify_message is not None:
            turn_record["clarification_required"] = True
            turn_record["clarification_message"] = clarify_message
        state.batch_turns.append(turn_record)
        state.batch_feedback = report_text
        state.batch_turn_count = turn_number + 1
        state.batch_budget_state = {
            "max_batches": max_batches,
            "max_consecutive_errors": max_consecutive_errors,
            "remaining_batches": max_batches - state.batch_turn_count,
            "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
            "consecutive_errors": consecutive_errors,
        }
        selected_precedent_unknown_class_feedback = (
            _selected_precedent_unknown_class_feedback(state, batch_result)
        )
        if selected_precedent_unknown_class_feedback and not _batch_candidate_graph_changed(state):
            turn_record["clarification_required"] = True
            turn_record["clarification_message"] = selected_precedent_unknown_class_feedback
            turn_record["authoring_blocker"] = "selected_precedent_unknown_class"

        response_log[-1] = {
            "turn_number": turn_number,
            "response": turn_result.to_dict(),
            "batch_result": turn_record,
        }
        write_json_artifact(state.model_response_path, {"turns": response_log})
        message_record = {
            "turn_number": turn_number,
            "task": state.task,
            "message": turn_result.message,
            "batch": turn_result.batch,
            "report": report_text,
        }
        if execution_plan_status:
            message_record["execution_plan_status"] = execution_plan_status
        if selected_precedent_unknown_class_feedback and not _batch_candidate_graph_changed(state):
            message_record["authoring_blocker"] = "selected_precedent_unknown_class"
            message_record["clarification_required"] = selected_precedent_unknown_class_feedback
        state.messages_path.open("a", encoding="utf-8").write(
            json.dumps(message_record, sort_keys=True)
            + "\n"
        )
        if selected_precedent_unknown_class_feedback and not _batch_candidate_graph_changed(state):
            state.batch_exit_mode = _BATCH_EXIT_PURE_CLARIFY
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            state.user_message = selected_precedent_unknown_class_feedback
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
                "authoring_blocker": {
                    "reason": "selected_precedent_unknown_class",
                    "message": selected_precedent_unknown_class_feedback,
                },
            }
            response_log[-1] = {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "batch_result": turn_record,
                "clarification": {
                    "message": selected_precedent_unknown_class_feedback,
                    "reason": "selected_precedent_unknown_class",
                },
            }
            write_json_artifact(state.model_response_path, {"turns": response_log})
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
                    "mode": "authoring_blocker",
                    "graph_unchanged": True,
                    "reason": "selected_precedent_unknown_class",
                },
            )
'''
