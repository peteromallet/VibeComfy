"""Focused custody regressions for published edit-operation reports."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from vibecomfy.porting.edit._session_types import (
    ApplyOpsResult,
    BatchResult,
    CompactDiagnostic,
    OperationTransition,
    StatementResult,
)
from vibecomfy.porting.edit.checkpoint import accepted_delta_id
from vibecomfy.porting.edit.lint import LintResult
from vibecomfy.porting.edit.ops import (
    NodeFieldTarget,
    SetNodeFieldOp,
    canonical_op_to_dict,
)


def _aggregate_op(value: object) -> SetNodeFieldOp:
    return SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "node", "value"),
        value=value,
    )


def test_apply_result_detaches_diff_literal_and_keeps_wire_shape() -> None:
    authored = ["new", {"nested": [1]}]
    op = _aggregate_op(authored)
    result = ApplyOpsResult(ok=True, landed_ops=(op,))

    authored[1]["nested"].append(2)  # type: ignore[index]
    assert canonical_op_to_dict(result.landed_ops[0])["value"] == [
        "new",
        {"nested": [1]},
    ]
    assert json.loads(json.dumps(canonical_op_to_dict(result.landed_ops[0]))) == {
        "op": "set_node_field",
        "target": ["", "node", "value"],
        "value": ["new", {"nested": [1]}],
    }
    with pytest.raises(AttributeError):
        result.landed_ops[0].value[1]["nested"].append(2)  # type: ignore[index]
    with pytest.raises(TypeError):
        list.append(
            result.landed_ops[0].value[1]["nested"], 2
        )  # type: ignore[arg-type,index]


def test_batch_result_and_apply_result_do_not_share_mutable_operation_payloads() -> None:
    source = ([1],)
    op = _aggregate_op(source)
    batch = BatchResult(
        ok=True,
        landed_ops=(op,),
        lint_result=LintResult((), (), ()),
    )
    applied = ApplyOpsResult(ok=True, landed_ops=batch.landed_ops)

    assert batch.landed_ops[0] == applied.landed_ops[0]
    assert batch.landed_ops[0] is not applied.landed_ops[0]
    with pytest.raises(AttributeError):
        batch.landed_ops[0].value[0].append(2)  # type: ignore[index]
    with pytest.raises(TypeError):
        list.append(batch.landed_ops[0].value[0], 2)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        applied.landed_ops[0].value[0].append(2)  # type: ignore[index]
    with pytest.raises(TypeError):
        list.append(applied.landed_ops[0].value[0], 2)  # type: ignore[arg-type]


def test_lint_surviving_freezes_list_nested_inside_tuple_payload() -> None:
    source = ([1],)
    op = _aggregate_op(source)
    result = LintResult(surviving=(op,), issues=(), normalizations=())

    source[0].append(2)
    assert result.surviving[0].value == ((1,),)
    with pytest.raises(AttributeError):
        result.surviving[0].value[0].append(2)  # type: ignore[index]
    with pytest.raises(TypeError):
        list.append(result.surviving[0].value[0], 2)  # type: ignore[arg-type]


def test_transition_report_detaches_nested_submitted_payload() -> None:
    source = {"nested": ([1],)}
    transition = OperationTransition(0, submitted=source)

    source["nested"][0].append(2)  # type: ignore[index]
    assert transition.submitted["nested"] == ((1,),)
    with pytest.raises(AttributeError):
        transition.submitted["nested"][0].append(2)  # type: ignore[index]
    with pytest.raises(TypeError):
        list.append(transition.submitted["nested"][0], 2)  # type: ignore[arg-type]


def test_statement_and_transition_shells_and_nested_diagnostics_are_immutable() -> None:
    from vibecomfy.comfy_nodes.agent._frag_chat import _json_safe

    diagnostic_source = {"nested": [{"values": [1]}]}
    detail_source = {"nested": [{"values": [2]}]}
    diagnostic = CompactDiagnostic(
        "probe",
        "probe",
        detail=diagnostic_source,
    )
    statement = StatementResult(
        statement_index=0,
        source="probe()",
        ok=True,
        diagnostics=(diagnostic,),
        detail=detail_source,
    )
    batch = BatchResult(
        ok=True,
        statements=(statement,),
        lint_result=LintResult((), (), ()),
    )
    transition = OperationTransition(
        0,
        submitted={"nested": [3]},
        diagnostics=(diagnostic,),
    )
    applied = ApplyOpsResult(ok=True, diagnostics=(diagnostic,))

    diagnostic_source["nested"][0]["values"].append(9)
    detail_source["nested"][0]["values"].append(9)
    assert batch.statements[0].diagnostics[0].detail["nested"][0]["values"] == (1,)
    assert batch.statements[0].detail["nested"][0]["values"] == (2,)
    assert json.loads(json.dumps(_json_safe(batch.statements[0].detail))) == {
        "nested": [{"values": [2]}]
    }

    with pytest.raises(FrozenInstanceError):
        batch.statements[0].ok = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        batch.ok = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        applied.ok = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        transition.outcome = "staged"  # type: ignore[misc]
    with pytest.raises(TypeError):
        batch.statements[0].detail["new"] = "value"  # type: ignore[index]
    with pytest.raises(AttributeError):
        batch.statements[0].diagnostics[0].detail["nested"].append("alias")
    with pytest.raises(TypeError):
        list.append(
            batch.statements[0].diagnostics[0].detail["nested"],
            "alias",
        )  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        transition.submitted["nested"][0] = 4  # type: ignore[index]


def test_freezing_canonical_ops_preserves_delta_identity() -> None:
    op = _aggregate_op(["new", {"nested": [1]}])
    expected = accepted_delta_id((op,))
    result = ApplyOpsResult(ok=True, landed_ops=(op,))

    assert accepted_delta_id(result.landed_ops) == expected
    assert canonical_op_to_dict(result.landed_ops[0])["value"] == [
        "new",
        {"nested": [1]},
    ]
