from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.intent_judge import (
    _parse_refusal_verdict,
    _parse_semantic_verdict,
    _parse_verdict,
    judge_edit_intent,
    judge_grounded_refusal,
    judge_semantic_answer,
)


def _edit_verdict_content(**overrides: object) -> dict:
    content = {
        "pass_": True,
        "criteria": {
            "correct_node_targeted": True,
            "correct_parameter_changed": True,
            "value_semantically_matches_intent": True,
            "no_orphaned_wiring": True,
        },
        "rationale": "all criteria satisfied",
    }
    content.update(overrides)
    return content


def _semantic_verdict_content(**overrides: object) -> dict:
    content = {
        "pass_": True,
        "criteria": {
            "grounded": True,
            "relevant": True,
            "correct": True,
        },
        "rationale": "all semantic criteria satisfied",
    }
    content.update(overrides)
    return content


def _refusal_verdict_content(**overrides: object) -> dict:
    content = {
        "pass_": True,
        "criteria": {
            "supported_blocker": True,
            "no_representable_edit": True,
            "specific_next_action": True,
            "no_fabricated_inability": True,
        },
        "rationale": "all refusal criteria satisfied",
    }
    content.update(overrides)
    return content


def test_parse_verdict_string_false_pass_with_all_criteria_true_is_not_pass() -> None:
    """D13 rework: a string-typed pass_ (``"false"``) is malformed, not a
    coercible value — the verdict must fail closed even with all criteria
    true."""
    verdict = _parse_verdict(json.dumps(_edit_verdict_content(pass_="false")))

    assert verdict["pass_"] is False
    assert all(verdict["criteria"].values())


def test_parse_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
    """D13 rework: the self-declared pass_ is never trusted — a false
    criterion fails the verdict closed."""
    criteria = _edit_verdict_content()["criteria"]
    criteria["correct_parameter_changed"] = False
    verdict = _parse_verdict(json.dumps(_edit_verdict_content(criteria=criteria)))

    assert verdict["pass_"] is False
    assert verdict["criteria"]["correct_parameter_changed"] is False


def test_parse_verdict_string_typed_criteria_booleans_are_not_pass() -> None:
    """D13 rework: string-typed criteria (``"true"``/``"false"``) are
    malformed, not coercible — the verdict must fail closed."""
    criteria = _edit_verdict_content()["criteria"]
    criteria["correct_node_targeted"] = "true"
    criteria["no_orphaned_wiring"] = "false"
    verdict = _parse_verdict(json.dumps(_edit_verdict_content(criteria=criteria)))

    assert verdict["pass_"] is False
    # Malformed (string-typed) criteria are excluded from the normalized
    # dict — only explicit booleans are retained — and a required criterion
    # that is not explicitly true fails the verdict closed.
    assert verdict["criteria"] == {
        "correct_parameter_changed": True,
        "value_semantically_matches_intent": True,
    }


def test_parse_verdict_pass_true_with_missing_criteria_is_not_pass() -> None:
    """D13 rework: a missing required criterion fails closed — pass_ requires
    ALL criteria to be explicitly true."""
    criteria = _edit_verdict_content()["criteria"]
    del criteria["value_semantically_matches_intent"]
    verdict = _parse_verdict(json.dumps(_edit_verdict_content(criteria=criteria)))

    assert verdict["pass_"] is False
    assert "value_semantically_matches_intent" not in verdict["criteria"]


def test_parse_verdict_missing_pass_field_is_not_pass() -> None:
    """D13 rework: a missing pass_ field is malformed output — fail closed."""
    content = _edit_verdict_content()
    del content["pass_"]
    verdict = _parse_verdict(json.dumps(content))

    assert verdict["pass_"] is False


def test_parse_verdict_genuine_all_true_is_pass() -> None:
    """D13 rework, positive control: explicit true booleans on every required
    criterion pass."""
    verdict = _parse_verdict(json.dumps(_edit_verdict_content()))

    assert verdict["pass_"] is True
    assert all(verdict["criteria"].values())


def test_parse_refusal_verdict_genuine_all_true_is_pass() -> None:
    """D13 rework, positive control: a grounded refusal (all four refusal
    criteria explicitly true) passes."""
    verdict = _parse_refusal_verdict(json.dumps(_refusal_verdict_content()))

    assert verdict["pass_"] is True
    assert all(verdict["criteria"].values())


