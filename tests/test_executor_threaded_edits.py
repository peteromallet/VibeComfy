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
