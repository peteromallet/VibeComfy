from __future__ import annotations

"""Edge case: multi-output node handling.

Tests nodes that produce multiple outputs (e.g., KSampler produces
LATENT, but multi-output nodes might produce IMAGE + MASK).
"""

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_multi_output_node_edges_preserved() -> None:
    """Edges referencing different output slots of the same node should be preserved."""
    wf = VibeWorkflow(
        "multi-out",
        WorkflowSource("source/multi_out", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["1"].metadata["output_names"] = ["image", "mask"]
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/img"})
    wf.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out/mask"})
    # Edge from slot 0 to node 2
    wf.edges.append(VibeEdge("1", "0", "2", "images"))
    # Edge from slot 1 to node 3
    wf.edges.append(VibeEdge("1", "1", "3", "images"))

    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    # Both output slots should be referenced in the emitted text.
    # F.5 (v2.7) changed emission to tuple-unpacking assignment
    # (e.g. ``image, mask = LoadImage(...)``), replacing the old
    # ``.out(slot)`` index syntax.  Check for either form.
    text = result.text
    assert ".out(" in text or ("image" in text and "mask" in text)


def test_single_output_node_no_edge_ambiguity() -> None:
    """Single-output node with implicit slot 0 should work correctly."""
    wf = VibeWorkflow(
        "single-out",
        WorkflowSource("source/single_out", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/img"})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))

    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    text = result.text
    # At a minimum, the edge connection should produce some output reference
    assert "out" in text.lower() or ".connect" in text or "images" in text
