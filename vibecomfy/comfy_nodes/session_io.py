from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .agent_contracts import ensure_agent_edit_response_contract, TurnContext
from .agent_session import read_state, session_dir_for
from .stages.humanize import _field_changes_payload, _json_safe, _safe_session_id

if TYPE_CHECKING:
    from .agent_edit import AgentEditState

LOGGER = logging.getLogger(__name__)
DEFAULT_CHAT_DISPLAY_MESSAGES = 50

def _write_turn_chat_artifact(
    state: AgentEditState,
    context: TurnContext,
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


def _stamped_turn_response_outcome(
    response: Mapping[str, Any] | None,
    *,
    stage: str = "submit",
) -> dict[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(dict(response), stage=stage)
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
        )
    except Exception:
        return None
    public_outcome = stamped.get("outcome")
    return dict(public_outcome) if isinstance(public_outcome, Mapping) else None


def _read_turn_response_payload(turn_dir: Path) -> dict[str, Any]:
    response_path = turn_dir / "response.json"
    try:
        response = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(response) if isinstance(response, Mapping) else {}


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


# Bounds for the reasoning trim attached to rehydrated chat messages. The chat
# endpoint is fetched on every page reload, so the embedded reasoning must stay
# lean — keep enough per-step context to diagnose a turn (what the agent tried
# and why the engine rejected it) without shipping the full diff/statements.
_CHAT_REASONING_MAX_STEPS = 12
_CHAT_REASONING_MAX_DIAGS = 4
_CHAT_REASONING_MAX_OPERATIONS = 8


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


def read_session_chat(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = DEFAULT_CHAT_DISPLAY_MESSAGES,
) -> dict[str, Any]:
    """Read conversation history for a session from persisted turn artifacts.

    Scans turn directories under the session root in deterministic order,
    reads ``chat.json`` where present, falls back to same-turn
    ``request.json`` + ``response.json``, and returns a bounded display
    history with session metadata.

    Returns:
        dict with keys: ``ok``, ``session_id``, ``session_path``,
        ``latest_turn_id``, ``detail_json_path``, ``messages``.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    turns_dir = session_dir / "turns"

    session_exists = session_dir.is_dir()
    if not turns_dir.is_dir():
        return {
            "ok": True,
            "exists": session_exists,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "latest_turn_id": None,
            "detail_json_path": None,
            "messages": [],
            "latest_candidate": None,
        }

    # Sort turn directories deterministically (zero-padded integers).
    try:
        turn_ids: list[str] = sorted(
            [d.name for d in turns_dir.iterdir() if d.is_dir()],
        )
    except OSError:
        turn_ids = []

    all_messages: list[dict[str, Any]] = []
    latest_turn_id: str | None = None

    for turn_id in turn_ids:
        turn_dir = turns_dir / turn_id
        chat_path = turn_dir / "chat.json"
        chat_record: dict[str, Any] | None = None
        response = _read_turn_response_payload(turn_dir)
        fallback_agent_outcome = _stamped_turn_response_outcome(response, stage="submit")

        # Try chat.json first.
        if chat_path.is_file():
            try:
                chat_record = json.loads(chat_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        # Fall back to request.json + response.json.
        if chat_record is None:
            request_path = turn_dir / "request.json"
            response_path = turn_dir / "response.json"
            if request_path.is_file() and response_path.is_file():
                try:
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                    response = json.loads(response_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue  # skip unrecoverable turn
                agent_text_raw = response.get("user_facing_message") or response.get("message", "")
                agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
                if not agent_text.strip():
                    agent_text = "The agent edit turn completed."
                chat_record = {
                    "session_id": safe_id,
                    "turn_id": turn_id,
                    "session_path": str(session_dir),
                    "turn_path": str(turn_dir),
                    "response_path": str(response_path),
                    "detail_json_path": str(response_path),
                    "messages": [
                        {
                            "role": "user",
                            "text": request.get("task", ""),
                            "turn_id": turn_id,
                        },
                        {
                            "role": "agent",
                            "text": agent_text,
                            "turn_id": turn_id,
                        },
                    ],
                }
                if fallback_agent_outcome is not None:
                    chat_record["messages"][1]["outcome"] = fallback_agent_outcome

        if chat_record is None:
            continue

        # Best-effort wall-clock for this turn, used by the panel to show a
        # relative timestamp ("5 minutes ago") below each chat bubble. Turn
        # artifacts carry no explicit timestamp, so the turn directory's mtime
        # is the most faithful proxy for when the exchange landed.
        try:
            turn_ts = datetime.fromtimestamp(
                turn_dir.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            turn_ts = None

        # Extract display messages from the chat record.
        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") in ("user", "agent"):
                    display_msg = {
                        "role": msg["role"],
                        "text": msg.get("text", ""),
                        "turn_id": msg.get("turn_id", turn_id),
                    }
                    if turn_ts is not None:
                        display_msg["timestamp"] = turn_ts
                    stamped_outcome = _stamped_message_outcome(msg.get("outcome"))
                    if msg["role"] == "agent" and stamped_outcome is None:
                        stamped_outcome = fallback_agent_outcome
                    if msg["role"] == "agent" and stamped_outcome is not None:
                        display_msg["outcome"] = stamped_outcome
                    if msg["role"] == "agent":
                        # Carry a trimmed view of the agent's per-step reasoning so a
                        # reloaded panel's diagnostic report can show what the agent
                        # tried and why the engine rejected it (the on-disk
                        # change_details is otherwise unreachable after reload).
                        reasoning = _compact_chat_change_details(msg.get("change_details"))
                        if reasoning is not None:
                            display_msg["change_details"] = reasoning
                    all_messages.append(display_msg)
        latest_turn_id = turn_id

    # Take the last N messages for display.
    display_messages = all_messages[-max_messages:] if max_messages > 0 else all_messages

    return {
        "ok": True,
        "exists": True,
        "session_id": safe_id,
        "session_path": str(session_dir),
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "messages": display_messages,
        "latest_candidate": _latest_session_candidate_payload(session_dir, turn_ids),
    }


# Suffixes treated as UTF-8 text in the downloadable session bundle; everything
# else is base64-encoded so binary artifacts (PNG previews, etc.) survive.
_BUNDLE_TEXT_SUFFIXES = frozenset(
    {".json", ".jsonl", ".py", ".txt", ".md", ".log", ".csv", ".yaml", ".yml", ".diff", ".html"}
)
_BUNDLE_MAX_FILE_BYTES = 8 * 1024 * 1024  # 8 MiB per file
_BUNDLE_MAX_TOTAL_BYTES = 64 * 1024 * 1024  # 64 MiB per bundle


def read_session_bundle(
    session_root: Path,
    session_id: str,
    *,
    max_file_bytes: int = _BUNDLE_MAX_FILE_BYTES,
    max_total_bytes: int = _BUNDLE_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Read every artifact under a session dir for a self-contained issue bundle.

    The issue-report ZIP is built in the browser, which cannot reach the
    filesystem; the report/prompt point at ``messages.jsonl`` etc. that a
    recipient on another machine does not have. This returns the full set of
    session artifacts (turn dirs + session_state.json) so the browser can embed
    them in the ZIP — making the report self-contained.

    Files are returned with names relative to the session dir. Text artifacts
    carry a ``text`` field; binary artifacts carry base64 ``base64``. Oversized
    files and anything past the total cap are recorded in ``skipped`` rather
    than silently dropped.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    if not session_dir.is_dir():
        return {
            "ok": True,
            "exists": False,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "files": [],
            "skipped": [],
            "file_count": 0,
            "total_bytes": 0,
        }

    files: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total = 0
    try:
        candidates = sorted(p for p in session_dir.rglob("*") if p.is_file())
    except OSError as exc:
        return {
            "ok": True,
            "exists": True,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "files": [],
            "skipped": [{"name": "(walk)", "reason": f"walk_failed: {exc}"}],
            "file_count": 0,
            "total_bytes": 0,
        }

    for path in candidates:
        try:
            rel = path.relative_to(session_dir).as_posix()
        except ValueError:
            continue  # defensive: never escape the session dir
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"name": rel, "reason": "stat_failed"})
            continue
        if size > max_file_bytes:
            skipped.append({"name": rel, "reason": "too_large", "size": size})
            continue
        if total + size > max_total_bytes:
            skipped.append({"name": rel, "reason": "bundle_full", "size": size})
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            skipped.append({"name": rel, "reason": "read_failed"})
            continue
        total += len(raw)
        if path.suffix.lower() in _BUNDLE_TEXT_SUFFIXES:
            files.append({"name": rel, "text": raw.decode("utf-8", errors="replace")})
        else:
            files.append({"name": rel, "base64": base64.b64encode(raw).decode("ascii")})

    return {
        "ok": True,
        "exists": True,
        "session_id": safe_id,
        "session_path": str(session_dir),
        "files": files,
        "skipped": skipped,
        "file_count": len(files),
        "total_bytes": total,
    }


def read_session_json(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = 5,
) -> dict[str, Any]:
    """Return session metadata, sorted turn summaries, and last-five messages.

    This is the JSON detail route helper — it returns turn-level artifact
    paths (``request.json``, ``response.json``, ``chat.json``) for each
    persisted turn alongside the same last-five display messages as
    ``read_session_chat``.  It does **not** browse, search, index, or read
    arbitrary paths.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    turns_dir = session_dir / "turns"

    session_meta = {
        "session_id": safe_id,
        "session_path": str(session_dir),
        "turns_dir": str(turns_dir),
    }

    if not turns_dir.is_dir():
        return {
            **session_meta,
            "ok": True,
            "latest_turn_id": None,
            "detail_json_path": None,
            "turn_count": 0,
            "turns": [],
            "messages": [],
        }

    # Deterministic sort of turn directories.
    try:
        turn_names: list[str] = sorted(
            [d.name for d in turns_dir.iterdir() if d.is_dir()],
        )
    except OSError:
        turn_names = []

    turn_summaries: list[dict[str, Any]] = []
    all_messages: list[dict[str, Any]] = []
    latest_turn_id: str | None = None

    for turn_name in turn_names:
        turn_dir = turns_dir / turn_name
        summary: dict[str, Any] = {
            "turn_id": turn_name,
            "turn_path": str(turn_dir),
        }

        # Artifact paths — only note what is actually present.
        for artifact_name in ("request.json", "response.json", "chat.json"):
            artifact_path = turn_dir / artifact_name
            if artifact_path.is_file():
                summary[artifact_name] = str(artifact_path)

        # Reuse the chat-reader logic for message extraction.
        chat_path = turn_dir / "chat.json"
        chat_record: dict[str, Any] | None = None

        if chat_path.is_file():
            try:
                chat_record = json.loads(chat_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        if chat_record is None:
            request_path = turn_dir / "request.json"
            response_path = turn_dir / "response.json"
            if request_path.is_file() and response_path.is_file():
                try:
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                    response = json.loads(response_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    summary["error"] = "unreadable artifacts"
                    turn_summaries.append(summary)
                    continue
                agent_text: str = response.get("message", "")
                if not isinstance(agent_text, str) or not agent_text.strip():
                    agent_text = "The agent edit turn completed."
                chat_record = {
                    "session_id": safe_id,
                    "turn_id": turn_name,
                    "session_path": str(session_dir),
                    "turn_path": str(turn_dir),
                    "response_path": str(response_path),
                    "detail_json_path": str(response_path),
                    "messages": [
                        {
                            "role": "user",
                            "text": request.get("task", ""),
                            "turn_id": turn_name,
                        },
                        {
                            "role": "agent",
                            "text": agent_text,
                            "turn_id": turn_name,
                        },
                    ],
                }

        if chat_record is None:
            summary["error"] = "no readable artifacts"
            turn_summaries.append(summary)
            continue

        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") in ("user", "agent"):
                    all_messages.append({
                        "role": msg["role"],
                        "text": msg.get("text", ""),
                        "turn_id": msg.get("turn_id", turn_name),
                    })

        summary["message_count"] = len(
            [m for m in messages if isinstance(m, dict) and m.get("role") in ("user", "agent")]
        )
        turn_summaries.append(summary)
        latest_turn_id = turn_name

    display_messages = all_messages[-max_messages:] if max_messages > 0 else all_messages

    return {
        **session_meta,
        "ok": True,
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "turn_count": len(turn_summaries),
        "turns": turn_summaries,
        "messages": display_messages,
    }


def _compact_diag_to_dict(diagnostic: Any) -> dict[str, Any]:
    return {
        "code": getattr(diagnostic, "code", type(diagnostic).__name__),
        "message": getattr(diagnostic, "message", str(diagnostic)),
        "severity": getattr(diagnostic, "severity", "error"),
        "detail": _json_safe(getattr(diagnostic, "detail", {})),
        "teaching_hint": getattr(diagnostic, "teaching_hint", None),
    }


def _port_issue_to_dict(issue: Any) -> dict[str, Any]:
    to_json = getattr(issue, "to_json", None)
    if callable(to_json):
        rendered = to_json()
        if isinstance(rendered, dict):
            return rendered
    if isinstance(issue, Mapping):
        return dict(issue)
    return {"code": type(issue).__name__, "message": str(issue), "severity": "error"}


