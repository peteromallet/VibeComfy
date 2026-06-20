from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from vibecomfy.commands.run import _cmd_run
import vibecomfy.runtime.session as session_module
from vibecomfy.artifacts import Artifact
from vibecomfy.runtime.session import SessionConfig
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

runtime_run_module = importlib.import_module("vibecomfy.runtime.run")


def _workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("runtime-test", WorkflowSource("runtime-test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "test"})
    return workflow


def test_run_starts_server_before_building(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    entered_server = False

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered_server
        entered_server = True
        yield "http://127.0.0.1:8188"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fail_if_entered)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(ValueError, match="Workflow build failed: Unknown compile backend"):
        asyncio.run(runtime_run_module.run(_workflow(), backend="missing"))

    assert entered_server is True
    assert (tmp_path / "out").exists()


def test_run_embedded_starts_before_building(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Workflow build failed: Unknown compile backend"):
        asyncio.run(runtime_run_module.run_embedded(_workflow(), backend="missing"))

    assert not (tmp_path / "out/runs").exists()


def test_run_validates_before_queueing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    entered_server = False

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered_server
        entered_server = True
        yield "http://127.0.0.1:8188"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fail_if_entered)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(RuntimeError, match=r"(?s)Workflow validation failed.*empty_workflow"):
        asyncio.run(runtime_run_module.run(VibeWorkflow("empty", WorkflowSource("empty"))))

    assert entered_server is True
    assert (tmp_path / "out").exists()


def test_run_surfaces_queue_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    queued_prompts: list[dict] = []

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FailingClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, prompt: dict) -> dict:
            queued_prompts.append(prompt)
            raise RuntimeError("runtime rejected prompt")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FailingClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    workflow = _workflow()
    workflow.metadata["id_map"] = {"save": "1"}
    workflow.nodes["1"].metadata["source_id"] = "7"

    with pytest.raises(RuntimeError, match="Workflow queue failed: runtime rejected prompt") as exc_info:
        asyncio.run(runtime_run_module.run(workflow, server_url="http://runtime.test"))

    assert queued_prompts == [
        {"1": {"class_type": "SaveImage", "inputs": {"filename_prefix": "test"}}}
    ]
    message = str(exc_info.value)
    assert "id_map=" in message
    assert "'save': '1'" in message
    assert "'7': '1'" in message


def test_run_managed_server_uses_workflow_session_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured_configs = []

    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 5,
        "port": 8205,
    }

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        captured_configs.append(config)
        yield "http://managed.test"

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-managed"}

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {"9": {"filename": "managed.mp4"}}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    result = asyncio.run(runtime_run_module.run(workflow, server_url=None))

    assert result.prompt_id == "prompt-managed"
    assert result.outputs == ["managed.mp4"]
    assert len(captured_configs) == 1
    config = captured_configs[0]
    assert config.memory_profile == 5
    assert config.port == 8205
    assert config.vram_policy == "low"
    assert config.cache_policy == "lru:1"
    assert config.reserve_vram_gb == 4.0
    assert config.disable_smart_memory is True


def test_run_external_server_does_not_apply_workflow_session_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured_configs = []
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {"memory_profile": 5}

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        captured_configs.append(config)
        yield server_url

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-external"}

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {"9": {"filename": "external.mp4"}}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    result = asyncio.run(runtime_run_module.run(workflow, server_url="http://external.test"))

    assert result.prompt_id == "prompt-external"
    assert result.outputs == ["external.mp4"]
    assert captured_configs == [None]


