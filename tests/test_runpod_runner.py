from __future__ import annotations

import asyncio
import base64
import json
import shutil
import tarfile
from collections import namedtuple
from pathlib import Path

import pytest

from scripts import runpod_runner


PNG_1X1_TRANSPARENT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axf"
    "p6kAAAAASUVORK5CYII="
)


def test_default_upload_excludes_skip_bulky_local_state(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    included = root / "vibecomfy" / "module.py"
    excluded = root / "out" / "runpod_artifacts" / "large.bin"
    pycache = root / "vibecomfy" / "__pycache__" / "module.pyc"
    included.parent.mkdir(parents=True)
    excluded.parent.mkdir(parents=True)
    pycache.parent.mkdir(parents=True)
    included.write_text("print('ok')\n", encoding="utf-8")
    excluded.write_bytes(b"x")
    pycache.write_bytes(b"x")

    assert not runpod_runner.should_skip(included, root, runpod_runner.DEFAULT_UPLOAD_EXCLUDES)
    assert runpod_runner.should_skip(excluded, root, runpod_runner.DEFAULT_UPLOAD_EXCLUDES)
    assert runpod_runner.should_skip(pycache, root, runpod_runner.DEFAULT_UPLOAD_EXCLUDES)


def test_build_upload_tarball_uses_excludes_and_custom_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    tmpdir = tmp_path / "upload_tmp"
    keep = root / "scripts" / "keep.py"
    skipped = root / ".venv" / "site-packages" / "huge.py"
    keep.parent.mkdir(parents=True)
    skipped.parent.mkdir(parents=True)
    keep.write_text("print('keep')\n", encoding="utf-8")
    skipped.write_text("print('skip')\n", encoding="utf-8")
    monkeypatch.setenv("VIBECOMFY_UPLOAD_TMPDIR", str(tmpdir))

    tar_path = runpod_runner._build_upload_tarball(runpod_runner.DEFAULT_UPLOAD_EXCLUDES, root=root)
    try:
        assert tar_path.parent == tmpdir
        with tarfile.open(tar_path, "r:gz") as tar:
            names = set(tar.getnames())
        assert "scripts/keep.py" in names
        assert ".venv/site-packages/huge.py" not in names
    finally:
        tar_path.unlink(missing_ok=True)


def test_upload_disk_preflight_fails_early_with_actionable_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Usage(total=1024, used=1014, free=10))

    with pytest.raises(RuntimeError, match="VIBECOMFY_UPLOAD_TMPDIR"):
        runpod_runner._preflight_upload_disk(tmp_path, estimated_bytes=10 * 1024 * 1024)


def test_parse_tsv_returns_structured_rows(tmp_path: Path) -> None:
    results = tmp_path / "results.tsv"
    results.write_text("id\tstatus\tseconds\nred\tok\t3\nblue\tfail\t9\n", encoding="utf-8")

    assert runpod_runner._parse_tsv(results) == [
        {"id": "red", "status": "ok", "seconds": "3"},
        {"id": "blue", "status": "fail", "seconds": "9"},
    ]


def test_png_info_reads_dimensions_without_pillow(tmp_path: Path) -> None:
    image = tmp_path / "smoke.png"
    image.write_bytes(PNG_1X1_TRANSPARENT)

    assert runpod_runner._png_info(image) == {
        "width": 1,
        "height": 1,
        "format": "PNG",
        "mode": None,
    }


