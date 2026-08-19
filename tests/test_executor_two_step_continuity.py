"""B03 — thread-continuous two-step session continuity (initial cases).

Covers the session authority directly plus the bounded execute loop's
transcript flattening: same-session reuse, new-window freshness, mid-thread
route change, missing turn-1 Δ failure, cumulative budget accumulation,
invalid-request / session-expired identity errors, and research_attempt
derivation.
"""

from __future__ import annotations

import json
from pathlib import Path
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
    assert outcome["research_attempt"] == "never"

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    # The compact transcript is FLATTENED into the final user payload.
    assert "PRIOR TURNS (this window)" in msgs[1]["content"]


def test_reply_is_the_models_final_message_text(tmp_path) -> None:
    """One-step: the reply is the model's FINAL MESSAGE text, not the submit
    contract's ``reply`` field."""
    store = _store(tmp_path)
    # The final message carries prose plus the structured submit contract; the
    # reply must equal the WHOLE final message text (prose), not the JSON field.
    final_message = (
        "I added a brightness node and bumped the exposure.\n"
        + json.dumps({"action": "submit", "reply": "IGNORED JSON FIELD", "delta_ids": []})
    )

    def fake_model_turn(task, messages, **kwargs):
        return {"content": final_message}

    request = SimpleNamespace(
        query="add a brightness node",
        graph={"nodes": []},
        session_id="win-a",
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )
    outcome = run_execute_turn(
        request,
        plan=None,
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=fake_model_turn,
    )
    assert outcome["ok"] is True
    assert outcome["reply"] == final_message


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


# ── B06 (Pro): concurrency / recovery / CAS / idempotent replay ──────────────
# Appended below the B03/B04 section (do not clobber).  These exercise the
# durable ``TwoStepSessionStore`` authority directly — the in-flight marker,
# the stale-baseline CAS precursor, the named-ingest door, and canonical Δ
# replay — without any model calls.

import threading  # noqa: E402

from vibecomfy.executor.two_step_session import (  # noqa: E402
    ERROR_CONCURRENT_MESSAGE,
    ERROR_STALE_MESSAGE,
    canonical_workflow_hash,
)


