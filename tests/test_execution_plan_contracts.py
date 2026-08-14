from __future__ import annotations

import json

from vibecomfy.comfy_nodes.agent.execution_plan import (
    EXECUTION_PLAN_CONTRACT_VERSION,
    PLAN_EVALUATION_CONTRACT_VERSION,
    PLAN_PROVENANCE_AGENT_AUTHORED,
    PLAN_PROVENANCE_ENFORCED,
    UNKNOWN_EVALUATION_VERSION_CONDITION_ID,
    UNKNOWN_PLAN_VERSION_CONDITION_ID,
    ExecutionPlan,
    PlanCondition,
    PlanEvaluation,
    PlanRevision,
    PlanStep,
    RoleBinding,
    SocketRef,
    execution_plan_version_status,
    fail_closed_if_unsupported_evaluation_version,
    fail_closed_if_unsupported_plan_version,
    plan_evaluation_version_status,
    revise_execution_plan,
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


def test_execution_plan_default_provenance_is_enforced_advisory() -> None:
    plan = ExecutionPlan(plan_id="plan.executor-built")

    assert plan.provenance == PLAN_PROVENANCE_ENFORCED
    assert plan.enforced is False
    assert plan.revision_history == ()
    assert plan.is_agent_authored is False
    assert plan.supported_contract_version is True

    payload = plan.to_dict()
    _assert_json_safe_and_stable(payload)
    assert payload["provenance"] == PLAN_PROVENANCE_ENFORCED
    assert payload["enforced"] is False
    assert payload["revision_history"] == []


def test_revise_execution_plan_flips_provenance_and_records_auditable_revision() -> None:
    plan = ExecutionPlan(
        plan_id="plan.revisable",
        required_steps=(
            PlanStep(
                step_id="S1",
                kind="add_node",
                criticality="required",
                class_type="KSampler",
            ),
        ),
        done_conditions=(
            PlanCondition(
                condition_id="sampler.present",
                kind="required_class",
                class_type="KSampler",
            ),
        ),
    )

    revised = revise_execution_plan(
        plan,
        authored_by="agent",
        reason="dropped the sampler step; terminal-only route",
        authored_at="2026-08-14T00:00:00+00:00",
        changes={"removed_steps": ["S1"], "route": "terminal_only"},
        required_steps=(),
    )

    assert revised is not plan
    assert revised.plan_id == "plan.revisable"
    assert revised.required_steps == ()
    assert revised.done_conditions == plan.done_conditions
    assert revised.provenance == PLAN_PROVENANCE_AGENT_AUTHORED
    assert revised.enforced is False
    assert revised.is_agent_authored is True
    assert len(revised.revision_history) == 1
    revision = revised.revision_history[0]
    assert isinstance(revision, PlanRevision)
    assert revision.revision_id == "rev.1"
    assert revision.authored_by == "agent"
    assert revision.authored_at == "2026-08-14T00:00:00+00:00"
    assert revision.reason == "dropped the sampler step; terminal-only route"
    assert revision.changes == {"removed_steps": ("S1",), "route": "terminal_only"}
    assert revision.provenance == PLAN_PROVENANCE_AGENT_AUTHORED
    assert revision.enforced is False

    # the original plan is untouched and the revision is persisted auditably
    assert plan.provenance == PLAN_PROVENANCE_ENFORCED
    assert plan.revision_history == ()

    payload = revised.to_dict()
    _assert_json_safe_and_stable(payload)
    assert payload["provenance"] == PLAN_PROVENANCE_AGENT_AUTHORED
    assert payload["enforced"] is False
    assert payload["revision_history"] == [
        {
            "revision_id": "rev.1",
            "authored_by": "agent",
            "authored_at": "2026-08-14T00:00:00+00:00",
            "reason": "dropped the sampler step; terminal-only route",
            "changes": {"removed_steps": ["S1"], "route": "terminal_only"},
            "provenance": PLAN_PROVENANCE_AGENT_AUTHORED,
            "enforced": False,
        }
    ]


def test_revise_execution_plan_appends_to_revision_history() -> None:
    plan = ExecutionPlan(
        plan_id="plan.twice-revised",
        required_steps=(
            PlanStep(step_id="S1", kind="add_node", class_type="KSampler"),
        ),
    )
    first = revise_execution_plan(
        plan,
        authored_by="agent",
        reason="first revision",
        authored_at="2026-08-14T00:00:00+00:00",
        revision_id="rev.a",
    )
    second = revise_execution_plan(
        first,
        authored_by="agent",
        reason="second revision",
        authored_at="2026-08-14T00:00:01+00:00",
        revision_id="rev.b",
        required_steps=(),
    )

    assert [revision.revision_id for revision in second.revision_history] == ["rev.a", "rev.b"]
    assert second.provenance == PLAN_PROVENANCE_AGENT_AUTHORED
    assert second.enforced is False
    assert second.required_steps == ()


def test_plan_revision_to_dict_is_deterministic_and_json_safe() -> None:
    revision = PlanRevision(
        revision_id="rev.1",
        authored_by="agent",
        authored_at="2026-08-14T00:00:00+00:00",
        reason="adjust invariants",
        changes={"z": ("late",), "a": {"added": ["sampler.present"]}},
    )

    first = revision.to_dict()
    second = revision.to_dict()

    assert first == second
    _assert_json_safe_and_stable(first)
    assert first["revision_id"] == "rev.1"
    assert first["authored_by"] == "agent"
    assert first["changes"] == {"a": {"added": ["sampler.present"]}, "z": ["late"]}
    assert first["provenance"] == PLAN_PROVENANCE_AGENT_AUTHORED
    assert first["enforced"] is False


def test_plan_evaluation_diagnostics_serialize_deterministically() -> None:
    evaluation = PlanEvaluation(
        plan_id="plan.diagnostics",
        ok=True,
        blocking=False,
        diagnostics=(
            {
                "step_id": "S1",
                "kind": "advisory_step_miss",
                "severity": "advisory",
                "status": "planned",
            },
        ),
    )

    payload = evaluation.to_dict()
    _assert_json_safe_and_stable(payload)
    assert payload["ok"] is True
    assert payload["blocking"] is False
    assert payload["diagnostics"] == [
        {
            "step_id": "S1",
            "kind": "advisory_step_miss",
            "severity": "advisory",
            "status": "planned",
        }
    ]
