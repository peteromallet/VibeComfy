from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from vibecomfy.node_packs import LockEntry, read_lockfile
from vibecomfy.node_packs import (
    install_pack,
    install_required_packs,
    missing_packs_for_workflow,
    preflight_pip_requirements,
    restore_pack,
)
from vibecomfy.node_packs._install import _known_schema_classes, _resolve_node_index_path
from vibecomfy.node_packs import CustomNodePack
from vibecomfy.registry.pack_resolver import PackRef

_VHS_CLASSES = ("VHS_LoadVideo", "VHS_VideoCombine")


def _video_helper_entry(sha: str) -> LockEntry:
    return LockEntry(
        name="ComfyUI-VideoHelperSuite",
        git_commit_sha=sha,
        url="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        class_set=_VHS_CLASSES,
    )
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class FakeRunner:
    def __init__(
        self,
        *,
        sha: str = "abc123",
        porcelain: str = "",
        origin_url: str = "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        checkout_head: str | None = None,
        fail_clone: bool = False,
        fail_pip: bool = False,
        fail_cm_cli: bool = False,
        cm_cli_checkout_dir: Path | None = None,
    ) -> None:
        self.sha = sha
        self.porcelain = porcelain
        self.origin_url = origin_url
        self.checkout_head = checkout_head
        self.fail_clone = fail_clone
        self.fail_pip = fail_pip
        self.fail_cm_cli = fail_cm_cli
        self.cm_cli_checkout_dir = cm_cli_checkout_dir
        self.calls: list[list[str]] = []
        self.cwd_calls: list[str | Path | None] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        self.calls.append(call)
        self.cwd_calls.append(cwd)
        assert check is True
        assert capture_output is True
        assert text is True
        if call[:2] == ["cm-cli", "install"]:
            if self.fail_cm_cli:
                raise subprocess.CalledProcessError(1, call, stderr="cm-cli failed")
            if self.cm_cli_checkout_dir is not None:
                (self.cm_cli_checkout_dir / ".git").mkdir(parents=True)
            return subprocess.CompletedProcess(call, 0, stdout="installed", stderr="")
        if call[:2] == ["git", "clone"]:
            if self.fail_clone:
                raise subprocess.CalledProcessError(1, call, stderr="clone failed")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if call[:4] == ["git", "-C", call[2], "status"]:
            return subprocess.CompletedProcess(call, 0, stdout=self.porcelain, stderr="")
        if call[:4] == ["git", "-C", call[2], "config"]:
            return subprocess.CompletedProcess(call, 0, stdout=f"{self.origin_url}\n", stderr="")
        if call[:4] == ["git", "-C", call[2], "rev-parse"]:
            return subprocess.CompletedProcess(call, 0, stdout=f"{self.sha}\n", stderr="")
        if call[:4] == ["git", "-C", call[2], "fetch"]:
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if call[:4] == ["git", "-C", call[2], "checkout"]:
            self.sha = self.checkout_head or call[4]
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if len(call) >= 4 and call[1:4] == ["-m", "pip", "install"]:
            if self.fail_pip:
                raise subprocess.CalledProcessError(1, call, stderr="pip failed")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {call!r}")


def test_install_clones_and_upserts_on_success(tmp_path: Path) -> None:
    runner = FakeRunner(sha="feedface")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "feedface"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ]
    assert read_lockfile(lockfile) == [
        _video_helper_entry("feedface")
    ]
    assert not (tmp_path / "custom_nodes" / ".vibecomfy-install-state" / "ComfyUI-VideoHelperSuite.json").exists()


def test_install_writes_sentinel_before_clone_and_leaves_it_on_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_clone=True)
    lockfile = tmp_path / "custom_nodes.lock"
    install_root = tmp_path / "custom_nodes"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    sentinel = install_root / ".vibecomfy-install-state" / "ComfyUI-VideoHelperSuite.json"
    assert result.status == "failed"
    assert sentinel.exists()
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert payload["phase"] == "clone"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(install_root / "ComfyUI-VideoHelperSuite"),
    ]


