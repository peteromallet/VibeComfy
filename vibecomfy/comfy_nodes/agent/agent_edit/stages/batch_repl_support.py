from __future__ import annotations

import json
import time
from typing import Any, Mapping

from ...audit import write_json_artifact
from ...contracts import FailureKind, StageResult, TurnContext
from ...provider import MalformedModelJSON, MissingRequiredField
from ..artifacts import _compact_diag_to_dict
from ..budget import _batch_budget_failure_kind
from ..messages import _lint_issue_to_dict
from ..state import AgentEditState
from ..websocket import _emit_agent_edit_turn_event
from .agent_delta import _edit_facade


def _resolve_edit_attr(name: str) -> Any:
    return getattr(_edit_facade(), name)


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _append_jsonl(path: Any, payload: Mapping[str, Any]) -> None:
    path.open("a", encoding="utf-8").write(json.dumps(payload, sort_keys=True) + "\n")


def _batch_artifacts(state: AgentEditState) -> tuple[Any, ...]:
    artifact = _resolve_edit_attr("_artifact")
    return (
        artifact(state.before_py_path),
        artifact(state.after_py_path),
        artifact(state.model_request_path),
        artifact(state.model_response_path),
        artifact(state.candidate_ui_path),
        artifact(state.messages_path),
    )


def _candidate_artifacts(state: AgentEditState) -> tuple[Any, ...]:
    artifact = _resolve_edit_attr("_artifact")
    return (
        artifact(state.after_py_path),
        artifact(state.model_request_path),
        artifact(state.model_response_path),
        artifact(state.candidate_ui_path),
        artifact(state.messages_path),
    )


def _update_batch_budget_state(
    state: AgentEditState,
    *,
    max_batches: int,
    max_consecutive_errors: int,
    turn_count: int,
    consecutive_errors: int,
) -> None:
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches - turn_count,
        "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
        "consecutive_errors": consecutive_errors,
    }


