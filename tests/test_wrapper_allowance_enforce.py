"""Focused tests for WRAPPER-ALLOWANCE-ENFORCE (E1/E2)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "run_workflow_execution_spine_agent.py"


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _setup(tmp_path: Path, allowed=None, forbidden=None) -> tuple[Path, Path, Path, Path]:
    case_root = Path(tempfile.mkdtemp(prefix="wrapper-enforce-", dir=tmp_path))
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
    if allowed is None:
        allowed = ["allowed.txt"]
    if forbidden is None:
        forbidden = ["forbidden.txt"]
    allowance.write_text(json.dumps({"allowed": allowed, "forbidden": forbidden}))
    return project, evidence, brief, allowance


def _write_fake(project: Path, case_root: Path, body: str) -> Path:
    fake = case_root / "fake_launcher.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, subprocess, sys, os\n"
        + body
    )
    fake.chmod(0o755)
    return fake


def _invoke(project: Path, evidence: Path, brief: Path, allowance: Path, fake: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["VCSPINE_FAKE_LAUNCHER"] = str(fake)
    command = [
        sys.executable, str(WRAPPER), "--task-id=T9.1", "--role=implementer",
        "--label=T9.1 [HARD] wrapper test", "--model-route=codex:gpt-5.6-luna",
        f"--query-file={brief}", f"--project-dir={project}",
        f"--allowance-file={allowance}", f"--evidence-dir={evidence}",
        f"--timeout={timeout}",
    ]
    return subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_commit_out_of_allowance_file_fails(tmp_path: Path) -> None:
    """(a) synthetic dispatch committing an out-of-allowance file -> allowance_violation."""
    project, evidence, brief, allowance = _setup(tmp_path, allowed=["allowed.txt"], forbidden=["forbidden.txt"])
    case_root = allowance.parent
    fake = _write_fake(project, case_root,
        "project = pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "(project / 'outside.txt').write_text('bad')\n"
        "subprocess.run(['git','add','outside.txt'], cwd=project, check=True)\n"
        "subprocess.run(['git','commit','-qm','add outside'], cwd=project, check=True)\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode != 0, result.stderr
    assert "ALLOWANCE_VIOLATION" in result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "allowance_violation"
    assert "outside.txt" in receipt["violating_files"]
    # Do NOT revert - file remains committed
    assert (project / "outside.txt").exists()
    # base_sha..HEAD includes it
    assert "outside.txt" in receipt.get("committed_files", [])


def test_forbidden_path_commit_fails(tmp_path: Path) -> None:
    """(b) forbidden-path commit -> same."""
    project, evidence, brief, allowance = _setup(tmp_path, allowed=["allowed.txt", "outside.txt"], forbidden=["tests/live_agentic_harness/**"])
    case_root = allowance.parent
    fake = _write_fake(project, case_root,
        "project = pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "p = project / 'tests' / 'live_agentic_harness' / 'evil.txt'\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        "p.write_text('bad')\n"
        "subprocess.run(['git','add','tests/live_agentic_harness/evil.txt'], cwd=project, check=True)\n"
        "subprocess.run(['git','commit','-qm','add forbidden'], cwd=project, check=True)\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode != 0, result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "allowance_violation"
    assert any("live_agentic_harness" in f for f in receipt["violating_files"])


def test_fully_in_allowance_commit_succeeds(tmp_path: Path) -> None:
    """(c) fully-in-allowance commit -> normal success receipt, exit 0."""
    project, evidence, brief, allowance = _setup(tmp_path, allowed=["allowed.txt"], forbidden=["forbidden.txt"])
    case_root = allowance.parent
    fake = _write_fake(project, case_root,
        "project = pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "(project / 'allowed.txt').write_text('ok')\n"
        "subprocess.run(['git','add','allowed.txt'], cwd=project, check=True)\n"
        "subprocess.run(['git','commit','-qm','add allowed'], cwd=project, check=True)\n"
        "print('{\"result\": \"done\"}')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode == 0, result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "success"
    assert receipt["exit"] == 0
    assert "allowed.txt" in receipt.get("committed_files", [])


def test_child_exit_nonzero_empty_output_fails(tmp_path: Path) -> None:
    """(d) child exit!=0 with empty output -> status=child_failed."""
    project, evidence, brief, allowance = _setup(tmp_path)
    case_root = allowance.parent
    fake = _write_fake(project, case_root,
        "import sys\n"
        "print('Retry budget exhausted ... 429', file=sys.stderr)\n"
        "sys.exit(1)\n"
    )
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode != 0, result.stderr
    assert "CHILD_FAILED" in result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "child_failed"
    assert receipt["child_exit"] == 1
    # Must not be exit 0 with empty result
    assert receipt["empty_result"] is True
    assert "429" in receipt.get("child_stderr_tail", "") or "429" in result.stderr


def test_child_exit_zero_with_empty_output_also_fails(tmp_path: Path) -> None:
    """Empty stdout even with exit 0 -> child_failed (never exit 0 with empty result)."""
    project, evidence, brief, allowance = _setup(tmp_path)
    case_root = allowance.parent
    fake = _write_fake(project, case_root,
        "import sys\n"
        "# no stdout, exit 0\n"
        "sys.exit(0)\n"
    )
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode != 0
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "child_failed"
    assert receipt["empty_result"] is True


def test_child_exit_zero_with_real_result_succeeds(tmp_path: Path) -> None:
    """(e) child exit 0 with real result -> unchanged success path."""
    project, evidence, brief, allowance = _setup(tmp_path)
    case_root = allowance.parent
    fake = _write_fake(project, case_root,
        "project = pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "(project / 'allowed.txt').write_text('ok')\n"
        "print('{\"result\": \"real document\"}')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode == 0, result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "success"
    assert receipt["exit"] == 0
