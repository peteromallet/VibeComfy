"""M2 Step 2 — _capture_virtual_wires correctness tests.

Covers:
- Content + endpoint-ordering equality against a pre-computed expected dict
- Multi-node fixture with ≥1 self-loop virtual-wire edge
"""

from __future__ import annotations

import copy

import pytest

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    PortConvertResult,
    PortConvertValidation,
    _capture_virtual_wires,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _wf(wf_id: str = "test-cvw") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


def _virtual_node(
    node_id: str,
    class_type: str,
    *,
    channel: str | None = None,
    pos=None,
    size=None,
) -> VibeNode:
    # broadcast_name() reads from node.inputs["name"], not _ui metadata.
    inputs: dict = {}
    if channel:
        inputs["name"] = channel
    n = VibeNode(node_id, class_type, inputs=inputs, pos=pos, size=size)
    n.uid = node_id
    return n


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


def test_capture_virtual_wires_equality():
    """_capture_virtual_wires output matches a pre-computed expected dict.

    Fixture: 3 virtual-wire nodes (SetNode, GetNode, Reroute) with edges
    including a self-loop on the Reroute node.
    """
    wf = _wf("cvw-equality")
    wf.nodes["1"] = _regular_node("1", "KSampler", pos=[0, 0], size=[300, 100])
    wf.nodes["10"] = _virtual_node("10", "SetNode", channel="LATENT", pos=[400, 0], size=[200, 58])
    wf.nodes["11"] = _virtual_node("11", "GetNode", channel="LATENT", pos=[700, 0], size=[200, 58])
    wf.nodes["12"] = _virtual_node("12", "Reroute", pos=[600, 100], size=[75, 26])

    # Edges: 1→10, 10→11, 11→12, 12→12 (self-loop)
    wf.edges = [
        VibeEdge(from_node="1", from_output="0", to_node="10", to_input="input"),
        VibeEdge(from_node="10", from_output="0", to_node="11", to_input="input"),
        VibeEdge(from_node="11", from_output="0", to_node="12", to_input="input"),
        VibeEdge(from_node="12", from_output="0", to_node="12", to_input="input"),
    ]

    result = _capture_virtual_wires(wf)

    # Pre-computed expected dict (must match byte-for-byte).
    expected: dict = {
        "10": {
            "type": "SetNode",
            "channel": "LATENT",
            "pos": [400, 0],
            "size": [200, 58],
            "endpoints": [
                ["1", "0", "10", "input"],
                ["10", "0", "11", "input"],
            ],
        },
        "11": {
            "type": "GetNode",
            "channel": "LATENT",
            "pos": [700, 0],
            "size": [200, 58],
            "endpoints": [
                ["10", "0", "11", "input"],
                ["11", "0", "12", "input"],
            ],
        },
        "12": {
            "type": "Reroute",
            "channel": None,
            "pos": [600, 100],
            "size": [75, 26],
            "endpoints": [
                ["11", "0", "12", "input"],
                ["12", "0", "12", "input"],
            ],
        },
    }

    assert result == expected, f"virtual wire capture mismatch:\n{result!r}\n!=\n{expected!r}"


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