def test_two_simultaneous_messages_serialize_without_corruption(tmp_path) -> None:
    """Two messages for one session serialize: neither write is lost.

    ``begin_message`` / ``append`` / ``end_message`` are all serialized by the
    reused process-safe ``SessionStateLock`` (O_EXCL), so a racing second
    message never drops the first message's transcript events.
    """
    store = _store(tmp_path)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def run_one(fingerprint: str, query: str) -> None:
        try:
            barrier.wait()
            store.begin_message(
                "win-a", message_fingerprint=fingerprint, base_graph={"nodes": []}
            )
            store.append("win-a", "user_message", {"query": query, "route": "revise"}, turn=1)
            store.end_message("win-a", message_fingerprint=fingerprint)
        except BaseException as exc:  # noqa: BLE001 - collect for assertion
            errors.append(exc)

    threads = [
        threading.Thread(target=run_one, args=("m1", "first")),
        threading.Thread(target=run_one, args=("m2", "second")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    assert errors == []
    state = store.load("win-a")
    queries = sorted(m["content"] for m in state.messages if m.get("role") == "user")
    assert queries == ["first", "second"]
    assert state.budget.user_messages == 2


def test_two_simultaneous_messages_second_fails_stale(tmp_path) -> None:
    """A changed canvas that no longer matches the retained revision fails CAS."""
    store = _store(tmp_path)
    base = {"nodes": [{"id": "1", "type": "T"}], "links": []}
    retained = canonical_workflow_hash(base)
    store.begin_message("win-a", message_fingerprint="m1", base_graph=base)
    store.end_message("win-a", message_fingerprint="m1")

    with pytest.raises(TwoStepSessionError) as excinfo:
        store.begin_message(
            "win-a",
            message_fingerprint="m2",
            expected_baseline_hash=canonical_workflow_hash({"nodes": []}),
        )
    assert excinfo.value.kind == ERROR_STALE_MESSAGE
    assert excinfo.value.detail["retained"] == retained


def test_server_restart_reconstructs_retained_state_via_ingest_and_replay(
    tmp_path,
) -> None:
    """A fresh store (new cache) over the same durable root rehydrates the
    retained revision through the named-ingest door plus canonical Δ replay."""
    root = tmp_path / "sessions"
    base = {"nodes": [{"id": "1", "type": "T", "widgets_values": ["before"]}], "links": []}
    store_a = TwoStepSessionStore(root)
    store_a.begin_message("win-a", message_fingerprint="m1", base_graph=base)
    store_a.append(
        "win-a",
        "delta_accepted",
        {
            "delta_ids": ["d1"],
            "ops": [
                {
                    "op": "set_node_field",
                    "target": ["", "1", "widgets_values"],
                    "value": ["after"],
                }
            ],
        },
        turn=1,
    )
    store_a.end_message("win-a", message_fingerprint="m1")

    # "Server restart": a brand-new store over the same durable root (its cache
    # is cold, so state must come from the append-only transcript).
    store_b = TwoStepSessionStore(root)
    state = store_b.load("win-a")
    assert state is not None
    assert state.accepted_delta_ids() == ("d1",)

    replayed = store_b.replay_workflow(state)
    assert replayed is not None
    # The edited value must appear in the replayed node under whichever channel
    # the converter-less ingest used (widgets_values for widget-backed fields,
    # inputs for link/input-backed fields).
    node = replayed["nodes"][0]
    assert (
        node.get("widgets_values") == ["after"]
        or "after" in (node.get("inputs") or {}).values()
    )


def test_changed_canvas_does_not_match_retained_revision_fails_cas(tmp_path) -> None:
    """CAS precursor: a message baseline that disagrees with the retained
    revision is refused before any model work; a matching baseline passes."""
    store = _store(tmp_path)
    base = {"nodes": [{"id": "1", "type": "T"}], "links": []}
    retained = canonical_workflow_hash(base)
    store.begin_message("win-a", message_fingerprint="m1", base_graph=base)
    # Persist the retained-revision hash through the transcript so it survives
    # a cache eviction (the canonical-Δ fold records ``workflow_hash``).
    store.append(
        "win-a",
        "delta_accepted",
        {"delta_ids": ["d1"], "ops": [], "workflow_hash": retained},
        turn=1,
    )
    store.end_message("win-a", message_fingerprint="m1")

    changed = canonical_workflow_hash(
        {"nodes": [{"id": "1", "type": "T"}, {"id": "2", "type": "U"}], "links": []}
    )
    with pytest.raises(TwoStepSessionError) as excinfo:
        store.begin_message("win-a", message_fingerprint="m2", expected_baseline_hash=changed)
    assert excinfo.value.kind == ERROR_STALE_MESSAGE
    assert excinfo.value.detail["retained"] == retained

    # A matching baseline passes the CAS check.
    state = store.begin_message(
        "win-a", message_fingerprint="m3", expected_baseline_hash=retained
    )
    assert state is not None
    store.end_message("win-a", message_fingerprint="m3")


def test_idempotent_replay_does_not_duplicate_tool_calls_or_delta(tmp_path) -> None:
    """A replay of the SAME message while it is in flight fails with
    ``concurrent_message`` instead of re-running (which would duplicate the
    tool call and the accepted Δ)."""
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="m1", base_graph={"nodes": []})
    store.append(
        "win-a",
        "tool_call",
        {"tool": "node_schema", "args": {}, "evidence_ids": ["e1"], "digest": "d"},
        turn=1,
    )
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)

    with pytest.raises(TwoStepSessionError) as excinfo:
        store.begin_message("win-a", message_fingerprint="m1", base_graph={"nodes": []})
    assert excinfo.value.kind == ERROR_CONCURRENT_MESSAGE

    store.end_message("win-a", message_fingerprint="m1")
    state = store.load("win-a")
    assert len(state.evidence_ledger) == 1
    assert len(state.accepted_delta_refs) == 1


# ── B06 (Flash): the five thread-continuity cases through the bounded loop ──


def _plan_for(route: str, *, implement: bool = True, research: bool = False):
    """Plan variant for loop-level continuity tests (existing ``_plan`` is fixed)."""
    return SimpleNamespace(
        effective_route=route,
        effective_task="",
        plan_summary=f"{route} the graph",
        implement=implement,
        research=research,
    )


def _scripted_model(*actions: dict, tokens: int = 100):
    """Model-turn stub that emits one host action per call (then submits)."""
    queue = [dict(action) for action in actions]

    def model_turn_fn(task, messages, **kwargs):
        action = queue.pop(0) if queue else {"action": "submit", "reply": "done", "delta_ids": []}
        return {
            "content": json.dumps(action),
            "model_attempts": [{"token_usage": {"completion_tokens": tokens}}],
        }

    return model_turn_fn


def _fake_tool_executor(tool: str, args: dict):
    """Tool stub: no artifacts, so the call is recorded with zero evidence."""
    return None


def _execute_turn(
    store,
    session_id: str,
    *,
    query: str,
    route: str,
    model_turn_fn,
    graph=None,
    idempotency_key=None,
):
    request = SimpleNamespace(
        query=query,
        graph=graph,
        session_id=session_id,
        idempotency_key=idempotency_key,
        expected_baseline_graph_hash=None,
    )
    return run_execute_turn(
        request,
        plan=_plan_for(route),
        route=route,
        spec=_spec(),
        session_store=store,
        session_id=session_id,
        model_turn_fn=model_turn_fn,
        tool_executor=_fake_tool_executor,
    )


