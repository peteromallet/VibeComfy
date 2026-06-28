"""Session read helpers for agent-edit conversation history and bundle access."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..session import session_dir_for
from .artifacts import (
    _compact_chat_change_details,
    _latest_session_candidate_payload,
    _read_turn_response_payload,
    _stamped_message_outcome,
    _stamped_turn_response_outcome,
)
from .paths import safe_session_id as _safe_session_id

# Suffixes treated as UTF-8 text in the downloadable session bundle; everything
# else is base64-encoded so binary artifacts (PNG previews, etc.) survive.
_BUNDLE_TEXT_SUFFIXES = frozenset(
    {".json", ".jsonl", ".py", ".txt", ".md", ".log", ".csv", ".yaml", ".yml", ".diff", ".html"}
)
_BUNDLE_MAX_FILE_BYTES = 8 * 1024 * 1024  # 8 MiB per file
_BUNDLE_MAX_TOTAL_BYTES = 64 * 1024 * 1024  # 64 MiB per bundle

# PROMPT_MEMORY_MESSAGES for _conversation_with_candidate_reference; this
# mirrors the facade constant to avoid a circular import back into edit.py.
_PROMPT_MEMORY_MESSAGES = 5


def _conversation_with_candidate_reference(
    messages: list[dict[str, Any]] | None,
    latest_candidate: Any,
) -> list[dict[str, Any]] | None:
    """Append compact latest-candidate context for follow-up references."""
    if not isinstance(messages, list):
        return messages
    if not isinstance(latest_candidate, Mapping):
        return messages
    parts: list[str] = []
    turn_id = latest_candidate.get("turn_id")
    if isinstance(turn_id, str) and turn_id:
        parts.append(f"turn={turn_id}")
    outcome = latest_candidate.get("outcome")
    if isinstance(outcome, Mapping) and isinstance(outcome.get("kind"), str):
        parts.append(f"outcome={outcome['kind']}")
    change_details = latest_candidate.get("change_details")
    operations = (
        change_details.get("operations")
        if isinstance(change_details, Mapping)
        else None
    )
    if isinstance(operations, list) and operations:
        summaries = []
        for op in operations[:4]:
            if isinstance(op, Mapping):
                summary = op.get("summary") or op.get("field_path")
                if isinstance(summary, str) and summary.strip():
                    summaries.append(summary.strip()[:120])
        if summaries:
            parts.append("changes=" + "; ".join(summaries))
    if not parts:
        return messages
    augmented = list(messages)
    augmented.append(
        {
            "role": "agent",
            "text": "Latest candidate reference (for resolving follow-up terms like "
            f"'that one'): {', '.join(parts)}",
        }
    )
    return augmented[-_PROMPT_MEMORY_MESSAGES:]


def read_session_chat(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = 50,
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
            "session_path_resolved": str(session_dir.resolve()),
            "latest_turn_id": None,
            "detail_json_path": None,
            "detail_json_path_resolved": None,
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
        # Defensively skip malformed entries (non-dict, missing role,
        # non-string text) so a corrupt chat.json in one turn cannot
        # poison the entire session history read.
        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if role not in ("user", "agent"):
                    continue
                text = msg.get("text", "")
                if not isinstance(text, str):
                    text = str(text) if text is not None else ""
                display_msg = {
                    "role": role,
                    "text": text,
                    "turn_id": msg.get("turn_id", turn_id),
                }
                if turn_ts is not None:
                    display_msg["timestamp"] = turn_ts
                stamped_outcome = _stamped_message_outcome(msg.get("outcome"))
                if role == "agent" and stamped_outcome is None:
                    stamped_outcome = fallback_agent_outcome
                if role == "agent" and stamped_outcome is not None:
                    display_msg["outcome"] = stamped_outcome
                if role == "agent":
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
        "session_path_resolved": str(session_dir.resolve()),
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "detail_json_path_resolved": (
            str((turns_dir / latest_turn_id / "response.json").resolve())
            if latest_turn_id
            else None
        ),
        "messages": display_messages,
        "latest_candidate": _latest_session_candidate_payload(session_dir, turn_ids),
    }


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
            "session_path_resolved": str(session_dir.resolve()),
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
            "session_path_resolved": str(session_dir.resolve()),
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


__all__ = [
    "_BUNDLE_MAX_FILE_BYTES",
    "_BUNDLE_MAX_TOTAL_BYTES",
    "_BUNDLE_TEXT_SUFFIXES",
    "_conversation_with_candidate_reference",
    "read_session_bundle",
    "read_session_chat",
    "read_session_json",
]