def test_parse_refusal_verdict_string_false_pass_with_all_criteria_true_is_not_pass() -> None:
    """D13 rework: a string-typed pass_ fails the refusal verdict closed too."""
    verdict = _parse_refusal_verdict(json.dumps(_refusal_verdict_content(pass_="false")))

    assert verdict["pass_"] is False
    assert all(verdict["criteria"].values())


def test_parse_semantic_verdict_genuine_all_true_is_pass() -> None:
    verdict = _parse_semantic_verdict(json.dumps(_semantic_verdict_content()))

    assert verdict["pass_"] is True
    assert all(verdict["criteria"].values())


def test_parse_semantic_verdict_string_false_pass_with_all_criteria_true_is_not_pass() -> None:
    verdict = _parse_semantic_verdict(json.dumps(_semantic_verdict_content(pass_="false")))

    assert verdict["pass_"] is False
    assert all(verdict["criteria"].values())


def test_parse_semantic_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
    criteria = _semantic_verdict_content()["criteria"]
    criteria["grounded"] = False
    verdict = _parse_semantic_verdict(json.dumps(_semantic_verdict_content(criteria=criteria)))

    assert verdict["pass_"] is False
    assert verdict["criteria"]["grounded"] is False


def test_parse_refusal_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
    """D13 rework: the refusal verdict is derived from its criteria — a
    fabricated pass_=true with a false criterion fails closed."""
    criteria = _refusal_verdict_content()["criteria"]
    criteria["supported_blocker"] = False
    verdict = _parse_refusal_verdict(json.dumps(_refusal_verdict_content(criteria=criteria)))

    assert verdict["pass_"] is False
    assert verdict["criteria"]["supported_blocker"] is False


def test_intent_judge_surfaces_derived_fail_for_fabricated_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The assessor-visible verdict is derived, not raw: a fabricated
    pass_=true with a false criterion surfaces as pass_ False, never True."""
    (tmp_path / "original.ui.json").write_text(
        json.dumps({"nodes": []}), encoding="utf-8"
    )
    (tmp_path / "candidate.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1}]}), encoding="utf-8"
    )
    criteria = _edit_verdict_content()["criteria"]
    criteria["correct_parameter_changed"] = False

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        return {"content": json.dumps(_edit_verdict_content(criteria=criteria))}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(tmp_path, {"query": "set seed to 42"})

    assert verdict["pass_"] is False
    assert verdict["criteria"]["correct_parameter_changed"] is False


def test_grounded_refusal_judge_surfaces_derived_fail_for_fabricated_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The assessor-visible refusal verdict is derived, not raw: a fabricated
    pass_=true with a false criterion surfaces as pass_ False."""
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "outcome": {"kind": "requires_custom_nodes"},
                "message": "the node class is unavailable",
            }
        ),
        encoding="utf-8",
    )
    criteria = _refusal_verdict_content()["criteria"]
    criteria["no_fabricated_inability"] = False

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        return {"content": json.dumps(_refusal_verdict_content(criteria=criteria))}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_grounded_refusal(tmp_path, {"query": "set seed to 42"})

    assert verdict["pass_"] is False
    assert verdict["criteria"]["no_fabricated_inability"] is False