def test_loop_reuses_one_execute_identity_and_exposes_turn1_observations(tmp_path) -> None:
    """Same window across two loop turns: ONE execute identity (single durable
    transcript), and turn-2 sees turn-1's observations + accepted Δ."""
    store = _store(tmp_path)
    transcript = store.transcript_path("win-a")

    first = _execute_turn(
        store,
        "win-a",
        query="make it brighter",
        route="revise",
        model_turn_fn=_scripted_model({"action": "submit", "reply": "t1 done", "delta_ids": []}),
    )
    assert first["ok"] is True

    # B04-style acceptance lands after the loop: the Δ + lens facts become
    # durable session state that a follow-up message may cite.
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)
    store.append("win-a", "lens_fact", {"fact_ids": ["f1"]}, turn=1)

    captured: dict = {}

    def turn2_model(task, messages, **kwargs):
        captured["messages"] = messages
        return {
            "content": json.dumps({"action": "submit", "reply": "t2 done", "delta_ids": ["d1"]}),
            "model_attempts": [{"token_usage": {"completion_tokens": 100}}],
        }

    second = _execute_turn(
        store,
        "win-a",
        query="now the seed",
        route="revise",
        model_turn_fn=turn2_model,
    )
    assert second["ok"] is True
    assert second["accepted_delta_ids"] == ["d1"]

    # ONE identity: a single durable transcript, never re-minted.
    assert transcript.is_file()
    assert store.session_dir("win-a").is_dir()

    state = store.load("win-a")
    assert state.session_id == "win-a"
    assert state.accepted_delta_ids() == ("d1",)
    assert state.lens_fact_ids() == ("f1",)
    assert state.budget.user_messages == 2

    # Turn-2's flattened transcript carries turn-1's observations verbatim.
    user_payload = captured["messages"][1]["content"]
    assert "PRIOR TURNS (this window)" in user_payload
    assert "make it brighter" in user_payload
    assert "t1 done" in user_payload


def test_loop_new_window_starts_fresh_with_no_prior_refs(tmp_path) -> None:
    """A new chat-window id begins a fresh session: no prior refs, evidence,
    or budget from the other window."""
    store = _store(tmp_path)
    _execute_turn(
        store,
        "win-a",
        query="touch graph a",
        route="revise",
        model_turn_fn=_scripted_model({"action": "submit", "reply": "a done", "delta_ids": []}),
    )
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)

    captured: dict = {}

    def fresh_model(task, messages, **kwargs):
        captured["messages"] = messages
        return {
            "content": json.dumps({"action": "submit", "reply": "b done", "delta_ids": []}),
            "model_attempts": [{"token_usage": {"completion_tokens": 100}}],
        }

    outcome = _execute_turn(
        store,
        "win-b",
        query="fresh window",
        route="revise",
        model_turn_fn=fresh_model,
    )
    assert outcome["ok"] is True

    state = store.load("win-b")
    assert state.accepted_delta_ids() == ()
    assert state.evidence_ids() == ()
    # Only the new window's own route event exists — no prior-window history.
    assert [entry["route"] for entry in state.route_history] == ["revise"]
    assert state.budget.user_messages == 1
    assert state.budget.output_tokens == 100  # only this window's slice

    payload = captured["messages"][1]["content"]
    assert "PRIOR TURNS (this window)" in payload
    assert "touch graph a" not in payload
    assert "a done" not in payload
    assert "fresh window" in payload


def test_loop_mid_thread_route_change_keeps_execute_session(tmp_path) -> None:
    """Reclassification mid-thread (revise → adapt) reuses the SAME execute
    session: the id never changes and the route history grows."""
    store = _store(tmp_path)
    transcript = store.transcript_path("win-a")

    first = _execute_turn(
        store,
        "win-a",
        query="tweak the prompt",
        route="revise",
        model_turn_fn=_scripted_model({"action": "submit", "reply": "revised", "delta_ids": []}),
    )
    assert first["ok"] is True

    request = SimpleNamespace(
        query="now research an adapter",
        graph={"nodes": []},
        session_id="win-a",
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )
    second = run_execute_turn(
        request,
        plan=_plan_for("adapt", research=True),
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=_scripted_model({"action": "submit", "reply": "adapted", "delta_ids": []}),
    )
    assert second["ok"] is True

    state = store.load("win-a")
    assert state.session_id == "win-a"
    assert [entry["route"] for entry in state.route_history] == ["revise", "adapt"]
    assert transcript.is_file()
    assert state.budget.user_messages == 2
    assert [m.get("route") for m in state.messages if m.get("role") == "user"] == [
        "revise",
        "adapt",
    ]


