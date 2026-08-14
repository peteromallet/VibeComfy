from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.assessor import assess_live_output_dir


def test_recovered_upstream_500_is_warning_when_candidate_succeeded(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "TestNode"}},
        "change_details": {"landed_operation_count": 1},
        "warnings": ["Hivemind HTTP error 500: Internal Server Error"],
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    upstream = [issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"]
    assert upstream
    assert {issue["severity"] for issue in upstream} == {"warning"}
    assert assessment["passed"] is True


def test_upstream_500_remains_error_without_candidate(tmp_path: Path) -> None:
    response = {
        "ok": False,
        "graph_unchanged": True,
        "error": "Hivemind HTTP error 500: Internal Server Error",
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    upstream = [issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"]
    assert upstream
    assert {issue["severity"] for issue in upstream} == {"error"}
    assert assessment["passed"] is False


def test_skipped_queue_validation_is_warning_when_candidate_succeeded(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "SaveAudio"}},
        "change_details": {"landed_operation_count": 1},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        "debug": {
            "stage_snapshots": [
                {"stage": "ingest", "ok": True, "issues": []},
                {"stage": "agent_batch", "ok": True, "issues": []},
            ]
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert assessment["passed"] is True
    assert [issue["check"] for issue in assessment["issues"]] == ["queue_validate_skipped"]
    assert assessment["issues"][0]["severity"] == "warning"


def test_skipped_queue_validation_does_not_hide_other_failed_gates(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "SaveAudio"}},
        "change_details": {"landed_operation_count": 1},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": False,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        "debug": {
            "stage_snapshots": [
                {"stage": "ingest", "ok": True, "issues": []},
                {"stage": "agent_batch", "ok": True, "issues": []},
            ]
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert assessment["passed"] is False
    assert [issue["check"] for issue in assessment["issues"]] == [
        "queue_validate_skipped",
        "gates",
    ]
    gates_issue = assessment["issues"][1]
    assert gates_issue["severity"] == "error"
    assert "lower_ok" in gates_issue["detail"]
    assert "queue_validate_ok" not in gates_issue["detail"]


def test_queue_validation_stage_failure_still_fails(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "SaveAudio"}},
        "change_details": {"landed_operation_count": 1},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        "debug": {
            "stage_snapshots": [
                {"stage": "queue_validate", "ok": False, "issues": [{"code": "schema_less_queue_blocker"}]},
            ]
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert assessment["passed"] is False
    assert [issue["check"] for issue in assessment["issues"]] == ["gates"]
    assert "queue_validate_ok" in assessment["issues"][0]["detail"]


def test_message_prose_never_affects_score(tmp_path: Path) -> None:
    """G0-T2: scoring is structured-only — identical structured records score
    identically no matter what prose the message carries.

    The same record (an edit landed, candidate produced, gates passed) must
    pass both with a grounded message and with message prose that the old
    deterministic matcher misread as a contradiction ("unchanged" parts of the
    graph).  The reverse also holds: a record with no landed edit and failed
    gates fails identically whether the message admits it or falsely claims
    success.
    """
    base = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "KSampler"}},
        "outcome": {"kind": "candidate"},
        "change_details": {"landed_operation_count": 1},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": True,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    }
    scenario = {"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}}

    passing_messages = (
        "Applied 1 edit.",
        "Updated the KSampler; the other nodes are unchanged.",
        "Node connections are unchanged; only the seed changed.",
        "I have not applied any further changes; this edit is complete.",
    )
    scores = []
    for index, message in enumerate(passing_messages):
        run_dir = tmp_path / f"pass-{index}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "response.json").write_text(
            json.dumps({**base, "message": message}),
            encoding="utf-8",
        )
        # G0R: the residual implementation_result prose gate is removed — the
        # same "unchanged"-wording message in implementation_result.json must
        # not affect scoring either.
        (run_dir / "implementation_result.json").write_text(
            json.dumps({"message": message}),
            encoding="utf-8",
        )
        assessment = assess_live_output_dir(run_dir, scenario=scenario)
        scores.append((assessment["passed"], assessment["error_count"]))

    assert scores == [(True, 0)] * len(passing_messages), scores
    assert all(
        issue["check"] not in {"message_artifact", "implementation_result"}
        for index in range(len(passing_messages))
        for issue in assess_live_output_dir(tmp_path / f"pass-{index}", scenario=scenario)["issues"]
    )

    failing_base = {
        "ok": True,
        "graph_unchanged": True,
        "no_candidate_reason": "no_changes",
        "outcome": {"kind": "noop"},
        "change_details": {"landed_operation_count": 0},
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
    }
    failing_messages = (
        "No changes were needed.",
        "Applied 3 edits and the candidate is ready to apply.",
        "Validation passed; everything landed.",
    )
    failing_scores = []
    for index, message in enumerate(failing_messages):
        run_dir = tmp_path / f"fail-{index}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "response.json").write_text(
            json.dumps({**failing_base, "message": message}),
            encoding="utf-8",
        )
        assessment = assess_live_output_dir(run_dir, scenario=scenario)
        failing_scores.append((assessment["passed"], assessment["error_count"]))

    # Four structured errors: graph_changed, no_candidate_reason,
    # outcome_kind, and gates — identical for every message wording.
    assert failing_scores == [(False, 4)] * len(failing_messages), failing_scores


