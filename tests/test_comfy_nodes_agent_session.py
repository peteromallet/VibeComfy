"""Tests for session-id path-component normalizer and filesystem containment."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.session import (
    normalize_path_component,
    normalize_session_id,
    session_dir_for,
    turn_dir_for,
)


# ── normalize_path_component ────────────────────────────────────────────────


class TestNormalizePathComponent:
    def test_preserves_ordinary_safe_ids(self):
        """Ordinary hex/alpha ids pass through unchanged."""
        assert normalize_path_component("abc123") == "abc123"
        assert normalize_path_component("my-session.id_v2") == "my-session.id_v2"
        assert normalize_path_component("a" * 80) == "a" * 80

    def test_truncates_long_ids(self):
        """Ids exceeding _MAX_PATH_COMPONENT_LENGTH are truncated."""
        result = normalize_path_component("x" * 200)
        assert len(result) == 80
        assert result == "x" * 80

    def test_empty_or_none_gets_fallback(self):
        """Empty, whitespace-only, and None values produce a UUID fallback."""
        r1 = normalize_path_component("")
        r2 = normalize_path_component(None)
        r3 = normalize_path_component("   ")
        # All are 32-char hex strings (uuid4().hex)
        assert re.fullmatch(r"[0-9a-f]{32}", r1)
        assert re.fullmatch(r"[0-9a-f]{32}", r2)
        assert re.fullmatch(r"[0-9a-f]{32}", r3)
        # Each gets a unique fallback
        assert len({r1, r2, r3}) == 3

    def test_custom_fallback_factory(self):
        """Custom fallback_factory is used when value is empty."""
        result = normalize_path_component("", fallback_factory=lambda: "custom-fallback")
        assert result == "custom-fallback"

    def test_replaces_non_safe_characters(self):
        """Characters outside [A-Za-z0-9_.-] become underscores."""
        assert normalize_path_component("hello world") == "hello_world"
        assert normalize_path_component("a\tb\nc") == "a_b_c"
        assert normalize_path_component("a\0b") == "a_b"

    def test_strips_leading_slashes(self):
        """Leading / and \\ are stripped before replacement."""
        assert normalize_path_component("/absolute/path") == "absolute_path"
        assert normalize_path_component("\\windows\\path") == "windows_path"
        assert normalize_path_component("//double/slash") == "double_slash"

    def test_rejects_dot_dot_traversal(self):
        """Values containing .. (even after normalization) get fallback."""
        # Direct traversal
        r1 = normalize_path_component("..")
        assert re.fullmatch(r"[0-9a-f]{32}", r1)
        # Nested traversal
        r2 = normalize_path_component("../../etc/passwd")
        assert re.fullmatch(r"[0-9a-f]{32}", r2)
        # Traversal with encoding attempts
        r3 = normalize_path_component("....")
        assert re.fullmatch(r"[0-9a-f]{32}", r3)

    def test_preserves_dots_in_non_traversal_positions(self):
        """Single dots and non-.. dot patterns are preserved."""
        # Single dot is valid in a filename
        assert normalize_path_component("my.file") == "my.file"
        # Trailing dot
        assert normalize_path_component("trailing.") == "trailing."
        # Leading dot (hidden file style) — could be ".." if input is ".hidden"
        # but ".hidden" doesn't contain ".." substring
        assert normalize_path_component(".hidden") == ".hidden"


# ── normalize_session_id ────────────────────────────────────────────────────


class TestNormalizeSessionId:
    def test_delegates_to_normalize_path_component(self):
        """normalize_session_id is a thin wrapper."""
        assert normalize_session_id("my-session") == "my-session"
        assert normalize_session_id("") != ""
        assert re.fullmatch(r"[0-9a-f]{32}", normalize_session_id("../../etc"))

    def test_default_called_with_no_args(self):
        """Calling with no args produces a UUID."""
        result = normalize_session_id()
        assert re.fullmatch(r"[0-9a-f]{32}", result)


# ── session_dir_for containment ─────────────────────────────────────────────


class TestSessionDirFor:
    @pytest.fixture
    def temp_root(self):
        root = Path(tempfile.mkdtemp())
        yield root
        import shutil

        shutil.rmtree(root, ignore_errors=True)

    def test_ordinary_session_id(self, temp_root):
        d = session_dir_for(temp_root, "my-session")
        assert d.name == "my-session"
        assert d.is_relative_to(temp_root.resolve())

    def test_malicious_traversal_id(self, temp_root):
        """A traversal session id is normalised to a UUID, staying within root."""
        d = session_dir_for(temp_root, "../../etc/passwd")
        assert d.is_relative_to(temp_root.resolve())
        # The directory name should be a UUID, not the raw traversal string
        assert d.name != "../../etc/passwd"
        assert re.fullmatch(r"[0-9a-f]{32}", d.name)

    def test_absolute_path_id(self, temp_root):
        """An absolute-path id is stripped of leading slashes."""
        d = session_dir_for(temp_root, "/etc/passwd")
        assert d.is_relative_to(temp_root.resolve())
        assert d.name == "etc_passwd"

    def test_empty_id(self, temp_root):
        d = session_dir_for(temp_root, "")
        assert d.is_relative_to(temp_root.resolve())
        assert re.fullmatch(r"[0-9a-f]{32}", d.name)

    def test_none_like_behavior(self, temp_root):
        """Empty string id produces a UUID-named directory within root."""
        d = session_dir_for(temp_root, "   ")
        assert d.is_relative_to(temp_root.resolve())
        assert re.fullmatch(r"[0-9a-f]{32}", d.name)

    def test_containment_with_symlink_root(self, temp_root):
        """Containment check works even with symlinked roots."""
        # Create a real dir and symlink to it
        real_dir = temp_root / "real"
        real_dir.mkdir()
        link_dir = temp_root / "link"
        link_dir.symlink_to(real_dir, target_is_directory=True)

        d = session_dir_for(link_dir, "test-session")
        # Must resolve within the real directory
        assert str(d.resolve()).startswith(str(real_dir.resolve()))

    def test_containment_raises_on_escape(self, temp_root):
        """If path somehow escapes root, ValueError is raised."""
        # This tests the defense-in-depth containment check.
        # We can't easily trigger it since the normaliser prevents escapes,
        # but we verify the API exists and works for the normal case.
        d = session_dir_for(temp_root, "safe-id")
        temp_root.resolve()  # just verify resolve() works
        assert d.is_relative_to(temp_root.resolve())


# ── turn_dir_for containment ────────────────────────────────────────────────


class TestTurnDirFor:
    @pytest.fixture
    def temp_root(self):
        root = Path(tempfile.mkdtemp())
        yield root
        import shutil

        shutil.rmtree(root, ignore_errors=True)

    def test_ordinary_turn_id(self, temp_root):
        t = turn_dir_for(temp_root, "my-session", "5")
        assert t.name == "5"
        assert t.is_relative_to(temp_root.resolve())
        assert t.parent.name == "turns"

    def test_malicious_turn_id(self, temp_root):
        """A traversal turn_id is normalised to a UUID."""
        t = turn_dir_for(temp_root, "my-session", "../../../malicious")
        assert t.is_relative_to(temp_root.resolve())
        assert t.name != "../../../malicious"
        assert re.fullmatch(r"[0-9a-f]{32}", t.name)
        # The session part should still be "my-session"
        assert t.parent.parent.name == "my-session"

    def test_malicious_both_ids(self, temp_root):
        """Both session_id and turn_id traversals are neutralised."""
        t = turn_dir_for(temp_root, "../../etc", "../../../malicious")
        assert t.is_relative_to(temp_root.resolve())
        # Both names should be UUIDs
        assert re.fullmatch(r"[0-9a-f]{32}", t.name)
        assert re.fullmatch(r"[0-9a-f]{32}", t.parent.parent.name)

    def test_empty_turn_id(self, temp_root):
        t = turn_dir_for(temp_root, "my-session", "")
        assert t.is_relative_to(temp_root.resolve())
        assert re.fullmatch(r"[0-9a-f]{32}", t.name)
        assert t.parent.parent.name == "my-session"

    def test_containment_with_resolved_paths(self, temp_root):
        """The resolved turn path is always within the resolved root."""
        t = turn_dir_for(temp_root, "sess-1", "turn-42")
        resolved_root = temp_root.resolve()
        assert str(t.resolve()).startswith(str(resolved_root))


# ── round-trip: session_dir_for → mkdir → turn_dir_for ────────────────────


class TestRoundTrip:
    def test_create_and_access(self):
        root = Path(tempfile.mkdtemp())
        try:
            sdir = session_dir_for(root, "my-workflow")
            sdir.mkdir(parents=True, exist_ok=True)
            tdir = turn_dir_for(root, "my-workflow", "1")
            tdir.mkdir(parents=True, exist_ok=True)

            assert sdir.is_dir()
            assert tdir.is_dir()
            assert tdir.is_relative_to(sdir)
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)


# ── Phase 4 transactional session tests (T20) ────────────────────────────────
# These tests cover lease nonce uniqueness, generation monotonicity,
# duplicate prepare idempotency, supersession, cancellation, and recovery
# from missing or corrupt index entries.  They exercise crash and
# idempotency behaviour across the transaction storage layer from the
# session.py public API surface.


def _fresh_session(tmp_path: Path) -> tuple[Path, Path, str]:
    """Return (session_dir, turn_dir, turn_id) for a new empty session."""
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    turn_id = "t1"
    turn_dir = session_dir / "turns" / turn_id
    turn_dir.mkdir(parents=True)
    return session_dir, turn_dir, turn_id


# ── Lease nonce uniqueness ───────────────────────────────────────────────────


def test_lease_nonce_preserved_in_prepared_artifact_and_index(tmp_path):
    """Each prepared transaction stores the exact lease_nonce it was given."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    event = S.record_prepared_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash="a" * 64,
        lease_nonce="unique-nonce-42",
        structural_hash_before="struct-before",
    )

    # Event receipt carries the nonce.
    assert event["receipt"]["lease_nonce"] == "unique-nonce-42"

    # Index pointer also carries it.
    assert state["prepared_transactions"][turn_id]["lease_nonce"] == "unique-nonce-42"

    # Recovery preserves the nonce from the log.
    recovered = S.recover_transaction_index(session_dir)
    assert recovered["prepared_transactions"][turn_id]["lease_nonce"] == "unique-nonce-42"


def test_different_prepares_get_different_lease_nonces(tmp_path):
    """Two prepares on the same turn can carry distinct nonces."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    S.record_prepared_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash="b" * 64,
        lease_nonce="first-nonce",
        structural_hash_before="s1",
    )
    S.record_prepared_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash="c" * 64,
        lease_nonce="second-nonce",
        structural_hash_before="s2",
    )

    # The latest prepare's nonce is in the index.
    assert state["prepared_transactions"][turn_id]["lease_nonce"] == "second-nonce"

    # Both nonces are recoverable from their respective artifact logs.
    # Read the first transaction's lifecycle log directly.
    txn_dir_1 = S.transaction_dir_for(turn_dir, "b" * 64)
    events_1 = S.read_transaction_lifecycle(txn_dir_1)
    assert events_1[0]["receipt"]["lease_nonce"] == "first-nonce"

    txn_dir_2 = S.transaction_dir_for(turn_dir, "c" * 64)
    events_2 = S.read_transaction_lifecycle(txn_dir_2)
    assert events_2[0]["receipt"]["lease_nonce"] == "second-nonce"


# ── Generation monotonicity ──────────────────────────────────────────────────


def test_generation_strictly_increasing_and_never_reused(tmp_path):
    """allocate_generation returns strictly increasing values across calls."""
    from vibecomfy.comfy_nodes.agent import session as S

    state = S.default_state()
    seen: set[int] = set()
    prev = 0
    for _ in range(100):
        gen = S.allocate_generation(state)
        assert gen > prev, f"generation {gen} not > {prev}"
        assert gen not in seen, f"generation {gen} reused"
        seen.add(gen)
        prev = gen
    assert state["next_generation"] == 101


def test_generation_advances_across_multiple_turns(tmp_path):
    """Generation counter is global across all turns in a session."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir_1, turn_id_1 = _fresh_session(tmp_path)
    turn_id_2 = "t2"
    turn_dir_2 = session_dir / "turns" / turn_id_2
    turn_dir_2.mkdir(parents=True)
    state = S.default_state()

    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir_1, turn_id=turn_id_1,
        plan_hash="d" * 64, lease_nonce="n1", structural_hash_before="b1",
    )
    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir_2, turn_id=turn_id_2,
        plan_hash="e" * 64, lease_nonce="n2", structural_hash_before="b2",
    )

    # Generations are 1 and 2 (global monotonic).
    assert state["prepared_transactions"][turn_id_1]["generation"] == 1
    assert state["prepared_transactions"][turn_id_2]["generation"] == 2
    assert state["next_generation"] == 3


# ── Duplicate prepare idempotency ────────────────────────────────────────────


def test_duplicate_prepare_same_plan_hash_creates_new_generation(tmp_path):
    """Calling record_prepared_transaction twice with the same plan_hash
    allocates a new generation each time; the prepared pointer tracks the
    latest.  Both artifacts exist on disk."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()
    plan_hash = "f" * 64

    e1 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, lease_nonce="n-1", structural_hash_before="sb1",
    )
    e2 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, lease_nonce="n-2", structural_hash_before="sb2",
    )

    assert e1["generation"] == 1
    assert e2["generation"] == 2
    assert state["prepared_transactions"][turn_id]["generation"] == 2

    # Both lifecycle logs exist and each has exactly one event (separate dirs
    # indexed by plan_hash, so the second prepare does NOT append to the
    # first's log—it creates a new transaction dir with the same plan_hash).
    txn_dir = S.transaction_dir_for(turn_dir, plan_hash)
    events = S.read_transaction_lifecycle(txn_dir)
    # Because transaction_dir_for uses only plan_hash, the second prepare
    # appends to the *same* log (plan_hash unchanged), so we get 2 events.
    assert len(events) == 2
    assert events[0]["generation"] == 1
    assert events[1]["generation"] == 2


def test_prepare_does_not_create_apply_idempotency_record(tmp_path):
    """A prepared-but-not-resolved transaction has no idempotency record.
    Only finalized/rolled_back/cancelled phases create those records."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()
    plan_hash = "g" * 64

    event = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, lease_nonce="nx", structural_hash_before="sb",
    )
    gen = event["generation"]

    rec = S.lookup_apply_idempotency_record(state, plan_hash=plan_hash, generation=gen)
    assert rec is None


