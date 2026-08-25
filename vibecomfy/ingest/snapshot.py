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
    # Canonical compact-widget field names aligned 1:1 with widgets_values
    # positions (P0-WIDGET-CANON).  Frozen at seal time; the ONLY name
    # authority consumed by admit / interpret / emit / replay.  Deliberately
    # excluded from _semantic_preimage so digest equality is unchanged.
    widget_names_sig: tuple


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


def _capture_widget_names(
    node: Any,
    node_id: str,
    incoming: Mapping[str, list],
) -> tuple[str, ...]:
    """Seal one node's canonical compact-widget name roster (P0-WIDGET-CANON).

    Resolved once here with the full source precedence (linked sockets
    excluded via the incoming-edge truth), then frozen: later admit /
    interpret / emit / replay stages read THIS table and never re-derive
    names from ambient object_info or live provider state.

    Lazy resolver import: ``compact_resolver`` sits above ingest in the
    layering, and importing it at module load would cycle through
    ``ingest.normalize``.
    """
    from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node

    linked_inputs = frozenset(str(to_input) for to_input, _ in incoming.get(node_id, []))
    try:
        resolution = compact_widget_names_for_node(
            node,
            linked_inputs=linked_inputs,
        )
    except Exception:  # noqa: BLE001 - sealing must never fail on exotic nodes
        return ()
    return tuple(resolution.names)


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
            "widget_names_sig": _capture_widget_names(node, node_id, incoming),
        }
    return result



def frozen_widget_names_by_uid(workflow: Any) -> Mapping[str, tuple[str, ...]]:
    """Read the sealed node→field-names table off *workflow*'s snapshot.

    Returns ``{uid: names}`` for every node whose seal captured a non-empty
    roster.  This mapping is the single name authority handed to admit /
    interpret / emit / replay; consumers never re-derive names from ambient
    object_info or live provider state for sealed nodes.
    """
    snapshot = snapshot_of(workflow)
    if snapshot is None:
        return {}
    field_snapshot = getattr(snapshot, "field_snapshot", None)
    if not isinstance(field_snapshot, Mapping):
        return {}
    result: dict[str, tuple[str, ...]] = {}
    for uid, snap in field_snapshot.items():
        names = snap.get("widget_names_sig") if isinstance(snap, Mapping) else None
        if isinstance(names, (list, tuple)) and names:
            result[str(uid)] = tuple(str(name) for name in names if name)
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


def raw_link_identity(
    snapshot: "WorkflowSnapshot",
) -> dict[tuple[str, str, str, str], int]:
    """Retained LiteGraph link IDs keyed by endpoint names, from the sidecar.

    RRSYN-3: graph inspection must carry the ORIGINAL LiteGraph ``links[i][0]``
    ids rather than enumeration indices.  The IR edge model (``VibeEdge``)
    drops the numeric id, so the lossless ``raw_sidecar`` is the only retained
    source.  Keys are ``(origin_node_id, output_name, target_node_id,
    input_name)`` — stable across the raw/IR representations.

    UI-format sidecars only; API-format or missing sidecars yield ``{}``.
    Callers fail closed to "identity unavailable" instead of inventing IDs.
    """
    raw = snapshot.raw_sidecar
    if not isinstance(raw, Mapping) or not isinstance(raw.get("nodes"), list):
        return {}
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for node in raw["nodes"]:
        if isinstance(node, Mapping) and node.get("id") is not None:
            nodes_by_id[str(node["id"])] = dict(node)

    def _input_name(node_id: Any, slot_index: Any) -> str | None:
        node = nodes_by_id.get(str(node_id))
        inputs = node.get("inputs") if isinstance(node, Mapping) else None
        if not isinstance(inputs, list) or not isinstance(slot_index, int):
            return None
        if slot_index < 0 or slot_index >= len(inputs):
            return None
        entry = inputs[slot_index]
        name = entry.get("name") if isinstance(entry, Mapping) else None
        return str(name) if isinstance(name, str) and name else None

    def _output_name(node_id: Any, slot_index: Any) -> str | None:
        node = nodes_by_id.get(str(node_id))
        outputs = node.get("outputs") if isinstance(node, Mapping) else None
        if not isinstance(outputs, list) or not isinstance(slot_index, int):
            return None
        if slot_index < 0 or slot_index >= len(outputs):
            return None
        entry = outputs[slot_index]
        name = entry.get("name") if isinstance(entry, Mapping) else None
        return str(name) if isinstance(name, str) and name else None

    identity: dict[tuple[str, str, str, str], int] = {}
    links = raw.get("links")
    if not isinstance(links, list):
        return {}

    def _spellings(
        oid: Any, osl: Any, oname: str | None, tid: Any, tsl: Any, tiname: str | None
    ) -> tuple[tuple[str, str, str, str], ...]:
        """Address spellings for one link's endpoints.

        Raw nodes may lack ``outputs`` arrays (or the origin may be absent),
        so each side is addressed by its declared NAME when available and
        always by its numeric slot index.  The IR edge names must match one
        of these spellings; every spelling maps to the SAME retained id —
        no id is ever derived from enumeration order.
        """
        out_forms = {str(osl)}
        if oname is not None:
            out_forms.add(oname)
        in_forms = {str(tsl)}
        if tiname is not None:
            in_forms.add(tiname)
        return tuple(
            (str(oid), o, str(tid), t) for o in sorted(out_forms) for t in sorted(in_forms)
        )

    for link in links:
        if isinstance(link, (list, tuple)) and len(link) >= 5:
            lid, oid, osl, tid, tsl = link[0], link[1], link[2], link[3], link[4]
        elif isinstance(link, Mapping):
            lid = link.get("id", link.get("link_id"))
            oid = link.get("origin_id")
            osl = link.get("origin_slot")
            tid = link.get("target_id")
            tsl = link.get("target_slot")
        else:
            continue
        if not isinstance(lid, int) or isinstance(lid, bool):
            continue
        oname = _output_name(oid, osl)
        tiname = _input_name(tid, tsl)
        for key in _spellings(oid, osl, oname, tid, tsl, tiname):
            identity.setdefault(key, lid)
    return identity
