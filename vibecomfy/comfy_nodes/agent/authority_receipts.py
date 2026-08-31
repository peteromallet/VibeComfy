"""Authority receipts and replay verification for applyable agent-edit turns.

This module implements the core Sprint 1 replay authority path.  Before any
response becomes applyable, the server replays the immutable submit graph plus
the cumulative normalized V2 delta envelope through ``interpret`` + emit and
requires exact equality with the persisted candidate.  The receipt (including
all hashes and the replay verdict) is persisted under a per-turn immutable
``authority/`` namespace so that redacted audit views never become replay
authority.

Fail-closed contract:
    * If replay cannot be performed (missing submit graph, missing delta,
      corrupted candidate, interpret/emit error), the receipt records
      ``replay_ok=False`` and the response must be made non-applyable.
    * If replay succeeds but the recomputed candidate hash does not exactly
      match the persisted candidate hash, the receipt records
      ``replay_ok=False, candidate_matches=False`` and the response must be
      made non-applyable.
    * Only when ``replay_ok=True`` **and** ``candidate_matches=True`` may a
      response carry applyability.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.ingest.normalize import door_get_nodes

from .candidate_transaction import (
    AUTHORITY_RECEIPT_DELTA_SCHEMA,
    build_schema_witness,
    content_hash,
    missing_touched_class_types,
    schema_provider_from_witness,
    validate_schema_witness,
)
from .session import (
    _write_response_immutable,
    canonical_json_bytes,
    payload_hash,
    structural_graph_hash,
)

_LOGGER = logging.getLogger(__name__)

AUTHORITY_RECEIPT_CONTRACT_VERSION = "authority_receipt_v2"
AUTHORITY_NAMESPACE = "authority"
AUTHORITY_RECEIPT_FILENAME = "receipt.json"


# ---------------------------------------------------------------------------
# Receipt data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayReceipt:
    """Outcome of replaying ``apply(submit_graph, cumulative_delta)``."""

    replay_ok: bool
    candidate_matches: bool
    recomputed_candidate_hash: str | None
    persisted_candidate_hash: str | None
    error: str | None = None
    op_count: int = 0
    verification_kind: str | None = None
    # P1-REPLAY-HASH-DOMAIN: the frozen per-node widget-name roster this
    # replay consumed, keyed by RAW submit-graph node id.  Recorded so the
    # hash domain of record stays reproducible from persisted bytes alone;
    # ``None`` on receipts minted before P1 (domain was implicit).
    frozen_name_table: Mapping[str, tuple[str, ...]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_ok": self.replay_ok,
            "candidate_matches": self.candidate_matches,
            "recomputed_candidate_hash": self.recomputed_candidate_hash,
            "persisted_candidate_hash": self.persisted_candidate_hash,
            "error": self.error,
            "op_count": self.op_count,
            "verification_kind": self.verification_kind,
            "frozen_name_table": (
                {
                    str(node_id): [name if isinstance(name, str) else None for name in names]
                    for node_id, names in self.frozen_name_table.items()
                    if isinstance(names, (list, tuple))
                }
                if isinstance(self.frozen_name_table, Mapping) and self.frozen_name_table
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReplayReceipt":
        raw_table = data.get("frozen_name_table")
        frozen_table: dict[str, tuple[str, ...]] | None = None
        if isinstance(raw_table, Mapping) and raw_table:
            parsed: dict[str, tuple[str, ...]] = {}
            for node_id, names in raw_table.items():
                if isinstance(node_id, str) and isinstance(names, (list, tuple)):
                    # RR1-FIX-REV2: an explicitly represented EMPTY roster is
                    # legitimate per-node coverage — keep it on round-trip
                    # instead of dropping the row.
                    parsed[node_id] = tuple(
                        str(name) for name in names if isinstance(name, str) and name
                    )
            frozen_table = parsed or None
        return cls(
            replay_ok=bool(data.get("replay_ok", False)),
            candidate_matches=bool(data.get("candidate_matches", False)),
            recomputed_candidate_hash=data.get("recomputed_candidate_hash"),
            persisted_candidate_hash=data.get("persisted_candidate_hash"),
            error=data.get("error"),
            op_count=int(data.get("op_count", 0)),
            verification_kind=(data.get("verification_kind") if isinstance(data.get("verification_kind"), str) else None),
            frozen_name_table=frozen_table,
        )


@dataclass(frozen=True)
class ResponseMetadataHashes:
    """Hashes of response metadata fields for tamper detection."""

    response_hash: str | None
    eligibility_hash: str | None
    outcome_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_hash": self.response_hash,
            "eligibility_hash": self.eligibility_hash,
            "outcome_hash": self.outcome_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResponseMetadataHashes":
        return cls(
            response_hash=data.get("response_hash"),
            eligibility_hash=data.get("eligibility_hash"),
            outcome_hash=data.get("outcome_hash"),
        )


@dataclass(frozen=True)
class AuthorityReceipt:
    """Immutable authority receipt persisted under the per-turn ``authority/``
    namespace.

    Fields:
        contract_version: Schema contract identifier.
        schema_version: V2 delta schema version at receipt time.
        session_id: Session identifier.
        turn_id: Turn identifier.
        submit_graph_hash: Hash of the submit graph (canonical JSON).
        submit_graph_bytes_sha256: SHA-256 of the canonical submit graph bytes.
        accepted_batch_digest: Hash of the sole durable Δ (accepted_batch).
        cumulative_delta_hash: Same digest; reference to accepted_batch, not ops.
        candidate_hash: Hash of the persisted candidate graph.
        replay: Replay verification result.
        response_metadata: Hashes of response metadata fields.
        created_at: ISO-8601 timestamp.
    """

    schema_version: str
    session_id: str
    turn_id: str
    submit_graph_hash: str | None
    submit_graph_bytes_sha256: str | None
    accepted_batch_digest: str | None
    cumulative_delta_hash: str | None
    candidate_hash: str | None
    schema_witness: dict[str, Any] | None
    schema_witness_hash: str | None
    replay: ReplayReceipt
    response_metadata: ResponseMetadataHashes
    created_at: str
    contract_version: str = field(
        default=AUTHORITY_RECEIPT_CONTRACT_VERSION,
        init=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "submit_graph_hash": self.submit_graph_hash,
            "submit_graph_bytes_sha256": self.submit_graph_bytes_sha256,
            "accepted_batch_digest": self.accepted_batch_digest,
            "cumulative_delta_hash": self.cumulative_delta_hash,
            "candidate_hash": self.candidate_hash,
            "schema_witness": self.schema_witness,
            "schema_witness_hash": self.schema_witness_hash,
            "replay": self.replay.to_dict(),
            "response_metadata": self.response_metadata.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuthorityReceipt":
        replay_data = data.get("replay")
        replay = ReplayReceipt.from_dict(replay_data) if isinstance(replay_data, Mapping) else ReplayReceipt(
            replay_ok=False, candidate_matches=False,
            recomputed_candidate_hash=None, persisted_candidate_hash=None,
        )
        meta_data = data.get("response_metadata")
        meta = ResponseMetadataHashes.from_dict(meta_data) if isinstance(meta_data, Mapping) else ResponseMetadataHashes(
            response_hash=None, eligibility_hash=None, outcome_hash=None,
        )
        digest = data.get("accepted_batch_digest")
        if not isinstance(digest, str):
            digest = data.get("cumulative_delta_hash")
        schema_witness = data.get("schema_witness")
        receipt = cls(
            schema_version=(
                data.get("schema_version")
                if isinstance(data.get("schema_version"), str)
                else ""
            ),
            session_id=data.get("session_id", ""),
            turn_id=data.get("turn_id", ""),
            submit_graph_hash=data.get("submit_graph_hash"),
            submit_graph_bytes_sha256=data.get("submit_graph_bytes_sha256"),
            accepted_batch_digest=digest if isinstance(digest, str) else None,
            cumulative_delta_hash=data.get("cumulative_delta_hash"),
            candidate_hash=data.get("candidate_hash"),
            schema_witness=(
                dict(schema_witness) if isinstance(schema_witness, Mapping) else None
            ),
            schema_witness_hash=data.get("schema_witness_hash"),
            replay=replay,
            response_metadata=meta,
            created_at=data.get("created_at", ""),
        )
        object.__setattr__(
            receipt,
            "contract_version",
            data.get("contract_version")
            if isinstance(data.get("contract_version"), str)
            else "",
        )
        return receipt

    @property
    def is_applyable(self) -> bool:
        """Only ``True`` when replay succeeded and candidate matches exactly."""
        witness_ok, _ = validate_schema_witness(self.schema_witness)
        digest = self.accepted_batch_digest or self.cumulative_delta_hash
        return (
            self.contract_version == AUTHORITY_RECEIPT_CONTRACT_VERSION
            and self.schema_version == "2.0.0"
            and isinstance(digest, str)
            and len(digest) == 64
            and self.cumulative_delta_hash == digest
            and witness_ok
            and self.schema_witness_hash == self.schema_witness.get("witness_hash")
            and self.replay.replay_ok
            and self.replay.candidate_matches
            and isinstance(self.replay.verification_kind, str)
        )


# ---------------------------------------------------------------------------
# Strict V2 validation and digest ownership
# ---------------------------------------------------------------------------

#: The only replay proofs a persisted V2 receipt may carry.
_ALLOWED_REPLAY_VERIFICATION_KINDS = frozenset(
    {"delta_replay", "layout_structural_noop"}
)

_HEX64_RE = re.compile(r"[0-9a-f]{64}")


class AuthorityReceiptValidationError(ValueError):
    """A raw persisted receipt failed strict ``authority_receipt_v2`` validation."""


def _require_hex64(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise AuthorityReceiptValidationError(f"invalid_hash:{field_name}")
    return value


def validate_authority_receipt_v2(raw: Mapping[str, Any]) -> AuthorityReceipt:
    """Strictly validate a raw persisted receipt BEFORE dataclass coercion.

    DEEP-AUDIT-FIX-2-REVISION-2: ``AuthorityReceipt.from_dict`` coerces fields
    through ``bool(...)``/``int(...)`` and silently defaults missing values, so
    it can never be the first gate over untrusted bytes.  This validator checks
    exact raw JSON types first and only then returns the coerced dataclass.

    Contract shape only: a receipt that validates here may still record a
    FAILED replay (``is_applyable`` False).  Verdict enforcement is the
    binding decision of the persisted-pair loader, not of this validator.
    """
    if not isinstance(raw, Mapping):
        raise AuthorityReceiptValidationError("not_a_mapping")
    if raw.get("contract_version") != AUTHORITY_RECEIPT_CONTRACT_VERSION:
        raise AuthorityReceiptValidationError("unsupported_contract_version")
    if raw.get("schema_version") != AUTHORITY_RECEIPT_DELTA_SCHEMA:
        raise AuthorityReceiptValidationError("unsupported_delta_schema_version")
    for identity_field in ("session_id", "turn_id"):
        value = raw.get(identity_field)
        if not isinstance(value, str) or not value:
            raise AuthorityReceiptValidationError(f"missing_{identity_field}")
    required_hashes = (
        "submit_graph_hash",
        "submit_graph_bytes_sha256",
        "accepted_batch_digest",
        "cumulative_delta_hash",
        "candidate_hash",
        "schema_witness_hash",
    )
    for hash_field in required_hashes:
        _require_hex64(raw.get(hash_field), hash_field)
    if raw["accepted_batch_digest"] != raw["cumulative_delta_hash"]:
        raise AuthorityReceiptValidationError("accepted_batch_digest_mismatch")

    witness = raw.get("schema_witness")
    witness_ok, _witness_error = validate_schema_witness(witness)
    if not witness_ok or not isinstance(witness, Mapping):
        raise AuthorityReceiptValidationError("invalid_schema_witness")
    if raw["schema_witness_hash"] != witness.get("witness_hash"):
        raise AuthorityReceiptValidationError("schema_witness_hash_mismatch")

    replay = raw.get("replay")
    if not isinstance(replay, Mapping):
        raise AuthorityReceiptValidationError("missing_replay")
    replay_ok = replay.get("replay_ok")
    candidate_matches = replay.get("candidate_matches")
    if type(replay_ok) is not bool or type(candidate_matches) is not bool:
        raise AuthorityReceiptValidationError("replay_boolean_type")
    replay_error = replay.get("error")
    if replay_error is not None and not isinstance(replay_error, str):
        raise AuthorityReceiptValidationError("invalid_replay_error_type")
    op_count = replay.get("op_count", 0)
    if type(op_count) is not int or op_count < 0:
        raise AuthorityReceiptValidationError("invalid_op_count_type")
    # P1-REPLAY-HASH-DOMAIN: optional recorded name domain.  Receipts minted
    # before P1 omit the key and stay valid; when present it must be a
    # raw-node-id → roster mapping.  Recording an INVALID shape fails closed
    # rather than silently ignoring tampered evidence.
    frozen_name_table = replay.get("frozen_name_table")
    if frozen_name_table is not None:
        if not isinstance(frozen_name_table, Mapping) or not frozen_name_table:
            raise AuthorityReceiptValidationError("invalid_frozen_name_table")
        for node_id, names in frozen_name_table.items():
            if not isinstance(node_id, str) or not node_id:
                raise AuthorityReceiptValidationError("invalid_frozen_name_table")
            if not isinstance(names, list):
                raise AuthorityReceiptValidationError("invalid_frozen_name_table")
    verification_kind = replay.get("verification_kind")
    if verification_kind not in _ALLOWED_REPLAY_VERIFICATION_KINDS:
        raise AuthorityReceiptValidationError("unknown_verification_kind")
    recomputed = replay.get("recomputed_candidate_hash")
    persisted = replay.get("persisted_candidate_hash")
    for replay_hash_field, replay_hash_value in (
        ("recomputed_candidate_hash", recomputed),
        ("persisted_candidate_hash", persisted),
    ):
        if replay_hash_value is not None:
            _require_hex64(replay_hash_value, replay_hash_field)
    # Internally consistent replay candidate hashes: a successful matching
    # replay must identify ONE candidate on both sides and record no error.
    if replay_ok and candidate_matches:
        if (
            not isinstance(recomputed, str)
            or not isinstance(persisted, str)
            or recomputed != persisted
        ):
            raise AuthorityReceiptValidationError("replay_candidate_hash_mismatch")
        if replay_error is not None:
            raise AuthorityReceiptValidationError("replay_error_on_success")

    metadata = raw.get("response_metadata")
    if not isinstance(metadata, Mapping):
        raise AuthorityReceiptValidationError("missing_response_metadata")
    for metadata_field in ("response_hash", "eligibility_hash", "outcome_hash"):
        value = metadata.get(metadata_field)
        if value is not None:
            _require_hex64(value, f"response_metadata.{metadata_field}")
    created_at = raw.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        raise AuthorityReceiptValidationError("missing_created_at")

    return AuthorityReceipt.from_dict(raw)


def authority_receipt_digest_v2(
    receipt: AuthorityReceipt | Mapping[str, Any],
) -> str:
    """Return THE digest of the complete persisted receipt dictionary.

    DEEP-AUDIT-FIX-2-REVISION-2: sole owner of the receipt digest.  SHA-256
    over the canonical JSON of ``AuthorityReceipt.to_dict()``.  Minting
    (``session.record_idempotent_response``), binding
    (``_artifact_store.load_bound_candidate_replay_evidence``), and any future
    verifier MUST call this function instead of duplicating
    ``payload_hash(receipt.to_dict())`` locally, so mint and verify can never
    diverge.
    """
    data = (
        receipt.to_dict()
        if isinstance(receipt, AuthorityReceipt)
        else dict(receipt)
    )
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


# ---------------------------------------------------------------------------
# Replay verification
# ---------------------------------------------------------------------------


def _extract_submit_graph(request_payload: Any) -> dict[str, Any] | None:
    """Extract the submit graph from a request payload."""
    if not isinstance(request_payload, Mapping):
        return None
    graph = request_payload.get("graph")
    if isinstance(graph, Mapping):
        return dict(graph)
    # Some payloads may use the payload itself as the graph.
    if "nodes" in request_payload or "last_node_id" in request_payload:
        return dict(request_payload)
    return None


def _extract_delta_ops_from_envelope(envelope: Any) -> tuple[Any, ...]:
    """Parse new authority through the explicit ``delta_v1`` boundary."""
    if not isinstance(envelope, Mapping):
        raise ValueError("delta envelope must be an object")

    from vibecomfy.porting.edit.ops import normalize_delta_v1

    # Pass the complete canonical envelope through the canonical parser.  In
    # particular, dropping schema_version here turns every valid V2 envelope
    # into a rejected legacy wrapper.  The old code then swallowed that parse
    # error and replayed zero operations, making mutation evidence look like an
    # identity apply.
    schema_version = envelope.get("schema_version")
    if not isinstance(schema_version, str):
        raise ValueError("delta_v1 requires an explicit schema_version")
    return normalize_delta_v1({
        "delta_contract": "delta_v1",
        "wire_version": schema_version,
        "ops": envelope.get("ops"),
    }).ops


def _op_touched_uids(ops: tuple[Any, ...]) -> frozenset[str]:
    """Collect the node uids a parsed delta touches (RR1-FIX-1)."""

    touched: set[str] = set()
    for op in ops:
        uid = getattr(op, "uid", None)
        if isinstance(uid, str) and uid:
            touched.add(uid)
        for attr in ("target", "source"):
            ref = getattr(op, attr, None)
            ref_uid = getattr(ref, "uid", None) if ref is not None else None
            if isinstance(ref_uid, str) and ref_uid:
                touched.add(ref_uid)
    return frozenset(touched)

def _submit_graph_existing_uids(submit_graph: Any) -> frozenset[str]:
    """Node identities already present in the raw submit graph.

    RR1-FIX-REV (RRSYN-1): the mint-time name-domain guard needs to know
    whether a delta touches a node the user's graph ALREADY had. Both the
    ``vibecomfy_uid`` property and the raw numeric id are accepted identities;
    over-matching only widens fail-closed coverage, never opens it.
    """
    if not isinstance(submit_graph, Mapping):
        return frozenset()
    nodes = door_get_nodes(submit_graph)
    if not isinstance(nodes, list):
        return frozenset()
    uids: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        properties = node.get("properties")
        uid = (
            properties.get("vibecomfy_uid")
            if isinstance(properties, Mapping)
            else None
        )
        if isinstance(uid, str) and uid:
            uids.add(uid)
        elif node.get("id") is not None:
            uids.add(str(node["id"]))
    return frozenset(uids)


def _submit_graph_uid_to_node_id(submit_graph: Any) -> dict[str, str]:
    """Map each raw submit-graph node identity to its node id key.

    RR1-FIX-REV2: the frozen name table is keyed by raw node id, while ops
    address nodes by uid (``vibecomfy_uid`` when present, else the id).  The
    mint guard needs both directions to decide whether a touched existing
    node has an explicit table row.
    """
    if not isinstance(submit_graph, Mapping):
        return {}
    key_by_uid: dict[str, str] = {}
    for node in door_get_nodes(submit_graph, []) or []:
        if not isinstance(node, Mapping):
            continue
        properties = node.get("properties")
        uid = (
            properties.get("vibecomfy_uid")
            if isinstance(properties, Mapping)
            else None
        )
        if not (isinstance(uid, str) and uid):
            uid = str(node["id"]) if node.get("id") is not None else None
        if isinstance(uid, str) and uid and node.get("id") is not None:
            key_by_uid[uid] = str(node["id"])
    return key_by_uid


def _verify_seal_coverage(
    workflow: Any,
    name_authority: Mapping[str, Any] | None,
    ops: tuple[Any, ...],
) -> str | None:
    """Require an explicit frozen-table row for EVERY touched EXISTING node.

    RR1-FIX-1 sealed the recorded roster onto the fresh ingest;
    RR1-FIX-REV2 closes the remaining fail-open: a non-empty table covering
    only SOME touched nodes used to verify, because this loop iterated table
    rows instead of the touched set. Now the direction is inverted — every
    node the delta touches that already exists in the replayed graph must
    have an EXPLICIT row in ``name_authority`` (an explicitly empty roster is
    legitimate; absence of a row is not). A missing row means replay would
    interpret names under a domain the receipt never pinned: reject before
    replay. ``name_authority=None`` remains the legacy unpinned self-
    consistent-domain path; the mint guard in ``build_authority_receipt``
    refuses such receipts for op-bearing deltas over existing nodes.
    """
    if not ops or not isinstance(name_authority, Mapping):
        return None
    from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid

    effective = frozen_widget_names_by_uid(workflow)
    touched = _op_touched_uids(ops)
    for node_id, node in getattr(workflow, "nodes", {}).items():
        uid = getattr(node, "uid", None) or str(node_id)
        if uid not in touched:
            continue
        row = name_authority.get(str(node_id))
        if row is None:
            return (
                "frozen_name_table_row_missing: node "
                f"{node_id} (uid {uid}) is touched by the delta but the "
                "frozen name-domain of record has no row for it"
            )
        normalized = tuple(
            str(name) for name in row if isinstance(name, str) and name
        )
        current = effective.get(str(uid)) or ()
        if current != normalized:
            return (
                f"name_domain_divergence: node {node_id} (uid {uid}) sealed as "
                f"{current!r} but the frozen authority of record is {normalized!r}"
            )
    return None


def _seal_frozen_name_domain(
    workflow: Any,
    name_authority: Mapping[str, Any] | None,
) -> Any:
    """Seal the retained hash domain's widget-name roster over a fresh ingest.

    P1-REPLAY-HASH-DOMAIN (R1).  ``name_authority`` maps RAW submit-graph
    node ids to positional compact-widget rosters.  For every node present in
    both the table and the freshly-ingested workflow this:

    1. overwrites the ingest-sealed ``widget_names_sig`` roster — interpret,
       apply, and emit read exactly this frozen table afterwards; and
    2. re-keys the node's IR widget-literal fields onto the frozen roster
       (positional alignment comes from the retained raw widget payload), so
       provider-derived field names assigned at ingest cannot shift which
       value occupies which emitted slot.

    Nodes absent from the table keep their own ingest evidence.  The snapshot
    is replaced wholesale via ``dataclasses.replace`` — the same pattern as
    ``bind_snapshot_lineage`` — and ``widget_names_sig`` is excluded from the
    semantic preimage, so digest equality is unchanged.
    """
    if not isinstance(name_authority, Mapping):
        return workflow
    from dataclasses import replace as _dc_replace

    from vibecomfy.ingest.snapshot import (
        WORKFLOW_SNAPSHOT_METADATA_KEY,
        snapshot_of,
    )

    snapshot = snapshot_of(workflow)
    if snapshot is None:
        return workflow
    field_snapshot = getattr(snapshot, "field_snapshot", None)
    if not isinstance(field_snapshot, Mapping):
        return workflow

    patched: dict[str, Any] = {}
    hit = False
    for node_id, node in getattr(workflow, "nodes", {}).items():
        key = getattr(node, "uid", None) or node_id
        current = field_snapshot.get(key)
        roster = name_authority.get(str(node_id))
        if current is None:
            continue
        if isinstance(roster, (list, tuple)):
            names = tuple(str(name) for name in roster if name)
            patched[str(key)] = {**current, "widget_names_sig": names}
            hit = True
            if names:
                _rekey_ir_widget_fields(node, names)
            continue
        patched[str(key)] = current
    if not hit:
        return workflow
    metadata = getattr(workflow, "metadata", None)
    if isinstance(metadata, dict):
        metadata[WORKFLOW_SNAPSHOT_METADATA_KEY] = _dc_replace(
            snapshot, field_snapshot=patched
        )
    return workflow


def _rekey_ir_widget_fields(node: Any, names: tuple[str, ...]) -> None:
    """Rebuild one node's IR widget-literal fields onto the frozen roster.

    Ingest keys compact ``widgets_values`` positionally against
    ``metadata.input_aliases`` — a full-input-order list that interleaves
    socket names (``MODEL_TASK_ID``, ``FILE_3D*``) and hidden API names with
    widget names. A leading socket alias therefore SWALLOWS widget value 0
    and shifts every literal one slot left (RR1-FIX-1 root cause). The
    retained raw widget payload is the positional truth, so literals are
    rebuilt from ``zip(raw_values, frozen_roster)``; genuine link-shaped
    entries are preserved and never overwritten.
    """
    inputs = getattr(node, "inputs", None)
    if not isinstance(inputs, dict) or not inputs or not names:
        return
    raw_widgets = getattr(node, "raw_widgets", None)
    values = list(getattr(raw_widgets, "values", None) or ())
    if not values:
        return

    def _is_link(value: Any) -> bool:
        return isinstance(value, (list, tuple)) and len(value) == 2

    rebuilt: dict[str, Any] = {
        key: value for key, value in inputs.items() if _is_link(value)
    }
    for value, name in zip(values, names):
        if not isinstance(name, str) or not name:
            continue
        rebuilt[name] = value
    node.inputs = rebuilt


def canonical_frozen_name_table(
    submit_graph: Mapping[str, Any] | None,
    *,
    schema_provider: Any = None,
) -> dict[str, tuple[str, ...]]:
    """Derive THE frozen widget-name domain of record for one replay.

    P1-REPLAY-HASH-DOMAIN (R1): the domain is a deterministic function of
    the persisted bytes — the submit graph plus the frozen admission schema
    snapshot reconstructed by the caller (``schema_provider_from_witness``).
    One canonical offline ingest seals each node's compact-widget roster
    once; the resulting table is what ``build_authority_receipt`` records
    on the receipt and stamps into every replay, so verification never
    depends on ambient object_info or a drifted second provider.

    RR1-FIX-REV2: every node the fresh ingest SEALED gets an explicit row —
    a widgetless node's empty roster is represented as ``()`` so per-node
    coverage can distinguish "sealed, zero names" from "never sealed".
    Nodes absent from the ingest's field snapshot get no row, and any
    ingest or provider failure yields an empty table; the receipt MINT then
    fails closed (``frozen_name_table_unavailable``) for op-bearing deltas
    touching such an existing node instead of silently replaying unpinned.
    """
    if not isinstance(submit_graph, Mapping) or not submit_graph:
        return {}
    try:
        from vibecomfy.ingest.normalize import from_ui
        from vibecomfy.ingest.snapshot import snapshot_of

        workflow = from_ui(
            dict(submit_graph),
            schema_provider=schema_provider,
            use_comfy_converter=False,
        )
        snapshot = snapshot_of(workflow)
        field_snapshot = getattr(snapshot, "field_snapshot", None)
        if not isinstance(field_snapshot, Mapping):
            return {}
        table: dict[str, tuple[str, ...]] = {}
        for node_id, node in getattr(workflow, "nodes", {}).items():
            key = str(getattr(node, "uid", None) or node_id)
            snap = field_snapshot.get(key)
            if snap is None:
                continue
            names = snap.get("widget_names_sig") if isinstance(snap, Mapping) else None
            table[str(node_id)] = tuple(
                str(name) for name in names if isinstance(name, str) and name
            ) if isinstance(names, (list, tuple)) else ()
        return table
    except Exception:  # noqa: BLE001 - derivation must never break minting
        return {}


def _unresolved_named_field_reason(
    ops: tuple[Any, ...],
    workflow: Any,
    *,
    name_authority: Mapping[str, Any] | None,
) -> str | None:
    """Return a typed rejection reason for ambiguous/unresolvable named
    widget writes, or ``None`` when every named field resolves to exactly
    one raw position (RRSYN2-5)."""
    from vibecomfy.porting.edit.ops import SetNodeFieldOp
    from vibecomfy.porting.widgets.compact_resolver import (
        widget_index_for_field,
    )

    def _row_for(node_id: str, uid: str) -> tuple[str | None, ...] | None:
        if not isinstance(name_authority, Mapping):
            return None
        row = name_authority.get(node_id)
        if row is None:
            row = name_authority.get(uid)
        return tuple(row) if isinstance(row, (list, tuple)) else None

    for op in ops:
        if not isinstance(op, SetNodeFieldOp):
            continue
        field = str(getattr(op.target, "field_path", "") or "")
        target_uid = str(getattr(op.target, "uid", "") or "")
        if not field or not target_uid:
            continue
        for node_id, node in getattr(workflow, "nodes", {}).items():
            uid = str(getattr(node, "uid", "") or "") or str(node_id)
            if uid != target_uid and str(node_id) != target_uid:
                continue
            # Same row-lookup direction as _verify_seal_coverage: the frozen
            # table is keyed by replayed node id; fall back to sealed uid.
            authority_row = _row_for(str(node_id), uid)
            if widget_index_for_field(
                node,
                field,
                name_authority=(
                    {uid: authority_row} if authority_row is not None else None
                ),
                strict_name_authority=True,
            ) is None:
                return f"field_resolution_unresolved:{uid}.{field}"
            break
    return None

def recompute_apply(
    submit_graph: Mapping[str, Any],
    cumulative_delta_envelope: Mapping[str, Any] | None,
    *,
    schema_provider: Any = None,
    name_authority: Mapping[str, Any] | None = None,
) -> tuple[bool, Any, str | None, int]:
    """Recompute ``apply(submit_graph, cumulative_delta)`` server-side.

    Returns ``(ok, candidate, error, op_count)``.

    Ops are applied **one at a time, in declared order**, feeding each result
    forward. This deliberately mirrors the batch-REPL executor, which builds the
    candidate it returns to the user by applying statements (and their ops)
    sequentially against a live working graph. A single all-at-once
    ``apply_delta(submit, all_ops)`` resolves every ``add_node`` against the
    pre-mutation graph (before any removes land); on multi-add edits that changes
    the collision-avoidance landscape, so node placement diverges from the
    executor's strict program order. That divergence is purely in non-semantic
    ``pos`` coordinates, but it is enough to trip the authority byte-hash and
    reject a candidate that passed every other gate. Applying the delta the same
    way the executor did makes the authority verify the graph the user actually
    receives. Determinism and fail-closed semantics are unchanged: the replay is
    still a pure function of ``(submit_graph, ops)`` and still rejects any
    candidate that does not equal its declared delta.

    P1-REPLAY-HASH-DOMAIN (R1): ``name_authority`` — the frozen per-node
    widget-name roster of the retained hash domain (raw node id → names).
    When supplied, it is sealed over the fresh ingest BEFORE any name
    resolution happens, so interpret/apply/emit consume exactly the domain
    the receipt pins instead of re-deriving widget names under whatever
    provider this verification runs with.  Hash-equality itself is untouched:
    only the INPUTS to the hasher are pinned.
    """
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit._interpret import interpret
    from vibecomfy.porting.emit.ui import emit_ui_json, pin_untouched_ui

    if cumulative_delta_envelope is None:
        # No delta → candidate is the submit graph itself (identity apply).
        return True, dict(submit_graph), None, 0

    raw_ops = cumulative_delta_envelope.get("ops")
    declared_op_count = len(raw_ops) if isinstance(raw_ops, list) else 0
    try:
        ops = _extract_delta_ops_from_envelope(cumulative_delta_envelope)
    except Exception as exc:
        # A present envelope is authority evidence.  If it is malformed, never
        # reinterpret it as an empty/identity delta; fail the receipt closed.
        return False, None, f"invalid_delta_envelope: {exc}", declared_op_count

    try:
        workflow = from_ui(
            dict(submit_graph),
            schema_provider=schema_provider,
            # Executor ingest contract (EditSession._workflow_from_ui,
            # porting/edit/session.py; gate twin _workflow_from_ui,
            # porting/edit/_gates.py): always the offline normalizer,
            # never the host's comfy converter. Replay must select the
            # same converter as live ingest or a host where the comfy
            # converter imports AND diverges would make every receipt
            # fail closed with candidate_hash_mismatch.
            use_comfy_converter=False,
        )
        # P1-R1: pin the hash domain before admit/interpret/emit run.  With no
        # explicit table the freshly-sealed ingest roster remains authoritative
        # (single self-consistent domain), preserving prior behavior.
        workflow = _seal_frozen_name_domain(workflow, name_authority)
        # RR1-FIX-1: the sealed domain must EQUAL the recorded authority on
        # every op-touched node. A silent skip (node absent from the fresh
        # ingest snapshot, empty roster, count-mismatched literals) means
        # replay would interpret under a divergent domain — reject instead.
        divergence = _verify_seal_coverage(workflow, name_authority, ops)
        if divergence:
            return False, None, divergence, len(ops)
        # RRSYN2-5: a NAMED field that cannot resolve to EXACTLY ONE raw
        # widget position must fail the receipt closed BEFORE any landing.
        # Reporting batch_ok=true and discovering the ambiguity only at
        # receipt time minted authority for rows that never matched live
        # materialization.  The same sealed frozen name table that live
        # materialization consumed decides here.
        field_resolution_error = _unresolved_named_field_reason(
            ops,
            workflow,
            name_authority=name_authority,
        )
        if field_resolution_error:
            return False, None, field_resolution_error, len(ops)
        from vibecomfy.porting.edit.admit import (
            AdmissionRejected,
            admission_snapshot_for,
            admit_operations,
        )

        admitted = admit_operations(
            admission_snapshot_for(workflow, schema_provider),
            ops,
            working_workflow=workflow,
        )
        if isinstance(admitted, AdmissionRejected):
            return False, None, admitted.typed_reason, len(ops)
        for op in ops:
            step = interpret(workflow, (op,), schema_provider=schema_provider)
            if not step.ok:
                return False, None, "interpret_failed", len(ops)
            workflow = step.workflow
        working = pin_untouched_ui(
            submit_graph,
            emit_ui_json(
                workflow,
                schema_provider=schema_provider,
                include_virtual_wires=True,
                prior_ui_payload=submit_graph,
            ),
            ops,
        )
    except Exception as exc:
        return False, None, f"interpret_error: {exc}", len(ops)

    # RR1-FIX-1 (phantom-landing guard): a declared, accepted named write that
    # resolves to NO emitted byte change never landed. Counting it as a
    # landing minted authority for graphs nothing changed (8800a9: Gate A
    # certified "1 edit verified" while candidate == submit byte-for-byte).
    # Fail closed with a typed reason; honest non-apply terminals carry no
    # ops and are unaffected.
    if ops and structural_graph_hash(working) == structural_graph_hash(submit_graph):
        return False, None, "phantom_landing_no_byte_change", len(ops)
    return True, working, None, len(ops)


def verify_replay(
    submit_graph: Mapping[str, Any] | None,
    cumulative_delta_envelope: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    *,
    schema_provider: Any = None,
    name_authority: Mapping[str, Any] | None = None,
) -> ReplayReceipt:
    """Verify that replaying the delta on the submit graph equals the candidate.

    Returns a :class:`ReplayReceipt`.  The receipt is fail-closed: any missing
    input, error, or hash mismatch produces ``replay_ok=False``.
    """
    if submit_graph is None:
        return ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash=None,
            error="missing_submit_graph",
            verification_kind="delta_replay",
        )

    persisted_hash = structural_graph_hash(candidate) if candidate is not None else None

    ok, recomputed, error, op_count = recompute_apply(
        submit_graph,
        cumulative_delta_envelope,
        schema_provider=schema_provider,
        name_authority=name_authority,
    )
    if not ok or recomputed is None:
        return ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash=persisted_hash,
            error=error or "recompute_failed",
            op_count=op_count,
            verification_kind="delta_replay",
        )

    from vibecomfy.executor.revision_evidence import (
        changed_link_has_malformed_endpoints,
        semantic_graph_hash,
    )
    if (
        isinstance(candidate, Mapping)
        and changed_link_has_malformed_endpoints(submit_graph, candidate)
    ):
        return ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash=persisted_hash,
            error="malformed_link",
            op_count=op_count,
            verification_kind="delta_replay",
        )

    recomputed_hash = structural_graph_hash(recomputed)
    semantic_matches = (
        isinstance(candidate, Mapping)
        and isinstance(recomputed, Mapping)
        and semantic_graph_hash(dict(candidate)) == semantic_graph_hash(dict(recomputed))
    )
    matches = recomputed_hash == persisted_hash and semantic_matches
    error_value: str | None = None if matches else "candidate_hash_mismatch"
    return ReplayReceipt(
        replay_ok=True,
        candidate_matches=matches,
        recomputed_candidate_hash=recomputed_hash,
        persisted_candidate_hash=persisted_hash,
        error=error_value,
        op_count=op_count,
        verification_kind="delta_replay",
    )


def _layout_authority_evidence(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return server-produced layout-only evidence for a prepared candidate.

    Layout reorganisation is deliberately outside the semantic V2 delta
    language: it changes node geometry and groups, not executable workflow
    state.  Such candidates therefore need a distinct authority proof instead
    of being misinterpreted as an empty/identity semantic delta.
    """
    change_details = response.get("change_details")
    if (
        response.get("route") == "reorganise"
        and isinstance(change_details, Mapping)
        and change_details.get("layout_only") is True
    ):
        evidence = change_details.get("structural_noop_evidence")
        return evidence if isinstance(evidence, Mapping) else None

    layout = response.get("layout_reorganisation")
    if (
        isinstance(layout, Mapping)
        and layout.get("candidate_prepared") is True
        and layout.get("advisory") is False
    ):
        evidence = layout.get("evidence")
        return evidence if isinstance(evidence, Mapping) else None
    return None