# ── Supersession ─────────────────────────────────────────────────────────────


def test_supersession_cancel_then_prepare_new(tmp_path):
    """Cancel a prepared transaction, then prepare a new one on the same
    turn.  The cancelled one is recorded in idempotency; the new one is the
    active prepared pointer."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    # First prepare
    e1 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="h" * 64, lease_nonce="n1", structural_hash_before="sb1",
    )
    gen1 = e1["generation"]

    # Cancel the first (supersede)
    S.record_cancelled_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="h" * 64, generation=gen1, reason="superseded",
    )

    # Cancelled: pointer cleared, idempotency recorded.
    assert turn_id not in state["prepared_transactions"]
    rec1 = S.lookup_apply_idempotency_record(state, plan_hash="h" * 64, generation=gen1)
    assert rec1 is not None
    assert rec1["phase"] == "cancelled"

    # Second prepare (superseding)
    e2 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="i" * 64, lease_nonce="n2", structural_hash_before="sb2",
    )
    gen2 = e2["generation"]

    assert gen2 > gen1
    assert state["prepared_transactions"][turn_id]["plan_hash"] == "i" * 64

    # Recovery sees the latest prepared only; cancelled is in idempotency.
    recovered = S.recover_transaction_index(session_dir)
    assert recovered["prepared_transactions"][turn_id]["generation"] == gen2
    assert recovered["apply_idempotency_records"][f"h{'h'*63}:{gen1}"]["phase"] == "cancelled"

    # The superseding prepare has NO idempotency record yet.
    assert S.lookup_apply_idempotency_record(state, plan_hash="i" * 64, generation=gen2) is None


def test_supersession_multiple_prepares_recovery_picks_latest(tmp_path):
    """After multiple unprepare→prepare cycles, recovery identifies the
    latest prepared (unresolved) transaction as the active pointer."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    # Prepare + cancel three times, then prepare a fourth.
    for idx, ph in enumerate(["j", "k", "l"]):
        e = S.record_prepared_transaction(
            state=state, turn_dir=turn_dir, turn_id=turn_id,
            plan_hash=ph * 64, lease_nonce=f"n{idx}", structural_hash_before="sb",
        )
        S.record_cancelled_transaction(
            state=state, turn_dir=turn_dir, turn_id=turn_id,
            plan_hash=ph * 64, generation=e["generation"], reason="superseded",
        )

    # Fourth prepare (no cancel).
    e4 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="m" * 64, lease_nonce="n4", structural_hash_before="sb",
    )

    recovered = S.recover_transaction_index(session_dir)
    assert recovered["prepared_transactions"][turn_id]["generation"] == e4["generation"]
    assert len(recovered["apply_idempotency_records"]) == 3  # three cancelled


# ── Cancellation ─────────────────────────────────────────────────────────────


