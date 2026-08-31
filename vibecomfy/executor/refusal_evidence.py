"""Frozen authority evidence for model-selected typed refusals.

The model only receives opaque IDs.  Each ID is deterministic and binds one
absence claim to the graph plus schema authority used for that lookup.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any, Mapping



def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def graph_identity(graph: Any) -> str:
    """Return the stable identity of the graph used for one evidence turn."""
    return hashlib.sha256(
        json.dumps(
            _jsonable(graph), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def authority_generation(source: Any) -> str | None:
    """Return a provider-owned generation marker without schema lookups."""
    content_digest = getattr(source, "content_digest", None)
    if content_digest is not None:
        return f"content_digest:{content_digest}"
    schemas = getattr(source, "schemas", None)
    if not callable(schemas):
        return None
    try:
        encoded = json.dumps(
            _jsonable(schemas()), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    except Exception:  # noqa: BLE001 - optional generation metadata
        return None
    return "schemas:" + hashlib.sha256(encoded).hexdigest()


def authority_content_digest(source: Any, class_types: tuple[str, ...]) -> str | None:
    """Digest a bounded set of live ``get_schema`` observations.

    Providers without a roster/generation marker still get freshness
    protection, but only for the exact classes represented by the frozen
    ledger.  A callable-only lookup is intentionally left opaque: it has no
    provider-owned observation surface to revalidate.
    """
    getter = getattr(source, "get_schema", None)
    if not callable(getter):
        return None
    observations: dict[str, Any] = {}
    for class_type in sorted(set(class_types), key=str.casefold):
        try:
            observations[class_type] = getter(class_type)
        except Exception:  # noqa: BLE001 - unavailable authority fails closed
            return None
    return _authority_content_digest_for_observations(observations)


def _authority_content_digest_for_observations(observations: Mapping[str, Any]) -> str:
    """Digest already-captured observations without consulting live authority."""
    payload = {"classes": observations}
    encoded = json.dumps(
        _jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return "bounded:" + hashlib.sha256(encoded).hexdigest()


def _graph_classes(graph: Any) -> set[str]:
    classes: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key in ("class_type", "type"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    classes.add(item.strip().casefold())
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)
        elif hasattr(value, "nodes"):
            walk(getattr(value, "nodes"))
        elif isinstance(getattr(value, "class_type", None), str):
            classes.add(value.class_type.strip().casefold())

    walk(graph)
    return classes


def authority_digest_for_snapshot(
    graph: Any,
    *,
    class_type: str,
    schema: Any,
    schema_content_digest: Any = None,
) -> str:
    """Digest a previously captured graph/schema observation without lookup."""
    payload = {
        "graph_classes": sorted(_graph_classes(graph)),
        "class_type": class_type,
        "schema": _jsonable(schema),
        "schema_content_digest": schema_content_digest,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def authority_digest(graph: Any, schema_provider: Any, *, class_type: str) -> str:
    """Digest the exact graph and class schema authority used by a lookup."""
    schema = None
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema) and callable(schema_provider):
        get_schema = schema_provider
    if callable(get_schema):
        try:
            schema = get_schema(class_type)
        except Exception:  # noqa: BLE001 - unavailable authority is not proof
            schema = None
    return authority_digest_for_snapshot(
        graph,
        class_type=class_type,
        schema=schema,
        schema_content_digest=getattr(schema_provider, "content_digest", None),
    )


def _ledger_integrity(
    records: Mapping[str, Mapping[str, Any]],
    *,
    graph_digest: str,
    schema_snapshot: Mapping[str, Any],
    schema_content_digest: Any,
    source_identity: int,
    source_generation: str | None,
) -> str:
    payload = {
        "records": records,
        "graph_identity": graph_digest,
        "schema_snapshot": schema_snapshot,
        "schema_content_digest": schema_content_digest,
        "source_identity": source_identity,
        "source_generation": source_generation,
    }
    return hashlib.sha256(
        json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class FrozenRefusalLedger(dict[str, dict[str, Any]]):
    """Legacy data type retained for inspection compatibility only."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("FrozenRefusalLedger is not a public authority capture input")

    @classmethod
    def from_collection(cls, *_args: Any, **_kwargs: Any) -> "FrozenRefusalLedger":
        """Reject arbitrary public snapshot construction.

        Production ledgers are minted only by the collector's private token
        path; accepting caller-owned schema snapshots here would turn the
        integrity checksum into self-authentication.
        """
        raise TypeError("FrozenRefusalLedger is not a public authority capture input")

@dataclass(frozen=True)
class RefusalEvidenceBundle:
    """Authority records owned by one executor evidence store entry."""

    records: Mapping[str, Mapping[str, Any]]
    graph_digest: str
    schema_snapshot: Mapping[str, Any]
    schema_content_digest: Any
    source_identity: int
    source_generation: str
    authority_source: Any
    integrity: str


