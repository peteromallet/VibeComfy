"""Tests for the Phase 4 transactional storage layer (T19).

These tests prove the authority model required by SC19:

* ``lifecycle_events.jsonl`` is the single authoritative, append-only source of
  truth (one JSON line per event, fsync'd).
* The ``prepared.json`` / ``finalized.json`` / ``rollback.json`` receipt
  snapshots are *derived* from the latest event — deleting them must not change
  recovery results.
* The ``session_state.json`` index (``next_generation``,
  ``prepared_transactions``, ``apply_idempotency_records``) is a discoverable
  cache that ``recover_transaction_index`` rebuilds purely from artifact truth.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent import session as S


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_session(tmp_path: Path) -> tuple[Path, Path, str, Path]:
    """Return (session_dir, turn_dir, turn_id, ) for an isolated session."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    turn_id = "turn-1"
    turn_dir = session_dir / "turns" / turn_id
    turn_dir.mkdir(parents=True)
    return session_dir, turn_dir, turn_id


def _state() -> dict:
    return S.default_state()


def _txn_dir(turn_dir: Path, plan_hash: str) -> Path:
    return turn_dir / S.TRANSACTIONS_DIR_NAME / plan_hash


def _log_lines(turn_dir: Path, plan_hash: str) -> list[dict]:
    log = _txn_dir(turn_dir, plan_hash) / S.TRANSACTION_LIFECYCLE_LOG_NAME
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _prepare(plan_hash: str = "a" * 64, *, turn_dir: Path, turn_id: str, state: dict):
    return S.record_prepared_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        lease_nonce="nonce-1",
        structural_hash_before="hash-before-1",
        candidate_payload={"entries": [{"id": "n1"}]},
    )


# ── Prepare ─────────────────────────────────────────────────────────────────


def test_prepare_writes_append_only_log_and_receipt_and_index(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "b" * 64

    event = S.record_prepared_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        lease_nonce="nonce-abc",
        structural_hash_before="struct-before",
        candidate_payload={"entries": [{"id": "x"}]},
    )

    # Append-only log: exactly one line, event_type prepared, 1-based seq.
    txn_dir = _txn_dir(turn_dir, plan_hash)
    log = txn_dir / S.TRANSACTION_LIFECYCLE_LOG_NAME
    assert log.exists()
    lines = _log_lines(turn_dir, plan_hash)
    assert len(lines) == 1
    assert lines[0]["event_type"] == "prepared"
    assert lines[0]["seq"] == 1
    assert lines[0]["plan_hash"] == plan_hash
    assert lines[0]["generation"] == 1

    # Derived receipt snapshot exists and equals the event.
    receipt_path = txn_dir / S.TRANSACTION_PREPARED_RECEIPT_NAME
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == event

    # Index updated: generation advanced, prepared pointer recorded.
    assert state["next_generation"] == 2
    assert state["prepared_transactions"][turn_id] == {
        "plan_hash": plan_hash,
        "generation": 1,
        "lease_nonce": "nonce-abc",
        "structural_hash_before": "struct-before",
        "timestamp": event["timestamp"],
    }


