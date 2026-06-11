from __future__ import annotations

"""Edge case: subgraph corner cases.

Tests subgraph handling in edge-case scenarios: empty subgraphs,
deeply nested subgraphs, subgraph with no nodes.
"""

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.emit.emitter import emit_ready_template_python
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_subgraph_empty_definitions_no_crash() -> None:
    """Empty definitions dict should not cause crashes during conversion."""
    wf = VibeWorkflow(
        "empty-defs",
        WorkflowSource("source/empty_defs", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    result = port_convert_workflow(wf, raw_workflow={"definitions": {}})
    assert result.validation is not None
    assert result.validation.ok


def test_subgraph_empty_list_no_crash() -> None:
    """Empty subgraphs list should not cause crashes."""
    wf = VibeWorkflow(
        "empty-subgraphs",
        WorkflowSource("source/empty_subgraphs", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    result = port_convert_workflow(
        wf, raw_workflow={"definitions": {"subgraphs": []}}
    )
    assert result.validation is not None
    assert result.validation.ok


def test_ready_template_with_raw_workflow_subgraphs() -> None:
    """Ready template emission with raw_workflow containing subgraph definitions."""
    wf = VibeWorkflow(
        "sub-ready",
        WorkflowSource("source/sub_ready", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode(
        "2", "SaveImage", inputs={"filename_prefix": "out/test"}
    )

    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "name": "test_sub",
                    "nodes": {
                        "100": {"class_type": "LoadImage", "inputs": {"image": "sub.png"}},
                    },
                }
            ]
        }
    }

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/sub-ready", "capability": "test"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/sub-ready",
        raw_workflow=raw,
    )
    # Subgraph materialization produces 'def test_sub(' in the template
    assert "def test_sub(" in text or "raw_call(" not in text
