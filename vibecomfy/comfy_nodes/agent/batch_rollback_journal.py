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
import stat
import sys
import uuid
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


class SnapshotCaptureError(RuntimeError):
    """Raised when the loop-entry snapshot cannot be captured safely."""


class UnsafeJournalPathError(OSError):
    """Raised when a journal path is symlinked or outside its authorized root."""


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
    restore_results: dict[str, bool] | None = None


def snapshot_file(path: Path | None, *, root: Path | None = None) -> FileSnapshot:
    if path is None:
        return FileSnapshot(existed=False)
    try:
        if root is None:
            root = path.parent
        safe_path, parent_fd, name = _open_parent_dir(path, root=root)
        try:
            try:
                fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent_fd)
            except FileNotFoundError:
                return FileSnapshot(existed=False)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise SnapshotCaptureError(f"journal snapshot is not a regular file: {safe_path}")
                data = bytearray()
                while chunk := os.read(fd, 1024 * 1024):
                    data.extend(chunk)
                return FileSnapshot(existed=True, data=bytes(data))
            finally:
                os.close(fd)
        finally:
            os.close(parent_fd)
    except SnapshotCaptureError:
        raise
    except UnsafeJournalPathError as exc:
        raise SnapshotCaptureError(str(exc)) from exc
    except OSError as exc:
        raise SnapshotCaptureError(f"could not capture journal snapshot: {path}") from exc


_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_ALLOWED_PLATFORM_ALIASES = {
    "/var": "/private/var",
    "/tmp": "/private/tmp",
} if sys.platform == "darwin" else {}


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise UnsafeJournalPathError(f"could not validate journal path: {path}") from exc
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _trusted_root(root: Path) -> tuple[Path, Path, tuple[int, int]]:
    lexical = Path(os.path.abspath(root))
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        if not _is_reparse_or_symlink(current):
            continue
        expected = _ALLOWED_PLATFORM_ALIASES.get(str(current))
        if expected is None or os.path.realpath(current) != expected:
            raise UnsafeJournalPathError(f"journal root contains an unauthorized link: {current}")
    if not lexical.is_dir():
        raise UnsafeJournalPathError(f"journal root is not an existing directory: {lexical}")
    canonical = Path(os.path.realpath(lexical))
    try:
        root_stat = os.stat(canonical, follow_symlinks=False)
    except OSError as exc:
        raise UnsafeJournalPathError(f"could not verify journal root: {canonical}") from exc
    if not stat.S_ISDIR(root_stat.st_mode):
        raise UnsafeJournalPathError(f"journal root is not a directory: {canonical}")
    return lexical, canonical, (root_stat.st_dev, root_stat.st_ino)


def _journal_component_identity(path: Path) -> tuple[int, int] | None:
    try:
        component_stat = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise UnsafeJournalPathError(f"could not verify journal path component: {path}") from exc
    if not stat.S_ISDIR(component_stat.st_mode):
        raise UnsafeJournalPathError(f"journal path component is not a directory: {path}")
    return component_stat.st_dev, component_stat.st_ino


