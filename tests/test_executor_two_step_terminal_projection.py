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
            {"action": "bogus", "nothing": 1},  # first malformed action → one retry
            {"action": "bogus", "nothing": 2},  # second malformed action → hard fail
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


# ── RC-P6 P0 — canonical landed-count projection ─────────────────────────────
#
# ``change_details.landed_operation_count`` is DERIVED from ``accepted_batch``
# (the sole durable Δ) in ``TerminalProduct.to_outcome_dict()``.  It is never a
# caller-supplied claim: a stale positive count from a caller is overwritten by
# ``len(accepted_batch)``, and an empty batch emits 0.  Every terminal path
# (success, budget stop, grounding failure, parse failure) projects the SAME
# count for the same batch.


from vibecomfy.executor.two_step_session import (  # noqa: E402
    TerminalProduct,
    terminal_durable_response,
)


def _terminal_product(*, batch: tuple[dict, ...], durable_response=None) -> TerminalProduct:
    return TerminalProduct(
        ok=True,
        route="revise",
        reply="done",
        accepted_delta_ids=tuple(str(i.get("delta_id")) for i in batch if i.get("delta_id")),
        accepted_batch=batch,
        durable_response=durable_response,
    )


def test_landed_count_derives_from_batch_size() -> None:
    """One accepted Δ carrying one op ⇒ 1; one Δ carrying two ops ⇒ 2."""
    one_op = ({"op": {"op": "set_node_field", "target": ["", "1", "p"], "value": 1}, "delta_id": "d1", "turn": 1},)
    two_ops = (
        {
            "op": {"op": "set_node_field", "target": ["", "1", "p"], "value": 1},
            "delta_id": "d1",
            "turn": 1,
        },
        {
            "op": {"op": "set_node_field", "target": ["", "1", "q"], "value": 2},
            "delta_id": "d1",
            "turn": 1,
        },
    )
    assert terminal_durable_response(_terminal_product(batch=one_op))["change_details"][
        "landed_operation_count"
    ] == 1
    assert terminal_durable_response(_terminal_product(batch=two_ops))["change_details"][
        "landed_operation_count"
    ] == 2


def test_landed_count_overwrites_stale_caller_count_and_emits_zero_when_empty() -> None:
    """A caller-supplied count is derived metadata, never an independent claim."""
    stale = {
        "reply": "done",
        "session_id": "s",
        "route": "revise",
        "change_details": {"landed_operation_count": 99, "note": "preserved"},
    }
    # Empty batch ⇒ 0, and the stale positive count cannot survive.
    empty = terminal_durable_response(_terminal_product(batch=(), durable_response=stale))
    assert empty["change_details"]["landed_operation_count"] == 0
    assert empty["change_details"]["note"] == "preserved"
    # Non-empty batch overwrites the caller's 99 with the derived 1.
    one_op = ({"op": {"op": "set_node_field", "target": ["", "1", "p"], "value": 1}, "delta_id": "d1", "turn": 1},)
    derived = terminal_durable_response(_terminal_product(batch=one_op, durable_response=stale))
    assert derived["change_details"]["landed_operation_count"] == 1
    assert derived["change_details"]["note"] == "preserved"


def test_outcome_dict_projects_landed_count() -> None:
    """``to_outcome_dict()`` exposes the projection, not the caller's raw dict."""
    one_op = ({"op": {"op": "set_node_field", "target": ["", "1", "p"], "value": 1}, "delta_id": "d1", "turn": 1},)
    product = _terminal_product(
        batch=one_op,
        durable_response={"reply": "done", "change_details": {"landed_operation_count": 7}},
    )
    payload = product.to_outcome_dict()
    assert payload["durable_response"]["change_details"]["landed_operation_count"] == 1
    assert payload["accepted_delta_ids"] == ["d1"]
    assert payload["accepted_batch"] == [dict(one_op[0])]


def test_loop_success_and_parse_failure_project_same_landed_count(tmp_path: Path) -> None:
    """Success and host-action parse failure project the SAME count for the same
    accepted batch (invariant 4)."""
    store = TwoStepSessionStore(tmp_path / "sessions")
    graph = _law_graph()
    success = _run(
        store,
        "win-count",
        _scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "submit", "reply": "done", "claim_refs": {"delta_ids": ["d1"]}},
        ),
        graph=graph,
    )
    assert success["ok"] is True
    assert success["durable_response"]["change_details"]["landed_operation_count"] == 1

    parse_fail = _run(
        store,
        "win-count-parse",
        _scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "bogus", "nothing": 1},
            {"action": "bogus", "nothing": 2},
        ),
        graph=graph,
    )
    assert parse_fail["ok"] is False
    assert parse_fail["accepted_delta_ids"] == ["d1"]
    assert parse_fail["durable_response"]["change_details"]["landed_operation_count"] == 1


def test_single_malformed_host_action_retries_once_then_submits(tmp_path: Path) -> None:
    """RC-P6 P1: ONE malformed host action is retried (bounded) before a terminal
    submit exists; the next model output may submit and land the accepted Δ."""
    store = TwoStepSessionStore(tmp_path / "sessions")
    graph = _law_graph()
    outcome = _run(
        store,
        "win-parse-retry",
        _scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "bogus", "nothing": 1},  # retried, not fatal
            {"action": "submit", "reply": "done", "claim_refs": {"delta_ids": ["d1"]}},
        ),
        graph=graph,
    )
    assert outcome["ok"] is True
    assert outcome["accepted_delta_ids"] == ["d1"]
    assert outcome["durable_response"]["change_details"]["landed_operation_count"] == 1


def test_executor_result_to_dict_consistent_landed_count(tmp_path: Path) -> None:
    """End-to-end: ``ExecutorResult.to_dict()`` carries top-level accepted_batch,
    derived accepted_delta_ids, and change_details.landed_operation_count that
    are all mutually consistent (invariant 5)."""
    from vibecomfy.executor.contracts import (
        ClassifyDecision,
        ExecuteReport,
        ExecutorResult,
        ImplementationResult,
        Report,
    )

    store = TwoStepSessionStore(tmp_path / "sessions")
    outcome = _run(
        store,
        "win-e2e",
        _scripted_model(
            {"action": "tool_call", "tool": "edit_node", "args": {"target": "lawnodec", "field": "prompt", "value": "after"}},
            {"action": "submit", "reply": "done", "claim_refs": {"delta_ids": ["d1"]}},
        ),
    )
    assert outcome["accepted_delta_ids"] == ["d1"]

    durable_response = outcome["durable_response"]
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision.edit(route="revise", plan_summary="summary"),
            pipeline_mode="two_step",
            implementation=ImplementationResult(
                graph=outcome["graph"],
                message=str(outcome["reply"] or ""),
                durable_response=durable_response,
            ),
            execute=ExecuteReport(
                session_id="win-e2e",
                route="revise",
                accepted_delta_ids=tuple(outcome["accepted_delta_ids"]),
                accepted_batch=tuple(dict(i) for i in outcome["accepted_batch"]),
            ),
        ),
        graph=outcome["graph"],
        reply=outcome["reply"],
    )
    payload = result.to_dict()
    assert payload["change_details"]["landed_operation_count"] == 1
    assert payload["accepted_delta_ids"] == ["d1"]
    assert payload["accepted_batch"] == [dict(i) for i in outcome["accepted_batch"]]
    assert len(payload["accepted_batch"]) == payload["change_details"]["landed_operation_count"]
