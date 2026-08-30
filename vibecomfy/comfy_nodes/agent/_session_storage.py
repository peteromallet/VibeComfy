"""Durable session-state loading, normalization, and atomic JSON persistence."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from vibecomfy.ingest.normalize import door_get_nodes

from .contracts import DiagnosticRecord


STATE_FILE_NAME = "session_state.json"
STATE_SCHEMA_VERSION = 1

DurableReadStatus = Literal["absent", "valid", "corrupt", "unreadable"]


@dataclass(frozen=True)
class DurableRead:
    """Typed result for a persisted artifact read."""

    status: DurableReadStatus
    value: Any = None
    path: Path | None = None
    error: str | None = None


class DurableReadError(RuntimeError):
    """Raised when an existing durable artifact cannot be trusted."""

    def __init__(self, read: DurableRead) -> None:
        if read.status not in {"corrupt", "unreadable"}:
            raise ValueError("DurableReadError requires a failed read")
        self.status = read.status
        self.path = read.path
        self.error = read.error
        super().__init__(
            f"{read.status} durable artifact"
            + (f" at {read.path}" if read.path is not None else "")
            + (f": {read.error}" if read.error else "")
        )


def default_state_impl(*, schema_version: int) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
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
        # These fields are a discoverable index over the authoritative
        # per-turn artifacts. They can be reconstructed from artifact truth.
        "next_generation": 1,
        "prepared_transactions": {},
        "apply_idempotency_records": {},
    }


def set_baseline_authoritatively_impl(
    state: dict[str, Any],
    *,
    next_hash: str | None,
    next_kind: Literal["structural", "raw"] | None,
    next_source: Literal["none", "turn", "rebaseline", "legacy"],
    reason: str,
    source_turn_id: str | None = None,
    rebaseline_id: str | None = None,
    source_path: str | None = None,
    projection_version: int | None = None,
    metadata: Mapping[str, Any] | None = None,
    structural_projection_version: int,
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
        projection_version = structural_projection_version

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


def source_path_for_turn_baseline_impl(
    session_dir: Path,
    turn_id: str,
) -> str | None:
    for relative in (
        Path("turns") / turn_id / "applied.ui.json",
        Path("turns") / turn_id / "candidate.ui.json",
        Path("turns") / turn_id / "response.json",
    ):
        if (session_dir / relative).is_file():
            return relative.as_posix()
    return None


def structural_hash_from_source_path_impl(
    session_dir: Path,
    source_path: str | None,
) -> str | None:
    from vibecomfy.comfy_nodes.agent.session import structural_graph_hash

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


def normalize_baseline_state_impl(
    session_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.session import (
        STRUCTURAL_PROJECTION_VERSION,
        _set_baseline_authoritatively,
        _source_path_for_turn_baseline,
        _structural_hash_from_source_path,
    )

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
                    source_path=_source_path_for_turn_baseline(
                        session_dir,
                        baseline_turn_id,
                    ),
                    projection_version=STRUCTURAL_PROJECTION_VERSION,
                )
                return state
            if not isinstance(baseline_hash, str):
                migrated_hash = baseline_turn.get(
                    "candidate_graph_hash"
                ) or baseline_turn.get("client_graph_hash")
                baseline_hash = (
                    migrated_hash if isinstance(migrated_hash, str) else None
                )
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
            source_path = (
                Path("_rebaseline") / rebaseline_id / "graph.ui.json"
            ).as_posix()
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


def read_state_impl(session_dir: Path) -> dict[str, Any]:
    result = read_state_result_impl(session_dir)
    if result.status == "absent":
        return default_state_impl(schema_version=STATE_SCHEMA_VERSION)
    if result.status != "valid":
        raise DurableReadError(result)
    return result.value


def read_state_result_impl(session_dir: Path) -> DurableRead:
    from vibecomfy.comfy_nodes.agent.session import (
        STATE_FILE_NAME,
        STATE_SCHEMA_VERSION,
        _normalize_apply_idempotency_records,
        _normalize_baseline_state,
        _normalize_prepared_transactions_index,
        default_state,
    )

    path = session_dir / STATE_FILE_NAME
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DurableRead("absent", path=path)
    except (OSError, UnicodeDecodeError) as exc:
        return DurableRead("unreadable", path=path, error=str(exc))
    try:
        state = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        return DurableRead("corrupt", path=path, error=str(exc))
    if not isinstance(state, dict):
        return DurableRead(
            "corrupt", path=path, error="session state must be a JSON object"
        )
    merged = default_state()
    merged.update(state)
    if not isinstance(merged.get("turns"), dict):
        merged["turns"] = {}
    if not isinstance(merged.get("idempotency_records"), dict):
        merged["idempotency_records"] = {}
    if not isinstance(merged.get("next_turn_index"), int) or merged[
        "next_turn_index"
    ] < 1:
        merged["next_turn_index"] = 1
    if (
        not isinstance(merged.get("next_rebaseline_index"), int)
        or merged["next_rebaseline_index"] < 1
    ):
        merged["next_rebaseline_index"] = 1
    if not isinstance(merged.get("next_generation"), int) or merged[
        "next_generation"
    ] < 1:
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
    return DurableRead("valid", value=merged, path=path)


def load_json_impl(path: Path) -> dict[str, Any] | None:
    result = load_json_result_impl(path)
    if result.status != "valid" or not isinstance(result.value, dict):
        return None
    return result.value


def load_json_result_impl(path: Path) -> DurableRead:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DurableRead("absent", path=path)
    except (OSError, UnicodeDecodeError) as exc:
        return DurableRead("unreadable", path=path, error=str(exc))
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        return DurableRead("corrupt", path=path, error=str(exc))
    if not isinstance(data, dict):
        return DurableRead("corrupt", path=path, error="JSON value must be an object")
    return DurableRead("valid", value=data, path=path)


def iter_turn_records_impl(
    session_root: Path | str,
    session_id: str,
) -> Iterator[DiagnosticRecord]:
    from vibecomfy.comfy_nodes.agent.session import (
        _read_response_publication,
        _turn_directories,
        read_state,
    )

    session_dir = Path(session_root) / session_id
    if not session_dir.is_dir():
        return

    state = read_state(session_dir)
    st_turns: dict[str, Any] = (
        state.get("turns") if isinstance(state.get("turns"), dict) else {}
    )
    baseline_turn_id = state.get("baseline_turn_id")
    turn_dirs = _turn_directories(session_dir)
    if not turn_dirs:
        return

    for turn_dir in turn_dirs:
        turn_id = turn_dir.name
        publication = _read_response_publication(turn_dir)
        if publication is not None:
            response = dict(publication["response"])
        else:
            response_result = load_json_result_impl(turn_dir / "response.json")
            if response_result.status == "absent":
                response = {}
            elif response_result.status != "valid":
                raise DurableReadError(response_result)
            else:
                response = dict(response_result.value)
        request_result = load_json_result_impl(turn_dir / "request.json")
        if request_result.status == "absent":
            request = {}
        elif request_result.status != "valid":
            raise DurableReadError(request_result)
        else:
            request = dict(request_result.value)
        life = st_turns.get(turn_id, {})
        if not isinstance(life, Mapping):
            life = {}
        gates = response.get("gates") or {}
        ok = response.get("ok")
        kind = response.get("kind")
        unchanged = response.get("graph_unchanged")
        lifecycle = life.get("state")

        if lifecycle == "accepted":
            outcome = "✅ APPLIED"
        elif lifecycle == "rejected":
            outcome = "✗ rejected"
        elif lifecycle == "discarded":
            outcome = "✗ discarded"
        elif lifecycle == "unknown" and life.get("superseded_by_turn_id"):
            outcome = "↷ superseded"
        elif lifecycle == "finalized":
            outcome = "✅ FINALIZED"
        elif lifecycle == "rollback_complete":
            outcome = "↺ ROLLED BACK"
        elif lifecycle == "canvas_verified":
            outcome = "🔍 canvas-verified"
        elif lifecycle == "apply_prepared":
            outcome = "⏳ apply-prepared"
        elif lifecycle == "review_bound":
            outcome = "👁 review-bound"
        elif lifecycle == "candidate_ready":
            outcome = "📋 candidate-ready"
        elif lifecycle == "submitted":
            outcome = "📨 submitted"
        elif lifecycle == "rollback_prepared":
            outcome = "⏳ rollback-prepared"
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
            len(door_get_nodes(candidate_graph, []))
            if isinstance(candidate_graph, dict)
            else None
        )

        yield DiagnosticRecord(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=(
                baseline_turn_id if turn_id == baseline_turn_id else None
            ),
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


def candidate_structural_hash_from_turn_dir_impl(
    *,
    session_dir: Path,
    turn_id: str,
) -> str | None:
    from vibecomfy.comfy_nodes.agent.session import structural_graph_hash

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


def write_state_atomic_impl(
    session_dir: Path,
    state: dict[str, Any],
    *,
    state_file_name: str,
) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    target = session_dir / state_file_name
    tmp = session_dir / f".{state_file_name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    tmp.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)


def write_response_atomic_impl(
    response_path: Path,
    response: dict[str, Any],
) -> None:
    response_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = response_path.with_name(
        f".{response_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    )
    tmp.write_text(
        json.dumps(response, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(response_path)


def write_response_immutable_impl(
    response_path: Path,
    response: Mapping[str, Any],
) -> bool:
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
