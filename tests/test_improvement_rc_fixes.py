"""Focused gates for RC4 / RC7 / RC8-A / RC9 improvement fixes."""

from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.executor.core import _classify_stage_message
from vibecomfy.executor.graph_inspection import inspect_workflow
from vibecomfy.executor.stage_contracts import NeedsInput
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeWorkflow, WorkflowSource
from tests.live_agentic_harness.assessor import assess_live_output_dir
from tests.live_agentic_harness.intent_judge import judge_edit_intent


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
