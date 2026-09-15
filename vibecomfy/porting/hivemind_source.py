"""Resolve one Hivemind workflow into the normal local import input.

Hivemind is the public workflow catalogue.  This module implements only the
small pull boundary needed by ``vibecomfy import``; it never mirrors or
indexes the public corpus locally.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


_EVIDENCE_RE = re.compile(
    r"^hivemind:(?P<table>external_resources):(?P<row_id>[^/?# :]+)$"
)
_URI_RE = re.compile(
    r"^hivemind://(?P<table>resource|resources|workflow|workflows|external_resources)/"
    r"(?P<row_id>[^/?# :]+)(?:/revisions/(?P<revision>[^/?# :]+))?$"
)


@dataclass(frozen=True, slots=True)
class HivemindSource:
    """One fetched workflow and the identity of its local snapshot."""

    source_bytes: bytes
    workflow_id: str
    evidence_id: str
    revision: str | None
    title: str | None = None

    @property
    def provenance(self) -> dict[str, str]:
        digest = "sha256:" + hashlib.sha256(self.source_bytes).hexdigest()
        return {
            "origin_kind": "hivemind",
            "origin_uri": self.evidence_id,
            # A natural row ID is mutable. When no provider revision is
            # available, identify the exact local snapshot by its bytes.
            "origin_pin": self.revision or f"snapshot:{digest}",
            "source_digest": digest,
        }


def evidence_id_for_reference(reference: str) -> str | None:
    """Normalize the supported Hivemind reference forms, if any."""
    if not isinstance(reference, str):
        return None
    value = reference.strip()
    if _EVIDENCE_RE.fullmatch(value):
        return value
    match = _URI_RE.fullmatch(value)
    if match:
        return f"hivemind:external_resources:{match.group('row_id')}"
    return None


def revision_for_reference(reference: str) -> str | None:
    """Return an optional expected revision from a Hivemind URI.

    The current Hivemind get API resolves a natural row ID; this selector is
    verified against the returned row and does not retrieve historical data.
    """
    if not isinstance(reference, str):
        return None
    match = _URI_RE.fullmatch(reference.strip())
    return match.group("revision") if match else None


def _workflow_json(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for container_key, json_key in (
        ("payload", "workflow_json"),
        ("payload", "workflow"),
        ("metadata", "workflow_json"),
        ("metadata", "workflow"),
    ):
        container = row.get(container_key)
        if isinstance(container, Mapping):
            candidate = container.get(json_key)
            if isinstance(candidate, Mapping):
                return _thaw_jsonish(candidate)
    return None


def _thaw_jsonish(value: Any) -> Any:
    """Convert frozen ToolResult JSON back to plain JSON containers.

    Hivemind tool results freeze nested mappings and lists at the tool
    boundary.  The importer needs ordinary dict/list values before it can
    serialize the workflow deterministically.
    """
    if isinstance(value, Mapping):
        return {str(key): _thaw_jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_jsonish(item) for item in value]
    return value


def fetch_hivemind_source(reference: str, *, timeout: float = 10.0) -> HivemindSource:
    """Fetch exactly one workflow record through the existing Hivemind tool."""
    evidence_id = evidence_id_for_reference(reference)
    if evidence_id is None:
        raise ValueError(
            "unsupported Hivemind reference; use "
            "hivemind:external_resources:<id> or hivemind://resource/<id>"
        )
    requested_revision = revision_for_reference(reference)

    from vibecomfy.executor.hivemind_tools import hivemind_get

    result = hivemind_get(evidence_id, timeout=timeout)
    status = getattr(result, "status", None)
    status_value = getattr(status, "value", status)
    if status_value != "ok":
        diagnostics = getattr(result, "diagnostics", ())
        detail = str(diagnostics[0]) if diagnostics else "Hivemind did not return the workflow"
        raise ValueError(f"could not fetch {evidence_id}: {detail}")
    body = getattr(result, "result", None)
    row = body.get("row") if isinstance(body, Mapping) else None
    if not isinstance(row, Mapping):
        raise ValueError(f"Hivemind record {evidence_id} did not contain a workflow row")
    workflow = _workflow_json(row)
    if workflow is None:
        raise ValueError(f"Hivemind record {evidence_id} does not contain workflow JSON")

    # Hivemind stores workflow data as JSON rather than formatting-sensitive
    # files. Canonical UTF-8 bytes give the pulled revision a reproducible
    # source representation and digest in the local bundle.
    source_bytes = json.dumps(
        workflow,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    revision_value = (
        row.get("revision_id")
        or row.get("revision")
        or metadata.get("revision_id")
        or metadata.get("revision")
        or payload.get("revision_id")
        or payload.get("revision")
    )
    revision = str(revision_value) if revision_value else None
    if requested_revision is not None and revision != requested_revision:
        raise ValueError(
            f"Hivemind record {evidence_id} resolved revision {revision!r}, "
            f"not requested revision {requested_revision!r}"
        )
    title = row.get("title") or row.get("name")
    workflow_id = str(row.get("id") or evidence_id.rsplit(":", 1)[-1])
    return HivemindSource(
        source_bytes=source_bytes,
        workflow_id=workflow_id,
        evidence_id=evidence_id,
        revision=revision,
        title=str(title) if title else None,
    )


__all__ = [
    "HivemindSource",
    "evidence_id_for_reference",
    "fetch_hivemind_source",
    "revision_for_reference",
]
