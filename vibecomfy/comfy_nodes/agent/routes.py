from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

_LOGGER = logging.getLogger(__name__)

from .audit import artifact_ref_for_path, write_audit, write_json_artifact
from .edit import DEFAULT_CHAT_DISPLAY_MESSAGES, _SESSION_ROOT, _write_turn_chat_artifact as _edit_write_turn_chat_artifact
from .contracts import (
    AgentError,
    ApplyEligibility,
    FailureKind,
    ProviderStatus,
    TurnContext,
    build_legacy_agent_edit_v1,
    classify_failure,
    ensure_agent_edit_response_contract,
    failure_envelope,
    product_failure_envelope_fields,
)
from .provider import readiness, handle_credential_submission
from .hivemind_feedback import submit_hivemind_feedback
from .session import (
    accept_turn as _session_accept_turn,
    allocate_turn as _session_allocate_turn,
    rebaseline_session as _session_rebaseline_session,
    record_idempotent_response as _session_record_idempotent_response,
    reject_turn as _session_reject_turn,
    session_dir_for,
    turn_dir_for,
)


def handle_agent_edit(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .edit import handle_agent_edit as _handle_agent_edit_impl  # noqa: PLC0415

    return _handle_agent_edit_impl(*args, **kwargs)


def read_session_chat(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .edit import read_session_chat as _read_session_chat_impl  # noqa: PLC0415

    return _read_session_chat_impl(*args, **kwargs)


def accept_turn(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _session_accept_turn(*args, **kwargs)


def reject_turn(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _session_reject_turn(*args, **kwargs)


def rebaseline_session(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _session_rebaseline_session(*args, **kwargs)


def _handle_roundtrip(
    payload: dict[str, Any], *, schema_provider: Any = None
) -> dict[str, Any]:
    """Torch-free core: convert UI graph + emit, return enriched graph + change report.

    All engine imports are lazy so this function is importable without ComfyUI or torch.
    Call from tests directly; the aiohttp wrapper below delegates to this.
    """
    from vibecomfy.ingest.normalize import convert_to_vibe_format  # noqa: PLC0415
    from vibecomfy.porting.layout import evaluate_felt_delta  # noqa: PLC0415
    from vibecomfy.porting.emit.ui import emit_ui_json  # noqa: PLC0415
    from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

    try:
        if schema_provider is None:
            schema_provider = get_schema_provider("local")
        recovery_report: list = []
        change_report_out: list = []
        wf = convert_to_vibe_format(payload["graph"])
        emitted_ui = emit_ui_json(
            wf,
            schema_provider=schema_provider,
            recovery_report=recovery_report,
            change_report_out=change_report_out,
            guard_original_ui=payload["graph"],
        )
        change_dict = dataclasses.asdict(change_report_out[0]) if change_report_out else {}
        reroute_uids = frozenset(
            (node.uid or node_id)
            for node_id, node in wf.nodes.items()
            if node.class_type == "Reroute"
        )
        felt_report = (
            evaluate_felt_delta(
                None,
                emitted_ui,
                change_report_out[0],
                reroute_uids=reroute_uids,
            )
            if change_report_out
            else None
        )
        return {
            "graph": emitted_ui,
            "report": {
                "change": change_dict,
                "recovery": recovery_report,
                "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
            },
            "version": 1,
        }
    except Exception as exc:
        return {"error": str(exc), "kind": type(exc).__name__}


def _handle_agent_status(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    route = params.get("route") if isinstance(params.get("route"), str) else None
    model = params.get("model") if isinstance(params.get("model"), str) else None
    _LOGGER.info("/vibecomfy/agent/status request route=%r model=%r", route, model)
    try:
        ready_payload = readiness(route=route, model=model)
    except Exception as exc:
        _LOGGER.exception("/vibecomfy/agent/status readiness() raised an exception")
        raise
    ok = bool(ready_payload.get("ready"))
    raw_provider_error = _provider_status_raw_error(ready_payload)
    user_message = _provider_status_message(
        ready=ok,
        provider_available=bool(ready_payload.get("provider_available")),
        raw_error=raw_provider_error,
        reason=ready_payload.get("reason"),
    )
    provider_status = ProviderStatus(
        provider=str(ready_payload.get("provider") or "arnold"),
        provider_available=bool(ready_payload.get("provider_available")),
        ready=ok,
        model=ready_payload.get("model") if isinstance(ready_payload.get("model"), str) else None,
        route=ready_payload.get("route") if isinstance(ready_payload.get("route"), str) else None,
        message=user_message,
        error=(
            {
                "message": user_message,
                "type": "provider_unavailable",
            }
            if not ok and not ready_payload.get("provider_available")
            else None
        ),
    )
    status: dict[str, Any] = {
        **ready_payload,
        **provider_status.to_dict(),
        "ok": ok,
        "readiness": "ready" if ok else "unavailable",
    }
    if not ok:
        status["reason"] = user_message
        status["message"] = user_message
    if raw_provider_error is not None:
        debug = dict(status.get("debug")) if isinstance(status.get("debug"), Mapping) else {}
        provider_debug = dict(debug.get("provider_status")) if isinstance(debug.get("provider_status"), Mapping) else {}
        provider_debug["raw_error"] = raw_provider_error
        debug["provider_status"] = provider_debug
        status["debug"] = debug
    _LOGGER.info(
        "/vibecomfy/agent/status response ready=%s route=%s requested_route=%s route_options=%s",
        status.get("ready"),
        status.get("route"),
        status.get("requested_route"),
        list(status.get("route_options", {}).keys()),
    )
    return status


def _provider_status_raw_error(payload: Mapping[str, Any]) -> str | None:
    for key in ("error", "reason", "detail", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _provider_status_message(
    *,
    ready: bool,
    provider_available: bool,
    raw_error: str | None,
    reason: Any,
) -> str:
    if ready:
        return "Provider ready."
    if not provider_available:
        return "The model provider is unavailable. Check local provider configuration."
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if raw_error:
        return "The model provider is not ready."
    return "The model provider is not ready."


def _agent_error_response(failure: AgentError) -> dict[str, Any]:
    response = failure.to_dict()
    response.update(product_failure_envelope_fields(failure))
    return response


def _handle_agent_edit(
    payload: Any,
    *,
    schema_provider: Any = None,
    deepseek_client: Any = None,
    session_root: Any = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    try:
        result = handle_agent_edit(
            payload,
            schema_provider=schema_provider,
            deepseek_client=deepseek_client,
            session_root=Path(session_root) if session_root is not None else None,
            client_id=client_id,
        )
    except Exception as exc:
        return _agent_error_response(classify_failure("route", exc))
    if isinstance(result, dict):
        return _sanitize_clarify_payload(result)
    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "route",
        agent_failure_context={"explanation": "handle_agent_edit returned a non-dict result."},
    )
    return _agent_error_response(failure)


def _executor_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    request_payload = dict(payload)
    if "query" not in request_payload and isinstance(request_payload.get("task"), str):
        request_payload["query"] = request_payload["task"]
    return request_payload


def _executor_compatibility_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build legacy compatibility fields from a canonical executor envelope.

    Durable ``outcome`` and ``apply_eligibility`` from the edit engine are
    preserved as-is when present; compatibility synthesis runs only as a
    fallback for executors that produce results without durable metadata
    (SD2: applyable == durable).
    """
    reply = payload.get("reply")
    message = reply if isinstance(reply, str) else ""
    route = payload.get("route") if isinstance(payload.get("route"), str) else "respond"
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), Mapping) else None
    candidate_graph = (
        candidate.get("graph")
        if isinstance(candidate, Mapping) and isinstance(candidate.get("graph"), dict)
        else None
    )
    apply_eligible = bool(payload.get("apply_eligible"))

    # ── Prefer durable envelope fields over synthesized compatibility ──
    has_durable_outcome = isinstance(payload.get("outcome"), Mapping)
    has_durable_apply_eligibility = isinstance(payload.get("apply_eligibility"), Mapping)
    has_durable_graph = isinstance(payload.get("graph"), dict)

    compatibility: dict[str, Any] = {
        "message": message,
    }

    # Only synthesize outcome when the durable envelope doesn't provide one.
    if not has_durable_outcome:
        if candidate_graph is not None and apply_eligible:
            outcome = {"kind": "candidate", "changes": []}
        elif route == "clarify":
            outcome = {
                "kind": "clarify",
                "question": message,
                "clarification": {"message": message},
            }
        else:
            reason = payload.get("no_candidate_reason")
            outcome = {
                "kind": "noop",
                "reason": str(reason) if isinstance(reason, str) and reason else message,
            }
        compatibility["outcome"] = outcome

    # Only synthesize apply_eligibility when the durable envelope
    # doesn't provide one.
    if not has_durable_apply_eligibility:
        compatibility["apply_eligibility"] = {
            "applyable": apply_eligible,
            "reason": "applyable" if apply_eligible else "no_candidate",
            "message": (
                "Ready to apply." if apply_eligible
                else "No candidate is available to apply."
            ),
            "warnings": [],
        }

    compatibility["eligibility"] = compatibility.get("apply_eligibility") or payload.get("eligibility")
    if not isinstance(compatibility.get("eligibility"), Mapping):
        compatibility["eligibility"] = {
            "applyable": apply_eligible,
            "reason": "applyable" if apply_eligible else "no_candidate",
            "message": (
                "Ready to apply." if apply_eligible
                else "No candidate is available to apply."
            ),
            "warnings": [],
        }

    # Only add graph when durable graph is not already present.
    if candidate_graph is not None and not has_durable_graph:
        compatibility["graph"] = candidate_graph
    compatibility = build_legacy_agent_edit_v1(
        {
            **compatibility,
            "candidate": candidate,
            "canvas_apply_allowed": apply_eligible,
            "queue_allowed": apply_eligible,
        }
    )

    if route == "clarify":
        compatibility["clarification_required"] = True
        compatibility["clarification_message"] = message
    return compatibility


_NON_APPLYABLE_FORBIDDEN_KEYS = {
    "candidate",
    "graph",
    "candidate_graph",
    "apply_eligible",
    "apply_eligibility",
    "eligibility",
    "apply_allowed",
    "canvas_apply_allowed",
    "queue_allowed",
}

# Legacy alias — kept for callers that reference the old name.
_CLARIFY_FORBIDDEN_KEYS = _NON_APPLYABLE_FORBIDDEN_KEYS


def _format_clarify_markdown(message: Any) -> str:
    text = message.strip() if isinstance(message, str) else ""
    if not text:
        text = "What detail should I use before continuing?"
    return text


def _strip_non_applyable_forbidden_fields(value: Any) -> Any:
    """Strip candidate/apply/eligibility fields from non-applyable route envelopes."""
    if isinstance(value, dict):
        stripped: dict[str, Any] = {}
        for key, item in value.items():
            if key in _NON_APPLYABLE_FORBIDDEN_KEYS or key.startswith("candidate_"):
                continue
            stripped[key] = _strip_non_applyable_forbidden_fields(item)
        return stripped
    if isinstance(value, list):
        return [_strip_non_applyable_forbidden_fields(item) for item in value]
    return value


# Legacy alias kept for callers that reference the old name.
_strip_clarify_forbidden_fields = _strip_non_applyable_forbidden_fields


def _sanitize_clarify_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = dict(payload)
    outcome = sanitized.get("outcome")
    route = sanitized.get("route")
    is_clarify = (
        route == "clarify"
        or (
            isinstance(outcome, Mapping)
            and outcome.get("kind") == "clarify"
        )
    )
    if not is_clarify:
        return sanitized

    message = (
        sanitized.get("reply")
        or sanitized.get("message")
        or (outcome.get("question") if isinstance(outcome, Mapping) else "")
    )
    markdown = _format_clarify_markdown(message)
    if "reply" in sanitized:
        sanitized["reply"] = markdown
    sanitized["message"] = markdown
    sanitized["clarification_required"] = True
    sanitized["clarification_message"] = markdown
    sanitized["outcome"] = {
        "kind": "clarify",
        "question": markdown,
        "clarification": {"message": markdown},
    }
    internal_outcome = sanitized.get("internal_outcome")
    if isinstance(internal_outcome, Mapping) and internal_outcome.get("kind") == "clarify":
        sanitized["internal_outcome"] = {"kind": "clarify", "question": markdown}
    return _strip_non_applyable_forbidden_fields(sanitized)


_NON_APPLYABLE_ROUTES = frozenset({"clarify", "respond", "inspect", "research"})


def _serialize_executor_result(result: Any) -> dict[str, Any]:
    """Serialise an executor result, preferring durable envelope fields.

    Compatibility fields are layered under durable fields so the canonical
    edit-envelope shape (``session_id``, ``turn_id``, ``outcome``,
    ``apply_eligibility``, etc.) always wins.  Non-applyable routes
    (clarify/respond/inspect/research) have candidate/apply fields stripped;
    clarify routes additionally receive clarification-specific formatting.
    """
    serialized = _to_serializable(result)
    if not isinstance(serialized, dict):
        serialized = {"ok": False, "error": "Non-dict executor result."}
    compatibility = _executor_compatibility_fields(serialized)
    # Durable fields (serialized) overwrite synthesized compatibility fields.
    merged = {**compatibility, **serialized}
    route = merged.get("route") if isinstance(merged.get("route"), str) else ""
    outcome = merged.get("outcome")
    is_clarify = (
        route == "clarify"
        or (isinstance(outcome, Mapping) and outcome.get("kind") == "clarify")
    )
    # Non-applyable routes: strip candidate/apply/eligibility fields.
    if route in _NON_APPLYABLE_ROUTES:
        merged = _strip_non_applyable_forbidden_fields(merged)
    # Clarify routes: apply clarify-specific formatting.
    if is_clarify:
        merged = _sanitize_clarify_payload(merged)
    return merged


def _handle_agent_executor_submit(
    payload: Any,
    *,
    client_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    from vibecomfy.executor.contracts import ExecutorRequest  # noqa: PLC0415
    from vibecomfy.executor.core import run_executor  # noqa: PLC0415

    if not isinstance(payload, dict):
        failure = _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "agent_executor",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
        return _validated_failure_response("agent_executor", failure), 400
    try:
        request = ExecutorRequest.from_payload(_executor_request_payload(payload))
    except Exception as exc:
        failure = _agent_error_response(classify_failure("agent_executor", exc))
        return _validated_failure_response("agent_executor", failure), 400
    result = run_executor(request, client_id=client_id)
    response = _serialize_executor_result(result)
    # T7/T9: Durable turn writer for executor-only non-applyable turns
    # (clarify/inspect/respond/research).  When the executor skips implementation,
    # no durable response is produced by handle_agent_edit.  Allocate a lightweight
    # turn and write request/response/chat artifacts so the frontend can rehydrate
    # from canonical durable storage (SD1, SD2).
    response = _maybe_write_executor_only_durable_turn(
        response=response,
        result=result,
        payload=payload,
        request=request,
    )
    status = 200 if response.get("ok") is not False else 500
    return response, status


# ── T7: Lightweight durable executor-only turn writer ──────────────────────────

# Routes for which the executor skips the implement phase entirely.  These
# turns still need durable session/turn/artifact bookkeeping so the UI can
# rehydrate from canonical storage (SD1: backend is the source of truth).
_EXECUTOR_ONLY_NON_APPLYABLE_ROUTES = frozenset({"clarify", "inspect", "respond", "research"})


def _maybe_write_executor_only_durable_turn(
    *,
    response: dict[str, Any],
    result: Any,
    payload: dict[str, Any],
    request: Any,
) -> dict[str, Any]:
    """Allocate a durable turn and write artifacts for executor-only non-applyable turns.

    Returns the *response* unchanged (or enriched with durable metadata) when
    the executor result already carries a ``durable_response`` from
    ``handle_agent_edit`` (revise/adapt routes).  For clarify/inspect/respond/
    research the executor skips the implement phase entirely, so this function
    provides the missing durable bookkeeping.
    """
    # ── Guard: only act when durable metadata is missing and the route is non-applyable ──
    route = response.get("route") if isinstance(response.get("route"), str) else ""
    if route not in _EXECUTOR_ONLY_NON_APPLYABLE_ROUTES:
        # revise/adapt — handle_agent_edit already wrote durable artifacts
        return response

    has_durable_session_id = isinstance(response.get("session_id"), str) and response["session_id"].strip()
    has_durable_turn_id = isinstance(response.get("turn_id"), str) and response["turn_id"].strip()
    if has_durable_session_id and has_durable_turn_id:
        # Already has durable metadata from a prior allocation (e.g. idempotency replay)
        return response

    # ── Only allocate a turn when the executor succeeded ──
    if response.get("ok") is False:
        return response

    session_id_raw = payload.get("session_id")
    session_id = (
        session_id_raw.strip()
        if isinstance(session_id_raw, str) and session_id_raw.strip()
        else uuid.uuid4().hex
    )

    session_root = _SESSION_ROOT
    idempotency_key = payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None

    try:
        # Build a compact request-payload representation for the artifact.
        query_text_raw = getattr(request, "query", "") or payload.get("query") or payload.get("task") or ""
        query_text = query_text_raw if isinstance(query_text_raw, str) else ""
        request_artifact_payload: dict[str, Any] = {
            "query": query_text,
            "task": query_text,
            "session_id": session_id,
        }
        if hasattr(request, "graph") and request.graph is not None:
            request_artifact_payload["graph"] = dict(request.graph) if isinstance(request.graph, dict) else request.graph

        allocation = _session_allocate_turn(
            session_root=session_root,
            session_id=session_id,
            request_payload=request_artifact_payload,
            idempotency_key=idempotency_key,
        )

        if allocation.replay is not None:
            # A prior idempotent response already exists — return it.
            return dict(allocation.replay.response)
        if allocation.conflict is not None:
            # Idempotency conflict — don't overwrite; return original response.
            return response

        context = allocation.context
        turn_dir = allocation.turn_dir

        # ── Write request.json ──
        write_json_artifact(turn_dir / "request.json", request_artifact_payload)

        # ── Stamp durable metadata on the response ──
        response_path = turn_dir / "response.json"
        stamped = dict(response)
        stamped["session_id"] = context.session_id
        stamped["turn_id"] = context.turn_id
        stamped["session_path"] = str(session_dir_for(session_root, context.session_id))
        stamped["session_path_resolved"] = str(session_dir_for(session_root, context.session_id).resolve())
        stamped["detail_json_path"] = str(response_path)
        stamped["detail_json_path_resolved"] = str(response_path.resolve())
        stamped["query"] = query_text
        stamped["task"] = query_text
        if context.baseline_turn_id is not None:
            stamped["baseline_turn_id"] = context.baseline_turn_id

        baseline_state = allocation.state
        baseline_graph_hash = baseline_state.get("baseline_graph_hash") if isinstance(baseline_state, dict) else None
        if isinstance(baseline_graph_hash, str):
            stamped["baseline_graph_hash"] = baseline_graph_hash

        # ── Non-applyable: no candidate, graph unchanged, clear reason ──
        stamped["eligibility"] = {
            "applyable": False,
            "reason": "no_candidate",
            "message": "No candidate is available to apply.",
            "warnings": [],
        }
        stamped["apply_eligible"] = False
        stamped["graph_unchanged"] = True
        stamped["no_candidate_reason"] = "route_not_applyable"

        outcome = stamped.get("outcome")
        if not isinstance(outcome, dict):
            # Synthesise a noop or clarify outcome based on route
            if route == "clarify":
                reply_text = stamped.get("reply") or stamped.get("message") or ""
                stamped["outcome"] = {
                    "kind": "clarify",
                    "question": reply_text if isinstance(reply_text, str) else "",
                    "clarification": {"message": reply_text if isinstance(reply_text, str) else ""},
                }
            else:
                stamped["outcome"] = {
                    "kind": "noop",
                    "reason": "Executor-only non-applyable turn.",
                }

        if route == "clarify":
            stamped = _sanitize_clarify_payload(stamped)
        else:
            stamped = build_legacy_agent_edit_v1(
                {
                    **stamped,
                    "canvas_apply_allowed": False,
                    "queue_allowed": False,
                }
            )

        # ── Write response.json ──
        write_json_artifact(response_path, stamped)

        # ── Write chat.json (lightweight) ──
        _write_executor_only_chat_artifact(
            turn_dir=turn_dir,
            context=context,
            response=stamped,
            route=route,
        )

        # ── Record idempotent response ──
        _session_record_idempotent_response(
            session_root=session_root,
            session_id=session_id,
            scope="edit",
            idempotency_key=idempotency_key,
            request_hash=allocation.request_hash,
            response=stamped,
            response_path=response_path,
            operation="edit",
            turn_id=context.turn_id,
        )

        return stamped
    except Exception:
        # Best-effort: durable turn writing failures must not break the
        # executor response path.  Log and return the original response.
        _LOGGER.warning(
            "Executor-only durable turn write failed for session=%s route=%s (best-effort)",
            session_id,
            route,
            exc_info=True,
        )
        return response


def _write_executor_only_chat_artifact(
    *,
    turn_dir: Path,
    context: Any,
    response: dict[str, Any],
    route: str,
) -> None:
    """Best-effort write of ``chat.json`` for an executor-only non-applyable turn.

    Follows the same shape as ``_write_turn_chat_artifact`` in ``edit.py``
    so ``read_session_chat`` can consume executor-only turns uniformly.

    For ``research`` and ``respond`` routes, includes bounded evidence
    (research summary/sources) and route metadata alongside chronological
    chat history.  Candidate, apply, hash, and rebaseline metadata are
    intentionally omitted for non-applyable routes.
    """
    agent_text_raw = response.get("reply") or response.get("message") or ""
    agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
    if not agent_text.strip():
        agent_text = "The agent inspected the graph and replied."

    user_query = response.get("query") or response.get("task") or ""
    if not isinstance(user_query, str):
        user_query = ""

    outcome_payload = response.get("outcome")
    agent_msg: dict[str, Any] = {
        "role": "agent",
        "text": agent_text,
        "turn_id": context.turn_id,
        "session_id": context.session_id,
    }
    if isinstance(outcome_payload, dict):
        agent_msg["outcome"] = dict(outcome_payload)

    chat_record: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "route": route,
        "session_path": str(turn_dir.parent.parent),
        "turn_path": str(turn_dir),
        "response_path": str(turn_dir / "response.json"),
        "detail_json_path": str(turn_dir / "response.json"),
        "messages": [
            {
                "role": "user",
                "text": user_query,
                "turn_id": context.turn_id,
                "session_id": context.session_id,
            },
            agent_msg,
        ],
    }

    # ── Bounded evidence for research / respond routes ──────────────────
    if route in {"research", "respond"}:
        evidence = response.get("evidence")
        if isinstance(evidence, dict):
            research_evidence = evidence.get("research")
            if isinstance(research_evidence, dict):
                summary = research_evidence.get("summary")
                if isinstance(summary, str) and summary.strip():
                    # Truncate long summaries for chat-readability.
                    chat_record["research_summary"] = (
                        summary[:512] + "…" if len(summary) > 512 else summary
                    )
                sources = research_evidence.get("sources")
                if isinstance(sources, list) and sources:
                    chat_record["research_source_count"] = len(sources)
                warnings_list = research_evidence.get("warnings")
                if isinstance(warnings_list, list) and warnings_list:
                    chat_record["research_warnings"] = [
                        str(w)[:256] for w in warnings_list[:6]
                    ]

    chat_path = turn_dir / "chat.json"
    try:
        turn_dir.mkdir(parents=True, exist_ok=True)
        import json as _json

        chat_path.write_text(
            _json.dumps(chat_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError) as exc:
        _LOGGER.warning(
            "chat.json write failed for executor-only turn %s (best-effort): %s",
            context.turn_id,
            exc,
        )


def _session_root_path(session_root: Any) -> Path:
    return Path(session_root) if session_root is not None else _SESSION_ROOT


def _coerce_chat_max_messages(raw_value: Any) -> int:
    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            return DEFAULT_CHAT_DISPLAY_MESSAGES
        try:
            parsed = int(value)
        except ValueError:
            return DEFAULT_CHAT_DISPLAY_MESSAGES
    elif isinstance(raw_value, int):
        parsed = raw_value
    else:
        return DEFAULT_CHAT_DISPLAY_MESSAGES
    if parsed <= 0:
        return DEFAULT_CHAT_DISPLAY_MESSAGES
    return min(parsed, DEFAULT_CHAT_DISPLAY_MESSAGES)


def _handle_agent_edit_chat(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "chat",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
    session_id = payload.get("session_id")
    max_messages = _coerce_chat_max_messages(payload.get("max_messages"))
    try:
        result = read_session_chat(
            Path(session_root) if session_root is not None else _SESSION_ROOT,
            session_id if isinstance(session_id, str) else None,
            max_messages=max_messages,
        )
    except Exception as exc:
        return _agent_error_response(classify_failure("chat", exc))
    if not isinstance(result, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.VALIDATION_ERROR,
                "chat",
                agent_failure_context={"explanation": "read_session_chat returned a non-dict result."},
            )
        )
    latest_candidate = result.get("latest_candidate")
    outcome = (
        latest_candidate.get("outcome")
        if isinstance(latest_candidate, Mapping) and isinstance(latest_candidate.get("outcome"), Mapping)
        else {"kind": "noop"}
    )
    response = dict(result)
    response["ok"] = True
    response["outcome"] = dict(outcome) if isinstance(outcome, Mapping) else {"kind": "noop"}
    return response


def _json_response_writer(path: Path):  # type: ignore[no-untyped-def]
    def _write(response: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(response, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    return _write


def _stamp_action_success(
    response: Mapping[str, Any],
    *,
    eligibility_reason: str,
    eligibility_message: str,
) -> dict[str, Any]:
    stamped = dict(response)
    stamped["outcome"] = {"kind": "noop"}
    stamped = build_legacy_agent_edit_v1(
        {
            **stamped,
            "eligibility": ApplyEligibility(
                applyable=False,
                reason=eligibility_reason,
                message=eligibility_message,
            ).to_dict(),
            "canvas_apply_allowed": False,
            "queue_allowed": False,
        }
    )
    return ensure_agent_edit_response_contract(stamped, stage=str(stamped.get("action") or "route"))


def _ensure_stale_recovery(response: Mapping[str, Any]) -> dict[str, Any]:
    if response.get("kind") != FailureKind.STALE_STATE_MISMATCH.value:
        return dict(response)
    if isinstance(response.get("rebaseline_recovery"), Mapping):
        return dict(response)
    agent_failure_context = response.get("agent_failure_context")
    issues = []
    if isinstance(agent_failure_context, Mapping) and isinstance(agent_failure_context.get("issues"), list):
        issues = [
            dict(issue)
            for issue in agent_failure_context["issues"]
            if isinstance(issue, Mapping)
        ]
    reason = (
        agent_failure_context.get("reason")
        if isinstance(agent_failure_context, Mapping) and isinstance(agent_failure_context.get("reason"), str)
        else "stale_state_recovery"
    )
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": reason,
        "last_known_baseline_graph_hash": response.get("expected_baseline_graph_hash"),
        "submit_structural_graph_hash": response.get("submit_structural_graph_hash"),
    }
    if issues:
        issues[0].setdefault("rebaseline_recovery", dict(recovery))
    else:
        issues = [
            {
                "message": (
                    agent_failure_context.get("explanation")
                    if isinstance(agent_failure_context, Mapping)
                    else response.get("message")
                ),
                "rebaseline_recovery": dict(recovery),
            }
        ]
    failure_context = dict(agent_failure_context) if isinstance(agent_failure_context, Mapping) else {}
    failure_context["issues"] = issues
    stamped = dict(response)
    stamped["agent_failure_context"] = failure_context
    stamped["rebaseline_recovery"] = dict(recovery)
    outcome = stamped.get("outcome")
    if isinstance(outcome, Mapping):
        outcome_payload = dict(outcome)
        outcome_payload["rebaseline_recovery"] = dict(recovery)
        stamped["outcome"] = outcome_payload
    return stamped


def _normalize_action_response(
    result: Any,
    *,
    stage: str,
    success_reason: str | None = None,
    success_message: str | None = None,
) -> dict[str, Any]:
    serialized = _to_serializable(result)
    if serialized.get("ok") is True:
        if success_reason is not None and success_message is not None:
            return _stamp_action_success(
                serialized,
                eligibility_reason=success_reason,
                eligibility_message=success_message,
            )
        return serialized
    return _validated_failure_response(stage, serialized)


def _validated_failure_response(stage: str, failure: Any) -> dict[str, Any]:
    serialized = _to_serializable(failure)
    try:
        stamped = ensure_agent_edit_response_contract(serialized, stage=stage)
    except Exception:
        stamped = serialized
    return _ensure_stale_recovery(stamped)


def _audit_path_for_action(session_root: Path, session_id: str, turn_id: str, action: str) -> Path:
    return session_dir_for(session_root, session_id) / "turns" / turn_id / f"{action}_audit" / "audit.json"


def _attach_action_audit(
    response: dict[str, Any],
    *,
    request_payload: Mapping[str, Any],
    session_root: Path,
    action: str,
) -> dict[str, Any]:
    session_id = response.get("session_id")
    turn_id = response.get("turn_id")
    if not isinstance(session_id, str) or not isinstance(turn_id, str):
        return response
    audit_path = _audit_path_for_action(session_root, session_id, turn_id, action)
    if not audit_path.is_file():
        write_audit(
            audit_path.parent,
            context=TurnContext(
                session_id=session_id,
                turn_id=turn_id,
                baseline_turn_id=response.get("baseline_turn_id")
                if isinstance(response.get("baseline_turn_id"), str)
                else None,
            ),
            turn_state=response.get("accepted_state") if isinstance(response.get("accepted_state"), str) else None,
            response=response,
            artifacts={"request": dict(request_payload)},
            metadata={"action": action},
        )
    result = dict(response)
    result["audit_ref"] = artifact_ref_for_path(audit_path).to_dict()
    return result


def _handle_agent_edit_accept(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "accept",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id.strip():
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "accept",
                agent_failure_context={"explanation": "turn_id is required."},
            )
        )
    root = _session_root_path(session_root)
    session_id = payload.get("session_id")
    try:
        result = accept_turn(
            session_root=root,
            session_id=session_id if isinstance(session_id, str) else "",
            turn_id=turn_id,
            client_graph_hash=payload.get("client_graph_hash")
            if isinstance(payload.get("client_graph_hash"), str)
            else None,
            request_payload=payload,
            idempotency_key=payload.get("idempotency_key")
            if isinstance(payload.get("idempotency_key"), str)
            else None,
            response_writer=_json_response_writer(root / session_id / "turns" / turn_id / "accept_response.json")
            if isinstance(session_id, str)
            else None,
        )
    except Exception as exc:
        return _agent_error_response(classify_failure("accept", exc))
    serialized = _normalize_action_response(
        result,
        stage="accept",
        success_reason="superseded",
        success_message="This candidate has been superseded.",
    )
    if serialized.get("ok") is True:
        try:
            return _attach_action_audit(
                serialized,
                request_payload=payload,
                session_root=root,
                action="accept",
            )
        except Exception as exc:
            return _agent_error_response(classify_failure("audit", exc))
    return serialized


def _handle_agent_edit_reject(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "reject",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id.strip():
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "reject",
                agent_failure_context={"explanation": "turn_id is required."},
            )
        )
    root = _session_root_path(session_root)
    session_id = payload.get("session_id")
    try:
        result = reject_turn(
            session_root=root,
            session_id=session_id if isinstance(session_id, str) else "",
            turn_id=turn_id,
            client_graph_hash=payload.get("client_graph_hash")
            if isinstance(payload.get("client_graph_hash"), str)
            else None,
            request_payload=payload,
            idempotency_key=payload.get("idempotency_key")
            if isinstance(payload.get("idempotency_key"), str)
            else None,
            response_writer=_json_response_writer(root / session_id / "turns" / turn_id / "reject_response.json")
            if isinstance(session_id, str)
            else None,
        )
    except Exception as exc:
        return _agent_error_response(classify_failure("reject", exc))
    serialized = _normalize_action_response(
        result,
        stage="reject",
        success_reason="superseded",
        success_message="This candidate has been superseded.",
    )
    if serialized.get("ok") is True:
        try:
            return _attach_action_audit(
                serialized,
                request_payload=payload,
                session_root=root,
                action="reject",
            )
        except Exception as exc:
            return _agent_error_response(classify_failure("audit", exc))
    return serialized


def _handle_agent_edit_rebaseline(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "rebaseline",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
    try:
        result = rebaseline_session(
            session_root=_session_root_path(session_root),
            session_id=payload.get("session_id") if isinstance(payload.get("session_id"), str) else "",
            request_payload=payload,
            idempotency_key=payload.get("idempotency_key")
            if isinstance(payload.get("idempotency_key"), str)
            else None,
        )
    except Exception as exc:
        return _agent_error_response(classify_failure("rebaseline", exc))
    return _normalize_action_response(
        result,
        stage="rebaseline",
        success_reason="no_candidate",
        success_message="No candidate is available to apply.",
    )


def _handle_agent_edit_audit(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
    session_id = payload.get("session_id")
    turn_id = payload.get("turn_id")
    action = payload.get("action")
    if not isinstance(session_id, str) or not session_id.strip():
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "session_id is required."},
            )
        )
    if not isinstance(turn_id, str) or not turn_id.strip():
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "turn_id is required."},
            )
        )
    if action not in {"accept", "reject", "rebaseline"}:
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "action must be one of accept, reject, or rebaseline."},
            )
        )
    audit_path = _audit_path_for_action(_session_root_path(session_root), session_id, turn_id, action)
    try:
        body = audit_path.read_bytes()
    except OSError as exc:
        return _agent_error_response(classify_failure("audit", exc))
    return {
        "ok": True,
        "headers": {
            "Content-Type": "application/json",
            "Content-Disposition": f'attachment; filename="{session_id}-{turn_id}-{action}_audit.json"',
            "X-Content-Type-Options": "nosniff",
        },
        "body": body,
    }





def _handle_agent_credentials(
    payload: Any,
    *,
    env_path: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _agent_error_response(
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "credentials",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            )
        )
    try:
        return handle_credential_submission(
            payload,
            env_path=Path(env_path) if env_path is not None else None,
        )
    except Exception as exc:
        return _agent_error_response(classify_failure("ingest", exc))




def _handle_vibecomfy_submit_rating(payload: Any) -> tuple[dict[str, Any], int]:
    result, status = submit_hivemind_feedback(payload)
    if result.get("ok") is True and 200 <= status < 300:
        return result, 201
    return result, status


def _to_serializable(result: Any) -> Any:
    """Convert a FailureEnvelope/dataclass result to a plain dict for JSON."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict") and callable(result.to_dict):
        return result.to_dict()
    return {"error": "Non-serializable result", "repr": repr(result)}


def register_agent_edit_routes(app) -> None:
    """Register the /vibecomfy/agent-edit/* routes on a ComfyUI PromptServer *app*.

    Includes the legacy POST /agent/edit alias for backward compatibility.
    This function is a no-op when ``VIBECOMFY_HEADLESS=1`` is set in the
    environment, so importing this module outside a ComfyUI server does not
    trigger ``aiohttp`` or ``server`` side effects.

    Parameters
    ----------
    app:
        A ComfyUI ``PromptServer`` instance whose ``.routes`` attribute exposes
        an ``aiohttp.RouteTableDef``.
    """
    from pathlib import Path as _Path  # noqa: PLC0415
    from aiohttp import web as _web  # noqa: PLC0415
    from .edit import (  # noqa: PLC0415
        _safe_session_id as _safe_session_id,
        _SESSION_ROOT as _EDIT_SESSION_ROOT,
        handle_agent_edit,
        read_session_bundle,
        read_session_chat,
        read_session_json,
    )
    from .session import (  # noqa: PLC0415
        accept_turn,
        reject_turn,
        rebaseline_session,
    )
    from .contracts import (
        FailureKind as _FK,
        classify_failure as _classify_failure,
        ensure_agent_edit_response_contract as _ensure_contract,
        failure_envelope as _failure_envelope,
    )

    _SESSION_ROOT = _Path(_EDIT_SESSION_ROOT)

    def _client_id_from_payload(payload: Any) -> str | None:
        cid = payload.get("client_id") if isinstance(payload, dict) else None
        if isinstance(cid, str) and cid.strip():
            return cid
        return None

    def _session_id_from_query(request) -> str:  # type: ignore[no-untyped-def]
        return _safe_session_id(request.query.get("session_id"))

    def _json_error(message: str, stage: str = "agent_edit", status: int = 400):  # type: ignore[no-untyped-def]
        return _web.json_response(
            _ensure_contract(
                _failure_envelope(
                    _FK.MISSING_REQUIRED_FIELD,
                    stage,
                    agent_failure_context={"explanation": message},
                ).to_dict(),
                stage=stage,
            ),
            status=status,
        )

    @app.routes.post("/vibecomfy/agent-edit")
    async def _agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result, status = await asyncio.to_thread(
                _handle_agent_executor_submit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("run_executor returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result, status=status)

    @app.routes.post("/vibecomfy/agent-executor")
    async def _agent_executor_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_executor")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_executor")
        try:
            result, status = await asyncio.to_thread(
                _handle_agent_executor_submit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_executor", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_executor"),
                status=500,
            )
        return _web.json_response(result, status=status)

    @app.routes.post("/agent/edit")
    async def _legacy_agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result = await asyncio.to_thread(handle_agent_edit, payload)
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("handle_agent_edit returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result)

    @app.routes.post("/vibecomfy/agent-edit/accept")
    async def _agent_edit_accept_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="accept")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="accept")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="accept")
        try:
            result = await asyncio.to_thread(
                accept_turn,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                client_graph_hash=payload.get("client_graph_hash"),
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("accept", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="accept"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/reject")
    async def _agent_edit_reject_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="reject")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="reject")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="reject")
        try:
            result = await asyncio.to_thread(
                reject_turn,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                client_graph_hash=payload.get("client_graph_hash"),
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("reject", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="reject"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/rebaseline")
    async def _agent_edit_rebaseline_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="rebaseline")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="rebaseline")
        session_id = _safe_session_id(payload.get("session_id"))
        try:
            result = await asyncio.to_thread(
                rebaseline_session,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("rebaseline", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="rebaseline"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/chat")
    async def _agent_edit_chat_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_chat,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("chat", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="chat"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/session-bundle")
    async def _agent_edit_session_bundle_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_bundle,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("session_bundle", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="session_bundle"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/session-json")
    async def _agent_edit_session_json_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_json,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("session_json", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="session_json"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))


# ── Route registration (guarded: no-op when VIBECOMFY_HEADLESS=1) ──────────

if os.environ.get("VIBECOMFY_HEADLESS") != "1":
    try:
        from aiohttp import web as _web  # noqa: PLC0415
        from server import PromptServer as _PromptServer  # noqa: PLC0415

        @_PromptServer.instance.routes.post("/vibecomfy/roundtrip")
        async def roundtrip_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/roundtrip request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    {"error": str(exc), "kind": type(exc).__name__}, status=400
                )
            result = _handle_roundtrip(payload)
            if "error" in result:
                return _web.json_response(result, status=400)
            return _web.json_response(result)


        @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/rating")
        async def agent_edit_rating_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent-edit/rating request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    {
                        "ok": False,
                        "error": "validation",
                        "detail": f"Request body must be valid JSON: {exc}",
                    },
                    status=400,
                )
            result, status = await asyncio.to_thread(_handle_vibecomfy_submit_rating, payload)
            return _web.json_response(result, status=status)

        @_PromptServer.instance.routes.get("/vibecomfy/agent/status")
        async def agent_status_route(request):  # type: ignore[no-untyped-def]
            try:
                payload = _handle_agent_status(dict(request.query))
                return _web.json_response(payload)
            except Exception as exc:
                _LOGGER.exception("/vibecomfy/agent/status route handler failed")
                return _web.json_response(
                    {
                        "ok": False,
                        "ready": False,
                        "error": f"Status handler error: {exc}",
                        "route_options": {},
                    },
                    status=500,
                )

        @_PromptServer.instance.routes.post("/vibecomfy/agent/credentials")
        async def agent_credentials_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent/credentials request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    failure_envelope(
                        FailureKind.MISSING_REQUIRED_FIELD,
                        "credentials",
                        agent_failure_context={
                            "explanation": f"Request body must be valid JSON: {exc}"
                        },
                    ).to_dict(),
                    status=400,
                )
            result = _handle_agent_credentials(payload)
            return _web.json_response(result, status=400 if result.get("ok") is False else 200)

        # Also register the agent edit route on the global PromptServer instance
        register_agent_edit_routes(_PromptServer.instance)
        _LOGGER.info("vibecomfy agent routes module loaded and all routes registered.")

    except ImportError as _routes_import_exc:
        _LOGGER.warning("vibecomfy agent routes module could not register server routes: %s", _routes_import_exc)
