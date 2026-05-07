"""Tests for the runtime execution watchdog.

These tests drive the watchdog via its public ``feed()`` method (which is the
same code path the WebSocket loop uses to apply messages to state). That lets
us simulate every Comfy event sequence without standing up a real socket.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import types
from pathlib import Path

import pytest

import vibecomfy.runtime.watchdog as watchdog_module
from vibecomfy.runtime.watchdog import (
    OOM_CONSECUTIVE_SAMPLES,
    OOM_FREE_BYTES,
    OOM_NODE_ACTIVE_S,
    SLOW_NODE_ACTIVE_S,
    STALL_NO_EVENT_S,
    VramSample,
    Watchdog,
    write_report,
)


def _make_watchdog(api_dict: dict | None = None) -> Watchdog:
    return Watchdog(
        server_url="http://127.0.0.1:8188",
        client_id="test-client",
        api_dict=api_dict
        or {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "42": {"class_type": "KSamplerAdvanced", "inputs": {}},
            "99": {"class_type": "VAEDecode", "inputs": {}},
        },
        prompt_id=None,
    )


def _ws_ok(path: str = "/ws") -> str:
    return path


# -----------------------------------------------------------------------------
# State updates
# -----------------------------------------------------------------------------


def test_executing_message_sets_current_node_and_class_type() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "42", "prompt_id": "abc"}})

    assert wd.state.prompt_id == "abc"
    assert wd.state.current_node_id == "42"
    assert wd.state.current_node_class_type == "KSamplerAdvanced"
    assert wd.state.current_node_started_at is not None


def test_executing_null_signals_completion_and_records_executed() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "1", "prompt_id": "abc"}})
    wd.feed({"type": "executed", "data": {"node": "1", "prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "42", "prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": None, "prompt_id": "abc"}})

    assert wd.state.prompt_completed is True
    assert wd.state.current_node_id is None
    assert "1" in wd.state.executed_node_ids
    assert "42" in wd.state.executed_node_ids


def test_progress_message_updates_progress_and_appends_event() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "executing", "data": {"node": "42"}})
    wd.feed({"type": "progress", "data": {"node": "42", "value": 5, "max": 20}})
    wd.feed({"type": "progress", "data": {"node": "42", "value": 10, "max": 20}})

    assert wd.state.current_node_progress == {"value": 10, "max": 20}
    assert len(wd.recent_progress_events) == 2
    assert wd.recent_progress_events[-1].value == 10


def test_execution_cached_records_node_ids() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_cached", "data": {"nodes": ["1", "2"], "prompt_id": "abc"}})
    wd.feed({"type": "execution_cached", "data": {"nodes": ["1", "3"], "prompt_id": "abc"}})

    assert wd.state.cached_node_ids == ["1", "2", "3"]


def test_execution_error_captures_payload() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "executing", "data": {"node": "42"}})
    wd.feed(
        {
            "type": "execution_error",
            "data": {
                "prompt_id": "abc",
                "node_id": "42",
                "node_type": "KSamplerAdvanced",
                "exception_message": "CUDA out of memory",
                "exception_type": "RuntimeError",
            },
        }
    )

    assert wd.state.last_error is not None
    assert wd.state.last_error["exception_message"] == "CUDA out of memory"


# -----------------------------------------------------------------------------
# Diagnosis branches
# -----------------------------------------------------------------------------


def test_diagnose_completed_after_clean_run() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "1", "prompt_id": "abc"}})
    wd.feed({"type": "executed", "data": {"node": "1", "prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "42", "prompt_id": "abc"}})
    wd.feed({"type": "executed", "data": {"node": "42", "prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": None, "prompt_id": "abc"}})

    report = wd.dump()

    assert report.diagnosis == "completed"
    assert "executed" in report.diagnosis_reason


def test_diagnose_errored_when_execution_error_seen() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "executing", "data": {"node": "42"}})
    wd.feed(
        {
            "type": "execution_error",
            "data": {"node_id": "42", "exception_message": "boom"},
        }
    )

    report = wd.dump()

    assert report.diagnosis == "errored"
    assert "boom" in report.diagnosis_reason


def test_diagnose_slow_node_when_node_long_active_with_recent_events(monkeypatch: pytest.MonkeyPatch) -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "42"}})

    # Pretend the node started SLOW_NODE_ACTIVE_S + 60 seconds ago, but the
    # last event arrived 5 seconds ago (still within the recent window).
    base = wd._monotonic_started
    wd._state.current_node_started_at = base - (SLOW_NODE_ACTIVE_S + 60)
    wd._state.last_event_at = base - 5

    monkeypatch.setattr(watchdog_module, "_now", lambda: base)

    report = wd.dump()
    assert report.diagnosis == "slow_node"


def test_diagnose_stalled_runtime_when_no_events_recently(monkeypatch: pytest.MonkeyPatch) -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "42"}})

    base = wd._monotonic_started
    # Last event: long ago. /system_stats: still responsive.
    wd._state.last_event_at = base - (STALL_NO_EVENT_S + 30)
    wd._stats_responsive = True

    monkeypatch.setattr(watchdog_module, "_now", lambda: base)

    report = wd.dump()
    assert report.diagnosis == "stalled_runtime"


def test_diagnose_oom_ish_when_low_vram_and_node_active(monkeypatch: pytest.MonkeyPatch) -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    wd.feed({"type": "executing", "data": {"node": "42"}})

    base = wd._monotonic_started
    wd._state.current_node_started_at = base - (OOM_NODE_ACTIVE_S + 5)
    wd._state.last_event_at = base - 1  # recent events; would otherwise be slow_node

    # Append OOM_CONSECUTIVE_SAMPLES low samples.
    for i in range(OOM_CONSECUTIVE_SAMPLES + 1):
        wd._vram_samples.append(
            VramSample(timestamp=base - (i + 1), vram_free_bytes=OOM_FREE_BYTES // 2, vram_total_bytes=24 * 1024**3)
        )
    wd._stats_responsive = True

    monkeypatch.setattr(watchdog_module, "_now", lambda: base)

    report = wd.dump()
    assert report.diagnosis == "oom_ish"


def test_diagnose_missing_event_stream_when_never_connected_and_no_prompt() -> None:
    wd = _make_watchdog()
    # No feed() calls; watchdog never received anything.
    assert wd.state.connection_state == "never_connected"

    report = wd.dump()
    assert report.diagnosis == "missing_event_stream"


def test_diagnose_crashed_when_system_stats_stops_responding() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "abc"}})
    # Simulate having taken at least one /system_stats sample.
    wd._vram_samples.append(VramSample(timestamp=time.monotonic(), vram_free_bytes=1024, vram_total_bytes=24 * 1024**3))
    wd._stats_responsive = False

    report = wd.dump()
    assert report.diagnosis == "crashed"


def test_diagnose_completed_stop_reason_overrides_shutdown_stats_miss() -> None:
    wd = _make_watchdog()
    wd._stats_responsive = False
    wd._vram_samples.append(VramSample(timestamp=time.monotonic(), vram_free_bytes=None, vram_total_bytes=None))
    wd._state.stop_reason = "completed"

    report = wd.dump()

    assert report.diagnosis == "completed"
    assert "stop reason was 'completed'" in report.diagnosis_reason


# -----------------------------------------------------------------------------
# Header line + report writing
# -----------------------------------------------------------------------------


def test_header_line_includes_diagnosis_node_class_type_and_vram() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "p-1"}})
    wd.feed({"type": "executing", "data": {"node": "42"}})
    wd._vram_samples.append(
        VramSample(timestamp=time.monotonic(), vram_free_bytes=int(1.5 * 1024**3), vram_total_bytes=24 * 1024**3)
    )

    report = wd.dump()
    line = report.header_line()
    assert line.startswith("WATCHDOG ")
    assert "diagnosis=" in line
    assert "prompt_id=p-1" in line
    assert "last_node=42" in line
    assert "KSamplerAdvanced" in line
    assert "vram_free=1.5GB" in line


def test_write_report_writes_header_then_json(tmp_path: Path) -> None:
    wd = _make_watchdog()
    wd.feed({"type": "execution_start", "data": {"prompt_id": "p-2"}})
    wd.feed({"type": "executing", "data": {"node": "42"}})

    report = wd.dump()
    target = write_report(tmp_path / "run-1", report)

    text = Path(target).read_text(encoding="utf-8")
    first, _, body = text.partition("\n")
    assert first.startswith("WATCHDOG ")
    parsed = json.loads(body)
    assert parsed["diagnosis"] in {
        "in_progress",
        "slow_node",
        "stalled_runtime",
        "missing_event_stream",
        "completed",
        "errored",
    }
    assert parsed["state"]["prompt_id"] == "p-2"


# -----------------------------------------------------------------------------
# Disable switch + lifecycle
# -----------------------------------------------------------------------------


def test_watchdog_disabled_via_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_WATCHDOG", "0")
    wd = _make_watchdog()

    async def go() -> None:
        await wd.start()
        # When disabled, start() returns immediately and creates no tasks.
        assert wd._ws_task is None
        assert wd._poll_task is None
        await wd.stop(reason="completed")

    asyncio.run(go())


def test_watchdog_stop_is_idempotent_and_cancels_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub websockets so start() doesn't actually open a socket.
    class FakeWS:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(3600)  # wait until cancelled
            raise StopAsyncIteration

    fake_module = types.SimpleNamespace(connect=lambda *args, **kwargs: FakeWS())
    monkeypatch.setitem(sys.modules, "websockets", fake_module)

    # Stub httpx so the poll loop doesn't actually hit the network.
    class FakeResp:
        status_code = 200

        def json(self):
            return {"devices": [{"vram_total": 24 * 1024**3, "vram_free": 12 * 1024**3}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return FakeResp()

    import vibecomfy.runtime.watchdog as wm

    monkeypatch.setattr(wm.httpx, "AsyncClient", FakeAsyncClient)

    async def go() -> None:
        wd = _make_watchdog()
        await wd.start()
        # Let the loops actually schedule.
        await asyncio.sleep(0.1)
        await wd.stop(reason="completed")
        # Idempotent: calling stop again is fine.
        await wd.stop(reason="completed")

    asyncio.run(go())


def test_watchdog_dump_includes_recent_progress_events_and_vram_samples() -> None:
    wd = _make_watchdog()
    wd.feed({"type": "executing", "data": {"node": "42"}})
    for v in range(3):
        wd.feed({"type": "progress", "data": {"node": "42", "value": v, "max": 10}})
    wd._vram_samples.append(VramSample(timestamp=time.monotonic(), vram_free_bytes=2048, vram_total_bytes=4096))

    report = wd.dump()
    payload = report.to_json()

    assert len(payload["recent_progress_events"]) == 3
    assert payload["vram_samples"][-1]["vram_free_bytes"] == 2048


def test_extract_vram_handles_missing_devices() -> None:
    from vibecomfy.runtime.watchdog import _extract_vram

    assert _extract_vram({}) == (None, None)
    assert _extract_vram({"devices": []}) == (None, None)
    assert _extract_vram({"devices": [{"vram_total": 0, "vram_free": 0}]}) == (None, None)
    assert _extract_vram({"devices": [{"vram_total": 100, "vram_free": 25}]}) == (25, 100)


def test_extract_vram_picks_first_gpu_device() -> None:
    from vibecomfy.runtime.watchdog import _extract_vram

    payload = {
        "devices": [
            {"name": "cpu", "vram_total": 0},
            {"name": "cuda:0", "vram_total": 1000, "vram_free": 250},
            {"name": "cuda:1", "vram_total": 2000, "vram_free": 500},
        ]
    }
    assert _extract_vram(payload) == (250, 1000)


# -----------------------------------------------------------------------------
# Real-world LTX-style stall reproduction (mocked) and clean-run reproduction
# -----------------------------------------------------------------------------


def test_simulated_ltx_stall_yields_stalled_runtime_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock a long LTX community workflow that progresses then goes silent.

    Mirrors the failure pattern documented in
    docs/hiddenswitch_incompatibilities.md: progress events arrive for a while,
    then the runtime stops emitting events but the process is still up.
    """
    api_dict = {
        "10": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "20": {"class_type": "LTXVTextEncoderLoader", "inputs": {}},
        "30": {"class_type": "KSamplerAdvanced", "inputs": {}},
    }
    wd = Watchdog(
        server_url="http://127.0.0.1:8188",
        client_id="ltx-stall-test",
        api_dict=api_dict,
        prompt_id="ltx-1",
    )
    wd.feed({"type": "execution_start", "data": {"prompt_id": "ltx-1"}})
    wd.feed({"type": "executing", "data": {"node": "10"}})
    wd.feed({"type": "executed", "data": {"node": "10"}})
    wd.feed({"type": "executing", "data": {"node": "30"}})
    for i in range(5):
        wd.feed({"type": "progress", "data": {"node": "30", "value": i, "max": 40}})

    base = wd._monotonic_started
    wd._state.last_event_at = base - (STALL_NO_EVENT_S + 100)
    wd._state.current_node_started_at = base - 280
    wd._stats_responsive = True
    monkeypatch.setattr(watchdog_module, "_now", lambda: base)

    report = wd.dump()

    assert report.diagnosis == "stalled_runtime"
    assert report.state["current_node_id"] == "30"
    assert report.state["current_node_class_type"] == "KSamplerAdvanced"
    assert report.elapsed_in_current_node_seconds is not None
    assert report.elapsed_in_current_node_seconds >= 280
    # Recent progress events should be on the report.
    assert len(report.recent_progress_events) == 5


def test_simulated_clean_run_yields_completed_diagnosis() -> None:
    """Mock a clean run of a runtime-green workflow."""
    api_dict = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "2": {"class_type": "KSampler", "inputs": {}},
        "3": {"class_type": "VAEDecode", "inputs": {}},
        "4": {"class_type": "SaveImage", "inputs": {}},
    }
    wd = Watchdog(
        server_url="http://127.0.0.1:8188",
        client_id="clean-test",
        api_dict=api_dict,
        prompt_id="clean-1",
    )
    wd.feed({"type": "execution_start", "data": {"prompt_id": "clean-1"}})
    for nid in ("1", "2", "3", "4"):
        wd.feed({"type": "executing", "data": {"node": nid}})
        wd.feed({"type": "executed", "data": {"node": nid}})
    wd.feed({"type": "executing", "data": {"node": None}})

    report = wd.dump()

    assert report.diagnosis == "completed"
    assert report.state["executed_node_ids"] == ["1", "2", "3", "4"]
    assert report.state["current_node_id"] is None
