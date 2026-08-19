"""Focused gates for RC4 / RC7 / RC8-A / RC9 / RC11-RC14 fixes."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent.diagnostics import queue_stage_diagnostics
from vibecomfy.executor.core import _classify_stage_message
from vibecomfy.executor.graph_inspection import inspect_workflow
from vibecomfy.executor.stage_contracts import NeedsInput
from vibecomfy.porting.edit.constants import MODE_LABELS
from vibecomfy.porting.edit.lint import LintIndex, lint_delta
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.porting.emit.emit_prepare import _AGENT_EDIT_MODE_LABELS
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.provider import InputSpec, NodeSchema
from vibecomfy.workflow import RawWidgetPayload, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
from tests.live_agentic_harness.assessor import assess_live_output_dir
from tests.live_agentic_harness.intent_judge import (
    _apply_parameter_identity_pregrade,
    _named_fields_for_delta,
    _parse_refusal_verdict,
    _pregrade_parameter_identity,
    judge_edit_intent,
    judge_grounded_refusal,
    judge_semantic_answer,
)


def test_classify_stage_message_is_not_workflow_validation() -> None:
    msg = _classify_stage_message(
        "The edited workflow has validation errors and was not applied. See details."
    )
    assert "edited workflow has validation errors" not in msg
    assert "Classification failed" in msg


def test_needs_input_accepts_clarify_without_evidence_ids() -> None:
    parsed = NeedsInput.from_dict(
        {"question": "Which of the two LoraLoaderModelOnly nodes (59 or 65)?"}
    )
    assert parsed.question
    assert parsed.evidence_ids == ()
    assert parsed.missing_information == (parsed.question,)


def test_inspect_lens_prints_schema_name_not_only_widget_index() -> None:
    wf = VibeWorkflow(id="w", source=WorkflowSource(id="t"))
    wf.nodes["1"] = VibeNode(
        "1",
        "SaveAnimatedWEBP",
        uid="save",
        raw_widgets=RawWidgetPayload(
            values=["ComfyUI", 80, False],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=3,
        ),
    )
    evidence = inspect_workflow(wf)
    names = [widget.name for widget in evidence.nodes[0].widgets]
    assert "lossless" in names or any(
        name and "lossless" in name for name in names
    )


def test_judge_rejects_new_self_loop_without_model(tmp_path: Path) -> None:
    original = {
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "inputs": [{"name": "latent_image", "type": "LATENT", "link": 1}],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [1], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": [0, "fixed", 20, 8, "euler", "normal", 1],
            },
            {
                "id": 2,
                "type": "EmptyLatentImage",
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [1], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "2"},
                "widgets_values": [512, 512, 1],
            },
        ],
        "links": [[1, 2, 0, 1, 0, "LATENT"]],
    }
    corrupt = {
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "inputs": [{"name": "latent_image", "type": "LATENT", "link": 1}],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [1], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": [0, "fixed", 20, 8, "euler", "normal", 1],
            },
            {
                "id": 2,
                "type": "EmptyLatentImage",
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "2"},
                "widgets_values": [512, 512, 1],
            },
        ],
        "links": [[1, 1, 0, 1, 0, "LATENT"]],
    }
    (tmp_path / "original.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(corrupt), encoding="utf-8")
    (tmp_path / "response.json").write_text(json.dumps({"ok": True, "accepted_batch": []}), encoding="utf-8")
    verdict = judge_edit_intent(tmp_path, {"query": "fix identity drift"})
    assert verdict["pass_"] is False
    assert "self-loop" in (verdict.get("rationale") or "")


def test_hivemind_500_is_warning_on_semantic_product(tmp_path: Path, monkeypatch) -> None:
    from tests.test_live_agentic_harness_guard_contract import (
        STATUS_SUCCESS,
        _semantic_product_scenario,
        _semantic_verdict,
        _write_flow_metadata,
        _write_non_edit_response,
    )

    output_dir = tmp_path / "semantic-hivemind"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_non_edit_response(
        output_dir,
        reply="The graph uses VHS_VideoCombine at 16 fps.",
    )
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "reply": "The graph uses VHS_VideoCombine at 16 fps.",
                "diagnostics": [
                    {
                        "severity": "error",
                        "message": "Hivemind HTTP error 500: canceling statement due to statement timeout",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "VHS_VideoCombine"}], "links": []}),
        encoding="utf-8",
    )
    (output_dir / "final.ui.json").write_text(
        (output_dir / "original.ui.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_semantic_answer",
        lambda *args, **kwargs: _semantic_verdict(),
    )
    assessment = assess_live_output_dir(
        output_dir,
        scenario=_semantic_product_scenario(),
    )
    upstream = [issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"]
    assert upstream
    assert all(issue["severity"] == "warning" for issue in upstream)
    assert assessment["verdict"] != "fail" or not any(
        issue["severity"] == "error" and issue["check"] == "upstream_failure"
        for issue in assessment["issues"]
    )


# ── RC11: judge consumes executor schema + MODE_LABELS ─────────────────────


ROOT = Path(__file__).resolve().parents[1]


def _fc240f_ui_pair() -> tuple[dict, dict, list[dict]]:
    """SVD node 12 with compact widgets_values[3] (motion_bucket_id) 127→200."""
    corpus = json.loads(
        (ROOT / "external_workflows/corpus/fc240f1c4331a5e5.json").read_text(
            encoding="utf-8"
        )
    )
    ui_node = copy.deepcopy(corpus["nodes"]["12"]["metadata"]["_ui"])
    ui_node.setdefault("properties", {})["vibecomfy_uid"] = "12"
    original = {
        "last_node_id": 12,
        "last_link_id": 0,
        "nodes": [ui_node],
        "links": [],
    }
    post_node = copy.deepcopy(ui_node)
    values = list(post_node["widgets_values"])
    assert values[3] == 127
    values[3] = 200
    post_node["widgets_values"] = values
    post = {
        "last_node_id": 12,
        "last_link_id": 0,
        "nodes": [post_node],
        "links": [],
    }
    op = {
        "op": "set_node_field",
        "target": ["", "12", "motion_bucket_id"],
        "value": 200,
    }
    return original, post, [op]


def _edit_llm_field_rename() -> dict:
    return {
        "pass_": False,
        "criteria": {
            "correct_node_targeted": True,
            "correct_parameter_changed": False,
            "value_semantically_matches_intent": True,
            "no_orphaned_wiring": True,
        },
        "rationale": "The Δ sets node 12's video_frames to 200.",
    }


def test_emit_mode_labels_reexport_cannot_drift() -> None:
    assert _AGENT_EDIT_MODE_LABELS is MODE_LABELS
    assert MODE_LABELS == {0: "enabled", 2: "muted", 4: "bypassed"}


def test_pregrade_requires_literal_intent_delta_schema_intersection() -> None:
    named = {"12": {"motion_bucket_id": 200, "video_frames": 14}}
    delta = [{"op": "set_node_field", "target": ["", "12", "motion_bucket_id"], "value": 200}]
    hit = _pregrade_parameter_identity(
        "increase the motion_bucket_id to add more visible motion",
        delta,
        named,
    )
    assert hit is not None
    assert hit["correct_parameter_changed"] is True
    assert hit["matched_fields"] == ["motion_bucket_id"]

    assert (
        _pregrade_parameter_identity("add more visible motion", delta, named) is None
    )
    assert (
        _pregrade_parameter_identity(
            "increase the motion_bucket_id",
            delta,
            {"12": {"video_frames": 14}},
        )
        is None
    )
    surface_hit = _pregrade_parameter_identity(
        "increase the motion_bucket_id to add more visible motion",
        [{"op": "set_node_field", "target": ["", "12", "video_frames"], "value": 200}],
        named,
        pre_named_fields={"12": {"motion_bucket_id": 127, "video_frames": 14}},
    )
    assert surface_hit is not None
    assert "motion_bucket_id" in surface_hit["matched_fields"]


def test_pregrade_cannot_be_overridden_by_llm_field_rename() -> None:
    verdict = _apply_parameter_identity_pregrade(
        {
            "pass_": False,
            "criteria": {
                "correct_node_targeted": True,
                "correct_parameter_changed": False,
                "value_semantically_matches_intent": True,
                "no_orphaned_wiring": True,
            },
            "rationale": "The Δ sets video_frames.",
            "metadata": {},
        },
        {"correct_parameter_changed": True, "matched_fields": ["motion_bucket_id"]},
    )
    assert verdict["criteria"]["correct_parameter_changed"] is True
    assert verdict["pass_"] is True


def test_fc240f_shaped_delta_passes_without_llm_field_rename(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original, post, ops = _fc240f_ui_pair()
    (tmp_path / "original.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(post), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "accepted_batch": [],
                "outcome": {
                    "kind": "applied",
                    "changes": [
                        {
                            "uid": "12",
                            "field_path": "motion_bucket_id",
                            "old": 127,
                            "new": 200,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        payload = json.loads(messages[1]["content"])
        seen["payload"] = payload
        delta_field = payload["delta"]["ops"][0]["target"][2]
        correct = delta_field == "motion_bucket_id"
        return {
            "content": json.dumps(
                {
                    "pass_": correct,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": correct,
                        "value_semantically_matches_intent": correct,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": f"The canonical delta sets {delta_field}.",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_edit_intent(
        tmp_path,
        {
            "query": (
                "The generated video looks almost like a still image. "
                "Can you increase the motion_bucket_id to add more visible motion?"
            )
        },
    )
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["mode_labels"]["4"] == "bypassed"
    assert payload["mode_labels"]["0"] == "enabled"
    assert payload["named_fields"]["12"]["motion_bucket_id"] == 200
    assert "video_frames" in payload["named_fields"]["12"]
    assert payload["delta"]["ops"][0]["target"][2] == "motion_bucket_id"
    assert payload["pregrade"]["correct_parameter_changed"] is True
    assert verdict["criteria"]["correct_parameter_changed"] is True
    assert verdict["pass_"] is True
    assert verdict["metadata"]["pregrade"]["matched_fields"] == ["motion_bucket_id"]


def test_d1caec_shaped_mode_4_is_bypassed_in_semantic_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = {
        "last_node_id": 228,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 228,
                "type": "LoadImage",
                "mode": 4,
                "properties": {"vibecomfy_uid": "228"},
                "widgets_values": ["input.png", "image"],
            }
        ],
        "links": [],
    }
    (tmp_path / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "reply": "LoadImage uid 228 is mode=4 (bypassed), so that image is skipped.",
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        seen["payload"] = json.loads(messages[1]["content"])
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "grounded": True,
                        "relevant": True,
                        "correct": True,
                    },
                    "rationale": "mode=4 is bypassed per mode_labels",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_semantic_answer(
        tmp_path,
        {
            "query": "Why is only the first batch image coherent?",
            "answer_rubric": {
                "expected_criteria": ["Ground claims in the workflow."],
                "fail_conditions": ["hallucinated settings"],
                "pass_condition": "grounded, relevant, correct",
            },
        },
    )
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["mode_labels"] == {"0": "enabled", "2": "muted", "4": "bypassed"}
    assert payload["mode_labels"]["4"] == "bypassed"
    assert verdict["pass_"] is True


def test_semantic_judge_does_not_soften_ungrounded_causal_claim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = {"nodes": [{"id": 1, "type": "LTXVConditioning"}], "links": []}
    (tmp_path / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps({"ok": True, "reply": "Gray color is caused by blur_radius."}),
        encoding="utf-8",
    )

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "grounded": False,
                        "relevant": True,
                        "correct": False,
                    },
                    "rationale": "causal claim lacks schema support",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_semantic_answer(
        tmp_path,
        {
            "query": "Why is the output gray?",
            "answer_rubric": {
                "expected_criteria": ["causal claims need schema support"],
                "fail_conditions": [],
                "pass_condition": "grounded",
            },
        },
    )
    assert verdict["criteria"]["grounded"] is False
    assert verdict["pass_"] is False
    assert "pregrade" not in (verdict.get("metadata") or {})


def test_rc12b_queue_withheld_batch_grades_product_not_fail_close(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """RC12b: queue_validate_ok=false + stale accepted_batch must not
    fail-close leftover replay. Seed Δ from the product and call the LLM."""
    original = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": [0, "fixed", 20, 8, "euler", "normal", 1],
            }
        ],
        "links": [],
    }
    post = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": [0, "fixed", 30, 8, "euler", "normal", 1],
            }
        ],
        "links": [],
    }
    (tmp_path / "original.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(post), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "gates": {"queue_validate_ok": False},
                "accepted_batch": [
                    {
                        "ok": True,
                        "landed": True,
                        "op": {
                            "op": "set_node_field",
                            "target": ["", "1", "seed"],
                            "value": 99,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        seen["payload"] = json.loads(messages[1]["content"])
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
                    "rationale": "product has the steps edit",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_edit_intent(tmp_path, {"query": "set steps to 30"})
    assert "payload" in seen
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["delta_replay"].get("queue_gate_issue")
    assert payload["delta"].get("seed") == "canonical_diff"
    assert verdict["pass_"] is True


def test_rc12a_untouched_preexisting_schema_less_is_warning_not_block() -> None:
    """b80848-shaped: dest remint on untouched TTS must keep queue_validate_ok."""
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "11",
                "class_type": "VibeVoiceTTS",
                "schema_less": True,
                "preexisting_ui_node": True,
                "ui_connection_shape_unchanged": False,
                "schema_less_queue_safe": False,
                "schema_less_safety": "schema_less_existing_output_links_removed",
            }
        ]
    )
    assert diagnostics.ok is True
    assert any(
        issue["code"] == "schema_less_queue_warning"
        and issue.get("severity") == "warning"
        for issue in diagnostics.issues
    )
    assert not any(
        issue["code"] == "schema_less_queue_blocker"
        and issue.get("severity") == "error"
        for issue in diagnostics.issues
    )


def test_rc12a_new_schema_less_node_stays_hard_block() -> None:
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "99",
                "class_type": "BrandNewSchemaLess",
                "schema_less": True,
                "preexisting_ui_node": False,
                "ui_connection_shape_unchanged": False,
                "schema_less_queue_safe": False,
                "schema_less_safety": "new_schema_less_node",
            }
        ]
    )
    assert diagnostics.ok is False
    assert any(issue["code"] == "schema_less_queue_blocker" for issue in diagnostics.issues)


def test_rc12c_named_scale_on_schema_less_class_is_not_unknown_field() -> None:
    """8800a9-shaped: node_schema lists scale even if object_info is schema-less."""

    class _Provider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type != "UltraShapeRefine":
                return None
            return NodeSchema(
                class_type=class_type,
                pack=None,
                inputs={
                    "scale": InputSpec(type="FLOAT", required=False, default=1.0),
                },
                outputs=[],
                source_provider="node_schema",
                confidence=0.8,
            )

    raw = {
        "nodes": [
            {
                "id": 7,
                "type": "UltraShapeRefine",
                "properties": {"vibecomfy_uid": "7"},
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "widgets_values": [1.0],
            }
        ],
        "links": [],
    }
    result = lint_delta(
        parse_edit_delta(
            [
                {
                    "op": "set_node_field",
                    "target": ["", "7", "scale"],
                    "value": 0.4,
                }
            ]
        ),
        LintIndex.build(raw),
        schema_provider=_Provider(),
    )
    assert result.rejected_count == 0
    assert not any(issue.code == "unknown_field" for issue in result.issues)


def test_rc12d_untouched_unknown_class_does_not_veto_widget_only_edit() -> None:
    """485ff2-shaped: unknown-class on an untouched node must not fail the queue."""
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "2",
                "class_type": "INPAINT_InpaintWithModel",
                "schema_less": True,
                "preexisting_ui_node": True,
                "ui_connection_shape_unchanged": False,
                "schema_less_queue_safe": False,
                "schema_less_safety": "schema_less_existing_output_links_removed",
            },
            {
                "node_id": "1",
                "class_type": "KSampler",
                "schema_less": False,
                "preexisting_ui_node": True,
                "ui_connection_shape_unchanged": True,
                "confidence": 1.0,
            },
        ]
    )
    assert diagnostics.ok is True


def test_rc13_empty_allowlist_defaults_on_missing_class(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Well-formed requires_custom_nodes + proven missing class + empty
    previous allowlist is a grounded-refusal candidate."""
    from tests.live_agentic_harness.assessor import assess_live_output_dir

    output_dir = tmp_path / "rc13-missing-class"
    output_dir.mkdir()
    (output_dir / "original.ui.json").write_text(
        json.dumps({"nodes": [], "links": []}), encoding="utf-8"
    )
    (output_dir / "final.ui.json").write_text(
        json.dumps({"nodes": [], "links": []}), encoding="utf-8"
    )
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "outcome": {
                    "kind": "requires_custom_nodes",
                    "missing_classes": ["HotshotXLAnimateDiffLoader"],
                },
                "report": {
                    "authoring_blocker": {
                        "reason": "unresolved_runtime_classes",
                        "missing_runtime_classes": ["HotshotXLAnimateDiffLoader"],
                    }
                },
                "message": "HotshotXLAnimateDiffLoader is not installed.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: {
            "pass_": True,
            "criteria": {
                "supported_blocker": True,
                "no_representable_edit": True,
                "specific_next_action": True,
                "no_fabricated_inability": True,
            },
            "rationale": "class is absent from schema",
        },
    )
    assessment = assess_live_output_dir(
        output_dir,
        scenario={
            "query": "make this 16 frames with Hotshot",
            "assessment": {"expect_graph_changed": True},
            "_tags": {"requires_custom_nodes": True},
        },
    )
    assert assessment["verdict"] == "pass"
    assert any(item["judge"] == "grounded_refusal" for item in assessment["judge_results"])


