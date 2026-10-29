from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import vibecomfy.workflow_bundle as bundle


def _windows_os(monkeypatch):
    """Simulate the Windows CRT without changing the host's pathlib behavior."""
    proxy = SimpleNamespace(**vars(os))
    directory_opens = []
    file_fsyncs = []

    def windows_open(path, flags, *args, **kwargs):
        if Path(path).is_dir():
            directory_opens.append(path)
            raise PermissionError(errno.EACCES, "cannot open directory", str(path))
        return os.open(path, flags, *args, **kwargs)

    def windows_rename(source, destination):
        if Path(destination).exists():
            raise FileExistsError(errno.EEXIST, "destination exists", str(destination))
        return os.rename(source, destination)

    def record_fsync(fd):
        file_fsyncs.append(fd)
        return os.fsync(fd)

    proxy.name = "nt"
    proxy.open = windows_open
    proxy.rename = windows_rename
    proxy.fsync = record_fsync
    monkeypatch.setattr(bundle, "os", proxy)
    return directory_opens, file_fsyncs


def test_windows_journal_replaces_existing_file_and_flushes_file(tmp_path, monkeypatch):
    directory_opens, file_fsyncs = _windows_os(monkeypatch)
    path = tmp_path / "workflow.py"
    for state in ("prepared", "publishing", "committed"):
        bundle._write_publish_transaction(path, {"version": 1, "state": state})
        assert json.loads(bundle._publish_transaction_path(path).read_text()) == {
            "version": 1, "state": state,
        }
    assert directory_opens == []
    assert len(file_fsyncs) == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_import_succeeds_with_windows_directory_open_denied(tmp_path, monkeypatch):
    from vibecomfy.porting.import_service import import_workflow_bytes

    monkeypatch.chdir(tmp_path)
    directory_opens, file_fsyncs = _windows_os(monkeypatch)
    source = json.dumps({"nodes": [{"id": 1, "type": "KSampler", "inputs": [], "widgets_values": []}]}).encode()
    artifacts = import_workflow_bytes(source, workflow_id="windows-import")
    assert artifacts.source_bytes == source
    assert artifacts.python_bytes and artifacts.companion_bytes
    assert json.loads(artifacts.companion_bytes)["format_version"] == 2
    assert directory_opens == []
    assert file_fsyncs


def test_posix_directory_open_failure_propagates(tmp_path, monkeypatch):
    proxy = SimpleNamespace(**vars(os))
    proxy.name = "posix"
    def denied(path, flags, *args, **kwargs):
        if Path(path).is_dir():
            raise PermissionError(errno.EACCES, "directory denied", str(path))
        return os.open(path, flags, *args, **kwargs)
    proxy.open = denied
    monkeypatch.setattr(bundle, "os", proxy)
    with pytest.raises(PermissionError, match="directory denied"):
        bundle._write_publish_transaction(tmp_path / "workflow.py", {"version": 1, "state": "prepared"})


def test_member_directory_fsync_failure_rolls_back_visible_replacement(tmp_path, monkeypatch):
    path = tmp_path / "workflow.py"
    sidecar = path.with_suffix(".vibe.json")
    bundle._atomic_publish_pair(path, b"old", {"value": "old"})
    originals = path.read_bytes(), sidecar.read_bytes()
    real_fsync_dir = bundle._fsync_dir
    calls = 0

    def fail_after_first_member(directory):
        nonlocal calls
        calls += 1
        if calls == 3:  # prepared journal, publishing journal, first member
            raise OSError("injected directory fsync failure")
        return real_fsync_dir(directory)

    monkeypatch.setattr(bundle, "_fsync_dir", fail_after_first_member)
    with pytest.raises(OSError, match="injected directory fsync failure"):
        bundle._atomic_publish_pair(path, b"new", {"value": "new"})
    assert (path.read_bytes(), sidecar.read_bytes()) == originals
    assert not bundle._publish_transaction_path(path).exists()


def test_windows_overwrite_rolls_back_on_member_failure(tmp_path, monkeypatch):
    _windows_os(monkeypatch)
    path = tmp_path / "workflow.py"
    sidecar = path.with_suffix(".vibe.json")
    bundle._atomic_publish_pair(path, b"old", {"value": "old"})
    originals = path.read_bytes(), sidecar.read_bytes()
    real_replace = os.replace

    def fail_sidecar(source, destination):
        if Path(destination) == sidecar and Path(source).suffix != ".bak":
            raise PermissionError(errno.EACCES, "destination held open")
        return real_replace(source, destination)

    monkeypatch.setattr(bundle.os, "replace", fail_sidecar)
    with pytest.raises(PermissionError, match="destination held open"):
        bundle._atomic_publish_pair(path, b"new", {"value": "new"})
    assert (path.read_bytes(), sidecar.read_bytes()) == originals
    assert not bundle._publish_transaction_path(path).exists()
    monkeypatch.setattr(bundle.os, "replace", real_replace)
    bundle._atomic_publish_pair(path, b"new", {"value": "new"})
    assert path.read_bytes() == b"new"
    assert json.loads(sidecar.read_text()) == {"value": "new"}
