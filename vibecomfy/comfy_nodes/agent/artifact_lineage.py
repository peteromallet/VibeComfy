"""T5.1 artifact lineage manifest.

One digest-linked manifest binds every execution-spine evidence class to the
shared scenario/session/turn/baseline lineage (plan contract 9):

    source commit, request, source representation, workflow snapshot,
    schema snapshot, prompt/tool contract, model/provider/transport,
    research, accepted delta, candidate, replay proof, terminal response,
    assessment.

Design law:

* Every manifest covers ALL link kinds exactly once. A link that could not be
  established is a **fallback row**: it carries a typed reason from the
  per-kind vocabulary below and NO digest, so it can never be mistaken for —
  and can never impersonate — a genuine candidate / final-graph / receipt
  digest.
* Primary rows carry a lowercase 64-hex SHA-256 digest over canonical JSON of
  the linked evidence. No row ever carries graph payloads; the manifest links,
  it does not duplicate.
* ``manifest_digest`` is the SHA-256 over the canonical form of
  ``{schema_version, lineage, rows}``, giving downstream artifacts (terminal
  response, assessment) one stable pointer to cite.

The manifest is built once per executor turn at the single report seam shared
by staged and threaded deliberation; mode never forks the row vocabulary.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent._canonical_contract_primitives import (
    canonical_json_bytes_v1,
)
from vibecomfy.porting.edit.checkpoint import CheckpointLineage, coerce_lineage

ARTIFACT_LINEAGE_SCHEMA_VERSION = "artifact_lineage_v1"

#: Every evidence class the manifest must speak about, exactly once each.
LINK_KINDS: tuple[str, ...] = (
    "source_commit",
    "request",
    "source_representation",
    "workflow_snapshot",
    "schema_snapshot",
    "prompt_tool_contract",
    "model_provider_transport",
    "research",
    "accepted_delta",
    "candidate",
    "replay_proof",
    "terminal_response",
    "assessment",
)

_LINK_KIND_SET = frozenset(LINK_KINDS)

#: Typed fallback vocabulary, keyed by link kind. A fallback row's ``reason``
#: MUST be a member of its kind's set — free-form strings are rejected so a
#: fallback can never smuggle semantics in through prose.
FALLBACK_REASONS: Mapping[str, frozenset[str]] = {
    "source_commit": frozenset({"unavailable_no_source_commit_evidence"}),
    "request": frozenset({"unavailable_request_not_serializable"}),
    "source_representation": frozenset({"not_stamped_in_durable_payload"}),
    "workflow_snapshot": frozenset({"no_retained_snapshot"}),
    "schema_snapshot": frozenset({"no_schema_witness"}),
    "prompt_tool_contract": frozenset({"profile_unresolved"}),
    "model_provider_transport": frozenset({"no_model_attempts_observed"}),
    "research": frozenset({"route_skips_research", "no_research_evidence"}),
    "accepted_delta": frozenset({"non_apply_route", "no_accepted_operations"}),
    "candidate": frozenset({"no_candidate_built", "non_apply_route"}),
    "replay_proof": frozenset(
        {"no_authority_receipt", "replay_not_run", "replay_not_accepted"}
    ),
    "terminal_response": frozenset({"projection_unavailable"}),
    "assessment": frozenset({"assessment_pending"}),
}
ROW_CLASSES = ("primary", "fallback")

#: Exact field contract per row class. ``detail`` is optional evidence prose;
#: every other key outside these sets is a forgery vector and is rejected both
#: at build time and at the serialized-manifest boundary (G5-B4-MUST-002).
_ALLOWED_ROW_KEYS: Mapping[str, frozenset[str]] = {
    "primary": frozenset({"kind", "row_class", "digest", "detail"}),
    "fallback": frozenset({"kind", "row_class", "reason", "detail"}),
}


class ArtifactLineageError(ValueError):
    """A lineage row or manifest violates the typed manifest contract."""


def canonical_lineage_digest(value: Any) -> str:
    """SHA-256 over canonical JSON of *value* (the one digest spelling)."""
    return hashlib.sha256(canonical_json_bytes_v1(value)).hexdigest()


def primary_row(kind: str, digest: str, *, detail: Any = None) -> dict[str, Any]:
    """Build one primary (digest-carrying) row after contract validation."""
    row = _validated_row(kind=kind, row_class="primary", digest=digest, detail=detail)
    return row


def fallback_row(kind: str, reason: str, *, detail: Any = None) -> dict[str, Any]:
    """Build one fallback row: typed reason, NEVER a digest."""
    return _validated_row(kind=kind, row_class="fallback", reason=reason, detail=detail)


def _validated_row(
    *,
    kind: str,
    row_class: str,
    digest: str | None = None,
    reason: str | None = None,
    detail: Any = None,
) -> dict[str, Any]:
    if kind not in _LINK_KIND_SET:
        raise ArtifactLineageError(f"unknown lineage link kind: {kind!r}")
    if row_class not in ROW_CLASSES:
        raise ArtifactLineageError(f"unknown row class for {kind!r}: {row_class!r}")
    if row_class == "primary":
        if not isinstance(digest, str) or not digest:
            raise ArtifactLineageError(f"primary row {kind!r} requires a digest")
        if not _is_sha256_hex(digest):
            raise ArtifactLineageError(
                f"primary row {kind!r} digest must be 64-hex sha256, got {digest!r}"
            )
        if reason is not None:
            raise ArtifactLineageError(f"primary row {kind!r} must not carry a reason")
        row: dict[str, Any] = {"kind": kind, "row_class": "primary", "digest": digest}
    else:
        allowed = FALLBACK_REASONS[kind]
        if reason not in allowed:
            raise ArtifactLineageError(
                f"fallback row {kind!r} reason {reason!r} not in typed vocabulary"
            )
        if digest is not None:
            # The impersonation guard: a fallback row never carries a digest,
            # so it can never be read as a candidate/final-graph/receipt link.
            raise ArtifactLineageError(
                f"fallback row {kind!r} must never carry a digest"
            )
        row = {"kind": kind, "row_class": "fallback", "reason": reason}
    if detail is not None:
        row["detail"] = detail
    return row
def _canonical_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one caller-supplied row and return its canonical form.

    The serialized-manifest impersonation guard lives here: a fallback row
    carrying a ``digest`` (or a primary row carrying a ``reason``, or any row
    carrying fields outside its class contract) is rejected — a fallback can
    never be read as a candidate/final-graph/receipt link, on the way in or on
    the way back out of a serialized manifest.
    """
    kind = row.get("kind")
    row_class = row.get("row_class")
    if row_class not in ROW_CLASSES:
        raise ArtifactLineageError(f"unknown row class for {kind!r}: {row_class!r}")
    unexpected = sorted(set(row) - _ALLOWED_ROW_KEYS[str(row_class)])
    if unexpected:
        raise ArtifactLineageError(
            f"row {kind!r} carries fields outside the {row_class} contract: "
            + ", ".join(unexpected)
        )
    if row_class == "primary":
        clean = _validated_row(
            kind=str(kind), row_class="primary", digest=row.get("digest")
        )
    else:
        clean = _validated_row(
            kind=str(kind),
            row_class="fallback",
            reason=row.get("reason"),
            digest=row.get("digest"),
        )
    detail = row.get("detail")
    if detail is not None:
        clean["detail"] = detail
    return clean




