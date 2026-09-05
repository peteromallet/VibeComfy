from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from vibecomfy.errors import QueueError, RuntimeNodeError

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import EmbeddedSession, SessionConfig
from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
from vibecomfy.porting.object_info import ObjectInfoLookupResult
from vibecomfy.schema import NodeSchema
from vibecomfy.workflow_bundle import load_bundle

from tests._runtime_session_helpers import (
    FakeConfiguration,
    _workflow,
    fake_comfy,  # noqa: F401 -- pytest fixture imported for use in tests
)


def _approved(workflow):
    for node in workflow.nodes.values():
        if not node.uid:
            node.uid = f"runtime-{node.id}"
    bundle = load_bundle(workflow)
    class _FixtureProvider:
        def get_schema(self, class_type):
            return NodeSchema(class_type, None, {}, [])

    entry = ModelEntry(
        "runtime-fixture-model",
        ModelSource("local"),
        0,
        (ModelTarget("comfy_core", "checkpoints"),),
    )
    with (
        patch("vibecomfy.registry.models_loader.load_registry", return_value=(entry,)),
        patch("vibecomfy.registry.models_loader.resolve_model_entry", return_value=entry),
        patch("vibecomfy.fetch.is_present", return_value=True),
        patch(
            "vibecomfy.porting.object_info.resolve_class_entry",
            return_value=ObjectInfoLookupResult(entry={}, source="fixture", low_confidence=False),
        ),
    ):
        return bundle.compile(schema_provider=_FixtureProvider()), bundle


def _patch_fast_runtime_run(monkeypatch):
    async def fake_prepare(record, bundle, *, backend, schema_provider, on_unavailable, cache_only=False):
        return session_module.PreparedPrompt(record.to_dict()["api_projection"])

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


def _terminal_events(tmp_path: Path, record):
    run_dir = next(path for path in (tmp_path / "out/runs").iterdir() if path.is_dir())
    attempt = json.loads((run_dir / "attempt.json").read_text(encoding="utf-8"))
    lifecycle = run_dir / "transactions" / record.api_digest / "lifecycle_events.jsonl"
    events = [json.loads(line) for line in lifecycle.read_text(encoding="utf-8").splitlines()]
    return attempt, events


