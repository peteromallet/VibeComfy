"""
Artifact store: transaction artifact storage, lifecycle logs, receipts, and index recovery (T-044).

Extracted from ``vibecomfy.comfy_nodes.agent.session`` (T-044, ORACLE-7, WP-6.2): the
Phase-4 transactional storage helpers (session.py :1147-1459) and the recovery/reconcile
functions (:3467-3647).  ``session`` re-exports this module via ``from ._artifact_store import *``
(façade seam added at T-043); ``__all__`` below is exactly the name set these ranges
contributed to the session namespace, so the re-export reproduces the identical top-level
attributes — the same contract ``edit`` uses for its ``_frag_*`` fragments (including
_-prefixed helpers that stay importable by name for the T-048 monkeypatch/importer
compatibility).

Dependency style (S6 ground truth): these ranges contain ZERO state-persistence call
sites — persisting the in-memory state dict is the caller's job under the session lock —
so this module needs no late-binding machinery.  Dependencies that live in non-cyclic
sibling modules (``candidate_transaction``) are imported ordinarily at module level.
The two receipt-name constants are also imported at module level because the module-level
``_PHASE_TO_RECEIPT_NAME`` mapping is built at import time; every other name that lives
in the host ``session`` façade is resolved with the standard T-044 late import
(function-local, host namespace lookup, resolved at call time) so the
``session`` → ``_artifact_store`` re-export cycle never bites and module-attr patching on
``session`` stays visible.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable

from .candidate_transaction import (
    CANDIDATE_TRANSACTION_FILENAME,
    CANDIDATE_TRANSACTION_V2,
    canonical_transaction_state,
    classify_legacy_migration_v1,
    validate_candidate_transaction,
)
# T-044 module-level host import: required at import time by the module-level
# ``_PHASE_TO_RECEIPT_NAME`` mapping (the only names the extracted ranges need at
# module-execution time); ``session`` is fully defined before its end-of-file
# ``from ._artifact_store import *`` re-export, so the cycle never bites.
from .session import (
    DurableRead,
    DurableReadError,
    TRANSACTION_FINALIZED_RECEIPT_NAME,
    TRANSACTION_ROLLBACK_RECEIPT_NAME,
)

# ── Phase 4 transactional storage helpers (T19) ─────────────────────────────
# Artifact layout (authoritative truth, per turn):
#   turns/<turn_id>/transactions/<plan_hash>/lifecycle_events.jsonl  (append-only)
#   turns/<turn_id>/transactions/<plan_hash>/prepared.json           (derived snapshot)
#   turns/<turn_id>/transactions/<plan_hash>/finalized.json          (derived snapshot)
#   turns/<turn_id>/transactions/<plan_hash>/rollback.json           (derived snapshot)
#
# Authority model (see SC19):
#   * ``lifecycle_events.jsonl`` is the SINGLE source of truth.  Each event is
#     one JSON line, appended under the session lock with an ``fsync``.
#   * The ``*.json`` receipt snapshots are *derived* projections of the latest
#     event of each phase, written only to make reload O(1).  They are never
#     authoritative.
#   * The ``session_state.json`` index (``next_generation``,
#     ``prepared_transactions``, ``apply_idempotency_records``) is a
#     discoverable *cache* that ``recover_transaction_index`` can rebuild purely
#     from the artifact logs.
_TRANSACTION_VALID_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "prepared",
        "canvas_verified",
        "finalized",
        "rollback_complete",
        "discarded",
        "superseded",
        "recoverable_error",
    }
)
_PHASE_TO_RECEIPT_NAME: Mapping[str, str | None] = MappingProxyType(
    {
        "finalized": TRANSACTION_FINALIZED_RECEIPT_NAME,
        "rollback_complete": TRANSACTION_ROLLBACK_RECEIPT_NAME,
        "discarded": None,
        "superseded": None,
    }
)


def transaction_dir_for(turn_dir: Path, plan_hash: str) -> Path:
    from vibecomfy.comfy_nodes.agent.session import (TRANSACTIONS_DIR_NAME, normalize_path_component)  # T-044 late import: host namespace lookup; resolved at call time
    """Return the authoritative transaction artifact directory for *plan_hash*.

    The *plan_hash* is normalised through ``normalize_path_component`` so the
    result is always a single path component safely contained within *turn_dir*.
    """
    safe_plan = normalize_path_component(plan_hash)
    candidate = (turn_dir / TRANSACTIONS_DIR_NAME / safe_plan).resolve()
    turn_resolved = turn_dir.resolve()
    try:
        candidate.relative_to(turn_resolved)
    except ValueError:
        raise ValueError(
            f"plan_hash {plan_hash!r} resolves outside turn directory "
            f"{turn_resolved}: {candidate}"
        )
    return candidate


def candidate_transaction_path(turn_dir: Path, plan_hash: str) -> Path:
    return transaction_dir_for(turn_dir, plan_hash) / CANDIDATE_TRANSACTION_FILENAME


def write_candidate_transaction(
    turn_dir: Path,
    transaction: Mapping[str, Any],
) -> Path:
    from vibecomfy.comfy_nodes.agent.session import (_load_json, _write_response_immutable)  # T-044 late import: host namespace lookup; resolved at call time
    """Persist the immutable candidate aggregate before candidate publication."""
    ok, error = validate_candidate_transaction(transaction)
    if not ok:
        raise ValueError(error or "invalid_candidate_transaction")
    plan_hash = transaction.get("plan_hash")
    if not isinstance(plan_hash, str) or not plan_hash:
        raise ValueError("Candidate transaction requires plan_hash.")
    path = candidate_transaction_path(turn_dir, plan_hash)
    if not _write_response_immutable(path, transaction):
        existing = _load_json(path)
        if existing != dict(transaction):
            raise ValueError(
                f"Candidate transaction collision for turn_dir={turn_dir}."
            )
        return path
    if _load_json(path) != dict(transaction):
        raise OSError(f"Candidate transaction did not persist exactly at {path}.")
    return path


def load_candidate_transaction(
    turn_dir: Path,
    plan_hash: str,
) -> dict[str, Any] | None:
    from vibecomfy.comfy_nodes.agent.session import (_load_json)  # T-044 late import: host namespace lookup; resolved at call time
    payload = _load_json(candidate_transaction_path(turn_dir, plan_hash))
    ok, _ = validate_candidate_transaction(payload)
    return dict(payload) if ok and isinstance(payload, Mapping) else None


def load_candidate_transaction_with_migration(
    turn_dir: Path,
    plan_hash: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    from vibecomfy.comfy_nodes.agent.session import (_load_json)  # T-044 late import: host namespace lookup; resolved at call time
    """Load validated v2 authority or explicitly classify the persisted legacy record."""
    payload = _load_json(candidate_transaction_path(turn_dir, plan_hash))
    ok, _ = validate_candidate_transaction(payload)
    if ok and isinstance(payload, Mapping):
        return dict(payload), None
    if not isinstance(payload, Mapping):
        return None, None
    contract_version = payload.get("contract_version")
    if contract_version == "candidate_transaction_v1":
        migration = classify_legacy_migration_v1(payload)
    else:
        migration = {
            "classification": (
                "invalid_v2_authority_fail_closed"
                if contract_version == CANDIDATE_TRANSACTION_V2
                else "unsupported_authority_version_fail_closed"
            ),
            "actions": ["rebaseline", "cancel"],
            "rollback_allowed": False,
        }
    return None, {
        **migration,
        "contract_version": payload.get("contract_version"),
        "state": payload.get("state"),
        "plan_hash": plan_hash,
    }


@dataclass(frozen=True)
class BoundCandidateReplayEvidence:
    """A validated persisted ``(candidate_transaction, authority_receipt)`` pair.

    ``transaction`` passed ``validate_candidate_transaction`` (V2 contract),
    ``receipt`` passed strict raw-JSON validation
    (``validate_authority_receipt_v2``), and ``receipt_digest`` is the sole
    owner's digest (``authority_receipt_digest_v2``) already proven equal to
    BOTH receipt-hash fields of the transaction envelope.
    """

    turn_dir: Path
    transaction: dict[str, Any]
    #: :class:`AuthorityReceipt` — kept untyped here to avoid an import cycle;
    #: this module must stay importable from inside ``session``'s own body.
    receipt: Any
    receipt_digest: str


def load_bound_candidate_replay_evidence(
    turn_dir: Path,
    *,
    session_id: str,
    turn_id: str,
    plan_hash: str,
) -> tuple[BoundCandidateReplayEvidence | None, str | None]:
    """Load and bind the ONE persisted transaction/receipt pair for *turn_dir*.

    DEEP-AUDIT-FIX-2-REVISION-2: single production seam for replay-landed
    authority.  Every binding check runs here, fail-closed, returning
    ``(None, typed_reason)`` on any mismatch:

    1. the persisted V2 transaction via ``load_candidate_transaction_with_migration``;
    2. the raw persisted ``authority/receipt.json`` through strict
       ``validate_authority_receipt_v2`` BEFORE dataclass coercion;
    3. receipt-digest binding: the complete-canonical receipt digest recomputed
       by the sole owner must equal ``candidate_authority.authority_receipt_digest``
       AND ``hashes.authority_receipt_hash`` (a present ``prepared_authority``
       was already checked key-by-key against ``candidate_authority`` by the
       V2 transition validation inside step 1);
    4. the receipt's ACTUAL verdict: ``replay_ok``, ``candidate_matches``,
       no replay error, and ``is_applyable`` — the transaction's copied booleans
       are consistency evidence only (they must EQUAL the receipt) and can
       never override it;
    5. delta-digest and candidate-hash chains: receipt Δ == derived plan Δ ==
       operation digest; payload-family candidate hash equals the transaction's
       ``candidate_graph_hash`` while the structural replay family identifies
       the same replayed candidate;
    6. every identity each carrier owns: session/turn/plan across envelope,
       authority, and receipt; ``transaction_id``/``candidate_id`` RECOMPUTED
       through the shared mint function ``candidate_transaction_identities_v2``;
    7. any embedded SOURCE-TURN ``response["candidate_transaction"]`` must equal
       the persisted transaction when present.

    The assessor's manually embedded replay booleans are never inspected or
    trusted: only the durable files under *turn_dir* are read.
    """
    from vibecomfy.comfy_nodes.agent.authority_receipts import (
        AuthorityReceiptValidationError,
        authority_receipt_digest_v2,
        authority_receipt_path,
        validate_authority_receipt_v2,
    )  # T-044-style late import: avoids the session → _artifact_store → authority_receipts cycle at import time
    from vibecomfy.comfy_nodes.agent.candidate_transaction import (
        candidate_transaction_identities_v2,
        content_hash,
        legacy_rendering_hash,
    )
    from vibecomfy.comfy_nodes.agent.session import _load_json

    transaction, legacy_migration = load_candidate_transaction_with_migration(
        turn_dir, plan_hash
    )
    if transaction is None:
        if isinstance(legacy_migration, Mapping):
            return None, str(
                legacy_migration.get("classification") or "legacy_non_resumable"
            )
        return None, "missing_candidate_transaction"
    if (
        transaction.get("session_id") != session_id
        or transaction.get("turn_id") != turn_id
        or transaction.get("plan_hash") != plan_hash
    ):
        return None, "candidate_transaction_identity_mismatch"
    candidate_authority = transaction.get("candidate_authority")
    hashes = transaction.get("hashes")
    plan = transaction.get("plan")
    authority_block = transaction.get("authority")
    if not all(
        isinstance(item, Mapping)
        for item in (candidate_authority, hashes, plan, authority_block)
    ):
        return None, "malformed_candidate_transaction"

    # Deterministic identities are RECOMPUTED through the mint-time formulas;
    # non-empty syntax alone is insufficient.
    expected_transaction_id, expected_candidate_id = (
        candidate_transaction_identities_v2(session_id, turn_id, plan_hash)
    )
    if (
        candidate_authority.get("transaction_id"),
        candidate_authority.get("candidate_id"),
    ) != (expected_transaction_id, expected_candidate_id):
        return None, "candidate_identity_mismatch"

    raw_receipt = _load_json(authority_receipt_path(turn_dir))
    if not isinstance(raw_receipt, Mapping):
        return None, "missing_authority_receipt"
    try:
        receipt = validate_authority_receipt_v2(raw_receipt)
    except AuthorityReceiptValidationError as exc:
        return None, f"invalid_authority_receipt:{exc}"
    receipt_digest = authority_receipt_digest_v2(receipt)

    if (
        candidate_authority.get("authority_receipt_digest") != receipt_digest
        or hashes.get("authority_receipt_hash") != receipt_digest
    ):
        return None, "authority_receipt_digest_mismatch"
    if (
        candidate_authority.get("authority_receipt_contract_version")
        != receipt.contract_version
        or candidate_authority.get("authority_receipt_delta_schema")
        != receipt.schema_version
    ):
        return None, "candidate_authority_receipt_binding_mismatch"

    # Tamper consistency: the transaction copies must equal the receipt fields
    # (strict bool identity — an int 1 copy fails here), but they can never
    # override the receipt's actual verdict below.
    if (
        type(authority_block.get("replay_ok")) is not bool
        or authority_block["replay_ok"] is not receipt.replay.replay_ok
        or type(authority_block.get("candidate_matches")) is not bool
        or authority_block["candidate_matches"] is not receipt.replay.candidate_matches
        or authority_block.get("verification_kind") != receipt.replay.verification_kind
        or authority_block.get("schema_witness_hash") != receipt.schema_witness_hash
    ):
        return None, "transaction_authority_copy_mismatch"

    accepted = plan.get("accepted_batch")
    if not isinstance(accepted, list):
        return None, "missing_persisted_delta_plan"
    from vibecomfy.comfy_nodes.agent._frag_state import derived_accepted_delta_envelope

    plan_envelope = derived_accepted_delta_envelope({"accepted_batch": accepted})
    receipt_delta = receipt.accepted_batch_digest or receipt.cumulative_delta_hash
    if receipt_delta not in {
        content_hash(plan_envelope),
        legacy_rendering_hash(plan_envelope),
    }:
        return None, "authority_delta_mismatch"
    if plan.get("delta_hash") != receipt.cumulative_delta_hash:
        return None, "authority_delta_hash_mismatch"
    operation = candidate_authority.get("operation")
    if (
        not isinstance(operation, Mapping)
        or operation.get("accepted_batch_digest") != receipt_delta
    ):
        return None, "operation_delta_digest_mismatch"

    # Candidate-hash chain.  Two hash families describe the SAME candidate:
    # the payload family binds exact bytes (receipt.candidate_hash ↔ the
    # transaction's candidate_graph_hash); the structural family proves the
    # replay re-derived the persisted structure (persisted == recomputed).
    # verify_replay computed both families over that one candidate object.
    if hashes.get("candidate_graph_hash") != receipt.candidate_hash:
        return None, "authority_candidate_hash_mismatch"
    if receipt.replay.persisted_candidate_hash != receipt.replay.recomputed_candidate_hash:
        return None, "replay_candidate_hash_inconsistent"

    # The receipt's ACTUAL verdict is the only upgrade authority.
    if not (
        receipt.replay.replay_ok is True
        and receipt.replay.candidate_matches is True
        and not receipt.replay.error
        and receipt.is_applyable
    ):
        return None, "authority_receipt_not_applyable"

    # The receipt carries session/turn (not plan_hash): with the accepted-delta
    # digest, candidate hash, and full receipt digest bound above, it is bound
    # transitively to the transaction plan without changing its version.
    if receipt.session_id != session_id or receipt.turn_id != turn_id:
        return None, "receipt_identity_mismatch"

    response = _load_json(turn_dir / "response.json")
    if isinstance(response, Mapping):
        response_transaction = response.get("candidate_transaction")
        if isinstance(response_transaction, Mapping) and dict(response_transaction) != transaction:
            return None, "response_transaction_mismatch"

    return BoundCandidateReplayEvidence(
        turn_dir=turn_dir,
        transaction=transaction,
        receipt=receipt,
        receipt_digest=receipt_digest,
    ), None


def _transaction_log_path(transaction_dir: Path) -> Path:
    from vibecomfy.comfy_nodes.agent.session import (TRANSACTION_LIFECYCLE_LOG_NAME)  # T-044 late import: host namespace lookup; resolved at call time
    return transaction_dir / TRANSACTION_LIFECYCLE_LOG_NAME


def _count_log_lines(path: Path) -> int:
    """Return the number of complete lines in *path* (0 if absent)."""
    try:
        count = 0
        with path.open("r", encoding="utf-8") as fh:
            for _ in fh:
                count += 1
    except FileNotFoundError:
        return 0
    except OSError:
        return 0
    return count


def _next_transaction_seq(transaction_dir: Path) -> int:
    """Return the next 1-based sequence number for a new lifecycle event."""
    return len(read_transaction_lifecycle(transaction_dir)) + 1


def read_transaction_lifecycle_result(transaction_dir: Path) -> DurableRead:
    """Read lifecycle evidence with an explicit absent/valid/corrupt status."""
    log_path = _transaction_log_path(transaction_dir)
    events: list[dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    return DurableRead("corrupt", path=log_path, error=str(exc))
                if not isinstance(parsed, dict):
                    return DurableRead(
                        "corrupt", path=log_path, error="lifecycle event must be an object"
                    )
                legacy_event_type = parsed.get("event_type")
                canonical_event_type = canonical_transaction_state(
                    legacy_event_type
                )
                if not isinstance(canonical_event_type, str):
                    return DurableRead(
                        "corrupt", path=log_path, error="invalid lifecycle event type"
                    )
                if canonical_event_type != legacy_event_type:
                    parsed["legacy_event_type"] = legacy_event_type
                    parsed["event_type"] = canonical_event_type
                    receipt = parsed.get("receipt")
                    if isinstance(receipt, dict):
                        receipt.setdefault("legacy_phase", receipt.get("phase"))
                        receipt["phase"] = canonical_event_type
                events.append(parsed)
    except FileNotFoundError:
        return DurableRead("absent", path=log_path)
    except (OSError, UnicodeError) as exc:
        return DurableRead("unreadable", path=log_path, error=str(exc))
    if not events:
        return DurableRead("valid", value=[], path=log_path)
    expected_turn = events[0].get("turn_id")
    expected_plan = events[0].get("plan_hash")
    expected_generation = events[0].get("generation")
    if (
        not isinstance(expected_turn, str)
        or not isinstance(expected_plan, str)
        or not isinstance(expected_generation, int)
    ):
        return DurableRead(
            "corrupt", path=log_path, error="lifecycle identity is incomplete"
        )
    terminal_seen = False
    active_generation = expected_generation
    for expected_seq, event in enumerate(events, start=1):
        generation = event.get("generation")
        # A retry may mint a newer prepared lease for the same immutable plan.
        # Only a new `prepared` event may advance the generation; every later
        # receipt must remain bound to that exact lease.
        advances_generation = (
            event.get("event_type") == "prepared"
            and isinstance(generation, int)
            and generation > active_generation
        )
        if (
            event.get("seq") != expected_seq
            or event.get("turn_id") != expected_turn
            or event.get("plan_hash") != expected_plan
            or (generation != active_generation and not advances_generation)
            or event.get("event_type") not in _TRANSACTION_VALID_EVENT_TYPES
            or terminal_seen
        ):
            return DurableRead(
                "corrupt", path=log_path, error="lifecycle sequence or identity is invalid"
            )
        if advances_generation:
            active_generation = generation
        terminal_seen = event.get("event_type") in {
            "finalized",
            "rollback_complete",
            "discarded",
            "superseded",
        }
    first_type = events[0].get("event_type")
    if first_type not in {"prepared", "discarded"}:
        return DurableRead(
            "corrupt", path=log_path, error="invalid lifecycle opening event"
        )
    return DurableRead("valid", value=events, path=log_path)


def read_transaction_lifecycle(transaction_dir: Path) -> list[dict[str, Any]]:
    """Read lifecycle evidence, failing closed when an existing log is damaged."""
    result = read_transaction_lifecycle_result(transaction_dir)
    if result.status == "absent":
        return []
    if result.status != "valid":
        raise DurableReadError(result)
    return result.value


def latest_transaction_event(transaction_dir: Path) -> dict[str, Any] | None:
    """Return the last lifecycle event, or ``None`` if the log is empty/absent."""
    events = read_transaction_lifecycle(transaction_dir)
    return events[-1] if events else None


def latest_transaction_phase(transaction_dir: Path) -> str | None:
    """Return the latest event_type, or ``None`` if the log is empty/absent."""
    event = latest_transaction_event(transaction_dir)
    if not isinstance(event, dict):
        return None
    phase = event.get("event_type")
    return phase if isinstance(phase, str) else None


def _safe_receipt(event: Mapping[str, Any]) -> Mapping[str, Any]:
    receipt = event.get("receipt")
    return receipt if isinstance(receipt, Mapping) else {}


def _append_transaction_lifecycle_event(
    transaction_dir: Path,
    *,
    event_type: str,
    turn_id: str,
    plan_hash: str,
    generation: int,
    receipt: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.session import (_now)  # T-044 late import: host namespace lookup; resolved at call time
    """Append one lifecycle event to the authoritative append-only log.

    The caller must hold the session lock so sequence numbers stay monotonic.
    Each event is a single JSON line terminated by ``\\n``; the file is opened
    in append mode and ``fsync``\\ 'd so the record survives a crash.  Returns
    the full event record that was appended.
    """
    if event_type not in _TRANSACTION_VALID_EVENT_TYPES:
        raise ValueError(f"unknown transaction event type: {event_type!r}")
    event: dict[str, Any] = {
        "seq": _next_transaction_seq(transaction_dir),
        "event_type": event_type,
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": generation,
        "timestamp": (now_fn or _now)(),
        "receipt": dict(receipt) if receipt else {},
    }
    transaction_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    log_path = _transaction_log_path(transaction_dir)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    return event


def _write_transaction_receipt(
    transaction_dir: Path,
    event_type: str,
    event: Mapping[str, Any],
) -> Path | None:
    from vibecomfy.comfy_nodes.agent.session import (TRANSACTION_RECEIPT_BY_EVENT, _write_response_atomic)  # T-044 late import: host namespace lookup; resolved at call time
    """Write the derived ``{event_type}.json`` receipt snapshot atomically.

    The snapshot is the full event record (the latest event of *event_type*),
    written only to make reload O(1).  It is *never* authoritative — the
    append-only log is.  Returns the receipt path, or ``None`` when
    *event_type* has no snapshot filename (e.g. ``cancelled``).
    """
    name = TRANSACTION_RECEIPT_BY_EVENT.get(event_type)
    if name is None:
        return None
    transaction_dir.mkdir(parents=True, exist_ok=True)
    target = transaction_dir / name
    _write_response_atomic(target, dict(event))
    return target



def recover_transaction_index(session_dir: Path) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.session import (TRANSACTIONS_DIR_NAME, _TRANSACTION_RESOLVED_PHASES, _apply_idempotency_key, _load_json)  # T-044 late import: host namespace lookup; resolved at call time
    """Rebuild the transaction index purely from authoritative artifact truth.

    Scans ``turns/<turn_id>/transactions/<plan_hash>/lifecycle_events.jsonl``
    for every turn and reconstructs ``next_generation``,
    ``prepared_transactions`` and ``apply_idempotency_records`` from the
    append-only logs only.  This is the proof — and the implementation — that
    the ``session_state.json`` index is a recoverable cache: it never holds
    information that cannot be derived from the artifacts.
    """
    turns_root = session_dir / "turns"
    prepared: dict[str, Any] = {}
    idempotency: dict[str, Any] = {}
    turn_states: dict[str, str] = {}
    baseline_events: list[dict[str, Any]] = []
    max_generation = 0
    if turns_root.is_dir():
        for turn_dir in sorted(p for p in turns_root.iterdir() if p.is_dir()):
            turn_id = turn_dir.name
            transactions_root = turn_dir / TRANSACTIONS_DIR_NAME
            if not transactions_root.is_dir():
                continue
            # A turn may carry several plan_hash dirs (superseded attempts).
            # The *current* prepared pointer is the dir whose latest event is
            # "prepared" with the highest generation.
            latest_prepared: dict[str, Any] | None = None
            for plan_dir in sorted(p for p in transactions_root.iterdir() if p.is_dir()):
                plan_hash = plan_dir.name
                events = read_transaction_lifecycle(plan_dir)
                if not events:
                    candidate = _load_json(plan_dir / CANDIDATE_TRANSACTION_FILENAME)
                    ok, _ = validate_candidate_transaction(candidate)
                    if ok:
                        turn_states[turn_id] = str(candidate.get("state"))
                    continue
                latest = events[-1]
                phase = latest.get("event_type")
                generation = latest.get("generation")
                if isinstance(generation, int) and generation > max_generation:
                    max_generation = generation
                if phase in {"prepared", "canvas_verified", "recoverable_error"} and isinstance(generation, int):
                    prepared_event = next(
                        (
                            event
                            for event in reversed(events)
                            if event.get("event_type") == "prepared"
                            and event.get("generation") == generation
                        ),
                        None,
                    )
                    prepared_receipt = _safe_receipt(prepared_event or {})
                    candidate = {
                        "plan_hash": plan_hash,
                        "generation": generation,
                        "lease_nonce": prepared_receipt.get("lease_nonce"),
                        "structural_hash_before": prepared_receipt.get(
                            "structural_hash_before"
                        ),
                        "timestamp": latest.get("timestamp"),
                    }
                    if latest_prepared is None or generation > latest_prepared.get(
                        "generation", 0
                    ):
                        latest_prepared = candidate
                    turn_states[turn_id] = str(phase)
                elif (
                    phase in _TRANSACTION_RESOLVED_PHASES
                    and isinstance(generation, int)
                ):
                    idempotency[_apply_idempotency_key(plan_hash, generation)] = {
                        "turn_id": latest.get("turn_id") or turn_id,
                        "plan_hash": plan_hash,
                        "generation": generation,
                        "phase": phase,
                        "receipt_path": _PHASE_TO_RECEIPT_NAME.get(phase),
                        "timestamp": latest.get("timestamp"),
                    }
                    turn_states[turn_id] = str(
                        canonical_transaction_state(phase) or phase
                    )
                    if phase in {"finalized", "rollback_complete"}:
                        baseline_events.append(
                            {
                                "turn_id": turn_id,
                                "plan_hash": plan_hash,
                                "generation": generation,
                                "phase": phase,
                                "receipt": dict(_safe_receipt(latest)),
                                "events": events,
                            }
                        )
            if latest_prepared is not None:
                prepared[turn_id] = latest_prepared
    return {
        "next_generation": max_generation + 1,
        "prepared_transactions": prepared,
        "apply_idempotency_records": idempotency,
        "turn_states": turn_states,
        "baseline_events": baseline_events,
    }


def reconcile_transaction_index_from_artifacts(
    state: dict[str, Any], session_dir: Path
) -> bool:
    from vibecomfy.comfy_nodes.agent.session import (STRUCTURAL_PROJECTION_VERSION, _normalize_apply_idempotency_records, _normalize_prepared_transactions_index, _payload_mapping, _restore_baseline_snapshot, _set_baseline_authoritatively, _source_path_for_turn_baseline)  # T-044 late import: host namespace lookup; resolved at call time
    """Rebuild the transaction index in *state* from artifact truth.

    Returns ``True`` if the recovered index differs from what *state* held.
    Used by the reload/reconciliation path (a later task) to repair a stale or
    corrupt ``session_state.json`` index.  The caller must persist *state*.
    """
    recovered = recover_transaction_index(session_dir)
    current_prepared = _normalize_prepared_transactions_index(
        state.get("prepared_transactions")
    )
    current_idempotency = _normalize_apply_idempotency_records(
        state.get("apply_idempotency_records")
    )
    changed = (
        recovered["next_generation"] != state.get("next_generation")
        or recovered["prepared_transactions"] != current_prepared
        or recovered["apply_idempotency_records"] != current_idempotency
    )
    state["next_generation"] = recovered["next_generation"]
    state["prepared_transactions"] = recovered["prepared_transactions"]
    state["apply_idempotency_records"] = recovered["apply_idempotency_records"]
    turns = state.get("turns")
    if isinstance(turns, dict):
        for turn_id, recovered_state in recovered["turn_states"].items():
            turn = turns.get(turn_id)
            if isinstance(turn, dict) and turn.get("state") != recovered_state:
                turn["state"] = recovered_state
                changed = True
    baseline_events = sorted(
        recovered["baseline_events"],
        key=lambda event: int(event.get("generation", 0)),
    )
    if baseline_events:
        latest = baseline_events[-1]
        receipt = _payload_mapping(latest.get("receipt"))
        if (
            latest.get("phase") == "finalized"
            # A valid rebaseline source represents canvas authority adopted
            # after the latest finalized transaction. Replaying historical
            # transaction events must not roll that newer revision backward.
            and state.get("baseline_source") != "rebaseline"
        ):
            recovered_hash = receipt.get("structural_hash_after")
            if isinstance(recovered_hash, str) and (
                state.get("baseline_graph_hash") != recovered_hash
                or state.get("baseline_turn_id") != latest.get("turn_id")
            ):
                _set_baseline_authoritatively(
                    state,
                    next_hash=recovered_hash,
                    next_kind="structural",
                    next_source="turn",
                    reason="transaction_recovery",
                    source_turn_id=str(latest.get("turn_id")),
                    source_path=_source_path_for_turn_baseline(
                        session_dir, str(latest.get("turn_id"))
                    ),
                    projection_version=STRUCTURAL_PROJECTION_VERSION,
                )
                changed = True
        elif latest.get("phase") == "rollback_complete":
            prepared = next(
                (
                    event
                    for event in reversed(latest.get("events", []))
                    if event.get("event_type") == "prepared"
                ),
                None,
            )
            snapshot = _payload_mapping(_safe_receipt(prepared or {}).get("baseline_snapshot"))
            if snapshot and any(state.get(key) != snapshot.get(key) for key in snapshot):
                _restore_baseline_snapshot(state, snapshot)
                changed = True
    return changed



__all__ = (
    "_TRANSACTION_VALID_EVENT_TYPES",
    "_PHASE_TO_RECEIPT_NAME",
    "transaction_dir_for",
    "candidate_transaction_path",
    "write_candidate_transaction",
    "load_candidate_transaction",
    "load_candidate_transaction_with_migration",
    "_transaction_log_path",
    "_count_log_lines",
    "_next_transaction_seq",
    "read_transaction_lifecycle_result",
    "read_transaction_lifecycle",
    "latest_transaction_event",
    "latest_transaction_phase",
    "_safe_receipt",
    "_append_transaction_lifecycle_event",
    "_write_transaction_receipt",
    "recover_transaction_index",
    "reconcile_transaction_index_from_artifacts",
)
