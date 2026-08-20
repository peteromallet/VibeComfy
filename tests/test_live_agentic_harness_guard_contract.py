from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness.guard import guard_output_dir
from tests.harness_common import (
    DISPATCHER_FAKE,
    DISPATCHER_FAKING,
    DISPATCHER_REAL,
    FLOW_KIND_LIVE_AGENTIC_HEADLESS,
    MODEL_BEHAVIOR_AGENTIC,
    MODEL_BEHAVIOR_DETERMINISTIC,
    MODEL_BEHAVIOR_SCRIPTED,
    STATUS_BLOCKED_PREREQUISITE,
    STATUS_SUCCESS,
)


_CORRECTED_D13_EDIT_IDS = (
    "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
    "video-image-to-video-conversion-with-moonvalley-d7853c",
    "multi-3d-preview-and-image-output-workflow-d93baf",
)


def _write_flow_metadata(output_dir: Path, **overrides: object) -> None:
    metadata = {
        "flow_kind": FLOW_KIND_LIVE_AGENTIC_HEADLESS,
        "dispatcher": DISPATCHER_REAL,
        "model_behavior": MODEL_BEHAVIOR_AGENTIC,
        "status": STATUS_SUCCESS,
    }
    metadata.update(overrides)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "flow_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def _write_successful_candidate(output_dir: Path, **overrides: object) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
        "outcome": {"kind": "candidate"},
        "change_details": {"landed_operation_count": 1},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "plan_validate_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": True,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    }
    response.update(overrides)
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")


def _write_ui_pair(output_dir: Path, original: dict, candidate: dict) -> None:
    (output_dir / "original.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (output_dir / "candidate.ui.json").write_text(json.dumps(candidate), encoding="utf-8")


def _write_safe_refusal_response(
    output_dir: Path,
    *,
    kind: str = "requires_custom_nodes",
    graph_unchanged: bool = True,
) -> None:
    response: dict[str, object] = {
        "ok": True,
        "graph_unchanged": graph_unchanged,
        "outcome": {"kind": kind},
        "gates": {
            "ir_validate_ok": False,
            "lower_ok": False,
            "python_load_ok": False,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": False,
            "ui_fidelity_ok": False,
            "ui_load_safe_ok": False,
        },
        "message": "No schema-backed replacement node was found.",
    }
    if graph_unchanged:
        response["no_candidate_reason"] = "no_changes"
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")


def _desired_edit_scenario(scenario_id: str, kind: str = "requires_custom_nodes") -> dict:
    return {
        "id": scenario_id,
        "query": "set seed to 42",
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify", kind],
        },
        "desired": {
            "outcome": "the seed parameter is 42",
            "quality": "only the intended seed changes",
            "alternatives_ok": False,
        },
    }


def _grounded_refusal_verdict(*, grounded: bool) -> dict:
    criteria = {
        "supported_blocker": grounded,
        "no_representable_edit": grounded,
        "specific_next_action": grounded,
        "no_fabricated_inability": grounded,
    }
    return {
        "pass_": grounded,
        "criteria": criteria,
        "rationale": (
            "blocker is real and the refusal names a concrete next action"
            if grounded
            else "fabricated inability: the cited node class exists in compiled_api"
        ),
    }


def _effective_target_scenario() -> dict:
    return {
        "id": "effective-edit",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "effective_edit_targets": [
                {
                    "label": "frame_count",
                    "node_id": 2,
                    "input_name": "frame_count",
                    "widget_index": 0,
                    "source_widget_index": 0,
                }
            ],
        },
    }


def _frame_count_graph(
    *,
    source_value: int = 8,
    target_value: int = 8,
    linked: bool = True,
    shared_source: bool = False,
    save_prefix: str | None = None,
) -> dict:
    link_id = 10 if linked else None
    nodes = []
    links = []
    if linked:
        nodes.append({"id": 1, "type": "PrimitiveInt", "widgets_values": [source_value]})
        links.append([10, 1, 0, 2, 0, "INT"])
    nodes.append(
        {
            "id": 2,
            "type": "VideoGenerator",
            "widgets_values": [target_value],
            "inputs": [{"name": "frame_count", "type": "INT", "link": link_id}],
        }
    )
    if save_prefix is not None:
        nodes.append({"id": 3, "type": "SaveVideo", "widgets_values": [save_prefix]})
    if linked and shared_source:
        nodes.append(
            {
                "id": 4,
                "type": "OtherConsumer",
                "widgets_values": [target_value],
                "inputs": [{"name": "other_count", "type": "INT", "link": 11}],
            }
        )
        links.append([11, 1, 0, 4, 0, "INT"])
    return {"nodes": nodes, "links": links}


@pytest.mark.parametrize("dispatcher", [DISPATCHER_FAKE, DISPATCHER_FAKING])
def test_agentic_guard_rejects_fake_dispatchers(tmp_path: Path, dispatcher: str) -> None:
    output_dir = tmp_path / dispatcher
    _write_flow_metadata(output_dir, dispatcher=dispatcher)

    with pytest.raises(ValueError, match="fake/faking dispatcher"):
        guard_output_dir(output_dir)


@pytest.mark.parametrize("model_behavior", [MODEL_BEHAVIOR_DETERMINISTIC, MODEL_BEHAVIOR_SCRIPTED, None])
def test_agentic_guard_rejects_non_agentic_model_behavior(
    tmp_path: Path,
    model_behavior: str | None,
) -> None:
    output_dir = tmp_path / str(model_behavior)
    _write_flow_metadata(output_dir, model_behavior=model_behavior)

    with pytest.raises(ValueError, match="agentic model behavior"):
        guard_output_dir(output_dir)


def test_agentic_guard_allows_blocked_real_agentic_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "blocked"
    _write_flow_metadata(output_dir, status=STATUS_BLOCKED_PREREQUISITE)

    verdict = guard_output_dir(output_dir)

    assert verdict["live_agentic_success"] is False
    assert verdict["dispatcher"] == DISPATCHER_REAL
    assert verdict["model_behavior"] == MODEL_BEHAVIOR_AGENTIC


