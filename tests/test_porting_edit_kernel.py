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
    from vibecomfy.comfy_nodes.agent import layout_operation_v1
    from vibecomfy.porting.edit.admit import (
        AdmissionAllowed,
        AdmissionRejected,
        admit_operation,
        rejected_ops_are_invisible,
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
    assert rejected_ops_are_invisible(missing_group) is True
    assert rejected_ops_are_invisible(allowed) is False

    normalized = layout_operation_v1._normalize_layout_op(ops[0], snapshot=pair, working_workflow=session.workflow)
    assert normalized["op"] == "set_node_geometry"
    try:
        layout_operation_v1._normalize_layout_op(ops[2], snapshot=pair, working_workflow=session.workflow)
        raise AssertionError("missing group must be rejected by the one gateway")
    except layout_operation_v1.LayoutOperationError as exc:
        assert exc.code == "unknown_target"

    admit_fns = [
        name
        for name, obj in __import__("inspect").getmembers(layout_operation_v1, __import__("inspect").isfunction)
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


def test_rejected_typed_dsl_op_does_not_land_or_commit() -> None:
    from vibecomfy.porting.edit._interpret import interpret
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    session = _session()
    pair, _uid = _schema_pair(session)
    session.schema_provider = pair.schema
    before = {node.uid: dict(node.widgets) for node in session.workflow.nodes.values()}
    rejected = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "missing-uid", "steps"),
        value=99,
    )
    result = interpret(session.workflow, (rejected,), schema_provider=session.schema_provider)
    assert result.ok is False
    assert result.landed_ops == ()
    after = {node.uid: dict(node.widgets) for node in session.workflow.nodes.values()}
    assert after == before


def test_python_source_dsl_rejected_op_mutates_nothing() -> None:
    session = _session()
    pair, _uid = _schema_pair(session)
    session.schema_provider = pair.schema
    before_sig = editable_signature(session.workflow)
    before_ops = tuple(session.landed_ops)
    result = session.apply_batch("missing_node.steps = 99\n")
    assert result.ok is False
    assert result.landed_ops == ()
    assert tuple(session.landed_ops) == before_ops
    assert editable_signature(session.workflow) == before_sig
    assert session.history == []


def test_apply_and_lint_block_every_typed_rejection() -> None:
    from vibecomfy.porting.edit.apply_gate import verify_apply
    from vibecomfy.porting.edit.lint import LintIndex, lint_delta
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    session = _session()
    pair, _uid = _schema_pair(session)
    malformed = SetNodeFieldOp(op="set_node_field", target=NodeFieldTarget("", "missing-uid", "steps"), value=1)
    unknown_layout = {"op": "set_node_geometry", "uid": "34", "pos": [0, 0], "size": [8, 8]}
    from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

    post = _cow_workflow_copy(session.workflow)
    gate = verify_apply(
        session.workflow,
        post,
        landed_ops=(malformed,),
        schema_provider=pair.schema,
    )
    assert gate.ok is False
    assert gate.apply_eligible is False
    assert gate.reason in {"unknown_target", "missing_touched_schema", "malformed_op"}

    index = LintIndex.build(session.working_ui)
    lint = lint_delta([malformed], index, schema_provider=pair.schema)
    assert lint.surviving == ()
    assert any(issue.code for issue in lint.issues)

    from vibecomfy.porting.edit.admit import AdmissionRejected, admit_operation

    rejected = admit_operation(pair, unknown_layout, working_workflow=session.workflow)
    assert isinstance(rejected, AdmissionRejected)
    layout_gate = verify_apply(
        session.workflow,
        post,
        landed_ops=(unknown_layout,),
        schema_provider=pair.schema,
    )
    assert layout_gate.ok is False


def test_snapshot_none_fails_closed_on_semantic_and_layout_paths() -> None:
    from vibecomfy.comfy_nodes.agent import layout_operation_v1
    from vibecomfy.porting.edit.admit import (
        AdmissionRejected,
        admission_snapshot_for,
        admit_operation,
        admit_operations,
    )
    from vibecomfy.porting.edit.ops import EditOpParseError, require_known_schema_for_operation

    unknown = {"op": "add_node", "class_type": "LayerMask: SegmentAnythingUltra V3", "uid": "34"}
    field = {"op": "set_node_field", "target": ["", "5", "steps"], "value": 25}
    geometry = {"op": "set_node_geometry", "uid": "5", "pos": [1, 2]}

    for op in (unknown, field, geometry):
        result = admit_operation(None, op)
        assert isinstance(result, AdmissionRejected)
        assert result.typed_reason == "missing_touched_schema"
        assert result.evidence_refs

    batch = admit_operations(None, [field])
    assert isinstance(batch, AdmissionRejected)

    try:
        layout_operation_v1._normalize_layout_op(geometry)
        raise AssertionError("layout envelope must fail closed without a snapshot")
    except layout_operation_v1.LayoutOperationError as exc:
        assert exc.code == "missing_touched_schema"

    admitted = admit_operations(admission_snapshot_for(None, None), [unknown])
    assert isinstance(admitted, AdmissionRejected)
    assert admitted.typed_reason == "missing_touched_schema"

    try:
        require_known_schema_for_operation(unknown, None)
        raise AssertionError("None snapshot must fail closed for semantic ops")
    except EditOpParseError as exc:
        assert exc.code == "missing_touched_schema"




def test_consumer_routing_is_behavioral_not_substring() -> None:
    import inspect

    from vibecomfy.comfy_nodes.agent import edit as agent_edit
    from vibecomfy.executor import edit_suggestion_tools
    from vibecomfy.porting.edit import _interpret
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    assert not hasattr(agent_edit, "_admit_operation")
    rank_source = inspect.getsource(edit_suggestion_tools.rank_edit_targets)
    assert "_ = admit_operation" not in rank_source
    apply_source = inspect.getsource(_interpret._InterpretRunner._apply)
    assert "admit_operation" in apply_source

    session = _session()
    pair, _uid = _schema_pair(session)
    session.schema_provider = pair.schema
    before_ops = tuple(session.landed_ops)
    before_sig = editable_signature(session.workflow)
    rejected = session.apply_ops(
        [
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", "missing-uid", "steps"),
                value=1,
            )
        ]
    )
    assert rejected.ok is False
    assert rejected.landed_ops == ()
    assert tuple(session.landed_ops) == before_ops
    assert editable_signature(session.workflow) == before_sig

    python = session.apply_batch(f"ksampler.made_up = 1\n")
    assert python.ok is False
    assert python.landed_ops == ()
    assert tuple(session.landed_ops) == before_ops