def test_rc5_c80bbf_named_absence_enters_grounded_refusal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A typed AudioLDM2 clarify is assessed as a grounded refusal, not noop."""
    from tests.live_agentic_harness.assessor import assess_live_output_dir

    output_dir = tmp_path / "rc5-c80bbf"
    output_dir.mkdir()
    graph = {"nodes": [], "links": []}
    (output_dir / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (output_dir / "final.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "outcome": {
                    "kind": "clarify",
                    "missing_classes": ["AudioLDM2"],
                    "question": (
                        "AudioLDM2 is absent. Either keep the native joint AV path "
                        "or name another installed audio class."
                    ),
                },
                "message": "AudioLDM2 is absent from the local schema.",
            }
        ),
        encoding="utf-8",
    )
    calls: list[object] = []

    def _judge(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "pass_": True,
            "criteria": {
                "supported_blocker": True,
                "no_representable_edit": True,
                "specific_next_action": True,
                "no_fabricated_inability": True,
            },
            "rationale": "AudioLDM2 is absent from schema",
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        _judge,
    )
    assessment = assess_live_output_dir(
        output_dir,
        scenario={
            "query": "Replace the sampler with AudioLDM2",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": [
                    "clarify",
                    "requires_custom_nodes",
                ],
            },
        },
    )

    assert calls
    assert assessment["verdict"] == "pass"
    assert any(item["judge"] == "grounded_refusal" for item in assessment["judge_results"])


def test_rc13_face_mtcnn_refusal_still_fails_when_substitution_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Face/kolors: allowlist is not sufficient; grounded_refusal stays authority."""
    from tests.live_agentic_harness.assessor import assess_live_output_dir

    output_dir = tmp_path / "rc13-face"
    output_dir.mkdir()
    (output_dir / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": 1, "type": "UltralyticsDetectorProvider"}], "links": []}),
        encoding="utf-8",
    )
    (output_dir / "final.ui.json").write_text(
        (output_dir / "original.ui.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "outcome": {"kind": "requires_custom_nodes"},
                "message": "MTCNN is missing.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
        lambda *args, **kwargs: {
            "pass_": False,
            "criteria": {
                "supported_blocker": True,
                "no_representable_edit": False,
                "specific_next_action": True,
                "no_fabricated_inability": False,
            },
            "rationale": "a BBOX_DETECTOR substitution is representable",
        },
    )
    assessment = assess_live_output_dir(
        output_dir,
        scenario={
            "query": "detect the face",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": [
                    "clarify",
                    "requires_custom_nodes",
                ],
            },
        },
    )
    assert assessment["verdict"] != "pass"
    assert any(
        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
        for issue in assessment["issues"]
    )


