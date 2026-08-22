"""Shared-IR edit, checkpoint, replay, and claim-grounding contracts."""

from __future__ import annotations

from typing import Any

import pytest

from tests._executor_threaded_helpers import (
    THREADED_FEATURE_REQUIRED,
    edit_kernel,
    edit_session,
)


pytestmark = THREADED_FEATURE_REQUIRED


def _edit_prompt(session: Any, value: str, *, revision: int | None = None) -> Any:
    return edit_kernel.apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "lawnodec", "field": "prompt", "value": value},
        expected_revision=revision,
    )


def test_atomic_rejection_leaves_original_revision_for_one_replacement() -> None:
    session = edit_session()
    before_graph = session.working_ui
    before_source = session.render()
    invalid_ops = edit_kernel.lower_edit_tool_call(
        session,
        "edit_batch",
        {
            "ops": [
                {
                    "op": "edit_node",
                    "target": "lawnodec",
                    "field": "prompt",
                    "value": "partially applied",
                },
                {
                    "op": "edit_node",
                    "target": "lawnodec",
                    "field": "made_up",
                    "value": 1,
                },
            ]
        },
    )
    rejected = session.apply_ops(invalid_ops, expected_revision=0)
    assert rejected.ok is False
    assert rejected.reason == "unknown_field"
    assert rejected.landed_ops == ()
    assert session.revision == 0
    assert session.history == []
    assert session.working_ui == before_graph
    assert session.render() == before_source

    replacement = _edit_prompt(session, "replacement landed", revision=0)
    assert replacement.ok is True
    assert replacement.revision == 1
    assert replacement.delta_id is not None
    assert len(replacement.landed_ops) == 1
    assert len(session.history) == 1

    stale_second_edit = _edit_prompt(session, "must not land", revision=0)
    assert stale_second_edit.ok is False
    assert stale_second_edit.reason == "stale_revision"
    assert session.revision == 1
    assert len(session.history) == 1


def test_accepted_delta_and_graph_survive_later_terminal_failure() -> None:
    session = edit_session()
    accepted = _edit_prompt(session, "after", revision=0)
    assert accepted.ok is True
    checkpoint = edit_kernel.close_terminal_checkpoint(
        session,
        facts={"fact:prompt": {"uid": "3", "value": "after"}},
        evidence_ids=("evidence:LawNodeC",),
    )

    projection = checkpoint.project(
        failure="terminal reply failed",
        claims={
            "delta_ids": [checkpoint.delta_ids[0]],
            "fact_ids": ["fact:prompt"],
            "evidence_ids": ["evidence:LawNodeC"],
        },
    )
    assert projection.accepted is True
    assert projection.landed_count == 1
    assert projection.graph == accepted.graph
    assert projection.failure == "terminal reply failed"
    assert projection.terminal_state == "applied"
    staged = checkpoint.project(
        failure="terminal reply failed",
        claims={
            "delta_ids": [checkpoint.delta_ids[0]],
            "fact_ids": ["fact:prompt"],
            "evidence_ids": ["evidence:LawNodeC"],
        },
        mode="staged",
    )
    threaded = checkpoint.project(
        failure="terminal reply failed",
        claims={
            "delta_ids": [checkpoint.delta_ids[0]],
            "fact_ids": ["fact:prompt"],
            "evidence_ids": ["evidence:LawNodeC"],
        },
        mode="threaded",
    )
    assert staged.authority_fields() == threaded.authority_fields()



