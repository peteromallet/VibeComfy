"""
Chat artifact and narrative payload helpers (T-038 extraction of the edit_chat fragment).

Extracted from the edit.py exec-assembled fragments (T-038, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Imports of sibling _frag modules follow
the foundation dependency order; names that would form an import cycle are
resolved lazily at call time (marked with a T-038 late import comment).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from vibecomfy.comfy_nodes.agent.candidate_transaction import classify_legacy_migration_v1
from vibecomfy.comfy_nodes.agent.contracts import TurnContext, ensure_agent_edit_response_contract
from vibecomfy.comfy_nodes.agent.session import DurableRead, DurableReadError, REVIEWABLE_CANDIDATE_STATES, _read_response_publication, _transaction_receipts_for_turn, load_candidate_transaction_with_migration, load_json_result_impl, project_transaction_state, read_state, session_dir_for
from vibecomfy.porting.edit.types import FieldChange
from ._frag_state import AgentEditState, DEFAULT_CHAT_DISPLAY_MESSAGES, LOGGER, PROMPT_MEMORY_MESSAGES, _ops_from_accepted_batch, _safe_session_id

def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _field_changes_payload(changes: tuple[FieldChange, ...]) -> list[dict[str, Any]]:
    return [change.to_dict() for change in changes]


def _write_turn_chat_artifact(
    state: AgentEditState,
    context: TurnContext,
    response: dict[str, Any],
    contract: str,
) -> None:
    """Best-effort write of ``chat.json`` for an allocated, completed edit turn.

    ``response.json`` is the durable turn artifact; ``chat.json`` is a
    JSON-canonical UI convenience.  Failures here are logged and swallowed.
    """
    turn_dir = state.turn_dir
    chat_path = turn_dir / "chat.json"

    agent_text_raw = response.get("user_facing_message") or response.get("message", "")
    agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
    if not agent_text.strip():
        agent_text = "The agent edit turn completed."

    # Extract structured changes by contract shape.
    changes: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        outcome = response.get("outcome")
        if isinstance(outcome, Mapping):
            raw = outcome.get("changes")
            if isinstance(raw, list):
                changes = [_json_safe(c) for c in raw]
        if changes is None and state.batch_field_changes:
            changes = _field_changes_payload(state.batch_field_changes)
    elif contract == "delta":
        accepted_ops = list(_ops_from_accepted_batch(response))
        if accepted_ops:
            changes = _json_safe(accepted_ops)

    agent_msg: dict[str, Any] = {
        "role": "agent",
        "text": agent_text,
        "turn_id": context.turn_id,
    }
    outcome_payload = response.get("outcome")
    if isinstance(outcome_payload, Mapping):
        agent_msg["outcome"] = dict(outcome_payload)
    if changes is not None:
        agent_msg["changes"] = changes
    change_details = response.get("change_details")
    if isinstance(change_details, Mapping):
        agent_msg["change_details"] = _json_safe(dict(change_details))

    chat_record: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "session_path": str(state.session_dir),
        "turn_path": str(turn_dir),
        "response_path": str(turn_dir / "response.json"),
        "detail_json_path": str(turn_dir / "response.json"),
        "messages": [
            {
                "role": "user",
                "text": state.task,
                "turn_id": context.turn_id,
            },
            agent_msg,
        ],
    }

    # Record narrative artifact paths when present (best-effort, non-failing).
    _narrative_artifact_keys = (
        ("narrative_context_path", "narrative_context"),
        ("narrative_request_path", "narrative_request"),
        ("narrative_response_path", "narrative_response"),
        ("narrative_validation_path", "narrative_validation"),
    )
    _narrative_paths: dict[str, str] = {}
    for _attr_name, _key_name in _narrative_artifact_keys:
        _path = getattr(state, _attr_name, None)
        if isinstance(_path, Path):
            try:
                if _path.is_file():
                    _narrative_paths[_key_name] = str(_path)
            except OSError:
                pass
    if _narrative_paths:
        chat_record["narrative_artifacts"] = _narrative_paths

    try:
        turn_dir.mkdir(parents=True, exist_ok=True)
        chat_path.write_text(
            json.dumps(chat_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning(
            "chat.json write failed for turn %s (best-effort): %s",
            context.turn_id,
            exc,
        )


def _stamped_turn_response_outcome(
    response: Mapping[str, Any] | None,
    *,
    stage: str = "submit",
) -> dict[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(
            dict(response),
            stage=stage,
            compatibility_mode=True,
        )
    except Exception:
        return None
    outcome = stamped.get("outcome")
    return dict(outcome) if isinstance(outcome, Mapping) else None


def _stamped_message_outcome(
    outcome: Mapping[str, Any] | None,
    *,
    stage: str = "chat",
) -> dict[str, Any] | None:
    if not isinstance(outcome, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(
            {"ok": True, "outcome": dict(outcome)},
            stage=stage,
            compatibility_mode=True,
        )
    except Exception:
        return None
    public_outcome = stamped.get("outcome")
    return dict(public_outcome) if isinstance(public_outcome, Mapping) else None


def _read_turn_response_payload(turn_dir: Path) -> dict[str, Any]:
    # response_publication.json is the immutable keyed replay authority. A
    # damaged response.json is only a repairable projection when publication
    # is valid; it must never hide a completed turn from chat reconstruction.
    publication = _read_response_publication(turn_dir)
    if publication is not None:
        return dict(publication["response"])
    response_path = turn_dir / "response.json"
    result = load_json_result_impl(response_path)
    if result.status == "absent":
        return {}
    if result.status != "valid":
        raise DurableReadError(result)
    return dict(result.value)


def _latest_session_candidate_payload(session_dir: Path, turn_ids: list[str]) -> dict[str, Any] | None:
    try:
        state = read_state(session_dir)
    except DurableReadError:
        raise
    except Exception:
        state = {}
    turns_state = state.get("turns") if isinstance(state, Mapping) else {}
    if not isinstance(turns_state, Mapping):
        turns_state = {}
    for turn_id in reversed(turn_ids):
        turn_state = turns_state.get(turn_id)
        if (
            not isinstance(turn_state, Mapping)
            or turn_state.get("state") not in REVIEWABLE_CANDIDATE_STATES
        ):
            continue
        turn_dir = session_dir / "turns" / turn_id
        response = _read_turn_response_payload(turn_dir)
        outcome = _stamped_turn_response_outcome(response, stage="submit")
        if outcome is None or outcome.get("kind") != "candidate":
            continue
        candidate_path = turn_dir / "candidate.ui.json"
        graph = response.get("graph")
        if not isinstance(graph, Mapping) and candidate_path.is_file():
            try:
                graph = json.loads(candidate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                graph = None
        if not isinstance(graph, Mapping):
            continue
        candidate = response.get("candidate")
        eligibility = response.get("apply_eligibility") or response.get("eligibility")
        candidate_fields = candidate if isinstance(candidate, Mapping) else {}
        aggregate = response.get("candidate_transaction")
        legacy_migration = None
        if (
            isinstance(aggregate, Mapping)
            and aggregate.get("contract_version") != "candidate_transaction_v2"
        ):
            legacy_migration = classify_legacy_migration_v1(aggregate)
            aggregate = None
        if not isinstance(aggregate, Mapping):
            plan_hash = turn_state.get("candidate_plan_hash")
            if isinstance(plan_hash, str):
                aggregate, persisted_migration = load_candidate_transaction_with_migration(
                    turn_dir, plan_hash
                )
                if legacy_migration is None:
                    legacy_migration = persisted_migration
        if (
            legacy_migration is None
            and turn_state.get("agent_edit_protocol") != "v2_delta"
        ):
            legacy_migration = classify_legacy_migration_v1(
                {
                    "contract_version": "candidate_transaction_v1",
                    "state": turn_state.get("state"),
                }
            )
        accepted_batch = response.get("accepted_batch")
        if not isinstance(accepted_batch, list):
            accepted_batch = None
        prepared_baseline = None
        if turn_state.get("state") in {"prepared", "apply_prepared"}:
            original_path = turn_dir / "original.ui.json"
            try:
                original_graph = json.loads(original_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                original_graph = None
            if isinstance(original_graph, Mapping):
                # A prepared transaction can outlive the browser page that
                # initiated it. Persisted pre-apply graph authority is needed
                # to distinguish an untouched canvas from a canvas mutated
                # before finalize, and to compensate the latter safely.
                prepared_baseline = {
                    "graph": _json_safe(original_graph),
                    "graph_hash": response.get("submit_graph_hash")
                    or turn_state.get("submit_graph_hash"),
                    "structural_graph_hash": response.get("submit_structural_graph_hash")
                    or turn_state.get("submit_structural_graph_hash"),
                }
        latest_candidate = {
            "turn_id": turn_id,
            "session_id": session_dir.name,
            "baseline_turn_id": response.get("baseline_turn_id"),
            "message": response.get("message"),
            "graph": _json_safe(graph),
            "report": _json_safe(response.get("report")) if isinstance(response.get("report"), Mapping) else None,
            "candidate": _json_safe(candidate) if isinstance(candidate, Mapping) else None,
            "candidate_transaction": (
                _json_safe(aggregate) if isinstance(aggregate, Mapping) else None
            ),
            "legacy_migration": (
                _json_safe(legacy_migration)
                if isinstance(legacy_migration, Mapping)
                else None
            ),
            "turn_state": turn_state.get("state"),
            "agent_edit_protocol": turn_state.get("agent_edit_protocol"),
            "plan_hash": turn_state.get("candidate_plan_hash")
            or candidate_fields.get("plan_hash"),
            "structural_hash_before": turn_state.get("candidate_structural_hash_before")
            or candidate_fields.get("structural_hash_before"),
            "structural_hash_after": turn_state.get("candidate_structural_hash_after")
            or candidate_fields.get("structural_hash_after"),
            "monotonic_generation": (
                aggregate.get("generation") if isinstance(aggregate, Mapping) else None
            ),
            "lease_nonce": (
                aggregate.get("lease_nonce") if isinstance(aggregate, Mapping) else None
            ),
            "accepted_batch": (
                _json_safe(accepted_batch) if accepted_batch is not None else None
            ),
            "apply_eligibility": (
                {
                    "applyable": False,
                    "reason": legacy_migration.get("classification"),
                    "message": "Legacy transaction authority cannot be resumed; rebaseline or cancel it.",
                    "warnings": [],
                }
                if isinstance(legacy_migration, Mapping)
                else (_json_safe(eligibility) if isinstance(eligibility, Mapping) else None)
            ),
            "canvas_apply_allowed": (
                False if isinstance(legacy_migration, Mapping)
                else bool(response.get("canvas_apply_allowed"))
            ),
            "apply_allowed": (
                False if isinstance(legacy_migration, Mapping)
                else response.get("apply_allowed") is not False
            ),
            "queue_allowed": (
                False if isinstance(legacy_migration, Mapping)
                else bool(response.get("queue_allowed"))
            ),
            "candidate_graph_hash": response.get("candidate_graph_hash") or turn_state.get("candidate_graph_hash"),
            "candidate_structural_graph_hash": response.get("candidate_structural_graph_hash") or turn_state.get("candidate_structural_graph_hash"),
            "submit_graph_hash": response.get("submit_graph_hash") or turn_state.get("submit_graph_hash"),
            "submit_structural_graph_hash": response.get("submit_structural_graph_hash") or turn_state.get("submit_structural_graph_hash"),
            "baseline_graph_hash": response.get("baseline_graph_hash") or state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": response.get("baseline_graph_hash_kind") or state.get("baseline_graph_hash_kind"),
            "baseline_graph_hash_version": response.get("baseline_graph_hash_version") or state.get("baseline_graph_hash_version"),
            "prepared_baseline": prepared_baseline,
            "audit_ref": _json_safe(response.get("audit_ref")) if isinstance(response.get("audit_ref"), Mapping) else None,
            "change_details": _json_safe(response.get("change_details")) if isinstance(response.get("change_details"), Mapping) else None,
            "batch_turns": _json_safe(response.get("batch_turns")) if isinstance(response.get("batch_turns"), list) else [],
            "outcome": outcome,
        }
        # Preserve absence for historical candidate responses.  An omitted
        # projection means "this older receipt did not carry dependency
        # authority", whereas an explicit [] means the candidate was resolved
        # with no runtime dependencies.  The browser uses that distinction to
        # avoid erasing same-candidate evidence during automatic rehydrate.
        if isinstance(response.get("runtime_dependencies"), list):
            latest_candidate["runtime_dependencies"] = _json_safe(
                response["runtime_dependencies"]
            )
        return latest_candidate
    return None


def _latest_turn_lifecycle_payload(
    session_dir: Path,
    turn_ids: list[str],
) -> dict[str, Any] | None:
    """Project the latest durable turn state even when no candidate is open.

    ``latest_candidate`` intentionally excludes terminal candidates.  This
    companion projection explains that absence so a reconnecting browser can
    atomically discard stale review state and render the durable disposition.
    Transaction receipts use the same event schema as the reconcile endpoint.
    """
    try:
        state = read_state(session_dir)
    except DurableReadError:
        raise
    except Exception:
        return None
    turns_state = state.get("turns") if isinstance(state, Mapping) else None
    if not isinstance(turns_state, Mapping):
        return None

    disposition_by_state = {
        "prepared": "prepared",
        "apply_prepared": "prepared",
        "finalized": "finalized",
        "rollback_complete": "rolled_back",
        "discarded": "discarded",
        "rejected": "rejected",
        "accepted": "finalized",
    }
    for turn_id in reversed(turn_ids):
        turn = turns_state.get(turn_id)
        if not isinstance(turn, Mapping):
            continue
        turn_state = turn.get("state")
        if turn_state in REVIEWABLE_CANDIDATE_STATES:
            disposition = "reviewable"
        else:
            disposition = disposition_by_state.get(str(turn_state), "other")
        plan_hash = turn.get("candidate_plan_hash")
        aggregate = None
        legacy_migration = None
        if isinstance(plan_hash, str):
            aggregate, legacy_migration = load_candidate_transaction_with_migration(
                session_dir / "turns" / turn_id,
                plan_hash,
            )
        if (
            legacy_migration is None
            and turn.get("agent_edit_protocol") != "v2_delta"
            and isinstance(turn_state, str)
        ):
            legacy_migration = classify_legacy_migration_v1(
                {
                    "contract_version": "candidate_transaction_v1",
                    "state": turn_state,
                }
            )
        receipts = _transaction_receipts_for_turn(
            session_dir / "turns" / turn_id
        )
        if isinstance(aggregate, Mapping) and receipts:
            latest_event = receipts[-1]
            latest_generation = (
                latest_event.get("generation")
                if isinstance(latest_event.get("generation"), int)
                else turn.get("finalized_generation")
                if isinstance(turn.get("finalized_generation"), int)
                else turn.get("prepared_generation")
                if isinstance(turn.get("prepared_generation"), int)
                else None
            )
            latest_lease_nonce = None
            # Terminal receipts do not necessarily repeat the lease at their
            # top level. Recover it from the newest event that carries it, the
            # durable identity fence, or the turn's prepared lease. Rehydrate
            # must project the same transaction identity used by finalize.
            for event in reversed(receipts):
                receipt = event.get("receipt")
                if not isinstance(receipt, Mapping):
                    continue
                direct_nonce = receipt.get("lease_nonce")
                if isinstance(direct_nonce, str) and direct_nonce:
                    latest_lease_nonce = direct_nonce
                    break
                journal = receipt.get("journal_durable")
                identity_fence = (
                    journal.get("identity_fence")
                    if isinstance(journal, Mapping)
                    else None
                )
                fenced_nonce = (
                    identity_fence.get("lease_nonce")
                    if isinstance(identity_fence, Mapping)
                    else None
                )
                if isinstance(fenced_nonce, str) and fenced_nonce:
                    latest_lease_nonce = fenced_nonce
                    break
            if latest_lease_nonce is None:
                prepared_nonce = turn.get("prepared_lease_nonce")
                if isinstance(prepared_nonce, str) and prepared_nonce:
                    latest_lease_nonce = prepared_nonce
            aggregate = project_transaction_state(
                aggregate,
                state=str(latest_event.get("event_type") or aggregate.get("state")),
                generation=latest_generation,
                lease_nonce=latest_lease_nonce,
            )
        return {
            "turn_id": turn_id,
            "state": turn_state if isinstance(turn_state, str) else None,
            "agent_edit_protocol": (
                turn.get("agent_edit_protocol")
                if isinstance(turn.get("agent_edit_protocol"), str)
                else None
            ),
            "candidate_plan_hash": (
                turn.get("candidate_plan_hash")
                if isinstance(turn.get("candidate_plan_hash"), str)
                else None
            ),
            "candidate_graph_hash": (
                turn.get("candidate_graph_hash")
                if isinstance(turn.get("candidate_graph_hash"), str)
                else None
            ),
            "disposition": disposition,
            "candidate_transaction": (
                _json_safe(aggregate) if isinstance(aggregate, Mapping) else None
            ),
            "legacy_migration": (
                _json_safe(legacy_migration)
                if isinstance(legacy_migration, Mapping)
                else None
            ),
            "transaction_receipts": receipts,
        }
    return None


# Bounds for the reasoning trim attached to rehydrated chat messages. The chat
# endpoint is fetched on every page reload, so the embedded reasoning must stay
# lean — keep enough per-step context to diagnose a turn (what the agent tried
# and why the engine rejected it) without shipping the full diff/statements.
_CHAT_REASONING_MAX_STEPS = 12
_CHAT_REASONING_MAX_DIAGS = 4
_CHAT_REASONING_MAX_OPERATIONS = 8


def _trim_chat_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _compact_chat_change_details(change_details: Any) -> dict[str, Any] | None:
    """Trim a turn's ``change_details`` to the reasoning the panel report needs.

    The full ``change_details`` carries per-step diffs, statements, and provider
    metadata that bloat the chat-rehydrate payload. The diagnostic report only
    consumes the agent's per-step ``message`` / ``batch`` and the engine
    ``diagnostics`` (which carry the root data — valid enum ``choices`` and
    ``available_slots``), plus the change summary. Keep just those.
    """
    if not isinstance(change_details, dict):
        return None
    compact: dict[str, Any] = {}

    summary = _trim_chat_text(
        change_details.get("done_summary") or change_details.get("final_summary"),
        400,
    )
    if summary is not None:
        compact["done_summary"] = summary
    if isinstance(change_details.get("landed_operation_count"), int):
        compact["landed_operation_count"] = change_details["landed_operation_count"]

    operations = change_details.get("operations")
    if isinstance(operations, list) and operations:
        trimmed_ops = []
        for op in operations[:_CHAT_REASONING_MAX_OPERATIONS]:
            if not isinstance(op, dict):
                continue
            entry = {}
            op_summary = _trim_chat_text(op.get("summary"), 160)
            if op_summary is not None:
                entry["summary"] = op_summary
            field_path = _trim_chat_text(op.get("field_path"), 160)
            if field_path is not None:
                entry["field_path"] = field_path
            if entry:
                trimmed_ops.append(entry)
        if trimmed_ops:
            compact["operations"] = trimmed_ops

    batch_turns = change_details.get("batch_turns")
    if isinstance(batch_turns, list) and batch_turns:
        trimmed_steps = []
        for step in batch_turns[:_CHAT_REASONING_MAX_STEPS]:
            if not isinstance(step, dict):
                continue
            trimmed: dict[str, Any] = {}
            if isinstance(step.get("turn_number"), int):
                trimmed["turn_number"] = step["turn_number"]
            if isinstance(step.get("batch_ok"), bool):
                trimmed["batch_ok"] = step["batch_ok"]
            if isinstance(step.get("landed_op_count"), int):
                trimmed["landed_op_count"] = step["landed_op_count"]
            message = _trim_chat_text(step.get("message"), 500)
            if message is not None:
                trimmed["message"] = message
            batch = _trim_chat_text(step.get("batch"), 400)
            if batch is not None:
                trimmed["batch"] = batch
            diagnostics = step.get("diagnostics")
            if isinstance(diagnostics, list) and diagnostics:
                trimmed_diags = []
                for diag in diagnostics[:_CHAT_REASONING_MAX_DIAGS]:
                    if not isinstance(diag, dict):
                        continue
                    diag_entry: dict[str, Any] = {}
                    for key in ("code", "severity"):
                        if isinstance(diag.get(key), str):
                            diag_entry[key] = diag[key]
                    diag_message = _trim_chat_text(diag.get("message"), 300)
                    if diag_message is not None:
                        diag_entry["message"] = diag_message
                    detail = diag.get("detail")
                    if isinstance(detail, dict):
                        detail_entry = {}
                        for key in ("input", "value", "slot", "class_type", "name"):
                            if isinstance(detail.get(key), (str, int, float, bool)):
                                detail_entry[key] = detail[key]
                        for key in ("choices", "available_slots"):
                            values = detail.get(key)
                            if isinstance(values, list):
                                detail_entry[key] = [v for v in values[:24] if isinstance(v, (str, int, float))]
                        if detail_entry:
                            diag_entry["detail"] = detail_entry
                    if diag_entry:
                        trimmed_diags.append(diag_entry)
                if trimmed_diags:
                    trimmed["diagnostics"] = trimmed_diags
            if trimmed:
                trimmed_steps.append(trimmed)
        if trimmed_steps:
            compact["batch_turns"] = trimmed_steps

    return compact or None


def _conversation_with_candidate_reference(
    messages: list[dict[str, Any]] | None,
    latest_candidate: Any,
) -> list[dict[str, Any]] | None:
    """Append compact latest-candidate context for follow-up references."""
    if not isinstance(messages, list):
        return messages
    if not isinstance(latest_candidate, Mapping):
        return messages
    parts: list[str] = []
    turn_id = latest_candidate.get("turn_id")
    if isinstance(turn_id, str) and turn_id:
        parts.append(f"turn={turn_id}")
    outcome = latest_candidate.get("outcome")
    if isinstance(outcome, Mapping) and isinstance(outcome.get("kind"), str):
        parts.append(f"outcome={outcome['kind']}")
    change_details = latest_candidate.get("change_details")
    operations = (
        change_details.get("operations")
        if isinstance(change_details, Mapping)
        else None
    )
    if isinstance(operations, list) and operations:
        summaries = []
        for op in operations[:4]:
            if isinstance(op, Mapping):
                summary = op.get("summary") or op.get("field_path")
                if isinstance(summary, str) and summary.strip():
                    summaries.append(summary.strip()[:120])
        if summaries:
            parts.append("changes=" + "; ".join(summaries))
    if not parts:
        return messages
    augmented = list(messages)
    augmented.append(
        {
            "role": "agent",
            "text": "Latest candidate reference (for resolving follow-up terms like "
            f"'that one'): {', '.join(parts)}",
        }
    )
    return augmented[-PROMPT_MEMORY_MESSAGES:]


def read_session_chat(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = DEFAULT_CHAT_DISPLAY_MESSAGES,
) -> dict[str, Any]:
    """Read conversation history for a session from persisted turn artifacts.

    Scans turn directories under the session root in deterministic order,
    reads ``chat.json`` where present, falls back to same-turn
    ``request.json`` + ``response.json``, and returns a bounded display
    history with session metadata.

    Returns:
        dict with keys: ``ok``, ``session_id``, ``session_path``,
        ``latest_turn_id``, ``detail_json_path``, ``messages``.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    turns_dir = session_dir / "turns"

    session_exists = session_dir.is_dir()
    try:
        session_state = read_state(session_dir) if session_exists else {}
    except DurableReadError:
        raise
    except Exception:
        session_state = {}
    baseline_payload = {
        "baseline_turn_id": session_state.get("baseline_turn_id"),
        "baseline_graph_hash": session_state.get("baseline_graph_hash"),
        "baseline_graph_hash_kind": session_state.get("baseline_graph_hash_kind"),
        "baseline_graph_hash_version": session_state.get("baseline_graph_hash_version"),
        "baseline_source": session_state.get("baseline_source"),
        "baseline_rebaseline_id": session_state.get("baseline_rebaseline_id"),
        "baseline_graph_source_path": session_state.get("baseline_graph_source_path"),
    }
    if not turns_dir.is_dir():
        return {
            "ok": True,
            "exists": session_exists,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "session_path_resolved": str(session_dir.resolve()),
            "latest_turn_id": None,
            "detail_json_path": None,
            "detail_json_path_resolved": None,
            "messages": [],
            "latest_candidate": None,
            "latest_turn_lifecycle": None,
            "pipeline_mode": "staged",
            **baseline_payload,
        }

    # Sort turn directories deterministically (zero-padded integers).
    try:
        turn_ids: list[str] = sorted(
            [d.name for d in turns_dir.iterdir() if d.is_dir()],
        )
    except (OSError, UnicodeError) as exc:
        raise DurableReadError(
            DurableRead("unreadable", path=turns_dir, error=str(exc))
        ) from exc

    all_messages: list[dict[str, Any]] = []
    latest_turn_id: str | None = None
    latest_pipeline_mode: str | None = None

    for turn_id in turn_ids:
        turn_dir = turns_dir / turn_id
        chat_path = turn_dir / "chat.json"
        chat_record: dict[str, Any] | None = None
        response = _read_turn_response_payload(turn_dir)
        fallback_agent_outcome = _stamped_turn_response_outcome(response, stage="submit")
        request_path = turn_dir / "request.json"
        request_metadata: dict[str, Any] | None = None
        if request_path.is_file():
            try:
                parsed_request_metadata = json.loads(request_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                parsed_request_metadata = None
            if isinstance(parsed_request_metadata, dict):
                request_metadata = parsed_request_metadata

        # Try chat.json first.
        if chat_path.is_file():
            try:
                chat_record = json.loads(chat_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        # Fall back to request.json + response.json.
        if chat_record is None:
            request_path = turn_dir / "request.json"
            response_path = turn_dir / "response.json"
            if request_path.is_file() and (
                response_path.is_file()
                or (turn_dir / "response_publication.json").is_file()
                or response
            ):
                try:
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise DurableReadError(
                        DurableRead(
                            "corrupt" if isinstance(exc, json.JSONDecodeError) else "unreadable",
                            path=request_path,
                            error=str(exc),
                        )
                    ) from exc
                if not isinstance(request, Mapping):
                    raise DurableReadError(
                        DurableRead("corrupt", path=request_path, error="request must be a JSON object")
                    )
                agent_text_raw = response.get("user_facing_message") or response.get("message", "")
                agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
                if not agent_text.strip():
                    agent_text = "The agent edit turn completed."
                chat_record = {
                    "session_id": safe_id,
                    "turn_id": turn_id,
                    "session_path": str(session_dir),
                    "turn_path": str(turn_dir),
                    "response_path": str(response_path),
                    "detail_json_path": str(response_path),
                    "messages": [
                        {
                            "role": "user",
                            "text": request.get("task", ""),
                            "turn_id": turn_id,
                        },
                        {
                            "role": "agent",
                            "text": agent_text,
                            "turn_id": turn_id,
                        },
                    ],
                }
                if fallback_agent_outcome is not None:
                    chat_record["messages"][1]["outcome"] = fallback_agent_outcome

        if chat_record is None:
            continue

        # Only an accepted, displayable turn may advance the recovered mode.
        # A partially allocated newer turn can have request.json without a
        # response/chat artifact; it must not override the last completed turn
        # while the panel is rehydrating.
        raw_pipeline_mode = (
            request_metadata.get("pipeline_mode") if request_metadata is not None else None
        )
        try:
            from vibecomfy.executor.contracts import coerce_orchestration_mode

            # An omitted mode is the legacy staged default. Invalid persisted
            # values fail closed at the public boundary.
            latest_pipeline_mode = (
                coerce_orchestration_mode(raw_pipeline_mode)
                if raw_pipeline_mode is not None
                else "staged"
            )
        except ValueError:
            latest_pipeline_mode = "staged"

        # Best-effort wall-clock for this turn, used by the panel to show a
        # relative timestamp ("5 minutes ago") below each chat bubble. Turn
        # artifacts carry no explicit timestamp, so the turn directory's mtime
        # is the most faithful proxy for when the exchange landed.
        try:
            turn_ts = datetime.fromtimestamp(
                turn_dir.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            turn_ts = None

        # Extract display messages from the chat record.
        # Defensively skip malformed entries (non-dict, missing role,
        # non-string text) so a corrupt chat.json in one turn cannot
        # poison the entire session history read.
        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if role not in ("user", "agent"):
                    continue
                text = msg.get("text", "")
                if not isinstance(text, str):
                    text = str(text) if text is not None else ""
                display_msg = {
                    "role": role,
                    "text": text,
                    "turn_id": msg.get("turn_id", turn_id),
                }
                if turn_ts is not None:
                    display_msg["timestamp"] = turn_ts
                stamped_outcome = _stamped_message_outcome(msg.get("outcome"))
                if role == "agent" and stamped_outcome is None:
                    stamped_outcome = fallback_agent_outcome
                if role == "agent" and stamped_outcome is not None:
                    display_msg["outcome"] = stamped_outcome
                if role == "agent":
                    # Carry a trimmed view of the agent's per-step reasoning so a
                    # reloaded panel's diagnostic report can show what the agent
                    # tried and why the engine rejected it (the on-disk
                    # change_details is otherwise unreachable after reload).
                    reasoning = _compact_chat_change_details(msg.get("change_details"))
                    if reasoning is not None:
                        display_msg["change_details"] = reasoning
                all_messages.append(display_msg)
        latest_turn_id = turn_id

    # Take the last N messages for display.
    display_messages = all_messages[-max_messages:] if max_messages > 0 else all_messages

    return {
        "ok": True,
        "exists": True,
        "session_id": safe_id,
        "session_path": str(session_dir),
        "session_path_resolved": str(session_dir.resolve()),
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "detail_json_path_resolved": (
            str((turns_dir / latest_turn_id / "response.json").resolve())
            if latest_turn_id
            else None
        ),
        "messages": display_messages,
        "latest_candidate": _latest_session_candidate_payload(session_dir, turn_ids),
        "latest_turn_lifecycle": _latest_turn_lifecycle_payload(session_dir, turn_ids),
        "pipeline_mode": latest_pipeline_mode or "staged",
        **baseline_payload,
    }


# Suffixes treated as UTF-8 text in the downloadable session bundle; everything
# else is base64-encoded so binary artifacts (PNG previews, etc.) survive.
_BUNDLE_TEXT_SUFFIXES = frozenset(
    {".json", ".jsonl", ".py", ".txt", ".md", ".log", ".csv", ".yaml", ".yml", ".diff", ".html"}
)
_BUNDLE_MAX_FILE_BYTES = 8 * 1024 * 1024  # 8 MiB per file
_BUNDLE_MAX_TOTAL_BYTES = 64 * 1024 * 1024  # 64 MiB per bundle


__all__ = (
     "_BUNDLE_MAX_FILE_BYTES", "_BUNDLE_MAX_TOTAL_BYTES", "_BUNDLE_TEXT_SUFFIXES",
     "_CHAT_REASONING_MAX_DIAGS", "_CHAT_REASONING_MAX_OPERATIONS",
     "_CHAT_REASONING_MAX_STEPS", "_compact_chat_change_details",
     "_conversation_with_candidate_reference", "_field_changes_payload", "_json_safe",
     "_latest_session_candidate_payload", "_latest_turn_lifecycle_payload",
     "_read_turn_response_payload", "_stamped_message_outcome",
     "_stamped_turn_response_outcome", "_trim_chat_text", "_write_turn_chat_artifact",
     "read_session_chat",
)
