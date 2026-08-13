from __future__ import annotations

"""Edge case: runtime failure scenarios.

Tests that expected runtime failures produce clear error messages
rather than opaque tracebacks.
"""

import pytest

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_missing_node_reference_error_clear() -> None:
    """Edge referencing non-existent node should produce clear validation issue."""
    wf = VibeWorkflow(
        "missing-node",
        WorkflowSource("source/missing_node", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    # Edge references node "99" which doesn't exist
    wf.edges.append(VibeEdge("99", "0", "1", "image"))

    report = wf.validate()
    assert not report.ok
    assert any(
        "missing" in issue.message.lower() or "99" in issue.message
        for issue in report.issues
    )


def test_empty_workflow_validation_message() -> None:
    """Empty workflow should produce 'Workflow contains no nodes' message."""
    wf = VibeWorkflow(
        "empty",
        WorkflowSource("source/empty", source_type="api"),
    )
    report = wf.validate()
    assert not report.ok
    assert any("no nodes" in issue.message.lower() for issue in report.issues)


def test_invalid_ready_id_format_caught() -> None:
    """Invalid ready_id formats should be caught during conversion."""
    wf = VibeWorkflow(
        "bad-id",
        WorkflowSource("source/bad_id", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/test"})

    # Using None/empty ready_id should fall back to scratchpad mode
    result = port_convert_workflow(wf, ready_id=None)
    assert result.mode == "scratchpad"
    assert result.validation is not None
    assert result.validation.ok


def test_node_with_no_class_type() -> None:
    """Node missing class_type should not cause a hard crash."""
    wf = VibeWorkflow(
        "no-class",
        WorkflowSource("source/no_class", source_type="api"),
    )
    # VibeNode requires class_type in constructor, but we can test
    # that empty/unknown is handled gracefully
    wf.nodes["1"] = VibeNode("1", "", inputs={})
    result = port_convert_workflow(wf)
    # Should not crash — may fail validation but must return a result
    assert result.text is not None
