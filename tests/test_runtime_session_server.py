from __future__ import annotations

import asyncio
import json
import time
import signal
from pathlib import Path
from unittest.mock import patch

import pytest
from vibecomfy.errors import QueueError, RuntimeNodeError

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import EmbeddedSession, ServerSession, SessionConfig
from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
from vibecomfy.porting.object_info import ObjectInfoLookupResult
from vibecomfy.schema import NodeSchema
from vibecomfy.workflow_bundle import load_bundle
from tests._runtime_session_helpers import (
    FakeAsyncClient,
    FakeProcess,
    FakeResponse,
    _workflow,
    fake_server,  # noqa: F401 -- pytest fixture imported for use in tests
)


def _terminal_events(tmp_path: Path, record):
    run_dir = next(path for path in (tmp_path / "out/runs").iterdir() if path.is_dir())
    attempt = json.loads((run_dir / "attempt.json").read_text(encoding="utf-8"))
    lifecycle = run_dir / "transactions" / record.api_digest / "lifecycle_events.jsonl"
    events = [json.loads(line) for line in lifecycle.read_text(encoding="utf-8").splitlines()]
    return attempt, events


def _assert_exact_runtime_record(evidence: dict, record) -> None:
    approved = evidence["approved_projection"]
    assert set(approved) == {
        "revision_id", "selected_variant", "input_binding",
        "api_projection", "ui_projection", "api_digest",
    }
    assert approved == record.to_dict()
    assert "approval_record" not in evidence
    assert "approved_record" not in evidence


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


def test_server_session_start_translates_config_to_cli_args(fake_server) -> None:
    async def run_start() -> None:
        session = ServerSession(
            SessionConfig(
                vram_policy="high",
                reserve_vram_gb=2.0,
                cache_policy="lru:3",
                disable_smart_memory=True,
                port=8200,
            )
        )
        await session.start()
        await session.stop()

    asyncio.run(run_start())

    argv = fake_server[0][0]
    assert "--highvram" in argv
    assert argv[argv.index("--reserve-vram") + 1] == "2.0"
    assert argv[argv.index("--cache-lru") + 1] == "3"
    assert "--disable-smart-memory" in argv
    assert argv[argv.index("--port") + 1] == "8200"


