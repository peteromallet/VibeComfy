from __future__ import annotations

import asyncio
import json
import time
import signal
from pathlib import Path

import pytest
from vibecomfy.errors import QueueError, RuntimeNodeError

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import EmbeddedSession, ServerSession, SessionConfig
from tests._runtime_session_helpers import (
    FakeAsyncClient,
    FakeProcess,
    FakeResponse,
    _workflow,
    fake_server,  # noqa: F401 -- pytest fixture imported for use in tests
)


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
            await session.run(_workflow())
            await session.run(_workflow())
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
            await session.run(_workflow("model-a.safetensors"))
            first_fingerprint = session.last_fingerprint
            assert first_fingerprint is not None

            FakeAsyncClient.history_status = {
                "status_str": "error",
                "completed": True,
                "messages": [["execution_error", {"exception_message": "model-b failed"}]],
            }
            with pytest.raises(RuntimeNodeError, match="model-b failed"):
                await session.run(_workflow("model-b.safetensors"))
            assert session.last_fingerprint == first_fingerprint

            FakeAsyncClient.history_status = {
                "status_str": "success",
                "completed": True,
                "messages": [],
            }
            monkeypatch.setattr(session_module, "_free_vram_gb", lambda: 0.5)
            await session.run(_workflow("model-b.safetensors"))
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
            return await asyncio.gather(*(session.run(_workflow()) for session in sessions))
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
            first = await session.run(_workflow())
            FakeAsyncClient.history_status = {
                "status_str": "error",
                "completed": True,
                "messages": [["execution_error", {"exception_message": "second run failed"}]],
            }
            with pytest.raises(RuntimeNodeError, match="second run failed"):
                await session.run(_workflow())
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
                await session.run(workflow)
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
            return await session.run(_workflow())
        finally:
            await session.stop()

    result = asyncio.run(run_case())
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))

    assert result.outputs == [str(output_dir / "server-output.png")]
    assert metadata["outputs"] == result.outputs
    assert metadata["prompt_id"] == "prompt-1"


    assert any(url.endswith("/history/prompt-1") for url in FakeAsyncClient.gets)


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
                await session.run(_workflow())
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
                await session.run(_workflow())
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert reasons == ["errored"]


def test_server_queue_http_200_without_prompt_id_fails_without_history_retry(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def post(self, url: str, json: dict | None = None):
        if url.endswith("/prompt"):
            return FakeResponse(200, {})
        return FakeResponse(200, {})

    monkeypatch.setattr(FakeAsyncClient, "post", post)

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(QueueError, match="did not include a prompt_id"):
                await session.run(_workflow())
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert not any("/history/" in url for url in FakeAsyncClient.gets)


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
