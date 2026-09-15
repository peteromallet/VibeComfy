from __future__ import annotations

import asyncio
import threading
from importlib import import_module
from pathlib import Path

import pytest

from vibecomfy.runtime import EmbeddedSessionOwner, SessionConfig
from tests._runtime_session_helpers import _approved, _workflow, fake_comfy

run_module = import_module("vibecomfy.runtime.run")


class _FakeSession:
    instances: list["_FakeSession"] = []

    def __init__(self, config: SessionConfig) -> None:
        self.config = config
        self.reconfigures = 0
        self.stopped = False
        self._process_configuration = type(
            "Snapshot", (), {"values": dict(config.extra)}
        )()
        self.__class__.instances.append(self)

    async def start(self) -> None:
        return None

    async def reconfigure(self, config: SessionConfig) -> None:
        self.config = config
        self.reconfigures += 1
        self._process_configuration.values = dict(config.extra)

    async def stop(self) -> None:
        self.stopped = True


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    _FakeSession.instances = []


def test_owner_reuses_real_session_class_on_one_persistent_event_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run_module, "EmbeddedSession", _FakeSession)
    seen: list[tuple[object, object, str | None]] = []

    async def fake_run(session, record, bundle, **_kwargs):
        seen.append((session, record, session.config.extra.get("output_directory")))
        return {"session": id(session), "spool": session.config.extra.get("output_directory")}

    monkeypatch.setattr(run_module, "run_embedded_with_session", fake_run)
    first_config = SessionConfig(extra={"output_directory": str(tmp_path / "one")})
    second_config = SessionConfig(extra={"output_directory": str(tmp_path / "two")})

    owner = EmbeddedSessionOwner(first_config)
    first = owner.run("record-1", "bundle-1")
    second = owner.run("record-2", "bundle-2", config=second_config)

    assert first["session"] == second["session"]
    assert [item[2] for item in seen] == [str(tmp_path / "one"), str(tmp_path / "two")]
    assert len(_FakeSession.instances) == 1
    assert _FakeSession.instances[0].reconfigures == 1
    owner.close()
    assert _FakeSession.instances[0].stopped is True


def test_owner_rejects_unobservable_output_rebind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run_module, "EmbeddedSession", _FakeSession)
    async def fake_run(*args, **kwargs):
        return None

    monkeypatch.setattr(run_module, "run_embedded_with_session", fake_run)
    owner = EmbeddedSessionOwner(
        SessionConfig(extra={"output_directory": str(tmp_path / "requested")})
    )
    owner.run("record", "bundle")
    # The owner starts the session before this check; remove the runtime
    # observation to model a backend whose rebind cannot be independently
    # attested.  The owner must fail closed.
    _FakeSession.instances[0]._process_configuration = None
    with pytest.raises(RuntimeError, match="not independently observable"):
        owner.run("record", "bundle")
    owner.close()


def test_owner_serializes_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run_module, "EmbeddedSession", _FakeSession)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    order: list[str] = []

    async def fake_run(_session, record, _bundle, **_kwargs):
        order.append(f"enter:{record}")
        if record == "first":
            first_entered.set()
            while not release_first.is_set():
                await asyncio.sleep(0.001)
        else:
            second_entered.set()
        order.append(f"exit:{record}")
        return record

    monkeypatch.setattr(run_module, "run_embedded_with_session", fake_run)
    owner = EmbeddedSessionOwner(
        SessionConfig(extra={"output_directory": str(tmp_path / "output")})
    )
    results: list[str] = []
    first = threading.Thread(
        target=lambda: results.append(owner.run("first", "bundle"))
    )
    second = threading.Thread(
        target=lambda: results.append(owner.run("second", "bundle"))
    )
    first.start()
    assert first_entered.wait(timeout=2)
    second.start()
    assert not second_entered.wait(timeout=0.05)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)
    owner.close()

    assert not first.is_alive()
    assert not second.is_alive()
    assert results == ["first", "second"]
    assert order == ["enter:first", "exit:first", "enter:second", "exit:second"]


def test_owner_drives_actual_embedded_session_across_two_cpu_tasks(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record, bundle = _approved(_workflow())
    first_config = SessionConfig(extra={"output_directory": str(tmp_path / "one")})
    second_config = SessionConfig(extra={"output_directory": str(tmp_path / "two")})

    owner = EmbeddedSessionOwner(first_config)
    try:
        first = owner.run(record, bundle)
        second = owner.run(record, bundle, config=second_config)
    finally:
        owner.close()

    assert first.prompt_id != second.prompt_id
    assert fake_comfy.enter_count == 1
    assert fake_comfy.exit_count == 1
    assert len(fake_comfy.instances) == 1
    assert len(fake_comfy.instances[0].queue_calls) == 2
    assert len(fake_comfy.instances[0].reconfigure_calls) == 1
