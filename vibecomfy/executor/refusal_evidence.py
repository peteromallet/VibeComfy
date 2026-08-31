"""Frozen authority evidence for model-selected typed refusals.

The model only receives opaque IDs.  Each ID is deterministic and binds one
absence claim to the graph plus schema authority used for that lookup.
"""

from __future__ import annotations

import hashlib
import json
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
    def graph_classes(value: Any, found: set[str]) -> None:
        if isinstance(value, Mapping):
            for key in ("class_type", "type"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    found.add(item.strip().casefold())
            for child in value.values():
                graph_classes(child, found)
        elif isinstance(value, (list, tuple)):
            for child in value:
                graph_classes(child, found)
        elif hasattr(value, "nodes"):
            graph_classes(getattr(value, "nodes"), found)
        elif isinstance(getattr(value, "class_type", None), str):
            found.add(value.class_type.strip().casefold())

    classes: set[str] = set()
    graph_classes(graph, classes)
    payload = {
        "graph_classes": sorted(classes),
        "class_type": class_type,
        "schema": _jsonable(schema),
        "schema_content_digest": getattr(schema_provider, "content_digest", None),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


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
    "authority_digest",
    "class_absence_record",
    "feature_absence_record",
    "validate_evidence_ids",
    "evidence_id_matches_record",
    "evidence_record_matches_authority",
]
