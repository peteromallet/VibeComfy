"""Canonical candidate-transaction aggregate and persisted schema witness.

The aggregate is the authority boundary shared by candidate publication,
prepare, browser mutation, finalization, rollback, and rehydration.  Mutable
session indexes are projections; the immutable candidate artifact plus its
append-only lifecycle events are the durable source of truth.
"""

from __future__ import annotations

from vibecomfy.ingest.normalize import door_get_nodes
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from vibecomfy.schema import (
    SCHEMA_SNAPSHOT_VERSION,
    FrozenSchemaSnapshotProvider,
    InputSpec,
    NodeSchema,
    OutputSpec,
    SchemaSnapshot,
    capture_schema_snapshot,
    schema_for,
    schema_payload_from_node_schema,
    schema_snapshot_to_payload,
    touched_schema_classes,
)
from .layout_operation_v1 import (
    compute_layout_operation_digest as _compute_layout_operation_digest,
    normalize_layout_operation_v1 as _normalize_layout_operation_v1,
)
from .mutation_materialization_v1 import (
    compute_mutation_materialization_digest as _compute_mutation_materialization_digest,
    normalize_mutation_materialization_v1 as _normalize_mutation_materialization_v1,
)
from .projection_registry_v1 import (
    CANDIDATE_TRANSACTION_V2,
    CANDIDATE_AUTHORITY_V1,
    PREPARED_AUTHORITY_V1,
    RESTORATION_COMPENSATION_CONTRACT_V1,
    RESTORATION_COMPENSATION_WIRE_VERSION,
    canonical_json_bytes_v1 as _registry_canonical_json_bytes,
    canonicalize_contract_numeric as _registry_canonicalize_contract_numeric,
    classify_legacy_migration_v1,
    projection_reference_v1,
    validate_candidate_transaction_v2,
    validate_prepared_authority_v1,
    workflow_identity_v1,
)
from .projection_registry_v1 import _hash as _registry_hash

# New production records are v2.  v1 is handled only by the explicit
# historical migration classifier in session/browser rehydration.
CANDIDATE_TRANSACTION_CONTRACT_VERSION = CANDIDATE_TRANSACTION_V2
LAYOUT_VERIFICATION_CONTRACT_VERSION = "layout_verification_v1"
LAYOUT_VERIFICATION_PROJECTION = "browser_layout_v1"
SCHEMA_WITNESS_CONTRACT_VERSION = "candidate_schema_witness_v1"
AUTHORITY_RECEIPT_CONTRACT_VERSION = "authority_receipt_v2"
AUTHORITY_RECEIPT_DELTA_SCHEMA = "2.0.0"
CANDIDATE_TRANSACTION_FILENAME = "candidate_transaction.json"

CandidateTransactionState = Literal[
    "candidate_ready",
    "prepared",
    "canvas_verified",
    "finalized",
    "discarded",
    "rollback_complete",
    "recoverable_error",
    "superseded",
]

CANONICAL_TRANSACTION_STATES: frozenset[str] = frozenset(
    {
        "candidate_ready",
        "prepared",
        "canvas_verified",
        "finalized",
        "discarded",
        "rollback_complete",
        "recoverable_error",
        "superseded",
    }
)
TERMINAL_TRANSACTION_STATES: frozenset[str] = frozenset(
    {"finalized", "discarded", "rollback_complete", "superseded"}
)
RECOVERABLE_TRANSACTION_STATES: frozenset[str] = frozenset(
    {"candidate_ready", "prepared", "canvas_verified", "recoverable_error"}
)

_LEGACY_STATE_ADAPTER: Mapping[str, str] = {
    "candidate": "candidate_ready",
    "review_bound": "candidate_ready",
    "apply_prepared": "prepared",
    "rollback_prepared": "prepared",
    "accepted": "finalized",
    "rejected": "discarded",
    "rolled_back": "rollback_complete",
    "cancelled": "superseded",
    "unknown": "superseded",
}


def canonical_json_bytes(value: Any) -> bytes:
    """Compatibility facade over the sole Python canonical-JSON owner."""
    return _registry_canonical_json_bytes(value, ensure_ascii=False)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_transaction_state(value: Any) -> str | None:
    """Return the canonical state, adapting read-only historical values."""
    if not isinstance(value, str):
        return None
    if value in CANONICAL_TRANSACTION_STATES:
        return value
    return _LEGACY_STATE_ADAPTER.get(value)


def available_actions_for_state(
    state: Any,
    *,
    resume_state: Any = None,
) -> tuple[str, ...]:
    canonical = canonical_transaction_state(state)
    if canonical == "recoverable_error":
        canonical = canonical_transaction_state(resume_state)
    if canonical == "candidate_ready":
        return ("apply", "reject")
    if canonical == "prepared":
        # A reload cannot prove whether an unrecorded local canvas mutation
        # happened.  Recovery is rollback-only until fresh verification exists.
        return ("rollback",)
    if canonical == "canvas_verified":
        return ("finalize", "rollback")
    return ()


