from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent.edit import (
    AgentEditState,
    _hydrate_execution_plan_from_protocol_notes,
)


def _state(tmp_path: Path) -> AgentEditState:
    turn_dir = tmp_path / "session" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    return AgentEditState(
        task="hydrate plan",
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


def test_nested_execution_plan_hydrates_state_and_persists_artifact(tmp_path: Path) -> None:
    state = _state(tmp_path)
    protocol_notes = {
        "execution_plan": {
            "plan": {
                "contract_version": "execution_plan_v1",
                "plan_id": "plan.test",
                "goal": "Add a sampler.",
                "required_steps": [
                    {
                        "id": "step.sampler",
                        "kind": "add_or_bind_node",
                        "class_type": "KSampler",
                        "conditions": [
                            {
                                "id": "sampler.present",
                                "kind": "required_class",
                                "class_type": "KSampler",
                            }
                        ],
                    }
                ],
                "done_conditions": [
                    {
                        "id": "sampler.present",
                        "kind": "required_class",
                        "class_type": "KSampler",
                    }
                ],
            }
        }
    }

    _hydrate_execution_plan_from_protocol_notes(state, protocol_notes)

    assert state.execution_plan is not None
    assert state.execution_plan.plan_id == "plan.test"
    assert state.execution_plan_path == state.turn_dir / "execution_plan.json"
    assert state.plan_evaluation is None
    assert state.plan_evaluation_path == state.turn_dir / "plan_evaluation.json"

    persisted = json.loads(state.execution_plan_path.read_text(encoding="utf-8"))
    assert persisted["plan_id"] == "plan.test"
    assert persisted["required_steps"][0]["id"] == "step.sampler"
    assert persisted["done_conditions"][0]["id"] == "sampler.present"


def test_absent_nested_execution_plan_leaves_runtime_plan_empty(tmp_path: Path) -> None:
    state = _state(tmp_path)

    _hydrate_execution_plan_from_protocol_notes(state, {"execution_plan": {"summary": "not a plan"}})

    assert state.execution_plan is None
    assert state.plan_evaluation is None
    assert not state.execution_plan_path.exists()
    assert not state.plan_evaluation_path.exists()
