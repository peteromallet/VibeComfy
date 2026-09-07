from __future__ import annotations

from typing import Any

from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeNode, VibeWorkflow


def add_block_node(
    workflow: VibeWorkflow,
    dotted_name: str,
    class_type: str,
    *,
    block_id: str | None = None,
    inputs: dict[str, Any] | None = None,
    widgets: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> VibeNode:
    raw_inputs = dict(inputs or {})
    # `_provenance` is a reserved keyword on add_node; pop it so it never
    # leaks into node.inputs and forward it explicitly.
    explicit_provenance = raw_inputs.pop("_provenance", None)
    node = workflow.node(class_type, _provenance=explicit_provenance, **raw_inputs).node
    widget_kwargs = dict(widgets or {})
    node.widgets.update(widget_kwargs)
    node.metadata.update(metadata or {})
    node.metadata.update(
        {
            "block": dotted_name,
            "block_id": block_id or dotted_name,
            "widget_kwargs": widget_kwargs,
        }
    )
    return node


def node_id(value: str | VibeNode | Handle) -> str:
    if isinstance(value, Handle):
        return value.node_id
    return value.id if isinstance(value, VibeNode) else str(value)


def connect(
    workflow: VibeWorkflow,
    source: str | VibeNode | Handle | None,
    target: VibeNode,
    input_name: str,
    *,
    output_slot: int = 0,
) -> None:
    if source is not None:
        if isinstance(source, Handle):
            workflow.connect(source, f"{target.id}.{input_name}")
            return
        source_id = node_id(source)
        source_ref = source_id if "." in source_id else f"{source_id}.{output_slot}"
        workflow.connect(source_ref, f"{target.id}.{input_name}")