def test_intent_judge_includes_scenario_desired_rubric(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    (tmp_path / "original.ui.json").write_text(
        json.dumps({"nodes": []}), encoding="utf-8"
    )
    (tmp_path / "candidate.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1}]}), encoding="utf-8"
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        seen["messages"] = messages
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "desired outcome satisfied",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    desired = {
        "outcome": "seed is 42",
        "quality": "only the intended seed changes",
        "alternatives_ok": False,
    }
    verdict = judge_edit_intent(
        tmp_path,
        {"query": "set seed to 42", "desired": desired},
    )

    assert verdict["pass_"] is True
    messages = seen["messages"]
    assert isinstance(messages, list)
    assert "Scenario-specific desired outcome" in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert payload["desired_outcome"] == desired


def test_intent_judge_includes_compiled_api_schema_context(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    candidate.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "original_ui": str(original),
                    "candidate_ui": str(candidate),
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implementation_payload.json").write_text(
        json.dumps(
            {
                "graph": {
                    "compiled_api": {
                        "3": {
                            "class_type": "llama_cpp_parameters",
                            "inputs": {
                                "max_tokens": 512,
                                "temperature": 0.8,
                                "top_p": 0.9,
                            },
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["messages"] = messages
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "ok",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(
        tmp_path,
        {"query": "set temperature to 0.8 and max tokens to 512"},
    )

    assert verdict["pass_"] is True
    messages = seen["messages"]
    assert isinstance(messages, list)
    payload = json.loads(messages[1]["content"])
    assert payload["schema_context"]["compiled_api"]["3"]["inputs"]["temperature"] == 0.8
    assert "Schema and widget evidence" in messages[0]["content"]


def test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 184,
                        "type": "Florence2Run",
                        "outputs": [{"name": "STRING", "type": "STRING", "slot_index": 0, "links": [7]}],
                    },
                    {
                        "id": 182,
                        "type": "StringFunction",
                        "inputs": [{"name": "text_a", "type": "STRING", "link": 7}],
                        "widgets_values": ["append", "", "", "", "real footage", "fabricated couch caption"],
                    },
                ],
                "links": [[7, 184, 0, 182, 0, "STRING"]],
            }
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 184,
                        "type": "Florence2Run",
                        "outputs": [{"name": "STRING", "type": "STRING", "slot_index": 0, "links": [7]}],
                    },
                    {
                        "id": 182,
                        "type": "StringFunction",
                        "inputs": [{"name": "text_a", "type": "STRING", "link": 7}],
                        "widgets_values": ["append", "", "", "", "real footage", ""],
                    },
                ],
                "links": [[7, 184, 0, 182, 0, "STRING"]],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "response.json").write_text(
        json.dumps({"artifacts": {"original_ui": str(original), "candidate_ui": str(candidate)}}),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["messages"] = messages
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "ok",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(
        tmp_path,
        {"query": "The prompt it generates doesn't capture what's actually in the image."},
    )

    assert verdict["pass_"] is True
    messages = seen["messages"]
    assert isinstance(messages, list)
    payload = json.loads(messages[1]["content"])
    dataflow = payload["schema_context"]["dataflow_context"]
    removals = dataflow["static_widget_removals_with_preserved_dynamic_inputs"]
    assert removals[0]["node_id"] == "182"
    assert removals[0]["widget_index"] == 5
    assert removals[0]["preserved_dynamic_inputs"] is True
    assert removals[0]["linked_inputs_post"][0]["source"]["class_type"] == "Florence2Run"
    assert "static widget" in messages[0]["content"]


def test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """A rich envelope without compiled_api still yields schema context (P3).

    The execution view is derived by compiling the IR (compile("api") is a
    function, not stored data); the schema_context key is preserved.
    """
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    candidate.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "original_ui": str(original),
                    "candidate_ui": str(candidate),
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implementation_payload.json").write_text(
        json.dumps(
            {
                "graph": {
                    "vibecomfy_format_version": "1.0",
                    "id": "sidecar-less",
                    "nodes": {
                        "10": {
                            "id": "10",
                            "class_type": "TripoRefineNode",
                            "uid": "uid-10",
                            "inputs": {"prompt": "refine it"},
                            "widgets": {"widget_0": ""},
                            "metadata": {"_ui": {"mode": 0}},
                        },
                        "17": {
                            "id": "17",
                            "class_type": "Preview3D",
                            "uid": "uid-17",
                            "inputs": {"images": ["10", 0]},
                            "widgets": {},
                            "metadata": {"_ui": {"mode": 0}},
                        },
                    },
                    "edges": [
                        {"from_node": "10", "from_output": "0", "to_node": "17", "to_input": "images"},
                    ],
                    "source": {"id": "sidecar-less", "path": None, "source_type": "workflow"},
                    "requirements": {},
                    "inputs": {},
                    "outputs": [{"node_id": "17", "output_type": "Preview3D"}],
                    "metadata": {},
                }
            }
        ),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["messages"] = messages
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "ok",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(
        tmp_path,
        {"query": "set the refine prompt to 'refine it'"},
    )

    assert verdict["pass_"] is True
    messages = seen["messages"]
    assert isinstance(messages, list)
    payload = json.loads(messages[1]["content"])
    compiled = payload["schema_context"]["compiled_api"]
    assert set(compiled) == {"10", "17"}
    assert compiled["10"]["inputs"]["prompt"] == "refine it"


def test_semantic_judge_surfaces_derived_fail_for_fabricated_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "SaveVideo"}]}), encoding="utf-8"
    )
    (tmp_path / "final.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "SaveVideo"}]}), encoding="utf-8"
    )
    (tmp_path / "response.json").write_text(
        json.dumps({"reply": "SaveVideo is the output node.", "ok": True}),
        encoding="utf-8",
    )
    criteria = _semantic_verdict_content()["criteria"]
    criteria["correct"] = False

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        lambda *args, **kwargs: {"content": json.dumps(_semantic_verdict_content(criteria=criteria))},
    )

    verdict = judge_semantic_answer(
        tmp_path,
        {
            "query": "what writes the video?",
            "answer_rubric": {
                "judge": "semantic_answer",
                "required_node_evidence": ["SaveVideo"],
                "expected_criteria": ["grounded", "relevant", "correct", "useful"],
            },
        },
    )

    assert verdict["pass_"] is False
    assert verdict["criteria"]["correct"] is False


