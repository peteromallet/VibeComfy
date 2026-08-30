from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Callable

from .audit import write_json_artifact
from .contracts import build_legacy_agent_edit_v1, classify_failure
from .executor_response import _sanitize_clarify_payload
from .session import (
    allocate_turn,
    normalize_session_id,
    record_idempotent_response,
    session_dir_for,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SESSION_ROOT = Path("out/editor_sessions")

# Routes for which the executor skips the implement phase entirely. These turns
# still need durable session/turn/artifact bookkeeping so the UI can rehydrate
# from canonical storage.
EXECUTOR_ONLY_NON_APPLYABLE_ROUTES = frozenset(
    {"clarify", "inspect", "respond", "research", "requires_custom_nodes"}
)


def maybe_write_executor_only_durable_turn(
    *,
    response: dict[str, Any],
    result: Any,
    payload: dict[str, Any],
    request: Any,
    session_root: Path | None = None,
    allocate_turn_func: Callable[..., Any] = allocate_turn,
    record_idempotent_response_func: Callable[..., Any] = record_idempotent_response,
) -> dict[str, Any]:
    """Allocate and write artifacts for executor-only non-applyable turns.

    Applyable revise/adapt turns already delegate durable artifact writing to
    ``handle_agent_edit``; this writer fills the durable gap for routes where
    the executor intentionally skips implementation.
    """
    route = response.get("route") if isinstance(response.get("route"), str) else ""
    if route not in EXECUTOR_ONLY_NON_APPLYABLE_ROUTES:
        return response

    has_durable_session_id = isinstance(response.get("session_id"), str) and response["session_id"].strip()
    has_durable_turn_id = isinstance(response.get("turn_id"), str) and response["turn_id"].strip()
    if has_durable_session_id and has_durable_turn_id:
        return response

    if response.get("ok") is False:
        return response

    session_id_raw = payload.get("session_id")
    if isinstance(session_id_raw, str):
        session_id = normalize_session_id(session_id_raw)
    else:
        session_id = uuid.uuid4().hex

    root = session_root if session_root is not None else DEFAULT_SESSION_ROOT
    idempotency_key = payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None

    try:
        query_text_raw = getattr(request, "query", "") or payload.get("query") or payload.get("task") or ""
        query_text = query_text_raw if isinstance(query_text_raw, str) else ""
        # Normalize any dict request graph through the named ingest door
        # BEFORE building the artifact payload and calling allocate_turn_func,
        # so allocation hashing/state and request.json persistence all see the
        # SAME canonical graph. The retained WorkflowSnapshot is the replay
        # authority; raw is never re-decoded after this ingest. Failures fall
        # through to the outer best-effort handler — a raw graph is never
        # allocated or persisted.
        request_graph = getattr(request, "graph", None)
        retained_snapshot = None
        if isinstance(request_graph, dict):
            from vibecomfy.ingest.normalize import ingest_workflow_and_ui
            from vibecomfy.ingest.snapshot import snapshot_of

            retained_workflow, request_graph = ingest_workflow_and_ui(
                request_graph, schema_provider=None
            )
            retained_snapshot = snapshot_of(retained_workflow)
        request_artifact_payload: dict[str, Any] = {
            "query": query_text,
            "task": query_text,
            "session_id": session_id,
        }
        if idempotency_key is not None:
            request_artifact_payload["idempotency_key"] = idempotency_key
        pipeline_mode = getattr(request, "pipeline_mode", None)
        if isinstance(pipeline_mode, str):
            request_artifact_payload["pipeline_mode"] = pipeline_mode
        if request_graph is not None:
            request_artifact_payload["graph"] = (
                dict(request_graph) if isinstance(request_graph, dict) else request_graph
            )
        # Include workflow_id from request field or extract from graph
        workflow_id = None
        if hasattr(request, "workflow_id") and request.workflow_id is not None:
            workflow_id = request.workflow_id
        elif hasattr(request, "graph") and isinstance(request.graph, dict):
            workflow_id = request.graph.get("workflow_id") or request.graph.get("id")
        if isinstance(workflow_id, str) and workflow_id.strip():
            request_artifact_payload["workflow_id"] = workflow_id

        allocation = allocate_turn_func(
            session_root=root,
            session_id=session_id,
            request_payload=request_artifact_payload,
            idempotency_key=idempotency_key,
        )

        if allocation.replay is not None:
            replayed = dict(allocation.replay.response)
            if idempotency_key is not None and "idempotency_key" not in replayed:
                replayed["idempotency_key"] = idempotency_key
            if retained_snapshot is not None:
                from vibecomfy.ingest.snapshot import bind_snapshot_lineage

                bind_snapshot_lineage(
                    retained_workflow,
                    session_id=session_id,
                    turn_id=allocation.context.turn_id,
                    baseline_id=allocation.context.baseline_turn_id,
                )
            return replayed
        if allocation.conflict is not None:
            # The session allocation is the conflict authority. Returning the
            # inbound executor success here would claim that conflicting work
            # completed even though the durable session rejected it.
            return allocation.conflict.failure.to_dict()

        context = allocation.context
        turn_dir = allocation.turn_dir
        write_json_artifact(turn_dir / "request.json", request_artifact_payload)

        # Non-edit routes still need authoritative UI evidence. Project final
        # from the submitted original so unchanged/clarify/refusal turns carry
        # both original.ui.json and final.ui.json.
        original_ui = (
            dict(request_graph)
            if isinstance(request_graph, dict)
            else {"nodes": [], "links": []}
        )
        write_json_artifact(turn_dir / "original.ui.json", original_ui)
        write_json_artifact(turn_dir / "final.ui.json", original_ui)

        response_path = turn_dir / "response.json"
        stamped = dict(response)
        stamped["session_id"] = context.session_id
        stamped["turn_id"] = context.turn_id
        if retained_snapshot is not None:
            from vibecomfy.ingest.snapshot import bind_snapshot_lineage

            retained_snapshot = bind_snapshot_lineage(
                retained_workflow,
                session_id=context.session_id,
                turn_id=context.turn_id,
                baseline_id=context.baseline_turn_id,
            )
            stamped["workflow_source_digest"] = retained_snapshot.source_digest
            stamped["workflow_semantic_digest"] = retained_snapshot.semantic_digest
            stamped["workflow_semantic_hash_version"] = retained_snapshot.semantic_hash_version
            # T5.1 lineage: the source representation name travels with the
            # snapshot digests so the artifact manifest can link it without
            # re-deriving shape from raw bytes.
            stamped["workflow_source_representation"] = str(
                getattr(retained_snapshot, "source_representation", "") or ""
            )
        stamped["session_path"] = str(session_dir_for(root, context.session_id))
        stamped["session_path_resolved"] = str(session_dir_for(root, context.session_id).resolve())
        stamped["detail_json_path"] = str(response_path)
        stamped["detail_json_path_resolved"] = str(response_path.resolve())
        stamped["query"] = query_text
        stamped["task"] = query_text
        if context.baseline_turn_id is not None:
            stamped["baseline_turn_id"] = context.baseline_turn_id
        if idempotency_key is not None:
            stamped["idempotency_key"] = idempotency_key

        baseline_state = allocation.state
        baseline_graph_hash = baseline_state.get("baseline_graph_hash") if isinstance(baseline_state, dict) else None
        if isinstance(baseline_graph_hash, str):
            stamped["baseline_graph_hash"] = baseline_graph_hash

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
            if route == "clarify":
                reply_text = stamped.get("reply") or stamped.get("message") or ""
                reply_text = reply_text if isinstance(reply_text, str) else ""
                stamped["outcome"] = {
                    "kind": "clarify",
                    "question": reply_text,
                    "clarification": {"message": reply_text},
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

        write_executor_only_chat_artifact(
            turn_dir=turn_dir,
            context=context,
            response=stamped,
            route=route,
        )
        write_executor_only_research_trace(
            turn_dir=turn_dir,
            result=result,
            route=route,
        )

        record_idempotent_response_func(
            session_root=root,
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
    except Exception as exc:
        _LOGGER.warning(
            "Executor-only durable turn write failed for session=%s route=%s (best-effort)",
            session_id,
            route,
            exc_info=True,
        )
        return classify_failure("durable_turn", exc).to_dict()


def write_executor_only_research_trace(
    *,
    turn_dir: Path,
    result: Any,
    route: str,
) -> None:
    """Best-effort write of ``research_trace.json`` for research-only turns.

    The C1 research trace (per-turn decisions + tool digests + final state)
    is deliberately NOT in the public envelope (bounded C5 memo only), so the
    durable turn dir is the one place the actual agent reasoning survives.
    This gives the panel/report the same ``messages.jsonl``-grade visibility
    the batch-REPL path has, without leaking evidence bodies.
    """
    if route != "research":
        return
    report = getattr(result, "report", None)
    research = getattr(report, "research", None)
    trace = getattr(research, "trace", None)
    if trace is None:
        return
    try:
        payload = trace.to_dict()
        write_json_artifact(turn_dir / "research_trace.json", payload)
    except (OSError, ValueError, TypeError) as exc:
        _LOGGER.warning(
            "research_trace.json write failed for turn %s (best-effort): %s",
            turn_dir.name,
            exc,
        )


def write_executor_only_chat_artifact(
    *,
    turn_dir: Path,
    context: Any,
    response: dict[str, Any],
    route: str,
) -> None:
    """Best-effort write of ``chat.json`` for an executor-only non-applyable turn."""
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

    if route in {"research", "respond"}:
        evidence = response.get("evidence")
        if isinstance(evidence, dict):
            research_evidence = evidence.get("research")
            if isinstance(research_evidence, dict):
                summary = research_evidence.get("summary")
                if isinstance(summary, str) and summary.strip():
                    chat_record["research_summary"] = (
                        summary[:512] + "..." if len(summary) > 512 else summary
                    )
                sources = research_evidence.get("sources")
                if isinstance(sources, list) and sources:
                    chat_record["research_source_count"] = len(sources)
                warnings_list = research_evidence.get("warnings")
                if isinstance(warnings_list, list) and warnings_list:
                    chat_record["research_warnings"] = [
                        str(warning)[:256] for warning in warnings_list[:6]
                    ]
                # R4: surface the honest stage status + executed-call/evidence
                # counters so the panel distinguishes "searched, found
                # nothing" from "research never completed" (deadline/turn
                # exhaustion drops the agent's synthesis, not the evidence).
                status_value = research_evidence.get("research_status")
                if isinstance(status_value, str) and status_value:
                    chat_record["research_status"] = status_value[:32]
                for key, out_key in (
                    ("tool_calls_executed", "research_tool_calls_executed"),
                    ("evidence_artifacts", "research_evidence_artifacts"),
                ):
                    value = research_evidence.get(key)
                    if isinstance(value, int):
                        chat_record[out_key] = value

                # The panel's diagnostic-event gate only admits transcript
                # messages that carry a diagnostics array (or stage /
                # lifecycle / batch_turns); a bare outcome message reads as
                # "no recent turn records".  Attach a typed diagnostic so the
                # research turn is visible in the issue report, carrying the
                # honest status and warning text.  The memo serializes the
                # warning list under ``research_warnings`` (not ``warnings``),
                # and a successful run is "completed", not a warning.
                if status_value == "ok":
                    diag_severity = "info"
                    diag_message = "research stage completed"
                elif status_value in {"failed", "exhausted"}:
                    diag_severity = "error"
                    diag_message = "research stage did not complete"
                else:
                    diag_severity = "warning"
                    diag_message = "research stage status unknown"
                warnings_list = research_evidence.get("research_warnings")
                if isinstance(warnings_list, list) and warnings_list:
                    first_warning = str(warnings_list[0])[:200]
                    if first_warning:
                        diag_message = first_warning
                diagnostics_payload: list[dict[str, str]] = [
                    {
                        "code": "research_status",
                        "severity": diag_severity,
                        "message": diag_message,
                        "stage": "research",
                        "status": status_value if isinstance(status_value, str) else "unknown",
                    }
                ]
                agent_msg["diagnostics"] = diagnostics_payload
                if isinstance(status_value, str) and status_value:
                    agent_msg["status"] = status_value[:32]

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