def test_agentic_guard_catches_unchanged_graph_and_upstream_errors(tmp_path: Path) -> None:
    """Deep assessment fails a run that reports success but produced no edit."""
    output_dir = tmp_path / "hotshot-failure"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)

    response = {
        "ok": True,
        "graph_unchanged": True,
        "no_candidate_reason": "no_changes",
        "outcome": {"kind": "requires_custom_nodes"},
        "gates": {
            "ir_validate_ok": False,
            "lower_ok": False,
            "python_load_ok": False,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": False,
            "ui_fidelity_ok": False,
            "ui_load_safe_ok": False,
        },
        "report": {
            "executor": {
                "plan": {
                    "implement": True,
                    "route": "adapt",
                },
            },
        },
        "warnings": ["hivemind: Hivemind HTTP error: HTTP Error 500: Internal Server Error"],
    }
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}),
        encoding="utf-8",
    )

    scenario = {"id": "hotshot-failure", "assessment": {"expect_graph_changed": True}}
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["metadata_success"] is True
    assert verdict["live_agentic_success"] is False
    assessment = verdict["assessment"]
    assert assessment["passed"] is False
    assert assessment["expect_graph_changed"] is True
    checks = {issue["check"] for issue in assessment["issues"] if issue["severity"] == "error"}
    assert "graph_changed" in checks
    assert "outcome_kind" in checks
    assert "upstream_failure" in checks
    assert "gates" in checks
    # G0R: the residual implementation_result prose gate is removed — the
    # "The graph is unchanged." message must not produce its own check.
    assert "implementation_result" not in checks


def test_agentic_guard_allows_explicit_safe_refusal_scenarios(tmp_path: Path) -> None:
    output_dir = tmp_path / "safe-refusal"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "clarify"},
                "gates": {
                    "ir_validate_ok": False,
                    "lower_ok": False,
                    "python_load_ok": False,
                    "queue_validate_ok": False,
                    "state_match_ok": True,
                    "ui_emit_ok": False,
                    "ui_fidelity_ok": False,
                    "ui_load_safe_ok": False,
                },
                "message": "No validated replacement node was found.",
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "No validated replacement node was found."}),
        encoding="utf-8",
    )

    scenario = {
        "id": "safe-refusal",
        "assessment": {
            "expect_graph_changed": False,
            "expected_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assessment = verdict["assessment"]
    assert assessment["passed"] is True
    assert assessment["expect_graph_changed"] is False
    assert assessment["expected_outcome_kinds"] == ["clarify", "requires_custom_nodes"]


def test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios(tmp_path: Path) -> None:
    output_dir = tmp_path / "wrong-refusal"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "message": "No changes.",
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "wrong-refusal",
        "assessment": {
            "expect_graph_changed": False,
            "expected_outcome_kind": "clarify",
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    assessment = verdict["assessment"]
    assert assessment["passed"] is False
    assert {issue["check"] for issue in assessment["issues"]} == {"outcome_kind"}


def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    output_dir = tmp_path / "edit-or-refuse"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "requires_custom_nodes"},
                "gates": {
                    "ir_validate_ok": False,
                    "lower_ok": False,
                    "python_load_ok": False,
                    "queue_validate_ok": False,
                    "state_match_ok": True,
                    "ui_emit_ok": False,
                    "ui_fidelity_ok": False,
                    "ui_load_safe_ok": False,
                },
                "message": "No schema-backed replacement node was found.",
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}),
        encoding="utf-8",
    )

    scenario = {
        "id": "edit-or-refuse",
        "query": "replace the missing custom node",
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
    )
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assessment = verdict["assessment"]
    assert assessment["passed"] is True
    assert assessment["verdict"] == "pass"
    assert assessment["expect_graph_changed"] is True
    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
    assert {"safe_refusal", "grounded_refusal"} <= {issue["check"] for issue in assessment["issues"]}


def test_desired_edit_rejects_safe_refusal_when_grounded_judge_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """D13 finding 5, fail-closed: a desired edit may not pass on an
    allowlisted refusal label when the grounded-refusal judge cannot run."""
    output_dir = tmp_path / "desired-refusal-judge-unavailable"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir)
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("desired-refusal-judge-unavailable"),
    )

    assert verdict["live_agentic_success"] is False
    assert verdict["score_class"] == "undetermined"
    assert verdict["assessment"]["verdict"] == "undetermined"
    assert verdict["assessment"]["passed"] is False
    assert any(
        issue["check"] == "grounded_refusal" and issue["severity"] == "undetermined"
        for issue in verdict["assessment"]["issues"]
    )


def test_desired_edit_rejects_fabricated_safe_refusal(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """D13 finding 5: a fabricated/unsupported requires_custom_nodes refusal
    (judge: not grounded) must fail a desired edit."""
    output_dir = tmp_path / "desired-refusal-fabricated"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir)
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=False),
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("desired-refusal-fabricated"),
    )

    assert verdict["live_agentic_success"] is False
    assert any(
        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
        for issue in verdict["assessment"]["issues"]
    )


def test_desired_edit_accepts_grounded_safe_refusal(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """D13 finding 5, positive control: a genuine grounded refusal (judge:
    grounded) may still pass a desired edit."""
    output_dir = tmp_path / "desired-refusal-grounded"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir)
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("desired-refusal-grounded"),
    )

    assert verdict["live_agentic_success"] is True
    assessment = verdict["assessment"]
    assert assessment["passed"] is True
    assert any(
        issue["check"] == "grounded_refusal" and issue["severity"] == "info"
        for issue in assessment["issues"]
    )


def test_grounded_safe_refusal_ignores_rolled_back_attempt_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """cc0df7: a failed scratch batch is not a defect in an accepted refusal."""
    output_dir = tmp_path / "grounded-refusal-after-rollback"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir, kind="clarify")
    response_path = output_dir / "response.json"
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["change_details"] = {
        "batch_turns": [
            {
                "batch_ok": False,
                "landed_op_count": 0,
                "raw_landed_op_count": 0,
                "diagnostics": [
                    {
                        "code": "socket_type_mismatch",
                        "severity": "error",
                        "message": "Cannot wire STRING into FILE_3D on Preview3D.model_file.",
                    },
                    {
                        "code": "batch_transaction_rolled_back",
                        "severity": "error",
                        "message": "A later edit statement failed, so all edits were rolled back.",
                    },
                ],
            }
        ]
    }
    response_path.write_text(json.dumps(response), encoding="utf-8")
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario(
            "grounded-refusal-after-rollback",
            kind="clarify",
        ),
    )

    assert verdict["live_agentic_success"] is True
    assert not any(
        issue["check"] == "hard_diagnostic"
        for issue in verdict["assessment"]["issues"]
    )


