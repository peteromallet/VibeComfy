from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.porting.edit import (
    ClaimReferenceError,
    EditSession,
    EditToolError,
    apply_edit_tool_call,
    close_terminal_checkpoint,
    lower_edit_tool_call,
)
from vibecomfy.porting.edit.apply_gate import editable_signature


_FLAT = Path(__file__).parent / "fixtures" / "agent_edit" / "flat.json"


def _session() -> EditSession:
    return EditSession(json.loads(_FLAT.read_text(encoding="utf-8")))


def test_python_and_typed_tool_lower_to_same_canonical_delta_and_ir() -> None:
    python_session = _session()
    tool_session = _session()

    python_result = python_session.apply_batch("ksampler.steps = 25\n")
    tool_result = apply_edit_tool_call(
        tool_session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
        expected_revision=0,
    )

    assert python_result.ok and python_result.apply_eligible
    assert tool_result.ok and tool_result.revision == 1
    assert tool_result.delta_id is not None
    assert tool_result.landed_ops == python_result.landed_ops
    assert editable_signature(tool_session.workflow) == editable_signature(
        python_session.workflow
    )
    assert tool_result.graph == tool_session.working_ui
    assert close_terminal_checkpoint(tool_session).delta_ids == (
        tool_result.delta_id,
    ) == close_terminal_checkpoint(python_session).delta_ids


def test_typed_batch_is_atomic_when_one_op_is_invalid() -> None:
    session = _session()
    before = editable_signature(session.workflow)
    before_ui = session.working_ui

    ops = lower_edit_tool_call(
        session,
        "edit_batch",
        {
            "ops": [
                {"op": "edit_node", "target": "ksampler", "field": "steps", "value": 25},
                {"op": "edit_node", "target": "ksampler", "field": "made_up", "value": 1},
            ]
        },
    )
    result = session.apply_ops(ops, expected_revision=0)

    assert not result.ok
    assert result.reason == "unknown_field"
    assert result.landed_ops == ()
    assert session.history == []
    assert session.revision == 0
    assert editable_signature(session.workflow) == before
    assert session.working_ui == before_ui


def test_stale_revision_fails_closed_without_mutation() -> None:
    session = _session()
    accepted = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
        expected_revision=0,
    )
    stale = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "cfg", "value": 6.0},
        expected_revision=0,
    )

    assert accepted.ok
    assert not stale.ok and stale.reason == "stale_revision"
    assert stale.revision == session.revision == 1
    assert len(session.history) == 1


def test_unknown_schema_and_wrong_channel_are_rejected() -> None:
    session = _session()
    with pytest.raises(EditToolError, match="unknown render binding"):
        lower_edit_tool_call(
            session, "edit_node", {"target": "forged", "field": "steps", "value": 25}
        )
    with pytest.raises(EditToolError, match="non-positional"):
        lower_edit_tool_call(
            session, "edit_node", {"target": "ksampler", "field": "widget_2", "value": 25}
        )

    # KSampler's model input is a socket, not a literal widget channel.
    result = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "model", "value": "forged"},
        expected_revision=0,
    )
    assert not result.ok
    assert result.reason in {"wrong_channel", "unknown_field"}
    assert session.history == []


def test_closed_checkpoint_preserves_accepted_delta_on_later_failure() -> None:
    session = _session()
    accepted = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
        expected_revision=0,
    )
    assert accepted.ok
    checkpoint = close_terminal_checkpoint(
        session,
        facts={"fact:steps": {"uid": "5", "value": 25}},
        evidence_ids=("evidence:node-schema:KSampler",),
    )

    projection = checkpoint.project(
        failure="reply continuation failed",
        claims={
            "delta_ids": [checkpoint.delta_ids[0]],
            "fact_ids": ["fact:steps"],
            "evidence_ids": ["evidence:node-schema:KSampler"],
        },
    )
    assert projection.accepted
    assert projection.landed_count == 1
    assert projection.graph == accepted.graph
    assert projection.failure == "reply continuation failed"


@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("delta_ids", "delta:forged"),
        ("fact_ids", "fact:forged"),
        ("evidence_ids", "evidence:forged"),
    ],
)
def test_closed_checkpoint_rejects_forged_claim_references(field: str, forged: str) -> None:
    session = _session()
    result = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
    )
    assert result.ok
    checkpoint = close_terminal_checkpoint(
        session, facts={"fact:steps": 25}, evidence_ids=("evidence:real",)
    )

    with pytest.raises(ClaimReferenceError) as exc_info:
        checkpoint.project(claims={field: [forged]})
    assert exc_info.value.unknown[field] == (forged,)


def test_rollback_advances_revision_to_prevent_aba() -> None:
    session = _session()
    result = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 25},
        expected_revision=0,
    )
    assert result.ok and session.revision == 1
    assert session.rollback()
    assert session.revision == 2
    stale = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 30},
        expected_revision=0,
    )
    assert not stale.ok and stale.reason == "stale_revision"
