"""Focused B15 durability tests for typed evidence and response publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent import session as S


def _allocation(tmp_path: Path, *, key: str = "retry-key") -> tuple[dict, S.TurnAllocation]:
    request = {"task": "inspect", "idempotency_key": key}
    allocation = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload=request,
        idempotency_key=key,
    )
    return request, allocation


def _record(allocation: S.TurnAllocation, response: dict[str, object]) -> None:
    S.record_idempotent_response(
        session_root=allocation.session_dir.parent,
        session_id=allocation.context.session_id,
        scope="edit",
        idempotency_key=allocation.context.idempotency_key,
        request_hash=allocation.request_hash,
        response=response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=allocation.context.turn_id,
    )


def test_publication_recovers_when_state_cache_is_missing(tmp_path: Path) -> None:
    request, allocation = _allocation(tmp_path)
    response = {"ok": True, "message": "authoritative"}
    _record(allocation, response)

    (allocation.session_dir / S.STATE_FILE_NAME).unlink()
    replay = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload=request,
        idempotency_key="retry-key",
    )

    assert replay.context.turn_id == allocation.context.turn_id
    assert replay.replay is not None
    assert replay.replay.response == response
    assert (allocation.session_dir / S.STATE_FILE_NAME).is_file()


def test_corrupt_state_refuses_turn_allocation(tmp_path: Path) -> None:
    session_dir = tmp_path / "b15-session"
    session_dir.mkdir()
    (session_dir / S.STATE_FILE_NAME).write_text("{broken", encoding="utf-8")

    with pytest.raises(S.DurableReadError) as exc_info:
        S.allocate_turn(
            session_root=tmp_path,
            session_id="b15-session",
            request_payload={"task": "must not mutate"},
        )
    assert exc_info.value.status == "corrupt"
    assert not (session_dir / "turns").exists()


def test_publication_recovers_after_state_write_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, allocation = _allocation(tmp_path)
    original_write_state = S.write_state_atomic
    failed = False

    def fail_once(session_dir: Path, state: dict) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("crash after publication")
        original_write_state(session_dir, state)

    monkeypatch.setattr(S, "write_state_atomic", fail_once)
    with pytest.raises(OSError, match="crash after publication"):
        _record(allocation, {"ok": True, "message": "recover me"})
    monkeypatch.setattr(S, "write_state_atomic", original_write_state)

    replay = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload={"task": "inspect", "idempotency_key": "retry-key"},
        idempotency_key="retry-key",
    )
    assert replay.replay is not None
    assert replay.replay.response["message"] == "recover me"
    assert replay.context.turn_id == allocation.context.turn_id


def test_publication_recovers_after_response_projection_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request, allocation = _allocation(tmp_path)
    original_write_response = S._write_response_atomic
    failed = False

    def fail_once(response_path: Path, response: dict) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("crash publishing projection")
        original_write_response(response_path, response)

    monkeypatch.setattr(S, "_write_response_atomic", fail_once)
    with pytest.raises(OSError, match="crash publishing projection"):
        _record(allocation, {"ok": True, "message": "recover projection"})
    monkeypatch.setattr(S, "_write_response_atomic", original_write_response)

    replay = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload=request,
        idempotency_key="retry-key",
    )
    assert replay.replay is not None
    assert replay.replay.response["message"] == "recover projection"
    assert json.loads((allocation.turn_dir / "response.json").read_text())["message"] == "recover projection"


def test_corrupt_publication_fails_closed_and_cannot_fork(tmp_path: Path) -> None:
    request, allocation = _allocation(tmp_path)
    _record(allocation, {"ok": True, "message": "do not fork"})
    (allocation.turn_dir / S.RESPONSE_PUBLICATION_FILE_NAME).write_text("{broken", encoding="utf-8")

    with pytest.raises(S.DurableReadError) as exc_info:
        S.allocate_turn(
            session_root=tmp_path,
            session_id="b15-session",
            request_payload=request,
            idempotency_key="retry-key",
        )
    assert exc_info.value.status == "corrupt"
    assert not (allocation.session_dir / "turns" / "0002").exists()


def test_idempotency_retry_conflict_still_does_not_allocate_second_turn(tmp_path: Path) -> None:
    _, allocation = _allocation(tmp_path)
    _record(allocation, {"ok": True, "message": "one turn"})

    conflict = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload={"task": "different", "idempotency_key": "retry-key"},
        idempotency_key="retry-key",
    )
    assert conflict.conflict is not None
    assert conflict.context.turn_id == allocation.context.turn_id
    assert not (allocation.session_dir / "turns" / "0002").exists()