def test_embedded_configuration_uses_hiddenswitch_configuration_object(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConfiguration(dict):
        def __getattr__(self, name: str):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    def default_configuration() -> FakeConfiguration:
        return FakeConfiguration({"cwd": None, "reserve_vram": 0.0, "cache_none": False})

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.default_configuration = default_configuration
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.setenv("VIBECOMFY_COMFY_CONFIGURATION", '{"reserve_vram":12,"cache_none":true}')

    config = runtime_run_module._embedded_configuration(_workflow())

    assert isinstance(config, FakeConfiguration)
    assert config.cwd is None
    assert config.reserve_vram == 12
    assert config.cache_none is True


def test_run_embedded_ignores_hiddenswitch_cleanup_bug_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            raise AttributeError("'NoneType' object has no attribute 'model_mmap_residency'")

        async def queue_prompt_api(self, api_dict):
            return {"outputs": {"1": {"filename": "output.mp4"}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = lambda: {}
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    result = runtime_run_module.run_embedded_sync(_workflow())

    assert result.outputs == ["output.mp4"]


@pytest.mark.parametrize(
    "cleanup_error",
    [
        RuntimeError("cannot cancel futures in this implementation"),
        RuntimeError("Abnormal termination"),
    ],
)
def test_run_embedded_ignores_comfy_kitchen_cleanup_bug_after_success(
    cleanup_error: RuntimeError,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            raise cleanup_error

        async def queue_prompt_api(self, api_dict):
            return {"outputs": {"1": {"filename": "output.mp4"}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = lambda: {}
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    result = runtime_run_module.run_embedded_sync(_workflow())

    assert result.outputs == ["output.mp4"]


def test_run_embedded_resolves_comfy_filename_outputs_against_configured_output_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    output_dir = tmp_path / "standard-output"

    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def queue_prompt_api(self, api_dict):
            return {
                "outputs": {
                    "19": {
                        "images": [
                            {
                                "filename": "Wanimate_00001_.mp4",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                }
            }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_COMFY_CONFIGURATION", f'{{"output_directory":"{output_dir}"}}')
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = lambda: {}
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    result = runtime_run_module.run_embedded_sync(_workflow())

    assert result.outputs == [str(output_dir / "Wanimate_00001_.mp4")]
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    assert metadata["outputs"] == result.outputs
    assert metadata["artifact_paths"] == result.outputs
    assert metadata["artifact_manifest"] == {
        "schema_version": 1,
        "by_output": {},
        "unmapped": result.outputs,
        "attribution": [],
    }
    assert metadata["comfy_outputs"] == {
        "19": {
            "images": [
                {
                    "filename": "Wanimate_00001_.mp4",
                    "subfolder": "",
                    "type": "output",
                }
            ]
        }
    }
    assert metadata["compiled_prompt"]["1"]["inputs"]["filename_prefix"] == "test"


def test_artifact_run_forwards_chain_kwargs_to_selected_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_embedded_sync(workflow: VibeWorkflow, *, chain_id=None, parent_run_id=None, **kwargs):
        captured.update(
            {
                "workflow": workflow,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
                "kwargs": kwargs,
            }
        )
        return types.SimpleNamespace(run_id="run-1")

    monkeypatch.setattr("vibecomfy.runtime.run_embedded_sync", fake_run_embedded_sync)
    monkeypatch.setattr(
        "vibecomfy.runtime.run_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("server runtime should not run")),
    )

    workflow = _workflow()
    artifact = Artifact(workflow=workflow, node_id="1", output_slot=0, kind="image")
    result = artifact.run(runtime="embedded", chain_id="chain-1", parent_run_id="run-0", backend="graphbuilder")

    assert result.run_id == "run-1"
    assert captured == {
        "workflow": workflow,
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
        "kwargs": {"backend": "graphbuilder"},
    }


def test_run_sync_forwards_chain_kwargs_to_async_run(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run(workflow: VibeWorkflow, *, chain_id=None, parent_run_id=None, **kwargs):
        captured.update(
            {
                "workflow": workflow,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
                "kwargs": kwargs,
            }
        )
        return types.SimpleNamespace(run_id="run-sync")

    monkeypatch.setattr(runtime_run_module, "run", fake_run)

    workflow = _workflow()
    result = runtime_run_module.run_sync(workflow, server_url="http://runtime.test", chain_id="chain-1", parent_run_id="run-0")

    assert result.run_id == "run-sync"
    assert captured == {
        "workflow": workflow,
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
        "kwargs": {
            "server_url": "http://runtime.test",
            "backend": "api",
            "config": None,
            "ensure_models": False,
            "shared_models_root": None,
            "strict_drift": None,
        },
    }


def test_run_embedded_sync_forwards_chain_kwargs_to_async_run_embedded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_embedded(workflow: VibeWorkflow, *, chain_id=None, parent_run_id=None, **kwargs):
        captured.update(
            {
                "workflow": workflow,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
                "kwargs": kwargs,
            }
        )
        return types.SimpleNamespace(run_id="run-embedded")

    monkeypatch.setattr(runtime_run_module, "run_embedded", fake_run_embedded)

    workflow = _workflow()
    result = runtime_run_module.run_embedded_sync(workflow, chain_id="chain-1", parent_run_id="run-0")

    assert result.run_id == "run-embedded"
    assert captured == {
        "workflow": workflow,
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
        "kwargs": {
            "backend": "api",
            "config": None,
            "ensure_packs": False,
            "ensure_models": False,
            "strict_drift": None,
        },
    }


def test_run_passes_chain_kwargs_into_metadata_writer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-chain"}

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {"9": {"filename": "chain.mp4"}}}}

    def fake_run_metadata(**kwargs):
        captured.update(kwargs)
        return {"run_id": kwargs["run_id"], "outputs": kwargs["outputs"]}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_run_metadata", fake_run_metadata)

    result = asyncio.run(
        runtime_run_module.run(
            _workflow(),
            server_url="http://runtime.test",
            chain_id="chain-1",
            parent_run_id="run-0",
        )
    )

    assert result.prompt_id == "prompt-chain"
    assert captured["chain_id"] == "chain-1"
    assert captured["parent_run_id"] == "run-0"


def test_cmd_run_prints_clear_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )

    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: _workflow())
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda workflow, **_kwargs: (_ for _ in ()).throw(ValueError("Workflow build failed: bad backend")),
    )

    assert _cmd_run(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "run failed: Workflow build failed: bad backend\n"


def test_cmd_run_auto_uses_active_session_for_schema_and_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    schema_calls: list[tuple[str, str | None]] = []
    loaded_schema_providers: list[object] = []
    run_calls: list[tuple[VibeWorkflow, str | None, str]] = []
    provider = object()

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: "http://warm.test")

    def fake_schema_provider(prefer: str, *, server_url: str | None = None):
        schema_calls.append((prefer, server_url))
        return provider

    def fake_load_workflow_reference(*args, **kwargs):
        loaded_schema_providers.append(kwargs["schema_provider"])
        return _workflow()

    def fake_run_sync(workflow: VibeWorkflow, *, server_url: str | None, backend: str, **kwargs):
        run_calls.append((workflow, server_url, backend))
        return types.SimpleNamespace(
            run_id="run-1",
            prompt_id="prompt-1",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", fake_schema_provider)
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", fake_load_workflow_reference)
    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("embedded should not run")),
    )

    assert _cmd_run(args) == 0

    assert schema_calls == [("auto", "http://warm.test")]
    assert loaded_schema_providers == [provider]
    assert run_calls[0][1:] == ("http://warm.test", "api")
    assert "run_id: run-1" in capsys.readouterr().out


def test_cmd_run_auto_without_active_session_falls_back_to_embedded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    schema_calls: list[tuple[str, str | None]] = []
    embedded_calls: list[tuple[VibeWorkflow, dict]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: schema_calls.append((prefer, server_url)) or object(),
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: _workflow())
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("server should not run")),
    )

    def fake_run_embedded_sync(workflow: VibeWorkflow, **kwargs):
        embedded_calls.append((workflow, kwargs))
        return types.SimpleNamespace(
            run_id="run-embedded",
            prompt_id="prompt-embedded",
            outputs=[],
            metadata_path="metadata.json",
            log_path="embedded.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)

    assert _cmd_run(args) == 0

    assert schema_calls == [("auto", None)]
    assert embedded_calls[0][1] == {"backend": "api", "ensure_models": True}
    assert "run_id: run-embedded" in capsys.readouterr().out


def test_cmd_run_server_without_active_session_starts_one_shot_managed_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    run_calls: list[tuple[VibeWorkflow, str | None, str]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: object(),
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: _workflow())

    def fake_run_sync(workflow: VibeWorkflow, *, server_url: str | None, backend: str, **kwargs):
        run_calls.append((workflow, server_url, backend))
        return types.SimpleNamespace(
            run_id="run-managed",
            prompt_id="prompt-managed",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("embedded should not run")),
    )

    assert _cmd_run(args) == 0

    assert run_calls[0][1:] == (None, "api")
    assert "run_id: run-managed" in capsys.readouterr().out


def test_cmd_run_memory_profile_overrides_embedded_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )
    embedded_configs: list[SessionConfig] = []

    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda prefer, *, server_url=None: object())
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: workflow)

    def fake_run_embedded_sync(
        workflow: VibeWorkflow,
        *,
        backend: str,
        config: SessionConfig,
        ensure_models: bool,
    ):
        assert backend == "api"
        assert ensure_models is True
        embedded_configs.append(config)
        return types.SimpleNamespace(
            run_id="run-embedded",
            prompt_id="prompt-embedded",
            outputs=[],
            metadata_path="metadata.json",
            log_path="embedded.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)

    assert _cmd_run(args) == 0

    assert len(embedded_configs) == 1
    assert embedded_configs[0].memory_profile == 5
    assert embedded_configs[0].cache_policy == "lru:1"
    assert embedded_configs[0].reserve_vram_gb == 4.0
    assert workflow.metadata["comfy_configuration"]["cache_policy"] == "none"
    assert "run_id: run-embedded" in capsys.readouterr().out


def test_cmd_run_memory_profile_overrides_new_managed_server_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )
    server_configs: list[SessionConfig] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda prefer, *, server_url=None: object())
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: workflow)

    def fake_run_sync(
        workflow: VibeWorkflow,
        *,
        server_url: str | None,
        backend: str,
        config: SessionConfig,
        **kwargs,
    ):
        server_configs.append(config)
        return types.SimpleNamespace(
            run_id="run-managed",
            prompt_id="prompt-managed",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)

    assert _cmd_run(args) == 0

    assert len(server_configs) == 1
    assert server_configs[0].memory_profile == 5
    assert server_configs[0].cache_policy == "lru:1"
    assert server_configs[0].reserve_vram_gb == 4.0
    assert "run_id: run-managed" in capsys.readouterr().out