def _open_parent_dir(path: Path, *, root: Path) -> tuple[Path, int, str]:
    lexical_root, canonical_root, expected_root = _trusted_root(root)
    path_lexical = Path(os.path.abspath(path if path.is_absolute() else lexical_root / path))
    try:
        relative = path_lexical.relative_to(lexical_root)
    except ValueError as exc:
        raise UnsafeJournalPathError(f"journal path escapes its authorized root: {path_lexical}") from exc
    if not relative.parts:
        raise UnsafeJournalPathError(f"journal path is a directory, not a file: {path_lexical}")
    current = lexical_root
    expected_components: list[tuple[str, tuple[int, int] | None]] = []
    for part in relative.parts:
            current /= part
            if _is_reparse_or_symlink(current):
                raise UnsafeJournalPathError(f"journal path contains an unauthorized symlink/junction: {current}")
            if part != relative.parts[-1]:
                expected_components.append((part, _journal_component_identity(current)))
    if os.name != "posix" or not _NOFOLLOW or not _DIRECTORY or os.open not in os.supports_dir_fd:
        raise UnsafeJournalPathError("race-resistant journal paths are unsupported on this platform")
    parent_fd = os.open(canonical_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
    try:
        opened_root = os.fstat(parent_fd)
        if (opened_root.st_dev, opened_root.st_ino) != expected_root:
            raise UnsafeJournalPathError(f"journal root was replaced during validation: {canonical_root}")
        for part, expected_component in expected_components:
            next_fd = os.open(part, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=parent_fd)
            if expected_component is not None:
                opened_component = os.fstat(next_fd)
                actual_component = (opened_component.st_dev, opened_component.st_ino)
                if actual_component != expected_component:
                    os.close(next_fd)
                    raise UnsafeJournalPathError(
                        f"journal path component was replaced during validation: {part}"
                    )
            os.close(parent_fd)
            parent_fd = next_fd
        return canonical_root / relative, parent_fd, relative.parts[-1]
    except BaseException:
        os.close(parent_fd)
        raise


def _validate_journal_path(path: Path, *, root: Path | None = None) -> Path:
    if root is None:
        root = path.parent
    lexical_root, canonical_root, _expected_root = _trusted_root(root)
    path_lexical = Path(os.path.abspath(path if path.is_absolute() else lexical_root / path))
    try:
        relative = path_lexical.relative_to(lexical_root)
    except ValueError as exc:
        raise UnsafeJournalPathError(f"journal path escapes its authorized root: {path_lexical}") from exc
    if not relative.parts:
        raise UnsafeJournalPathError(f"journal path is a directory, not a file: {path_lexical}")
    current = lexical_root
    for part in relative.parts:
        current /= part
        if _is_reparse_or_symlink(current):
            raise UnsafeJournalPathError(f"journal path contains an unauthorized symlink/junction: {current}")
    return canonical_root / relative


def _atomic_restore_file(path: Path, data: bytes, *, root: Path) -> None:
    safe_path, parent_fd, name = _open_parent_dir(path, root=root)
    temp_name = f".{name}.{uuid.uuid4().hex}.restore-tmp"
    fd = -1
    try:
        fd = os.open(temp_name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _NOFOLLOW, 0o600, dir_fd=parent_fd)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
        verify_fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent_fd)
        try:
            if os.read(verify_fd, len(data) + 1) != data:
                raise OSError(f"restored bytes differ from snapshot: {safe_path}")
        finally:
            os.close(verify_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)