def _graph_class_types(graph: Mapping[str, Any] | None) -> set[str]:
    result: set[str] = set()

    def visit(scope: Mapping[str, Any]) -> None:
        nodes = door_get_nodes(scope)
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                class_type = node.get("type") or node.get("class_type")
                if isinstance(class_type, str) and class_type:
                    result.add(class_type)
        definitions = scope.get("definitions")
        if isinstance(definitions, Mapping):
            for definition in definitions.values():
                if isinstance(definition, Mapping):
                    visit(definition)
        prompt = scope.get("prompt")
        if isinstance(prompt, Mapping):
            visit(prompt)
        if not isinstance(nodes, list):
            # API-format graphs (including the standard ``{prompt: api}``
            # wrapper) are keyed directly by node id.
            for node in scope.values():
                if not isinstance(node, Mapping):
                    continue
                class_type = node.get("type") or node.get("class_type")
                if isinstance(class_type, str) and class_type:
                    result.add(class_type)

    if isinstance(graph, Mapping):
        visit(graph)
    return result


def _delta_class_types(delta_envelope: Mapping[str, Any] | None) -> set[str]:
    result: set[str] = set()
    ops = delta_envelope.get("ops") if isinstance(delta_envelope, Mapping) else None
    for op in ops if isinstance(ops, list) else ():
        if not isinstance(op, Mapping):
            continue
        class_type = op.get("class_type")
        if isinstance(class_type, str) and class_type:
            result.add(class_type)
    return result


def _graph_node_class_by_identity(
    graph: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Index serialized nodes by every stable identity available on the wire."""
    result: dict[str, str] = {}

    def add(node: Mapping[str, Any], *, fallback_id: Any = None) -> None:
        class_type = node.get("type") or node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            return
        identities: list[Any] = [fallback_id, node.get("id"), node.get("uid")]
        properties = node.get("properties")
        if isinstance(properties, Mapping):
            identities.append(properties.get("vibecomfy_uid"))
        for identity in identities:
            if identity is not None and str(identity):
                result[str(identity)] = class_type

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            nodes = door_get_nodes(value)
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, Mapping):
                        add(node)
            elif nodes is None:
                # API-format root/definition: node id -> {class_type, inputs}.
                for node_id, node in value.items():
                    if isinstance(node, Mapping) and isinstance(
                        node.get("type") or node.get("class_type"), str
                    ):
                        add(node, fallback_id=node_id)
            definitions = value.get("definitions")
            if isinstance(definitions, (Mapping, list)):
                visit(definitions)
            subgraphs = value.get("subgraphs")
            if isinstance(subgraphs, (Mapping, list)):
                visit(subgraphs)
            prompt = value.get("prompt")
            if isinstance(prompt, Mapping):
                visit(prompt)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (Mapping, list)):
                    visit(item)

    if isinstance(graph, Mapping):
        visit(graph)
    return result


def _delta_touched_node_identities(
    delta_envelope: Mapping[str, Any] | None,
) -> set[str]:
    """Return node uids referenced by canonical delta and layout operations."""
    touched: set[str] = set()
    ops = delta_envelope.get("ops") if isinstance(delta_envelope, Mapping) else None
    for op in ops if isinstance(ops, list) else ():
        if not isinstance(op, Mapping):
            continue
        op_name = op.get("op")

        def add_ref(ref: Any) -> None:
            if (
                isinstance(ref, Sequence)
                and not isinstance(ref, (str, bytes))
                and len(ref) >= 2
                and ref[1] is not None
            ):
                touched.add(str(ref[1]))
            elif isinstance(ref, Mapping):
                for key in ("uid", "id", "node_id"):
                    value = ref.get(key)
                    if value is not None and str(value):
                        touched.add(str(value))
            elif isinstance(ref, (str, int)) and str(ref):
                touched.add(str(ref))

        if op_name in {"set_node_field", "set_mode", "remove_node"}:
            add_ref(op.get("target"))
        elif op_name == "upsert_link":
            add_ref(op.get("from"))
            add_ref(op.get("to"))
        elif op_name == "remove_link":
            add_ref(op.get("to"))
        elif op_name == "add_node":
            inputs = op.get("inputs")
            if isinstance(inputs, Mapping):
                for source in inputs.values():
                    add_ref(source)
            anchor = op.get("anchor")
            if isinstance(anchor, Mapping):
                add_ref(anchor.get("near"))
                between = anchor.get("between")
                if isinstance(between, Sequence) and not isinstance(between, (str, bytes)):
                    for ref in between:
                        add_ref(ref)
        elif op_name in {"set_node_geometry", "add_group", "set_group_geometry", "remove_group", "subgraph_interface"}:
            add_ref(op.get("uid"))
            add_ref(op.get("id"))
            add_ref(op.get("node_id"))
    return touched


def missing_touched_class_types(
    *,
    schema_witness: Mapping[str, Any],
    submit_graph: Mapping[str, Any] | None,
    candidate_payload: Mapping[str, Any] | None,
    delta_envelope: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Return touched classes for which replay has no frozen schema.

    Untouched unknown classes may remain in a graph because byte-preserving
    ingest/emit can carry them through.  A delta that addresses one of those
    classes cannot be authoritative without its schema, so it must fail before
    publication rather than falling back to positional widget semantics.
    """
    from vibecomfy.schema import require_known_touched_schema
    from vibecomfy.schema.types import SchemaSnapshotError

    raw_missing = schema_witness.get("missing_class_types")
    missing = {
        str(class_type)
        for class_type in raw_missing if isinstance(class_type, str) and class_type
    } if isinstance(raw_missing, list) else set()
    snapshot = schema_witness.get("schema_snapshot") if isinstance(schema_witness, Mapping) else None
    snapshot_missing = snapshot.get("missing_classes") if isinstance(snapshot, Mapping) else None
    if isinstance(snapshot_missing, list):
        missing.update(str(item) for item in snapshot_missing if isinstance(item, str) and item)
    raw_schemas = snapshot.get("schemas") if isinstance(snapshot, Mapping) else schema_witness.get("schemas")
    known = set(str(name) for name in raw_schemas) if isinstance(raw_schemas, Mapping) else set()

    by_identity = _graph_node_class_by_identity(submit_graph)
    by_identity.update(_graph_node_class_by_identity(candidate_payload))
    if isinstance(snapshot, Mapping):
        node_classes = snapshot.get("node_classes")
        if isinstance(node_classes, Mapping):
            for uid, class_type in node_classes.items():
                if str(uid) and isinstance(class_type, str) and class_type:
                    by_identity[str(uid)] = class_type

    catalog: dict[str, Any]
    if isinstance(snapshot, Mapping):
        catalog = dict(snapshot)
    else:
        catalog = dict(schema_witness)
        catalog.setdefault("missing_classes", list(missing))
    catalog["node_classes"] = by_identity

    unknown: set[str] = set()
    ops = delta_envelope.get("ops") if isinstance(delta_envelope, Mapping) else None
    from vibecomfy.porting.edit.admit import AdmissionRejected, admit_operation

    for op in ops if isinstance(ops, list) else ():
        if not isinstance(op, Mapping):
            continue
        admitted = admit_operation(catalog, op)
        if isinstance(admitted, AdmissionRejected) and admitted.typed_reason == "missing_touched_schema":
            try:
                require_known_touched_schema(op, catalog)
            except SchemaSnapshotError:
                unknown.update(touched_schema_classes(op, catalog))
                class_type = op.get("class_type")
                if isinstance(class_type, str) and class_type and (class_type in missing or class_type not in known):
                    unknown.add(class_type)
                for identity in _delta_touched_node_identities({"ops": [op]}):
                    resolved = by_identity.get(identity)
                    if resolved is None:
                        unknown.add(identity)
                    elif resolved in missing or resolved not in known:
                        unknown.add(resolved)
            continue
        try:
            require_known_touched_schema(op, catalog)
        except SchemaSnapshotError:
            unknown.update(touched_schema_classes(op, catalog))
            class_type = op.get("class_type")
            if isinstance(class_type, str) and class_type and (class_type in missing or class_type not in known):
                unknown.add(class_type)
            for identity in _delta_touched_node_identities({"ops": [op]}):
                resolved = by_identity.get(identity)
                if resolved is None:
                    unknown.add(identity)
                elif resolved in missing or resolved not in known:
                    unknown.add(resolved)
        else:
            for class_type in touched_schema_classes(op, catalog):
                if class_type in missing or class_type not in known:
                    unknown.add(class_type)
    return tuple(sorted(unknown))




def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return repr(value)[:512]


def _input_spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "type": getattr(spec, "type", None),
        "required": bool(getattr(spec, "required", False)),
        "default": _json_safe(getattr(spec, "default", None)),
        "choices": _json_safe(getattr(spec, "choices", None)),
        "min": getattr(spec, "min", None),
        "max": getattr(spec, "max", None),
    }