def test_cmd_run_memory_profile_rejects_explicit_external_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url="http://external.test",
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )

    monkeypatch.setattr(
        "vibecomfy.commands.run.load_workflow_reference",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("workflow should not load")),
    )

    assert _cmd_run(args) == 2

    assert "requires a new local VibeComfy runtime" in capsys.readouterr().err


def test_cmd_run_memory_profile_rejects_active_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="server",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=5,
    )

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: "http://warm.test")
    monkeypatch.setattr(
        "vibecomfy.commands.run.load_workflow_reference",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("workflow should not load")),
    )

    assert _cmd_run(args) == 2

    assert "Stop/restart the session" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# T7: eval-node tests
# ---------------------------------------------------------------------------


def _eval_test_workflow(with_vae: bool = True) -> VibeWorkflow:
    """Build a small workflow for eval-node testing.

    Edges:
      1 (CheckpointLoaderSimple) → 2 (KSampler)
      (optional) 3 (VAELoader) → sibling of KSampler

    Notes:
      - 1 emits MODEL + CLIP + VAE (output 0=MODEL, 1=CLIP, 2=VAE)
      - 2 emits LATENT
      - 3 (if present) is a standalone VAELoader not connected upstream of 2
    """
    wf = VibeWorkflow("eval-test", WorkflowSource("eval-test"))
    wf.nodes["1"] = VibeNode(
        "1", "CheckpointLoaderSimple",
        inputs={"ckpt_name": "model.safetensors"},
    )
    wf.nodes["2"] = VibeNode("2", "KSampler", inputs={"seed": 42, "steps": 20, "cfg": 7.0})
    # KSampler depends on model from checkpoint
    wf.edges.append(VibeEdge(from_node="1", from_output="0", to_node="2", to_input="model"))
    if with_vae:
        wf.nodes["3"] = VibeNode("3", "VAELoader", inputs={"vae_name": "vae.safetensors"})
        # NOTE: VAE is NOT connected upstream of KSampler — it's a sibling.
        # The CheckpointLoaderSimple node 1 already emits VAE at output 2.
    return wf