def test_applied_corrupt_candidate_keeps_hard_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Crops/wan-vace guard: applied candidate diagnostics still fail closed."""
    output_dir = tmp_path / "applied-corrupt-candidate"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(
        output_dir,
        change_details={
            "landed_operation_count": 1,
            "batch_turns": [
                {
                    "batch_ok": True,
                    "landed_op_count": 1,
                    "raw_landed_op_count": 1,
                    "diagnostics": [
                        {
                            "code": "widget_shape_mismatch",
                            "severity": "error",
                            "message": "Applied candidate changed an opaque widget shape.",
                        }
                    ],
                }
            ],
        },
    )
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "Candidate applied."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_edit_intent",
        lambda *args, **kwargs: {"pass_": True, "criteria": {}, "rationale": "ok"},
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "applied-corrupt-candidate",
            "query": "crop the image",
            "assessment": {"expect_graph_changed": True},
            "desired": {"outcome": "image is cropped"},
        },
    )

    assert verdict["live_agentic_success"] is False
    assert any(
        issue["check"] == "hard_diagnostic" and issue["severity"] == "error"
        for issue in verdict["assessment"]["issues"]
    )


def test_desired_edit_refusal_label_with_graph_change_fails_closed_without_verdict(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """D13 finding 5: graph_unchanged=false plus a refusal label is never a
    safe refusal; without any grounded judge verdict a desired edit fails
    closed (structural guards + fail-closed intent judge)."""
    output_dir = tmp_path / "desired-refusal-graph-changed"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir, graph_unchanged=False)
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_edit_intent",
        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("desired-refusal-graph-changed"),
    )

    assert verdict["live_agentic_success"] is False
    assert verdict["assessment"]["verdict"] == "fail"
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert {"outcome_kind", "landed_operation_count", "gates"} <= error_checks
    assert any(
        issue["check"] == "intent_judge" and issue["severity"] == "undetermined"
        for issue in verdict["assessment"]["issues"]
    )


def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_path: Path) -> None:
    output_dir = tmp_path / "edit-or-refuse-noop"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "message": "No changes.",
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "edit-or-refuse-noop",
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    checks = {issue["check"] for issue in verdict["assessment"]["issues"] if issue["severity"] == "error"}
    assert "graph_changed" in checks
    assert "no_candidate_reason" in checks


@pytest.mark.parametrize("scenario_id", _CORRECTED_D13_EDIT_IDS)
def test_corrected_d13_edits_cannot_pass_as_noops(
    tmp_path: Path,
    scenario_id: str,
) -> None:
    output_dir = tmp_path / scenario_id
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "message": "No changes.",
            }
        ),
        encoding="utf-8",
    )
    scenario_path = (
        Path(__file__).parent
        / "live_agentic_harness"
        / "scenarios"
        / f"{scenario_id}.json"
    )
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))

    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "graph_changed" in checks
    assert "no_candidate_reason" in checks
    assert "outcome_kind" in checks


def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    output_dir = tmp_path / "desired-judge-unavailable"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"status": "success"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_edit_intent",
        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "desired-judge-unavailable",
            "query": "set seed to 42",
            "assessment": {"expect_graph_changed": True},
            "desired": {
                "outcome": "seed is 42",
                "quality": "only the intended seed changes",
                "alternatives_ok": False,
            },
        },
    )

    assert verdict["live_agentic_success"] is False
    assert verdict["score_class"] == "undetermined"
    assert verdict["assessment"]["verdict"] == "undetermined"
    assert verdict["assessment"]["passed"] is False
    assert any(
        issue["check"] == "intent_judge" and issue["severity"] == "undetermined"
        for issue in verdict["assessment"]["issues"]
    )


def test_desired_edit_fails_closed_on_fabricated_intent_judge_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """D13 rework: the assessor consumes the DERIVED intent-judge verdict
    (assessor.py intent_judge branch).  A fabricated pass_=true with a false
    criterion must fail the desired edit instead of passing it."""
    output_dir = tmp_path / "desired-fabricated-intent-pass"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(output_dir, {"nodes": []}, {"nodes": [{"id": 1}]})
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"status": "success"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        lambda *args, **kwargs: {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": False,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "fabricated pass",
                }
            )
        },
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("desired-fabricated-intent-pass"),
    )

    assert verdict["live_agentic_success"] is False
    assert any(
        issue["check"] == "intent_judge" and issue["severity"] == "error"
        for issue in verdict["assessment"]["issues"]
    )


def test_desired_edit_fails_closed_on_fabricated_grounded_refusal_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """D13 rework: the assessor consumes the DERIVED grounded-refusal verdict
    (assessor.py grounded_refusal branch).  A fabricated pass_=true with a
    false criterion must fail the desired edit instead of passing it."""
    output_dir = tmp_path / "desired-fabricated-refusal-pass"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir)
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        lambda *args, **kwargs: {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "supported_blocker": True,
                        "no_representable_edit": True,
                        "specific_next_action": True,
                        "no_fabricated_inability": False,
                    },
                    "rationale": "fabricated grounded refusal",
                }
            )
        },
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("desired-fabricated-refusal-pass"),
    )

    assert verdict["live_agentic_success"] is False
    assert any(
        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
        for issue in verdict["assessment"]["issues"]
    )


def test_agentic_guard_ignores_oversized_model_request(tmp_path: Path) -> None:
    """B12/B13: ``assessment.max_model_request_bytes`` is deleted scoring
    prejudice — prompt length never gates a run, even when a scenario still
    declares a limit."""
    output_dir = tmp_path / "oversized-model-request"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "candidate": {"nodes": [{"id": 1}]},
                "change_details": {"landed_operation_count": 1},
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "model_request.json").write_text("x" * 101, encoding="utf-8")

    scenario = {
        "id": "oversized-model-request",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "max_model_request_bytes": 100,
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"].startswith("model_request")
    ]


def test_agentic_guard_ignores_forbidden_model_request_substrings(tmp_path: Path) -> None:
    """B12/B13: ``assessment.forbid_model_request_substrings`` is deleted
    scoring prejudice — prompt content never gates a run, even when a scenario
    still declares forbidden substrings."""
    output_dir = tmp_path / "forbidden-model-request"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "candidate": {"nodes": [{"id": 1}]},
                "change_details": {"landed_operation_count": 1},
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "model_request.json").write_text(
        '{"turns":[{"messages":[{"content":"raw \\"workflow_schema\\" leaked"}]}]}',
        encoding="utf-8",
    )

    scenario = {
        "id": "forbidden-model-request",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "forbid_model_request_substrings": ["\"workflow_schema\""],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"].startswith("model_request")
    ]


def test_agentic_guard_rejects_static_widget_edit_overridden_by_link(tmp_path: Path) -> None:
    output_dir = tmp_path / "inert-linked-widget"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True),
        _frame_count_graph(source_value=8, target_value=16, linked=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"inert_effective_edit"}


def test_agentic_guard_rejects_no_effective_value_change_for_claimed_target(tmp_path: Path) -> None:
    output_dir = tmp_path / "no-effective-target-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(target_value=8, linked=False, save_prefix="before"),
        _frame_count_graph(target_value=8, linked=False, save_prefix="after"),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"effective_edit"}


def test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value(tmp_path: Path) -> None:
    output_dir = tmp_path / "linked-source-effective-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True


# ── G0-T2: structured-only scoring — prose never gates a scenario ──────────
#
# The nine matcher-only scenarios (Dig2 counterfactual rescore,
# docs/failure-analysis/agentic-pipeline-improvement-2026-08.md §9) failed
# ONLY because the deterministic message-artifact matcher misread prose:
#   - group A: the message says parts of the graph are "unchanged" while the
#     structured record proves an edit landed (the old \bunchanged\b matcher
#     produced "message claims no change even though response graph changed");
#   - group B: the message is an explanation that uses words like
#     "connected"/"applied" while the structured record proves no edit landed
#     (the old \bconnected\b/\bapplied\b matchers produced "message claims
#     edits even though response.graph_unchanged is True").
# With deterministic prose gating removed, every one of these must PASS on the
# structured record alone — the message never flips pass/fail.

_ALL_GATES_PASS = {
    "ir_validate_ok": True,
    "lower_ok": True,
    "plan_validate_ok": True,
    "python_load_ok": True,
    "queue_validate_ok": True,
    "state_match_ok": True,
    "ui_emit_ok": True,
    "ui_fidelity_ok": True,
    "ui_load_safe_ok": True,
}

# (scenario_id, response) — prose excerpts are grounded in the persisted
# response.json artifacts of the recorded matcher-only failures.
_MATCHER_ONLY_COUNTEREXAMPLES: tuple[tuple[str, dict[str, object]], ...] = (
    (
        "3d-generates-a-3d-mesh-from",
        {
            "message": (
                "Done — I tuned the mesh-generation path to reduce floating bits and noise. "
                "Concretely, `KSampler` steps went from 20 to 50 so the sampler converges "
                "further before `VAEDecodeHunyuan3D` extracts the mesh; node connections and "
                "other widgets are unchanged (structure validated)."
            ),
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "change_details": {"landed_operation_count": 1},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "audio-acestep-audio-generation-workflow-2a31ec",
        {
            "message": (
                "The AceStepSFTGenerate node now uses acestep-sft-v2.safetensors as its base "
                "model checkpoint (widget_0), replacing acestep-v15.safetensors. The rest of "
                "the SFT chain (audio input, prompt, LoRA, and save) is preserved unchanged."
            ),
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "change_details": {"landed_operation_count": 1},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "image-sd3-image-generation-with-controlnet-19d221",
        {
            "message": (
                "I lowered the ControlNet influence to give your text prompt the upper hand: "
                "the `strength` widget on `ACN_AdvancedControlNetApply` (node 60) is now 0.5, "
                "down from 0.6, while the tile ControlNet loader and its start/end percent "
                "(0 / 0.75) stay unchanged."
            ),
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "change_details": {"landed_operation_count": 1},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "video-generates-a-video-from-a",
        {
            "message": (
                "Done — I set the video output to 24 fps by updating the `frame_rate` widget "
                "on VHS_VideoCombine from 15 to 24. No other nodes were touched; the "
                "`Modelscopet2v` and `CR Prompt Text` nodes are unchanged."
            ),
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "change_details": {"landed_operation_count": 1},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "video-image-to-video-conversion-with-moonvalley-d7853c",
        {
            "message": (
                "Updated MoonvalleyImg2VideoNode so the output videos are 5.0 seconds long: "
                "frame count (widget_3) 7 -> 120, frame rate (widget_6) 100 -> 24 fps. "
                "LoadImage and SaveVideo are unchanged and still connected as before."
            ),
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "change_details": {"landed_operation_count": 2},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "multi-ai-video-upscaling-with-detail-daemon-sampler-673197",
        {
            "message": (
                "Here's what your graph (29 nodes) actually does, and where the color-shift "
                "suspects live. Pipeline as connected: 1. Conditioning — CLIPLoader encodes "
                "the prompt via CLIPTextEncode; 2. Sampling chain — UNETLoader feeds three "
                "BetaSamplingScheduler nodes. Since the SeedVR2 nodes are disconnected here, "
                "I'd verify whether the upscaler is being used."
            ),
            "graph_unchanged": True,
            "outcome": {"kind": "noop"},
            "change_details": {"landed_operation_count": 0},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "multi-audio-to-image-mel-band-roformer-workflow-b22937",
        {
            "message": (
                "This graph is an audio-enhancement pipeline: load a WAV, process it with a "
                "Mel-band separation model, then upscale the result. The sampler applies "
                "MelBandRoFormer to do the core audio processing. Portability note: the "
                "model loader isn't connected to the data flow; no changes were made."
            ),
            "graph_unchanged": True,
            "outcome": {"kind": "noop"},
            "change_details": {"landed_operation_count": 0},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "video-hunyuan-video-text-to-video-generation-265847",
        {
            "message": (
                "This is a Hunyuan Video T2V workflow: UNETLoader -> ModelSamplingSD3 -> "
                "SamplerCustomAdvanced with euler / 20 steps / denoise=1, starting from "
                "EmptyHunyuanLatentVideo (73 frames). There is a VAEDecode (node 8) that is "
                "not connected to the save node; the animated WEBP is saved from "
                "VAEDecodeTiled at 24 fps."
            ),
            "graph_unchanged": True,
            "outcome": {"kind": "noop"},
            "change_details": {"landed_operation_count": 0},
            "gates": _ALL_GATES_PASS,
        },
    ),
    (
        "video-video-output-workflow-f855de",
        {
            "message": (
                "This graph makes a low-resolution image, upscales it, decodes latents, and "
                "writes the video directly. Likely causes of blur: both upscale stages are "
                "toggled off, so the saved frames are the tiny base resolution. Note the "
                "detail-enhancement edits I have not applied."
            ),
            "graph_unchanged": True,
            "outcome": {"kind": "noop"},
            "change_details": {"landed_operation_count": 0},
            "gates": _ALL_GATES_PASS,
        },
    ),
)


@pytest.mark.parametrize(
    ("scenario_id", "response"),
    _MATCHER_ONLY_COUNTEREXAMPLES,
    ids=[scenario_id for scenario_id, _ in _MATCHER_ONLY_COUNTEREXAMPLES],
)
def test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating(
    tmp_path: Path,
    scenario_id: str,
    response: dict[str, object],
) -> None:
    """The nine matcher-only scenarios now pass: prose never gates scoring."""
    output_dir = tmp_path / scenario_id
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")

    expect_edit = bool(response.get("graph_unchanged") is False)
    scenario = {
        "id": scenario_id,
        "assessment": {
            "expect_graph_changed": expect_edit,
            "skip_intent_judge": True,
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True, verdict["assessment"]["issues"]
    assert verdict["score_class"] == "pass"
    assert verdict["assessment"]["passed"] is True
    assert all(
        issue["check"] != "message_artifact"
        for issue in verdict["assessment"]["issues"]
    ), "prose must never produce an error-severity issue"


def test_agentic_guard_false_landed_claim_still_fails_via_structured_checks(
    tmp_path: Path,
) -> None:
    """Control: a message claiming edits that never landed still fails the run.

    The failure comes from the STRUCTURED record (no edit landed while one was
    expected — graph_changed / outcome_kind / no_candidate_reason), never from
    matching the message's words.
    """
    output_dir = tmp_path / "false-landed-claim"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "message": "Applied 2 edits and rewired the sampler.",
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "change_details": {"landed_operation_count": 0},
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "false-landed-claim",
        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert {"graph_changed", "outcome_kind", "no_candidate_reason"} <= error_checks
    assert "message_artifact" not in error_checks


def test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks(
    tmp_path: Path,
) -> None:
    """Control: a message claiming nothing changed when an edit DID land fails.

    The structured record proves the edit landed (outcome.kind=candidate) while
    the scenario expected a no-edit outcome — the outcome_kind STRUCTURED check
    catches it, not the message's words.
    """
    output_dir = tmp_path / "false-unchanged-claim"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "message": "No changes were needed; the workflow already matches that.",
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "change_details": {"landed_operation_count": 1},
                "gates": _ALL_GATES_PASS,
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "false-unchanged-claim",
        "assessment": {
            "expect_graph_changed": False,
            "expected_outcome_kinds": ["noop", "clarify"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "outcome_kind" in error_checks
    assert "message_artifact" not in error_checks


def test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check(
    tmp_path: Path,
) -> None:
    """Control: a message claiming a connection that changed nothing effective.

    The effective_edit STRUCTURED check compares the UI artifacts and proves
    the claimed target never changed value; the message's words are irrelevant.
    """
    output_dir = tmp_path / "false-connection-claim"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(
        output_dir,
        message="Connected the frame-count source to the generator.",
    )
    _write_ui_pair(
        output_dir,
        _frame_count_graph(target_value=8, linked=False, save_prefix="before"),
        _frame_count_graph(target_value=8, linked=False, save_prefix="after"),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert error_checks == {"effective_edit"}
    assert "message_artifact" not in error_checks


def test_agentic_guard_false_validation_success_claim_still_fails_via_gates(
    tmp_path: Path,
) -> None:
    """Control: a message claiming validation passed when gates failed.

    The gates STRUCTURED check reads the gate flags; the message's words do not
    enter scoring at all.
    """
    output_dir = tmp_path / "false-validation-success-claim"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "message": "Validation passed and the candidate is ready to apply.",
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "candidate_graph": {"nodes": [{"id": 1}]},
                "change_details": {"landed_operation_count": 1},
                "gates": {
                    "ir_validate_ok": False,
                    "lower_ok": True,
                    "plan_validate_ok": False,
                    "python_load_ok": True,
                    "queue_validate_ok": True,
                    "state_match_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                },
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "false-validation-success-claim",
        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "gates" in error_checks
    assert "message_artifact" not in error_checks


# ── G0R: structural expected-edit guard (landed_operation_count) ──────────
#
# A claimed edit (graph_unchanged is False) must be backed by a positive
# integer change_details.landed_operation_count.  Missing, malformed, or
# zero counts fail closed; accepted grounded refusals and canonical
# non-edit routes (read from response.route — never from self-declared
# outcome/no_candidate_reason labels) are exempt (they are scored by
# their own checks, including the route/graph consistency check).


@pytest.mark.parametrize(
    "change_details",
    [
        pytest.param(None, id="missing-change-details"),
        pytest.param({}, id="missing-landed-count"),
        pytest.param({"landed_operation_count": 0}, id="zero-landed-count"),
        pytest.param({"landed_operation_count": -1}, id="negative-landed-count"),
        pytest.param({"landed_operation_count": "1"}, id="string-landed-count"),
        pytest.param({"landed_operation_count": 1.5}, id="float-landed-count"),
        pytest.param({"landed_operation_count": True}, id="bool-landed-count"),
    ],
)
def test_agentic_guard_expected_edit_requires_positive_landed_count(
    tmp_path: Path,
    change_details: dict[str, object] | None,
    request: pytest.FixtureRequest,
) -> None:
    """G0R negative control: graph_unchanged=false with a missing, malformed,
    or zero landed_operation_count fails closed structurally."""
    output_dir = tmp_path / f"landed-count-{request.node.callspec.id}"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    response = {
        "ok": True,
        "graph_unchanged": False,
        "outcome": {"kind": "candidate"},
        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
        "gates": _ALL_GATES_PASS,
    }
    if change_details is not None:
        response["change_details"] = change_details
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")

    scenario = {
        "id": f"landed-count-{change_details!r}",
        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]


def test_agentic_guard_expected_edit_with_positive_landed_count_passes(
    tmp_path: Path,
) -> None:
    """G0R positive control: graph_unchanged=false with a positive integer
    landed_operation_count passes the structural guard."""
    output_dir = tmp_path / "landed-count-positive"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "candidate_graph": {"nodes": [{"id": 1}], "links": []},
                "change_details": {"landed_operation_count": 1},
                "gates": _ALL_GATES_PASS,
            }
        ),
        encoding="utf-8",
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-positive",
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
        },
    )

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"] == "landed_operation_count"
    ]


def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """G0R: an accepted grounded refusal (graph_unchanged=true, allowed
    outcome kind) is exempt from the landed_operation_count requirement."""
    output_dir = tmp_path / "landed-count-refusal-exempt"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "requires_custom_nodes"},
                "message": "No schema-backed replacement node was found.",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
    )
    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-refusal-exempt",
            "query": "add the missing custom node",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
            },
        },
    )

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    assert verdict["assessment"]["verdict"] == "pass"
    assert {"safe_refusal", "grounded_refusal"} <= {
        issue["check"] for issue in verdict["assessment"]["issues"]
    }
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"] == "landed_operation_count"
    ]


def test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify(tmp_path: Path) -> None:
    """G0R negative control: an edit-route envelope (route=revise) with
    graph_unchanged=false, no landed count, self-labeling outcome.kind=clarify
    must fail closed — self-declared outcome labels cannot buy an exemption
    from the landed_operation_count guard."""
    output_dir = tmp_path / "landed-count-edit-route-clarify-relabel"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "route": "revise",
                "graph_unchanged": False,
                "outcome": {"kind": "clarify"},
                "message": "Which node should I edit next?",
            }
        ),
        encoding="utf-8",
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-edit-route-clarify-relabel",
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
        },
    )

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]


def test_agentic_guard_rejects_route_not_applyable_without_landed_count(tmp_path: Path) -> None:
    """G0R negative control: graph_unchanged=false with
    no_candidate_reason=route_not_applyable and no landed count must fail
    closed — a self-declared no-candidate reason cannot bypass the guard when
    no canonical non-edit route backs it."""
    output_dir = tmp_path / "landed-count-route-not-applyable"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": False,
                "no_candidate_reason": "route_not_applyable",
                "message": "This request is not applicable to the current graph.",
            }
        ),
        encoding="utf-8",
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-route-not-applyable",
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
        },
    )

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]


def test_agentic_guard_rejects_failure_outcome_without_landed_count(tmp_path: Path) -> None:
    """G0R negative control: failure outcomes cannot bypass all structured
    checks — an edit-route envelope with outcome.kind=failure,
    graph_unchanged=false and no landed count still fails the
    landed_operation_count guard."""
    output_dir = tmp_path / "landed-count-failure-outcome"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "route": "revise",
                "graph_unchanged": False,
                "outcome": {"kind": "failure"},
                "message": "The edit could not be completed.",
            }
        ),
        encoding="utf-8",
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-failure-outcome",
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
        },
    )

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]


def test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """G0R positive control: a canonical non-edit route (route=respond) with
    graph_unchanged=true and an authorized refusal outcome kind is still
    exempt — the route-aware exemption must not over-correct truthful non-edit
    responses. B06 still requires the grounded-refusal judge; a passing
    verdict keeps the structural exemption.
    """
    output_dir = tmp_path / "landed-count-genuine-non-edit-route-exempt"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "route": "respond",
                "graph_unchanged": True,
                "no_candidate_reason": "route_not_applyable",
                "outcome": {"kind": "respond"},
                "message": "I answered directly; no graph change was needed.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-genuine-non-edit-route-exempt",
            "query": "what does this graph do?",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": ["respond", "clarify"],
                "skip_intent_judge": True,
            },
        },
    )

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    checks = {issue["check"] for issue in verdict["assessment"]["issues"]}
    assert "safe_refusal" in checks
    assert "grounded_refusal" in checks
    assert "landed_operation_count" not in checks
    assert "route_graph_consistency" not in checks


def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
    tmp_path: Path,
) -> None:
    """G0R control: a canonical non-edit route (route=respond) claiming
    graph_unchanged=false is exempt from the landed-count guard but still
    fails through its own structured checks (route/graph consistency,
    no_candidate_reason, outcome_kind) when an edit was expected."""
    output_dir = tmp_path / "landed-count-noop-not-exempt-from-noop-check"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "route": "respond",
                "graph_unchanged": False,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
            }
        ),
        encoding="utf-8",
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-noop-check",
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
        },
    )

    assert verdict["live_agentic_success"] is False
    error_checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert "route_graph_consistency" in error_checks
    assert "no_candidate_reason" in error_checks
    assert "outcome_kind" in error_checks
    assert "landed_operation_count" not in error_checks


def test_agentic_guard_allows_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
    """B12/B13: a change landing through a shared linked source is a valid
    edit by default — effects determine edit correctness, and an agent may
    intentionally edit one source feeding several consumers.  The former
    ``shared_effective_source_edit`` error and the per-target
    ``allow_shared_source_edit`` flag are deleted."""
    output_dir = tmp_path / "shared-linked-source-effective-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"] == "shared_effective_source_edit"
    ]


def test_agentic_guard_rejects_shared_linked_source_edit_when_isolation_opted_in(
    tmp_path: Path,
) -> None:
    """The shared-source error survives only as an explicit scenario opt-in
    (``assessment.isolate_shared_effective_sources``)."""
    output_dir = tmp_path / "shared-linked-source-isolated"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
    )
    scenario = _effective_target_scenario()
    scenario["assessment"]["isolate_shared_effective_sources"] = True

    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"shared_effective_source_edit"}


def test_agentic_guard_treats_skipped_queue_validation_as_warning(tmp_path: Path) -> None:
    output_dir = tmp_path / "queue-skipped"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(
        output_dir,
        gates={
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        debug={
            "stage_snapshots": [
                {"stage": "ingest", "ok": True, "issues": []},
                {"stage": "agent_batch", "ok": True, "issues": []},
            ]
        },
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert verdict["live_agentic_success"] is True
    assert verdict["score_class"] == "pass"
    assert verdict["assessment"]["passed"] is True
    assert [issue["check"] for issue in verdict["assessment"]["issues"]] == [
        "queue_validate_skipped",
    ]
    assert verdict["assessment"]["issues"][0]["severity"] == "warning"


def test_agentic_guard_product_fails_real_queue_validation_failure(tmp_path: Path) -> None:
    output_dir = tmp_path / "queue-failed"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(
        output_dir,
        gates={
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        debug={
            "stage_snapshots": [
                {
                    "stage": "queue_validate",
                    "ok": False,
                    "issues": [{"code": "schema_less_queue_blocker"}],
                },
            ]
        },
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert verdict["live_agentic_success"] is False
    assert verdict["score_class"] == "product_fail"
    assert [issue["check"] for issue in verdict["assessment"]["issues"]] == ["gates"]
    assert "queue_validate_ok" in verdict["assessment"]["issues"][0]["detail"]


def _semantic_product_scenario(**overrides: object) -> dict:
    scenario: dict[str, object] = {
        "id": "semantic-fixture",
        "query": "Why is the output blurry?",
        "assessment": {"expect_graph_changed": False},
        "classification": {"kind": "semantic_product"},
        "answer_rubric": {
            "judge": "semantic_answer",
            "required_node_evidence": ["SaveVideo"],
            "expected_criteria": [
                "Ground claims in the workflow.",
                "Name the relevant node.",
                "Give a causal diagnosis.",
                "Answer the asked question.",
            ],
            "pass_condition": "Pass only when the answer is grounded, relevant, and correct.",
            "fail_conditions": [
                "hallucinated nodes",
                "technically wrong",
                "irrelevant",
                "vacuous listing",
                "empty answer",
            ],
        },
    }
    scenario.update(overrides)
    return scenario


def _semantic_verdict(*, grounded: bool = True, relevant: bool = True, correct: bool = True) -> dict:
    return {
        "pass_": grounded and relevant and correct,
        "criteria": {
            "grounded": grounded,
            "relevant": relevant,
            "correct": correct,
        },
        "rationale": "fixture verdict",
    }


def _write_non_edit_response(output_dir: Path, *, reply: str = "SaveVideo uses a low bitrate.") -> None:
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "route": "inspect",
                "graph_unchanged": True,
                "reply": reply,
                "message": reply,
                "outcome": {"kind": "noop"},
            }
        ),
        encoding="utf-8",
    )


def test_refusal_fixtures_produce_pass_fail_fail_undetermined(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Grounded / unsupported / fabricated / outage → pass / fail / fail / undetermined."""
    cases = (
        ("grounded", _grounded_refusal_verdict(grounded=True), "pass", "pass"),
        (
            "unsupported",
            {
                "pass_": False,
                "criteria": {
                    "supported_blocker": False,
                    "no_representable_edit": True,
                    "specific_next_action": True,
                    "no_fabricated_inability": True,
                },
                "rationale": "no supported blocker",
            },
            "fail",
            "product_fail",
        ),
        ("fabricated", _grounded_refusal_verdict(grounded=False), "fail", "product_fail"),
        (
            "outage",
            {"pass_": None, "error": "judge unavailable"},
            "undetermined",
            "undetermined",
        ),
    )
    for name, judge_verdict, expected_verdict, expected_score in cases:
        output_dir = tmp_path / name
        _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
        _write_safe_refusal_response(output_dir)
        monkeypatch.setattr(
            "tests.live_agentic_harness.assessor.judge_grounded_refusal",
            lambda *args, _verdict=judge_verdict, **kwargs: _verdict,
        )
        result = guard_output_dir(
            output_dir,
            scenario=_desired_edit_scenario(f"refusal-{name}"),
        )
        assert result["assessment"]["verdict"] == expected_verdict, name
        assert result["score_class"] == expected_score, name
        assert result["live_agentic_success"] is (expected_verdict == "pass"), name
        assert result["assessment"]["passed"] is (expected_verdict == "pass"), name


