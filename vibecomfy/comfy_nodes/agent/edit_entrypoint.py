# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: handle_agent_edit and websocket turn events.

SOURCE = r'''
def handle_agent_edit(
    payload: dict[str, Any],
    *,
    schema_provider: Any = None,
    deepseek_client: DeepSeekClient | None = None,
    session_root: Path | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Convert current UI JSON to Python, ask the agent to edit it, emit UI JSON."""
    from vibecomfy.schema import get_schema_provider

    if not isinstance(payload, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`task` is required."},
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")
    if not isinstance(graph, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={
                "explanation": "`graph` must be a ComfyUI UI JSON object."
            },
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")

    if schema_provider is None:
        schema_provider = _default_runtime_schema_provider()
    root = session_root or _SESSION_ROOT
    session_id = _safe_session_id(payload.get("session_id"))
    allocation = allocate_turn(
        session_root=root,
        session_id=session_id,
        request_payload=payload,
        idempotency_key=payload.get("idempotency_key")
        if isinstance(payload.get("idempotency_key"), str)
        else None,
    )
    if allocation.replay is not None:
        return _validated_agent_edit_response(allocation.replay.response, stage="replay")
    if allocation.conflict is not None:
        try:
            audit_ref = write_allocation_failure_audit(
                allocation.session_dir,
                session_id=session_id,
                failure=allocation.conflict.failure,
                request=payload,
            )
            failure = dataclasses.replace(allocation.conflict.failure, audit_ref=audit_ref)
        except Exception:
            failure = allocation.conflict.failure
        return _validated_agent_edit_response(
            _product_failure_response(failure),
            stage="allocation",
        )

    context = allocation.context
    context.client_graph_hash = payload.get("client_graph_hash") if isinstance(payload.get("client_graph_hash"), str) else None
    initialize_gates(context)
    _write_unknown_transition_audits(
        session_root=root,
        session_id=session_id,
        baseline_turn_id=context.baseline_turn_id,
        unknown_transitions=allocation.unknown_transitions,
        request_payload=payload,
    )
    turn_dir = allocation.turn_dir
    turn_record = allocation.state.get("turns", {}).get(context.turn_id)
    baseline_graph_hash = (
        allocation.state.get("baseline_graph_hash")
        if isinstance(allocation.state.get("baseline_graph_hash"), str)
        else None
    )
    submit_graph_hash = (
        turn_record.get("submit_graph_hash")
        if isinstance(turn_record, dict) and isinstance(turn_record.get("submit_graph_hash"), str)
        else None
    )
    submit_structural_graph_hash = (
        turn_record.get("submit_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submit_structural_graph_hash"), str)
        else None
    )
    submitted_client_graph_hash = (
        turn_record.get("submitted_client_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_graph_hash"), str)
        else None
    )
    submitted_client_structural_graph_hash = (
        turn_record.get("submitted_client_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_structural_graph_hash"), str)
        else None
    )
    state = AgentEditState(
        task=task,
        graph=graph,
        request_payload=payload,
        schema_provider=schema_provider,
        baseline_graph_hash=baseline_graph_hash,
        submit_graph_hash=submit_graph_hash,
        submit_structural_graph_hash=submit_structural_graph_hash,
        submitted_client_graph_hash=submitted_client_graph_hash,
        submitted_client_structural_graph_hash=submitted_client_structural_graph_hash,
        session_dir=allocation.session_dir,
        turn_dir=turn_dir,
        request_path=turn_dir / "request.json",
        original_ui_path=turn_dir / "original.ui.json",
        before_py_path=turn_dir / "before.py",
        after_py_path=turn_dir / "after.py",
        model_request_path=turn_dir / "model_request.json",
        model_response_path=turn_dir / "model_response.json",
        candidate_ui_path=turn_dir / "candidate.ui.json",
        revision_evidence_path=turn_dir / "revision_evidence.json",
        execution_plan_path=turn_dir / "execution_plan.json",
        plan_evaluation_path=turn_dir / "plan_evaluation.json",
        projection_path=turn_dir / "projection.txt",
        messages_path=turn_dir / "messages.jsonl",
        narrative_context_path=turn_dir / "narrative_context.json",
        narrative_request_path=turn_dir / "narrative_request.json",
        narrative_response_path=turn_dir / "narrative_response.json",
        narrative_validation_path=turn_dir / "narrative_validation.json",
    )
    research_summary = payload.get("research_summary")
    if isinstance(research_summary, str) and research_summary.strip():
        state.executor_research_summary = research_summary.strip()
    research_warnings: list[str] = []
    raw_research_warnings = payload.get("research_warnings")
    if isinstance(raw_research_warnings, list):
        research_warnings.extend(
            warning.strip()
            for warning in raw_research_warnings
            if isinstance(warning, str) and warning.strip()
        )
    executor_research = payload.get("executor_research")
    if isinstance(executor_research, dict):
        raw_executor_warnings = executor_research.get("warnings")
        if isinstance(raw_executor_warnings, list):
            research_warnings.extend(
                warning.strip()
                for warning in raw_executor_warnings
                if isinstance(warning, str) and warning.strip()
            )
    if research_warnings:
        state.executor_research_warnings = tuple(dict.fromkeys(research_warnings))
    research_sources = payload.get("research_sources")
    if isinstance(research_sources, list):
        state.executor_research_sources = tuple(
            source for source in research_sources if isinstance(source, dict)
        )
    # Extract structured precedent data from payload (SD2)
    precedent_slices = payload.get("precedent_slices")
    if isinstance(precedent_slices, list):
        state.executor_precedent_slices = tuple(
            s for s in precedent_slices if isinstance(s, dict)
        )
    adaptation_plan = payload.get("adaptation_plan")
    if isinstance(adaptation_plan, dict):
        state.executor_adaptation_plan = adaptation_plan
    research_brief = payload.get("research_brief")
    if isinstance(research_brief, dict):
        state.executor_research_brief = research_brief
    # SD3: scoped adapt-prefetch fields.
    protocol_notes = payload.get("execution_protocol_notes")
    if isinstance(protocol_notes, dict):
        state.execution_protocol_notes = protocol_notes
        _hydrate_execution_plan_from_protocol_notes(state, protocol_notes)
    context_packet = payload.get("research_context_packet")
    if isinstance(context_packet, dict):
        state.research_context_packet = context_packet
    graph_inspection = payload.get("graph_inspection")
    if isinstance(graph_inspection, str) and graph_inspection.strip():
        state.graph_inspection = graph_inspection.strip()
    if isinstance(payload.get("max_batches"), int) and payload["max_batches"] > 0:
        state.batch_max_turns = int(payload["max_batches"])
    if (
        isinstance(payload.get("max_consecutive_errors"), int)
        and payload["max_consecutive_errors"] > 0
    ):
        state.batch_max_consecutive_errors = int(payload["max_consecutive_errors"])

    contract = _agent_edit_contract()

    raw_route = payload.get("route") if isinstance(payload.get("route"), str) else None
    executor_route = payload.get("executor_route") if isinstance(payload.get("executor_route"), str) else raw_route
    provider_route = payload.get("provider_route") if isinstance(payload.get("provider_route"), str) else raw_route
    route = _canonical_agent_edit_route(executor_route)
    model = payload.get("model") if isinstance(payload.get("model"), str) else None
    state.route = route

    from .reorganise import build_reorganise_agent_response, is_reorganise_agent_request

    if is_reorganise_agent_request(task, route):
        state.route = "reorganise"
        response = _validated_agent_edit_response(
            build_reorganise_agent_response(state, context),
            stage="submit",
        )
        try:
            audit_ref = _stage_audit(state, context, response=response)
            response["audit_ref"] = audit_ref.to_dict()
        except Exception as exc:
            failure = failure_envelope(
                FailureKind.AUDIT_WRITE_FAILURE,
                "audit",
                context,
                agent_failure_context={"explanation": str(exc)},
                audit_error=str(exc),
            )
            return _validated_agent_edit_response(_product_failure_response(failure), stage="audit")
        response = _validated_agent_edit_response(response, stage="submit")
        _write_turn_chat_artifact(state, context, response, contract)
        record_idempotent_response(
            session_root=root,
            session_id=session_id,
            scope="edit",
            idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
            request_hash=allocation.request_hash,
            response=response,
            response_path=turn_dir / "response.json",
            operation="edit",
            turn_id=context.turn_id,
        )
        return response

    # Load session-local last-five conversation messages for prompt memory.
    # Only the batch_repl product path injects them (SD2); delta/full-dev
    # paths persist chat artifacts but do not receive prompt memory in this
    # slim v1 milestone.
    conversation_messages: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        try:
            chat = read_session_chat(root, session_id, max_messages=PROMPT_MEMORY_MESSAGES)
            if chat.get("ok") and isinstance(chat.get("messages"), list):
                conversation_messages = chat["messages"]
                conversation_messages = _conversation_with_candidate_reference(
                    conversation_messages,
                    chat.get("latest_candidate"),
                )
        except Exception:
            conversation_messages = None

    try:
        if contract == "batch_repl":
            state = _run_batch_repl_product_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
                client_id=client_id,
                conversation_messages=conversation_messages,
            )
        elif contract == "delta":
            state = _run_delta_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
            )
        else:
            state = _run_full_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
            )
    except _StageBlocked as blocked:
        stage_name = (
            blocked.failure.stage
            if blocked.failure is not None
            else blocked.result.stage
        )
        response = _validated_agent_edit_response(
            _failure_response(
                state,
                context,
                contract=contract,
                failure=blocked.failure
                or classify_failure(blocked.result.stage, blocked, context),
            ),
            stage=stage_name,
        )
        _write_turn_chat_artifact(state, context, response, contract)
        record_idempotent_response(
            session_root=root,
            session_id=session_id,
            scope="edit",
            idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
            request_hash=allocation.request_hash,
            response=response,
            response_path=turn_dir / "response.json",
            operation="edit",
            turn_id=context.turn_id,
        )
        return response

    # Carry canonical executor route on state so response builders can apply
    # route-aware gating independent of provider dispatch.
    state.route = route

    if contract == "delta":
        response = _validated_agent_edit_response(
            _build_dev_success_response(state, context, contract=contract),
            stage="submit",
        )
    elif contract == "batch_repl":
        response = _validated_agent_edit_response(
            _build_batch_repl_response(state, context),
            stage="submit",
        )
    else:
        response = _validated_agent_edit_response(
            _build_dev_success_response(state, context, contract=contract),
            stage="submit",
        )
    try:
        if contract == "delta":
            _record(
                context,
                StageResult(
                    stage="audit",
                    ok=True,
                    blocking=False,
                    value={"mode": "agent_edit_v2_delta"},
                ),
            )
        elif contract == "batch_repl":
            _record(
                context,
                StageResult(
                    stage="audit",
                    ok=True,
                    blocking=False,
                    value={"mode": state.batch_exit_mode or "batch_repl"},
                ),
            )
        audit_ref = _stage_audit(state, context, response=response)
        response["audit_ref"] = audit_ref.to_dict()
    except Exception as exc:
        failure = failure_envelope(
            FailureKind.AUDIT_WRITE_FAILURE,
            "audit",
            context,
            agent_failure_context={"explanation": str(exc)},
            audit_error=str(exc),
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="audit")
    response = _validated_agent_edit_response(response, stage="submit")
    _write_turn_chat_artifact(state, context, response, contract)
    record_idempotent_response(
        session_root=root,
        session_id=session_id,
        scope="edit",
        idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
        request_hash=allocation.request_hash,
        response=response,
        response_path=turn_dir / "response.json",
        operation="edit",
        turn_id=context.turn_id,
    )
    return response


# ── WebSocket event helpers (best-effort, compact) ──────────────────────────


def _ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None) -> None:
    """Send a websocket event to a client, preferring send_sync, falling back to send_json.

    This is a best-effort adapter: failures are logged and swallowed so websocket issues
    never block the agent-edit control flow.
    """
    try:
        from server import PromptServer  # noqa: PLC0415
    except ImportError:
        return  # not running inside ComfyUI (tests, CLI, etc.)
    try:
        if hasattr(PromptServer.instance, "send_sync") and callable(
            PromptServer.instance.send_sync
        ):
            PromptServer.instance.send_sync(event, payload, sid=client_id)
        elif hasattr(PromptServer.instance, "send_json") and callable(
            PromptServer.instance.send_json
        ):
            PromptServer.instance.send_json(event, payload, sid=client_id)
    except Exception:
        LOGGER.debug("websocket send for event %r to client %r failed (best-effort)", event, client_id, exc_info=True)


def _brief_batch_statements(turn_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact, privacy-safe list of statement summaries from a batch turn record.

    Excludes: diff, raw batch/source, report text, provider metadata, and any raw JSON dumps.
    """
    if not isinstance(turn_record, dict):
        return []

    # Clarification turns have a different shape
    if turn_record.get("clarification_required"):
        return [
            {
                "clarification": True,
                "message": turn_record.get("clarification_message", ""),
            }
        ]

    statements = turn_record.get("statements")
    if not isinstance(statements, list) or not statements:
        # Fallback: build a minimal summary from turn-level fields
        return [
            {
                "ok": bool(turn_record.get("batch_ok")),
                "statement_count": int(turn_record.get("statement_count", 0)),
                "landed": int(turn_record.get("landed_op_count", 0)),
                "diagnostic_count": len(turn_record.get("diagnostics") or []),
            }
        ]

    brief: list[dict[str, Any]] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        compact: dict[str, Any] = {
            "statement_index": stmt.get("statement_index"),
            "ok": stmt.get("ok"),
            "landed": stmt.get("landed"),
            "op_kind": stmt.get("op_kind"),
        }
        # Only include teaching_hint if present (it's compact guidance, not raw source)
        if stmt.get("teaching_hint"):
            compact["teaching_hint"] = stmt["teaching_hint"]
        if stmt.get("dependency_cause"):
            compact["dependency_cause"] = stmt["dependency_cause"]
        # Compact diagnostics: only code + message, no raw detail blobs
        diags = stmt.get("diagnostics")
        if isinstance(diags, list) and diags:
            compact["diagnostics"] = [
                {"code": d.get("code"), "message": d.get("message")}
                for d in diags
                if isinstance(d, dict)
            ][:5]
        # Touched uids are small identifiers, safe to include
        if stmt.get("touched_uids"):
            compact["touched_uids"] = list(stmt["touched_uids"])[:10]
        brief.append(compact)
    return brief


def _agent_edit_turn_event_payload(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    entry_type: str = "batch",
    status: str = "progress",
) -> dict[str, Any]:
    """Build a compact websocket event payload for a batch turn.

    Excludes: diff, raw batch/source text, file paths, provider metadata,
    and raw JSON blobs.  Only includes fields safe for wire transport.
    """
    payload: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "turn_number": turn_record.get("turn_number"),
        "entry_type": entry_type,
        "status": status,
    }

    # Include a bounded user-facing message
    message = turn_record.get("message")
    if isinstance(message, str) and message:
        payload["message"] = message[:500] if len(message) > 500 else message

    if turn_record.get("clarification_required"):
        payload["clarification_required"] = True
        cm = turn_record.get("clarification_message")
        if isinstance(cm, str) and cm:
            payload["clarification_message"] = cm[:500] if len(cm) > 500 else cm
    else:
        payload["batch_ok"] = bool(turn_record.get("batch_ok"))
        payload["statement_count"] = int(turn_record.get("statement_count", 0))
        payload["landed_op_count"] = int(turn_record.get("landed_op_count", 0))

    # Compact statement summaries (privacy-safe)
    statements = _brief_batch_statements(turn_record)
    if statements:
        payload["statements"] = statements

    # Turn-level diagnostics (compact: code + message only)
    diags = turn_record.get("diagnostics")
    if isinstance(diags, list) and diags:
        payload["diagnostics"] = [
            {"code": d.get("code"), "message": d.get("message")}
            for d in diags
            if isinstance(d, dict)
        ][:5]

    # Exit mode info when present
    exit_mode = getattr(state, "batch_exit_mode", "")
    if exit_mode:
        payload["exit_mode"] = exit_mode
    if exit_mode in {_BATCH_EXIT_DONE, _BATCH_EXIT_NOOP} and getattr(state, "batch_done_summary", ""):
        payload["done_summary"] = str(state.batch_done_summary)[:500]

    # Budget snapshot
    budget = getattr(state, "batch_budget_state", None)
    if isinstance(budget, dict) and budget:
        payload["budget"] = {
            "remaining_batches": budget.get("remaining_batches"),
            "consecutive_errors": budget.get("consecutive_errors"),
        }

    return payload


def _emit_agent_edit_turn_event(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    client_id: str | None = None,
    entry_type: str = "batch",
    status: str = "progress",
) -> None:
    """Emit a compact websocket event for a batch turn.  Best-effort; never raises."""
    try:
        payload = _agent_edit_turn_event_payload(
            state, context, turn_record, entry_type=entry_type, status=status
        )
        _ws_send("vibecomfy.agent_edit.turn", payload, client_id=client_id)
    except Exception:
        LOGGER.debug("emit agent-edit turn event failed (best-effort)", exc_info=True)


__all__ = [
    "AgentEditState",
    "DeepSeekClient",
    "handle_agent_edit",
]
'''
