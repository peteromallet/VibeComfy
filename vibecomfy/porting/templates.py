"""Template constants and emitted helper source for ready-template porting."""

from __future__ import annotations


# Top-of-file generator marker.
GENERATED_HEADER = (
    "# vibecomfy: generated — converted by tools/convert_ready_templates.py\n"
    "# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`\n"
    "# marker on the first line if hand-editing is required.\n"
)


# AUTHORED templates with subgraph inlining: tail-call patches that depend
# on specific original node IDs from the source workflow JSON. Generated
# code must preserve IDs and re-emit the patch calls verbatim.
LTX2_3_TAIL_PATCHES: tuple[str, ...] = (
    "from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram",
    "from vibecomfy.patches.requirements import ensure_custom_nodes",
    "from vibecomfy.patches.resolution import resolution",
)


# Sentinel used in the emitted file to mark generated content vs hand-edited.
GENERATED_MARKER_LINES = (
    "# vibecomfy: generated",
    "# vibecomfy: manual",
)


NODE_HELPER_SOURCE = '''
def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, _uid: str | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.

    `_uid` carries the durable node identity (M2) and is applied verbatim so the
    round-trip preserves uids.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _uid:
        builder.node.uid = _uid
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
'''


def has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


__all__ = [
    "GENERATED_HEADER",
    "GENERATED_MARKER_LINES",
    "LTX2_3_TAIL_PATCHES",
    "NODE_HELPER_SOURCE",
    "has_ltx_lowvram_tail",
]
