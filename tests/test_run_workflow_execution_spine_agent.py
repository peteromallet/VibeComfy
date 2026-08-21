from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DISPOSABLE_ROOT = Path("/workspace/vibecomfy-exec-spine-20260820/artifacts/t03-revision2-fixtures")

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
        "import json, os, pathlib, sys, time\n"
        "project = pathlib.Path(next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "mode = os.environ.get('VCSPINE_FAKE_WRITE')\n"
        "if os.environ.get('VCSPINE_FAKE_INTERRUPT_RECEIPT'):\n"
        "    pathlib.Path(os.environ['VCSPINE_FAKE_INTERRUPT_RECEIPT']).write_text(json.dumps({'task_id': 'T9.1', 'status': 'interrupted', 'sentinel': 'preserve'}))\n"
        "elif os.environ.get('VCSPINE_FAKE_MODE') == 'sleep':\n"
        "    pathlib.Path(os.environ['VCSPINE_FAKE_HANDSHAKE']).write_text(str(os.getpid()))\n"
        "    print('fake child ready', flush=True)\n"
        "    time.sleep(60)\n"
        "elif mode == 'forbidden': (project / 'forbidden.txt').write_text('bad')\n"
        "elif mode == 'dirty': (project / 'seed.txt').write_text('child update')\n"
        "elif mode == 'hidden':\n"
        "    (project / '.gitignore').write_text('hidden-created/\\n')\n"
        "    hidden = project / 'hidden-created'\n"
        "    hidden.mkdir()\n"
        "    (hidden / 'secret.txt').write_text('hidden')\n"
        "else: (project / 'allowed.txt').write_text('ok')\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    fake.chmod(0o755)
    return project, evidence, brief, allowance, fake


def _invoke(
    project: Path,
    evidence: Path,
    brief: Path,
    allowance: Path,
    fake: Path,
    *extra: str,
    wait: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.Popen[str]:
    env = os.environ.copy()
    env["VCSPINE_FAKE_LAUNCHER"] = str(fake)
    env["VCSPINE_FAKE_WRITE"] = (
        "forbidden" if "--write=forbidden" in extra
        else "dirty" if "--write=dirty" in extra
        else "hidden" if "--write=hidden" in extra
        else ""
    )
    env.pop("VCSPINE_FAKE_MODE", None)
    env.pop("VCSPINE_FAKE_HANDSHAKE", None)
    env.pop("VCSPINE_FAKE_INTERRUPT_RECEIPT", None)
    if "--sleep" in extra:
        env["VCSPINE_FAKE_MODE"] = "sleep"
        env["VCSPINE_FAKE_HANDSHAKE"] = str(evidence / "child-handshake")
    if "--interrupt-receipt" in extra:
        env["VCSPINE_FAKE_INTERRUPT_RECEIPT"] = str(evidence / "T9.1-receipt.json")
    command = [
        sys.executable, str(WRAPPER), "--task-id=T9.1", "--role=implementer",
        "--label=T9.1 [HARD] wrapper test", "--model-route=codex:gpt-5.6-luna",
        f"--query-file={brief}", f"--project-dir={project}",
        f"--allowance-file={allowance}", f"--evidence-dir={evidence}",
        "--timeout=30",
    ]
    runner = subprocess.run if wait else subprocess.Popen
    return runner(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


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

def test_hidden_child_create_under_new_ignore_rule_is_reported_and_rejected(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    allowance.write_text(json.dumps({"allowed": ["*"], "forbidden": ["hidden-created/**"]}))

    result = _invoke(project, evidence, brief, allowance, fake, "--write=hidden")

    assert result.returncode == 2
    assert "ALLOWANCE_VIOLATION" in result.stderr
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    violation = json.loads((evidence / "T9.1-violation.json").read_text())
    assert "hidden-created/secret.txt" in receipt["changed_files"]
    assert "hidden-created/secret.txt" in violation["violations"]
    assert receipt["changed_files"] == sorted(receipt["changed_files"])
    assert receipt["evidence"]
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


@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGHUP"])
def test_interrupt_writes_partial_receipt_and_leaves_child_running(tmp_path: Path, signal_name: str) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    wrapper = _invoke(project, evidence, brief, allowance, fake, "--sleep", wait=False)
    handshake = evidence / "child-handshake"
    deadline = time.monotonic() + 5
    while not handshake.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert handshake.exists()

    wrapper.send_signal(getattr(signal, signal_name))
    wrapper_returncode = wrapper.wait(timeout=5)
    assert wrapper_returncode != 0
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["status"] == "interrupted"
    assert receipt["signal"] == signal_name
    assert receipt["wrapper_pid"] == wrapper.pid
    assert receipt["child_pid"] == int(handshake.read_text())
    assert receipt["preserved_args"] == {
        "task_id": "T9.1",
        "role": "implementer",
        "label": "T9.1 [HARD] wrapper test",
        "model_route": "codex:gpt-5.6-luna",
        "gate": None,
        "query_file": str(brief),
        "project_dir": str(project),
        "allowance_file": str(allowance),
        "evidence_dir": str(evidence),
        "timeout": 30,
    }
    assert receipt["start_ts"] <= receipt["interrupted_ts"]
    os.kill(receipt["child_pid"], 0)
    os.kill(receipt["child_pid"], signal.SIGTERM)
    wrapper.communicate(timeout=5)
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_interrupted_receipt_survives_normal_completion(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    result = _invoke(project, evidence, brief, allowance, fake, "--interrupt-receipt")
    assert result.returncode == 0, result.stderr
    assert json.loads((evidence / "T9.1-receipt.json").read_text()) == {
        "task_id": "T9.1",
        "status": "interrupted",
        "sentinel": "preserve",
    }


def test_stop_marker_requires_literal_line_start() -> None:
    spec = importlib.util.spec_from_file_location("workflow_execution_wrapper", WRAPPER)
    assert spec is not None and spec.loader is not None
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)

    assert wrapper._stop_marker("JUDGMENT_REQUIRED: review this\nSTOP: stop now") == "JUDGMENT_REQUIRED: review this"
    assert wrapper._stop_marker("STOP: stop now") == "STOP: stop now"
    assert wrapper._stop_marker(
        "# JUDGMENT_REQUIRED handling\n"
        "see JUDGMENT_REQUIRED above\n"
        "example JUDGMENT_REQUIRED: not a marker\n"
        "JUDGMENT_REQUIRED\n"
        " JUDGMENT_REQUIRED: leading whitespace\n"
        " STOP: leading whitespace\n"
        "ordinary prose"
    ) == ""


def test_finalization_failure_does_not_clobber_interrupted_receipt(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("workflow_execution_wrapper_finalization", WRAPPER)
    assert spec is not None and spec.loader is not None
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    receipt_path = evidence / "T9.1-receipt.json"
    partial = {"task_id": "T9.1", "status": "interrupted", "sentinel": "preserve"}
    receipt_path.write_text(json.dumps(partial))

    failure = {
        "task_id": "T9.1",
        "cleanup": {"attempted": True, "succeeded": False, "error": {"type": "OSError", "message": "cleanup"}},
        "registry_release": {"attempted": True, "succeeded": True, "error": None},
    }
    assert wrapper._record_finalization_failure(evidence, receipt_path, partial.copy(), failure) is None
    assert json.loads(receipt_path.read_text()) == partial
