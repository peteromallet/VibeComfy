"""Single operation-admission gateway (plan §6 T2.1).

``admit_operation(snapshot, canonical_operation)`` is the sole authority that
may allow a canonical operation into an accepted delta or an externally
visible candidate.  Consumers (DSL, typed tools, lint, candidate building,
browser preview, Apply, replay, durable session apply, accepted-batch parse,
and layout ops) consume this result.  Layout ops share this function; there
is no second layout admission path.

The gateway never mutates its snapshot inputs.  Mixed-validity batches are
atomic.  Unknown-touched schema fails closed; there is no whole-graph fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from vibecomfy.ingest.snapshot import WorkflowSnapshot, snapshot_of
from vibecomfy.porting.edit._op_validate import ApplyOpsError, _validate_one
from vibecomfy.porting.edit.ops import (
    EditOp,
    EditOpParseError,
    canonical_op_to_dict,
    parse_edit_op,
)
from vibecomfy.schema import (
    FrozenSchemaSnapshotProvider,
    SchemaSnapshot,
    SchemaSnapshotError,
    require_known_touched_schema,
    schema_snapshot_from_payload,
    touched_schema_classes,
)


LAYOUT_OPERATION_NAMES = frozenset(
    {"set_node_geometry", "add_group", "set_group_geometry", "remove_group"}
)

_SEMANTIC_OPERATION_NAMES = frozenset(
    {
        "set_node_field",
        "add_node",
        "remove_node",
        "upsert_link",
        "remove_link",
        "set_mode",
        "subgraph_interface",
    }
)


@dataclass(frozen=True, slots=True)
class TouchedScope:
    """Schema-complete identities and classes required by one operation."""

    identities: tuple[str, ...]
    class_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    """Immutable WorkflowSnapshot + SchemaSnapshot pair from T1."""

    workflow: WorkflowSnapshot | None = None
    schema: SchemaSnapshot | None = None
    schema_provider: Any = None


@dataclass(frozen=True, slots=True)
class AdmissionAllowed:
    allowed: bool = True
    touched_scope: TouchedScope = TouchedScope((), ())


@dataclass(frozen=True, slots=True)
class AdmissionRejected:
    allowed: bool = False
    typed_reason: str = "rejected"
    evidence_refs: tuple[str, ...] = ()
    touched_scope: TouchedScope = TouchedScope((), ())


AdmissionResult = AdmissionAllowed | AdmissionRejected


def _freeze_snapshot_pair(snapshot: Any) -> AdmissionSnapshot:
    if isinstance(snapshot, AdmissionSnapshot):
        return snapshot
    if isinstance(snapshot, SchemaSnapshot):
        return AdmissionSnapshot(schema=snapshot)
    if isinstance(snapshot, WorkflowSnapshot):
        return AdmissionSnapshot(workflow=snapshot)
    if isinstance(snapshot, tuple) and len(snapshot) == 2:
        workflow, schema = snapshot
        return AdmissionSnapshot(
            workflow=workflow if isinstance(workflow, WorkflowSnapshot) else None,
            schema=schema if isinstance(schema, SchemaSnapshot) else None,
        )
    if isinstance(snapshot, Mapping):
        workflow = snapshot.get("workflow") or snapshot.get("workflow_snapshot")
        schema = snapshot.get("schema") or snapshot.get("schema_snapshot")
        provider = snapshot.get("schema_provider")
        if isinstance(schema, Mapping):
            try:
                schema = schema_snapshot_from_payload(schema)
            except SchemaSnapshotError:
                schema = None
        return AdmissionSnapshot(
            workflow=workflow if isinstance(workflow, WorkflowSnapshot) else None,
            schema=schema if isinstance(schema, SchemaSnapshot) else None,
            schema_provider=provider,
        )
    return AdmissionSnapshot()


def admission_snapshot_for(
    workflow: Any = None,
    schema_provider: Any = None,
    *,
    schema_snapshot: SchemaSnapshot | Mapping[str, Any] | None = None,
) -> AdmissionSnapshot:
    """Build a pair from retained ingest/schema authorities. Never mutates."""

    workflow_snapshot = workflow if isinstance(workflow, WorkflowSnapshot) else snapshot_of(workflow)
    schema = schema_snapshot
    if isinstance(schema, Mapping):
        try:
            schema = schema_snapshot_from_payload(schema)
        except SchemaSnapshotError:
            schema = None
    if schema is None and schema_provider is not None:
        candidate = getattr(schema_provider, "snapshot", None)
        if isinstance(candidate, SchemaSnapshot):
            schema = candidate
    return AdmissionSnapshot(
        workflow=workflow_snapshot if isinstance(workflow_snapshot, WorkflowSnapshot) else None,
        schema=schema if isinstance(schema, SchemaSnapshot) else None,
        schema_provider=schema_provider,
    )


def snapshot_from_schema_witness(
    schema_witness: Mapping[str, Any] | None,
    submit_graph: Mapping[str, Any] | None = None,
    workflow: Any = None,
) -> AdmissionSnapshot:
    """Reconstruct the pair from a persisted schema witness. No ambient lookup."""

    payload = None
    if isinstance(schema_witness, Mapping):
        raw = schema_witness.get("schema_snapshot")
        if isinstance(raw, Mapping):
            payload = raw
        elif schema_witness.get("contract_version") == "schema-snapshot-v1":
            payload = schema_witness
    schema = None
    if isinstance(payload, Mapping):
        try:
            schema = schema_snapshot_from_payload(payload)
        except SchemaSnapshotError:
            schema = None
    return admission_snapshot_for(workflow, schema_snapshot=schema)


def _operation_mapping(operation: Any) -> dict[str, Any]:
    if isinstance(operation, Mapping):
        return dict(operation)
    op_name = getattr(operation, "op", None)
    if isinstance(op_name, str):
        try:
            return dict(canonical_op_to_dict(operation))
        except Exception:
            return {"op": op_name}
    return {}


def _identity_refs(ref: Any, bucket: set[str]) -> None:
    if isinstance(ref, Mapping):
        for key in ("uid", "id", "node_id"):
            value = ref.get(key)
            if value is not None and str(value):
                bucket.add(str(value))
        return
    if isinstance(ref, Sequence) and not isinstance(ref, (str, bytes)) and len(ref) >= 2:
        if ref[1] is not None and str(ref[1]):
            bucket.add(str(ref[1]))
        return
    if isinstance(ref, str) and ref:
        bucket.add(ref)


def _touched_identities(operation: Mapping[str, Any]) -> tuple[str, ...]:
    op_name = str(operation.get("op") or "")
    identities: set[str] = set()
    if op_name in {"set_node_field", "set_mode", "remove_node"}:
        _identity_refs(operation.get("target"), identities)
    elif op_name in {"upsert_link", "remove_link"}:
        _identity_refs(operation.get("from") or operation.get("source"), identities)
        _identity_refs(operation.get("to") or operation.get("target"), identities)
    elif op_name == "add_node":
        _identity_refs(operation.get("uid"), identities)
        _identity_refs(operation.get("node_id"), identities)
        inputs = operation.get("inputs")
        if isinstance(inputs, Mapping):
            for source in inputs.values():
                _identity_refs(source, identities)
        anchor = operation.get("anchor")
        if isinstance(anchor, Mapping):
            _identity_refs(anchor.get("near"), identities)
            between = anchor.get("between")
            if isinstance(between, Sequence) and not isinstance(between, (str, bytes)):
                for ref in between:
                    _identity_refs(ref, identities)
    elif op_name in LAYOUT_OPERATION_NAMES:
        for key in ("uid", "id", "node_id"):
            value = operation.get(key)
            if isinstance(value, (str, int)) and str(value):
                identities.add(str(value))
    elif op_name == "subgraph_interface":
        for key in ("uid", "id", "node_id"):
            value = operation.get(key)
            if isinstance(value, (str, int)) and str(value):
                identities.add(str(value))
    return tuple(sorted(identities))


def _touched_scope(operation: Any, schema: SchemaSnapshot | None) -> TouchedScope:
    mapping = _operation_mapping(operation)
    classes = touched_schema_classes(operation, schema) if schema is not None else ()
    if not classes:
        class_type = mapping.get("class_type")
        classes = (str(class_type),) if isinstance(class_type, str) and class_type else ()
    return TouchedScope(identities=_touched_identities(mapping), class_types=tuple(classes))


def _evidence_refs(
    pair: AdmissionSnapshot,
    operation: Mapping[str, Any],
    *,
    extra: Iterable[str] = (),
) -> tuple[str, ...]:
    refs: list[str] = []
    if pair.workflow is not None:
        refs.append(f"workflow_snapshot:{pair.workflow.semantic_digest}")
    if pair.schema is not None:
        refs.append(f"schema_snapshot:{pair.schema.content_digest}")
    op_name = operation.get("op")
    if isinstance(op_name, str) and op_name:
        refs.append(f"op:{op_name}")
    refs.extend(extra)
    return tuple(dict.fromkeys(refs))


def _reject(
    pair: AdmissionSnapshot,
    operation: Mapping[str, Any],
    typed_reason: str,
    *,
    extra: Iterable[str] = (),
    touched: TouchedScope | None = None,
) -> AdmissionRejected:
    scope = touched if touched is not None else _touched_scope(operation, pair.schema)
    extras = list(extra)
    extras.extend(f"identity:{identity}" for identity in scope.identities)
    extras.extend(f"class_type:{class_type}" for class_type in scope.class_types)
    extras.append(f"reason:{typed_reason}")
    return AdmissionRejected(
        typed_reason=typed_reason,
        evidence_refs=_evidence_refs(pair, operation, extra=extras),
        touched_scope=scope,
    )


def _node_uids(workflow: Any) -> set[str]:
    nodes = getattr(workflow, "nodes", None) or {}
    uids: set[str] = set()
    for node_id, node in nodes.items():
        uid = str(getattr(node, "uid", "") or "")
        uids.add(uid if uid else str(node_id))
        uids.add(str(node_id))
    return uids


def _group_ids(workflow: Any) -> set[str]:
    ids: set[str] = set()
    for group in getattr(workflow, "groups", None) or ():
        if not isinstance(group, Mapping):
            continue
        value = group.get("vibecomfy_group_id")
        if value in (None, ""):
            value = group.get("id")
        if value not in (None, ""):
            ids.add(str(value))
    return ids


def _finite_vector(value: Any, length: int) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != length:
        return False
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return False
        if item != item or item in (float("inf"), float("-inf")):
            return False
    return True


def _admit_layout(
    pair: AdmissionSnapshot,
    operation: Mapping[str, Any],
    *,
    working_workflow: Any,
) -> AdmissionResult:
    op_name = str(operation.get("op") or "")
    extras = set(operation) - {"op"}
    if op_name == "set_node_geometry":
        extras -= {"uid", "pos", "size"}
        if extras:
            return _reject(pair, operation, "malformed_layout_op", extra=sorted(f"key:{key}" for key in extras))
        uid = operation.get("uid")
        if not isinstance(uid, str) or not uid:
            return _reject(pair, operation, "missing_identity", extra=("field:uid",))
        if not _finite_vector(operation.get("pos"), 2):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:pos",))
        if "size" in operation and operation.get("size") is not None and not _finite_vector(operation.get("size"), 2):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:size",))
        if working_workflow is not None and uid not in _node_uids(working_workflow):
            return _reject(pair, operation, "unknown_target", extra=(f"identity:{uid}",))
        return AdmissionAllowed(touched_scope=_touched_scope(operation, pair.schema))

    if op_name == "add_group":
        extras -= {"id", "bounding", "title", "color"}
        if extras:
            return _reject(pair, operation, "malformed_layout_op", extra=sorted(f"key:{key}" for key in extras))
        group_id = operation.get("id")
        if not isinstance(group_id, str) or not group_id:
            return _reject(pair, operation, "missing_identity", extra=("field:id",))
        if not _finite_vector(operation.get("bounding"), 4):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:bounding",))
        if not isinstance(operation.get("title"), str):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:title",))
        color = operation.get("color")
        if color is not None and not isinstance(color, str):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:color",))
        if working_workflow is not None and group_id in _group_ids(working_workflow):
            return _reject(pair, operation, "duplicate_identity", extra=(f"identity:{group_id}",))
        return AdmissionAllowed(touched_scope=_touched_scope(operation, pair.schema))

    if op_name == "set_group_geometry":
        extras -= {"id", "bounding", "title", "color"}
        if extras:
            return _reject(pair, operation, "malformed_layout_op", extra=sorted(f"key:{key}" for key in extras))
        group_id = operation.get("id")
        if not isinstance(group_id, str) or not group_id:
            return _reject(pair, operation, "missing_identity", extra=("field:id",))
        changed = [key for key in ("bounding", "title", "color") if key in operation]
        if not changed:
            return _reject(pair, operation, "malformed_layout_op")
        if "bounding" in operation and not _finite_vector(operation.get("bounding"), 4):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:bounding",))
        if "title" in operation and not isinstance(operation.get("title"), str):
            return _reject(pair, operation, "malformed_layout_op", extra=("field:title",))
        if "color" in operation:
            color = operation.get("color")
            if color is not None and not isinstance(color, str):
                return _reject(pair, operation, "malformed_layout_op", extra=("field:color",))
        if working_workflow is not None and group_id not in _group_ids(working_workflow):
            return _reject(pair, operation, "unknown_target", extra=(f"identity:{group_id}",))
        return AdmissionAllowed(touched_scope=_touched_scope(operation, pair.schema))

    # remove_group
    extras -= {"id"}
    if extras:
        return _reject(pair, operation, "malformed_layout_op", extra=sorted(f"key:{key}" for key in extras))
    group_id = operation.get("id")
    if not isinstance(group_id, str) or not group_id:
        return _reject(pair, operation, "missing_identity", extra=("field:id",))
    if working_workflow is not None and group_id not in _group_ids(working_workflow):
        return _reject(pair, operation, "unknown_target", extra=(f"identity:{group_id}",))
    return AdmissionAllowed(touched_scope=_touched_scope(operation, pair.schema))


def _schema_provider_for(pair: AdmissionSnapshot) -> Any:
    if pair.schema is not None:
        return FrozenSchemaSnapshotProvider(pair.schema)
    return pair.schema_provider


def admit_operation(
    snapshot: Any,
    canonical_operation: Any,
    *,
    working_workflow: Any = None,
) -> AdmissionResult:
    """Admit one canonical operation against the retained T1 snapshot pair.

    Returns ``AdmissionAllowed`` or ``AdmissionRejected``.  Never mutates
    ``snapshot`` or ``canonical_operation``.  ``working_workflow`` is a
    sequential simulation handle for add-then-wire batches; it is not an
    authority and is never written by this function.
    """

    pair = _freeze_snapshot_pair(snapshot)
    operation = _operation_mapping(canonical_operation)
    op_name = str(operation.get("op") or "")
    touched = _touched_scope(canonical_operation, pair.schema)
    workflow = working_workflow
    if workflow is None and pair.workflow is not None:
        workflow = pair.workflow.workflow

    schema_catalog: SchemaSnapshot | Mapping[str, Any] | None = pair.schema
    if schema_catalog is None and isinstance(snapshot, Mapping) and (
        "schemas" in snapshot or "node_classes" in snapshot or "missing_classes" in snapshot
    ):
        schema_catalog = snapshot
    if schema_catalog is not None:
        try:
            require_known_touched_schema(canonical_operation, schema_catalog)
        except SchemaSnapshotError as exc:
            return _reject(pair, operation, exc.code, extra=(str(exc),), touched=touched)

    if not op_name:
        return _reject(pair, operation, "unsupported_op", touched=touched)

    if op_name in LAYOUT_OPERATION_NAMES:
        return _admit_layout(pair, operation, working_workflow=workflow)

    if op_name not in _SEMANTIC_OPERATION_NAMES:
        return _reject(pair, operation, "unsupported_op", touched=touched)

    parsed: EditOp
    if isinstance(canonical_operation, (str, bytes)):
        return _reject(pair, operation, "unsupported_op", touched=touched)
    if hasattr(canonical_operation, "op") and not isinstance(canonical_operation, Mapping):
        parsed = canonical_operation  # type: ignore[assignment]
    else:
        try:
            parsed = parse_edit_op(operation)
        except EditOpParseError as exc:
            return _reject(
                pair,
                operation,
                getattr(exc, "code", None) or "malformed_op",
                extra=(str(exc),),
                touched=touched,
            )

    if workflow is None:
        return AdmissionAllowed(touched_scope=touched)

    provider = _schema_provider_for(pair)
    try:
        _validate_one(workflow, parsed, provider)
    except ApplyOpsError as exc:
        return _reject(pair, operation, exc.code, extra=(exc.message,), touched=touched)
    return AdmissionAllowed(touched_scope=touched)


def admit_operations(
    snapshot: Any,
    operations: Sequence[Any],
    *,
    working_workflow: Any = None,
) -> AdmissionResult:
    """Admit a batch atomically. One rejection rejects the whole batch."""

    pair = _freeze_snapshot_pair(snapshot)
    workflow = working_workflow
    if workflow is None and pair.workflow is not None:
        workflow = pair.workflow.workflow
    from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy, apply_edit_cow

    simulated = _cow_workflow_copy(workflow) if workflow is not None else None
    last_allowed: AdmissionAllowed | None = None
    for operation in operations:
        result = admit_operation(pair, operation, working_workflow=simulated)
        if isinstance(result, AdmissionRejected):
            return result
        last_allowed = result
        mapping = _operation_mapping(operation)
        if simulated is None or mapping.get("op") in LAYOUT_OPERATION_NAMES:
            continue
        parsed = operation if hasattr(operation, "op") and not isinstance(operation, Mapping) else parse_edit_op(mapping)
        try:
            simulated = apply_edit_cow(
                simulated, parsed, schema_provider=_schema_provider_for(pair)
            )
        except Exception:
            # Simulation failure is still a typed rejection of the batch.
            return _reject(pair, mapping, "apply_failed")
    if last_allowed is None:
        return AdmissionAllowed()
    return last_allowed


def rejected_ops_are_invisible(result: AdmissionResult) -> bool:
    """Rejected ops must not enter accepted delta or visible candidates."""

    return isinstance(result, AdmissionRejected) or result.allowed is True


__all__ = [
    "AdmissionAllowed",
    "AdmissionRejected",
    "AdmissionResult",
    "AdmissionSnapshot",
    "LAYOUT_OPERATION_NAMES",
    "TouchedScope",
    "admission_snapshot_for",
    "admit_operation",
    "admit_operations",
    "rejected_ops_are_invisible",
    "snapshot_from_schema_witness",
]
