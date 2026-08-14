from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from tests.execution_plan_hotshotxl_fixtures import (
    disconnected_sidecar_graph,
    hotshotxl_video_execution_plan,
    structurally_complete_video_graph,
)
from vibecomfy.comfy_nodes.agent.edit import AgentEditState
from vibecomfy.comfy_nodes.agent.execution_plan import ExecutionPlan
from vibecomfy.comfy_nodes.agent.execution_plan_runtime import (
    MALFORMED_PLAN_CONDITION_ID,
    evaluate_execution_plan_for_state,
    format_compact_plan_feedback,
    hydrate_execution_plan_from_protocol_notes,
)


def _state(tmp_path: Path) -> AgentEditState:
    turn_dir = tmp_path / "session" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    return AgentEditState(
        task="runtime plan",
        graph={},
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=tmp_path / "session",
        turn_dir=turn_dir,
        request_path=turn_dir / "request.json",
        original_ui_path=turn_dir / "original.ui.json",
        before_py_path=turn_dir / "before.py",
        after_py_path=turn_dir / "after.py",
        projection_path=turn_dir / "projection.txt",
        model_request_path=turn_dir / "model_request.json",
        model_response_path=turn_dir / "model_response.json",
        candidate_ui_path=turn_dir / "candidate.ui.json",
        messages_path=turn_dir / "messages.jsonl",
        execution_plan_path=turn_dir / "execution_plan.json",
        plan_evaluation_path=turn_dir / "plan_evaluation.json",
    )


def _failed_condition_ids(evaluation: Any) -> set[str]:
    return {
        str(condition["condition_id"])
        for condition in evaluation.failed_conditions
        if isinstance(condition, Mapping)
    }


def test_runtime_noops_cleanly_when_state_has_no_plan(tmp_path: Path) -> None:
    state = _state(tmp_path)

    update = evaluate_execution_plan_for_state(state, structurally_complete_video_graph())

    assert update.evaluation is None
    assert update.execution_plan_ref is None
    assert update.plan_evaluation_ref is None
    assert update.compact_status == {}
    assert state.execution_plan is None
    assert state.plan_evaluation is None
    assert not state.execution_plan_path.exists()
    assert not state.plan_evaluation_path.exists()