def test_implementation_result_unchanged_prose_does_not_gate_scoring(tmp_path: Path) -> None:
    """G0R counterexample: an implementation_result message saying other
    nodes are unchanged must NOT affect scoring when the structured record
    proves an edit landed.

    The residual ``"unchanged"`` substring gate (assessor.py:774 pre-G0R)
    turned this into an error-severity ``implementation_result`` issue; it is
    gone — prose never gates scoring.
    """
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "KSampler"}},
        "outcome": {"kind": "candidate"},
        "change_details": {"landed_operation_count": 1},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": True,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")
    (tmp_path / "implementation_result.json").write_text(
        json.dumps({"message": "Updated the sampler; other nodes are unchanged."}),
        encoding="utf-8",
    )

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert assessment["passed"] is True, assessment["issues"]
    assert assessment["verdict"] == "pass"
    assert not [
        issue for issue in assessment["issues"] if issue["check"] == "implementation_result"
    ]


def _successful_edit_response() -> dict:
    return {
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


def _frame_graph(*, source_value: int, target_value: int, linked: bool, shared_source: bool = False) -> dict:
    """A target node with a widget at index 0, optionally fed by a PrimitiveInt."""
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
    if linked and shared_source:
        nodes.append(
            {
                "id": 4,
                "type": "OtherConsumer",
                "widgets_values": [8],
                "inputs": [{"name": "other_count", "type": "INT", "link": 11}],
            }
        )
        links.append([11, 1, 0, 4, 0, "INT"])
    return {"nodes": nodes, "links": links}


def _effective_edit_scenario(**assessment_overrides: object) -> dict:
    scenario = {
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
                }
            ],
        },
    }
    scenario["assessment"].update(assessment_overrides)
    return scenario


def test_model_request_size_and_content_gates_removed(tmp_path: Path) -> None:
    """B12/B13: max_model_request_bytes and forbid_model_request_substrings are
    deleted scoring prejudice.  Even when a scenario still declares them, an
    oversized model_request.json containing a forbidden substring must NOT
    gate the run — prose length/content never gates."""
    (tmp_path / "response.json").write_text(
        json.dumps(_successful_edit_response()), encoding="utf-8"
    )
    (tmp_path / "model_request.json").write_text(
        json.dumps(
            {
                "turns": [
                    {"messages": [{"content": 'raw "workflow_schema" leaked'}]}
                ]
            }
        )
        * 200,
        encoding="utf-8",
    )
    scenario = {
        "id": "hotshot",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "max_model_request_bytes": 100,
            "forbid_model_request_substrings": ['"workflow_schema"'],
        },
    }
    assessment = assess_live_output_dir(tmp_path, scenario=scenario)

    assert assessment["passed"] is True, assessment["issues"]
    assert not [
        issue
        for issue in assessment["issues"]
        if issue["check"].startswith("model_request")
    ]


