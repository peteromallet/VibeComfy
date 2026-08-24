from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


WRAPPER = ROOT / "scripts" / "run_workflow_execution_spine_agent.py"


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _setup(_tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    case_root = Path(tempfile.mkdtemp(prefix="wrapper-", dir=_tmp_path))
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
        "if os.environ.get('VCSPINE_FAKE_SENTINEL'): pathlib.Path(os.environ['VCSPINE_FAKE_SENTINEL']).write_text('launched')\n"
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
    role: str = "implementer",
    brief_text: str | None = None,
    sentinel: Path | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.Popen[str]:
    if brief_text is not None:
        brief.write_text(brief_text)
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
    env.pop("VCSPINE_FAKE_SENTINEL", None)
    if sentinel is not None:
        env["VCSPINE_FAKE_SENTINEL"] = str(sentinel)
    if "--sleep" in extra:
        env["VCSPINE_FAKE_MODE"] = "sleep"
        env["VCSPINE_FAKE_HANDSHAKE"] = str(evidence / "child-handshake")
    if "--interrupt-receipt" in extra:
        env["VCSPINE_FAKE_INTERRUPT_RECEIPT"] = str(evidence / "T9.1-receipt.json")
    command = [
        sys.executable, str(WRAPPER), "--task-id=T9.1", f"--role={role}",
        "--label=T9.1 [HARD] wrapper test", "--model-route=codex:gpt-5.6-luna",
        f"--query-file={brief}", f"--project-dir={project}",
        f"--allowance-file={allowance}", f"--evidence-dir={evidence}",
        "--timeout=30",
    ]
    runner = subprocess.run if wait else subprocess.Popen
    return runner(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _load_wrapper(name: str = "workflow_execution_wrapper_sweep"):
    spec = importlib.util.spec_from_file_location(name, WRAPPER)
    assert spec is not None and spec.loader is not None
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    return wrapper


def _dead_pid(wrapper) -> int:
    candidate = os.getpid() + 1
    while wrapper._pid_exists(candidate):
        candidate += 1
    return candidate


def _write_registry(evidence: Path, task_id: str, entry: dict) -> None:
    (evidence / "active-allowances.json").write_text(json.dumps({task_id: entry}))


def test_dead_pid_grace_clears_synthetic_dead_wrapper_and_writes_note(tmp_path: Path) -> None:
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper()
    dead_pid = _dead_pid(wrapper)
    _write_registry(evidence, "T1.2-precode-dead-wrapper", {
        "task_id": "T1.2-precode-dead-wrapper",
        "allowance_file": str(allowance),
        "worktree": str(project),
        "start_ts_epoch": time.time() - wrapper.DEAD_PID_GRACE_SECONDS - 120,
        "pid": dead_pid,
        "allowed": ["allowed.txt"],
    })

    registry, _candidate = wrapper._registry_guard(
        evidence, "next-dispatch", allowance, project, ["allowed.txt"]
    )
    try:
        assert "T1.2-precode-dead-wrapper" not in registry
        assert "next-dispatch" in registry
    finally:
        wrapper._registry_release(evidence, "next-dispatch")

    note = json.loads((evidence / "stale-allowance-cleared.json").read_text())
    assert set(note) == {"cleared_task_ids", "cleared_ts", "reason"}
    assert note["cleared_task_ids"] == ["T1.2-precode-dead-wrapper"]
    assert "dead-PID grace" in note["reason"]
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_dead_pid_younger_than_grace_is_retained_then_cleared_later(tmp_path: Path) -> None:
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_dead_pid_grace_boundary")
    dead_pid = _dead_pid(wrapper)
    task_id = "dead-young"
    entry = {
        "task_id": task_id,
        "allowance_file": str(allowance),
        "worktree": str(project),
        "start_ts_epoch": time.time() - 1,
        "pid": dead_pid,
        "allowed": ["allowed.txt"],
    }
    _write_registry(evidence, task_id, entry)

    first = _invoke(project, evidence, _brief, allowance, _fake)
    assert first.returncode == 2
    assert "ALLOWANCE_OVERLAP" in first.stderr
    assert task_id in json.loads((evidence / "active-allowances.json").read_text())
    assert not (evidence / "stale-allowance-cleared.json").exists()

    entry["start_ts_epoch"] = time.time() - wrapper.DEAD_PID_GRACE_SECONDS - 120
    _write_registry(evidence, task_id, entry)
    registry, _candidate = wrapper._registry_guard(
        evidence, "next-dispatch", allowance, project, ["allowed.txt"]
    )
    try:
        assert task_id not in registry
    finally:
        wrapper._registry_release(evidence, "next-dispatch")
    note = json.loads((evidence / "stale-allowance-cleared.json").read_text())
    assert note["cleared_task_ids"] == [task_id]


def test_live_pid_is_retained_regardless_of_age(tmp_path: Path) -> None:
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_live_pid")
    task_id = "live-old"
    _write_registry(evidence, task_id, {
        "task_id": task_id,
        "allowance_file": str(allowance),
        "worktree": str(project.parent / "other-worktree"),
        "start_ts_epoch": time.time() - wrapper.STALE_SECONDS - 120,
        "pid": os.getpid(),
        "allowed": ["live.txt"],
    })

    registry, _candidate = wrapper._registry_guard(
        evidence, "next-dispatch", allowance, project, ["allowed.txt"]
    )
    try:
        assert task_id in registry
    finally:
        wrapper._registry_release(evidence, "next-dispatch")
    assert task_id in json.loads((evidence / "active-allowances.json").read_text())
    assert not (evidence / "stale-allowance-cleared.json").exists()


@pytest.mark.parametrize("pid", [None, "1234"])
@pytest.mark.parametrize("age,cleared", [
    (1, False),
    (6 * 60 * 60 + 120, True),
])
def test_missing_or_non_int_pid_uses_six_hour_path(
    tmp_path: Path, pid, age: float, cleared: bool
) -> None:
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_missing_pid")
    task_id = f"missing-pid-{pid}-{age}"
    _write_registry(evidence, task_id, {
        "task_id": task_id,
        "allowance_file": str(allowance),
        "worktree": str(project.parent / "other-worktree"),
        "start_ts_epoch": time.time() - age,
        "pid": pid,
        "allowed": ["missing.txt"],
    })

    registry, _candidate = wrapper._registry_guard(
        evidence, "next-dispatch", allowance, project, ["allowed.txt"]
    )
    try:
        assert (task_id not in registry) is cleared
    finally:
        wrapper._registry_release(evidence, "next-dispatch")
    if cleared:
        note = json.loads((evidence / "stale-allowance-cleared.json").read_text())
        assert note["cleared_task_ids"] == [task_id]
        assert "six-hour missing/non-int PID" in note["reason"]
    else:
        assert not (evidence / "stale-allowance-cleared.json").exists()


def test_mixed_sweep_note_names_dead_and_six_hour_classes(tmp_path: Path) -> None:
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_mixed_sweep")
    dead_pid = _dead_pid(wrapper)
    now = time.time()
    _write_registry(evidence, "dead-entry", {
        "task_id": "dead-entry",
        "allowance_file": str(allowance),
        "worktree": str(project),
        "start_ts_epoch": now - wrapper.DEAD_PID_GRACE_SECONDS - 120,
        "pid": dead_pid,
        "allowed": ["allowed.txt"],
    })
    registry_path = evidence / "active-allowances.json"
    registry = json.loads(registry_path.read_text())
    registry["missing-entry"] = {
        "task_id": "missing-entry",
        "allowance_file": str(allowance),
        "worktree": str(project.parent / "other-worktree"),
        "start_ts_epoch": now - wrapper.STALE_SECONDS - 120,
        "allowed": ["missing.txt"],
    }
    registry_path.write_text(json.dumps(registry))

    active, _candidate = wrapper._registry_guard(
        evidence, "next-dispatch", allowance, project, ["allowed.txt"]
    )
    try:
        assert "dead-entry" not in active
        assert "missing-entry" not in active
    finally:
        wrapper._registry_release(evidence, "next-dispatch")
    note = json.loads((evidence / "stale-allowance-cleared.json").read_text())
    assert note["cleared_task_ids"] == ["dead-entry", "missing-entry"]
    assert "dead-PID grace" in note["reason"]
    assert "six-hour missing/non-int PID" in note["reason"]


@pytest.mark.parametrize(
    "brief_text",
    [
        "Record your own end_ts in the evidence result.",
        "Record this run's receipt digest and result_sha256.",
        "Do not record the receipt PATH; record your own end_ts.",
        "The wrapper writes its own end_ts post-exit; record your own end_ts.",
        "Your own end_ts is required in the result.",
        "Your own receipt digest is required in the result.",
        "Your own result_sha256 is required in the result.",
        "The result must contain your own end_ts.",
        "The result must contain your own receipt digest.",
        "The result must contain your own result_sha256.",
        "Your own end_ts is mandatory in the result.",
        "Your own receipt digest is mandatory in the result.",
        "Your own result_sha256 is mandatory in the result.",
        "The result must include your own end_ts.",
        "The result must include your own receipt digest.",
        "The result must include your own result_sha256.",
        "Your own receipt digest is needed in the result.",
        "Your own result_sha256 is expected in the result.",
    ],
)
def test_evidence_self_referential_brief_rejects_before_launch(tmp_path: Path, brief_text: str) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    sentinel = evidence / "launcher-started"

    result = _invoke(
        project,
        evidence,
        brief,
        allowance,
        fake,
        role="evidence",
        brief_text=brief_text,
        sentinel=sentinel,
    )

    assert result.returncode == 2
    assert "EVIDENCE_BRIEF_SELF_REFERENTIAL" in result.stderr
    assert not sentinel.exists()
    assert not (evidence / "active-allowances.json").exists()
    assert not (evidence / "T9.1-receipt.json").exists()


def test_compliant_evidence_brief_launches_and_records_normal_receipt(tmp_path: Path) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    sentinel = evidence / "launcher-started"

    result = _invoke(
        project,
        evidence,
        brief,
        allowance,
        fake,
        role="evidence",
        brief_text="Record the receipt PATH, wrapper PID, and wrapper start timestamp only.",
        sentinel=sentinel,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.read_text() == "launched"
    receipt = json.loads((evidence / "T9.1-receipt.json").read_text())
    assert receipt["role"] == "evidence"
    assert receipt["exit"] == 0
    assert not json.loads((evidence / "active-allowances.json").read_text())


@pytest.mark.parametrize(
    "brief_text",
    [
        "Do not record your own end_ts.",
        "The wrapper writes its own end_ts post-exit.",
        "Do not record your own end_ts; the wrapper writes it post-exit.",
        "The wrapper writes its own end_ts and receipt digest post-exit.",
    ],
)
def test_evidence_brief_negation_and_wrapper_explanation_pass(
    tmp_path: Path, brief_text: str
) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    sentinel = evidence / "launcher-started"

    result = _invoke(
        project,
        evidence,
        brief,
        allowance,
        fake,
        role="evidence",
        brief_text=brief_text,
        sentinel=sentinel,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.read_text() == "launched"


@pytest.mark.parametrize("role", ["implementer", "reviewer", "integration"])
def test_self_referential_phrases_do_not_guard_non_evidence_roles(tmp_path: Path, role: str) -> None:
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    sentinel = evidence / "launcher-started"

    result = _invoke(
        project,
        evidence,
        brief,
        allowance,
        fake,
        role=role,
        brief_text="Record your own end_ts and receipt digest.",
        sentinel=sentinel,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.read_text() == "launched"
    assert json.loads((evidence / "T9.1-receipt.json").read_text())["role"] == role


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
            "allowed": ["allowed.txt"],
        }
    }))
    result = _invoke(project, evidence, brief, allowance, fake)
    assert result.returncode == 2
    assert "ALLOWANCE_OVERLAP" in result.stderr
    assert not (project / "allowed.txt").exists()


def test_allowances_overlap_narrowed_to_intersecting_mutating_paths(tmp_path: Path) -> None:
    """WRAPPER-OVERLAP-NARLOW + R2: read-only sides (empty ``allowed``) never
    overlap; cross-worktree mutating pairs resolve via conservative fail-closed
    pattern intersection; same-worktree mutating pairs serialize unconditionally
    (covered by the R2 F-b test below).
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_overlap_narlow")
    shared = tmp_path / "shared-worktree"
    other = tmp_path / "other-worktree"

    def entry(worktree: Path, allowed: list[str]) -> dict[str, object]:
        return {"task_id": "t", "worktree": str(worktree), "allowed": allowed}

    # Same worktree + one side empty: a read-only task blocks nothing.
    assert wrapper._allowances_overlap(entry(shared, []), entry(shared, ["allowed.txt"])) is False
    assert wrapper._allowances_overlap(entry(shared, ["allowed.txt"]), entry(shared, [])) is False
    # Same worktree + disjoint non-empty alloweds: serialized since R2 (F-b),
    # regardless of path reasoning.
    assert wrapper._allowances_overlap(entry(shared, ["docs/**"]), entry(shared, ["vibecomfy/**"]), same_worktree=True) is True
    # Same worktree + intersecting non-empty alloweds.
    assert wrapper._allowances_overlap(entry(shared, ["docs/**"]), entry(shared, ["docs/x.md"])) is True
    # Different worktrees + crossing globs that fnmatch cannot cross-check:
    # conservative intersection must admit them as overlapping (R2 F-a;
    # pre-R2 this pair returned False).
    assert wrapper._allowances_overlap(entry(shared, ["docs/*.md"]), entry(other, ["docs/x*"])) is True
    # Different worktrees + intersecting.
    assert wrapper._allowances_overlap(entry(shared, ["docs/**"]), entry(other, ["docs/**"])) is True
    # Different worktrees + decidable disjoint.
    assert wrapper._allowances_overlap(entry(shared, ["docs/**"]), entry(other, ["vibecomfy/**"])) is False


def test_allowances_overlap_serializes_mutating_same_worktree_pairs(tmp_path: Path) -> None:
    """WRAPPER-OVERLAP-NARROW-R2 F-b: same-worktree pairs whose BOTH allowed
    lists are non-empty always overlap (whole-worktree snapshots cannot
    attribute writes between concurrent children); read-only sides keep the
    §15.3 / §21.4 guarantee of never blocking anything.
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_same_worktree_serialize")
    shared = tmp_path / "shared-worktree"
    other = tmp_path / "other-worktree"

    def entry(worktree: Path, allowed: list[str]) -> dict[str, object]:
        return {"task_id": "t", "worktree": str(worktree), "allowed": allowed}

    assert wrapper._allowances_overlap(
        entry(shared, ["docs/**"]), entry(shared, ["vibecomfy/**"]), same_worktree=True
    ) is True
    assert wrapper._allowances_overlap(
        entry(shared, ["allowed.txt"]), entry(shared, ["other.txt"]), same_worktree=True
    ) is True
    # Read-only sides never overlap, even on the same worktree.
    assert wrapper._allowances_overlap(
        entry(shared, []), entry(shared, ["allowed.txt"]), same_worktree=True
    ) is False
    assert wrapper._allowances_overlap(
        entry(shared, ["allowed.txt"]), entry(shared, []), same_worktree=True
    ) is False
    # Cross-worktree pairs still resolve via path intersection.
    assert wrapper._allowances_overlap(
        entry(shared, ["docs/**"]), entry(other, ["vibecomfy/**"]), same_worktree=False
    ) is False
    assert wrapper._allowances_overlap(
        entry(shared, ["docs/**"]), entry(other, ["docs/**"]), same_worktree=False
    ) is True


def test_patterns_may_intersect_crossing_globs_fail_closed(tmp_path: Path) -> None:
    """WRAPPER-OVERLAP-NARROW-R2 F-a: ``_patterns_may_intersect`` decides
    exact/suffix/prefix-star crossings exactly and returns True (overlap) for
    any undecidable crossing. Pre-R2, ``docs/*.md`` vs ``docs/x*`` fell
    through the fnmatch cross-check as False -- unsound parallel admission.
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_pattern_intersection")
    # The reviewer's crossing-glob case intersects at docs/x.md.
    assert wrapper._patterns_may_intersect("docs/*.md", "docs/x*") is True
    assert wrapper._patterns_may_intersect("docs/x*", "docs/*.md") is True
    # Decidable intersections stay exact.
    assert wrapper._patterns_may_intersect("docs/x*", "docs/x.md") is True
    assert wrapper._patterns_may_intersect("*", "vibecomfy/anything.txt") is True
    assert wrapper._patterns_may_intersect("**", "anything.txt") is True
    # Two wildcard-free literals are decidable-disjoint unless equal -- the
    # exact fnmatch semantics enforcement itself uses ("dir/" matches only a
    # literal path "dir/"); adding a star restores prefix coverage.
    assert wrapper._patterns_may_intersect("dir/", "dir/nested/file.txt") is False
    assert wrapper._patterns_may_intersect("dir/*", "dir/nested/file.txt") is True
    assert wrapper._patterns_may_intersect("a*b", "axxxyb") is True
    # Decidable disjointness stays exact.
    assert wrapper._patterns_may_intersect("allowed.txt", "forbidden.txt") is False
    assert wrapper._patterns_may_intersect("docs/**", "vibecomfy/**") is False
    assert wrapper._patterns_may_intersect("docs/a*", "docs/b.md") is False
    assert wrapper._patterns_may_intersect("docs/*z", "docs/*y") is False
    # Undecidable fragments (?/class/multi-star): fail closed to True even
    # when a human might prove disjointness.
    assert wrapper._patterns_may_intersect("docs/?z", "docs/literal") is True
    assert wrapper._patterns_may_intersect("doc[s]/x", "vibe/y") is True
    assert wrapper._patterns_may_intersect("docs/*/x/*/y", "docs/a/x/b/y") is True


def test_registry_guard_allows_second_dispatch_with_empty_allowed(tmp_path: Path) -> None:
    """A second dispatch with an empty ``allowed`` list registers alongside a
    live same-worktree entry instead of raising ALLOWANCE_OVERLAP; the active
    entry survives and the candidate is stored verbatim.
    """
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_empty_allowed_guard")
    task_id = "evidence-active"
    _write_registry(evidence, task_id, {
        "task_id": task_id,
        "allowance_file": str(allowance),
        "worktree": str(project),
        "start_ts_epoch": time.time(),
        "pid": os.getpid(),
        "allowed": ["allowed.txt"],
    })

    registry, candidate = wrapper._registry_guard(
        evidence, "next-dispatch", allowance, project, []
    )
    try:
        assert set(registry) == {task_id, "next-dispatch"}
        assert candidate["allowed"] == []
    finally:
        wrapper._registry_release(evidence, "next-dispatch")
    stored = json.loads((evidence / "active-allowances.json").read_text())
    assert set(stored) == {task_id}


def test_registry_guard_refuses_duplicate_active_task_id(tmp_path: Path) -> None:
    """WRAPPER-OVERLAP-NARROW-R2 F-c: an already-active task_id is refused
    before overlap evaluation and before the live entry can be overwritten --
    either side's release would otherwise unregister the survivor. The seeded
    entry uses a different worktree and empty ``allowed`` so ONLY the
    duplicate-ID check can fire.
    """
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_duplicate_task_id")
    seeded = {
        "task_id": "dup-id",
        "allowance_file": str(allowance),
        "worktree": str(project.parent / "elsewhere"),
        "start_ts_epoch": time.time(),
        "pid": os.getpid(),
        "allowed": [],
    }
    _write_registry(evidence, "dup-id", seeded)

    with pytest.raises(wrapper.WrapperError) as excinfo:
        wrapper._registry_guard(evidence, "dup-id", allowance, project, ["other.txt"])
    assert "TASK_ALREADY_ACTIVE" in str(excinfo.value)

    stored = json.loads((evidence / "active-allowances.json").read_text())
    assert stored == {"dup-id": seeded}


def test_registry_guard_allows_reuse_after_dead_pid_sweep_clears_entry(tmp_path: Path) -> None:
    """WRAPPER-OVERLAP-NARROW-R2 F-c: a stale same-task_id entry cleared by the
    dead-PID sweep does NOT count as active; reuse registers a fresh entry."""
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_stale_task_id_reuse")
    dead_pid = _dead_pid(wrapper)
    _write_registry(evidence, "reused-id", {
        "task_id": "reused-id",
        "allowance_file": str(allowance),
        "worktree": str(project),
        "start_ts_epoch": time.time() - wrapper.DEAD_PID_GRACE_SECONDS - 120,
        "pid": dead_pid,
        "allowed": ["allowed.txt"],
    })

    registry, candidate = wrapper._registry_guard(
        evidence, "reused-id", allowance, project, ["allowed.txt"]
    )
    try:
        assert set(registry) == {"reused-id"}
        assert candidate["pid"] == os.getpid()
    finally:
        wrapper._registry_release(evidence, "reused-id")
    note = json.loads((evidence / "stale-allowance-cleared.json").read_text())
    assert note["cleared_task_ids"] == ["reused-id"]
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_duplicate_task_id_exits_nonzero_without_launching_child(tmp_path: Path) -> None:
    """WRAPPER-OVERLAP-NARROW-R2 F-c end-to-end: a duplicate active task_id
    makes the wrapper exit nonzero BEFORE launching a child; the live registry
    entry survives byte-identical and no receipt appears.
    """
    project, evidence, brief, allowance, fake = _setup(tmp_path)
    sentinel = evidence / "launcher-started"
    seeded = {
        "task_id": "T9.1",
        "allowance_file": str(allowance),
        "worktree": str(project.parent / "elsewhere"),
        "start_ts_epoch": time.time(),
        "pid": os.getpid(),
        "allowed": [],
    }
    _write_registry(evidence, "T9.1", seeded)

    result = _invoke(project, evidence, brief, allowance, fake, sentinel=sentinel)

    assert result.returncode == 2
    assert "TASK_ALREADY_ACTIVE" in result.stderr
    assert not sentinel.exists()
    assert not (project / "allowed.txt").exists()
    assert not (evidence / "T9.1-receipt.json").exists()
    stored = json.loads((evidence / "active-allowances.json").read_text())
    assert stored == {"T9.1": seeded}


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


def test_timeout_default_is_7200() -> None:
    spec = importlib.util.spec_from_file_location("workflow_execution_wrapper_timeout_default", WRAPPER)
    assert spec is not None and spec.loader is not None
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    args = wrapper.build_parser().parse_args([
        "--task-id=T", "--role=r", "--label=l", "--model-route=stealth/ox-alpha",
        "--query-file=q", "--project-dir=p", "--allowance-file=a", "--evidence-dir=e",
    ])
    assert args.timeout == 7200


def test_registry_critical_section_ends_after_candidate_write(tmp_path: Path) -> None:
    """H3 fix: the exclusive lock is released once the candidate entry is durable.

    Under the pre-fix behavior the guard returned a lock handle held for the
    whole child runtime, so this non-blocking probe would raise BlockingIOError
    and a second registration would stall until the first dispatch finished.
    """
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_short_critical_section")
    registry, _candidate = wrapper._registry_guard(evidence, "task-a", allowance, project, ["allowed.txt"])
    try:
        assert "task-a" in registry
        probe = (evidence / ".active-allowances.lock").open("r+")
        try:
            fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
        finally:
            probe.close()
        other_project = project.parent / "worktree-b"
        other_project.mkdir()
        second_registry, _second = wrapper._registry_guard(
            evidence, "task-b", allowance, other_project, ["other.txt"]
        )
        assert set(second_registry) == {"task-a", "task-b"}
        stored = json.loads((evidence / "active-allowances.json").read_text())
        assert set(stored) == {"task-a", "task-b"}
    finally:
        wrapper._registry_release(evidence, "task-a")
        wrapper._registry_release(evidence, "task-b")
    assert not json.loads((evidence / "active-allowances.json").read_text())


def test_registry_guard_publishes_active_lock_for_interrupt_reuse(tmp_path: Path) -> None:
    """The guard's lock handle reaches the module global so an interrupt landing
    inside the critical section takes _registry_release's reuse branch instead
    of deadlocking on a second flock acquisition.
    """
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_active_lock_global")
    observed: dict[str, object] = {}
    real_json_write = wrapper._json_write

    def spy_json_write(path: Path, value: object) -> None:
        if Path(path).name == "active-allowances.json":
            handle = wrapper._ACTIVE_REGISTRY_LOCK
            # Liveness must be observed at write time: the guard closes the
            # descriptor before returning, so a post-return check would lie.
            observed["published_path"] = None if handle is None else Path(getattr(handle, "name"))
            observed["published_open"] = handle is not None and not getattr(handle, "closed")
        real_json_write(path, value)

    wrapper._json_write = spy_json_write
    try:
        wrapper._registry_guard(evidence, "task-a", allowance, project, ["allowed.txt"])
    finally:
        wrapper._json_write = real_json_write
    assert observed["published_open"] is True
    assert observed["published_path"] == evidence / ".active-allowances.lock"
    # Success path hands the descriptor back: global cleared, lock released.
    assert wrapper._ACTIVE_REGISTRY_LOCK is None

    # Simulate the interrupt window: a live held descriptor, then release.
    held = (evidence / ".active-allowances.lock").open("r+")
    try:
        wrapper._ACTIVE_REGISTRY_LOCK = held
        wrapper._registry_release(evidence, "task-a")
        # Reuse branch taken: entry removed via the held descriptor, which stays
        # open and exclusively locked (release neither closes nor unlocks it).
        assert not held.closed
        assert wrapper._ACTIVE_REGISTRY_LOCK is held
        probe = (evidence / ".active-allowances.lock").open("r+")
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            probe.close()
        assert "task-a" not in json.loads((evidence / "active-allowances.json").read_text())
    finally:
        fcntl.flock(held.fileno(), fcntl.LOCK_UN)
        held.close()
        wrapper._ACTIVE_REGISTRY_LOCK = None


def test_concurrent_registry_release_preserves_both_deletions(tmp_path: Path) -> None:
    """Releases take LOCK_EX around their read-modify-write so neither deletion is lost."""
    project, evidence, _brief, allowance, _fake = _setup(tmp_path)
    wrapper = _load_wrapper("workflow_execution_wrapper_concurrent_release")
    other_project = project.parent / "worktree-b"
    other_project.mkdir()
    registry_path = evidence / "active-allowances.json"

    def release(task_id: str, failures: list[BaseException]) -> None:
        try:
            wrapper._registry_release(evidence, task_id)
        except BaseException as exc:  # surfaced via the assertion below
            failures.append(exc)

    for _round in range(25):
        wrapper._registry_guard(evidence, "task-a", allowance, project, ["allowed.txt"])
        wrapper._registry_guard(evidence, "task-b", allowance, other_project, ["other.txt"])
        failures: list[BaseException] = []
        threads = [
            threading.Thread(target=release, args=("task-a", failures)),
            threading.Thread(target=release, args=("task-b", failures)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
            assert not thread.is_alive()
        assert not failures
        # Post-state: BOTH deletions persisted. Dropping LOCK_EX interleaves the
        # two read-modify-writes and resurrects one entry as a zombie allowance.
        assert json.loads(registry_path.read_text()) == {}


def test_second_wrapper_completes_while_first_child_still_sleeping(tmp_path: Path) -> None:
    """End-to-end H3 proof: registration, sweep, and release all work while
    another wrapper's child is mid-run; the live entry survives the sweep.
    """
    case_root = Path(tempfile.mkdtemp(prefix="wrapper-overlap-", dir=tmp_path))
    evidence = case_root / "evidence"
    evidence.mkdir()

    def make_worktree(name: str, allowed_name: str) -> tuple[Path, Path]:
        project = case_root / name
        project.mkdir()
        _git(project, "init", "-q")
        _git(project, "config", "user.email", "test@example.invalid")
        _git(project, "config", "user.name", "Test")
        (project / "seed.txt").write_text("seed\n")
        _git(project, "add", "-A")
        _git(project, "commit", "-qm", "seed")
        allowance = case_root / f"{name}-allowance.json"
        allowance.write_text(json.dumps({"allowed": [allowed_name], "forbidden": []}))
        return project, allowance

    project_a, allowance_a = make_worktree("project-a", "allowed-a.txt")
    project_b, allowance_b = make_worktree("project-b", "allowed-b.txt")
    brief_a = case_root / "brief-a.md"
    brief_a.write_text("brief a\n")
    brief_b = case_root / "brief-b.md"
    brief_b.write_text("brief b\n")
    fake = case_root / "fake_launcher.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys, time\n"
        "project = pathlib.Path(next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        "if os.environ.get('FAKE_MODE') == 'sleep':\n"
        "    pathlib.Path(os.environ['FAKE_HANDSHAKE']).write_text(str(os.getpid()))\n"
        "    print('fake child ready', flush=True)\n"
        "    time.sleep(60)\n"
        "else:\n"
        "    target = project / os.environ.get('FAKE_TARGET', 'allowed.txt')\n"
        "    target.write_text('ok')\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=sys.stderr)\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["VCSPINE_FAKE_LAUNCHER"] = str(fake)
    handshake = evidence / "child-handshake"
    env["FAKE_MODE"] = "sleep"
    env["FAKE_HANDSHAKE"] = str(handshake)

    first = subprocess.Popen(
        [
            sys.executable, str(WRAPPER), "--task-id=first-dispatch", "--role=implementer",
            "--label=T9.1 [HARD] overlap holder", "--model-route=codex:gpt-5.6-luna",
            f"--query-file={brief_a}", f"--project-dir={project_a}",
            f"--allowance-file={allowance_a}", f"--evidence-dir={evidence}",
            "--timeout=30",
        ],
        env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    child_pid: int | None = None
    try:
        deadline = time.monotonic() + 10
        while not handshake.exists() and time.monotonic() < deadline:
            if first.poll() is not None:
                raise AssertionError(f"first wrapper exited early: {first.communicate()}")
            time.sleep(0.01)
        assert handshake.exists()
        child_pid = int(handshake.read_text())
        registry = json.loads((evidence / "active-allowances.json").read_text())
        assert set(registry) == {"first-dispatch"}

        second_env = os.environ.copy()
        second_env["VCSPINE_FAKE_LAUNCHER"] = str(fake)
        second_env["FAKE_TARGET"] = "allowed-b.txt"
        second = subprocess.run(
            [
                sys.executable, str(WRAPPER), "--task-id=second-dispatch", "--role=implementer",
                "--label=T9.2 [HARD] overlap entrant", "--model-route=codex:gpt-5.6-luna",
                f"--query-file={brief_b}", f"--project-dir={project_b}",
                f"--allowance-file={allowance_b}", f"--evidence-dir={evidence}",
                "--timeout=30",
            ],
            env=second_env, text=True, capture_output=True, timeout=60,
        )
        assert second.returncode == 0, second.stderr
        # The live first entry survived the second wrapper's dead-PID sweep,
        # and the second wrapper already released its own entry on completion.
        registry = json.loads((evidence / "active-allowances.json").read_text())
        assert set(registry) == {"first-dispatch"}
        assert json.loads((evidence / "second-dispatch-receipt.json").read_text())["exit"] == 0
    finally:
        first.send_signal(signal.SIGTERM)
        try:
            first_returncode = first.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            first.kill()
            first_returncode = first.wait(timeout=5)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        first.communicate(timeout=10)
    interrupted = json.loads((evidence / "first-dispatch-receipt.json").read_text())
    assert interrupted["status"] == "interrupted"
    assert not json.loads((evidence / "active-allowances.json").read_text())

def test_route_launchers_semantic_section27_mapping() -> None:
    """WRAPPER-ROUTE-FIX §27: semantic routes resolve directly, legacy ids stay on muse.

    WRAPPER-ROUTE-THINKING: stealth entries append :max so hermes launcher sets --thinking max.
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_route_fix")
    launchers = wrapper.ROUTE_LAUNCHERS
    # stealth entries — thinking=max suffix for tool-use fix
    assert launchers["ox-alpha"][1] == "stealth/ox-alpha:max"
    assert launchers["stealth/ox-alpha"][1] == "stealth/ox-alpha:max"
    assert launchers["codex:gpt-5.6-sol"][1] == "codex:gpt-5.6-sol"
    # legacy §24 translation unchanged
    assert launchers["codex:gpt-5.6-luna"][1] == "openrouter/meta/muse-spark-1.2-contributor"
    assert launchers["grok-4.6"][1] == "openrouter/meta/muse-spark-1.2-contributor"
    # explicit alias for the legacy blanket target
    assert launchers["muse-spark"][1] == "openrouter/meta/muse-spark-1.2-contributor"
    # launcher executable unchanged for all routes
    for _route, (launcher, _model) in launchers.items():
        assert launcher == wrapper.HERMES_LAUNCHER


def test_redact_secrets_covers_each_pattern_class() -> None:
    wrapper = _load_wrapper("workflow_execution_wrapper_redact_classes")
    text = "\n".join(
        [
            "token sk-or-v1-Ab12_-Zx9876543210cd tail",
            "OPENROUTER_API_KEY=live-secret-value-001",
            "DEEPSEEK_API_KEY=another-live-value",
            "OPENAI_API_KEY=third-live-value",
            "authorization: bearer abc.def.ghi",
            "Authorization:\tBearer\tTok123",
        ]
    )
    assert wrapper._redact_secrets(text) == "\n".join(
        [
            "token sk-or-v1-[REDACTED] tail",
            "OPENROUTER_API_KEY=[REDACTED]",
            "DEEPSEEK_API_KEY=[REDACTED]",
            "OPENAI_API_KEY=[REDACTED]",
            "Authorization: Bearer [REDACTED]",
            "Authorization: Bearer [REDACTED]",
        ]
    )


def test_redact_secrets_is_idempotent_and_preserves_non_secrets() -> None:
    wrapper = _load_wrapper("workflow_execution_wrapper_redact_idempotent")
    once = wrapper._redact_secrets("k=sk-or-v1-Ab12_-Zx9876543210cd OPENROUTER_API_KEY=v1 Authorization: Bearer t1")
    assert wrapper._redact_secrets(once) == once
    # token class runs first, then the VAR=... pass re-redacts the collapsed
    # token, leaving the spec's canonical <VAR>=[REDACTED] form
    combined = wrapper._redact_secrets("OPENROUTER_API_KEY=sk-or-v1-Ab12_-Zx9876543210cd")
    assert combined == "OPENROUTER_API_KEY=[REDACTED]"
    digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    plain = f"sha256={digest} note=ok"
    assert wrapper._redact_secrets(plain) == plain


def test_json_write_sanitizes_payload_before_disk(tmp_path: Path) -> None:
    wrapper = _load_wrapper("workflow_execution_wrapper_json_write_redaction")
    target = tmp_path / "receipts" / "REDACT-CHECK-receipt.json"
    payload = {
        "env": "OPENROUTER_API_KEY=fake-live-key-000111222",
        "note": "bearer Authorization: Bearer fake-token-abc",
        "token": "sk-or-v1-FakeKeyFakeKeyFake12",
        "digest": "0" * 64,
    }
    wrapper._json_write(target, payload)
    written = json.loads(target.read_text(encoding="utf-8"))
    flat = json.dumps(written)
    assert "fake-live-key-000111222" not in flat
    assert "fake-token-abc" not in flat
    assert "FakeKeyFakeKeyFake12" not in flat
    assert written["env"] == "OPENROUTER_API_KEY=[REDACTED]"
    assert written["note"] == "bearer Authorization: Bearer [REDACTED]"
    assert written["token"] == "sk-or-v1-[REDACTED]"
    assert written["digest"] == "0" * 64
    assert not list(tmp_path.rglob("*.tmp"))


def test_redact_secrets_walks_structured_leaves() -> None:
    """MUST-001: _redact_secrets operates on Python objects before serialization."""
    wrapper = _load_wrapper("workflow_execution_wrapper_redact_structured")
    value = {
        "OPENROUTER_API_KEY=live-key": (
            "tok sk-or-v1-Ab12_-Zx9876543210cd",
            [7, None, True, {"deep": "Authorization: Bearer live-token"}],
        ),
        "digest": "0" * 64,
    }
    out = wrapper._redact_secrets(value)
    assert list(out) == ["OPENROUTER_API_KEY=[REDACTED]", "digest"]  # str dict keys are leaves too
    branch = out["OPENROUTER_API_KEY=[REDACTED]"]
    assert isinstance(branch, tuple)
    assert branch[0] == "tok sk-or-v1-[REDACTED]"
    assert branch[1][:3] == [7, None, True]  # non-str leaves untouched
    assert branch[1][3]["deep"] == "Authorization: Bearer [REDACTED]"
    assert out["digest"] == "0" * 64


def test_json_write_roundtrips_embedded_quote_secret_payloads(tmp_path: Path) -> None:
    """MUST-001 reviewer reproduction: secrets containing '"' corrupted the file.

    Redacting the SERIALIZED string ate the escape backslash and left an
    unescaped quote. Redaction now precedes serialization, so the write must
    stay valid, parseable JSON with every fake secret gone.
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_json_write_quotes")
    target = tmp_path / "receipts" / "QUOTES-receipt.json"
    payload = {
        "env": 'OPENAI_API_KEY=fake-value"suffix',
        "auth": 'Authorization: Bearer fake-bearer"suffix',
        "nested": {"pair": ('DEEPSEEK_API_KEY=fake-ds"value', ['sk-or-v1-FakeKeyFakeKeyFake12"tail'])},
        "digest": "0" * 64,
        "count": 3,
    }
    wrapper._json_write(target, payload)
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["env"] == "OPENAI_API_KEY=[REDACTED]"
    assert written["auth"] == "Authorization: Bearer [REDACTED]"
    assert written["nested"]["pair"][0] == "DEEPSEEK_API_KEY=[REDACTED]"
    # Token class is charclass-scoped (spec keeps it as-is): only the token
    # itself redacts; trailing junk after the key material survives.
    assert written["nested"]["pair"][1][0] == 'sk-or-v1-[REDACTED]"tail'
    assert written["digest"] == "0" * 64
    assert written["count"] == 3
    flat = json.dumps(written)
    assert "fake-" not in flat and "suffix" not in flat
    # Re-writing sanitized output is a byte-identical fixed point.
    again = tmp_path / "receipts" / "QUOTES-again.json"
    wrapper._json_write(again, written)
    assert again.read_bytes() == target.read_bytes()
    assert not list(tmp_path.rglob("*.tmp"))


def test_redact_secrets_rejects_dict_key_collision(tmp_path: Path) -> None:
    """T29A-REVISION-2 F1: two distinct source keys that normalize to one
    redacted key fail closed. The typed error carries no original key, no
    normalized key, no value, and no path material; _json_write completes the
    full structural pass before any filesystem effect (existing target stays
    byte-identical, nonexistent target stays absent, no temp residue).
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_redact_collision")
    top_level = {
        "sk-or-v1-LeftTokenLeft123456": "value-marker-alpha-777",
        "sk-or-v1-RightTokenRight1234": "value-marker-beta-888",
    }
    with pytest.raises(wrapper.WrapperError) as caught:
        wrapper._redact_secrets(top_level)
    message = str(caught.value)
    assert message.startswith("CREDENTIAL_REDACTION_KEY_COLLISION:")
    for marker in ("LeftToken", "RightToken", "alpha-777", "beta-888", "sk-or-v1"):
        assert marker not in message

    nested = {
        "outer": {
            "note OPENROUTER_API_KEY=leaf-left-secret": {},
            "note OPENROUTER_API_KEY=leaf-right-secret": [],
        }
    }
    with pytest.raises(wrapper.WrapperError) as nested_caught:
        wrapper._redact_secrets(nested)
    assert str(nested_caught.value).startswith("CREDENTIAL_REDACTION_KEY_COLLISION:")
    assert "leaf-left-secret" not in str(nested_caught.value)
    assert "leaf-right-secret" not in str(nested_caught.value)

    receipts = tmp_path / "receipts"
    receipts.mkdir()
    sentinel_target = receipts / "sentinel-receipt.json"
    sentinel = b'{"locked": true}\n'
    sentinel_target.write_bytes(sentinel)
    with pytest.raises(wrapper.WrapperError) as caught:
        wrapper._json_write(sentinel_target, dict(top_level))
    assert str(caught.value).startswith("CREDENTIAL_REDACTION_KEY_COLLISION:")
    assert "value-marker-alpha-777" not in str(caught.value)
    assert "value-marker-beta-888" not in str(caught.value)
    assert sentinel_target.read_bytes() == sentinel
    absent_target = receipts / "absent-receipt.json"
    with pytest.raises(wrapper.WrapperError):
        wrapper._json_write(absent_target, dict(top_level))
    assert not absent_target.exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_redact_secrets_rewashes_suffixed_placeholders() -> None:
    """T29A-REVISION-2 F2: on decoded leaves only canonical [REDACTED] followed
    by whitespace or end-of-string is exempt. Suffixed placeholders are live
    material and re-wash to the canonical form; canonical forms stay fixed points.
    """
    wrapper = _load_wrapper("workflow_execution_wrapper_redact_suffix")
    suffixes = ("<suffix>", "suffix", "-suffix")
    for name in ("OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        canonical = f"{name}=[REDACTED]"
        assert wrapper._redact_secrets(canonical) == canonical
        assert wrapper._redact_secrets(f"{canonical} tail") == f"{canonical} tail"
        for suffix in suffixes:
            assert wrapper._redact_secrets(f"{name}=[REDACTED]{suffix}") == canonical
            assert wrapper._redact_secrets(f"note {name}=[REDACTED]{suffix} end") == f"note {canonical} end"
    bearer_canonical = "Authorization: Bearer [REDACTED]"
    for form in ("authorization: bearer [REDACTED]", "Authorization:\tBearer\t[REDACTED]", f"{bearer_canonical} "):
        assert wrapper._redact_secrets(form) == form  # canonical (any case) is an exempt fixed point
    for suffix in suffixes:
        assert wrapper._redact_secrets(f"Authorization: Bearer [REDACTED]{suffix}") == bearer_canonical
        assert wrapper._redact_secrets(f"authorization: bearer [REDACTED]{suffix}!") == bearer_canonical