def restore_file(path: Path | None, snapshot: FileSnapshot, *, root: Path | None = None) -> bool:
    if path is None:
        return True
    if not snapshot.existed:
        try:
            if root is None:
                root = path.parent
            _safe_path, parent_fd, name = _open_parent_dir(path, root=root)
            try:
                try:
                    os.unlink(name, dir_fd=parent_fd)
                except FileNotFoundError:
                    return True
                os.fsync(parent_fd)
                try:
                    os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    return True
                return False
            finally:
                os.close(parent_fd)
        except OSError:
            LOGGER.debug("journal unlink failed for %s", path, exc_info=True)
            return False
    try:
        if root is None:
            root = path.parent
        expected = snapshot.data if snapshot.data is not None else b""
        _atomic_restore_file(path, expected, root=root)
        return True
    except OSError:
        LOGGER.debug("journal restore-write failed for %s", path, exc_info=True)
        return False


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
    root = getattr(state, "turn_dir", None)
    files = {
        attr: snapshot_file(getattr(state, attr, None), root=root)
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


def restore_loop_entry_journal(session: Any, state: Any, journal: LoopEntryJournal) -> dict[str, bool]:
    session._restore_snapshot(journal.session_snapshot)
    for name, value in journal.state_snapshot.items():
        setattr(state, name, _copy_state_value(value))
    results: dict[str, bool] = {}
    root = getattr(state, "turn_dir", None)
    for attr, file_snapshot in journal.files.items():
        results[attr] = restore_file(getattr(state, attr, None), file_snapshot, root=root)
    journal.restore_results = results
    journal.restored = all(results.values())
    return results


def build_abort_diagnostic(
    journal: LoopEntryJournal,
    exc: BaseException,
    *,
    context: Any | None = None,
    fault_point: str | None = None,
    restore_results: Mapping[str, bool] | None = None,
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
    results = dict(restore_results if restore_results is not None else journal.restore_results or {})
    restored = journal.restored if results else True
    diagnostic: dict[str, Any] = {
        "contract_version": ABORT_CONTRACT_VERSION,
        "code": ABORT_DIAGNOSTIC_CODE,
        "status": ABORT_STATUS,
        "session_id": session_id,
        "turn_id": turn_id,
        "turn_number": journal.turn_number,
        "fault_point": point,
        "error_type": type(exc).__name__,
        "error": message,
        "restored": restored,
        "committed": False,
    }
    if not restored:
        failed_files = sorted(attr for attr, ok in results.items() if not ok)
        diagnostic.update(
            {
                "recovery_required": True,
                "recovery_blocker": {
                    "code": "batch_restore_incomplete",
                    "failed_files": failed_files,
                },
                "next_action": (
                    "Manual recovery required: restore the listed turn files before retrying."
                ),
            }
        )
    return diagnostic


def _reconcile_aborted_turn_evidence(state: Any, journal: LoopEntryJournal, diagnostic: Mapping[str, Any]) -> None:
    records = getattr(state, "batch_aborted_turns", ()) or ()
    for record in reversed(records):
        if not isinstance(record, dict) or record.get("turn_number") != journal.turn_number:
            continue
        restored = bool(diagnostic.get("restored"))
        record["rolled_back"] = restored
        record["restored"] = restored
        record["recovery_required"] = bool(diagnostic.get("recovery_required"))
        abort = record.get("abort")
        if isinstance(abort, dict):
            abort["restored"] = restored
            abort["recovery_required"] = bool(diagnostic.get("recovery_required"))
            for field in ("recovery_blocker", "next_action"):
                if field in diagnostic:
                    abort[field] = diagnostic[field]
        return


def persist_abort_diagnostic(state: Any, diagnostic: Mapping[str, Any]) -> Path | None:
    turn_dir = getattr(state, "turn_dir", None)
    if turn_dir is None:
        return None
    try:
        root = _validate_journal_path(Path(turn_dir))
        path = _validate_journal_path(root / ABORT_DIAGNOSTIC_NAME, root=root)
    except OSError:
        LOGGER.debug("unsafe abort diagnostic path at %s", turn_dir, exc_info=True)
        return None
    try:
        _write_json_atomic(path, diagnostic)
    except OSError:
        LOGGER.debug("failed to persist abort diagnostic at %s", path, exc_info=True)
        return None
    return path


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    root = path.parent
    path = _validate_journal_path(path, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_path, parent_fd, name = _open_parent_dir(path, root=root)
    temp_name = f".{name}.{uuid.uuid4().hex}.tmp"
    fd = -1
    try:
        fd = os.open(temp_name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _NOFOLLOW, 0o600, dir_fd=parent_fd)
        data = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)


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
                        "restored": bool(diagnostic.get("restored")),
                        "committed": False,
                    }
                    for field in ("recovery_required", "recovery_blocker", "next_action"):
                        if field in diagnostic:
                            record["abort"][field] = diagnostic[field]
                    if record.get("candidate_graph_hash") is None and record.get("state") in {
                        "candidate",
                        "submitted",
                    }:
                        record["state"] = "no_candidate"
                    write_state_atomic(Path(session_dir), session_state)
        if turn_dir is not None:
            root = _validate_journal_path(Path(turn_dir))
            response_path = _validate_journal_path(root / "response.json", root=root)
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
    restore_results = restore_loop_entry_journal(session, state, journal)
    diagnostic = build_abort_diagnostic(
        journal,
        exc,
        context=context,
        fault_point=fault_point,
        restore_results=restore_results,
    )
    _reconcile_aborted_turn_evidence(state, journal, diagnostic)
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
                "rolled_back": bool(diagnostic.get("restored")),
                "committed": False,
                "recovery_required": bool(diagnostic.get("recovery_required")),
            }
            for field in ("recovery_blocker", "next_action"):
                if field in diagnostic:
                    abort_record[field] = diagnostic[field]
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
    "SnapshotCaptureError",
    "UnsafeJournalPathError",
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