def test_compile_eval_subgraph_image_preview():
    """IMAGE output from a VAEDecode node gets PreviewImage injected."""
    from vibecomfy.runtime.eval import compile_eval_subgraph

    wf = VibeWorkflow("img-test", WorkflowSource("img-test"))
    wf.nodes["1"] = VibeNode("1", "VAEDecode", inputs={"samples": "latent", "vae": "vae_handle"})
    # VAEDecode has class_type with "vae" + "decode" → _detect_output_type returns IMAGE

    result = compile_eval_subgraph(wf, "1")
    assert isinstance(result, dict)
    # Should have the original node and a preview node
    assert "1" in result
    assert result["1"]["class_type"] == "VAEDecode"
    preview_key = "1_preview"
    assert preview_key in result, f"Expected {preview_key} in {list(result.keys())}"
    assert result[preview_key]["class_type"] == "PreviewImage"


def test_compile_eval_subgraph_latent_with_vae_from_checkpoint():
    """LATENT from KSampler with upstream CheckpointLoaderSimple (VAE-emitter)."""
    from vibecomfy.runtime.eval import compile_eval_subgraph

    wf = _eval_test_workflow(with_vae=False)
    # CheckpointLoaderSimple is a VAE emitter (output 2)
    # KSampler depends on CheckpointLoaderSimple for "model" input → upstream

    result = compile_eval_subgraph(wf, "2")
    assert isinstance(result, dict)
    # Should have VAEDecode + PreviewImage injected
    decode_key = "2_vaedecode"
    preview_key = "2_preview"
    assert decode_key in result, f"Expected {decode_key} in {list(result.keys())}"
    assert result[decode_key]["class_type"] == "VAEDecode"
    assert preview_key in result
    assert result[preview_key]["class_type"] == "PreviewImage"
    # KSampler should be wired to VAEDecode
    assert result[decode_key]["inputs"]["samples"] == ["2", 0]


def test_compile_eval_subgraph_latent_without_vae():
    """LATENT from KSampler with no upstream VAE → metadata fallback (SD1)."""
    from vibecomfy.runtime.eval import compile_eval_subgraph

    wf = VibeWorkflow("latent-no-vae", WorkflowSource("latent-no-vae"))
    wf.nodes["1"] = VibeNode("1", "KSampler", inputs={"seed": 42, "steps": 20, "cfg": 7.0})
    # No upstream nodes, no VAE emitter

    result = compile_eval_subgraph(wf, "1")
    assert isinstance(result, dict)
    assert result["type"] == "LATENT"
    assert result["node_id"] == "1"
    assert result["class_type"] == "KSampler"
    assert result["previewable"] is False
    assert result["plan_only"] is True


def test_compile_eval_subgraph_non_visualizable():
    """Non-visualizable output (e.g., CLIPTextEncode) returns metadata."""
    from vibecomfy.runtime.eval import compile_eval_subgraph

    wf = VibeWorkflow("non-viz", WorkflowSource("non-viz"))
    wf.nodes["1"] = VibeNode("1", "CLIPTextEncode", inputs={"text": "hello"})

    result = compile_eval_subgraph(wf, "1")
    assert isinstance(result, dict)
    assert result["previewable"] is False
    assert result["node_id"] == "1"
    assert result["class_type"] == "CLIPTextEncode"


def test_compile_eval_subgraph_absent_node():
    """Requesting a node not in the workflow raises KeyError."""
    from vibecomfy.runtime.eval import compile_eval_subgraph

    wf = VibeWorkflow("absent-test", WorkflowSource("absent-test"))
    wf.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "test"})

    with pytest.raises(KeyError):
        compile_eval_subgraph(wf, "999")


# ---------------------------------------------------------------------------
# T5: drift tests
# ---------------------------------------------------------------------------