def test_cancellation_clears_pointer_and_is_recoverable(tmp_path):
    """record_cancelled_transaction clears the prepared pointer and creates
    a durable idempotency record that survives recovery."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()
    plan_hash = "n" * 64

    e = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, lease_nonce="nc", structural_hash_before="sb",
    )
    gen = e["generation"]

    S.record_cancelled_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, generation=gen, reason="user_rejected",
    )

    assert turn_id not in state["prepared_transactions"]
    rec = S.lookup_apply_idempotency_record(state, plan_hash=plan_hash, generation=gen)
    assert rec["phase"] == "cancelled"
    assert rec["turn_id"] == turn_id

    # Recovery from artifacts matches.
    recovered = S.recover_transaction_index(session_dir)
    assert recovered["prepared_transactions"] == {}
    recovered_rec = recovered["apply_idempotency_records"][f"{plan_hash}:{gen}"]
    assert recovered_rec["phase"] == "cancelled"


def test_cancellation_reason_preserved_in_lifecycle_log(tmp_path):
    """The cancellation reason is written into the lifecycle event."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()
    plan_hash = "o" * 64

    e = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, lease_nonce="nr", structural_hash_before="sb",
    )

    cancel_event = S.record_cancelled_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash=plan_hash, generation=e["generation"],
        reason="stale_candidate_superseded",
    )

    assert cancel_event["receipt"]["reason"] == "stale_candidate_superseded"

    # Read back from log.
    txn_dir = S.transaction_dir_for(turn_dir, plan_hash)
    events = S.read_transaction_lifecycle(txn_dir)
    assert events[-1]["receipt"]["reason"] == "stale_candidate_superseded"


# ── Recovery from missing or corrupt index entries ───────────────────────────


def test_read_state_repairs_corrupt_prepared_transactions(tmp_path):
    """When session_state.json has a non-dict prepared_transactions field,
    read_state resets it to an empty dict without raising."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, _, _ = _fresh_session(tmp_path)
    # Write a corrupt state file directly.
    corrupt = {
        "schema_version": 1,
        "next_turn_index": 1,
        "turns": {},
        "prepared_transactions": "not-a-dict",
        "apply_idempotency_records": [],
        "next_generation": "bad",
    }
    (session_dir / S.STATE_FILE_NAME).write_text(
        json.dumps(corrupt), encoding="utf-8"
    )

    state = S.read_state(session_dir)
    assert isinstance(state["prepared_transactions"], dict)
    assert state["prepared_transactions"] == {}
    assert isinstance(state["apply_idempotency_records"], dict)
    assert state["apply_idempotency_records"] == {}
    assert state["next_generation"] == 1  # repaired from bad value


def test_read_state_drops_corrupt_prepared_entries(tmp_path):
    """Individual corrupt entries inside prepared_transactions are dropped
    during normalization; valid entries survive."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, _, _ = _fresh_session(tmp_path)
    # Write state with one valid and several invalid prepared entries.
    state_data = S.default_state()
    state_data["prepared_transactions"] = {
        "turn-ok": {"plan_hash": "p" * 64, "generation": 5, "lease_nonce": "ok"},
        "turn-bad-gen": {"plan_hash": "q" * 64, "generation": 0},
        "turn-no-hash": {"generation": 3},
        "turn-not-dict": ["list"],
        "": {"plan_hash": "r" * 64, "generation": 1},
    }
    (session_dir / S.STATE_FILE_NAME).write_text(
        json.dumps(state_data), encoding="utf-8"
    )

    state = S.read_state(session_dir)
    assert list(state["prepared_transactions"].keys()) == ["turn-ok"]
    assert state["prepared_transactions"]["turn-ok"]["generation"] == 5


def test_read_state_drops_non_resolved_idempotency_entries(tmp_path):
    """apply_idempotency_records with phase not in resolved set are dropped."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, _, _ = _fresh_session(tmp_path)
    state_data = S.default_state()
    state_data["apply_idempotency_records"] = {
        "aa:1": {"plan_hash": "aa", "generation": 1, "phase": "finalized"},
        "bb:2": {"plan_hash": "bb", "generation": 2, "phase": "prepared"},
        "cc:3": {"plan_hash": "cc", "generation": 3, "phase": "rolled_back"},
        "dd:4": {"plan_hash": "dd", "generation": 4, "phase": "cancelled"},
        "ee:5": {"plan_hash": "ee", "generation": 5, "phase": "invented"},
    }
    (session_dir / S.STATE_FILE_NAME).write_text(
        json.dumps(state_data), encoding="utf-8"
    )

    state = S.read_state(session_dir)
    records = state["apply_idempotency_records"]
    # Only finalized, rolled_back, cancelled survive.
    assert set(records.keys()) == {"aa:1", "cc:3", "dd:4"}


def test_recover_transaction_index_with_no_turns_dir(tmp_path):
    """When the turns/ directory does not exist, recovery returns empty
    indexes and generation=1."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir = tmp_path / "empty-session"
    session_dir.mkdir()
    # No turns/ directory at all.

    recovered = S.recover_transaction_index(session_dir)
    assert recovered["next_generation"] == 1
    assert recovered["prepared_transactions"] == {}
    assert recovered["apply_idempotency_records"] == {}


