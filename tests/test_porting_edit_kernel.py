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


def _ksampler_uid(session: EditSession) -> str:
    for node in session.workflow.nodes.values():
        if node.class_type == "KSampler":
            return str(node.uid)
    raise AssertionError("KSampler missing from fixture graph")


def _schema_pair(session: EditSession, *, extra_missing: str | None = "LayerMask: SegmentAnythingUltra V3"):
    from vibecomfy.porting.edit.admit import AdmissionSnapshot
    from vibecomfy.schema import capture_schema_snapshot

    uid = _ksampler_uid(session)
    node_classes = {uid: "KSampler"}
    class_types = ["KSampler"]
    object_info = {
        "KSampler": {
            "input": {
                "required": {
                    "steps": ["INT", {}],
                    "cfg": ["FLOAT", {}],
                    "seed": ["INT", {}],
                    "model": ["MODEL", {}],
                    "positive": ["CONDITIONING", {}],
                    "negative": ["CONDITIONING", {}],
                    "latent_image": ["LATENT", {}],
                }
            },
            "output": ["LATENT"],
        }
    }
    if extra_missing:
        class_types.append(extra_missing)
        node_classes["34"] = extra_missing
    schema = capture_schema_snapshot(
        class_types=class_types,
        connected_object_info=object_info,
        connected_object_info_verified=True,
        node_classes=node_classes,
    )
    return AdmissionSnapshot(workflow=session.workflow_snapshot, schema=schema), uid


def test_admit_operation_families_and_fail_closed_unknown_touched() -> None:
    from vibecomfy.porting.edit.admit import (
        AdmissionAllowed,
        AdmissionRejected,
        admit_operation,
        admit_operations,
    )

    session = _session()
    pair, uid = _schema_pair(session)
    families = {
        "field": {"op": "set_node_field", "target": ["", uid, "steps"], "value": 25},
        "mode": {"op": "set_mode", "target": ["", uid], "mode": 2},
        "remove": {"op": "remove_node", "target": ["", uid]},
        "layout": {"op": "set_node_geometry", "uid": uid, "pos": [1, 2], "size": [10, 10]},
        "link": {
            "op": "upsert_link",
            "from": ["", uid, 0],
            "to": ["", uid, "model"],
        },
    }
    for name, op in families.items():
        result = admit_operation(pair, op)
        assert isinstance(result, AdmissionAllowed), (name, result)
        assert result.touched_scope.class_types
        assert uid in result.touched_scope.identities or name == "layout"

    add_unknown = {"op": "add_node", "class_type": "LayerMask: SegmentAnythingUltra V3", "uid": "34"}
    layout_unknown = {"op": "set_node_geometry", "uid": "34", "pos": [0, 0], "size": [1, 1]}
    for op in (add_unknown, layout_unknown):
        rejected = admit_operation(pair, op)
        assert isinstance(rejected, AdmissionRejected)
        assert rejected.typed_reason == "missing_touched_schema"
        assert rejected.evidence_refs
        assert any("schema_snapshot:" in ref for ref in rejected.evidence_refs)

    group_op = {"op": "add_group", "id": "g1", "bounding": [0, 0, 10, 10], "title": "box", "color": None}
    assert isinstance(admit_operation(pair, group_op), AdmissionAllowed)

    mixed = admit_operations(
        pair,
        [families["field"], add_unknown],
        working_workflow=session.workflow,
    )
    assert isinstance(mixed, AdmissionRejected)
    assert mixed.typed_reason == "missing_touched_schema"


def test_rejected_proposal_never_enters_accepted_delta_or_visible_candidate() -> None:
    from vibecomfy.porting.edit.admit import AdmissionRejected, admit_operation
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    session = _session()
    pair, _uid = _schema_pair(session)
    before_ui = session.working_ui
    before_ops = tuple(session.landed_ops)
    unknown = {"op": "set_node_geometry", "uid": "34", "pos": [0, 0], "size": [8, 8]}
    result = admit_operation(pair, unknown)
    assert isinstance(result, AdmissionRejected)
    apply_result = session.apply_ops(
        [
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", "missing", "steps"),
                value=1,
            )
        ]
    )
    assert not apply_result.ok
    assert apply_result.landed_ops == ()
    assert tuple(session.landed_ops) == before_ops
    assert session.working_ui == before_ui
    assert session.history == []


