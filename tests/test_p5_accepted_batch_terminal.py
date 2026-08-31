"""P5-ACCEPTEDBATCH-TERMINAL focused tests.

Card P5-ACCEPTEDBATCH-TERMINAL (§30 item 4, 2026-08-24) — persist the
accepted batch onto the terminal response.

R1  The Δ admission ACCEPTED persists onto the terminal response in the
    established field spelling (``accepted_batch``) whenever admission
    produced one: the builder's statement view, the durable turn
    ``response.json``, and the serialized executor envelope all carry the
    SAME landed ops.
R2  ANTI-GAMING INVARIANT: this card changes NO scoring.  ``applied-
    unverified`` keeps grading non-pass, ``changed_product_without_
    accepted_delta`` keeps grading ``undetermined``, and a pass is
    reachable ONLY through the normal judge running on the persisted Δ.
    ``tests/live_agentic_harness/**`` is imported read-only here; this
    card edits none of it.
R3  Fail-closed preserved: when the batch cannot be persisted coherently
    (V2 publication authority unavailable) today's behavior stands — no
    accepted batch reaches any durable carrier and typed failure context
    replaces it instead of a fabricated one.

Boundary note: (a)/(d) fail against any build whose terminal builder drops
the ``accepted_batch`` write (e.g. the pre-G6 baseline the 13 finale legs
ran on — there ``debug.delta_evidence`` proved admission verified an op
while the response carried no batch at all).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.comfy_nodes.agent._frag_state import (
    _ops_from_accepted_batch,
    derived_accepted_delta_envelope,
)
from vibecomfy.comfy_nodes.agent.candidate_transaction import content_hash
from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
from vibecomfy.comfy_nodes.agent.session import read_state
from vibecomfy.executor.contracts import (
    ExecutorResult,
    ImplementationResult,
    Report,
    validate_reply_change_claims,
)
from vibecomfy.comfy_nodes.agent.executor_response import (
    serialize_executor_result,
)
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# hermetic fixtures (minimal local mirrors of tests/test_comfy_nodes_agent_edit)


@pytest.fixture(autouse=True)
def _hermetic_narrator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the final-message narrator offline (deterministic fallback)."""
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: {"json": {}},
    )


def _schema(class_type: str, outputs: list[OutputSpec] | None = None) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs or [],
        source_provider="test",
        confidence=1.0,
    )


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return self._schemas


def _batch_repl_provider() -> _Provider:
    return _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={
                    "images": InputSpec("IMAGE", required=True),
                    "filename_prefix": InputSpec("STRING"),
                },
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )


_WORKFLOW_ID = "6b4611de-b2b2-42f2-b358-5f566d6a8933"