def test_server_session_two_runs_share_one_subprocess(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_twice() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(*_approved(_workflow()))
            await session.run(*_approved(_workflow()))
        finally:
            await session.stop()

    asyncio.run(run_twice())

    assert len(fake_server) == 1
    assert [post[0] for post in FakeAsyncClient.posts].count("http://127.0.0.1:8200/prompt") == 2


def test_embedded_and_server_sessions_keep_fingerprint_state_separate() -> None:
    embedded = EmbeddedSession()
    server = ServerSession(SessionConfig(port=8200))
    assert embedded.last_fingerprint is None
    assert server.last_fingerprint is None

    embedded.last_fingerprint = (("embedded", "model", "a"),)
    assert server.last_fingerprint is None

    server.last_fingerprint = (("server", "model", "b"),)

    assert embedded.last_fingerprint != server.last_fingerprint


def test_server_failed_run_does_not_promote_fingerprint_authority(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: 10.0)
    session = ServerSession(SessionConfig(port=8200))

    async def run_cases() -> None:
        try:
            await session.run(*_approved(_workflow("model-a.safetensors")))
            first_fingerprint = session.last_fingerprint
            assert first_fingerprint is not None

            FakeAsyncClient.history_status = {
                "status_str": "error",
                "completed": True,
                "messages": [["execution_error", {"exception_message": "model-b failed"}]],
            }
            with pytest.raises(RuntimeNodeError, match="model-b failed"):
                await session.run(*_approved(_workflow("model-b.safetensors")))
            assert session.last_fingerprint == first_fingerprint

            FakeAsyncClient.history_status = {
                "status_str": "success",
                "completed": True,
                "messages": [],
            }
            monkeypatch.setattr(session_module, "_free_vram_gb", lambda: 0.5)
            await session.run(*_approved(_workflow("model-b.safetensors")))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert sum(url.endswith("/api/free") for url, _payload in FakeAsyncClient.posts) == 1



def test_server_session_concurrent_runs_get_exclusive_roots(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.time, "time", lambda: 1234567890.0)
    original_post = FakeAsyncClient.post
    prompt_count = 0
    release = asyncio.Event()

    async def synchronized_post(self, url: str, json: dict | None = None):
        nonlocal prompt_count
        if url.endswith("/prompt"):
            prompt_count += 1
            if prompt_count == 2:
                release.set()
            await release.wait()
        return await original_post(self, url, json)

    monkeypatch.setattr(FakeAsyncClient, "post", synchronized_post)

    async def run_both():
        sessions = [ServerSession(SessionConfig(port=8200)), ServerSession(SessionConfig(port=8200))]
        try:
            return await asyncio.gather(*(session.run(*_approved(_workflow())) for session in sessions))
        finally:
            await asyncio.gather(*(session.stop() for session in sessions))

    results = asyncio.run(run_both())

    assert len({result.run_id for result in results}) == 2
    assert len({Path(result.metadata_path).parent for result in results}) == 2
    assert all(Path(result.metadata_path).is_file() for result in results)


def test_server_session_success_then_failure_same_second_keeps_roots_isolated(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module.time, "time", lambda: 1234567890.0)
    session = ServerSession(SessionConfig(port=8200))

    async def run_case():
        try:
            first = await session.run(*_approved(_workflow()))
            FakeAsyncClient.history_status = {
                "status_str": "error",
                "completed": True,
                "messages": [["execution_error", {"exception_message": "second run failed"}]],
            }
            with pytest.raises(RuntimeNodeError, match="second run failed"):
                await session.run(*_approved(_workflow()))
            return first
        finally:
            await session.stop()

    first = asyncio.run(run_case())
    run_dirs = [path for path in (tmp_path / "out/runs").iterdir() if path.is_dir()]
    metadata_paths = list((tmp_path / "out/runs").glob("*/metadata.json"))

    assert len(run_dirs) == 2
    assert Path(first.metadata_path).is_file()
    assert metadata_paths == [Path(first.metadata_path).resolve()]


def test_server_session_queue_failure_includes_id_map(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    from tests._runtime_session_helpers import FakeResponse

    async def post(self, url: str, json: dict | None = None):
        if url.endswith("/prompt"):
            raise RuntimeError("queue refused prompt")
        return FakeResponse(200, {})

    monkeypatch.setattr(FakeAsyncClient, "post", post)

    workflow = _workflow()
    workflow.metadata["id_map"] = {"sampler": "2"}
    workflow.nodes["2"].metadata["source_id"] = "7"

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(RuntimeError, match="Workflow queue failed: queue refused prompt") as exc_info:
                await session.run(*_approved(workflow))
            message = str(exc_info.value)
            assert "id_map=" in message
            assert "'sampler': '2'" in message
            assert "'7': '2'" in message
        finally:
            await session.stop()

    asyncio.run(run_case())


def test_server_session_waits_for_history_and_records_outputs(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "server-output.png").write_bytes(b"png")

    async def run_case():
        session = ServerSession(SessionConfig(port=8200, extra={"output_directory": str(output_dir)}))
        try:
            return await session.run(*_approved(_workflow()))
        finally:
            await session.stop()

    result = asyncio.run(run_case())
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))

    assert result.outputs == [str(output_dir / "server-output.png")]
    assert metadata["outputs"] == result.outputs
    assert metadata["prompt_id"] == "prompt-1"


    assert any(url.endswith("/history/prompt-1") for url in FakeAsyncClient.gets)