def test_rc13_promote_missing_class_emits_requires_custom_nodes() -> None:
    from vibecomfy.comfy_nodes.agent.contracts import (
        missing_runtime_classes_from_report,
        promote_requires_custom_nodes_outcome,
    )

    report = {
        "authoring_blocker": {
            "reason": "unresolved_runtime_classes",
            "missing_runtime_classes": ["Rodin3D_Regular"],
        }
    }
    assert missing_runtime_classes_from_report(report) == ("Rodin3D_Regular",)
    promoted = promote_requires_custom_nodes_outcome(
        {"kind": "clarify", "question": "install Rodin3D_Regular"},
        missing_classes=("Rodin3D_Regular",),
    )
    assert promoted["kind"] == "requires_custom_nodes"
    assert promoted["missing_classes"] == ["Rodin3D_Regular"]


def test_rc14_classify_malformed_json_retries_once(monkeypatch) -> None:
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import _CLASSIFY_JSON_NUDGE, _run_classify

    calls: list[dict[str, object]] = []

    def fake_classify(query, **kwargs):  # noqa: ANN001, ANN202
        calls.append(kwargs)
        if len(calls) == 1:
            exc = ValueError("not valid JSON")
            exc.raw_response_preview = "sure, I can help {not json"
            raise exc
        return ClassifyDecision(intent="respond", route="inspect", reply=True)

    monkeypatch.setattr("vibecomfy.executor.core.run_classify_turn", fake_classify)
    decision = _run_classify(
        ExecutorRequest(query="what is lossless on the webp node?"),
        SimpleNamespace(agent="openrouter", model="x", effort="low"),
    )
    assert len(calls) == 2
    assert any(
        isinstance(msg, dict) and _CLASSIFY_JSON_NUDGE in str(msg.get("content"))
        for msg in calls[1].get("messages") or []
    )
    assert decision.intent == "respond"


