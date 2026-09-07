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

from vibecomfy.ingest.snapshot import (
    SnapshotAuthorityError,
    WorkflowSnapshot,
    compare_snapshot_authority,
    snapshot_of,
)
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
    SchemaSnapshotIdentity,
    SchemaSnapshotError,
    SCHEMA_SNAPSHOT_VERSION,
    require_known_touched_schema,
    schema_snapshot_from_payload,
    schema_snapshot_to_payload,
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


def _is_readonly_source_missing(
    operation: dict,
    pair,
    schema_catalog,
) -> bool:
    """True when upsert_link's missing schema is source-only (read-only edge).

    S3 Liberating Structure: a wire that reads from a schema-less source
    but writes to a schema-known target should not be blocked by
    missing_touched_schema — the read side is schema-opaque. Only the
    write target needs validation. This keeps valid add_node work from
    being wiped by a best-effort emit gap elsewhere.
    """ 
    if str(operation.get("op") or "") != "upsert_link":
        return False
    try:
        from vibecomfy.schema.types import _snapshot_node_class_map, _snapshot_known_and_missing
    except ImportError:
        return False
    catalog = schema_catalog
    if catalog is None:
        catalog = pair.schema
    if catalog is None:
        return False
    try:
        known, missing = _snapshot_known_and_missing(catalog)
    except Exception:
        return False
    node_map = _snapshot_node_class_map(catalog)
    def _uid_from_ref(ref):
        if isinstance(ref, dict):
            for k in ("uid", "id", "node_id"):
                v = ref.get(k)
                if v is not None and str(v):
                    return str(v)
        if isinstance(ref, (list, tuple)) and len(ref) >= 2 and ref[1]:
            return str(ref[1])
        if isinstance(ref, (list, tuple)) and len(ref) >= 1 and ref[0]:
            return str(ref[0])
        # Also handle LinkSourceRef/LinkTargetRef objects
        if hasattr(ref, "uid"):
            try:
                v = getattr(ref, "uid")
                if v is not None and str(v):
                    return str(v)
            except Exception:
                pass
        return None
    source_ref = operation.get("source") or operation.get("from")
    target_ref = operation.get("target") or operation.get("to")
    source_uid = _uid_from_ref(source_ref)
    target_uid = _uid_from_ref(target_ref)
    source_class = node_map.get(str(source_uid)) if source_uid else None
    target_class = node_map.get(str(target_uid)) if target_uid else None
    if (source_class is None or target_class is None) and pair.workflow is not None:
        try:
            wf = pair.workflow.workflow if hasattr(pair.workflow, "workflow") else pair.workflow
            nodes = getattr(wf, "nodes", {}) or {}
            for nid, node in nodes.items():
                uid = str(getattr(node, "uid", "") or "")
                ctype = str(getattr(node, "class_type", "") or "")
                if source_uid and uid == str(source_uid) and source_class is None:
                    source_class = ctype
                if target_uid and uid == str(target_uid) and target_class is None:
                    target_class = ctype
        except Exception:
            pass
    if source_class is None or target_class is None:
        return False
    source_known = source_class in known and source_class not in missing
    target_known = target_class in known and target_class not in missing
    return (not source_known) and target_known


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
    def checked_schema(value: Any, *, label: str) -> SchemaSnapshot | None:
        if value is None:
            return None
        if isinstance(value, (SchemaSnapshot, Mapping)):
            parsed, _payload = _validated_schema_argument(value, label=label)
            # Preserve identity for a retained typed witness; payloads are
            # parsed only after their original representation is checked.
            return value if isinstance(value, SchemaSnapshot) else parsed
        raise SchemaSnapshotError(
            f"{label} must be a SchemaSnapshot or complete payload",
            code="malformed_schema_snapshot",
        )

    if isinstance(snapshot, AdmissionSnapshot):
        schema = checked_schema(snapshot.schema, label="admission snapshot schema")
        if schema is snapshot.schema:
            return snapshot
        return AdmissionSnapshot(
            workflow=snapshot.workflow,
            schema=schema,
            schema_provider=snapshot.schema_provider,
        )
    if isinstance(snapshot, SchemaSnapshot):
        checked_schema(snapshot, label="schema snapshot")
        return AdmissionSnapshot(schema=snapshot)
    if isinstance(snapshot, WorkflowSnapshot):
        return AdmissionSnapshot(workflow=snapshot)
    if isinstance(snapshot, tuple) and len(snapshot) == 2:
        workflow, schema = snapshot
        return AdmissionSnapshot(
            workflow=workflow if isinstance(workflow, WorkflowSnapshot) else None,
            schema=checked_schema(schema, label="tuple schema snapshot"),
        )
    if isinstance(snapshot, Mapping):
        workflow = snapshot.get("workflow") or snapshot.get("workflow_snapshot")
        if "schema" in snapshot:
            raw_schema = snapshot["schema"]
        elif "schema_snapshot" in snapshot:
            raw_schema = snapshot["schema_snapshot"]
        else:
            raw_schema = None
        provider = snapshot.get("schema_provider")
        return AdmissionSnapshot(
            workflow=workflow if isinstance(workflow, WorkflowSnapshot) else None,
            schema=checked_schema(raw_schema, label="mapping schema snapshot"),
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


def _schema_validation_error(label: str, detail: str) -> SchemaSnapshotError:
    return SchemaSnapshotError(
        f"{label} has malformed schema evidence: {detail}",
        code="malformed_schema_snapshot",
    )


def _validate_json_value(value: Any, *, path: str) -> None:
    """Validate JSON evidence without applying the schema parser's coercions."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise _schema_validation_error(path, "mapping keys must be non-empty strings")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    raise _schema_validation_error(path, f"unsupported value type {type(value).__name__}")


def _validate_schema_payload_structure(payload: Mapping[str, Any], *, label: str) -> None:
    """Check the persisted witness *before* schema_snapshot_from_payload().

    The schema parser intentionally ignores malformed entries and stringifies
    several fields.  Admission must therefore validate the submitted shape
    first, so malformed nested evidence cannot become a different valid
    snapshot through parser normalization.
    """
    required = {
        "contract_version", "identity", "content_digest", "precedence",
        "selected_source", "generation", "conflicts", "timestamp", "version",
        "schemas", "missing_classes", "input_order",
        "workflow_observation_authoritative", "ambient_lookup_forbidden",
    }
    allowed = required | {"node_classes"}
    keys = set(payload)
    if not required.issubset(keys) or not keys.issubset(allowed):
        raise _schema_validation_error(label, "incomplete or unknown top-level fields")
    if payload.get("contract_version") != SCHEMA_SNAPSHOT_VERSION:
        raise SchemaSnapshotError(
            f"{label} has unsupported schema snapshot version",
            code="unsupported_schema_snapshot",
        )
    identity = payload.get("identity")
    if not isinstance(identity, Mapping) or set(identity) != {
        "runtime_fingerprint", "cache_fingerprint", "request_fingerprint", "server_url",
    }:
        raise _schema_validation_error(label, "identity must contain its complete four-field shape")
    for field_name, value in identity.items():
        if value is not None and (not isinstance(value, str) or not value):
            raise _schema_validation_error(label, f"identity.{field_name} must be a string or null")
    if not isinstance(payload.get("content_digest"), str) or not payload["content_digest"]:
        raise _schema_validation_error(label, "content_digest must be a non-empty string")
    precedence = payload.get("precedence")
    if not isinstance(precedence, list) or any(
        not isinstance(item, str) or not item for item in precedence
    ):
        raise _schema_validation_error(label, "precedence must be a list of non-empty strings")
    if not isinstance(payload.get("selected_source"), str):
        raise _schema_validation_error(label, "selected_source must be a string")
    generation = payload.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise _schema_validation_error(label, "generation must be a non-negative integer")
    conflicts = payload.get("conflicts")
    if not isinstance(conflicts, list) or any(
        not isinstance(item, str) or not item for item in conflicts
    ):
        raise _schema_validation_error(label, "conflicts must be a list of non-empty strings")
    timestamp = payload.get("timestamp")
    if timestamp is not None and (not isinstance(timestamp, str) or not timestamp):
        raise _schema_validation_error(label, "timestamp must be a string or null")
    if payload.get("version") != SCHEMA_SNAPSHOT_VERSION:
        raise _schema_validation_error(label, "version must match the snapshot contract")
    if payload.get("workflow_observation_authoritative") is not False:
        raise SchemaSnapshotError(
            f"{label} cannot use workflow observation as authority",
            code="workflow_observation_not_authoritative",
        )
    if payload.get("ambient_lookup_forbidden") is not True:
        raise SchemaSnapshotError(
            f"{label} must forbid ambient lookup",
            code="ambient_lookup_forbidden",
        )

    schemas = payload.get("schemas")
    if not isinstance(schemas, Mapping):
        raise _schema_validation_error(label, "schemas must be a mapping")
    for class_type, raw in schemas.items():
        path = f"{label}.schemas[{class_type!r}]"
        if not isinstance(class_type, str) or not class_type or not isinstance(raw, Mapping):
            raise _schema_validation_error(path, "class keys and values must be well-formed")
        if set(raw) != {
            "class_type", "pack", "inputs", "input_order", "outputs",
            "widget_input_order", "provenance",
        }:
            raise _schema_validation_error(path, "nested schema has incomplete or unknown fields")
        if raw.get("class_type") != class_type:
            raise _schema_validation_error(path, "class_type does not match its schema key")
        if raw.get("pack") is not None and not isinstance(raw.get("pack"), str):
            raise _schema_validation_error(path, "pack must be a string or null")
        inputs = raw.get("inputs")
        if not isinstance(inputs, Mapping):
            raise _schema_validation_error(path, "inputs must be a mapping")
        for input_name, spec in inputs.items():
            spec_path = f"{path}.inputs[{input_name!r}]"
            if not isinstance(input_name, str) or not isinstance(spec, Mapping):
                raise _schema_validation_error(spec_path, "input names/specs are malformed")
            if set(spec) != {
                "type", "required", "default", "choices", "min", "max", "unresolved_choices",
                "asset_kind",
            }:
                raise _schema_validation_error(spec_path, "input spec has incomplete or unknown fields")
            if spec.get("type") is not None and not isinstance(spec.get("type"), str):
                raise _schema_validation_error(spec_path, "input type must be a string or null")
            if not isinstance(spec.get("required"), bool):
                raise _schema_validation_error(spec_path, "required must be boolean")
            choices = spec.get("choices")
            if choices is not None and (
                not isinstance(choices, list) or any(not isinstance(item, (str, int, float, bool, type(None))) for item in choices)
            ):
                raise _schema_validation_error(spec_path, "choices must be a JSON list or null")
            for bound in ("min", "max"):
                value = spec.get(bound)
                if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                    raise _schema_validation_error(spec_path, f"{bound} must be numeric or null")
            if not isinstance(spec.get("unresolved_choices"), bool):
                raise _schema_validation_error(spec_path, "unresolved_choices must be boolean")
            asset_kind = spec.get("asset_kind")
            if asset_kind is not None and asset_kind != "image":
                raise _schema_validation_error(
                    spec_path,
                    "asset_kind must be null or the canonical 'image' claim",
                )
            _validate_json_value(spec.get("default"), path=f"{spec_path}.default")
        for field_name in ("input_order", "widget_input_order"):
            order = raw.get(field_name)
            if not isinstance(order, list) or any(
                not isinstance(item, str) and not (field_name == "widget_input_order" and item is None)
                for item in order
            ):
                raise _schema_validation_error(path, f"{field_name} has malformed order evidence")
        outputs = raw.get("outputs")
        if not isinstance(outputs, list):
            raise _schema_validation_error(path, "outputs must be a list")
        for output in outputs:
            if not isinstance(output, Mapping) or set(output) != {"type", "name"}:
                raise _schema_validation_error(path, "output entries must contain type and name")
            if output.get("type") is not None and not isinstance(output.get("type"), str):
                raise _schema_validation_error(path, "output type must be a string or null")
            if output.get("name") is not None and not isinstance(output.get("name"), str):
                raise _schema_validation_error(path, "output name must be a string or null")
        provenance = raw.get("provenance")
        if not isinstance(provenance, Mapping) or set(provenance) != {
            "source_provider", "source_path", "source_cache_path", "source_server_url",
            "source_package", "source_version", "source_hash", "confidence",
            "conflicts", "ignored_evidence",
        }:
            raise _schema_validation_error(path, "provenance has incomplete or unknown fields")
        for field_name in (
            "source_provider", "source_path", "source_cache_path", "source_server_url",
            "source_package", "source_version", "source_hash",
        ):
            value = provenance.get(field_name)
            if value is not None and not isinstance(value, str):
                raise _schema_validation_error(path, f"provenance.{field_name} must be a string or null")
        confidence = provenance.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise _schema_validation_error(path, "provenance.confidence must be numeric")
        for field_name in ("conflicts", "ignored_evidence"):
            value = provenance.get(field_name)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise _schema_validation_error(path, f"provenance.{field_name} must be a string list")

    missing = payload.get("missing_classes")
    if not isinstance(missing, list) or any(not isinstance(item, str) or not item for item in missing):
        raise _schema_validation_error(label, "missing_classes must be a list of non-empty strings")
    input_order = payload.get("input_order")
    if not isinstance(input_order, Mapping):
        raise _schema_validation_error(label, "input_order must be a mapping")
    for class_type, names in input_order.items():
        if not isinstance(class_type, str) or not class_type or not isinstance(names, list) or any(
            not isinstance(name, str) for name in names
        ):
            raise _schema_validation_error(label, "input_order contains malformed class/order evidence")
    if "node_classes" in payload:
        node_classes = payload.get("node_classes")
        if not isinstance(node_classes, Mapping) or any(
            not isinstance(uid, str) or not uid or not isinstance(class_type, str) or not class_type
            for uid, class_type in node_classes.items()
        ):
            raise _schema_validation_error(label, "node_classes must map non-empty strings to non-empty strings")


def _validate_snapshot_object(snapshot: SchemaSnapshot, *, label: str) -> None:
    """Check typed witness fields before canonical serialization."""
    identity = snapshot.identity
    for field_name in ("runtime_fingerprint", "cache_fingerprint", "request_fingerprint", "server_url"):
        value = getattr(identity, field_name, None)
        if value is not None and (not isinstance(value, str) or not value):
            raise _schema_validation_error(label, f"identity.{field_name} must be a string or null")
    if not isinstance(snapshot.precedence, Sequence) or isinstance(snapshot.precedence, (str, bytes)) or any(
        not isinstance(item, str) or not item for item in snapshot.precedence
    ):
        raise _schema_validation_error(label, "precedence must be a string sequence")
    if not isinstance(snapshot.conflicts, Sequence) or isinstance(snapshot.conflicts, (str, bytes)) or any(
        not isinstance(item, str) or not item for item in snapshot.conflicts
    ):
        raise _schema_validation_error(label, "conflicts must be a string sequence")
    if not isinstance(snapshot.missing_classes, Sequence) or isinstance(snapshot.missing_classes, (str, bytes)) or any(
        not isinstance(item, str) or not item for item in snapshot.missing_classes
    ):
        raise _schema_validation_error(label, "missing_classes must be a string sequence")
    if not isinstance(snapshot.input_order, Mapping) or any(
        not isinstance(class_type, str) or not class_type or not isinstance(names, Sequence)
        or isinstance(names, (str, bytes)) or any(not isinstance(name, str) for name in names)
        for class_type, names in snapshot.input_order.items()
    ):
        raise _schema_validation_error(label, "input_order has malformed original evidence")
    if not isinstance(snapshot.node_classes, Mapping) or any(
        not isinstance(uid, str) or not uid or not isinstance(class_type, str) or not class_type
        for uid, class_type in snapshot.node_classes.items()
    ):
        raise _schema_validation_error(label, "node_classes has malformed original evidence")


def _schema_snapshot_payload(snapshot: SchemaSnapshot, *, label: str) -> dict[str, Any]:
    """Validate one *original* schema witness before canonical serialization.

    ``schema_snapshot_to_payload`` deliberately emits the canonical authority
    flags.  That is useful for persistence, but it must not be the first
    validation step here: a forged dataclass with ``ambient_lookup_forbidden``
    cleared would otherwise be normalized back into an apparently valid
    witness.  Keep this check local to admission so every explicit-schema
    consumer gets the same custody contract.
    """
    if not isinstance(snapshot, SchemaSnapshot):
        raise SchemaSnapshotError(
            f"{label} must be a SchemaSnapshot",
            code="malformed_schema_snapshot",
        )
    if snapshot.version != SCHEMA_SNAPSHOT_VERSION:
        raise SchemaSnapshotError(
            f"{label} has unsupported schema snapshot version",
            code="unsupported_schema_snapshot",
        )
    if not isinstance(snapshot.generation, int) or isinstance(snapshot.generation, bool) or snapshot.generation < 0:
        raise SchemaSnapshotError(
            f"{label} has invalid schema snapshot generation",
            code="malformed_schema_snapshot",
        )
    if snapshot.ambient_lookup_forbidden is not True:
        raise SchemaSnapshotError(
            f"{label} must forbid ambient lookup",
            code="ambient_lookup_forbidden",
        )
    if snapshot.workflow_observation_authoritative is not False:
        raise SchemaSnapshotError(
            f"{label} cannot use workflow observation as authority",
            code="workflow_observation_not_authoritative",
        )
    if not isinstance(snapshot.content_digest, str) or not snapshot.content_digest:
        raise SchemaSnapshotError(
            f"{label} is missing a content digest",
            code="malformed_schema_snapshot",
        )
    if not isinstance(snapshot.identity, SchemaSnapshotIdentity):
        raise SchemaSnapshotError(
            f"{label} has malformed identity",
            code="malformed_schema_snapshot",
        )
    _validate_snapshot_object(snapshot, label=label)
    payload = schema_snapshot_to_payload(snapshot)
    _validate_schema_payload_structure(payload, label=label)
    # Reparse solely to verify the digest and all canonical payload fields;
    # the returned object remains the caller-retained witness.
    try:
        parsed = schema_snapshot_from_payload(payload)
    except SchemaSnapshotError as exc:
        raise SchemaSnapshotError(
            f"{label} failed schema witness validation: {exc}",
            code=exc.code,
        ) from exc
    if schema_snapshot_to_payload(parsed) != payload:
        raise SchemaSnapshotError(
            f"{label} is not a complete canonical schema payload",
            code="malformed_schema_snapshot",
        )
    return payload


def _validated_schema_argument(value: SchemaSnapshot | Mapping[str, Any], *, label: str) -> tuple[SchemaSnapshot, dict[str, Any]]:
    """Validate a supplied schema in its original representation."""
    if isinstance(value, SchemaSnapshot):
        return value, _schema_snapshot_payload(value, label=label)
    if not isinstance(value, Mapping):
        raise SchemaSnapshotError(
            f"{label} must be a SchemaSnapshot or complete payload",
            code="malformed_schema_snapshot",
        )
    if value.get("ambient_lookup_forbidden") is not True:
        raise SchemaSnapshotError(
            f"{label} must forbid ambient lookup",
            code="ambient_lookup_forbidden",
        )
    if value.get("workflow_observation_authoritative") is not False:
        raise SchemaSnapshotError(
            f"{label} cannot use workflow observation as authority",
            code="workflow_observation_not_authoritative",
        )
    _validate_schema_payload_structure(value, label=label)
    try:
        parsed = schema_snapshot_from_payload(value)
    except SchemaSnapshotError:
        raise
    canonical = schema_snapshot_to_payload(parsed)
    if dict(value) != canonical:
        raise SchemaSnapshotError(
            f"{label} is not a complete canonical schema payload",
            code="malformed_schema_snapshot",
        )
    # ``parsed`` is only the validated representation of this submitted
    # payload; explicit admission still returns the independently retained
    # witness object below.
    return parsed, canonical


def _workflow_witness_payload(snapshot: WorkflowSnapshot) -> tuple[Any, ...]:
    """All ingress witness fields except the retained live workflow handle."""
    return (
        snapshot.source_representation,
        snapshot.source_digest,
        snapshot.semantic_hash_version,
        snapshot.semantic_digest,
        snapshot.layout,
        snapshot.raw_sidecar,
        snapshot.identity,
        snapshot.topology,
        snapshot.lineage,
        snapshot.field_snapshot,
        snapshot.shape,
    )


def _require_preview_workflow_witness(
    pre_workflow: Any,
    retained: AdmissionSnapshot,
) -> None:
    """Bind direct preview to the retained ingress WorkflowSnapshot."""
    retained_workflow = retained.workflow
    if not isinstance(retained_workflow, WorkflowSnapshot):
        raise SchemaSnapshotError(
            "direct preview requires retained WorkflowSnapshot authority",
            code="missing_workflow_authority",
        )
    if pre_workflow is retained_workflow.workflow:
        return
    supplied = snapshot_of(pre_workflow)
    if not isinstance(supplied, WorkflowSnapshot):
        raise SchemaSnapshotError(
            "direct preview pre_workflow lacks retained workflow witness",
            code="missing_workflow_authority",
        )
    try:
        compare_snapshot_authority(supplied, retained_workflow)
    except SnapshotAuthorityError as exc:
        raise SchemaSnapshotError(str(exc), code=exc.code) from exc
    if _workflow_witness_payload(supplied) != _workflow_witness_payload(retained_workflow):
        raise SchemaSnapshotError(
            "direct preview workflow witness lineage does not match retained authority",
            code="workflow_snapshot_lineage_mismatch",
        )


def admission_snapshot_for(
    workflow: Any = None,
    schema_provider: Any = None,
    *,
    schema_snapshot: SchemaSnapshot | Mapping[str, Any] | None = None,
    retained_authority: AdmissionSnapshot | None = None,
) -> AdmissionSnapshot:
    """Build a pair from retained ingest/schema authorities. Never mutates."""

    workflow_snapshot = workflow if isinstance(workflow, WorkflowSnapshot) else snapshot_of(workflow)
    schema = schema_snapshot
    if schema is not None:
        if not isinstance(retained_authority, AdmissionSnapshot):
            raise SchemaSnapshotError(
                "explicit schema admission requires an independently retained authority pair",
                code="missing_retained_authority",
            )
        retained_schema = retained_authority.schema
        if not isinstance(retained_schema, SchemaSnapshot):
            raise SchemaSnapshotError(
                "explicit schema admission requires a retained SchemaSnapshot",
                code="missing_retained_authority",
            )
        _supplied_schema, supplied_payload = _validated_schema_argument(
            schema,
            label="supplied schema",
        )
        retained_payload = _schema_snapshot_payload(retained_schema, label="retained schema")
        if supplied_payload != retained_payload:
            raise SchemaSnapshotError(
                "supplied schema does not match retained authority",
                code="schema_snapshot_lineage_mismatch",
            )
        # The pair's schema is deliberately the independently retained object,
        # even when the submitted payload was an equivalent serialized copy.
        schema = retained_schema
    if schema is None and schema_provider is not None:
        schema = _bind_schema_from_provider(schema_provider)
    if isinstance(schema, SchemaSnapshot):
        # Provider-only ingress validates its own frozen witness.  On the
        # explicit-schema path the provider is advisory and intentionally not
        # inspected: the retained pair is the authority and must remain the
        # exact object supplied by ingress.
        _schema_snapshot_payload(schema, label="schema")
        if schema_snapshot is None:
            provider_snapshot = _bind_schema_from_provider(schema_provider)
            if provider_snapshot is not None:
                _schema_snapshot_payload(provider_snapshot, label="provider schema")
                if (
                    provider_snapshot.content_digest != schema.content_digest
                    or provider_snapshot.generation != schema.generation
                    or provider_snapshot.identity != schema.identity
                ):
                    raise SchemaSnapshotError(
                        "schema snapshot generation/witness does not match retained provider",
                        code="schema_snapshot_lineage_mismatch",
                    )
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


def _catalog_with_known_working_nodes(
    catalog: SchemaSnapshot | Mapping[str, Any] | None,
    workflow: Any,
    baseline_workflow: Any,
) -> SchemaSnapshot | Mapping[str, Any] | None:
    """Overlay sequentially-created identities without expanding authority.

    ``admit_operations`` simulates allowed operations in order. A later wire
    must therefore be able to resolve a node added earlier in that batch, but
    only when its class schema was already frozen at ingress. This local view
    leaves the retained snapshot and its digest untouched.
    """
    if catalog is None or workflow is None:
        return catalog
    from vibecomfy.schema.types import (
        _snapshot_known_and_missing,
        _snapshot_node_class_map,
    )

    known, missing = _snapshot_known_and_missing(catalog)
    node_classes = _snapshot_node_class_map(catalog)
    try:
        # The frozen node-class map is the authoritative baseline identity set.
        # ``pair.workflow`` is intentionally optional when callers supply a
        # schema snapshot plus an explicit working workflow, so do not require
        # a retained baseline IR merely to recognize same-batch additions.
        baseline_identities: set[str] = {str(identity) for identity in node_classes}
        if baseline_workflow is not None:
            for node_id, node in (getattr(baseline_workflow, "nodes", {}) or {}).items():
                baseline_identities.add(str(node_id))
                uid = str(getattr(node, "uid", "") or "")
                if uid:
                    baseline_identities.add(uid)
        nodes = getattr(workflow, "nodes", {}) or {}
        for node_id, node in nodes.items():
            class_type = str(getattr(node, "class_type", "") or "")
            if not class_type or class_type not in known or class_type in missing:
                continue
            uid = str(getattr(node, "uid", "") or "")
            if str(node_id) in baseline_identities or (uid and uid in baseline_identities):
                continue
            node_classes[str(node_id)] = class_type
            if uid:
                node_classes[uid] = class_type
    except Exception as exc:
        _LOGGER.debug("working node-class overlay failed: %s", exc)
        return catalog

    schemas = (
        catalog.schemas
        if isinstance(catalog, SchemaSnapshot)
        else catalog.get("schemas", {})
    )
    missing_classes = (
        list(catalog.missing_classes)
        if isinstance(catalog, SchemaSnapshot)
        else list(
            catalog.get("missing_classes")
            or catalog.get("missing_class_types")
            or ()
        )
    )
    return {
        "schemas": schemas,
        "missing_classes": missing_classes,
        "node_classes": node_classes,
    }


def _needs_schema_knowledge(operation: Mapping[str, Any]) -> bool:
    """True when a non-empty op requires retained admission authority."""

    op_name = str(operation.get("op") or "")
    if op_name in _SEMANTIC_OPERATION_NAMES or op_name in LAYOUT_OPERATION_NAMES:
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
    if not isinstance(payload, Mapping):
        raise SchemaSnapshotError(
            "persisted schema witness is missing",
            code="missing_schema_snapshot",
        )
    # Validate the original witness before any parser normalization or submit
    # graph reconstruction.  In particular, schema_snapshot_from_payload()
    # coerces flags, generations, and nested entries; none of those coerced
    # values may become authority for replay.
    schema, _canonical = _validated_schema_argument(payload, label="persisted schema witness")
    if workflow is None and isinstance(submit_graph, Mapping):
        try:
            from vibecomfy.ingest.normalize import from_ui

            frozen_provider = FrozenSchemaSnapshotProvider(schema)
            workflow = from_ui(
                dict(submit_graph),
                schema_provider=frozen_provider,
                use_comfy_converter=False,
            )
        except Exception as exc:
            # Replay remains fail-closed if the persisted submit graph cannot
            # be reconstructed. In particular, never fall back to ambient
            # object_info or a live provider here.
            _LOGGER.debug("submit graph reconstruction failed: %s", exc)
            workflow = None
    retained_workflow = snapshot_of(workflow)
    retained = AdmissionSnapshot(workflow=retained_workflow, schema=schema)
    return admission_snapshot_for(
        workflow,
        schema_snapshot=schema,
        retained_authority=retained,
    )

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

    Only a verified frozen SchemaSnapshot is authoritative.  A retained live
    provider is deliberately not a replay schema source.
    """
    if pair.schema is not None:
        return FrozenSchemaSnapshotProvider(pair.schema)
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


def check_touched_schema_evidence(
    pair: AdmissionSnapshot,
    operation: Any,
    *,
    working_workflow: Any = None,
) -> TouchedScope | AdmissionRejected:
    """Check the operation's touched closure against retained evidence.

    This is deliberately the only touched-schema check.  It may overlay
    identities created earlier in the same transaction, but it never queries
    a live provider or broadens the frozen catalog.
    """
    operation_mapping = _operation_mapping(operation)
    workflow = working_workflow
    if workflow is None and pair.workflow is not None:
        workflow = pair.workflow.workflow
    catalog = _schema_catalog_for(pair, pair.schema)
    operation_catalog = _catalog_with_known_working_nodes(
        catalog,
        workflow,
        pair.workflow.workflow if pair.workflow is not None else None,
    )
    classes = touched_schema_classes(operation, operation_catalog) if operation_catalog is not None else ()
    if not classes:
        class_type = operation_mapping.get("class_type")
        classes = (str(class_type),) if isinstance(class_type, str) and class_type else ()
    touched = TouchedScope(
        identities=_touched_identities(operation_mapping),
        class_types=tuple(classes),
    )
    if operation_catalog is not None:
        try:
            require_known_touched_schema(operation, operation_catalog)
        except SchemaSnapshotError as exc:
            if exc.code == "missing_touched_schema" and _is_readonly_source_missing(
                operation, pair, operation_catalog
            ):
                return touched
            if _add_node_provisional_allows(
                operation_mapping,
                operation_catalog,
                working_workflow=workflow,
            ):
                return touched
            return _reject(pair, operation_mapping, exc.code, extra=(str(exc),), touched=touched)
    elif _needs_schema_knowledge(operation_mapping):
        return _reject(
            pair,
            operation_mapping,
            "missing_touched_schema",
            extra=("schema_catalog:absent",),
            touched=touched,
        )
    return touched


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
    workflow = working_workflow
    if workflow is None and pair.workflow is not None:
        workflow = pair.workflow.workflow
    checked = check_touched_schema_evidence(
        pair, operation, working_workflow=workflow
    )
    if isinstance(checked, AdmissionRejected):
        return checked
    touched = checked

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
            if _is_provisional_touched(operation, workflow, pair.schema):
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