def test_server_managed_success_adapter_provenance_is_identical(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())

    async def run_case():
        session = ServerSession(SessionConfig(port=8200))
        try:
            return await session.run(record, bundle)
        finally:
            await session.stop()

    result = asyncio.run(run_case())
    run_dir = Path(result.metadata_path).parent
    attempt = json.loads((run_dir / "attempt.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    lifecycle = run_dir / "transactions" / record.api_digest / "lifecycle_events.jsonl"
    events = [json.loads(line) for line in lifecycle.read_text(encoding="utf-8").splitlines()]
    adapters = [
        attempt["runtime_evidence"]["adapter"],
        metadata["runtime_evidence"]["adapter"],
        events[-1]["receipt"]["runtime_evidence"]["adapter"],
    ]
    assert all(adapter == adapters[0] for adapter in adapters)
    assert adapters[0] == {"kind": "managed", "backend": "api", "endpoint": "http://127.0.0.1:8200"}
    _assert_exact_runtime_record(attempt["runtime_evidence"], record)
    _assert_exact_runtime_record(metadata["runtime_evidence"], record)
    _assert_exact_runtime_record(events[-1]["receipt"]["runtime_evidence"], record)


def test_server_history_active_states_continue_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_id = "prompt-active"

    class SequenceClient:
        calls = 0

        def __init__(self, _url: str) -> None:
            pass

        async def history(self, requested_id: str) -> dict:
            assert requested_id == prompt_id
            SequenceClient.calls += 1
            status = ("pending", "queued", "running")[SequenceClient.calls - 1] if SequenceClient.calls <= 3 else "success"
            return {
                prompt_id: {
                    "outputs": {},
                    "status": {
                        "status_str": status,
                        "completed": status == "success",
                        "messages": [],
                    },
                }
            }

    monkeypatch.setattr(session_module, "ComfyClient", SequenceClient)
    monkeypatch.setenv("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC", "0")

    history = asyncio.run(
        session_module._wait_for_server_history(
            "http://runtime.test",
            prompt_id,
            config=SessionConfig(extra={"prompt_timeout_sec": 1}),
        )
    )

    assert SequenceClient.calls == 4
    assert session_module._outputs_from_server_history(history, prompt_id) == {}


def test_message_only_execution_error_preserves_bounded_causal_tail() -> None:
    prompt_id = "p" * 10_000
    cause = "wrapper-" * 100 + "ROOT_CAUSE_AT_END"
    with pytest.raises(RuntimeNodeError) as exc_info:
        session_module._decode_terminal_result(
            {
                "outputs": {},
                "status": {
                    "completed": False,
                    "messages": [["execution_error", {"exception_message": cause}]],
                },
            },
            prompt_id=prompt_id,
            status_required=True,
        )

    message = str(exc_info.value)
    assert "ROOT_CAUSE_AT_END" in message
    assert len(message) < 2200
    assert "p" * 1000 not in message


def test_contradictory_success_and_execution_error_fails() -> None:
    with pytest.raises(RuntimeNodeError, match="contradiction-cause"):
        session_module._decode_terminal_result(
            {
                "outputs": {},
                "status": {
                    "status_str": "success",
                    "completed": True,
                    "messages": [["execution_error", {"exception_message": "contradiction-cause"}]],
                },
            },
            prompt_id="prompt-contradiction",
            status_required=True,
        )


def test_history_request_timeout_bounds_in_flight_http(monkeypatch: pytest.MonkeyPatch) -> None:
    cancelled = False

    class HangingClient:
        def __init__(self, _url: str) -> None:
            pass

        async def history(self, _prompt_id: str) -> dict:
            nonlocal cancelled
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return {}

    monkeypatch.setattr(session_module, "ComfyClient", HangingClient)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(
            session_module._wait_for_server_history(
                "http://runtime.test",
                "prompt-timeout",
                config=SessionConfig(extra={"prompt_timeout_sec": 0.02}),
            )
        )
    assert cancelled
    assert time.monotonic() - started < 0.5


@pytest.mark.parametrize("completed", [False, True])
def test_server_session_terminal_error_fails_before_metadata(
    fake_server,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    completed: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    FakeAsyncClient.history_outputs = {}
    FakeAsyncClient.history_status = {
        "status_str": "error",
        "completed": completed,
        "messages": [
            [
                "execution_error",
                {
                    "node_id": "7",
                    "exception_type": "ValueError",
                    "exception_message": "bad latent shape",
                },
            ]
        ],
    }

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(RuntimeNodeError) as exc_info:
                await session.run(*_approved(_workflow()))
            message = str(exc_info.value)
            assert "prompt-1" in message
            assert "execution_error" in message
            assert "bad latent shape" in message
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert not list(tmp_path.glob("out/runs/*/metadata.json"))


def test_server_session_does_not_finalize_watchdog_completed_before_history(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    FakeAsyncClient.history_outputs = {}
    FakeAsyncClient.history_status = {
        "status_str": "success",
        "completed": True,
        "messages": [["execution_error", {"exception_message": "history-error"}]],
    }
    reasons: list[str] = []

    async def fake_start_watchdog(**_kwargs):
        return object()

    async def fake_finalize_watchdog(_watchdog, *, run_dir, reason):
        reasons.append(reason)

    monkeypatch.setattr(session_module, "_start_watchdog", fake_start_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", fake_finalize_watchdog)

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(RuntimeNodeError, match="history-error"):
                await session.run(*_approved(_workflow()))
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert reasons == ["errored"]


def test_server_queue_http_200_without_prompt_id_fails_without_history_retry(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def post(self, url: str, json: dict | None = None):
        FakeAsyncClient.posts.append((url, json))
        if url.endswith("/prompt"):
            return FakeResponse(200, {})
        return FakeResponse(200, {})

    monkeypatch.setattr(FakeAsyncClient, "post", post)
    record, bundle = _approved(_workflow())

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(QueueError, match="did not include a prompt_id"):
                await session.run(record, bundle)
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert not any("/history/" in url for url in FakeAsyncClient.gets)
    attempt, events = _terminal_events(tmp_path, record)
    assert len([url for url, _payload in FakeAsyncClient.posts if url.endswith("/prompt")]) == 1
    assert attempt["queue_acceptance"] == {"status": "unknown", "prompt_id": None}
    evidence = events[-1]["receipt"]["runtime_evidence"]
    assert evidence["queue_acceptance"] == attempt["queue_acceptance"]
    assert evidence["terminal"]["acceptance_known"] is False
    assert events[-1]["event_type"] == "discarded"
    assert events[-1]["generation"] == events[0]["generation"]
    _assert_exact_runtime_record(attempt["runtime_evidence"], record)
    _assert_exact_runtime_record(evidence, record)


def test_server_acceptance_witness_write_failure_is_unknown_discarded(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())
    real_persist = session_module._persist_runtime_evidence
    calls = 0

    def fail_witness(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("witness disk full")
        return real_persist(*args, **kwargs)

    monkeypatch.setattr(session_module, "_persist_runtime_evidence", fail_witness)

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(QueueError, match="acceptance could not be recorded"):
                await session.run(record, bundle)
        finally:
            await session.stop()

    asyncio.run(run_case())
    attempt, events = _terminal_events(tmp_path, record)
    assert len([url for url, _payload in FakeAsyncClient.posts if url.endswith("/prompt")]) == 1
    assert not any("/history/" in url for url in FakeAsyncClient.gets)
    assert attempt["queue_acceptance"] == {"status": "unknown", "prompt_id": "prompt-1"}
    assert events[-1]["event_type"] == "discarded"
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == attempt["queue_acceptance"]


@pytest.mark.parametrize("failure_kind", ["output", "metadata", "journal", "completed_attempt"])
def test_server_post_witness_failure_matrix(
    failure_kind: str, fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())
    if failure_kind == "output":
        monkeypatch.setattr(
            session_module, "_collect_output_paths",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("output collection failed")),
        )
    elif failure_kind == "metadata":
        real_atomic = session_module.atomic_write_json

        def fail_metadata(path, value):
            if Path(path).name == "metadata.json":
                raise OSError("metadata disk full")
            return real_atomic(path, value)

        monkeypatch.setattr(session_module, "atomic_write_json", fail_metadata)
    elif failure_kind == "journal":
        real_journal = session_module._journal_terminal
        calls = 0

        def fail_finalized(*args, **kwargs):
            nonlocal calls
            calls += 1
            if kwargs.get("event_type") == "finalized":
                raise OSError("finalized journal disk full")
            return real_journal(*args, **kwargs)

        monkeypatch.setattr(session_module, "_journal_terminal", fail_finalized)
    else:
        real_persist = session_module._persist_runtime_evidence
        calls = 0

        def fail_completed(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("completion attempt disk full")
            return real_persist(*args, **kwargs)

        monkeypatch.setattr(session_module, "_persist_runtime_evidence", fail_completed)

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            expected = QueueError if failure_kind in {"metadata", "journal", "completed_attempt"} else OSError
            with pytest.raises(expected) as exc_info:
                await session.run(record, bundle)
            if failure_kind == "completed_attempt":
                assert isinstance(exc_info.value.__cause__, OSError)
        finally:
            await session.stop()

    asyncio.run(run_case())
    attempt, events = _terminal_events(tmp_path, record)
    assert len([url for url, _payload in FakeAsyncClient.posts if url.endswith("/prompt")]) == 1
    assert attempt["queue_acceptance"] == {"status": "accepted", "prompt_id": "prompt-1"}
    assert events[-1]["event_type"] == "discarded"
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == attempt["queue_acceptance"]
    if failure_kind != "journal":
        assert not list(tmp_path.glob("out/runs/*/metadata.json"))
    _assert_exact_runtime_record(attempt["runtime_evidence"], record)
    _assert_exact_runtime_record(events[-1]["receipt"]["runtime_evidence"], record)


def test_server_cancel_during_queue_persists_unknown_superseded(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked_queue(*_args, **_kwargs):
        entered.set()
        await release.wait()
        return types.SimpleNamespace(queued={"prompt_id": "never"})

    import types
    monkeypatch.setattr(session_module, "queue_server_prompt", blocked_queue)

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        task = asyncio.create_task(session.run(record, bundle))
        await entered.wait()
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await session.stop()

    asyncio.run(run_case())
    attempt, events = _terminal_events(tmp_path, record)
    assert events[-1]["event_type"] == "superseded"
    assert attempt["queue_acceptance"] == {"status": "unknown", "prompt_id": None}
    assert events[-1]["receipt"]["runtime_evidence"]["terminal"]["acceptance_known"] is False


@pytest.mark.parametrize("interruption", [asyncio.CancelledError("cancelled after accept"), KeyboardInterrupt("interrupt after accept")])
def test_server_interrupt_after_acceptance_persists_accepted_superseded(
    interruption: BaseException, fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())

    async def interrupted_history(*_args, **_kwargs):
        raise interruption

    monkeypatch.setattr(session_module, "_wait_for_server_history", interrupted_history)

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(type(interruption)):
                await session.run(record, bundle)
        finally:
            await session.stop()

    asyncio.run(run_case())
    attempt, events = _terminal_events(tmp_path, record)
    assert len([url for url, _payload in FakeAsyncClient.posts if url.endswith("/prompt")]) == 1
    assert attempt["queue_acceptance"] == {"status": "accepted", "prompt_id": "prompt-1"}
    assert events[-1]["event_type"] == "superseded"
    assert events[-1]["receipt"]["runtime_evidence"]["queue_acceptance"] == attempt["queue_acceptance"]


@pytest.mark.parametrize("failure", [asyncio.TimeoutError("queue timeout"), QueueError("queue rejected")])
def test_server_queue_failure_classifies_timeout_and_rejection(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())

    async def post(self, url: str, json: dict | None = None):
        FakeAsyncClient.posts.append((url, json))
        if url.endswith("/prompt"):
            raise failure
        return FakeResponse(200, {})

    monkeypatch.setattr(FakeAsyncClient, "post", post)
    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises((TimeoutError, QueueError)):
                await session.run(record, bundle)
        finally:
            await session.stop()

    asyncio.run(run_case())
    attempt, events = _terminal_events(tmp_path, record)
    expected = "unknown" if isinstance(failure, asyncio.TimeoutError) else "rejected"
    assert attempt["queue_acceptance"]["status"] == expected
    evidence = events[-1]["receipt"]["runtime_evidence"]
    assert evidence["queue_acceptance"]["status"] == expected
    assert evidence["terminal"]["acceptance_known"] is (expected == "rejected")
    assert [event["event_type"] for event in events] == ["prepared", "discarded"]
    assert len([url for url, _payload in FakeAsyncClient.posts if url.endswith("/prompt")]) == 1


def test_server_model_preflight_is_recorded_after_lifecycle_begin(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())
    monkeypatch.setattr(
        session_module, "apply_model_preflight", lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("managed preflight failed")
        )
    )
    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(RuntimeError, match="managed preflight failed"):
                await session.run(record, bundle, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())
    attempt, events = _terminal_events(tmp_path, record)
    assert attempt["queue_acceptance"] == {"status": "not_attempted", "prompt_id": None}
    assert events[-1]["event_type"] == "discarded"
    assert events[-1]["receipt"]["runtime_evidence"]["terminal"]["phase"] == "preflight"
    assert not any(url.endswith("/prompt") for url, _payload in FakeAsyncClient.posts)


def test_terminal_error_evidence_is_bounded() -> None:
    with pytest.raises(RuntimeNodeError) as exc_info:
        session_module._decode_terminal_result(
            {
                "outputs": {},
                "status": {
                    "status_str": "error",
                    "completed": False,
                    "messages": [["execution_error", {"exception_message": "x" * 10_000}]],
                },
            },
            prompt_id="prompt-large-error",
            status_required=True,
        )

    message = str(exc_info.value)
    assert "prompt-large-error" in message
    assert "execution_error" in message
    assert len(message) < 2200


def test_server_history_pending_then_explicit_empty_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "prompt-pending"
    empty_outputs: dict[str, object] = {}

    class SequenceClient:
        calls = 0

        def __init__(self, _url: str) -> None:
            pass

        async def history(self, requested_id: str) -> dict:
            assert requested_id == prompt_id
            SequenceClient.calls += 1
            if SequenceClient.calls == 1:
                return {}
            return {
                prompt_id: {
                    "outputs": empty_outputs,
                    "status": {
                        "status_str": "success",
                        "completed": True,
                        "messages": [],
                    },
                }
            }

    monkeypatch.setattr(session_module, "ComfyClient", SequenceClient)
    monkeypatch.setenv("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC", "0")

    history = asyncio.run(
        session_module._wait_for_server_history(
            "http://runtime.test",
            prompt_id,
            config=SessionConfig(extra={"prompt_timeout_sec": 1}),
        )
    )

    assert SequenceClient.calls == 2
    assert session_module._outputs_from_server_history(history, prompt_id) is empty_outputs


def test_server_history_rejects_status_bearing_list_outputs() -> None:
    with pytest.raises(QueueError, match="outputs must be an object"):
        session_module._outputs_from_server_history(
            {
                "prompt-list": {
                    "outputs": [],
                    "status": {
                        "status_str": "success",
                        "completed": True,
                        "messages": [],
                    },
                }
            },
            "prompt-list",
        )


@pytest.mark.parametrize(
    ("history", "message"),
    [
        (["not", "an", "object"], "history response must be an object"),
        ({"different-prompt": {}}, "omitted the requested prompt"),
        ({"prompt-malformed": []}, "missing status"),
        (
            {
                "prompt-malformed": {
                    "outputs": {},
                    "status": {
                        "status_str": "success",
                        "completed": False,
                        "messages": [],
                    },
                }
            },
            "completed=true",
        ),
        (
            {
                "prompt-malformed": {
                    "outputs": None,
                    "status": {
                        "status_str": "success",
                        "completed": True,
                        "messages": [],
                    },
                }
            },
            "outputs must be an object",
        ),
    ],
)
def test_server_history_malformed_terminal_data_fails_immediately(
    monkeypatch: pytest.MonkeyPatch,
    history: object,
    message: str,
) -> None:
    class MalformedClient:
        def __init__(self, _url: str) -> None:
            pass

        async def history(self, _prompt_id: str) -> object:
            return history

    monkeypatch.setattr(session_module, "ComfyClient", MalformedClient)

    with pytest.raises(QueueError, match=message):
        asyncio.run(
            session_module._wait_for_server_history(
                "http://runtime.test",
                "prompt-malformed",
                config=SessionConfig(extra={"prompt_timeout_sec": 1}),
            )
        )


def test_server_history_requires_queue_prompt_id() -> None:
    with pytest.raises(QueueError, match="did not include a prompt_id"):
        asyncio.run(
            session_module._wait_for_server_history(
                "http://runtime.test",
                None,
                config=SessionConfig(),
            )
        )


def test_server_session_flush_posts_api_free_payload(fake_server) -> None:
    async def run_flush() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.start()
            await session.flush()
        finally:
            await session.stop()

    asyncio.run(run_flush())

    assert (
        "http://127.0.0.1:8200/api/free",
        {"unload_models": True, "free_memory": True},
    ) in FakeAsyncClient.posts


def test_server_session_reconfigure_noop_or_restart(fake_server) -> None:
    async def run_reconfigure() -> tuple[bool, bool]:
        config = SessionConfig(port=8200, cache_policy="smart")
        session = ServerSession(config)
        try:
            await session.start()
            same = await session.reconfigure(SessionConfig(port=8200, cache_policy="smart"))
            changed = await session.reconfigure(SessionConfig(port=8201, cache_policy="none"))
            return same, changed
        finally:
            await session.stop()

    same, changed = asyncio.run(run_reconfigure())

    assert same is False
    assert changed is True
    assert len(fake_server) == 2
    assert signal.SIGTERM in fake_server[0][1].signals


def test_server_session_stop_sigterms_then_falls_back_to_kill(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess()
    process.wait_blocks = True
    session = ServerSession()
    session.process = process

    async def fake_wait_for(awaitable, *, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        assert timeout == 15
        raise asyncio.TimeoutError

    async def fake_wait_after_kill() -> int:
        process.returncode = -9
        return -9

    monkeypatch.setattr(session_module.asyncio, "wait_for", fake_wait_for)
    process.wait = fake_wait_after_kill  # type: ignore[method-assign]

    asyncio.run(session.stop())

    assert process.signals == [signal.SIGTERM]
    assert process.killed is True


def test_server_reload_calls_stop_then_start() -> None:
    async def run_case() -> None:
        session = ServerSession()
        calls: list[str] = []

        async def fake_stop(wait_for_inflight: bool = True) -> None:
            calls.append("stop")

        async def fake_start() -> None:
            calls.append("start")

        session.stop = fake_stop  # type: ignore[method-assign]
        session.start = fake_start  # type: ignore[method-assign]
        await session.reload_for_nodepack_change(reason="test")
        assert calls == ["stop", "start"]

    asyncio.run(run_case())


def test_server_reload_refuses_inflight_and_has_no_external_mode_api() -> None:
    async def run_case() -> None:
        session = ServerSession()
        task = asyncio.create_task(asyncio.sleep(3600))
        session._inflight_run = task
        try:
            with pytest.raises(RuntimeError, match="reload_for_nodepack_change refused: run in flight"):
                await session.reload_for_nodepack_change(reason="test")
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run_case())
    assert not hasattr(ServerSession, "attach")
    assert not hasattr(session_module, "ExternalServerRestartRequired")
