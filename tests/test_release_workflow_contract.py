"""Offline contract tests for the release and schema-freshness workflows.

These tests execute the workflow shell snippets against local fake git/ComfyUI
state.  They deliberately never contact GitHub or a ComfyUI installation.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml


REPO = Path(__file__).parents[1]
FIXED_TAG_DATE = "20200102"


def _git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def _workflow_step(workflow: str, name: str) -> dict[str, str]:
    document = yaml.safe_load((REPO / ".github" / "workflows" / workflow).read_text())
    steps = document["jobs"]["refresh"]["steps"] if workflow.startswith("refresh") else document["jobs"]["schema-freshness"]["steps"]
    return next(step for step in steps if step.get("name") == name)


def _run_step(
    step: dict[str, str], *, cwd: Path, env: dict[str, str] | None = None, replacements: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    script = step["run"]
    for old, new in (replacements or {}).items():
        script = script.replace(old, new)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env=merged_env,
        text=True,
        capture_output=True,
    )


def _new_git_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    _git("clone", str(remote), str(work), cwd=tmp_path)
    _git("config", "user.name", "workflow-test", cwd=work)
    _git("config", "user.email", "workflow-test@example.invalid", cwd=work)
    (work / "README").write_text("initial\n")
    _git("add", "README", cwd=work)
    _git("commit", "-m", "initial", cwd=work)
    _git("push", "-u", "origin", "HEAD", cwd=work)
    target = _git("rev-parse", "HEAD", cwd=work).stdout.strip()
    return remote, work, target


def _tag_step() -> dict[str, str]:
    return _workflow_step("refresh-node-schemas.yml", "Tag dated release")


def _run_tag_step(work: Path) -> subprocess.CompletedProcess[str]:
    return _run_step(
        _tag_step(),
        cwd=work,
        replacements={"$(date -u +%Y%m%d)": FIXED_TAG_DATE},
    )


def test_existing_same_remote_tag_is_idempotent_offline(tmp_path: Path) -> None:
    _, work, target = _new_git_repo(tmp_path)
    tag = f"schemas-{FIXED_TAG_DATE}"
    _git("tag", tag, target, cwd=work)
    _git("push", "origin", f"refs/tags/{tag}", cwd=work)
    _git("tag", "-d", tag, cwd=work)

    result = _run_tag_step(work)

    assert result.returncode == 0, result.stderr
    assert "already resolves" in result.stdout
    assert _git("ls-remote", "origin", f"refs/tags/{tag}", cwd=work).stdout.startswith(target)


def test_existing_same_local_tag_is_pushed_offline(tmp_path: Path) -> None:
    _, work, target = _new_git_repo(tmp_path)
    tag = f"schemas-{FIXED_TAG_DATE}"
    _git("tag", tag, target, cwd=work)

    result = _run_tag_step(work)

    assert result.returncode == 0, result.stderr
    assert _git("ls-remote", "origin", f"refs/tags/{tag}", cwd=work).stdout.startswith(target)


def test_existing_same_annotated_remote_tag_is_idempotent_offline(tmp_path: Path) -> None:
    _, work, target = _new_git_repo(tmp_path)
    tag = f"schemas-{FIXED_TAG_DATE}"
    _git("tag", "-a", tag, target, "-m", "release", cwd=work)
    _git("push", "origin", f"refs/tags/{tag}", cwd=work)
    _git("tag", "-d", tag, cwd=work)

    result = _run_tag_step(work)

    assert result.returncode == 0, result.stderr
    assert "already resolves" in result.stdout


def test_missing_tag_is_created_and_pushed_offline(tmp_path: Path) -> None:
    _, work, target = _new_git_repo(tmp_path)

    result = _run_tag_step(work)

    assert result.returncode == 0, result.stderr
    assert _git("ls-remote", "origin", f"refs/tags/schemas-{FIXED_TAG_DATE}", cwd=work).stdout.startswith(target)


def test_push_failure_is_not_masked_offline(tmp_path: Path) -> None:
    remote, work, _ = _new_git_repo(tmp_path)
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected >&2\nexit 1\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

    result = _run_tag_step(work)

    assert result.returncode != 0
    assert "rejected" in result.stderr


def test_conflicting_remote_tag_fails_offline(tmp_path: Path) -> None:
    _, work, first_target = _new_git_repo(tmp_path)
    tag = f"schemas-{FIXED_TAG_DATE}"
    _git("tag", tag, first_target, cwd=work)
    _git("push", "origin", f"refs/tags/{tag}", cwd=work)
    _git("tag", "-d", tag, cwd=work)
    (work / "README").write_text("second\n")
    _git("commit", "-am", "second", cwd=work)

    result = _run_tag_step(work)

    assert result.returncode != 0
    assert "remote tag" in result.stderr
    assert "expected" in result.stderr


def _gate_step() -> dict[str, str]:
    return _workflow_step("schema_freshness.yml", "Check ComfyUI availability (env-gate)")


def _fake_comfy(tmp_path: Path, body: str) -> None:
    package = tmp_path / "vibecomfy"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "comfy_backend.py").write_text(body)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("def ensure_nodes():\n    return True\n", "available=true\n"),
        ("def ensure_nodes():\n    return False\n", "available=false\n"),
    ],
    ids=["available", "unavailable"],
)
def test_comfy_gate_publishes_expected_availability(
    tmp_path: Path, body: str, expected: str
) -> None:
    _fake_comfy(tmp_path, body)
    output = tmp_path / "github-output"
    result = _run_step(
        _gate_step(),
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path), "GITHUB_OUTPUT": str(output)},
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text() == expected


def test_comfy_gate_keeps_unexpected_probe_error_failed(tmp_path: Path) -> None:
    _fake_comfy(
        tmp_path,
        "def ensure_nodes():\n    raise RuntimeError('probe exploded')\n",
    )
    output = tmp_path / "github-output"
    result = _run_step(
        _gate_step(),
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path), "GITHUB_OUTPUT": str(output)},
    )

    assert result.returncode != 0
    assert not output.exists()


def _hash_step() -> dict[str, str]:
    return _workflow_step("schema_freshness.yml", "Per-pack hash vs booted registry")


def _run_hash_step(tmp_path: Path, *, category: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    comfy = tmp_path / "comfy"
    comfy.mkdir()
    (comfy / "__init__.py").write_text("")
    (comfy / "nodes.py").write_text(
        "class Node:\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'text': ('STRING', {})}}\n"
        "    OUTPUT_NODE = False\n"
        "    RETURN_TYPES = ('STRING',)\n"
        f"    CATEGORY = {category!r}\n"
        "NODE_CLASS_MAPPINGS = {'NodeA': Node}\n"
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "index.json").write_text(json.dumps({"NodeA": "pack.json"}))
    (cache / "pack.json").write_text(
        json.dumps(
            {
                "NodeA": {
                    "class_type": "NodeA",
                    "input": {"required": {"text": ["STRING", {}]}},
                    "output_node": False,
                    "output": ["STRING"],
                    "category": "match" if category == "match" else "pinned",
                }
            }
        )
    )
    result = _run_step(
        _hash_step(),
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path)},
        replacements={"${{ inputs.object_info_source }}": str(cache)},
    )
    return result, tmp_path / "out" / "schema-freshness" / "freshness_report.json"


@pytest.mark.parametrize("category, errors", [("match", 0), ("different", 1)])
def test_hash_check_distinguishes_match_and_mismatch_offline(
    tmp_path: Path, category: str, errors: int
) -> None:
    result, report_path = _run_hash_step(tmp_path, category=category)

    assert result.returncode == (0 if errors == 0 else 1), result.stderr
    assert json.loads(report_path.read_text())["errors"] == errors


def test_hash_check_is_gated_by_explicit_availability_output() -> None:
    step = _hash_step()
    assert step["if"] == "steps.comfy-gate.outputs.available == 'true'"
    assert "steps.comfy-gate.outcome" not in step["if"]
