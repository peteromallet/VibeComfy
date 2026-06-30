# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Batch REPL setup, prompt assembly, provider calls, and first clarify rejection branch.

SOURCE = r'''
_BATCH_PROTOCOL_RETRY_PROMPT = """Your previous response could not be applied because it did not include a valid batch block.

Reply in exactly this format:

One short sentence for the user.
```batch
# one or more edit statements, or clarify("question"), or done()
```

If you cannot safely edit the graph, still use the same format and put your question or blocker inside `clarify("...")` in the batch block.
Do not include markdown other than the single batch block."""


def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
    detail: dict[str, str] = {}
    parse_reason = getattr(exc, "parse_reason", None)
    if isinstance(parse_reason, str) and parse_reason.strip():
        detail["parse_reason"] = parse_reason.strip()
    raw_preview = getattr(exc, "raw_response_preview", None)
    if isinstance(raw_preview, str) and raw_preview.strip():
        detail["raw_response_preview"] = raw_preview.strip()
    return detail


def _batch_protocol_parse_reason(exc: BaseException) -> str:
    explicit = getattr(exc, "parse_reason", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    text = str(exc).lower()
    if "empty" in text:
        return "empty"
    if "multiple" in text:
        return "multiple_batch_fences"
    if "must be a string" in text or "non_string" in text:
        return "non_string"
    if "batch fenced block" in text or "batch code block" in text:
        return "missing_batch_fence"
    return "malformed"


def _batch_protocol_retry_messages(
    messages: list[dict[str, str]],
    exc: BaseException | None = None,
) -> list[dict[str, str]]:
    prompt = _BATCH_PROTOCOL_RETRY_PROMPT
    if exc is not None:
        detail = _malformed_model_json_detail(exc)
        raw_preview = detail.get("raw_response_preview")
        if raw_preview:
            prompt = (
                f"{prompt}\n\n"
                "Previous response preview, for correction only:\n"
                f"{raw_preview}"
            )
    return [*messages, {"role": "system", "content": prompt}]


def _evaluate_execution_plan_after_candidate_update(state: AgentEditState) -> dict[str, Any]:
    if getattr(state, "execution_plan", None) is None:
        return {}
    if not isinstance(state.ui_payload, Mapping):
        return {}
    update = evaluate_execution_plan_for_state(
        state,
        state.ui_payload,
        candidate_graph_hash=structural_graph_hash(state.ui_payload),
    )
    return dict(update.compact_status or {})


def _execution_plan_status_for_prompt(state: AgentEditState) -> dict[str, Any]:
    if getattr(state, "execution_plan", None) is None:
        return {}
    return format_compact_plan_status(state.execution_plan, state.plan_evaluation)


def _execution_plan_done_refusal_hint(state: AgentEditState) -> str:
    evaluation = getattr(state, "plan_evaluation", None)
    if evaluation is None:
        return "the execution plan has not been evaluated yet."
    missing_step_ids = [
        str(status.get("step_id") or "unknown_step")
        for status in getattr(evaluation, "step_status", ()) or ()
        if isinstance(status, Mapping)
        and str(status.get("criticality") or "required") != "optional"
        and str(status.get("status") or "") != "satisfied"
    ]
    failed_condition_ids = [
        str(condition.get("condition_id") or condition.get("id") or "unknown_condition")
        for condition in getattr(evaluation, "failed_conditions", ()) or ()
        if isinstance(condition, Mapping)
    ]
    parts = [
        "the authoritative execution plan still blocks completion.",
        f"plan_id={getattr(evaluation, 'plan_id', 'unknown')}",
    ]
    if missing_step_ids:
        parts.append(
            "missing required execution-plan step ids: "
            + ", ".join(missing_step_ids)
        )
    if failed_condition_ids:
        parts.append(
            "failed execution-plan condition ids: "
            + ", ".join(failed_condition_ids)
        )
    feedback = str(getattr(evaluation, "feedback", "") or "").strip()
    if feedback:
        parts.append(feedback)
    parts.append(
        "Fix the missing planned graph structure and call done() again."
    )
    return " ".join(parts)


_MAX_EXECUTION_PROTOCOL_SOURCES = 3
_MAX_EXECUTION_PROTOCOL_LIST_ITEMS = 16
_MAX_EXECUTION_PROTOCOL_STRING = 900


def _compact_protocol_string(value: Any, *, limit: int = _MAX_EXECUTION_PROTOCOL_STRING) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 18)].rstrip() + "\n... [truncated]"


def _compact_protocol_list(value: Any, *, limit: int = _MAX_EXECUTION_PROTOCOL_LIST_ITEMS) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    compacted: list[Any] = []
    for item in value[:limit]:
        if isinstance(item, str):
            compacted.append(_compact_protocol_string(item, limit=240))
        elif isinstance(item, (int, float, bool)) or item is None:
            compacted.append(item)
        else:
            compacted.append(_compact_protocol_string(item, limit=240))
    if len(value) > limit:
        compacted.append(f"... [{len(value) - limit} omitted]")
    return compacted


def _copy_compact_protocol_fields(
    source: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    string_limit: int = _MAX_EXECUTION_PROTOCOL_STRING,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if isinstance(value, str):
            result[key] = _compact_protocol_string(value, limit=string_limit)
        elif isinstance(value, (list, tuple)):
            result[key] = _compact_protocol_list(value)
        elif isinstance(value, Mapping):
            result[key] = {
                str(k): (
                    _compact_protocol_string(v, limit=240)
                    if isinstance(v, str)
                    else v
                )
                for k, v in list(value.items())[:12]
                if not isinstance(v, (dict, list, tuple))
            }
        elif value is not None:
            result[key] = value
    return result


def _compact_research_source_for_prompt(source: Any) -> dict[str, Any] | None:
    if not isinstance(source, Mapping):
        return None
    compact = _copy_compact_protocol_fields(
        source,
        (
            "source",
            "source_type",
            "pack",
            "class_type",
            "name",
            "title",
            "url",
            "source_workflow_path",
            "description",
            "summary",
            "node_types",
            "workflow_schema_classes",
            "terminal_output_path",
            "minimal_spine",
            "model_families",
            "models",
            "reasons",
            "requested_terms",
            "promotion_gates",
        ),
    )
    if "workflow_schema" in source:
        schema = source.get("workflow_schema")
        if isinstance(schema, Mapping):
            compact["workflow_schema_classes"] = _compact_protocol_list(
                list(schema.keys()),
                limit=_MAX_EXECUTION_PROTOCOL_LIST_ITEMS,
            )
            compact["workflow_schema_omitted"] = (
                "omitted from prompt; exact classes are provisional authoring evidence when surfaced in signatures"
            )
    return compact or None


def _compact_execution_protocol_notes_for_prompt(notes: Mapping[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "research_goal",
        "workflow_precedent_status",
        "research_warnings",
    ):
        if key in notes:
            value = notes.get(key)
            if isinstance(value, str):
                compact[key] = _compact_protocol_string(value)
            elif isinstance(value, (list, tuple)):
                compact[key] = _compact_protocol_list(value, limit=8)
            else:
                compact[key] = value

    selected = notes.get("selected_precedent")
    if isinstance(selected, Mapping):
        compact["selected_precedent"] = _copy_compact_protocol_fields(
            selected,
            (
                "name",
                "source",
                "source_workflow_path",
                "minimal_spine",
                "terminal_output_path",
                "model_families",
                "models",
                "reasons",
                "requested_terms",
                "promotion_gates",
            ),
        )

    sources = notes.get("research_sources")
    if isinstance(sources, (list, tuple)):
        compact_sources: list[dict[str, Any]] = []
        for source in sources[:_MAX_EXECUTION_PROTOCOL_SOURCES]:
            compact_source = _compact_research_source_for_prompt(source)
            if compact_source:
                compact_sources.append(compact_source)
        if compact_sources:
            compact["research_sources"] = compact_sources
        if len(sources) > _MAX_EXECUTION_PROTOCOL_SOURCES:
            compact["research_sources_omitted"] = len(sources) - _MAX_EXECUTION_PROTOCOL_SOURCES

    for key, value in notes.items():
        if key in compact or key in {
            "_discardability",
            "selected_precedent",
            "research_sources",
            "research_goal",
            "workflow_precedent_status",
            "research_warnings",
        }:
            continue
        if isinstance(value, str):
            compact[key] = _compact_protocol_string(value, limit=500)
        elif isinstance(value, (list, tuple)):
            compact[key] = _compact_protocol_list(value, limit=8)
        elif isinstance(value, (int, float, bool)) or value is None:
            compact[key] = value
    return compact


def _stage_agent_batch_repl(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from vibecomfy.porting.edit import session as edit_session_module

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    _hydrate_research_precedent_node_schemas(state)
    session = edit_session_module.EditSession(prepared_ui, schema_provider=state.schema_provider)
    state.batch_session = session
    initial_render = session.render()
    present_types = _present_class_types(session)
    focus_types = set(present_types)
    effective_task = _effective_implementation_task(state)
    focus_types.update(_seed_focus_types_for_authoring(state))
    focus_types.update(
        _workflow_class_types_from_research_context(
            state,
            max_classes=32,
            missing_only=False,
            custom_only=False,
        )
    )
    focus_types.update(_focus_types_from_research_brief(state.executor_research_brief))
    if _is_code_node_intent(effective_task):
        focus_types.add("vibecomfy.exec")
    signature_catalog = session.search(focus_types=sorted(focus_types), formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

    classification = (
        state.request_payload.get("executor_classification")
        if isinstance(state.request_payload, dict)
        else None
    )
    intent = classification.get("intent") if isinstance(classification, dict) else ""
    # explain_graph intent now maps to the executor inspect route, which
    # never reaches the agent-edit pipeline.  Keep the text-pattern fallback
    # for revise / adapt operations where the task reads like a graph
    # explanation (provides helpful context in the batch-REPL prompt).
    prefetch_explain = not intent and _is_graph_explain_intent(effective_task)
    prefetch_research_summary = state.executor_research_summary or (
        _prefetch_research_summary(effective_task) if prefetch_explain else ""
    )
    research_brief_prompt = _format_research_brief_for_prompt(state.executor_research_brief)
    if prefetch_research_summary and state.executor_research_warnings:
        warning_lines = [
            f"- {warning}" for warning in state.executor_research_warnings[:6]
        ]
        prefetch_research_summary = (
            f"{prefetch_research_summary}\n\n"
            "Research warnings:\n"
            + "\n".join(warning_lines)
        )
    if prefetch_research_summary and state.executor_research_sources:
        source_lines = [
            json.dumps(source, sort_keys=True)
            for source in state.executor_research_sources[:8]
        ]
        prefetch_research_summary = (
            f"{prefetch_research_summary}\n\n"
            "Structured research sources (JSON lines):\n"
            + "\n".join(source_lines)
        )
    prefetch_graph_report = (
        state.graph_inspection
        or (_build_graph_report(state.graph) if prefetch_explain else "")
    )
    # Build compact adaptation plan prompt for adapt route.
    precedent_adaptation_prompt = ""
    adapt_scoped_research_context = ""
    canonical_route = _canonical_agent_edit_route(state.route or route)
    research_only_route = canonical_route == "research"
    if canonical_route == "adapt":
        if state.executor_adaptation_plan:
            precedent_adaptation_prompt = _build_precedent_adaptation_prompt(
                state.executor_adaptation_plan,
                state.executor_precedent_slices,
            )
        # SD3: scoped adapt prefetch from execution_protocol_notes and
        # research_context_packet — discardable, evidence-only context.
        if (
            state.execution_protocol_notes
            or state.research_context_packet
            or state.graph_facts
            or state.graph_inspection
        ):
            parts: list[str] = []
            discard_note: str | None = None
            if state.execution_protocol_notes:
                notes = dict(state.execution_protocol_notes)
                discard_note = notes.pop("_discardability", None)
                notes = _compact_execution_protocol_notes_for_prompt(notes)
                notes_str = json.dumps(notes, indent=2, sort_keys=True)
                authority_line = (
                    str(discard_note).strip()
                    if isinstance(discard_note, str) and discard_note.strip()
                    else "This is contextual evidence, NOT authoritative guidance."
                )
                parts.append(
                    "## Scoped Research Context (execution_protocol_notes)\n"
                    f"{authority_line}\n"
                    f"{notes_str}"
                )
            has_selected_precedent = False
            if isinstance(state.execution_protocol_notes, Mapping):
                has_selected_precedent = isinstance(
                    state.execution_protocol_notes.get("selected_precedent"),
                    Mapping,
                )
            if state.research_context_packet and not has_selected_precedent:
                packet_str = json.dumps(
                    state.research_context_packet, indent=2, sort_keys=True
                )
                parts.append(
                    "## Research Context Packet (discardable)\n"
                    "Precedent evidence from research phase. "
                    "Discard if empty, irrelevant, or contradictory.\n"
                    f"{packet_str}"
                )
            # SD2: compact graph facts from topology/readiness collectors.
            if state.graph_facts:
                facts_str = json.dumps(state.graph_facts, indent=2, sort_keys=True)
                parts.append(
                    "## Graph Facts (workflow topology evidence)\n"
                    "Deterministic topology/readiness evidence about the current graph. "
                    "Use this to understand the workflow structure, terminal outputs, "
                    "and any known blockers. NOT a revision verdict.\n"
                    f"{facts_str}"
                )
            if state.graph_inspection:
                parts.append(
                    "## Graph Inspection (current graph evidence)\n"
                    "Deterministic node/widget evidence from the attached current graph. "
                    "Use this to identify existing editable nodes before asking for more precedent.\n"
                    f"{state.graph_inspection}"
                )
            if discard_note:
                parts.append(f"**Discardability**: {discard_note}")
            adapt_scoped_research_context = "\n\n".join(parts)

    max_batches = max(1, int(state.batch_max_turns or 1))
    max_consecutive_errors = max(1, int(state.batch_max_consecutive_errors or 1))
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches,
        "remaining_consecutive_errors": max_consecutive_errors,
    }
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "revision_evidence": str(state.revision_evidence_path),
        "messages": str(state.messages_path),
    }

    current_render = initial_render
    last_diff = ""
    last_report = ""
    last_landed_count: int | None = None
    previous_model_message = ""
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    done_candidate_rejection_nudges = 0
    failed_edit_turns = 0
    last_failed_edit_turn = -1
    last_successful_edit_turn_after_failure = -1
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = _format_node_variable_index(session)
        research_memory = _batch_research_memory_summary(state)
        turn_research_summary = prefetch_research_summary if turn_number == 0 else ""
        if research_memory:
            turn_research_summary = (
                f"{turn_research_summary}\n\nPrior research/query memory:\n{research_memory}"
            ).strip()
        execution_plan_status = _execution_plan_status_for_prompt(state)
        messages = build_batch_messages(
            task=effective_task,
            turn_number=turn_number,
            python_source=(initial_render if turn_number == 0 else current_render)
            if include_full_render
            else "",
            node_variable_index=node_variable_index,
            previous_model_message=previous_model_message,
            signature_catalog=state.batch_signature_catalog if turn_number == 0 else "",
            available_node_names=available_node_names if turn_number == 0 else "",
            diff=last_diff,
            report=last_report,
            budget_remaining=budget_remaining,
            max_batches=max_batches,
            conversation_messages=conversation_messages if turn_number == 0 else None,
            research_only=research_only_route,
            research_brief=research_brief_prompt if turn_number == 0 else "",
            research_summary=turn_research_summary,
            graph_report=prefetch_graph_report if turn_number == 0 else "",
            precedent_adaptation_plan=(
                (precedent_adaptation_prompt + "\n\n" + adapt_scoped_research_context).strip()
                if turn_number == 0
                else ""
            ),
            revision_evidence_json=_revision_evidence_prompt_json(state)
            if turn_number == 0
            else "",
            execution_plan_status=execution_plan_status,
        )
        request_entry = {
            "turn_number": turn_number,
            "messages": messages,
            "budget_remaining": budget_remaining,
            "node_variable_index": node_variable_index,
            "included_full_render": include_full_render,
        }
        request_log.append(request_entry)
        write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        try:
            try:
                if deepseek_client is not None:
                    turn_result = _normalize_test_client_batch_response(deepseek_client(messages))
                else:
                    turn_result = run_agent_turn_batch(
                        state.task,
                        messages,
                        route=route,
                        model=model,
                    )
            except (MalformedModelJSON, MissingRequiredField) as first_exc:
                retry_messages = _batch_protocol_retry_messages(messages, first_exc)
                first_detail = _malformed_model_json_detail(first_exc)
                retry_request_entry = {
                    "turn_number": turn_number,
                    "messages": retry_messages,
                    "budget_remaining": budget_remaining,
                    "node_variable_index": node_variable_index,
                    "included_full_render": include_full_render,
                    "protocol_retry": {
                        "attempt": 2,
                        "reason": _batch_protocol_parse_reason(first_exc),
                        "message": str(first_exc),
                    },
                }
                request_log.append(retry_request_entry)
                write_json_artifact(
                    state.model_request_path,
                    {"response_contract": "batch_repl", "turns": request_log},
                )
                response_log.append(
                    {
                        "turn_number": turn_number,
                        "error": {
                            "type": type(first_exc).__name__,
                            "message": str(first_exc),
                            "parse_reason": _batch_protocol_parse_reason(first_exc),
                            "retrying": True,
                            "attempt": 1,
                            **first_detail,
                        },
                    }
                )
                write_json_artifact(state.model_response_path, {"turns": response_log})
                if deepseek_client is not None:
                    turn_result = _normalize_test_client_batch_response(deepseek_client(retry_messages))
                else:
                    turn_result = run_agent_turn_batch(
                        state.task,
                        retry_messages,
                        route=route,
                        model=model,
                    )
                retry_metadata = dict(turn_result.audit_metadata or {})
                retry_metadata["batch_repl_protocol_retry"] = {
                    "count": 1,
                    "reason": str(first_exc),
                    "parse_reason": _batch_protocol_parse_reason(first_exc),
                }
                turn_result = dataclasses.replace(
                    turn_result,
                    audit_metadata=retry_metadata,
                )
        except (MalformedModelJSON, MissingRequiredField) as exc:
            parse_reason = _batch_protocol_parse_reason(exc)
            exc_detail = _malformed_model_json_detail(exc)
            malformed_diagnostic = {
                "code": "malformed_batch_response",
                "severity": "error",
                "parse_reason": parse_reason,
                "attempt_count": 2,
                "turn_number": turn_number,
                "response_contract": "batch_repl",
                **exc_detail,
            }
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                **exc_detail,
                "diagnostics": [malformed_diagnostic],
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "parse_reason": parse_reason,
                        "retrying": False,
                        "attempt": 2,
                        **exc_detail,
                        "diagnostics": [
                            malformed_diagnostic,
                        ],
                    },
                }
            )
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            state.batch_exit_mode = "protocol_failure"
            state.batch_final_summary = (
                "Stopped because the model did not return a valid batch_repl response."
            )
            if state.batch_turns:
                _emit_agent_edit_turn_event(
                    state,
                    _context,
                    state.batch_turns[-1],
                    client_id=client_id,
                    status="error",
                )
            raise
        except Exception as exc:
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            raise

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        previous_model_message = turn_result.message
        clarify_split = split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "status": "received",
            }
        )
        write_json_artifact(state.model_response_path, {"turns": response_log})
        if clarify_message is not None and not editable_batch.strip():
            clarify_feedback = (
                _premature_workflow_schema_clarify_feedback(
                    state,
                    clarify_message,
                )
                or _premature_missing_custom_node_clarify_feedback(
                    state,
                    clarify_message,
                )
                or _direct_existing_parameter_tweak_feedback(
                    state,
                    clarify_message,
                )
            )
            if clarify_feedback:
                consecutive_errors += 1
                turn_record = {
                    "turn_number": turn_number,
                    "batch": turn_result.batch,
                    "message": turn_result.message,
                    "route": turn_result.route,
                    "model": turn_result.model,
                    "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
                    "batch_ok": False,
                    "landed_op_count": 0,
                    "raw_landed_op_count": 0,
                    "statement_count": 1,
                    "diagnostics": [
                        {
                            "code": "premature_missing_custom_node_clarify",
                            "message": clarify_feedback,
                            "severity": "error",
                        }
                    ],
                    "report": clarify_feedback,
                    "field_changes": [],
                }
                state.batch_turns.append(turn_record)
                state.batch_feedback = clarify_feedback
                state.batch_turn_count = turn_number + 1
                state.batch_budget_state = {
                    "max_batches": max_batches,
                    "max_consecutive_errors": max_consecutive_errors,
                    "remaining_batches": max_batches - state.batch_turn_count,
                    "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                    "consecutive_errors": consecutive_errors,
                }
                response_log[-1] = {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "rejected_clarification": turn_record,
                }
                write_json_artifact(state.model_response_path, {"turns": response_log})
                state.messages_path.open("a", encoding="utf-8").write(
                    json.dumps(
                        {
                            "turn_number": turn_number,
                            "task": state.task,
                            "message": turn_result.message,
                            "batch": turn_result.batch,
'''