def test_semantic_judge_empty_answer_fails_without_model_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "original.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (tmp_path / "response.json").write_text(json.dumps({"reply": "  ", "ok": True}), encoding="utf-8")

    def fail_if_called(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise AssertionError("empty answers must not call the model")

    monkeypatch.setattr("tests.live_agentic_harness.intent_judge.run_model_turn", fail_if_called)

    verdict = judge_semantic_answer(
        tmp_path,
        {"query": "explain this", "answer_rubric": {"judge": "semantic_answer"}},
    )

    assert verdict["pass_"] is False
    assert verdict["criteria"] == {"grounded": False, "relevant": False, "correct": False}


def test_semantic_judge_missing_ui_is_undetermined(tmp_path: Path) -> None:
    (tmp_path / "response.json").write_text(
        json.dumps({"reply": "It saves a video.", "ok": True}), encoding="utf-8"
    )

    verdict = judge_semantic_answer(
        tmp_path,
        {"query": "explain this", "answer_rubric": {"judge": "semantic_answer"}},
    )

    assert verdict["pass_"] is None
    assert "missing UI" in verdict["error"]


def test_semantic_judge_includes_rubric_and_ui_not_prose_as_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original = {"nodes": [{"id": 1, "type": "SaveVideo"}], "links": []}
    (tmp_path / "original.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps({"reply": "SaveVideo writes the clip.", "ok": True}), encoding="utf-8"
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        seen["payload"] = json.loads(messages[1]["content"])
        return {"content": json.dumps(_semantic_verdict_content())}

    monkeypatch.setattr("tests.live_agentic_harness.intent_judge.run_model_turn", fake_run_model_turn)

    verdict = judge_semantic_answer(
        tmp_path,
        {
            "query": "what writes the video?",
            "answer_rubric": {
                "judge": "semantic_answer",
                "required_node_evidence": ["SaveVideo"],
                "expected_criteria": ["grounded", "relevant", "correct", "useful"],
                "fail_conditions": ["hallucinated"],
            },
        },
    )

    assert verdict["pass_"] is True
    payload = seen["payload"]
    assert payload["original_ui"] == original
    assert payload["final_ui"] == original
    assert payload["required_node_evidence"] == ["SaveVideo"]
    assert payload["node_inventory"] == [{"id": 1, "type": "SaveVideo"}]
    assert payload["answer"] == "SaveVideo writes the clip."


def test_grounded_refusal_judge_includes_ui_inventory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "outcome": {"kind": "requires_custom_nodes"},
                "message": "the node class is unavailable",
                "graph_unchanged": True,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}]}),
        encoding="utf-8",
    )
    (tmp_path / "final.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}]}),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        seen["payload"] = json.loads(messages[1]["content"])
        return {"content": json.dumps(_refusal_verdict_content())}

    monkeypatch.setattr("tests.live_agentic_harness.intent_judge.run_model_turn", fake_run_model_turn)

    verdict = judge_grounded_refusal(tmp_path, {"query": "set seed to 42"})

    assert verdict["pass_"] is True
    payload = seen["payload"]
    assert payload["node_inventory"] == [{"id": 1, "type": "CheckpointLoaderSimple"}]
    assert payload["original_ui"]["nodes"][0]["type"] == "CheckpointLoaderSimple"
