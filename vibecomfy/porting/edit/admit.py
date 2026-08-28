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
import logging

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

_LOGGER = logging.getLogger(__name__)

# Keep LayerMask: SegmentAnythingUltra V3 fail-closed while other provisional
# adds are allowed — documents test_admit_operation_families_and_fail_closed_unknown_touched.
_CARVED_OUT_FAIL_CLOSED_CLASSES = frozenset({"LayerMask: SegmentAnythingUltra V3"})

def _add_node_provisional_allows(
    operation: Mapping[str, Any],
    catalog: SchemaSnapshot | Mapping[str, Any] | None,
    *,
    working_workflow: Any | None = None,
) -> bool:
    """Schema-known unresolved-anchor behavior ONLY (DEEP-AUDIT-FIX-1-ADJUDICATION).

    Retained solely so an add_node whose OWN class_type is already present in
    the frozen catalog (in ``known`` AND absent from ``missing``) can still be
    admitted when an anchor/endpoint identity is unresolved in the node-class
    map but present in the sequential working workflow. It may NOT forgive
    class absence: an added class absent from the frozen authority returns
    False and admission rejects. Evidence-backed provisional classes are
    already inside the completed frozen generation before admission runs, so
    this helper performs no provider probe at all.
    """
    if str(operation.get("op") or "") != "add_node":
        return False
    class_type = operation.get("class_type")
    if not isinstance(class_type, str) or not class_type:
        return False
    if class_type in _CARVED_OUT_FAIL_CLOSED_CLASSES:
        return False
    try:
        from vibecomfy.schema.types import (
            _operation_schema_endpoints,
            _snapshot_known_and_missing,
            _snapshot_node_class_map,
        )
        known, missing = _snapshot_known_and_missing(catalog)
        # ADJUDICATION: never forgive class absence — fail closed unless the
        # added class_type is already schema-known in the frozen authority.
        if class_type not in known or class_type in missing:
            return False
        all_classes = set(touched_schema_classes(operation, catalog))
        remaining = all_classes - {class_type}
        if working_workflow is not None and remaining:
            try:
                nodes = getattr(working_workflow, "nodes", {}) or {}
                workflow_classes = {str(getattr(n, "class_type", "") or "") for n in nodes.values()}
                remaining = {c for c in remaining if c not in workflow_classes}
            except Exception as exc:
                _LOGGER.debug("provisional remaining filter failed: %s", exc)
        unknown_remaining = [c for c in remaining if c not in known or c in missing]
        if unknown_remaining:
            return False
        required, _optional, _explicit = _operation_schema_endpoints(operation, catalog)
        node_classes = _snapshot_node_class_map(catalog)
        if working_workflow is not None:
            try:
                nodes = getattr(working_workflow, "nodes", {}) or {}
                workflow_uids = set()
                for nid, node in nodes.items():
                    uid = str(getattr(node, "uid", "") or "")
                    workflow_uids.add(uid if uid else str(nid))
                    workflow_uids.add(str(nid))
                required = {ident for ident in required if ident not in workflow_uids}
            except Exception as exc:
                _LOGGER.debug("provisional required filter failed: %s", exc)
        unresolved = [ident for ident in required if ident not in node_classes]
        if unresolved:
            return False
        return True
    except Exception as exc:
        _LOGGER.debug("provisional add_node check failed: %s", exc)
        return False



def _is_provisional_touched(
    operation: Mapping[str, Any],
    workflow: Any | None,
    catalog: SchemaSnapshot | Mapping[str, Any] | None,
) -> bool:
    """True when operation touches a provisional/unknown node present in workflow."""
    if catalog is None:
        return False
    try:
        from vibecomfy.schema.types import _snapshot_known_and_missing
        known, missing = _snapshot_known_and_missing(catalog)
        if not known and not missing:
            return False
        touched = set(_touched_identities(operation))
        if not touched or workflow is None:
            return False
        nodes = getattr(workflow, "nodes", {}) or {}
        uid_to_class: dict[str, str] = {}
        for nid, node in nodes.items():
            uid = str(getattr(node, "uid", "") or "")
            cls = str(getattr(node, "class_type", "") or "")
            uid_to_class[uid if uid else str(nid)] = cls
            uid_to_class[str(nid)] = cls
        for tid in touched:
            cls = uid_to_class.get(str(tid))
            if cls and (cls not in known or cls in missing):
                return True
        if str(operation.get("op") or "") == "add_node":
            cls = operation.get("class_type")
            if isinstance(cls, str) and cls and (cls not in known or cls in missing):
                return True
        return False
    except Exception as exc:
        _LOGGER.debug("provisional touched check failed: %s", exc)
        return False


