from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

import vibecomfy.runtime.session as runtime_session
from vibecomfy.runtime.model_policy import resolve_model_preflight_policy, shared_models_root
from vibecomfy.runtime.session import ServerSession
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

runtime_run = importlib.import_module("vibecomfy.runtime.run")


def _workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("policy", WorkflowSource("policy"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out"})
    return workflow


def test_explicit_remote_ensure_models_requires_matching_shared_root(tmp_path: Path) -> None:
    local = tmp_path / "models"
    shared = tmp_path / "other"

    with pytest.raises(RuntimeError, match="requires --shared-models-root"):
        resolve_model_preflight_policy(
            mode="explicit_remote_server_unverified",
            ensure_models=True,
            local_models_root=local,
        )

    with pytest.raises(RuntimeError, match="requires shared models root to match"):
        resolve_model_preflight_policy(
            mode="explicit_remote_server_unverified",
            ensure_models=True,
            local_models_root=local,
            shared_root=shared,
        )

    policy = resolve_model_preflight_policy(
        mode="explicit_remote_server_unverified",
        ensure_models=True,
        local_models_root=local,
        shared_root=local,
    )
    assert policy.mode == "explicit_remote_server_shared_root"
    assert policy.ensure_models is True


def test_shared_models_root_cli_overrides_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_SHARED_MODELS_ROOT", str(tmp_path / "env"))

    assert shared_models_root(tmp_path / "cli") == str((tmp_path / "cli").resolve())


def test_runtime_remote_policy_blocks_before_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))
    queued: list[dict] = []

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://remote.test"

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, prompt: dict) -> dict:
            queued.append(prompt)
            return {"prompt_id": "p", "outputs": []}

    monkeypatch.setattr(runtime_run, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run, "_build_schema_provider", lambda _url: None)

    with pytest.raises(RuntimeError, match="requires shared models root to match"):
        asyncio.run(
            runtime_run.run(
                _workflow(),
                server_url="http://remote.test",
                ensure_models=True,
                shared_models_root=tmp_path / "different",
            )
        )

    assert queued == []


def test_server_session_run_uses_shared_model_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_apply(workflow: VibeWorkflow, policy) -> None:
        calls.append(f"{policy.mode}:{policy.ensure_models}")

    async def fake_run_untracked(self, workflow: VibeWorkflow, *, backend: str = "api", strict_drift: bool = False, **kwargs):
        calls.append("queue")
        return object()

    monkeypatch.setattr(runtime_session, "apply_model_preflight", fake_apply)
    monkeypatch.setattr(ServerSession, "_run_untracked", fake_run_untracked)

    result = asyncio.run(ServerSession().run(_workflow(), ensure_models=True))

    assert result is not None
    assert calls == ["managed_local_server:True", "queue"]
