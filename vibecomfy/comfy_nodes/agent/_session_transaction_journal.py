"""Transaction journal writes and their recoverable session-state index.

The public compatibility surface remains in :mod:`.session`.  Implementations
resolve host helpers at call time so tests and integrations that patch the
historical ``session`` attributes keep observing the same call graph.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from .candidate_transaction import (
    CANDIDATE_TRANSACTION_V2,
    project_transaction_state,
    validate_candidate_transaction,
)


def allocate_generation_impl(state: dict[str, Any]) -> int:
    """Return the current monotonic generation and advance the counter."""
    current = state.get("next_generation")
    if not isinstance(current, int) or current < 1:
        current = 1
    state["next_generation"] = current + 1
    return current


def apply_idempotency_key_impl(plan_hash: str, generation: int) -> str:
    return f"{plan_hash}:{generation}"


def clear_prepared_pointer_impl(state: dict[str, Any], *, turn_id: str) -> None:
    state.setdefault("prepared_transactions", {}).pop(turn_id, None)


def set_apply_idempotency_record_impl(
    state: dict[str, Any],
    *,
    plan_hash: str,
    generation: int,
    record: Mapping[str, Any],
) -> None:
    from . import session as host

    state.setdefault("apply_idempotency_records", {})[
        host._apply_idempotency_key(plan_hash, generation)
    ] = dict(record)


def lookup_apply_idempotency_record_impl(
    state: Mapping[str, Any],
    *,
    plan_hash: str,
    generation: int,
) -> dict[str, Any] | None:
    from . import session as host

    record = state.get("apply_idempotency_records", {}).get(
        host._apply_idempotency_key(plan_hash, generation)
    )
    return dict(record) if isinstance(record, Mapping) else None


def record_prepared_transaction_impl(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    revision_id: str,
    parent_revision: str,
    lease_nonce: str,
    structural_hash_before: str | None,
    candidate_payload: Mapping[str, Any] | None = None,
    baseline_snapshot: Mapping[str, Any] | None = None,
    runtime_evidence: Mapping[str, Any] | None = None,
    bundle_digests: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    from .projection_registry_v1 import revision_identity_v1

    revision_identity_v1(revision_id, parent_revision)

    generation = host.allocate_generation(state)
    transaction_dir = host.transaction_dir_for(turn_dir, plan_hash)
    prepared_candidate: dict[str, Any] = {}
    if (
        candidate_payload
        and candidate_payload.get("contract_version") == CANDIDATE_TRANSACTION_V2
    ):
        prepared_candidate = project_transaction_state(
            candidate_payload,
            state="prepared",
            generation=generation,
            lease_nonce=lease_nonce,
        )
        ok, error = validate_candidate_transaction(prepared_candidate)
        if not ok:
            raise ValueError(error or "invalid_prepared_candidate_transaction")
        authority = prepared_candidate.get("prepared_authority")
        if (
            not isinstance(authority, Mapping)
            or authority.get("revision_id") != revision_id
            or authority.get("parent_revision") != parent_revision
        ):
            raise ValueError("prepared candidate revision identity mismatch")
    elif candidate_payload:
        prepared_candidate = dict(candidate_payload)
    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "revision_id": revision_id,
        "parent_revision": parent_revision,
        "generation": generation,
        "lease_nonce": lease_nonce,
        "structural_hash_before": structural_hash_before,
        "baseline_snapshot": dict(baseline_snapshot) if baseline_snapshot else {},
        "candidate": prepared_candidate,
        "candidate_transaction": prepared_candidate,
        "phase": "prepared",
    }
    if bundle_digests is not None:
        receipt["bundle"] = {
            "revision_id": revision_id,
            "parent_revision": parent_revision,
            **{
                str(key): value
                for key, value in bundle_digests.items()
                if str(key) in {"semantic_digest", "ui_digest"}
                and isinstance(value, str)
            },
        }
    if runtime_evidence is not None:
        receipt["runtime_evidence"] = dict(runtime_evidence)
    event = host._append_transaction_lifecycle_event(
        transaction_dir,
        event_type="prepared",
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        receipt=receipt,
        now_fn=now_fn,
    )
    host._write_transaction_receipt(transaction_dir, "prepared", event)
    state.setdefault("prepared_transactions", {})[turn_id] = {
        "plan_hash": plan_hash,
        "generation": generation,
        "lease_nonce": lease_nonce,
        "structural_hash_before": structural_hash_before,
        "revision_id": revision_id,
        "parent_revision": parent_revision,
        "timestamp": event["timestamp"],
    }
    return event


def record_resolved_transaction_impl(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    generation: int,
    event_type: str,
    receipt: Mapping[str, Any],
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    transaction_dir = host.transaction_dir_for(turn_dir, plan_hash)
    event = host._append_transaction_lifecycle_event(
        transaction_dir,
        event_type=event_type,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        receipt=receipt,
        now_fn=now_fn,
    )
    host._write_transaction_receipt(transaction_dir, event_type, event)
    host._clear_prepared_pointer(state, turn_id=turn_id)
    host._set_apply_idempotency_record(
        state,
        plan_hash=plan_hash,
        generation=generation,
        record={
            "turn_id": turn_id,
            "plan_hash": plan_hash,
            "generation": generation,
            "revision_id": receipt.get("revision_id"),
            "parent_revision": receipt.get("parent_revision"),
            "phase": event_type,
            "receipt_path": host._PHASE_TO_RECEIPT_NAME.get(event_type),
            "timestamp": event["timestamp"],
        },
    )
    return event


def record_finalized_transaction_impl(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    revision_id: str,
    parent_revision: str,
    generation: int,
    structural_hash_after: str | None,
    applied_payload: Mapping[str, Any] | None = None,
    journal_durable: Mapping[str, Any] | None = None,
    runtime_evidence: Mapping[str, Any] | None = None,
    approval_evidence: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    from .projection_registry_v1 import revision_identity_v1

    revision_identity_v1(revision_id, parent_revision)

    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "revision_id": revision_id,
        "parent_revision": parent_revision,
        "generation": generation,
        "structural_hash_after": structural_hash_after,
        "applied": dict(applied_payload) if applied_payload else {},
        "phase": "finalized",
    }
    if journal_durable is not None:
        from .projection_registry_v1 import validate_journal_durable_v1

        validated_journal = validate_journal_durable_v1(journal_durable)

        def _plain_json(value: Any) -> Any:
            if isinstance(value, Mapping):
                return {str(key): _plain_json(entry) for key, entry in value.items()}
            if isinstance(value, (list, tuple)):
                return [_plain_json(entry) for entry in value]
            return value

        receipt["journal_durable"] = _plain_json(validated_journal)
    if runtime_evidence is not None:
        receipt["runtime_evidence"] = dict(runtime_evidence)
    if approval_evidence is not None:
        allowed = {
            "revision_id",
            "parent_revision",
            "semantic_digest",
            "ui_digest",
            "api_digest",
            "record_digest",
        }
        receipt["approval"] = {
            str(key): value
            for key, value in approval_evidence.items()
            if str(key) in allowed and isinstance(value, str)
        }
    return host._record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        event_type="finalized",
        receipt=receipt,
        now_fn=now_fn,
    )


def record_canvas_verified_transaction_impl(
    *,
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    revision_id: str,
    parent_revision: str,
    generation: int,
    lease_nonce: str,
    post_apply_graph_hash: str,
    post_apply_structural_hash: str,
    applied_delta_hash: str,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    from .projection_registry_v1 import revision_identity_v1

    revision_identity_v1(revision_id, parent_revision)

    receipt = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "revision_id": revision_id,
        "parent_revision": parent_revision,
        "generation": generation,
        "lease_nonce": lease_nonce,
        "post_apply_graph_hash": post_apply_graph_hash,
        "post_apply_structural_hash": post_apply_structural_hash,
        "applied_delta_hash": applied_delta_hash,
        "phase": "canvas_verified",
    }
    transaction_dir = host.transaction_dir_for(turn_dir, plan_hash)
    latest = host.latest_transaction_event(transaction_dir)
    if (
        isinstance(latest, Mapping)
        and latest.get("event_type") == "canvas_verified"
        and latest.get("generation") == generation
        and host._safe_receipt(latest) == receipt
    ):
        return dict(latest)
    event = host._append_transaction_lifecycle_event(
        transaction_dir,
        event_type="canvas_verified",
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        receipt=receipt,
        now_fn=now_fn,
    )
    host._write_transaction_receipt(transaction_dir, "canvas_verified", event)
    return event


def record_rolled_back_transaction_impl(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    revision_id: str,
    parent_revision: str,
    generation: int,
    restored_structural_hash: str | None,
    compensation: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    from .projection_registry_v1 import revision_identity_v1

    revision_identity_v1(revision_id, parent_revision)

    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "revision_id": revision_id,
        "parent_revision": parent_revision,
        "generation": generation,
        "restored_structural_hash": restored_structural_hash,
        "phase": "rollback_complete",
    }
    if compensation:
        receipt["compensation"] = dict(compensation)
    return host._record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        event_type="rollback_complete",
        receipt=receipt,
        now_fn=now_fn,
    )


def record_cancelled_transaction_impl(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    generation: int,
    reason: str | None = None,
    runtime_evidence: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": generation,
        "reason": reason,
        "phase": "superseded",
    }
    if runtime_evidence is not None:
        receipt["runtime_evidence"] = dict(runtime_evidence)
    return host._record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        event_type="superseded",
        receipt=receipt,
        now_fn=now_fn,
    )


def record_discarded_transaction_impl(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    reason: str = "rejected_by_user",
    generation: int | None = None,
    runtime_evidence: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    from . import session as host

    resolved_generation = 0 if generation is None else generation
    receipt = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": resolved_generation,
        "reason": reason,
        "phase": "discarded",
    }
    if runtime_evidence is not None:
        receipt["runtime_evidence"] = dict(runtime_evidence)
    return host._record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=resolved_generation,
        event_type="discarded",
        receipt=receipt,
        now_fn=now_fn,
    )


def normalize_prepared_transactions_index_impl(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    from .projection_registry_v1 import ContractError, revision_identity_v1

    result: dict[str, Any] = {}
    for turn_id, entry in raw.items():
        if not isinstance(turn_id, str) or not turn_id or not isinstance(entry, Mapping):
            continue
        plan_hash = entry.get("plan_hash")
        generation = entry.get("generation")
        if not isinstance(plan_hash, str) or not plan_hash:
            continue
        if not isinstance(generation, int) or generation < 1:
            continue
        try:
            revision_id, parent_revision = revision_identity_v1(
                entry.get("revision_id"), entry.get("parent_revision")
            )
        except ContractError:
            continue
        result[turn_id] = {
            "plan_hash": plan_hash,
            "generation": generation,
            "lease_nonce": entry.get("lease_nonce"),
            "structural_hash_before": entry.get("structural_hash_before"),
            "revision_id": revision_id,
            "parent_revision": parent_revision,
            "timestamp": entry.get("timestamp"),
        }
    return result


def normalize_apply_idempotency_records_impl(
    raw: Any,
    *,
    resolved_phases: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, record in raw.items():
        if not isinstance(key, str) or not key or not isinstance(record, Mapping):
            continue
        plan_hash = record.get("plan_hash")
        generation = record.get("generation")
        phase = record.get("phase")
        if not isinstance(plan_hash, str) or not plan_hash:
            continue
        if not isinstance(generation, int) or generation < 0:
            continue
        if phase not in resolved_phases:
            continue
        result[key] = {
            "turn_id": record.get("turn_id"),
            "plan_hash": plan_hash,
            "generation": generation,
            "phase": phase,
            "receipt_path": record.get("receipt_path"),
            "timestamp": record.get("timestamp"),
        }
    return result
