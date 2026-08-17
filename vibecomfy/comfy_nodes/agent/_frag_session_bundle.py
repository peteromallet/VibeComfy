"""
Session bundle / issue-report helpers (T-038 extraction of the edit_session_bundle fragment).

Extracted from the edit.py exec-assembled fragments (T-038, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Imports of sibling _frag modules follow
the foundation dependency order; names that would form an import cycle are
resolved lazily at call time (marked with a T-038 late import comment).
"""
import base64
import json
import os
from pathlib import Path
from typing import Any, Mapping
from vibecomfy.comfy_nodes.agent.session import session_dir_for
from ._frag_chat import _BUNDLE_MAX_FILE_BYTES, _BUNDLE_MAX_TOTAL_BYTES, _BUNDLE_TEXT_SUFFIXES, _json_safe
from ._frag_state import LOGGER, _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS, _WARNED_LEGACY_CONTRACTS, _safe_session_id

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


def _compact_diag_to_dict(diagnostic: Any) -> dict[str, Any]:
    if isinstance(diagnostic, Mapping):
        # CompactDiagnostic-shaped dicts (e.g. re-hydrated turn records) must
        # compact to the same shape as the dataclass path below; getattr-based
        # access would otherwise collapse every dict into code="dict".
        return {
            "code": diagnostic.get("code") or type(diagnostic).__name__,
            "message": diagnostic.get("message") or str(diagnostic),
            "severity": diagnostic.get("severity") or "error",
            "detail": _json_safe(diagnostic.get("detail") or {}),
            "teaching_hint": diagnostic.get("teaching_hint"),
        }
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


def _warn_legacy_contract_once(contract: str) -> None:
    if contract in _WARNED_LEGACY_CONTRACTS:
        return
    _WARNED_LEGACY_CONTRACTS.add(contract)
    LOGGER.warning(
        "agent-edit legacy contract '%s' selected via VIBECOMFY_AGENT_EDIT_LEGACY; "
        "this is deprecated and will be removed",
        contract,
    )


def _warn_ignored_public_protocol_envs_once(env_names: tuple[str, ...]) -> None:
    unseen = tuple(name for name in env_names if name not in _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS)
    if not unseen:
        return
    _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS.update(unseen)
    LOGGER.warning(
        "agent-edit ignoring legacy public protocol env vars (%s); product protocol is always "
        "'batch_repl'.",
        ", ".join(unseen),
    )


def _agent_edit_contract() -> str:
    ignored_public_envs = tuple(
        name
        for name in (
            "VIBECOMFY_AGENT_EDIT_LEGACY",
            "VIBECOMFY_AGENT_EDIT_V2",
            "VIBECOMFY_AGENT_EDIT_BATCH_REPL",
            "VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS",
            "VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL",
        )
        if os.getenv(name) is not None
    )
    if ignored_public_envs:
        _warn_ignored_public_protocol_envs_once(ignored_public_envs)
    return "batch_repl"


def _agent_edit_batch_repl_enabled() -> bool:
    return True


def _edit_lint_enabled() -> bool:
    """Return True unless VIBECOMFY_AGENT_EDIT_LINT is explicitly disabled.

    Accepts ``0``, ``false``, ``off``, or ``no`` (case-insensitive) as disabled
    values.  Defaults to ON (enabled) when the env var is unset or set to any
    other value.

    Rollout flag / off-switch
    -------------------------
    Setting ``VIBECOMFY_AGENT_EDIT_LINT=0`` disables the entire lint gate in
    ``_stage_agent_batch_repl``.  When lint is off the
    pipeline sends every op straight to ``interpret``: no-ops are not
    pre-filtered, and diagnostics come from interpret / the emit-exit guard
    rather than from ``lint_delta()``.  This flag is intended as an emergency
    off-switch; the default path is *enabled*.
    """
    raw = os.getenv("VIBECOMFY_AGENT_EDIT_LINT")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "off", "no"}


__all__ = (
     "_agent_edit_batch_repl_enabled", "_agent_edit_contract",
     "_compact_diag_to_dict", "_edit_lint_enabled", "_port_issue_to_dict",
     "_warn_ignored_public_protocol_envs_once", "_warn_legacy_contract_once",
     "read_session_bundle", "read_session_json",
)