def test_embedded_session_reuses_single_comfy_context(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_twice() -> None:
        session = EmbeddedSession()
        try:
            await session.run(*_approved(_workflow()))
            await session.run(*_approved(_workflow()))
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

    result = asyncio.run(EmbeddedSession().run(*_approved(_workflow())))

    assert result.prompt_id == "embedded-empty"
    assert result.outputs == []
    assert Path(result.metadata_path).is_file()




@pytest.mark.parametrize(
    ("outputs", "expected"),
    [
        ([], []),
        ([{"images": [{"filename": "embedded-list.png"}]}], ["embedded-list.png"]),
    ],
)
def test_embedded_session_status_bearing_list_outputs_remain_valid(
    fake_comfy,
    outputs: list[dict[str, Any]],
    expected: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def successful_queue(_self, _api_dict):
        return {
            "prompt_id": "embedded-list",
            "outputs": outputs,
            "status": {
                "status_str": "success",
                "completed": True,
                "messages": [],
            },
        }

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", successful_queue)
    result = asyncio.run(EmbeddedSession().run(*_approved(_workflow())))

    assert result.outputs == expected
    assert Path(result.metadata_path).is_file()


def test_embedded_session_preserves_statusless_raw_output_mapping(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def raw_outputs(_self, _api_dict):
        return {"2": {"images": [{"filename": "raw-output.png"}]}}

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", raw_outputs)
    with pytest.raises(QueueError, match="did not include a prompt_id"):
        asyncio.run(EmbeddedSession().run(*_approved(_workflow())))
    assert not list(tmp_path.glob("out/runs/*/metadata.json"))

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
        asyncio.run(EmbeddedSession().run(*_approved(_workflow())))

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
        asyncio.run(EmbeddedSession().run(*_approved(_workflow())))

    assert not list(tmp_path.glob("out/runs/*/metadata.json"))


@pytest.mark.parametrize("failure", [asyncio.TimeoutError("queue timeout"), QueueError("queue rejected")])
def test_embedded_queue_failure_classifies_timeout_and_rejection(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    record, bundle = _approved(_workflow())

    async def failing_queue(_self, _api_dict):
        raise failure

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", failing_queue)
    with pytest.raises((TimeoutError, QueueError)):
        asyncio.run(EmbeddedSession().run(record, bundle))
    attempt, events = _terminal_events(tmp_path, record)
    evidence = events[-1]["receipt"]["runtime_evidence"]
    expected = "unknown" if isinstance(failure, asyncio.TimeoutError) else "rejected"
    assert attempt["queue_acceptance"]["status"] == expected
    assert evidence["queue_acceptance"]["status"] == expected
    assert evidence["terminal"]["acceptance_known"] is (expected == "rejected")
    assert [event["event_type"] for event in events] == ["prepared", "discarded"]


def test_embedded_acceptance_witness_failure_discards_without_retry(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    record, bundle = _approved(_workflow())
    real_persist = session_module._persist_runtime_evidence
    calls = 0

    def fail_witness(run_dir, attempt_bundle, evidence):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("witness disk full")
        return real_persist(run_dir, attempt_bundle, evidence)

    monkeypatch.setattr(session_module, "_persist_runtime_evidence", fail_witness)
    with pytest.raises(QueueError, match="acceptance could not be recorded"):
        asyncio.run(EmbeddedSession().run(record, bundle))
    attempt, events = _terminal_events(tmp_path, record)
    assert len(fake_comfy.instances[0].queue_calls) == 1
    assert attempt["queue_acceptance"] == {"status": "unknown", "prompt_id": "prompt-1"}
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == attempt["queue_acceptance"]
    assert events[-1]["event_type"] == "discarded"


def test_embedded_cancel_during_queue_persists_unknown_superseded(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    record, bundle = _approved(_workflow())
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked_queue(*_args):
        entered.set()
        await release.wait()
        return {"prompt_id": "never-reached", "outputs": []}

    monkeypatch.setattr(session_module, "queue_embedded_prompt", blocked_queue)

    async def run_case() -> None:
        task = asyncio.create_task(EmbeddedSession().run(record, bundle))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_case())
    _attempt, events = _terminal_events(tmp_path, record)
    assert events[-1]["event_type"] == "superseded"
    evidence = events[-1]["receipt"]["runtime_evidence"]
    assert evidence["queue_acceptance"] == {"status": "unknown", "prompt_id": None}
    assert evidence["terminal"]["acceptance_known"] is False


@pytest.mark.parametrize("interruption", [asyncio.CancelledError(), KeyboardInterrupt()])
def test_embedded_interrupt_after_witness_is_durable_and_not_retried(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interruption: BaseException
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    record, bundle = _approved(_workflow())

    def interrupt_decode(*_args, **_kwargs):
        raise interruption

    monkeypatch.setattr(session_module, "_decode_terminal_result", interrupt_decode)
    with pytest.raises(type(interruption)):
        asyncio.run(EmbeddedSession().run(record, bundle))
    attempt, events = _terminal_events(tmp_path, record)
    assert len(fake_comfy.instances[0].queue_calls) == 1
    assert attempt["queue_acceptance"] == {"status": "accepted", "prompt_id": "prompt-1"}
    assert events[-1]["event_type"] == "superseded"
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"]["status"] == "accepted"


def test_embedded_metadata_failure_is_discarded_after_accepted_witness(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    record, bundle = _approved(_workflow())
    real_atomic = session_module.atomic_write_json

    def fail_metadata(path, value):
        if Path(path).name == "metadata.json":
            raise OSError("metadata disk full")
        return real_atomic(path, value)

    monkeypatch.setattr(session_module, "atomic_write_json", fail_metadata)
    with pytest.raises(QueueError, match="metadata could not be persisted"):
        asyncio.run(EmbeddedSession().run(record, bundle))
    _attempt, events = _terminal_events(tmp_path, record)
    assert len(fake_comfy.instances[0].queue_calls) == 1
    assert events[-1]["event_type"] == "discarded"
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"]["status"] == "accepted"


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


def test_auto_flush_unchanged_model_no_flush_changed_model_once(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    free_vram = 0.5
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: free_vram)

    async def run_cases() -> None:
        nonlocal free_vram
        session = EmbeddedSession(SessionConfig(auto_flush_vram_threshold_gb=2.0))
        try:
            await session.run(*_approved(_workflow("model-a.safetensors", seed=1)))
            await session.run(*_approved(_workflow("model-a.safetensors", seed=2)))
            assert fake_comfy.instances[0].clear_cache_calls == 0
            await session.run(*_approved(_workflow("model-b.safetensors", seed=2)))
            assert fake_comfy.instances[0].clear_cache_calls == 1
            free_vram = 10.0
            await session.run(*_approved(_workflow("model-c.safetensors", seed=2)))
            assert fake_comfy.instances[0].clear_cache_calls == 1
        finally:
            await session.stop()

    asyncio.run(run_cases())


def test_embedded_failed_run_does_not_promote_fingerprint_authority(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    free_vram = 10.0
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: free_vram)
    queue_calls = 0

    async def queue_with_failure(_self, _api_dict):
        nonlocal queue_calls
        queue_calls += 1
        if queue_calls == 2:
            raise RuntimeError("model-b failed")
        return {"prompt_id": f"prompt-{queue_calls}", "outputs": []}

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", queue_with_failure)

    async def run_cases() -> None:
        nonlocal free_vram
        session = EmbeddedSession()
        try:
            await session.run(*_approved(_workflow("model-a.safetensors")))
            first_fingerprint = session.last_fingerprint
            assert first_fingerprint is not None

            with pytest.raises(QueueError, match="model-b failed"):
                await session.run(*_approved(_workflow("model-b.safetensors")))
            assert session.last_fingerprint == first_fingerprint

            free_vram = 0.5
            await session.run(*_approved(_workflow("model-b.safetensors")))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert fake_comfy.instances[0].clear_cache_calls == 1


def test_embedded_output_collection_failure_does_not_promote_fingerprint_authority(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    free_vram = 10.0
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: free_vram)
    collect_calls = 0
    collect_outputs = session_module._collect_output_paths

    def collect_with_failure(value, *, output_directory=None):
        nonlocal collect_calls
        collect_calls += 1
        if collect_calls == 2:
            raise RuntimeError("output collection failed")
        return collect_outputs(value, output_directory=output_directory)

    monkeypatch.setattr(session_module, "_collect_output_paths", collect_with_failure)

    async def run_cases() -> None:
        nonlocal free_vram
        session = EmbeddedSession()
        try:
            await session.run(*_approved(_workflow("model-a.safetensors")))
            first_fingerprint = session.last_fingerprint
            assert first_fingerprint is not None

            with pytest.raises(RuntimeError, match="output collection failed"):
                await session.run(*_approved(_workflow("model-b.safetensors")))
            assert session.last_fingerprint == first_fingerprint

            free_vram = 0.5
            await session.run(*_approved(_workflow("model-b.safetensors")))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert fake_comfy.instances[0].clear_cache_calls == 1


def test_warm_policy_never_flushes_before_every_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_WARM", "never")

    async def run_cases() -> None:
        session = EmbeddedSession()
        try:
            await session.run(*_approved(_workflow("model-a.safetensors")))
            await session.run(*_approved(_workflow("model-a.safetensors")))
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
            await session.run(*_approved(_workflow("model-a.safetensors")))
            await session.run(*_approved(_workflow("model-b.safetensors")))
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
        task = asyncio.create_task(session.run(*_approved(_workflow())))
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
        task = asyncio.create_task(session.run(*_approved(_workflow())))
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
        task = asyncio.create_task(session.run(*_approved(workflow)))
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
        task = asyncio.create_task(session.run(*_approved(_workflow())))
        await started.wait()
        with pytest.raises(RuntimeError, match="session already has a run in flight"):
            await session.run(*_approved(_workflow(seed=2)))
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
        task = asyncio.create_task(session.run(*_approved(_workflow())))
        await started.wait()
        with pytest.raises(RuntimeError, match="reload_for_nodepack_change refused: run in flight"):
            await session.reload_for_nodepack_change(reason="test")
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())
