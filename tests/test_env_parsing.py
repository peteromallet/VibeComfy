from __future__ import annotations

import asyncio
from decimal import Decimal
import importlib
from fractions import Fraction

import pytest

from vibecomfy.errors import RuntimeConfigurationError
from vibecomfy.comfy_nodes.agent import provider as agent_provider
from vibecomfy.comfy_nodes.agent import runtime as agent_runtime
from vibecomfy.porting.emit import ui as emit_ui_module
from vibecomfy.porting.emit.ui import _chunked_emit_settings, _positive_int_value
import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import _duration_seconds, _wait_for_server_history


CHUNKED_ENV_DEFAULTS = {
    "VIBECOMFY_CHUNKED_EMIT_THRESHOLD": "400",
    "VIBECOMFY_CHUNKED_EMIT_CHUNK_SIZE": "128",
    "VIBECOMFY_CHUNKED_EMIT_WARN_EVERY": "50",
}


def test_chunked_emit_settings_keep_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CHUNKED_ENV_DEFAULTS:
        monkeypatch.delenv(name, raising=False)

    assert _chunked_emit_settings() == (400, 128, 50)


def test_chunked_emit_settings_accept_valid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_CHUNKED_EMIT_THRESHOLD", "401")
    monkeypatch.setenv("VIBECOMFY_CHUNKED_EMIT_CHUNK_SIZE", "17")
    monkeypatch.setenv("VIBECOMFY_CHUNKED_EMIT_WARN_EVERY", "3")

    assert _chunked_emit_settings() == (401, 17, 3)
    assert _positive_int_value(7, name="threshold") == 7
    assert _positive_int_value("8", name="threshold") == 8
    assert _positive_int_value(10**10000, name="threshold") == 10**10000


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VIBECOMFY_CHUNKED_EMIT_THRESHOLD", "oops"),
        ("VIBECOMFY_CHUNKED_EMIT_CHUNK_SIZE", "0"),
        ("VIBECOMFY_CHUNKED_EMIT_WARN_EVERY", "-1"),
    ],
)
def test_chunked_emit_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeConfigurationError, match=f"Invalid {name} value") as exc_info:
        _chunked_emit_settings()

    assert name in str(exc_info.value.next_action)
    assert "positive integer" in str(exc_info.value)


class _PathologicalValue:
    def __repr__(self) -> str:
        raise AssertionError("repr must not be called")

    def __str__(self) -> str:
        raise AssertionError("str must not be called")


@pytest.mark.parametrize("raw", [True, False])
def test_chunked_integer_parser_rejects_booleans(raw: object) -> None:
    with pytest.raises(RuntimeConfigurationError, match="positive integer") as exc_info:
        _positive_int_value(raw, name="VIBECOMFY_CHUNKED_EMIT_THRESHOLD")

    assert "VIBECOMFY_CHUNKED_EMIT_THRESHOLD" in str(exc_info.value.next_action)


def test_chunked_integer_parser_does_not_call_pathological_repr() -> None:
    with pytest.raises(RuntimeConfigurationError, match="positive integer") as exc_info:
        _positive_int_value(_PathologicalValue(), name="VIBECOMFY_CHUNKED_EMIT_THRESHOLD")

    assert "_PathologicalValue" in str(exc_info.value)


@pytest.mark.parametrize(
    "raw",
    [
        1.9,
        2.1,
        -1.5,
        1.0,
        Decimal("2"),
        Fraction(2, 1),
    ],
)
def test_chunked_integer_parser_rejects_non_integral_programmatic_values(raw: object) -> None:
    with pytest.raises(RuntimeConfigurationError, match="positive integer"):
        _positive_int_value(raw, name="VIBECOMFY_CHUNKED_EMIT_THRESHOLD")


def test_malformed_chunked_env_does_not_break_module_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_CHUNKED_EMIT_THRESHOLD", "oops")

    importlib.reload(emit_ui_module)


def test_runtime_duration_defaults_and_accepts_valid_values() -> None:
    assert _duration_seconds(None, name="duration", default=12) == 12
    assert _duration_seconds("", name="duration", default=12) == 12
    assert _duration_seconds("2.5", name="duration", default=12) == 2.5
    assert _duration_seconds("0", name="poll", default=1, allow_zero=True) == 0


@pytest.mark.parametrize(
    "value",
    ["oops", "0", "-1", True, False, pytest.param(10**10000, id="huge-int")],
)
def test_runtime_duration_rejects_invalid_values(value: object) -> None:
    with pytest.raises(RuntimeConfigurationError, match="positive finite number") as exc_info:
        _duration_seconds(value, name="duration", default=12)

    assert "Fix the runtime configuration and retry" in str(exc_info.value.next_action)


def test_runtime_duration_error_does_not_call_pathological_repr() -> None:
    with pytest.raises(RuntimeConfigurationError, match="finite number") as exc_info:
        _duration_seconds(_PathologicalValue(), name="duration", default=12)

    assert "_PathologicalValue" in str(exc_info.value)


@pytest.mark.parametrize("value", ["oops", "-1", "nan", "inf", "-inf"])
def test_zero_allowed_poll_duration_rejects_invalid_values(value: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match="non-negative finite number"):
        _duration_seconds(value, name="poll", default=1, allow_zero=True)


def test_wait_for_server_history_allows_zero_poll_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ImmediateClient:
        def __init__(self, _url: str) -> None:
            pass

        async def history(self, prompt_id: str) -> dict[str, object]:
            return {
                prompt_id: {
                    "outputs": {},
                    "status": {"status_str": "success", "completed": True, "messages": []},
                }
            }

    monkeypatch.setattr(session_module, "ComfyClient", ImmediateClient)
    monkeypatch.setenv("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC", "0")

    result = asyncio.run(
        _wait_for_server_history("http://runtime.test", "prompt-id", config=None)
    )

    assert result["prompt-id"]["status"]["completed"] is True  # type: ignore[index]


def test_agent_runtime_import_and_discovery_ignore_malformed_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_CHUNKED_EMIT_THRESHOLD", "oops")

    imported = importlib.reload(agent_runtime)
    monkeypatch.setenv("VIBECOMFY_ARNOLD_RUNTIME_MODULE", imported.__name__)

    assert agent_provider._load_arnold_runtime() is imported


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VIBECOMFY_PROMPT_TIMEOUT_SEC", "oops"),
        ("VIBECOMFY_PROMPT_TIMEOUT_SEC", "0"),
        ("VIBECOMFY_HISTORY_POLL_INTERVAL_SEC", "-1"),
    ],
)
def test_wait_for_server_history_rejects_invalid_environment_durations(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeConfigurationError, match="finite number"):
        asyncio.run(_wait_for_server_history("http://127.0.0.1:8188", "prompt-id", config=None))
