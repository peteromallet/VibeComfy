"""Compact websocket event helpers for agent-edit batch turns."""

from __future__ import annotations

from typing import Any

from .budget import _BATCH_EXIT_DONE, _BATCH_EXIT_NOOP
from .state import AgentEditState


def _ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None, logger: Any) -> None:
    try:
        from server import PromptServer
    except ImportError:
        return
    try:
        if hasattr(PromptServer.instance, "send_sync") and callable(
            PromptServer.instance.send_sync
        ):
            PromptServer.instance.send_sync(event, payload, sid=client_id)
        elif hasattr(PromptServer.instance, "send_json") and callable(
            PromptServer.instance.send_json
        ):
            PromptServer.instance.send_json(event, payload, sid=client_id)
    except Exception:
        logger.debug(
            "websocket send for event %r to client %r failed (best-effort)",
            event,
            client_id,
            exc_info=True,
        )


def _brief_batch_statements(turn_record: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(turn_record, dict):
        return []
    if turn_record.get("clarification_required"):
        return [
            {
                "clarification": True,
                "message": turn_record.get("clarification_message", ""),
            }
        ]
    statements = turn_record.get("statements")
    if not isinstance(statements, list) or not statements:
        return [
            {
                "ok": bool(turn_record.get("batch_ok")),
                "statement_count": int(turn_record.get("statement_count", 0)),
                "landed": int(turn_record.get("landed_op_count", 0)),
                "diagnostic_count": len(turn_record.get("diagnostics") or []),
            }
        ]
    brief: list[dict[str, Any]] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        compact: dict[str, Any] = {
            "statement_index": stmt.get("statement_index"),
            "ok": stmt.get("ok"),
            "landed": stmt.get("landed"),
            "op_kind": stmt.get("op_kind"),
        }
        if stmt.get("teaching_hint"):
            compact["teaching_hint"] = stmt["teaching_hint"]
        if stmt.get("dependency_cause"):
            compact["dependency_cause"] = stmt["dependency_cause"]
        diags = stmt.get("diagnostics")
        if isinstance(diags, list) and diags:
            compact["diagnostics"] = [
                {"code": d.get("code"), "message": d.get("message")}
                for d in diags
                if isinstance(d, dict)
            ][:5]
        if stmt.get("touched_uids"):
            compact["touched_uids"] = list(stmt["touched_uids"])[:10]
        brief.append(compact)
    return brief


def _agent_edit_turn_event_payload(
    state: AgentEditState,
    context: Any,
    turn_record: dict[str, Any],
    *,
    entry_type: str = "batch",
    status: str = "progress",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "turn_number": turn_record.get("turn_number"),
        "entry_type": entry_type,
        "status": status,
    }
    message = turn_record.get("message")
    if isinstance(message, str) and message:
        payload["message"] = message[:500] if len(message) > 500 else message
    if turn_record.get("clarification_required"):
        payload["clarification_required"] = True
        cm = turn_record.get("clarification_message")
        if isinstance(cm, str) and cm:
            payload["clarification_message"] = cm[:500] if len(cm) > 500 else cm
    else:
        payload["batch_ok"] = bool(turn_record.get("batch_ok"))
        payload["statement_count"] = int(turn_record.get("statement_count", 0))
        payload["landed_op_count"] = int(turn_record.get("landed_op_count", 0))
    statements = _brief_batch_statements(turn_record)
    if statements:
        payload["statements"] = statements
    diags = turn_record.get("diagnostics")
    if isinstance(diags, list) and diags:
        payload["diagnostics"] = [
            {"code": d.get("code"), "message": d.get("message")}
            for d in diags
            if isinstance(d, dict)
        ][:5]
    exit_mode = getattr(state, "batch_exit_mode", "")
    if exit_mode:
        payload["exit_mode"] = exit_mode
    if exit_mode in {_BATCH_EXIT_DONE, _BATCH_EXIT_NOOP} and getattr(state, "batch_done_summary", ""):
        payload["done_summary"] = str(state.batch_done_summary)[:500]
    budget = getattr(state, "batch_budget_state", None)
    if isinstance(budget, dict) and budget:
        payload["budget"] = {
            "remaining_batches": budget.get("remaining_batches"),
            "consecutive_errors": budget.get("consecutive_errors"),
        }
    return payload


def _emit_agent_edit_turn_event(
    state: AgentEditState,
    context: Any,
    turn_record: dict[str, Any],
    *,
    ws_send: Any,
    logger: Any,
    client_id: str | None = None,
    entry_type: str = "batch",
    status: str = "progress",
) -> None:
    try:
        payload = _agent_edit_turn_event_payload(
            state, context, turn_record, entry_type=entry_type, status=status
        )
        ws_send("vibecomfy.agent_edit.turn", payload, client_id=client_id)
    except Exception:
        logger.debug("emit agent-edit turn event failed (best-effort)", exc_info=True)


__all__ = [
    "_agent_edit_turn_event_payload",
    "_brief_batch_statements",
    "_emit_agent_edit_turn_event",
    "_ws_send",
]
