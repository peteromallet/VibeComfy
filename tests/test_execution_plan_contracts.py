from __future__ import annotations

import json

from vibecomfy.comfy_nodes.agent.execution_plan import (
    EXECUTION_PLAN_CONTRACT_VERSION,
    PLAN_EVALUATION_CONTRACT_VERSION,
    UNKNOWN_EVALUATION_VERSION_CONDITION_ID,
    UNKNOWN_PLAN_VERSION_CONDITION_ID,
    ExecutionPlan,
    PlanCondition,
    PlanEvaluation,
    PlanStep,
    RoleBinding,
    SocketRef,
    execution_plan_version_status,
    fail_closed_if_unsupported_evaluation_version,
    fail_closed_if_unsupported_plan_version,
    plan_evaluation_version_status,
)


def _assert_json_safe_and_stable(payload: dict) -> None:
    assert payload == json.loads(json.dumps(payload, sort_keys=True))
    assert json.dumps(payload, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_execution_plan_to_dict_is_deterministic_and_json_safe() -> None:
    condition = PlanCondition(
        condition_id="video.terminal",
        kind="terminal_consumes",
        criticality="critical",
        source=SocketRef(node_id="14", class_type="VAEDecode", output_name="IMAGE"),
        target=SocketRef(node_id="15", class_type="VHS_VideoCombine", input_name="images"),
        expected={"value": ("VIDEO", "IMAGE"), "field": "domain"},
        input_name="images",
        message="Video terminal must consume decoded frames.",
        details={"z": (3, 2), "a": {"tuple": ("x", "y")}},
    )
    plan = ExecutionPlan(
        plan_id="plan-hotshotxl",
        goal="Generate an 8-frame video.",
        source_graph_hash="source-hash",
        candidate_graph_hash="candidate-hash",
        research_result_hash="research-hash",
        selected_precedent_id="precedent-1",
        selected_precedent={"z": ("late",), "a": {"id": 7}},
        role_bindings=(
            RoleBinding(
                role="video_terminal",
                node_ref=SocketRef(node_id="15", class_type="VHS_VideoCombine"),
                class_type="VHS_VideoCombine",
                confidence="high",
                evidence={"z": (2, 1), "a": {"source": "fixture"}},
            ),
        ),
        required_steps=(
            PlanStep(
                step_id="S1",
                kind="add_node",
                criticality="required",
                status="planned",
                class_type="HotshotXLLoader",
                assign_to="hotshot",
                schema_source="object_info",
                runtime_availability="available",
                inputs={"z": ("motion_model",), "a": {"model": "required"}},
                values={"frames": 8},
                conditions=(condition,),
                evidence_refs=("graph-inspection",),
            ),
        ),
        done_conditions=(condition,),
        active_path_conditions=(
            PlanCondition(
                condition_id="active.video.domain",
                kind="active_output_domain",
                expected="VIDEO",
            ),
        ),
        blocked_if=(
            PlanCondition(
                condition_id="sidecar.unconsumed",
                kind="unconsumed_functional_outputs",
                criticality="required",
                class_type="HotshotXLLoader",
                expected=0,
            ),
        ),
        schema_provenance={"z": "object-info", "a": {"version": 1}},
        runtime_provenance={"z": "runtime", "a": {"adapter": "unit"}},
    )

    first = plan.to_dict()
    second = plan.to_dict()

    assert first == second
    _assert_json_safe_and_stable(first)
    assert first["contract_version"] == EXECUTION_PLAN_CONTRACT_VERSION
    assert first["plan_id"] == "plan-hotshotxl"
    assert first["source_graph_hash"] == "source-hash"
    assert first["candidate_graph_hash"] == "candidate-hash"
    assert first["research_result_hash"] == "research-hash"
    assert first["selected_precedent_id"] == "precedent-1"
    assert first["selected_precedent"] == {"a": {"id": 7}, "z": ["late"]}
    assert first["role_bindings"][0]["role"] == "video_terminal"
    assert first["role_bindings"][0]["evidence"] == {"a": {"source": "fixture"}, "z": [2, 1]}
    assert first["required_steps"][0]["criticality"] == "required"
    assert first["required_steps"][0]["status"] == "planned"
    assert first["required_steps"][0]["conditions"][0]["criticality"] == "critical"
    assert first["done_conditions"][0]["details"] == {"a": {"tuple": ["x", "y"]}, "z": [3, 2]}
    assert first["active_path_conditions"][0]["id"] == "active.video.domain"
    assert first["blocked_if"][0]["id"] == "sidecar.unconsumed"
    assert first["schema_provenance"] == {"a": {"version": 1}, "z": "object-info"}
    assert first["runtime_provenance"] == {"a": {"adapter": "unit"}, "z": "runtime"}


def test_plan_evaluation_to_dict_is_deterministic_and_json_safe() -> None:
    evaluation = PlanEvaluation(
        plan_id="plan-hotshotxl",
        ok=False,
        blocking=True,
        source_graph_hash="source-hash",
        candidate_graph_hash="candidate-hash",
        selected_precedent_id="precedent-1",
        step_status=(
            {
                "step_id": "S1",
                "kind": "add_node",
                "criticality": "required",
                "status": "failed",
                "failed_condition_ids": ("video.terminal",),
            },
        ),
        failed_conditions=(
            {
                "condition_id": "video.terminal",
                "kind": "terminal_consumes",
                "severity": "required",
                "message": "Video terminal is disconnected.",
                "evidence": {"edge_count": 0, "nodes": ("14", "15")},
            },
        ),
        feedback="plan evaluation failed: video.terminal.",
        schema_provenance={"z": "schema", "a": {"contract": 1}},
        runtime_provenance={"z": "runtime", "a": {"evaluator": "unit"}},
    )

    first = evaluation.to_dict()
    second = evaluation.to_dict()

    assert first == second
    _assert_json_safe_and_stable(first)
    assert first["contract_version"] == PLAN_EVALUATION_CONTRACT_VERSION
    assert first["plan_id"] == "plan-hotshotxl"
    assert first["ok"] is False
    assert first["blocking"] is True
    assert first["source_graph_hash"] == "source-hash"
    assert first["candidate_graph_hash"] == "candidate-hash"
    assert first["selected_precedent_id"] == "precedent-1"
    assert first["step_status"] == [
        {
            "criticality": "required",
            "failed_condition_ids": ["video.terminal"],
            "kind": "add_node",
            "status": "failed",
            "step_id": "S1",
        }
    ]
    assert first["failed_conditions"][0]["condition_id"] == "video.terminal"
    assert first["failed_conditions"][0]["severity"] == "required"
    assert first["failed_conditions"][0]["evidence"] == {"edge_count": 0, "nodes": ["14", "15"]}
    assert first["feedback"] == "plan evaluation failed: video.terminal."
    assert first["schema_provenance"] == {"a": {"contract": 1}, "z": "schema"}
    assert first["runtime_provenance"] == {"a": {"evaluator": "unit"}, "z": "runtime"}


def test_unknown_newer_versions_fail_closed() -> None:
    plan = ExecutionPlan(
        plan_id="future-plan",
        source_graph_hash="source-hash",
        candidate_graph_hash="candidate-hash",
        selected_precedent_id="precedent-1",
        schema_provenance={"schema": "future"},
        runtime_provenance={"runtime": "future"},
        contract_version="execution_plan_v2",
    )

    assert execution_plan_version_status(plan.contract_version) == "newer"
    plan_result = fail_closed_if_unsupported_plan_version(plan, candidate_graph_hash="actual-hash")
    assert plan_result is not None
    plan_payload = plan_result.to_dict()
    assert plan_payload["ok"] is False
    assert plan_payload["blocking"] is True
    assert plan_payload["candidate_graph_hash"] == "actual-hash"
    assert plan_payload["selected_precedent_id"] == "precedent-1"
    assert plan_payload["failed_conditions"][0]["condition_id"] == UNKNOWN_PLAN_VERSION_CONDITION_ID
    assert "execution_plan_v2" in plan_payload["failed_conditions"][0]["message"]
    assert plan_payload["feedback"].startswith("plan evaluation blocked")
    _assert_json_safe_and_stable(plan_payload)

    evaluation = PlanEvaluation(
        plan_id="future-plan",
        ok=True,
        blocking=False,
        source_graph_hash="source-hash",
        candidate_graph_hash="candidate-hash",
        selected_precedent_id="precedent-1",
        step_status=({"step_id": "S1", "status": "satisfied"},),
        contract_version="plan_evaluation_v2",
    )

    assert plan_evaluation_version_status(evaluation.contract_version) == "newer"
    evaluation_result = fail_closed_if_unsupported_evaluation_version(evaluation)
    evaluation_payload = evaluation_result.to_dict()
    assert evaluation_payload["contract_version"] == PLAN_EVALUATION_CONTRACT_VERSION
    assert evaluation_payload["ok"] is False
    assert evaluation_payload["blocking"] is True
    assert evaluation_payload["step_status"] == [{"status": "satisfied", "step_id": "S1"}]
    assert (
        evaluation_payload["failed_conditions"][0]["condition_id"]
        == UNKNOWN_EVALUATION_VERSION_CONDITION_ID
    )
    assert "plan_evaluation_v2" in evaluation_payload["failed_conditions"][0]["message"]
    assert evaluation_payload["feedback"].startswith("plan evaluation blocked")
    _assert_json_safe_and_stable(evaluation_payload)
