"""Durable continuity, isolation, budget, and turn-fencing contracts."""

from __future__ import annotations

from typing import Any

import pytest

from tests._executor_threaded_helpers import (
    THREADED_FEATURE_REQUIRED,
    ThreadSessionError,
    host_ports,
)


pytestmark = THREADED_FEATURE_REQUIRED


def _begin(ports: Any, session_id: str, request: dict[str, Any], **kwargs: Any) -> Any:
    assert ports.thread_begin is not None
    return ports.thread_begin(
        session_id=session_id, request_payload=request, **kwargs
    )


def _append(ports: Any, session_id: str, token: str, events: Any) -> Any:
    assert ports.thread_append is not None
    return ports.thread_append(
        session_id=session_id, lease_token=token, events=events
    )


def _complete(
    ports: Any,
    session_id: str,
    token: str,
    outcome: dict[str, Any],
    *,
    checkpoint: dict[str, Any] | None = None,
) -> Any:
    assert ports.thread_complete is not None
    return ports.thread_complete(
        session_id=session_id,
        lease_token=token,
        outcome=outcome,
        checkpoint=checkpoint,
    )


def test_same_session_continuity_accumulates_messages_refs_and_budget(tmp_path) -> None:
    ports = host_ports(tmp_path / "sessions")
    first = _begin(
        ports,
        "window-a",
        {"query": "set the prompt"},
        idempotency_key="turn-1",
        expected_revision=0,
    )
    state = _append(
        ports,
        "window-a",
        first["lease_token"],
        [
            {"kind": "user_message", "content": "set the prompt"},
            {"kind": "assistant_message", "content": "prompt set"},
            {
                "kind": "budget",
                "budget_delta": {"model_tokens": 120, "tool_calls": 1},
            },
            {
                "kind": "edit_accepted",
                "delta_id": "delta:one",
                "fact_ids": ["fact:prompt"],
                "evidence_ids": ["evidence:schema"],
                "revision": 1,
            },
        ],
    )
    assert state["revision"] == 1
    _complete(
        ports,
        "window-a",
        first["lease_token"],
        {"ok": True, "reply": "prompt set"},
        checkpoint={"delta_ids": ["delta:one"]},
    )

    second = _begin(
        ports,
        "window-a",
        {"query": "now explain it"},
        idempotency_key="turn-2",
        expected_revision=1,
    )
    state = _append(
        ports,
        "window-a",
        second["lease_token"],
        [
            {"kind": "user_message", "content": "now explain it"},
            {"kind": "budget", "budget_delta": {"model_tokens": 80}},
        ],
    )

    assert state["session_id"] == "window-a"
    assert state["messages"] == [
        {"role": "user", "content": "set the prompt"},
        {"role": "assistant", "content": "prompt set"},
        {"role": "user", "content": "now explain it"},
    ]
    assert state["accepted_delta_ids"] == ["delta:one"]
    assert state["fact_ids"] == ["fact:prompt"]
    assert state["evidence_ids"] == ["evidence:schema"]
    assert state["budget"] == {"model_tokens": 200, "tool_calls": 1}

    assert ports.thread_abort is not None
    ports.thread_abort(
        session_id="window-a",
        lease_token=second["lease_token"],
        reason="test complete",
    )


def test_new_window_isolation_starts_without_prior_context_or_budget(tmp_path) -> None:
    ports = host_ports(tmp_path / "sessions")
    first = _begin(ports, "window-a", {"query": "first"}, expected_revision=0)
    _append(
        ports,
        "window-a",
        first["lease_token"],
        [
            {"kind": "user_message", "content": "first"},
            {"kind": "budget", "budget_delta": {"model_tokens": 55}},
            {"kind": "edit_accepted", "delta_id": "delta:a", "revision": 1},
        ],
    )
    _complete(ports, "window-a", first["lease_token"], {"ok": True})

    fresh = _begin(ports, "window-b", {"query": "fresh"}, expected_revision=0)
    assert fresh["state"]["session_id"] == "window-b"
    assert fresh["state"]["messages"] == []
    assert fresh["state"]["budget"] == {}
    assert fresh["state"]["accepted_delta_ids"] == []
    assert fresh["state"]["fact_ids"] == []
    assert fresh["state"]["evidence_ids"] == []
    assert fresh["state"]["revision"] == 0


