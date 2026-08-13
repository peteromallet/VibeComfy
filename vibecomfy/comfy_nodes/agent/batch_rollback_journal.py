"""Loop-entry journal for one model-authored batch.

Captures exact pre-batch session/state/file bytes at the start of a batch-REPL
turn. On an unexpected exception after mutation starts, restores that snapshot,
closes the allocated durable turn as aborted, persists a bounded abort
diagnostic, and emits an abort telemetry marker. No repair, retry, or fingerprint.
"""

from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

LOGGER = logging.getLogger(__name__)

ABORT_CONTRACT_VERSION = "batch_repl_abort_v1"
ABORT_DIAGNOSTIC_CODE = "unexpected_batch_exception"
ABORT_STATUS = "aborted"
ABORT_DIAGNOSTIC_NAME = "abort.json"
_ERROR_MESSAGE_LIMIT = 500
_BATCH_STATE_FIELDS: tuple[str, ...] = (
    "ui_payload",
    "python_after",
    "batch_turns",
    "batch_field_changes",
    "batch_noop_field_changes",
    "lint_noop_messages",
    "batch_budget_state",
    "batch_turn_count",
    "batch_feedback",
    "batch_exit_mode",
    "batch_done_summary",
    "batch_final_summary",
    "user_message",
    "report",
    "artifacts",
    "revision_evidence",
    "revision_evidence_payload",
    "provider_metadata",
    "raw_executor_message",
    "plan_evaluation",
)
_JOURNALED_FILE_ATTRS: tuple[str, ...] = (
    "after_py_path",
    "candidate_ui_path",
    "model_request_path",
    "model_response_path",
    "messages_path",
    "revision_evidence_path",
)

# Test/oracle hook. Set to a callable ``(point: str) -> None`` that may raise.
BATCH_FAULT_INJECTOR: Callable[[str], None] | None = None


class InjectedBatchFault(RuntimeError):
    """Raised by the test/oracle fault injector at a named journal point."""

    def __init__(self, point: str) -> None:
        super().__init__(f"injected fault after {point}")
        self.fault_point = point


def maybe_inject_batch_fault(point: str) -> None:
    injector = BATCH_FAULT_INJECTOR
    if injector is not None:
        injector(point)


@dataclass(frozen=True)
class FileSnapshot:
    existed: bool
    data: bytes | None = None


@dataclass
class LoopEntryJournal:
    """Exact loop-entry snapshot for one model-authored batch."""

    session_snapshot: dict[str, Any]
    state_snapshot: dict[str, Any]
    files: dict[str, FileSnapshot]
    turn_number: int
    session_id: str | None = None
    turn_id: str | None = None
    fault_point: str | None = None
    restored: bool = False


def snapshot_file(path: Path | None) -> FileSnapshot:
    if path is None:
        return FileSnapshot(existed=False)
    try:
        if not path.exists():
            return FileSnapshot(existed=False)
    except OSError:
        return FileSnapshot(existed=False)
    try:
        return FileSnapshot(existed=True, data=path.read_bytes())
    except OSError:
        return FileSnapshot(existed=False)


def restore_file(path: Path | None, snapshot: FileSnapshot) -> None:
    if path is None:
        return
    if not snapshot.existed:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            LOGGER.debug("journal unlink failed for %s", path, exc_info=True)
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(snapshot.data if snapshot.data is not None else b"")
    except OSError:
        LOGGER.debug("journal restore-write failed for %s", path, exc_info=True)