def _is_provisional_touched_for_admit(
    operation: Mapping[str, Any],
    workflow: Any | None,
    catalog: SchemaSnapshot | Mapping[str, Any] | None,
    *,
    working_workflow: Any | None = None,
) -> bool:
    """Canonical helper reused by admit and _interpret (single import).

    Wraps :func:`_is_provisional_touched` with the LayerMask carve-out.
    ``working_workflow`` is accepted for signature compatibility with the
    add-node path but not needed for touched-only checks.
    """
    if str(operation.get("op") or "") == "add_node":
        class_type = operation.get("class_type")
        if isinstance(class_type, str) and class_type in _CARVED_OUT_FAIL_CLOSED_CLASSES:
            return False
    # For add_node provisional, also allow when class itself is provisional even
    # if workflow is None or touched is empty — mirror _is_provisional_touched's
    # add_node branch but using the same catalog.
    # FAIL-CLOSED: when catalog is None, no schema evidence exists, so do NOT
    # admit provisional adds — missing catalog must reject schema-dependent ops.
    if str(operation.get("op") or "") == "add_node":
        if catalog is None:
            return False
        try:
            from vibecomfy.schema.types import _snapshot_known_and_missing
            known, missing = _snapshot_known_and_missing(catalog)
            cls = operation.get("class_type")
            if isinstance(cls, str) and cls and (cls not in known or cls in missing):
                return True
        except (KeyError, AttributeError, Exception) as exc:
            _LOGGER.debug("canonical add_node provisional check failed: %s", exc)
            return False
    return _is_provisional_touched(operation, workflow, catalog)

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


def _bind_schema_from_provider(schema_provider: Any) -> SchemaSnapshot | None:
    """Bind a frozen SchemaSnapshot from a live provider, or None.

    Live providers that expose ``snapshot`` as a SchemaSnapshot are bound.
    Providers that expose ``schemas()``/``get_schema`` without a frozen
    snapshot are not silently treated as schema-complete: callers must
    either pass a verified SchemaSnapshot or the gateway fails closed.
    """

    if schema_provider is None:
        return None
    candidate = getattr(schema_provider, "snapshot", None)
    if callable(candidate):
        try:
            candidate = candidate()
        except Exception as exc:
            _LOGGER.debug("schema provider snapshot callable failed: %s", exc)
            candidate = None
    if isinstance(candidate, SchemaSnapshot):
        return candidate
    return None


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
        schema = _bind_schema_from_provider(schema_provider)
    return AdmissionSnapshot(
        workflow=workflow_snapshot if isinstance(workflow_snapshot, WorkflowSnapshot) else None,
        schema=schema if isinstance(schema, SchemaSnapshot) else None,
        schema_provider=schema_provider,
    )


def _schema_catalog_for(pair: AdmissionSnapshot, snapshot: Any) -> SchemaSnapshot | Mapping[str, Any] | None:
    """Verified schema catalog for require_known_touched_schema.

    Only a frozen SchemaSnapshot or an explicit mapping catalog counts.
    A live schema_provider with no frozen snapshot is not a catalog.
    """

    if pair.schema is not None:
        return pair.schema
    if isinstance(snapshot, Mapping) and (
        "schemas" in snapshot or "node_classes" in snapshot or "missing_classes" in snapshot
    ):
        return snapshot
    return None


def _needs_schema_knowledge(operation: Mapping[str, Any]) -> bool:
    """True when the op's touched closure is schema-dependent (T1.2 MUST-001)."""

    op_name = str(operation.get("op") or "")
    if op_name in _SEMANTIC_OPERATION_NAMES:
        return True
    return False





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
        except Exception as exc:
            _LOGGER.debug("canonical_op_to_dict failed: %s", exc)
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
    """Validation provider built from the schema pair.

    When a frozen SchemaSnapshot exists, admission validates against
    ``FrozenSchemaSnapshotProvider(pair.schema)``.  When no frozen snapshot
    exists but a live schema_provider was retained, fall back to it so
    providers without ``.snapshot`` (test mocks, minimal providers) can
    still validate.
    """
    if pair.schema is not None:
        return FrozenSchemaSnapshotProvider(pair.schema)
    if pair.schema_provider is not None:
        return pair.schema_provider
    return None


