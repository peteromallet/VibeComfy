from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from execution_plan_hotshotxl_fixtures import (
    disconnected_sidecar_graph,
    hotshotxl_video_execution_plan,
    missing_active_8_frame_path_graph,
    missing_connected_video_terminal_graph,
    structurally_complete_video_graph,
)
from vibecomfy.comfy_nodes.agent.execution_plan import PlanEvaluation, evaluate_execution_plan


def _evaluate_hotshotxl_graph(graph: dict[str, Any]) -> PlanEvaluation:
    return evaluate_execution_plan(graph, hotshotxl_video_execution_plan())


def _failed_condition_ids(evaluation: PlanEvaluation) -> set[str]:
    return {str(condition["condition_id"]) for condition in evaluation.failed_conditions}


def _assert_blocked_by(evaluation: PlanEvaluation, expected_condition_ids: set[str]) -> None:
    assert evaluation.ok is False
    assert evaluation.blocking is True
    assert expected_condition_ids <= _failed_condition_ids(evaluation)
    assert evaluation.feedback.startswith("plan evaluation failed:")


def test_rejects_disconnected_animatediff_sidecar() -> None:
    evaluation = _evaluate_hotshotxl_graph(disconnected_sidecar_graph())

    _assert_blocked_by(
        evaluation,
        {
            "hotshotxl.8_frames",
            "hotshotxl.reaches_video_terminal",
            "video.terminal.consumes_decoded_frames",
            "video.output_domain.active",
        },
    )
    assert "hotshotxl.loader.present" not in _failed_condition_ids(evaluation)
    assert "animatediff.present" not in _failed_condition_ids(evaluation)


def test_rejects_missing_active_exact_8_frame_evidence() -> None:
    evaluation = _evaluate_hotshotxl_graph(missing_active_8_frame_path_graph())

    _assert_blocked_by(evaluation, {"hotshotxl.8_frames"})
    assert _failed_condition_ids(evaluation) == {"hotshotxl.8_frames"}


def test_rejects_missing_connected_vhs_video_combine() -> None:
    evaluation = _evaluate_hotshotxl_graph(missing_connected_video_terminal_graph())

    _assert_blocked_by(
        evaluation,
        {
            "hotshotxl.reaches_video_terminal",
            "video.terminal.consumes_decoded_frames",
            "video.output_domain.active",
        },
    )
    assert "hotshotxl.8_frames" not in _failed_condition_ids(evaluation)


def test_accepts_structurally_complete_hotshotxl_video_graph() -> None:
    evaluation = _evaluate_hotshotxl_graph(structurally_complete_video_graph())

    assert evaluation.ok is True
    assert evaluation.blocking is False
    assert evaluation.failed_conditions == ()
    assert evaluation.feedback == "plan evaluation passed."