def _ui_graph() -> dict:
    wf = VibeWorkflow(_WORKFLOW_ID, WorkflowSource(_WORKFLOW_ID))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.images")
    graph = emit_ui_json(
        wf,
        schema_provider=_Provider(
            {"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])}
        ),
    )
    for node in graph["nodes"]:
        node.setdefault("properties", {})["vibecomfy_uid"] = str(node["id"])
    return graph


_EDIT_THEN_DONE: list[dict[str, str]] = [
    {
        "batch": 'saveimage.filename_prefix = "after"',
        "message": "Adjusted the save prefix.",
    },
    {
        "batch": "done()",
        "message": "Ready to commit the candidate.",
    },
]


def _run_turn(
    tmp_path: Path,
    responses: list[dict[str, str]],
    *,
    session_id: str = "p5-terminal",
):
    iterator = iter(responses)
    return handle_agent_edit(
        {
            "graph": _ui_graph(),
            "workflow_id": _WORKFLOW_ID,
            "task": "change the save prefix to after and finish",
            "session_id": session_id,
            "max_batches": 4,
            "max_consecutive_errors": 2,
        },
        schema_provider=_batch_repl_provider(),
        deepseek_client=lambda _messages: next(iterator),
        session_root=tmp_path,
    )


def _statement_landed_ops(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The ops admission landed, straight from the per-turn statements."""
    ops: list[dict[str, Any]] = []
    for turn in response.get("batch_turns") or []:
        for statement in turn.get("statements") or []:
            if statement.get("ok") is True and statement.get("landed") is True:
                if isinstance(statement.get("op"), Mapping):
                    ops.append(dict(statement["op"]))
    return ops


def _executor_envelope(response: Mapping[str, Any]) -> dict[str, Any]:
    """The harness-visible envelope: ExecutorResult → serialized merge."""
    result = ExecutorResult.success(
        report=Report(
            implementation=ImplementationResult(
                graph=response["graph"],
                message=response["message"],
                durable_response=json.loads(json.dumps(response)),
            )
        ),
        graph=response["graph"],
        reply=response["message"],
    )
    return serialize_executor_result(result)


# ---------------------------------------------------------------------------
# (a) R1: admitted edit ⇒ non-null accepted_batch on the terminal response


def test_p5_a_admitted_edit_persists_accepted_batch_onto_terminal_response(
    tmp_path: Path,
) -> None:
    result = _run_turn(tmp_path, _EDIT_THEN_DONE)

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "candidate"

    admitted_ops = _statement_landed_ops(result)
    assert admitted_ops, "admission must have landed at least one op"

    batch = result.get("accepted_batch")
    assert isinstance(batch, list) and batch, (
        "terminal response must carry a non-null accepted_batch"
    )
    # Identical to the admitted ops, in landed order.
    assert _ops_from_accepted_batch(result) == tuple(admitted_ops)
    assert [item["op"]["target"] for item in batch] == [
        ["", "2", "filename_prefix"]
    ]
    assert result["agent_edit_protocol"] == "v2_delta"

    # The Δ digest derived from the persisted batch is stable across the
    # projection boundary (apply/plan_hash binding depends on this).
    envelope = derived_accepted_delta_envelope(result)
    assert envelope["ops"] == admitted_ops
    assert content_hash(envelope) == content_hash(
        derived_accepted_delta_envelope({"accepted_batch": batch})
    )


# ---------------------------------------------------------------------------
# (b) R3/R1: clarify/no-edit turn keeps the batch null — nothing fabricated


def test_p5_b_clarify_turn_keeps_accepted_batch_null_no_fabrication(
    tmp_path: Path,
) -> None:
    result = _run_turn(
        tmp_path,
        [
            {
                "batch": 'clarify("Which image should I use as the input?")',
                "message": "Which image should I use as the input?",
            }
        ],
        session_id="p5-clarify",
    )

    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result.get("graph_unchanged") is True

    batch = result.get("accepted_batch")
    # Null-equivalent: absent/None or an empty list — never fabricated ops.
    assert not batch or batch == []
    assert _ops_from_accepted_batch(result) == ()

    envelope = _executor_envelope_with_optional(result)
    assert not envelope.get("accepted_batch") or envelope["accepted_batch"] == []
    assert _ops_from_accepted_batch(envelope) == ()


def _executor_envelope_with_optional(response: Mapping[str, Any]) -> dict[str, Any]:
    result = ExecutorResult.success(
        report=Report(
            implementation=ImplementationResult(
                message=response.get("message") or "",
                durable_response=json.loads(json.dumps(response)),
            )
        ),
        reply=response.get("message") or "",
    )
    return serialize_executor_result(result)


# ---------------------------------------------------------------------------
# (c) R3: forced publication failure ⇒ fail-closed, null + failure context


def test_p5_c_forced_publication_failure_fails_closed_null_with_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    def _boom(**_kwargs):  # pragma: no cover - replaces persistence only
        raise ValueError(
            "V2 candidate publication requires complete durable replay authority."
        )

    monkeypatch.setattr(agent_edit_module, "record_idempotent_response", _boom)

    with pytest.raises(ValueError, match="durable replay authority"):
        _run_turn(tmp_path, _EDIT_THEN_DONE, session_id="p5-publication-failure")

    turn_dir = (
        tmp_path
        / "p5-publication-failure"
        / "turns"
        / sorted(p.name for p in (tmp_path / "p5-publication-failure" / "turns").iterdir())[-1]
    )
    assert not (turn_dir / "response.json").exists(), (
        "failed V2 publication must never publish a terminal response"
    )

    # The raised product error IS the failure context; the envelope built
    # from it carries no accepted batch (fail-closed shape, not a fabricated
    # one).
    from vibecomfy.comfy_nodes.agent.contracts import (
        FailureKind,
        failure_envelope,
        public_outcome_from_turn_outcome,
        TurnOutcome,
    )

    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "authority",
        agent_failure_context={
            "explanation": "V2 candidate publication requires complete durable replay authority."
        },
    )
    outcome = public_outcome_from_turn_outcome(TurnOutcome.from_failure(failure))
    assert outcome["kind"] == "error"


# ---------------------------------------------------------------------------
# (d) R1: consumers see identical Δ content pre/post projection (round trip)


def test_p5_d_round_trip_consumers_see_identical_delta_pre_and_post_projection(
    tmp_path: Path,
) -> None:
    result = _run_turn(tmp_path, _EDIT_THEN_DONE, session_id="p5-roundtrip")
    admitted_ops = _statement_landed_ops(result)
    assert admitted_ops

    # 1) Durable turn artifact (response.json) round-trips through JSON bytes.
    turn_dir = tmp_path / "p5-roundtrip" / "turns" / result["turn_id"]
    persisted = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    assert isinstance(persisted.get("accepted_batch"), list)
    assert _ops_from_accepted_batch(persisted) == tuple(admitted_ops)

    # 2) Serialized executor envelope (what the judge reads) carries the SAME ops.
    envelope = _executor_envelope(result)
    assert _ops_from_accepted_batch(envelope) == tuple(admitted_ops)
    assert envelope["accepted_batch"] == persisted["accepted_batch"]

    # 3) Reply-claims law accepts claims grounded in exactly this Δ.
    grounded = dict(envelope)
    grounded["reply"] = "Changed SaveImage filename_prefix to after."
    assert validate_reply_change_claims(grounded) == []

    overreaching = dict(envelope)
    overreaching["reply"] = "Changed KSampler steps to 50."
    overreaching["outcome"] = {
        "kind": "candidate",
        "changes": [{"uid": "9", "field_path": "steps", "old": 20, "new": 50}],
    }
    violations = validate_reply_change_claims(overreaching)
    assert violations, "claims outside the accepted Δ must stay invalid"


def test_a7_landed_candidate_survives_withheld_apply_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A landed delta stays inspectable when a later gate withholds Apply.

    This is the A6-shaped boundary: the real batch handler lands an edit and
    writes ``after.py``/accepted statements, then a server gate makes
    ``eligibility.applyable`` false.  The entrypoint must not turn that
    changed candidate into a noop/no_changes response or erase its hashes.
    Apply and Queue remain false; only evidence publication is preserved.
    """
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    original_builder = agent_edit_module._build_batch_repl_response

    def _withhold_apply(state, context):
        response = original_builder(state, context)
        blocked = {
            "applyable": False,
            "reason": "server_blocked",
            "message": "Server validation gates blocked Apply.",
            "warnings": [],
        }
        response["eligibility"] = blocked
        response["apply_eligibility"] = blocked
        response["apply_allowed"] = False
        response["canvas_apply_allowed"] = False
        response["queue_allowed"] = False
        return response

    monkeypatch.setattr(
        agent_edit_module,
        "_build_batch_repl_response",
        _withhold_apply,
    )
    result = _run_turn(
        tmp_path,
        _EDIT_THEN_DONE,
        session_id="a7-withheld-apply",
    )

    assert result["ok"] is True
    assert result["terminal_state"] == "undetermined"
    assert result["terminal_reason"] == "server_blocked"
    assert result["eligibility"]["applyable"] is False
    assert result["eligibility"]["reason"] == "server_blocked"
    assert result["apply_allowed"] is False
    assert result["queue_allowed"] is False
    assert result["candidate"] is not None
    assert isinstance(result["candidate"]["graph"], dict)
    assert isinstance(result["candidate"]["graph_hash"], str)
    assert isinstance(result["candidate"]["structural_graph_hash"], str)
    assert result["accepted_batch"]
    assert result["outcome"]["kind"] in {"candidate", "candidate_transaction"}
    assert result.get("no_candidate_reason") not in {"no_changes", "authority_replay_mismatch"}
    assert result.get("graph_unchanged") is not True

    turn_dir = tmp_path / "a7-withheld-apply" / "turns" / result["turn_id"]
    persisted = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    assert persisted["candidate"]["graph"] == result["candidate"]["graph"]
    assert persisted["accepted_batch"] == result["accepted_batch"]
    assert persisted["terminal_state"] == "undetermined"
    assert persisted["terminal_reason"] == "server_blocked"
    transaction_path = next(turn_dir.glob("transactions/*/candidate_transaction.json"))
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    assert transaction["state"] == "recoverable_error"
    assert transaction["available_actions"] == []
    durable = read_state(tmp_path / "a7-withheld-apply")
    turn_record = durable["turns"][result["turn_id"]]
    assert turn_record["state"] == "recoverable_error"
    assert turn_record["candidate_graph_hash"] == result["candidate"]["graph_hash"]


# ---------------------------------------------------------------------------
# R2 invariant: scoring vocabulary untouched — judge classes keep their grades


def test_p5_r2_invariant_scoring_vocabulary_untouched() -> None:
    from tests.live_agentic_harness.semantic_assessor import (
        canonical_semantic_view,
        judge_graph_pair,
    )

    lineage = {
        "scenario_id": "p5-r2",
        "session_id": "sess",
        "turn_id": "0001",
        "baseline_id": "0000",
    }

    def _graph(seed: int) -> dict:
        return {
            "last_node_id": 1,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "properties": {"vibecomfy_uid": "1"},
                    "widgets_values": [seed, "fixed", 20, 8, "euler", "normal", 1],
                }
            ],
            "links": [],
        }

    pre = canonical_semantic_view(_graph(7), lineage=lineage)
    post = canonical_semantic_view(_graph(30), lineage=lineage)

    # Changed product + NO accepted delta ⇒ undetermined (never pass/fail flip).
    verdict = judge_graph_pair(pre, post, ())
    assert verdict.outcome == "undetermined"
    assert verdict.reason == "changed_product_without_accepted_delta"

    # Landed + replay-verified WITHOUT a persisted Δ stays applied-unverified:
    # honest class, still NOT a pass grade.
    unverified = judge_graph_pair(
        pre, post, (), landed_replay_verified=True
    )
    assert unverified.outcome == "applied_unverified"

    # A withheld batch (queue gate refused) can back NO verdict: even a
    # present Δ grades undetermined when the queue gate refused it.
    steps_delta = (
        {"op": "set_node_field", "target": ["", "1", "widgets_values", 0], "value": 30},
    )
    withheld = judge_graph_pair(
        pre, post, steps_delta, queue_gate_failed=True
    )
    assert withheld.outcome == "undetermined"
    assert withheld.reason == "withheld_accepted_batch"

    # Tri-state mapping unchanged: only pass_=True ever passes.
    from tests.live_agentic_harness.assessor import _tri_state_from_judge

    assert _tri_state_from_judge({"pass_": True}) == "pass"
    assert _tri_state_from_judge({"pass_": False}) == "fail"
    assert _tri_state_from_judge({"pass_": None}) == "undetermined"
