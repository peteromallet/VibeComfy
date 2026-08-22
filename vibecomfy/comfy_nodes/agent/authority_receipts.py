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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .candidate_transaction import (
    build_schema_witness,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_ok": self.replay_ok,
            "candidate_matches": self.candidate_matches,
            "recomputed_candidate_hash": self.recomputed_candidate_hash,
            "persisted_candidate_hash": self.persisted_candidate_hash,
            "error": self.error,
            "op_count": self.op_count,
            "verification_kind": self.verification_kind,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReplayReceipt":
        return cls(
            replay_ok=bool(data.get("replay_ok", False)),
            candidate_matches=bool(data.get("candidate_matches", False)),
            recomputed_candidate_hash=data.get("recomputed_candidate_hash"),
            persisted_candidate_hash=data.get("persisted_candidate_hash"),
            error=data.get("error"),
            op_count=int(data.get("op_count", 0)),
            verification_kind=(data.get("verification_kind") if isinstance(data.get("verification_kind"), str) else None),
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


def recompute_apply(
    submit_graph: Mapping[str, Any],
    cumulative_delta_envelope: Mapping[str, Any] | None,
    *,
    schema_provider: Any = None,
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

    return True, working, None, len(ops)


def verify_replay(
    submit_graph: Mapping[str, Any] | None,
    cumulative_delta_envelope: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    *,
    schema_provider: Any = None,
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

    recomputed_hash = structural_graph_hash(recomputed)
    matches = persisted_hash is not None and recomputed_hash == persisted_hash
    return ReplayReceipt(
        replay_ok=True,
        candidate_matches=matches,
        recomputed_candidate_hash=recomputed_hash,
        persisted_candidate_hash=persisted_hash,
        error=None if matches else "candidate_hash_mismatch",
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
    else:
        replay = verify_layout_candidate(
            submit_graph,
            cumulative_delta_envelope,
            candidate,
            response,
            schema_provider=persisted_schema_provider,
        ) or verify_replay(
            submit_graph,
            cumulative_delta_envelope,
            candidate,
            schema_provider=persisted_schema_provider,
        )

    submit_graph_hash = payload_hash(submit_graph) if submit_graph is not None else None
    submit_bytes = canonical_json_bytes(submit_graph) if submit_graph is not None else None
    submit_graph_bytes_sha256 = (
        hashlib.sha256(submit_bytes).hexdigest() if submit_bytes is not None else None
    )

    delta_envelope_dict = (
        dict(cumulative_delta_envelope) if isinstance(cumulative_delta_envelope, Mapping) else None
    )
    cumulative_delta_hash = (
        payload_hash(delta_envelope_dict) if delta_envelope_dict is not None else None
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
        # Narrow: discovery-stop clarify must be preserved even when replay
        # is not applyable (candidate_hash_mismatch / accepted_batch==[]).
        # Only this specific report key maps to clarify; all other
        # non-applyable cases remain fail-closed.
        _orig_outcome = response.get("outcome") if isinstance(response.get("outcome"), Mapping) else None
        _report = response.get("report") if isinstance(response.get("report"), Mapping) else None
        if isinstance(_orig_outcome, Mapping) and _orig_outcome.get("kind") == "clarify" and isinstance(_report, Mapping) and "discovery_stop" in _report:
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
        stamped["outcome"] = {
            "kind": "error",
            "failure_kind": "ValidationError",
            "stage": "authority",
            "retryable": False,
            "next_action": "none",
            "graph_unchanged": True,
            "question": message,
            "clarification": {"message": message},
        }
        stamped["internal_outcome"] = {
            "kind": "failure",
            "failure_kind": "ValidationError",
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
    elif receipt.replay.replay_ok and receipt.replay.candidate_matches:
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
    "ReplayReceipt",
    "ResponseMetadataHashes",
    "authority_dir_for",
    "authority_receipt_path",
    "build_and_persist_authority_receipt",
    "build_authority_receipt",
    "load_authority_receipt",
    "recompute_apply",
    "stamp_response_with_authority",
    "verify_replay",
    "write_authority_receipt",
]