def test_finalize_artifacts_writes_manifest_and_report(tmp_path: Path) -> None:
    artifact_root = tmp_path / "bundle"
    results = artifact_root / "out" / "corpus_matrix" / "results.tsv"
    output = artifact_root / "output" / "smoke.png"
    run_dir = artifact_root / "out" / "runs" / "run-1"
    results.parent.mkdir(parents=True)
    output.parent.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (artifact_root / "artifacts.tar.gz").write_bytes(b"archive")
    results.write_text("id\tstatus\tseconds\tmedia_files\tbytes\nred\tok\t3\t1\t7\n", encoding="utf-8")
    output.write_bytes(PNG_1X1_TRANSPARENT)
    (results.parent / "remote_live.log").write_text("remote log\n", encoding="utf-8")
    (results.parent / "remote_run.sh").write_text("echo run\n", encoding="utf-8")
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "workflow_id": "smoke-red",
                "runtime": "embedded",
                "queued": {"prompt_id": "prompt-1"},
                "outputs": ["output/smoke.png"],
                "workflow_hash": "abc",
                "git_sha": "def",
            }
        ),
        encoding="utf-8",
    )
    watchdog_body = {
        "diagnosis": "crashed",
        "diagnosis_reason": "event stream ended",
        "state": {"stop_reason": "completed", "prompt_id": "prompt-1"},
        "elapsed_seconds": 12.5,
    }
    (run_dir / "watchdog.json").write_text(
        "WATCHDOG diagnosis=crashed prompt_id=prompt-1\n" + json.dumps(watchdog_body),
        encoding="utf-8",
    )

    manifest = runpod_runner._finalize_artifacts(
        artifact_root,
        pod_id="pod-1",
        exit_code=0,
        terminated=True,
        remote_command="cd /workspace/vibecomfy && bash /tmp/vibecomfy-remote-run.sh",
        upload={"mode": "tarball", "archive_bytes": 123},
    )

    manifest_path = artifact_root / "manifest.json"
    report_path = artifact_root / "report.md"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert manifest["summary"]["status"] == "pass"
    assert persisted["pod_id"] == "pod-1"
    assert persisted["exit_code"] == 0
    assert persisted["terminated"] is True
    assert persisted["summary"]["outputs"] == 1
    assert persisted["summary"]["failures"] == 0
    assert persisted["results"]["rows"][0]["id"] == "red"
    assert persisted["outputs"][0]["relative_path"] == "output/smoke.png"
    assert persisted["outputs"][0]["bytes"] == len(PNG_1X1_TRANSPARENT)
    assert persisted["outputs"][0]["image"]["width"] == 1
    assert persisted["outputs"][0]["image"]["height"] == 1
    assert persisted["run_metadata"][0]["prompt_id"] == "prompt-1"
    assert persisted["watchdogs"][0]["diagnosis"] == "crashed"
    assert "watchdog diagnosis=crashed" in persisted["warnings"][0]
    assert persisted["remote_script"]["relative_path"] == "out/corpus_matrix/remote_run.sh"
    assert persisted["manifest_path"].endswith("manifest.json")
    assert persisted["report_path"].endswith("report.md")
    assert "# RunPod Evidence Report" in report
    assert "| run-1 | crashed | completed | 12.5 | prompt-1 |" in report


def test_artifact_manifest_counts_result_failures(tmp_path: Path) -> None:
    results = tmp_path / "out" / "corpus_matrix" / "results.tsv"
    results.parent.mkdir(parents=True)
    results.write_text("id\tstatus\nred\tok\nblue\tfailed\n", encoding="utf-8")

    manifest = runpod_runner._build_artifact_manifest(tmp_path, exit_code=0)

    assert manifest["summary"]["status"] == "fail"
    assert manifest["summary"]["failures"] == 1


async def test_run_pod_cancellation_returns_130_and_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    terminated: list[bool] = []

    class FakeGuard:
        pod = None

        def __init__(self, **_kwargs) -> None:
            pass

        async def launch(self):
            raise asyncio.CancelledError

        async def terminate(self) -> None:
            terminated.append(True)

    monkeypatch.setattr(runpod_runner, "PodGuard", FakeGuard)
    monkeypatch.setattr(runpod_runner, "install_signal_handlers", lambda _loop: asyncio.Event())

    code = await runpod_runner.run_pod(
        "echo unreachable",
        name_prefix="test",
        exclude=runpod_runner.DEFAULT_UPLOAD_EXCLUDES,
        upload_mode="tarball",
        timeout=1,
    )

    assert code == 130
    assert terminated == [True]