def test_layout_ops_use_the_same_admit_operation_gateway() -> None:
    import inspect

    from vibecomfy.comfy_nodes.agent import layout_operation_v1
    from vibecomfy.porting.edit.admit import (
        AdmissionAllowed,
        AdmissionRejected,
        admit_operation,
    )

    session = _session()
    pair, uid = _schema_pair(session, extra_missing=None)
    ops = [
        {"op": "set_node_geometry", "uid": uid, "pos": [4, 5]},
        {"op": "add_group", "id": "g-new", "bounding": [0, 0, 20, 20], "title": "g", "color": None},
        {"op": "set_group_geometry", "id": "missing-group", "bounding": [1, 1, 2, 2]},
        {"op": "remove_group", "id": "missing-group"},
    ]
    allowed = admit_operation(pair, ops[0])
    assert isinstance(allowed, AdmissionAllowed)
    added = admit_operation(pair, ops[1], working_workflow=session.workflow)
    assert isinstance(added, AdmissionAllowed)
    missing_group = admit_operation(pair, ops[2], working_workflow=session.workflow)
    assert isinstance(missing_group, AdmissionRejected)
    assert missing_group.typed_reason == "unknown_target"

    source = inspect.getsource(layout_operation_v1._normalize_layout_op)
    assert "admit_operation" in source
    admit_fns = [
        name
        for name, obj in inspect.getmembers(layout_operation_v1, inspect.isfunction)
        if "admit" in name.lower()
    ]
    assert admit_fns == []


def test_admit_operation_does_not_mutate_snapshots() -> None:
    from copy import deepcopy

    from vibecomfy.porting.edit.admit import admit_operation

    session = _session()
    pair, uid = _schema_pair(session)
    before_workflow = deepcopy(pair.workflow.semantic_digest)
    before_schema = deepcopy(pair.schema.content_digest)
    before_classes = dict(pair.schema.node_classes)
    admit_operation(pair, {"op": "set_node_field", "target": ["", uid, "steps"], "value": 7})
    admit_operation(pair, {"op": "set_node_geometry", "uid": "34", "pos": [0, 0], "size": [1, 1]})
    assert pair.workflow.semantic_digest == before_workflow
    assert pair.schema.content_digest == before_schema
    assert dict(pair.schema.node_classes) == before_classes


def test_consumer_routing_resolves_through_one_gateway() -> None:
    import inspect

    from vibecomfy.comfy_nodes.agent import (
        _frag_response_contract,
        _v2_scoped_validation,
        authority_receipts,
        candidate_transaction,
        edit as agent_edit,
        edit_batch_repl,
        layout_operation_v1,
        session as agent_session,
    )
    from vibecomfy.executor import edit_suggestion_tools
    from vibecomfy.porting.edit import (
        _interpret,
        _op_validate,
        _parse_execute,
        apply_gate,
        lint,
        ops,
        session as edit_session,
        typed_tools,
    )

    consumers = [
        _op_validate.validate_typed_ops,
        _interpret._interpret_ops,
        _parse_execute._ParseExecuteMixin.apply_batch,
        typed_tools.apply_edit_tool_call,
        lint.lint_delta,
        apply_gate.verify_apply,
        edit_session.EditSession.apply_ops,
        ops.require_known_schema_for_operation,
        candidate_transaction.missing_touched_class_types,
        authority_receipts.recompute_apply,
        _frag_response_contract._validate_delta_evidence_for_apply,
        edit_batch_repl._publish_session_candidate,
        agent_session.record_idempotent_response,
        _v2_scoped_validation._load_turn_delta_ops,
        layout_operation_v1._normalize_layout_op,
        agent_edit._admit_operation,
        edit_suggestion_tools.rank_edit_targets,
    ]
    for consumer in consumers:
        source = inspect.getsource(consumer)
        assert "admit_operation" in source or "admit_operations" in source, consumer