def test_rc14_classify_timeout_is_not_retried(monkeypatch) -> None:
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import ExecutorRequest
    from vibecomfy.executor.core import _ExecutorPhaseError, _run_classify

    calls = {"n": 0}

    def fake_classify(query, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls["n"] += 1
        raise TimeoutError("classify timed out")

    monkeypatch.setattr("vibecomfy.executor.core.run_classify_turn", fake_classify)
    try:
        _run_classify(
            ExecutorRequest(query="inspect this"),
            SimpleNamespace(agent="openrouter", model="x", effort="low"),
        )
    except _ExecutorPhaseError:
        pass
    else:
        raise AssertionError("expected classify phase error")
    assert calls["n"] == 1


def test_rc14_classify_missing_fields_retries_at_most_once(monkeypatch) -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent.provider import MissingRequiredField
    from vibecomfy.executor.contracts import ExecutorRequest
    from vibecomfy.executor.core import _ExecutorPhaseError, _run_classify

    calls = {"n": 0}

    def fake_classify(query, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls["n"] += 1
        raise MissingRequiredField("missing intent")

    monkeypatch.setattr("vibecomfy.executor.core.run_classify_turn", fake_classify)
    try:
        _run_classify(
            ExecutorRequest(query="inspect this"),
            SimpleNamespace(agent="openrouter", model="x", effort="low"),
        )
    except _ExecutorPhaseError:
        pass
    else:
        raise AssertionError("expected classify phase error")
    assert calls["n"] == 2


def test_rc14_classify_retry_keeps_edit_routing_for_expected_edit(monkeypatch) -> None:
    """RC14: a retry that routes an expected-edit scenario to respond is re-asked
    until it returns an edit/inspect route — never returned as a respond no-op."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import (
        _CLASSIFY_EDIT_ROUTING_NUDGE,
        _CLASSIFY_JSON_NUDGE,
        _run_classify,
    )

    calls: list[dict[str, object]] = []

    def fake_classify(query, **kwargs):  # noqa: ANN001, ANN202
        calls.append(kwargs)
        if len(calls) == 1:
            exc = ValueError("not valid JSON")
            exc.raw_response_preview = "sure, I can help {not json"
            raise exc
        if len(calls) == 2:
            # The RC14 retry corrects the JSON but misroutes the expected-edit
            # scenario to respond (the v5-batch-2 #2 / v5-batch-4 #6 bug).
            return ClassifyDecision(intent="respond", route="respond", reply=True)
        # The edit-routing re-ask honors the hard rule: edit/inspect, never respond.
        return ClassifyDecision(intent="edit", route="revise", implement=True, reply=True)

    monkeypatch.setattr("vibecomfy.executor.core.run_classify_turn", fake_classify)
    decision = _run_classify(
        ExecutorRequest(query="change the webp quality to lossless"),
        SimpleNamespace(agent="openrouter", model="x", effort="low"),
        expect_graph_changed=True,
    )
    assert len(calls) == 3
    retry_content = "\n".join(
        str(msg.get("content"))
        for msg in (calls[1].get("messages") or [])
        if isinstance(msg, dict)
    )
    assert _CLASSIFY_JSON_NUDGE in retry_content
    assert _CLASSIFY_EDIT_ROUTING_NUDGE in retry_content
    reroute_content = "\n".join(
        str(msg.get("content"))
        for msg in (calls[2].get("messages") or [])
        if isinstance(msg, dict)
    )
    assert _CLASSIFY_EDIT_ROUTING_NUDGE in reroute_content
    assert decision.effective_route == "revise"
    assert decision.intent == "edit"


def test_rc14_classify_retry_respond_on_expected_edit_is_rejected(monkeypatch) -> None:
    """RC14: when the retry AND the edit-routing re-ask both return respond for
    an expected-edit scenario, the classify phase fails loudly with a clear
    error instead of proceeding to a no-op respond."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import _ExecutorPhaseError, _run_classify

    calls = {"n": 0}

    def fake_classify(query, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            exc = ValueError("not valid JSON")
            exc.raw_response_preview = "sure, I can help {not json"
            raise exc
        return ClassifyDecision(intent="respond", route="respond", reply=True)

    monkeypatch.setattr("vibecomfy.executor.core.run_classify_turn", fake_classify)
    try:
        _run_classify(
            ExecutorRequest(query="change the webp quality to lossless"),
            SimpleNamespace(agent="openrouter", model="x", effort="low"),
            expect_graph_changed=True,
        )
    except _ExecutorPhaseError as exc:
        assert exc.stage == "classify"
        assert exc.failure_kind == "MissingRequiredField"
        assert "expect_graph_changed" in str(exc)
        assert "respond" in str(exc)
    else:
        raise AssertionError("expected classify phase error for respond misroute")
    assert calls["n"] == 3


def test_rc14_inspect_on_expected_edit_is_rejected_as_non_applyable(monkeypatch) -> None:
    """inspect cannot satisfy an assessment that requires a landed graph edit."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import _ExecutorPhaseError, _run_classify

    calls = {"n": 0}

    def fake_classify(query, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls["n"] += 1
        return ClassifyDecision(
            intent="explain_graph", route="inspect", implement=False, reply=True
        )

    monkeypatch.setattr("vibecomfy.executor.core.run_classify_turn", fake_classify)
    try:
        _run_classify(
            ExecutorRequest(query="make this workflow faster"),
            SimpleNamespace(agent="openrouter", model="x", effort="low"),
            expect_graph_changed=True,
        )
    except _ExecutorPhaseError as exc:
        assert exc.stage == "classify"
        assert "expect_graph_changed" in str(exc)
        assert "inspect" in str(exc)
    else:
        raise AssertionError("expected classify phase error for inspect misroute")
    assert calls["n"] == 2


def test_named_fields_map_uses_executor_surface() -> None:
    original, post, ops = _fc240f_ui_pair()
    named = _named_fields_for_delta(
        original,
        post,
        ops,
        schema_provider=get_schema_provider("auto"),
    )
    assert named["12"]["motion_bucket_id"] == 200
    assert named["12"]["video_frames"] == 14


# ── v5-batch-3 #4 (359848): no fail-close on a missing refusal criterion ─────


def _refusal_359848_artifacts(tmp_path: Path) -> None:
    """359848-shaped refusal artifacts: AnimateDiff absent from graph/schema."""
    graph = {
        "last_node_id": 2,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": ["input.png", "image"],
            },
            {
                "id": 2,
                "type": "ImageUpscaleWithModel",
                "properties": {"vibecomfy_uid": "2"},
                "widgets_values": ["upscale_model"],
            },
        ],
        "links": [],
    }
    (tmp_path / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": False,
                "outcome": {
                    "kind": "clarify",
                    "message": (
                        "The AnimateDiff classes needed for the swap are not "
                        "available in this session; no AnimateDiff nodes exist "
                        "to wire into the graph."
                    ),
                },
                "message": (
                    "The AnimateDiff classes needed for the swap are not "
                    "available in this session."
                ),
                "no_candidate_reason": "requires_custom_nodes",
                "route": "adapt",
                "graph_unchanged": True,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implementation_payload.json").write_text(
        json.dumps(
            {
                "graph": {
                    "compiled_api": {
                        "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["STRING"]}}},
                        "LoadImage": {"input": {"required": {"image": ["STRING"]}}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _refusal_verdict_content(**overrides: object) -> dict:
    content: dict = {
        "pass_": True,
        "criteria": {
            "supported_blocker": True,
            "no_representable_edit": True,
            "specific_next_action": True,
            "no_fabricated_inability": True,
        },
        "rationale": "AnimateDiff classes are absent from the schema and graph.",
    }
    content.update(overrides)
    return content


def test_parse_refusal_verdict_missing_criterion_is_undetermined_not_fail() -> None:
    """Unit pin: a refusal criterion key absent from the response is
    undetermined (``pass_`` None) with the missing key surfaced — never the
    silent fail-close that flipped 359848 one criterion short of accept."""
    criteria = _refusal_verdict_content()["criteria"]
    del criteria["no_fabricated_inability"]
    verdict = _parse_refusal_verdict(json.dumps(_refusal_verdict_content(criteria=criteria)))

    assert verdict["pass_"] is None
    assert verdict["missing_criteria"] == ["no_fabricated_inability"]
    assert verdict["criteria"]["supported_blocker"] is True


def test_359848_shaped_missing_refusal_criterion_retries_and_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """v5-batch-3 #4 (359848): a refusal response omitting a criterion is
    retried once — the retry supplies the key and the grounded refusal is
    accepted, instead of failing one criterion short of a flip."""
    _refusal_359848_artifacts(tmp_path)
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        if len(calls) == 1:
            criteria = {
                "supported_blocker": True,
                "no_representable_edit": True,
                "specific_next_action": True,
            }
        else:
            criteria = {
                "supported_blocker": True,
                "no_representable_edit": True,
                "specific_next_action": True,
                "no_fabricated_inability": True,
            }
        return {"content": json.dumps(_refusal_verdict_content(criteria=criteria))}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_grounded_refusal(tmp_path, {"query": "swap in AnimateDiff"})

    assert len(calls) == 2  # retried once after the missing criterion
    assert verdict["pass_"] is True
    assert verdict["criteria"]["no_fabricated_inability"] is True


def test_359848_shaped_missing_refusal_criterion_stays_undetermined_after_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A refusal response that STILL omits a criterion after the retry is
    undetermined (``pass_`` None with an error), never a silent fail-close."""
    _refusal_359848_artifacts(tmp_path)
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        criteria = {
            "supported_blocker": True,
            "no_representable_edit": True,
            "specific_next_action": True,
        }
        return {"content": json.dumps(_refusal_verdict_content(criteria=criteria))}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_grounded_refusal(tmp_path, {"query": "swap in AnimateDiff"})

    assert len(calls) == 2
    assert verdict["pass_"] is None
    assert "no_fabricated_inability" in verdict["missing_criteria"]
    assert "after retry" in (verdict.get("error") or "")


def test_refusal_criterion_explicit_false_still_fails_without_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """An explicitly returned False criterion must still fail the refusal —
    only ABSENT criteria trigger the retry/undetermined path."""
    _refusal_359848_artifacts(tmp_path)
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        criteria = {
            "supported_blocker": True,
            "no_representable_edit": True,
            "specific_next_action": True,
            "no_fabricated_inability": False,  # the refusal fabricates an inability
        }
        return {"content": json.dumps(_refusal_verdict_content(criteria=criteria))}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_grounded_refusal(tmp_path, {"query": "swap in AnimateDiff"})

    assert len(calls) == 1  # explicit False decides without a retry
    assert verdict["pass_"] is False
    assert verdict["criteria"]["no_fabricated_inability"] is False


def test_false_refusal_criterion_wins_over_another_missing_without_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A missing key cannot mask an explicit False as undetermined."""
    _refusal_359848_artifacts(tmp_path)
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        criteria = {
            "supported_blocker": True,
            "no_representable_edit": False,
            "specific_next_action": True,
            # no_fabricated_inability intentionally absent
        }
        return {"content": json.dumps(_refusal_verdict_content(criteria=criteria))}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_grounded_refusal(tmp_path, {"query": "swap in AnimateDiff"})

    assert len(calls) == 1
    assert verdict["pass_"] is False
    assert verdict["criteria"]["no_representable_edit"] is False
    assert "missing_criteria" not in verdict


def test_kolors_actionable_refusal_is_accepted_through_live_assessor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Kolors live path: response prose reaches the real refusal judge actionable."""
    graph = {
        "last_node_id": 2,
        "last_link_id": 0,
        "nodes": [
            {"id": 1, "type": "UltralyticsDetectorProvider"},
            {"id": 2, "type": "ImpactSimpleDetectorSEGS_for_AD"},
        ],
        "links": [],
    }
    action = (
        "GroundingDinoSAMSegment and GroundingDinoModelLoader are unavailable. "
        "Please provide the missing dependency or answer the unresolved choice "
        "named above so I can continue."
    )
    (tmp_path / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "outcome": {"kind": "clarify", "question": action},
                "message": action,
                "reply": action,
                "no_candidate_reason": "no_changes",
                "route": "adapt",
                "graph_unchanged": True,
                "gates": {
                    "ir_validate_ok": False,
                    "lower_ok": False,
                    "python_load_ok": False,
                    "queue_validate_ok": False,
                    "ui_emit_ok": False,
                    "ui_fidelity_ok": False,
                    "ui_load_safe_ok": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implementation_payload.json").write_text(
        json.dumps(
            {
                "graph": {
                    "compiled_api": {
                        "UltralyticsDetectorProvider": {"input": {"required": {}}},
                        "ImpactSimpleDetectorSEGS_for_AD": {"input": {"required": {}}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        payload = json.loads(messages[1]["content"])
        seen["payload"] = payload
        refusal_message = payload["refusal"]["message"]
        specific = (
            "GroundingDinoSAMSegment" in refusal_message
            and "provide the missing dependency" in refusal_message
        )
        return {
            "content": json.dumps(
                _refusal_verdict_content(
                    pass_=specific,
                    criteria={
                        "supported_blocker": True,
                        "no_representable_edit": True,
                        "specific_next_action": specific,
                        "no_fabricated_inability": True,
                    },
                )
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    assessment = assess_live_output_dir(
        tmp_path,
        scenario={
            "query": "Replace Ultralytics with GroundingDINO.",
            "assessment": {
                "expect_graph_changed": True,
                "allow_safe_refusal_outcome_kinds": ["clarify"],
            },
        },
    )

    assert seen["payload"]["refusal"]["message"] == action
    assert assessment["verdict"] == "pass"
    assert any(issue["check"] == "safe_refusal" for issue in assessment["issues"])
    assert not any(issue["severity"] == "error" for issue in assessment["issues"])


# ── v5-batch-4 #7 (d1caec): harden the semantic judge JSON parse ────────────


def _semantic_judge_artifacts(tmp_path: Path) -> None:
    graph = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": ["input.png", "image"],
            }
        ],
        "links": [],
    }
    (tmp_path / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps({"ok": True, "reply": "LoadImage uid 1 reads input.png."}),
        encoding="utf-8",
    )


_SEMANTIC_RUBRIC = {
    "expected_criteria": ["Ground claims in the workflow."],
    "fail_conditions": [],
    "pass_condition": "grounded, relevant, correct",
}


def test_d1caec_shaped_trailing_json_semantic_judge_tolerated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """v5-batch-4 #7 (d1caec): the semantic judge emitted a second JSON
    object ('Extra data: line 10 column 1'). The first object is recovered
    and graded — parsed, never undetermined-by-parse-alone."""
    _semantic_judge_artifacts(tmp_path)
    calls: list[int] = []
    verdict_content = {
        "pass_": True,
        "criteria": {"grounded": True, "relevant": True, "correct": True},
        "rationale": "grounded in the LoadImage evidence",
    }
    trailing = {"duplicate": True, "criteria": {"grounded": False}}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        return {"content": json.dumps(verdict_content) + "\n" + json.dumps(trailing)}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_semantic_answer(tmp_path, {"query": "What does LoadImage uid 1 do?", "answer_rubric": _SEMANTIC_RUBRIC})

    assert len(calls) == 1  # tolerated, no retry needed
    assert verdict["pass_"] is True
    assert verdict["criteria"]["grounded"] is True
    assert verdict["criteria"]["relevant"] is True
    assert verdict["criteria"]["correct"] is True


def test_d1caec_shaped_unparsable_semantic_judge_retries_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Genuinely unparsable judge output (not just trailing data) is retried
    once; a clean retry yields a verdict instead of undetermined-by-parse."""
    _semantic_judge_artifacts(tmp_path)
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        if len(calls) == 1:
            return {"content": '{"pass_": true, "criteria": {'}  # truncated
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {"grounded": True, "relevant": True, "correct": True},
                    "rationale": "clean retry",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_semantic_answer(tmp_path, {"query": "What does LoadImage uid 1 do?", "answer_rubric": _SEMANTIC_RUBRIC})

    assert len(calls) == 2  # retried exactly once
    assert verdict["pass_"] is True
    assert verdict["criteria"]["correct"] is True


def test_semantic_judge_retry_exhausted_is_undetermined_not_hard_fail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Both attempts unparsable: undetermined with an error after one retry —
    the scenario gets a retryable undetermined, not a parse-induced verdict."""
    _semantic_judge_artifacts(tmp_path)
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
        calls.append(len(calls))
        return {"content": "not json at all { "}

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    verdict = judge_semantic_answer(tmp_path, {"query": "What does LoadImage uid 1 do?", "answer_rubric": _SEMANTIC_RUBRIC})

    assert len(calls) == 2
    assert verdict["pass_"] is None
    assert "after retry" in (verdict.get("error") or "")


# ── reply grounding (v5-batch-3 #3 fidelity, v5-batch-4 #1 node ids) ───────


def test_reply_fidelity_guard_corrects_false_success_narrative() -> None:
    """v5-batch-3 #3: a no_changes reply must never claim the edit landed.

    The i2v-gen failure was graph_unchanged=true / no_candidate_reason=
    "no_changes" while the narrative asserted "I changed ... from 25 to 24"
    and "the edit landed and validation passed".  The fidelity guard must
    replace that narrative with a truthful no-change reply.
    """
    from vibecomfy.executor.core import (
        _enforce_reply_grounding,
        _reply_claims_landed_edit,
    )

    false_success = (
        "I changed the frame-rate constant from 25 to 24 so the audio "
        "pipeline matches the video's 24 fps output. The edit landed and "
        "validation passed."
    )
    assert _reply_claims_landed_edit(false_success) is True

    corrected = _enforce_reply_grounding(
        false_success,
        landed=False,
        graph=None,
        reason="no_changes",
    )
    assert "No changes were applied" in corrected
    assert "no_changes" in corrected
    # The truthful template may state "no edit landed" (negated); the
    # false-claim phrasing must be gone.
    assert "the edit landed" not in corrected
    assert "validation passed" not in corrected
    assert "I changed" not in corrected
    # The corrected reply must itself pass the guard (no false claim left).
    assert _reply_claims_landed_edit(corrected) is False


def test_reply_fidelity_guard_keeps_truthful_no_change_narrative() -> None:
    """A truthful no-change narrative passes through unmodified."""
    from vibecomfy.executor.core import (
        _enforce_reply_grounding,
        _reply_claims_landed_edit,
    )

    truthful = "No changes were applied: the graph is unchanged."
    assert _reply_claims_landed_edit(truthful) is False
    assert (
        _enforce_reply_grounding(truthful, landed=False, graph=None)
        == truthful
    )


def test_reply_fidelity_guard_keeps_claims_when_edit_landed() -> None:
    """When an edit genuinely landed, first-person claims are preserved."""
    from vibecomfy.executor.core import _enforce_reply_grounding

    landed_reply = "I changed the frame rate on node 43 to 24."
    out = _enforce_reply_grounding(
        landed_reply,
        landed=True,
        graph={
            "nodes": [
                {"id": 43, "type": "Float", "widgets_values": [25]},
            ],
            "links": [],
        },
    )
    assert out == landed_reply


def test_implementation_landed_edit_distinguishes_no_changes_from_candidate() -> None:
    """The landed signal follows the durable Δ, not the message prose."""
    from vibecomfy.executor.contracts import ImplementationResult
    from vibecomfy.executor.core import _implementation_landed_edit

    no_changes = ImplementationResult(
        graph=None,
        message="I changed the frame-rate constant from 25 to 24.",
        durable_response={
            "ok": True,
            "graph_unchanged": True,
            "no_candidate_reason": "no_changes",
            "outcome": {"kind": "noop"},
            "accepted_batch": [],
        },
    )
    assert _implementation_landed_edit(no_changes) is False

    landed = ImplementationResult(
        graph={"nodes": [{"id": 43, "type": "Float"}]},
        message="I set node 43 to 24.",
        durable_response={
            "ok": True,
            "graph_unchanged": False,
            "outcome": {
                "kind": "candidate",
                "changes": [{"uid": "43", "field_path": "value", "old": 25, "new": 24}],
            },
            "accepted_batch": [
                {"op": {"op": "set_node_field", "uid": "43", "field_path": "value", "value": 24}}
            ],
        },
    )
    assert _implementation_landed_edit(landed) is True

    assert _implementation_landed_edit(None) is False


def test_terminal_no_candidate_message_is_grounded_like_a_reply() -> None:
    """The terminal-no-candidate path passes the implement message through as
    the reply, so the fidelity guard must apply there too (the exact
    v5-batch-3 #3 shape: message claims success, durable says no_changes)."""
    from vibecomfy.executor.contracts import ImplementationResult
    from vibecomfy.executor.core import (
        _enforce_reply_grounding,
        _implementation_landed_edit,
    )

    result = ImplementationResult(
        graph=None,
        message=(
            "I changed the frame-rate constant from 25 to 24 so the audio "
            "pipeline matches the video's 24 fps output... **the edit landed "
            "and validation passed**."
        ),
        durable_response={
            "ok": True,
            "graph_unchanged": True,
            "no_candidate_reason": "no_changes",
            "outcome": {"kind": "noop"},
            "accepted_batch": [],
        },
    )
    reply = _enforce_reply_grounding(
        result.message,
        landed=_implementation_landed_edit(result),
        graph=None,
        reason="no_changes",
    )
    assert "No changes were applied" in reply
    assert "the edit landed" not in reply


def test_node_id_hallucination_is_corrected_via_class_match() -> None:
    """v5-batch-4 #1: the reply cited HyVideoEncode node ID 120 while the
    final graph wires node 43.  The class name in the sentence grounds the
    hallucinated id to the real node."""
    from vibecomfy.executor.core import _ground_reply_node_ids

    graph = {
        "nodes": [
            {
                "id": 43,
                "type": "HyVideoEncode",
                "properties": {"vibecomfy_uid": "43"},
            },
            {"id": 90, "type": "VHS_VideoCombine"},
        ],
        "links": [
            [6, 43, 0, 90, 0],
            [7, 43, 1, 90, 1],
        ],
    }
    reply = (
        "I wired HyVideoEncode node ID 120 to the VHS_VideoCombine node 90 "
        "so the samples and image_cond_latents flow through."
    )
    grounded = _ground_reply_node_ids(reply, graph)
    assert "node ID 43" in grounded
    assert "120" not in grounded
    assert "node 90" in grounded


def test_node_id_hallucination_without_class_match_is_stripped() -> None:
    """Without a uniquely named class the bogus cite is removed, never kept."""
    from vibecomfy.executor.core import _ground_reply_node_ids

    graph = {"nodes": [{"id": 43, "type": "HyVideoEncode"}], "links": []}
    reply = "The frame_rate comes from node 120, which feeds the encoder."
    grounded = _ground_reply_node_ids(reply, graph)
    assert "node 120" not in grounded
    assert grounded == "The frame_rate comes from node, which feeds the encoder."


def test_node_id_grounding_fails_closed_when_attached_graph_has_no_node_ids() -> None:
    """An attached empty/malformed graph must not bypass the cite guard.

    With no authoritative IDs available, every node-ID claim is ungrounded and
    must be stripped rather than passed through unchanged.
    """
    from vibecomfy.executor.core import _ground_reply_node_ids

    reply = "I updated node ID 120 and uid 742."
    grounded = _ground_reply_node_ids(reply, {"nodes": [], "links": []})
    assert "120" not in grounded
    assert "742" not in grounded
    assert "node ID" not in grounded
    assert "uid" not in grounded


def test_real_node_cites_kept_and_link_ids_ignored() -> None:
    """Real node ids pass through; link ids (a separate namespace) are not
    treated as node cites."""
    from vibecomfy.executor.core import _ground_reply_node_ids

    graph = {
        "nodes": [
            {"id": 43, "type": "HyVideoEncode"},
            {"id": 90, "type": "VHS_VideoCombine"},
        ],
        "links": [[5, 43, 0, 90, 0]],
    }
    reply = "The update touches nodes 43 and 90; link id 5 carries the samples."
    grounded = _ground_reply_node_ids(reply, graph)
    assert grounded == reply


def test_reply_phase_enforces_fidelity_guard(monkeypatch) -> None:
    """The full _run_reply path corrects a false-success model reply."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import (
        ClassifyDecision,
        ExecutorRequest,
        ImplementationResult,
    )
    from vibecomfy.executor.core import _run_reply

    false_success = (
        "I changed the frame-rate constant from 25 to 24. The edit landed "
        "and validation passed."
    )
    seen: dict[str, object] = {}

    def fake_reply_turn(query, **kwargs):  # noqa: ANN001, ANN002
        seen["query"] = query
        seen["landed_edit"] = kwargs.get("landed_edit")
        seen["real_node_ids"] = kwargs.get("real_node_ids")
        return false_success

    monkeypatch.setattr("vibecomfy.executor.core.run_reply_turn", fake_reply_turn)
    implementation = ImplementationResult(
        graph=None,
        message=false_success,
        durable_response={
            "ok": True,
            "graph_unchanged": True,
            "no_candidate_reason": "no_changes",
            "outcome": {"kind": "noop"},
            "accepted_batch": [],
        },
    )
    reply = _run_reply(
        ExecutorRequest(query="change the frame rate to 24"),
        SimpleNamespace(agent="openrouter", model="x", effort="low"),
        plan=ClassifyDecision(route="adapt"),
        effective_graph=None,
        implementation_result=implementation,
    )
    assert seen["landed_edit"] is False
    assert seen["real_node_ids"] is None
    assert "No changes were applied" in reply
    assert "the edit landed" not in reply


def test_reply_phase_grounds_hallucinated_node_ids(monkeypatch) -> None:
    """The full _run_reply path corrects a reply that cites a non-existent
    node id, and passes the real node id set into the model turn."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import (
        ClassifyDecision,
        ExecutorRequest,
        ImplementationResult,
    )
    from vibecomfy.executor.core import _run_reply

    graph = {
        "nodes": [
            {"id": 43, "type": "HyVideoEncode"},
            {"id": 90, "type": "VHS_VideoCombine"},
        ],
        "links": [[6, 43, 0, 90, 0]],
    }
    hallucinated = (
        "I wired HyVideoEncode node ID 120 to VHS_VideoCombine node 90."
    )
    seen: dict[str, object] = {}

    def fake_reply_turn(query, **kwargs):  # noqa: ANN001, ANN002
        seen["query"] = query
        seen["landed_edit"] = kwargs.get("landed_edit")
        seen["real_node_ids"] = kwargs.get("real_node_ids")
        return hallucinated

    monkeypatch.setattr("vibecomfy.executor.core.run_reply_turn", fake_reply_turn)
    implementation = ImplementationResult(
        graph=graph,
        message=hallucinated,
        durable_response={
            "ok": True,
            "graph_unchanged": False,
            "outcome": {
                "kind": "candidate",
                "changes": [{"uid": "43", "field_path": "x", "old": 1, "new": 2}],
            },
            "accepted_batch": [
                {"op": {"op": "set_node_field", "uid": "43", "field_path": "x", "value": 2}}
            ],
        },
    )
    reply = _run_reply(
        ExecutorRequest(query="wire the encoder"),
        SimpleNamespace(agent="openrouter", model="x", effort="low"),
        plan=ClassifyDecision(route="adapt"),
        effective_graph=graph,
        implementation_result=implementation,
    )
    assert seen["landed_edit"] is True
    assert set(seen["real_node_ids"]) == {"43", "90"}  # type: ignore[arg-type]
    assert "node ID 43" in reply
    assert "120" not in reply


def test_reply_grounding_facts_are_injected_into_the_prompt(monkeypatch) -> None:
    """agent_backend appends the grounding facts to the reply user message."""
    from vibecomfy.executor.agent_backend import run_reply_turn
    from vibecomfy.executor.contracts import ClassifyDecision

    captured: dict[str, object] = {}

    def fake_run_model_turn(query, messages, **kwargs):  # noqa: ANN001, ANN002, ANN003
        captured["messages"] = messages
        return {"content": "ok"}

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.provider.run_model_turn",
        fake_run_model_turn,
    )
    reply = run_reply_turn(
        "why is the output gray?",
        route="openrouter",
        model="x",
        plan=ClassifyDecision(route="respond"),
        landed_edit=False,
        real_node_ids=("43", "90"),
    )
    assert reply == "ok"
    content = captured["messages"][1]["content"]
    assert "NO edit was applied" in content
    assert "43" in content
    assert "90" in content
    assert "Never cite a node id/uid outside this set" in content


def test_reply_phase_replaces_stale_no_change_answer_with_accepted_delta(monkeypatch) -> None:
    """374aa9 live path: narration cannot contradict its own landed edit."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import (
        ClassifyDecision,
        ExecutorRequest,
        ImplementationResult,
    )
    from vibecomfy.executor.core import _run_reply

    graph = {
        "nodes": [{"id": 73, "type": "TrimVideo", "properties": {"vibecomfy_uid": "73"}}],
        "links": [],
    }
    monkeypatch.setattr(
        "vibecomfy.executor.core.run_reply_turn",
        lambda query, **kwargs: (
            "Validation failed, so the workflow remains exactly unchanged."
        ),
    )
    implementation = ImplementationResult(
        graph=graph,
        message="Trimmed the sequence to 20 frames.",
        durable_response={
            "ok": True,
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "accepted_batch": [
                {
                    "op": {
                        "op": "set_node_field",
                        "target": ["", "73", "video_frames"],
                        "value": 20,
                    }
                }
            ],
        },
    )

    reply = _run_reply(
        ExecutorRequest(query="trim this to 20 frames"),
        SimpleNamespace(agent="openrouter", model="x", effort="low"),
        plan=ClassifyDecision(route="revise"),
        effective_graph=graph,
        implementation_result=implementation,
    )

    assert "workflow edit landed" in reply
    assert "set_node_field 73.video_frames = 20" in reply
    assert "unchanged" not in reply
    assert "Validation failed" not in reply


def test_inspect_topology_renders_set_get_semantic_model_path() -> None:
    """d1caec live renderer path: virtual MODEL wiring is explicit to reply."""
    from vibecomfy.porting.render import render_text

    wf = VibeWorkflow(id="semantic-path", source=WorkflowSource(id="semantic-path"))
    wf.nodes = {
        "54": VibeNode("54", "Power Lora Loader", uid="power-lora"),
        "115": VibeNode("115", "SetNode", uid="set-model", widgets={"name": "MODEL"}),
        "118": VibeNode("118", "GetNode", uid="get-model", widgets={"name": "MODEL"}),
        "52": VibeNode("52", "ModelSamplingSD3", uid="model-sampling"),
        "53": VibeNode("53", "KSampler", uid="sampler"),
    }
    wf.edges = [
        VibeEdge("54", "MODEL", "115", "value"),
        VibeEdge("118", "MODEL", "52", "model"),
        VibeEdge("52", "MODEL", "53", "model"),
    ]

    rendered = render_text(wf, lenses=("surface", "topology"))
    assert rendered is not None
    assert "virtual_binding_paths:" in rendered
    assert "power-lora.MODEL -> set-model[SetNode name='MODEL']" in rendered
    assert "=> get-model[GetNode name='MODEL'] -> model-sampling.model" in rendered
    assert "model-sampling -> sampler" in rendered