def test_loop_followup_claiming_missing_turn1_delta_fails(tmp_path) -> None:
    """A follow-up that cites a Δ the session never accepted fails closed with
    the typed missing-delta-reference error through the real loop."""
    store = _store(tmp_path)
    first = _execute_turn(
        store,
        "win-a",
        query="turn one",
        route="revise",
        model_turn_fn=_scripted_model({"action": "submit", "reply": "t1", "delta_ids": []}),
    )
    assert first["ok"] is True
    store.append("win-a", "delta_accepted", {"delta_ids": ["d1"], "ops": []}, turn=1)

    second = _execute_turn(
        store,
        "win-a",
        query="follow up",
        route="revise",
        model_turn_fn=_scripted_model(
            {"action": "submit", "reply": "claim", "delta_ids": ["forged"]}
        ),
    )
    assert second["ok"] is False
    assert getattr(second["failure"], "kind", None) == ERROR_MISSING_DELTA_REFERENCE

    # The in-flight marker was still cleared by the loop's finally block.
    assert not store._in_flight_path("win-a").exists()


def test_loop_budgets_accumulate_while_messages_get_only_their_route_slice(tmp_path) -> None:
    """Session budgets accumulate across messages; each message is gated by
    ONLY its route's slice (a denied tool consumes nothing and never lands in
    the evidence ledger)."""
    from vibecomfy.executor.two_step import BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST

    store = _store(tmp_path)

    # Turn 1 (revise): hivemind_search is NOT on the revise allowlist — the
    # message receives only its route slice and the denial is typed.
    denied = _execute_turn(
        store,
        "win-a",
        query="revise pass",
        route="revise",
        model_turn_fn=_scripted_model(
            {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "x"}}
        ),
    )
    assert denied["ok"] is False
    assert getattr(denied["failure"], "family", None) == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST
    state = store.load("win-a")
    assert state.evidence_ledger == ()  # denial before dispatch consumed nothing

    # Turn 1 retry: layout_hints IS on the revise allowlist → succeeds.
    t1 = _execute_turn(
        store,
        "win-a",
        query="revise pass",
        route="revise",
        model_turn_fn=_scripted_model(
            {"action": "tool_call", "tool": "layout_hints", "args": {}},
            {"action": "submit", "reply": "r done", "delta_ids": []},
        ),
    )
    assert t1["ok"] is True

    # Turn 2 (adapt): hivemind_search is on the adapt allowlist → succeeds.
    t2 = _execute_turn(
        store,
        "win-a",
        query="adapt pass",
        route="adapt",
        model_turn_fn=_scripted_model(
            {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "y"}},
            {"action": "submit", "reply": "a done", "delta_ids": []},
        ),
    )
    assert t2["ok"] is True

    state = store.load("win-a")
    # Session budget accumulates EVERY continuation's slice: the denied
    # message's model output (1 × 100), then two 2-continuation messages
    # (2 × 100 each) → 500; the session never resets per message.
    assert state.budget.output_tokens == 500
    assert state.budget.user_messages == 3
    # Each recorded tool call carries exactly its message's route (the
    # evidence ledger entries carry tool+turn; the assistant_tool message log
    # carries the route that gated the call).
    assert [(e["tool"], e["turn"]) for e in state.evidence_ledger] == [
        ("layout_hints", 1),
        ("hivemind_search", 3),
    ]
    assert [m.get("route") for m in state.messages if m.get("role") == "assistant_tool"] == [
        "revise",
        "adapt",
    ]
    assert t1["budget"].output_tokens == 300
    assert t2["budget"].output_tokens == 500


# ── B06 (Pro): real-loop apply→submit with a REAL EditSession ─────────────────
#
# The loop-through proof: a scripted model emits ``apply`` (real
# ``EditSession.apply_batch`` → ``TwoStepEditStateMachine``) then ``submit``
# citing the landed Δ.  The real ``_two_step_tool_executor`` is wired in so the
# route-gated dispatcher is exercised; accepted Δ ids, post-edit lens facts,
# the durable candidate graph, and claim-ref validation all flow through the
# real bounded loop — never a hand-written ``delta_accepted`` event.


class _CLIPTextEncodeProvider:
    """Offline schema for CLIPTextEncode only (the flat.json fixture edits)."""

    def get_schema(self, class_type: str) -> Any:
        if class_type != "CLIPTextEncode":
            return None
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        return NodeSchema(
            "CLIPTextEncode",
            "core",
            {"text": InputSpec("STRING"), "clip": InputSpec("CLIP")},
            [OutputSpec("CONDITIONING", "CONDITIONING")],
        )


def _flat_ui() -> dict[str, Any]:
    return json.loads(
        (Path("tests/fixtures/agent_edit/flat.json")).read_text(encoding="utf-8")
    )


