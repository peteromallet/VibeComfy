from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import vibecomfy.runtime.session as session_module
from vibecomfy.errors import RuntimeConfigurationError
from vibecomfy.runtime.session import (
    EmbeddedSession,
    ServerSession,
    SessionConfig,
    _allocate_request_root,
    _comfy_server_argv,
    _configured_output_directory,
)

from tests._runtime_session_helpers import (
    _patch_fast_runtime_run,
    _workflow,
    fake_comfy,  # noqa: F401 -- pytest fixture imported for use in tests
    fake_server,  # noqa: F401 -- pytest fixture imported for use in tests
)


def test_strict_drift_is_typed_round_tripped_and_used(
    fake_comfy,  # noqa: F811 -- pytest fixture is intentionally shadowed by its parameter
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    checked: list[object] = []
    monkeypatch.setattr(session_module, "enforce_strict_drift", checked.append)

    config = SessionConfig.from_dict({"strict_drift": True})
    assert config.strict_drift is True
    assert "strict_drift" not in config.extra

    workflow = _workflow()
    session = EmbeddedSession(config)

    async def run_case() -> None:
        try:
            await session.run(workflow)
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert checked == [workflow]


@pytest.mark.parametrize(
    "values",
    [
        {"strict_drift": "true"},
        {"strict_drift": 1},
        {"strict_drift": None},
        {"port": "8200"},
    ],
)
def test_malformed_typed_runtime_config_has_one_normalized_failure(
    values: dict[str, object],
) -> None:
    with pytest.raises(RuntimeConfigurationError, match="Invalid runtime session configuration") as exc_info:
        SessionConfig.from_dict(values)

    assert isinstance(exc_info.value, ValueError)
    assert exc_info.value.next_action == "Fix the runtime configuration and retry."


def test_runtime_root_and_cwd_are_captured_before_process_cwd_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = tmp_path / "initial"
    later = tmp_path / "later"
    initial.mkdir()
    later.mkdir()
    monkeypatch.chdir(initial)
    config = SessionConfig.from_dict({"input_directory": "inputs"})

    monkeypatch.chdir(later)
    _run_id, run_dir = _allocate_request_root("run", config=config)
    argv = _comfy_server_argv(config)

    assert run_dir.parent == initial / "out/runs"
    assert argv[argv.index("--input-directory") + 1] == str(initial / "inputs")
    assert config.runtime_root == initial
    assert config.cwd == initial


def test_dynamic_io_is_snapshotted_at_server_process_start(
    fake_server,  # noqa: F811 -- pytest fixture is intentionally shadowed by its parameter
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first_output = tmp_path / "first-output"
    later_output = tmp_path / "later-output"
    monkeypatch.setenv(
        "VIBECOMFY_COMFY_CONFIGURATION",
        json.dumps({"output_directory": str(first_output)}),
    )
    session = ServerSession(SessionConfig(port=8200))

    async def run_case() -> str:
        await session.start()
        monkeypatch.setenv(
            "VIBECOMFY_COMFY_CONFIGURATION",
            json.dumps({"output_directory": str(later_output)}),
        )
        try:
            assert _configured_output_directory(session.config) == str(later_output)
            result = await session.run(_workflow())
            return result.outputs[0]
        finally:
            await session.stop()

    output = asyncio.run(run_case())
    assert output == str(first_output / "server-output.png")
    argv = fake_server[0][0]
    assert argv[argv.index("--output-directory") + 1] == str(first_output)


def test_duplicate_start_and_repeated_stop_keep_b08_ownership_intact(
    fake_server,  # noqa: F811 -- pytest fixture is intentionally shadowed by its parameter
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    session = ServerSession(SessionConfig(port=8200))

    async def run_case() -> None:
        await session.start()
        process = session.process
        await session.start()
        assert session.process is process
        await session.stop()
        await session.stop()

    asyncio.run(run_case())
    assert len(fake_server) == 1
    assert session.process is None
    assert session.url is None