def test_allowlisted_refusal_without_desired_still_requires_grounded_judge(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Label-first acceptance is gone: non-desired allowlisted refusals are judged."""
    output_dir = tmp_path / "no-desired-refusal"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir)
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=False),
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "no-desired-refusal",
            "query": "set seed to 42",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
            },
        },
    )

    assert verdict["live_agentic_success"] is False
    assert verdict["assessment"]["verdict"] == "fail"
    assert any(
        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
        for issue in verdict["assessment"]["issues"]
    )


def test_identical_refusal_prose_fails_when_schema_contradicts(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Same plausible refusal prose with contradictory schema/graph evidence fails."""
    output_dir = tmp_path / "contradictory-schema-refusal"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_safe_refusal_response(output_dir)
    _write_ui_pair(
        output_dir,
        {"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}]},
        {"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}]},
    )
    (output_dir / "final.ui.json").write_text(
        (output_dir / "original.ui.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (output_dir / "implementation_payload.json").write_text(
        json.dumps(
            {
                "graph": {
                    "compiled_api": {
                        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        payload = json.loads(messages[1]["content"])
        captured["payload"] = payload
        schema = payload.get("schema_context") or {}
        compiled = schema.get("compiled_api") or {}
        inventory = payload.get("node_inventory") or []
        types = {item.get("type") for item in inventory if isinstance(item, dict)}
        has_loader = "CheckpointLoaderSimple" in compiled or "CheckpointLoaderSimple" in types
        criteria = {
            "supported_blocker": not has_loader,
            "no_representable_edit": not has_loader,
            "specific_next_action": True,
            "no_fabricated_inability": not has_loader,
        }
        return {
            "content": json.dumps(
                {
                    "pass_": all(criteria.values()),
                    "criteria": criteria,
                    "rationale": "schema contains the cited class" if has_loader else "ok",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = guard_output_dir(
        output_dir,
        scenario=_desired_edit_scenario("contradictory-schema-refusal"),
    )

    assert "schema_context" in captured["payload"] or "node_inventory" in captured["payload"]
    assert verdict["live_agentic_success"] is False
    assert verdict["assessment"]["verdict"] == "fail"
    assert any(issue["check"] == "grounded_refusal" for issue in verdict["assessment"]["issues"])


def test_healthy_but_false_explanation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    output_dir = tmp_path / "false-explanation"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_non_edit_response(
        output_dir,
        reply="The blur is caused by a GaussianBlur node that is not in the graph.",
    )
    (output_dir / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "SaveVideo"}], "links": []}),
        encoding="utf-8",
    )
    (output_dir / "final.ui.json").write_text(
        (output_dir / "original.ui.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: _semantic_verdict(grounded=False, correct=False),
    )

    verdict = guard_output_dir(output_dir, scenario=_semantic_product_scenario())

    assert verdict["live_agentic_success"] is False
    assert verdict["assessment"]["verdict"] == "fail"
    assert any(issue["check"] == "semantic_answer" for issue in verdict["assessment"]["issues"])
    assert any(
        result["judge"] == "semantic_answer" and result["verdict"] == "fail"
        for result in verdict["assessment"]["judge_results"]
    )


def test_semantic_judge_outage_never_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    output_dir = tmp_path / "semantic-outage"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_non_edit_response(output_dir)
    (output_dir / "original.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (output_dir / "final.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
    )

    verdict = guard_output_dir(output_dir, scenario=_semantic_product_scenario())

    assert verdict["live_agentic_success"] is False
    assert verdict["score_class"] == "undetermined"
    assert verdict["assessment"]["verdict"] == "undetermined"
    assert verdict["assessment"]["passed"] is False


def test_empty_but_valid_semantic_answer_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "empty-answer"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_non_edit_response(output_dir, reply="   ")
    (output_dir / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "SaveVideo"}]}), encoding="utf-8"
    )
    (output_dir / "final.ui.json").write_text(
        (output_dir / "original.ui.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    verdict = guard_output_dir(output_dir, scenario=_semantic_product_scenario())

    assert verdict["live_agentic_success"] is False
    assert verdict["assessment"]["verdict"] == "fail"
    semantic = [
        result
        for result in verdict["assessment"]["judge_results"]
        if result["judge"] == "semantic_answer"
    ]
    assert semantic and semantic[0]["verdict"] == "fail"


def test_every_semantic_non_edit_has_rubric_and_judge_result(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = Path(__file__).parent / "live_agentic_harness" / "scenarios"
    semantic = []
    for path in sorted(scenarios_dir.glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if scenario.get("answer_rubric"):
            semantic.append(scenario)

    assert len(semantic) == 35
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: _semantic_verdict(),
    )

    for scenario in semantic:
        assert scenario["answer_rubric"]["judge"] == "semantic_answer"
        output_dir = tmp_path / scenario["id"]
        _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
        _write_non_edit_response(output_dir)
        (output_dir / "original.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
        (output_dir / "final.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
        verdict = guard_output_dir(output_dir, scenario=scenario)
        results = verdict["assessment"]["judge_results"]
        assert any(result["judge"] == "semantic_answer" for result in results), scenario["id"]
        assert verdict["assessment"]["scenario_kind"] == "semantic_product"
        assert verdict["assessment"]["excluded_from_semantic_product_rates"] is False


def test_health_controls_are_structurally_scored_not_semantically_judged(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    called = {"semantic": False}
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: called.__setitem__("semantic", True) or _semantic_verdict(),
    )
    for scenario_id in ("live-graph-explanation-smoke", "speed-distillation-research"):
        output_dir = tmp_path / scenario_id
        _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
        _write_non_edit_response(output_dir, reply="ok")
        scenario_path = (
            Path(__file__).parent / "live_agentic_harness" / "scenarios" / f"{scenario_id}.json"
        )
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        verdict = guard_output_dir(output_dir, scenario=scenario)
        assert verdict["assessment"]["scenario_kind"] == "health_control"
        assert verdict["assessment"]["excluded_from_semantic_product_rates"] is True
        assert not any(
            result["judge"] == "semantic_answer"
            for result in verdict["assessment"]["judge_results"]
        )
        assert verdict["assessment"]["verdict"] == "pass"
    assert called["semantic"] is False


def test_corrected_d13_edits_use_edit_intent_judge(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    called = {"edit": 0, "semantic": 0}
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_edit_intent",
        lambda *args, **kwargs: (
            called.__setitem__("edit", called["edit"] + 1)
            or {
                "pass_": True,
                "criteria": {
                    "correct_node_targeted": True,
                    "correct_parameter_changed": True,
                    "value_semantically_matches_intent": True,
                    "no_orphaned_wiring": True,
                },
                "rationale": "edit matches desired outcome",
            }
        ),
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: called.__setitem__("semantic", called["semantic"] + 1)
        or _semantic_verdict(),
    )
    for scenario_id in _CORRECTED_D13_EDIT_IDS:
        output_dir = tmp_path / scenario_id
        _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
        _write_successful_candidate(output_dir)
        _write_ui_pair(output_dir, {"nodes": []}, {"nodes": [{"id": 1}]})
        scenario = json.loads(
            (
                Path(__file__).parent
                / "live_agentic_harness"
                / "scenarios"
                / f"{scenario_id}.json"
            ).read_text(encoding="utf-8")
        )
        verdict = guard_output_dir(output_dir, scenario=scenario)
        assert any(
            result["judge"] == "edit_intent" for result in verdict["assessment"]["judge_results"]
        ), scenario_id
        assert not any(
            result["judge"] == "semantic_answer"
            for result in verdict["assessment"]["judge_results"]
        ), scenario_id
        assert scenario.get("desired")
        assert scenario["assessment"]["expect_graph_changed"] is True
    assert called["edit"] == 3
    assert called["semantic"] == 0


def test_only_pass_satisfies_a_semantic_scenario(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    output_dir = tmp_path / "semantic-pass-only"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_non_edit_response(output_dir)
    (output_dir / "original.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (output_dir / "final.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: _semantic_verdict(),
    )
    passing = guard_output_dir(output_dir, scenario=_semantic_product_scenario())
    assert passing["live_agentic_success"] is True
    assert passing["assessment"]["verdict"] == "pass"

    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: {"pass_": None, "error": "outage"},
    )
    undetermined = guard_output_dir(output_dir, scenario=_semantic_product_scenario())
    assert undetermined["live_agentic_success"] is False
    assert undetermined["assessment"]["verdict"] == "undetermined"
