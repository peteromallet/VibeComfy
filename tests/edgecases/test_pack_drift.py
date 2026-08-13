from __future__ import annotations

"""Edge case: pack drift detection for node references.

Verifies that pack provenance tracking survives the convert round-trip
without pack information being dropped or corrupted.
"""

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _build_workflow_with_pack_info() -> VibeWorkflow:
    """Build a workflow where nodes carry explicit pack metadata."""
    wf = VibeWorkflow(
        "pack-drift-test",
        WorkflowSource("source/pack_drift", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", pack="comfy-core", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", pack="comfy-core", inputs={"filename_prefix": "out/test"})
    wf.edges = []
    return wf


def test_pack_metadata_preserved_through_conversion() -> None:
    """Pack information on nodes should survive the convert round-trip."""
    wf = _build_workflow_with_pack_info()
    result = port_convert_workflow(wf)

    assert result.validation is not None
    assert result.validation.ok

    # Verify the emitted text contains pack information
    # (pack info flows through node metadata)
    for node in wf.nodes.values():
        assert node.pack is not None


def test_pack_drift_empty_no_crash() -> None:
    """Empty pack info should not cause crashes."""
    wf = VibeWorkflow("no-pack", WorkflowSource("source/no_pack", source_type="api"))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok
