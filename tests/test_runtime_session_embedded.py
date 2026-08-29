from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from vibecomfy.errors import QueueError, RuntimeNodeError

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import EmbeddedSession, SessionConfig

from tests._runtime_session_helpers import (
    FakeConfiguration,
    _patch_fast_runtime_run,
    _workflow,
    fake_comfy,  # noqa: F401 -- pytest fixture imported for use in tests
)


def test_embedded_session_reuses_single_comfy_context(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_twice() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow())
            await session.run(_workflow())
        finally:
            await session.stop()

    asyncio.run(run_twice())

    assert fake_comfy.enter_count == 1
    assert fake_comfy.exit_count == 1
    assert len(fake_comfy.instances) == 1
    assert len(fake_comfy.instances[0].queue_calls) == 2


def test_embedded_session_explicit_empty_success_remains_valid(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def successful_queue(_self, _api_dict):
        return {
            "prompt_id": "embedded-empty",
            "outputs": {},
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [],
            },
        }

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", successful_queue)

    result = asyncio.run(EmbeddedSession().run(_workflow()))

    assert result.prompt_id == "embedded-empty"
    assert result.outputs == []
    assert Path(result.metadata_path).is_file()



def test_embedded_session_preserves_statusless_raw_output_mapping(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def raw_outputs(_self, _api_dict):
        return {"2": {"images": [{"filename": "raw-output.png"}]}}

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", raw_outputs)
    result = asyncio.run(EmbeddedSession().run(_workflow()))

    assert result.prompt_id is None
    assert result.outputs == ["raw-output.png"]

def test_embedded_session_terminal_error_fails_before_metadata(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def failed_queue(_self, _api_dict):
        return {
            "prompt_id": "embedded-error",
            "outputs": {},
            "status": {
                "status_str": "error",
                "completed": True,
                "messages": [
                    [
                        "execution_error",
                        {
                            "node_id": "2",
                            "exception_message": "embedded sampler failed",
                        },
                    ]
                ],
            },
        }

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", failed_queue)

    with pytest.raises(RuntimeNodeError, match="embedded sampler failed"):
        asyncio.run(EmbeddedSession().run(_workflow()))

    assert not list(tmp_path.glob("out/runs/*/metadata.json"))


def test_embedded_session_malformed_result_fails_before_metadata(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def malformed_queue(_self, _api_dict):
        return {"prompt_id": "embedded-malformed"}

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", malformed_queue)

    with pytest.raises(QueueError, match="embedded result is missing outputs"):
        asyncio.run(EmbeddedSession().run(_workflow()))

    assert not list(tmp_path.glob("out/runs/*/metadata.json"))


def test_embedded_session_flush_invokes_clear_cache(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_flush() -> None:
        session = EmbeddedSession()
        try:
            await session.start()
            await session.flush()
        finally:
            await session.stop()

    asyncio.run(run_flush())

    assert fake_comfy.instances[0].clear_cache_calls == 1


def test_embedded_session_reconfigure_passes_typed_configuration(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_reconfigure() -> None:
        session = EmbeddedSession()
        try:
            await session.start()
            await session.reconfigure(
                SessionConfig(
                    port=8200,
                    vram_policy="high",
                    reserve_vram_gb=2.0,
                    cache_policy="lru:3",
                    disable_smart_memory=True,
                )
            )
        finally:
            await session.stop()

    asyncio.run(run_reconfigure())

    config = fake_comfy.instances[0].reconfigure_calls[0]
    assert isinstance(config, FakeConfiguration)
    assert config.port == 8200
    assert config.highvram is True
    assert config.reserve_vram == 2.0
    assert config.cache_lru == 3
    assert config.disable_smart_memory is True


def test_auto_flush_truth_table(fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    free_vram = 0.5
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: free_vram)

    async def run_cases() -> None:
        nonlocal free_vram
        session = EmbeddedSession(SessionConfig(auto_flush_vram_threshold_gb=2.0))
        try:
            await session.run(_workflow("model-a.safetensors", seed=1))
            await session.run(_workflow("model-a.safetensors", seed=2))
            assert fake_comfy.instances[0].clear_cache_calls == 0
            await session.run(_workflow("model-b.safetensors", seed=2))
            assert fake_comfy.instances[0].clear_cache_calls == 1
            free_vram = 10.0
            await session.run(_workflow("model-c.safetensors", seed=2))
            assert fake_comfy.instances[0].clear_cache_calls == 1
        finally:
            await session.stop()

    asyncio.run(run_cases())


def test_warm_policy_never_flushes_before_every_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_WARM", "never")

    async def run_cases() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow("model-a.safetensors"))
            await session.run(_workflow("model-a.safetensors"))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert fake_comfy.instances[0].clear_cache_calls == 2


def test_warm_policy_always_never_auto_flushes(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_WARM", "always")
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: 0.5)

    async def run_cases() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow("model-a.safetensors"))
            await session.run(_workflow("model-b.safetensors"))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert fake_comfy.instances[0].clear_cache_calls == 0


def test_embedded_stop_refuses_inflight_when_not_waiting(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        with pytest.raises(RuntimeError, match="session.stop\\(\\) called while a run is in flight"):
            await session.stop(wait_for_inflight=False)
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())


def test_embedded_stop_waits_for_inflight_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        stop_task = asyncio.create_task(session.stop(wait_for_inflight=True))
        await asyncio.sleep(0)
        assert not stop_task.done()
        release.set()
        await stop_task
        assert task.done()

    asyncio.run(run_case())


def test_embedded_stop_exits_comfy_context_directly(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_tasks: list[asyncio.Task[Any] | None] = []

    async def recording_exit(self, exc_type, exc, tb):
        exit_tasks.append(asyncio.current_task())

    monkeypatch.setattr(fake_comfy, "__aexit__", recording_exit)

    async def run_case() -> None:
        session = EmbeddedSession()
        await session.start()
        task = asyncio.current_task()
        await session.stop()
        assert exit_tasks == [task]
        assert session._context is None
        assert session._comfy is None

    asyncio.run(run_case())


def test_embedded_stop_reraises_inflight_run_exception_before_teardown(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def failing_queue(self, api_dict):
            started.set()
            await release.wait()
            raise ValueError("boom")

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", failing_queue)
        session = EmbeddedSession()
        workflow = _workflow()
        workflow.metadata["id_map"] = {"sampler": "2"}
        workflow.nodes["2"].metadata["source_id"] = "7"
        task = asyncio.create_task(session.run(workflow))
        await started.wait()
        stop_task = asyncio.create_task(session.stop(wait_for_inflight=True))
        await asyncio.sleep(0)
        assert not stop_task.done()
        release.set()
        with pytest.raises(RuntimeError, match="Workflow queue failed: boom") as exc_info:
            await stop_task
        message = str(exc_info.value)
        assert "id_map=" in message
        assert "'sampler': '2'" in message
        assert "'7': '2'" in message
        assert task.done()
        assert fake_comfy.exit_count == 0
        await session.stop()

    asyncio.run(run_case())


def test_embedded_concurrent_run_is_rejected(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        with pytest.raises(RuntimeError, match="session already has a run in flight"):
            await session.run(_workflow(seed=2))
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())


def test_embedded_reload_reopens_fresh_context_and_resets_cached_state(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_case() -> None:
        session = EmbeddedSession()
        await session.start()
        first_comfy = session._comfy
        session._schema_provider = object()
        session._schema_warning_emitted = True
        session.last_fingerprint = ("stale",)
        await session.reload_for_nodepack_change(reason="test")
        assert fake_comfy.exit_count == 1
        assert fake_comfy.enter_count == 2
        assert len(fake_comfy.instances) == 2
        assert session._comfy is not first_comfy
        assert session._schema_provider is None
        assert session._schema_warning_emitted is False
        assert session.last_fingerprint is None
        await session.stop()

    asyncio.run(run_case())


def test_embedded_reload_refuses_inflight_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        with pytest.raises(RuntimeError, match="reload_for_nodepack_change refused: run in flight"):
            await session.reload_for_nodepack_change(reason="test")
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())