def _output_spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "type": getattr(spec, "type", None),
        "name": getattr(spec, "name", None),
    }


def _schema_payload(class_type: str, schema: Any) -> dict[str, Any]:
    return schema_payload_from_node_schema(class_type, schema)


def capture_ingress_schema_snapshot(
    *,
    schema_provider: Any,
    graph: Mapping[str, Any] | None = None,
) -> SchemaSnapshot:
    """Freeze the ingress-bound schema authority at the production ingest door.

    DEEP-AUDIT-FIX-1-REVISION 002: ``handle_agent_edit`` captures ONCE at
    allocation/ingest time and retains the result on the turn state (the
    Batch-3 "one retained ingest authority" pattern). The frozen surface is
    the ingest graph's classes plus every class the runtime provider can
    enumerate, each resolved through the LIVE provider — external
    custom-node completion happens here at the door per the revision-001
    fresh-capture rule and is never re-resolved at witness/receipt time.
    Classes the provider cannot resolve stay genuinely missing and fail
    closed in admission.
    """
    requested = set(_graph_class_types(graph))
    surface = None
    if schema_provider is not None:
        try:
            from vibecomfy.schema.provider import schemas_for

            surface = schemas_for(schema_provider)
        except Exception:  # noqa: BLE001 - surface enumeration must never break ingest
            surface = None
    if surface:
        requested.update(str(name) for name in surface)
    schemas: dict[str, Any] = {}
    missing: list[str] = []
    for class_type in sorted(requested):
        payload = None
        schema = schema_for(schema_provider, class_type)
        if schema is not None:
            try:
                payload = schema_payload_from_node_schema(class_type, schema)
            except Exception:  # noqa: BLE001 - an unusable schema reads as absence
                payload = None
        if payload is None:
            missing.append(class_type)
            continue
        schemas[class_type] = payload
    return capture_schema_snapshot(
        class_types=sorted(requested),
        request_snapshot={
            "contract_version": SCHEMA_SNAPSHOT_VERSION,
            "schemas": schemas,
            "missing_classes": missing,
        },
        node_classes=_graph_node_class_by_identity(graph),
    )