def _batch_artifact_map(state: AgentEditState, *, include_python: bool = False) -> dict[str, str]:
    artifacts = {
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
    if include_python:
        artifacts["python"] = str(state.after_py_path)
    return artifacts


def _build_prefetch_research_summary(state: AgentEditState, effective_task: str) -> str:
    prefetch_summary = state.executor_research_summary or (
        _resolve_edit_attr("_prefetch_research_summary")(effective_task)
        if _resolve_edit_attr("_is_graph_explain_intent")(effective_task)
        else ""
    )
    if prefetch_summary and state.executor_research_warnings:
        warning_lines = [f"- {warning}" for warning in state.executor_research_warnings[:6]]
        prefetch_summary = (
            f"{prefetch_summary}\n\nResearch warnings:\n" + "\n".join(warning_lines)
        )
    if prefetch_summary and state.executor_research_sources:
        source_lines = [
            json.dumps(source, sort_keys=True)
            for source in state.executor_research_sources[:8]
        ]
        prefetch_summary = (
            f"{prefetch_summary}\n\nStructured research sources (JSON lines):\n"
            + "\n".join(source_lines)
        )
    return prefetch_summary


def _build_adapt_scoped_research_context(state: AgentEditState) -> str:
    if not (
        state.execution_protocol_notes
        or state.research_context_packet
        or state.graph_facts
    ):
        return ""
    parts: list[str] = []
    discard_note: str | None = None
    if state.execution_protocol_notes:
        notes = dict(state.execution_protocol_notes)
        discard_note = notes.pop("_discardability", None)
        parts.append(
            "## Scoped Research Context (execution_protocol_notes)\n"
            "This is contextual evidence, NOT authoritative guidance.\n"
            f"{json.dumps(notes, indent=2, sort_keys=True)}"
        )
    if state.research_context_packet:
        parts.append(
            "## Research Context Packet (discardable)\n"
            "Precedent evidence from research phase. "
            "Discard if empty, irrelevant, or contradictory.\n"
            f"{json.dumps(state.research_context_packet, indent=2, sort_keys=True)}"
        )
    if state.graph_facts:
        parts.append(
            "## Graph Facts (workflow topology evidence)\n"
            "Deterministic topology/readiness evidence about the current graph. "
            "Use this to understand the workflow structure, terminal outputs, "
            "and any known blockers. NOT a revision verdict.\n"
            f"{json.dumps(state.graph_facts, indent=2, sort_keys=True)}"
        )
    if discard_note:
        parts.append(f"**Discardability**: {discard_note}")
    return "\n\n".join(parts)


def _write_model_response(state: AgentEditState, response_log: list[dict[str, Any]]) -> None:
    write_json_artifact(state.model_response_path, {"turns": response_log})


def _invoke_batch_turn(
    *,
    state: AgentEditState,
    turn_number: int,
    messages: list[dict[str, Any]],
    deepseek_client: Any,
    route: str | None,
    model: str | None,
    response_log: list[dict[str, Any]],
    max_consecutive_errors: int,
    consecutive_errors: int,
) -> Any:
    run_agent_turn_batch = _resolve_edit_attr("run_agent_turn_batch")
    normalize = _resolve_edit_attr("_normalize_test_client_batch_response")
    try:
        if deepseek_client is not None:
            return normalize(deepseek_client(messages))
        return run_agent_turn_batch(state.task, messages, route=route, model=model)
    except (MalformedModelJSON, MissingRequiredField) as exc:
        response_log.append(
            {
                "turn_number": turn_number,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "retrying": consecutive_errors + 1 < max_consecutive_errors,
                },
            }
        )
        _write_model_response(state, response_log)
        _append_jsonl(
            state.messages_path,
            {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            },
        )
        raise
    except Exception as exc:
        response_log.append(
            {
                "turn_number": turn_number,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        _write_model_response(state, response_log)
        _append_jsonl(
            state.messages_path,
            {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            },
        )
        raise


def _budget_exhausted_result(
    state: AgentEditState,
    start: float,
    *,
    turn_record: dict[str, Any] | None,
    context: TurnContext,
    client_id: str | None,
) -> StageResult:
    failure_kind = _batch_budget_failure_kind(state.batch_turns)
    state.batch_exit_mode = _resolve_edit_attr("_BATCH_EXIT_BUDGET")
    state.batch_final_summary = (
        f"Stopped after {state.batch_turn_count} turn(s); "
        f"{state.batch_budget_state.get('remaining_batches', 0)} turn(s) remaining."
    )
    if turn_record is not None:
        _emit_agent_edit_turn_event(
            state,
            context,
            turn_record,
            client_id=client_id,
            status="budget_exhausted",
        )
    return StageResult(
        stage="agent_batch",
        ok=False,
        blocking=True,
        duration_ms=_duration_ms(start),
        artifacts=_batch_artifacts(state),
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


def _pure_clarify_result(
    state: AgentEditState,
    start: float,
    *,
    turn_record: dict[str, Any],
    context: TurnContext,
    client_id: str | None,
) -> StageResult:
    edit_clarify = _resolve_edit_attr("_BATCH_EXIT_EDIT_CLARIFY")
    pure_clarify = _resolve_edit_attr("_BATCH_EXIT_PURE_CLARIFY")
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
            "mode": "clarification_required",
            "graph_unchanged": state.batch_exit_mode == pure_clarify,
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
        if state.batch_exit_mode == edit_clarify
        else {},
    )


def _done_result(
    state: AgentEditState,
    start: float,
    *,
    turn_record: dict[str, Any],
    context: TurnContext,
    client_id: str | None,
    done_summary: str,
) -> StageResult:
    _emit_agent_edit_turn_event(
        state,
        context,
        turn_record,
        client_id=client_id,
        status="done",
    )
    return StageResult(
        stage="agent_batch",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=_batch_artifacts(state),
        value={"mode": "done", "done_summary": done_summary},
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


def _done_validation_failure(
    state: AgentEditState,
    start: float,
    *,
    done_summary: str,
    diagnostics: tuple[Any, ...],
) -> StageResult:
    return StageResult(
        stage="agent_batch",
        ok=False,
        blocking=True,
        duration_ms=_duration_ms(start),
        artifacts=_batch_artifacts(state),
        issues=tuple(_compact_diag_to_dict(item) for item in diagnostics),
        value={
            "failure_kind": FailureKind.VALIDATION_ERROR.value,
            "turn_count": state.batch_turn_count,
            "done_summary": done_summary,
        },
    )


def _lint_batch_result(
    *,
    state: AgentEditState,
    batch_result: Any,
    batch_repl_enabled: bool,
) -> tuple[frozenset[tuple[str, str]] | None, int, tuple[dict[str, Any], ...]]:
    if not (_resolve_edit_attr("_edit_lint_enabled")() and batch_result.landed_ops and batch_repl_enabled):
        return None, 0, ()

    from vibecomfy.porting.edit.lint import LintIndex, lint_delta
    from vibecomfy.porting.edit.ops import RemoveLinkOp, SetModeOp, SetNodeFieldOp, UpsertLinkOp

    lint_result = lint_delta(
        batch_result.landed_ops,
        LintIndex.build(state.graph),
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
    dropped_keys: list[tuple[str, str]] = []
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
            dropped_keys.append(key)
    state.lint_noop_messages = state.lint_noop_messages + tuple(
        norm.issue.message
        for norm in lint_result.normalizations
        if norm.disposition == "dropped_noop" and norm.issue is not None
    )
    lint_diag_dicts = tuple(
        _lint_issue_to_dict(issue)
        for issue in lint_result.issues
        if not (issue.code == "unknown_target" and issue.uid in landed_add_uids)
    )
    return frozenset(dropped_keys), lint_result.dropped_count, lint_diag_dicts


def _record_batch_response(
    *,
    state: AgentEditState,
    turn_number: int,
    turn_result: Any,
    report_text: str,
    response_log: list[dict[str, Any]],
    turn_record: dict[str, Any],
) -> None:
    response_log[-1] = {
        "turn_number": turn_number,
        "response": turn_result.to_dict(),
        "batch_result": turn_record,
    }
    _write_model_response(state, response_log)
    _append_jsonl(
        state.messages_path,
        {
            "turn_number": turn_number,
            "task": state.task,
            "message": turn_result.message,
            "batch": turn_result.batch,
            "report": report_text,
        },
    )