def test_runtime_updates_state_artifacts_and_feedback_for_sidecar_failure(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.execution_plan = hotshotxl_video_execution_plan()

    update = evaluate_execution_plan_for_state(state, disconnected_sidecar_graph())

    assert update.evaluation is state.plan_evaluation
    assert state.plan_evaluation is not None
    assert state.plan_evaluation.ok is False
    assert state.plan_evaluation.blocking is True
    assert {
        "hotshotxl.8_frames",
        "hotshotxl.reaches_video_terminal",
        "video.terminal.consumes_decoded_frames",
        "video.output_domain.active",
    } <= _failed_condition_ids(state.plan_evaluation)
    assert update.execution_plan_ref is not None
    assert update.plan_evaluation_ref is not None
    assert json.loads(state.execution_plan_path.read_text(encoding="utf-8"))["plan_id"] == "hotshotxl-video"
    persisted = json.loads(state.plan_evaluation_path.read_text(encoding="utf-8"))
    assert persisted["contract_version"] == "plan_evaluation_v1"
    assert persisted["ok"] is False
    assert update.compact_status is not None
    assert update.compact_status["failed_condition_ids"]
    assert "hotshotxl.8_frames" in format_compact_plan_feedback(
        state.execution_plan,
        state.plan_evaluation,
    )


def test_runtime_accepts_complete_hotshotxl_graph_and_persists_pass(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.execution_plan = hotshotxl_video_execution_plan()

    update = evaluate_execution_plan_for_state(state, structurally_complete_video_graph())

    assert state.plan_evaluation is not None
    assert state.plan_evaluation.ok is True
    assert state.plan_evaluation.blocking is False
    assert state.plan_evaluation.failed_conditions == ()
    assert update.compact_status is not None
    assert update.compact_status["ok"] is True
    persisted = json.loads(state.plan_evaluation_path.read_text(encoding="utf-8"))
    assert persisted["feedback"] == "plan evaluation passed."


def test_runtime_fails_closed_for_unsupported_plan_version(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.execution_plan = replace(
        hotshotxl_video_execution_plan(),
        contract_version="execution_plan_v99",
    )

    evaluate_execution_plan_for_state(state, structurally_complete_video_graph())

    assert state.plan_evaluation is not None
    assert state.plan_evaluation.ok is False
    assert state.plan_evaluation.blocking is True
    assert _failed_condition_ids(state.plan_evaluation) == {"execution_plan_contract_version"}
    persisted = json.loads(state.plan_evaluation_path.read_text(encoding="utf-8"))
    assert persisted["failed_conditions"][0]["condition_id"] == "execution_plan_contract_version"


def test_runtime_fails_closed_for_malformed_supported_plan_payload(tmp_path: Path) -> None:
    state = _state(tmp_path)
    hydrate_execution_plan_from_protocol_notes(
        state,
        {
            "execution_plan": {
                "plan": {
                    "contract_version": "execution_plan_v1",
                    "plan_id": "empty-plan",
                }
            }
        },
    )

    update = evaluate_execution_plan_for_state(state, structurally_complete_video_graph())

    assert state.execution_plan == ExecutionPlan(
        plan_id="empty-plan",
        contract_version="execution_plan_v1",
    )
    assert state.plan_evaluation is not None
    assert state.plan_evaluation.ok is False
    assert state.plan_evaluation.blocking is True
    assert _failed_condition_ids(state.plan_evaluation) == {MALFORMED_PLAN_CONDITION_ID}
    assert update.compact_status is not None
    assert update.compact_status["feedback"] == (
        "plan evaluation blocked: malformed execution plan payload."
    )


def test_runtime_advisory_step_miss_does_not_block(tmp_path: Path) -> None:
    """B3: a missing advisory plan step yields a diagnostic, never a block."""
    from vibecomfy.comfy_nodes.agent.execution_plan import (
        PlanCondition,
        PlanStep,
        plan_evaluation_blocks,
    )

    state = _state(tmp_path)
    state.execution_plan = ExecutionPlan(
        plan_id="plan.advisory",
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
                condition_id="latent.present",
                kind="required_class",
                class_type="EmptyLatentImage",
            ),
        ),
    )

    # The graph satisfies the invariant but never performs the advisory step.
    update = evaluate_execution_plan_for_state(
        state,
        {
            "nodes": [
                {
                    "id": 1,
                    "type": "EmptyLatentImage",
                    "class_type": "EmptyLatentImage",
                    "widgets_values": [512, 512, 1],
                }
            ]
        },
    )

    evaluation = state.plan_evaluation
    assert evaluation is not None
    assert evaluation.ok is True
    assert evaluation.blocking is False
    assert evaluation.failed_conditions == ()
    assert plan_evaluation_blocks(evaluation) is False
    diagnostics = list(evaluation.diagnostics)
    assert len(diagnostics) == 1
    assert diagnostics[0]["step_id"] == "S1"
    assert diagnostics[0]["kind"] == "advisory_step_miss"
    assert diagnostics[0]["severity"] == "advisory"
    assert "advisory" in evaluation.feedback
    assert update.compact_status is not None
    assert update.compact_status["ok"] is True
    assert update.compact_status["blocking"] is False
    assert update.compact_status["advisory_miss_ids"] == ["S1"]
    assert update.compact_status["failed_condition_ids"] == []
    persisted = json.loads(state.plan_evaluation_path.read_text(encoding="utf-8"))
    assert persisted["diagnostics"][0]["kind"] == "advisory_step_miss"
    assert persisted["ok"] is True
    assert persisted["blocking"] is False


def test_runtime_invariant_failure_still_blocks(tmp_path: Path) -> None:
    """B3: failed declared safety/invariant conditions still block done()."""
    from vibecomfy.comfy_nodes.agent.execution_plan import (
        PlanCondition,
        PlanStep,
        plan_evaluation_blocks,
    )

    state = _state(tmp_path)
    state.execution_plan = ExecutionPlan(
        plan_id="plan.invariant",
        required_steps=(
            PlanStep(
                step_id="S1",
                kind="add_node",
                criticality="required",
                class_type="KSampler",
                conditions=(
                    PlanCondition(
                        condition_id="sampler.present",
                        kind="required_class",
                        class_type="KSampler",
                    ),
                ),
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

    update = evaluate_execution_plan_for_state(state, {})

    evaluation = state.plan_evaluation
    assert evaluation is not None
    assert evaluation.ok is False
    assert evaluation.blocking is True
    assert plan_evaluation_blocks(evaluation) is True
    assert {"sampler.present"} <= {
        str(condition["condition_id"]) for condition in evaluation.failed_conditions
    }
    assert evaluation.feedback.startswith("plan evaluation failed:")
    assert update.compact_status is not None
    assert update.compact_status["ok"] is False
    assert update.compact_status["blocking"] is True
    assert "sampler.present" in update.compact_status["failed_condition_ids"]


def test_runtime_hydrated_plan_provenance_is_enforced_advisory(tmp_path: Path) -> None:
    """B3: executor-built plans are provenance 'enforced' with enforced=false."""
    from vibecomfy.comfy_nodes.agent.execution_plan import PLAN_PROVENANCE_ENFORCED

    state = _state(tmp_path)
    hydrate_execution_plan_from_protocol_notes(
        state,
        {
            "execution_plan": {
                "plan": {
                    "contract_version": "execution_plan_v1",
                    "plan_id": "plan.executor-built",
                    "required_steps": [
                        {
                            "id": "step.sampler",
                            "kind": "add_or_bind_node",
                            "class_type": "KSampler",
                        }
                    ],
                }
            }
        },
    )

    assert state.execution_plan is not None
    assert state.execution_plan.provenance == PLAN_PROVENANCE_ENFORCED
    assert state.execution_plan.enforced is False
    assert state.execution_plan.revision_history == ()
    persisted = json.loads(state.execution_plan_path.read_text(encoding="utf-8"))
    assert persisted["provenance"] == PLAN_PROVENANCE_ENFORCED
    assert persisted["enforced"] is False
    assert persisted["revision_history"] == []


def test_runtime_agent_revision_is_recorded_with_provenance(tmp_path: Path) -> None:
    """B3: the agent can revise the plan; revision history is auditable."""
    from vibecomfy.comfy_nodes.agent.execution_plan import PLAN_PROVENANCE_AGENT_AUTHORED
    from vibecomfy.comfy_nodes.agent.execution_plan_runtime import (
        revise_execution_plan_for_state,
    )

    state = _state(tmp_path)
    hydrate_execution_plan_from_protocol_notes(
        state,
        {
            "execution_plan": {
                "plan": {
                    "contract_version": "execution_plan_v1",
                    "plan_id": "plan.revisable",
                    "required_steps": [
                        {
                            "id": "step.sampler",
                            "kind": "add_or_bind_node",
                            "class_type": "KSampler",
                        }
                    ],
                }
            }
        },
    )

    update = revise_execution_plan_for_state(
        state,
        {"required_steps": []},
        authored_by="agent",
        reason="terminal-only route; sampler not needed",
        authored_at="2026-08-14T00:00:00+00:00",
        changes={"removed_steps": ["step.sampler"]},
    )

    assert update is not None
    assert update.execution_plan_ref is not None
    assert state.execution_plan is not None
    assert state.execution_plan.provenance == PLAN_PROVENANCE_AGENT_AUTHORED
    assert state.execution_plan.enforced is False
    assert state.execution_plan.required_steps == ()
    assert len(state.execution_plan.revision_history) == 1
    revision = state.execution_plan.revision_history[0]
    assert revision.authored_by == "agent"
    assert revision.authored_at == "2026-08-14T00:00:00+00:00"
    assert revision.reason == "terminal-only route; sampler not needed"
    assert revision.changes == {"removed_steps": ("step.sampler",)}
    assert revision.provenance == PLAN_PROVENANCE_AGENT_AUTHORED
    assert revision.enforced is False

    persisted = json.loads(state.execution_plan_path.read_text(encoding="utf-8"))
    assert persisted["provenance"] == PLAN_PROVENANCE_AGENT_AUTHORED
    assert persisted["enforced"] is False
    assert persisted["required_steps"] == []
    assert persisted["revision_history"] == [
        {
            "revision_id": "rev.1",
            "authored_by": "agent",
            "authored_at": "2026-08-14T00:00:00+00:00",
            "reason": "terminal-only route; sampler not needed",
            "changes": {"removed_steps": ["step.sampler"]},
            "provenance": PLAN_PROVENANCE_AGENT_AUTHORED,
            "enforced": False,
        }
    ]

    assert update.compact_status is not None
    assert update.compact_status["provenance"] == PLAN_PROVENANCE_AGENT_AUTHORED
    assert update.compact_status["enforced"] is False
    assert update.compact_status["revision_count"] == 1