def test_terminal_checkpoint_isolated_from_later_session_mutation() -> None:
    session = edit_session()
    first = _edit_prompt(session, "first", revision=0)
    assert first.ok is True
    first_checkpoint = edit_kernel.close_terminal_checkpoint(
        session, facts={"fact:first": "first"}, evidence_ids=("evidence:first",)
    )
    frozen_graph = first_checkpoint.project().graph

    second = edit_kernel.apply_edit_tool_call(
        session,
        "set_node_mode",
        {"target": "lawnodeb", "mode": "bypassed"},
        expected_revision=1,
    )
    assert second.ok is True
    second_checkpoint = edit_kernel.close_terminal_checkpoint(session)

    assert first_checkpoint.revision == 1
    assert second_checkpoint.revision == 2
    assert len(first_checkpoint.delta_ids) == 1
    assert len(second_checkpoint.delta_ids) == 2
    assert first_checkpoint.project().graph == frozen_graph
    assert first_checkpoint.project().graph != second_checkpoint.project().graph

    with pytest.raises(edit_kernel.ClaimReferenceError) as cross_checkpoint:
        first_checkpoint.project(claims={"delta_ids": [second_checkpoint.delta_ids[1]]})
    assert cross_checkpoint.value.unknown == {
        "delta_ids": (second_checkpoint.delta_ids[1],)
    }


def test_replay_fidelity_reconstructs_exact_editable_ir_and_emitted_graph() -> None:
    from vibecomfy.porting.edit.apply_gate import editable_signature

    session = edit_session()
    first = _edit_prompt(session, "after", revision=0)
    assert first.ok is True
    second = edit_kernel.apply_edit_tool_call(
        session,
        "upsert_link",
        {
            "source": "lawnodeb",
            "source_output": "IMAGE",
            "target": "lawnodec",
            "target_input": "image",
        },
        expected_revision=1,
    )
    assert second.ok is True

    replayed = session.verify_delta_history(
        equality=lambda left, right: editable_signature(left)
        == editable_signature(right)
    )
    checkpoint = edit_kernel.close_terminal_checkpoint(session)
    assert editable_signature(replayed) == editable_signature(session.workflow)
    assert checkpoint.project().graph == second.graph
    assert checkpoint.landed_count == 2
    assert checkpoint.delta_ids == (first.delta_id, second.delta_id)

    identical = edit_session()
    assert _edit_prompt(identical, "after", revision=0).delta_id == first.delta_id
    assert edit_kernel.apply_edit_tool_call(
        identical,
        "upsert_link",
        {
            "source": "lawnodeb",
            "source_output": "IMAGE",
            "target": "lawnodec",
            "target_input": "image",
        },
        expected_revision=1,
    ).delta_id == second.delta_id
    assert edit_kernel.close_terminal_checkpoint(identical).project().graph == checkpoint.project().graph


@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("delta_ids", "delta:forged"),
        ("fact_ids", "fact:forged"),
        ("evidence_ids", "evidence:forged"),
    ],
)
def test_exact_claim_grounding_rejects_every_reference_outside_checkpoint(
    field: str, forged: str
) -> None:
    session = edit_session()
    accepted = _edit_prompt(session, "after", revision=0)
    assert accepted.ok is True
    checkpoint = edit_kernel.close_terminal_checkpoint(
        session,
        facts={"fact:prompt": "after"},
        evidence_ids=("evidence:LawNodeC",),
    )
    exact = checkpoint.project(
        claims={
            "delta_ids": [accepted.delta_id],
            "fact_ids": ["fact:prompt"],
            "evidence_ids": ["evidence:LawNodeC"],
        }
    )
    assert exact.claims.delta_ids == (accepted.delta_id,)
    assert exact.claims.fact_ids == ("fact:prompt",)
    assert exact.claims.evidence_ids == ("evidence:LawNodeC",)

    with pytest.raises(edit_kernel.ClaimReferenceError) as exc_info:
        checkpoint.project(claims={field: [forged]})
    assert exc_info.value.unknown == {field: (forged,)}


def test_claim_domains_are_not_interchangeable() -> None:
    session = edit_session()
    assert _edit_prompt(session, "after", revision=0).ok is True
    checkpoint = edit_kernel.close_terminal_checkpoint(
        session,
        facts={"shared-looking-id": "fact"},
        evidence_ids=("evidence:real",),
    )

    with pytest.raises(edit_kernel.ClaimReferenceError) as exc_info:
        checkpoint.project(claims={"evidence_ids": ["shared-looking-id"]})
    assert exc_info.value.unknown == {
        "evidence_ids": ("shared-looking-id",)
    }


