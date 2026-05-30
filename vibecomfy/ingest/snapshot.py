"""Ingest-time snapshot capture for uid-keyed field signatures.

Captures a frozen snapshot of each node's field state at ingest time so that
later delta computation can identify which fields changed (widget edits, rewires,
public-input rebindings) versus which nodes were added or had no snapshot taken.

``NodeFieldSnapshot`` is a TypedDict with all-tuple fields for stable comparison.
Tuples are sorted and canonicalized — no rank/positional ordering.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[no-redef]


class NodeFieldSnapshot(TypedDict):
    """Frozen field-level snapshot for a single IR node, keyed by uid."""

    class_type: str
    # Sorted tuple of (field_name, value_repr) — all non-link values (widgets + inputs)
    widget_values_sig: tuple
    # Sorted tuple of (to_input_field, (source_uid, source_output_slot))
    incoming_edge_sig: tuple
    # Sorted tuple of (from_output_slot, (target_uid, to_input_field))
    outgoing_edge_sig: tuple
    # Sorted tuple of (public_input_name, bound_field)
    public_input_binding: tuple


def capture_ingest_snapshot(
    raw_ui_or_api: dict[str, Any] | None,
    ir_workflow: "VibeWorkflow",
) -> dict[str, NodeFieldSnapshot]:
    """Capture a uid-keyed field snapshot of every node in *ir_workflow*.

    Arguments
    ---------
    raw_ui_or_api:
        The raw litegraph UI dict or ComfyUI API dict that was ingested to produce
        *ir_workflow*.  Currently unused; reserved for future cross-validation.
    ir_workflow:
        The fully-constructed IR workflow (all nodes AND edges already present).

    Returns
    -------
    ``{uid: NodeFieldSnapshot}`` — one entry per IR node, keyed by ``node.uid``.
    Nodes without a uid (``node.uid == ""``) use ``str(node.id)`` as a fallback key
    so they are still captured.
    """
    nodes = ir_workflow.nodes
    edges = ir_workflow.edges
    inputs = ir_workflow.inputs

    # Build id → uid map for resolving edge endpoints to stable keys.
    id_to_uid: dict[str, str] = {}
    for node_id, node in nodes.items():
        id_to_uid[node_id] = node.uid if node.uid else node_id

    # Incoming edges per node_id: [(to_input, (source_uid, source_slot))]
    incoming: dict[str, list] = {node_id: [] for node_id in nodes}
    for edge in edges:
        if edge.to_node in incoming:
            source_uid = id_to_uid.get(edge.from_node, edge.from_node)
            incoming[edge.to_node].append((edge.to_input, (source_uid, edge.from_output)))

    # Outgoing edges per node_id: [(from_output_slot, (target_uid, to_input))]
    outgoing: dict[str, list] = {node_id: [] for node_id in nodes}
    for edge in edges:
        if edge.from_node in outgoing:
            target_uid = id_to_uid.get(edge.to_node, edge.to_node)
            outgoing[edge.from_node].append((edge.from_output, (target_uid, edge.to_input)))

    # Public input bindings per node_id: [(input_name, field)]
    public_bindings: dict[str, list] = {node_id: [] for node_id in nodes}
    for input_name, vibe_input in inputs.items():
        if vibe_input.node_id in public_bindings:
            public_bindings[vibe_input.node_id].append((input_name, vibe_input.field))

    result: dict[str, NodeFieldSnapshot] = {}
    for node_id, node in nodes.items():
        uid_key = node.uid if node.uid else node_id

        # Combine non-link widget and input values into a sorted, canonicalized sig.
        all_values: dict[str, Any] = {**node.widgets, **node.inputs}
        widget_sig = tuple(sorted((k, repr(v)) for k, v in all_values.items()))

        incoming_sig = tuple(sorted(incoming.get(node_id, [])))
        outgoing_sig = tuple(sorted(outgoing.get(node_id, [])))
        binding_sig = tuple(sorted(public_bindings.get(node_id, [])))

        result[uid_key] = {
            "class_type": node.class_type,
            "widget_values_sig": widget_sig,
            "incoming_edge_sig": incoming_sig,
            "outgoing_edge_sig": outgoing_sig,
            "public_input_binding": binding_sig,
        }

    return result
