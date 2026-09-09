from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

import vibecomfy.commands.doctor as doctor_cmd
from vibecomfy.security.provenance import Provenance
from vibecomfy.node_packs import LockEntry


def _write_scratchpad(path: Path) -> Path:
    path.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow(id="doctor-lockfile", source=WorkflowSource(id="doctor-lockfile"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="CLIPTextEncode", inputs={"clip": "clip", "text": "hello"}, uid="1")
    return workflow
""",
        encoding="utf-8",
    )
    return path


def _run_doctor(path: Path, *, allow_drift: bool = False) -> int:
    return doctor_cmd._cmd_doctor(argparse.Namespace(path=str(path), allow_drift=allow_drift, lint=False))


@pytest.fixture
def doctor_scratchpad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor_cmd, "get_schema_provider", lambda _mode: None)
    real_load_bundle = doctor_cmd.load_bundle
    monkeypatch.setattr(
        doctor_cmd,
        "load_bundle",
        lambda path: real_load_bundle(path, trust=Provenance.USER_CONFIRMED),
    )
    return _write_scratchpad(tmp_path / "scratch.py")


def test_doctor_lockfile_absent_skips_silently(
    doctor_scratchpad: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(doctor_cmd, "read_lockfile", lambda: [])

    assert _run_doctor(doctor_scratchpad) == 0

    assert "lockfile" not in capsys.readouterr().out


def test_doctor_lockfile_missing_pack_warns_without_failing(
    doctor_scratchpad: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        doctor_cmd,
        "read_lockfile",
        lambda: [LockEntry(name="MissingPack", git_commit_sha="abc123", url="https://example.test/missing.git")],
    )

    assert _run_doctor(doctor_scratchpad) == 0

    captured = capsys.readouterr()
    assert "Nodepack lockfile warnings:" in captured.out
    assert "MissingPack in lockfile but not installed; skipping drift check" in captured.out


def test_doctor_lockfile_matching_pack_succeeds(
    doctor_scratchpad: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack = tmp_path / "vendor" / "MatchPack"
    pack.mkdir(parents=True)
    (pack / "nodes.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(
        doctor_cmd,
        "read_lockfile",
        lambda: [
            LockEntry(
                name="MatchPack",
                git_commit_sha="abc123",
                url="https://example.test/match.git",
                source_sha256={"nodes.py": "ad64355106bb158b020ecf9702be48f7730fc091dd4bb6a2f092b40393495b3d"},
            )
        ],
    )
    monkeypatch.setattr(
        doctor_cmd.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="abc123\n"),
    )

    assert _run_doctor(doctor_scratchpad) == 0

    assert "nodepack lockfile" not in capsys.readouterr().out.lower()


def test_doctor_lockfile_mismatch_fails_closed(
    doctor_scratchpad: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "vendor" / "DriftPack").mkdir(parents=True)
    monkeypatch.setattr(
        doctor_cmd,
        "read_lockfile",
        lambda: [LockEntry(name="DriftPack", git_commit_sha="expected", url="https://example.test/drift.git")],
    )
    monkeypatch.setattr(
        doctor_cmd.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="actual\n"),
    )

    assert _run_doctor(doctor_scratchpad) == 1

    captured = capsys.readouterr()
    assert "Layer: nodepack lockfile drift" in captured.out
    assert "does not match lockfile git_commit_sha expected" in captured.out


def test_doctor_lockfile_mismatch_allow_drift_warns(
    doctor_scratchpad: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "vendor" / "DriftPack").mkdir(parents=True)
    monkeypatch.setattr(
        doctor_cmd,
        "read_lockfile",
        lambda: [LockEntry(name="DriftPack", git_commit_sha="expected", url="https://example.test/drift.git")],
    )
    monkeypatch.setattr(
        doctor_cmd.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="actual\n"),
    )

    assert _run_doctor(doctor_scratchpad, allow_drift=True) == 0

    captured = capsys.readouterr()
    assert "Nodepack lockfile drift warnings:" in captured.out
    assert "does not match lockfile git_commit_sha expected" in captured.out