def test_shared_source_effective_edit_passes_by_default(tmp_path: Path) -> None:
    """B12/B13: a change landing through a shared linked source is a valid
    edit by default — the agent may intentionally edit one source feeding
    several consumers."""
    run_dir = tmp_path / "shared-default"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "response.json").write_text(
        json.dumps(_successful_edit_response()), encoding="utf-8"
    )
    (run_dir / "original.ui.json").write_text(
        json.dumps(_frame_graph(source_value=8, target_value=8, linked=True, shared_source=True)),
        encoding="utf-8",
    )
    (run_dir / "candidate.ui.json").write_text(
        json.dumps(_frame_graph(source_value=16, target_value=8, linked=True, shared_source=True)),
        encoding="utf-8",
    )

    assessment = assess_live_output_dir(run_dir, scenario=_effective_edit_scenario())

    assert assessment["passed"] is True, assessment["issues"]
    assert not [
        issue for issue in assessment["issues"] if issue["check"] == "shared_effective_source_edit"
    ]


def test_shared_source_effective_edit_fails_when_isolation_opted_in(tmp_path: Path) -> None:
    """The shared-source error survives only as an explicit scenario opt-in:
    assessment.isolate_shared_effective_sources=true."""
    run_dir = tmp_path / "shared-isolated"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "response.json").write_text(
        json.dumps(_successful_edit_response()), encoding="utf-8"
    )
    (run_dir / "original.ui.json").write_text(
        json.dumps(_frame_graph(source_value=8, target_value=8, linked=True, shared_source=True)),
        encoding="utf-8",
    )
    (run_dir / "candidate.ui.json").write_text(
        json.dumps(_frame_graph(source_value=16, target_value=8, linked=True, shared_source=True)),
        encoding="utf-8",
    )

    assessment = assess_live_output_dir(
        run_dir,
        scenario=_effective_edit_scenario(isolate_shared_effective_sources=True),
    )

    assert assessment["passed"] is False
    shared = [
        issue for issue in assessment["issues"] if issue["check"] == "shared_effective_source_edit"
    ]
    assert shared
    assert shared[0]["severity"] == "error"


def test_equivalent_effect_different_paths_score_equally(tmp_path: Path) -> None:
    """Effects determine edit correctness: a direct widget edit and an edit
    through a linked source that land the SAME effective value must score
    identically — implementation path never affects the score."""
    direct_dir = tmp_path / "direct-widget"
    direct_dir.mkdir(parents=True, exist_ok=True)
    (direct_dir / "response.json").write_text(
        json.dumps(_successful_edit_response()), encoding="utf-8"
    )
    (direct_dir / "original.ui.json").write_text(
        json.dumps(_frame_graph(source_value=8, target_value=8, linked=False)),
        encoding="utf-8",
    )
    (direct_dir / "candidate.ui.json").write_text(
        json.dumps(_frame_graph(source_value=8, target_value=16, linked=False)),
        encoding="utf-8",
    )

    linked_dir = tmp_path / "linked-source"
    linked_dir.mkdir(parents=True, exist_ok=True)
    (linked_dir / "response.json").write_text(
        json.dumps(_successful_edit_response()), encoding="utf-8"
    )
    (linked_dir / "original.ui.json").write_text(
        json.dumps(_frame_graph(source_value=8, target_value=8, linked=True)),
        encoding="utf-8",
    )
    (linked_dir / "candidate.ui.json").write_text(
        json.dumps(_frame_graph(source_value=16, target_value=8, linked=True)),
        encoding="utf-8",
    )

    scenario = _effective_edit_scenario()
    direct = assess_live_output_dir(direct_dir, scenario=scenario)
    linked = assess_live_output_dir(linked_dir, scenario=scenario)

    assert direct["passed"] is True, direct["issues"]
    assert linked["passed"] is True, linked["issues"]
    assert direct["issues"] == linked["issues"]
    assert direct["error_count"] == linked["error_count"] == 0