def test_install_updates_sentinel_through_pip_and_leaves_it_on_pip_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_pip=True)
    install_root = tmp_path / "custom_nodes"

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    sentinel = install_root / ".vibecomfy-install-state" / "ComfyUI-KJNodes.json"
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    assert result.status == "failed"
    assert payload["complete"] is False
    assert payload["phase"] == "pip"


def test_install_retry_after_clone_ok_pip_failure_refuses_before_false_refresh(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    lockfile = tmp_path / "custom_nodes.lock"
    first_runner = FakeRunner(fail_pip=True)

    def clone_persists_checkout(
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        if call[:2] == ["git", "clone"]:
            Path(call[3]).mkdir(parents=True)
        return first_runner(call, check=check, capture_output=capture_output, text=text, cwd=cwd)

    first = install_pack(
        name="ComfyUI-KJNodes",
        install_root=install_root,
        lockfile_path=lockfile,
        runner=clone_persists_checkout,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert first.status == "failed"
    sentinel = install_root / ".vibecomfy-install-state" / "ComfyUI-KJNodes.json"
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    assert payload["phase"] == "pip"
    assert (install_root / "ComfyUI-KJNodes").exists()
    assert read_lockfile(lockfile) == []

    retry_runner = FakeRunner(sha="retryhead", porcelain="")
    second = install_pack(
        name="ComfyUI-KJNodes",
        install_root=install_root,
        lockfile_path=lockfile,
        runner=retry_runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert second.status == "failed"
    assert "incomplete install sentinel" in (second.error or "")
    assert retry_runner.calls == []
    assert read_lockfile(lockfile) == []


def test_install_git_head_uses_injected_runner_after_helper_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_default_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        raise AssertionError("git_head should use the injected node-pack runner")

    monkeypatch.setattr("vibecomfy._git_utils.subprocess.run", unexpected_default_run)
    runner = FakeRunner(sha="injectedhead")
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "injectedhead"
    assert ["git", "-C", str(install_dir), "rev-parse", "HEAD"] in runner.calls


def test_install_no_lockfile_mutation_on_clone_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_clone=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "clone failed" in (result.error or "")
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_no_lockfile_mutation_on_pip_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_pip=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "pip failed" in (result.error or "")
    assert lockfile.read_text(encoding="utf-8") == original


class PipPreflightRunner(FakeRunner):
    def __init__(
        self,
        *,
        pip_help: str = "--dry-run\n--report\n",
        fail_dry_run: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.pip_help = pip_help
        self.fail_dry_run = fail_dry_run

    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        if call == [call[0], "-m", "pip", "install", "--help"]:
            self.calls.append(call)
            self.cwd_calls.append(cwd)
            return subprocess.CompletedProcess(call, 0, stdout=self.pip_help, stderr="")
        if len(call) >= 7 and call[1:6] == ["-m", "pip", "install", "--dry-run", "--report"]:
            self.calls.append(call)
            self.cwd_calls.append(cwd)
            if self.fail_dry_run:
                raise subprocess.CalledProcessError(1, call, stderr="dry-run failed")
            Path(call[6]).write_text("{}", encoding="utf-8")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        return super().__call__(args, check=check, capture_output=capture_output, text=text, cwd=cwd)


def test_preflight_pip_requirements_runs_joint_dry_run_report() -> None:
    runner = PipPreflightRunner()
    packs = [
        CustomNodePack("A", "https://example.test/a.git", ("AClass",), pip_packages=("zeta", "alpha")),
        CustomNodePack("B", "https://example.test/b.git", ("BClass",), pip_packages=("alpha",)),
    ]

    result = preflight_pip_requirements(packs, runner=runner)

    assert result.ok is True
    assert result.unsupported is False
    assert result.packages == ("alpha", "zeta")
    assert runner.calls[0] == [runner.calls[0][0], "-m", "pip", "install", "--help"]
    assert runner.calls[1][1:6] == ["-m", "pip", "install", "--dry-run", "--report"]
    assert runner.calls[1][-2:] == ["alpha", "zeta"]


def test_batch_install_fails_closed_when_pip_preflight_is_unsupported(tmp_path: Path) -> None:
    runner = PipPreflightRunner(pip_help="")
    packs = [
        CustomNodePack("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git", ("ImageResizeKJv2",), pip_packages=("matplotlib",)),
        CustomNodePack("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", _VHS_CLASSES),
    ]

    result = install_required_packs(
        packs,
        install_root=tmp_path / "custom_nodes",
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.ok is False
    assert result.preflight_unsupported is True
    assert [item.name for item in result.results] == ["ComfyUI-KJNodes", "ComfyUI-VideoHelperSuite"]
    assert all(item.status == "failed" for item in result.results)
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert not (tmp_path / "custom_nodes.lock").exists()


def test_batch_install_stops_before_mutation_when_pip_dry_run_fails(tmp_path: Path) -> None:
    runner = PipPreflightRunner(fail_dry_run=True)
    packs = [
        CustomNodePack("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git", ("ImageResizeKJv2",), pip_packages=("matplotlib",)),
    ]

    result = install_required_packs(
        packs,
        install_root=tmp_path / "custom_nodes",
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.ok is False
    assert result.preflight_unsupported is False
    assert "dry-run failed" in (result.preflight.error or "")
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert not (tmp_path / "custom_nodes" / ".vibecomfy-install-state").exists()


def test_batch_install_collects_all_pack_outcomes_and_preserves_force_and_restore(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    existing = install_root / "ComfyUI-VideoHelperSuite"
    existing.mkdir(parents=True)
    runner = PipPreflightRunner(sha="forcehead", porcelain=" M nodes.py\n")
    packs = [
        CustomNodePack("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", _VHS_CLASSES),
        CustomNodePack("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git", ("ImageResizeKJv2",), pip_packages=("matplotlib",)),
        CustomNodePack("ExamplePack", "https://example.test/example.git", ("ExampleNode",)),
    ]
    restore_entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = install_required_packs(
        packs,
        force=True,
        restore_entries=[restore_entry],
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.ok is True
    assert [(item.name, item.status, item.git_commit_sha) for item in result.results] == [
        ("ComfyUI-VideoHelperSuite", "refreshed", "forcehead"),
        ("ComfyUI-KJNodes", "installed", "forcehead"),
        ("ExamplePack", "installed", "pinnedsha"),
    ]
    assert ["git", "clone", "https://example.test/example.git", str(install_root / "ExamplePack")] in runner.calls
    assert ["git", "-C", str(install_root / "ExamplePack"), "checkout", "pinnedsha"] in runner.calls


def test_batch_install_commit_ref_uses_restore_entry_and_writes_verified_pin(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    runner = PipPreflightRunner()
    commit = "feedfacefeedfacefeedfacefeedfacefeedface"
    packs = [
        CustomNodePack("ExamplePack", "https://example.test/example.git", ("ExampleNode",)),
    ]

    result = install_required_packs(
        packs,
        install_refs_by_name={
            "ExamplePack": PackRef(
                slug="example-pack",
                source="aux-git",
                version=commit,
                commit=commit,
                url="https://example.test/example.git",
            )
        },
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.ok is True
    assert [(item.name, item.status, item.git_commit_sha) for item in result.results] == [
        ("ExamplePack", "installed", commit),
    ]
    assert ["git", "clone", "https://example.test/example.git", str(install_root / "ExamplePack")] in runner.calls
    assert ["git", "-C", str(install_root / "ExamplePack"), "checkout", commit] in runner.calls
    assert read_lockfile(tmp_path / "custom_nodes.lock") == [
        LockEntry(
            name="ExamplePack",
            git_commit_sha=commit,
            url="https://example.test/example.git",
            slug="example-pack",
            source="aux-git",
            version=commit,
            commit=commit,
            class_set=("ExampleNode",),
        )
    ]


def test_install_pack_checkout_ref_verifies_expected_commit_before_lockfile_write(tmp_path: Path) -> None:
    runner = FakeRunner(sha="wronghead")

    def checkout_without_moving_head(
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        if call[:4] == ["git", "-C", call[2], "checkout"]:
            runner.calls.append(call)
            runner.cwd_calls.append(cwd)
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        return runner(args, check=check, capture_output=capture_output, text=text, cwd=cwd)

    result = install_pack(
        repo="https://example.test/some-pack.git",
        checkout_ref="expectedhead",
        expected_commit="expectedhead",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=checkout_without_moving_head,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "expected git HEAD expectedhead" in (result.error or "")
    assert not (tmp_path / "custom_nodes.lock").exists()


def test_install_pack_existing_checkout_ref_fetches_and_locks_verified_head(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_dir = install_root / "some-pack"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="oldhead", porcelain="", origin_url="https://example.test/some-pack.git")

    result = install_pack(
        repo="https://example.test/some-pack.git",
        checkout_ref="newhead",
        expected_commit="newhead",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "refreshed"
    assert result.git_commit_sha == "newhead"
    assert ["git", "-C", str(install_dir), "fetch", "origin"] in runner.calls
    assert ["git", "-C", str(install_dir), "checkout", "newhead"] in runner.calls
    assert read_lockfile(tmp_path / "custom_nodes.lock") == [
        LockEntry(
            name="some-pack",
            git_commit_sha="newhead",
            url="https://example.test/some-pack.git",
        )
    ]


def test_batch_install_semver_ref_attempts_checkout_and_preserves_version_identity(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    runner = PipPreflightRunner(
        sha="pre-checkout-head",
        checkout_head="tag-head",
        origin_url="https://example.test/example.git",
    )
    packs = [
        CustomNodePack("ExamplePack", "https://example.test/example.git", ("ExampleNode",)),
    ]

    result = install_required_packs(
        packs,
        install_refs_by_name={
            "ExamplePack": PackRef(
                slug="example-pack",
                source="aux-git",
                version="v1.2.3",
                url="https://example.test/example.git",
            )
        },
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.ok is True
    assert [(item.name, item.status, item.git_commit_sha) for item in result.results] == [
        ("ExamplePack", "installed", "tag-head"),
    ]
    assert ["git", "-C", str(install_root / "ExamplePack"), "checkout", "v1.2.3"] in runner.calls
    assert read_lockfile(tmp_path / "custom_nodes.lock") == [
        LockEntry(
            name="ExamplePack",
            git_commit_sha="tag-head",
            url="https://example.test/example.git",
            slug="example-pack",
            source="aux-git",
            version="v1.2.3",
            commit="tag-head",
            class_set=("ExampleNode",),
        )
    ]


def test_install_idempotent_when_clean(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="cleanhead", porcelain="")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "refreshed"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        _video_helper_entry("cleanhead")
    ]


def test_install_recovers_legacy_sentinel_without_owner_metadata(tmp_path: Path) -> None:
    """A sentinel without pid/hostname/timestamp has no detectable owner
    and is quarantined so the install can proceed."""
    install_root = tmp_path / "custom_nodes"
    install_dir = install_root / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    sentinel = install_root / ".vibecomfy-install-state" / "ComfyUI-VideoHelperSuite.json"
    sentinel.parent.mkdir()
    sentinel.write_text('{"complete": false, "phase": "pip"}\n', encoding="utf-8")
    runner = FakeRunner(sha="cleanhead", porcelain="")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    # Sentinel without owner metadata is quarantined; install proceeds.
    assert result.status == "refreshed"
    assert result.git_commit_sha == "cleanhead"
    assert not sentinel.exists()
    assert len(list(sentinel.parent.glob(".corrupt-*"))) >= 1
    assert len(runner.calls) >= 1


def test_install_quarantines_corrupt_sentinel_and_proceeds(tmp_path: Path) -> None:
    """A corrupt (unparseable) sentinel has no detectable owner
    and is quarantined so the install can proceed."""
    install_root = tmp_path / "custom_nodes"
    sentinel = install_root / ".vibecomfy-install-state" / "ComfyUI-VideoHelperSuite.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("{not json", encoding="utf-8")
    runner = FakeRunner(sha="freshhead")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    # Corrupt sentinel is quarantined; install proceeds.
    assert result.status == "installed"
    assert result.git_commit_sha == "freshhead"
    assert not sentinel.exists()
    assert len(list(sentinel.parent.glob(".corrupt-*"))) >= 1
    assert len(runner.calls) >= 1



def test_install_refuses_live_owner_sentinel(tmp_path: Path) -> None:
    """A sentinel whose owner PID is still alive blocks the install."""
    import os, json, time
    install_root = tmp_path / "custom_nodes"
    sentinel_dir = install_root / ".vibecomfy-install-state"
    sentinel_dir.mkdir(parents=True)
    sentinel = sentinel_dir / "ComfyUI-VideoHelperSuite.json"
    # Write a sentinel with the current PID — simulating a live owner.
    payload = {
        "complete": False,
        "phase": "clone",
        "name": "ComfyUI-VideoHelperSuite",
        "repo_url": "https://example.test/vhs.git",
        "install_dir": str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
        "pid": os.getpid(),
        "hostname": "localhost",  # will not match real hostname → lease path
        "timestamp": time.time(),
    }
    sentinel.write_text(json.dumps(payload), encoding="utf-8")
    runner = FakeRunner(sha="cleanhead", porcelain="")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    # Different hostname but fresh lease — treated as potentially live.
    assert result.status == "failed"
    assert "active" in (result.error or "")
    assert runner.calls == []


def test_install_recovers_dead_owner_sentinel(tmp_path: Path) -> None:
    """A sentinel whose owner PID no longer exists is recovered
    (cleared) so the install can proceed."""
    import os, json, time
    install_root = tmp_path / "custom_nodes"
    sentinel_dir = install_root / ".vibecomfy-install-state"
    sentinel_dir.mkdir(parents=True)
    sentinel = sentinel_dir / "ComfyUI-VideoHelperSuite.json"
    # Use a PID that almost certainly does not exist (large number).
    dead_pid = 99999
    # Make sure it's really dead on this system.
    try:
        os.kill(dead_pid, 0)
        # If it exists, pick another unlikely PID.
        dead_pid = 99998
        try:
            os.kill(dead_pid, 0)
            dead_pid = 99997
        except OSError:
            pass
    except OSError:
        pass
    payload = {
        "complete": False,
        "phase": "clone",
        "name": "ComfyUI-VideoHelperSuite",
        "repo_url": "https://example.test/vhs.git",
        "install_dir": str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
        "pid": dead_pid,
        "hostname": __import__("socket").gethostname(),  # same host
        "timestamp": time.time(),
    }
    sentinel.write_text(json.dumps(payload), encoding="utf-8")
    runner = FakeRunner(sha="recoveredhead", porcelain="")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=tmp_path / "custom_nodes.lock",
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    # Dead owner — sentinel is cleared, install proceeds.
    assert result.status == "installed"
    assert result.git_commit_sha == "recoveredhead"
    assert not sentinel.exists()
    assert len(runner.calls) >= 1


def test_install_refuses_dirty_without_force(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="dirtyhead", porcelain=" M nodes.py\n")
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "skipped_dirty"
    assert result.git_commit_sha == "dirtyhead"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_existing_mismatched_origin_refuses_without_overwriting(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_dir = install_root / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(
        sha="existinghead",
        porcelain="",
        origin_url="https://example.test/not-video-helper.git",
    )
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=install_root,
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "skipped_dirty"
    assert result.git_commit_sha == "existinghead"
    assert "refusing to overwrite existing clone" in (result.error or "")
    assert not any(call[:4] == ["git", "-C", str(install_dir), "fetch"] for call in runner.calls)
    assert not any(call[:4] == ["git", "-C", str(install_dir), "checkout"] for call in runner.calls)
    assert not lockfile.exists()


def test_install_force_dirty_does_not_clone_and_upserts_head(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="dirtyhead", porcelain=" M nodes.py\n")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        force=True,
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "refreshed"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        _video_helper_entry("dirtyhead")
    ]


def test_install_with_repo_url_infers_name_and_skips_pip_when_uncatalogued(tmp_path: Path) -> None:
    runner = FakeRunner(sha="uncatalogued")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        repo="https://example.test/some-pack.git",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.name == "some-pack"
    assert result.status == "installed"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://example.test/some-pack.git",
        str(tmp_path / "custom_nodes" / "some-pack"),
    ]
    assert not any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        LockEntry(
            name="some-pack",
            git_commit_sha="uncatalogued",
            url="https://example.test/some-pack.git",
        )
    ]


def test_install_registry_pack_fails_when_class_set_cannot_be_derived(tmp_path: Path, monkeypatch) -> None:
    import vibecomfy.node_packs as node_packs_install
    from vibecomfy.registry.pack_resolver import PackRef, PackResolution

    monkeypatch.setattr(
        node_packs_install,
        "resolve_pack",
        lambda name: PackResolution(
            query=name,
            query_type="slug",
            ref=PackRef(
                slug=name,
                source="comfy-registry",
                url="https://example.test/registry-pack.git",
            ),
        ),
    )
    runner = FakeRunner(sha="registryhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="registry-pack",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "failed to derive class_set" in (result.error or "")
    assert read_lockfile(lockfile) == []


def test_install_uses_cm_cli_when_available(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    runner = FakeRunner(sha="cmclihead", cm_cli_checkout_dir=install_dir)
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: ["cm-cli"],
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "cmclihead"
    assert runner.calls[0] == ["cm-cli", "install", "ComfyUI-VideoHelperSuite"]
    assert runner.cwd_calls[0] == tmp_path
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert not any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        _video_helper_entry("cmclihead")
    ]


def test_install_cm_cli_failure_falls_back_to_clone(tmp_path: Path) -> None:
    runner = FakeRunner(fail_cm_cli=True, sha="fallbackhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: ["cm-cli"],
    )

    assert result.status == "installed"
    assert ["cm-cli", "install", "ComfyUI-VideoHelperSuite"] in runner.calls
    assert [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ] in runner.calls
    assert read_lockfile(lockfile) == [
        _video_helper_entry("fallbackhead")
    ]


def test_install_cm_cli_succeeded_but_no_git_falls_back_to_clone(tmp_path: Path) -> None:
    runner = FakeRunner(sha="fallbackhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: ["cm-cli"],
    )

    assert result.status == "installed"
    assert ["cm-cli", "install", "ComfyUI-VideoHelperSuite"] in runner.calls
    assert [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ] in runner.calls
    assert read_lockfile(lockfile) == [
        _video_helper_entry("fallbackhead")
    ]


def test_install_falls_back_to_clone_when_cm_cli_missing(tmp_path: Path) -> None:
    runner = FakeRunner(sha="fallbackhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "installed"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://github.com/kijai/ComfyUI-KJNodes.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-KJNodes"),
    ]
    assert any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    [entry] = read_lockfile(lockfile)
    assert entry.name == "ComfyUI-KJNodes"
    assert entry.git_commit_sha == "fallbackhead"
    assert entry.url == "https://github.com/kijai/ComfyUI-KJNodes.git"
    assert "ImageResizeKJv2" in entry.class_set
    assert entry.pip_packages == ("matplotlib",)


def test_restore_clones_and_checks_out_pinned_sha(tmp_path: Path) -> None:
    runner = FakeRunner()
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "installed"
    assert result.git_commit_sha == "pinnedsha"
    assert runner.calls == [
        ["git", "clone", "https://example.test/example.git", str(tmp_path / "custom_nodes" / "ExamplePack")],
        ["git", "-C", str(tmp_path / "custom_nodes" / "ExamplePack"), "checkout", "pinnedsha"],
        ["git", "-C", str(tmp_path / "custom_nodes" / "ExamplePack"), "rev-parse", "HEAD"],
    ]


def test_restore_installs_known_pack_pip_dependencies(tmp_path: Path) -> None:
    runner = FakeRunner()
    entry = LockEntry(
        "ComfyUI-WanVideoWrapper",
        "pinnedsha",
        "https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
    )

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "installed"
    assert [
        "git",
        "clone",
        "https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-WanVideoWrapper"),
    ] in runner.calls
    assert any(call[1:4] == ["-m", "pip", "install"] and "onnx" in call for call in runner.calls)


def test_restore_existing_clean_dir_at_correct_sha_is_noop(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ExamplePack"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="pinnedsha", porcelain="")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "refreshed"
    assert result.git_commit_sha == "pinnedsha"
    assert not any(call[:4] == ["git", "-C", str(install_dir), "checkout"] for call in runner.calls)


def test_restore_recovers_legacy_sentinel_without_owner_metadata(tmp_path: Path) -> None:
    """A sentinel without pid/hostname/timestamp has no detectable owner
    and is quarantined so the restore can proceed."""
    install_root = tmp_path / "custom_nodes"
    install_dir = install_root / "ExamplePack"
    install_dir.mkdir(parents=True)
    sentinel = install_root / ".vibecomfy-install-state" / "ExamplePack.json"
    sentinel.parent.mkdir()
    sentinel.write_text('{"complete": false, "phase": "verification"}\n', encoding="utf-8")
    runner = FakeRunner(sha="pinnedsha", porcelain="")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=install_root, runner=runner)

    # Sentinel without owner metadata is quarantined; restore proceeds.
    assert result.status == "refreshed"
    assert result.git_commit_sha == "pinnedsha"
    assert not sentinel.exists()
    assert len(list(sentinel.parent.glob(".corrupt-*"))) >= 1
    assert len(runner.calls) >= 1


def test_restore_quarantines_corrupt_sentinel_and_proceeds(tmp_path: Path) -> None:
    """A corrupt (unparseable) sentinel has no detectable owner
    and is quarantined so the restore can proceed."""
    install_root = tmp_path / "custom_nodes"
    install_dir = install_root / "ExamplePack"
    install_dir.mkdir(parents=True)
    sentinel = install_root / ".vibecomfy-install-state" / "ExamplePack.json"
    sentinel.parent.mkdir()
    sentinel.write_text("{not json", encoding="utf-8")
    runner = FakeRunner(sha="pinnedsha", porcelain="")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=install_root, runner=runner)

    # Corrupt sentinel is quarantined; restore proceeds.
    assert result.status == "refreshed"
    assert result.git_commit_sha == "pinnedsha"
    assert not sentinel.exists()
    assert len(list(sentinel.parent.glob(".corrupt-*"))) >= 1
    assert len(runner.calls) >= 1


def test_restore_keeps_sentinel_when_verification_head_mismatches(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    runner = FakeRunner(sha="wrongsha")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    def run_without_checkout_side_effect(
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        if call[:4] == ["git", "-C", call[2], "checkout"]:
            runner.calls.append(call)
            runner.cwd_calls.append(cwd)
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        return runner(args, check=check, capture_output=capture_output, text=text, cwd=cwd)

    result = restore_pack(entry, install_root=install_root, runner=run_without_checkout_side_effect)

    sentinel = install_root / ".vibecomfy-install-state" / "ExamplePack.json"
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    assert result.status == "failed"
    assert "expected git HEAD pinnedsha" in (result.error or "")
    assert payload["phase"] == "verification"


def test_restore_existing_dirty_dir_returns_skipped(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ExamplePack"
    install_dir.mkdir(parents=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "ExamplePack pinnedsha https://example.test/example.git\n"
    lockfile.write_text(original, encoding="utf-8")
    runner = FakeRunner(porcelain=" M nodes.py\n")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "skipped_dirty"
    assert result.git_commit_sha == "abc123"
    assert lockfile.read_text(encoding="utf-8") == original
    assert not any(call[:4] == ["git", "-C", str(install_dir), "checkout"] for call in runner.calls)


def test_missing_packs_for_workflow_returns_resolved_and_unresolved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text(
        '[{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("missing-packs", WorkflowSource("missing-packs"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage")
    workflow.nodes["2"] = VibeNode("2", "Qwen3CustomVoice")
    workflow.nodes["3"] = VibeNode("3", "UnknownCustomNode")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-Qwen3-TTS"]
    assert unresolved == ["UnknownCustomNode"]


def test_missing_packs_for_workflow_resolves_sam2_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("sam2", WorkflowSource("sam2"))
    workflow.nodes["1"] = VibeNode("1", "DownloadAndLoadSAM2Model")
    workflow.nodes["2"] = VibeNode("2", "Sam2Segmentation")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-segment-anything-2"]
    assert unresolved == []


def test_missing_packs_for_workflow_resolves_wan_animate_preprocess_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("wan-animate-preprocess", WorkflowSource("wan-animate-preprocess"))
    workflow.nodes["1"] = VibeNode("1", "OnnxDetectionModelLoader")
    workflow.nodes["2"] = VibeNode("2", "PoseAndFaceDetection")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-WanAnimatePreprocess"]
    assert unresolved == []


def test_missing_packs_for_workflow_resolves_rgthree_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("rgthree", WorkflowSource("rgthree"))
    workflow.nodes["1"] = VibeNode("1", "Power Lora Loader (rgthree)")
    workflow.nodes["2"] = VibeNode("2", "Fast Groups Bypasser (rgthree)")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["rgthree-comfy"]
    assert unresolved == []


def test_missing_packs_for_workflow_ignores_core_comfy_classes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("core-classes", WorkflowSource("core-classes"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage")
    workflow.nodes["2"] = VibeNode("2", "SaveImage")
    workflow.nodes["3"] = VibeNode("3", "CLIPLoader")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert packs == []
    assert unresolved == []


def test_missing_packs_for_workflow_resolves_wanvideo_i2v_helpers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("wan-i2v", WorkflowSource("wan-i2v"))
    workflow.nodes["1"] = VibeNode("1", "WanVideoLoraSelect")
    workflow.nodes["2"] = VibeNode("2", "CreateCFGScheduleFloatList")
    workflow.nodes["3"] = VibeNode("3", "WanVideoTextEmbedBridge")
    workflow.nodes["4"] = VibeNode("4", "GetImageSizeAndCount")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-KJNodes", "ComfyUI-WanVideoWrapper"]
    assert unresolved == []


def test_missing_packs_for_workflow_includes_declared_requirements_even_when_schema_knows_nodes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text(
        '[{"class_type": "VHS_VideoCombine", "pack": "ComfyUI-VideoHelperSuite", "inputs": {}, "outputs": []}]',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("declared-pack", WorkflowSource("declared-pack"))
    workflow.nodes["1"] = VibeNode("1", "VHS_VideoCombine")
    workflow.requirements.custom_nodes.append("ComfyUI-VideoHelperSuite")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-VideoHelperSuite"]
    assert unresolved == []


def test_known_schema_classes_falls_back_to_authoring_schema_when_missing(tmp_path: Path) -> None:
    classes = _known_schema_classes(tmp_path / "node_index.json")

    assert "KSampler" in classes
    assert "SaveImage" in classes


def test_resolve_node_index_path_falls_back_to_repo_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_node_index_path(Path("node_index.json"))
    repo_index = Path(__file__).resolve().parents[1] / "node_index.json"

    assert resolved.name == "node_index.json"
    if repo_index.exists():
        assert resolved.exists()
        assert resolved == repo_index
    else:
        assert resolved == Path("node_index.json")


@pytest.mark.parametrize("content", ["{", '{"class_type": "SaveImage"}'])
def test_known_schema_classes_raises_when_invalid(tmp_path: Path, content: str) -> None:
    path = tmp_path / "node_index.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        _known_schema_classes(path)
