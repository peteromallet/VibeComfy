from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DISPOSABLE_ROOT = Path("/workspace/vibecomfy-exec-spine-20260820/artifacts/t03-revision-fixtures")

WRAPPER = ROOT / "scripts" / "run_workflow_execution_spine_agent.py"


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _setup(_tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    DISPOSABLE_ROOT.mkdir(parents=True, exist_ok=True)
    case_root = Path(tempfile.mkdtemp(prefix="wrapper-", dir=DISPOSABLE_ROOT))
    project = case_root / "project"
    evidence = case_root / "evidence"
    project.mkdir()
    evidence.mkdir()
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.invalid")
    _git(project, "config", "user.name", "Test")
    (project / "seed.txt").write_text("seed\n")
    _git(project, "add", "seed.txt")
    _git(project, "commit", "-qm", "seed")
    brief = case_root / "brief.md"
    brief.write_text("brief\n")
    allowance = case_root / "allowance.json"
    allowance.write_text(json.dumps({"allowed": ["allowed.txt"], "forbidden": ["forbidden.txt"]}))
    fake = case_root / "fake_launcher.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        "project = pathlib.Path(next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "mode = os.environ.get('VCSPINE_FAKE_WRITE')\n"
        "if mode == 'forbidden': (project / 'forbidden.txt').write_text('bad')\n"
        "elif mode == 'dirty': (project / 'seed.txt').write_text('child update')\n"
        "else: (project / 'allowed.txt').write_text('ok')\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    fake.chmod(0o755)
    return project, evidence, brief, allowance, fake


def _invoke(project: Path, evidence: Path, brief: Path, allowance: Path, fake: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["VCSPINE_FAKE_LAUNCHER"] = str(fake)
    env["VCSPINE_FAKE_WRITE"] = (
        "forbidden" if "--write=forbidden" in extra
        else "dirty" if "--write=dirty" in extra
        else ""
    )
    return subprocess.run(
        [
            sys.executable, str(WRAPPER), "--task-id=T9.1", "--role=implementer",
            "--label=T9.1 [HARD] wrapper test", "--model-route=codex:gpt-5.6-luna",
            f"--query-file={brief}", f"--project-dir={project}",
            f"--allowance-file={allowance}", f"--evidence-dir={evidence}",
            "--timeout=30",
        ],
        env=env, text=True, capture_output=True,
    )


def test_receipt_shape_with_fake_launcher(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "fake result\n"
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["task_id"] == "T9.1"
    assert receipt["model_route"] == "codex:gpt-5.6-luna"
    assert receipt["resolved_model"] == "fake-model"
    assert receipt["exit"] == 0
    assert len(receipt["launcher_command"]) == 5
    assert len(receipt["brief_sha256"]) == 64
    assert len(receipt["result_sha256"]) == 64
    assert receipt["changed_files"] == ["allowed.txt"]
    assert receipt["evidence"]
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_allowance_rejection_writes_violation(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    result = _invoke(project, evidence, brief, allowance, fake, "--write=forbidden")
    assert result.returncode == 2
    assert "ALLOWANCE_VIOLATION" in result.stderr
    violation = json.loads((evidence / "T9.1-violation.json").read_text())
    assert violation["violations"] == ["forbidden.txt"]
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_changed_files_only_include_process_lifetime_delta(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    (project / "seed.txt").write_text("pre-existing tracked edit\n")
    (project / "pre-existing-untracked.txt").write_text("pre-existing untracked file\n")

    result = _invoke(project, evidence, brief, allowance, fake)

    assert result.returncode == 0, result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["changed_files"] == ["allowed.txt"]
    assert not (evidence / "T9.1-violation.json").exists()
    assert (project / "seed.txt").read_text() == "pre-existing tracked edit\n"
    assert (project / "pre-existing-untracked.txt").exists()


def test_child_change_to_pre_dirty_path_is_reported_and_rejected(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    (project / "seed.txt").write_text("pre-existing tracked edit\n")
    (project / "pre-existing-untracked.txt").write_text("pre-existing untracked file\n")

    result = _invoke(project, evidence, brief, allowance, fake, "--write=dirty")

    assert result.returncode == 2
    assert "ALLOWANCE_VIOLATION" in result.stderr
    violation = json.loads((evidence / "T9.1-violation.json").read_text())
    assert violation["changed_files"] == ["seed.txt"]
    assert violation["violations"] == ["seed.txt"]
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_overlap_rejection_does_not_launch(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    (evidence / "active-allowances.json").write_text(json.dumps({
        "other": {
            "task_id": "other", "allowance_file": "other.json",
            "worktree": str(project), "start_ts": "now", "pid": os.getpid(),
            "allowed": ["other.txt"],
        }
    }))
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode == 2
    assert "ALLOWANCE_OVERLAP" in result.stderr
    assert not (project / "allowed.txt").exists()


def test_missing_allowance_rejects_before_launch(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    allowance.unlink()
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode == 2
    assert "ALLOWANCE_INVALID" in result.stderr
    assert not (project / "allowed.txt").exists()