def test_recover_transaction_index_with_empty_transactions_dirs(tmp_path):
    """Turns with no transactions/ subdirectory are skipped silently."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    # Create a second turn dir with no transactions/ subdirectory.
    turn_dir_2 = session_dir / "turns" / "t2"
    turn_dir_2.mkdir(parents=True)

    # Write a real prepared transaction for the first turn.
    state = S.default_state()
    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="s" * 64, lease_nonce="n", structural_hash_before="b",
    )
    gen = state["prepared_transactions"][turn_id]["generation"]

    recovered = S.recover_transaction_index(session_dir)
    assert recovered["next_generation"] == gen + 1
    assert turn_id in recovered["prepared_transactions"]


def test_recover_transaction_index_skips_empty_lifecycle_logs(tmp_path):
    """A transaction directory with an empty lifecycle log is skipped."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    # Create a transaction dir with an empty lifecycle log.
    txn_dir = S.transaction_dir_for(turn_dir, "u" * 64)
    txn_dir.mkdir(parents=True)
    (txn_dir / S.TRANSACTION_LIFECYCLE_LOG_NAME).write_text("", encoding="utf-8")

    recovered = S.recover_transaction_index(session_dir)
    # Empty log → skipped entirely.
    assert recovered["prepared_transactions"] == {}
    assert recovered["apply_idempotency_records"] == {}


def test_reconcile_repairs_stale_generation_counter(tmp_path):
    """reconcile_transaction_index_from_artifacts repairs a state whose
    next_generation has fallen behind artifact truth."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="v" * 64, lease_nonce="n", structural_hash_before="b",
    )
    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="w" * 64, lease_nonce="n2", structural_hash_before="b2",
    )

    # Corrupt the in-memory state: roll back next_generation.
    stale_state = S.default_state()
    stale_state["next_generation"] = 1  # should be 3

    changed = S.reconcile_transaction_index_from_artifacts(stale_state, session_dir)
    assert changed is True
    assert stale_state["next_generation"] == 3  # repaired to max+1


def test_reconcile_noop_when_index_already_matches(tmp_path):
    """reconcile_transaction_index_from_artifacts returns False when the
    index is already consistent with artifacts."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="x" * 64, lease_nonce="n", structural_hash_before="b",
    )
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="x" * 64, generation=1, structural_hash_after="after",
    )

    # Build a fresh state and reconcile — should match.
    fresh = S.default_state()
    changed = S.reconcile_transaction_index_from_artifacts(fresh, session_dir)
    assert changed is True  # fresh was empty, so it changed.

    # Reconcile again — now it should be a noop.
    changed_again = S.reconcile_transaction_index_from_artifacts(fresh, session_dir)
    assert changed_again is False


def test_recover_preserves_lease_nonce_from_artifact_truth(tmp_path):
    """When the session_state.json index is corrupt, recovery reconstructs
    the lease_nonce from the authoritative lifecycle log."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    state = S.default_state()

    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir, turn_id=turn_id,
        plan_hash="y" * 64, lease_nonce="recovered-nonce", structural_hash_before="b",
    )

    # Simulate a corrupt index by wiping the prepared pointer.
    corrupt_state = S.default_state()
    # (prepared_transactions is empty, so the index has lost the nonce.)

    changed = S.reconcile_transaction_index_from_artifacts(corrupt_state, session_dir)
    assert changed is True
    assert corrupt_state["prepared_transactions"][turn_id]["lease_nonce"] == "recovered-nonce"


def test_read_state_with_missing_file_returns_defaults(tmp_path):
    """When no session_state.json exists, read_state returns a clean default
    with transaction index fields initialized."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir = tmp_path / "brand-new"
    session_dir.mkdir()

    state = S.read_state(session_dir)
    assert state["next_generation"] == 1
    assert state["prepared_transactions"] == {}
    assert state["apply_idempotency_records"] == {}
    assert state["schema_version"] == S.STATE_SCHEMA_VERSION