def test_generation_is_monotonic_across_prepared_transactions(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()

    _prepare("c" * 64, turn_dir=turn_dir, turn_id=turn_id, state=state)
    _prepare("d" * 64, turn_dir=turn_dir, turn_id=turn_id, state=state)
    _prepare("e" * 64, turn_dir=turn_dir, turn_id=turn_id, state=state)

    assert state["next_generation"] == 4
    # The prepared pointer always tracks the latest prepared transaction.
    assert state["prepared_transactions"][turn_id]["plan_hash"] == "e" * 64
    assert state["prepared_transactions"][turn_id]["generation"] == 3


def test_at_most_one_prepared_pointer_per_turn(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    _prepare("f" * 64, turn_dir=turn_dir, turn_id=turn_id, state=state)
    _prepare("g" * 64, turn_dir=turn_dir, turn_id=turn_id, state=state)
    assert len(state["prepared_transactions"]) == 1


# ── Finalize ────────────────────────────────────────────────────────────────


def test_finalize_appends_event_writes_receipt_clears_pointer_records_idempotency(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "1" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    generation = prep["generation"]

    finalize_event = S.record_finalized_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        structural_hash_after="struct-after",
        applied_payload={"entries": [{"id": "x", "pos": [0, 0]}]},
    )

    txn_dir = _txn_dir(turn_dir, plan_hash)
    lines = _log_lines(turn_dir, plan_hash)
    assert [l["event_type"] for l in lines] == ["prepared", "finalized"]
    assert lines[1]["seq"] == 2
    assert finalize_event["event_type"] == "finalized"
    assert (txn_dir / S.TRANSACTION_FINALIZED_RECEIPT_NAME).exists()

    # Prepared pointer cleared.
    assert turn_id not in state["prepared_transactions"]
    # Idempotency record recorded.
    rec = S.lookup_apply_idempotency_record(state, plan_hash=plan_hash, generation=generation)
    assert rec is not None
    assert rec["phase"] == "finalized"
    assert rec["receipt_path"] == S.TRANSACTION_FINALIZED_RECEIPT_NAME


def test_duplicate_finalize_is_idempotent_via_lookup(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "2" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    generation = prep["generation"]

    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=generation, structural_hash_after="h",
    )
    # Second lookup for the same identity returns the same recorded phase.
    rec = S.lookup_apply_idempotency_record(state, plan_hash=plan_hash, generation=generation)
    assert rec["phase"] == "finalized"


# ── Rollback ────────────────────────────────────────────────────────────────


def test_rollback_appends_event_clears_pointer_records_idempotency(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "3" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    generation = prep["generation"]

    S.record_rolled_back_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=generation, restored_structural_hash="struct-before",
    )

    txn_dir = _txn_dir(turn_dir, plan_hash)
    assert (txn_dir / S.TRANSACTION_ROLLBACK_RECEIPT_NAME).exists()
    assert turn_id not in state["prepared_transactions"]
    rec = S.lookup_apply_idempotency_record(state, plan_hash=plan_hash, generation=generation)
    assert rec["phase"] == "rolled_back"
    assert rec["receipt_path"] == S.TRANSACTION_ROLLBACK_RECEIPT_NAME


# ── Cancel ──────────────────────────────────────────────────────────────────


def test_cancel_marks_terminal_no_receipt_snapshot(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "4" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    generation = prep["generation"]

    S.record_cancelled_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=generation, reason="superseded",
    )

    txn_dir = _txn_dir(turn_dir, plan_hash)
    # cancelled has no derived receipt snapshot.
    assert not (txn_dir / "cancelled.json").exists()
    assert turn_id not in state["prepared_transactions"]
    rec = S.lookup_apply_idempotency_record(state, plan_hash=plan_hash, generation=generation)
    assert rec["phase"] == "cancelled"
    assert rec["receipt_path"] is None


# ── Append-only authority ───────────────────────────────────────────────────


def test_lifecycle_log_is_append_only_events_never_overwritten(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "5" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    gen = prep["generation"]
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=gen, structural_hash_after="h",
    )

    lines = _log_lines(turn_dir, plan_hash)
    # Both events retained in order; prepare not lost.
    assert len(lines) == 2
    assert lines[0]["event_type"] == "prepared"
    assert lines[1]["event_type"] == "finalized"
    # seq is monotonic within a transaction dir.
    assert lines[0]["seq"] < lines[1]["seq"]


# ── SC19: receipts are derived; recovery uses the log only ─────────────────


def test_recovery_rebuilds_index_purely_from_artifacts(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "6" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    gen = prep["generation"]
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=gen, structural_hash_after="after",
    )

    # Simulate a crash that wipes the session_state.json index entirely.
    recovered = S.recover_transaction_index(session_dir)

    assert recovered["next_generation"] == gen + 1
    # Finalized transaction is no longer "prepared".
    assert recovered["prepared_transactions"] == {}
    rec = recovered["apply_idempotency_records"][f"{plan_hash}:{gen}"]
    assert rec["phase"] == "finalized"
    assert rec["receipt_path"] == S.TRANSACTION_FINALIZED_RECEIPT_NAME


def test_recovery_ignores_derived_receipts_uses_log_only(tmp_path):
    """Deleting the derived receipt snapshots must not change recovery (SC19)."""
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "7" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    gen = prep["generation"]
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=gen, structural_hash_after="after",
    )

    txn_dir = _txn_dir(turn_dir, plan_hash)
    # Delete the derived snapshots — they are NOT authoritative.
    for name in (
        S.TRANSACTION_PREPARED_RECEIPT_NAME,
        S.TRANSACTION_FINALIZED_RECEIPT_NAME,
    ):
        (txn_dir / name).unlink(missing_ok=True)

    recovered = S.recover_transaction_index(session_dir)
    assert recovered["prepared_transactions"] == {}
    assert recovered["apply_idempotency_records"][f"{plan_hash}:{gen}"]["phase"] == "finalized"


def test_reconcile_detects_stale_index_and_repairs(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "8" * 64
    prep = _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    gen = prep["generation"]
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash=plan_hash,
        generation=gen, structural_hash_after="after",
    )

    # Corrupt the in-memory index: pretend nothing was finalized.
    stale = _state()
    changed = S.reconcile_transaction_index_from_artifacts(stale, session_dir)
    assert changed is True
    assert stale["prepared_transactions"] == {}
    assert stale["apply_idempotency_records"][f"{plan_hash}:{gen}"]["phase"] == "finalized"

    # Re-running reconcile on a fresh recovered state reports no change.
    changed_again = S.reconcile_transaction_index_from_artifacts(stale, session_dir)
    assert changed_again is False


def test_recovery_picks_highest_generation_prepared_among_superseded_attempts(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    # First prepared, then supersede with a second prepared (different plan).
    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash="9" * 64,
        lease_nonce="n1", structural_hash_before="b1",
    )
    second = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash="a" * 64,
        lease_nonce="n2", structural_hash_before="b2",
    )

    recovered = S.recover_transaction_index(session_dir)
    # The current prepared pointer is the higher-generation attempt.
    assert recovered["prepared_transactions"][turn_id]["plan_hash"] == "a" * 64
    assert recovered["prepared_transactions"][turn_id]["generation"] == second["generation"]
    assert recovered["next_generation"] == second["generation"] + 1