def test_narrated_change_claims_are_grounded_to_the_exact_accepted_field() -> None:
    op = {
        "op": "set_node_field",
        "target": ["", "law-c-uid", "prompt"],
        "value": "after",
    }
    response = {
        "accepted_batch": [{"statement_index": 1, "op": op}],
        "change_details": {
            "operations": [
                {"uid": "law-c-uid", "field_path": "prompt"},
            ]
        },
    }
    assert edit_kernel is not None
    from vibecomfy.executor.contracts import validate_reply_change_claims

    assert validate_reply_change_claims(response) == []

    response["change_details"]["operations"] = [
        {"uid": "law-c-uid", "field_path": "seed"}
    ]
    violations = validate_reply_change_claims(response)
    assert len(violations) == 1
    assert "(law-c-uid, seed)" in violations[0]
    assert "not in the accepted Δ" in violations[0]


def test_threaded_fallback_consumes_closed_checkpoint_projection() -> None:
    from vibecomfy.executor import threaded as threaded_mod
    from vibecomfy.porting.edit.checkpoint import (
        close_terminal_checkpoint,
        project_terminal_checkpoint,
    )

    checkpoint = close_terminal_checkpoint(
        terminal_state="applied",
        original_graph={"nodes": [], "links": []},
        graph={"nodes": [{"id": 1}], "links": []},
        ops=({"op": "set_node_field", "target": ["", "u", "prompt"], "value": "after"},),
        admitted=__import__("vibecomfy.porting.edit.admit", fromlist=["AdmissionAllowed"]).AdmissionAllowed(),
        replay_verified=True,
    )
    projection = project_terminal_checkpoint(checkpoint, failure="reply boom")
    prose = threaded_mod._durable_projection_fallback(
        landed=False,
        reason="should-be-ignored",
        delta_ops=(),
        projection=projection,
    )
    assert projection.terminal_state == "applied"
    assert "landed" in prose.lower()


def _stamped_applied_implementation():
    from vibecomfy.executor.contracts import ImplementationResult

    original = {"nodes": [{"id": 1, "type": "KSampler"}], "links": []}
    graph = {"nodes": [{"id": 1, "type": "KSampler", "widgets_values": [25]}], "links": []}
    op = {"op": "set_node_field", "target": ["", "u", "steps"], "value": 25}
    durable = {
        "terminal_state": "applied",
        "accepted_batch": [{"statement_index": 1, "op": op}],
        "authority_receipt": {"replay_ok": True, "candidate_matches": True},
        "graph": graph,
        "original_graph": original,
        "apply_eligible": True,
        "eligibility": {"applyable": True, "reason": "applied"},
        "outcome": {"kind": "candidate"},
        "message": "The edit landed.",
    }
    result = ImplementationResult(graph=graph, message="The edit landed.", durable_response=durable)
    return original, graph, result


def test_threaded_project_on_stamped_applied_durable_does_not_raise() -> None:
    from vibecomfy.executor.core import _durable_terminal_projection

    original, graph, result = _stamped_applied_implementation()
    projection = _durable_terminal_projection(
        result, request_graph=original, reply=result.message, mode="threaded"
    )
    assert projection.terminal_state == "applied"
    assert projection.accepted is True
    assert projection.eligibility["applyable"] is True
    assert projection.graph == graph