def test_run_execute_turn_real_edit_session_apply_then_submit(tmp_path) -> None:
    """A scripted ``edit_node`` tool call → ``submit`` runs through the REAL
    EditSession and tool dispatcher: the accepted Δ, post-edit lens facts,
    durable candidate graph, and claim_refs are all produced by the bounded loop."""
    from vibecomfy.executor.two_step import _two_step_tool_executor
    from vibecomfy.porting.edit.session import EditSession

    graph = _flat_ui()
    edit_session = EditSession(dict(graph), schema_provider=_CLIPTextEncodeProvider())
    tool_executor = _two_step_tool_executor(route="revise", edit_session=edit_session)

    actions: list[dict[str, Any]] = [
        {
            "action": "tool_call",
            "tool": "edit_node",
            "args": {"target": "cliptextencode", "field": "text", "value": "a faithful edited prompt"},
        },
        {"action": "submit", "reply": "edited", "claim_refs": {"delta_ids": ["d1"]}},
    ]

    def model_turn_fn(task, messages, **kwargs):
        action = actions.pop(0)
        return {
            "content": json.dumps(action),
            "model_attempts": [{"token_usage": {"completion_tokens": 100}}],
        }

    request = SimpleNamespace(
        query="edit the prompt",
        graph=dict(graph),
        session_id="win-real",
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )
    store = _store(tmp_path)
    outcome = run_execute_turn(
        request,
        plan=_plan_for("revise"),
        route="revise",
        spec=_spec(),
        session_store=store,
        session_id="win-real",
        model_turn_fn=model_turn_fn,
        tool_executor=tool_executor,
        edit_session=edit_session,
    )

    # The edit tool call was accepted through the real atomic runtime.
    assert outcome["ok"] is True
    assert outcome["accepted_delta_ids"] == ["d1"]
    assert outcome["claim_validation"] == {"status": "ok", "violations": []}

    # Post-edit lens facts landed (the current fact pack references the edited
    # candidate graph).
    assert outcome["lens_fact_ids"], "post-edit lens facts must be recorded"

    # The durable candidate graph reflects the landed edit.
    assert outcome["graph"] is not None
    edited = [
        n
        for n in outcome["graph"].get("nodes", [])
        if n.get("type") == "CLIPTextEncode"
    ]
    assert any(
        "a faithful edited prompt" in (n.get("widgets_values") or ()) for n in edited
    )

    # The accepted Δ is durable session state a follow-up message may cite.
    state = store.load("win-real")
    assert state is not None
    assert state.accepted_delta_ids() == ("d1",)


# ── RC1 / RC2: truncation retry + graceful degradation ───────────────────────


def test_truncation_continues_instead_of_failing_closed(tmp_path) -> None:
    """RC1: a provider ``finish_reason=length`` is retryable — the loop records
    the truncated output as a continuation and re-invokes the model with the
    accumulated transcript, instead of failing with a placeholder reply."""
    store = _store(tmp_path)
    calls: list[list[dict]] = []

    def model_turn_fn(task, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            # Provider cut the model off mid-action before a valid JSON object.
            return {
                "content": '{"action": "tool_call", "tool": "node_schema", ',
                "finish_reason": "length",
                "model_attempts": [
                    {
                        "finish_reason": "length",
                        "token_usage": {"completion_tokens": 40},
                    }
                ],
            }
        return {
            "content": json.dumps(
                {"action": "submit", "reply": "done", "delta_ids": []}
            ),
            "model_attempts": [{"token_usage": {"completion_tokens": 100}}],
        }

    request = SimpleNamespace(
        query="inspect the node",
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
        model_turn_fn=model_turn_fn,
    )
    assert outcome["ok"] is True
    # Two model turns: the truncated one and the resumed one.
    assert len(calls) == 2
    # The resumed call's flattened transcript carries the truncated partial
    # output so the model can continue from where it was cut off.
    user_payload = calls[1][1]["content"]
    assert "assistant_partial" in user_payload
    assert "node_schema" in user_payload
    # The truncated fragment was durable session state.
    state = store.load("win-a")
    assert any(m.get("role") == "assistant_partial" for m in state.messages)


def test_truncation_degrades_gracefully_when_continuation_budget_exhausted(
    tmp_path,
) -> None:
    """RC1+RC2: when every continuation is truncated, the continuation budget
    eventually exhausts and the reply degrades gracefully — never the
    diagnostic string."""
    store = _store(tmp_path)

    def model_turn_fn(task, messages, **kwargs):
        return {
            "content": '{"action": "tool_call", "tool": "node_schema", ',
            "finish_reason": "length",
            "model_attempts": [{"finish_reason": "length"}],
        }

    request = SimpleNamespace(
        query="inspect the node",
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
        model_turn_fn=model_turn_fn,
        max_continuations=2,
    )
    assert outcome["ok"] is False
    assert getattr(outcome["failure"], "kind", None) == "stale_message"
    reply = outcome["reply"]
    assert reply is not None
    assert "ran out of budget" in reply
    # The diagnostic must never be the reply.
    assert "continuation budget" not in reply


def test_budget_denial_never_echoes_diagnostic_as_reply(tmp_path) -> None:
    """RC2: a budget denial mid-session returns a graceful partial-product
    reply — the raw diagnostic string is never the user-facing reply."""
    from vibecomfy.executor.two_step import BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST

    store = _store(tmp_path)
    outcome = _execute_turn(
        store,
        "win-a",
        query="deny me",
        route="revise",
        model_turn_fn=_scripted_model(
            {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "x"}}
        ),
    )
    assert outcome["ok"] is False
    assert outcome["failure"].family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST
    reply = outcome["reply"]
    assert reply is not None
    assert "ran out of budget" in reply
    # The diagnostic string must never leak into the reply.
    assert "route_tool_allowlist" not in reply
    assert "hivemind_search" not in reply


