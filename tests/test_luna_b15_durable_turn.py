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


def test_missing_publication_for_state_key_fails_closed(tmp_path: Path) -> None:
    request, allocation = _allocation(tmp_path)
    _record(allocation, {"ok": True, "message": "must not trust projection"})
    (allocation.turn_dir / S.RESPONSE_PUBLICATION_FILE_NAME).unlink()

    with pytest.raises(S.DurableReadError) as exc_info:
        S.allocate_turn(
            session_root=tmp_path,
            session_id="b15-session",
            request_payload=request,
            idempotency_key="retry-key",
        )

    assert exc_info.value.status == "unreadable"

    with pytest.raises(S.DurableReadError) as exc_info:
        S.record_idempotent_response(
            session_root=tmp_path,
            session_id="b15-session",
            scope="edit",
            idempotency_key="retry-key",
            request_hash=allocation.request_hash,
            response={"ok": True, "message": "must not win"},
            response_path=allocation.turn_dir / "response.json",
            operation="edit",
            turn_id=allocation.context.turn_id,
        )
    assert exc_info.value.status == "unreadable"


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


def test_publication_wins_over_tampered_projection_on_both_replay_doors(
    tmp_path: Path,
) -> None:
    request, allocation = _allocation(tmp_path)
    _record(allocation, {"ok": True, "message": "immutable answer"})
    projection = allocation.turn_dir / "response.json"
    projection.write_text(json.dumps({"ok": True, "message": "tampered"}), encoding="utf-8")

    replay = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload=request,
        idempotency_key="retry-key",
    )
    assert replay.replay is not None
    assert replay.replay.response["message"] == "immutable answer"

    projection.write_text(json.dumps({"ok": True, "message": "tampered again"}), encoding="utf-8")
    inbound = {"ok": True, "message": "new inbound body"}
    record = S.record_idempotent_response(
        session_root=tmp_path,
        session_id="b15-session",
        scope="edit",
        idempotency_key="retry-key",
        request_hash=allocation.request_hash,
        response=inbound,
        response_path=projection,
        operation="edit",
        turn_id=allocation.context.turn_id,
    )
    assert record is not None
    assert inbound["message"] == "immutable answer"
    assert json.loads(projection.read_text(encoding="utf-8"))["message"] == "immutable answer"


def test_state_reconstruction_advances_past_occupied_turn_for_new_key(tmp_path: Path) -> None:
    _, allocation = _allocation(tmp_path)
    _record(allocation, {"ok": True, "message": "first"})
    (allocation.session_dir / S.STATE_FILE_NAME).unlink()

    next_allocation = S.allocate_turn(
        session_root=tmp_path,
        session_id="b15-session",
        request_payload={"task": "different", "idempotency_key": "new-key"},
        idempotency_key="new-key",
    )

    assert next_allocation.context.turn_id == "0002"
    assert (allocation.session_dir / "turns" / "0001" / S.RESPONSE_PUBLICATION_FILE_NAME).is_file()
    state = S.read_state(allocation.session_dir)
    assert "0001" in state["turns"]
    assert state["next_turn_index"] == 3


def test_executor_only_same_key_conflict_returns_typed_failure(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.executor_durable import (
        maybe_write_executor_only_durable_turn,
    )

    graph = {"nodes": [{"id": 1, "type": "LoadImage"}], "links": []}
    first_request = SimpleNamespace(query="one", graph=graph)
    first_payload = {
        "query": "one",
        "graph": graph,
        "session_id": "executor-conflict",
        "idempotency_key": "same-key",
    }
    first = maybe_write_executor_only_durable_turn(
        response={
            "ok": True,
            "route": "inspect",
            "reply": "one",
            "message": "one",
            "outcome": {"kind": "noop"},
        },
        result=None,
        payload=first_payload,
        request=first_request,
        session_root=tmp_path,
    )

    second = maybe_write_executor_only_durable_turn(
        response={
            "ok": True,
            "route": "inspect",
            "reply": "two",
            "message": "two",
            "outcome": {"kind": "noop"},
        },
        result=None,
        payload={**first_payload, "query": "two"},
        request=SimpleNamespace(query="two", graph=graph),
        session_root=tmp_path,
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["turn_id"] == first["turn_id"]


def test_session_iteration_raises_for_corrupt_state(tmp_path: Path) -> None:
    session_dir = tmp_path / "iter-session"
    session_dir.mkdir()
    (session_dir / S.STATE_FILE_NAME).write_text("{broken", encoding="utf-8")

    with pytest.raises(S.DurableReadError) as exc_info:
        list(S.iter_turn_records(tmp_path, "iter-session"))
    assert exc_info.value.status == "corrupt"


def test_chat_reconstruction_uses_publication_when_projection_is_corrupt(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent._frag_chat import read_session_chat

    request, allocation = _allocation(tmp_path)
    request_path = allocation.turn_dir / "request.json"
    request_path.write_text(json.dumps({"task": "remember this"}), encoding="utf-8")
    _record(allocation, {"ok": True, "message": "published answer"})
    (allocation.turn_dir / "response.json").write_text("{broken", encoding="utf-8")

    result = read_session_chat(tmp_path, "b15-session")

    assert result["ok"] is True
    assert result["messages"][-1]["text"] == "published answer"


def test_batch_repl_does_not_continue_after_typed_chat_read_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.comfy_nodes.agent.edit as edit_module

    def fail_chat(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise S.DurableReadError(
            S.DurableRead("unreadable", path=tmp_path / "turns", error="walk failed")
        )

    monkeypatch.setattr(edit_module, "read_session_chat", fail_chat)

    result = edit_module.handle_agent_edit(
        {
            "task": "inspect this workflow",
            "graph": {"nodes": [], "links": []},
            "session_id": "batch-chat-failure",
        },
        session_root=tmp_path,
    )

    assert result["ok"] is False
    assert result["debug"]["failure"]["agent_failure_context"]["explanation"]
