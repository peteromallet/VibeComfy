from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands import COMMANDS, CommandSpec, load_command
from vibecomfy.commands.check import _cmd_check
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.commands.copy_to_recipe import _cmd_copy_to_recipe
from vibecomfy.commands.inspect import _cmd_inspect

from tests._cli_helpers import _top_level_commands


def test_cli_command_registry_is_explicit_and_ordered() -> None:
    assert [spec.name for spec in COMMANDS] == [
        "sources",
        "workflows",
        "nodes",
        "analyze",
        "search",
        "inspect",
        "reorganise",
        "port",
        "contract",
        "validate",
        "doctor",
        "fetch",
        "models",
        "run",
        "runtime",
        "session",
        "logs",
        "debug",
        "runpod",
        "watchdog",
        "schemas",
        "check",
        "agentic",
        "copy-to-recipe",
        "test",
        "config",
    ]


def test_build_parser_registers_all_known_commands() -> None:
    parser = build_parser()

    assert _top_level_commands(parser) == [spec.name for spec in COMMANDS]


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


# ── copy-to-recipe ──────────────────────────────────────────────────────


def test_copy_to_recipe_resolves_and_writes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_copy.py"
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="video/wan_i2v",
            out=str(out_file),
            strip_markers=False,
            with_runner=False,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert out_file.is_file()
    assert "Copied" in captured.out
    text = out_file.read_text(encoding="utf-8")
    assert "def build()" in text
    assert "vibecomfy" in text.lower()


def test_copy_to_recipe_strip_markers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_copy_stripped.py"
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="video/wan_i2v",
            out=str(out_file),
            strip_markers=True,
            with_runner=False,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    text = out_file.read_text(encoding="utf-8")
    # Markers should be stripped
    assert "vibecomfy: generated" not in text.lower()
    assert "vibecomfy: manual" not in text.lower()
    assert "def build()" in text


def test_copy_to_recipe_with_runner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_copy_runner.py"
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="video/wan_i2v",
            out=str(out_file),
            strip_markers=False,
            with_runner=True,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    text = out_file.read_text(encoding="utf-8")
    assert "if __name__ == '__main__':" in text
    assert "build()" in text
    assert "runner" in captured.out.lower()


def test_copy_to_recipe_unknown_id_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="nonexistent/template_id_xyz",
            out="/tmp/nonexistent_out.py",
            strip_markers=False,
            with_runner=False,
        )
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err or captured.out


# ── inspect --field ─────────────────────────────────────────────────────


