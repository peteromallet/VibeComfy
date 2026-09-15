from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vibecomfy.porting.import_service import import_workflow_bytes
from vibecomfy.runtime import session as session_module
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import load_bundle


def _publish_import(root: Path, source: bytes) -> tuple[object, dict[str, object]]:
    artifacts = import_workflow_bytes(source, workflow_id="hc03-composed")
    root.mkdir()
    python_path = root / "workflow.py"
    python_path.write_bytes(artifacts.python_bytes)
    (root / "workflow.vibe.json").write_bytes(artifacts.companion_bytes)
    (root / "source.json").write_bytes(artifacts.source_bytes)
    bundle = load_bundle(python_path, trust=Provenance.USER_CONFIRMED)
    companion = json.loads(artifacts.companion_bytes)
    return bundle, companion


def test_canonical_import_and_cross_load_share_v2_identity(tmp_path: Path) -> None:
    source_path = Path(__file__).parent / "fixtures" / "walking_skeleton" / "flat.json"
    source = source_path.read_bytes()

    first, first_companion = _publish_import(tmp_path / "first", source)
    second, second_companion = _publish_import(tmp_path / "second", source)

    assert first_companion["format_version"] == 2
    assert second_companion["format_version"] == 2
    assert first.workflow_identity == second.workflow_identity
    assert first.revision_id == second.revision_id
    assert first.semantic_digest == second.semantic_digest
    assert first.ui_digest == second.ui_digest
    assert (tmp_path / "first" / "source.json").read_bytes() == source
    assert (tmp_path / "second" / "source.json").read_bytes() == source


def test_source_revision_comes_from_checkout_not_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = session_module.find_repo_root()
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv("VIBECOMFY_SOURCE_REVISION", "launcher-controlled-value")
    monkeypatch.setenv("GIT_DIR", str(root / "launcher-controlled-git-dir"))

    assert session_module.current_source_revision() == expected


def test_source_content_digest_changes_with_effective_checkout_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "checkout"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    tracked = repository / "tracked.py"
    tracked.write_bytes(b"value = 1\n")
    subprocess.run(["git", "add", "tracked.py"], cwd=repository, check=True)
    monkeypatch.setattr(session_module, "find_repo_root", lambda: repository)
    monkeypatch.setenv("GIT_INDEX_FILE", str(repository / "launcher-controlled-index"))

    before = session_module.current_source_content_digest()
    tracked.write_bytes(b"value = 2\n")
    after = session_module.current_source_content_digest()

    assert before is not None and before.startswith("sha256:")
    assert after is not None and after.startswith("sha256:")
    assert after != before


def _write_composite_registry(session_dir: Path) -> None:
    session_dir.mkdir()
    (session_dir / "pid").write_text("4101", encoding="utf-8")
    (session_dir / "comfy_pid").write_text("4102", encoding="utf-8")
    (session_dir / "comfy_process_start_identity").write_text(
        "child-birth", encoding="utf-8"
    )
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "launch.json").write_text(
        json.dumps(
            {
                "launch_token": "exact-token",
                "pid": 4101,
                "process_start_identity": "daemon-birth",
                "comfy_pid": 4102,
                "comfy_process_start_identity": "child-birth",
                "url": "http://127.0.0.1:8200",
            }
        ),
        encoding="utf-8",
    )


def test_composite_custody_binds_daemon_child_and_listener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_dir = tmp_path / "session"
    _write_composite_registry(session_dir)
    births = {4101: "daemon-birth", 4102: "child-birth"}
    monkeypatch.setattr(
        session_module, "_process_start_identity", lambda pid: births.get(pid)
    )
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda pid: ("python", "--launch-token", "exact-token") if pid == 4101 else None,
    )
    monkeypatch.setattr(
        session_module, "_process_parent_pid", lambda pid: 4101 if pid == 4102 else None
    )
    monkeypatch.setattr(session_module, "_listener_owner_pid", lambda _url: 4102)

    assert session_module._session_composite_ownership_verified(session_dir, 4101)

    (session_dir / "comfy_process_start_identity").write_text(
        "different-child", encoding="utf-8"
    )
    assert not session_module._session_composite_ownership_verified(session_dir, 4101)

    (session_dir / "comfy_process_start_identity").write_text(
        "child-birth", encoding="utf-8"
    )
    monkeypatch.setattr(session_module, "_listener_owner_pid", lambda _url: 4999)
    assert not session_module._session_composite_ownership_verified(session_dir, 4101)


def test_composite_custody_rejects_child_with_foreign_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_dir = tmp_path / "session"
    _write_composite_registry(session_dir)
    births = {4101: "daemon-birth", 4102: "child-birth"}
    monkeypatch.setattr(
        session_module, "_process_start_identity", lambda pid: births.get(pid)
    )
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda _pid: ("python", "--launch-token", "exact-token"),
    )
    monkeypatch.setattr(session_module, "_process_parent_pid", lambda _pid: 4999)
    monkeypatch.setattr(session_module, "_listener_owner_pid", lambda _url: 4102)

    assert not session_module._session_composite_ownership_verified(session_dir, 4101)
