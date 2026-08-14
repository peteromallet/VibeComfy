from __future__ import annotations

import pytest

from vibecomfy.comfy_nodes.agent.contracts import StageResult, TurnContext
from vibecomfy.comfy_nodes.agent.gates import derive_gates, initialize_gates, update_queue_gate
from vibecomfy.ingest.snapshot import capture_ingest_snapshot
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.refuse import RefusedEmit
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(
    class_type: str,
    widget_count: int,
    outputs: list[OutputSpec] | None = None,
) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={f"widget_{idx}": InputSpec("STRING") for idx in range(widget_count)},
        outputs=outputs or [],
        source_provider="test_provider",
        confidence=1.0,
    )


def _provider() -> _Provider:
    return _Provider(
        {
            "TargetNode": _schema("TargetNode", 1, [OutputSpec("OUT", "STRING")]),
            "Load3D": _schema("Load3D", 4, [OutputSpec("MESH", "MESH")]),
        }
    )


def _workflow_with_target_and_collateral_overflow() -> VibeWorkflow:
    wf = VibeWorkflow("wf", WorkflowSource("wf", None, "test"))
    wf.nodes["1"] = VibeNode(
        "1",
        "TargetNode",
        uid="uid-target",
        widgets={"widget_0": "target"},
    )
    wf.nodes["2"] = VibeNode(
        "2",
        "Load3D",
        uid="uid-collateral",
        widgets={f"widget_{idx}": f"value-{idx}" for idx in range(8)},
    )
    return wf


def test_collateral_overflow_without_recovery_path_still_refuses() -> None:
    wf = _workflow_with_target_and_collateral_overflow()

    with pytest.raises(RefusedEmit) as exc_info:
        emit_ui_json(
            wf,
            schema_provider=_provider(),
            guard_resolved_ops=({"target": {"uid": "uid-target"}},),
        )

    reasons = set(exc_info.value.diff["2"]["reasons"])
    assert "overflow" in reasons
    assert "no_prior_ui_payload" in reasons
    assert "missing_raw_widget_payload" in reasons


def test_collateral_non_benign_widget_shape_reason_still_refuses() -> None:
    wf = _workflow_with_target_and_collateral_overflow()
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)
    wf.nodes["2"].widgets["widget_0"] = "mutated"

    with pytest.raises(RefusedEmit) as exc_info:
        emit_ui_json(
            wf,
            schema_provider=_provider(),
            guard_resolved_ops=({"target": {"uid": "uid-target"}},),
        )

    reasons = set(exc_info.value.diff["2"]["reasons"])
    assert "overflow" in reasons
    assert "widget_delta" in reasons


def test_queue_validate_stage_passes_when_validate_stage_is_absent() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    assert context.gate_results["ir_validate_ok"].ok is False
    context.record_stage(
        StageResult(
            stage="queue_validate",
            ok=True,
            blocking=False,
            issues=(),
            gate_updates={"queue_validate_ok": True},
        )
    )

    blockers = update_queue_gate(context, require_probe_receipt=False)

    assert blockers == ()
    assert context.gate_results["queue_validate_ok"].ok is True
    evidence = context.gate_results["queue_validate_ok"].evidence
    assert evidence["validate_stage_present"] is False
    assert evidence["queue_validate_stage_present"] is True


def test_queue_validate_stage_still_fails_with_real_blockers() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    context.record_stage(
        StageResult(
            stage="queue_validate",
            ok=True,
            blocking=False,
            issues=(),
            gate_updates={"queue_validate_ok": True},
        )
    )

    derived = derive_gates(
        context,
        queue_blockers=({"code": "schema_less_queue_blocker", "severity": "error"},),
        require_probe_receipt=False,  # offline validation; pins explicit-blocker behavior
    )

    assert context.gate_results["queue_validate_ok"].ok is False
    assert derived.queue_blockers == ({"code": "schema_less_queue_blocker", "severity": "error"},)