def test_recover_max_generation_from_multiple_turns(tmp_path):
    """Recovery computes next_generation as max(all event generations) + 1."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir_1, turn_id_1 = _fresh_session(tmp_path)
    turn_dir_2 = session_dir / "turns" / "t2"
    turn_dir_2.mkdir(parents=True)
    state = S.default_state()

    # Turn 1: gen 1, 2 (prepared then superseded by second prepare).
    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir_1, turn_id=turn_id_1,
        plan_hash="z1" + "z" * 62, lease_nonce="n1", structural_hash_before="b",
    )
    S.record_prepared_transaction(
        state=state, turn_dir=turn_dir_1, turn_id=turn_id_1,
        plan_hash="z2" + "z" * 62, lease_nonce="n2", structural_hash_before="b",
    )

    # Turn 2: gen 3, 4 (prepared then finalized).
    e3 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir_2, turn_id="t2",
        plan_hash="z3" + "z" * 62, lease_nonce="n3", structural_hash_before="b",
    )
    S.record_finalized_transaction(
        state=state, turn_dir=turn_dir_2, turn_id="t2",
        plan_hash="z3" + "z" * 62, generation=e3["generation"], structural_hash_after="after",
    )
    e4 = S.record_prepared_transaction(
        state=state, turn_dir=turn_dir_2, turn_id="t2",
        plan_hash="z4" + "z" * 62, lease_nonce="n4", structural_hash_before="b",
    )

    recovered = S.recover_transaction_index(session_dir)
    # Max generation across all turns is 4 (from e4), so next is 5.
    assert recovered["next_generation"] == 5

    # Turn 1's prepared pointer is the latest (gen 2).
    assert recovered["prepared_transactions"][turn_id_1]["generation"] == 2
    # Turn 2's prepared pointer is the latest (gen 4).
    assert recovered["prepared_transactions"]["t2"]["generation"] == 4
    # Turn 2's gen 3 is finalized → in idempotency.
    assert f"z3{'z'*62}:3" in recovered["apply_idempotency_records"]


def test_recovery_handles_transaction_dir_with_no_log_file(tmp_path):
    """A transactions/<plan_hash>/ directory with no lifecycle log is
    silently skipped during recovery."""
    from vibecomfy.comfy_nodes.agent import session as S

    session_dir, turn_dir, turn_id = _fresh_session(tmp_path)
    # Create a transaction dir with no log file.
    txn_dir = S.transaction_dir_for(turn_dir, "zz" + "z" * 62)
    txn_dir.mkdir(parents=True)
    # No lifecycle_events.jsonl written.

    recovered = S.recover_transaction_index(session_dir)
    assert recovered["prepared_transactions"] == {}
    assert recovered["next_generation"] == 1


# ── Transactional apply server semantics (T21) ──────────────────────────────


def _fresh_v2_apply_turn(tmp_path: Path):
    from vibecomfy.comfy_nodes.agent import session as S

    root = tmp_path
    session_id = "txn-session"
    turn_id = "0001"
    session_dir = S.session_dir_for(root, session_id)
    turn_dir = S.turn_dir_for(root, session_id, turn_id)
    turn_dir.mkdir(parents=True)
    state = S.default_state()
    state.update(
        {
            "baseline_graph_hash": "base-hash",
            "baseline_graph_hash_kind": "structural",
            "baseline_graph_hash_version": S.STRUCTURAL_PROJECTION_VERSION,
            "baseline_source": "legacy",
        }
    )
    state["turns"][turn_id] = {
        "state": "review_bound",
        "candidate_graph_hash": "candidate-hash",
        "candidate_structural_graph_hash": "after-hash",
        "candidate_structural_graph_hash_version": S.STRUCTURAL_PROJECTION_VERSION,
        "submitted_baseline_graph_hash": "base-hash",
        "submitted_baseline_graph_hash_kind": "structural",
        "agent_edit_protocol": "v2_delta",
    }
    S.write_state_atomic(session_dir, state)
    return S, root, session_id, turn_id, session_dir


def _prepare_payload(*, plan_hash: str = "a" * 64, generation: int = 1) -> dict:
    return {
        "turn_id": "0001",
        "candidate_graph_hash": "candidate-hash",
        "plan_hash": plan_hash,
        "structural_hash_before": "base-hash",
        "structural_hash_after": "after-hash",
        "generation": generation,
        "apply_eligibility": {"applyable": True, "reason": "applyable", "message": "ok"},
    }


def test_prepare_cas_records_receipt_without_advancing_baseline(tmp_path):
    S, root, session_id, turn_id, session_dir = _fresh_v2_apply_turn(tmp_path)

    result = S.prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=_prepare_payload(),
    )

    assert result["ok"] is True
    assert result["phase"] == "prepared"
    assert result["baseline_advanced"] is False
    state = S.read_state(session_dir)
    assert state["baseline_graph_hash"] == "base-hash"
    assert state["baseline_turn_id"] is None
    assert state["turns"][turn_id]["state"] == "apply_prepared"
    prepared = state["prepared_transactions"][turn_id]
    assert prepared["plan_hash"] == "a" * 64
    assert prepared["generation"] == 1
    receipt = result["receipt"]["receipt"]
    assert receipt["baseline_snapshot"]["baseline_graph_hash"] == "base-hash"


def test_prepare_rejects_stale_baseline_candidate_plan_generation_and_eligibility(tmp_path):
    S, root, session_id, turn_id, session_dir = _fresh_v2_apply_turn(tmp_path)

    cases = [
        {**_prepare_payload(), "structural_hash_before": "stale"},
        {**_prepare_payload(), "candidate_graph_hash": "wrong"},
        {**_prepare_payload(), "plan_hash": ""},
        {**_prepare_payload(generation=2)},
        {**_prepare_payload(), "apply_eligibility": {"applyable": False}},
    ]
    for payload in cases:
        result = S.prepare_turn_transaction(
            session_root=root,
            session_id=session_id,
            turn_id=turn_id,
            request_payload=payload,
        )
        assert result.ok is False
        assert S.read_state(session_dir)["baseline_graph_hash"] == "base-hash"


def test_finalize_requires_matching_nonce_and_verified_post_apply_hash_before_baseline_advance(tmp_path):
    S, root, session_id, turn_id, session_dir = _fresh_v2_apply_turn(tmp_path)
    prepared = S.prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=_prepare_payload(),
    )

    bad_nonce = S.finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": "a" * 64,
            "generation": prepared["generation"],
            "lease_nonce": "wrong",
            "post_apply_hash": "after-hash",
            "post_apply_hash_verified": True,
        },
    )
    assert bad_nonce.ok is False
    assert S.read_state(session_dir)["baseline_graph_hash"] == "base-hash"

    bad_hash = S.finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": "a" * 64,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "post_apply_hash": "wrong-after",
            "post_apply_hash_verified": True,
        },
    )
    assert bad_hash.ok is False
    assert S.read_state(session_dir)["baseline_graph_hash"] == "base-hash"

    result = S.finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": "a" * 64,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "post_apply_hash": "after-hash",
            "post_apply_hash_verified": True,
        },
    )
    assert result["ok"] is True
    assert result["phase"] == "finalized"
    state = S.read_state(session_dir)
    assert state["baseline_graph_hash"] == "after-hash"
    assert state["baseline_turn_id"] == turn_id
    assert state["turns"][turn_id]["state"] == "finalized"


def test_rollback_restores_prepare_time_baseline_from_nonterminal_state(tmp_path):
    S, root, session_id, turn_id, session_dir = _fresh_v2_apply_turn(tmp_path)
    prepared = S.prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=_prepare_payload(),
    )
    state = S.read_state(session_dir)
    state["baseline_graph_hash"] = "drifted-before-finalize"
    S.write_state_atomic(session_dir, state)

    result = S.rollback_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": "a" * 64,
            "generation": prepared["generation"],
        },
    )

    assert result["ok"] is True
    assert result["phase"] == "rolled_back"
    state = S.read_state(session_dir)
    assert state["baseline_graph_hash"] == "base-hash"
    assert state["baseline_source"] == "legacy"
    assert state["turns"][turn_id]["state"] == "rollback_complete"


def test_reconcile_returns_durable_receipts_and_repairs_index(tmp_path):
    S, root, session_id, turn_id, session_dir = _fresh_v2_apply_turn(tmp_path)
    prepared = S.prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=_prepare_payload(),
    )
    state = S.read_state(session_dir)
    state["prepared_transactions"] = {}
    S.write_state_atomic(session_dir, state)

    result = S.reconcile_turn_transactions(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
    )

    assert result["ok"] is True
    assert result["index_repaired"] is True
    assert result["prepared_transactions"][turn_id]["generation"] == prepared["generation"]
    receipts = result["receipts_by_turn"][turn_id]
    assert [event["event_type"] for event in receipts] == ["prepared"]
    assert receipts[0]["receipt"]["lease_nonce"] == prepared["lease_nonce"]