def test_collect_drift_no_lockfile(tmp_path, monkeypatch):
    """When lockfile is missing, collect_drift reports 'lockfile not found'."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-no-lock", WorkflowSource("drift-no-lock"))
    wf.requirements.custom_nodes = ["some-pack"]

    _invalidate_cache_entry(wf)
    result = collect_drift(wf)
    assert result["actual"]["custom_node_packs"] == "lockfile not found"
    assert result["pinned"]["custom_node_packs"] == ["some-pack"]
    assert result["mismatches"] == []


def test_collect_drift_pinned_comfy_commit(tmp_path, monkeypatch):
    """Workflow.metadata comfy_commit pinned vs observed."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-comfy", WorkflowSource("drift-comfy"))
    wf.metadata["comfy_commit"] = "abc123def"

    # Mock _comfyui_git_head to return a different commit
    monkeypatch.setattr(
        "vibecomfy.runtime.drift._comfyui_git_head",
        lambda: "xyz789",
    )

    _invalidate_cache_entry(wf)
    result = collect_drift(wf)
    assert result["pinned"]["comfy_commit"] == "abc123def"
    assert result["actual"]["comfy_commit"] == "xyz789"
    assert any("ComfyUI commit" in m for m in result["mismatches"])


def test_collect_drift_canonical_schema_hash_match_is_not_mismatch(tmp_path, monkeypatch):
    """Canonical object_info metadata is comparable and matching hashes pass."""
    from vibecomfy.node_packs import LockEntry, compute_schema_hash
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift
    import vibecomfy.porting.object_info as object_info

    monkeypatch.chdir(tmp_path)
    pack_dir = tmp_path / "vendor" / "ExamplePack"
    (pack_dir / ".git").mkdir(parents=True)
    schema = {
        "ExampleNode": {
            "pack_slug": "example-pack",
            "git_commit": "abc123",
            "inputs": {"required": {"value": ["INT", {"default": 1}]}},
            "input_order": {"required": ["value"]},
            "outputs": [{"name": "INT", "type": "INT", "is_list": False}],
        }
    }
    expected_hash = compute_schema_hash(schema)
    schema["ExampleNode"]["schema_hash"] = expected_hash
    schema["ExampleNode"]["class_schema_sha256"] = expected_hash
    entry = LockEntry(
        name="ExamplePack",
        git_commit_sha="abc123",
        slug="example-pack",
        class_set=("ExampleNode",),
        class_schema_sha256=expected_hash,
    )

    monkeypatch.setattr("vibecomfy.runtime.drift.read_lockfile", lambda: [entry], raising=False)
    monkeypatch.setattr("vibecomfy.node_packs.read_lockfile", lambda: [entry])
    monkeypatch.setattr("vibecomfy.runtime.drift._nodepack_dir", lambda name: pack_dir)
    monkeypatch.setattr("vibecomfy.runtime.drift._git_head", lambda path: "abc123")
    monkeypatch.setattr(
        object_info,
        "get_class_by_identity",
        lambda class_type, *, pack_slug, git_commit=None, evidence_identity=None: schema[class_type],
    )

    wf = VibeWorkflow("drift-canonical", WorkflowSource("drift-canonical"))
    _invalidate_cache_entry(wf)
    result = collect_drift(wf)

    pack_info = result["actual"]["custom_node_packs"]["ExamplePack"]
    assert pack_info["schema_hash_status"] == "canonical"
    assert pack_info["actual_schema_hash"] == expected_hash
    assert result["mismatches"] == []


def test_collect_drift_legacy_schema_hash_is_unverified_not_mismatch(tmp_path, monkeypatch):
    """Legacy lockfile hashes without class_set are not compared as canonical hashes."""
    from vibecomfy.node_packs import LockEntry
    from vibecomfy.runtime.drift import _invalidate_cache_entry, collect_drift

    monkeypatch.chdir(tmp_path)
    pack_dir = tmp_path / "vendor" / "LegacyPack"
    (pack_dir / ".git").mkdir(parents=True)
    (pack_dir / "node.py").write_text("changed schema source", encoding="utf-8")
    entry = LockEntry(
        name="LegacyPack",
        git_commit_sha="abc123",
        class_schema_sha256="legacy-file-byte-hash",
    )

    monkeypatch.setattr("vibecomfy.node_packs.read_lockfile", lambda: [entry])
    monkeypatch.setattr("vibecomfy.runtime.drift._nodepack_dir", lambda name: pack_dir)
    monkeypatch.setattr("vibecomfy.runtime.drift._git_head", lambda path: "abc123")

    wf = VibeWorkflow("drift-legacy", WorkflowSource("drift-legacy"))
    _invalidate_cache_entry(wf)
    result = collect_drift(wf)

    pack_info = result["actual"]["custom_node_packs"]["LegacyPack"]
    assert pack_info["schema_hash_status"] == "unverified_legacy"
    assert "actual_schema_hash" not in pack_info
    assert result["mismatches"] == []


