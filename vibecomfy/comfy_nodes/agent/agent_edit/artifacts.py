"""Artifact read/write helpers and JSON-safe serialization for agent-edit."""

from __future__ import annotations

import base64
import difflib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..contracts import (
    ensure_agent_edit_response_contract,
)
from ..provider import AgentTurnResult
from ..provider import BatchTurnResult
from ..session import read_state, session_dir_for
from .fields import field_changes_payload as _field_changes_payload
from .paths import safe_session_id as _safe_session_id
from .state import AgentEditState

LOGGER = logging.getLogger(__name__)

# Bounds for the reasoning trim attached to rehydrated chat messages. The chat
# endpoint is fetched on every page reload, so the embedded reasoning must stay
# lean — keep enough per-step context to diagnose a turn (what the agent tried
# and why the engine rejected it) without shipping the full diff/statements.
_CHAT_REASONING_MAX_STEPS = 12
_CHAT_REASONING_MAX_DIAGS = 4
_CHAT_REASONING_MAX_OPERATIONS = 8


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _render_batch_diff(before: str, after: str, *, max_chars: int = 2000) -> str:
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before.py",
            tofile="after.py",
            n=2,
        )
    ).strip()
    if len(diff) <= max_chars:
        return diff
    return diff[: max(0, max_chars - 15)].rstrip() + "\n... [truncated]"


def _format_statement_source(source: str, *, max_chars: int = 72) -> str:
    """Truncate a statement source string for inline display."""
    if len(source) <= max_chars:
        return source
    return source[: max(0, max_chars - 3)] + "..."


def _format_query_output(text: str, *, max_chars: int | None = 4000) -> str:
    """Bound read-only query output before it is included in agent feedback."""
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 18)].rstrip() + "\n... [truncated]"


def _normalize_test_client_response(response: dict[str, str]) -> AgentTurnResult:
    python = response.get("python")
    message = response.get("message")
    if not isinstance(python, str):
        raise ValueError("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise ValueError("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client"},
    )


def _normalize_test_client_batch_response(response: dict[str, str]) -> BatchTurnResult:
    batch = response.get("batch")
    message = response.get("message")
    if not isinstance(batch, str):
        raise ValueError("Batch agent response must include string key `batch`.")
    if not isinstance(message, str):
        raise ValueError("Batch agent response must include string key `message`.")
    return BatchTurnResult(
        batch=batch,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client", "response_contract": "batch_repl"},
    )


def _read_turn_response_payload(turn_dir: Path) -> dict[str, Any]:
    response_path = turn_dir / "response.json"
    try:
        response = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(response) if isinstance(response, Mapping) else {}