def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def build_artifact_lineage(
    *,
    lineage: CheckpointLineage | Mapping[str, Any] | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze one manifest: shared lineage + exactly one row per link kind."""
    coerced = coerce_lineage(lineage)
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ArtifactLineageError("lineage rows must be mappings")
        kind = row.get("kind")
        if not isinstance(kind, str) or kind not in _LINK_KIND_SET:
            raise ArtifactLineageError(f"row kind {kind!r} is not a lineage link kind")
        if kind in seen:
            raise ArtifactLineageError(f"duplicate lineage rows for kind {kind!r}")
        seen[kind] = _canonical_row(row)
    missing = [kind for kind in LINK_KINDS if kind not in seen]
    if missing:
        raise ArtifactLineageError(
            "artifact lineage manifest is incomplete; missing kinds: "
            + ", ".join(missing)
        )
    ordered = [seen[kind] for kind in LINK_KINDS]
    manifest = {
        "schema_version": ARTIFACT_LINEAGE_SCHEMA_VERSION,
        "lineage": coerced.to_dict(),
        "rows": ordered,
    }
    manifest["manifest_digest"] = canonical_lineage_digest(
        {k: v for k, v in manifest.items()}
    )
    return manifest


def validate_artifact_lineage(value: Any) -> tuple[bool, str | None]:
    """Validate a serialized manifest; ``(ok, error)`` — never raises."""
    if not isinstance(value, Mapping):
        return False, "artifact lineage manifest must be a mapping"
    if value.get("schema_version") != ARTIFACT_LINEAGE_SCHEMA_VERSION:
        return False, "unknown artifact lineage schema_version"
    lineage = value.get("lineage")
    if not isinstance(lineage, Mapping):
        return False, "artifact lineage manifest requires a lineage mapping"
    rows = value.get("rows")
    if not isinstance(rows, list):
        return False, "artifact lineage manifest requires a rows list"
    kinds: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            return False, "lineage rows must be mappings"
        kind = row.get("kind")
        row_class = row.get("row_class")
        if kind not in _LINK_KIND_SET:
            return False, f"unknown lineage link kind: {kind!r}"
        kinds.append(str(kind))
        try:
            # Serialized-boundary guard (G5-B4-MUST-002): reconstruct each row
            # through the canonical contract so a fallback carrying a digest,
            # a primary carrying a reason, or any out-of-contract field is rejected.
            _canonical_row(row)
        except ArtifactLineageError as exc:
            return False, str(exc)
        detail = row.get("detail")
        if detail is not None and not isinstance(
            detail, (str, int, float, bool, list, dict)
        ):
            return False, f"row {kind!r} detail must be JSON-safe"
    if sorted(kinds) != sorted(LINK_KINDS):
        missing = [k for k in LINK_KINDS if k not in kinds]
        extra = [k for k in kinds if k not in LINK_KINDS]
        return False, f"row coverage mismatch (missing={missing}, extra={extra})"
    digest = value.get("manifest_digest")
    if not isinstance(digest, str) or not _is_sha256_hex(digest):
        return False, "manifest_digest must be 64-hex sha256"
    expected = canonical_lineage_digest(
        {
            "schema_version": value["schema_version"],
            "lineage": dict(lineage),
            "rows": [dict(row) for row in rows],
        }
    )
    if digest != expected:
        return False, "manifest_digest does not match manifest content"
    return True, None


__all__ = [
    "ARTIFACT_LINEAGE_SCHEMA_VERSION",
    "ArtifactLineageError",
    "FALLBACK_REASONS",
    "LINK_KINDS",
    "ROW_CLASSES",
    "build_artifact_lineage",
    "canonical_lineage_digest",
    "fallback_row",
    "primary_row",
    "validate_artifact_lineage",
]