def test_enforce_strict_drift_raises_on_mismatch(tmp_path, monkeypatch):
    """enforce_strict_drift raises DriftError when mismatches exist."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, enforce_strict_drift
    from vibecomfy.errors import DriftError

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-strict", WorkflowSource("drift-strict"))
    wf.metadata["comfy_commit"] = "pinned-commit"

    monkeypatch.setattr(
        "vibecomfy.runtime.drift._comfyui_git_head",
        lambda: "different-commit",
    )

    _invalidate_cache_entry(wf)
    with pytest.raises(DriftError, match="Pre-queue drift check failed"):
        enforce_strict_drift(wf)


def test_enforce_strict_drift_passes_without_mismatch(tmp_path, monkeypatch):
    """enforce_strict_drift does nothing when no mismatches exist."""
    from vibecomfy.runtime.drift import _invalidate_cache_entry, enforce_strict_drift

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-ok", WorkflowSource("drift-ok"))

    _invalidate_cache_entry(wf)
    # Should not raise
    enforce_strict_drift(wf)


def test_drift_caching(tmp_path, monkeypatch):
    """Per-process caching prevents repeated filesystem/git calls."""
    import vibecomfy.runtime.drift as drift_module

    monkeypatch.chdir(tmp_path)
    wf = VibeWorkflow("drift-cache", WorkflowSource("drift-cache"))

    call_count = [0]
    original = getattr(drift_module, "_comfyui_git_head", None)

    def counting_git_head():
        call_count[0] += 1
        return None

    monkeypatch.setattr(drift_module, "_comfyui_git_head", counting_git_head)
    drift_module._invalidate_cache_entry(wf)

    result1 = drift_module.collect_drift(wf)
    result2 = drift_module.collect_drift(wf)
    # Second call should hit the cache, so the git head function is called only once
    assert result1 is result2
    assert call_count[0] == 1


def test_session_config_strict_drift_default():
    """SessionConfig.strict_drift defaults to False."""
    config = SessionConfig()
    assert config.strict_drift is False


def test_session_config_strict_drift_explicit():
    """SessionConfig.strict_drift can be set explicitly."""
    config = SessionConfig(strict_drift=True)
    assert config.strict_drift is True


# ---------------------------------------------------------------------------
# T21: normalize_prompt_id queue return shape tests
# ---------------------------------------------------------------------------
# normalize_prompt_id must extract prompt_id from both dict and object queue
# return shapes.  Each path that writes RunResult.prompt_id or metadata must
# be covered.
# ---------------------------------------------------------------------------


def _make_one_shot_run_wf() -> VibeWorkflow:
    """Minimal workflow usable in one-shot run tests."""
    wf = VibeWorkflow("one-shot-test", WorkflowSource("one-shot-test"))
    wf.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "t21"})
    return wf


class _ObjectQueueResult:
    """Simulates a queue result returned as an object (attribute access)."""

    def __init__(self, prompt_id: str, outputs: list | None = None) -> None:
        self.prompt_id = prompt_id
        self.outputs = outputs or []


def test_normalize_prompt_id_dict_shape() -> None:
    """normalize_prompt_id extracts prompt_id from a dict return."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    result = normalize_prompt_id({"prompt_id": "abc-123", "extra": "ignored"})
    assert result == "abc-123"


def test_normalize_prompt_id_object_shape() -> None:
    """normalize_prompt_id extracts prompt_id from an object return."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    result = normalize_prompt_id(_ObjectQueueResult("obj-456"))
    assert result == "obj-456"


def test_normalize_prompt_id_dict_missing_key() -> None:
    """normalize_prompt_id returns None when prompt_id key absent in dict."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    assert normalize_prompt_id({}) is None
    assert normalize_prompt_id({"other": "x"}) is None


def test_normalize_prompt_id_object_missing_attr() -> None:
    """normalize_prompt_id returns None when object lacks prompt_id attr."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    class _NoId:
        pass

    assert normalize_prompt_id(_NoId()) is None


def test_normalize_prompt_id_numeric_coerced_to_str() -> None:
    """normalize_prompt_id stringifies numeric prompt_ids for both shapes."""
    from vibecomfy.runtime.execution import normalize_prompt_id

    assert normalize_prompt_id({"prompt_id": 7}) == "7"

    class _NumId:
        prompt_id = 99

    assert normalize_prompt_id(_NumId()) == "99"


def test_one_shot_run_dict_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One-shot run path: dict queue result → RunResult.prompt_id via normalize_prompt_id."""

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _DictClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def queue_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "dict-prompt-id"}

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {}}}

    async def _fake_history_dict(url: str, pid: str | None, config=None) -> dict:
        return {pid: {"outputs": {}}} if pid else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _DictClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history_dict)

    result = asyncio.run(runtime_run_module.run(_make_one_shot_run_wf()))
    assert result.prompt_id == "dict-prompt-id"