def _stamped_turn_response_outcome(
    response: Mapping[str, Any] | None,
    *,
    stage: str = "submit",
) -> dict[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(
            dict(response),
            stage=stage,
            compatibility_mode=True,
        )
    except Exception:
        return None
    outcome = stamped.get("outcome")
    return dict(outcome) if isinstance(outcome, Mapping) else None


def _stamped_message_outcome(
    outcome: Mapping[str, Any] | None,
    *,
    stage: str = "chat",
) -> dict[str, Any] | None:
    if not isinstance(outcome, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(
            {"ok": True, "outcome": dict(outcome)},
            stage=stage,
            compatibility_mode=True,
        )
    except Exception:
        return None
    public_outcome = stamped.get("outcome")
    return dict(public_outcome) if isinstance(public_outcome, Mapping) else None


def _trim_chat_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _compact_chat_change_details(change_details: Any) -> dict[str, Any] | None:
    """Trim a turn's ``change_details`` to the reasoning the panel report needs.

    The full ``change_details`` carries per-step diffs, statements, and provider
    metadata that bloat the chat-rehydrate payload. The diagnostic report only
    consumes the agent's per-step ``message`` / ``batch`` and the engine
    ``diagnostics`` (which carry the root data — valid enum ``choices`` and
    ``available_slots``), plus the change summary. Keep just those.
    """
    if not isinstance(change_details, dict):
        return None
    compact: dict[str, Any] = {}

    summary = _trim_chat_text(
        change_details.get("done_summary") or change_details.get("final_summary"),
        400,
    )
    if summary is not None:
        compact["done_summary"] = summary
    if isinstance(change_details.get("landed_operation_count"), int):
        compact["landed_operation_count"] = change_details["landed_operation_count"]

    operations = change_details.get("operations")
    if isinstance(operations, list) and operations:
        trimmed_ops = []
        for op in operations[:_CHAT_REASONING_MAX_OPERATIONS]:
            if not isinstance(op, dict):
                continue
            entry = {}
            op_summary = _trim_chat_text(op.get("summary"), 160)
            if op_summary is not None:
                entry["summary"] = op_summary
            field_path = _trim_chat_text(op.get("field_path"), 160)
            if field_path is not None:
                entry["field_path"] = field_path
            if entry:
                trimmed_ops.append(entry)
        if trimmed_ops:
            compact["operations"] = trimmed_ops

    batch_turns = change_details.get("batch_turns")
    if isinstance(batch_turns, list) and batch_turns:
        trimmed_steps = []
        for step in batch_turns[:_CHAT_REASONING_MAX_STEPS]:
            if not isinstance(step, dict):
                continue
            trimmed: dict[str, Any] = {}
            if isinstance(step.get("turn_number"), int):
                trimmed["turn_number"] = step["turn_number"]
            if isinstance(step.get("batch_ok"), bool):
                trimmed["batch_ok"] = step["batch_ok"]
            if isinstance(step.get("landed_op_count"), int):
                trimmed["landed_op_count"] = step["landed_op_count"]
            message = _trim_chat_text(step.get("message"), 500)
            if message is not None:
                trimmed["message"] = message
            batch = _trim_chat_text(step.get("batch"), 400)
            if batch is not None:
                trimmed["batch"] = batch
            diagnostics = step.get("diagnostics")
            if isinstance(diagnostics, list) and diagnostics:
                trimmed_diags = []
                for diag in diagnostics[:_CHAT_REASONING_MAX_DIAGS]:
                    if not isinstance(diag, dict):
                        continue
                    diag_entry: dict[str, Any] = {}
                    for key in ("code", "severity"):
                        if isinstance(diag.get(key), str):
                            diag_entry[key] = diag[key]
                    diag_message = _trim_chat_text(diag.get("message"), 300)
                    if diag_message is not None:
                        diag_entry["message"] = diag_message
                    detail = diag.get("detail")
                    if isinstance(detail, dict):
                        detail_entry = {}
                        for key in ("input", "value", "slot", "class_type", "name"):
                            if isinstance(detail.get(key), (str, int, float, bool)):
                                detail_entry[key] = detail[key]
                        for key in ("choices", "available_slots"):
                            values = detail.get(key)
                            if isinstance(values, list):
                                detail_entry[key] = [v for v in values[:24] if isinstance(v, (str, int, float))]
                        if detail_entry:
                            diag_entry["detail"] = detail_entry
                    if diag_entry:
                        trimmed_diags.append(diag_entry)
                if trimmed_diags:
                    trimmed["diagnostics"] = trimmed_diags
            if trimmed:
                trimmed_steps.append(trimmed)
        if trimmed_steps:
            compact["batch_turns"] = trimmed_steps

    return compact or None


def _compact_diag_to_dict(diagnostic: Any) -> dict[str, Any]:
    return {
        "code": getattr(diagnostic, "code", type(diagnostic).__name__),
        "message": getattr(diagnostic, "message", str(diagnostic)),
        "severity": getattr(diagnostic, "severity", "error"),
        "detail": _json_safe(getattr(diagnostic, "detail", {})),
        "teaching_hint": getattr(diagnostic, "teaching_hint", None),
    }


def _port_issue_to_dict(issue: Any) -> dict[str, Any]:
    return {
        "code": getattr(issue, "code", type(issue).__name__),
        "message": getattr(issue, "message", str(issue)),
        "severity": getattr(issue, "severity", "error"),
        "detail": _json_safe(getattr(issue, "detail", {})),
        "teaching_hint": getattr(issue, "teaching_hint", None),
    }


def _latest_session_candidate_payload(session_dir: Path, turn_ids: list[str]) -> dict[str, Any] | None:
    try:
        state = read_state(session_dir)
    except Exception:
        state = {}
    turns_state = state.get("turns") if isinstance(state, Mapping) else {}
    if not isinstance(turns_state, Mapping):
        turns_state = {}
    for turn_id in reversed(turn_ids):
        turn_state = turns_state.get(turn_id)
        if not isinstance(turn_state, Mapping) or turn_state.get("state") != "candidate":
            continue
        turn_dir = session_dir / "turns" / turn_id
        response = _read_turn_response_payload(turn_dir)
        outcome = _stamped_turn_response_outcome(response, stage="submit")
        if outcome is None or outcome.get("kind") != "candidate":
            continue
        candidate_path = turn_dir / "candidate.ui.json"
        graph = response.get("graph")
        if not isinstance(graph, Mapping) and candidate_path.is_file():
            try:
                graph = json.loads(candidate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                graph = None
        if not isinstance(graph, Mapping):
            continue
        candidate = response.get("candidate")
        eligibility = response.get("apply_eligibility") or response.get("eligibility")
        latest_candidate = {
            "turn_id": turn_id,
            "session_id": session_dir.name,
            "baseline_turn_id": response.get("baseline_turn_id"),
            "message": response.get("message"),
            "graph": _json_safe(graph),
            "report": _json_safe(response.get("report")) if isinstance(response.get("report"), Mapping) else None,
            "candidate": _json_safe(candidate) if isinstance(candidate, Mapping) else None,
            "apply_eligibility": _json_safe(eligibility) if isinstance(eligibility, Mapping) else None,
            "canvas_apply_allowed": bool(response.get("canvas_apply_allowed")),
            "apply_allowed": response.get("apply_allowed") is not False,
            "queue_allowed": bool(response.get("queue_allowed")),
            "candidate_graph_hash": response.get("candidate_graph_hash") or turn_state.get("candidate_graph_hash"),
            "candidate_structural_graph_hash": response.get("candidate_structural_graph_hash") or turn_state.get("candidate_structural_graph_hash"),
            "submit_graph_hash": response.get("submit_graph_hash") or turn_state.get("submit_graph_hash"),
            "submit_structural_graph_hash": response.get("submit_structural_graph_hash") or turn_state.get("submit_structural_graph_hash"),
            "baseline_graph_hash": response.get("baseline_graph_hash") or state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": response.get("baseline_graph_hash_kind") or state.get("baseline_graph_hash_kind"),
            "baseline_graph_hash_version": response.get("baseline_graph_hash_version") or state.get("baseline_graph_hash_version"),
            "audit_ref": _json_safe(response.get("audit_ref")) if isinstance(response.get("audit_ref"), Mapping) else None,
            "change_details": _json_safe(response.get("change_details")) if isinstance(response.get("change_details"), Mapping) else None,
            "batch_turns": _json_safe(response.get("batch_turns")) if isinstance(response.get("batch_turns"), list) else [],
            "outcome": outcome,
        }
        return latest_candidate
    return None


def _write_turn_chat_artifact(
    state: AgentEditState,
    context: Any,
    response: dict[str, Any],
    contract: str,
) -> None:
    """Best-effort write of ``chat.json`` for an allocated, completed edit turn.

    ``response.json`` is the durable turn artifact; ``chat.json`` is a
    JSON-canonical UI convenience.  Failures here are logged and swallowed.
    """
    turn_dir = state.turn_dir
    chat_path = turn_dir / "chat.json"

    agent_text_raw = response.get("user_facing_message") or response.get("message", "")
    agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
    if not agent_text.strip():
        agent_text = "The agent edit turn completed."

    # Extract structured changes by contract shape.
    changes: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        outcome = response.get("outcome")
        if isinstance(outcome, Mapping):
            raw = outcome.get("changes")
            if isinstance(raw, list):
                changes = [_json_safe(c) for c in raw]
        if changes is None and state.batch_field_changes:
            changes = _field_changes_payload(state.batch_field_changes)
    elif contract == "delta":
        delta_ops = response.get("delta_ops")
        if isinstance(delta_ops, list):
            changes = _json_safe(delta_ops)

    agent_msg: dict[str, Any] = {
        "role": "agent",
        "text": agent_text,
        "turn_id": context.turn_id,
    }
    outcome_payload = response.get("outcome")
    if isinstance(outcome_payload, Mapping):
        agent_msg["outcome"] = dict(outcome_payload)
    if changes is not None:
        agent_msg["changes"] = changes
    change_details = response.get("change_details")
    if isinstance(change_details, Mapping):
        agent_msg["change_details"] = _json_safe(dict(change_details))

    chat_record: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "session_path": str(state.session_dir),
        "turn_path": str(turn_dir),
        "response_path": str(turn_dir / "response.json"),
        "detail_json_path": str(turn_dir / "response.json"),
        "messages": [
            {
                "role": "user",
                "text": state.task,
                "turn_id": context.turn_id,
            },
            agent_msg,
        ],
    }

    try:
        turn_dir.mkdir(parents=True, exist_ok=True)
        chat_path.write_text(
            json.dumps(chat_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning(
            "chat.json write failed for turn %s (best-effort): %s",
            context.turn_id,
            exc,
        )


__all__ = [
    "_CHAT_REASONING_MAX_DIAGS",
    "_CHAT_REASONING_MAX_OPERATIONS",
    "_CHAT_REASONING_MAX_STEPS",
    "_compact_chat_change_details",
    "_compact_diag_to_dict",
    "_format_query_output",
    "_format_statement_source",
    "_json_safe",
    "_latest_session_candidate_payload",
    "_normalize_test_client_batch_response",
    "_normalize_test_client_response",
    "_port_issue_to_dict",
    "_read_turn_response_payload",
    "_render_batch_diff",
    "_stamped_message_outcome",
    "_stamped_turn_response_outcome",
    "_trim_chat_text",
    "_write_turn_chat_artifact",
]
