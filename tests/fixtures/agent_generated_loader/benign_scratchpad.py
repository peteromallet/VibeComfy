# vibecomfy: generated scratchpad
"""Auto-generated VibeComfy scratchpad."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        "agent-scratchpad-fixture",
        WorkflowSource(
            id="agent-scratchpad-fixture", path=__file__, source_type="scratchpad"
        ),
    )
    load = _node(wf, "LoadImage", "4", _extras={"image": "example.png"})
    preview = _node(wf, "PreviewImage", "7", images=load.out(0))
    save = _node(
        wf, "SaveImage", "9", filename_prefix="agent-gen", images=load.out(0)
    )
    wf.finalize_metadata()
    return wf


def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    _uid: str | None = None,
    **kwargs,
):
    from vibecomfy.handles import Handle

    builder = wf.node(class_type, **kwargs)
    if _uid:
        builder.node.uid = _uid
    if _outputs is not None:
        builder.node.metadata["output_names"] = list(_outputs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
