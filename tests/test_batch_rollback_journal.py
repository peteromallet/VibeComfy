from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.comfy_nodes.agent import batch_rollback_journal as journal


class _Session:
    def _restore_snapshot(self, snapshot):
        self.restored_snapshot = snapshot


def _journal_for(path: Path, snapshot: journal.FileSnapshot) -> journal.LoopEntryJournal:
    return journal.LoopEntryJournal(
        session_snapshot={"session": "before"},
        state_snapshot={},
        files={"after_py_path": snapshot},
        turn_number=1,
    )


def test_restore_loop_entry_journal_reports_failed_write_and_blocks_restored_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "after.py"
    path.write_bytes(b"partial")
    entry = _journal_for(path, journal.FileSnapshot(existed=True, data=b"before"))
    state = SimpleNamespace(after_py_path=path)

    def fail_fsync(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", fail_fsync)
    results = journal.restore_loop_entry_journal(_Session(), state, entry)
    diagnostic = journal.build_abort_diagnostic(entry, RuntimeError("apply failed"), restore_results=results)

    assert results == {"after_py_path": False}
    assert entry.restore_results == results
    assert entry.restored is False
    assert diagnostic["restored"] is False
    assert diagnostic["recovery_required"] is True
    assert diagnostic["recovery_blocker"] == {
        "code": "batch_restore_incomplete",
        "failed_files": ["after_py_path"],
    }
    assert "Manual recovery required" in diagnostic["next_action"]
    assert not list(tmp_path.glob(".*.restore-*"))


def test_restore_file_verifies_bytes_after_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "candidate.json"
    path.write_bytes(b"partial")
    real_read = os.read

    def read_wrong_bytes(fd: int, size: int) -> bytes:
        if size == len(b"before") + 1:
            return b"wrong"
        return real_read(fd, size)

    monkeypatch.setattr(os, "read", read_wrong_bytes)
    assert journal.restore_file(path, journal.FileSnapshot(existed=True, data=b"before")) is False
    assert path.read_bytes() == b"before"


def test_restore_file_reports_failed_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "new-file"
    path.write_bytes(b"new")

    def fail_unlink(path, *, dir_fd=None) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(os, "unlink", fail_unlink)
    assert journal.restore_file(path, journal.FileSnapshot(existed=False)) is False
    assert path.exists()


def test_snapshot_capture_failure_is_distinct_and_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "original.py"
    path.write_bytes(b"ORIGINAL")

    def fail_read(fd: int, size: int) -> bytes:
        raise OSError("unreadable")

    monkeypatch.setattr(os, "read", fail_read)
    with pytest.raises(journal.SnapshotCaptureError, match="could not capture"):
        journal.snapshot_file(path)
    assert path.exists()


def test_snapshot_capture_rejects_symlink_and_noncontained_path(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"KEEP")
    (root / "after.py").symlink_to(outside)
    with pytest.raises(journal.SnapshotCaptureError, match="symlink"):
        journal.snapshot_file(root / "after.py", root=root)
    with pytest.raises(journal.SnapshotCaptureError, match="escapes"):
        journal.snapshot_file(outside, root=root)
    assert outside.read_bytes() == b"KEEP"


def test_restore_rejects_symlink_final_and_parent_without_touching_external_target(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.write_bytes(b"KEEP")
    root = tmp_path / "turn"
    root.mkdir()
    final_link = root / "after.py"
    final_link.symlink_to(outside)
    assert journal.restore_file(
        final_link,
        journal.FileSnapshot(existed=True, data=b"ORIGINAL"),
        root=root,
    ) is False
    assert outside.read_bytes() == b"KEEP"
    assert final_link.is_symlink()

    parent = tmp_path / "external-parent"
    parent.mkdir()
    parent_file = parent / "candidate.json"
    parent_file.write_bytes(b"KEEP-PARENT")
    parent_link = root / "linked-parent"
    parent_link.symlink_to(parent, target_is_directory=True)
    assert journal.restore_file(
        parent_link / "candidate.json",
        journal.FileSnapshot(existed=True, data=b"ORIGINAL"),
        root=root,
    ) is False
    assert parent_file.read_bytes() == b"KEEP-PARENT"


def test_restore_rejects_nested_ancestor_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    target = outside / "a" / "turn" / "after.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"KEEP")
    link = tmp_path / "linked-root"
    link.symlink_to(outside, target_is_directory=True)
    assert journal.restore_file(
        link / "a" / "turn" / "after.py",
        journal.FileSnapshot(existed=True, data=b"CHANGED"),
        root=link / "a" / "turn",
    ) is False
    assert target.read_bytes() == b"KEEP"


def test_restore_replace_uses_authorized_directory_fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "after.py"
    path.write_bytes(b"old")
    replace_calls: list[tuple[object, object, dict[str, object]]] = []
    real_replace = os.replace

    def capture_replace(source, destination, **kwargs):
        replace_calls.append((source, destination, kwargs))
        return real_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", capture_replace)
    assert journal.restore_file(path, journal.FileSnapshot(existed=True, data=b"new")) is True
    assert replace_calls
    source, destination, kwargs = replace_calls[0]
    assert isinstance(source, str) and source.startswith(".after.py.")
    assert destination == "after.py"
    assert kwargs["src_dir_fd"] == kwargs["dst_dir_fd"]


def test_restore_fails_closed_when_parent_is_swapped_after_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "turn"
    nested = root / "nested"
    nested.mkdir(parents=True)
    path = nested / "after.py"
    path.write_bytes(b"KEEP-IN-ROOT")
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "after.py"
    external.write_bytes(b"KEEP-EXTERNAL")

    real_open = os.open
    swapped = False

    def swap_before_parent_open(name, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and name == "nested" and dir_fd is not None:
            swapped = True
            nested.rename(root / "nested-original")
            nested.symlink_to(outside, target_is_directory=True)
        return real_open(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap_before_parent_open)
    assert journal.restore_file(
        path,
        journal.FileSnapshot(existed=True, data=b"CHANGED"),
        root=root,
    ) is False
    assert external.read_bytes() == b"KEEP-EXTERNAL"


def test_restore_fails_closed_when_root_directory_is_replaced_after_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "turn"
    root.mkdir()
    path = root / "after.py"
    path.write_bytes(b"KEEP-AUTHORIZED")
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    replacement_file = replacement / "after.py"
    replacement_file.write_bytes(b"KEEP-REPLACEMENT")

    swapped = False

    real_trusted_root = journal._trusted_root

    def swap_after_root_validation(path: Path):
        nonlocal swapped
        result = real_trusted_root(path)
        if not swapped:
            swapped = True
            root.rename(tmp_path / "turn-original")
            replacement.rename(root)
        return result

    monkeypatch.setattr(journal, "_trusted_root", swap_after_root_validation)
    assert journal.restore_file(
        path,
        journal.FileSnapshot(existed=True, data=b"CHANGED"),
        root=root,
    ) is False
    assert (root / "after.py").read_bytes() == b"KEEP-REPLACEMENT"


def test_restore_fails_closed_when_nested_directory_is_replaced_after_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "turn"
    nested = root / "nested"
    nested.mkdir(parents=True)
    path = nested / "after.py"
    path.write_bytes(b"KEEP-AUTHORIZED")
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    replacement_file = replacement / "after.py"
    replacement_file.write_bytes(b"KEEP-REPLACEMENT")

    real_component_identity = journal._journal_component_identity
    swapped = False

    def swap_after_component_validation(path: Path):
        nonlocal swapped
        result = real_component_identity(path)
        if path == nested and not swapped:
            swapped = True
            nested.rename(root / "nested-original")
            replacement.rename(nested)
        return result

    monkeypatch.setattr(journal, "_journal_component_identity", swap_after_component_validation)
    assert journal.restore_file(
        path,
        journal.FileSnapshot(existed=True, data=b"CHANGED"),
        root=root,
    ) is False
    assert (nested / "after.py").read_bytes() == b"KEEP-REPLACEMENT"


def test_abort_diagnostic_rejects_symlinked_turn_path(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.write_text("KEEP", encoding="utf-8")
    turn = tmp_path / "turn"
    turn.mkdir()
    (turn / "abort.json").symlink_to(outside)
    state = SimpleNamespace(turn_dir=turn)
    assert journal.persist_abort_diagnostic(state, {"status": "aborted"}) is None
    assert outside.read_text(encoding="utf-8") == "KEEP"


def test_abort_evidence_reconciles_rollback_truth_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = journal.LoopEntryJournal({}, {}, {}, 4)
    state = SimpleNamespace(
        batch_aborted_turns=[
            {
                "turn_number": 4,
                "rolled_back": True,
                "abort": {"code": "unexpected_batch_exception"},
            }
        ]
    )
    monkeypatch.setattr(journal, "restore_loop_entry_journal", lambda *args: {"after_py_path": False})
    monkeypatch.setattr(journal, "persist_abort_diagnostic", lambda *args: None)
    monkeypatch.setattr(journal, "close_allocated_turn_as_aborted", lambda **kwargs: None)
    result = journal.abort_journaled_batch(
        session=object(),
        state=state,
        journal=entry,
        exc=RuntimeError("apply failed"),
        context=SimpleNamespace(session_id="s", turn_id="t"),
    )
    assert result["restored"] is False
    assert state.batch_aborted_turns[0]["rolled_back"] is False
    assert state.batch_aborted_turns[0]["restored"] is False
    assert state.batch_aborted_turns[0]["recovery_required"] is True
    assert state.batch_aborted_turns[0]["abort"]["restored"] is False


def test_abort_journaled_batch_propagates_recovery_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = journal.LoopEntryJournal({}, {}, {}, 1)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        journal,
        "restore_loop_entry_journal",
        lambda session, state, journal_entry: {"after_py_path": False},
    )
    monkeypatch.setattr(journal, "persist_abort_diagnostic", lambda state, diagnostic: None)
    monkeypatch.setattr(
        journal,
        "close_allocated_turn_as_aborted",
        lambda *, state, context, diagnostic: captured.update(diagnostic),
    )

    diagnostic = journal.abort_journaled_batch(
        session=object(),
        state=object(),
        journal=entry,
        exc=RuntimeError("apply failed"),
        context=SimpleNamespace(session_id="s", turn_id="t"),
    )

    assert diagnostic["restored"] is False
    assert diagnostic["recovery_required"] is True
    assert captured["restored"] is False
    assert captured["recovery_required"] is True
