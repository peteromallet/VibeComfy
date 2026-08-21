"""Ingest-time snapshot capture for uid-keyed field signatures and WorkflowSnapshot.

Captures a frozen snapshot of each node's field state at ingest time so that
later delta computation can identify which fields changed (widget edits, rewires,
public-input rebindings) versus which nodes were added or had no snapshot taken.

``NodeFieldSnapshot`` is a TypedDict with all-tuple fields for stable comparison.
Tuples are sorted and canonicalized — no rank/positional ordering.

``WorkflowSnapshot`` is the T1.1 immutable ingest authority: a retained copy of
canonical ``VibeWorkflow`` plus source representation/digest, semantic-hash
version, layout *reference* (not layout-as-semantics), raw sidecar, stable
identity/topology, and session/turn lineage.  The live ``VibeWorkflow`` dataclass
is never frozen in place; the snapshot holds an independent copy/handle.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.comfy_nodes.agent._canonical_contract_primitives import (
    canonical_json_bytes_v1,
)

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[no-redef]


SEMANTIC_HASH_VERSION = "workflow-snapshot-v1"
WORKFLOW_SNAPSHOT_METADATA_KEY = "_workflow_snapshot"


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


class SnapshotAuthorityError(ValueError):
    """Fail-closed comparison/replay authority error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class WorkflowLineage:
    """Scenario/session/turn/baseline lineage bound at ingest/allocation."""

    scenario_id: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    baseline_id: str | None = None


@dataclass(frozen=True, slots=True)
class LayoutReference:
    """Layout is a REFERENCE, never mixed into semantic graph content."""

    kind: str
    digest: str | None = None


@dataclass(frozen=True)
class WorkflowSnapshot:
    """Immutable ingest authority for one retained canonical ``VibeWorkflow``."""

    workflow: Any
    source_representation: str
    source_digest: str
    semantic_hash_version: str
    semantic_digest: str
    layout: LayoutReference
    raw_sidecar: Mapping[str, Any]
    identity: tuple[str, ...]
    topology: tuple[tuple[str, str, str, str], ...]
    lineage: WorkflowLineage = field(default_factory=WorkflowLineage)
    field_snapshot: Mapping[str, NodeFieldSnapshot] = field(default_factory=dict)
    shape: str = "unknown"


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
    del raw_ui_or_api
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


def _freeze_jsonable(value: Any) -> Any:
    """Detach mappings/lists so sidecar mutation cannot alias ingest."""
    if isinstance(value, Mapping):
        return {str(key): _freeze_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_freeze_jsonable(item) for item in value]
    return value


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _digest(value: Any) -> str:
    """SHA-256 of the shared canonical-JSON leaf. Not a second hasher."""
    return hashlib.sha256(canonical_json_bytes_v1(value, ensure_ascii=False)).hexdigest()


def _node_uid(node: Any, node_id: str) -> str:
    uid = getattr(node, "uid", "") or ""
    return uid if uid else str(node_id)


def _identity_and_topology(workflow: Any) -> tuple[tuple[str, ...], tuple[tuple[str, str, str, str], ...]]:
    id_to_uid = {
        str(node_id): _node_uid(node, str(node_id))
        for node_id, node in workflow.nodes.items()
    }
    identity = tuple(sorted(id_to_uid.values()))
    topology = tuple(
        sorted(
            (
                id_to_uid.get(str(edge.from_node), str(edge.from_node)),
                str(edge.from_output),
                id_to_uid.get(str(edge.to_node), str(edge.to_node)),
                str(edge.to_input),
            )
            for edge in workflow.edges
        )
    )
    return identity, topology


def _layout_preimage(workflow: Any) -> dict[str, Any]:
    nodes = []
    for node_id, node in sorted(workflow.nodes.items(), key=lambda item: str(item[0])):
        nodes.append(
            {
                "uid": _node_uid(node, str(node_id)),
                "pos": _jsonable(getattr(node, "pos", None)),
                "size": _jsonable(getattr(node, "size", None)),
            }
        )
    return {"nodes": nodes, "groups": _jsonable(getattr(workflow, "groups", []) or [])}


def _semantic_preimage(
    *,
    identity: tuple[str, ...],
    topology: tuple[tuple[str, str, str, str], ...],
    field_snapshot: Mapping[str, NodeFieldSnapshot],
) -> dict[str, Any]:
    fields = {
        uid: {
            "class_type": snap["class_type"],
            "widget_values_sig": _jsonable(snap["widget_values_sig"]),
            "incoming_edge_sig": _jsonable(snap["incoming_edge_sig"]),
            "outgoing_edge_sig": _jsonable(snap["outgoing_edge_sig"]),
            "public_input_binding": _jsonable(snap["public_input_binding"]),
        }
        for uid, snap in sorted(field_snapshot.items())
    }
    return {
        "semantic_hash_version": SEMANTIC_HASH_VERSION,
        "identity": list(identity),
        "topology": [list(edge) for edge in topology],
        "fields": fields,
    }