def verify_layout_candidate(
    submit_graph: Mapping[str, Any] | None,
    cumulative_delta_envelope: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    *,
    schema_provider: Any = None,
    name_authority: Mapping[str, Any] | None = None,
) -> ReplayReceipt | None:
    """Verify a layout-only candidate on top of the semantic replay result.

    Returns ``None`` when the response does not claim the dedicated layout
    contract.  A claimed but invalid layout contract returns a fail-closed
    receipt.  The semantic delta is replayed first (identity for an explicit
    reorganise turn), then the server structural projection must be identical
    before and after layout application.  That projection includes node types,
    modes, wired endpoints, and widget values while intentionally excluding
    positions and groups.
    """
    evidence = _layout_authority_evidence(response)
    if evidence is None:
        return None

    persisted_hash = payload_hash(candidate) if candidate is not None else None
    ok, semantic_candidate, error, op_count = recompute_apply(
        submit_graph or {},
        cumulative_delta_envelope,
        schema_provider=schema_provider,
        name_authority=name_authority,
    )
    if not ok or semantic_candidate is None:
        return ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash=persisted_hash,
            error=error or "layout_semantic_replay_failed",
            op_count=op_count,
            verification_kind="layout_structural_noop",
        )

    evidence_ok = (
        evidence.get("candidate_available") is True
        and evidence.get("layout_only_structural_noop") is True
        and evidence.get("patch_apply_error") in (None, {})
    )
    before_structural = structural_graph_hash(semantic_candidate)
    after_structural = structural_graph_hash(candidate)
    structural_match = (
        isinstance(before_structural, str)
        and before_structural == after_structural
    )
    matches = bool(candidate is not None and evidence_ok and structural_match)
    return ReplayReceipt(
        replay_ok=matches,
        candidate_matches=matches,
        recomputed_candidate_hash=persisted_hash if matches else payload_hash(semantic_candidate),
        persisted_candidate_hash=persisted_hash,
        error=None if matches else "layout_authority_mismatch",
        op_count=op_count,
        verification_kind="layout_structural_noop",
    )


