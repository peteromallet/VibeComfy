from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness import assessor as assessor_module
from tests.live_agentic_harness.assessor import (
    AssessmentPublicationError,
    assess_live_output_dir,
)
from tests.live_agentic_harness.intent_judge import (
    judge_edit_intent,
    judge_grounded_refusal,
    judge_semantic_answer,
)

_LINEAGE_SHA = "b" * 64


def _seed_lineage(output_dir: Path, scenario_id: str | None = None) -> None:
    """Attach a typed artifact-lineage manifest (sidecar + envelope copy).

    G5-B4-MUST-003 made absent lineage grade ``undetermined``; these
    score-honesty tests exercise OTHER structured checks, so they seed
    valid all-primary lineage instead of relying on the old fail-open
    absence behavior. Mirrors tests/test_live_agentic_harness_guard_contract.py::_seed_lineage.
    """
    from vibecomfy.comfy_nodes.agent.artifact_lineage import (
        LINK_KINDS,
        build_artifact_lineage,
        primary_row,
    )

    if scenario_id is None:
        scenario_id = (
            output_dir.name
            if output_dir.name and "tmp" not in output_dir.name
            else "s1"
        )
    manifest = build_artifact_lineage(
        lineage={"scenario_id": scenario_id},
        rows=[primary_row(kind, _LINEAGE_SHA) for kind in LINK_KINDS],
    )
    manifest["binding"] = {"scenario_id": scenario_id}
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(json.dumps(manifest))
    (output_dir / "artifact_lineage.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    response_path = output_dir / "response.json"
    if response_path.is_file():
        response = json.loads(response_path.read_text(encoding="utf-8"))
        report = response.setdefault("report", {})
        executor = report.setdefault("executor", {})
        executor["artifact_lineage"] = frozen
        response_path.write_text(json.dumps(response), encoding="utf-8")


def test_recovered_upstream_500_is_warning_when_candidate_succeeded(
    tmp_path: Path,
) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "TestNode"}},
        "change_details": {"landed_operation_count": 1},
        "warnings": ["Hivemind HTTP error 500: Internal Server Error"],
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")
    _seed_lineage(tmp_path)

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True}
        },
    )

    upstream = [
        issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"
    ]
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
        scenario={
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True}
        },
    )

    upstream = [
        issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"
    ]
    assert upstream
    assert {issue["severity"] for issue in upstream} == {"error"}
    assert assessment["passed"] is False


def test_skipped_queue_validation_is_warning_when_candidate_succeeded(
    tmp_path: Path,
) -> None:
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
    _seed_lineage(tmp_path)

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True}
        },
    )

    assert assessment["passed"] is True
    assert [issue["check"] for issue in assessment["issues"]] == [
        "queue_validate_skipped"
    ]
    assert assessment["issues"][0]["severity"] == "warning"


def test_skipped_queue_validation_does_not_hide_other_failed_gates(
    tmp_path: Path,
) -> None:
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
    _seed_lineage(tmp_path)

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True}
        },
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
                {
                    "stage": "queue_validate",
                    "ok": False,
                    "issues": [{"code": "schema_less_queue_blocker"}],
                },
            ]
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")
    _seed_lineage(tmp_path)

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True}
        },
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
        _seed_lineage(run_dir)
        assessment = assess_live_output_dir(run_dir, scenario=scenario)
        scores.append((assessment["passed"], assessment["error_count"]))

    assert scores == [(True, 0)] * len(passing_messages), scores
    assert all(
        issue["check"] not in {"message_artifact", "implementation_result"}
        for index in range(len(passing_messages))
        for issue in assess_live_output_dir(
            tmp_path / f"pass-{index}", scenario=scenario
        )["issues"]
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


def test_implementation_result_unchanged_prose_does_not_gate_scoring(
    tmp_path: Path,
) -> None:
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
    _seed_lineage(tmp_path)

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True}
        },
    )

    assert assessment["passed"] is True, assessment["issues"]
    assert assessment["verdict"] == "pass"
    assert not [
        issue
        for issue in assessment["issues"]
        if issue["check"] == "implementation_result"
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


def _frame_graph(
    *, source_value: int, target_value: int, linked: bool, shared_source: bool = False
) -> dict:
    """A target node with a widget at index 0, optionally fed by a PrimitiveInt."""
    link_id = 10 if linked else None
    nodes = []
    links = []
    if linked:
        nodes.append(
            {"id": 1, "type": "PrimitiveInt", "widgets_values": [source_value]}
        )
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
            {"turns": [{"messages": [{"content": 'raw "workflow_schema" leaked'}]}]}
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
    _seed_lineage(tmp_path, scenario_id=str(scenario["id"]))
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
        json.dumps(
            _frame_graph(
                source_value=8, target_value=8, linked=True, shared_source=True
            )
        ),
        encoding="utf-8",
    )
    (run_dir / "candidate.ui.json").write_text(
        json.dumps(
            _frame_graph(
                source_value=16, target_value=8, linked=True, shared_source=True
            )
        ),
        encoding="utf-8",
    )
    _seed_lineage(run_dir, scenario_id="effective-edit")

    assessment = assess_live_output_dir(run_dir, scenario=_effective_edit_scenario())

    assert assessment["passed"] is True, assessment["issues"]
    assert not [
        issue
        for issue in assessment["issues"]
        if issue["check"] == "shared_effective_source_edit"
    ]


