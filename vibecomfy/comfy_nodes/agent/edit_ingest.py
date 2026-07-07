# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Ingest, conversion, project, and direct provider stages.

SOURCE = r'''
def _record(context: TurnContext, result: StageResult) -> StageResult:
    context.stage_results[result.stage] = result
    apply_stage_gate_updates(context, result)
    return result


def _stamp_identity_on_original(graph: dict[str, Any], workflow: Any) -> int:
    """Phase 1 (concrete-tree migration): stamp the IR's stable uid onto the
    *original* UI nodes so the delta-scope guard (`guard_emit`) and pin-opaque
    can match on a user's FIRST edit. A hand-authored ComfyUI canvas carries no
    `properties.vibecomfy_uid`, so `guard_emit`'s scope (uids shared between the
    original and the candidate) is otherwise empty and the whole preserve/guard
    layer no-ops (blockers.md B12). The candidate inherits these same uids from
    the IR, so stamping the original makes the scope non-empty.

    See docs/agent-edit/concrete-tree.md. Match is by litegraph node id, which is
    stable across the round-trip.
    """
    by_id = {str(nid): node for nid, node in getattr(workflow, "nodes", {}).items()}
    stamped = 0
    for ui_node in graph.get("nodes") or []:
        if not isinstance(ui_node, dict):
            continue
        ir = by_id.get(str(ui_node.get("id")))
        uid = getattr(ir, "uid", "") if ir is not None else ""
        if not uid:
            continue
        props = ui_node.get("properties")
        if not isinstance(props, dict):
            props = {}
            ui_node["properties"] = props
        if not props.get("vibecomfy_uid"):
            props["vibecomfy_uid"] = uid
            stamped += 1
    return stamped


def _stale_rebaseline_recovery_issue(
    state: AgentEditState,
    gate_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "stale_state_recovery",
        "last_known_baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
        "client_structural_graph_hash": state.submitted_client_structural_graph_hash,
    }
    return {
        "code": "stale_state_mismatch",
        "severity": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "message": "Submitted graph no longer matches the current baseline.",
        "detail": dict(gate_evidence),
        "rebaseline_recovery": recovery,
    }


def _stage_ingest(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout_store import store_from_ui_json

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)
    state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
    state.prior_store = store_from_ui_json(state.graph)
    # Phase 1 (concrete-tree migration, docs/agent-edit/concrete-tree.md): give the
    # user's original graph stable identity so the delta-scope guard (guard_emit)
    # engages on the FIRST edit. Stamp a COPY — never mutate state.graph, which is
    # hashed/echoed/audited. The candidate inherits the same uids (verified: uid ==
    # node id, preserved across the scratchpad round-trip), so the guard scope
    # becomes non-empty.
    #
    # Gated OFF by default: with the guard engaged but the candidate still produced
    # by the LOSSY regeneration path (Phase 2 not yet landed), guard_emit correctly
    # refuses candidates that diverge from the original outside the intended delta.
    # Enabling identity is therefore only safe once Phase 2 (verbatim-preserve)
    # makes the candidate faithful. Toggle with VIBECOMFY_AGENT_EDIT_IDENTITY=1.
    if os.getenv("VIBECOMFY_AGENT_EDIT_IDENTITY") == "1":
        from copy import deepcopy as _deepcopy
        guard_original = _deepcopy(state.graph)
        _stamp_identity_on_original(guard_original, state.workflow)
        state.guard_original_ui = guard_original
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
    )


def _stage_ingest_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.ledger import EditLedger

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    # The EditLedger walks a UI ``nodes`` array. An API-format (compiled_api)
    # source has no ``nodes`` key, so every edit op would die on ``stale_graph_name``
    # ("uid no longer present"). When the source is not already UI format,
    # re-serialize the canonical VibeWorkflow (which ingests both formats) to a UI
    # envelope so the ledger sees the nodes. UI-format inputs already have ``nodes``
    # and are left untouched — re-serializing them is lossy and breaks the path that
    # already works. ``state.graph`` is hashed/echoed/audited, so all downstream
    # consumers share this one canonical view.
    from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape
    from vibecomfy.porting.emit.ui import emit_ui_json

    if detect_workflow_shape(state.graph) != "ui":
        state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
        state.graph = emit_ui_json(
            state.workflow,
            schema_provider=state.schema_provider,
            guard_original_ui=state.graph,
        )
    ledger = EditLedger.ingest(state.graph)
    state.guard_original_ui = ledger.stamped_copy()
    original_ui_ref = write_json_artifact(state.original_ui_path, state.guard_original_ui)
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
        issues=tuple(issue.to_dict() for issue in ledger.diagnostics),
        value={
            "mode": "agent_edit_v2_delta",
            "node_count": len(ledger.node_index),
            "scope_count": len(ledger.scopes),
        },
    )


def _stage_convert(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow

    start = time.monotonic()
    conversion = port_convert_workflow(
        state.workflow,
        source_path=str(state.original_ui_path),
        schema_provider=state.schema_provider,
        raw_workflow=state.graph,
        # Editing a user's live canvas must preserve every node. Dead-branch
        # pruning is for authoring minimal templates; here it would silently
        # drop nodes that don't feed a recognized output (e.g. a GeminiNode
        # feeding only a PreviewAny passthrough) and corrupt the round-trip.
        prune_dead_branches=False,
    )
    # Keep the strict parity gate: with prune disabled + UI-only passthrough
    # preservation (emitter), a faithful user canvas round-trips and passes here,
    # while a genuinely-lossy conversion still fails honestly rather than applying
    # a corrupted candidate.
    port_convert_and_write(conversion, state.before_py_path)
    state.python_before = state.before_py_path.read_text(encoding="utf-8")
    return StageResult(
        stage="convert",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.before_py_path),),
    )


def _stage_project_v2(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.projection import ProjectionOptions, render_edit_projection

    start = time.monotonic()
    # The 8000-token default forces sparse mode on every real ComfyUI graph (140-200+
    # nodes), collapsing all nodes to summaries and starving the model of the field
    # names / slot types it needs to target edits and wire links correctly. Modern
    # models have 64K+ context, so render real graphs in FULL detail. Env-overridable.
    try:
        _proj_budget = int(os.getenv("VIBECOMFY_EDIT_PROJECTION_MAX_TOKENS", "256000"))
    except (TypeError, ValueError):
        _proj_budget = 256000
    projection = render_edit_projection(
        state.guard_original_ui or state.graph,
        task=state.task,
        schema_provider=state.schema_provider,
        options=ProjectionOptions(max_tokens=_proj_budget),
    )
    state.projection_text = projection.text
    state.projection_path.write_text(projection.text, encoding="utf-8")
    return StageResult(
        stage="project",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.projection_path),),
        value={
            "token_estimate": projection.token_estimate,
            "node_count": projection.node_count,
            "detailed_node_count": projection.detailed_node_count,
            "truncated": projection.truncated,
        },
    )


def _stage_agent(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    start = time.monotonic()
    messages = build_messages(task=state.task, python_source=state.python_before, execution_mode="sandboxed_loose")
    write_json_artifact(state.model_request_path, {"messages": messages})
    if deepseek_client is not None:
        agent_result = _normalize_test_client_response(
            deepseek_client(messages)
        )
    else:
        agent_result = run_agent_turn(
            state.task,
            state.python_before,
            route=route,
            model=model,
        )
    state.python_after = agent_result.python
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "provider_metadata": state.provider_metadata,
        },
    )


def _stage_agent_delta(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        EDIT_OP_RESPONSE_SCHEMA_V2,
        EditOpParseError,
        ensure_root_scoped_delta_envelope,
        normalize_delta_test_client_response,
        op_to_dict,
    )

    start = time.monotonic()
    messages = build_delta_messages(
        task=state.task,
        projection=state.projection_text,
        op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
    )
    write_json_artifact(
        state.model_request_path,
        {"messages": messages, "response_contract": "delta"},
    )
    if deepseek_client is not None:
        agent_result = normalize_delta_test_client_response(deepseek_client(messages))
    else:
        agent_result = run_agent_turn_delta(
            state.task,
            state.projection_text,
            op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
            route=route,
            model=model,
        )
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    try:
        delta_envelope = ensure_root_scoped_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [op_to_dict(op) for op in agent_result.delta],
            },
            strict=False,
        )
    except EditOpParseError as exc:
        issue = {
            "code": exc.code,
            "message": str(exc),
            "severity": "error",
        }
        if isinstance(exc.detail, Mapping) and exc.detail:
            issue["detail"] = dict(exc.detail)
        model_response_ref = write_json_artifact(
            state.model_response_path,
            {
                "message": agent_result.message,
                "route": agent_result.route,
                "model": agent_result.model,
                "audit_metadata": state.provider_metadata,
                "delta_error": issue,
            },
        )
        state.delta_diagnostics = [dict(issue)]
        return StageResult(
            stage="agent_delta",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(_artifact(state.model_request_path), model_response_ref),
            issues=(issue,),
            value={
                "failure_kind": FailureKind.VALIDATION_ERROR.value,
                "op_count": len(agent_result.delta),
                "provider_metadata": state.provider_metadata,
            },
        )

    state.delta_ops = delta_envelope.ops
    delta_payload = delta_envelope.to_dict()
    model_response_ref = write_json_artifact(
        state.model_response_path,
        {
            "delta": list(delta_payload["ops"]),
            "delta_ops_envelope": delta_payload,
            "message": agent_result.message,
            "route": agent_result.route,
            "model": agent_result.model,
            "audit_metadata": state.provider_metadata,
        },
    )
    return StageResult(
        stage="agent_delta",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "op_count": len(agent_result.delta),
            "provider_metadata": state.provider_metadata,
        },
    )


_RESEARCH_TRIGGER_TERMS = (
    "look up", "lookup", "research", "find out", "how does", "how do", "what is",
    "what are", "explain how", "how can", "how to", "information about",
)

_GRAPH_EXPLAIN_TRIGGER_TERMS = (
    "what's happening", "what is happening", "what's going on", "what is going on",
    "explain this graph", "explain the graph", "describe this graph",
    "describe the graph", "analyze this graph", "analyze the graph",
    "inspect this graph", "inspect the graph", "what does this graph do",
)

_CODE_NODE_TRIGGER_TERMS = (
    "code node",
    "python",
    "pil",
    "pillow",
    "custom image-processing",
    "custom image processing",
    "process images",
    "image processing",
)


def _task_mentions_any(task: str, terms: tuple[str, ...]) -> bool:
    lowered = task.lower()
    return any(term in lowered for term in terms)


def _is_research_intent(task: str) -> bool:
    return _task_mentions_any(task, _RESEARCH_TRIGGER_TERMS)


'''
