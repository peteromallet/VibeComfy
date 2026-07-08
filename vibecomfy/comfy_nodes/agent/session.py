from __future__ import annotations

import hashlib
import json
import os
import re
import time
import socket
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Literal

from .contracts import DiagnosticRecord, FailureEnvelope, FailureKind, TurnContext, failure_envelope
from vibecomfy.porting.edit.ops import parse_edit_delta

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
TurnState = Literal["candidate", "accepted", "rejected", "unknown", "no_candidate"]
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
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


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
            structural_hash = baseline_turn.get("candidate_structural_graph_hash")
            stored_version = baseline_turn.get("candidate_structural_graph_hash_version")
            if (
                not isinstance(structural_hash, str)
                or stored_version != STRUCTURAL_PROJECTION_VERSION
            ):
                recomputed = _candidate_structural_hash_from_turn_dir(
                    session_dir=session_dir,
                    turn_id=baseline_turn_id,
                )
                if isinstance(recomputed, str):
                    structural_hash = recomputed
                    baseline_turn["candidate_structural_graph_hash"] = recomputed
                    baseline_turn[
                        "candidate_structural_graph_hash_version"
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
        elif lifecycle == "unknown" and life.get("superseded_by_turn_id"):
            outcome = "\u21b7 superseded"
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


def _natural_id_key(value: Any) -> tuple[int, int | str]:
    text = str(value if value is not None else "")
    if re_match := re.fullmatch(r"-?\d+", text):
        return (0, int(re_match.group(0)))
    return (1, text)


def _is_preview_like_key(key: Any) -> bool:
    return re.search(r"(?:^|_)(?:video)?preview(?:_|$)", str(key or ""), re.I) is not None


def _normalize_structural_widget_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_structural_widget_value(entry) for entry in value]
    if isinstance(value, dict):
        return {
            key: _normalize_structural_widget_value(entry)
            for key, entry in sorted(value.items(), key=lambda item: str(item[0]))
            if not _is_preview_like_key(key)
        }
    # Canonicalise integral floats to ints so the hash matches what the browser
    # round-trips. JS `JSON.stringify(2.0)` emits `2`, so the backend's float
    # widget value (e.g. scale_by=2.0) and the canvas's resubmitted `2` are the
    # same graph and must hash identically. (bool is an int subclass — leave it.)
    if isinstance(value, float) and not isinstance(value, bool):
        if value == value and value not in (float("inf"), float("-inf")):
            if value.is_integer():
                return int(value)
    return value


def _normalize_node_structural_widget_values(node: Mapping[str, Any]) -> Any:
    values = node.get("widgets_values", [])
    if node.get("type") != "vibecomfy.exec":
        return _normalize_structural_widget_value(values)
    if isinstance(values, Mapping):
        return {
            key: _normalize_structural_widget_value(entry)
            for key, entry in sorted(values.items(), key=lambda item: str(item[0]))
            if key != "io" and not _is_preview_like_key(key)
        }
    if isinstance(values, list):
        # ComfyUI does not reliably preserve the `io` widget for dynamic-IO
        # exec nodes after configure/decorate. Socket topology and labels carry
        # the actual graph shape; keeping this duplicate widget in the baseline
        # hash turns a representation round-trip into a false stale-state edit.
        return [
            _normalize_structural_widget_value(entry)
            for index, entry in enumerate(values)
            if index != 1
        ]
    return _normalize_structural_widget_value(values)


def _normalize_structural_link(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_structural_link(entry) for entry in value]
    if isinstance(value, dict):
        return {
            key: _normalize_structural_link(entry)
            for key, entry in sorted(value.items(), key=lambda item: str(item[0]))
        }
    return value