# ── Crash reconstruction: corrupt/partial log lines ────────────────────────


def test_read_drops_partial_trailing_line(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "p" * 64
    _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)

    txn_dir = _txn_dir(turn_dir, plan_hash)
    log = txn_dir / S.TRANSACTION_LIFECYCLE_LOG_NAME
    # Append a partial (non-JSON) line simulating a crash mid-write.
    with log.open("a", encoding="utf-8") as fh:
        fh.write('{"event_type":"finalized","receipt":')  # truncated

    events = S.read_transaction_lifecycle(txn_dir)
    assert len(events) == 1
    assert events[0]["event_type"] == "prepared"
    # Latest phase ignores the corrupt trailing fragment.
    assert S.latest_transaction_phase(txn_dir) == "prepared"


def test_read_transaction_lifecycle_returns_empty_for_missing_dir(tmp_path):
    missing = tmp_path / "does" / "not" / "exist"
    assert S.read_transaction_lifecycle(missing) == []
    assert S.latest_transaction_event(missing) is None
    assert S.latest_transaction_phase(missing) is None


def test_read_transaction_lifecycle_drops_malformed_json_lines(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    plan_hash = "q" * 64
    _prepare(plan_hash, turn_dir=turn_dir, turn_id=turn_id, state=state)
    txn_dir = _txn_dir(turn_dir, plan_hash)
    log = txn_dir / S.TRANSACTION_LIFECYCLE_LOG_NAME
    # Inject garbage between valid lines.
    original = log.read_text(encoding="utf-8")
    log.write_text("not json at all\n" + original + "\n{broken\n", encoding="utf-8")
    events = S.read_transaction_lifecycle(txn_dir)
    assert len(events) == 1
    assert events[0]["event_type"] == "prepared"


# ── Path safety ─────────────────────────────────────────────────────────────


def test_transaction_dir_for_neutralises_path_traversal_plan_hash(tmp_path):
    """``normalize_path_component`` neutralises traversal; the result must stay
    inside the turn directory (the single choke-point defence)."""
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    safe = S.transaction_dir_for(turn_dir, "../../etc")
    # The normalised component is contained within the turn directory.
    safe.relative_to(turn_dir.resolve())
    assert turn_dir.resolve() != safe
    # And the sanitised component contains no path separators or parent refs.
    assert "/" not in safe.name
    assert ".." not in safe.name


# ── now_fn injection (configurable clock) ───────────────────────────────────


def test_now_fn_is_injected_for_deterministic_timestamps(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()
    event = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash="z" * 64,
        lease_nonce="n", structural_hash_before="b",
        now_fn=lambda: "2030-01-01T00:00:00Z",
    )
    assert event["timestamp"] == "2030-01-01T00:00:00Z"


# ── Index normalisation robustness ──────────────────────────────────────────


def test_normalize_prepared_transactions_drops_invalid_entries():
    raw = {
        "turn-1": {"plan_hash": "ab", "generation": 1, "lease_nonce": "n"},
        "turn-2": {"plan_hash": "cd", "generation": -1},  # bad generation
        "turn-3": {"generation": 1},  # missing plan_hash
        "turn-4": "not-a-dict",
        "": {"plan_hash": "ef", "generation": 1},  # empty turn_id
    }
    out = S._normalize_prepared_transactions_index(raw)
    assert list(out.keys()) == ["turn-1"]


def test_normalize_apply_idempotency_drops_invalid_and_non_resolved():
    raw = {
        "ab:1": {"plan_hash": "ab", "generation": 1, "phase": "finalized"},
        "cd:2": {"plan_hash": "cd", "generation": 2, "phase": "prepared"},  # not resolved
        "ef:x": {"plan_hash": "ef", "generation": "x", "phase": "finalized"},  # bad gen
        "gh:3": {"plan_hash": "gh", "generation": 3, "phase": "rolled_back"},
        "ij:4": {"plan_hash": "", "generation": 4, "phase": "finalized"},  # missing plan_hash
    }
    out = S._normalize_apply_idempotency_records(raw)
    assert set(out.keys()) == {"ab:1", "gh:3"}
    assert out["ab:1"]["phase"] == "finalized"


def test_allocate_generation_repairs_missing_counter():
    state = {}
    assert S.allocate_generation(state) == 1
    assert state["next_generation"] == 2
    assert S.allocate_generation(state) == 2
    assert state["next_generation"] == 3


def test_allocate_generation_repairs_corrupt_counter():
    state = {"next_generation": "oops"}
    assert S.allocate_generation(state) == 1


# ── Full prepare→finalize→rollback lifecycle round-trip ────────────────────


def test_full_prepare_finalize_then_rollback_of_next_attempt(tmp_path):
    session_dir, turn_dir, turn_id = _make_session(tmp_path)
    state = _state()

    # First transaction: prepared then finalized.
    p1 = _prepare("aa" * 32, turn_dir=turn_dir, turn_id=turn_id, state=state)
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash="aa" * 32,
        generation=p1["generation"], structural_hash_after="h1",
    )
    assert turn_id not in state["prepared_transactions"]

    # Second transaction: prepared then rolled back.
    p2 = _prepare("bb" * 32, turn_dir=turn_dir, turn_id=turn_id, state=state)
    S.record_rolled_back_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id, plan_hash="bb" * 32,
        generation=p2["generation"], restored_structural_hash="h1",
    )
    assert turn_id not in state["prepared_transactions"]

    # Both resolved transactions are durable idempotency records.
    assert S.lookup_apply_idempotency_record(state, plan_hash="aa" * 32, generation=p1["generation"])["phase"] == "finalized"
    assert S.lookup_apply_idempotency_record(state, plan_hash="bb" * 32, generation=p2["generation"])["phase"] == "rolled_back"

    # Recovery reconstructs both.
    recovered = S.recover_transaction_index(session_dir)
    assert recovered["next_generation"] == p2["generation"] + 1
    assert recovered["prepared_transactions"] == {}
    assert len(recovered["apply_idempotency_records"]) == 2