def test_one_shot_run_object_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One-shot run path: object queue result → RunResult.prompt_id via normalize_prompt_id."""

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _ObjectClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def queue_prompt(self, prompt: dict) -> _ObjectQueueResult:
            return _ObjectQueueResult("obj-prompt-id")

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {}}}

    async def _fake_history_obj(url: str, pid: str | None, config=None) -> dict:
        return {pid: {"outputs": {}}} if pid else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _ObjectClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history_obj)

    result = asyncio.run(runtime_run_module.run(_make_one_shot_run_wf()))
    assert result.prompt_id == "obj-prompt-id"


def test_embedded_session_dict_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Embedded session: dict queue result → RunResult.prompt_id via normalize_prompt_id."""

    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def queue_prompt_api(self, api_dict: dict) -> dict:
            return {"prompt_id": "emb-dict-id", "outputs": []}

        async def clear_cache(self) -> None:
            pass

    import sys
    import types as _types

    monkeypatch.setitem(sys.modules, "comfy", _types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", _types.ModuleType("comfy.client"))
    embedded = _types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()

    def _default_config():
        class _C(dict):
            def __getattr__(self, k):
                try:
                    return self[k]
                except KeyError as e:
                    raise AttributeError(k) from e

        return _C({"cwd": None})

    embedded.default_configuration = _default_config
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.delenv("VIBECOMFY_WARM", raising=False)
    monkeypatch.chdir(tmp_path)
    # Disable schema validation so schema provider is not needed
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(
        session_module.EmbeddedSession().run(wf)
    )
    assert result.prompt_id == "emb-dict-id"


def test_embedded_session_object_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Embedded session: object queue result → RunResult.prompt_id via normalize_prompt_id."""

    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def queue_prompt_api(self, api_dict: dict) -> _ObjectQueueResult:
            return _ObjectQueueResult("emb-obj-id")

        async def clear_cache(self) -> None:
            pass

    import sys
    import types as _types

    monkeypatch.setitem(sys.modules, "comfy", _types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", _types.ModuleType("comfy.client"))
    embedded = _types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()

    def _default_config():
        class _C(dict):
            def __getattr__(self, k):
                try:
                    return self[k]
                except KeyError as e:
                    raise AttributeError(k) from e

        return _C({"cwd": None})

    embedded.default_configuration = _default_config
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.delenv("VIBECOMFY_WARM", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(
        session_module.EmbeddedSession().run(wf)
    )
    assert result.prompt_id == "emb-obj-id"


def test_server_session_dict_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Server session: dict queue result → RunResult.prompt_id via normalize_prompt_id."""

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def queue_prompt(self, api_dict: dict) -> dict:
            return {"prompt_id": "srv-dict-id"}

    async def _fake_history(url: str, pid: str | None, *, config=None) -> dict:
        return {pid: {"outputs": {}}} if pid else {}

    async def _fake_start(self) -> None:
        self.url = "http://fake-srv.test"

    async def _fake_watchdog(*args, **kwargs):
        return None

    async def _fake_finalize_watchdog(*args, **kwargs):
        pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.ServerSession, "start", _fake_start)
    monkeypatch.setattr(session_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(session_module, "_wait_for_server_history", _fake_history)
    monkeypatch.setattr(session_module, "_start_watchdog", _fake_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", _fake_finalize_watchdog)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(session_module.ServerSession()._run_untracked(wf))
    assert result.prompt_id == "srv-dict-id"


def test_server_session_object_queue_result_sets_run_result_prompt_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Server session: object queue result → RunResult.prompt_id via normalize_prompt_id."""

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def queue_prompt(self, api_dict: dict) -> _ObjectQueueResult:
            return _ObjectQueueResult("srv-obj-id")

    async def _fake_history(url: str, pid: str | None, *, config=None) -> dict:
        return {pid: {"outputs": {}}} if pid else {}

    async def _fake_start(self) -> None:
        self.url = "http://fake-srv.test"

    async def _fake_watchdog(*args, **kwargs):
        return None

    async def _fake_finalize_watchdog(*args, **kwargs):
        pass

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.ServerSession, "start", _fake_start)
    monkeypatch.setattr(session_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(session_module, "_wait_for_server_history", _fake_history)
    monkeypatch.setattr(session_module, "_start_watchdog", _fake_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", _fake_finalize_watchdog)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    wf = _make_one_shot_run_wf()
    result = asyncio.run(session_module.ServerSession()._run_untracked(wf))
    assert result.prompt_id == "srv-obj-id"


def test_prompt_id_consistency_across_run_result_and_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RunResult.prompt_id matches the prompt_id stored in the metadata.json queued field.

    The 'queued' value is written verbatim into metadata.json, while RunResult.prompt_id
    is the normalized string.  For a dict return the two must agree without expansion.
    """
    import json as _json

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _DictClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def queue_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "meta-check-id", "extra_field": "ignored"}

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {}}}

    async def _fake_history_meta(url: str, pid: str | None, config=None) -> dict:
        return {pid: {"outputs": {}}} if pid else {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _DictClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history_meta)

    result = asyncio.run(runtime_run_module.run(_make_one_shot_run_wf()))

    assert result.prompt_id == "meta-check-id"
    metadata = _json.loads(Path(result.metadata_path).read_text())
    # queued is stored verbatim; prompt_id in RunResult is the normalized string
    assert metadata["queued"]["prompt_id"] == "meta-check-id"
    # RunResult does not gain extra fields beyond what is already in its dataclass
    assert not hasattr(result, "extra_field")


# ---------------------------------------------------------------------------
# T6: _allocate_run_dir tests (collision-resistant run directory allocation)
# ---------------------------------------------------------------------------


