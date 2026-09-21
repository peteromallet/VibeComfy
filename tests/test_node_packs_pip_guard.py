from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.node_packs import CustomNodePack, install_required_packs
from vibecomfy.node_packs import _install as install


def test_node_pip_rejects_transitive_torch_change_before_install(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(install.importlib.metadata, "version", lambda name: "2.10.0+cu130")
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(list(command))
        report = Path(command[command.index("--report") + 1])
        report.write_text(json.dumps({"install": [{"metadata": {"name": "torch", "version": "2.11.0"}}]}))
        return type("Result", (), {"stdout": "", "stderr": ""})()

    error = install._install_pack_pip_packages(
        "pack", CustomNodePack("pack", "https://example.test/pack", frozenset({"Node"}), ("dep",)), runner
    )
    assert error is not None and "protected runtime package torch" in error
    assert len(calls) == 1
    assert "--dry-run" in calls[0]
    assert "--report" in calls[0]


def test_node_pip_allows_compatible_torch_and_verifies_after_install(monkeypatch) -> None:
    monkeypatch.setattr(install.importlib.metadata, "version", lambda name: "2.10.0+cu130")
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(list(command))
        if "--dry-run" in command:
            report = Path(command[command.index("--report") + 1])
            report.write_text(json.dumps({"install": [{"metadata": {"name": "torch", "version": "2.10.0+cu130"}}]}))
        return type("Result", (), {"stdout": "", "stderr": ""})()

    error = install._install_pack_pip_packages(
        "pack", CustomNodePack("pack", "https://example.test/pack", frozenset({"Node"}), ("dep",)), runner
    )
    assert error is None
    assert len(calls) == 2
    assert "--no-deps" not in calls[1]


def test_node_pip_rejects_malformed_resolution_report(monkeypatch) -> None:
    monkeypatch.setattr(install.importlib.metadata, "version", lambda name: "2.10.0+cu130")

    def runner(command, **kwargs):
        report = Path(command[command.index("--report") + 1])
        report.write_text("{}")
        return type("Result", (), {"stdout": "", "stderr": ""})()

    error = install._install_pack_pip_packages(
        "pack", CustomNodePack("pack", "https://example.test/pack", frozenset({"Node"}), ("dep",)), runner
    )
    assert error == "pip dry-run produced a malformed resolution report"


def test_batch_preflight_blocks_before_clone_or_lock_write(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(install.importlib.metadata, "version", lambda name: "2.10.0+cu130")
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(list(command))
        if command[-1] == "--help":
            return type("Result", (), {"stdout": "--dry-run --report", "stderr": ""})()
        report = Path(command[command.index("--report") + 1])
        report.write_text(json.dumps({"install": [{"metadata": {"name": "torch", "version": "2.11.0"}}]}))
        return type("Result", (), {"stdout": "", "stderr": ""})()

    pack = CustomNodePack("pack", "https://example.test/pack", frozenset({"Node"}), ("dep",))
    result = install_required_packs(
        [pack], install_root=tmp_path / "custom_nodes", lockfile_path=tmp_path / "custom_nodes.lock", runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )
    assert not result.ok
    assert result.preflight.error and "protected runtime package torch" in result.preflight.error
    assert not any(command[:2] == ["git", "clone"] for command in calls)
    assert not (tmp_path / "custom_nodes.lock").exists()


def test_runtime_requirement_constraints_preserve_compatible_specs_and_markers(monkeypatch) -> None:
    versions = {"torch": "2.10.0+cu130", "requests": "2.31.0", "urllib3": "1.26.18"}
    monkeypatch.setattr(install.importlib.metadata, "version", lambda name: versions[name])
    path = install._write_runtime_constraints(("requests>=2", "urllib3>=2", "idna>=3; sys_platform == 'never'"))
    try:
        text = path.read_text()
        assert "requests==2.31.0" in text
        assert "urllib3" not in text
        assert "idna" not in text
    finally:
        path.unlink()