def representation_family(source_representation: str) -> str:
    """Collapse wrapper-equivalent API spellings for mixed-representation checks."""
    if source_representation in {"api", "prompt_api"}:
        return "api"
    return source_representation


def snapshot_of(workflow: Any) -> WorkflowSnapshot | None:
    metadata = getattr(workflow, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    snapshot = metadata.get(WORKFLOW_SNAPSHOT_METADATA_KEY)
    return snapshot if isinstance(snapshot, WorkflowSnapshot) else None


def bind_snapshot_lineage(
    workflow: Any,
    *,
    scenario_id: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    baseline_id: str | None = None,
) -> WorkflowSnapshot | None:
    """Rebind lineage on the retained snapshot without mutating the live IR copy."""
    snapshot = snapshot_of(workflow)
    if snapshot is None:
        return None
    bound = replace(
        snapshot,
        lineage=WorkflowLineage(
            scenario_id=scenario_id if scenario_id is not None else snapshot.lineage.scenario_id,
            session_id=session_id if session_id is not None else snapshot.lineage.session_id,
            turn_id=turn_id if turn_id is not None else snapshot.lineage.turn_id,
            baseline_id=baseline_id if baseline_id is not None else snapshot.lineage.baseline_id,
        ),
    )
    workflow.metadata[WORKFLOW_SNAPSHOT_METADATA_KEY] = bound
    return bound


def compare_snapshot_authority(left: WorkflowSnapshot, right: WorkflowSnapshot) -> None:
    """Reject mixed raw representations or cross-turn/session lineage."""
    if representation_family(left.source_representation) != representation_family(
        right.source_representation
    ):
        raise SnapshotAuthorityError(
            "mixed_representation",
            "comparison/replay cannot mix raw representations "
            f"{left.source_representation!r} and {right.source_representation!r}",
        )
    if left.semantic_hash_version != right.semantic_hash_version:
        raise SnapshotAuthorityError(
            "semantic_hash_version_mismatch",
            "comparison/replay cannot mix semantic hash versions "
            f"{left.semantic_hash_version!r} and {right.semantic_hash_version!r}",
        )
    if (
        left.lineage.session_id
        and right.lineage.session_id
        and left.lineage.session_id != right.lineage.session_id
    ):
        raise SnapshotAuthorityError(
            "cross_session_lineage",
            "comparison/replay cannot mix session lineage "
            f"{left.lineage.session_id!r} and {right.lineage.session_id!r}",
        )
    if (
        left.lineage.turn_id
        and right.lineage.turn_id
        and left.lineage.turn_id != right.lineage.turn_id
    ):
        raise SnapshotAuthorityError(
            "cross_turn_lineage",
            "comparison/replay cannot mix turn lineage "
            f"{left.lineage.turn_id!r} and {right.lineage.turn_id!r}",
        )


def capture_workflow_snapshot(
    raw_ui_or_api: Mapping[str, Any] | None,
    ir_workflow: "VibeWorkflow",
    *,
    source_representation: str,
    lineage: WorkflowLineage | None = None,
) -> WorkflowSnapshot:
    """Freeze a copy/handle of *ir_workflow* plus lossless raw sidecar.

    Does not freeze the live ``VibeWorkflow`` dataclass in place.  Layout is
    hashed as a reference only and is excluded from ``semantic_digest``.
    Canonical JSON/hash identity is ``canonical_json_bytes_v1``.
    """
    field_snapshot = capture_ingest_snapshot(
        dict(raw_ui_or_api) if isinstance(raw_ui_or_api, Mapping) else None,
        ir_workflow,
    )
    identity, topology = _identity_and_topology(ir_workflow)
    sidecar_src = _freeze_jsonable(raw_ui_or_api if isinstance(raw_ui_or_api, Mapping) else {})
    layout_digest = _digest(_layout_preimage(ir_workflow))
    semantic_digest = _digest(
        _semantic_preimage(
            identity=identity,
            topology=topology,
            field_snapshot=field_snapshot,
        )
    )
    source_digest = _digest(_jsonable(sidecar_src))
    retained = ir_workflow.copy()
    retained_metadata = getattr(retained, "metadata", None)
    if isinstance(retained_metadata, dict):
        retained_metadata.pop(WORKFLOW_SNAPSHOT_METADATA_KEY, None)
    return WorkflowSnapshot(
        workflow=retained,
        source_representation=source_representation,
        source_digest=source_digest,
        semantic_hash_version=SEMANTIC_HASH_VERSION,
        semantic_digest=semantic_digest,
        layout=LayoutReference(kind="ingest_geometry_ref", digest=layout_digest),
        raw_sidecar=sidecar_src,
        identity=identity,
        topology=topology,
        lineage=lineage if lineage is not None else WorkflowLineage(),
        field_snapshot=dict(field_snapshot),
        shape=source_representation,
    )
