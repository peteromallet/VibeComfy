from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Mapping

from ..agent_audit import write_json_artifact
from ..agent_contracts import FailureKind, StageResult, TurnContext
from ..agent_provider import build_batch_messages
from .emit import _edit_lint_enabled
from .humanize import (
    _artifact,
    _batch_candidate_graph_changed,
    _compact_diag_to_dict,
    _duration_ms,
    _field_changes_payload,
    _format_available_node_names,
    _format_batch_report,
    _format_batch_report_json,
    _format_node_variable_index,
    _json_safe,
    _noop_field_changes,
    _normalize_test_client_batch_response,
    _present_class_types,
    _real_field_changes,
    _render_batch_diff,
    _repair_field_changes_from_original_ui,
)

if TYPE_CHECKING:
    from ..agent_edit import AgentEditState, DeepSeekClient


def _batch_has_landed_edits(state: "AgentEditState") -> bool:
    return any(
        isinstance(turn, Mapping) and int(turn.get("landed_op_count", 0)) > 0
        for turn in state.batch_turns
    )


def _batch_budget_failure_kind(turns: list[dict[str, Any]]) -> FailureKind:
    schema_gap_markers = (
        "schema",
        "schema-backed",
        "socket type",
        "compatible output",
        "confidence",
    )
    unrepresentable_codes = {
        "statement_not_allowed",
        "call_not_allowed",
        "nested_call_not_allowed",
        "raw_coordinate_kwarg_not_allowed",
        "intent_class_construction_not_allowed",
        "cross_scope_add_node_unsupported",
        "scope_escape_not_allowed",
        "original_virtual_node_immutable",
        "kwargs_unpack_not_allowed",
        "dict_unpack_not_allowed",
        "lambda_not_allowed",
        "comprehension_not_allowed",
        "f_string_not_allowed",
        "for_else_not_allowed",
        "import_not_allowed",
    }
    category_turn_hits = {
        FailureKind.MODEL_MISTAKE: 0,
        FailureKind.UNREPRESENTABLE: 0,
        FailureKind.SCHEMA_GAP: 0,
    }
    for turn in turns:
        turn_categories: set[FailureKind] = set()
        diagnostics = list(turn.get("diagnostics") or [])
        for statement in turn.get("statements") or []:
            diagnostics.extend(statement.get("diagnostics") or [])
        for diagnostic in diagnostics:
            code = str(diagnostic.get("code", "")).lower()
            message = str(diagnostic.get("message", "")).lower()
            teaching_hint = str(diagnostic.get("teaching_hint", "")).lower()
            haystack = " ".join((code, message, teaching_hint))
            if any(marker in haystack for marker in schema_gap_markers):
                turn_categories.add(FailureKind.SCHEMA_GAP)
                continue
            if code in unrepresentable_codes or "not allowed" in haystack or "immutable" in haystack:
                turn_categories.add(FailureKind.UNREPRESENTABLE)
                continue
            turn_categories.add(FailureKind.MODEL_MISTAKE)
        for category in turn_categories:
            category_turn_hits[category] += 1
    ranked = sorted(
        category_turn_hits.items(),
        key=lambda item: (item[1], item[0] == FailureKind.SCHEMA_GAP, item[0] == FailureKind.UNREPRESENTABLE),
        reverse=True,
    )
    if ranked and ranked[0][1] > 0:
        return ranked[0][0]
    return FailureKind.MODEL_MISTAKE


def _stage_agent_batch_repl(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from ..agent_edit import (
        _BATCH_EXIT_BUDGET,
        _BATCH_EXIT_DONE,
        _BATCH_EXIT_EDIT_CLARIFY,
        _BATCH_EXIT_NOOP,
        _BATCH_EXIT_PURE_CLARIFY,
        _agent_edit_batch_repl_enabled,
        _emit_agent_edit_turn_event,
        run_agent_turn_batch,
        split_terminal_clarify,
    )
    from vibecomfy.porting.edit.session import EditSession

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    session = EditSession(prepared_ui, schema_provider=state.schema_provider)
    state.batch_session = session
    initial_render = session.render()
    present_types = _present_class_types(session)
    signature_catalog = session.search(focus_types=present_types, formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

    max_batches = max(1, int(state.batch_max_turns or 1))
    max_consecutive_errors = max(1, int(state.batch_max_consecutive_errors or 1))
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches,
        "remaining_consecutive_errors": max_consecutive_errors,
    }
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }

    current_render = initial_render
    last_diff = ""
    last_report = ""
    last_landed_count: int | None = None
    previous_model_message = ""
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = _format_node_variable_index(session)
        messages = build_batch_messages(
            task=state.task,
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
        )
        request_entry = {
            "turn_number": turn_number,
            "messages": messages,
            "budget_remaining": budget_remaining,
            "node_variable_index": node_variable_index,
            "included_full_render": include_full_render,
        }
        request_log.append(request_entry)
        write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        if deepseek_client is not None:
            turn_result = _normalize_test_client_batch_response(deepseek_client(messages))
        else:
            turn_result = run_agent_turn_batch(
                state.task,
                messages,
                route=route,
                model=model,
        )

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        previous_model_message = turn_result.message
        clarify_split = split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
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
            response_log.append(
                {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "clarification": turn_record,
                }
            )
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
        next_render = session.render()
        state.python_after = next_render
        state.after_py_path.write_text(next_render, encoding="utf-8")
        state.ui_payload = json.loads(json.dumps(session.working_ui))
        write_json_artifact(state.candidate_ui_path, state.ui_payload)

        # ── lint gate: post-apply no-op detection on landed ops ──────────
        lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None
        lint_dropped_count = 0
        lint_diag_dicts: tuple[dict[str, Any], ...] = ()
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

            lint_diag_dicts = tuple(
                _lint_issue_to_dict(issue) for issue in lint_result.issues
            )

        raw_landed = len(batch_result.landed_ops)
        effective_landed = raw_landed - lint_dropped_count
        landed_count = effective_landed
        total_landed += effective_landed
        last_landed_count = effective_landed

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
        report_json = _format_batch_report_json(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
            lint_dropped_count=lint_dropped_count,
            lint_diagnostics=lint_diag_dicts,
        )
        field_changes = _repair_field_changes_from_original_ui(
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

        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "batch_result": turn_record,
            }
        )
        write_json_artifact(state.model_response_path, {"turns": response_log})
        state.messages_path.open("a", encoding="utf-8").write(
            json.dumps(
                {
                    "turn_number": turn_number,
                    "task": state.task,
                    "message": turn_result.message,
                    "batch": turn_result.batch,
                    "report": report_text,
                },
                sort_keys=True,
            )
            + "\n"
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
            and (turn_number + 1) < max_batches
            and consecutive_errors < max_consecutive_errors
        ):
            if total_landed == 0 and done_noop_nudges < 2:
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
                else:
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
            state.user_message = (
                f"{turn_result.message}\n\n{done_result.summary}".strip()
                if turn_result.message
                else done_result.summary
            )
            state.report = {
                "done_summary": done_result.summary,
                "queue_blockers": [],
            }
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
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
    state.batch_exit_mode = _BATCH_EXIT_BUDGET
    state.batch_final_summary = (
        f"Stopped after {state.batch_turn_count} batch turn(s); "
        f"{state.batch_budget_state.get('remaining_batches', 0)} batch(es) remaining."
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