def test_allocate_run_dir_prefix_and_unique_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_allocate_run_dir produces IDs with stable prefix, timestamp, and uuid4 hex."""
    import time as _time

    monkeypatch.chdir(tmp_path)
    run_id, run_dir = runtime_run_module._allocate_run_dir("testprefix")

    # Stable prefix
    assert run_id.startswith(
        "testprefix-"
    ), f"Expected 'testprefix-' prefix, got {run_id!r}"

    # Format: testprefix-<timestamp>-<8 hex chars>
    suffix = run_id[len("testprefix-"):]
    parts = suffix.split("-")
    assert len(parts) == 2, f"Expected 2 parts after prefix, got {parts}"

    # First part is integer timestamp within a reasonable window
    assert parts[0].isdigit(), f"Expected integer timestamp, got {parts[0]!r}"
    ts = int(parts[0])
    now = int(_time.time())
    assert abs(ts - now) <= 5, f"Timestamp {ts} too far from now ({now})"

    # Second part is 8 lowercase hex chars (uuid4 hex fragment)
    assert len(parts[1]) == 8, f"Expected 8 hex chars, got {parts[1]!r} (len={len(parts[1])})"
    assert all(c in "0123456789abcdef" for c in parts[1]), (
        f"Non-hex chars in uuid fragment {parts[1]!r}"
    )

    # Directory was created
    assert run_dir.exists()
    assert run_dir.is_dir()


def test_allocate_run_dir_smoke_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_allocate_run_dir('smoke') produces IDs with 'smoke-' prefix."""
    monkeypatch.chdir(tmp_path)
    run_id, run_dir = runtime_run_module._allocate_run_dir("smoke")
    assert run_id.startswith("smoke-")
    assert run_dir.exists()


def test_allocate_run_dir_collision_raises_file_exists_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forced collision in _allocate_run_dir raises FileExistsError (no artifact merging)."""
    import time as _time
    import uuid as _uuid

    monkeypatch.chdir(tmp_path)

    # Freeze uuid4 and time so a second call inevitably collides
    fixed_uuid = "deadbeef-cafe-4bad-babe-123456789abc"
    monkeypatch.setattr(_uuid, "uuid4", lambda: _uuid.UUID(fixed_uuid))
    frozen_time = 1000000.0
    monkeypatch.setattr(_time, "time", lambda: frozen_time)

    # First allocation succeeds
    run_id1, run_dir1 = runtime_run_module._allocate_run_dir("collision")
    assert run_dir1.exists()
    assert run_id1 == "collision-1000000-deadbeef"

    # Second allocation with identical prefix+timestamp+uuid must collide
    with pytest.raises(FileExistsError):
        runtime_run_module._allocate_run_dir("collision")


def test_allocate_run_dir_different_prefixes_no_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Different prefixes produce distinct directories even with frozen time + uuid."""
    import time as _time
    import uuid as _uuid

    monkeypatch.chdir(tmp_path)

    fixed_uuid = "deadbeef-cafe-4bad-babe-123456789abc"
    monkeypatch.setattr(_uuid, "uuid4", lambda: _uuid.UUID(fixed_uuid))
    frozen_time = 2000000.0
    monkeypatch.setattr(_time, "time", lambda: frozen_time)

    run_id_a, run_dir_a = runtime_run_module._allocate_run_dir("alpha")
    run_id_b, run_dir_b = runtime_run_module._allocate_run_dir("beta")

    assert run_id_a.startswith("alpha-")
    assert run_id_b.startswith("beta-")
    assert run_id_a != run_id_b
    assert run_dir_a != run_dir_b
    assert run_dir_a.exists()
    assert run_dir_b.exists()


def test_run_uses_collision_resistant_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """run() produces a run_id with the 'run-' collision-resistant prefix and uuid suffix."""
    import re

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _FakeClient:
        def __init__(self, server_url: str) -> None:
            pass

        async def queue_prompt(self, prompt: dict) -> dict:
            return {"prompt_id": "prompt-t6-run"}

        async def history(self, prompt_id: str) -> dict:
            return {prompt_id: {"outputs": {}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _FakeClient)
    monkeypatch.setattr(
        runtime_run_module, "_build_schema_provider", lambda active_url: None
    )
    # _wait_for_server_history needs to return something valid
    async def _fake_history(url: str, pid: str | None, config=None) -> dict:
        return {pid: {"outputs": {}}} if pid else {}

    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", _fake_history)

    result = asyncio.run(runtime_run_module.run(_make_one_shot_run_wf()))

    # run_id format: run-<timestamp>-<8 hex>
    assert re.match(r"^run-\d+-[0-9a-f]{8}$", result.run_id), (
        f"run_id {result.run_id!r} does not match expected collision-resistant pattern"
    )
    run_dir = tmp_path / "out" / "runs" / result.run_id
    assert run_dir.is_dir()
    assert (run_dir / "metadata.json").exists()


def test_smoke_runtime_uses_collision_resistant_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """smoke_runtime() produces a run_id with the 'smoke-' collision-resistant prefix."""
    import re

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://127.0.0.1:8188"

    class _FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def object_info(self) -> dict:
            return {"KSampler": {}, "SaveImage": {}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", _FakeClient)

    result = asyncio.run(runtime_run_module.smoke_runtime())

    assert re.match(r"^smoke-\d+-[0-9a-f]{8}$", result["run_id"]), (
        f"run_id {result['run_id']!r} does not match expected collision-resistant pattern"
    )
    assert result["node_count"] == 2
    run_dir = tmp_path / "out" / "runs" / result["run_id"]
    assert run_dir.is_dir()