def test_shared_source_effective_edit_fails_when_isolation_opted_in(
    tmp_path: Path,
) -> None:
    """The shared-source error survives only as an explicit scenario opt-in:
    assessment.isolate_shared_effective_sources=true."""
    run_dir = tmp_path / "shared-isolated"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "response.json").write_text(
        json.dumps(_successful_edit_response()), encoding="utf-8"
    )
    (run_dir / "original.ui.json").write_text(
        json.dumps(
            _frame_graph(
                source_value=8, target_value=8, linked=True, shared_source=True
            )
        ),
        encoding="utf-8",
    )
    (run_dir / "candidate.ui.json").write_text(
        json.dumps(
            _frame_graph(
                source_value=16, target_value=8, linked=True, shared_source=True
            )
        ),
        encoding="utf-8",
    )

    assessment = assess_live_output_dir(
        run_dir,
        scenario=_effective_edit_scenario(isolate_shared_effective_sources=True),
    )

    assert assessment["passed"] is False
    shared = [
        issue
        for issue in assessment["issues"]
        if issue["check"] == "shared_effective_source_edit"
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
    _seed_lineage(direct_dir, scenario_id="effective-edit")

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
    _seed_lineage(linked_dir, scenario_id="effective-edit")

    scenario = _effective_edit_scenario()
    direct = assess_live_output_dir(direct_dir, scenario=scenario)
    linked = assess_live_output_dir(linked_dir, scenario=scenario)

    assert direct["passed"] is True, direct["issues"]
    assert linked["passed"] is True, linked["issues"]
    assert direct["issues"] == linked["issues"]
    assert direct["error_count"] == linked["error_count"] == 0


def test_research_health_control_cannot_pass_with_zero_calls_or_evidence(
    tmp_path: Path,
) -> None:
    response = {
        "ok": True,
        "route": "research",
        "graph_unchanged": True,
        "reply": "No graph attached; implementation skipped.",
        "evidence": {"research": {}},
        "report": {
            "executor": {
                "deepseek_usage": {"n_calls": 0},
                "model_attempts": [],
            }
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {
                "expect_graph_changed": False,
                "require_executed_research": True,
            },
            "classification": {"kind": "health_control"},
        },
    )

    assert assessment["passed"] is False
    assert {issue["check"] for issue in assessment["issues"]} >= {
        "research_model_call",
        "research_tool_execution",
        "research_evidence_present",
    }


def test_research_health_control_accepts_executed_grounded_evidence(
    tmp_path: Path,
) -> None:
    response = {
        "ok": True,
        "route": "research",
        "graph_unchanged": True,
        "reply": "The retrieved precedent supports a lower-step option.",
        "evidence": {
            "research": {
                "research_attempt": "grounded",
                "tool_calls_executed": 2,
                "evidence_artifacts": 1,
                "citations": ["hivemind:1"],
            }
        },
        "report": {
            "executor": {
                "deepseek_usage": {"n_calls": 2},
                "model_attempts": [{"phase": "research", "outcome": "success"}],
            }
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "assessment": {
                "expect_graph_changed": False,
                "require_executed_research": True,
            },
            "classification": {"kind": "health_control"},
        },
    )

    assert assessment["passed"] is True, assessment["issues"]


def test_inspect_health_control_rejects_reply_that_contradicts_locked_census(
    tmp_path: Path,
) -> None:
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}},
    }
    response = {
        "ok": True,
        "route": "inspect",
        "graph_unchanged": True,
        "reply": (
            "Based on the workflow inspection, the graph is currently empty — "
            "it contains 0 nodes and no links."
        ),
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "graph": graph,
            "assessment": {
                "expect_graph_changed": False,
                "require_graph_census_consistency": True,
            },
            "classification": {"kind": "health_control"},
        },
    )

    assert assessment["passed"] is False
    census = [
        issue
        for issue in assessment["issues"]
        if issue["check"] == "graph_census_consistency"
    ]
    assert census and "2 nodes and 1 edges" in census[0]["detail"]


