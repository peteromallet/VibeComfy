from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import socket
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterator, Literal

from .contracts import DiagnosticRecord, FailureEnvelope, FailureKind, TurnContext, failure_envelope
from .candidate_transaction import (
    CANDIDATE_TRANSACTION_V2,
    CANDIDATE_TRANSACTION_FILENAME,
    LAYOUT_VERIFICATION_CONTRACT_VERSION,
    LAYOUT_VERIFICATION_PROJECTION,
    build_candidate_transaction,
    canonical_transaction_state,
    classify_legacy_migration_v1,
    project_transaction_state,
    validate_candidate_transaction,
)
from .projection_registry_v1 import (
    browser_layout_scope_issues_v1 as _registry_browser_layout_scope_issues,
    build_layout_graph_projection as _registry_layout_graph_projection,
    build_structural_graph_projection as _registry_structural_graph_projection,
    canonical_json_bytes_v1 as _registry_canonical_json_bytes,
    layout_graph_hash_compat as _registry_layout_graph_hash,
    projection_reference_v1,
    structural_graph_hash_compat as _registry_structural_graph_hash,
    workflow_identity_v1,
)
from .mutation_materialization_v1 import build_mutation_materialization_v1
from .layout_operation_v1 import build_layout_operation_envelope
from vibecomfy.porting.edit.ops import parse_edit_delta

_LOGGER = logging.getLogger(__name__)

STATE_FILE_NAME = "session_state.json"
LOCK_FILE_NAME = ".session_state.lock"
STATE_SCHEMA_VERSION = 1
# Bumped whenever `structural_graph_projection` changes shape. A baseline hash
# stored by an older version is recomputed from the on-disk accepted graph on
# read, so a projection change never strands an open session on a stale baseline
# it can no longer match (the StaleStateMismatch-on-every-submit failure mode).
STRUCTURAL_PROJECTION_VERSION = 3
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_LEASE_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.025

# ── Phase 4 transactional storage constants (T19) ───────────────────────────
# Authoritative per-turn artifacts live under
# ``turns/<turn_id>/transactions/<plan_hash>/``.  The append-only
# ``lifecycle_events.jsonl`` is the single source of truth; the ``*.json``
# receipt snapshots are derived for fast reload, and the
# ``session_state.json`` index entries are a discoverable cache that can always
# be rebuilt from the artifacts (see ``recover_transaction_index``).
TRANSACTIONS_DIR_NAME = "transactions"
TRANSACTION_LIFECYCLE_LOG_NAME = "lifecycle_events.jsonl"
TRANSACTION_PREPARED_RECEIPT_NAME = "prepared.json"
TRANSACTION_VERIFIED_RECEIPT_NAME = "canvas_verified.json"
TRANSACTION_FINALIZED_RECEIPT_NAME = "finalized.json"
TRANSACTION_ROLLBACK_RECEIPT_NAME = "rollback.json"
# Event-type → receipt snapshot filename (the snapshot is derived from the event).
TRANSACTION_RECEIPT_BY_EVENT: Mapping[str, str] = MappingProxyType(
    {
        "prepared": TRANSACTION_PREPARED_RECEIPT_NAME,
        "finalized": TRANSACTION_FINALIZED_RECEIPT_NAME,
        "canvas_verified": TRANSACTION_VERIFIED_RECEIPT_NAME,
        "rollback_complete": TRANSACTION_ROLLBACK_RECEIPT_NAME,
        # Read-only historical adapter.
        "rolled_back": TRANSACTION_ROLLBACK_RECEIPT_NAME,
    }
)
# Lifecycle phases that resolve a transaction (no longer merely "prepared").
_TRANSACTION_RESOLVED_PHASES: frozenset[str] = frozenset(
    {
        "finalized",
        "rollback_complete",
        "discarded",
        "superseded",
        # Read-only historical adapter.
        "rolled_back",
        "cancelled",
    }
)

def _process_alive(pid: int) -> bool:
    """Return ``True`` when a process with *pid* exists on this host."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    else:
        return True


OperationScope = Literal["edit", "accept", "reject", "rebaseline"]
# ── TurnState lifecycle ──────────────────────────────────────────────────
# V1 historical states (read-only migration; never authored for new turns):
#   candidate, accepted, rejected, unknown, no_candidate
#
# V2 lifecycle states (authored for turns with agent_edit_protocol >= v2_delta):
#   submitted         – turn allocated, no candidate yet
#   candidate_ready   – candidate computed and persisted, ready for review
#   review_bound      – candidate has been reviewed / previewed by browser
#   prepared          – prepare route completed (CAS without baseline advance)
#   canvas_verified   – browser verified post-apply canvas hash matches plan hash
#   finalized         – finalize route succeeded; baseline advanced
#   rollback_complete – rollback confirmed and baseline restored
#   discarded         – unprepared candidate explicitly rejected by the user
#
# Valid V2 forward transitions (every state reachable from submitted):
#   submitted       → candidate_ready
#   candidate_ready → review_bound
#   review_bound    → prepared
#   prepared        → canvas_verified  | rollback_complete
#   canvas_verified → finalized        | rollback_complete
#   finalized       → (terminal)
#   rollback_complete → (terminal)
#   candidate_ready / review_bound → discarded (terminal, baseline unchanged)
# V2 turns can also transition to unknown (superseded) from any pre-finalized state.
TurnState = Literal[
    # V1 historical (read-only migration)
    "candidate",
    "accepted",
    "rejected",
    "unknown",
    "no_candidate",
    # V2 lifecycle
    "submitted",
    "candidate_ready",
    "review_bound",
    "prepared",
    "canvas_verified",
    "finalized",
    "rollback_complete",
    "discarded",
    "recoverable_error",
    "superseded",
]

# V2 states that are terminal / should not be mutated further by accept/reject.
_V2_TERMINAL_STATES: frozenset[TurnState] = frozenset(
    {"finalized", "rollback_complete", "discarded", "superseded"}
)

# V2 states that are pre-finalize / still mutable.
_V2_PRE_FINALIZE_STATES: frozenset[TurnState] = frozenset({
    "submitted",
    "candidate_ready",
    "review_bound",
    "prepared",
    "canvas_verified",
    "recoverable_error",
})

# Durable states whose turn still owns a candidate that the browser must be
# able to rehydrate.  Keep this separate from ``_V2_PRE_FINALIZE_STATES``:
# ``submitted`` has no candidate yet, while the legacy ``candidate`` state is
# still a reviewable persisted state during the V1 migration window.
REVIEWABLE_CANDIDATE_STATES: frozenset[TurnState] = frozenset({
    "candidate",
    "candidate_ready",
    "review_bound",
    "prepared",
    "canvas_verified",
    "recoverable_error",
})

# Historical V1 states that may appear in persisted state files.
_V1_HISTORICAL_STATES: frozenset[TurnState] = frozenset({
    "candidate",
    "accepted",
    "rejected",
    "unknown",
    "no_candidate",
})
# Event-type → V2 TurnState it represents (the latest event of a transaction
# pins the turn's authoritative lifecycle state after recovery).
_TRANSACTION_EVENT_TO_TURN_STATE: Mapping[str, TurnState] = MappingProxyType(
    {
        "prepared": "prepared",
        "finalized": "finalized",
        "rolled_back": "rollback_complete",
        "rollback_complete": "rollback_complete",
        "discarded": "discarded",
        "cancelled": "superseded",
        "superseded": "superseded",
        "canvas_verified": "canvas_verified",
    }
)
BaselineSource = Literal["none", "turn", "rebaseline", "legacy"]
RebaselineReason = Literal["undo", "stale_state_recovery", "continue_from_canvas"]
REBASELINE_REASONS: tuple[RebaselineReason, ...] = (
    "undo",
    "stale_state_recovery",
    "continue_from_canvas",
)


@dataclass(frozen=True)
class IdempotencyReplay:
    response: dict[str, Any]
    record: dict[str, Any]


@dataclass(frozen=True)
class IdempotencyConflict:
    failure: FailureEnvelope
    record: dict[str, Any]


@dataclass(frozen=True)
class TurnAllocation:
    context: TurnContext
    session_dir: Path
    turn_dir: Path
    state: dict[str, Any]
    request_hash: str
    unknown_transitions: tuple[dict[str, Any], ...] = ()
    idempotency_record_key: str | None = None
    replay: IdempotencyReplay | None = None
    conflict: IdempotencyConflict | None = None


@dataclass(frozen=True)
class ExpectedBaseline:
    reliable: bool
    graph_hash: str | None
    hash_kind: str | None
    source: str | None
    reason: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class RebaselineReplay:
    response: dict[str, Any]
    record: dict[str, Any]


@dataclass(frozen=True)
class RebaselineConflict:
    failure: FailureEnvelope
    record: dict[str, Any]


# ── Authoritative path-component normalizer ────────────────────────────────
# Every session_id and turn_id MUST pass through this boundary before it
# becomes a filesystem path component.  This is the single choke-point that
# prevents path-traversal attacks (e.g. "../../etc/passwd") and prevents
# absolute-path injection from callers that receive raw user input.

_MAX_PATH_COMPONENT_LENGTH = 80
_PATH_COMPONENT_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _deterministic_fallback(raw: str) -> str:
    """Return a deterministic 32-char hex string for *raw*.

    Uses SHA-256 so the same rejected input always maps to the same safe
    component.  This keeps ``_safe_session_id`` backwards-compatible: callers
    that sanitise a malicious session id once and later look it up from
    storage get the same normalised id.
    """
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]


def normalize_path_component(
    value: str | None,
    *,
    fallback_factory: Callable[[], str] | None = None,
) -> str:
    """Return *value* as a single safe filesystem path component.

    *   Characters outside ``[A-Za-z0-9_.-]`` are replaced with ``_``.
    *   The result is truncated to ``_MAX_PATH_COMPONENT_LENGTH`` chars.
    *   Empty/whitespace-only values produce the *fallback_factory* result
        (default: ``uuid.uuid4().hex``).
    *   Values that still contain ``..`` after normalisation are rejected
        (a deterministic SHA-256 fallback is used so the same raw value always
        maps to the same safe component) — no normalised component can act as
        a parent-directory reference.
    *   Leading ``/`` and ``\\\\`` are stripped so the component can never
        constitute an absolute path when joined to a root.
    """
    if fallback_factory is None:
        fallback_factory = lambda: uuid.uuid4().hex

    if not isinstance(value, str) or not value.strip():
        return fallback_factory()

    # Strip leading slashes/backslashes first so they don't become
    # leading underscores; then replace remaining dangerous characters.
    safe = value.strip().lstrip("/").lstrip("\\\\")
    safe = _PATH_COMPONENT_SAFE_RE.sub("_", safe)
    safe = safe[:_MAX_PATH_COMPONENT_LENGTH]

    if not safe or ".." in safe:
        # Deterministic fallback: same rejected raw value → same safe id.
        # This preserves backwards compat with _safe_session_id callers
        # that sanitise once and look up later (e.g. read_session_chat).
        return _deterministic_fallback(value)

    return safe


def normalize_session_id(value: str | None = None) -> str:
    """Normalize a session id to a single safe path component.

    This is the authoritative entry-point used by ``session_dir_for`` and
    ``turn_dir_for``.  Callers that obtain raw session ids from HTTP routes
    or executor requests can also call it directly for early validation.
    """
    return normalize_path_component(value)


def session_dir_for(root: Path, session_id: str) -> Path:
    """Return the canonical session directory for *session_id* under *root*.

    The *session_id* is normalised through ``normalize_session_id`` so the
    result is always a single path component safely contained within *root*.
    """
    safe_id = normalize_session_id(session_id)
    candidate = (root / safe_id).resolve()
    # Containment check: the resolved path must be within *root* (or be the
    # root itself).  This is a defence-in-depth guard in case a future
    # normalizer regression lets a traversal component through.
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"session_id {session_id!r} resolves outside session root "
            f"{root_resolved}: {candidate}"
        )
    return candidate


def turn_dir_for(root: Path, session_id: str, turn_id: str) -> Path:
    """Return the canonical turn directory for (*session_id*, *turn_id*).

    Both *session_id* and *turn_id* are normalised so the result is always
    a path safely contained within the session directory.
    """
    safe_session = normalize_session_id(session_id)
    safe_turn = normalize_path_component(turn_id)
    candidate = (root / safe_session / "turns" / safe_turn).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"turn_dir_for({session_id!r}, {turn_id!r}) resolves outside "
            f"session root {root_resolved}: {candidate}"
        )
    return candidate


def canonical_json_bytes(value: Any) -> bytes:
    return _registry_canonical_json_bytes(value, ensure_ascii=False)


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SessionStateLock:
    """Mutual-exclusion lock for per-session state files.

    Structured owner metadata (pid, hostname, timestamp) is stored in the lock
    file so that dead-owner and stale-lease locks can be recovered safely.
    """

    def __init__(
        self,
        session_dir: Path,
        *,
        timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self.session_dir = session_dir
        self.lock_path = session_dir / LOCK_FILE_NAME
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None
        self._lock_id: str | None = None
        self._heartbeat_stop: threading.Event | None = None
        self._heartbeat_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _read_lock_metadata(self) -> dict[str, Any] | None:
        """Read structured owner metadata from the lock file.

        Returns ``None`` for corrupt, unreadable, empty, or legacy-format
        (non-JSON) locks so the caller can quarantine them.
        """
        try:
            raw = self.lock_path.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            return json.loads(raw)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    def _write_lock_metadata(self, fd: int) -> None:
        """Write structured owner metadata into the open file descriptor."""
        self._lock_id = uuid.uuid4().hex
        payload = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "timestamp": time.time(),
            "lock_id": self._lock_id,
        }
        os.write(
            fd, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        )
        os.fsync(fd)

    def _refresh_lock_lease(self) -> None:
        """Atomically renew this owner's cross-host lease."""
        current = self._read_lock_metadata()
        if not isinstance(current, dict) or current.get("lock_id") != self._lock_id:
            raise RuntimeError("session lock ownership changed during lease renewal")
        current["timestamp"] = time.time()
        _write_response_atomic(self.lock_path, current)

    def _heartbeat_lock_lease(self) -> None:
        stop = self._heartbeat_stop
        if stop is None:
            return
        interval = max(0.25, LOCK_LEASE_SECONDS / 3.0)
        while not stop.wait(interval):
            try:
                self._refresh_lock_lease()
            except Exception:
                # Ownership verification on exit and competing acquisition
                # remain fail-closed. A failed renewal must not touch a
                # successor's lock file.
                return

    def _start_lock_heartbeat(self) -> None:
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_lock_lease,
            name=f"vibecomfy-session-lock-{self._lock_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _quarantine_lock(self, reason: str) -> bool:
        """Rename *lock_path* to a ``.corrupt-<ts>-...`` sibling.

        Returns ``True`` when the lock is gone after the call (whether we
        removed it or it disappeared on its own).
        """
        ts = int(time.time())
        dest = self.lock_path.with_name(
            f".corrupt-{ts}-{self.lock_path.name}-{reason}"
        )
        counter = 0
        while dest.exists():
            counter += 1
            dest = self.lock_path.with_name(
                f".corrupt-{ts}-{counter}-{self.lock_path.name}-{reason}"
            )
        try:
            self.lock_path.rename(dest)
            return True
        except FileNotFoundError:
            return True  # already gone
        except OSError:
            try:
                self.lock_path.unlink()
                return True
            except FileNotFoundError:
                return True
            except OSError:
                return False

    # ------------------------------------------------------------------
    # recovery
    # ------------------------------------------------------------------

    def _try_recover(self) -> bool:
        """Attempt to recover a dead-owner or stale-lease lock.

        Recovery rules (conservative):

        * Corrupt / unreadable / legacy-format -> quarantine, retry.
        * Malformed metadata (missing or wrong-typed fields) -> quarantine, retry.
        * Same host, pid alive -> **refuse** (live owner).
        * Same host, pid dead -> recover.
        * Different host, lease stale (> *LOCK_LEASE_SECONDS*) -> recover.
        * Different host, lease fresh -> **preserve timeout** (ambiguous).

        Returns ``True`` if the lock was cleared (caller should retry
        ``O_EXCL`` immediately).  Returns ``False`` if ownership is
        ambiguous or live (caller should continue waiting).
        """
        # Stat *before* reading so we can detect file replacement.
        try:
            stat_before = self.lock_path.stat()
        except FileNotFoundError:
            return True  # lock vanished, retry O_EXCL

        metadata = self._read_lock_metadata()

        # -- no structured metadata we can act on --
        if metadata is None:
            # The lock file may belong to a just-created lock whose
            # metadata has not been flushed yet (window between O_EXCL
            # and os.write).  If the file is brand-new, treat it as a
            # live lock and wait rather than quarantining a valid owner.
            try:
                file_age = time.time() - self.lock_path.stat().st_mtime
                if file_age < 0.1:
                    return False
            except FileNotFoundError:
                return True
            self._quarantine_lock("corrupt_or_legacy")
            return True

        pid = metadata.get("pid")
        hostname = metadata.get("hostname")
        timestamp = metadata.get("timestamp")

        if not (
            isinstance(pid, int)
            and isinstance(hostname, str)
            and isinstance(timestamp, (int, float))
        ):
            self._quarantine_lock("malformed_metadata")
            return True

        # -- live / ambiguous check --
        if hostname == socket.gethostname():
            # Same host -- we can test the process directly.
            if _process_alive(pid):
                return False  # live owner, cannot recover
            # Dead owner -> fall through to quarantine.
        else:
            # Different host -- fall back to lease staleness.
            if time.time() - timestamp <= LOCK_LEASE_SECONDS:
                return False  # fresh lease, ambiguous
            # Stale lease -> fall through to quarantine.

        # -- file unchanged since we read it? --
        try:
            stat_after = self.lock_path.stat()
        except FileNotFoundError:
            return True  # vanished

        if (
            stat_after.st_ino != stat_before.st_ino
            or stat_after.st_mtime_ns != stat_before.st_mtime_ns
        ):
            # Another process touched the lock -- abort to avoid a race.
            return False

        # Content-level verification: re-read metadata to confirm the
        # lock still belongs to the same dead/stale owner we identified
        # above.  This guards against filesystem edge cases where inode
        # and mtime alone do not capture a replacement.
        recheck = self._read_lock_metadata()
        if recheck is None:
            # File corrupted between reads — quarantine is still safe.
            pass
        else:
            recheck_pid = recheck.get("pid")
            recheck_hostname = recheck.get("hostname")
            recheck_timestamp = recheck.get("timestamp")
            if not (
                recheck_pid == pid
                and recheck_hostname == hostname
                and recheck_timestamp == timestamp
            ):
                # Owner changed — abort, the lock is now live.
                return False

        self._quarantine_lock("dead_or_stale_owner")
        return True

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "SessionStateLock":
        self.session_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                self._write_lock_metadata(self._fd)
                self._start_lock_heartbeat()
                return self
            except FileExistsError:
                if self._try_recover():
                    continue  # lock cleared, retry O_EXCL immediately
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out acquiring session lock {self.lock_path}"
                    )
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._heartbeat_stop is not None:
            self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=max(1.0, LOCK_LEASE_SECONDS / 2.0))
        self._heartbeat_stop = None
        self._heartbeat_thread = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        # Verify ownership before unlinking: another process may have
        # recovered and replaced this lock between __enter__ and
        # __exit__.  Only unlink when the file still carries our
        # lock_id; otherwise a racing live writer would lose its lock.
        if self._lock_id is not None:
            current = self._read_lock_metadata()
            if isinstance(current, dict) and current.get("lock_id") == self._lock_id:
                try:
                    self.lock_path.unlink()
                except FileNotFoundError:
                    pass
            # If lock_id differs or metadata is unreadable the lock
            # belongs to a successor — leave it alone.


