from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from .agent_contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope

STATE_FILE_NAME = "session_state.json"
LOCK_FILE_NAME = ".session_state.lock"
STATE_SCHEMA_VERSION = 1
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.025

OperationScope = Literal["edit", "accept", "reject"]
TurnState = Literal["candidate", "accepted", "rejected", "unknown"]


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


def session_dir_for(root: Path, session_id: str) -> Path:
    return root / session_id


def turn_dir_for(root: Path, session_id: str, turn_id: str) -> Path:
    return session_dir_for(root, session_id) / "turns" / turn_id


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SessionStateLock:
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
                os.write(self._fd, f"{os.getpid()} {time.time()}\n".encode("ascii"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out acquiring session lock {self.lock_path}")
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def default_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "next_turn_index": 1,
        "baseline_turn_id": None,
        "baseline_graph_hash": None,
        "turns": {},
        "idempotency_records": {},
    }


def read_state(session_dir: Path) -> dict[str, Any]:
    path = session_dir / STATE_FILE_NAME
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
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
    if merged.get("baseline_graph_hash") is None and isinstance(merged.get("baseline_turn_id"), str):
        baseline_turn = merged["turns"].get(merged["baseline_turn_id"])
        if isinstance(baseline_turn, dict):
            migrated_hash = baseline_turn.get("candidate_graph_hash") or baseline_turn.get(
                "client_graph_hash"
            )
            merged["baseline_graph_hash"] = migrated_hash if isinstance(migrated_hash, str) else None
    merged["schema_version"] = STATE_SCHEMA_VERSION
    return merged


def write_state_atomic(session_dir: Path, state: dict[str, Any]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    target = session_dir / STATE_FILE_NAME
    tmp = session_dir / f".{STATE_FILE_NAME}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    tmp.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)


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


def _client_graph_hash(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("client_graph_hash")
    return value if isinstance(value, str) else None


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
    submitted_client_graph_hash = _client_graph_hash(request_payload)
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
            "submitted_client_graph_hash": submitted_client_graph_hash,
            "candidate_graph_hash": None,
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
    if key is None:
        if scope == "edit" and turn_id is not None:
            session_dir = session_dir_for(session_root, session_id)
            with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
                state = read_state(session_dir)
                turn_record = state["turns"].get(turn_id)
                if isinstance(turn_record, dict):
                    turn_record["candidate_graph_hash"] = candidate_graph_hash
                    write_state_atomic(session_dir, state)
        return None
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    response_digest = payload_hash(response)
    record = {
        "request_hash": request_hash,
        "response_hash": response_digest,
        "response_path": str(response_path),
        "created_at": _now(),
        "operation": operation,
        "turn_id": turn_id,
    }
    session_dir = session_dir_for(session_root, session_id)
    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        if scope == "edit" and turn_id is not None:
            turn_record = state["turns"].get(turn_id)
            if isinstance(turn_record, dict):
                turn_record["candidate_graph_hash"] = candidate_graph_hash
        state["idempotency_records"][key] = record
        write_state_atomic(session_dir, state)
    return record


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
        if client_graph_hash != submit_graph_hash:
            return failure_envelope(
                FailureKind.STALE_STATE_MISMATCH,
                scope,
                context,
                agent_failure_context={
                    "explanation": "Client graph hash does not match the graph submitted for this turn.",
                    "turn_id": turn_id,
                    "client_graph_hash": client_graph_hash,
                    "submit_graph_hash": submit_graph_hash,
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

        timestamp_key = "accepted_at" if scope == "accept" else "rejected_at"
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
            state["baseline_turn_id"] = turn_id
            state["baseline_graph_hash"] = candidate_graph_hash
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
            "accepted_state": target_state,
            "client_graph_hash": client_graph_hash,
            "submit_graph_hash": submit_graph_hash,
            "candidate_graph_hash": turn_record.get("candidate_graph_hash"),
            "unknown_transitions": unknown_transitions,
            "idempotency_key": idempotency_key,
        }
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


__all__ = [
    "IdempotencyConflict",
    "IdempotencyReplay",
    "SessionStateLock",
    "TurnAllocation",
    "accept_turn",
    "allocate_turn",
    "canonical_json_bytes",
    "default_state",
    "payload_hash",
    "read_state",
    "record_idempotent_response",
    "reject_turn",
    "session_dir_for",
    "turn_dir_for",
    "write_state_atomic",
]