def test_concurrent_stale_and_idempotent_turns_are_deterministically_fenced(
    tmp_path,
) -> None:
    ports = host_ports(tmp_path / "sessions")
    request = {"query": "edit once", "graph_hash": "base:0"}
    first = _begin(
        ports,
        "window-a",
        request,
        idempotency_key="idem-1",
        expected_revision=0,
    )

    with pytest.raises(ThreadSessionError) as concurrent:
        _begin(
            ports,
            "window-a",
            {"query": "racing turn"},
            idempotency_key="idem-race",
            expected_revision=0,
        )
    assert concurrent.value.kind == "concurrent_message"

    _append(
        ports,
        "window-a",
        first["lease_token"],
        {"kind": "edit_accepted", "delta_id": "delta:one", "revision": 1},
    )
    outcome = {"ok": True, "reply": "edited", "delta_ids": ["delta:one"]}
    completed = _complete(
        ports,
        "window-a",
        first["lease_token"],
        outcome,
        checkpoint={"delta_ids": ["delta:one"], "revision": 1},
    )
    completed_seq = completed["last_seq"]

    replay = _begin(
        ports,
        "window-a",
        request,
        idempotency_key="idem-1",
        expected_revision=0,
    )
    assert replay["status"] == "replay"
    assert replay["lease_token"] is None
    assert replay["outcome"] == outcome
    assert replay["state"]["last_seq"] == completed_seq
    assert replay["state"]["accepted_delta_ids"] == ["delta:one"]

    with pytest.raises(ThreadSessionError) as conflict:
        _begin(
            ports,
            "window-a",
            {"query": "different payload"},
            idempotency_key="idem-1",
            expected_revision=1,
        )
    assert conflict.value.kind == "idempotency_conflict"

    with pytest.raises(ThreadSessionError) as stale:
        _begin(
            ports,
            "window-a",
            {"query": "next turn"},
            idempotency_key="idem-2",
            expected_revision=0,
        )
    assert stale.value.kind == "stale_message"
    assert stale.value.detail == {"expected": 0, "retained": 1}


def test_closed_thread_is_terminal_instead_of_becoming_a_fresh_session(tmp_path) -> None:
    ports = host_ports(tmp_path / "sessions")
    first = _begin(ports, "window-a", {"query": "done"})
    _complete(ports, "window-a", first["lease_token"], {"ok": True})
    assert ports.thread_close is not None
    closed = ports.thread_close(session_id="window-a")
    assert closed["closed"] is True

    with pytest.raises(ThreadSessionError) as expired:
        _begin(ports, "window-a", {"query": "too late"})
    assert expired.value.kind == "session_expired"


def test_completed_checkpoint_isolated_from_a_later_aborted_turn(tmp_path) -> None:
    ports = host_ports(tmp_path / "sessions")
    first = _begin(
        ports,
        "window-a",
        {"query": "land edit"},
        idempotency_key="turn-1",
        expected_revision=0,
    )
    _append(
        ports,
        "window-a",
        first["lease_token"],
        {"kind": "edit_accepted", "delta_id": "delta:one", "revision": 1},
    )
    checkpoint = {
        "revision": 1,
        "delta_ids": ["delta:one"],
        "fact_ids": ["fact:one"],
        "evidence_ids": ["evidence:one"],
    }
    _complete(
        ports,
        "window-a",
        first["lease_token"],
        {"ok": True},
        checkpoint=checkpoint,
    )

    second = _begin(
        ports,
        "window-a",
        {"query": "failing follow-up"},
        idempotency_key="turn-2",
        expected_revision=1,
    )
    _append(
        ports,
        "window-a",
        second["lease_token"],
        {"kind": "budget", "budget_delta": {"model_tokens": 99}},
    )
    assert ports.thread_abort is not None
    ports.thread_abort(
        session_id="window-a",
        lease_token=second["lease_token"],
        reason="provider failed",
    )

    assert ports.thread_load is not None
    reloaded = ports.thread_load("window-a")
    assert reloaded["checkpoint"] == checkpoint
    assert reloaded["accepted_delta_ids"] == ["delta:one"]
    assert reloaded["revision"] == 1
    assert reloaded["last_event"]["kind"] == "message_aborted"
