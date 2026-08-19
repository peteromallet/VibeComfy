"""RC-P2 P0 — accepted-Δ terminal projection.

The accepted Δ must survive every terminal boundary (second-apply soft stop,
host-action parse failure, budget stop) and become the sole authority for the
projected outcome.  These tests drive the REAL ``run_execute_turn`` loop with a
real edit session and a scripted model, then assert the projected fields.

Fixture: the LawNode* graph from ``tests.executor_mode_harness`` (real
``EditSession`` over an offline schema provider).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from vibecomfy.executor.agent_backend import run_execute_turn
from vibecomfy.executor.two_step_session import TwoStepSessionStore

from tests.executor_mode_harness import _law_edit_session


def _law_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "1", "type": "LawNodeA", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}], "widgets_values": []},
            {"id": "2", "type": "LawNodeB", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}], "widgets_values": []},
            {"id": "3", "type": "LawNodeC", "inputs": [{"name": "image", "type": "IMAGE", "link": 1}], "outputs": [], "widgets_values": ["before"]},
        ],
        "links": [
            [1, "1", 0, "3", 0, "IMAGE"],
            [2, "2", 0, "3", 0, "IMAGE"],
        ],
    }


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


def _request(session_id: str, graph: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        query="edit the graph",
        graph=graph,
        session_id=session_id,
        idempotency_key=None,
        expected_baseline_graph_hash=None,
    )


def _scripted_model(*actions: dict) -> Any:
    queue = [dict(a) for a in actions]

    def model_turn_fn(task, messages, **kwargs):
        action = queue.pop(0) if queue else {"action": "submit", "reply": "done", "claim_refs": {"delta_ids": []}}
        return {"content": json.dumps(action), "model_attempts": [{"token_usage": {"completion_tokens": 5}}]}

    return model_turn_fn


def _run(store: TwoStepSessionStore, session_id: str, model_turn_fn, *, graph=None) -> dict:
    return run_execute_turn(
        _request(session_id, graph or _law_graph()),
        plan=_plan(),
        route="revise",
        spec=_spec(),
        session_store=store,
        session_id=session_id,
        edit_session=_law_edit_session(graph or _law_graph()),
        model_turn_fn=model_turn_fn,
    )


def test_accepted_edit_then_second_apply_is_soft_stop(tmp_path: Path) -> None:
    """RC-P2 P0 #1: accepted edit + second apply-cap attempt returns the first
    Δ and graph with ok=true; the second attempt is recorded unapplied."""
    store = TwoStepSessionStore(tmp_path / "sessions")
    graph = _law_graph()
    outcome = _run(
        store,
        "win-soft",
        _scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "again"}},
        ),
        graph=graph,
    )
    assert outcome["ok"] is True
    assert outcome["accepted_delta_ids"] == ["d1"]
    assert outcome["graph"] is not None
    # The second apply was recorded as a soft stop, not a failure.
    assert outcome.get("failure") is None
    assert outcome.get("soft_stop") is not None
    assert outcome["soft_stop"]["family"] == "apply_batches"
    # The retained graph reflects the first edit (LawNodeC prompt → "after").
    node_c = next(n for n in outcome["graph"]["nodes"] if n.get("type") == "LawNodeC")
    assert node_c.get("widgets_values") == ["after"]


def test_accepted_edit_then_parse_failure_preserves_delta_and_graph(tmp_path: Path) -> None:
    """RC-P2 P0 #2: parse failure after an accepted edit preserves identical
    accepted ids + replayed graph; only the diagnostic/reply status differs."""
    store = TwoStepSessionStore(tmp_path / "sessions")
    graph = _law_graph()
    outcome = _run(
        store,
        "win-parse",
        _scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "bogus", "nothing": 1},  # host-action parse failure
        ),
        graph=graph,
    )
    assert outcome["ok"] is False
    assert outcome["accepted_delta_ids"] == ["d1"]
    assert outcome["graph"] is not None
    assert outcome["failure"] is not None
    # The projected graph is the replayed retained revision.
    state = store.load("win-parse")
    replayed = store.replay_workflow(state)
    assert outcome["graph"] == replayed
    assert outcome["graph"] != graph


def test_accepted_edit_then_grounding_failure_preserves_delta(tmp_path: Path) -> None:
    """RC-P2 P0 #2: grounding failure after an accepted edit preserves the
    accepted ids + graph (the failure only changes the diagnostic)."""
    store = TwoStepSessionStore(tmp_path / "sessions")
    graph = _law_graph()

    # A submit with an uncited numeric recommendation trips the grounding gate
    # after the accepted edit.
    def model_turn_fn(task, messages, **kwargs):
        return {"content": json.dumps(
            {"action": "tool_call", "tool": "edit_node",
             "args": {"target": "lawnodec", "field": "prompt", "value": "after"}}
        )}

    # First accept the edit, then drive a grounding-violating submit.
    first = run_execute_turn(
        _request("win-ground", graph),
        plan=_plan(),
        route="revise",
        spec=_spec(),
        session_store=store,
        session_id="win-ground",
        edit_session=_law_edit_session(graph),
        model_turn_fn=_scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "submit", "reply": "set denoise to 0.3", "claim_refs": {"delta_ids": [], "evidence_ids": []}},
        ),
    )
    # The grounding gate may reject the submit; either way the accepted Δ must
    # survive in the projected outcome.
    assert first["accepted_delta_ids"] == ["d1"]
    assert first["graph"] is not None
