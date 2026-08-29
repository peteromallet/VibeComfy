"""Shared fixtures and helper classes for the split test_runtime_session_*.py files.

Pytest auto-discovers fixtures referenced from a test module's namespace, so
each split file does ``from tests._runtime_session_helpers import fake_comfy``
and uses the fixture by name. Underscore-prefixed so pytest does not collect
this module as a test file.
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.runtime.session as session_module
import vibecomfy.runtime.client as client_module
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class FakeConfiguration(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _default_configuration() -> FakeConfiguration:
    return FakeConfiguration({"cwd": None})


@pytest.fixture
def fake_comfy(monkeypatch: pytest.MonkeyPatch):
    class FakeComfy:
        instances: list["FakeComfy"] = []
        enter_count = 0
        exit_count = 0

        def __init__(self, configuration=None) -> None:
            self.configuration = configuration
            self.queue_calls: list[dict[str, Any]] = []
            self.clear_cache_calls = 0
            self.reconfigure_calls: list[Any] = []
            FakeComfy.instances.append(self)

        async def __aenter__(self):
            FakeComfy.enter_count += 1
            return self

        async def __aexit__(self, exc_type, exc, tb):
            FakeComfy.exit_count += 1

        async def queue_prompt_api(self, api_dict):
            self.queue_calls.append(api_dict)
            return {"prompt_id": f"prompt-{len(self.queue_calls)}", "outputs": []}

        async def clear_cache(self):
            self.clear_cache_calls += 1

        async def reconfigure(self, configuration):
            self.reconfigure_calls.append(configuration)
            return configuration

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = _default_configuration
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.delenv("VIBECOMFY_WARM", raising=False)
    return FakeComfy


def _workflow(ckpt: str = "model-a.safetensors", *, seed: int = 1) -> VibeWorkflow:
    workflow = VibeWorkflow("session-test", WorkflowSource("session-test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": ckpt},
    )
    workflow.nodes["2"] = VibeNode("2", "KSampler", inputs={"seed": seed})
    return workflow


class WarmProvider:
    def __init__(self) -> None:
        self.cache_path = Path("unused-cache.json")
        self._object_info: dict[str, Any] | None = None
        self.object_info_calls = 0
        self._schemas = {
            "CheckpointLoaderSimple": NodeSchema(
                "CheckpointLoaderSimple",
                None,
                {"ckpt_name": InputSpec("STRING")},
                [],
            ),
            "KSampler": NodeSchema("KSampler", None, {"seed": InputSpec("INT")}, []),
        }

    async def object_info_async(self) -> dict[str, Any]:
        self.object_info_calls += 1
        return {"ready": True}

    def schemas(self) -> dict[str, NodeSchema]:
        if self._object_info is None:
            raise AssertionError("schemas read before object_info_async warmup")
        return self._schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)


class FakeResponse:
    def __init__(self, status_code: int = 200, data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._data = data or {}
        self.content = json.dumps(self._data).encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._data


class FakeAsyncClient:
    posts: list[tuple[str, dict[str, Any] | None]] = []
    gets: list[str] = []
    history_outputs: dict[str, Any] = {
        "9": {"images": [{"filename": "server-output.png", "subfolder": "", "type": "output"}]}
    }
    history_status: dict[str, Any] = {
        "status_str": "success",
        "completed": True,
        "messages": [],
    }

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        if "/history/" in url:
            prompt_id = url.rstrip("/").rsplit("/", 1)[-1]
            return FakeResponse(
                200,
                {
                    prompt_id: {
                        "outputs": self.history_outputs,
                        "status": self.history_status,
                    }
                },
            )
        return FakeResponse(200, {"ready": True})

    async def post(self, url: str, json: dict[str, Any] | None = None) -> FakeResponse:
        self.posts.append((url, json))
        if url.endswith("/prompt"):
            return FakeResponse(200, {"prompt_id": f"prompt-{len(self.posts)}"})
        return FakeResponse(200, {})


class FakeProcess:
    def __init__(self, *, wait_blocks: bool = False) -> None:
        self.returncode: int | None = None
        self.signals: list[int] = []
        self.killed = False
        self.wait_blocks = wait_blocks

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)

    async def wait(self) -> int:
        if self.wait_blocks:
            await asyncio.sleep(3600)
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch):
    FakeAsyncClient.posts = []
    FakeAsyncClient.gets = []
    FakeAsyncClient.history_outputs = {
        "9": {"images": [{"filename": "server-output.png", "subfolder": "", "type": "output"}]}
    }
    FakeAsyncClient.history_status = {
        "status_str": "success",
        "completed": True,
        "messages": [],
    }
    spawned: list[tuple[tuple[str, ...], FakeProcess]] = []

    async def fake_create_subprocess_exec(*argv, **kwargs):
        process = FakeProcess()
        spawned.append((tuple(argv), process))
        return process

    monkeypatch.setattr(session_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(client_module.httpx, "AsyncClient", FakeAsyncClient)
    return spawned


def _patch_fast_runtime_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_prepare(workflow, *, backend, schema_provider, on_unavailable, cache_only=False):
        return workflow.compile(backend=backend)

    async def fake_maybe_flush(_session, _fp):
        return None

    async def fake_start_watchdog(*, server_url, client_id, api_dict):
        return object()

    async def fake_finalize_watchdog(_watchdog, *, run_dir, reason):
        return None

    monkeypatch.setattr(session_module, "_prepare_prompt_async", fake_prepare)
    monkeypatch.setattr(session_module, "_maybe_flush_for_policy", fake_maybe_flush)
    monkeypatch.setattr(session_module, "_start_watchdog", fake_start_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", fake_finalize_watchdog)
    monkeypatch.setattr(session_module, "_build_schema_provider", lambda _url: object())