# ── RC-P0: _two_step_edit_session + real typed tool runtime (envelope + API) ──


def _named_widget_envelope() -> dict:
    """A minimal valid Vibe envelope whose KSampler carries named widgets."""
    return {
        "vibecomfy_format_version": "1.0",
        "id": "test-envelope",
        "source": {"id": "test-envelope", "path": None, "source_type": "test"},
        "requirements": {
            "models": [],
            "custom_nodes": [],
            "missing_models": [],
            "missing_nodes": [],
            "unsupported": [],
        },
        "metadata": {},
        "strict_types": False,
        "groups": [],
        "inputs": {},
        "outputs": [],
        "nodes": {
            "1": {
                "id": "1",
                "class_type": "EmptyLatentImage",
                "uid": "1",
                "mode": 0,
                "inputs": {},
                "widgets": {"width": 512, "height": 512, "batch_size": 1},
                "metadata": {},
            },
            "2": {
                "id": "2",
                "class_type": "KSampler",
                "uid": "2",
                "mode": 0,
                "inputs": {},
                "widgets": {
                    "seed": 42,
                    "steps": 20,
                    "cfg": 8.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
                "metadata": {},
            },
            "3": {
                "id": "3",
                "class_type": "VAEDecode",
                "uid": "3",
                "mode": 0,
                "inputs": {},
                "widgets": {},
                "metadata": {},
            },
        },
        "edges": [
            {"from_node": "1", "from_output": "0", "to_node": "2", "to_input": "latent_image"},
            {"from_node": "2", "from_output": "0", "to_node": "3", "to_input": "samples"},
        ],
    }


def _bare_api_fixture() -> dict:
    """A bare Comfy-API graph derived from the LiteGraph flat fixture."""
    from vibecomfy.ingest.normalize import normalize_to_api

    flat = json.loads(
        (Path(__file__).parent / "fixtures" / "agent_edit" / "flat.json").read_text(
            encoding="utf-8"
        )
    )
    return normalize_to_api(flat, use_comfy_converter=False)


def test_two_step_edit_session_typed_runtime_accepts_edit_for_envelope_and_api() -> None:
    """RC-P0: the real typed edit runtime accepts one edit for BOTH the
    envelope and bare-API ingest shapes, returns ``d1``, and retains the entire
    original graph plus the edit (no silent zero-node session)."""
    from vibecomfy.executor.edit_tools import EditToolRuntime
    from vibecomfy.executor.two_step import _two_step_edit_session

    # Envelope input: before the fix this decoded to zero nodes and no edit
    # could ever resolve.
    envelope_session = _two_step_edit_session(_named_widget_envelope())
    assert envelope_session is not None
    assert set(envelope_session.workflow.nodes.keys()) == {"1", "2", "3"}
    envelope_runtime = EditToolRuntime(edit_session=envelope_session)
    envelope_out = envelope_runtime.dispatch(
        "edit_node", {"target": "ksampler", "field": "seed", "value": 99}
    )
    assert envelope_out.ok is True, envelope_out.diagnostics
    assert envelope_out.delta_id == "d1"
    assert set(envelope_session.workflow.nodes.keys()) == {"1", "2", "3"}
    assert envelope_session.workflow.nodes["2"].widgets.get("seed") == 99

    # Bare-API input: the same dispatch authority must retain every node.
    api_session = _two_step_edit_session(_bare_api_fixture())
    assert api_session is not None
    api_nodes = set(api_session.workflow.nodes.keys())
    assert api_nodes
    api_runtime = EditToolRuntime(edit_session=api_session)
    api_out = api_runtime.dispatch(
        "edit_node", {"target": "cliptextencode", "field": "text", "value": "a dog"}
    )
    assert api_out.ok is True, api_out.diagnostics
    assert api_out.delta_id == "d1"
    assert set(api_session.workflow.nodes.keys()) == api_nodes
    assert api_session.workflow.nodes["2"].inputs.get("text") == "a dog"


# ── RC-P3: per-purpose continuation partitioning ─────────────────────────────
#
# One undifferentiated continuation pool (max_model_continuations=64) let
# research consume the ability to edit or answer.  Admission is now partitioned
# by purpose: research/discovery 40, edit/recovery 16, final synthesis/reply 8
# (summing to the unchanged 64 ceiling).  Research may not borrow the edit/
# reply reserve; a successful apply closes research for the message; a fresh
# budget epoch scopes an exhausted prior attempt out of the next measurement.


def _fake_tool_executor_evidence(tool: str, args: dict):
    """Tool stub returning non-empty evidence so no-result detection stays quiet."""
    return ({"e1": {"tool": tool}}, {}, f"{tool}-digest")


def _partition_request(session_id: str, graph=None):
    return SimpleNamespace(
        query="partition scenario",
        graph=graph,
        session_id=session_id,
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )


def test_research_partition_exhaustion_stops_research_and_enters_reply(tmp_path) -> None:
    """A research-heavy message exceeding 40 research continuations stops
    researching and still enters reply with budget for the answer."""
    store = _store(tmp_path)
    research_calls = {"n": 0}
    submit_calls = {"n": 0}

    def model_turn_fn(task, messages, **kwargs):
        if research_calls["n"] < 41:
            research_calls["n"] += 1
            return {
                "content": json.dumps(
                    {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "x"}}
                ),
                "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
            }
        submit_calls["n"] += 1
        return {
            "content": json.dumps({"action": "submit", "reply": "the answer", "delta_ids": []}),
            "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
        }

    outcome = run_execute_turn(
        _partition_request("win-a"),
        plan=_plan_for("adapt", research=True),
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=model_turn_fn,
        tool_executor=_fake_tool_executor_evidence,
    )
    assert outcome["ok"] is True
    assert research_calls["n"] == 41  # 40 admitted + 1 denied, then submit
    assert submit_calls["n"] == 1

    state = store.load("win-a")
    research_ledger = [e for e in state.evidence_ledger if e.get("tool") == "hivemind_search"]
    assert len(research_ledger) == 40  # the 41st research call was denied
    assert any(
        m.get("role") == "assistant_feedback" and "research" in m.get("content", "")
        for m in state.messages
    )


