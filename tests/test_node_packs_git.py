from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vibecomfy.node_packs import find_installed_pack_ref


def _git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def test_find_installed_pack_ref_reads_explicit_install_roots_only(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "ComfyUI-KJNodes"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/kijai/ComfyUI-KJNodes.git"], cwd=pack_dir)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pack_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    ignored_root = tmp_path / "ignored"
    ignored_root.mkdir()
    ignored_pack = ignored_root / "ComfyUI-KJNodes"
    ignored_pack.mkdir()
    (ignored_pack / ".git").mkdir()

    match = find_installed_pack_ref(
        "ComfyUI-KJNodes",
        install_roots=[install_root],
        version_pin="deadbeef",
    )

    assert match is not None
    assert match.install_root == install_root
    assert match.pack_ref.slug == "ComfyUI-KJNodes"
    assert match.pack_ref.version == "deadbeef"
    assert match.pack_ref.commit == head
    assert match.pack_ref.url == "https://github.com/kijai/ComfyUI-KJNodes.git"
    assert match.pack_ref.path == str(pack_dir)


def test_find_installed_pack_ref_matches_aux_id(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "repo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "git@github.com:owner/repo.git"], cwd=pack_dir)

    match = find_installed_pack_ref(
        "",
        install_roots=[install_root],
        aux_id="owner/repo",
    )

    assert match is not None
    assert match.pack_ref.slug == "repo"
    assert match.pack_ref.url == "git@github.com:owner/repo.git"
    assert match.pack_ref.name == "repo"


# ---------------------------------------------------------------------------
# T5 — Installed-clone local lookup edge cases
# ---------------------------------------------------------------------------


def test_find_installed_pack_ref_raises_value_error_when_query_and_aux_id_empty(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()

    with pytest.raises(ValueError, match="query or aux_id is required"):
        find_installed_pack_ref("", install_roots=[install_root])


def test_find_installed_pack_ref_returns_none_when_no_match(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "OtherPack"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/kijai/ComfyUI-KJNodes.git"], cwd=pack_dir)

    match = find_installed_pack_ref("NonExistentPack", install_roots=[install_root])

    assert match is None


def test_find_installed_pack_ref_skips_nonexistent_install_root(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist"

    match = find_installed_pack_ref("SomePack", install_roots=[nonexistent])

    assert match is None


def test_find_installed_pack_ref_skips_missing_git_dir(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "NoGitPack"
    pack_dir.mkdir()
    (pack_dir / "README.md").write_text("not a git repo\n", encoding="utf-8")

    match = find_installed_pack_ref("NoGitPack", install_roots=[install_root])

    assert match is None


def test_find_installed_pack_ref_returns_none_for_no_origin(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "NoOrigin"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    # no remote origin added

    match = find_installed_pack_ref("NoOrigin", install_roots=[install_root])

    assert match is None


def test_find_installed_pack_ref_matches_by_dir_name(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "ComfyUI-Foo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/someuser/not-the-same-name.git"], cwd=pack_dir)

    # Query matches dir_name, not origin-derived slug
    match = find_installed_pack_ref("ComfyUI-Foo", install_roots=[install_root])

    assert match is not None
    assert match.pack_ref.slug == "not-the-same-name"
    assert match.pack_ref.name == "ComfyUI-Foo"


def test_find_installed_pack_ref_preserves_version_pin(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "MyPack"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/user/MyPack.git"], cwd=pack_dir)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pack_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    match = find_installed_pack_ref(
        "MyPack",
        install_roots=[install_root],
        version_pin="v1.0.0-pinned",
    )

    assert match is not None
    assert match.pack_ref.version == "v1.0.0-pinned"
    assert match.pack_ref.commit == head


def test_find_installed_pack_ref_empty_install_roots_returns_none(tmp_path: Path) -> None:
    match = find_installed_pack_ref("Anything", install_roots=[])

    assert match is None


def test_find_installed_pack_ref_aux_id_mismatch_returns_none(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "repo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/owner/repo.git"], cwd=pack_dir)

    # aux_id doesn't match the actual origin
    match = find_installed_pack_ref(
        "",
        install_roots=[install_root],
        aux_id="other-owner/other-repo",
    )

    assert match is None


def test_find_installed_pack_ref_first_matching_root_wins(tmp_path: Path) -> None:
    root_a = tmp_path / "root_a"
    root_a.mkdir()
    pack_a = root_a / "SharedName"
    pack_a.mkdir()
    _git(["git", "init"], cwd=pack_a)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_a)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_a)
    (pack_a / "README.md").write_text("a\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_a)
    _git(["git", "commit", "-m", "init"], cwd=pack_a)
    _git(["git", "remote", "add", "origin", "https://github.com/user/SharedName.git"], cwd=pack_a)
    head_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pack_a,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    root_b = tmp_path / "root_b"
    root_b.mkdir()
    pack_b = root_b / "SharedName"
    pack_b.mkdir()
    _git(["git", "init"], cwd=pack_b)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_b)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_b)
    (pack_b / "README.md").write_text("b\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_b)
    _git(["git", "commit", "-m", "init"], cwd=pack_b)
    _git(["git", "remote", "add", "origin", "https://github.com/user/SharedName.git"], cwd=pack_b)

    match = find_installed_pack_ref("SharedName", install_roots=[root_a, root_b])

    assert match is not None
    assert match.install_root == root_a
    assert match.pack_ref.commit == head_a
    assert match.pack_ref.path == str(pack_a)


def test_find_installed_pack_ref_origin_without_dot_git_suffix(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "repo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/owner/repo"], cwd=pack_dir)

    match = find_installed_pack_ref(
        "",
        install_roots=[install_root],
        aux_id="owner/repo",
    )

    assert match is not None
    assert match.pack_ref.slug == "repo"
    assert match.pack_ref.url == "https://github.com/owner/repo"

# ---------------------------------------------------------------------------
# T12 — Sentinel recovery tests
# ---------------------------------------------------------------------------


import json as _json
import os as _os
import socket as _socket
import time as _time
from unittest import mock as _mock

from vibecomfy.node_packs._install import (
    _has_incomplete_install,
    _install_sentinel,
    _process_alive,
    _quarantine_sentinel,
    _safe_pack_slug,
    INSTALL_STATE_DIR,
    SENTINEL_LEASE_SECONDS,
    _InstallSentinel,
)


class _SentinelFakeRunner:
    """Fake subprocess runner for sentinel behaviour tests.

    Supports *fail_pip* (raise on any pip install call) and *wrong_head*
    (return *alternate_sha* for git rev-parse).  All other git commands
    succeed with canned output.
    """

    def __init__(
        self,
        *,
        sha: str = "abc123",
        alternate_sha: str = "deadbeef",
        porcelain: str = "",
        origin_url: str = "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        fail_pip: bool = False,
        wrong_head: bool = False,
        fail_clone: bool = False,
    ) -> None:
        self.sha = sha
        self.alternate_sha = alternate_sha
        self.porcelain = porcelain
        self.origin_url = origin_url
        self.fail_pip = fail_pip
        self.wrong_head = wrong_head
        self.fail_clone = fail_clone
        self.calls: list[list[str]] = []

    def __call__(self, args, *, check, capture_output, text, cwd=None):
        import subprocess as _subprocess

        call = list(args)
        self.calls.append(call)
        assert check is True
        assert capture_output is True
        assert text is True

        if call[:2] == ["git", "clone"]:
            if self.fail_clone:
                raise _subprocess.CalledProcessError(1, call, stderr="clone failed")
            return _subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if len(call) >= 4 and call[:4] == ["git", "-C", call[2], "status"]:
            return _subprocess.CompletedProcess(call, 0, stdout=self.porcelain, stderr="")
        if len(call) >= 4 and call[:4] == ["git", "-C", call[2], "config"]:
            return _subprocess.CompletedProcess(call, 0, stdout=f"{self.origin_url}\n", stderr="")
        if len(call) >= 4 and call[:4] == ["git", "-C", call[2], "rev-parse"]:
            sha = self.alternate_sha if self.wrong_head else self.sha
            return _subprocess.CompletedProcess(call, 0, stdout=f"{sha}\n", stderr="")
        if len(call) >= 4 and call[:4] == ["git", "-C", call[2], "fetch"]:
            return _subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if len(call) >= 4 and call[:4] == ["git", "-C", call[2], "checkout"]:
            return _subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if len(call) >= 4 and call[1:4] == ["-m", "pip", "install"]:
            if self.fail_pip:
                raise _subprocess.CalledProcessError(1, call, stderr="pip install failed")
            return _subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {call!r}")


# ---------------------------------------------------------------------------
# Direct unit tests of _install_sentinel recovery rules
# ---------------------------------------------------------------------------


def test_sentinel_no_file_returns_fresh(tmp_path):
    """No sentinel present -> fresh _InstallSentinel with incomplete=False."""
    install_root = tmp_path / "custom_nodes"
    sentinel = _install_sentinel(install_root, "SomePack")
    assert isinstance(sentinel, _InstallSentinel)
    assert sentinel.incomplete is False
    assert sentinel.live_owner_pid is None
    assert not sentinel.path.exists()


def test_sentinel_live_owner_refusal_same_host(tmp_path, monkeypatch):
    """Sentinel with same hostname + alive pid -> live_owner_pid set."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"

    # Force hostname to a known value so we control the same-host branch.
    monkeypatch.setattr(_socket, "gethostname", lambda: "testhost")

    payload = {
        "complete": False,
        "phase": "clone",
        "name": "SomePack",
        "repo_url": "https://example.test/pack.git",
        "install_dir": str(install_root / "SomePack"),
        "pid": _os.getpid(),
        "hostname": "testhost",
        "timestamp": _time.time(),
    }
    sentinel_path.write_text(_json.dumps(payload), encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is True
    assert sentinel.live_owner_pid == _os.getpid()
    assert sentinel_path.exists()  # sentinel is NOT cleared for live owner
    assert "active" in sentinel.reason.lower()


def test_sentinel_dead_owner_recovery_same_host(tmp_path, monkeypatch):
    """Sentinel with same hostname but dead pid -> cleared, sentinel.incomplete=False."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"

    monkeypatch.setattr(_socket, "gethostname", lambda: "testhost")

    # Find a pid that is definitely not alive.
    dead_pid = 99999
    for candidate in (99999, 99998, 99997, 99996, 1):
        try:
            _os.kill(candidate, 0)
        except OSError:
            dead_pid = candidate
            break

    payload = {
        "complete": False,
        "phase": "clone",
        "name": "SomePack",
        "repo_url": "https://example.test/pack.git",
        "install_dir": str(install_root / "SomePack"),
        "pid": dead_pid,
        "hostname": "testhost",
        "timestamp": _time.time(),
    }
    sentinel_path.write_text(_json.dumps(payload), encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is False
    assert sentinel.live_owner_pid is None
    assert not sentinel_path.exists()  # cleared


def test_sentinel_stale_lease_recovery_cross_host(tmp_path, monkeypatch):
    """Sentinel with different hostname + stale timestamp -> cleared."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"

    monkeypatch.setattr(_socket, "gethostname", lambda: "currenthost")

    stale_time = _time.time() - SENTINEL_LEASE_SECONDS - 60  # 31 min ago
    payload = {
        "complete": False,
        "phase": "clone",
        "name": "SomePack",
        "repo_url": "https://example.test/pack.git",
        "install_dir": str(install_root / "SomePack"),
        "pid": 12345,  # arbitrary; won't be checked cross-host when stale
        "hostname": "otherhost",
        "timestamp": stale_time,
    }
    sentinel_path.write_text(_json.dumps(payload), encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is False
    assert sentinel.live_owner_pid is None
    assert not sentinel_path.exists()


def test_sentinel_fresh_lease_refusal_cross_host(tmp_path, monkeypatch):
    """Sentinel with different hostname + fresh timestamp -> refused."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"

    monkeypatch.setattr(_socket, "gethostname", lambda: "currenthost")

    payload = {
        "complete": False,
        "phase": "clone",
        "name": "SomePack",
        "repo_url": "https://example.test/pack.git",
        "install_dir": str(install_root / "SomePack"),
        "pid": 12345,
        "hostname": "otherhost",
        "timestamp": _time.time(),
    }
    sentinel_path.write_text(_json.dumps(payload), encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is True
    assert sentinel.live_owner_pid == 12345
    assert sentinel_path.exists()
    assert "active" in sentinel.reason.lower()


# ---------------------------------------------------------------------------
# Corrupt sentinel variants (quarantine behaviour)
# ---------------------------------------------------------------------------


def test_sentinel_corrupt_unparseable_json_quarantined(tmp_path):
    """Unparseable sentinel JSON -> quarantined, fresh sentinel returned."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"
    sentinel_path.write_text("{not valid json!!!", encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is False
    assert sentinel.live_owner_pid is None
    assert not sentinel_path.exists()
    corrupt_files = list(state_dir.glob(".corrupt-*"))
    assert len(corrupt_files) >= 1, "corrupt sentinel should be quarantined"


def test_sentinel_corrupt_complete_true_quarantined(tmp_path):
    """Sentinel with complete:true (not False) -> treated as corrupt, quarantined."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"
    payload = {
        "complete": True,
        "phase": "done",
    }
    sentinel_path.write_text(_json.dumps(payload), encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is False
    assert sentinel.live_owner_pid is None
    assert not sentinel_path.exists()
    corrupt_files = list(state_dir.glob(".corrupt-*"))
    assert len(corrupt_files) >= 1


def test_sentinel_corrupt_not_a_dict_quarantined(tmp_path):
    """Sentinel JSON that parses to a list (not dict) -> quarantined."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"
    sentinel_path.write_text('[1, 2, 3]', encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is False
    assert not sentinel_path.exists()
    assert len(list(state_dir.glob(".corrupt-*"))) >= 1


def test_sentinel_legacy_no_owner_metadata_quarantined(tmp_path):
    """Sentinel with complete:false but no pid/hostname/timestamp -> quarantined."""
    install_root = tmp_path / "custom_nodes"
    state_dir = install_root / INSTALL_STATE_DIR
    state_dir.mkdir(parents=True)
    sentinel_path = state_dir / "SomePack.json"
    sentinel_path.write_text('{"complete": false, "phase": "pip"}', encoding="utf-8")

    sentinel = _install_sentinel(install_root, "SomePack")

    assert sentinel.incomplete is False
    assert sentinel.live_owner_pid is None
    assert not sentinel_path.exists()
    assert len(list(state_dir.glob(".corrupt-*"))) >= 1


# ---------------------------------------------------------------------------
# Proof: sentinel cleanup ONLY after full finalization succeeds
# ---------------------------------------------------------------------------


def test_sentinel_survives_pip_failure_and_block_retry(tmp_path):
    """Sentinel is written before pip, survives pip failure, and blocks retry.

    Uses ComfyUI-KJNodes which has pip_packages=('matplotlib',) so the pip
    install subprocess call is actually exercised.
    """
    from vibecomfy.node_packs import install_pack

    install_root = tmp_path / "custom_nodes"

    # Clone succeeds, pip fails.
    runner = _SentinelFakeRunner(sha="abc123", fail_pip=True)

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _r, _rn: None,
    )

    assert result.status == "failed"
    assert "pip" in (result.error or "").lower()

    sentinel_path = install_root / INSTALL_STATE_DIR / "ComfyUI-KJNodes.json"
    assert sentinel_path.exists(), "sentinel should survive pip failure"
    payload = _json.loads(sentinel_path.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert payload["phase"] == "pip"

    # Retry should be blocked by the surviving sentinel.
    retry_runner = _SentinelFakeRunner(sha="retryhead")
    retry = install_pack(
        name="ComfyUI-KJNodes",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=retry_runner,
        cm_cli_resolver=lambda _r, _rn: None,
    )

    assert retry.status == "failed"
    assert "incomplete install sentinel" in (retry.error or "").lower()
    assert retry_runner.calls == []


def test_sentinel_survives_head_mismatch_and_block_retry(tmp_path):
    """Sentinel survives expected-commit mismatch during verification phase."""
    from vibecomfy.node_packs import install_pack

    install_root = tmp_path / "custom_nodes"

    # clone ok, then head returns wrong sha (wrong_head=True for all rev-parse).
    runner = _SentinelFakeRunner(sha="abc123", alternate_sha="wrongsha", wrong_head=True)

    result = install_pack(
        repo="https://example.test/some-pack.git",
        checkout_ref="expectedhead",
        expected_commit="expectedhead",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _r, _rn: None,
    )

    assert result.status == "failed"
    assert "expected git head" in (result.error or "").lower()

    sentinel_path = install_root / INSTALL_STATE_DIR / "some-pack.json"
    assert sentinel_path.exists(), "sentinel should survive verification failure"
    payload = _json.loads(sentinel_path.read_text(encoding="utf-8"))
    assert payload["complete"] is False

    # Retry should be blocked.
    retry_runner = _SentinelFakeRunner(sha="retryhead")
    retry = install_pack(
        repo="https://example.test/some-pack.git",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=retry_runner,
        cm_cli_resolver=lambda _r, _rn: None,
    )

    assert retry.status == "failed"
    assert "incomplete install sentinel" in (retry.error or "").lower()


def test_sentinel_cleared_only_after_full_finalization(tmp_path):
    """Sentinel must be present after pip+verify but gone after lockfile upsert.

    This is the golden-path proof: sentinel.clear() is the very last durable
    step inside _finalize_install, after pip deps, git HEAD verification, and
    lockfile entry derivation + upsert all succeed.
    """
    from vibecomfy.node_packs import install_pack, read_lockfile

    install_root = tmp_path / "custom_nodes"
    lockfile_path = tmp_path / "custom_nodes.lock"
    sentinel_path = install_root / INSTALL_STATE_DIR / "ComfyUI-VideoHelperSuite.json"

    # Full success path (VideoHelperSuite has no pip deps so install is a no-op).
    runner = _SentinelFakeRunner(sha="goldenhead")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=lockfile_path,
        runner=runner,
        cm_cli_resolver=lambda _r, _rn: None,
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "goldenhead"

    # Sentinel must be CLEARED after all phases succeed.
    assert not sentinel_path.exists(), (
        "sentinel should be cleared only after all durable work succeeds"
    )

    # Lockfile must contain the entry.
    entries = read_lockfile(lockfile_path)
    assert len(entries) == 1
    assert entries[0].name == "ComfyUI-VideoHelperSuite"
    assert entries[0].git_commit_sha == "goldenhead"


def test_sentinel_cleared_after_restore_full_success(tmp_path):
    """Sentinel cleared after restore_pack completes full finalization."""
    from vibecomfy.node_packs import restore_pack, LockEntry

    install_root = tmp_path / "custom_nodes"
    install_dir = install_root / "ExamplePack"
    install_dir.mkdir(parents=True)
    sentinel_path = install_root / INSTALL_STATE_DIR / "ExamplePack.json"

    runner = _SentinelFakeRunner(
        sha="pinnedsha", porcelain="", origin_url="https://example.test/example.git"
    )

    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=install_root, runner=runner)

    assert result.status == "refreshed"
    assert not sentinel_path.exists(), "sentinel should be cleared after successful restore"