def _snapshot_response_for_lane(lane: str) -> tuple[dict, dict]:
    response = {
        "ok": True,
        "graph_unchanged": True,
        "route": "respond",
        "outcome": {"kind": "respond"},
        "gates": {},
        "artifacts": {},
        "report": {"executor": {"plan": {"implement": False, "route": "respond"}}},
    }
    scenario: dict = {"id": f"snapshot-{lane}", "query": "perform the requested task"}
    if lane == "edit":
        response.update(
            {
                "graph_unchanged": False,
                "route": "revise",
                "outcome": {"kind": "candidate", "changes": []},
                "change_details": {"landed_operation_count": 1},
            }
        )
        scenario["apply"] = True
    elif lane == "refusal":
        response.update(
            {
                "route": "revise",
                "outcome": {
                    "kind": "requires_custom_nodes",
                    "candidates": [],
                },
            }
        )
        scenario.update(
            {
                "apply": True,
                "assessment": {
                    "allow_safe_refusal_outcome_kinds": ["requires_custom_nodes"]
                },
            }
        )
    else:
        scenario["answer_rubric"] = {
            "expected_criteria": ["answer the question"],
            "fail_conditions": [],
            "pass_condition": "grounded answer",
        }
        response["message"] = "The graph is already configured."
    return response, scenario