def test_edit_partition_does_not_starve_reply(tmp_path) -> None:
    """An edit-heavy message consumes its 16-edit reserve without starving the
    8-strong reply reserve."""
    store = _store(tmp_path)
    edit_calls = {"n": 0}
    submit_calls = {"n": 0}

    def model_turn_fn(task, messages, **kwargs):
        if edit_calls["n"] < 17:
            edit_calls["n"] += 1
            return {
                "content": json.dumps({"action": "tool_call", "tool": "edit_node", "args": {}}),
                "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
            }
        submit_calls["n"] += 1
        return {
            "content": json.dumps({"action": "submit", "reply": "edited", "delta_ids": []}),
            "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
        }

    outcome = run_execute_turn(
        _partition_request("win-a"),
        plan=_plan_for("adapt"),
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=model_turn_fn,
    )
    assert outcome["ok"] is True
    assert edit_calls["n"] == 17  # 16 admitted + 1 denied, then submit
    assert submit_calls["n"] == 1

    state = store.load("win-a")
    edit_ledger = [e for e in state.evidence_ledger if e.get("tool") == "edit_node"]
    assert len(edit_ledger) == 16  # the 17th edit call was denied by the edit partition
    assert any(
        m.get("role") == "assistant_feedback" and "edit" in m.get("content", "")
        for m in state.messages
    )


def test_research_cannot_borrow_edit_reserve(tmp_path) -> None:
    """A message that exhausts research can still perform the edit from the
    separate edit reserve (research never borrows edit/reply)."""
    store = _store(tmp_path)
    stage = {"n": 0}

    def model_turn_fn(task, messages, **kwargs):
        n = stage["n"]
        stage["n"] += 1
        if n < 41:
            return {
                "content": json.dumps(
                    {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "x"}}
                ),
                "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
            }
        if n == 41:
            return {
                "content": json.dumps({"action": "tool_call", "tool": "edit_node", "args": {}}),
                "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
            }
        return {
            "content": json.dumps({"action": "submit", "reply": "edited", "delta_ids": []}),
            "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
        }

    outcome = run_execute_turn(
        _partition_request("win-a"),
        plan=_plan_for("adapt", research=True),
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=model_turn_fn,
        tool_executor=_fake_tool_executor_evidence,
    )
    assert outcome["ok"] is True
    state = store.load("win-a")
    research_n = len([e for e in state.evidence_ledger if e.get("tool") == "hivemind_search"])
    edit_n = len([e for e in state.evidence_ledger if e.get("tool") == "edit_node"])
    assert research_n == 40
    assert edit_n == 1  # the edit came from the separate edit reserve


