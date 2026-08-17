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


def test_intent_judge_payload_has_no_raw_ui_widget_walker(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Batch 12 fix: the judge's payload carries NO judge-only raw-UI
    widget/link walker (``dataflow_context``) and no raw ``pre_ir``/``post_ir``
    dump.  The graph facts come from the renderer's lens subset (topology,
    same facts as the reply) + the accepted Δ only."""
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
    # No judge-only raw-UI walker: no dataflow_context anywhere in the
    # payload, and no raw pre_ir/post_ir dump.
    assert "dataflow_context" not in json.dumps(payload)
    assert "pre_ir" not in payload
    assert "post_ir" not in payload
    # The renderer's topology lens carries the preserved dynamic link
    # (Florence2Run -> StringFunction.text_a) — the same facts the reply
    # window carries (symmetry, Law 4).
    for side in ("pre", "post"):
        rendered = payload["renderer_lenses"][side]
        assert rendered is not None
        assert "## Topology" in rendered
        assert "184 -> 182 (184.0 -> 182.text_a)" in rendered


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
                            "inputs": {},
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


# ── Batch 10: the edit judge grades the canonical Δ (replayable) ────────────


def _judge_delta_response_json(original: Path, candidate: Path, *, ops: list[dict]) -> dict:
    return {
        "artifacts": {
            "original_ui": str(original),
            "candidate_ui": str(candidate),
        },
        # The accepted Δ is the batch: each accepted statement carries its
        # landed op.  No parallel delta_ops_envelope/change_details.
        "accepted_batch": [
            {
                "statement_index": 1,
                "source": 'set_field(uid="sampler", field="steps", value=30)',
                "op_kind": "edit",
                "touched_uids": ["sampler"],
                "op": ops[0] if ops else None,
            }
        ],
        "batch_turns": [
            {
                "statements": [
                    {
                        "statement_index": 1,
                        "source": 'set_field(uid="sampler", field="steps", value=30)',
                        "ok": True,
                        "landed": True,
                        "op_kind": "edit",
                        "touched_uids": ["sampler"],
                    },
                    {
                        "statement_index": 2,
                        "source": 'set_field(uid="sampler", field="seed", value=99)',
                        "ok": False,
                        "landed": False,
                        "op_kind": "edit",
                        "touched_uids": ["sampler"],
                    },
                ]
            }
        ],
    }


def test_intent_judge_grades_delta_with_replay_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """The judge receives the accepted batch + pre/post IR and grades the
    canonical Δ directly; the replay evidence is present."""
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    # widgets_values are positional in schema order (seed, control_after_generate,
    # steps, cfg, sampler_name, scheduler, denoise); steps is index 2.
    original.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "sampler",
                        "type": "KSampler",
                        "properties": {"vibecomfy_uid": "sampler"},
                        "widgets_values": [42, "fixed", 20, 7, "euler", "normal", 1],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "sampler",
                        "type": "KSampler",
                        "properties": {"vibecomfy_uid": "sampler"},
                        "widgets_values": [42, "fixed", 30, 7, "euler", "normal", 1],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "response.json").write_text(
        json.dumps(
            _judge_delta_response_json(
                original,
                candidate,
                ops=[{"op": "set_node_field", "target": ["", "sampler", "steps"], "value": 30}],
            )
        ),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["payload"] = json.loads(messages[1]["content"])
        seen["messages"] = messages
        return {"content": json.dumps(_edit_verdict_content())}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(tmp_path, {"query": "set steps to 30"})

    assert verdict["pass_"] is True
    payload = seen["payload"]
    assert payload["delta"]["ops"][0]["target"][2] == "steps"
    assert payload["delta_replay"]["verified"] is True
    assert payload["delta_replay"]["checked"] == 1
    # Only accepted statements are the Δ references.
    assert [item["statement_index"] for item in payload["accepted_batch"]] == [1]
    # The judge's graph facts are the renderer's lens subset — the diff lens
    # (canonical Δ) and topology — NOT a raw pre_ir/post_ir dump.
    assert "pre_ir" not in payload
    assert "post_ir" not in payload
    for side in ("pre", "post"):
        rendered = payload["renderer_lenses"][side]
        assert rendered is not None
        assert "## Diff" in rendered
        assert "sampler.steps = 30" in rendered
    assert "Accepted Δ" in seen["messages"][0]["content"]


def test_intent_judge_fails_closed_on_delta_replay_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """When the canonical Δ is not what actually changed (replay mismatch),
    the judge fails closed without a model call."""
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(
        json.dumps({"nodes": [{"id": "sampler", "type": "KSampler", "properties": {"vibecomfy_uid": "sampler"}}]}),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps({"nodes": [{"id": "sampler", "type": "KSampler", "properties": {"vibecomfy_uid": "sampler"}}]}),
        encoding="utf-8",
    )
    (tmp_path / "response.json").write_text(
        json.dumps(
            _judge_delta_response_json(
                original,
                candidate,
                ops=[{"op": "set_node_field", "target": ["", "sampler", "steps"], "value": 30}],
            )
        ),
        encoding="utf-8",
    )

    def fail_if_called(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise AssertionError("delta replay mismatch must not call the model")

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fail_if_called,
    )

    verdict = judge_edit_intent(tmp_path, {"query": "set steps to 30"})

    assert verdict["pass_"] is False
    assert "delta replay mismatch" in verdict["rationale"]
    assert verdict["metadata"]["delta_replay"]["verified"] is False


# ── Batch 12 (Law 4): judge lens parity + 3c978e live symmetry ──────────────

_BATCH12_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_intent_judge_payload_lens_subset_is_within_reply_lens_set(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Law 4 (batch 12): the judge's payload carries the renderer's lens
    output — a STRICT SUBSET of the reply's lens set (surface+diff+topology)
    — and the rendered pre/post text shows the same topology facts (link ids)
    the reply stage's window carries."""
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    pre_post = {
        "nodes": [
            {
                "id": 1,
                "type": "CLIPTextEncode",
                "class_type": "CLIPTextEncode",
                "outputs": [
                    {"name": "MODEL", "type": "MODEL", "links": [1], "slot_index": 0},
                ],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1, "slot_index": 0}
                ],
                "widgets_values": [42, "fixed", 20, 7, "euler", "normal", 1],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "MODEL"]],
    }
    original.write_text(json.dumps(pre_post), encoding="utf-8")
    candidate.write_text(json.dumps(pre_post), encoding="utf-8")
    # No accepted Δ: replay verification is None (nothing claimed), so the
    # model call runs and the lens payload is observable.
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["payload"] = json.loads(messages[1]["content"])
        return {"content": json.dumps(_edit_verdict_content())}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(tmp_path, {"query": "set steps to 30"})

    assert verdict["pass_"] is True
    payload = seen["payload"]
    renderer_lenses = payload["renderer_lenses"]
    reply_set = set(renderer_lenses["reply_lens_set"])
    judge_subset = set(renderer_lenses["judge_lens_subset"])
    # The judge's lens set is a strict subset of the reply's lens set.
    assert judge_subset <= reply_set
    assert judge_subset < reply_set
    # The renderer's lens output (not a raw-graph dump) carries the same
    # topology facts the reply window carries: the wired edge with named
    # endpoints, and the diff lens (canonical Δ only).
    for side in ("pre", "post"):
        rendered = renderer_lenses[side]
        assert rendered is not None
        assert "## Topology" in rendered
        assert "1 -> 2 (1.0 -> 2.model)" in rendered
        assert "## Diff" in rendered
        assert "## Surface" not in rendered  # surface is reply-only (not a judge lens)