def structural_graph_projection(graph: Any) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        return {"nodes": [], "links": []}
    raw_nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    # Per-node slot-index -> name maps, so links can be projected by NAME. This
    # makes the hash invariant to ComfyUI materialising declared-but-unwired input
    # slots on apply (which shifts later inputs' slot indices and would otherwise
    # change the hash for a graph whose actual wiring is unchanged).
    input_names: dict[Any, list[Any]] = {}
    output_names: dict[Any, list[Any]] = {}
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            continue
        nid = node.get("id")
        input_names[nid] = [
            (i.get("name") if isinstance(i, Mapping) else None)
            for i in (node.get("inputs") if isinstance(node.get("inputs"), list) else [])
        ]
        output_names[nid] = [
            (o.get("name") if isinstance(o, Mapping) else None)
            for o in (node.get("outputs") if isinstance(node.get("outputs"), list) else [])
        ]
    nodes: list[dict[str, Any]] = []
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            node = {}
        # Only WIRED input names — an unwired slot ComfyUI adds on apply is not
        # meaningful graph state and must not change the hash.
        wired_inputs = sorted(
            str(i.get("name"))
            for i in (node.get("inputs") if isinstance(node.get("inputs"), list) else [])
            if isinstance(i, Mapping)
            and i.get("link") is not None
            and i.get("name") is not None
        )
        live_outputs = sorted(
            str(o.get("name"))
            for o in (node.get("outputs") if isinstance(node.get("outputs"), list) else [])
            if isinstance(o, Mapping) and o.get("links") and o.get("name") is not None
        )
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("type"),
                "mode": node.get("mode"),
                "inputs": wired_inputs,
                "outputs": live_outputs,
                "widgets_values": _normalize_node_structural_widget_values(node),
            }
        )
    nodes.sort(
        key=lambda node: (_natural_id_key(node.get("id")), str(node.get("type") or ""))
    )

    def _slot_name(names: list[Any], slot: Any) -> Any:
        if isinstance(slot, int) and 0 <= slot < len(names):
            return names[slot]
        return slot

    # Project links by endpoint NAME (not slot index or link id) so they survive
    # slot reordering and link renumbering across the apply round-trip.
    links: list[dict[str, Any]] = []
    for link in (graph.get("links") if isinstance(graph.get("links"), list) else []):
        if isinstance(link, list) and len(link) >= 6:
            o_id, o_slot, t_id, t_slot, l_type = (
                link[1], link[2], link[3], link[4], link[5],
            )
        elif isinstance(link, Mapping):
            o_id, o_slot = link.get("origin_id"), link.get("origin_slot")
            t_id, t_slot = link.get("target_id"), link.get("target_slot")
            l_type = link.get("type")
        else:
            continue
        links.append(
            {
                "from": o_id,
                "out": _slot_name(output_names.get(o_id, []), o_slot),
                "to": t_id,
                "in": _slot_name(input_names.get(t_id, []), t_slot),
                "type": l_type,
            }
        )
    links.sort(
        key=lambda link: json.dumps(
            link, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    )
    return {"nodes": nodes, "links": links}


def structural_graph_hash(graph: Any) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    return payload_hash(structural_graph_projection(graph))


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


def _recorded_turn_state_for_response(*, candidate_graph_hash: str | None) -> TurnState:
    return "candidate" if candidate_graph_hash is not None else "no_candidate"


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
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> TurnAllocation:
    session_dir = session_dir_for(session_root, session_id)
    request_digest = payload_hash(request_payload)
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
            if other_record.get("state") != "candidate":
                continue
            other_record["state"] = "unknown"
            other_record["unknown_at"] = other_record.get("unknown_at") or _now()
            other_record["unknown_reason"] = "superseded_by_new_submit"
            other_record["superseded_by_turn_id"] = turn_id
            transitioned_at = other_record["unknown_at"]
            unknown_transitions.append(
                {
                    "session_id": session_id,
                    "turn_id": other_turn_id,
                    "from_state": "candidate",
                    "to_state": "unknown",
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
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    key = _record_key(scope, idempotency_key)
    candidate_graph_hash = _mapping_graph_hash(response)
    candidate_structural_graph_hash = _mapping_graph_structural_hash(response)
    agent_edit_protocol = "v2_delta" if isinstance(response.get("delta_ops"), list) else "v1"
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
                    turn_record["state"] = _recorded_turn_state_for_response(
                        candidate_graph_hash=candidate_graph_hash
                    )
                    turn_record["candidate_graph_hash"] = candidate_graph_hash
                    turn_record["candidate_structural_graph_hash"] = candidate_structural_graph_hash
                    turn_record[
                        "candidate_structural_graph_hash_version"
                    ] = STRUCTURAL_PROJECTION_VERSION
                    turn_record["agent_edit_protocol"] = agent_edit_protocol
                    write_state_atomic(session_dir, state)
        # Atomically publish response.json after durable state completes.
        _write_response_atomic(response_path, response)
        return None
    response_digest = payload_hash(response)
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
                turn_record["state"] = _recorded_turn_state_for_response(
                    candidate_graph_hash=candidate_graph_hash
                )
                turn_record["candidate_graph_hash"] = candidate_graph_hash
                turn_record["candidate_structural_graph_hash"] = candidate_structural_graph_hash
                turn_record[
                    "candidate_structural_graph_hash_version"
                ] = STRUCTURAL_PROJECTION_VERSION
                turn_record["agent_edit_protocol"] = agent_edit_protocol
        state["idempotency_records"][key] = record
        write_state_atomic(session_dir, state)
    # Atomically publish response.json after durable state + idempotency
    # record completes.
    _write_response_atomic(response_path, response)
    return record


# ---------------------------------------------------------------------------
# V2 accept evidence loading -- load persisted turn/session artifacts so
# scoped validation can derive expected_old from the submit-time graph.
# These are consumed by _mutate_turn_state (V2 branch) but do not change
# the accept gate themselves; that is done in later tasks.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ScopedValueSentinel:
    code: str


_SENTINEL_NO_VALUE = _ScopedValueSentinel("missing_value")
_SENTINEL_LINK_ABSENT = _ScopedValueSentinel("link_absent")
_SENTINEL_NODE_ABSENT = _ScopedValueSentinel("node_absent")


@dataclass(frozen=True)
class _GraphIndex:
    graph: Mapping[str, Any]
    nodes_by_uid: dict[str, Mapping[str, Any]]
    nodes_by_id: dict[int | str, Mapping[str, Any]]
    nodes_by_str_id: dict[str, Mapping[str, Any]]
    links_by_id: dict[int | str, Any]


def _load_turn_request_graph(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any] | None:
    """Load the submit-time graph from the turn's ``request.json``."""
    path = session_dir / "turns" / turn_id / "request.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        return dict(graph)
    return None


def _load_turn_response_payload(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any] | None:
    """Load the turn's ``response.json``."""
    path = session_dir / "turns" / turn_id / "response.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _load_turn_candidate_graph(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any] | None:
    """Load the candidate graph from the persisted turn response."""
    payload = _load_turn_response_payload(session_dir=session_dir, turn_id=turn_id)
    if payload is None:
        return None
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        return dict(graph)
    return None


def _load_turn_delta_ops(
    *, session_dir: Path, turn_id: str
) -> tuple[dict[str, Any], ...] | None:
    """Load canonical ``delta_ops`` from the persisted turn response.

    Prefers the ``delta_ops_envelope`` (``{schema_version: "2.0.0", ops: [...]}``)
    over the legacy flat ``delta_ops`` list.  Returns None if the response does
    not contain a valid ops list.
    """
    response = _load_turn_response_payload(session_dir=session_dir, turn_id=turn_id)
    if response is None:
        return None

    # Canonical path: delta_ops_envelope with {schema_version, ops}
    envelope = response.get("delta_ops_envelope")
    if isinstance(envelope, Mapping):
        ops = envelope.get("ops")
        if isinstance(ops, list) and all(isinstance(op, Mapping) for op in ops):
            # Validate each op through the backend normaliser so that
            # malformed ops (unknown op kind, missing required fields,
            # etc.) inside a syntactically-valid envelope are rejected
            # before downstream accept verification consumes them.
            try:
                parse_edit_delta(ops)
            except ValueError:
                return None
            return tuple(dict(op) for op in ops)
        # Envelope present but ops is malformed — fall through to delta_ops.
        # We record the shape for diagnostics in _build_v2_accept_evidence.

    # Legacy bridge: flat delta_ops list
    delta_ops = response.get("delta_ops")
    if isinstance(delta_ops, list) and all(isinstance(op, Mapping) for op in delta_ops):
        return tuple(dict(op) for op in delta_ops)

    # Legacy wrapped shape: a dict under delta_ops that is NOT a list
    # (e.g. {"delta_ops": {...}, "diagnostics": [...]}) — reject.
    if isinstance(delta_ops, Mapping):
        return None

    return None


def _load_turn_delta_ops_diagnostic(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any]:
    """Inspect the persisted turn response and return a diagnostic classifying
    the delta shape, without attempting to normalise.

    Returns a dict with:
      * ``shape`` — one of ``canonical``, ``legacy_flat``, ``legacy_wrapped``,
        ``missing``
      * ``code`` — stable diagnostic code
      * ``detail`` — shape-specific evidence
    """
    response = _load_turn_response_payload(session_dir=session_dir, turn_id=turn_id)
    if response is None:
        return {
            "shape": "missing",
            "code": "missing_turn_response",
            "detail": {},
        }

    envelope = response.get("delta_ops_envelope")
    if isinstance(envelope, Mapping):
        ops = envelope.get("ops")
        if isinstance(ops, list):
            # Validate each op through the backend normaliser so that
            # malformed entries (unknown op kind, missing required fields,
            # etc.) are classified as malformed rather than canonical.
            try:
                parse_edit_delta(ops)
            except ValueError:
                return {
                    "shape": "canonical",
                    "code": "canonical_envelope_malformed_ops",
                    "detail": {
                        "schema_version": envelope.get("schema_version"),
                        "reason": "ops list present but entries failed parse_edit_delta validation",
                    },
                }
            return {
                "shape": "canonical",
                "code": "canonical_delta_ops",
                "detail": {"schema_version": envelope.get("schema_version")},
            }
        return {
            "shape": "canonical",
            "code": "canonical_envelope_malformed_ops",
            "detail": {"ops_type": type(ops).__name__},
        }

    delta_ops = response.get("delta_ops")
    if isinstance(delta_ops, list):
        return {
            "shape": "legacy_flat",
            "code": "legacy_delta_ops_flat",
            "detail": {},
        }
    if isinstance(delta_ops, Mapping):
        legacy_keys = sorted(
            k for k in delta_ops
            if k in (
                "delta", "delta_ops", "diagnostics", "guard_result",
                "automatic_link_removals", "re_stitches", "normalize",
                "ops",
            )
        )
        return {
            "shape": "legacy_wrapped",
            "code": "legacy_delta_shape",
            "detail": {"keys": legacy_keys},
        }

    return {
        "shape": "missing",
        "code": "missing_delta_ops",
        "detail": {},
    }


def _scoped_sentinel_payload(value: Any) -> Any:
    if value is _SENTINEL_NO_VALUE:
        return {"sentinel": _SENTINEL_NO_VALUE.code}
    if value is _SENTINEL_LINK_ABSENT:
        return {"sentinel": _SENTINEL_LINK_ABSENT.code}
    if value is _SENTINEL_NODE_ABSENT:
        return {"sentinel": _SENTINEL_NODE_ABSENT.code}
    return value


def _build_graph_index(graph: Mapping[str, Any]) -> _GraphIndex:
    nodes_by_uid: dict[str, Mapping[str, Any]] = {}
    nodes_by_id: dict[int | str, Mapping[str, Any]] = {}
    nodes_by_str_id: dict[str, Mapping[str, Any]] = {}
    for node in graph.get("nodes") if isinstance(graph.get("nodes"), list) else []:
        if not isinstance(node, Mapping):
            continue
        node_id = node.get("id")
        if isinstance(node_id, (int, str)):
            nodes_by_id[node_id] = node
            nodes_by_str_id[str(node_id)] = node
        props = node.get("properties")
        if isinstance(props, Mapping):
            uid = props.get("vibecomfy_uid")
            if isinstance(uid, str) and uid:
                nodes_by_uid[uid] = node
    links_by_id: dict[int | str, Any] = {}
    for link in graph.get("links") if isinstance(graph.get("links"), list) else []:
        if isinstance(link, list) and link:
            link_id = link[0]
        elif isinstance(link, Mapping):
            link_id = link.get("id")
        else:
            continue
        if isinstance(link_id, (int, str)):
            links_by_id[link_id] = link
            links_by_id[str(link_id)] = link
    return _GraphIndex(
        graph=graph,
        nodes_by_uid=nodes_by_uid,
        nodes_by_id=nodes_by_id,
        nodes_by_str_id=nodes_by_str_id,
        links_by_id=links_by_id,
    )


def _canonical_node_uid(node: Mapping[str, Any]) -> str | None:
    props = node.get("properties")
    if isinstance(props, Mapping):
        uid = props.get("vibecomfy_uid")
        if isinstance(uid, str) and uid:
            return uid
    node_id = node.get("id")
    if isinstance(node_id, (int, str)):
        return str(node_id)
    return None


def _normalize_target_uid(target: Any) -> str | None:
    if isinstance(target, Mapping):
        for key in ("uid", "node_uid", "id", "node_id", "scope_path"):
            value = target.get(key)
            if isinstance(value, (int, str)) and str(value):
                return str(value)
        return None
    if isinstance(target, list) and len(target) >= 2:
        value = target[1]
        if isinstance(value, (int, str)) and str(value):
            return str(value)
    return None


def _find_node_in_index(index: _GraphIndex, alias: Any) -> Mapping[str, Any] | None:
    if isinstance(alias, str) and alias in index.nodes_by_uid:
        return index.nodes_by_uid[alias]
    if isinstance(alias, (int, str)) and alias in index.nodes_by_id:
        return index.nodes_by_id[alias]
    if isinstance(alias, (int, str)):
        return index.nodes_by_str_id.get(str(alias))
    return None


def _find_node_in_graph(graph: Mapping[str, Any], uid: str) -> Mapping[str, Any] | None:
    return _find_node_in_index(_build_graph_index(graph), uid)


def _split_field_path(field_path: str) -> list[str]:
    normalized = re.sub(r"\[(\d+)\]", r".\1", field_path)
    return [segment for segment in normalized.split(".") if segment]


def _read_named_socket(
    entries: Any,
    key: str,
) -> Mapping[str, Any] | Any:
    if not isinstance(entries, list):
        return _SENTINEL_NO_VALUE
    if key.isdigit():
        index = int(key)
        return entries[index] if 0 <= index < len(entries) else _SENTINEL_NO_VALUE
    for entry in entries:
        if isinstance(entry, Mapping) and entry.get("name") == key:
            return entry
    return _SENTINEL_NO_VALUE


def _descend_field_value(root: Any, segments: list[str]) -> Any:
    current = root
    for segment in segments:
        if isinstance(current, Mapping):
            if segment not in current:
                return _SENTINEL_NO_VALUE
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return _SENTINEL_NO_VALUE
            index = int(segment)
            if not 0 <= index < len(current):
                return _SENTINEL_NO_VALUE
            current = current[index]
            continue
        return _SENTINEL_NO_VALUE
    return current


def _read_widget_value(node: Mapping[str, Any], widget_name: str) -> Any:
    widgets = node.get("widgets")
    widgets_values = node.get("widgets_values")
    if isinstance(widgets, list) and isinstance(widgets_values, list):
        for index, widget in enumerate(widgets):
            if (
                isinstance(widget, Mapping)
                and widget.get("name") == widget_name
                and index < len(widgets_values)
            ):
                return widgets_values[index]
    if isinstance(widgets_values, Mapping) and widget_name in widgets_values:
        return widgets_values[widget_name]
    return _SENTINEL_NO_VALUE


def _read_field_value_from_node(
    node: Mapping[str, Any], field_path: str
) -> Any:
    """Read a field from widgets, widgets_values, inputs, outputs, or top-level keys."""
    if not isinstance(field_path, str) or not field_path:
        return _SENTINEL_NO_VALUE
    if field_path == "mode":
        return node["mode"] if "mode" in node else _SENTINEL_NO_VALUE

    segments = _split_field_path(field_path)
    if not segments:
        return _SENTINEL_NO_VALUE

    simple_widget_value = _read_widget_value(node, field_path)
    if simple_widget_value is not _SENTINEL_NO_VALUE:
        return simple_widget_value

    head = segments[0]
    tail = segments[1:]
    if head == "widgets":
        root = _read_named_socket(node.get("widgets"), tail[0]) if tail else node.get("widgets")
        return _descend_field_value(root, tail[1:]) if tail else root
    if head == "widgets_values":
        return _descend_field_value(node.get("widgets_values"), tail)
    if head == "inputs":
        root = _read_named_socket(node.get("inputs"), tail[0]) if tail else node.get("inputs")
        return _descend_field_value(root, tail[1:]) if tail else root
    if head == "outputs":
        root = _read_named_socket(node.get("outputs"), tail[0]) if tail else node.get("outputs")
        return _descend_field_value(root, tail[1:]) if tail else root
    if head in node:
        return _descend_field_value(node, segments)
    return _SENTINEL_NO_VALUE


def _normalize_link_endpoint(node_alias: Any, output_slot: Any) -> Any:
    if not isinstance(node_alias, (int, str)) or output_slot is None:
        return _SENTINEL_NO_VALUE
    return {"uid": str(node_alias), "output_slot": output_slot}


def _link_target_ref(op: Mapping[str, Any]) -> tuple[str | None, str | int | None]:
    target = op.get("to") if "to" in op else op.get("target")
    if isinstance(target, Mapping):
        uid = _normalize_target_uid(target)
        field = target.get("input_field")
        if not isinstance(field, (str, int)):
            field = target.get("field")
        return uid, field if isinstance(field, (str, int)) else None
    if isinstance(target, list) and len(target) >= 3:
        uid = _normalize_target_uid(target)
        field = target[2]
        return uid, field if isinstance(field, (str, int)) else None
    return None, None


def _read_link_source_endpoint(
    index: _GraphIndex,
    *,
    target_uid: str,
    input_field: str | int,
) -> Any:
    node = _find_node_in_index(index, target_uid)
    if node is None:
        return _SENTINEL_NODE_ABSENT
    inputs = node.get("inputs")
    input_entry = _read_named_socket(inputs, str(input_field))
    if input_entry is _SENTINEL_NO_VALUE:
        return _SENTINEL_NO_VALUE
    if not isinstance(input_entry, Mapping):
        return _SENTINEL_NO_VALUE
    link_id = input_entry.get("link")
    if link_id is None:
        return _SENTINEL_LINK_ABSENT
    link = index.links_by_id.get(link_id)
    if link is None:
        link = index.links_by_id.get(str(link_id))
    if isinstance(link, list) and len(link) >= 3:
        origin_id = link[1]
        origin_slot = link[2]
    elif isinstance(link, Mapping):
        origin_id = link.get("origin_id")
        origin_slot = link.get("origin_slot")
    else:
        return _SENTINEL_NO_VALUE
    origin_node = _find_node_in_index(index, origin_id)
    if origin_node is None:
        return _SENTINEL_NO_VALUE
    origin_uid = _canonical_node_uid(origin_node)
    return _normalize_link_endpoint(origin_uid, origin_slot)


def _resolve_candidate_value_for_op(
    candidate_graph: Mapping[str, Any] | None,
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    op_kind = op.get("op")
    if not isinstance(op_kind, str):
        return (None, f"Missing or invalid op kind: {op_kind!r}")
    candidate_index = _build_graph_index(candidate_graph) if isinstance(candidate_graph, Mapping) else None
    if op_kind == "set_node_field":
        if "value" in op:
            return (op.get("value"), None)
        target = op.get("target")
        uid = _normalize_target_uid(target)
        field_path = target[2] if isinstance(target, list) and len(target) >= 3 else None
        if candidate_index is None or uid is None or not isinstance(field_path, str):
            return (_SENTINEL_NO_VALUE, "Could not resolve candidate field value.")
        node = _find_node_in_index(candidate_index, uid)
        if node is None:
            return (_SENTINEL_NODE_ABSENT, None)
        return (_read_field_value_from_node(node, field_path), None)
    if op_kind == "set_mode":
        if "mode" in op:
            return (op.get("mode"), None)
        uid = _normalize_target_uid(op.get("target"))
        if candidate_index is None or uid is None:
            return (_SENTINEL_NO_VALUE, "Could not resolve candidate mode.")
        node = _find_node_in_index(candidate_index, uid)
        if node is None:
            return (_SENTINEL_NODE_ABSENT, None)
        return (_read_field_value_from_node(node, "mode"), None)
    if op_kind == "reorder":
        order = op.get("order")
        if isinstance(order, list):
            return (tuple(order), None)
        return (_SENTINEL_NO_VALUE, "Reorder op missing order.")
    if op_kind == "upsert_link":
        source = op.get("from")
        if isinstance(source, list) and len(source) >= 3:
            source_uid = _normalize_target_uid(source)
            output_slot = source[2]
            return (_normalize_link_endpoint(source_uid, output_slot), None)
        target_uid, input_field = _link_target_ref(op)
        if candidate_index is None or target_uid is None or input_field is None:
            return (_SENTINEL_NO_VALUE, "Could not resolve candidate link target.")
        return (
            _read_link_source_endpoint(
                candidate_index, target_uid=target_uid, input_field=input_field
            ),
            None,
        )
    if op_kind == "remove_link":
        return (_SENTINEL_LINK_ABSENT, None)
    if op_kind == "add_node":
        # Canonical: prefer explicit uid, then node_id, then scope_path
        uid = op.get("uid")
        if not (isinstance(uid, str) and uid):
            node_id = op.get("node_id")
            if isinstance(node_id, (int, str)) and str(node_id):
                uid = str(node_id)
            else:
                scope_path = op.get("scope_path")
                if isinstance(scope_path, (str, int)) and str(scope_path):
                    uid = str(scope_path)
                else:
                    uid = None
        if candidate_index is not None and isinstance(uid, str) and uid:
            node = _find_node_in_index(candidate_index, uid)
            if node is not None:
                return (
                    {
                        "uid": _canonical_node_uid(node),
                        "id": node.get("id"),
                        "type": node.get("type"),
                    },
                    None,
                )
        return (
            {
                "uid": uid,
                "class_type": op.get("class_type"),
                "fields": op.get("fields"),
                "inputs": op.get("inputs"),
            },
            None,
        )
    if op_kind == "remove_node":
        return (_SENTINEL_NODE_ABSENT, None)
    return (None, f"Unsupported delta op kind: {op_kind!r}")


def _resolve_submit_value_for_set_node_field(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``set_node_field`` op."""
    target = op.get("target")
    if not isinstance(target, list) or len(target) < 3:
        return (None, "Invalid target for set_node_field op")
    uid = _normalize_target_uid(target)
    field_path = target[2] if len(target) > 2 else None
    if not isinstance(uid, str):
        return (None, f"Invalid uid in target: {uid!r}")
    if not isinstance(field_path, str):
        return (None, f"Invalid field_path in target: {field_path!r}")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    value = _read_field_value_from_node(node, field_path)
    return (value, None)


def _resolve_submit_value_for_set_mode(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``set_mode`` op."""
    target = op.get("target")
    uid = _normalize_target_uid(target)
    if uid is None:
        return (None, "Invalid target for set_mode op")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    return (_read_field_value_from_node(node, "mode"), None)


def _resolve_submit_value_for_reorder(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``reorder`` op (current widget/slot order)."""
    target = op.get("target")
    uid = _normalize_target_uid(target)
    if uid is None:
        return (None, "Invalid target for reorder op")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    axis = op.get("axis")
    if axis == "widgets":
        widgets = node.get("widgets")
        if isinstance(widgets, list):
            return (
                tuple(w.get("name") for w in widgets if isinstance(w, Mapping)),
                None,
            )
        return (_SENTINEL_NO_VALUE, "Could not resolve widget reorder from serialized graph.")
    if axis == "inputs":
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            return (
                tuple(
                    entry.get("name")
                    for entry in inputs
                    if isinstance(entry, Mapping) and entry.get("name") is not None
                ),
                None,
            )
        return (_SENTINEL_NO_VALUE, "Could not resolve input reorder from serialized graph.")
    if axis == "outputs":
        outputs = node.get("outputs")
        if isinstance(outputs, list):
            return (
                tuple(
                    entry.get("name")
                    for entry in outputs
                    if isinstance(entry, Mapping) and entry.get("name") is not None
                ),
                None,
            )
        return (_SENTINEL_NO_VALUE, "Could not resolve output reorder from serialized graph.")
    return (_SENTINEL_NO_VALUE, f"Unsupported reorder axis: {axis!r}")


def _resolve_submit_value_for_upsert_link(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for an ``upsert_link`` op.

    Returns the current link source endpoint ``(origin_uid, origin_slot)``
    connected to the target input, or ``_SENTINEL_NO_VALUE`` if unwired.
    """
    target_uid, input_field = _link_target_ref(op)
    if target_uid is None or input_field is None:
        return (None, "Invalid 'to' ref for upsert_link op")
    value = _read_link_source_endpoint(
        _build_graph_index(submit_graph),
        target_uid=target_uid,
        input_field=input_field,
    )
    return (value, None)


def _resolve_submit_value_for_remove_link(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``remove_link`` op (same as upsert_link --
    what link currently feeds the target input)."""
    return _resolve_submit_value_for_upsert_link(submit_graph, op)


def _resolve_submit_value_for_add_node(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for an ``add_node`` op -- expected absence.

    Checks whether any node in the submit graph already claims the UID or
    LiteGraph id carried by the op payload.  Prefers the canonical ``uid``
    and ``node_id`` fields; only falls back to ``scope_path`` when neither
    explicit identity field is present (legacy flat bridge).

    Returns ``_SENTINEL_NODE_ABSENT`` (absent) on success, or
    ``(existing_node_summary, None)`` if a collision is detected (callers
    treat a non-sentinel value as a conflict signal).
    """
    # Canonical path: explicit uid and node_id take priority over scope_path
    explicit_uid = op.get("uid")
    explicit_node_id = op.get("node_id")

    if isinstance(explicit_uid, str) and explicit_uid:
        existing = _find_node_in_graph(submit_graph, explicit_uid)
        if existing is not None:
            return (
                {
                    "uid": _canonical_node_uid(existing),
                    "id": existing.get("id"),
                    "type": existing.get("type"),
                },
                None,
            )
        # Explicit uid was supplied and no collision was found — expected
        # absence for add_node.
        return (_SENTINEL_NODE_ABSENT, None)

    if isinstance(explicit_node_id, (int, str)) and str(explicit_node_id):
        existing = _find_node_in_graph(submit_graph, str(explicit_node_id))
        if existing is not None:
            return (
                {
                    "uid": _canonical_node_uid(existing),
                    "id": existing.get("id"),
                    "type": existing.get("type"),
                },
                None,
            )
        # Explicit node_id was supplied and no collision was found — expected
        # absence for add_node.
        return (_SENTINEL_NODE_ABSENT, None)

    # Legacy fallback: infer identity from scope_path when neither uid nor
    # node_id is present.  This path exists only for pre-canonical flat
    # delta_ops that have not been re-persisted with explicit identity.
    scope_path = op.get("scope_path")
    if isinstance(scope_path, (str, int)) and str(scope_path):
        uid = str(scope_path)
        existing = _find_node_in_graph(submit_graph, uid)
        if existing is not None:
            return (
                {
                    "uid": _canonical_node_uid(existing),
                    "id": existing.get("id"),
                    "type": existing.get("type"),
                },
                None,
            )
        # Valid scope_path, node not found — expected absence for add_node.
        return (_SENTINEL_NODE_ABSENT, None)

    # A canonical add_node must carry at least one of uid, node_id, or
    # scope_path.  If none are present the op is malformed.
    return (
        None,
        "Missing add_node identity: need uid, node_id, or scope_path.",
    )


def _resolve_submit_value_for_remove_node(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``remove_node`` op -- expected presence.

    Returns a summary of the existing node on success, or
    ``_SENTINEL_NO_VALUE`` if already absent.
    """
    target = op.get("target")
    uid = _normalize_target_uid(target)
    if uid is None:
        return (None, "Invalid target for remove_node op")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    return (
        {
            "uid": _canonical_node_uid(node),
            "id": node.get("id"),
            "type": node.get("type"),
        },
        None,
    )


def _resolve_submit_value_for_op(
    *,
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive ``expected_old`` for a single delta op from the submit-time graph.

    Returns ``(expected_old_value, error_message)``.
    ``error_message`` is ``None`` on success.
    """
    op_kind = op.get("op")
    if not isinstance(op_kind, str):
        return (None, f"Missing or invalid op kind: {op_kind!r}")
    if op_kind == "set_node_field":
        return _resolve_submit_value_for_set_node_field(submit_graph, op)
    if op_kind == "set_mode":
        return _resolve_submit_value_for_set_mode(submit_graph, op)
    if op_kind == "reorder":
        return _resolve_submit_value_for_reorder(submit_graph, op)
    if op_kind == "upsert_link":
        return _resolve_submit_value_for_upsert_link(submit_graph, op)
    if op_kind == "remove_link":
        return _resolve_submit_value_for_remove_link(submit_graph, op)
    if op_kind == "add_node":
        return _resolve_submit_value_for_add_node(submit_graph, op)
    if op_kind == "remove_node":
        return _resolve_submit_value_for_remove_node(submit_graph, op)
    return (None, f"Unsupported delta op kind: {op_kind!r}")


def _status_for_scoped_validation_entry(
    *,
    op_kind: str,
    expected_old: Any,
    actual_before: Any,
    desired_new: Any,
    error: str | None,
) -> str:
    if error is not None:
        return "unscopable"
    if expected_old is _SENTINEL_NO_VALUE or actual_before is _SENTINEL_NO_VALUE:
        return "unscopable"
    if desired_new is _SENTINEL_NO_VALUE:
        return "unscopable"
    if op_kind == "remove_node" and actual_before is _SENTINEL_NODE_ABSENT:
        return "already_absent"
    if op_kind == "add_node":
        return "ok" if actual_before is _SENTINEL_NODE_ABSENT else "conflict"
    if op_kind == "remove_link" and actual_before is _SENTINEL_LINK_ABSENT:
        return "already_absent"
    if expected_old == desired_new:
        return "noop"
    if actual_before == expected_old:
        return "ok"
    if actual_before == desired_new:
        return "already_applied"
    return "conflict"


def _scoped_validation_diagnostic_code(entry: Mapping[str, Any]) -> str:
    error = entry.get("error")
    if isinstance(error, str) and (
        "Unsupported delta op kind" in error or "Missing or invalid op kind" in error
    ):
        return "unsupported_delta_op"
    return "unscopable_delta_op"


def _build_scoped_validation_plan_entry(
    *,
    submit_graph: Mapping[str, Any],
    live_graph: Mapping[str, Any],
    candidate_graph: Mapping[str, Any] | None,
    op: Mapping[str, Any],
) -> dict[str, Any]:
    expected_old, expected_error = _resolve_submit_value_for_op(
        submit_graph=submit_graph,
        op=op,
    )
    actual_before, actual_error = _resolve_submit_value_for_op(
        submit_graph=live_graph,
        op=op,
    )
    desired_new, desired_error = _resolve_candidate_value_for_op(candidate_graph, op)
    op_kind = op.get("op")
    errors = [error for error in (expected_error, actual_error, desired_error) if error]
    error = "; ".join(errors) if errors else None
    return {
        "op": op_kind,
        "target": op.get("target") if "target" in op else op.get("to"),
        "expected_old": _scoped_sentinel_payload(expected_old),
        "actual_before": _scoped_sentinel_payload(actual_before),
        "desired_new": _scoped_sentinel_payload(desired_new),
        "status": _status_for_scoped_validation_entry(
            op_kind=op_kind if isinstance(op_kind, str) else "",
            expected_old=expected_old,
            actual_before=actual_before,
            desired_new=desired_new,
            error=error,
        ),
        "error": error,
    }


def _build_scoped_validation_plan(
    *,
    submit_graph: Mapping[str, Any],
    live_graph: Mapping[str, Any],
    candidate_graph: Mapping[str, Any] | None,
    delta_ops: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> dict[str, Any]:
    entries = [
        _build_scoped_validation_plan_entry(
            submit_graph=submit_graph,
            live_graph=live_graph,
            candidate_graph=candidate_graph,
            op=op,
        )
        for op in delta_ops
    ]
    diagnostics = [
        {
            "code": _scoped_validation_diagnostic_code(entry),
            "severity": "error",
            "op": entry.get("op"),
            "target": entry.get("target"),
            "message": entry.get("error") or "Scoped validation could not resolve this op.",
        }
        for entry in entries
        if entry.get("status") == "unscopable"
    ]
    return {
        "entries": entries,
        "diagnostics": diagnostics,
        "ok": not diagnostics,
    }


def _scoped_accept_recovery_payload(
    *,
    turn_id: str,
    submit_graph_hash: str,
    candidate_graph_hash: str,
) -> dict[str, Any]:
    return {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "scoped_accept_conflict",
        "turn_id": turn_id,
        "submit_graph_hash": submit_graph_hash,
        "candidate_graph_hash": candidate_graph_hash,
    }


def _scoped_issue_node_uid(op: Mapping[str, Any]) -> str | None:
    op_kind = op.get("op")
    if op_kind == "add_node":
        # Canonical: explicit uid takes priority; fall back to scope_path
        # only for legacy flat delta_ops that lack explicit identity.
        uid = op.get("uid")
        if isinstance(uid, str) and uid:
            return uid
        node_id = op.get("node_id")
        if isinstance(node_id, (int, str)) and str(node_id):
            return str(node_id)
        scope_path = op.get("scope_path")
        if isinstance(scope_path, (int, str)) and str(scope_path):
            return str(scope_path)
        return None
    target = op.get("target") if "target" in op else op.get("to")
    return _normalize_target_uid(target)


def _scoped_issue_field_path(op: Mapping[str, Any]) -> str | None:
    op_kind = op.get("op")
    if op_kind == "set_node_field":
        target = op.get("target")
        if isinstance(target, list) and len(target) >= 3:
            field_path = target[2]
            return str(field_path) if isinstance(field_path, (int, str)) else None
        return None
    if op_kind == "set_mode":
        return "mode"
    if op_kind == "reorder":
        axis = op.get("axis")
        return str(axis) if isinstance(axis, str) and axis else None
    return None


def _scoped_issue_link_target(op: Mapping[str, Any]) -> dict[str, Any] | None:
    op_kind = op.get("op")
    if op_kind not in {"upsert_link", "remove_link"}:
        return None
    target_uid, input_field = _link_target_ref(op)
    if target_uid is None or input_field is None:
        return None
    return {"node_uid": target_uid, "input_field": input_field}


def _whole_graph_hash_diagnostic(cas_evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": "whole_graph_hash_mismatch",
        "severity": "info",
        "message": "Whole-graph structural CAS mismatched at accept time; v2 used scoped validation instead.",
        "detail": dict(cas_evidence),
    }


def _scoped_accept_issue(
    *,
    op: Mapping[str, Any],
    entry: Mapping[str, Any] | None,
    code: str,
    message: str,
    rebaseline_recovery: Mapping[str, Any],
) -> dict[str, Any]:
    issue = {
        "code": code,
        "op": op.get("op"),
        "node_uid": _scoped_issue_node_uid(op),
        "field_path": _scoped_issue_field_path(op),
        "link_target": _scoped_issue_link_target(op),
        "expected_old": entry.get("expected_old") if isinstance(entry, Mapping) else None,
        "actual_before": entry.get("actual_before") if isinstance(entry, Mapping) else None,
        "desired_new": entry.get("desired_new") if isinstance(entry, Mapping) else None,
        "status": entry.get("status") if isinstance(entry, Mapping) else None,
        "message": message,
        "detail": message,
        "rebaseline_recovery": dict(rebaseline_recovery),
    }
    return {key: value for key, value in issue.items() if value is not None}


def _fail_v2_scoped_accept(
    *,
    scope: Literal["accept"],
    context: TurnContext,
    explanation: str,
    issues: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
) -> FailureEnvelope:
    agent_failure_context: dict[str, Any] = {
        "explanation": explanation,
        "issues": issues,
    }
    if diagnostics:
        agent_failure_context["diagnostics"] = diagnostics
    return failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        scope,
        context,
        agent_failure_context=agent_failure_context,
        queue_allowed=False,
    )


def _build_v2_accept_evidence(
    *,
    session_dir: Path,
    turn_id: str,
    turn_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Load V2 accept evidence from persisted turn/session artifacts.

    Returns a dict with keys:
      * ``submit_graph`` -- the submit-time graph loaded from ``request.json``
      * ``candidate_graph`` -- the candidate graph loaded from ``response.json``
      * ``delta_ops`` -- authoritative mutation-intent list from the canonical
        envelope (preferred) or legacy flat bridge
      * ``delta_shape_diagnostic`` -- classification of the delta payload shape
      * ``submit_graph_hash`` -- hash of the loaded submit graph
      * ``candidate_graph_hash`` -- from the turn record
      * ``protocol`` -- ``"v2_delta"``
      * ``loaded_ok`` -- ``True`` iff required evidence was loaded
      * ``diagnostics`` -- list of evidence-loading issues, classified into
        distinct buckets: *malformed_delta*, *legacy_delta_shape*,
        *unsupported_scoped_apply*, *missing_submit_graph*,
        *missing_candidate_graph*
    """
    evidence: dict[str, Any] = {
        "submit_graph": None,
        "candidate_graph": None,
        "delta_ops": None,
        "delta_shape_diagnostic": None,
        "submit_graph_hash": None,
        "candidate_graph_hash": None,
        "protocol": "v2_delta",
        "loaded_ok": True,
        "diagnostics": [],
    }

    submit_graph = _load_turn_request_graph(session_dir=session_dir, turn_id=turn_id)
    if submit_graph is not None:
        evidence["submit_graph"] = submit_graph
        evidence["submit_graph_hash"] = payload_hash(submit_graph)
    else:
        evidence["loaded_ok"] = False
        evidence["diagnostics"].append(
            {
                "code": "missing_submit_graph",
                "severity": "error",
                "message": "Could not load submit-time graph from turn artifacts.",
            }
        )

    # Classify the delta shape before loading so we can surface legacy /
    # malformed shapes in distinct evidence buckets.
    shape_diag = _load_turn_delta_ops_diagnostic(
        session_dir=session_dir, turn_id=turn_id
    )
    evidence["delta_shape_diagnostic"] = shape_diag

    delta_ops = _load_turn_delta_ops(session_dir=session_dir, turn_id=turn_id)
    if delta_ops is not None:
        evidence["delta_ops"] = delta_ops
        # Optional: surface legacy flat bridge use as an info diagnostic.
        if shape_diag.get("code") == "legacy_delta_ops_flat":
            evidence["diagnostics"].append(
                {
                    "code": "legacy_delta_shape",
                    "severity": "info",
                    "message": (
                        "Delta loaded from legacy flat delta_ops list; "
                        "canonical consumers should migrate to "
                        "delta_ops_envelope."
                    ),
                    "detail": shape_diag.get("detail", {}),
                }
            )
    else:
        evidence["loaded_ok"] = False
        diag_code = shape_diag.get("code", "missing_delta_ops")
        diag_message: str
        if diag_code == "legacy_delta_shape":
            diag_message = (
                "Persisted delta uses a legacy wrapped shape that is not a "
                "canonical V2 envelope; re-persist the turn with a canonical "
                "delta_ops_envelope."
            )
            evidence["delta_ops"] = ()
        elif diag_code == "canonical_envelope_malformed_ops":
            diag_code = "malformed_delta"
            diag_message = (
                "Canonical delta_ops_envelope is present but its `ops` field "
                "is malformed."
            )
        elif diag_code == "missing_turn_response":
            diag_message = "Could not load the persisted turn response."
        else:
            diag_message = (
                "Could not load delta_ops from persisted turn response."
            )
        evidence["diagnostics"].append(
            {
                "code": diag_code,
                "severity": "error",
                "message": diag_message,
                "detail": shape_diag.get("detail", {}),
            }
        )

    candidate_graph_hash = turn_record.get("candidate_graph_hash")
    if isinstance(candidate_graph_hash, str):
        evidence["candidate_graph_hash"] = candidate_graph_hash
    candidate_graph = _load_turn_candidate_graph(session_dir=session_dir, turn_id=turn_id)
    if candidate_graph is not None:
        evidence["candidate_graph"] = candidate_graph
    else:
        evidence["loaded_ok"] = False
        evidence["diagnostics"].append(
            {
                "code": "missing_candidate_graph",
                "severity": "error",
                "message": "Could not load candidate graph from persisted turn response.",
            }
        )

    return evidence


def _mutate_turn_state(
    *,
    session_root: Path,
    session_id: str,
    turn_id: str,
    scope: Literal["accept", "reject"],
    client_graph_hash: str | None,
    request_payload: Any,
    idempotency_key: str | None = None,
    response_writer: Callable[[dict[str, Any]], Path] | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any] | FailureEnvelope:
    session_dir = session_dir_for(session_root, session_id)
    request_digest = payload_hash(request_payload)
    key = _record_key(scope, idempotency_key)

    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
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
                    _conflict_kind(scope),
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Idempotency key was reused with a different request hash.",
                        "idempotency_key": idempotency_key,
                        "existing_request_hash": existing.get("request_hash"),
                        "request_hash": request_digest,
                    },
                )

        turn_record = state["turns"].get(turn_id)
        if not isinstance(turn_record, dict):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={"explanation": f"Unknown turn_id {turn_id!r}."},
            )

        current_state = turn_record.get("state")
        target_state: TurnState = "accepted" if scope == "accept" else "rejected"
        opposite_state: TurnState = "rejected" if scope == "accept" else "accepted"
        if current_state == "unknown":
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": f"Turn {turn_id} was superseded by a newer accepted turn.",
                    "accepted_state": current_state,
                },
            )
        if current_state == opposite_state:
            return failure_envelope(
                FailureKind.EDITOR_AHEAD_CONFLICT,
                scope,
                context,
                agent_failure_context={
                    "explanation": f"Turn {turn_id} is already {opposite_state}.",
                    "accepted_state": current_state,
                },
            )

        submit_graph_hash = turn_record.get("submit_graph_hash")
        if not isinstance(submit_graph_hash, str):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Turn has no persisted submit graph hash.",
                    "turn_id": turn_id,
                    "submit_graph_hash_present": False,
                },
            )
        candidate_graph_hash = turn_record.get("candidate_graph_hash")
        if not isinstance(candidate_graph_hash, str):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Turn has no persisted candidate graph hash.",
                    "turn_id": turn_id,
                    "candidate_graph_hash_present": False,
                },
            )
        candidate_structural_graph_hash = turn_record.get("candidate_structural_graph_hash")
        stored_struct_version = turn_record.get("candidate_structural_graph_hash_version")
        recomputed_candidate_structural_graph_hash: str | None = None
        if (
            not isinstance(candidate_structural_graph_hash, str)
            or stored_struct_version != STRUCTURAL_PROJECTION_VERSION
        ):
            recomputed = _candidate_structural_hash_from_turn_dir(
                session_dir=session_dir,
                turn_id=turn_id,
            )
            if isinstance(recomputed, str):
                candidate_structural_graph_hash = recomputed
                recomputed_candidate_structural_graph_hash = recomputed
        if not isinstance(candidate_structural_graph_hash, str):
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Turn has no persisted candidate structural graph hash.",
                    "turn_id": turn_id,
                    "candidate_structural_graph_hash_present": False,
                },
            )
        agent_edit_protocol = turn_record.get("agent_edit_protocol")
        expected_baseline: ExpectedBaseline | None = None
        v2_whole_graph_hash_diagnostic: dict[str, Any] | None = None
        if scope == "accept":
            expected_baseline = _expected_baseline_for_turn(turn_record, state)
            if not expected_baseline.reliable:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Cannot derive a reliable expected baseline for this turn.",
                        "turn_id": turn_id,
                        **expected_baseline.evidence,
                    },
                )
            cas_evidence = _accept_structural_cas_evidence(
                expected_baseline=expected_baseline,
                state=state,
                turn_record=turn_record,
            )
            if agent_edit_protocol == "v2_delta":
                if cas_evidence is not None:
                    v2_whole_graph_hash_diagnostic = _whole_graph_hash_diagnostic(cas_evidence)
            elif cas_evidence is not None:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Accepted turn no longer matches the authoritative structural baseline.",
                        "turn_id": turn_id,
                        **cas_evidence,
                    },
                )
        submitted_client_graph_hash = turn_record.get("submitted_client_graph_hash")
        action_diagnostics: list[dict[str, Any]] = []
        _scoped_accept_result: dict[str, Any] | None = None
        _delta_ops_echo: list[dict[str, Any]] | None = None
        if scope == "accept" and agent_edit_protocol == "v2_delta":
            if not isinstance(request_payload, Mapping):
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={"explanation": "Accept request body must be a JSON object."},
                )
            if not isinstance(request_payload.get("live_graph"), Mapping):
                return failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "V2 accept requires `live_graph` (current serialized canvas snapshot).",
                        "turn_id": turn_id,
                    },
                )
            request_submit_graph_hash = request_payload.get("submit_graph_hash")
            request_candidate_graph_hash = request_payload.get("candidate_graph_hash")
            request_live_canvas_token = request_payload.get("client_live_canvas_token")
            submitted_live_canvas_token = turn_record.get("submitted_client_live_canvas_token")
            if request_submit_graph_hash != submit_graph_hash:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Accepted v2 turn did not echo the server-side submit graph hash.",
                        "turn_id": turn_id,
                        "submit_graph_hash": submit_graph_hash,
                        "request_submit_graph_hash": request_submit_graph_hash,
                    },
                )
            if request_candidate_graph_hash != candidate_graph_hash:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Accepted v2 turn did not match the persisted candidate graph hash.",
                        "turn_id": turn_id,
                        "candidate_graph_hash": candidate_graph_hash,
                        "request_candidate_graph_hash": request_candidate_graph_hash,
                    },
                )
            if (
                not isinstance(submitted_live_canvas_token, str)
                or not submitted_live_canvas_token
                or request_live_canvas_token != submitted_live_canvas_token
            ):
                action_diagnostics.append(
                    {
                        "code": "client_live_canvas_token_mismatch",
                        "severity": "info",
                        "message": "Client live-canvas token differed from the token captured at v2 submit time.",
                        "detail": {
                            "turn_id": turn_id,
                            "client_live_canvas_token": request_live_canvas_token,
                            "submitted_client_live_canvas_token": submitted_live_canvas_token,
                        },
                    }
                )
            if v2_whole_graph_hash_diagnostic is not None:
                action_diagnostics.append(v2_whole_graph_hash_diagnostic)
            v2_evidence = _build_v2_accept_evidence(
                session_dir=session_dir,
                turn_id=turn_id,
                turn_record=turn_record,
            )
            if not v2_evidence["loaded_ok"]:
                recovery = _scoped_accept_recovery_payload(
                    turn_id=turn_id,
                    submit_graph_hash=submit_graph_hash,
                    candidate_graph_hash=candidate_graph_hash,
                )
                issues = [
                    {
                        "code": diagnostic.get("code"),
                        "message": diagnostic.get("message"),
                        "detail": diagnostic.get("message"),
                        "rebaseline_recovery": dict(recovery),
                    }
                    for diagnostic in v2_evidence["diagnostics"]
                ]
                return _fail_v2_scoped_accept(
                    scope="accept",
                    context=context,
                    explanation="Scoped accept verification could not load persisted v2 evidence.",
                    issues=issues,
                    diagnostics=action_diagnostics,
                )
            else:
                scoped_plan = _build_scoped_validation_plan(
                    submit_graph=v2_evidence["submit_graph"],
                    live_graph=request_payload["live_graph"],
                    candidate_graph=v2_evidence.get("candidate_graph"),
                    delta_ops=v2_evidence["delta_ops"],
                )
                acceptable_statuses = {"ok", "noop", "already_applied", "already_absent"}
                conflict_entries = [
                    entry
                    for entry, op in zip(scoped_plan["entries"], v2_evidence["delta_ops"])
                    if entry.get("status") not in acceptable_statuses
                    and isinstance(op, Mapping)
                ]
                if not scoped_plan["ok"] or conflict_entries:
                    recovery = _scoped_accept_recovery_payload(
                        turn_id=turn_id,
                        submit_graph_hash=submit_graph_hash,
                        candidate_graph_hash=candidate_graph_hash,
                    )
                    issues = [
                        _scoped_accept_issue(
                            op=op,
                            entry=entry,
                            code=(
                                _scoped_validation_diagnostic_code(entry)
                                if entry.get("status") == "unscopable"
                                else "scoped_conflict"
                            ),
                            message=(
                                entry.get("error")
                                if entry.get("status") == "unscopable"
                                else (
                                    f"Scoped accept verification failed for {entry.get('op')} "
                                    f"because live state was {entry.get('status')}."
                                )
                            ),
                            rebaseline_recovery=recovery,
                        )
                        for entry, op in zip(scoped_plan["entries"], v2_evidence["delta_ops"])
                        if (
                            entry.get("status") == "unscopable"
                            or entry in conflict_entries
                        )
                        and isinstance(op, Mapping)
                    ]
                    return _fail_v2_scoped_accept(
                        scope="accept",
                        context=context,
                        explanation="Scoped accept verification failed.",
                        issues=issues,
                        diagnostics=action_diagnostics,
                    )
                # Capture scoped verification and delta_ops for the response payload.
                _scoped_accept_result = scoped_plan
                if isinstance(v2_evidence.get("delta_ops"), (tuple, list)):
                    _delta_ops_echo = [dict(op) for op in v2_evidence["delta_ops"]]
        else:
            # V1 compatibility: the backend's `submit_graph_hash` is canonical,
            # while older browser clients send their own hash. Accept either
            # submit-time fingerprint only for non-v2 turns.
            accepted_submit_hashes = {submit_graph_hash}
            if isinstance(submitted_client_graph_hash, str) and submitted_client_graph_hash:
                accepted_submit_hashes.add(submitted_client_graph_hash)
            request_submit_graph_hash = (
                request_payload.get("submit_graph_hash")
                if isinstance(request_payload, Mapping)
                and isinstance(request_payload.get("submit_graph_hash"), str)
                else None
            )
            request_live_graph = (
                request_payload.get("live_graph")
                if isinstance(request_payload, Mapping)
                and isinstance(request_payload.get("live_graph"), Mapping)
                else None
            )
            request_live_graph_hash = (
                payload_hash(request_live_graph)
                if request_live_graph is not None
                else None
            )
            request_live_structural_graph_hash = (
                structural_graph_hash(request_live_graph)
                if request_live_graph is not None
                else None
            )
            submit_structural_graph_hash = (
                turn_record.get("submit_structural_graph_hash")
                if isinstance(turn_record.get("submit_structural_graph_hash"), str)
                else None
            )
            echoed_submit_graph_matches = (
                isinstance(submit_graph_hash, str)
                and request_submit_graph_hash == submit_graph_hash
                and (
                    request_live_graph_hash == submit_graph_hash
                    or (
                        isinstance(submit_structural_graph_hash, str)
                        and request_live_structural_graph_hash == submit_structural_graph_hash
                    )
                )
            )
            if client_graph_hash not in accepted_submit_hashes and not echoed_submit_graph_matches:
                return failure_envelope(
                    FailureKind.STALE_STATE_MISMATCH,
                    scope,
                    context,
                    agent_failure_context={
                        "explanation": "Client graph hash does not match the graph submitted for this turn.",
                        "turn_id": turn_id,
                        "client_graph_hash": client_graph_hash,
                        "submit_graph_hash": submit_graph_hash,
                        "submitted_client_graph_hash": submitted_client_graph_hash,
                        "request_submit_graph_hash": request_submit_graph_hash,
                        "request_live_graph_hash": request_live_graph_hash,
                        "request_live_structural_graph_hash": request_live_structural_graph_hash,
                        "submit_structural_graph_hash": submit_structural_graph_hash,
                    },
                )

        timestamp_key = "accepted_at" if scope == "accept" else "rejected_at"
        if recomputed_candidate_structural_graph_hash is not None:
            turn_record[
                "candidate_structural_graph_hash"
            ] = recomputed_candidate_structural_graph_hash
            turn_record[
                "candidate_structural_graph_hash_version"
            ] = STRUCTURAL_PROJECTION_VERSION
        turn_record["state"] = target_state
        turn_record["client_graph_hash"] = client_graph_hash
        turn_record[timestamp_key] = turn_record.get(timestamp_key) or _now()
        turn_record["action_request_hash"] = request_digest
        turn_record["action_client_graph_hash"] = client_graph_hash
        turn_record["action_submit_graph_hash"] = (
            submit_graph_hash if isinstance(submit_graph_hash, str) else None
        )
        unknown_transitions: list[dict[str, Any]] = []
        if scope == "accept":
            _set_baseline_authoritatively(
                state,
                next_hash=candidate_structural_graph_hash,
                next_kind="structural",
                next_source="turn",
                reason="accept_turn",
                source_turn_id=turn_id,
                source_path=_source_path_for_turn_baseline(session_dir, turn_id),
                projection_version=STRUCTURAL_PROJECTION_VERSION,
            )
            for other_turn_id, other_record in state["turns"].items():
                if other_turn_id == turn_id or not isinstance(other_record, dict):
                    continue
                if other_record.get("state") != "candidate":
                    continue
                other_record["state"] = "unknown"
                other_record["unknown_at"] = other_record.get("unknown_at") or _now()
                other_record["unknown_reason"] = "superseded_by_accept"
                other_record["superseded_by_turn_id"] = turn_id
                transitioned_at = other_record["unknown_at"]
                unknown_transitions.append(
                    {
                        "session_id": session_id,
                        "turn_id": other_turn_id,
                        "from_state": "candidate",
                        "to_state": "unknown",
                        "reason": "superseded_by_accept",
                        "superseded_by_turn_id": turn_id,
                        "transitioned_at": transitioned_at,
                    }
                )

        response = {
            "ok": True,
            "action": scope,
            "session_id": session_id,
            "turn_id": turn_id,
            "baseline_turn_id": state.get("baseline_turn_id"),
            "baseline_graph_hash": state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": state.get("baseline_graph_hash_kind"),
            "accepted_state": target_state,
            "client_graph_hash": client_graph_hash,
            "submit_graph_hash": submit_graph_hash,
            "submit_structural_graph_hash": turn_record.get("submit_structural_graph_hash"),
            "submitted_client_live_canvas_token": turn_record.get(
                "submitted_client_live_canvas_token"
            ),
            "candidate_graph_hash": turn_record.get("candidate_graph_hash"),
            "candidate_structural_graph_hash": turn_record.get("candidate_structural_graph_hash"),
            "expected_baseline_graph_hash": (
                expected_baseline.graph_hash if expected_baseline is not None else None
            ),
            "expected_baseline_graph_hash_kind": (
                expected_baseline.hash_kind if expected_baseline is not None else None
            ),
            "unknown_transitions": unknown_transitions,
            "idempotency_key": idempotency_key,
        }
        if action_diagnostics:
            response["diagnostics"] = action_diagnostics
        if _scoped_accept_result is not None:
            response["scoped_accept_verification"] = {
                "entries": _scoped_accept_result["entries"],
                "ok": _scoped_accept_result["ok"],
            }
        if _delta_ops_echo is not None:
            response["delta_ops"] = _delta_ops_echo
        if key is not None and response_writer is not None:
            response_path = response_writer(response)
            state["idempotency_records"][key] = {
                "request_hash": request_digest,
                "response_hash": payload_hash(response),
                "response_path": str(response_path),
                "created_at": _now(),
                "operation": scope,
                "turn_id": turn_id,
            }
        write_state_atomic(session_dir, state)
        return response


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
    return _mutate_turn_state(
        session_root=session_root,
        session_id=session_id,
        turn_id=turn_id,
        scope="accept",
        client_graph_hash=client_graph_hash,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        response_writer=response_writer,
    )


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
    return _mutate_turn_state(
        session_root=session_root,
        session_id=session_id,
        turn_id=turn_id,
        scope="reject",
        client_graph_hash=client_graph_hash,
        request_payload=request_payload,
        idempotency_key=idempotency_key,
        response_writer=response_writer,
    )


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
    "normalize_path_component",
    "normalize_session_id",
    "payload_hash",
    "read_state",
    "record_idempotent_response",
    "rebaseline_session",
    "reject_turn",
    "session_dir_for",
    "turn_dir_for",
    "write_state_atomic",
]