@pytest.mark.parametrize("lane", ["edit", "refusal", "semantic"])
def test_assessor_reads_once_and_injects_one_immutable_snapshot_per_judge_lane(
    tmp_path: Path, monkeypatch, lane: str
) -> None:
    response, scenario = _snapshot_response_for_lane(lane)
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    reads = 0
    real_read_text = Path.read_text
    seen: dict[str, dict] = {}
    real_load_response = assessor_module._load_response_json
    loaded: dict[str, object] = {}

    def capture_load_response(path: Path):
        snapshot, state = real_load_response(path)
        loaded["snapshot"] = snapshot
        return snapshot, state

    def counting_read_text(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal reads
        if path == response_path:
            reads += 1
        return real_read_text(path, *args, **kwargs)

    def judge(*args, response_snapshot, **kwargs):  # noqa: ANN002, ANN003
        seen["snapshot"] = response_snapshot
        assert response_snapshot is loaded["snapshot"]
        assert json.loads(json.dumps(response_snapshot)) == response
        with pytest.raises(TypeError, match="immutable"):
            response_snapshot["outcome"]["kind"] = "mutated"
        response_path.write_text(
            json.dumps({"ok": False, "graph_unchanged": "not-a-boolean"}),
            encoding="utf-8",
        )
        return {"pass_": True, "criteria": {}, "rationale": "injected snapshot"}

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    monkeypatch.setattr(assessor_module, "_load_response_json", capture_load_response)
    monkeypatch.setattr(
        assessor_module,
        {
            "edit": "judge_edit_intent",
            "refusal": "judge_grounded_refusal",
            "semantic": "judge_semantic_answer",
        }[lane],
        judge,
    )

    assessment = assess_live_output_dir(tmp_path, scenario=scenario)

    assert reads == 1
    assert seen["snapshot"]["ok"] is True
    assert assessment["expect_graph_changed"] is (lane != "semantic")


@pytest.mark.parametrize("lane", ["edit", "refusal", "semantic"])
def test_injected_judges_never_reopen_response_json(
    tmp_path: Path, monkeypatch, lane: str
) -> None:
    response_path = tmp_path / "response.json"
    response_path.write_text('{"mutated": true}', encoding="utf-8")
    snapshot = {
        "ok": True,
        "graph_unchanged": True,
        "outcome": {"kind": "respond"},
        "message": "The graph is already configured.",
    }
    reads = 0
    real_read_text = Path.read_text

    def counting_read_text(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal reads
        if path == response_path:
            reads += 1
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    if lane == "edit":
        judge_edit_intent(
            tmp_path,
            {"query": "change the graph"},
            response_snapshot=snapshot,
        )
    elif lane == "refusal":
        judge_grounded_refusal(tmp_path, {}, response_snapshot=snapshot)
    else:
        judge_semantic_answer(
            tmp_path,
            {
                "query": "explain the graph",
                "answer_rubric": {"pass_condition": "grounded"},
            },
            response_snapshot=snapshot,
        )

    assert reads == 0


def test_malformed_response_is_injected_as_none_without_semantic_disk_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    response_path = tmp_path / "response.json"
    response_path.write_text(
        '{"ok": true, "graph_unchanged": "wrong"}', encoding="utf-8"
    )
    reads = 0
    real_read_text = Path.read_text

    def counting_read_text(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal reads
        if path == response_path:
            reads += 1
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "query": "explain this graph",
            "answer_rubric": {"pass_condition": "grounded"},
        },
    )

    assert reads == 1
    assert assessment["verdict"] == "undetermined"
    assert any(issue["check"] == "response_malformed" for issue in assessment["issues"])


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"ok": "true", "graph_unchanged": True},
        {"ok": True, "graph_unchanged": 0},
        {"ok": True, "graph_unchanged": True, "outcome": []},
        {"ok": True, "graph_unchanged": True, "readiness": "ready"},
        {"ok": True, "graph_unchanged": True, "gates": []},
        {"ok": True, "graph_unchanged": True, "artifacts": "paths"},
        {"ok": True, "graph_unchanged": True, "route": []},
        {"ok": True, "graph_unchanged": True, "outcome": None},
        {"ok": True, "graph_unchanged": True, "outcome": {"kind": 1}},
        {"ok": True, "graph_unchanged": True, "readiness": {"ready": "yes"}},
        {"ok": True, "graph_unchanged": True, "gates": {"queue_validate_ok": 1}},
        {"ok": True, "graph_unchanged": True, "artifacts": {"original_ui": 1}},
        {
            "ok": True,
            "graph_unchanged": True,
            "report": {"executor": {"plan": {"implement": "true"}}},
        },
        {"ok": True, "graph_unchanged": True, "report": []},
        {"ok": True, "graph_unchanged": True, "report": {"executor": []}},
        {
            "ok": True,
            "graph_unchanged": True,
            "report": {"executor": {"plan": []}},
        },
    ],
)
def test_type_invalid_response_envelopes_are_malformed_and_never_pass(
    tmp_path: Path, response: dict
) -> None:
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(tmp_path)

    assert assessment["passed"] is False
    assert assessment["verdict"] == "undetermined"
    assert {(issue["check"], issue["severity"]) for issue in assessment["issues"]} == {
        ("response_malformed", "undetermined")
    }


@pytest.mark.parametrize(
    "response",
    [
        {"graph_unchanged": True},
        {"ok": True, "graph_unchanged": True, "outcome": {}},
        {
            "ok": True,
            "graph_unchanged": False,
            "route": "revise",
            "outcome": {"kind": "edit"},
            "change_details": {"landed_operation_count": 1},
            "accepted_batch": [{}],
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {"kind": "noop", "changes": [{}]},
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {"kind": "requires_custom_nodes", "missing_classes": [1]},
        },
        {
            "ok": True,
            "graph_unchanged": False,
            "route": "revise",
            "outcome": {
                "kind": "candidate",
                "changes": [{"uid": "sampler", "field_path": "steps"}],
            },
            "candidate_graph": {"nodes": [], "links": []},
            "change_details": {"landed_operation_count": 1},
            "accepted_batch": [
                {"op": {"op": "set_node_field", "target": ["", "sampler"]}}
            ],
        },
        {
            "ok": True,
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "candidate_graph": {"garbage": "x"},
            "change_details": {"landed_operation_count": 1},
        },
        {
            "ok": True,
            "graph_unchanged": False,
            "outcome": {"kind": "candidate_transaction"},
            "candidate_transaction": {"garbage": "x"},
            "change_details": {"landed_operation_count": 1},
        },
        {
            "ok": True,
            "graph_unchanged": False,
            "outcome": {
                "kind": "candidate",
                "changes": [{"op": "set_node_field"}],
            },
            "candidate_graph": {"nodes": [], "links": []},
            "change_details": {"landed_operation_count": 1},
        },
        {
            "ok": True,
            "graph_unchanged": False,
            "outcome": {
                "kind": "candidate",
                "changes": [{"op": "definitely_not_an_op"}],
            },
            "candidate_graph": {"nodes": [], "links": []},
            "change_details": {"landed_operation_count": 1},
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "candidates": [{"expected_classes": [3]}],
            },
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "missing_classes": [],
            },
            "message": "A custom node is required.",
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "candidates": [
                    {
                        "expected_classes": ["MissingNode"],
                        "evidence": [],
                    }
                ],
            },
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "candidates": [
                    {
                        "expected_classes": ["MissingNode"],
                        "evidence": [{"garbage": "x"}],
                    }
                ],
            },
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {"kind": "clarify", "candidates": []},
            "message": "Which node should change?",
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {"kind": "budget", "candidates": []},
            "message": "The execution budget was exhausted.",
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {"kind": "noop", "reason": "No changes."},
            "accepted_batch": {},
        },
    ],
)
def test_semantically_incomplete_response_envelopes_never_pass(
    tmp_path: Path, response: dict
) -> None:
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"skip_intent_judge": True}},
    )

    assert assessment["passed"] is False
    assert assessment["verdict"] == "undetermined"
    assert any(
        issue["check"] == "response_malformed" and issue["severity"] == "undetermined"
        for issue in assessment["issues"]
    )


