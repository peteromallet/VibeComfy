"""B14b regression tests for transactional on-demand pack clones."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.errors import OnDemandCloneError
from vibecomfy.schema import on_demand
from vibecomfy.schema.on_demand import OnDemandInstallSchemaProvider


def _ref(slug: str = "sample-pack") -> SimpleNamespace:
    return SimpleNamespace(slug=slug, url="https://example.invalid/sample-pack")


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _source_repo(tmp_path: Path, name: str = "source") -> tuple[Path, str, str]:
    source = tmp_path / name
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
    _git(source, "config", "user.email", "tests@example.invalid")
    _git(source, "config", "user.name", "VibeComfy tests")
    (source / "node.py").write_text("VERSION = 1\n", encoding="utf-8")
    _git(source, "add", "node.py")
    _git(source, "commit", "-m", "one")
    first = _git(source, "rev-parse", "HEAD")
    (source / "node.py").write_text("VERSION = 2\n", encoding="utf-8")
    _git(source, "commit", "-am", "two")
    second = _git(source, "rev-parse", "HEAD")
    return source, first, second


def test_clone_slug_cannot_escape_sandbox(tmp_path: Path) -> None:
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")

    with pytest.raises(ValueError, match="path-safe"):
        provider._ensure_clone(_ref("../outside"))
    assert not (tmp_path / "outside").exists()


def test_failed_clone_preserves_git_diagnostics_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")

    def fail(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            7, command, output="clone stdout", stderr="clone stderr"
        )

    monkeypatch.setattr(on_demand.subprocess, "run", fail)
    with pytest.raises(OnDemandCloneError) as caught:
        provider._ensure_clone(_ref())

    message = str(caught.value)
    assert "returncode=7" in message
    assert "clone stdout" in message
    assert "clone stderr" in message
    assert provider.last_clone_error == message
    sandbox = tmp_path / "sandbox"
    assert not (sandbox / "sample-pack").exists()
    assert list(sandbox.glob(".*-*/")) == []


def test_incomplete_clone_is_cleaned_and_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "sandbox"
    target = sandbox / "sample-pack"
    (target / ".git").mkdir(parents=True)
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["git", "clone"]:
            Path(command[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(command, 0, stdout="commit-123\n", stderr="")

    monkeypatch.setattr(on_demand.subprocess, "run", fake_run)
    result = provider._ensure_clone(_ref())

    assert result == target
    assert (target / ".vibecomfy-clone-complete.json").is_file()


def test_empty_preexisting_clone_is_not_a_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "sandbox"
    target = sandbox / "sample-pack"
    target.mkdir(parents=True)
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["git", "clone"]:
            Path(command[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(command, 0, stdout="commit-456\n", stderr="")

    monkeypatch.setattr(on_demand.subprocess, "run", fake_run)
    result = provider._ensure_clone(_ref())

    assert result == target
    marker = json.loads((target / ".vibecomfy-clone-complete.json").read_text(encoding="utf-8"))
    assert marker["complete"] is True
    assert marker["head"] == "commit-456"


def test_incomplete_clone_with_active_reader_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = tmp_path / "sandbox"
    target = sandbox / "sample-pack"
    (target / ".git").mkdir(parents=True)
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)
    def fail_if_called(command: list[str], timeout: int) -> None:
        raise AssertionError(command)

    monkeypatch.setattr(on_demand, "_run_git", fail_if_called)

    with provider._reader_lease(target):
        with pytest.raises(OnDemandCloneError, match="active reader"):
            provider._ensure_clone(_ref())
        assert target.exists()


def test_clone_publishes_only_after_completion_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = OnDemandInstallSchemaProvider(sandbox_root=tmp_path / "sandbox")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["check"] is True
        if command[:2] == ["git", "clone"]:
            Path(command[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(command, 0, stdout="commit-123\n", stderr="")

    monkeypatch.setattr(on_demand.subprocess, "run", fake_run)
    target = provider._ensure_clone(_ref())

    assert target is not None
    marker = target / ".vibecomfy-clone-complete.json"
    assert marker.exists()
    assert '"complete": true' in marker.read_text(encoding="utf-8")
    assert list((tmp_path / "sandbox").glob(".*-*/")) == []


def test_active_reader_is_not_evicted(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    pack = sandbox / "sample-pack"
    pack.mkdir(parents=True)
    (pack / "payload").write_text("data", encoding="utf-8")
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox, max_packs=0)

    with provider._reader_lease(pack):
        provider._enforce_cap()
        assert pack.exists()
    provider._enforce_cap()
    assert not pack.exists()


def test_stale_reader_lease_is_removed_and_pack_can_be_evicted(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    pack = sandbox / "sample-pack"
    pack.mkdir(parents=True)
    (pack / ".vibecomfy-reader-99999999-stale.lease").write_text("99999999", encoding="ascii")
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox, max_packs=0)

    provider._enforce_cap()

    assert not pack.exists()


def test_markerless_legacy_clone_reuses_only_matching_origin_and_pin(tmp_path: Path) -> None:
    source, _first, second = _source_repo(tmp_path)
    sandbox = tmp_path / "sandbox"
    target = sandbox / "sample-pack"
    sandbox.mkdir()
    subprocess.run(["git", "clone", str(source), str(target)], check=True, capture_output=True)
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)
    ref = SimpleNamespace(slug="sample-pack", url=str(source), commit=second, version=None)

    assert provider._ensure_clone(ref) == target
    assert _git(target, "rev-parse", "HEAD") == second
    assert not (target / on_demand._CLONE_COMPLETE_MARKER).exists()


def test_markerless_legacy_clone_with_wrong_pin_is_recloned_at_requested_pin(
    tmp_path: Path,
) -> None:
    source, first, second = _source_repo(tmp_path)
    sandbox = tmp_path / "sandbox"
    target = sandbox / "sample-pack"
    sandbox.mkdir()
    subprocess.run(["git", "clone", str(source), str(target)], check=True, capture_output=True)
    _git(target, "checkout", first)
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)
    ref = SimpleNamespace(slug="sample-pack", url=str(source), commit=second, version=None)

    assert provider._ensure_clone(ref) == target
    assert _git(target, "rev-parse", "HEAD") == second
    marker = json.loads((target / on_demand._CLONE_COMPLETE_MARKER).read_text(encoding="utf-8"))
    assert marker["pin"] == second
    assert marker["head"] == second


def test_markerless_legacy_clone_with_wrong_origin_is_not_reused(tmp_path: Path) -> None:
    source_a, _first_a, second_a = _source_repo(tmp_path, "source-a")
    source_b, _first_b, second_b = _source_repo(tmp_path, "source-b")
    sandbox = tmp_path / "sandbox"
    target = sandbox / "sample-pack"
    sandbox.mkdir()
    subprocess.run(["git", "clone", str(source_a), str(target)], check=True, capture_output=True)
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)
    ref = SimpleNamespace(slug="sample-pack", url=str(source_b), commit=second_b, version=None)

    assert provider._ensure_clone(ref) == target
    assert _git(target, "remote", "get-url", "origin") == str(source_b)
    assert _git(target, "rev-parse", "HEAD") == second_b
