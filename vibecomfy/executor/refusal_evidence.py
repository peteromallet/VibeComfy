"""Frozen authority evidence for model-selected typed refusals.

The model only receives opaque IDs.  Each ID is deterministic and binds one
absence claim to the graph plus schema authority used for that lookup.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from types import MappingProxyType



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


_LEDGER_TOKEN = object()


class FrozenRefusalLedger(dict[str, dict[str, Any]]):
    """Authenticated evidence mapping produced by one authority snapshot."""

    def __init__(
        self,
        records: Mapping[str, Mapping[str, Any]],
        *,
        graph_digest: str,
        schema_snapshot: Mapping[str, Any],
        schema_content_digest: Any,
        source_identity: int,
        source_generation: str | None,
        owner: Any,
        _token: object | None = None,
    ) -> None:
        capability = getattr(owner, "_capture_capability", None)
        if (
            _token is not _LEDGER_TOKEN
            or not callable(capability)
            or capability() is None
        ):
            raise TypeError("FrozenRefusalLedger must come from authority collection")
        super().__init__((str(key), dict(value)) for key, value in records.items())
        self.graph_digest = graph_digest
        self.schema_content_digest = schema_content_digest
        self.source_identity = source_identity
        self.source_generation = source_generation
        self.authority_source = getattr(owner, "source", None)
        self.schema_snapshot = MappingProxyType(dict(schema_snapshot))
        self._integrity = _ledger_integrity(
            self,
            graph_digest=graph_digest,
            schema_snapshot=self.schema_snapshot,
            schema_content_digest=schema_content_digest,
            source_identity=source_identity,
            source_generation=source_generation,
        )

    @classmethod
    def _from_capture(
        cls,
        records: Mapping[str, Mapping[str, Any]],
        *,
        graph: Any,
        schema_snapshot: Mapping[str, Any],
        schema_content_digest: Any,
        source_identity: int,
        source_generation: str | None,
        owner: Any,
    ) -> "FrozenRefusalLedger":
        return cls(
            records,
            graph_digest=graph_identity(graph),
            schema_snapshot=schema_snapshot,
            schema_content_digest=schema_content_digest,
            source_identity=source_identity,
            source_generation=source_generation,
            owner=owner,
            _token=_LEDGER_TOKEN,
        )

    @classmethod
    def from_collection(cls, *_args: Any, **_kwargs: Any) -> "FrozenRefusalLedger":
        """Reject arbitrary public snapshot construction.

        Production ledgers are minted only by the collector's private token
        path; accepting caller-owned schema snapshots here would turn the
        integrity checksum into self-authentication.
        """
        raise TypeError("FrozenRefusalLedger must be minted by authority capture")

    def integrity_valid(self) -> bool:
        return self._integrity == _ledger_integrity(
            self,
            graph_digest=self.graph_digest,
            schema_snapshot=self.schema_snapshot,
            schema_content_digest=self.schema_content_digest,
            source_identity=self.source_identity,
            source_generation=self.source_generation,
        )


def frozen_ledger_matches_authority(
    ledger: FrozenRefusalLedger,
    *,
    graph: Any,
    authority_source: Any,
) -> bool:
    """Validate a ledger against its captured graph/schema witness only."""
    if not isinstance(ledger, FrozenRefusalLedger):
        return False
    if not ledger.integrity_valid() or ledger.graph_digest != graph_identity(graph):
        return False
    if id(authority_source) != ledger.source_identity:
        return False
    record_classes = tuple(
        str(record.get("class_type"))
        for record in ledger.values()
        if isinstance(record.get("class_type"), str)
    )
    if not isinstance(ledger.source_generation, str) or not ledger.source_generation:
        return False
    if ledger.source_generation.startswith("bounded:"):
        if authority_content_digest(authority_source, record_classes) != ledger.source_generation:
            return False
    elif ledger.source_generation.startswith(("content_digest:", "schemas:")):
        if authority_generation(authority_source) != ledger.source_generation:
            return False
    classes = _graph_classes(graph)
    for key, record in ledger.items():
        if not isinstance(key, str) or key != record.get("evidence_id"):
            return False
        if not evidence_id_matches_record(record):
            return False
        class_type = record.get("class_type")
        if not isinstance(class_type, str):
            return False
        schema = ledger.schema_snapshot.get(class_type)
        if record.get("authority_digest") != authority_digest_for_snapshot(
            graph,
            class_type=class_type,
            schema=schema,
            schema_content_digest=ledger.schema_content_digest,
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
    "authority_generation",
    "authority_digest",
    "authority_digest_for_snapshot",
    "class_absence_record",
    "feature_absence_record",
    "frozen_ledger_matches_authority",
    "graph_identity",
    "validate_evidence_ids",
    "evidence_id_matches_record",
    "evidence_record_matches_authority",
]
