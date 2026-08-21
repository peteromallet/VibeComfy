from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

SCHEMA_SNAPSHOT_VERSION = "schema-snapshot-v1"
SCHEMA_SNAPSHOT_PRECEDENCE = (
    "explicit_request_snapshot",
    "verified_connected_object_info",
    "configured_content_addressed_cache",
)


@dataclass(frozen=True)
class InputSpec:
    type: str | None = None
    required: bool = False
    default: Any = None
    choices: list[Any] | None = None
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class OutputSpec:
    type: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class NodeSchema:
    class_type: str
    pack: str | None
    inputs: dict[str, InputSpec]
    outputs: list[OutputSpec]


class SchemaIndexError(ValueError):
    def __init__(self, path: Path, cause: Exception) -> None:
        super().__init__(f"{path} could not be read: {type(cause).__name__}: {cause}")
        self.path = path
        self.cause = cause


@runtime_checkable
class SchemaProvider(Protocol):
    def get_schema(self, class_type: str) -> NodeSchema | None: ...


class SchemaSnapshotError(ValueError):
    """Fail-closed schema-authority error for authoring and replay."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SchemaSnapshotIdentity:
    """Runtime/cache/request identity frozen at ingress."""

    runtime_fingerprint: str | None = None
    cache_fingerprint: str | None = None
    request_fingerprint: str | None = None
    server_url: str | None = None


@dataclass(frozen=True)
class SchemaSnapshot:
    """Immutable ingress-bound schema authority for authoring and replay.

    One retained snapshot binds a turn. Replay reconstructs from this object
    and cannot perform a fresh ambient provider/cache lookup.
    """

    identity: SchemaSnapshotIdentity
    content_digest: str
    precedence: tuple[str, ...]
    selected_source: str
    generation: int
    conflicts: tuple[str, ...]
    timestamp: str | None
    version: str
    schemas: Mapping[str, Any]
    missing_classes: tuple[str, ...]
    input_order: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    node_classes: Mapping[str, str] = field(default_factory=dict)
    workflow_observation_authoritative: bool = False
    ambient_lookup_forbidden: bool = True

    def get_schema(self, class_type: str) -> Any | None:
        return self.schemas.get(class_type)

    def schemas_map(self) -> dict[str, Any]:
        return dict(self.schemas)


def _freeze_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _freeze_jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_freeze_jsonable(item) for item in value]
    return value


def _schema_snapshot_digest(payload: Mapping[str, Any]) -> str:
    from vibecomfy.comfy_nodes.agent._canonical_contract_primitives import (
        canonical_json_bytes_v1,
    )
    import hashlib

    return hashlib.sha256(canonical_json_bytes_v1(payload, ensure_ascii=False)).hexdigest()


def _input_spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "type": getattr(spec, "type", None),
        "required": bool(getattr(spec, "required", False)),
        "default": _freeze_jsonable(getattr(spec, "default", None)),
        "choices": _freeze_jsonable(getattr(spec, "choices", None)),
        "min": getattr(spec, "min", None),
        "max": getattr(spec, "max", None),
    }


def _output_spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "type": getattr(spec, "type", None),
        "name": getattr(spec, "name", None),
    }


def schema_payload_from_node_schema(class_type: str, schema: Any) -> dict[str, Any]:
    """Durable per-class payload. Named inputs only; no positional alias authority."""
    inputs = getattr(schema, "inputs", {})
    ordered_inputs = inputs if isinstance(inputs, Mapping) else {}
    provenance_fields = (
        "source_provider",
        "source_path",
        "source_cache_path",
        "source_server_url",
        "source_package",
        "source_version",
        "source_hash",
        "confidence",
        "conflicts",
        "ignored_evidence",
    )
    return {
        "class_type": class_type,
        "pack": getattr(schema, "pack", None),
        "inputs": {
            str(name): _input_spec_payload(spec)
            for name, spec in sorted(ordered_inputs.items(), key=lambda item: str(item[0]))
        },
        "input_order": [str(name) for name in ordered_inputs.keys()],
        "outputs": [
            _output_spec_payload(spec) for spec in (getattr(schema, "outputs", None) or ()) if spec is not None
        ],
        "provenance": {
            field: _freeze_jsonable(getattr(schema, field, None)) for field in provenance_fields
        },
    }


def node_schema_from_payload(class_type: str, raw: Mapping[str, Any]) -> NodeSchema:
    from vibecomfy.schema.provider import NodeSchema as ProviderNodeSchema

    raw_inputs = raw.get("inputs")
    inputs: dict[str, InputSpec] = {}
    raw_input_order = raw.get("input_order")
    ordered_names = (
        [name for name in raw_input_order if isinstance(name, str)]
        if isinstance(raw_input_order, list)
        else []
    )
    if isinstance(raw_inputs, Mapping):
        ordered_names.extend(str(name) for name in raw_inputs if str(name) not in ordered_names)
    for name in ordered_names:
        spec = raw_inputs.get(name) if isinstance(raw_inputs, Mapping) else None
        if not isinstance(spec, Mapping):
            continue
        if str(name).startswith("widget_"):
            continue
        choices = spec.get("choices")
        inputs[str(name)] = InputSpec(
            type=spec.get("type") if isinstance(spec.get("type"), str) else None,
            required=spec.get("required") is True,
            default=spec.get("default"),
            choices=list(choices) if isinstance(choices, list) else None,
            min=spec.get("min") if isinstance(spec.get("min"), (int, float)) else None,
            max=spec.get("max") if isinstance(spec.get("max"), (int, float)) else None,
        )
    raw_outputs = raw.get("outputs")
    outputs = [
        OutputSpec(
            type=item.get("type") if isinstance(item.get("type"), str) else None,
            name=item.get("name") if isinstance(item.get("name"), str) else None,
        )
        for item in raw_outputs
        if isinstance(item, Mapping)
    ] if isinstance(raw_outputs, list) else []
    provenance = raw.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    return ProviderNodeSchema(
        class_type=class_type,
        pack=raw.get("pack") if isinstance(raw.get("pack"), str) else None,
        inputs=inputs,
        outputs=outputs,
        source_provider=str(provenance.get("source_provider") or "persisted_snapshot"),
        source_path=provenance.get("source_path") if isinstance(provenance.get("source_path"), str) else None,
        source_cache_path=(
            provenance.get("source_cache_path")
            if isinstance(provenance.get("source_cache_path"), str)
            else None
        ),
        source_server_url=None,
        source_package=(
            provenance.get("source_package") if isinstance(provenance.get("source_package"), str) else None
        ),
        source_version=(
            provenance.get("source_version") if isinstance(provenance.get("source_version"), str) else None
        ),
        source_hash=provenance.get("source_hash") if isinstance(provenance.get("source_hash"), str) else None,
        confidence=(
            float(provenance.get("confidence", 1.0))
            if isinstance(provenance.get("confidence"), (int, float))
            else 1.0
        ),
        conflicts=tuple(
            str(item) for item in provenance.get("conflicts", []) if isinstance(item, str)
        ),
        ignored_evidence=tuple(
            str(item) for item in provenance.get("ignored_evidence", []) if isinstance(item, str)
        ),
    )


def schema_snapshot_to_payload(snapshot: SchemaSnapshot) -> dict[str, Any]:
    payload = {
        "contract_version": SCHEMA_SNAPSHOT_VERSION,
        "identity": {
            "runtime_fingerprint": snapshot.identity.runtime_fingerprint,
            "cache_fingerprint": snapshot.identity.cache_fingerprint,
            "request_fingerprint": snapshot.identity.request_fingerprint,
            "server_url": snapshot.identity.server_url,
        },
        "content_digest": snapshot.content_digest,
        "precedence": list(snapshot.precedence),
        "selected_source": snapshot.selected_source,
        "generation": snapshot.generation,
        "conflicts": list(snapshot.conflicts),
        "timestamp": snapshot.timestamp,
        "version": snapshot.version,
        "schemas": _freeze_jsonable(snapshot.schemas),
        "missing_classes": list(snapshot.missing_classes),
        "input_order": {
            str(class_type): list(names) for class_type, names in snapshot.input_order.items()
        },
        "workflow_observation_authoritative": False,
        "ambient_lookup_forbidden": True,
    }
    node_classes = {
        str(uid): str(class_type)
        for uid, class_type in snapshot.node_classes.items()
        if str(uid) and str(class_type)
    }
    if node_classes:
        payload["node_classes"] = node_classes
    return payload


def schema_snapshot_from_payload(payload: Mapping[str, Any]) -> SchemaSnapshot:
    if not isinstance(payload, Mapping):
        raise SchemaSnapshotError("schema snapshot payload must be an object", code="malformed_schema_snapshot")
    if payload.get("contract_version") != SCHEMA_SNAPSHOT_VERSION:
        raise SchemaSnapshotError(
            "unsupported schema snapshot contract",
            code="unsupported_schema_snapshot",
        )
    identity_raw = payload.get("identity")
    identity_raw = identity_raw if isinstance(identity_raw, Mapping) else {}
    schemas_raw = payload.get("schemas")
    schemas = {
        str(class_type): dict(raw)
        for class_type, raw in (schemas_raw.items() if isinstance(schemas_raw, Mapping) else ())
        if isinstance(raw, Mapping)
    }
    input_order_raw = payload.get("input_order")
    input_order = {
        str(class_type): tuple(str(name) for name in names if isinstance(name, str))
        for class_type, names in (input_order_raw.items() if isinstance(input_order_raw, Mapping) else ())
        if isinstance(names, list)
    }
    missing = payload.get("missing_classes")
    node_classes_raw = payload.get("node_classes")
    node_classes = {
        str(uid): str(class_type)
        for uid, class_type in (node_classes_raw.items() if isinstance(node_classes_raw, Mapping) else ())
        if str(uid) and isinstance(class_type, str) and class_type
    }
    snapshot = SchemaSnapshot(
        identity=SchemaSnapshotIdentity(
            runtime_fingerprint=identity_raw.get("runtime_fingerprint")
            if isinstance(identity_raw.get("runtime_fingerprint"), str)
            else None,
            cache_fingerprint=identity_raw.get("cache_fingerprint")
            if isinstance(identity_raw.get("cache_fingerprint"), str)
            else None,
            request_fingerprint=identity_raw.get("request_fingerprint")
            if isinstance(identity_raw.get("request_fingerprint"), str)
            else None,
            server_url=identity_raw.get("server_url") if isinstance(identity_raw.get("server_url"), str) else None,
        ),
        content_digest=str(payload.get("content_digest") or ""),
        precedence=tuple(str(item) for item in payload.get("precedence", SCHEMA_SNAPSHOT_PRECEDENCE) if isinstance(item, str)),
        selected_source=str(payload.get("selected_source") or ""),
        generation=int(payload.get("generation") or 0),
        conflicts=tuple(str(item) for item in payload.get("conflicts", ()) if isinstance(item, str)),
        timestamp=payload.get("timestamp") if isinstance(payload.get("timestamp"), str) else None,
        version=str(payload.get("version") or SCHEMA_SNAPSHOT_VERSION),
        schemas=schemas,
        missing_classes=tuple(str(item) for item in missing if isinstance(item, str)) if isinstance(missing, list) else (),
        input_order=input_order,
        node_classes=node_classes,
        workflow_observation_authoritative=False,
        ambient_lookup_forbidden=True,
    )
    expected = _schema_snapshot_digest(_digest_body(snapshot))
    if snapshot.content_digest != expected:
        raise SchemaSnapshotError("schema snapshot digest mismatch", code="schema_snapshot_digest_mismatch")
    return snapshot


def _digest_body(snapshot: SchemaSnapshot) -> dict[str, Any]:
    body = {
        "contract_version": SCHEMA_SNAPSHOT_VERSION,
        "identity": {
            "runtime_fingerprint": snapshot.identity.runtime_fingerprint,
            "cache_fingerprint": snapshot.identity.cache_fingerprint,
            "request_fingerprint": snapshot.identity.request_fingerprint,
            "server_url": snapshot.identity.server_url,
        },
        "precedence": list(snapshot.precedence),
        "selected_source": snapshot.selected_source,
        "generation": snapshot.generation,
        "conflicts": list(snapshot.conflicts),
        "timestamp": snapshot.timestamp,
        "version": snapshot.version,
        "schemas": _freeze_jsonable(snapshot.schemas),
        "missing_classes": list(snapshot.missing_classes),
        "input_order": {
            str(class_type): list(names) for class_type, names in snapshot.input_order.items()
        },
        "workflow_observation_authoritative": False,
        "ambient_lookup_forbidden": True,
    }
    node_classes = {
        str(uid): str(class_type)
        for uid, class_type in snapshot.node_classes.items()
        if str(uid) and str(class_type)
    }
    if node_classes:
        body["node_classes"] = node_classes
    return body


def capture_schema_snapshot(
    *,
    class_types: Sequence[str] | None = None,
    request_snapshot: Mapping[str, Any] | SchemaSnapshot | None = None,
    connected_object_info: Mapping[str, Any] | None = None,
    connected_object_info_verified: bool = False,
    cache_payload: Mapping[str, Any] | None = None,
    cache_path: str | Path | None = None,
    runtime_fingerprint: str | None = None,
    server_url: str | None = None,
    timestamp: str | None = None,
    generation: int | None = None,
    workflow_observation: Mapping[str, Any] | None = None,
    node_classes: Mapping[str, str] | None = None,
) -> SchemaSnapshot:
    """Freeze schema authority at ingress.

    Precedence is explicit request snapshot, then verified connected
    ``/object_info``, then configured content-addressed cache. Workflow
    observation is recorded as non-authoritative and never selected.
    """
    del workflow_observation  # non-authoritative by contract
    selected_source = ""
    selected_payload: Mapping[str, Any] | None = None
    conflicts: list[str] = []
    identity = SchemaSnapshotIdentity(
        runtime_fingerprint=runtime_fingerprint,
        cache_fingerprint=None,
        request_fingerprint=None,
        server_url=server_url,
    )
    frozen_generation = 0
    frozen_timestamp = timestamp
    frozen_version = SCHEMA_SNAPSHOT_VERSION

    if isinstance(request_snapshot, SchemaSnapshot):
        selected_source = "explicit_request_snapshot"
        selected_payload = schema_snapshot_to_payload(request_snapshot)
        identity = SchemaSnapshotIdentity(
            runtime_fingerprint=request_snapshot.identity.runtime_fingerprint or runtime_fingerprint,
            cache_fingerprint=request_snapshot.identity.cache_fingerprint,
            request_fingerprint=request_snapshot.content_digest,
            server_url=request_snapshot.identity.server_url or server_url,
        )
        frozen_generation = request_snapshot.generation
        frozen_timestamp = request_snapshot.timestamp or timestamp
        frozen_version = request_snapshot.version
    elif isinstance(request_snapshot, Mapping) and request_snapshot:
        selected_source = "explicit_request_snapshot"
        selected_payload = request_snapshot
        identity = SchemaSnapshotIdentity(
            runtime_fingerprint=runtime_fingerprint,
            cache_fingerprint=None,
            request_fingerprint=_schema_snapshot_digest(_freeze_jsonable(request_snapshot)),
            server_url=server_url,
        )
        frozen_generation = int(request_snapshot.get("generation") or 0)
        frozen_timestamp = (
            request_snapshot.get("timestamp")
            if isinstance(request_snapshot.get("timestamp"), str)
            else timestamp
        )
        frozen_version = str(request_snapshot.get("version") or SCHEMA_SNAPSHOT_VERSION)
    elif connected_object_info_verified and isinstance(connected_object_info, Mapping) and connected_object_info:
        selected_source = "verified_connected_object_info"
        selected_payload = connected_object_info
        identity = SchemaSnapshotIdentity(
            runtime_fingerprint=runtime_fingerprint,
            cache_fingerprint=None,
            request_fingerprint=None,
            server_url=server_url,
        )
        frozen_generation = int(connected_object_info.get("generation") or 0) if isinstance(connected_object_info.get("generation"), int) else 0
        frozen_timestamp = (
            connected_object_info.get("timestamp")
            if isinstance(connected_object_info.get("timestamp"), str)
            else timestamp
        )
    elif isinstance(cache_payload, Mapping) and cache_payload:
        from vibecomfy.schema.cache import (
            CACHE_METADATA_KEY,
            object_info_payload,
            object_info_payload_checksum,
            validate_object_info_cache,
        )

        expected = {"runtime_fingerprint": runtime_fingerprint} if runtime_fingerprint else None
        result = validate_object_info_cache(
            dict(cache_payload),
            expected=expected,
            policy="strict",
            cache_path=cache_path,
        )
        if result.ok:
            selected_source = "configured_content_addressed_cache"
            selected_payload = object_info_payload(dict(cache_payload))
            metadata = cache_payload.get(CACHE_METADATA_KEY)
            metadata = metadata if isinstance(metadata, Mapping) else {}
            identity = SchemaSnapshotIdentity(
                runtime_fingerprint=runtime_fingerprint or (
                    metadata.get("runtime_fingerprint")
                    if isinstance(metadata.get("runtime_fingerprint"), str)
                    else None
                ),
                cache_fingerprint=object_info_payload_checksum(dict(cache_payload)),
                request_fingerprint=None,
                server_url=server_url
                or (metadata.get("server_url") if isinstance(metadata.get("server_url"), str) else None),
            )
            frozen_generation = int(metadata.get("generation") or 0) if isinstance(metadata.get("generation"), int) else 0
            frozen_timestamp = (
                metadata.get("captured_at")
                if isinstance(metadata.get("captured_at"), str)
                else timestamp
            )
            frozen_version = str(metadata.get("format_version") or SCHEMA_SNAPSHOT_VERSION)
        else:
            conflicts.append(f"rejected_cache:{result.reason}")
    if generation is not None:
        frozen_generation = int(generation)

    schemas: dict[str, Any] = {}
    missing: list[str] = []
    input_order: dict[str, tuple[str, ...]] = {}
    requested = [str(item) for item in (class_types or ()) if str(item)]
    if selected_source == "explicit_request_snapshot" and isinstance(selected_payload, Mapping) and "schemas" in selected_payload:
        raw_schemas = selected_payload.get("schemas")
        if isinstance(raw_schemas, Mapping):
            for class_type, raw in raw_schemas.items():
                if not isinstance(raw, Mapping):
                    continue
                payload = dict(raw)
                if str(class_type) in requested or not requested:
                    schemas[str(class_type)] = payload
                    order = payload.get("input_order")
                    if isinstance(order, list):
                        input_order[str(class_type)] = tuple(str(name) for name in order if isinstance(name, str) and not str(name).startswith("widget_"))
        raw_missing = selected_payload.get("missing_classes") or selected_payload.get("missing_class_types")
        if isinstance(raw_missing, list):
            missing.extend(str(item) for item in raw_missing if isinstance(item, str))
        extra_conflicts = selected_payload.get("conflicts")
        if isinstance(extra_conflicts, list):
            conflicts.extend(str(item) for item in extra_conflicts if isinstance(item, str))
    elif isinstance(selected_payload, Mapping):
        from vibecomfy.schema.provider import _schema_from_object_info

        for class_type, info in selected_payload.items():
            if str(class_type).startswith("_") or not isinstance(info, Mapping):
                continue
            if requested and str(class_type) not in requested:
                continue
            schema = _schema_from_object_info(str(class_type), dict(info))
            payload = schema_payload_from_node_schema(str(class_type), schema)
            schemas[str(class_type)] = payload
            input_order[str(class_type)] = tuple(payload.get("input_order") or ())

    if requested:
        for class_type in requested:
            if class_type not in schemas and class_type not in missing:
                missing.append(class_type)

    frozen_node_classes: dict[str, str] = {}
    inherited = None
    if isinstance(request_snapshot, SchemaSnapshot):
        inherited = request_snapshot.node_classes
    elif isinstance(request_snapshot, Mapping):
        inherited = request_snapshot.get("node_classes")
    if inherited is None:
        inherited = node_classes
    if isinstance(inherited, Mapping):
        frozen_node_classes = {
            str(uid): str(class_type)
            for uid, class_type in inherited.items()
            if str(uid) and isinstance(class_type, str) and class_type
        }
    if isinstance(node_classes, Mapping):
        frozen_node_classes.update(
            {
                str(uid): str(class_type)
                for uid, class_type in node_classes.items()
                if str(uid) and isinstance(class_type, str) and class_type
            }
        )

    snapshot = SchemaSnapshot(
        identity=identity,
        content_digest="",
        precedence=SCHEMA_SNAPSHOT_PRECEDENCE,
        selected_source=selected_source,
        generation=frozen_generation,
        conflicts=tuple(dict.fromkeys(conflicts)),
        timestamp=frozen_timestamp,
        version=str(frozen_version),
        schemas=schemas,
        missing_classes=tuple(dict.fromkeys(missing)),
        input_order=input_order,
        node_classes=frozen_node_classes,
        workflow_observation_authoritative=False,
        ambient_lookup_forbidden=True,
    )
    digest = _schema_snapshot_digest(_digest_body(snapshot))
    return SchemaSnapshot(
        identity=snapshot.identity,
        content_digest=digest,
        precedence=snapshot.precedence,
        selected_source=snapshot.selected_source,
        generation=snapshot.generation,
        conflicts=snapshot.conflicts,
        timestamp=snapshot.timestamp,
        version=snapshot.version,
        schemas=snapshot.schemas,
        missing_classes=snapshot.missing_classes,
        input_order=snapshot.input_order,
        node_classes=snapshot.node_classes,
        workflow_observation_authoritative=False,
        ambient_lookup_forbidden=True,
    )


def _operation_mapping(operation: Any) -> Mapping[str, Any]:
    if isinstance(operation, Mapping):
        return operation
    op_name = getattr(operation, "op", None)
    if isinstance(op_name, str):
        from vibecomfy.porting.edit.ops import canonical_op_to_dict

        try:
            return canonical_op_to_dict(operation)
        except Exception:
            return {"op": op_name}
    return {}


def _add_identity(bucket: set[str], ref: Any) -> None:
    if isinstance(ref, Mapping):
        for key in ("uid", "id", "node_id"):
            value = ref.get(key)
            if value is not None and str(value):
                bucket.add(str(value))
        return
    if isinstance(ref, Sequence) and not isinstance(ref, (str, bytes)) and len(ref) >= 2 and ref[1] is not None:
        bucket.add(str(ref[1]))
        return
    if isinstance(ref, str) and ref:
        bucket.add(ref)


def _snapshot_node_class_map(snapshot: SchemaSnapshot | Mapping[str, Any] | None) -> dict[str, str]:
    """Return uid/id -> class_type from a snapshot. Never treats uid as class."""
    if isinstance(snapshot, SchemaSnapshot):
        return {
            str(uid): str(class_type)
            for uid, class_type in snapshot.node_classes.items()
            if str(uid) and str(class_type)
        }
    if not isinstance(snapshot, Mapping):
        return {}
    raw = snapshot.get("node_classes")
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(uid): str(class_type)
        for uid, class_type in raw.items()
        if str(uid) and isinstance(class_type, str) and class_type
    }


def _snapshot_known_and_missing(
    snapshot: SchemaSnapshot | Mapping[str, Any] | None,
) -> tuple[set[str], set[str]]:
    if isinstance(snapshot, SchemaSnapshot):
        known = set(str(name) for name in snapshot.schemas)
        missing = set(snapshot.missing_classes)
        return known, missing
    if isinstance(snapshot, Mapping):
        schemas = snapshot.get("schemas")
        known = set(str(name) for name in schemas) if isinstance(schemas, Mapping) else set()
        raw_missing = snapshot.get("missing_classes") or snapshot.get("missing_class_types")
        missing = (
            {str(item) for item in raw_missing if isinstance(item, str)}
            if isinstance(raw_missing, list)
            else set()
        )
        return known, missing
    return set(), set()


def _operation_schema_endpoints(
    operation: Mapping[str, Any],
    snapshot: SchemaSnapshot | Mapping[str, Any] | None = None,
) -> tuple[set[str], set[str], set[str]]:
    """Return (required identities, optional identities, explicit class types).

    Required identities fail closed when unmapped. Optional identities
    (group/subgraph layout records) contribute a class only when mapped.
    """
    op_name = str(operation.get("op") or "")
    required: set[str] = set()
    optional: set[str] = set()
    explicit_classes: set[str] = set()
    class_type = operation.get("class_type")
    if isinstance(class_type, str) and class_type:
        explicit_classes.add(class_type)

    if op_name in {"set_node_field", "set_mode", "remove_node"}:
        _add_identity(required, operation.get("target"))
    elif op_name in {"upsert_link", "remove_link"}:
        _add_identity(required, operation.get("from") or operation.get("source"))
        _add_identity(required, operation.get("to") or operation.get("target"))
    elif op_name == "add_node":
        inputs = operation.get("inputs")
        if isinstance(inputs, Mapping):
            for source in inputs.values():
                _add_identity(required, source)
        anchor = operation.get("anchor")
        if isinstance(anchor, Mapping):
            _add_identity(required, anchor.get("near"))
            between = anchor.get("between")
            if isinstance(between, Sequence) and not isinstance(between, (str, bytes)):
                for ref in between:
                    _add_identity(required, ref)
    elif op_name == "set_node_geometry":
        if isinstance(operation.get("uid"), (str, int)):
            required.add(str(operation.get("uid")))
        if isinstance(operation.get("id"), (str, int)):
            required.add(str(operation.get("id")))
        if isinstance(operation.get("node_id"), (str, int)):
            required.add(str(operation.get("node_id")))
    elif op_name in {"set_group_geometry", "remove_group", "subgraph_interface"}:
        node_classes = _snapshot_node_class_map(snapshot)
        for key in ("uid", "id", "node_id"):
            value = operation.get(key)
            if isinstance(value, (str, int)) and str(value):
                identity = str(value)
                if identity in node_classes:
                    optional.add(identity)
    return required, optional, explicit_classes


def touched_schema_classes(operation: Any, snapshot: SchemaSnapshot | Mapping[str, Any] | None) -> tuple[str, ...]:
    """Return schema classes whose validity is required by *operation*.

    Covers field, add/remove, link/socket, mode, and layout operations.
    Node uids are resolved through the snapshot node-class map; a uid is never
    treated as a class type merely because it is a string. Unknown untouched
    nodes are not returned and remain preserved.
    """
    op = _operation_mapping(operation)
    required, optional, explicit_classes = _operation_schema_endpoints(op, snapshot)
    node_classes = _snapshot_node_class_map(snapshot)
    classes = set(explicit_classes)
    for identity in required | optional:
        resolved = node_classes.get(identity)
        if resolved is None:
            continue
        classes.add(resolved)
    return tuple(sorted(classes))


def require_known_touched_schema(
    operation: Any,
    snapshot: SchemaSnapshot | Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Fail closed when a touched operation depends on unknown schema."""
    op = _operation_mapping(operation)
    required, _optional, _explicit = _operation_schema_endpoints(op, snapshot)
    node_classes = _snapshot_node_class_map(snapshot)
    known, missing = _snapshot_known_and_missing(snapshot)
    classes = list(touched_schema_classes(operation, snapshot))
    unresolved = [identity for identity in sorted(required) if identity not in node_classes]
    unknown = [
        class_type
        for class_type in classes
        if class_type not in known or class_type in missing
    ]
    if unresolved or unknown:
        raise SchemaSnapshotError(
            "missing_touched_schema:" + ",".join([*unresolved, *unknown]),
            code="missing_touched_schema",
        )
    return tuple(classes)



class FrozenSchemaSnapshotProvider:
    """Schema provider reconstructed exclusively from a persisted SchemaSnapshot."""

    def __init__(self, snapshot: SchemaSnapshot | Mapping[str, Any]) -> None:
        if isinstance(snapshot, SchemaSnapshot):
            self._snapshot = snapshot
        else:
            self._snapshot = schema_snapshot_from_payload(snapshot)
        if not self._snapshot.ambient_lookup_forbidden:
            raise SchemaSnapshotError("replay snapshot must forbid ambient lookup", code="ambient_lookup_forbidden")
        self._schemas: dict[str, Any] = {
            class_type: node_schema_from_payload(class_type, raw)
            for class_type, raw in self._snapshot.schemas.items()
            if isinstance(raw, Mapping)
        }

    def get(self, class_type: str) -> Any | None:
        return self._schemas.get(class_type)

    def get_schema(self, class_type: str) -> Any | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, Any]:
        return dict(self._schemas)

    @property
    def snapshot(self) -> SchemaSnapshot:
        return self._snapshot

    def lookup_ambient(self, *args: Any, **kwargs: Any) -> None:
        raise SchemaSnapshotError(
            "replay cannot perform a fresh ambient schema lookup",
            code="ambient_lookup_forbidden",
        )
