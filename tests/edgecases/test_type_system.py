from __future__ import annotations

"""Edge case: type system boundary conditions.

Tests type-related edge cases: unknown class types, widget_* prefix
inputs, link-only type handling.
"""

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.widgets.aliases import LINK_ONLY_TYPES
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_unknown_class_type_no_crash() -> None:
    """Unknown class types should not crash conversion."""
    wf = VibeWorkflow(
        "unknown-ct",
        WorkflowSource("source/unknown_ct", source_type="api"),
    )
    wf.nodes["1"] = VibeNode(
        "1",
        "NonExistentCustomNodeXYZ",
        inputs={"some_param": "value", "another": 42},
    )
    result = port_convert_workflow(wf)
    assert result.validation is not None
    # Unknown classes may produce warnings but should not hard-crash
    assert result.text is not None
    assert len(result.text) > 0


def test_widget_prefixed_inputs_normalized() -> None:
    """widget_N prefixed inputs should be normalized during conversion."""
    wf = VibeWorkflow(
        "widget-prefix",
        WorkflowSource("source/widget_prefix", source_type="api"),
    )
    wf.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={},
        widgets={"widget_0": "test_image.png"},
    )
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok
    # widget_0 should be resolved to a proper name (image) for LoadImage
    # The emitted text should NOT contain the raw widget_0 for this known class
    assert "widget_0" not in result.text.lower()


def test_link_edge_handling() -> None:
    """Edges between nodes should be preserved as proper links, not raw arrays."""
    wf = VibeWorkflow(
        "link-test",
        WorkflowSource("source/link_test", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["1"].metadata["output_names"] = ["image"]
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/link"})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))

    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    # The emitted text must NOT contain raw link arrays like ['1', 0]
    import re
    assert not re.search(r"\[\s*'1'\s*,\s*0\s*\]", result.text), (
        "Raw link array found in emitted text"
    )


def test_broadcast_source_handling() -> None:
    """Nodes that broadcast to multiple targets should be handled."""
    wf = VibeWorkflow(
        "broadcast",
        WorkflowSource("source/broadcast", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["1"].metadata["output_names"] = ["image"]
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/1"})
    wf.nodes["3"] = VibeNode("3", "PreviewImage", inputs={})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))
    wf.edges.append(VibeEdge("1", "0", "3", "images"))

    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok
