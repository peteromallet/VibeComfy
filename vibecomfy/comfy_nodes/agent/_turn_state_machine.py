"""Turn state machine: accept/reject turn-state transitions (T-046, ORACLE-7, SPINE).

Extracted from ``vibecomfy.comfy_nodes.agent.session`` (T-046, ORACLE-7, SPINE): the
turn-state-machine range (session.py :5828-6402 per S6 ground truth; post-T-044/045 the
surviving code is ``_mutate_turn_state`` at :4143-4664).  ``session`` re-exports this
module via ``from ._turn_state_machine import *`` (façade seam added at T-043);
``__all__`` below is exactly the name set this range contributed to the session
namespace, so the re-export reproduces the identical top-level attributes -- the same
contract ``edit`` uses for its ``_frag_*`` fragments (including ``_``-prefixed helpers
that stay importable by name for the T-048 monkeypatch/importer compatibility).

Dependency style (S6 ground truth): this range contains the ONE ``write_state_atomic``
call site (old session.py:6398) and it MUST late-bind the host façade's
``write_state_atomic`` at call time (function-local, host namespace lookup, resolved at
call time) because backend tests monkeypatch ``session.write_state_atomic`` and the
patched attribute must be visible when ``_mutate_turn_state`` runs -- a module-level
import would freeze the original and break the monkeypatch.  Every other name that
lives in the host ``session`` façade is resolved with the same T-046 late import
(function-local, host namespace lookup, resolved at call time) so the
``session`` -> ``_turn_state_machine`` re-export cycle never bites and module-attr
patching on ``session`` stays visible.  Non-cyclic deps (``contracts``,
``candidate_transaction``, ``_v2_scoped_validation``) are imported ordinarily at module
level.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Literal

from .candidate_transaction import classify_legacy_migration_v1
from .contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope
from ._v2_scoped_validation import (
    _build_scoped_validation_plan,
    _build_v2_accept_evidence,
    _fail_v2_scoped_accept,
    _scoped_accept_issue,
    _scoped_accept_recovery_payload,
    _scoped_validation_diagnostic_code,
    _whole_graph_hash_diagnostic,
)
# T-046 module-level host imports: ``DEFAULT_LOCK_TIMEOUT_SECONDS`` is needed at
# module-execution time as the default parameter value of ``lock_timeout_seconds``
# (defaults are evaluated at function-definition time, not call time -- the same
# def-time binding the original session module had); ``ExpectedBaseline`` and
# ``TurnState`` are referenced only in annotations (PEP 563 strings -- never evaluated
# at runtime), imported here so those annotations stay resolvable for type checkers.
# ``session`` is fully defined before its end-of-file ``from ._turn_state_machine
# import *`` re-export, so the cycle never bites when ``session`` is the entry point.
from .session import DEFAULT_LOCK_TIMEOUT_SECONDS, ExpectedBaseline, TurnState

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
    from vibecomfy.comfy_nodes.agent.session import (  # T-046 late import: host namespace lookup; resolved at call time
        STRUCTURAL_PROJECTION_VERSION,
        SessionStateLock,
        _V2_PRE_FINALIZE_STATES,
        _V2_TERMINAL_STATES,
        _accept_structural_cas_evidence,
        _candidate_structural_hash_from_turn_dir,
        _conflict_kind,
        _expected_baseline_for_turn,
        _load_response,
        _now,
        _record_key,
        _read_authoritative_turn_response,
        _recover_response_publications,
        _merge_recovered_publications,
        _set_baseline_authoritatively,
        _source_path_for_turn_baseline,
        payload_hash,
        read_state,
        session_dir_for,
        turn_dir_for,
        structural_graph_hash,
        write_state_atomic,
    )
    session_dir = session_dir_for(session_root, session_id)
    request_digest = payload_hash(request_payload)
    key = _record_key(scope, idempotency_key)

    with SessionStateLock(session_dir, timeout_seconds=lock_timeout_seconds):
        state = read_state(session_dir)
        recovered_publications = _recover_response_publications(session_dir)
        if _merge_recovered_publications(
            state, recovered_publications, session_dir=session_dir
        ):
            write_state_atomic(session_dir, state)
        turn_dir = turn_dir_for(session_root, session_id, turn_id)
        if turn_dir.is_dir():
            _read_authoritative_turn_response(turn_dir, state=state)
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
                    response = _load_response(
                        existing.get("response_path"),
                        state=state,
                        turn_dir=turn_dir_for(session_root, session_id, turn_id),
                        keyed=True,
                    )
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
        # ── V2 state guards: accept/reject is a V1 operation ──────────────
        # V2 turns must use prepare → finalize (or rollback) instead of the
        # legacy accept/reject endpoints.  This guard fails closed so a V2
        # turn is never accidentally transitioned through a V1 code path.
        if current_state in _V2_TERMINAL_STATES:
            return failure_envelope(
                FailureKind.EDITOR_AHEAD_CONFLICT,
                scope,
                context,
                agent_failure_context={
                    "explanation": (
                        f"Turn {turn_id} is in V2 terminal state {current_state!r} "
                        f"and cannot be {scope}ed."
                    ),
                    "accepted_state": current_state,
                },
            )
        if current_state in _V2_PRE_FINALIZE_STATES:
            return failure_envelope(
                FailureKind.EDITOR_AHEAD_CONFLICT,
                scope,
                context,
                agent_failure_context={
                    "explanation": (
                        f"Turn {turn_id} is in V2 lifecycle state {current_state!r}. "
                        f"Use the V2 prepare / finalize / rollback endpoints instead of {scope}."
                    ),
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
        if scope == "accept" and agent_edit_protocol != "v2_delta":
            legacy_migration = classify_legacy_migration_v1(
                {
                    "contract_version": "candidate_transaction_v1",
                    "state": current_state,
                }
            )
            return failure_envelope(
                FailureKind.EDITOR_AHEAD_CONFLICT,
                scope,
                context,
                agent_failure_context={
                    "explanation": (
                        "Legacy nonterminal authority is nonresumable and cannot be "
                        "promoted to v2 from delta fixture evidence. Rebaseline or cancel it."
                    ),
                    "legacy_migration": legacy_migration,
                },
            )
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
                from vibecomfy.ingest.normalize import detect_workflow_shape
                from vibecomfy.ingest.snapshot import SnapshotAuthorityError

                submit_graph = v2_evidence["submit_graph"]
                live_graph = request_payload["live_graph"]
                if (
                    isinstance(submit_graph, dict)
                    and isinstance(live_graph, dict)
                    and detect_workflow_shape(submit_graph) != detect_workflow_shape(live_graph)
                ):
                    return failure_envelope(
                        FailureKind.STALE_STATE_MISMATCH,
                        scope,
                        context,
                        agent_failure_context={
                            "explanation": "comparison/replay cannot mix raw representations",
                            "code": SnapshotAuthorityError(
                                "mixed_representation",
                                "comparison/replay cannot mix raw representations",
                            ).code,
                            "submit_shape": detect_workflow_shape(submit_graph),
                            "live_shape": detect_workflow_shape(live_graph),
                            "turn_id": turn_id,
                        },
                    )
                scoped_plan = _build_scoped_validation_plan(
                    submit_graph=submit_graph,
                    live_graph=live_graph,
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
        # T3.2 provenance freeze: this accept-response echo is DERIVED, never
        # authoritative. ``_delta_ops_echo`` is reconstructed from the turn's
        # persisted v2 evidence, whose source of truth is the landed
        # accepted_batch; Apply authority stays exclusively with
        # plan.accepted_batch (ops-by-digest). The echo only restates the
        # durable Δ for response consumers and is skipped if one is present.
        if _delta_ops_echo is not None and "accepted_batch" not in response:
            response["accepted_batch"] = [{"op": op} for op in _delta_ops_echo]
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


__all__ = (
    "_mutate_turn_state",
)