def test_threaded_run_preserves_applied_on_projection_exception() -> None:
    from vibecomfy.executor.contracts import ExecutorRequest
    from vibecomfy.executor import threaded as threaded_mod
    from vibecomfy.executor import core as core_mod
    from tests._executor_threaded_helpers import host_ports

    original, graph, implementation = _stamped_applied_implementation()

    class _Spec:
        agent = "edit"

    def _raise_project(*_args, **_kwargs):
        raise TypeError("cannot pickle 'mappingproxy' object")

    kernel = threaded_mod.ThreadedKernel(
        resolve_spec=lambda *_args, **_kwargs: _Spec(),
        run_implement=lambda *_args, **_kwargs: implementation,
        emit_phase=lambda *_args, **_kwargs: None,
        enforce_reply_grounding=lambda reply, **_kwargs: reply,
        accepted_delta_ops=core_mod._accepted_delta_ops,
        implementation_landed_edit=lambda _result: True,
        no_candidate_reason=lambda _result: None,
    )
    request = ExecutorRequest(query="edit steps", graph=original, pipeline_mode="threaded")
    ports = host_ports()
    original_project = core_mod._durable_terminal_projection
    core_mod._durable_terminal_projection = _raise_project
    try:
        result = threaded_mod.run_threaded_executor(
            request,
            kernel=kernel,
            host_ports=ports,
            executor_id="exec-t22",
        )
    finally:
        core_mod._durable_terminal_projection = original_project
    assert result.ok is True
    assert result.graph == graph or result.graph == original
    assert "landed" in (result.reply or "").lower()




# ── T4.3: terminal projection is mode-neutral and Row-7 recoverable ──────────


def test_t43_terminal_projection_identical_across_modes() -> None:
    from vibecomfy.executor.core import _durable_terminal_projection

    original, graph, result = _stamped_applied_implementation()
    staged = _durable_terminal_projection(
        result, request_graph=original, reply=result.message, mode="staged"
    )
    threaded = _durable_terminal_projection(
        result, request_graph=original, reply=result.message, mode="threaded"
    )
    # One mode-neutral projector: identical checkpoints project identically
    # no matter which driver called it.
    assert staged.terminal_state == threaded.terminal_state == "applied"
    assert staged.graph == threaded.graph
    assert [d.ops for d in staged.accepted_delta] == [
        d.ops for d in threaded.accepted_delta
    ]
    assert dict(staged.eligibility) == dict(threaded.eligibility)
    assert staged.reason == threaded.reason


def test_t43_row7_recovery_receipt_plus_batch_is_applied_else_undetermined() -> None:
    from vibecomfy.executor.core import _durable_terminal_projection

    original = {"nodes": [{"id": 1, "type": "KSampler"}], "links": []}
    op = {"op": "set_node_field", "target": ["", "u", "steps"], "value": 25}

    receipted = _durable_terminal_projection(
        _receipted_implementation(original, op),
        request_graph=original,
        reply="done",
        mode="threaded",
    )
    assert receipted.terminal_state == "applied"
    assert receipted.eligibility["applyable"] is True

    unreceipted = _durable_terminal_projection(
        _unreceipted_implementation(original, op),
        request_graph=original,
        reply="done",
        mode="threaded",
    )
    # Missing lifecycle/receipt evidence is NEVER guessed applied (Row 7).
    assert unreceipted.terminal_state in {"undetermined", "no_candidate", "authority_rejected"}
    assert unreceipted.eligibility["applyable"] is False
    # And the staged driver derives the SAME terminal row for the same durable.
    staged_unreceipted = _durable_terminal_projection(
        _unreceipted_implementation(original, op),
        request_graph=original,
        reply="done",
        mode="staged",
    )
    assert staged_unreceipted.terminal_state == unreceipted.terminal_state


def _receipted_implementation(original: dict, op: dict):
    from vibecomfy.executor.contracts import ImplementationResult

    graph = {"nodes": [{"id": 1, "type": "KSampler", "widgets_values": [25]}], "links": []}
    return ImplementationResult(
        graph=graph,
        message="landed",
        durable_response={
            "terminal_state": "applied",
            "accepted_batch": [{"statement_index": 0, "op": op}],
            "authority_receipt": {"replay_ok": True, "candidate_matches": True},
            "graph": graph,
            "original_graph": original,
            "outcome": {"kind": "candidate"},
        },
    )


def _unreceipted_implementation(original: dict, op: dict):
    from dataclasses import replace

    receipted = _receipted_implementation(original, op)
    return replace(
        receipted,
        durable_response={
            key: value
            for key, value in receipted.durable_response.items()
            if key != "authority_receipt"
        },
    )
