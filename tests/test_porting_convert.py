"""M2 Step 2 — _capture_virtual_wires correctness tests.

Covers:
- Content + endpoint-ordering equality against a pre-computed expected dict
- Multi-node fixture with ≥1 self-loop virtual-wire edge
"""

from __future__ import annotations

from vibecomfy.porting.convert import _capture_virtual_wires
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
    properties = {}
    if channel:
        properties["broadcast_name"] = channel
    ui: dict = {"type": class_type, "properties": properties}
    if pos is not None:
        ui["pos"] = pos
    if size is not None:
        ui["size"] = size
    # broadcast_name() reads from node.inputs, not _ui metadata.
    inputs: dict = {}
    if channel:
        inputs["name"] = channel
    n = VibeNode(node_id, class_type, inputs=inputs, metadata={"_ui": ui})
    n.uid = node_id
    return n


def _regular_node(
    node_id: str,
    class_type: str = "KSampler",
    *,
    pos=None,
    size=None,
) -> VibeNode:
    ui: dict = {}
    if pos is not None:
        ui["pos"] = pos
    if size is not None:
        ui["size"] = size
    metadata: dict = {}
    if ui:
        metadata["_ui"] = ui
    n = VibeNode(node_id, class_type, metadata=metadata)
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
