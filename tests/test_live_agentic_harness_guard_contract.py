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


def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
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
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assessment = verdict["assessment"]
    assert assessment["passed"] is True
    assert assessment["expect_graph_changed"] is True
    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}


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


def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
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

    assert verdict["live_agentic_success"] is False
    issues = verdict["assessment"]["issues"]
    assert {
        issue["check"]
        for issue in issues
        if issue["severity"] == "error"
    } == {"model_request_size"}


def test_agentic_guard_rejects_forbidden_model_request_substrings(tmp_path: Path) -> None:
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

    assert verdict["live_agentic_success"] is False
    issues = verdict["assessment"]["issues"]
    assert {
        issue["check"]
        for issue in issues
        if issue["severity"] == "error"
    } == {"model_request_forbidden_substring"}


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
# zero counts fail closed; accepted grounded refusals and explicitly
# non-edit routes are exempt (they are scored by their own checks).


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
) -> None:
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

    verdict = guard_output_dir(
        output_dir,
        scenario={
            "id": "landed-count-refusal-exempt",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
            },
        },
    )

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True
    assert {issue["check"] for issue in verdict["assessment"]["issues"]} == {"safe_refusal"}
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"] == "landed_operation_count"
    ]


def test_agentic_guard_exempts_explicit_non_edit_route_from_landed_count(
    tmp_path: Path,
) -> None:
    """G0R: an explicitly non-edit route (outcome.kind=clarify, e.g. the
    edit-clarify exit mode) is exempt from the landed_operation_count
    requirement — the agent declared no landed edit, so there is nothing to
    count."""
    output_dir = tmp_path / "landed-count-clarify-exempt"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
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
            "id": "landed-count-clarify-exempt",
            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
        },
    )

    assert verdict["assessment"]["passed"] is True
    assert not [
        issue
        for issue in verdict["assessment"]["issues"]
        if issue["check"] == "landed_operation_count"
    ]


def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
    tmp_path: Path,
) -> None:
    """G0R control: an explicitly non-edit route (no_candidate_reason set)
    is exempt from the landed-count guard but still fails through its own
    structured check when an edit was expected."""
    output_dir = tmp_path / "landed-count-noop-not-exempt-from-noop-check"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
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
    assert "no_candidate_reason" in error_checks
    assert "landed_operation_count" not in error_checks


def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
    output_dir = tmp_path / "shared-linked-source-effective-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"shared_effective_source_edit"}


def test_agentic_guard_allows_shared_linked_source_edit_when_declared(tmp_path: Path) -> None:
    output_dir = tmp_path / "shared-linked-source-intentional"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
    )
    scenario = _effective_target_scenario()
    scenario["assessment"]["effective_edit_targets"][0]["allow_shared_source_edit"] = True

    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True


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
