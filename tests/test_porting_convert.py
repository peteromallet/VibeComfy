"""T05 conversion preserves authored semantics and write behavior."""

from __future__ import annotations

import copy

import pytest

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    PortConvertResult,
    PortConvertValidation,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _wf(wf_id: str = "test-cvw") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


def _regular_node(
    node_id: str,
    class_type: str = "KSampler",
    *,
    pos=None,
    size=None,
) -> VibeNode:
    n = VibeNode(node_id, class_type, pos=pos, size=size)
    n.uid = node_id
    return n


def test_port_convert_ready_template_emits_structured_custom_node_refs():
    wf = _wf("structured-refs")
    wf.nodes["1"] = _regular_node("1", "ExampleCustomNode")
    wf.metadata["requirements"] = {
        "custom_nodes": ["ExamplePack"],
        "custom_node_refs": [
            {
                "slug": "ExamplePack",
                "source": "git",
                "url": "https://example.test/ExamplePack.git",
                "commit": "abc123",
            }
        ],
    }

    result = port_convert_workflow(wf, ready_id="test/structured_refs", validate=False)

    assert "custom_node_refs" in result.text
    assert "ExamplePack" in result.text
    assert "abc123" in result.text


def test_port_convert_does_not_mutate_caller_owned_workflow_or_raw_evidence():
    wf = _wf("caller-owned")
    wf.nodes["1"] = VibeNode("1", "PrimitiveInt", inputs={"value": 7})
    wf.nodes["2"] = VibeNode("2", "Sink")
    wf.edges = [VibeEdge("1", "0", "2", "value")]
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "nodes": [
                        {"id": "10", "type": "PrimitiveInt", "widgets_values": [3]}
                    ],
                    "links": [],
                }
            ]
        }
    }
    workflow_before = wf.copy()
    raw_before = copy.deepcopy(raw)

    result = port_convert_workflow(wf, raw_workflow=raw, validate=False)

    assert "value=7" in result.text
    assert wf == workflow_before
    assert raw == raw_before


def _passing_write_result(text: str) -> PortConvertResult:
    return PortConvertResult(
        mode="scratchpad",
        text=text,
        validation=PortConvertValidation(
            ok=True,
            import_ok=True,
            build_ok=True,
            compile_ok=True,
            parity_ok=True,
        ),
    )


def test_diff_mode_forces_dry_run_and_preserves_manual_target(tmp_path):
    target = tmp_path / "manual.py"
    original = "# vibecomfy: manual\nVALUE = 'existing'\n"
    emitted = "VALUE = 'preview only'\n"
    target.write_text(original, encoding="utf-8")

    payload = port_convert_and_write(
        _passing_write_result(emitted),
        target,
        dry_run=False,
        diff=True,
    )

    assert payload["written"] is False
    assert payload["dry_run"] is True
    assert payload["diff_requested"] is True
    assert payload["diff_forced_dry_run"] is True
    assert payload["target_exists"] is True
    assert payload["manual_refusal"]["refused"] is True
    assert payload["manual_refusal"]["marker"] == "# vibecomfy: manual"
    assert "Remove the marker" in payload["manual_refusal"]["message"]
    assert payload["diff"]["original_exists"] is True
    assert payload["diff"]["changed"] is True
    assert payload["diff"]["original_line_count"] == 2
    assert payload["diff"]["emitted_line_count"] == 1
    assert payload["diff"]["line_count_delta"] == -1
    assert payload["diff"]["unified_diff_line_count"] > 0
    assert "preview only" in payload["diff"]["unified_diff"]
    assert target.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".vibecomfy-port-*")) == []


def test_manual_template_real_write_refusal_preserves_target_bytes(tmp_path):
    target = tmp_path / "manual.py"
    original = "# vibecomfy: manual\nVALUE = 'keep'\n"
    target.write_text(original, encoding="utf-8")

    with pytest.raises(ManualTemplateRefusal):
        port_convert_and_write(
            _passing_write_result("VALUE = 'replace'\n"),
            target,
            dry_run=False,
            diff=False,
        )

    assert target.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".vibecomfy-port-*")) == []
