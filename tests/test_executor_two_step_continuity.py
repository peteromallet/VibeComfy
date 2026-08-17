"""B03 — thread-continuous two-step session continuity (initial cases).

Covers the session authority directly plus the bounded execute loop's
transcript flattening: same-session reuse, new-window freshness, mid-thread
route change, missing turn-1 Δ failure, cumulative budget accumulation,
invalid-request / session-expired identity errors, and research_attempt
derivation.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from vibecomfy.executor.agent_backend import run_execute_turn
from vibecomfy.executor.two_step_session import (
    ERROR_INVALID_REQUEST,
    ERROR_MISSING_DELTA_REFERENCE,
    ERROR_SESSION_EXPIRED,
    TwoStepSessionError,
    TwoStepSessionStore,
    derive_research_attempt,
)


def _store(tmp_path) -> TwoStepSessionStore:
    return TwoStepSessionStore(tmp_path / "sessions")


def _plan():
    return SimpleNamespace(
        effective_route="revise",
        effective_task="",
        plan_summary="revise the graph",
        implement=True,
        research=False,
    )


def _spec():
    return SimpleNamespace(agent="hermes", model="m", effort=None)


def test_same_session_reuse_sees_turn1_delta(tmp_path) -> None:
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    store.append("win-a", "user_message", {"query": "q1", "route": "revise"}, turn=1)
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)
    store.end_message("win-a", message_fingerprint="f1")

    state = store.begin_message("win-a", message_fingerprint="f2")
    assert "d1" in state.accepted_delta_ids()
    state.validate_delta_references(["d1"])


def test_new_window_fresh(tmp_path) -> None:
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)
    store.end_message("win-a", message_fingerprint="f1")

    state = store.begin_message("win-b", message_fingerprint="f2", base_graph={"nodes": []})
    assert state.accepted_delta_ids() == ()
    assert state.route_history == ()


def test_mid_thread_route_change_keeps_session(tmp_path) -> None:
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    store.append("win-a", "route", {"route": "revise"}, turn=1)
    store.append("win-a", "user_message", {"query": "q1", "route": "revise"}, turn=1)
    store.end_message("win-a", message_fingerprint="f1")

    store.begin_message("win-a", message_fingerprint="f2")
    store.append("win-a", "route", {"route": "adapt"}, turn=2)
    state = store.load("win-a")
    assert state.session_id == "win-a"
    assert [r["route"] for r in state.route_history] == ["revise", "adapt"]


def test_missing_turn1_delta_fails(tmp_path) -> None:
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)
    store.end_message("win-a", message_fingerprint="f1")

    state = store.load("win-a")
    with pytest.raises(TwoStepSessionError) as excinfo:
        state.validate_delta_references(["d1", "forged"])
    assert excinfo.value.kind == ERROR_MISSING_DELTA_REFERENCE


def test_budgets_accumulate_with_per_message_slices(tmp_path) -> None:
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    store.append("win-a", "user_message", {"query": "q1", "route": "revise"}, turn=1)
    store.append(
        "win-a",
        "budget",
        {"budget": store.load("win-a").budget.record_output_tokens(1000).to_dict()},
        turn=1,
    )
    store.end_message("win-a", message_fingerprint="f1")

    store.begin_message("win-a", message_fingerprint="f2")
    store.append("win-a", "user_message", {"query": "q2", "route": "revise"}, turn=2)
    store.append(
        "win-a",
        "budget",
        {"budget": store.load("win-a").budget.record_output_tokens(2000).to_dict()},
        turn=2,
    )
    state = store.load("win-a")
    assert state.budget.output_tokens == 3000
    assert state.budget.user_messages == 2


def test_missing_session_id_is_invalid_request(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(TwoStepSessionError) as excinfo:
        store.begin_message(None)
    assert excinfo.value.kind == ERROR_INVALID_REQUEST


def test_closed_session_is_expired_never_fresh(tmp_path) -> None:
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    store.close("win-a")
    with pytest.raises(TwoStepSessionError) as excinfo:
        store.begin_message("win-a", message_fingerprint="f2")
    assert excinfo.value.kind == ERROR_SESSION_EXPIRED


def test_run_execute_turn_flattens_transcript_into_user_payload(tmp_path) -> None:
    store = _store(tmp_path)
    captured: dict = {}

    def fake_model_turn(task, messages, **kwargs):
        captured["messages"] = messages
        captured["remaining_output_cap"] = kwargs.get("remaining_output_cap")
        return {
            "content": json.dumps(
                {"action": "submit", "reply": "done", "delta_ids": []}
            )
        }

    request = SimpleNamespace(
        query="make it brighter",
        graph={"nodes": []},
        session_id="win-a",
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )
    outcome = run_execute_turn(
        request,
        plan=_plan(),
        route="revise",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=fake_model_turn,
    )
    assert outcome["ok"] is True
    assert outcome["reply"] == "done"
    assert outcome["research_attempt"] == "never"

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    # The compact transcript is FLATTENED into the final user payload.
    assert "PRIOR TURNS (this window)" in msgs[1]["content"]


def test_run_execute_turn_rejects_forged_delta(tmp_path) -> None:
    store = _store(tmp_path)

    def fake_model_turn(task, messages, **kwargs):
        return {
            "content": json.dumps(
                {"action": "submit", "reply": "done", "delta_ids": ["forged"]}
            )
        }

    request = SimpleNamespace(
        query="q",
        graph={"nodes": []},
        session_id="win-a",
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )
    outcome = run_execute_turn(
        request,
        plan=_plan(),
        route="revise",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=fake_model_turn,
    )
    assert outcome["ok"] is False
    assert getattr(outcome["failure"], "kind", None) == ERROR_MISSING_DELTA_REFERENCE


def test_derive_research_attempt_levels() -> None:
    assert derive_research_attempt([]) == "never"
    assert derive_research_attempt([{"tool": "hivemind_search", "evidence_ids": []}]) == "empty"
    assert derive_research_attempt([{"tool": "hivemind_search", "evidence_ids": ["e1"]}]) == "thin"
    assert derive_research_attempt([{"tool": "hivemind_get", "evidence_ids": ["e1"]}]) == "grounded"