def build_schema_witness(
    *,
    schema_provider: Any,
    submit_graph: Mapping[str, Any] | None,
    candidate_payload: Mapping[str, Any] | None,
    delta_envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Freeze every schema that can affect replay of this candidate.

    The witness carries an ingress-bound SchemaSnapshot so replay reconstructs
    from the persisted snapshot and cannot perform a fresh ambient lookup.
    """
    class_types = (
        _graph_class_types(submit_graph)
        | _graph_class_types(candidate_payload)
        | _delta_class_types(delta_envelope)
    )
    request_snapshot = None
    if isinstance(schema_provider, FrozenSchemaSnapshotProvider):
        request_snapshot = schema_provider.snapshot
    elif isinstance(schema_provider, SchemaSnapshot):
        request_snapshot = schema_provider
    elif hasattr(schema_provider, "snapshot") and isinstance(getattr(schema_provider, "snapshot"), SchemaSnapshot):
        request_snapshot = schema_provider.snapshot

    if request_snapshot is not None:
        # DEEP-AUDIT-FIX-1-REVISION: the frozen ingress authority is never
        # ambient-healed here. One completion seam remains — a touched class
        # the RETAINED turn provider can still resolve (evidence-backed
        # provisional registry/workflow schema hydrated during the turn)
        # completes the frozen payload exactly as the ingest door would
        # have; everything else stays byte-frozen.
        base = (
            dict(request_snapshot)
            if isinstance(request_snapshot, Mapping)
            else schema_snapshot_to_payload(request_snapshot)
        )
        raw_frozen_schemas = base.get("schemas")
        if not isinstance(raw_frozen_schemas, Mapping):
            raw_frozen_schemas = {}
        frozen_schemas = {str(name) for name in raw_frozen_schemas}
        raw_frozen_missing = (
            base.get("missing_classes") or base.get("missing_class_types")
        )
        frozen_missing = {
            str(item) for item in raw_frozen_missing if isinstance(item, str)
        } if isinstance(raw_frozen_missing, list) else set()
        additions: dict[str, Any] = {}
        new_missing: list[str] = []
        for class_type in sorted(class_types):
            if class_type in frozen_schemas:
                continue
            schema = schema_for(schema_provider, class_type)
            payload = None
            if schema is not None:
                try:
                    payload = _schema_payload(class_type, schema)
                except Exception:  # noqa: BLE001 - unusable schema reads as absence
                    payload = None
            if payload is None:
                new_missing.append(class_type)
            else:
                additions[class_type] = payload
        if additions or new_missing:
            base["schemas"] = {**(raw_frozen_schemas or {}), **additions}
            base["missing_classes"] = sorted(
                (frozen_missing | set(new_missing)) - set(additions)
            )
            request_snapshot = base

    snapshot = capture_schema_snapshot(
        class_types=sorted(class_types),
        request_snapshot=request_snapshot,
        node_classes=_graph_node_class_by_identity(submit_graph)
        | _graph_node_class_by_identity(candidate_payload),
    )
    schemas: dict[str, Any] = dict(snapshot.schemas)
    missing: list[str] = list(snapshot.missing_classes)
    if request_snapshot is None:
        schemas = {}
        missing = []
        for class_type in sorted(class_types):
            schema = schema_for(schema_provider, class_type)
            if schema is None:
                missing.append(class_type)
                continue
            schemas[class_type] = _schema_payload(class_type, schema)
        snapshot = capture_schema_snapshot(
            class_types=sorted(class_types),
            request_snapshot={
                "contract_version": "schema-snapshot-v1",
                "schemas": schemas,
                "missing_classes": missing,
                "generation": snapshot.generation,
                "timestamp": snapshot.timestamp,
                "version": snapshot.version,
                "conflicts": list(snapshot.conflicts),
                "node_classes": dict(snapshot.node_classes),
            },
            node_classes=snapshot.node_classes,
        )
        schemas = dict(snapshot.schemas)
        missing = list(snapshot.missing_classes)
        for class_type in sorted(class_types):
            if class_type not in schemas and class_type not in missing:
                missing.append(class_type)
    snapshot_payload = schema_snapshot_to_payload(snapshot)
    body = {
        "contract_version": SCHEMA_WITNESS_CONTRACT_VERSION,
        "provider_mode": "none" if schema_provider is None else "frozen",
        "schemas": schemas,
        "missing_class_types": missing,
        "schema_snapshot": snapshot_payload,
    }
    return {**body, "witness_hash": content_hash({
        "contract_version": body["contract_version"],
        "provider_mode": body["provider_mode"],
        "schemas": body["schemas"],
        "missing_class_types": body["missing_class_types"],
        "schema_snapshot": body["schema_snapshot"],
    })}


def validate_schema_witness(witness: Any) -> tuple[bool, str | None]:
    if not isinstance(witness, Mapping):
        return False, "missing_schema_witness"
    if witness.get("contract_version") != SCHEMA_WITNESS_CONTRACT_VERSION:
        return False, "unsupported_schema_witness"
    snapshot_payload = witness.get("schema_snapshot")
    body: dict[str, Any] = {
        "contract_version": witness.get("contract_version"),
        "provider_mode": witness.get("provider_mode"),
        "schemas": witness.get("schemas"),
        "missing_class_types": witness.get("missing_class_types"),
    }
    if snapshot_payload is not None:
        body["schema_snapshot"] = snapshot_payload
    if not isinstance(body["schemas"], Mapping) or not isinstance(
        body["missing_class_types"], list
    ):
        return False, "malformed_schema_witness"
    if body["provider_mode"] not in {"none", "frozen"}:
        return False, "malformed_schema_provider_mode"
    if witness.get("witness_hash") != content_hash(body):
        if snapshot_payload is not None:
            return False, "invalid_schema_snapshot"
        return False, "schema_witness_hash_mismatch"
    if snapshot_payload is not None:
        if not isinstance(snapshot_payload, Mapping):
            return False, "malformed_schema_snapshot"
        try:
            frozen = FrozenSchemaSnapshotProvider(snapshot_payload)
        except Exception:
            return False, "invalid_schema_snapshot"
        snapshot_schemas = set(str(name) for name in frozen.snapshot.schemas)
        snapshot_missing = set(frozen.snapshot.missing_classes)
        witness_schemas = set(str(name) for name in body["schemas"])
        witness_missing = {
            str(item) for item in body["missing_class_types"] if isinstance(item, str)
        }
        if snapshot_schemas != witness_schemas or snapshot_missing != witness_missing:
            return False, "invalid_schema_snapshot"
    return True, None


class FrozenSchemaProvider:
    """Schema provider reconstructed exclusively from a persisted witness.

    Replay reconstructs from the hashed per-class payload. A bound
    ``schema_snapshot`` must agree with that payload; historic witnesses
    without a snapshot stay on the per-class path. Ambient lookup is forbidden.
    """

    def __init__(self, witness: Mapping[str, Any]) -> None:
        ok, error = validate_schema_witness(witness)
        if not ok:
            raise ValueError(error or "invalid_schema_witness")
        from vibecomfy.schema.types import node_schema_from_payload

        self._schemas = {}
        raw_schemas = witness.get("schemas")
        for class_type, raw in (
            raw_schemas.items() if isinstance(raw_schemas, Mapping) else ()
        ):
            if not isinstance(class_type, str) or not isinstance(raw, Mapping):
                continue
            self._schemas[class_type] = node_schema_from_payload(class_type, raw)
        snapshot_payload = witness.get("schema_snapshot")
        if isinstance(snapshot_payload, Mapping):
            frozen = FrozenSchemaSnapshotProvider(snapshot_payload)
            self._snapshot = frozen.snapshot
            self._frozen_snapshot_provider = frozen
        else:
            self._snapshot = None
            self._frozen_snapshot_provider = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return dict(self._schemas)

    def lookup_ambient(self, *args: Any, **kwargs: Any) -> None:
        if self._frozen_snapshot_provider is not None:
            self._frozen_snapshot_provider.lookup_ambient(*args, **kwargs)
        raise RuntimeError("replay cannot perform a fresh ambient schema lookup")


def schema_provider_from_witness(witness: Mapping[str, Any]) -> Any:
    """Reconstruct the exact provider mode used when the plan was authored."""
    ok, error = validate_schema_witness(witness)
    if not ok:
        raise ValueError(error or "invalid_schema_witness")
    if witness.get("provider_mode") == "none":
        return None
    return FrozenSchemaProvider(witness)



def schema_provenance_summary(witness: Mapping[str, Any]) -> dict[str, Any]:
    schemas = witness.get("schemas")
    sources: dict[str, str] = {}
    if isinstance(schemas, Mapping):
        for class_type, raw in schemas.items():
            provenance = raw.get("provenance") if isinstance(raw, Mapping) else None
            source = provenance.get("source_provider") if isinstance(provenance, Mapping) else None
            sources[str(class_type)] = str(source or "unknown")
    return {
        "contract_version": witness.get("contract_version"),
        "provider_mode": witness.get("provider_mode"),
        "witness_hash": witness.get("witness_hash"),
        "class_count": len(sources),
        "missing_class_types": list(witness.get("missing_class_types", []))[:64]
        if isinstance(witness.get("missing_class_types"), list)
        else [],
        "sources": sources,
    }


def build_candidate_transaction(
    *,
    workflow_id: str,
    session_id: str,
    turn_id: str,
    plan_hash: str,
    submit_graph: Mapping[str, Any],
    candidate_graph: Mapping[str, Any],
    accepted_batch: Sequence[Mapping[str, Any]] | None = None,
    delta_hash: str | None = None,
    submit_graph_hash: str | None,
    submit_structural_graph_hash: str | None,
    candidate_graph_hash: str,
    candidate_structural_graph_hash: str,
    authority_receipt_hash: str,
    schema_witness: Mapping[str, Any],
    replay_ok: bool,
    candidate_matches: bool,
    applyable: bool,
    candidate_layout_graph_hash: str | None = None,
    layout_verification: Mapping[str, Any] | None = None,
    verification_kind: str = "delta_replay",
    state: str = "candidate_ready",
    layout_operation_envelope: Mapping[str, Any] | None = None,
    mutation_materialization_envelope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if state not in CANONICAL_TRANSACTION_STATES:
        raise ValueError(f"Unknown candidate transaction state {state!r}.")
    from vibecomfy.comfy_nodes.agent._frag_state import derived_accepted_delta_envelope

    if accepted_batch is None:
        raise ValueError("Candidate authority requires accepted_batch.")
    persisted_batch = [dict(item) for item in accepted_batch if isinstance(item, Mapping)]
    derived_envelope = derived_accepted_delta_envelope({"accepted_batch": persisted_batch})
    if delta_hash is None:
        delta_hash = content_hash(derived_envelope)
    canonical_state = state
    actions = available_actions_for_state(canonical_state) if applyable else ()
    workflow_identity_v1(workflow_id)
    if derived_envelope.get("schema_version") != AUTHORITY_RECEIPT_DELTA_SCHEMA:
        raise ValueError("New candidate authority requires delta wire schema 2.0.0.")
    if (
        not isinstance(authority_receipt_hash, str)
        or len(authority_receipt_hash) != 64
        or any(character not in "0123456789abcdef" for character in authority_receipt_hash)
    ):
        raise ValueError("Candidate authority requires an exact lowercase 64-hex receipt digest.")
    transaction_id = hashlib.sha256(f"{session_id}:{turn_id}:{plan_hash}:transaction".encode()).hexdigest()
    candidate_id = hashlib.sha256(f"{session_id}:{turn_id}:{plan_hash}:candidate".encode()).hexdigest()
    family = "layout" if verification_kind == "layout_structural_noop" else "structural"
    projection = "layout_v1" if family == "layout" else "structural_v1"
    precondition = projection_reference_v1(submit_graph, projection)
    postcondition = projection_reference_v1(candidate_graph, projection)
    # §3.1: the grandfathered baseline_snapshot_v1 ref restoration is digested
    # over {contract_version, ref} via the shared hash owner so the validator's
    # recomputation matches byte-for-byte.
    restoration_ref = "original.ui.json"
    restoration_digest = _registry_hash(
        {"contract_version": "baseline_snapshot_v1", "ref": restoration_ref}
    )
    delta_ops = list(derived_envelope.get("ops", []))
    operation: dict[str, Any] = {
        "delta_contract": "delta_v1",
        "wire_version": "2.0.0",
        "accepted_batch_digest": delta_hash,
    }
    hashes_extra: dict[str, Any] = {}
    if family == "layout":
        # §1.6: layout family binds operation.layout_operation + digest.
        if layout_operation_envelope is None:
            raise ValueError(
                "Layout (layout_structural_noop) verification requires a layout_operation_envelope."
            )
        from vibecomfy.porting.edit.admit import snapshot_from_schema_witness

        layout_snapshot = snapshot_from_schema_witness(schema_witness, submit_graph=submit_graph)
        normalized_layout = _normalize_layout_operation_v1(
            layout_operation_envelope,
            snapshot=layout_snapshot,
        )
        layout_digest = normalized_layout["digest"]
        operation["layout_operation"] = normalized_layout
        operation["layout_operation_digest"] = layout_digest
        hashes_extra["layout_operation_digest"] = layout_digest
    else:
        add_node_present = any(
            isinstance(op, Mapping) and op.get("op") == "add_node" for op in delta_ops
        )
        if add_node_present:
            # §2.5: structural family with add_node binds mutation_materialization.
            if mutation_materialization_envelope is None:
                raise ValueError(
                    "Structural delta with add_node requires a mutation_materialization_envelope."
                )
            normalized_mat = _normalize_mutation_materialization_v1(
                mutation_materialization_envelope, accompanying_ops=delta_ops
            )
            mat_digest = normalized_mat["digest"]
            operation["mutation_materialization"] = normalized_mat
            operation["mutation_materialization_digest"] = mat_digest
            hashes_extra["mutation_materialization_digest"] = mat_digest
    candidate_authority = {
        "contract_version": CANDIDATE_AUTHORITY_V1,
        "transaction_id": transaction_id,
        "candidate_id": candidate_id,
        "workflow_id": workflow_id,
        "scope": {"kind": "root", "path": ""},
        "session_id": session_id,
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "operation": operation,
        "operation_family": family,
        "precondition": precondition,
        "postcondition": postcondition,
        "rollback_projection": projection,
        "restoration_strategy": {
            "contract_version": "baseline_snapshot_v1",
            "digest": restoration_digest,
            "ref": restoration_ref,
        },
        "authority_receipt_contract_version": AUTHORITY_RECEIPT_CONTRACT_VERSION,
        "authority_receipt_delta_schema": AUTHORITY_RECEIPT_DELTA_SCHEMA,
        "authority_receipt_digest": authority_receipt_hash,
    }
    if family == "layout":
        structural_pre = projection_reference_v1(submit_graph, "structural_v1")
        structural_post = projection_reference_v1(candidate_graph, "structural_v1")
        if structural_pre["digest"] != structural_post["digest"]:
            raise ValueError("Layout authority requires a genuine structural pre==post witness.")
        candidate_authority["structural_witness"] = {
            **structural_pre,
            "precondition_digest": structural_pre["digest"],
            "postcondition_digest": structural_post["digest"],
        }
    return {
        "contract_version": CANDIDATE_TRANSACTION_CONTRACT_VERSION,
        "candidate_authority": candidate_authority,
        "prepared_authority": None,
        "state": canonical_state,
        "resume_state": None,
        "session_id": session_id,
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": None,
        "lease_nonce": None,
        "plan": {
            "schema_version": derived_envelope.get("schema_version"),
            "accepted_batch": persisted_batch,
            "delta_hash": delta_hash,
            "op_count": len(delta_ops),
            "schema_provenance": schema_provenance_summary(schema_witness),
        },
        "hashes": {
            "submit_graph_hash": submit_graph_hash,
            "submit_structural_graph_hash": submit_structural_graph_hash,
            "candidate_graph_hash": candidate_graph_hash,
            "candidate_structural_graph_hash": candidate_structural_graph_hash,
            "candidate_layout_graph_hash": candidate_layout_graph_hash,
            "authority_receipt_hash": authority_receipt_hash,
            **hashes_extra,
        },
        "authority": {
            "replay_ok": replay_ok,
            "candidate_matches": candidate_matches,
            "verification_kind": verification_kind,
            "schema_witness_hash": schema_witness.get("witness_hash"),
            **(
                {"layout_verification": dict(layout_verification)}
                if isinstance(layout_verification, Mapping)
                else {}
            ),
        },
        "available_actions": list(actions),
        "terminal": canonical_state in TERMINAL_TRANSACTION_STATES,
        "last_error": None,
    }


def _mint_restoration_compensation(
    prepared_authority: Mapping[str, Any],
    *,
    compensation_ref: str,
) -> dict[str, Any]:
    """Mint a prepare-owned optional compensation envelope (§3.4).

    Sole minter: the trusted prepare step (``project_transaction_state``),
    invoked only **after** ``lease_nonce`` and ``generation`` have been issued.
    The fence binds the prepared authority's own identity/projection fields so
    the compensation cannot be replayed against a different prepared authority.
    The digest is computed over the shared hash owner (identical preimage to the
    validator's recomputation).
    """
    if not isinstance(compensation_ref, str) or not compensation_ref:
        raise ValueError("compensation_ref must be a non-empty durable ref string.")
    precondition = prepared_authority.get("precondition")
    postcondition = prepared_authority.get("postcondition")
    fence = {
        "transaction_id": prepared_authority.get("transaction_id"),
        "candidate_id": prepared_authority.get("candidate_id"),
        "plan_hash": prepared_authority.get("plan_hash"),
        "lease_nonce": prepared_authority.get("lease_nonce"),
        "generation": prepared_authority.get("generation"),
        "pre_projection_digest": precondition.get("digest") if isinstance(precondition, Mapping) else None,
        "post_projection_digest": postcondition.get("digest") if isinstance(postcondition, Mapping) else None,
    }
    normalized_fence = _registry_canonicalize_contract_numeric(
        fence, finite_error_code="non_finite_materialization"
    )
    digest = _registry_hash({
        "contract_version": RESTORATION_COMPENSATION_CONTRACT_V1,
        "wire_version": RESTORATION_COMPENSATION_WIRE_VERSION,
        "ref": compensation_ref,
        "fence": normalized_fence,
    })
    return {
        "contract_version": RESTORATION_COMPENSATION_CONTRACT_V1,
        "wire_version": RESTORATION_COMPENSATION_WIRE_VERSION,
        "ref": compensation_ref,
        "fence": fence,
        "digest": digest,
    }


def project_transaction_state(
    candidate: Mapping[str, Any],
    *,
    state: str,
    generation: int | None = None,
    lease_nonce: str | None = None,
    last_error: Mapping[str, Any] | None = None,
    resume_state: str | None = None,
    compensation_ref: str | None = None,
) -> dict[str, Any]:
    projected = json.loads(json.dumps(candidate))
    if state not in CANONICAL_TRANSACTION_STATES:
        raise ValueError(f"Unknown candidate transaction state {state!r}.")
    canonical_state = state
    if resume_state is not None and resume_state not in CANONICAL_TRANSACTION_STATES:
        raise ValueError(f"Unknown candidate transaction resume state {resume_state!r}.")
    projected["state"] = canonical_state
    projected["resume_state"] = resume_state
    projected["generation"] = generation
    projected["lease_nonce"] = lease_nonce
    projected["last_error"] = dict(last_error) if isinstance(last_error, Mapping) else None
    candidate_authority = projected.get("candidate_authority")
    if canonical_state in {"prepared", "canvas_verified", "finalized", "rollback_complete", "superseded"}:
        if not isinstance(candidate_authority, Mapping) or not isinstance(generation, int) or generation <= 0 or not isinstance(lease_nonce, str) or not lease_nonce:
            raise ValueError("Prepared v2 transition requires explicit generation and lease nonce.")
        prepared = dict(candidate_authority)
        prepared["contract_version"] = PREPARED_AUTHORITY_V1
        prepared["generation"] = generation
        prepared["lease_nonce"] = lease_nonce
        # Sole prepare-owned additive: optionally mint restoration_strategy_compensation
        # after lease/generation issuance.  Candidate authority never carries it.
        if compensation_ref is not None:
            prepared["restoration_strategy_compensation"] = _mint_restoration_compensation(
                prepared, compensation_ref=compensation_ref
            )
        projected["prepared_authority"] = prepared
    else:
        projected["prepared_authority"] = None
    projected["available_actions"] = list(
        available_actions_for_state(canonical_state, resume_state=resume_state)
    )
    projected["terminal"] = canonical_state in TERMINAL_TRANSACTION_STATES
    return projected


def validate_candidate_transaction(value: Any) -> tuple[bool, str | None]:
    if not isinstance(value, Mapping):
        return False, "missing_candidate_transaction"
    if value.get("contract_version") != CANDIDATE_TRANSACTION_CONTRACT_VERSION:
        return False, "unsupported_candidate_transaction"
    state = canonical_transaction_state(value.get("state"))
    if state is None:
        return False, "invalid_candidate_transaction_state"
    try:
        validate_candidate_transaction_v2(value)
    except Exception as exc:
        return False, getattr(exc, "code", "invalid_candidate_authority")
    plan = value.get("plan")
    hashes = value.get("hashes")
    authority = value.get("authority")
    candidate_authority = value.get("candidate_authority")
    if not all(isinstance(item, Mapping) for item in (plan, hashes, authority)):
        return False, "malformed_candidate_transaction"
    accepted = plan.get("accepted_batch")
    if not isinstance(accepted, list):
        return False, "missing_persisted_delta_plan"
    from vibecomfy.comfy_nodes.agent._frag_state import derived_accepted_delta_envelope

    derived = derived_accepted_delta_envelope({"accepted_batch": accepted})
    if plan.get("delta_hash") != content_hash(derived):
        return False, "persisted_delta_hash_mismatch"
    required_hashes = ("candidate_graph_hash", "candidate_structural_graph_hash", "authority_receipt_hash")
    if any(not isinstance(hashes.get(field), str) or not hashes.get(field) for field in required_hashes):
        return False, "missing_candidate_transaction_hash"
    # Recompute layout_operation / mutation_materialization digests bound on the
    # candidate operation and compare against the transaction-level hashes block
    # (§1.6).  The authority validator already checks operation-internal digest
    # consistency; this is the cross-block tamper check.
    operation = candidate_authority.get("operation") if isinstance(candidate_authority, Mapping) else None
    if isinstance(operation, Mapping):
        if isinstance(operation.get("layout_operation"), Mapping):
            recomputed_layout = _compute_layout_operation_digest(
                operation["layout_operation"].get("ops", [])
            )
            if hashes.get("layout_operation_digest") != recomputed_layout:
                return False, "layout_operation_digest_mismatch"
        if isinstance(operation.get("mutation_materialization"), Mapping):
            from vibecomfy.comfy_nodes.agent._frag_state import _ops_from_accepted_batch

            recomputed_mat = _compute_mutation_materialization_digest(
                operation["mutation_materialization"].get("entries", []),
                list(_ops_from_accepted_batch({"accepted_batch": accepted})),
            )
            if hashes.get("mutation_materialization_digest") != recomputed_mat:
                return False, "mutation_materialization_digest_mismatch"
    layout_verification = authority.get("layout_verification")
    if layout_verification is not None:
        if not isinstance(layout_verification, Mapping):
            return False, "malformed_layout_verification_contract"
        if (
            layout_verification.get("contract_version")
            != LAYOUT_VERIFICATION_CONTRACT_VERSION
            or layout_verification.get("projection")
            != LAYOUT_VERIFICATION_PROJECTION
        ):
            return False, "unsupported_layout_verification_contract"
        layout_hash = layout_verification.get("candidate_layout_graph_hash")
        if (
            not isinstance(layout_hash, str)
            or len(layout_hash) != 64
            or any(character not in "0123456789abcdef" for character in layout_hash)
            or hashes.get("candidate_layout_graph_hash") != layout_hash
        ):
            return False, "invalid_layout_verification_hash"
    actions = value.get("available_actions")
    if not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
        return False, "malformed_candidate_transaction_actions"
    expected_actions = list(
        available_actions_for_state(state, resume_state=value.get("resume_state"))
    )
    if actions != expected_actions and not (state == "candidate_ready" and actions == []):
        return False, "candidate_transaction_action_state_mismatch"
    return True, None


def bounded_error_diagnostic(
    error: BaseException | str,
    *,
    stage: str,
    substage: str,
    recoverable: bool,
    resume_state: str | None = None,
) -> dict[str, Any]:
    message = str(error)
    stack: list[str] = []
    if isinstance(error, BaseException) and error.__traceback__ is not None:
        import traceback

        stack = [line.strip()[:512] for line in traceback.format_tb(error.__traceback__, limit=8)]
    return {
        "stage": stage[:64],
        "substage": substage[:128],
        "message": message[:2048],
        "stack": stack[:8],
        "recoverable": bool(recoverable),
        "resume_state": canonical_transaction_state(resume_state),
    }


__all__ = [
    "CANONICAL_TRANSACTION_STATES",
    "CANDIDATE_TRANSACTION_CONTRACT_VERSION",
    "CANDIDATE_TRANSACTION_V2",
    "CANDIDATE_TRANSACTION_FILENAME",
    "CandidateTransactionState",
    "FrozenSchemaProvider",
    "RECOVERABLE_TRANSACTION_STATES",
    "SCHEMA_WITNESS_CONTRACT_VERSION",
    "TERMINAL_TRANSACTION_STATES",
    "available_actions_for_state",
    "bounded_error_diagnostic",
    "build_candidate_transaction",
    "build_schema_witness",
    "capture_ingress_schema_snapshot",
    "canonical_transaction_state",
    "content_hash",
    "missing_touched_class_types",
    "project_transaction_state",
    "schema_provenance_summary",
    "schema_provider_from_witness",
    "validate_candidate_transaction",
    "validate_candidate_transaction_v2",
    "validate_prepared_authority_v1",
    "classify_legacy_migration_v1",
    "validate_schema_witness",
]
