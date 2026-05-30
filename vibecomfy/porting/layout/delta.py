"""Field-level delta computation between an ingest snapshot and the current IR.

``compute_field_delta`` compares a stored ``_ingest_snapshot`` (captured at
ingest time by ``vibecomfy.ingest.snapshot.capture_ingest_snapshot``) against
the live IR state of a ``VibeWorkflow``.

Nodes absent from *snapshot* (added after ingest) are omitted from the result —
downstream logic treats them as ``'snapshot-absent'``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

_SNAPSHOT_FIELDS = (
    "class_type",
    "widget_values_sig",
    "incoming_edge_sig",
    "outgoing_edge_sig",
    "public_input_binding",
)


def compute_field_delta(
    snapshot: dict[str, Any],
    current_ir: "VibeWorkflow",
) -> dict[str, dict[str, tuple]]:
    """Compute field-level changes between a stored snapshot and the current IR.

    Parameters
    ----------
    snapshot:
        A ``{uid: NodeFieldSnapshot}`` dict as returned by
        ``capture_ingest_snapshot``.  This is the *before* state.
    current_ir:
        The live ``VibeWorkflow`` to compare against.  This is the *after* state.

    Returns
    -------
    ``{uid: {field_name: (old_value, new_value)}}`` — only nodes and fields
    where something changed.  Nodes absent from *snapshot* are omitted.
    Nodes in *snapshot* but absent from *current_ir* (removed nodes) are also
    omitted; callers that need to detect removals should diff snapshot keys against
    the current IR's uid set directly.
    """
    # Build uid → node lookup for the current IR.
    uid_to_node = {(node.uid if node.uid else node_id): node for node_id, node in current_ir.nodes.items()}

    # Recompute current signatures inline to avoid a round-trip through capture.
    nodes = current_ir.nodes
    edges = current_ir.edges
    workflow_inputs = current_ir.inputs

    id_to_uid: dict[str, str] = {}
    for node_id, node in nodes.items():
        id_to_uid[node_id] = node.uid if node.uid else node_id

    incoming: dict[str, list] = {node_id: [] for node_id in nodes}
    for edge in edges:
        if edge.to_node in incoming:
            source_uid = id_to_uid.get(edge.from_node, edge.from_node)
            incoming[edge.to_node].append((edge.to_input, (source_uid, edge.from_output)))

    outgoing: dict[str, list] = {node_id: [] for node_id in nodes}
    for edge in edges:
        if edge.from_node in outgoing:
            target_uid = id_to_uid.get(edge.to_node, edge.to_node)
            outgoing[edge.from_node].append((edge.from_output, (target_uid, edge.to_input)))

    public_bindings: dict[str, list] = {node_id: [] for node_id in nodes}
    for input_name, vibe_input in workflow_inputs.items():
        if vibe_input.node_id in public_bindings:
            public_bindings[vibe_input.node_id].append((input_name, vibe_input.field))

    delta: dict[str, dict[str, tuple]] = {}
    for uid, old_snap in snapshot.items():
        node = uid_to_node.get(uid)
        if node is None:
            # Node removed after snapshot — omit per spec (caller diffs keys directly).
            continue

        # Recompute the current signature for this node.
        all_values = {**node.widgets, **node.inputs}
        current: dict[str, Any] = {
            "class_type": node.class_type,
            "widget_values_sig": tuple(sorted((k, repr(v)) for k, v in all_values.items())),
            "incoming_edge_sig": tuple(sorted(incoming.get(node.id, []))),
            "outgoing_edge_sig": tuple(sorted(outgoing.get(node.id, []))),
            "public_input_binding": tuple(sorted(public_bindings.get(node.id, []))),
        }

        node_delta: dict[str, tuple] = {}
        for field_name in _SNAPSHOT_FIELDS:
            old_val = old_snap[field_name]
            new_val = current[field_name]
            if old_val != new_val:
                node_delta[field_name] = (old_val, new_val)

        if node_delta:
            delta[uid] = node_delta

    return delta
