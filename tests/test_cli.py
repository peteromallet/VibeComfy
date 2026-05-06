from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands import COMMANDS, CommandSpec, load_command
from vibecomfy.commands.doctor import _doctor_warnings
from vibecomfy.commands.fetch import _cmd_fetch
from vibecomfy.commands.nodes import _cmd_nodes_ensure, _cmd_nodes_install, _cmd_nodes_install_plan, _cmd_nodes_list, _cmd_nodes_restore
import vibecomfy.node_packs_install as node_packs_install
import vibecomfy.commands.validate as validate_cmd
import vibecomfy.commands.runpod as runpod_cmd
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.commands.workflows import _cmd_workflows_list
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _top_level_commands(parser: argparse.ArgumentParser) -> list[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    raise AssertionError("parser has no subparsers")


def _write_fetch_scratchpad(tmp_path: Path) -> Path:
    scratchpad = tmp_path / "fetch_scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow(id="fetch-test", source=WorkflowSource(id="fetch-test"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple")
    workflow.metadata["model_assets"] = [
        {
            "name": "present.safetensors",
            "url": "https://example.test/present.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "missing.safetensors",
            "url": "https://example.test/missing.safetensors",
            "subdir": "checkpoints",
        },
    ]
    return workflow
""",
        encoding="utf-8",
    )
    return scratchpad


def test_cli_command_registry_is_explicit_and_ordered() -> None:
    assert [spec.name for spec in COMMANDS] == [
        "sources",
        "workflows",
        "nodes",
        "analyze",
        "search",
        "inspect",
        "convert",
        "validate",
        "doctor",
        "fetch",
        "models",
        "run",
        "runtime",
        "session",
        "logs",
        "runpod",
        "watchdog",
    ]


def test_build_parser_registers_all_known_commands() -> None:
    parser = build_parser()

    assert _top_level_commands(parser) == [spec.name for spec in COMMANDS]


def test_runpod_corpus_matrix_forwards_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "runpod_corpus_matrix.py").write_text("print('unreachable')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runpod_cmd.subprocess, "call", lambda argv: calls.append(argv) or 0)

    args = argparse.Namespace(scope="ltx_runexx_creation")

    assert runpod_cmd._cmd_runpod_corpus_matrix(args) == 0
    assert calls == [[sys.executable, "scripts/runpod_corpus_matrix.py", "--scope", "ltx_runexx_creation"]]


def test_validate_no_schema_skips_schema_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = tmp_path / "workflow.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow("validate-no-schema", WorkflowSource("validate-no-schema"))
    workflow.nodes["1"] = VibeNode("1", "UnknownRuntimeOnlyNode")
    return workflow
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_cmd,
        "get_schema_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("schema provider should not be built")),
    )

    assert validate_cmd._cmd_validate(argparse.Namespace(path=str(scratchpad), backend="api", no_schema=True)) == 0
    assert capsys.readouterr().out == "ok\n"


def test_fetch_cli_dry_run_lists_entries_without_downloading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = _write_fetch_scratchpad(tmp_path)
    present = tmp_path / "models" / "checkpoints" / "present.safetensors"
    present.parent.mkdir(parents=True)
    present.write_bytes(b"present")
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))
    calls = 0

    def download_many(_entries, *, force=False):
        nonlocal calls
        calls += 1
        raise AssertionError("download_many must not be called during dry-run")

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", download_many)

    assert _cmd_fetch(argparse.Namespace(workflow=str(scratchpad), force=False, dry_run=True)) == 0

    captured = capsys.readouterr()
    assert "present present.safetensors" in captured.out
    assert f"would fetch missing.safetensors -> {tmp_path / 'models' / 'checkpoints' / 'missing.safetensors'}" in captured.out
    assert calls == 0


def test_fetch_cli_invokes_download_many(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratchpad = _write_fetch_scratchpad(tmp_path)
    calls: list[tuple[list[dict], bool]] = []

    def download_many(entries, *, force=False):
        calls.append((entries, force))
        return []

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", download_many)

    assert _cmd_fetch(argparse.Namespace(workflow=str(scratchpad), force=True, dry_run=False)) == 0

    assert calls == [
        (
            [
                {
                    "name": "present.safetensors",
                    "url": "https://example.test/present.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "missing.safetensors",
                    "url": "https://example.test/missing.safetensors",
                    "subdir": "checkpoints",
                },
            ],
            True,
        )
    ]


def test_command_modules_expose_register() -> None:
    for spec in COMMANDS:
        assert callable(load_command(spec).register)


def test_load_command_rejects_module_without_register() -> None:
    with pytest.raises(TypeError, match="must expose register"):
        load_command(CommandSpec("argparse", "argparse"))


def test_resolve_workflow_path_accepts_existing_path(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")

    assert resolve_workflow_path(str(workflow)) == str(workflow)


def test_resolve_workflow_path_rejects_empty_or_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_workflow_path("")

    with pytest.raises(FileNotFoundError):
        resolve_workflow_path(str(tmp_path))


def test_resolve_workflow_path_accepts_index_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "sample", "path": str(workflow)}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert resolve_workflow_path("sample") == str(workflow)


def test_resolve_workflow_path_raises_for_unknown_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        resolve_workflow_path("missing")


def test_workflows_list_reports_malformed_index_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "workflow_index.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _cmd_workflows_list(argparse.Namespace(ready=False, limit=10)) == 1

    captured = capsys.readouterr()
    assert "workflow_index.json could not be read" in captured.err
    assert "vibecomfy sources sync" in captured.err


def test_nodes_list_reports_malformed_index_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_list(argparse.Namespace(limit=10)) == 1

    captured = capsys.readouterr()
    assert "node_index.json could not be read" in captured.err
    assert "vibecomfy sources sync" in captured.err


def test_doctor_warns_about_optional_video_audio_edge() -> None:
    workflow = VibeWorkflow("video", WorkflowSource("video"))
    workflow.nodes["1"] = VibeNode("1", "LTXVAudioVAEDecode")
    workflow.nodes["2"] = VibeNode("2", "CreateVideo")
    workflow.edges.append(VibeEdge("1", "0", "2", "audio"))

    warnings = _doctor_warnings(workflow)

    assert any("CreateVideo node 2 has optional audio input connected from 1:LTXVAudioVAEDecode" in item for item in warnings)


def test_doctor_suggests_custom_node_pack_for_unknown_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="DWPreprocessor")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    from vibecomfy.commands.doctor import _cmd_doctor

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 1

    captured = capsys.readouterr()
    assert "Suggested custom node packs:" in captured.out
    assert "comfyui_controlnet_aux" in captured.out


def test_nodes_install_plan_suggests_pack_for_missing_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "PreviewAudio", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_install_plan(argparse.Namespace(path=str(scratchpad), json=False)) == 0

    captured = capsys.readouterr()
    assert "ComfyUI-Qwen3-TTS" in captured.out
    assert "Qwen3CustomVoice" in captured.out


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("installed", 0),
        ("refreshed", 0),
        ("skipped_dirty", 1),
        ("failed", 1),
    ],
)
def test_cmd_nodes_install_translates_install_result_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    def fake_install_pack(**kwargs):
        assert kwargs == {"name": "ExamplePack", "repo": None, "force": False}
        return node_packs_install.InstallResult(
            name="ExamplePack",
            status=status,  # type: ignore[arg-type]
            git_commit_sha="abc123" if status in {"installed", "refreshed"} else None,
            error="install issue" if status in {"skipped_dirty", "failed"} else None,
        )

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)

    code = _cmd_nodes_install(argparse.Namespace(name="ExamplePack", repo=None, force=False))

    captured = capsys.readouterr()
    assert code == expected_code
    assert f"ExamplePack: {status}" in captured.out
    if expected_code:
        assert "install issue" in captured.err
    else:
        assert captured.err == ""


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("installed", 0),
        ("refreshed", 0),
        ("skipped_dirty", 1),
        ("failed", 1),
    ],
)
def test_cmd_nodes_restore_translates_results_to_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text("ExamplePack abc123 https://example.test/example.git\n", encoding="utf-8")

    def fake_restore_pack(entry):
        assert entry.name == "ExamplePack"
        assert entry.git_commit_sha == "abc123"
        return node_packs_install.InstallResult(
            name="ExamplePack",
            status=status,  # type: ignore[arg-type]
            git_commit_sha="abc123" if status in {"installed", "refreshed"} else None,
            error="restore issue" if status in {"skipped_dirty", "failed"} else None,
        )

    monkeypatch.setattr(node_packs_install, "restore_pack", fake_restore_pack)

    code = _cmd_nodes_restore(argparse.Namespace(lockfile=str(lockfile)))

    captured = capsys.readouterr()
    assert code == expected_code
    assert f"ExamplePack: {status}" in captured.out
    if expected_code:
        assert "restore issue" in captured.err
    else:
        assert captured.err == ""


def test_cmd_nodes_ensure_dry_run_does_not_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    def fail_install_pack(**_kwargs):
        raise AssertionError("install_pack must not be called during dry-run")

    monkeypatch.setattr(node_packs_install, "install_pack", fail_install_pack)

    code = _cmd_nodes_ensure(argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=True))

    captured = capsys.readouterr()
    assert code == 0
    assert "Suggested custom node packs:" in captured.out
    assert "ComfyUI-Qwen3-TTS" in captured.out


def test_ensure_calls_install_for_each_missing_pack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    workflow.nodes["2"] = VibeNode(id="2", class_type="VHS_LoadVideo")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    installed: list[str | None] = []

    def fake_install_pack(**kwargs):
        installed.append(kwargs.get("name"))
        return node_packs_install.InstallResult(
            name=str(kwargs["name"]),
            status="refreshed",
            git_commit_sha="abc123",
            error=None,
        )

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)

    code = _cmd_nodes_ensure(argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=False))

    captured = capsys.readouterr()
    assert code == 0
    assert installed == ["ComfyUI-Qwen3-TTS", "ComfyUI-VideoHelperSuite"]
    assert "Nodepacks installed/refreshed." in captured.out