def _offered_endpoint_refs(operation: Any) -> tuple[str, ...]:
    """Return the endpoint aliases an operation offered, for rejection
    evidence (RRSYN2-4)."""
    mapping = operation if isinstance(operation, Mapping) else None
    if mapping is None:
        try:
            mapping = _operation_mapping(operation)
        except Exception:  # noqa: BLE001 - evidence extraction must never raise
            return ()
    op_name = str(mapping.get("op") or "")
    refs: list[str] = []
    if op_name == "upsert_link":
        source = mapping.get("source")
        if source is None and isinstance(mapping.get("from"), (list, tuple)):
            from_ref = mapping["from"]
            source = (
                {"uid": from_ref[0] if len(from_ref) > 0 else None,
                 "output_slot": from_ref[2] if len(from_ref) > 2 else None}
                if isinstance(from_ref, (list, tuple)) and len(from_ref) >= 3
                else None
            )
        if not isinstance(source, Mapping) and hasattr(operation, "source"):
            src_obj = getattr(operation, "source", None)
            if src_obj is not None:
                source = {
                    "uid": getattr(src_obj, "uid", None),
                    "output_slot": getattr(src_obj, "output_slot", None),
                }
        target = mapping.get("target")
        if target is None and isinstance(mapping.get("to"), (list, tuple)):
            to_ref = mapping["to"]
            target = (
                {"uid": to_ref[0] if len(to_ref) > 0 else None,
                 "input_field": to_ref[2] if len(to_ref) > 2 else None}
                if isinstance(to_ref, (list, tuple)) and len(to_ref) >= 3
                else None
            )
        if not isinstance(target, Mapping) and hasattr(operation, "target"):
            tgt_obj = getattr(operation, "target", None)
            if tgt_obj is not None:
                target = {
                    "uid": getattr(tgt_obj, "uid", None),
                    "input_field": getattr(tgt_obj, "input_field", None),
                }
        if isinstance(source, Mapping):
            refs.append(
                f"source:{source.get('uid')}.{source.get('output_slot')}"
            )
        if isinstance(target, Mapping):
            refs.append(
                f"target:{target.get('uid')}.{target.get('input_field')}"
            )
    elif op_name == "add_node":
        inputs = mapping.get("inputs")
        if isinstance(inputs, Mapping):
            for field, link_source in inputs.items():
                slot = None
                uid = None
                if isinstance(link_source, Mapping):
                    slot = link_source.get("output_slot")
                    uid = link_source.get("uid")
                elif isinstance(link_source, (list, tuple)) and len(link_source) >= 3:
                    uid, slot = link_source[0], link_source[2]
                elif hasattr(link_source, "output_slot"):
                    slot = getattr(link_source, "output_slot", None)
                    uid = getattr(link_source, "uid", None)
                refs.append(f"{field}<-{uid}.{slot}")
    return tuple(refs)


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

    ``snapshot=None`` (or any pair with no verified SchemaSnapshot/catalog)
    fails closed for operations whose touched closure needs schema knowledge.
    """

    pair = _freeze_snapshot_pair(snapshot)
    operation = _operation_mapping(canonical_operation)
    op_name = str(operation.get("op") or "")
    schema_catalog = _schema_catalog_for(pair, snapshot)
    touched = _touched_scope(canonical_operation, pair.schema)
    if schema_catalog is not None and pair.schema is None and isinstance(schema_catalog, Mapping):
        classes = touched_schema_classes(canonical_operation, schema_catalog)
        if not classes:
            class_type = operation.get("class_type")
            classes = (str(class_type),) if isinstance(class_type, str) and class_type else ()
        touched = TouchedScope(identities=_touched_identities(operation), class_types=tuple(classes))
    workflow = working_workflow
    if workflow is None and pair.workflow is not None:
        workflow = pair.workflow.workflow

    if schema_catalog is not None:
        try:
            require_known_touched_schema(canonical_operation, schema_catalog)
        except SchemaSnapshotError as exc:
            # DEEP-AUDIT-FIX-1-ADJUDICATION: the immutable pair.schema is the
            # SOLE admission authority. The retained live provider is never
            # consulted to complete a touched closure — evidence-backed
            # provisional schemas must already be part of the completed frozen
            # generation pinned on the composite. Only the schema-known
            # unresolved-anchor add behavior remains.
            if _add_node_provisional_allows(operation, schema_catalog, working_workflow=workflow):
                pass
            else:
                return _reject(pair, operation, exc.code, extra=(str(exc),), touched=touched)
    elif _needs_schema_knowledge(operation) and workflow is None:
        return _reject(
            pair,
            operation,
            "missing_touched_schema",
            extra=("schema_catalog:absent",),
            touched=touched,
        )



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
        # RRSYN2-4: unknown_port rejections retain the ORIGINAL alias plus
        # its resolution outcome (node, offered slot, valid slots, evidence
        # source) so the rejection is diagnosable from evidence alone and
        # admission/replay can never disagree silently about a rendered
        # endpoint.
        extra: tuple[str, ...] = (
            exc.message,
            "resolver:canonical_renderer_output",
        )
        for ref in _offered_endpoint_refs(operation):
            extra = (*extra, f"offered:{ref}")
        if exc.code in ("unknown_schema", "unknown_port", "unknown_field", "wrong_channel", "unknown_target"):
            # Allow only when touching provisional/unknown node (touched-only)
            if _is_provisional_touched(operation, workflow, pair.schema if pair.schema is not None else schema_catalog):
                pass
            else:
                return _reject(pair, operation, exc.code, extra=extra, touched=touched)
        else:
            return _reject(pair, operation, exc.code, extra=extra, touched=touched)
    return AdmissionAllowed(touched_scope=touched)




def _is_set_node_field_operation(operation: Any) -> bool:
    if getattr(operation, "op", None) == "set_node_field":
        return True
    if isinstance(operation, Mapping) and operation.get("op") == "set_node_field":
        return True
    return False


def admit_operations(
    snapshot: Any,
    operations: Sequence[Any],
    *,
    working_workflow: Any = None,
) -> AdmissionResult:
    """Admit a batch atomically. One rejection rejects the whole batch.

    Already-set ``set_node_field`` ops (same value) are pruned rather than
    ``no_op``-ing the whole batch. A batch that is *only* already-set writes
    still fails closed as ``no_op``.
    """

    pair = _freeze_snapshot_pair(snapshot)
    workflow = working_workflow
    if workflow is None and pair.workflow is not None:
        workflow = pair.workflow.workflow
    from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy, apply_edit_cow

    simulated = _cow_workflow_copy(workflow) if workflow is not None else None
    last_allowed: AdmissionAllowed | None = None
    kept = 0
    for operation in operations:
        result = admit_operation(pair, operation, working_workflow=simulated)
        if isinstance(result, AdmissionRejected):
            if result.typed_reason == "no_op" and _is_set_node_field_operation(operation):
                continue
            return result
        last_allowed = result
        kept += 1
        mapping = _operation_mapping(operation)
        if simulated is None or mapping.get("op") in LAYOUT_OPERATION_NAMES:
            continue
        parsed = operation if hasattr(operation, "op") and not isinstance(operation, Mapping) else parse_edit_op(mapping)
        try:
            simulated = apply_edit_cow(
                simulated, parsed, schema_provider=_schema_provider_for(pair)
            )
        except Exception as exc:
            _LOGGER.debug("admit_operations simulation apply failed: %s", exc)
            # Simulation failure is still a typed rejection of the batch.
            return _reject(pair, mapping, "apply_failed")
    if last_allowed is None:
        if operations and kept == 0:
            mapping = _operation_mapping(operations[0])
            return _reject(pair, mapping, "no_op")
        return AdmissionAllowed()
    return last_allowed


def rejected_ops_are_invisible(result: AdmissionResult) -> bool:
    """True only when a rejected op is excluded from accepted/visible surfaces.

    Allowed results are not invisible. Rejected results are invisible: they
    must not enter an accepted delta, landed_ops, Apply ok=True, lint
    surviving, preview evidence, or durable session apply.
    """

    return isinstance(result, AdmissionRejected)



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