# ---------------------------------------------------------------------------
# Receipt building
# ---------------------------------------------------------------------------


def _now() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _compute_response_metadata_hashes(response: Mapping[str, Any]) -> ResponseMetadataHashes:
    """Compute hashes of key response metadata fields."""
    eligibility = response.get("eligibility") if isinstance(response.get("eligibility"), Mapping) else None
    outcome = response.get("outcome") if isinstance(response.get("outcome"), Mapping) else None
    return ResponseMetadataHashes(
        response_hash=payload_hash(response),
        eligibility_hash=payload_hash(eligibility) if eligibility is not None else None,
        outcome_hash=payload_hash(outcome) if outcome is not None else None,
    )


def build_authority_receipt(
    *,
    session_id: str,
    turn_id: str,
    submit_graph: Mapping[str, Any] | None,
    cumulative_delta_envelope: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    schema_version: str = "",
    schema_provider: Any = None,
) -> AuthorityReceipt:
    """Build an authority receipt by replaying the delta on the submit graph.

    This is the canonical entry point.  The receipt records the replay verdict
    and all hashes needed for tamper detection.
    """
    schema_witness = build_schema_witness(
        schema_provider=schema_provider,
        submit_graph=submit_graph,
        candidate_payload=candidate,
        delta_envelope=cumulative_delta_envelope,
    )
    persisted_schema_provider = schema_provider_from_witness(schema_witness)
    # P1-REPLAY-HASH-DOMAIN (R1): derive THE name domain of record once, from
    # the frozen admission snapshot this witness reconstructs, and consume the
    # SAME table in the replay below.  The table is recorded on the receipt so
    # any future verification reproduces the identical hash domain from
    # persisted bytes instead of re-resolving names under an ambient provider.
    frozen_name_table = canonical_frozen_name_table(
        submit_graph,
        # Use original ingest-bound provider (carries frozen snapshot) not witness-reconstructed
        schema_provider=schema_provider,
    )
    # RR1-FIX-REV (RRSYN-1) / RR1-FIX-REV2: a delta that touches an EXISTING
    # node may never mint authority without an explicit frozen name-domain
    # row of record FOR THAT NODE.  The REV guard fired only when the whole
    # derived table was empty, so a roster for one node laundered an
    # unpinned replay of a different touched node.  Coverage is now checked
    # per touched existing node against the table keys (raw node ids): a
    # missing row — including the whole-table-absent case — is fail-closed.
    # Only genuine zero-op identity terminals (no envelope, no parsed ops)
    # may stay unpinned.  A malformed envelope is left to the replay layer's
    # own typed ``invalid_delta_envelope`` failure.
    guard_touched_existing: tuple[str, ...] = ()
    if isinstance(cumulative_delta_envelope, Mapping):
        try:
            guard_ops = _extract_delta_ops_from_envelope(
                cumulative_delta_envelope
            )
        except Exception:  # noqa: BLE001 - parse errors fail closed in replay
            guard_ops = ()
        if guard_ops:
            touched_existing = _op_touched_uids(guard_ops) & (
                _submit_graph_existing_uids(submit_graph)
            )
            key_by_uid = _submit_graph_uid_to_node_id(submit_graph)
            guard_touched_existing = tuple(
                sorted(
                    uid
                    for uid in touched_existing
                    if key_by_uid.get(uid) not in frozen_name_table
                )
            )
    missing_touched = missing_touched_class_types(
        schema_witness=schema_witness,
        submit_graph=submit_graph,
        candidate_payload=candidate,
        delta_envelope=cumulative_delta_envelope,
    )
    if missing_touched:
        raw_ops = (
            cumulative_delta_envelope.get("ops")
            if isinstance(cumulative_delta_envelope, Mapping)
            else None
        )
        replay = ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash=(
                structural_graph_hash(candidate)
                if isinstance(candidate, Mapping)
                else None
            ),
            error="missing_touched_schema:" + ",".join(missing_touched),
            op_count=len(raw_ops) if isinstance(raw_ops, list) else 0,
            verification_kind="delta_replay",
        )
    elif guard_touched_existing:
        raw_ops = (
            cumulative_delta_envelope.get("ops")
            if isinstance(cumulative_delta_envelope, Mapping)
            else None
        )
        replay = ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash=(
                structural_graph_hash(candidate)
                if isinstance(candidate, Mapping)
                else None
            ),
            error=(
                "frozen_name_table_unavailable: no frozen widget-name "
                "domain row of record for touched existing "
                f"node(s) {list(guard_touched_existing[:8])}; refusing to "
                "replay unpinned"
            ),
            op_count=len(raw_ops) if isinstance(raw_ops, list) else 0,
            verification_kind="delta_replay",
        )
    else:
        replay = verify_layout_candidate(
            submit_graph,
            cumulative_delta_envelope,
            candidate,
            response,
            schema_provider=persisted_schema_provider,
            name_authority=frozen_name_table or None,
        ) or verify_replay(
            submit_graph,
            cumulative_delta_envelope,
            candidate,
            schema_provider=persisted_schema_provider,
            name_authority=frozen_name_table or None,
        )
    # Record the domain of record on the replay verdict itself (both the
    # missing-touched-schema fail-closed receipt and a verified one).
    from dataclasses import replace as _dc_replace

    replay = _dc_replace(
        replay,
        frozen_name_table=dict(frozen_name_table) if frozen_name_table else None,
    )

    submit_graph_hash = payload_hash(submit_graph) if submit_graph is not None else None
    submit_bytes = canonical_json_bytes(submit_graph) if submit_graph is not None else None
    submit_graph_bytes_sha256 = (
        hashlib.sha256(submit_bytes).hexdigest() if submit_bytes is not None else None
    )

    delta_envelope_dict = (
        dict(cumulative_delta_envelope) if isinstance(cumulative_delta_envelope, Mapping) else None
    )
    # DEEP-AUDIT-REVIEW-2-001: ONE canonical semantic Δ digest.  The
    # numeric-canonical view (``content_hash``) is authoritative for the
    # delta-hash chain and is consumed unchanged by candidate construction,
    # both validation layers, and rehydration — minting the exact-rendering
    # ``payload_hash`` here made integral-float deltas fail as
    # ``accepted_batch_digest_mismatch`` on the semantic verify side.
    # ``payload_hash`` remains only where it hashes a genuinely byte-meaningful
    # envelope applied identically at mint and verify (receipt digest, graph
    # and response-metadata hashes).
    cumulative_delta_hash = (
        content_hash(delta_envelope_dict) if delta_envelope_dict is not None else None
    )
    candidate_hash = payload_hash(candidate) if candidate is not None else None

    return AuthorityReceipt(
        schema_version=schema_version,
        session_id=session_id,
        turn_id=turn_id,
        submit_graph_hash=submit_graph_hash,
        submit_graph_bytes_sha256=submit_graph_bytes_sha256,
        accepted_batch_digest=cumulative_delta_hash,
        cumulative_delta_hash=cumulative_delta_hash,
        candidate_hash=candidate_hash,
        schema_witness=schema_witness,
        schema_witness_hash=schema_witness.get("witness_hash"),
        replay=replay,
        response_metadata=_compute_response_metadata_hashes(response),
        created_at=_now(),
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def authority_dir_for(turn_dir: Path) -> Path:
    """Return the immutable ``authority/`` namespace path for a turn."""
    return turn_dir / AUTHORITY_NAMESPACE


def authority_receipt_path(turn_dir: Path) -> Path:
    """Return the path to the authority receipt JSON file."""
    return authority_dir_for(turn_dir) / AUTHORITY_RECEIPT_FILENAME


def write_authority_receipt(turn_dir: Path, receipt: AuthorityReceipt) -> Path:
    """Persist the authority receipt under the per-turn ``authority/`` namespace.

    The receipt is written once and is treated as immutable.  If a receipt
    already exists it is **not** overwritten — the existing receipt is the
    authority of record.
    """
    path = authority_receipt_path(turn_dir)
    if not _write_response_immutable(path, receipt.to_dict()):
        existing = load_authority_receipt(turn_dir)
        if existing is None or existing.to_dict() != receipt.to_dict():
            raise ValueError(
                f"Authority receipt collision for turn_dir={turn_dir}."
            )
        return path
    # Authority evidence is operational state, not a redacted audit view. The
    # create-exclusive publish above also prevents concurrent writers from
    # replacing authority after both observed an absent path.
    persisted = load_authority_receipt(turn_dir)
    if persisted is None or persisted.to_dict() != receipt.to_dict():
        raise OSError(f"Authority receipt did not persist exactly at {path}.")
    return path


def load_authority_receipt(turn_dir: Path) -> AuthorityReceipt | None:
    """Load the authority receipt from the per-turn ``authority/`` namespace."""
    path = authority_receipt_path(turn_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.warning("Failed to load authority receipt at %s: %s", path, exc)
        return None
    if not isinstance(data, Mapping):
        return None
    return AuthorityReceipt.from_dict(data)


# ---------------------------------------------------------------------------
# Response stamping (fail-closed)
# ---------------------------------------------------------------------------

#: Authority-bearing fields that must be stripped when replay fails.
_APPLYABILITY_FIELDS = (
    "canvas_apply_allowed",
    "queue_allowed",
    "apply_allowed",
    "apply_eligible",
)


def _response_claims_applyable(response: Mapping[str, Any]) -> bool:
    """Return ``True`` when the response is asserting applyability.

    This recognizes every public compatibility spelling, including both
    nested eligibility objects.  Receipt failure stamping is unconditional;
    this helper remains the canonical detector for callers that need to
    classify the response's original claim.
    """
    if response.get("apply_eligible") is True:
        return True
    if response.get("canvas_apply_allowed") is True:
        return True
    if response.get("apply_allowed") is True:
        return True
    if response.get("queue_allowed") is True:
        return True
    for eligibility_field in ("eligibility", "apply_eligibility"):
        eligibility = response.get(eligibility_field)
        if isinstance(eligibility, Mapping) and eligibility.get("applyable") is True:
            return True
    return False


def _candidate_payload_has_content(value: Any) -> bool:
    """True when a candidate-authority payload carries any non-empty content.

    P1-R2: candidate authority requires a NON-EMPTY payload.  Empty mappings,
    empty sequences, and containers that collapse to emptiness once their
    empty children are stripped — e.g. ``{}``, ``{"graph": {}}``,
    ``{"nodes": [], "links": []}`` — carry no candidate authority.  Any leaf
    value (string, number, bool, nested content) counts as content, so real
    candidates and malformed-but-populated payloads still fail closed.
    """
    if value is None:
        return False
    if isinstance(value, Mapping):
        return any(_candidate_payload_has_content(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_candidate_payload_has_content(item) for item in value)
    return True


def _has_accepted_batch_content(response: Mapping[str, Any]) -> bool:
    """True when the response admits at least one accepted delta entry."""
    batch = response.get("accepted_batch")
    if not isinstance(batch, (list, tuple)):
        return False
    return any(isinstance(item, Mapping) and item for item in batch)

def _is_schema_gap_error(error: str) -> bool:
    """True for schema-gap failures that must remain fail-closed even with a gate pass."""
    return (
        error.startswith("missing_touched_schema:")
        or error.startswith("frozen_name_table_unavailable")
        or "name_domain_divergence" in error
    )


def _response_has_landed_gate_pass(response: Mapping[str, Any]) -> bool:
    """Trust Judgment S1: detect a Gate A/B pass that must not be nulled as no_changes.

    A landed delta is authoritative when Gate A (replayed interpret + emit) and
    Gate B (compile isomorphism) have passed locally.  Replay divergence at
    authority time (candidate_hash_mismatch, emit drift, phantom guard off-by-byte)
    must not null such a candidate as ``authority_rejected`` / ``no_changes``.

    Evidence hierarchy (minimal, explicit-bug focus):
      * ``change_details.landed_operation_count > 0`` plus ``gate_a``/``gate_b``
        when present — direct Gate A/B proof from ``_change_details_payload``.
      * ``accepted_batch`` non-empty + candidate payload — fallback when gate
        fields are absent (legacy fixtures, early tests).
      * ``change_details.batch_turns[*].landed_op_count > 0`` is also landed.

    Schema-gap errors (missing_touched_schema, frozen table, name divergence)
    are NOT gate-pass successes and remain fail-closed.
    """
    cd = response.get("change_details")
    landed: int | None = None
    gate_a: Any = None
    gate_b: Any = None
    if isinstance(cd, Mapping):
        raw_landed = cd.get("landed_operation_count")
        if isinstance(raw_landed, int):
            landed = raw_landed
        gate_a = cd.get("gate_a")
        gate_b = cd.get("gate_b")
        if (landed is None or landed <= 0) and isinstance(cd.get("batch_turns"), (list, tuple)):
            for turn in cd.get("batch_turns") or []:  # type: ignore[union-attr]
                if isinstance(turn, Mapping):
                    cnt = turn.get("landed_op_count")
                    if isinstance(cnt, int) and cnt > 0:
                        landed = cnt
                        break
    has_batch = _has_accepted_batch_content(response)
    if (landed is None or landed <= 0) and has_batch:
        landed = 1
    if landed is None or landed <= 0:
        return False
    has_candidate = any(
        _candidate_payload_has_content(response.get(key))
        for key in ("graph", "candidate", "candidate_graph", "candidate_transaction")
    )
    if not has_candidate:
        return False
    if gate_a is None and gate_b is None:
        return True
    def _gate_ok(value: Any) -> bool:
        if isinstance(value, bool):
            return value is True
        if isinstance(value, Mapping):
            for gate_key in (
                "ok",
                "passed",
                "is_ok",
                "edit_scope_ok",
                "isomorphic_ok",
                "python_load_ok",
                "ui_fidelity_ok",
            ):
                if value.get(gate_key) is True:
                    return True
            return False
        return False
    if gate_a is not None and _gate_ok(gate_a):
        return True
    if gate_b is not None and _gate_ok(gate_b):
        return True
    return False



def stamp_response_with_authority(
    response: dict[str, Any],
    receipt: AuthorityReceipt,
) -> dict[str, Any]:
    """Stamp the response with authority receipt reference and enforce fail-closed.

    The ``authority_receipt`` summary is always added so that every durable
    edit turn carries an immutable receipt reference.

    Every non-applyable receipt projects one truthful failure envelope.  This
    is deliberately independent of the response's original applyability
    claims: a failed replay must not retain success narration or a candidate
    outcome merely because one compatibility gate was omitted.  The rejected
    candidate graph and accepted batch remain available as audit evidence.
    """
    stamped = dict(response)
    stamped["authority_receipt"] = {
        "contract_version": receipt.contract_version,
        "schema_version": receipt.schema_version,
        "submit_graph_hash": receipt.submit_graph_hash,
        "submit_graph_bytes_sha256": receipt.submit_graph_bytes_sha256,
        "cumulative_delta_hash": receipt.cumulative_delta_hash,
        "candidate_hash": receipt.candidate_hash,
        "replay_ok": receipt.replay.replay_ok,
        "candidate_matches": receipt.replay.candidate_matches,
        "replay_error": receipt.replay.error,
        "op_count": receipt.replay.op_count,
        "verification_kind": receipt.replay.verification_kind,
        "response_hash": receipt.response_metadata.response_hash,
        "created_at": receipt.created_at,
    }

    replay_error = str(receipt.replay.error or "")
    missing_touched = (
        tuple(
            item
            for item in replay_error.removeprefix("missing_touched_schema:").split(",")
            if item
        )
        if replay_error.startswith("missing_touched_schema:")
        else ()
    )
    if not receipt.is_applyable:
        # Preserve non-applyable terminal clarifications instead of rewriting
        # them as authority_replay_mismatch.  Two shapes are preserved:
        #   1. discovery-stop clarify (report key present); and
        #   2. ANY pure clarification: original outcome kind is ``clarify``,
        #      the graph is unchanged, the canonical applyability detector
        #      (_response_claims_applyable) finds NO claim, the accepted
        #      batch is empty, and NO candidate authority exists in any
        #      recognized spelling (``graph``, ``candidate``,
        #      ``candidate_graph``, ``candidate_transaction``) — there is
        #      nothing to replay, so the question must survive verbatim.
        #      A malformed edit response carrying an apply claim or candidate
        #      authority under a clarify label still fails closed.
        _orig_outcome = response.get("outcome") if isinstance(response.get("outcome"), Mapping) else None
        _report = response.get("report") if isinstance(response.get("report"), Mapping) else None
        _accepted_batch = response.get("accepted_batch")
        # P1-R2 (empty graph ≠ candidate): a recognized carrier counts as
        # candidate authority only when it carries NON-EMPTY payload content.
        # ``candidate={"graph": {}}`` and other all-empty containers are NOT
        # authority — a pure clarify carrying one must survive verbatim.
        _has_candidate_authority = any(
            _candidate_payload_has_content(response.get(key))
            for key in (
                "graph",
                "candidate",
                "candidate_graph",
                "candidate_transaction",
            )
        )
        _is_pure_clarify = (
            isinstance(_orig_outcome, Mapping)
            and _orig_outcome.get("kind") == "clarify"
            and response.get("graph_unchanged") is True
            and not _accepted_batch
            and not _response_claims_applyable(response)
            and not _has_candidate_authority
        )
        # RR1-FIX(2) — honest non-apply terminal: an empty accepted delta with
        # NO candidate authority in any spelling and a replay-clean identity
        # (replay of the empty batch succeeded, zero ops, no candidate hash on
        # either side) is a genuine non-apply terminal. The persisted
        # candidate_matches=False on such receipts is an artifact of comparing
        # a null candidate against the recomputed empty apply — NOT a replay
        # failure — so the turn keeps its outcome kind and its substantive
        # final message instead of being laundered into a fabricated
        # authority error (Hotshot/AnimateDiff/face-detect finale evidence).
        _replay_clean_identity = (
            receipt.replay.replay_ok is True
            and receipt.replay.op_count == 0
            and receipt.candidate_hash is None
            and receipt.replay.persisted_candidate_hash is None
        )
        _is_honest_non_apply_terminal = (
            isinstance(_orig_outcome, Mapping)
            and _orig_outcome.get("kind") in {"noop", "clarify", "requires_custom_nodes"}
            and response.get("graph_unchanged") is True
            and not _has_accepted_batch_content(response)
            and not _response_claims_applyable(response)
            and not _has_candidate_authority
            and _replay_clean_identity
        )
        if _is_pure_clarify or _is_honest_non_apply_terminal or (
            isinstance(_orig_outcome, Mapping)
            and _orig_outcome.get("kind") == "clarify"
            and isinstance(_report, Mapping)
            and "discovery_stop" in _report
        ):
            return stamped
        # S1 — Trust Judgment: landed Δ that passed Gate A/B must not be nulled as no_changes.
        # When Gate A (replayed interpret + emit, pinned @ :883) and Gate B (compile
        # isomorphism) passed locally — evidenced by change_details.landed_operation_count
        # + gate_a/b or accepted_batch + candidate — authority replay divergence
        # (candidate_hash_mismatch / emit drift from schema-less best-effort slots
        #  at vibecomfy/ingest/normalize.py:1746 + emit_ready.py:1577) must persist
        # candidate.ui → final.ui instead of authority_rejected.  Never null a
        # Gate A/B pass as no_changes.  Scenarios: character-replacement,
        # e8c20a, d93baf, wan-vace (staged/threaded).  Schema-gap and phantom
        # landings remain fail-closed.
        if replay_error != "phantom_landing_no_byte_change" and not _is_schema_gap_error(replay_error):
            if _response_has_landed_gate_pass(response):
                return stamped
            _debug = response.get("debug") if isinstance(response.get("debug"), Mapping) else None
            if isinstance(_debug, Mapping):
                _gates = _debug.get("gates") if isinstance(_debug.get("gates"), Mapping) else None
                if isinstance(_gates, Mapping) and any(
                    _gates.get(k) is True
                    for k in ("edit_scope_ok", "isomorphic_ok", "python_load_ok", "ui_fidelity_ok")
                ):
                    if _has_accepted_batch_content(response) and _has_candidate_authority:
                        return stamped
        # Fail closed: force applyability fields to False. Row 4, not row 3:
        from vibecomfy.comfy_nodes.agent.contracts import stamp_terminal_state
        from vibecomfy.porting.edit.checkpoint import (
            TERMINAL_STATE_AUTHORITY_REJECTED,
        )

        stamped["canvas_apply_allowed"] = False
        stamped["queue_allowed"] = False
        stamped["apply_allowed"] = False
        stamped["apply_eligible"] = False
        stamped["graph_unchanged"] = True
        stamped["no_candidate_reason"] = "authority_replay_mismatch"
        eligibility_payload = {
            "applyable": False,
            "reason": TERMINAL_STATE_AUTHORITY_REJECTED,
            "message": (
                "Server replay verification failed; candidate is not authoritative."
            ),
        }
        for eligibility_field in ("eligibility", "apply_eligibility"):
            eligibility = stamped.get(eligibility_field)
            eligibility = dict(eligibility) if isinstance(eligibility, Mapping) else {}
            eligibility.update(eligibility_payload)
            stamped[eligibility_field] = eligibility
        if missing_touched:
            classes = ", ".join(missing_touched)
            message = (
                "I couldn't safely prepare this edit because authoritative node "
                f"schema evidence is unavailable for: {classes}. The graph is unchanged."
            )
            stamped["message"] = message
            stamped["schema_witness_error"] = {
                "code": "missing_touched_schema",
                "class_types": list(missing_touched),
            }
        else:
            message = (
                "I couldn't safely prepare this edit because server replay "
                "verification failed. The graph is unchanged."
            )
            stamped["message"] = message
        # Preserve typed failure kind through authority path instead of
        # collapsing to ValidationError. Missing touched schema is SCHEMA_GAP.
        prior_outcome = response.get("outcome") if isinstance(response.get("outcome"), dict) else {}
        prior_kind = prior_outcome.get("failure_kind") if isinstance(prior_outcome, dict) else None
        if missing_touched:
            authority_failure_kind = "SchemaGap"
        elif isinstance(prior_kind, str) and prior_kind in {"ModelMistake", "Unrepresentable", "SchemaGap", "ValidationError", "ProviderError"}:
            authority_failure_kind = prior_kind
        else:
            authority_failure_kind = "ValidationError"
        stamped["outcome"] = {
            "kind": "error",
            "failure_kind": authority_failure_kind,
            "stage": "authority",
            "retryable": False,
            "next_action": "none",
            "graph_unchanged": True,
            "question": message,
            "clarification": {"message": message},
        }
        stamped["internal_outcome"] = {
            "kind": "failure",
            "failure_kind": authority_failure_kind,
            "stage": "authority",
            "retryable": False,
            "next_action": "none",
            "graph_unchanged": True,
        }
        candidate = stamped.get("candidate")
        rejected_candidate = None
        if isinstance(candidate, Mapping):
            rejected_candidate = dict(candidate)
            rejected_candidate["state"] = "rejected"
        elif stamped.get("graph") is not None or stamped.get("accepted_batch") is not None:
            rejected_candidate = {
                "graph": dict(stamped["graph"]) if isinstance(stamped.get("graph"), Mapping) else stamped.get("graph"),
                "accepted_batch": list(stamped["accepted_batch"])
                if isinstance(stamped.get("accepted_batch"), (list, tuple))
                else stamped.get("accepted_batch"),
                "state": "rejected",
            }
        audit = dict(stamped.get("audit") or {}) if isinstance(stamped.get("audit"), Mapping) else {}
        if rejected_candidate is not None:
            audit["rejected_candidate"] = rejected_candidate
        stamped["audit"] = audit
        # Row 4: rejected product is audit-only. Public keys must not carry it.
        stamped.pop("candidate", None)
        stamped.pop("graph", None)
        stamped.pop("accepted_batch", None)
        stamped.pop("candidate_graph", None)
        stamped.pop("candidate_transaction", None)

        stamped = stamp_terminal_state(
            stamped,
            terminal_state=TERMINAL_STATE_AUTHORITY_REJECTED,
            eligibility=eligibility_payload,
            reason=TERMINAL_STATE_AUTHORITY_REJECTED,
            evidence_refs=("authority_receipt",),
            accepted_delta_ids=(),
        )
    elif (
        receipt.replay.replay_ok
        and receipt.replay.candidate_matches
        # P1-R3 (apply eligibility gate): semantic applyability additionally
        # requires a non-empty accepted batch whenever a REAL delta was
        # declared.  A matched replay over a declared delta with nothing
        # admitted must not project ``applyable`` — fail-closed per §25 item 2.
        # Two documented exemptions keep prior contracts intact:
        #   * layout structural-noop turns — their empty batch is the
        #     documented contract (no executable graph edit) and their proof
        #     is the dedicated layout evidence, not the delta chain; and
        #   * zero-op identity matches — nothing was mutated, so there is no
        #     unverified product to demote; identity-turn applyability stays
        #     owned by the apply-gate layer (porting/edit/apply_gate.py).
        and (
            receipt.replay.verification_kind == "layout_structural_noop"
            or receipt.replay.op_count == 0
            or _has_accepted_batch_content(response)
        )
    ):
        from vibecomfy.comfy_nodes.agent.contracts import stamp_terminal_state
        from vibecomfy.porting.edit.checkpoint import TERMINAL_STATE_APPLIED

        eligibility_payload = stamped.get("eligibility")
        if not isinstance(eligibility_payload, Mapping):
            eligibility_payload = stamped.get("apply_eligibility")
        if not isinstance(eligibility_payload, Mapping):
            eligibility_payload = {
                "applyable": True,
                "reason": TERMINAL_STATE_APPLIED,
                "message": "Gateway-admitted accepted delta with verified replay.",
            }
        else:
            eligibility_payload = dict(eligibility_payload)
            eligibility_payload.setdefault("applyable", True)
            eligibility_payload.setdefault("reason", TERMINAL_STATE_APPLIED)
        stamped = stamp_terminal_state(
            stamped,
            terminal_state=TERMINAL_STATE_APPLIED,
            eligibility=eligibility_payload,
            reason=TERMINAL_STATE_APPLIED,
            evidence_refs=("authority_receipt",),
        )
    elif (
        receipt.replay.replay_ok
        and receipt.replay.candidate_matches
        # P1-R3: a DECLARED, replay-matched delta whose accepted batch is
        # empty.  Not an authority error — the delta verified but nothing was
        # admitted — so the response survives, yet applyability is forced
        # false: ``apply_eligible`` may only be true with a non-empty
        # accepted batch AND a matching replay.  Zero-op identity matches and
        # layout structural-noop turns never reach this branch.
        and receipt.replay.verification_kind != "layout_structural_noop"
        and receipt.replay.op_count > 0
    ):
        from vibecomfy.comfy_nodes.agent.contracts import stamp_terminal_state
        from vibecomfy.porting.edit.checkpoint import TERMINAL_STATE_NO_CANDIDATE

        stamped["canvas_apply_allowed"] = False
        stamped["queue_allowed"] = False
        stamped["apply_allowed"] = False
        stamped["apply_eligible"] = False
        eligibility_payload = {
            "applyable": False,
            "reason": "no_accepted_batch",
            "message": (
                "Replay verification matched, but no delta was admitted; "
                "there is nothing to apply."
            ),
        }
        for eligibility_field in ("eligibility", "apply_eligibility"):
            existing = stamped.get(eligibility_field)
            existing = dict(existing) if isinstance(existing, Mapping) else {}
            existing.update(eligibility_payload)
            stamped[eligibility_field] = existing
        stamped = stamp_terminal_state(
            stamped,
            terminal_state=TERMINAL_STATE_NO_CANDIDATE,
            eligibility=eligibility_payload,
            reason="no_accepted_batch",
            evidence_refs=("authority_receipt",),
        )

    return stamped




def build_and_persist_authority_receipt(
    *,
    turn_dir: Path,
    session_id: str,
    turn_id: str,
    request_payload: Any,
    response: dict[str, Any],
    schema_version: str = "",
    schema_provider: Any = None,
) -> tuple[AuthorityReceipt, dict[str, Any]]:
    """Build, persist, and stamp an authority receipt for a durable turn.

    Returns ``(receipt, stamped_response)``.  The stamped response enforces
    fail-closed semantics when replay verification fails.
    """
    submit_graph = _extract_submit_graph(request_payload)
    from vibecomfy.comfy_nodes.agent._frag_state import derived_accepted_delta_envelope

    cumulative_delta_envelope = derived_accepted_delta_envelope(response)
    candidate = response.get("graph")
    if not isinstance(candidate, Mapping):
        candidate = response.get("candidate", {}).get("graph") if isinstance(
            response.get("candidate"), Mapping
        ) else None
        if not isinstance(candidate, Mapping):
            candidate = None

    receipt = build_authority_receipt(
        session_id=session_id,
        turn_id=turn_id,
        submit_graph=submit_graph,
        cumulative_delta_envelope=cumulative_delta_envelope,
        candidate=candidate,
        response=response,
        schema_version=schema_version,
        schema_provider=schema_provider,
    )

    write_authority_receipt(turn_dir, receipt)

    stamped = stamp_response_with_authority(response, receipt)
    return receipt, stamped


__all__ = [
    "AUTHORITY_NAMESPACE",
    "AUTHORITY_RECEIPT_CONTRACT_VERSION",
    "AUTHORITY_RECEIPT_FILENAME",
    "AuthorityReceipt",
    "AuthorityReceiptValidationError",
    "ReplayReceipt",
    "ResponseMetadataHashes",
    "authority_dir_for",
    "authority_receipt_digest_v2",
    "authority_receipt_path",
    "build_and_persist_authority_receipt",
    "build_authority_receipt",
    "canonical_frozen_name_table",
    "load_authority_receipt",
    "recompute_apply",
    "stamp_response_with_authority",
    "validate_authority_receipt_v2",
    "verify_replay",
    "write_authority_receipt",
]