def test_successful_apply_closes_research_reply_only(tmp_path) -> None:
    """After a successful apply, further research tool calls are denied
    (reply-only mode)."""
    from vibecomfy.executor.two_step import _two_step_tool_executor  # noqa: PLC0415
    from vibecomfy.porting.edit.session import EditSession  # noqa: PLC0415

    store = _store(tmp_path)
    graph = _flat_ui()
    edit_session = EditSession(dict(graph), schema_provider=_CLIPTextEncodeProvider())
    tool_executor = _two_step_tool_executor(route="adapt", edit_session=edit_session)

    actions = [
        {
            "action": "tool_call",
            "tool": "edit_node",
            "args": {"target": "cliptextencode", "field": "text", "value": "a faithful edited prompt"},
        },
        {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "post-apply research"}},
        {"action": "submit", "reply": "edited", "claim_refs": {"delta_ids": ["d1"]}},
    ]

    def model_turn_fn(task, messages, **kwargs):
        action = actions.pop(0)
        return {
            "content": json.dumps(action),
            "model_attempts": [{"token_usage": {"completion_tokens": 100}}],
        }

    outcome = run_execute_turn(
        _partition_request("win-a", graph=dict(graph)),
        plan=_plan_for("adapt", research=True),
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=model_turn_fn,
        tool_executor=tool_executor,
        edit_session=edit_session,
    )
    assert outcome["ok"] is True
    assert outcome["accepted_delta_ids"] == ["d1"]
    state = store.load("win-a")
    # The post-apply research call was denied, never dispatched.
    assert not any(e.get("tool") == "hivemind_search" for e in state.evidence_ledger)
    assert any(
        m.get("role") == "assistant_feedback" and "research closed" in m.get("content", "")
        for m in state.messages
    )


def test_fresh_budget_epoch_scopes_out_exhausted_prior_attempt(tmp_path) -> None:
    """An exhausted prior attempt does not starve the next attempt on the same
    scenario: a fresh budget epoch folds the prior-epoch budget out."""
    store = _store(tmp_path)
    # Prior attempt exhausts the cumulative model-continuation budget.
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    budget = store.load("win-a").budget
    for _ in range(64):
        budget = budget.record_model_continuation()
    store.append("win-a", "budget", {"budget": budget.to_dict()}, turn=1)
    store.end_message("win-a", message_fingerprint="f1")
    assert store.load("win-a").budget.model_continuations == 64

    # Same scenario, fresh epoch: the exhausted prior budget is folded out.
    state = store.begin_message(
        "win-a", message_fingerprint="f2", fresh_budget_epoch=True
    )
    assert state.budget.model_continuations == 0
    assert state.budget_epoch
    store.end_message("win-a", message_fingerprint="f2")


def test_fresh_budget_epoch_turn_not_starved_by_prior_attempt(tmp_path) -> None:
    """A real execute turn with ``fresh_budget_epoch`` is not starved by an
    exhausted prior attempt on the same session id."""
    store = _store(tmp_path)
    store.begin_message("win-a", message_fingerprint="f1", base_graph={"nodes": []})
    budget = store.load("win-a").budget
    for _ in range(64):
        budget = budget.record_model_continuation()
    store.append("win-a", "budget", {"budget": budget.to_dict()}, turn=1)
    store.end_message("win-a", message_fingerprint="f1")

    outcome = run_execute_turn(
        _partition_request("win-a"),
        plan=_plan_for("revise"),
        route="revise",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=_scripted_model({"action": "submit", "reply": "ok", "delta_ids": []}),
        fresh_budget_epoch=True,
    )
    assert outcome["ok"] is True
    assert outcome["reply"] is not None


def test_repeated_no_result_research_closes_research(tmp_path) -> None:
    """Repeated no-result research transitions to a grounded reply instead of
    restarting the same search forever."""
    store = _store(tmp_path)
    calls = {"n": 0}

    def model_turn_fn(task, messages, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 4:
            return {
                "content": json.dumps(
                    {"action": "tool_call", "tool": "hivemind_search", "args": {"q": "x"}}
                ),
                "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
            }
        return {
            "content": json.dumps(
                {"action": "submit", "reply": "no results; here is the grounded answer", "delta_ids": []}
            ),
            "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
        }

    outcome = run_execute_turn(
        _partition_request("win-a"),
        plan=_plan_for("adapt", research=True),
        route="adapt",
        spec=_spec(),
        session_store=store,
        session_id="win-a",
        model_turn_fn=model_turn_fn,
        tool_executor=_fake_tool_executor,  # returns None → empty evidence
    )
    assert outcome["ok"] is True
    state = store.load("win-a")
    research_n = len([e for e in state.evidence_ledger if e.get("tool") == "hivemind_search"])
    assert research_n == 3  # only 3 no-result searches admitted; the 4th denied