def test_inspect_field_json_returns_tracefield(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(
        argparse.Namespace(workflow="video/wan_i2v", json=True, field="prompt")
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "field" in payload
    assert payload["field"] == "prompt"
    assert "resolution_chain" in payload
    assert "aliases" in payload
    assert "bound_node" in payload


def test_inspect_field_unknown_field_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(
        argparse.Namespace(workflow="video/wan_i2v", json=True, field="nonexistent_field_xyz")
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert "error" in payload


def test_inspect_field_text_renders_chain(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(
        argparse.Namespace(workflow="video/wan_i2v", json=False, field="prompt")
    )
    text = capsys.readouterr().out
    assert code == 0
    assert "field:" in text
    assert "resolution chain" in text
    assert "bound to:" in text


# ── check ───────────────────────────────────────────────────────────────


def test_check_json_emits_structured_report(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from vibecomfy.commands._checks import CheckReport, CheckResult

    monkeypatch.setattr(
        "vibecomfy.commands.check.run_checks",
        lambda: CheckReport(
            ok=False,
            status="error",
            schema_cache_class_count=12,
            pack_file_count=3,
            stub_pack_inventory=["kjnodes", "ltxvideo", "rgthree"],
            checks=[
                CheckResult(name="one", ok=True, status="pass", details={"a": 1}),
                CheckResult(name="legacy_file_presence", ok=True, status="state", details={"present": [], "missing": []}),
                CheckResult(name="two", ok=False, status="fail", details={"b": 2}),
            ],
        ),
    )

    code = _cmd_check(argparse.Namespace(json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "error"
    assert payload["schema_cache_class_count"] == 12
    assert payload["pack_file_count"] == 3
    assert payload["stub_pack_inventory"] == ["kjnodes", "ltxvideo", "rgthree"]
    assert [check["status"] for check in payload["checks"]] == ["pass", "state", "fail"]

# ── runtime eval-node ───────────────────────────────────────────────────


def test_eval_node_non_visualizable_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--json output for a CLIPTextEncode node (non-visualizable)."""
    import vibecomfy.commands.runtime as runtime_mod

    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test-eval", WorkflowSource("test-eval"))
    wf.nodes["1"] = VibeNode("1", "CLIPTextEncode", inputs={"text": "hello"})

    monkeypatch.setattr(runtime_mod, "get_schema_provider", lambda *a, **kw: None)
    monkeypatch.setattr(
        runtime_mod, "load_workflow_reference", lambda *a, **kw: wf
    )

    args = argparse.Namespace(
        path="test-eval",
        node="1",
        runtime="embedded",
        server_url=None,
        ready=False,
        json=True,
    )
    code = runtime_mod._cmd_runtime_eval_node(args)

    assert code == 0
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["node_id"] == "1"
    assert result["class_type"] == "CLIPTextEncode"
    assert result["previewable"] is False
    assert result["outputs"]["previewable"] is False


def test_eval_node_image_preview_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """--json output for a VAEDecode node (previewable) with mocked embedded runtime."""
    import vibecomfy.commands.runtime as runtime_mod

    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("img-test", WorkflowSource("img-test"))
    wf.nodes["1"] = VibeNode(
        "1", "VAEDecode", inputs={"samples": ["0", 0], "vae": ["0", 2]}
    )

    monkeypatch.setattr(runtime_mod, "get_schema_provider", lambda *a, **kw: None)
    monkeypatch.setattr(
        runtime_mod, "load_workflow_reference", lambda *a, **kw: wf
    )

    # Mock the embedded session queue to avoid needing a real ComfyUI
    async def fake_queue_embedded(api_dict):
        return {"prompt_id": "fake-prompt-123"}

    monkeypatch.setattr(runtime_mod, "_queue_embedded", fake_queue_embedded)

    monkeypatch.chdir(tmp_path)

    args = argparse.Namespace(
        path="img-test",
        node="1",
        runtime="embedded",
        server_url=None,
        ready=False,
        json=True,
    )
    code = runtime_mod._cmd_runtime_eval_node(args)

    assert code == 0
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["node_id"] == "1"
    assert result["class_type"] == "VAEDecode"
    assert result["previewable"] is True
    assert result["outputs"]["prompt_id"] == "fake-prompt-123"


def test_eval_node_runpod_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--runtime runpod without credentials emits clear message per FLAG-004."""
    import vibecomfy.commands.runtime as runtime_mod

    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test-eval", WorkflowSource("test-eval"))
    wf.nodes["1"] = VibeNode(
        "1", "VAEDecode", inputs={"samples": ["0", 0], "vae": ["0", 2]}
    )

    monkeypatch.setattr(runtime_mod, "get_schema_provider", lambda *a, **kw: None)
    monkeypatch.setattr(
        runtime_mod, "load_workflow_reference", lambda *a, **kw: wf
    )

    # Ensure no RunPod credentials
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_CONFIG_PATH", raising=False)

    args = argparse.Namespace(
        path="test-eval",
        node="1",
        runtime="runpod",
        server_url=None,
        ready=False,
        json=False,
    )
    code = runtime_mod._cmd_runtime_eval_node(args)

    assert code == 2
    err = capsys.readouterr().err
    assert "RunPod eval-node not available without credentials" in err
    assert "--runtime embedded or --runtime server" in err


def test_eval_node_absent_node_keyerror(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Requesting a node not in the workflow raises KeyError → caught, exit 1."""
    import vibecomfy.commands.runtime as runtime_mod

    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test-eval", WorkflowSource("test-eval"))
    wf.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "test"})

    monkeypatch.setattr(runtime_mod, "get_schema_provider", lambda *a, **kw: None)
    monkeypatch.setattr(
        runtime_mod, "load_workflow_reference", lambda *a, **kw: wf
    )

    args = argparse.Namespace(
        path="test-eval",
        node="999",  # absent node
        runtime="embedded",
        server_url=None,
        ready=False,
        json=True,
    )
    code = runtime_mod._cmd_runtime_eval_node(args)

    assert code == 1
    err = capsys.readouterr().err
    assert "eval-node failed:" in err


def test_eval_node_server_requires_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--runtime server without --server-url returns exit code 2."""
    import vibecomfy.commands.runtime as runtime_mod

    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test-eval", WorkflowSource("test-eval"))
    wf.nodes["1"] = VibeNode(
        "1", "VAEDecode", inputs={"samples": ["0", 0], "vae": ["0", 2]}
    )

    monkeypatch.setattr(runtime_mod, "get_schema_provider", lambda *a, **kw: None)
    monkeypatch.setattr(
        runtime_mod, "load_workflow_reference", lambda *a, **kw: wf
    )

    args = argparse.Namespace(
        path="test-eval",
        node="1",
        runtime="server",
        server_url=None,
        ready=False,
        json=False,
    )
    code = runtime_mod._cmd_runtime_eval_node(args)

    assert code == 2
    err = capsys.readouterr().err
    assert "--server-url is required" in err


def test_eval_node_unknown_runtime(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unknown runtime value returns exit code 2."""
    import vibecomfy.commands.runtime as runtime_mod

    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test-eval", WorkflowSource("test-eval"))
    wf.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "test"})

    monkeypatch.setattr(runtime_mod, "get_schema_provider", lambda *a, **kw: None)
    monkeypatch.setattr(
        runtime_mod, "load_workflow_reference", lambda *a, **kw: wf
    )

    args = argparse.Namespace(
        path="test-eval",
        node="1",
        runtime="nope",
        server_url=None,
        ready=False,
        json=False,
    )
    code = runtime_mod._cmd_runtime_eval_node(args)

    assert code == 2
    err = capsys.readouterr().err
    assert "unknown runtime" in err