@dataclass(frozen=True)
class RefusalEvidenceHandle(Mapping[str, Mapping[str, Any]]):
    """Opaque model-facing handle for one executor-owned evidence entry."""

    token: str
    evidence_ids: tuple[str, ...]

    def _bundle(self) -> RefusalEvidenceBundle | None:
        return resolve_refusal_evidence_handle(self)

    def __getitem__(self, key: str) -> Mapping[str, Any]:
        bundle = self._bundle()
        if bundle is None:
            raise KeyError(key)
        return bundle.records[key]

    def __iter__(self) -> Iterator[str]:
        bundle = self._bundle()
        return iter(bundle.records if bundle is not None else ())

    def __len__(self) -> int:
        bundle = self._bundle()
        return len(bundle.records) if bundle is not None else 0

    @property
    def records(self) -> Mapping[str, Mapping[str, Any]]:
        bundle = self._bundle()
        return bundle.records if bundle is not None else {}


class RefusalEvidenceStore:
    """Executor-owned registry; entries are addressed only by opaque handles."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        raise TypeError("RefusalEvidenceStore is owned by the executor capture path")

def _make_refusal_evidence_registry() -> tuple[
    Any, Any
]:
    """Create the private capture/resolve closures for executor evidence."""
    # Keep the exact store identities strongly alive for the duration of the
    # executor process.  The registry, not any public object field, is the
    # authority witness for a handle.
    stores: dict[int, RefusalEvidenceStore] = {}
    entries: dict[int, dict[str, RefusalEvidenceBundle]] = {}

    def capture(bundle: RefusalEvidenceBundle) -> RefusalEvidenceHandle:
        store = object.__new__(RefusalEvidenceStore)
        store_identity = id(store)
        stores[store_identity] = store
        token = secrets.token_urlsafe(32)
        entries[store_identity] = {token: bundle}
        return RefusalEvidenceHandle(
            token=token,
            evidence_ids=tuple(bundle.records),
        )

    def resolve(handle: RefusalEvidenceHandle) -> RefusalEvidenceBundle | None:
        if type(handle) is not RefusalEvidenceHandle:
            return None
        for store_identity in stores:
            bundle = entries.get(store_identity, {}).get(handle.token)
            if bundle is not None and handle.evidence_ids == tuple(bundle.records):
                return bundle
        return None

    return capture, resolve


_register_executor_refusal_evidence, _resolve_refusal_evidence = (
    _make_refusal_evidence_registry()
)


def resolve_refusal_evidence_handle(
    handle: RefusalEvidenceHandle,
) -> RefusalEvidenceBundle | None:
    """Resolve only handles issued by the trusted executor capture closure."""
    return _resolve_refusal_evidence(handle)


def frozen_ledger_matches_authority(
    bundle: RefusalEvidenceBundle,
    *,
    graph: Any,
    authority_source: Any,
) -> bool:
    """Validate executor-owned evidence against its frozen authority witness."""
    if type(bundle) is not RefusalEvidenceBundle:
        return False
    if _ledger_integrity(
        bundle.records,
        graph_digest=bundle.graph_digest,
        schema_snapshot=bundle.schema_snapshot,
        schema_content_digest=bundle.schema_content_digest,
        source_identity=bundle.source_identity,
        source_generation=bundle.source_generation,
    ) != bundle.integrity:
        return False
    if bundle.graph_digest != graph_identity(graph):
        return False
    if id(authority_source) != bundle.source_identity:
        return False
    record_classes = tuple(
        str(record.get("class_type"))
        for record in bundle.records.values()
        if isinstance(record.get("class_type"), str)
    )
    if not isinstance(bundle.source_generation, str) or not bundle.source_generation:
        return False
    if bundle.source_generation.startswith("bounded:"):
        if authority_content_digest(authority_source, record_classes) != bundle.source_generation:
            return False
    elif bundle.source_generation.startswith(("content_digest:", "schemas:")):
        if authority_generation(authority_source) != bundle.source_generation:
            return False
    classes = _graph_classes(graph)
    for key, record in bundle.records.items():
        if not isinstance(key, str) or key != record.get("evidence_id"):
            return False
        if not evidence_id_matches_record(record):
            return False
        class_type = record.get("class_type")
        if not isinstance(class_type, str):
            return False
        schema = bundle.schema_snapshot.get(class_type)
        if record.get("authority_digest") != authority_digest_for_snapshot(
            graph,
            class_type=class_type,
            schema=schema,
            schema_content_digest=bundle.schema_content_digest,
        ):
            return False
        if record.get("kind") == "class_absence":
            if class_type.casefold() in classes or schema is not None:
                return False
        elif record.get("kind") == "feature_absence":
            if class_type.casefold() not in classes or schema is None:
                return False
            member_kind = record.get("member_kind")
            member = record.get("member")
            if member_kind not in {"input", "widget", "output"} or not isinstance(member, str):
                return False
            if member_kind == "output":
                names = {
                    str(getattr(item, "name", None) or getattr(item, "type", ""))
                    for item in (getattr(schema, "outputs", None) or ())
                }
            else:
                names = {str(name) for name in (getattr(schema, "inputs", None) or {})}
            if member in names or record.get("present") is not False:
                return False
            if sorted(str(item) for item in record.get("available_members", ())) != sorted(names):
                return False
        else:
            return False
    return True


def class_absence_record(graph: Any, schema_provider: Any, class_type: str) -> dict[str, Any]:
    digest = authority_digest(graph, schema_provider, class_type=class_type)
    identity = f"class_absent|{class_type}|{digest}"
    evidence_id = "refusal:v1:" + hashlib.sha256(identity.encode()).hexdigest()[:24]
    return {
        "evidence_id": evidence_id,
        "kind": "class_absence",
        "class_type": class_type,
        "graph_present": False,
        "schema_present": False,
        "authority_digest": digest,
    }


def feature_absence_record(
    graph: Any,
    schema_provider: Any,
    *,
    class_type: str,
    member_kind: str,
    member: str,
    available_members: list[str],
) -> dict[str, Any]:
    digest = authority_digest(graph, schema_provider, class_type=class_type)
    identity = f"feature_absent|{class_type}|{member_kind}|{member}|{digest}"
    evidence_id = "refusal:v1:" + hashlib.sha256(identity.encode()).hexdigest()[:24]
    return {
        "evidence_id": evidence_id,
        "kind": "feature_absence",
        "feature": member,
        "class_type": class_type,
        "member_kind": member_kind,
        "member": member,
        "present": False,
        "available_members": list(available_members),
        "authority_digest": digest,
    }


def validate_evidence_ids(
    claimed_ids: Any,
    ledger: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...] | None:
    """Resolve a model ID list exactly; unknown/duplicate/malformed fails."""
    if not isinstance(claimed_ids, (list, tuple)) or not claimed_ids:
        return None
    if any(not isinstance(item, str) or not item.strip() for item in claimed_ids):
        return None
    if len(set(claimed_ids)) != len(claimed_ids):
        return None
    records: list[dict[str, Any]] = []
    for item in claimed_ids:
        record = ledger.get(item)
        if not isinstance(record, Mapping):
            return None
        records.append(dict(record))
    return tuple(records)


def evidence_id_matches_record(record: Mapping[str, Any]) -> bool:
    """Check that an ID is the canonical hash of its immutable record fields."""
    evidence_id = record.get("evidence_id")
    digest = record.get("authority_digest")
    if not isinstance(evidence_id, str) or not isinstance(digest, str) or not digest:
        return False
    kind = record.get("kind")
    if kind == "class_absence":
        identity = f"class_absent|{record.get('class_type')}|{digest}"
    elif kind == "feature_absence":
        identity = (
            f"feature_absent|{record.get('class_type')}|{record.get('member_kind')}|"
            f"{record.get('member')}|{digest}"
        )
    else:
        return False
    expected = "refusal:v1:" + hashlib.sha256(identity.encode()).hexdigest()[:24]
    return evidence_id == expected


def evidence_record_matches_authority(
    record: Mapping[str, Any], graph: Any, schema_provider: Any
) -> bool:
    """Bind a record to the current graph/schema authority, not just its ID."""
    if not evidence_id_matches_record(record):
        return False
    class_type = record.get("class_type")
    digest = record.get("authority_digest")
    if not isinstance(class_type, str) or not isinstance(digest, str):
        return False
    expected_digest = authority_digest(graph, schema_provider, class_type=class_type)
    if digest != expected_digest:
        return False

    classes: set[str] = set()
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key in ("class_type", "type"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    classes.add(item.strip().casefold())
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)
        elif hasattr(value, "nodes"):
            walk(getattr(value, "nodes"))
        elif isinstance(getattr(value, "class_type", None), str):
            classes.add(value.class_type.strip().casefold())
    walk(graph)
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema) and callable(schema_provider):
        get_schema = schema_provider
    try:
        schema = get_schema(class_type) if callable(get_schema) else None
    except Exception:  # noqa: BLE001 - unavailable authority fails closed
        return False
    if record.get("kind") == "class_absence":
        return class_type.casefold() not in classes and schema is None
    if record.get("kind") != "feature_absence":
        return False
    if class_type.casefold() not in classes or schema is None:
        return False
    member_kind = record.get("member_kind")
    member = record.get("member")
    if member_kind not in {"input", "widget", "output"} or not isinstance(member, str):
        return False
    if member_kind == "output":
        names = {
            str(getattr(item, "name", None) or getattr(item, "type", ""))
            for item in (getattr(schema, "outputs", None) or ())
        }
    else:
        names = {str(name) for name in (getattr(schema, "inputs", None) or {})}
    return member not in names and record.get("present") is False


__all__ = [
    "FrozenRefusalLedger",
    "RefusalEvidenceBundle",
    "RefusalEvidenceHandle",
    "RefusalEvidenceStore",
    "authority_generation",
    "authority_digest",
    "authority_digest_for_snapshot",
    "class_absence_record",
    "feature_absence_record",
    "frozen_ledger_matches_authority",
    "graph_identity",
    "resolve_refusal_evidence_handle",
    "validate_evidence_ids",
    "evidence_id_matches_record",
    "evidence_record_matches_authority",
]