def _copy_state_value(value: Any) -> Any:
    """Copy restoreable state without failing on MappingProxyType or similar."""
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, MappingProxyType):
        return {key: _copy_state_value(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: _copy_state_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_state_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_state_value(item) for item in value)
    if isinstance(value, set):
        return {_copy_state_value(item) for item in value}
    try:
        return deepcopy(value)
    except Exception:
        return value


def capture_loop_entry_journal(
    session: Any,
    state: Any,
    *,
    turn_number: int,
    context: Any | None = None,
) -> LoopEntryJournal:
    session_snapshot = session._snapshot_mutable_state()
    state_snapshot = {
        name: _copy_state_value(getattr(state, name, None)) for name in _BATCH_STATE_FIELDS
    }
    files = {
        attr: snapshot_file(getattr(state, attr, None))
        for attr in _JOURNALED_FILE_ATTRS
    }
    return LoopEntryJournal(
        session_snapshot=session_snapshot,
        state_snapshot=state_snapshot,
        files=files,
        turn_number=turn_number,
        session_id=getattr(context, "session_id", None),
        turn_id=getattr(context, "turn_id", None),
    )


def restore_loop_entry_journal(session: Any, state: Any, journal: LoopEntryJournal) -> None:
    session._restore_snapshot(journal.session_snapshot)
    for name, value in journal.state_snapshot.items():
        setattr(state, name, _copy_state_value(value))
    for attr, file_snapshot in journal.files.items():
        restore_file(getattr(state, attr, None), file_snapshot)
    journal.restored = True


def build_abort_diagnostic(
    journal: LoopEntryJournal,
    exc: BaseException,
    *,
    context: Any | None = None,
    fault_point: str | None = None,
) -> dict[str, Any]:
    message = str(exc)
    if len(message) > _ERROR_MESSAGE_LIMIT:
        message = message[:_ERROR_MESSAGE_LIMIT]
    point = fault_point or journal.fault_point or getattr(exc, "fault_point", None)
    session_id = journal.session_id
    turn_id = journal.turn_id
    if context is not None:
        session_id = getattr(context, "session_id", session_id)
        turn_id = getattr(context, "turn_id", turn_id)
    return {
        "contract_version": ABORT_CONTRACT_VERSION,
        "code": ABORT_DIAGNOSTIC_CODE,
        "status": ABORT_STATUS,
        "session_id": session_id,
        "turn_id": turn_id,
        "turn_number": journal.turn_number,
        "fault_point": point,
        "error_type": type(exc).__name__,
        "error": message,
        "restored": True,
        "committed": False,
    }


def persist_abort_diagnostic(state: Any, diagnostic: Mapping[str, Any]) -> Path | None:
    turn_dir = getattr(state, "turn_dir", None)
    if turn_dir is None:
        return None
    path = Path(turn_dir) / ABORT_DIAGNOSTIC_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(dict(diagnostic), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        LOGGER.debug("failed to persist abort diagnostic at %s", path, exc_info=True)
        return None
    return path


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def close_allocated_turn_as_aborted(
    *,
    state: Any,
    context: Any,
    diagnostic: Mapping[str, Any],
) -> None:
    """Record the allocated durable turn so it is not left unrecorded."""
    session_dir = getattr(state, "session_dir", None)
    turn_dir = getattr(state, "turn_dir", None)
    turn_id = getattr(context, "turn_id", None)
    if session_dir is None or turn_id is None:
        return
    try:
        from vibecomfy.comfy_nodes.agent.session import (
            SessionStateLock,
            read_state,
            write_state_atomic,
        )

        with SessionStateLock(Path(session_dir)):
            session_state = read_state(Path(session_dir))
            turns = session_state.get("turns")
            if isinstance(turns, dict):
                record = turns.get(turn_id)
                if isinstance(record, dict):
                    record["abort"] = {
                        "status": ABORT_STATUS,
                        "code": ABORT_DIAGNOSTIC_CODE,
                        "restored": True,
                        "committed": False,
                    }
                    if record.get("candidate_graph_hash") is None and record.get("state") in {
                        "candidate",
                        "submitted",
                    }:
                        record["state"] = "no_candidate"
                    write_state_atomic(Path(session_dir), session_state)
        if turn_dir is not None:
            response_path = Path(turn_dir) / "response.json"
            if not response_path.exists():
                _write_json_atomic(
                    response_path,
                    {
                        "ok": False,
                        "status": ABORT_STATUS,
                        "kind": ABORT_DIAGNOSTIC_CODE,
                        "canvas_apply_allowed": False,
                        "apply_allowed": False,
                        "queue_allowed": False,
                        "session_id": getattr(context, "session_id", None),
                        "turn_id": turn_id,
                        "abort": dict(diagnostic),
                    },
                )
    except Exception:
        LOGGER.debug("failed to close allocated turn as aborted", exc_info=True)


def abort_journaled_batch(
    *,
    session: Any,
    state: Any,
    journal: LoopEntryJournal,
    exc: BaseException,
    context: Any,
    client_id: str | None = None,
    emit_turn_event: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Restore loop-entry state, persist abort evidence, and emit an abort marker."""
    fault_point = getattr(exc, "fault_point", None)
    restore_loop_entry_journal(session, state, journal)
    diagnostic = build_abort_diagnostic(
        journal, exc, context=context, fault_point=fault_point
    )
    persist_abort_diagnostic(state, diagnostic)
    close_allocated_turn_as_aborted(state=state, context=context, diagnostic=diagnostic)
    if emit_turn_event is not None:
        try:
            from vibecomfy.comfy_nodes.agent import _frag_entrypoint as entry

            discarded = entry.discard_turn_event_buffer()
            abort_record = {
                "turn_number": journal.turn_number,
                "batch_ok": False,
                "statement_count": 0,
                "landed_op_count": 0,
                "diagnostics": [
                    {
                        "code": ABORT_DIAGNOSTIC_CODE,
                        "message": diagnostic.get("error") or ABORT_STATUS,
                    }
                ],
                "discarded_buffered_events": discarded,
                "rolled_back": True,
            }
            emit_turn_event(
                state,
                context,
                abort_record,
                client_id=client_id,
                status=ABORT_STATUS,
            )
        except Exception:
            LOGGER.debug("failed to emit abort turn event", exc_info=True)
    return diagnostic


__all__ = [
    "ABORT_CONTRACT_VERSION",
    "ABORT_DIAGNOSTIC_CODE",
    "ABORT_DIAGNOSTIC_NAME",
    "ABORT_STATUS",
    "BATCH_FAULT_INJECTOR",
    "FileSnapshot",
    "InjectedBatchFault",
    "LoopEntryJournal",
    "abort_journaled_batch",
    "build_abort_diagnostic",
    "capture_loop_entry_journal",
    "close_allocated_turn_as_aborted",
    "maybe_inject_batch_fault",
    "persist_abort_diagnostic",
    "restore_file",
    "restore_loop_entry_journal",
    "snapshot_file",
]