def test_intent_judge_3c978e_sees_same_controlnet_facts_as_reply(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """3c978e live: the judge's renderer payload sees the SAME complete
    ControlNet chain (all 6 links with named endpoints) the reply stage's
    graph window carries — symmetry (Law 4)."""
    fixture = _BATCH12_REPO_ROOT / "tests" / "fixtures" / "3c978e6c11a8a768.json"
    assert fixture.is_file(), f"3c978e fixture missing: {fixture}"
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(json.dumps(raw), encoding="utf-8")
    candidate.write_text(json.dumps(raw), encoding="utf-8")
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
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["payload"] = json.loads(messages[1]["content"])
        return {"content": json.dumps(_edit_verdict_content())}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(tmp_path, {"query": "explain the controlnet chain"})

    assert verdict["pass_"] is True
    payload = seen["payload"]
    chain = (
        ("15", "16", "conditioning"),
        ("18", "16", "image"),
        ("25", "26", "image"),
        ("26", "3", "positive"),
        ("33", "16", "control_net"),
        ("34", "26", "control_net"),
    )
    for side in ("pre", "post"):
        rendered = payload["renderer_lenses"][side]
        assert rendered is not None
        for origin, target, target_input in chain:
            assert (
                f"{origin} -> {target} ({origin}.0 -> {target}.{target_input})"
            ) in rendered, (
                f"ControlNet chain link {origin}->{target} missing from judge "
                f"{side} lens payload"
            )