def default_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "next_turn_index": 1,
        "baseline_turn_id": None,
        "baseline_graph_hash": None,
        "baseline_graph_hash_kind": None,
        "baseline_graph_hash_version": None,
        "baseline_source": "none",
        "baseline_rebaseline_id": None,
        "baseline_graph_source_path": None,
        "next_rebaseline_index": 1,
        "turns": {},
        "idempotency_records": {},
        # ── Phase 4 transactional storage (T19) ───────────────────────────
        # These fields are a DISCOVERABLE INDEX over the authoritative
        # per-turn artifacts under ``turns/<turn_id>/transactions/<plan_hash>/``.
        # They can always be reconstructed from artifact truth (see
        # ``recover_transaction_index``); they exist only to make a hot
        # request path O(1) instead of scanning the filesystem.
        "next_generation": 1,  # monotonic generation counter (1-based)
        # turn_id -> prepared (unfinalized) transaction pointer.
        # A turn has at most one entry here at a time.
        "prepared_transactions": {},
        # "<plan_hash>:<generation>" -> durable apply idempotency record.
        # Keyed by transaction identity so a duplicate finalize/rollback with
        # the same plan hash and generation replays the recorded receipt.
        "apply_idempotency_records": {},
    }


def _set_baseline_authoritatively(
    state: dict[str, Any],
    *,
    next_hash: str | None,
    next_kind: Literal["structural", "raw"] | None,
    next_source: BaselineSource,
    reason: str,
    source_turn_id: str | None = None,
    rebaseline_id: str | None = None,
    source_path: str | None = None,
    projection_version: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    if not isinstance(next_hash, str):
        next_hash = None
        next_kind = None
        next_source = "none"
        projection_version = None
        source_turn_id = None
        rebaseline_id = None
        source_path = None
    elif next_kind not in {"structural", "raw"}:
        raise ValueError("baseline hash kind must be 'structural' or 'raw'")
    elif next_source not in {"turn", "rebaseline", "legacy"}:
        raise ValueError("baseline source must identify a persisted source")

    if next_source == "turn" and not isinstance(source_turn_id, str):
        raise ValueError("turn baselines require a source turn id")
    if next_source == "rebaseline" and not isinstance(rebaseline_id, str):
        raise ValueError("rebaseline baselines require a rebaseline id")
    if next_kind == "structural" and projection_version is None:
        projection_version = STRUCTURAL_PROJECTION_VERSION

    state["baseline_turn_id"] = source_turn_id if next_source == "turn" else None
    state["baseline_graph_hash"] = next_hash
    state["baseline_graph_hash_kind"] = next_kind
    state["baseline_graph_hash_version"] = (
        projection_version if next_kind == "structural" else None
    )
    state["baseline_source"] = next_source
    state["baseline_rebaseline_id"] = (
        rebaseline_id if next_source == "rebaseline" else None
    )
    state["baseline_graph_source_path"] = source_path
    _ = reason, metadata


def _source_path_for_turn_baseline(session_dir: Path, turn_id: str) -> str | None:
    for relative in (
        Path("turns") / turn_id / "applied.ui.json",
        Path("turns") / turn_id / "candidate.ui.json",
        Path("turns") / turn_id / "response.json",
    ):
        if (session_dir / relative).is_file():
            return relative.as_posix()
    return None


def _structural_hash_from_source_path(session_dir: Path, source_path: str | None) -> str | None:
    if not isinstance(source_path, str) or not source_path:
        return None
    path = Path(source_path)
    if path.is_absolute():
        try:
            path.relative_to(session_dir)
        except ValueError:
            return None
    else:
        path = session_dir / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    graph = payload.get("graph", payload) if isinstance(payload, Mapping) else payload
    return structural_graph_hash(graph)


def _normalize_baseline_state(session_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    baseline_turn_id = state.get("baseline_turn_id")
    baseline_hash = state.get("baseline_graph_hash")
    baseline_kind = state.get("baseline_graph_hash_kind")
    baseline_source = state.get("baseline_source")
    baseline_version = state.get("baseline_graph_hash_version")

    if isinstance(baseline_turn_id, str):
        baseline_turn = state["turns"].get(baseline_turn_id)
        if isinstance(baseline_turn, dict):
            finalized = baseline_turn.get("state") == "finalized"
            structural_hash = baseline_turn.get(
                "finalized_structural_graph_hash"
                if finalized
                else "candidate_structural_graph_hash"
            )
            stored_version = baseline_turn.get(
                "finalized_structural_graph_hash_version"
                if finalized
                else "candidate_structural_graph_hash_version"
            )
            if (
                not isinstance(structural_hash, str)
                or stored_version != STRUCTURAL_PROJECTION_VERSION
            ):
                recomputed = _structural_hash_from_source_path(
                    session_dir,
                    _source_path_for_turn_baseline(session_dir, baseline_turn_id),
                )
                if isinstance(recomputed, str):
                    structural_hash = recomputed
                    baseline_turn[
                        "finalized_structural_graph_hash"
                        if finalized
                        else "candidate_structural_graph_hash"
                    ] = recomputed
                    baseline_turn[
                        "finalized_structural_graph_hash_version"
                        if finalized
                        else "candidate_structural_graph_hash_version"
                    ] = STRUCTURAL_PROJECTION_VERSION
            if isinstance(structural_hash, str):
                _set_baseline_authoritatively(
                    state,
                    next_hash=structural_hash,
                    next_kind="structural",
                    next_source="turn",
                    reason="normalize_turn_baseline",
                    source_turn_id=baseline_turn_id,
                    source_path=_source_path_for_turn_baseline(session_dir, baseline_turn_id),
                    projection_version=STRUCTURAL_PROJECTION_VERSION,
                )
                return state
            if not isinstance(baseline_hash, str):
                migrated_hash = baseline_turn.get("candidate_graph_hash") or baseline_turn.get(
                    "client_graph_hash"
                )
                baseline_hash = migrated_hash if isinstance(migrated_hash, str) else None
        if isinstance(baseline_hash, str):
            _set_baseline_authoritatively(
                state,
                next_hash=baseline_hash,
                next_kind="raw",
                next_source="legacy",
                reason="normalize_legacy_turn_baseline",
            )
            return state

    rebaseline_id = state.get("baseline_rebaseline_id")
    if baseline_source == "rebaseline" and isinstance(rebaseline_id, str):
        source_path = state.get("baseline_graph_source_path")
        if not isinstance(source_path, str):
            source_path = (Path("_rebaseline") / rebaseline_id / "graph.ui.json").as_posix()
        structural_hash = baseline_hash if isinstance(baseline_hash, str) else None
        if (
            baseline_kind != "structural"
            or baseline_version != STRUCTURAL_PROJECTION_VERSION
            or not isinstance(structural_hash, str)
        ):
            recomputed = _structural_hash_from_source_path(session_dir, source_path)
            if isinstance(recomputed, str):
                structural_hash = recomputed
        if isinstance(structural_hash, str):
            _set_baseline_authoritatively(
                state,
                next_hash=structural_hash,
                next_kind="structural",
                next_source="rebaseline",
                reason="normalize_rebaseline",
                rebaseline_id=rebaseline_id,
                source_path=source_path,
                projection_version=STRUCTURAL_PROJECTION_VERSION,
            )
            return state

    if isinstance(baseline_hash, str):
        _set_baseline_authoritatively(
            state,
            next_hash=baseline_hash,
            next_kind="raw" if baseline_kind != "structural" else "structural",
            next_source="legacy",
            reason="normalize_legacy_baseline",
            projection_version=(
                baseline_version if isinstance(baseline_version, int) else None
            ),
        )
        return state

    _set_baseline_authoritatively(
        state,
        next_hash=None,
        next_kind=None,
        next_source="none",
        reason="normalize_empty_baseline",
    )
    return state


def read_state(session_dir: Path) -> dict[str, Any]:
    path = session_dir / STATE_FILE_NAME
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default_state()
    if not isinstance(state, dict):
        return default_state()
    merged = default_state()
    merged.update(state)
    if not isinstance(merged.get("turns"), dict):
        merged["turns"] = {}
    if not isinstance(merged.get("idempotency_records"), dict):
        merged["idempotency_records"] = {}
    if not isinstance(merged.get("next_turn_index"), int) or merged["next_turn_index"] < 1:
        merged["next_turn_index"] = 1
    if (
        not isinstance(merged.get("next_rebaseline_index"), int)
        or merged["next_rebaseline_index"] < 1
    ):
        merged["next_rebaseline_index"] = 1
    # ── Phase 4 transactional index normalisation (T19) ───────────────────
    # The index is recoverable from artifact truth, so on read we only need to
    # coerce shape: a missing/corrupt counter falls back to 1, and non-dict
    # index maps are reset to empty.  A corrupt entry never blocks reads.
    if not isinstance(merged.get("next_generation"), int) or merged["next_generation"] < 1:
        merged["next_generation"] = 1
    if not isinstance(merged.get("prepared_transactions"), dict):
        merged["prepared_transactions"] = {}
    else:
        merged["prepared_transactions"] = _normalize_prepared_transactions_index(
            merged["prepared_transactions"]
        )
    if not isinstance(merged.get("apply_idempotency_records"), dict):
        merged["apply_idempotency_records"] = {}
    else:
        merged["apply_idempotency_records"] = _normalize_apply_idempotency_records(
            merged["apply_idempotency_records"]
        )
    _normalize_baseline_state(path.parent, merged)
    merged["schema_version"] = STATE_SCHEMA_VERSION
    return merged


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def iter_turn_records(
    session_root: Path | str,
    session_id: str,
) -> Iterator[DiagnosticRecord]:
    """Yield typed diagnostic records for every turn under *session_id*.

    This is the canonical server-side iterator used by audit/reporting and by
    the CLI debug tool.  It depends only on the stdlib, ``pathlib`` and the
    shared ``DiagnosticRecord`` contract, so it can be imported in lightweight
    consumers without pulling in ComfyUI or torch.
    """
    session_dir = Path(session_root) / session_id
    if not session_dir.is_dir():
        return

    state = _load_json(session_dir / STATE_FILE_NAME) or {}
    st_turns: dict[str, Any] = state.get("turns") if isinstance(state.get("turns"), dict) else {}
    baseline_turn_id = state.get("baseline_turn_id")
    turns_dir = session_dir / "turns"
    if not turns_dir.is_dir():
        return

    for turn_dir in sorted(turns_dir.iterdir()):
        if not turn_dir.is_dir():
            continue
        turn_id = turn_dir.name
        response = _load_json(turn_dir / "response.json") or {}
        request = _load_json(turn_dir / "request.json") or {}
        life = st_turns.get(turn_id, {})
        gates = response.get("gates") or {}
        ok = response.get("ok")
        kind = response.get("kind")
        unchanged = response.get("graph_unchanged")
        lifecycle = life.get("state")

        if lifecycle == "accepted":
            outcome = "\u2705 APPLIED"
        elif lifecycle == "rejected":
            outcome = "\u2717 rejected"
        elif lifecycle == "discarded":
            outcome = "\u2717 discarded"
        elif lifecycle == "unknown" and life.get("superseded_by_turn_id"):
            outcome = "\u21b7 superseded"
        elif lifecycle == "finalized":
            outcome = "\u2705 FINALIZED"
        elif lifecycle == "rollback_complete":
            outcome = "\u21ba ROLLED BACK"
        elif lifecycle == "canvas_verified":
            outcome = "\U0001f50d canvas-verified"
        elif lifecycle == "apply_prepared":
            outcome = "\u23f3 apply-prepared"
        elif lifecycle == "review_bound":
            outcome = "\U0001f441 review-bound"
        elif lifecycle == "candidate_ready":
            outcome = "\U0001f4cb candidate-ready"
        elif lifecycle == "submitted":
            outcome = "\U0001f4e8 submitted"
        elif lifecycle == "rollback_prepared":
            outcome = "\u23f3 rollback-prepared"
        elif ok is True and unchanged:
            outcome = "clarify/noop"
        elif ok is True:
            outcome = "candidate"
        elif kind:
            outcome = f"FAIL:{kind}"
        elif ok is False:
            outcome = "FAIL"
        else:
            outcome = lifecycle or "?"

        candidate_graph = response.get("graph")
        candidate_nodes = (
            len(candidate_graph.get("nodes", []))
            if isinstance(candidate_graph, dict)
            else None
        )

        yield DiagnosticRecord(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=baseline_turn_id if turn_id == baseline_turn_id else None,
            ok=ok,
            kind=kind,
            outcome=outcome,
            lifecycle=lifecycle,
            fidelity_ok=gates.get("ui_fidelity_ok"),
            state_match_ok=gates.get("state_match_ok"),
            queue_validate_ok=gates.get("queue_validate_ok"),
            canvas_apply_allowed=response.get("canvas_apply_allowed"),
            queue_allowed=response.get("queue_allowed"),
            candidate_nodes=candidate_nodes,
            task=request.get("task") or response.get("task") or "",
            route=request.get("route") or "",
            protocol=life.get("agent_edit_protocol"),
            summary=(
                response.get("done_summary")
                or response.get("message")
                or response.get("user_facing_message")
                or ""
            ),
            is_baseline=(turn_id == baseline_turn_id),
            accepted_at=life.get("accepted_at"),
            live_token=life.get("submitted_client_live_canvas_token"),
        )


def structural_graph_projection(graph: Any) -> dict[str, Any]:
    """Compatibility facade for the registry-owned M0 projection profile."""
    return _registry_structural_graph_projection(graph)


def structural_graph_hash(graph: Any) -> str | None:
    """Compatibility facade for the registry-owned M0 projection digest."""
    return _registry_structural_graph_hash(graph)


def browser_layout_scope_issues(graph: Any) -> list[dict[str, str]]:
    """Compatibility facade for registry-owned root-scope diagnostics."""
    return _registry_browser_layout_scope_issues(graph)


def layout_graph_projection(graph: Any) -> dict[str, Any]:
    """Compatibility facade for the registry-owned M0 layout profile."""
    return _registry_layout_graph_projection(graph)


def layout_graph_hash(graph: Any) -> str | None:
    """Compatibility facade for the registry-owned M0 layout digest."""
    return _registry_layout_graph_hash(graph)


def _candidate_structural_hash_from_turn_dir(
    *, session_dir: Path, turn_id: str
) -> str | None:
    for filename in ("candidate.ui.json", "response.json"):
        path = session_dir / "turns" / turn_id / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        graph = (
            payload.get("graph")
            if filename == "response.json" and isinstance(payload, Mapping)
            else payload
        )
        digest = structural_graph_hash(graph)
        if isinstance(digest, str):
            return digest
    return None


def write_state_atomic(session_dir: Path, state: dict[str, Any]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    target = session_dir / STATE_FILE_NAME
    tmp = session_dir / f".{STATE_FILE_NAME}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    tmp.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)


def _write_response_atomic(response_path: Path, response: dict[str, Any]) -> None:
    """Write *response* to *response_path* atomically via a temp file + rename."""
    response_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = response_path.with_name(
        f".{response_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    )
    tmp.write_text(
        json.dumps(response, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(response_path)


def _write_response_immutable(
    response_path: Path,
    response: Mapping[str, Any],
) -> bool:
    """Publish immutable JSON without replacing an existing authority file.

    Returns ``True`` for the winning publisher and ``False`` on collision.
    A fully fsync'd sibling is hard-linked into place, so readers observe either
    the complete old authority or the complete new authority, never a partial
    direct ``O_EXCL`` write.
    """
    response_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = response_path.with_name(
        f".{response_path.name}.{os.getpid()}.{time.monotonic_ns()}.immutable"
    )
    data = json.dumps(dict(response), indent=2, sort_keys=True) + "\n"
    try:
        with tmp.open("x", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, response_path)
        except FileExistsError:
            return False
        try:
            directory_fd = os.open(response_path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return True
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


# ── Index mutation primitives (operate on the in-memory state dict) ─────────
# Callers hold the session lock and persist *state* (``write_state_atomic``)
# after a completed transaction step.


def allocate_generation(state: dict[str, Any]) -> int:
    """Return the current monotonic generation and advance the counter by 1.

    The generation is 1-based and strictly increasing for the lifetime of a
    session.  A missing/corrupt counter is repaired to 1.
    """
    current = state.get("next_generation")
    if not isinstance(current, int) or current < 1:
        current = 1
    state["next_generation"] = current + 1
    return current


def _apply_idempotency_key(plan_hash: str, generation: int) -> str:
    return f"{plan_hash}:{generation}"


def _clear_prepared_pointer(state: dict[str, Any], *, turn_id: str) -> None:
    state.setdefault("prepared_transactions", {}).pop(turn_id, None)


def _set_apply_idempotency_record(
    state: dict[str, Any],
    *,
    plan_hash: str,
    generation: int,
    record: Mapping[str, Any],
) -> None:
    state.setdefault("apply_idempotency_records", {})[
        _apply_idempotency_key(plan_hash, generation)
    ] = dict(record)


def lookup_apply_idempotency_record(
    state: Mapping[str, Any],
    *,
    plan_hash: str,
    generation: int,
) -> dict[str, Any] | None:
    """Return the durable apply idempotency record for ``(plan_hash, generation)``.

    A non-``None`` result means this transaction identity was already resolved
    (finalized, rolled back, or cancelled); a duplicate apply must replay the
    recorded phase deterministically rather than re-applying.
    """
    record = state.get("apply_idempotency_records", {}).get(
        _apply_idempotency_key(plan_hash, generation)
    )
    return dict(record) if isinstance(record, Mapping) else None


# ── High-level transaction step storage (artifact + index) ──────────────────


def record_prepared_transaction(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    lease_nonce: str,
    structural_hash_before: str | None,
    candidate_payload: Mapping[str, Any] | None = None,
    baseline_snapshot: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Persist the authoritative ``prepared`` artifact and update the index.

    Allocates a fresh monotonic generation, appends a ``prepared`` lifecycle
    event to the append-only log, writes the derived ``prepared.json`` receipt,
    and records the prepared pointer in the session index (at most one
    prepared transaction per turn).  The caller must hold the session lock and
    persist *state* afterwards.  Returns the prepared event record.
    """
    generation = allocate_generation(state)
    transaction_dir = transaction_dir_for(turn_dir, plan_hash)
    prepared_candidate: dict[str, Any] = {}
    if candidate_payload and candidate_payload.get("contract_version") == CANDIDATE_TRANSACTION_V2:
        prepared_candidate = project_transaction_state(
            candidate_payload,
            state="prepared",
            generation=generation,
            lease_nonce=lease_nonce,
        )
        ok, error = validate_candidate_transaction(prepared_candidate)
        if not ok:
            raise ValueError(error or "invalid_prepared_candidate_transaction")
    elif candidate_payload:
        # Storage primitive compatibility for historical test/audit fixtures.
        # Production callers are v2-only and take the validated branch above.
        prepared_candidate = dict(candidate_payload)
    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": generation,
        "lease_nonce": lease_nonce,
        "structural_hash_before": structural_hash_before,
        "baseline_snapshot": dict(baseline_snapshot) if baseline_snapshot else {},
        "candidate": prepared_candidate,
        "candidate_transaction": prepared_candidate,
        "phase": "prepared",
    }
    event = _append_transaction_lifecycle_event(
        transaction_dir,
        event_type="prepared",
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        receipt=receipt,
        now_fn=now_fn,
    )
    _write_transaction_receipt(transaction_dir, "prepared", event)
    state.setdefault("prepared_transactions", {})[turn_id] = {
        "plan_hash": plan_hash,
        "generation": generation,
        "lease_nonce": lease_nonce,
        "structural_hash_before": structural_hash_before,
        "timestamp": event["timestamp"],
    }
    return event


def _record_resolved_transaction(
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
    """Shared storage for finalize / rollback / cancel steps.

    Appends the lifecycle event, writes the derived receipt snapshot (if any),
    clears the prepared pointer, and stores the durable apply idempotency
    record so a duplicate apply with the same ``(plan_hash, generation)``
    replays deterministically.  The caller must hold the session lock and
    persist *state* afterwards.  Returns the event record.
    """
    transaction_dir = transaction_dir_for(turn_dir, plan_hash)
    event = _append_transaction_lifecycle_event(
        transaction_dir,
        event_type=event_type,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        receipt=receipt,
        now_fn=now_fn,
    )
    _write_transaction_receipt(transaction_dir, event_type, event)
    _clear_prepared_pointer(state, turn_id=turn_id)
    _set_apply_idempotency_record(
        state,
        plan_hash=plan_hash,
        generation=generation,
        record={
            "turn_id": turn_id,
            "plan_hash": plan_hash,
            "generation": generation,
            "phase": event_type,
            "receipt_path": _PHASE_TO_RECEIPT_NAME.get(event_type),
            "timestamp": event["timestamp"],
        },
    )
    return event


def record_finalized_transaction(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    generation: int,
    structural_hash_after: str | None,
    applied_payload: Mapping[str, Any] | None = None,
    journal_durable: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Persist the authoritative ``finalized`` artifact and update the index.

    Marks the transaction resolved (terminal) so a duplicate finalize with the
    same ``(plan_hash, generation)`` is idempotent.  Returns the event record.
    """
    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
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
    return _record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        event_type="finalized",
        receipt=receipt,
        now_fn=now_fn,
    )


def record_canvas_verified_transaction(
    *,
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    generation: int,
    lease_nonce: str,
    post_apply_graph_hash: str,
    post_apply_structural_hash: str,
    applied_delta_hash: str,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Persist server-verified browser canvas evidence before finalization."""
    receipt = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": generation,
        "lease_nonce": lease_nonce,
        "post_apply_graph_hash": post_apply_graph_hash,
        "post_apply_structural_hash": post_apply_structural_hash,
        "applied_delta_hash": applied_delta_hash,
        "phase": "canvas_verified",
    }
    transaction_dir = transaction_dir_for(turn_dir, plan_hash)
    latest = latest_transaction_event(transaction_dir)
    if (
        isinstance(latest, Mapping)
        and latest.get("event_type") == "canvas_verified"
        and latest.get("generation") == generation
        and _safe_receipt(latest) == receipt
    ):
        return dict(latest)
    event = _append_transaction_lifecycle_event(
        transaction_dir,
        event_type="canvas_verified",
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        receipt=receipt,
        now_fn=now_fn,
    )
    _write_transaction_receipt(transaction_dir, "canvas_verified", event)
    return event


def record_rolled_back_transaction(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    generation: int,
    restored_structural_hash: str | None,
    compensation: Mapping[str, Any] | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Persist the authoritative ``rolled_back`` artifact and update the index.

    Marks the transaction resolved (terminal); the baseline is restored by the
    caller.  Returns the event record.
    """
    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": generation,
        "restored_structural_hash": restored_structural_hash,
        "phase": "rollback_complete",
    }
    if compensation:
        receipt["compensation"] = dict(compensation)
    return _record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        event_type="rollback_complete",
        receipt=receipt,
        now_fn=now_fn,
    )


_ROLLBACK_TRIGGER_STAGES = frozenset(
    {
        "plan_hash_verification",
        "canvas_apply",
        "post_apply_serialize",
        "post_apply_verification",
        "finalize",
        "manual",
        "unknown",
    }
)
_ROLLBACK_COMPENSATION_HASH_FIELDS = (
    "pre_apply_graph_hash",
    "post_restore_graph_hash",
    "pre_apply_structural_hash",
    "post_restore_structural_hash",
)


def _rollback_compensation_from_request(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate optional browser compensation evidence for a rollback.

    The server cannot inspect or restore the browser canvas.  This bounded,
    explicit receipt records why an automatic rollback happened and whether
    the browser proved that its compensating canvas restore reached the
    pre-apply structural state.
    """
    raw = payload.get("compensation")
    if raw is None:
        return None, None
    if not isinstance(raw, Mapping):
        return None, "compensation must be an object."

    allowed = {
        "trigger_stage",
        "failure_kind",
        "failure_message",
        "canvas_was_mutated",
        "canvas_restore_attempted",
        "canvas_restore_succeeded",
        *_ROLLBACK_COMPENSATION_HASH_FIELDS,
    }
    unknown = sorted(str(key) for key in raw if key not in allowed)
    if unknown:
        return None, (
            f"compensation contains unsupported fields: {', '.join(unknown)}."
        )

    trigger_stage = raw.get("trigger_stage")
    if trigger_stage not in _ROLLBACK_TRIGGER_STAGES:
        return None, (
            "compensation.trigger_stage must be one of: "
            + ", ".join(sorted(_ROLLBACK_TRIGGER_STAGES))
            + "."
        )

    result: dict[str, Any] = {"trigger_stage": trigger_stage}
    for field, limit in (("failure_kind", 128), ("failure_message", 2048)):
        value = raw.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            return None, (
                f"compensation.{field} must be a non-empty string of at most "
                f"{limit} characters."
            )
        result[field] = value

    for field in (
        "canvas_was_mutated",
        "canvas_restore_attempted",
        "canvas_restore_succeeded",
    ):
        value = raw.get(field)
        if not isinstance(value, bool):
            return None, f"compensation.{field} must be a boolean."
        result[field] = value

    for field in _ROLLBACK_COMPENSATION_HASH_FIELDS:
        value = raw.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            return None, (
                f"compensation.{field} must be a non-empty string of at most "
                "256 characters."
            )
        result[field] = value

    attempted = result["canvas_restore_attempted"]
    succeeded = result["canvas_restore_succeeded"]
    if succeeded and not attempted:
        return None, (
            "compensation cannot claim canvas_restore_succeeded without "
            "attempting restoration."
        )
    before = result.get("pre_apply_structural_hash")
    after = result.get("post_restore_structural_hash")
    if succeeded and (before is None or after is None):
        return None, (
            "successful canvas restoration requires pre_apply_structural_hash "
            "and post_restore_structural_hash."
        )
    if succeeded and before != after:
        return None, (
            "successful canvas restoration requires matching pre-apply and "
            "post-restore structural hashes."
        )

    result["canvas_restoration_verified"] = bool(succeeded and before == after)
    return result, None


def record_cancelled_transaction(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    generation: int,
    reason: str | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Mark a prepared transaction as cancelled (superseded) and clear its pointer.

    A cancelled transaction can never be finalized: its apply idempotency
    record records the cancellation so a late finalize replays as a no-op
    rejection rather than applying.  Returns the event record.
    """
    receipt: dict[str, Any] = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": generation,
        "reason": reason,
        "phase": "superseded",
    }
    return _record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=generation,
        event_type="superseded",
        receipt=receipt,
        now_fn=now_fn,
    )


def record_discarded_transaction(
    *,
    state: dict[str, Any],
    turn_dir: Path,
    turn_id: str,
    plan_hash: str,
    reason: str = "rejected_by_user",
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    receipt = {
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": 0,
        "reason": reason,
        "phase": "discarded",
    }
    return _record_resolved_transaction(
        state=state,
        turn_dir=turn_dir,
        turn_id=turn_id,
        plan_hash=plan_hash,
        generation=0,
        event_type="discarded",
        receipt=receipt,
        now_fn=now_fn,
    )


# ── Transactional apply route semantics (T21) ───────────────────────────────


def _transaction_context(
    *, session_id: str, turn_id: str | None, state: Mapping[str, Any], idempotency_key: str | None = None
) -> TurnContext:
    return TurnContext(
        session_id=session_id,
        turn_id=turn_id,
        baseline_turn_id=state.get("baseline_turn_id")
        if isinstance(state.get("baseline_turn_id"), str)
        else None,
        idempotency_key=idempotency_key,
    )


def _transaction_failure(
    *,
    kind: FailureKind,
    stage: str,
    session_id: str,
    turn_id: str | None,
    state: Mapping[str, Any],
    explanation: str,
    evidence: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> FailureEnvelope:
    context_payload: dict[str, Any] = {"explanation": explanation}
    if evidence:
        context_payload.update(dict(evidence))
    return failure_envelope(
        kind,
        stage,
        _transaction_context(
            session_id=session_id,
            turn_id=turn_id,
            state=state,
            idempotency_key=idempotency_key,
        ),
        agent_failure_context=context_payload,
        queue_allowed=False,
    )


def _baseline_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "baseline_turn_id": state.get("baseline_turn_id"),
        "baseline_graph_hash": state.get("baseline_graph_hash"),
        "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
        "baseline_graph_hash_version": state.get("baseline_graph_hash_version"),
        "baseline_source": state.get("baseline_source"),
        "baseline_rebaseline_id": state.get("baseline_rebaseline_id"),
        "baseline_graph_source_path": state.get("baseline_graph_source_path"),
    }


def _restore_baseline_snapshot(state: dict[str, Any], snapshot: Mapping[str, Any]) -> None:
    for key in (
        "baseline_turn_id",
        "baseline_graph_hash",
        "baseline_graph_hash_kind",
        "baseline_graph_hash_version",
        "baseline_source",
        "baseline_rebaseline_id",
        "baseline_graph_source_path",
    ):
        state[key] = snapshot.get(key)
    if not isinstance(state.get("baseline_source"), str):
        state["baseline_source"] = "none"


def _payload_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _payload_str(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _payload_int(payload: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def _payload_bool(payload: Mapping[str, Any], *keys: str) -> bool:
    return any(payload.get(key) is True for key in keys)


def _candidate_payload_from_request(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidate = payload.get("candidate")
    return dict(candidate) if isinstance(candidate, Mapping) else {}


def _candidate_hash_from_request(payload: Mapping[str, Any]) -> str | None:
    candidate = _candidate_payload_from_request(payload)
    return (
        _payload_str(payload, "candidate_graph_hash", "graph_hash")
        or _payload_str(candidate, "graph_hash", "candidate_graph_hash")
    )


def _plan_hash_from_request(payload: Mapping[str, Any]) -> str | None:
    candidate = _candidate_payload_from_request(payload)
    return (
        _payload_str(payload, "plan_hash", "mutation_plan_hash")
        or _payload_str(candidate, "plan_hash", "mutation_plan_hash")
    )


def _structural_before_from_request(payload: Mapping[str, Any]) -> str | None:
    candidate = _candidate_payload_from_request(payload)
    return (
        _payload_str(
            payload,
            "structural_hash_before",
            "expected_baseline_graph_hash",
            "baseline_graph_hash",
        )
        or _payload_str(candidate, "structural_hash_before", "baseline_graph_hash")
    )


def _structural_after_from_payloads(
    payload: Mapping[str, Any], prepared_receipt: Mapping[str, Any] | None = None
) -> str | None:
    candidate = _candidate_payload_from_request(payload)
    receipt = prepared_receipt or {}
    receipt_candidate = _payload_mapping(receipt.get("candidate"))
    return (
        _payload_str(payload, "structural_hash_after", "candidate_structural_graph_hash")
        or _payload_str(candidate, "structural_hash_after", "structural_graph_hash")
        or _payload_str(receipt, "structural_hash_after")
        or _payload_str(receipt_candidate, "structural_hash_after", "structural_graph_hash")
    )


def _eligibility_applyable(payload: Mapping[str, Any]) -> bool:
    eligibility = payload.get("apply_eligibility")
    if not isinstance(eligibility, Mapping):
        eligibility = payload.get("eligibility")
    candidate = _candidate_payload_from_request(payload)
    candidate_eligibility = candidate.get("apply_eligibility")
    if isinstance(eligibility, Mapping):
        return eligibility.get("applyable") is True
    if isinstance(candidate_eligibility, Mapping):
        return candidate_eligibility.get("applyable") is True
    return payload.get("apply_allowed") is True or payload.get("canvas_apply_allowed") is True


def _prepared_receipt_from_event(event: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(event, Mapping) or event.get("event_type") != "prepared":
        return {}
    receipt = event.get("receipt")
    return dict(receipt) if isinstance(receipt, Mapping) else {}


def _load_authoritative_candidate_transaction(
    *,
    turn_dir: Path,
    session_id: str,
    turn_id: str,
    plan_hash: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load and cross-check the immutable aggregate and replay receipt."""
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

    from .authority_receipts import load_authority_receipt

    authority = load_authority_receipt(turn_dir)
    if authority is None:
        return None, "missing_authority_receipt"
    if not authority.is_applyable:
        return None, "authority_receipt_not_applyable"
    candidate_authority = transaction.get("candidate_authority")
    receipt_digest = payload_hash(authority.to_dict())
    if not isinstance(candidate_authority, Mapping):
        return None, "missing_candidate_authority"
    if (
        candidate_authority.get("authority_receipt_contract_version")
        != authority.contract_version
        or candidate_authority.get("authority_receipt_delta_schema")
        != authority.schema_version
        or candidate_authority.get("authority_receipt_digest") != receipt_digest
    ):
        return None, "candidate_authority_receipt_binding_mismatch"
    hashes = transaction.get("hashes")
    plan = transaction.get("plan")
    if not isinstance(hashes, Mapping) or not isinstance(plan, Mapping):
        return None, "malformed_candidate_transaction"
    if hashes.get("authority_receipt_hash") != receipt_digest:
        return None, "authority_receipt_hash_mismatch"
    envelope = plan.get("delta_ops_envelope")
    if not isinstance(envelope, Mapping):
        return None, "missing_persisted_delta_plan"
    if authority.cumulative_delta_envelope != dict(envelope):
        return None, "authority_delta_mismatch"
    if plan.get("delta_hash") != authority.cumulative_delta_hash:
        return None, "authority_delta_hash_mismatch"
    if hashes.get("candidate_graph_hash") != authority.candidate_hash:
        return None, "authority_candidate_hash_mismatch"
    response = _load_turn_response_payload(
        session_dir=turn_dir.parents[1],
        turn_id=turn_id,
    )
    if not isinstance(response, Mapping):
        return None, "missing_turn_response"
    if response.get("delta_ops_envelope") != envelope:
        return None, "response_delta_mismatch"
    response_transaction = response.get("candidate_transaction")
    if isinstance(response_transaction, Mapping) and dict(response_transaction) != transaction:
        return None, "response_transaction_mismatch"
    return transaction, None


def _latest_prepared_event(turn_dir: Path, plan_hash: str, generation: int) -> dict[str, Any] | None:
    transaction_dir = transaction_dir_for(turn_dir, plan_hash)
    for event in reversed(read_transaction_lifecycle(transaction_dir)):
        if event.get("event_type") != "prepared":
            continue
        if event.get("generation") == generation:
            return event
    return None


def _read_transaction_receipt(turn_dir: Path, plan_hash: str, phase: str) -> dict[str, Any] | None:
    name = TRANSACTION_RECEIPT_BY_EVENT.get(phase)
    if not name:
        return None
    payload = _load_json(transaction_dir_for(turn_dir, plan_hash) / name)
    return payload if isinstance(payload, dict) else None


def _response_from_resolved_record(
    *,
    session_id: str,
    turn_id: str,
    turn_dir: Path,
    record: Mapping[str, Any],
    action: str,
) -> dict[str, Any] | None:
    phase = record.get("phase")
    plan_hash = record.get("plan_hash")
    if not isinstance(phase, str) or not isinstance(plan_hash, str):
        return None
    receipt = _read_transaction_receipt(turn_dir, plan_hash, phase)
    canonical_phase = canonical_transaction_state(phase) or phase
    requested_phase = "finalized" if action == "finalize" else "rollback_complete"
    same_terminal_action = canonical_phase == requested_phase
    return {
        "ok": same_terminal_action,
        "action": action,
        "idempotent_replay": True,
        "terminal_conflict": not same_terminal_action,
        "session_id": session_id,
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": record.get("generation"),
        "phase": canonical_phase,
        "receipt": receipt,
    }


def _prepare_post_hash_expected(
    *,
    payload: Mapping[str, Any],
    prepared_receipt: Mapping[str, Any],
    plan_hash: str,
) -> str | None:
    candidate = _payload_mapping(prepared_receipt.get("candidate"))
    return (
        _payload_str(payload, "expected_post_apply_hash")
        or _payload_str(candidate, "post_apply_hash", "canvas_projection_hash_after")
        or _payload_str(candidate, "structural_hash_after")
        or _payload_str(prepared_receipt, "structural_hash_after")
        or plan_hash
    )


def _validate_current_baseline_for_prepare(
    *,
    payload: Mapping[str, Any],
    state: Mapping[str, Any],
    turn_record: Mapping[str, Any],
) -> dict[str, Any] | None:
    expected = _structural_before_from_request(payload)
    current = _current_structural_baseline_hash(state)
    pristine_baseline = (
        current is None
        and state.get("baseline_graph_hash") is None
        and state.get("baseline_turn_id") is None
        and state.get("baseline_source") in {None, "none"}
    )
    if pristine_baseline:
        # The first candidate has no accepted session baseline yet.  Its
        # submit-time structural hash is the authoritative CAS boundary.
        submitted = turn_record.get("submit_structural_graph_hash")
        persisted_before = turn_record.get("candidate_structural_hash_before")
        if expected == submitted and (
            not isinstance(persisted_before, str) or persisted_before == submitted
        ):
            return None
        return {
            "reason": "pristine_submit_cas_mismatch",
            "expected_baseline_graph_hash": expected,
            "submitted_structural_graph_hash": submitted,
            "persisted_candidate_structural_hash_before": persisted_before,
            "current_baseline_graph_hash": None,
            "current_baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
        }
    if expected != current:
        return {
            "reason": "baseline_cas_mismatch",
            "expected_baseline_graph_hash": expected,
            "current_baseline_graph_hash": current,
            "current_baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
        }
    submitted = turn_record.get("submitted_baseline_graph_hash")
    if isinstance(submitted, str) and submitted != current:
        return {
            "reason": "submitted_baseline_cas_mismatch",
            "submitted_baseline_graph_hash": submitted,
            "current_baseline_graph_hash": current,
        }
    return None


def prepare_turn_transaction(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    request_payload: Any,
    idempotency_key: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope:
    """Prepare a V2 apply without advancing the authoritative baseline."""
    session_dir = session_dir_for(session_root, session_id)
    payload = _payload_mapping(request_payload)
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        reconcile_transaction_index_from_artifacts(state, session_dir)
        turn_record = state["turns"].get(turn_id)
        if not isinstance(turn_record, dict):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation=f"Unknown turn_id {turn_id!r}.",
            )
        current_state = turn_record.get("state")
        plan_hash = _plan_hash_from_request(payload)
        if not isinstance(plan_hash, str) or not plan_hash:
            return _transaction_failure(
                kind=FailureKind.MISSING_REQUIRED_FIELD,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepare requires a mutation plan_hash.",
            )
        stored_plan_hash = turn_record.get("candidate_plan_hash")
        if plan_hash != stored_plan_hash:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepare mutation plan hash did not match the persisted candidate.",
                evidence={
                    "plan_hash": plan_hash,
                    "persisted_candidate_plan_hash": stored_plan_hash,
                },
            )
        turn_dir = turn_dir_for(session_root, session_id, turn_id)
        if canonical_transaction_state(current_state) == "prepared":
            previous = state.get("prepared_transactions", {}).get(turn_id)
            if isinstance(previous, Mapping) and previous.get("plan_hash") == plan_hash:
                previous_generation = previous.get("generation")
                prepared_event = (
                    _latest_prepared_event(turn_dir, plan_hash, previous_generation)
                    if isinstance(previous_generation, int)
                    else None
                )
                transaction = load_candidate_transaction(turn_dir, plan_hash)
                if prepared_event is not None and transaction is not None:
                    projected = project_transaction_state(
                        transaction,
                        state="prepared",
                        generation=previous_generation,
                        lease_nonce=(
                            previous.get("lease_nonce")
                            if isinstance(previous.get("lease_nonce"), str)
                            else None
                        ),
                    )
                    return {
                        "ok": True,
                        "action": "prepare",
                        "idempotent_replay": True,
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "plan_hash": plan_hash,
                        "generation": previous_generation,
                        "lease_nonce": previous.get("lease_nonce"),
                        "phase": "prepared",
                        "candidate_transaction": projected,
                        "receipt": prepared_event,
                    }
        if canonical_transaction_state(current_state) != "candidate_ready":
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepare requires a candidate_ready transaction.",
                evidence={"current_state": current_state},
            )
        transaction, transaction_error = _load_authoritative_candidate_transaction(
            turn_dir=turn_dir,
            session_id=session_id,
            turn_id=turn_id,
            plan_hash=plan_hash,
        )
        if transaction is None:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Persisted candidate transaction authority is unavailable or inconsistent.",
                evidence={"transaction_error": transaction_error},
            )
        if "apply" not in transaction.get("available_actions", []):
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Persisted candidate transaction does not authorize Apply.",
                evidence={"transaction_state": transaction.get("state")},
            )
        candidate_authority = transaction.get("candidate_authority")
        expected_precondition = (
            candidate_authority.get("precondition")
            if isinstance(candidate_authority, Mapping)
            else None
        )
        claimed_precondition = payload.get("precondition_projection")
        typed_precondition_matches = (
            isinstance(expected_precondition, Mapping)
            and isinstance(claimed_precondition, Mapping)
            and claimed_precondition.get("kind") == "projection_ref_v1"
            and claimed_precondition.get("projection")
            == expected_precondition.get("projection")
            and claimed_precondition.get("digest")
            == expected_precondition.get("digest")
        )
        if (
            typed_precondition_matches
            and "canonical" in claimed_precondition
            and claimed_precondition.get("canonical")
            != expected_precondition.get("canonical")
        ):
            typed_precondition_matches = False
        if not typed_precondition_matches:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Browser typed precondition evidence did not match candidate v2 authority.",
                evidence={
                    "claimed_precondition_projection": (
                        dict(claimed_precondition)
                        if isinstance(claimed_precondition, Mapping)
                        else None
                    ),
                    "expected_precondition_projection": (
                        dict(expected_precondition)
                        if isinstance(expected_precondition, Mapping)
                        else None
                    ),
                },
            )
        hashes = _payload_mapping(transaction.get("hashes"))
        stored_candidate_hash = hashes.get("candidate_graph_hash")
        candidate_hash = _candidate_hash_from_request(payload)
        if candidate_hash is not None and candidate_hash != stored_candidate_hash:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepare candidate hash did not match durable authority.",
                evidence={
                    "candidate_graph_hash": candidate_hash,
                    "persisted_candidate_graph_hash": stored_candidate_hash,
                },
            )
        trusted_baseline_payload = {
            "structural_hash_before": hashes.get("submit_structural_graph_hash")
        }
        baseline_mismatch = _validate_current_baseline_for_prepare(
            payload=trusted_baseline_payload, state=state, turn_record=turn_record
        )
        if baseline_mismatch is not None:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepare baseline CAS mismatched the authoritative baseline.",
                evidence=baseline_mismatch,
            )
        expected_generation = _payload_int(
            payload, "expected_generation", "generation", "monotonic_generation"
        )
        generation_cas_enforced = isinstance(expected_generation, int) and expected_generation > 0
        if generation_cas_enforced and expected_generation != state.get("next_generation"):
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="prepare",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepare generation CAS mismatched the next server generation.",
                evidence={
                    "expected_generation": expected_generation,
                    "next_generation": state.get("next_generation"),
                },
            )
        lease_nonce = uuid.uuid4().hex
        baseline_snapshot = _baseline_snapshot(state)
        event = record_prepared_transaction(
            state=state,
            turn_dir=turn_dir,
            turn_id=turn_id,
            plan_hash=plan_hash,
            lease_nonce=lease_nonce,
            structural_hash_before=_current_structural_baseline_hash(state),
            candidate_payload=transaction,
            baseline_snapshot=baseline_snapshot,
        )
        projected_transaction = project_transaction_state(
            transaction,
            state="prepared",
            generation=event["generation"],
            lease_nonce=lease_nonce,
        )
        turn_record["state"] = "prepared"
        turn_record["prepared_plan_hash"] = plan_hash
        turn_record["prepared_generation"] = event["generation"]
        turn_record["prepared_lease_nonce"] = lease_nonce
        turn_record["prepared_at"] = event["timestamp"]
        write_state_atomic(session_dir, state)
        return {
            "ok": True,
            "action": "prepare",
            "session_id": session_id,
            "turn_id": turn_id,
            "plan_hash": plan_hash,
            "generation": event["generation"],
            "lease_nonce": lease_nonce,
            "phase": "prepared",
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "baseline_advanced": False,
            "generation_cas_enforced": generation_cas_enforced,
            "candidate_transaction": projected_transaction,
            "delta_ops_envelope": projected_transaction["plan"]["delta_ops_envelope"],
            "receipt": event,
        }


def finalize_turn_transaction(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    request_payload: Any,
    idempotency_key: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope:
    """Finalize a prepared V2 apply after browser post-apply verification."""
    session_dir = session_dir_for(session_root, session_id)
    payload = _payload_mapping(request_payload)
    plan_hash = _plan_hash_from_request(payload)
    generation = _payload_int(payload, "generation", "monotonic_generation")
    lease_nonce = _payload_str(payload, "lease_nonce")
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        reconcile_transaction_index_from_artifacts(state, session_dir)
        turn_dir = turn_dir_for(session_root, session_id, turn_id)
        if isinstance(plan_hash, str) and isinstance(generation, int):
            replay = lookup_apply_idempotency_record(
                state, plan_hash=plan_hash, generation=generation
            )
            if replay is not None:
                response = _response_from_resolved_record(
                    session_id=session_id,
                    turn_id=turn_id,
                    turn_dir=turn_dir,
                    record=replay,
                    action="finalize",
                )
                if response is not None:
                    return response
        turn_record = state["turns"].get(turn_id)
        if not isinstance(turn_record, dict):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation=f"Unknown turn_id {turn_id!r}.",
            )
        prepared = state.get("prepared_transactions", {}).get(turn_id)
        if not isinstance(prepared, Mapping):
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize requires an active prepared transaction.",
                evidence={"current_state": turn_record.get("state")},
            )
        prepared_plan = prepared.get("plan_hash")
        prepared_generation = prepared.get("generation")
        prepared_nonce = prepared.get("lease_nonce")
        lease_nonce = _payload_str(payload, "lease_nonce")
        if (
            plan_hash != prepared_plan
            or generation != prepared_generation
            or lease_nonce != prepared_nonce
        ):
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize transaction identity did not match the active prepared lease.",
                evidence={
                    "plan_hash": plan_hash,
                    "generation": generation,
                    "lease_nonce_matches": lease_nonce == prepared_nonce,
                    "prepared_plan_hash": prepared_plan,
                    "prepared_generation": prepared_generation,
                },
            )
        prepared_event = _latest_prepared_event(turn_dir, str(prepared_plan), int(prepared_generation))
        prepared_receipt = _prepared_receipt_from_event(prepared_event)
        prepared_transaction = prepared_receipt.get("candidate_transaction")
        legacy_migration = (
            classify_legacy_migration_v1(prepared_transaction)
            if isinstance(prepared_transaction, Mapping)
            and prepared_transaction.get("contract_version") != CANDIDATE_TRANSACTION_V2
            else None
        )
        prepared_ok, prepared_error = validate_candidate_transaction(prepared_transaction)
        prepared_authority = (
            prepared_transaction.get("prepared_authority")
            if isinstance(prepared_transaction, Mapping) else None
        )
        if (
            not prepared_ok
            or not isinstance(prepared_authority, Mapping)
            or prepared_authority.get("plan_hash") != prepared_plan
            or prepared_authority.get("generation") != prepared_generation
            or prepared_authority.get("lease_nonce") != prepared_nonce
        ):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize could not validate the prepared v2 authority.",
                evidence={
                    "prepared_authority_error": prepared_error,
                    "legacy_migration": legacy_migration,
                },
            )
        prepared_before = prepared_receipt.get("structural_hash_before")
        current_baseline = _current_structural_baseline_hash(state)
        if prepared_before != current_baseline:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize baseline CAS mismatched the baseline captured at prepare.",
                evidence={
                    "prepared_structural_hash_before": prepared_before,
                    "current_baseline_graph_hash": current_baseline,
                },
            )
        transaction, transaction_error = _load_authoritative_candidate_transaction(
            turn_dir=turn_dir,
            session_id=session_id,
            turn_id=turn_id,
            plan_hash=str(prepared_plan),
        )
        if transaction is None:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize could not reload durable candidate authority.",
                evidence={"transaction_error": transaction_error},
            )
        post_apply_graph = payload.get("post_apply_graph")
        if not isinstance(post_apply_graph, Mapping):
            return _transaction_failure(
                kind=FailureKind.MISSING_REQUIRED_FIELD,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize requires the serialized post-apply graph.",
            )
        post_apply_graph_hash = payload_hash(post_apply_graph)
        post_apply_structural_hash = structural_graph_hash(post_apply_graph)
        if not isinstance(post_apply_structural_hash, str):
            return _transaction_failure(
                kind=FailureKind.VALIDATION_ERROR,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize could not compute the post-apply structural hash.",
            )
        expected_postcondition = prepared_authority.get("postcondition")
        claimed_postcondition = payload.get("postcondition_projection")
        if not isinstance(expected_postcondition, Mapping):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepared v2 authority is missing its typed postcondition projection.",
            )
        expected_projection = expected_postcondition.get("projection")
        if not isinstance(expected_projection, str):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Prepared v2 authority has an invalid postcondition projection family.",
            )
        try:
            actual_postcondition = projection_reference_v1(
                post_apply_graph, expected_projection
            )
        except Exception as exc:
            return _transaction_failure(
                kind=FailureKind.VALIDATION_ERROR,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Finalize could not project the serialized post-apply graph.",
                evidence={"projection_error": str(exc)[:512]},
            )
        typed_claim_matches = (
            isinstance(claimed_postcondition, Mapping)
            and claimed_postcondition.get("kind") == "projection_ref_v1"
            and claimed_postcondition.get("projection") == expected_projection
            and claimed_postcondition.get("digest")
            == expected_postcondition.get("digest")
        )
        if (
            typed_claim_matches
            and "canonical" in claimed_postcondition
            and claimed_postcondition.get("canonical")
            != expected_postcondition.get("canonical")
        ):
            typed_claim_matches = False
        actual_matches = (
            actual_postcondition.get("projection") == expected_projection
            and actual_postcondition.get("digest")
            == expected_postcondition.get("digest")
            and (
                "canonical" not in expected_postcondition
                or actual_postcondition.get("canonical")
                == expected_postcondition.get("canonical")
            )
        )
        if not typed_claim_matches or not actual_matches:
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Browser typed postcondition evidence did not match prepared v2 authority.",
                evidence={
                    "claimed_postcondition_projection": (
                        dict(claimed_postcondition)
                        if isinstance(claimed_postcondition, Mapping)
                        else None
                    ),
                    "expected_postcondition_projection": dict(expected_postcondition),
                    "computed_postcondition_projection": actual_postcondition,
                },
            )
        hashes = _payload_mapping(transaction.get("hashes"))
        expected_post_hash = hashes.get("candidate_structural_graph_hash")
        # The typed postcondition above is the V2 semantic authority.  Do not
        # also require equality with the compatibility structural digest:
        # native ComfyUI construction may add derived UI carriers (for
        # example LoadImage's image_upload widget) that are intentionally
        # excluded from the typed projection.  Treating the raw compatibility
        # digest as a second postcondition makes valid native materialization
        # impossible and duplicates authority with different semantics.  The
        # compatibility value remains in the receipt as diagnostic evidence.
        authority = _payload_mapping(transaction.get("authority"))
        if authority.get("verification_kind") == "layout_structural_noop":
            layout_verification = authority.get("layout_verification")
            if isinstance(layout_verification, Mapping):
                expected_layout_hash = layout_verification.get(
                    "candidate_layout_graph_hash"
                )
                post_apply_layout_hash = layout_graph_hash(post_apply_graph)
                if (
                    layout_verification.get("contract_version")
                    != LAYOUT_VERIFICATION_CONTRACT_VERSION
                    or layout_verification.get("projection")
                    != LAYOUT_VERIFICATION_PROJECTION
                    or not isinstance(expected_layout_hash, str)
                    or post_apply_layout_hash != expected_layout_hash
                ):
                    return _transaction_failure(
                        kind=FailureKind.STALE_STATE_MISMATCH,
                        stage="finalize",
                        session_id=session_id,
                        turn_id=turn_id,
                        state=state,
                        explanation=(
                            "Finalize layout geometry did not match the prepared "
                            "layout verification contract."
                        ),
                        evidence={
                            "post_apply_layout_hash": post_apply_layout_hash,
                            "expected_candidate_layout_hash": expected_layout_hash,
                            "post_apply_graph_hash": post_apply_graph_hash,
                            "layout_verification": dict(layout_verification),
                        },
                    )
            elif post_apply_graph_hash != hashes.get("candidate_graph_hash"):
                return _transaction_failure(
                    kind=FailureKind.STALE_STATE_MISMATCH,
                    stage="finalize",
                    session_id=session_id,
                    turn_id=turn_id,
                    state=state,
                    explanation=(
                        "Finalize legacy layout graph did not exactly match the "
                        "prepared layout candidate."
                    ),
                    evidence={
                        "post_apply_graph_hash": post_apply_graph_hash,
                        "expected_candidate_graph_hash": hashes.get(
                            "candidate_graph_hash"
                        ),
                        "verification_kind": "layout_structural_noop",
                    },
                )
        claimed_post_hash = _payload_str(
            payload, "post_apply_hash", "browser_verified_post_apply_hash", "canvas_hash"
        )
        if (
            claimed_post_hash is not None
            and claimed_post_hash != post_apply_structural_hash
        ):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Browser post-apply hash claim did not match the serialized graph.",
                evidence={
                    "claimed_post_apply_hash": claimed_post_hash,
                    "computed_post_apply_hash": post_apply_structural_hash,
                },
            )
        plan = _payload_mapping(transaction.get("plan"))
        applied_delta_hash = _payload_str(payload, "applied_delta_hash")
        if applied_delta_hash != plan.get("delta_hash"):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="finalize",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Landed operation evidence did not match the persisted plan.",
                evidence={
                    "applied_delta_hash": applied_delta_hash,
                    "persisted_delta_hash": plan.get("delta_hash"),
                },
            )
        verified_event = record_canvas_verified_transaction(
            turn_dir=turn_dir,
            turn_id=turn_id,
            plan_hash=str(prepared_plan),
            generation=int(prepared_generation),
            lease_nonce=str(prepared_nonce),
            post_apply_graph_hash=post_apply_graph_hash,
            post_apply_structural_hash=post_apply_structural_hash,
            applied_delta_hash=applied_delta_hash,
        )
        _write_response_atomic(turn_dir / "applied.ui.json", dict(post_apply_graph))
        turn_record["state"] = "canvas_verified"
        next_baseline_hash = post_apply_structural_hash
        turn_record["state"] = "finalized"
        turn_record["client_graph_hash"] = post_apply_graph_hash
        turn_record["finalized_structural_graph_hash"] = post_apply_structural_hash
        turn_record[
            "finalized_structural_graph_hash_version"
        ] = STRUCTURAL_PROJECTION_VERSION
        turn_record["finalized_at"] = _now()
        turn_record["finalized_plan_hash"] = prepared_plan
        turn_record["finalized_generation"] = prepared_generation
        _set_baseline_authoritatively(
            state,
            next_hash=next_baseline_hash,
            next_kind="structural",
            next_source="turn",
            reason="finalize_turn_transaction",
            source_turn_id=turn_id,
            source_path=_source_path_for_turn_baseline(session_dir, turn_id),
            projection_version=STRUCTURAL_PROJECTION_VERSION,
        )
        durable_precondition = prepared_authority.get("precondition")
        durable_postcondition = prepared_authority.get("postcondition")
        if prepared_authority.get("operation_family") == "layout":
            structural_witness = prepared_authority.get("structural_witness")
            if isinstance(structural_witness, Mapping):
                durable_before = structural_witness.get("precondition_digest")
                durable_after = structural_witness.get("postcondition_digest")
            else:
                durable_before = durable_after = None
        else:
            durable_before = (
                durable_precondition.get("digest")
                if isinstance(durable_precondition, Mapping)
                else None
            )
            durable_after = (
                durable_postcondition.get("digest")
                if isinstance(durable_postcondition, Mapping)
                else None
            )
        event = record_finalized_transaction(
            state=state,
            turn_dir=turn_dir,
            turn_id=turn_id,
            plan_hash=str(prepared_plan),
            generation=int(prepared_generation),
            structural_hash_after=next_baseline_hash,
            applied_payload={
                "post_apply_hash": post_apply_structural_hash,
                "post_apply_graph_hash": post_apply_graph_hash,
                "post_apply_hash_verified": True,
                "claimed_post_apply_hash": claimed_post_hash,
                "claimed_post_apply_hash_matches": (
                    claimed_post_hash is None
                    or claimed_post_hash == post_apply_structural_hash
                ),
                "expected_post_apply_hash": expected_post_hash,
                "applied_delta_hash": applied_delta_hash,
                "canvas_verified_event_seq": verified_event.get("seq"),
            },
            journal_durable={
                "contract_version": "journal_durable_v1",
                "state": "finalized",
                "workflow_id": prepared_authority["workflow_id"],
                "baseline": {
                    "structural_hash_before": durable_before,
                    "structural_hash_after": durable_after,
                },
                "identity_fence": {
                    "transaction_id": prepared_authority["transaction_id"],
                    "candidate_id": prepared_authority["candidate_id"],
                    "plan_hash": prepared_plan,
                    "generation": prepared_generation,
                    "lease_nonce": prepared_nonce,
                },
                "inverse_or_restore": dict(prepared_authority["restoration_strategy"]),
            },
        )
        for other_turn_id, other_record in state["turns"].items():
            if other_turn_id == turn_id or not isinstance(other_record, dict):
                continue
            if other_record.get("state") in _V2_PRE_FINALIZE_STATES or other_record.get("state") == "candidate":
                other_prepared = state.get("prepared_transactions", {}).get(other_turn_id)
                if isinstance(other_prepared, Mapping):
                    other_plan = other_prepared.get("plan_hash")
                    other_generation = other_prepared.get("generation")
                    if isinstance(other_plan, str) and isinstance(other_generation, int):
                        record_cancelled_transaction(
                            state=state,
                            turn_dir=turn_dir_for(session_root, session_id, other_turn_id),
                            turn_id=other_turn_id,
                            plan_hash=other_plan,
                            generation=other_generation,
                            reason="superseded_by_finalize",
                        )
                other_record["state"] = "superseded"
                other_record["unknown_at"] = other_record.get("unknown_at") or _now()
                other_record["unknown_reason"] = "superseded_by_finalize"
                other_record["superseded_by_turn_id"] = turn_id
        write_state_atomic(session_dir, state)
        finalized_transaction = project_transaction_state(
            transaction,
            state="finalized",
            generation=int(prepared_generation),
            lease_nonce=str(prepared_nonce),
        )
        return {
            "ok": True,
            "action": "finalize",
            "session_id": session_id,
            "turn_id": turn_id,
            "plan_hash": prepared_plan,
            "generation": prepared_generation,
            "phase": "finalized",
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "post_apply_hash": post_apply_structural_hash,
            "post_apply_graph_hash": post_apply_graph_hash,
            "candidate_transaction": finalized_transaction,
            "canvas_verified_receipt": verified_event,
            "receipt": event,
        }


def rollback_turn_transaction(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    request_payload: Any,
    idempotency_key: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope:
    """Rollback a nonterminal V2 apply and restore the prepare-time baseline."""
    session_dir = session_dir_for(session_root, session_id)
    payload = _payload_mapping(request_payload)
    plan_hash = _plan_hash_from_request(payload)
    generation = _payload_int(payload, "generation", "monotonic_generation")
    lease_nonce = _payload_str(payload, "lease_nonce")
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        reconcile_transaction_index_from_artifacts(state, session_dir)
        turn_dir = turn_dir_for(session_root, session_id, turn_id)
        compensation, compensation_error = _rollback_compensation_from_request(
            payload
        )
        if compensation_error is not None:
            return _transaction_failure(
                kind=FailureKind.VALIDATION_ERROR,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation=compensation_error,
            )
        if isinstance(plan_hash, str) and isinstance(generation, int):
            replay = lookup_apply_idempotency_record(
                state, plan_hash=plan_hash, generation=generation
            )
            if replay is not None:
                response = _response_from_resolved_record(
                    session_id=session_id,
                    turn_id=turn_id,
                    turn_dir=turn_dir,
                    record=replay,
                    action="rollback",
                )
                if response is not None:
                    return response
        turn_record = state["turns"].get(turn_id)
        if not isinstance(turn_record, dict):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation=f"Unknown turn_id {turn_id!r}.",
            )
        if turn_record.get("state") in _V2_TERMINAL_STATES:
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Rollback cannot mutate a terminal V2 turn.",
                evidence={"current_state": turn_record.get("state")},
            )
        prepared = state.get("prepared_transactions", {}).get(turn_id)
        if not isinstance(prepared, Mapping):
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Rollback requires an active prepared transaction.",
                evidence={"current_state": turn_record.get("state")},
            )
        prepared_plan = prepared.get("plan_hash")
        prepared_generation = prepared.get("generation")
        prepared_nonce = prepared.get("lease_nonce")
        if (
            plan_hash != prepared_plan
            or generation != prepared_generation
            or lease_nonce != prepared_nonce
        ):
            return _transaction_failure(
                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Rollback transaction identity did not match the active prepared transaction.",
                evidence={
                    "plan_hash": plan_hash,
                    "generation": generation,
                    "prepared_plan_hash": prepared_plan,
                    "prepared_generation": prepared_generation,
                    "lease_nonce_matches": lease_nonce == prepared_nonce,
                },
            )
        prepared_event = _latest_prepared_event(turn_dir, str(prepared_plan), int(prepared_generation))
        prepared_receipt = _prepared_receipt_from_event(prepared_event)
        prepared_transaction = prepared_receipt.get("candidate_transaction")
        legacy_migration = (
            classify_legacy_migration_v1(prepared_transaction)
            if isinstance(prepared_transaction, Mapping)
            and prepared_transaction.get("contract_version") != CANDIDATE_TRANSACTION_V2
            else None
        )
        prepared_ok, prepared_error = validate_candidate_transaction(prepared_transaction)
        prepared_authority = (
            prepared_transaction.get("prepared_authority")
            if isinstance(prepared_transaction, Mapping) else None
        )
        if (
            not prepared_ok
            or not isinstance(prepared_authority, Mapping)
            or prepared_authority.get("plan_hash") != prepared_plan
            or prepared_authority.get("generation") != prepared_generation
            or prepared_authority.get("lease_nonce") != prepared_nonce
        ):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Rollback could not validate the prepared v2 authority.",
                evidence={
                    "prepared_authority_error": prepared_error,
                    "legacy_migration": legacy_migration,
                },
            )
        if (
            isinstance(compensation, Mapping)
            and compensation.get("canvas_was_mutated") is True
            and compensation.get("canvas_restoration_verified") is not True
        ):
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation=(
                    "Rollback cannot resolve the server transaction until the "
                    "mutated canvas is restored and verified."
                ),
                evidence={
                    "canvas_restoration_verified": False,
                    "current_state": turn_record.get("state"),
                },
            )
        snapshot = _payload_mapping(prepared_receipt.get("baseline_snapshot"))
        prepared_before = prepared_receipt.get("structural_hash_before")
        current_baseline = _current_structural_baseline_hash(state)
        if prepared_before != current_baseline:
            record_cancelled_transaction(
                state=state,
                turn_dir=turn_dir,
                turn_id=turn_id,
                plan_hash=str(prepared_plan),
                generation=int(prepared_generation),
                reason="baseline_ownership_lost",
            )
            turn_record["state"] = "superseded"
            turn_record["superseded_at"] = _now()
            write_state_atomic(session_dir, state)
            return _transaction_failure(
                kind=FailureKind.STALE_STATE_MISMATCH,
                stage="rollback",
                session_id=session_id,
                turn_id=turn_id,
                state=state,
                explanation="Rollback baseline ownership was lost to a newer transaction.",
                evidence={
                    "prepared_structural_hash_before": prepared_before,
                    "current_baseline_graph_hash": current_baseline,
                },
            )
        if snapshot:
            _restore_baseline_snapshot(state, snapshot)
        turn_record["state"] = "rollback_complete"
        turn_record["rollback_at"] = _now()
        event = record_rolled_back_transaction(
            state=state,
            turn_dir=turn_dir,
            turn_id=turn_id,
            plan_hash=str(prepared_plan),
            generation=int(prepared_generation),
            restored_structural_hash=_current_structural_baseline_hash(state),
            compensation=compensation,
        )
        write_state_atomic(session_dir, state)
        transaction = load_candidate_transaction(turn_dir, str(prepared_plan))
        projected_transaction = (
            project_transaction_state(
                transaction,
                state="rollback_complete",
                generation=int(prepared_generation),
                lease_nonce=(
                    prepared.get("lease_nonce")
                    if isinstance(prepared.get("lease_nonce"), str)
                    else None
                ),
            )
            if isinstance(transaction, Mapping)
            else None
        )
        return {
            "ok": True,
            "action": "rollback",
            "session_id": session_id,
            "turn_id": turn_id,
            "plan_hash": prepared_plan,
            "generation": prepared_generation,
            "phase": "rollback_complete",
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "candidate_transaction": projected_transaction,
            "receipt": event,
        }


def _transaction_receipts_for_turn(turn_dir: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    tx_root = turn_dir / TRANSACTIONS_DIR_NAME
    if not tx_root.is_dir():
        return receipts
    for plan_dir in sorted(p for p in tx_root.iterdir() if p.is_dir()):
        for event in read_transaction_lifecycle(plan_dir):
            receipts.append(dict(event))
    return receipts


def candidate_transaction_for_turn(
    turn_dir: Path,
    plan_hash: str | None = None,
) -> dict[str, Any] | None:
    tx_root = turn_dir / TRANSACTIONS_DIR_NAME
    if not tx_root.is_dir():
        return None
    plan_dirs = (
        [transaction_dir_for(turn_dir, plan_hash)]
        if isinstance(plan_hash, str) and plan_hash
        else sorted((path for path in tx_root.iterdir() if path.is_dir()), reverse=True)
    )
    candidates: list[tuple[int, dict[str, Any]]] = []
    for plan_dir in plan_dirs:
        candidate = _load_json(plan_dir / CANDIDATE_TRANSACTION_FILENAME)
        ok, _ = validate_candidate_transaction(candidate)
        if not ok or not isinstance(candidate, Mapping):
            continue
        events = read_transaction_lifecycle(plan_dir)
        if not events:
            candidates.append((0, dict(candidate)))
            continue
        latest = events[-1]
        receipt = _safe_receipt(latest)
        generation = latest.get("generation")
        lease_nonce = (
            receipt.get("lease_nonce")
            if isinstance(receipt.get("lease_nonce"), str)
            else None
        )
        if lease_nonce is None:
            # Terminal receipts deliberately avoid duplicating the prepared
            # lease. Rehydrate the immutable prepared authority from the same
            # append-only lifecycle rather than inventing a new nonce.
            for earlier in reversed(events[:-1]):
                earlier_receipt = _safe_receipt(earlier)
                earlier_nonce = earlier_receipt.get("lease_nonce")
                if (
                    earlier.get("generation") == generation
                    and isinstance(earlier_nonce, str)
                    and earlier_nonce
                ):
                    lease_nonce = earlier_nonce
                    break
        projected = project_transaction_state(
            candidate,
            state=str(latest.get("event_type") or candidate.get("state")),
            generation=generation if isinstance(generation, int) else None,
            lease_nonce=lease_nonce,
        )
        candidates.append((generation if isinstance(generation, int) else 0, projected))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def reconcile_turn_transactions(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Repair the discoverable transaction index and return durable receipts."""
    session_dir = session_dir_for(session_root, session_id)
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        index_repaired = reconcile_transaction_index_from_artifacts(state, session_dir)
        if index_repaired:
            write_state_atomic(session_dir, state)
        turn_ids: list[str]
        if isinstance(turn_id, str) and turn_id:
            turn_ids = [turn_id]
        else:
            turns = state.get("turns")
            turn_ids = sorted(turns.keys()) if isinstance(turns, Mapping) else []
        receipts_by_turn = {
            tid: _transaction_receipts_for_turn(
                turn_dir_for(session_root, session_id, tid)
            )
            for tid in turn_ids
        }
        transactions_by_turn = {
            tid: candidate_transaction_for_turn(
                turn_dir_for(session_root, session_id, tid),
                (
                    state.get("turns", {}).get(tid, {}).get("candidate_plan_hash")
                    if isinstance(state.get("turns", {}).get(tid), Mapping)
                    else None
                ),
            )
            for tid in turn_ids
        }
        legacy_migrations_by_turn: dict[str, Any] = {}
        for tid in turn_ids:
            turn_record = state.get("turns", {}).get(tid)
            if not isinstance(turn_record, Mapping):
                continue
            plan_hash = turn_record.get("candidate_plan_hash")
            migration = None
            if isinstance(plan_hash, str):
                _transaction, migration = load_candidate_transaction_with_migration(
                    turn_dir_for(session_root, session_id, tid), plan_hash
                )
            if (
                migration is None
                and turn_record.get("agent_edit_protocol") != "v2_delta"
                and isinstance(turn_record.get("state"), str)
            ):
                migration = classify_legacy_migration_v1(
                    {
                        "contract_version": "candidate_transaction_v1",
                        "state": turn_record.get("state"),
                    }
                )
            if isinstance(migration, Mapping):
                legacy_migrations_by_turn[tid] = dict(migration)
        recovery_graphs_by_turn: dict[str, Any] = {}
        for tid in turn_ids:
            original_graph = _load_json(
                turn_dir_for(session_root, session_id, tid) / "original.ui.json"
            )
            if isinstance(original_graph, Mapping):
                recovery_graphs_by_turn[tid] = {
                    "graph": dict(original_graph),
                    "graph_hash": payload_hash(original_graph),
                    "structural_graph_hash": structural_graph_hash(original_graph),
                    "layout_graph_hash": layout_graph_hash(original_graph),
                }
        return {
            "ok": True,
            "action": "reconcile",
            "session_id": session_id,
            "turn_id": turn_id,
            "index_repaired": index_repaired,
            "prepared_transactions": dict(state.get("prepared_transactions", {})),
            "apply_idempotency_records": dict(state.get("apply_idempotency_records", {})),
            "receipts_by_turn": receipts_by_turn,
            "transactions_by_turn": transactions_by_turn,
            "legacy_migrations_by_turn": legacy_migrations_by_turn,
            "recovery_graphs_by_turn": recovery_graphs_by_turn,
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
        }


# ── Index recovery from authoritative artifact truth ────────────────────────


def _normalize_prepared_transactions_index(raw: Any) -> dict[str, Any]:
    """Coerce the prepared_transactions index into a well-shaped mapping.

    Drops entries that are not dicts or that lack ``plan_hash`` and a positive
    ``generation``.  Never raises: a corrupt entry never blocks reads.
    """
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, Any] = {}
    for turn_id, entry in raw.items():
        if not isinstance(turn_id, str) or not turn_id:
            continue
        if not isinstance(entry, Mapping):
            continue
        plan_hash = entry.get("plan_hash")
        generation = entry.get("generation")
        if not isinstance(plan_hash, str) or not plan_hash:
            continue
        if not isinstance(generation, int) or generation < 1:
            continue
        result[turn_id] = {
            "plan_hash": plan_hash,
            "generation": generation,
            "lease_nonce": entry.get("lease_nonce"),
            "structural_hash_before": entry.get("structural_hash_before"),
            "timestamp": entry.get("timestamp"),
        }
    return result


def _normalize_apply_idempotency_records(raw: Any) -> dict[str, Any]:
    """Coerce the apply_idempotency_records index into a well-shaped mapping.

    Drops records that are not dicts, lack identity fields, or carry a phase
    that is not a resolved (terminal) transaction phase.  Never raises.
    """
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, record in raw.items():
        if not isinstance(key, str) or not key:
            continue
        if not isinstance(record, Mapping):
            continue
        plan_hash = record.get("plan_hash")
        generation = record.get("generation")
        phase = record.get("phase")
        if not isinstance(plan_hash, str) or not plan_hash:
            continue
        if not isinstance(generation, int) or generation < 0:
            continue
        if phase not in _TRANSACTION_RESOLVED_PHASES:
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


def _record_key(scope: OperationScope, idempotency_key: str | None) -> str | None:
    if not idempotency_key:
        return None
    return f"{scope}:{idempotency_key}"


def _load_response(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _conflict_kind(scope: OperationScope) -> FailureKind:
    if scope == "edit":
        return FailureKind.STALE_STATE_MISMATCH
    return FailureKind.EDITOR_AHEAD_CONFLICT


def _mapping_graph_hash(payload: Any, *, field: str = "graph") -> str | None:
    if not isinstance(payload, Mapping):
        return None
    graph = payload.get(field)
    if not isinstance(graph, Mapping):
        return None
    return payload_hash(graph)


def _mapping_graph_structural_hash(payload: Any, *, field: str = "graph") -> str | None:
    if not isinstance(payload, Mapping):
        return None
    return structural_graph_hash(payload.get(field))


def _recorded_turn_state_for_response(
    *,
    candidate_graph_hash: str | None,
    agent_edit_protocol: str | None = None,
) -> TurnState:
    """Return the appropriate TurnState after a candidate response is recorded.

    V2 (``agent_edit_protocol == "v2_delta"``) turns advance from ``submitted``
    to ``candidate_ready`` when a candidate is produced; otherwise they stay
    ``submitted``.

    V1 / legacy turns keep the historical ``candidate`` / ``no_candidate``
    states for backward compatibility with readers that only understand the
    original five-state lifecycle.
    """
    if agent_edit_protocol == "v2_delta":
        return "candidate_ready" if candidate_graph_hash is not None else "submitted"
    return "candidate" if candidate_graph_hash is not None else "no_candidate"


def v2_mutation_plan_hash(
    *,
    delta_ops_envelope: Mapping[str, Any],
    structural_hash_before: str | None,
    structural_hash_after: str | None,
) -> str:
    """Return the canonical transaction identity for a V2 graph mutation."""
    return payload_hash(
        {
            "contract_version": "agent_edit_mutation_plan_v1",
            "agent_edit_protocol": "v2_delta",
            "delta_ops_envelope": dict(delta_ops_envelope),
            "structural_hash_before": structural_hash_before,
            "structural_hash_after": structural_hash_after,
        }
    )


def _validated_agent_edit_protocol(response: Mapping[str, Any]) -> str:
    """Resolve the durable protocol, validating explicit V2 evidence.

    Answer-only legacy responses may still be inferred for audit compatibility.
    Any newly recorded candidate authority must be explicit ``v2_delta`` with
    one canonical delta envelope and a server-authored mutation-plan binding.
    """
    explicit = response.get("agent_edit_protocol")
    if explicit is not None and explicit not in {"v1", "v2_delta"}:
        raise ValueError(f"Unsupported agent_edit_protocol {explicit!r}.")

    delta_envelope = response.get("delta_ops_envelope")
    flat_delta_ops = response.get("delta_ops")
    canonical_ops: list[dict[str, Any]] | None = None
    if isinstance(delta_envelope, Mapping):
        from vibecomfy.porting.edit.ops import ensure_root_scoped_delta_envelope

        canonical = ensure_root_scoped_delta_envelope(delta_envelope, strict=True)
        canonical_payload = canonical.to_dict()
        raw_ops = canonical_payload.get("ops")
        canonical_ops = list(raw_ops) if isinstance(raw_ops, list) else []

    if explicit == "v1":
        if canonical_ops is not None or isinstance(flat_delta_ops, list):
            raise ValueError("agent_edit_protocol 'v1' cannot carry V2 delta evidence.")
        if isinstance(response.get("graph"), Mapping) or isinstance(response.get("candidate"), Mapping):
            raise ValueError("agent_edit_protocol 'v1' candidate authority is historical and read-only.")
        return "v1"

    if explicit == "v2_delta":
        if canonical_ops is None:
            raise ValueError(
                "agent_edit_protocol 'v2_delta' requires delta_ops_envelope."
            )
        if isinstance(flat_delta_ops, list) and flat_delta_ops != canonical_ops:
            raise ValueError(
                "delta_ops compatibility view does not match delta_ops_envelope."
            )
        candidate = response.get("candidate")
        eligibility = response.get("eligibility")
        if not isinstance(eligibility, Mapping):
            eligibility = response.get("apply_eligibility")
        if (
            isinstance(candidate, Mapping)
            and isinstance(eligibility, Mapping)
            and eligibility.get("applyable") is True
        ):
            required = (
                "plan_hash",
                "structural_hash_before",
                "structural_hash_after",
            )
            missing = [
                field
                for field in required
                if not isinstance(candidate.get(field), str) or not candidate.get(field)
            ]
            if missing:
                raise ValueError(
                    "Applyable v2_delta candidate is missing transaction fields: "
                    + ", ".join(missing)
                )
            response_structural_before = response.get("submit_structural_graph_hash")
            response_structural_after = _mapping_graph_structural_hash(response)
            if (
                isinstance(response_structural_before, str)
                and candidate.get("structural_hash_before") != response_structural_before
            ):
                raise ValueError(
                    "Applyable v2_delta candidate structural_hash_before does not "
                    "match the submitted graph."
                )
            if (
                isinstance(response_structural_after, str)
                and candidate.get("structural_hash_after") != response_structural_after
            ):
                raise ValueError(
                    "Applyable v2_delta candidate structural_hash_after does not "
                    "match the candidate graph."
                )
            expected_plan_hash = v2_mutation_plan_hash(
                delta_ops_envelope=delta_envelope,
                structural_hash_before=candidate.get("structural_hash_before"),
                structural_hash_after=candidate.get("structural_hash_after"),
            )
            if candidate.get("plan_hash") != expected_plan_hash:
                raise ValueError(
                    "Applyable v2_delta candidate plan_hash does not match canonical "
                    "delta and structural boundaries."
                )
        return "v2_delta"

    if isinstance(response.get("graph"), Mapping) or isinstance(response.get("candidate"), Mapping):
        if isinstance(flat_delta_ops, list):
            # Legacy flat-delta_ops candidate without a v2_delta envelope is
            # still rejected: the strict path requires a canonical envelope.
            raise ValueError("New candidate authority requires explicit v2_delta evidence.")
        # Non-delta contracts (e.g. the default ``batch_repl``/canvas contract)
        # produce a legitimate applyable candidate but carry no delta evidence.
        # Stabilization: demote the strict raise to a warning so the candidate
        # is still recorded as a readable v1 audit artifact instead of throwing
        # and failing the whole turn. The strict v2_delta evidence requirements
        # above (explicit protocol / envelope / plan-hash) are preserved.
        _LOGGER.warning(
            "Candidate authority without explicit v2_delta evidence recorded "
            "as v1 audit artifact; delta_ops_envelope absent on this response."
        )
        return "v1"
    if canonical_ops is not None or isinstance(flat_delta_ops, list):
        return "v2_delta"
    # Answer-only/no-candidate records remain readable audit artifacts.
    return "v1"


def _stamp_recorded_candidate(
    turn_record: dict[str, Any],
    *,
    candidate_graph_hash: str | None,
    candidate_structural_graph_hash: str | None,
    agent_edit_protocol: str,
    candidate_plan_hash: str | None,
    candidate_structural_hash_before: str | None,
    candidate_structural_hash_after: str | None,
) -> None:
    """Project one validated response into the durable turn index."""
    turn_record["state"] = _recorded_turn_state_for_response(
        candidate_graph_hash=candidate_graph_hash,
        agent_edit_protocol=agent_edit_protocol,
    )
    turn_record["candidate_graph_hash"] = candidate_graph_hash
    turn_record["candidate_structural_graph_hash"] = candidate_structural_graph_hash
    turn_record["candidate_structural_graph_hash_version"] = STRUCTURAL_PROJECTION_VERSION
    turn_record["agent_edit_protocol"] = agent_edit_protocol
    turn_record["candidate_plan_hash"] = candidate_plan_hash
    turn_record["candidate_structural_hash_before"] = candidate_structural_hash_before
    turn_record["candidate_structural_hash_after"] = candidate_structural_hash_after


def _client_graph_hash(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_graph_hash")
    return value if isinstance(value, str) else None


def _client_structural_graph_hash(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_structural_graph_hash")
    return value if isinstance(value, str) else None


def _client_live_canvas_token(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_live_canvas_token")
    return value if isinstance(value, str) else None


def _stale_state_recovery_evidence(
    *,
    reason: str,
    expected_baseline_graph_hash: str | None = None,
    current_baseline_graph_hash: str | None = None,
    submitted_baseline_graph_hash: str | None = None,
    submit_structural_graph_hash: str | None = None,
    baseline_source: str | None = None,
) -> dict[str, Any]:
    return {
        "reason": reason,
        "expected_baseline_graph_hash": expected_baseline_graph_hash,
        "current_baseline_graph_hash": current_baseline_graph_hash,
        "submitted_baseline_graph_hash": submitted_baseline_graph_hash,
        "submit_structural_graph_hash": submit_structural_graph_hash,
        "baseline_source": baseline_source,
        "recovery": {
            "action": "rebaseline",
            "endpoint": "/vibecomfy/agent-edit/rebaseline",
            "reason": reason,
            "last_known_baseline_graph_hash": expected_baseline_graph_hash,
            "submit_structural_graph_hash": submit_structural_graph_hash,
        },
    }


def _current_structural_baseline_hash(state: Mapping[str, Any]) -> str | None:
    current_hash = state.get("baseline_graph_hash")
    current_kind = state.get("baseline_graph_hash_kind")
    if isinstance(current_hash, str) and current_kind == "structural":
        return current_hash
    return None


def _accept_structural_cas_evidence(
    *,
    expected_baseline: ExpectedBaseline,
    state: Mapping[str, Any],
    turn_record: Mapping[str, Any],
) -> dict[str, Any] | None:
    current_hash = _current_structural_baseline_hash(state)
    current_source = state.get("baseline_source")
    current_raw_hash = state.get("baseline_graph_hash")
    current_kind = state.get("baseline_graph_hash_kind")
    if expected_baseline.graph_hash is None:
        if (
            current_raw_hash is None
            and current_source in {None, "none"}
            and state.get("baseline_turn_id") is None
        ):
            return None
    elif expected_baseline.hash_kind == "structural" and current_hash == expected_baseline.graph_hash:
        return None

    return _stale_state_recovery_evidence(
        reason="structural_baseline_cas_mismatch",
        expected_baseline_graph_hash=expected_baseline.graph_hash,
        current_baseline_graph_hash=current_hash,
        submitted_baseline_graph_hash=(
            turn_record.get("submitted_baseline_graph_hash")
            if isinstance(turn_record.get("submitted_baseline_graph_hash"), str)
            else None
        ),
        submit_structural_graph_hash=(
            turn_record.get("submit_structural_graph_hash")
            if isinstance(turn_record.get("submit_structural_graph_hash"), str)
            else None
        ),
        baseline_source=current_source if isinstance(current_source, str) else None,
    ) | {
        "current_baseline_graph_hash_kind": (
            current_kind if isinstance(current_kind, str) else None
        ),
        "expected_baseline_graph_hash_kind": expected_baseline.hash_kind,
    }


def _expected_baseline_for_turn(
    turn_record: Mapping[str, Any],
    state: Mapping[str, Any],
) -> ExpectedBaseline:
    if "submitted_baseline_graph_hash" in turn_record:
        submitted_hash = turn_record.get("submitted_baseline_graph_hash")
        submitted_kind = turn_record.get("submitted_baseline_graph_hash_kind")
        submitted_source = turn_record.get("submitted_baseline_source")
        if submitted_hash is None:
            return ExpectedBaseline(
                reliable=True,
                graph_hash=None,
                hash_kind=None,
                source=submitted_source if isinstance(submitted_source, str) else "none",
                reason="submitted_no_baseline",
                evidence={
                    "submitted_baseline_graph_hash": None,
                    "submitted_baseline_graph_hash_kind": submitted_kind,
                    "submitted_baseline_source": submitted_source,
                },
            )
        if isinstance(submitted_hash, str):
            return ExpectedBaseline(
                reliable=True,
                graph_hash=submitted_hash,
                hash_kind=submitted_kind if isinstance(submitted_kind, str) else None,
                source=submitted_source if isinstance(submitted_source, str) else None,
                reason="submitted_baseline_snapshot",
                evidence={
                    "submitted_baseline_graph_hash": submitted_hash,
                    "submitted_baseline_graph_hash_kind": submitted_kind,
                    "submitted_baseline_source": submitted_source,
                    "submitted_baseline_graph_hash_version": turn_record.get(
                        "submitted_baseline_graph_hash_version"
                    ),
                    "submitted_baseline_rebaseline_id": turn_record.get(
                        "submitted_baseline_rebaseline_id"
                    ),
                },
            )
        reason = "submitted_baseline_snapshot_malformed"
        return ExpectedBaseline(
            reliable=False,
            graph_hash=None,
            hash_kind=None,
            source=None,
            reason=reason,
            evidence=_stale_state_recovery_evidence(
                reason=reason,
                current_baseline_graph_hash=(
                    state.get("baseline_graph_hash")
                    if isinstance(state.get("baseline_graph_hash"), str)
                    else None
                ),
                submitted_baseline_graph_hash=None,
                submit_structural_graph_hash=(
                    turn_record.get("submit_structural_graph_hash")
                    if isinstance(turn_record.get("submit_structural_graph_hash"), str)
                    else None
                ),
                baseline_source=(
                    state.get("baseline_source")
                    if isinstance(state.get("baseline_source"), str)
                    else None
                ),
            ),
        )

    submit_structural_hash = turn_record.get("submit_structural_graph_hash")
    current_baseline_hash = state.get("baseline_graph_hash")
    current_baseline_kind = state.get("baseline_graph_hash_kind")
    current_baseline_source = state.get("baseline_source")
    if (
        current_baseline_hash is None
        and current_baseline_source in {None, "none"}
        and state.get("baseline_turn_id") is None
    ):
        return ExpectedBaseline(
            reliable=True,
            graph_hash=None,
            hash_kind=None,
            source="none",
            reason="legacy_no_baseline",
            evidence={"legacy_derivation": "no_baseline"},
        )
    if (
        isinstance(submit_structural_hash, str)
        and current_baseline_kind == "structural"
        and current_baseline_source in {"turn", "rebaseline"}
    ):
        return ExpectedBaseline(
            reliable=True,
            graph_hash=submit_structural_hash,
            hash_kind="structural",
            source="legacy",
            reason="legacy_submit_structural_graph_hash",
            evidence={
                "legacy_derivation": "submit_structural_graph_hash",
                "submit_structural_graph_hash": submit_structural_hash,
                "current_baseline_source": current_baseline_source,
            },
        )

    reason = "legacy_expected_baseline_untrusted"
    return ExpectedBaseline(
        reliable=False,
        graph_hash=None,
        hash_kind=None,
        source=None,
        reason=reason,
        evidence=_stale_state_recovery_evidence(
            reason=reason,
            current_baseline_graph_hash=(
                current_baseline_hash if isinstance(current_baseline_hash, str) else None
            ),
            submit_structural_graph_hash=(
                submit_structural_hash if isinstance(submit_structural_hash, str) else None
            ),
            baseline_source=(
                current_baseline_source if isinstance(current_baseline_source, str) else None
            ),
        ),
    )


def allocate_turn(
    *,
    session_root: Path,
    session_id: str,
    request_payload: Any,
    idempotency_key: str | None = None,
    idempotency_request_hash: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> TurnAllocation:
    session_dir = session_dir_for(session_root, session_id)
    request_digest = (
        idempotency_request_hash
        if isinstance(idempotency_request_hash, str)
        and re.fullmatch(r"[0-9a-f]{64}", idempotency_request_hash)
        else payload_hash(request_payload)
    )
    submit_graph_hash = _mapping_graph_hash(request_payload)
    submit_structural_graph_hash = _mapping_graph_structural_hash(request_payload)
    submitted_client_graph_hash = _client_graph_hash(request_payload)
    submitted_client_structural_graph_hash = _client_structural_graph_hash(request_payload)
    submitted_client_live_canvas_token = _client_live_canvas_token(request_payload)
    key = _record_key("edit", idempotency_key)

    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        if key is not None:
            existing = state["idempotency_records"].get(key)
            if isinstance(existing, dict):
                context = TurnContext(
                    session_id=session_id,
                    turn_id=existing.get("turn_id"),
                    baseline_turn_id=state.get("baseline_turn_id"),
                    idempotency_key=idempotency_key,
                )
                if existing.get("request_hash") == request_digest:
                    response = _load_response(existing.get("response_path"))
                    if response is not None:
                        return TurnAllocation(
                            context=context,
                            session_dir=session_dir,
                            turn_dir=turn_dir_for(session_root, session_id, str(context.turn_id)),
                            state=state,
                            request_hash=request_digest,
                            idempotency_record_key=key,
                            replay=IdempotencyReplay(response=response, record=dict(existing)),
                        )
                failure = failure_envelope(
                    _conflict_kind("edit"),
                    "ingest",
                    context,
                    agent_failure_context={
                        "explanation": "Idempotency key was reused with a different request hash.",
                        "idempotency_key": idempotency_key,
                        "existing_request_hash": existing.get("request_hash"),
                        "request_hash": request_digest,
                    },
                )
                return TurnAllocation(
                    context=context,
                    session_dir=session_dir,
                    turn_dir=turn_dir_for(session_root, session_id, str(context.turn_id)),
                    state=state,
                    request_hash=request_digest,
                    idempotency_record_key=key,
                    conflict=IdempotencyConflict(failure=failure, record=dict(existing)),
                )

        # The serialized graph on Submit is authoritative input for the new
        # turn. When it has semantically diverged from a prior durable
        # baseline (for example, the user manually changed a widget after the
        # previous turn finalized), persist that graph and advance the
        # baseline *before* minting candidate authority. The old implementation
        # called this "auto-rebaseline" but merely disabled the ingest gate,
        # leaving Prepare to compare the new candidate against the obsolete
        # finalized baseline.
        #
        # New browser clients bind this transition to the baseline they last
        # observed. Keep the field optional for old clients, whose last-writer
        # submit behavior is preserved, but never permit adoption across an
        # active prepared lease.
        expected_baseline_present = (
            isinstance(request_payload, Mapping)
            and "expected_baseline_graph_hash" in request_payload
        )
        expected_baseline_graph_hash = (
            request_payload.get("expected_baseline_graph_hash")
            if isinstance(request_payload, Mapping)
            else None
        )
        if expected_baseline_present and not _rebaseline_expected_matches(
            state, expected_baseline_graph_hash
        ):
            failure = failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                "ingest",
                TurnContext(
                    session_id=session_id,
                    baseline_turn_id=state.get("baseline_turn_id"),
                    idempotency_key=idempotency_key,
                ),
                agent_failure_context={
                    "explanation": (
                        "Submit-time baseline adoption no longer matches the "
                        "workflow baseline observed by this browser."
                    ),
                    **_stale_state_recovery_evidence(
                        reason="submit_baseline_cas_mismatch",
                        expected_baseline_graph_hash=(
                            expected_baseline_graph_hash
                            if isinstance(expected_baseline_graph_hash, str)
                            else None
                        ),
                        current_baseline_graph_hash=_current_structural_baseline_hash(state),
                        submit_structural_graph_hash=submit_structural_graph_hash,
                        baseline_source=(
                            state.get("baseline_source")
                            if isinstance(state.get("baseline_source"), str)
                            else None
                        ),
                    ),
                },
            )
            return TurnAllocation(
                context=TurnContext(
                    session_id=session_id,
                    baseline_turn_id=state.get("baseline_turn_id"),
                    idempotency_key=idempotency_key,
                ),
                session_dir=session_dir,
                turn_dir=session_dir,
                state=state,
                request_hash=request_digest,
                idempotency_record_key=key,
                conflict=IdempotencyConflict(failure=failure, record={}),
            )

        pristine_baseline = (
            state.get("baseline_graph_hash") is None
            and state.get("baseline_turn_id") is None
            and state.get("baseline_source") in {None, "none"}
        )
        baseline_differs_from_submit = (
            isinstance(submit_structural_graph_hash, str)
            and (
                state.get("baseline_graph_hash_kind") != "structural"
                or _current_structural_baseline_hash(state)
                != submit_structural_graph_hash
            )
        )
        if (
            expected_baseline_present
            and not pristine_baseline
            and baseline_differs_from_submit
        ):
            active_prepared = state.get("prepared_transactions")
            if isinstance(active_prepared, Mapping) and active_prepared:
                failure = failure_envelope(
                    FailureKind.EDITOR_AHEAD_CONFLICT,
                    "ingest",
                    TurnContext(
                        session_id=session_id,
                        baseline_turn_id=state.get("baseline_turn_id"),
                        idempotency_key=idempotency_key,
                    ),
                    agent_failure_context={
                        "explanation": (
                            "Submit cannot adopt a changed canvas while a "
                            "prepared transaction still owns the workflow baseline."
                        ),
                        "prepared_turn_ids": sorted(str(item) for item in active_prepared),
                    },
                )
                return TurnAllocation(
                    context=TurnContext(
                        session_id=session_id,
                        baseline_turn_id=state.get("baseline_turn_id"),
                        idempotency_key=idempotency_key,
                    ),
                    session_dir=session_dir,
                    turn_dir=session_dir,
                    state=state,
                    request_hash=request_digest,
                    idempotency_record_key=key,
                    conflict=IdempotencyConflict(failure=failure, record={}),
                )

            graph = (
                request_payload.get("graph")
                if isinstance(request_payload, Mapping)
                else None
            )
            if not isinstance(graph, Mapping):
                raise ValueError("Submit-time baseline adoption requires a graph object.")
            rebaseline_index = int(state["next_rebaseline_index"])
            rebaseline_id = f"{rebaseline_index:04d}"
            state["next_rebaseline_index"] = rebaseline_index + 1
            source_path = (
                Path("_rebaseline") / rebaseline_id / "graph.ui.json"
            ).as_posix()
            graph_path = session_dir / source_path
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            _write_response_atomic(graph_path, dict(graph))
            _set_baseline_authoritatively(
                state,
                next_hash=submit_structural_graph_hash,
                next_kind="structural",
                next_source="rebaseline",
                reason="submit_live_canvas_adoption",
                rebaseline_id=rebaseline_id,
                source_path=source_path,
                projection_version=STRUCTURAL_PROJECTION_VERSION,
                metadata={
                    "idempotency_key": idempotency_key,
                    "submitted_client_graph_hash": submitted_client_graph_hash,
                    "submitted_client_structural_graph_hash": (
                        submitted_client_structural_graph_hash
                    ),
                },
            )

        turn_index = int(state["next_turn_index"])
        turn_id = f"{turn_index:04d}"
        state["next_turn_index"] = turn_index + 1
        state["turns"][turn_id] = {
            "state": "candidate",
            "submit_graph_hash": submit_graph_hash,
            "submit_structural_graph_hash": submit_structural_graph_hash,
            "submitted_baseline_graph_hash": state.get("baseline_graph_hash"),
            "submitted_baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "submitted_baseline_graph_hash_version": state.get("baseline_graph_hash_version"),
            "submitted_baseline_source": state.get("baseline_source"),
            "submitted_baseline_rebaseline_id": state.get("baseline_rebaseline_id"),
            "submitted_baseline_turn_id": state.get("baseline_turn_id"),
            "submitted_baseline_graph_source_path": state.get("baseline_graph_source_path"),
            "submitted_client_graph_hash": submitted_client_graph_hash,
            "submitted_client_structural_graph_hash": submitted_client_structural_graph_hash,
            "submitted_client_live_canvas_token": submitted_client_live_canvas_token,
            "candidate_graph_hash": None,
            "candidate_structural_graph_hash": None,
            "candidate_plan_hash": None,
            "candidate_structural_hash_before": None,
            "candidate_structural_hash_after": None,
            "agent_edit_protocol": None,
            "client_graph_hash": None,
            "accepted_at": None,
            "rejected_at": None,
            "action_request_hash": None,
            "action_client_graph_hash": None,
            "action_submit_graph_hash": None,
            "created_at": _now(),
        }
        unknown_transitions: list[dict[str, Any]] = []
        for other_turn_id, other_record in state["turns"].items():
            if other_turn_id == turn_id or not isinstance(other_record, dict):
                continue
            other_state = other_record.get("state")
            if other_state == "candidate":
                superseded_state = "unknown"
            elif other_state in {
                "submitted",
                "candidate_ready",
                "review_bound",
                "recoverable_error",
            }:
                superseded_state = "superseded"
            else:
                continue
            other_record["state"] = superseded_state
            other_record["unknown_at"] = other_record.get("unknown_at") or _now()
            other_record["unknown_reason"] = "superseded_by_new_submit"
            other_record["superseded_by_turn_id"] = turn_id
            transitioned_at = other_record["unknown_at"]
            unknown_transitions.append(
                {
                    "session_id": session_id,
                    "turn_id": other_turn_id,
                    "from_state": other_state,
                    "to_state": superseded_state,
                    "reason": "superseded_by_new_submit",
                    "superseded_by_turn_id": turn_id,
                    "transitioned_at": transitioned_at,
                }
            )
        write_state_atomic(session_dir, state)

    turn_dir = turn_dir_for(session_root, session_id, turn_id)
    turn_dir.mkdir(parents=True, exist_ok=True)
    return TurnAllocation(
        context=TurnContext(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=state.get("baseline_turn_id"),
            idempotency_key=idempotency_key,
        ),
        session_dir=session_dir,
        turn_dir=turn_dir,
        state=state,
        request_hash=request_digest,
        unknown_transitions=tuple(unknown_transitions),
        idempotency_record_key=key,
    )


def record_idempotent_response(
    *,
    session_root: Path,
    session_id: str,
    scope: OperationScope,
    idempotency_key: str | None,
    request_hash: str,
    response: dict[str, Any],
    response_path: Path,
    operation: str,
    turn_id: str | None,
    schema_provider: Any = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    key = _record_key(scope, idempotency_key)
    stamped_response = response
    authority_receipt: Any = None
    request_payload: Mapping[str, Any] | None = None
    requested_v2 = response.get("agent_edit_protocol") == "v2_delta" or isinstance(
        response.get("delta_ops_envelope"), Mapping
    )
    if scope == "edit" and turn_id is not None:
        try:
            turn_dir = response_path.parent
            loaded_request_payload = _load_json(turn_dir / "request.json")
            if isinstance(loaded_request_payload, Mapping):
                request_payload = loaded_request_payload
                if requested_v2:
                    scope_metadata = request_payload.get("scope_metadata")
                    workflow_id = request_payload.get("workflow_id")
                    if not isinstance(workflow_id, str) and isinstance(scope_metadata, Mapping):
                        workflow_id = scope_metadata.get("workflow_id")
                    workflow_identity_v1(workflow_id)
                    if not isinstance(request_payload.get("graph"), Mapping):
                        raise ValueError("V2 candidate issuance requires the persisted submit graph.")
                    from .authority_receipts import build_and_persist_authority_receipt

                    schema_version = ""
                    delta_envelope = response.get("delta_ops_envelope")
                    if isinstance(delta_envelope, Mapping):
                        raw_schema_version = delta_envelope.get("schema_version")
                        if isinstance(raw_schema_version, str):
                            schema_version = raw_schema_version
                    authority_receipt, stamped_response = build_and_persist_authority_receipt(
                        turn_dir=turn_dir,
                        session_id=session_id,
                        turn_id=turn_id,
                        request_payload=request_payload,
                        response=response,
                        schema_version=schema_version,
                        schema_provider=schema_provider,
                    )
        except Exception:
            if requested_v2:
                # An applyable V2 candidate must never be published without
                # durable replay authority.  V1 artifacts remain display-only.
                raise
            stamped_response = response
    candidate_graph_hash = _mapping_graph_hash(stamped_response)
    candidate_structural_graph_hash = _mapping_graph_structural_hash(stamped_response)
    candidate_layout_graph_hash = (
        layout_graph_hash(stamped_response.get("graph"))
        if isinstance(stamped_response, Mapping)
        else None
    )
    agent_edit_protocol = _validated_agent_edit_protocol(stamped_response)
    candidate_payload = (
        stamped_response.get("candidate")
        if isinstance(stamped_response.get("candidate"), Mapping)
        else {}
    )
    candidate_plan_hash = (
        candidate_payload.get("plan_hash")
        if isinstance(candidate_payload.get("plan_hash"), str)
        else None
    )
    candidate_structural_hash_before = (
        candidate_payload.get("structural_hash_before")
        if isinstance(candidate_payload.get("structural_hash_before"), str)
        else None
    )
    candidate_structural_hash_after = (
        candidate_payload.get("structural_hash_after")
        if isinstance(candidate_payload.get("structural_hash_after"), str)
        else None
    )
    if requested_v2 and isinstance(candidate_graph_hash, str):
        complete_authority = (
            turn_id is not None
            and authority_receipt is not None
            and isinstance(candidate_plan_hash, str)
            and isinstance(candidate_structural_graph_hash, str)
            and isinstance(authority_receipt.cumulative_delta_envelope, Mapping)
            and isinstance(authority_receipt.cumulative_delta_hash, str)
            and isinstance(authority_receipt.schema_witness, Mapping)
        )
        if not complete_authority:
            raise ValueError("V2 candidate publication requires complete durable replay authority.")
        assert authority_receipt is not None
        assert turn_id is not None
        if not isinstance(request_payload, Mapping):
            raise ValueError("V2 candidate issuance requires the persisted submit request.")
        submit_graph = request_payload.get("graph")
        candidate_graph = stamped_response.get("graph")
        if not isinstance(submit_graph, Mapping) or not isinstance(candidate_graph, Mapping):
            raise ValueError("V2 candidate issuance requires genuine submit and candidate graphs.")
        scope_metadata = request_payload.get("scope_metadata")
        workflow_id = request_payload.get("workflow_id")
        if not isinstance(workflow_id, str) and isinstance(scope_metadata, Mapping):
            workflow_id = scope_metadata.get("workflow_id")
        if not isinstance(workflow_id, str):
            raise ValueError("V2 candidate issuance requires an explicit stable workflow_id UUID.")
        eligibility = stamped_response.get("eligibility")
        if not isinstance(eligibility, Mapping):
            eligibility = stamped_response.get("apply_eligibility")
        applyable = (
            authority_receipt.is_applyable
            and isinstance(eligibility, Mapping)
            and eligibility.get("applyable") is True
        )
        layout_verification = None
        layout_operation_envelope = None
        if authority_receipt.replay.verification_kind == "layout_structural_noop":
            layout_verification = (
                {
                    "contract_version": LAYOUT_VERIFICATION_CONTRACT_VERSION,
                    "projection": LAYOUT_VERIFICATION_PROJECTION,
                    "candidate_layout_graph_hash": candidate_layout_graph_hash,
                }
                if isinstance(candidate_layout_graph_hash, str)
                else None
            )
            applyable = applyable and layout_verification is not None
            layout_operation_envelope = build_layout_operation_envelope(
                submit_graph, candidate_graph
            )
        transaction = build_candidate_transaction(
            workflow_id=workflow_id,
            session_id=session_id,
            turn_id=turn_id,
            plan_hash=candidate_plan_hash,
            submit_graph=submit_graph,
            candidate_graph=candidate_graph,
            delta_ops_envelope=authority_receipt.cumulative_delta_envelope,
            delta_hash=authority_receipt.cumulative_delta_hash,
            submit_graph_hash=authority_receipt.submit_graph_hash,
            submit_structural_graph_hash=(
                stamped_response.get("submit_structural_graph_hash")
                if isinstance(stamped_response.get("submit_structural_graph_hash"), str)
                else candidate_structural_hash_before
            ),
            candidate_graph_hash=candidate_graph_hash,
            candidate_structural_graph_hash=candidate_structural_graph_hash,
            candidate_layout_graph_hash=candidate_layout_graph_hash,
            layout_verification=layout_verification,
            authority_receipt_hash=payload_hash(authority_receipt.to_dict()),
            schema_witness=authority_receipt.schema_witness,
            replay_ok=authority_receipt.replay.replay_ok,
            candidate_matches=authority_receipt.replay.candidate_matches,
            verification_kind=authority_receipt.replay.verification_kind,
            layout_operation_envelope=layout_operation_envelope,
            applyable=applyable,
            state="candidate_ready" if applyable else "recoverable_error",
            mutation_materialization_envelope=(
                build_mutation_materialization_v1(
                    authority_receipt.cumulative_delta_envelope.get("ops", [])
                )
                if any(
                    isinstance(op, Mapping) and op.get("op") == "add_node"
                    for op in authority_receipt.cumulative_delta_envelope.get("ops", [])
                )
                else None
            ),
        )
        write_candidate_transaction(response_path.parent, transaction)
        stamped_response = dict(stamped_response)
        stamped_response["candidate_transaction"] = transaction
        stamped_candidate = stamped_response.get("candidate")
        if isinstance(stamped_candidate, Mapping):
            stamped_candidate = dict(stamped_candidate)
            stamped_candidate["state"] = transaction["state"]
            stamped_response["candidate"] = stamped_candidate
    response_digest = payload_hash(stamped_response)
    # Persist state mutation and idempotency record BEFORE publishing
    # response.json so that durable state always precedes the response
    # artifact.  If state persistence fails the response never becomes
    # visible, preventing orphaned successful responses.
    if key is None:
        # Unkeyed edit path: persist turn state first, then publish response.
        if scope == "edit" and turn_id is not None:
            session_dir = session_dir_for(session_root, session_id)
            with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
                state = read_state(session_dir)
                turn_record = state["turns"].get(turn_id)
                if isinstance(turn_record, dict):
                    _stamp_recorded_candidate(
                        turn_record,
                        candidate_graph_hash=candidate_graph_hash,
                        agent_edit_protocol=agent_edit_protocol,
                        candidate_structural_graph_hash=candidate_structural_graph_hash,
                        candidate_plan_hash=candidate_plan_hash,
                        candidate_structural_hash_before=candidate_structural_hash_before,
                        candidate_structural_hash_after=candidate_structural_hash_after,
                    )
                    write_state_atomic(session_dir, state)
        # Atomically publish response.json after durable state completes.
        _write_response_atomic(response_path, stamped_response)
        # The HTTP caller must observe the same validated v2 aggregate that was
        # durably published; returning the pre-stamp object would strand the
        # first browser review until a rehydrate.
        published_response = json.loads(json.dumps(stamped_response))
        response.clear()
        response.update(published_response)
        return None
    record = {
        "request_hash": request_hash,
        "response_hash": response_digest,
        "response_path": str(response_path),
        "created_at": _now(),
        "operation": operation,
        "turn_id": turn_id,
    }
    # Keyed edit path: persist turn state + idempotency record first,
    # then publish response.
    session_dir = session_dir_for(session_root, session_id)
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        if scope == "edit" and turn_id is not None:
            turn_record = state["turns"].get(turn_id)
            if isinstance(turn_record, dict):
                _stamp_recorded_candidate(
                    turn_record,
                    candidate_graph_hash=candidate_graph_hash,
                    agent_edit_protocol=agent_edit_protocol,
                    candidate_structural_graph_hash=candidate_structural_graph_hash,
                    candidate_plan_hash=candidate_plan_hash,
                    candidate_structural_hash_before=candidate_structural_hash_before,
                    candidate_structural_hash_after=candidate_structural_hash_after,
                )
        state["idempotency_records"][key] = record
        write_state_atomic(session_dir, state)
    # Atomically publish response.json after durable state + idempotency
    # record completes.
    _write_response_atomic(response_path, stamped_response)
    published_response = json.loads(json.dumps(stamped_response))
    response.clear()
    response.update(published_response)
    return record


# ── Named temporary bridge: /vibecomfy/agent-edit/accept → finalize ──────
# Deletion condition: remove this bridge once every live browser client has been
# updated to POST directly to /vibecomfy/agent-edit/finalize for V2 applyable
# turns (tracked via the per-session accept_bridge_v2_count counter).  The bridge
# is named "accept-to-finalize" and exists solely to let browsers that still hit
# the legacy accept endpoint complete V2 apply flows without an independent
# commit path.  When counter stops incrementing across all deployed sessions for
# one release cycle, delete accept_turn, the /accept route handler, and this
# bridge delegation block.
_ACCEPT_BRIDGE_V2_KEY: str = "accept_bridge_v2_count"


def _increment_accept_bridge_counter(state: dict[str, Any]) -> int:
    """Increment and return the per-session accept→finalize bridge use count."""
    counters: dict[str, Any] = state.setdefault("_bridge_counters", {})
    current: int = int(counters.get(_ACCEPT_BRIDGE_V2_KEY, 0))
    current += 1
    counters[_ACCEPT_BRIDGE_V2_KEY] = current
    return current


def accept_turn(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
) -> dict[str, Any] | FailureEnvelope:
    # ── Accept→Finalize bridge for V2 applyable turns ──────────────────
    # If the turn is in a V2 applyable state (prepared or canvas_verified),
    # delegate to finalize_turn_transaction with browser verification proof.
    # The request_payload MUST carry the same fields that /finalize expects:
    # plan_hash, generation, lease_nonce, post_apply_hash, and a verification
    # boolean (post_apply_hash_verified / browser_verified / verified).
    #
    # This bridge does NOT independently advance the baseline — finalize owns
    # the authoritative commit path including CAS, post-apply hash matching,
    # and idempotency replay.
    session_dir = session_dir_for(session_root, session_id)
    bridge_count: int | None = None
    blocked_state: str | None = None
    legacy_migration: dict[str, Any] | None = None
    try:
        with SessionStateLock(session_dir, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
            state = read_state(session_dir)
            turn_record = state["turns"].get(turn_id)
            if isinstance(turn_record, dict):
                current_state = turn_record.get("state")
                blocked_state = current_state if isinstance(current_state, str) else None
                plan_hash = turn_record.get("candidate_plan_hash")
                if isinstance(plan_hash, str):
                    _transaction, legacy_migration = load_candidate_transaction_with_migration(
                        turn_dir_for(session_root, session_id, turn_id), plan_hash
                    )
                if (
                    legacy_migration is None
                    and turn_record.get("agent_edit_protocol") != "v2_delta"
                    and isinstance(current_state, str)
                ):
                    legacy_migration = classify_legacy_migration_v1(
                        {
                            "contract_version": "candidate_transaction_v1",
                            "state": current_state,
                        }
                    )
                if legacy_migration is not None:
                    return failure_envelope(
                        FailureKind.EDITOR_AHEAD_CONFLICT,
                        "accept",
                        TurnContext(
                            session_id=session_id,
                            turn_id=turn_id,
                            baseline_turn_id=state.get("baseline_turn_id"),
                            idempotency_key=idempotency_key,
                        ),
                        agent_failure_context={
                            "explanation": (
                                "Legacy candidate authority is nonresumable and cannot enter "
                                "the v2 accept-to-finalize bridge. Rebaseline or cancel it."
                            ),
                            "legacy_migration": dict(legacy_migration),
                        },
                    )
                # Record bridge use under the session lock, then release it
                # before finalize acquires the same non-reentrant lock.
                if current_state in ("prepared", "canvas_verified"):
                    bridge_count = _increment_accept_bridge_counter(state)
                    write_state_atomic(session_dir, state)
                # V2 non-applyable pre-finalize states: fail closed.
                elif current_state in _V2_PRE_FINALIZE_STATES:
                    return failure_envelope(
                        FailureKind.EDITOR_AHEAD_CONFLICT,
                        "accept",
                        TurnContext(
                            session_id=session_id,
                            turn_id=turn_id,
                            baseline_turn_id=state.get("baseline_turn_id"),
                            idempotency_key=idempotency_key,
                        ),
                        agent_failure_context={
                            "explanation": (
                                f"Turn {turn_id} is in V2 lifecycle state {current_state!r}, "
                                f"which is not applyable.  Applyable V2 states (prepared, "
                                f"canvas_verified) delegate to /finalize via the accept→finalize "
                                f"bridge.  Non-applyable V2 states ({', '.join(sorted(_V2_PRE_FINALIZE_STATES))}) "
                                f"must use the V2 prepare / finalize / rollback endpoints directly."
                            ),
                            "accepted_state": current_state,
                        },
                    )
    except (OSError, TimeoutError, KeyError, TypeError, ValueError):
        # If the quick state check fails for any reason, fall through to the
        # standard _mutate_turn_state path which performs its own state reads
        # under lock and has V2 guards for the remaining edge cases.
        pass

    if bridge_count is not None:
        result = finalize_turn_transaction(
            session_root=session_root,
            session_id=session_id,
            turn_id=turn_id,
            request_payload=request_payload,
            idempotency_key=idempotency_key,
            lock_timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
        )
        if isinstance(result, dict):
            result.setdefault(
                "bridge",
                {
                    "name": "accept-to-finalize",
                    "route": "/vibecomfy/agent-edit/accept",
                    "delegated_to": "finalize_turn_transaction",
                    "bridge_use_count": bridge_count,
                    "deletion_condition": (
                        "Delete when every live browser client posts "
                        "directly to /vibecomfy/agent-edit/finalize "
                        "for V2 applyable turns and the per-session "
                        "accept_bridge_v2_count counter no longer "
                        "increments across all deployed sessions for "
                        "one release cycle."
                    ),
                },
            )
        return result

    # Legacy accept is never transaction authority. Terminal records are audit
    # only; nonterminal records must be rebaselined/cancelled rather than
    # silently resumed through the historical state mutator.
    return failure_envelope(
        FailureKind.EDITOR_AHEAD_CONFLICT,
        "accept",
        TurnContext(
            session_id=session_id,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
        ),
        agent_failure_context={
            "explanation": (
                "Accept cannot authorize legacy or unprepared transaction state; "
                "use the validated v2 prepare/finalize lifecycle."
            ),
            "current_state": blocked_state,
            "legacy_migration": legacy_migration,
        },
    )


def _discard_v2_candidate_if_applicable(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None,
    response_writer: Callable[[dict[str, Any]], Path] | None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope | None:
    """Discard an unprepared V2 candidate without advancing the baseline.

    Returns ``None`` only when the turn belongs to the legacy V1 lifecycle, so
    the caller can preserve the historical reject implementation.
    """
    session_dir = session_dir_for(session_root, session_id)
    request_digest = payload_hash(request_payload)
    key = _record_key("reject", idempotency_key)
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        turn_record = state["turns"].get(turn_id)
        if not isinstance(turn_record, dict):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                "reject",
                TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=state.get("baseline_turn_id"),
                    idempotency_key=idempotency_key,
                ),
                agent_failure_context={"explanation": f"Unknown turn_id {turn_id!r}."},
            )
        current_state = turn_record.get("state")
        protocol = turn_record.get("agent_edit_protocol")
        if protocol != "v2_delta" and current_state not in (
            _V2_PRE_FINALIZE_STATES | _V2_TERMINAL_STATES
        ):
            return None

        context = TurnContext(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=state.get("baseline_turn_id"),
            idempotency_key=idempotency_key,
        )
        if key is not None:
            existing = state["idempotency_records"].get(key)
            if isinstance(existing, dict):
                if existing.get("request_hash") == request_digest:
                    response = _load_response(existing.get("response_path"))
                    if response is not None:
                        return response
                return failure_envelope(
                    FailureKind.EDITOR_AHEAD_CONFLICT,
                    "reject",
                    context,
                    agent_failure_context={
                        "explanation": "Idempotency key was reused with a different request hash.",
                        "idempotency_key": idempotency_key,
                        "existing_request_hash": existing.get("request_hash"),
                        "request_hash": request_digest,
                    },
                )

        canonical_state = canonical_transaction_state(current_state)
        if canonical_state not in {"candidate_ready", "discarded"}:
            explanation = (
                "Prepared V2 candidates must use rollback instead of Reject."
                if canonical_state in {"prepared", "canvas_verified", "recoverable_error"}
                else f"V2 turn {turn_id} in state {current_state!r} cannot be discarded."
            )
            return failure_envelope(
                FailureKind.EDITOR_AHEAD_CONFLICT,
                "reject",
                context,
                agent_failure_context={
                    "explanation": explanation,
                    "current_state": current_state,
                    "required_action": (
                        "rollback"
                        if canonical_state in {"prepared", "canvas_verified", "recoverable_error"}
                        else None
                    ),
                },
            )

        already_discarded = canonical_state == "discarded"
        discarded_at = turn_record.get("discarded_at") or turn_record.get("rejected_at") or _now()
        if not already_discarded:
            plan_hash = turn_record.get("candidate_plan_hash")
            if not isinstance(plan_hash, str):
                return failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "reject",
                    context,
                    agent_failure_context={
                        "explanation": "V2 discard requires the persisted candidate plan hash."
                    },
                )
            transaction = load_candidate_transaction(
                turn_dir_for(session_root, session_id, turn_id),
                plan_hash,
            )
            if not isinstance(transaction, Mapping) or "reject" not in transaction.get(
                "available_actions", []
            ):
                return failure_envelope(
                    FailureKind.EDITOR_AHEAD_CONFLICT,
                    "reject",
                    context,
                    agent_failure_context={
                        "explanation": "Durable candidate transaction does not authorize Reject."
                    },
                )
            discard_event = record_discarded_transaction(
                state=state,
                turn_dir=turn_dir_for(session_root, session_id, turn_id),
                turn_id=turn_id,
                plan_hash=plan_hash,
            )
            turn_record["state"] = "discarded"
            turn_record["discarded_at"] = discarded_at
            turn_record["rejected_at"] = discarded_at
            turn_record["discard_request_hash"] = request_digest
            turn_record["action_request_hash"] = request_digest
            turn_record["action_client_graph_hash"] = client_graph_hash
            turn_record["client_graph_hash"] = client_graph_hash

        plan_hash = turn_record.get("candidate_plan_hash")
        transaction = (
            load_candidate_transaction(
                turn_dir_for(session_root, session_id, turn_id), plan_hash
            )
            if isinstance(plan_hash, str)
            else None
        )
        projected_transaction = (
            project_transaction_state(transaction, state="discarded", generation=0)
            if isinstance(transaction, Mapping)
            else None
        )
        response = {
            "ok": True,
            "action": "reject",
            "disposition": "discarded",
            "candidate_state": "discarded",
            "accepted_state": "discarded",
            "session_id": session_id,
            "turn_id": turn_id,
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "baseline_advanced": False,
            "graph_unchanged": True,
            "client_graph_hash": client_graph_hash,
            "candidate_graph_hash": turn_record.get("candidate_graph_hash"),
            "discarded_at": discarded_at,
            "idempotency_key": idempotency_key,
            "idempotent_replay": already_discarded,
            "candidate_transaction": projected_transaction,
            "receipt": discard_event if not already_discarded else None,
        }
        if key is not None and response_writer is not None:
            response_path = response_writer(response)
            state["idempotency_records"][key] = {
                "request_hash": request_digest,
                "response_hash": payload_hash(response),
                "response_path": str(response_path),
                "created_at": _now(),
                "operation": "reject",
                "turn_id": turn_id,
            }
        write_state_atomic(session_dir, state)
        return response


def reject_turn(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
) -> dict[str, Any] | FailureEnvelope:
    discarded = _discard_v2_candidate_if_applicable(
        session_root=session_root,
        session_id=session_id,
        turn_id=turn_id,
        client_graph_hash=client_graph_hash,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        response_writer=response_writer,
    )
    if discarded is not None:
        return discarded
    legacy_migration: dict[str, Any] | None = None
    try:
        state = read_state(session_dir_for(session_root, session_id))
        turn_record = state.get("turns", {}).get(turn_id)
        if isinstance(turn_record, Mapping):
            plan_hash = turn_record.get("candidate_plan_hash")
            if isinstance(plan_hash, str):
                _transaction, legacy_migration = load_candidate_transaction_with_migration(
                    turn_dir_for(session_root, session_id, turn_id), plan_hash
                )
            if (
                legacy_migration is None
                and turn_record.get("agent_edit_protocol") != "v2_delta"
            ):
                legacy_migration = classify_legacy_migration_v1(
                    {
                        "contract_version": "candidate_transaction_v1",
                        "state": turn_record.get("state"),
                    }
                )
    except (OSError, TypeError, ValueError):
        legacy_migration = None
    if legacy_migration and legacy_migration.get("classification") == "legacy_terminal_read_only":
        return failure_envelope(
            FailureKind.EDITOR_AHEAD_CONFLICT,
            "reject",
            TurnContext(session_id=session_id, turn_id=turn_id),
            agent_failure_context={
                "explanation": "Terminal legacy transaction records are read-only audit history.",
                "legacy_migration": legacy_migration,
            },
        )
    result = _mutate_turn_state(
        session_root=session_root,
        session_id=session_id,
        turn_id=turn_id,
        scope="reject",
        client_graph_hash=client_graph_hash,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        response_writer=response_writer,
    )
    if isinstance(result, dict) and legacy_migration is not None:
        result = dict(result)
        result["legacy_migration"] = legacy_migration
    return result


def _rebaseline_expected_matches(
    state: Mapping[str, Any],
    expected_baseline_graph_hash: Any,
) -> bool:
    current_hash = state.get("baseline_graph_hash")
    current_source = state.get("baseline_source")
    if expected_baseline_graph_hash is None:
        return (
            current_hash is None
            and current_source in {None, "none"}
            and state.get("baseline_turn_id") is None
        )
    return (
        isinstance(expected_baseline_graph_hash, str)
        and state.get("baseline_graph_hash_kind") == "structural"
        and _current_structural_baseline_hash(state) == expected_baseline_graph_hash
    )


def rebaseline_session(
    *,
    session_root: Path,
    session_id: str,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope:
    request_digest = payload_hash(request_payload)
    key = _record_key("rebaseline", idempotency_key)
    session_dir = session_dir_for(session_root, session_id)
    context = TurnContext(session_id=session_id, idempotency_key=idempotency_key)

    if not isinstance(request_payload, Mapping):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "rebaseline",
            context,
            agent_failure_context={"explanation": "Rebaseline request body must be a JSON object."},
        )
    graph = request_payload.get("graph")
    next_structural_hash = structural_graph_hash(graph)
    if next_structural_hash is None:
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "rebaseline",
            context,
            agent_failure_context={"explanation": "`graph` must be a UI workflow JSON object."},
        )
    reason = request_payload.get("reason")
    if reason not in REBASELINE_REASONS:
        return failure_envelope(
            FailureKind.VALIDATION_ERROR,
            "rebaseline",
            context,
            agent_failure_context={
                "explanation": "`reason` must be one of the supported rebaseline reasons.",
                "reason": reason,
                "allowed_reasons": list(REBASELINE_REASONS),
            },
        )
    if "last_known_baseline_graph_hash" not in request_payload:
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "rebaseline",
            context,
            agent_failure_context={"explanation": "`last_known_baseline_graph_hash` is required."},
        )
    expected_baseline_graph_hash = request_payload.get("last_known_baseline_graph_hash")
    if expected_baseline_graph_hash is not None and not isinstance(expected_baseline_graph_hash, str):
        return failure_envelope(
            FailureKind.VALIDATION_ERROR,
            "rebaseline",
            context,
            agent_failure_context={
                "explanation": "`last_known_baseline_graph_hash` must be a string or null.",
                "last_known_baseline_graph_hash": expected_baseline_graph_hash,
            },
        )

    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        context = TurnContext(
            session_id=session_id,
            baseline_turn_id=state.get("baseline_turn_id"),
            idempotency_key=idempotency_key,
        )
        if key is not None:
            existing = state["idempotency_records"].get(key)
            if isinstance(existing, dict):
                if existing.get("request_hash") == request_digest:
                    response = _load_response(existing.get("response_path"))
                    if response is not None:
                        return response
                return failure_envelope(
                    _conflict_kind("rebaseline"),
                    "rebaseline",
                    context,
                    agent_failure_context={
                        "explanation": "Idempotency key was reused with a different request hash.",
                        "idempotency_key": idempotency_key,
                        "existing_request_hash": existing.get("request_hash"),
                        "request_hash": request_digest,
                    },
                )

        previous_baseline_graph_hash = state.get("baseline_graph_hash")
        previous_baseline_graph_hash_kind = state.get("baseline_graph_hash_kind")
        previous_baseline_source = state.get("baseline_source")
        if not _rebaseline_expected_matches(state, expected_baseline_graph_hash):
            current_structural_hash = _current_structural_baseline_hash(state)
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                "rebaseline",
                context,
                agent_failure_context={
                    "explanation": "Rebaseline request no longer matches the authoritative structural baseline.",
                    **_stale_state_recovery_evidence(
                        reason="rebaseline_structural_baseline_cas_mismatch",
                        expected_baseline_graph_hash=expected_baseline_graph_hash,
                        current_baseline_graph_hash=current_structural_hash,
                        submitted_baseline_graph_hash=expected_baseline_graph_hash,
                        submit_structural_graph_hash=next_structural_hash,
                        baseline_source=previous_baseline_source
                        if isinstance(previous_baseline_source, str)
                        else None,
                    ),
                    "current_baseline_graph_hash_kind": previous_baseline_graph_hash_kind,
                },
            )

        rebaseline_index = int(state["next_rebaseline_index"])
        rebaseline_id = f"{rebaseline_index:04d}"
        state["next_rebaseline_index"] = rebaseline_index + 1
        rebaseline_dir = session_dir / "_rebaseline" / rebaseline_id
        source_path = (Path("_rebaseline") / rebaseline_id / "graph.ui.json").as_posix()
        graph_path = session_dir / source_path
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(
            json.dumps(graph, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _set_baseline_authoritatively(
            state,
            next_hash=next_structural_hash,
            next_kind="structural",
            next_source="rebaseline",
            reason="rebaseline",
            rebaseline_id=rebaseline_id,
            source_path=source_path,
            projection_version=STRUCTURAL_PROJECTION_VERSION,
            metadata={
                "reason": reason,
                "expected_baseline_graph_hash": expected_baseline_graph_hash,
                "previous_baseline_graph_hash": previous_baseline_graph_hash,
            },
        )
        response = {
            "ok": True,
            "action": "rebaseline",
            "session_id": session_id,
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "baseline_graph_hash_version": state.get("baseline_graph_hash_version"),
            "baseline_source": state.get("baseline_source"),
            "baseline_rebaseline_id": state.get("baseline_rebaseline_id"),
            "baseline_graph_source_path": state.get("baseline_graph_source_path"),
            "previous_baseline_graph_hash": previous_baseline_graph_hash,
            "previous_baseline_graph_hash_kind": previous_baseline_graph_hash_kind,
            "expected_baseline_graph_hash": expected_baseline_graph_hash,
            "rebaseline_id": rebaseline_id,
            "reason": reason,
            "client_graph_hash": request_payload.get("client_graph_hash")
            if isinstance(request_payload.get("client_graph_hash"), str)
            else None,
            "client_structural_graph_hash": request_payload.get("client_structural_graph_hash")
            if isinstance(request_payload.get("client_structural_graph_hash"), str)
            else None,
            "computed_structural_graph_hash": next_structural_hash,
            "idempotency_key": idempotency_key,
        }
        audit_metadata = {
            "action": "rebaseline",
            "reason": reason,
            "rebaseline_id": rebaseline_id,
            "request_hash": request_digest,
            "expected_baseline_graph_hash": expected_baseline_graph_hash,
            "previous_baseline_graph_hash": previous_baseline_graph_hash,
            "next_baseline_graph_hash": next_structural_hash,
            "baseline_graph_source_path": source_path,
            "structural_projection_version": STRUCTURAL_PROJECTION_VERSION,
        }
        metadata_path = rebaseline_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(audit_metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if response_writer is not None:
            response_path = response_writer(response)
        else:
            response_path = rebaseline_dir / "response.json"
            response_path.write_text(
                json.dumps(response, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if key is not None:
            state["idempotency_records"][key] = {
                "request_hash": request_digest,
                "response_hash": payload_hash(response),
                "response_path": str(response_path),
                "created_at": _now(),
                "operation": "rebaseline",
                "turn_id": None,
                "rebaseline_id": rebaseline_id,
            }
        write_state_atomic(session_dir, state)
        return response


__all__ = [
    "IdempotencyConflict",
    "IdempotencyReplay",
    "SessionStateLock",
    "TurnAllocation",
    "accept_turn",
    "allocate_turn",
    "canonical_json_bytes",
    "default_state",
    "finalize_turn_transaction",
    "normalize_path_component",
    "normalize_session_id",
    "payload_hash",
    "prepare_turn_transaction",
    "read_state",
    "reconcile_turn_transactions",
    "record_idempotent_response",
    "rebaseline_session",
    "reject_turn",
    "rollback_turn_transaction",
    "session_dir_for",
    "turn_dir_for",
    "v2_mutation_plan_hash",
    "write_state_atomic",
]

# ── ORACLE-7 SPINE façade re-exports (T-043) ────────────────────────────────
# Seams for the session decomposition: T-044/045/046 move the pinned surface
# ranges (_artifact_store / _v2_scoped_validation / _turn_state_machine) into
# the three scaffold modules below.  Each filled module defines __all__ as
# exactly the name set its extracted ranges contribute to this namespace, so
# `import *` reproduces the identical top-level attributes — the same contract
# edit.py uses for its _frag_* fragments (including _-prefixed helpers that
# must stay importable by name for the T-048 monkeypatch/importer
# compatibility).  The scaffolds are empty today, so these imports are no-ops
# and must not change __all__ or the frozen 23/31/23 surface (S5).
from ._artifact_store import *  # noqa: F401,F403
from ._v2_scoped_validation import *  # noqa: F401,F403
from ._turn_state_machine import *  # noqa: F401,F403

# T-047: transaction-loading façade (public_direct surface) restored as
# session-defined delegates.  The implementations live in `_artifact_store`
# (T-044 extraction); these wrappers keep the transaction API importable and
# patchable from session exactly as it was before extraction.
from . import _artifact_store


def load_candidate_transaction(
    turn_dir: Path,
    plan_hash: str,
) -> dict[str, Any] | None:
    return _artifact_store.load_candidate_transaction(turn_dir, plan_hash)


def load_candidate_transaction_with_migration(
    turn_dir: Path,
    plan_hash: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Load validated v2 authority or explicitly classify the persisted legacy record."""
    return _artifact_store.load_candidate_transaction_with_migration(turn_dir, plan_hash)