@pytest.mark.parametrize(
    "response",
    [
        {
            "ok": True,
            "graph_unchanged": True,
            "outcome": {"kind": "noop", "reason": "Nothing needed."},
        },
        {
            "ok": True,
            "graph_unchanged": True,
            "route": "adapt",
            "outcome": {
                "kind": "requires_custom_nodes",
                "candidates": [{"expected_classes": ["MissingNode"]}],
            },
        },
        {
            "ok": False,
            "graph_unchanged": True,
            "error": "Provider failed before graph execution.",
        },
        {
            "ok": False,
            "outcome": {
                "kind": "error",
                "failure_kind": "ProviderError",
                "stage": "ingest",
                "retryable": True,
                "next_action": "retry",
                "graph_unchanged": True,
            },
        },
    ],
)
def test_valid_terminal_response_variants_remain_accepted(response: dict) -> None:
    assert assessor_module._response_envelope_is_valid(response) is True


def test_apply_true_is_authoritative_without_assessment_flag(tmp_path: Path) -> None:
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "route": "revise",
                "outcome": {"kind": "noop"},
            }
        ),
        encoding="utf-8",
    )

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "apply": True,
            "query": "change the graph",
            "assessment": {"skip_intent_judge": True},
        },
    )

    assert assessment["expect_graph_changed"] is True
    assert assessment["verdict"] == "fail"
    assert any(issue["check"] == "graph_changed" for issue in assessment["issues"])


def test_response_authored_plan_cannot_create_scenario_edit_obligation(
    tmp_path: Path,
) -> None:
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "route": "respond",
                "outcome": {"kind": "respond"},
                "report": {
                    "executor": {"plan": {"implement": True, "route": "revise"}}
                },
            }
        ),
        encoding="utf-8",
    )

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"classification": {"kind": "health_control"}},
    )

    assert assessment["expect_graph_changed"] is False
    assert not any(issue["check"] == "graph_changed" for issue in assessment["issues"])


def test_assessment_publication_failure_preserves_stale_canonical_and_raises(
    tmp_path: Path, monkeypatch
) -> None:
    stale = '{"verdict": "stale"}\n'
    assessment_path = tmp_path / "assessment.json"
    assessment_path.write_text(stale, encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "route": "respond",
                "outcome": {"kind": "respond"},
            }
        ),
        encoding="utf-8",
    )

    def deny_replace(source, destination):  # noqa: ANN001
        assert Path(source).parent == assessment_path.parent
        assert Path(destination) == assessment_path
        assert Path(source).name.startswith(".assessment.")
        raise PermissionError("denied")

    monkeypatch.setattr(assessor_module.os, "replace", deny_replace)

    with pytest.raises(AssessmentPublicationError) as excinfo:
        assess_live_output_dir(tmp_path)

    assert isinstance(excinfo.value.__cause__, PermissionError)
    assert assessment_path.read_text(encoding="utf-8") == stale
    assert list(tmp_path.glob(".assessment.*.tmp")) == []
