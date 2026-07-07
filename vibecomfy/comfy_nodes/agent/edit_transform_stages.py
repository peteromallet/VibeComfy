# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Python load, lower, validate, emit, delta apply, summarize, and audit stages.

SOURCE = r'''
def _stage_load_python(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad

    start = time.monotonic()
    state.after_py_path.write_text(state.python_after, encoding="utf-8")
    state.edited_workflow = load_agent_generated_scratchpad(state.after_py_path)
    return StageResult(
        stage="load_python",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.after_py_path),),
        gate_updates={"python_load_ok": True},
    )


def _stage_lower(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.lowering import lower_workflow

    start = time.monotonic()
    original_workflow = state.edited_workflow
    lowering = lower_workflow(state.edited_workflow, schema_provider=state.schema_provider)
    result = lower_stage_result(lowering)
    if result.ok:
        if lowering.lowered_count > 0:
            if lowering.workflow is not None:
                state.edited_workflow = lowering.workflow
            state.original_intent_workflow = original_workflow
        else:
            state.edited_workflow = original_workflow
        state.lowering_evidence = [dict(dataclasses.asdict(item)) for item in lowering.evidence]
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_validate(state: AgentEditState, _context: TurnContext) -> StageResult:
    from .diagnostics import validate_stage_result

    start = time.monotonic()
    result = validate_stage_result(state.edited_workflow, schema_provider=state.schema_provider)
    if result.blocking:
        validation_issues: list[ValidationIssue] = []
        for issue in result.issues:
            if not isinstance(issue, Mapping):
                continue
            detail = issue.get("detail")
            validation_issues.append(
                ValidationIssue(
                    code=str(issue.get("code", "validation_error")),
                    message=str(issue.get("message", "Validation error.")),
                    severity=str(issue.get("severity", "error")),
                    detail=dict(detail) if isinstance(detail, Mapping) else {},
                )
            )
        if validation_issues:
            value = dict(result.value or {})
            value["validation_errors"] = validation_errors_payload(validation_issues)
            result = dataclasses.replace(result, value=value)
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_emit(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.emit.ui import emit_ui_json

    start = time.monotonic()
    recovery_report: list[dict[str, Any]] = []
    change_report_out: list[Any] = []
    ui_payload = emit_ui_json(
        state.edited_workflow,
        schema_provider=state.schema_provider,
        prior_store=state.prior_store,
        recovery_report=recovery_report,
        change_report_out=change_report_out,
        guard_original_ui=state.guard_original_ui or state.graph,
        guard_resolved_ops=state.emit_guard_resolved_ops,
        prior_ui_payload=state.guard_original_ui or state.graph,
    )
    state.candidate_ui_path.write_text(
        json.dumps(ui_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_store(state.after_py_path, store_from_ui_json(ui_payload))
    state.ui_payload = ui_payload

    reroute_uids = frozenset(
        (node.uid or node_id)
        for node_id, node in state.edited_workflow.nodes.items()
        if node.class_type == "Reroute"
    )
    felt_report = (
        evaluate_felt_delta(
            state.prior_store,
            ui_payload,
            change_report_out[0],
            reroute_uids=reroute_uids,
        )
        if change_report_out
        else None
    )
    state.report = {
        "change": dataclasses.asdict(change_report_out[0]) if change_report_out else {},
        "recovery": recovery_report,
        "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
    }
    _inject_lowering_provenance(state)
    return StageResult(
        stage="emit",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.candidate_ui_path),),
        gate_updates={
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    )


def _ensure_canonical_delta_ops(
    delta_ops: tuple[Any, ...],
    *,
    strict: bool = False,
) -> tuple[Any, ...]:
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        ensure_root_scoped_delta_envelope,
        op_to_dict,
    )

    envelope = ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [op_to_dict(op) for op in delta_ops],
        },
        strict=strict,
    )
    return envelope.ops


def _canonical_delta_ops_envelope_payload(
    delta_ops: tuple[Any, ...],
) -> dict[str, Any]:
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        ensure_root_scoped_delta_envelope,
        op_to_dict,
    )

    return ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [op_to_dict(op) for op in delta_ops],
        },
        strict=True,
    ).to_dict()


def _stage_apply_delta(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.apply import apply_delta
    from vibecomfy.porting.edit.apply import (
        AppliedAddNodeSpec,
        ResolvedFieldRef,
        ResolvedRemoveNodePlan,
    )
    from vibecomfy.porting.edit.ops import EditOpParseError

    def _build_delta_audit(result: Any) -> dict[str, Any]:
        automatic_link_removals: list[dict[str, Any]] = []
        re_stitches: list[dict[str, Any]] = []
        for op, resolved_op in result.resolved_ops:
            if isinstance(resolved_op, ResolvedFieldRef) and resolved_op.automatic_link_removal is not None:
                automatic_link_removals.append(
                    {
                        "scope_path": resolved_op.target.scope_path,
                        "uid": resolved_op.target.uid,
                        "field_path": resolved_op.target.field_path,
                        "link_id": resolved_op.automatic_link_removal,
                    }
                )
            elif isinstance(resolved_op, ResolvedRemoveNodePlan) and resolved_op.link_rewires:
                re_stitches.append(
                    {
                        "scope_path": resolved_op.node_ref.target.scope_path,
                        "uid": resolved_op.node_ref.target.uid,
                        "class_type": resolved_op.node_ref.class_type,
                        "link_rewrites": [
                            {
                                "scope_path": rewire.scope_path,
                                "link_id": rewire.link_id,
                                "old_origin_id": rewire.old_origin_id,
                                "new_origin_id": rewire.new_origin_id,
                                "new_origin_slot": rewire.new_origin_slot,
                            }
                            for rewire in resolved_op.link_rewires
                        ],
                    }
                )
            elif isinstance(resolved_op, AppliedAddNodeSpec):
                continue
        guard = result.guard_result
        guard_payload = {
            "ok": bool(guard.ok) if guard is not None else True,
            "diagnostics": [
                _port_issue_to_dict(issue) for issue in (guard.diagnostics if guard is not None else ())
            ],
        }
        normalize_payload = {
            "fallback_used": bool(getattr(guard, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(guard, "normalize_allow_list_used", False)),
        }
        return {
            "diagnostics": [_port_issue_to_dict(issue) for issue in result.diagnostics],
            "automatic_link_removals": automatic_link_removals,
            "re_stitches": re_stitches,
            "guard_result": guard_payload,
            "normalize": normalize_payload,
        }

    start = time.monotonic()
    state.delta_audit = None

    try:
        state.delta_ops = _ensure_canonical_delta_ops(state.delta_ops)
    except EditOpParseError as exc:
        issue = {
            "code": exc.code,
            "message": str(exc),
            "severity": "error",
        }
        if isinstance(exc.detail, Mapping) and exc.detail:
            issue["detail"] = _json_safe(dict(exc.detail))
        state.delta_diagnostics = [dict(issue)]
        return StageResult(
            stage="apply_delta",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            issues=(issue,),
            value={
                "failure_kind": FailureKind.VALIDATION_ERROR.value,
                "mutation_started": 0,
                "op_count": len(state.delta_ops),
            },
        )

    # ── lint gate (VIBECOMFY_AGENT_EDIT_LINT defaults ON) ──────────────────
    original_ui = state.guard_original_ui or state.graph
    if _edit_lint_enabled() and state.delta_ops:
        from vibecomfy.porting.edit.lint import LintIndex, lint_delta

        index = LintIndex.build(original_ui)
        lint_result = lint_delta(
            state.delta_ops,
            index,
            schema_provider=state.schema_provider,
        )

        def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
            return {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
                "op_index": getattr(issue, "op_index", None),
                "op_kind": getattr(issue, "op_kind", None),
            }

        lint_issue_dicts = tuple(
            _lint_issue_to_dict(issue) for issue in lint_result.issues
        )

        # Rejected ops → fail before mutation
        if lint_result.rejected_count > 0:
            error_issues = tuple(
                i for i in lint_issue_dicts if i.get("severity") == "error"
            )
            return StageResult(
                stage="apply_delta",
                ok=False,
                blocking=True,
                duration_ms=_duration_ms(start),
                issues=error_issues or lint_issue_dicts,
                value={
                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
                    "mutation_started": 0,
                    "op_count": len(state.delta_ops),
                    "lint_rejected": lint_result.rejected_count,
                    "lint_dropped": lint_result.dropped_count,
                },
            )

        # All ops dropped as no-ops → clean no-op turn
        if lint_result.passed_count == 0:
            state.delta_ops = lint_result.surviving
            state.ui_payload = original_ui
            state.delta_diagnostics = [
                dict(d) for d in lint_issue_dicts
            ]
            delta_envelope = _canonical_delta_ops_envelope_payload(state.delta_ops)
            state.delta_audit = {
                "diagnostics": [dict(d) for d in lint_issue_dicts],
                "automatic_link_removals": [],
                "re_stitches": [],
                "guard_result": {"ok": True, "diagnostics": []},
                "normalize": {"fallback_used": False, "allow_list_used": False},
            }
            # Collect human-readable no-op messages for user-facing display
            _noop_msgs: list[str] = []
            for norm in lint_result.normalizations:
                if norm.disposition == "dropped_noop" and norm.issue is not None:
                    _noop_msgs.append(norm.issue.message)
            state.lint_noop_messages = tuple(_noop_msgs)
            state.report = {
                "change": {
                    "mode": "agent_edit_v2_delta",
                    "op_count": len(state.delta_ops),
                    "delta_ops_envelope": delta_envelope,
                    "ops": list(delta_envelope["ops"]),
                    "mutation_started": 0,
                    "lint_noop": True,
                },
                "recovery": [],
                "felt": {},
                "diagnostics": lint_issue_dicts,
            }
            return StageResult(
                stage="apply_delta",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                issues=lint_issue_dicts,
                value={
                    "mode": "agent_edit_v2_delta",
                    "op_count": 0,
                    "mutation_started": 0,
                    "lint_noop": True,
                    "lint_dropped": lint_result.dropped_count,
                },
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                },
            )

        # Surviving ops proceed to apply
        state.delta_ops = lint_result.surviving
        state.delta_lint = {
            "issues": [dict(d) for d in lint_issue_dicts],
            "dropped": lint_result.dropped_count,
            "rejected": lint_result.rejected_count,
            "passed": lint_result.passed_count,
        }

    result = apply_delta(
        original_ui,
        state.delta_ops,
        schema_provider=state.schema_provider,
    )
    state.emit_guard_resolved_ops = result.resolved_ops
    issues = tuple(_port_issue_to_dict(issue) for issue in result.diagnostics)
    if not result.ok or result.candidate is None:
        return StageResult(
            stage="apply_delta",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            issues=issues,
            value={
                "failure_kind": FailureKind.VALIDATION_ERROR.value,
                "mutation_started": result.mutation_started,
                "op_count": len(state.delta_ops),
            },
        )

    state.ui_payload = result.candidate
    candidate_ui_ref = write_json_artifact(state.candidate_ui_path, state.ui_payload)

    # Populate add_node ops with assigned uid/node_id from the resolved ops.
    from vibecomfy.porting.edit.ops import AddNodeOp as _AddNodeOp
    from vibecomfy.porting.edit.apply_types import AppliedAddNodeSpec as _AppliedAddNodeSpec

    _updated_ops: list[Any] = []
    _uid_node_id_by_index: dict[int, tuple[str, str]] = {}
    for _idx, (_op, _resolved) in enumerate(result.resolved_ops):
        if isinstance(_op, _AddNodeOp) and isinstance(_resolved, _AppliedAddNodeSpec):
            _uid_node_id_by_index[_idx] = (_resolved.uid, str(_resolved.node_id))
    _add_node_idx = 0
    for _op in state.delta_ops:
        if isinstance(_op, _AddNodeOp):
            _uid, _nid = _uid_node_id_by_index.get(_add_node_idx, (None, None))
            if _uid is not None and _nid is not None:
                _op = _AddNodeOp(
                    op=_op.op,
                    scope_path=_op.scope_path,
                    class_type=_op.class_type,
                    fields=dict(_op.fields),
                    inputs=dict(_op.inputs),
                    anchor=_op.anchor,
                    uid=_uid,
                    node_id=_nid,
                )
            _add_node_idx += 1
        _updated_ops.append(_op)
    state.delta_ops = tuple(_updated_ops)

    delta_envelope = _canonical_delta_ops_envelope_payload(state.delta_ops)
    ops = list(delta_envelope["ops"])
    state.delta_diagnostics = [_port_issue_to_dict(issue) for issue in result.diagnostics]
    state.guard_result = {
        "ok": bool(result.guard_result.ok) if result.guard_result is not None else True,
        "diagnostics": [
            _port_issue_to_dict(issue)
            for issue in (result.guard_result.diagnostics if result.guard_result is not None else ())
        ],
        "normalize": {
            "fallback_used": bool(getattr(result.guard_result, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(result.guard_result, "normalize_allow_list_used", False)),
        },
    }
    state.delta_audit = _build_delta_audit(result)
    state.report = {
        "change": {
            "mode": "agent_edit_v2_delta",
            "op_count": len(ops),
            "delta_ops_envelope": delta_envelope,
            "ops": ops,
            "mutation_started": result.mutation_started,
        },
        "recovery": [],
        "felt": {},
        "diagnostics": [issue for issue in issues if issue.get("severity") != "info"],
    }
    return StageResult(
        stage="apply_delta",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(candidate_ui_ref,),
        issues=issues,
        value={
            "mode": "agent_edit_v2_delta",
            "op_count": len(ops),
            "mutation_started": result.mutation_started,
        },
        gate_updates={
            "python_load_ok": True,
            "lower_ok": True,
            "ir_validate_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    )


def _stage_summarize(state: AgentEditState, context: TurnContext) -> StageResult:
    start = time.monotonic()
    recovery_report = _queue_recovery_report_for_candidate(
        ui_payload=state.ui_payload,
        schema_provider=state.schema_provider,
        original_ui_payload=state.graph,
        existing_recovery_report=(state.report or {}).get("recovery"),
    )
    if state.report is None:
        state.report = {}
    state.report["recovery"] = recovery_report
    queue_result = queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
    derive_gates(context, queue_blockers=queue_result.issues)
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _recovery_report_from_ui_payload(
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
    *,
    original_ui_payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a queue-diagnostics recovery report by re-resolving each UI node.

    The batch-REPL product path does not run ``emit_ui_json``, so it has no
    emit-time recovery report.  This fallback lets the final summarize stage
    still detect schema-less or low-confidence nodes before declaring the
    candidate queue-safe.
    """
    recovery: list[dict[str, Any]] = []
    if ui_payload is None or schema_provider is None:
        return recovery
    nodes = ui_payload.get("nodes")
    if not isinstance(nodes, list):
        return recovery
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return recovery

    def _connection_signature(node: Mapping[str, Any]) -> tuple[Any, ...]:
        inputs = node.get("inputs")
        outputs = node.get("outputs")

        def _input_signature(item: Any) -> tuple[Any, ...] | None:
            if not isinstance(item, Mapping):
                return None
            return (
                item.get("name"),
                item.get("type"),
                item.get("link"),
            )

        def _output_signature(item: Any) -> tuple[Any, ...] | None:
            if not isinstance(item, Mapping):
                return None
            links = item.get("links")
            if isinstance(links, list):
                links_sig: Any = tuple(links)
            else:
                links_sig = links
            return (
                item.get("name"),
                item.get("type"),
                item.get("slot_index"),
                links_sig,
            )

        return (
            tuple(
                sig
                for sig in (
                    _input_signature(item)
                    for item in (inputs if isinstance(inputs, list) else [])
                )
                if sig is not None
            ),
            tuple(
                sig
                for sig in (
                    _output_signature(item)
                    for item in (outputs if isinstance(outputs, list) else [])
                )
                if sig is not None
            ),
        )

    def _node_input_shape_signature(node: Mapping[str, Any]) -> tuple[Any, ...]:
        inputs = node.get("inputs")
        if not isinstance(inputs, list):
            return ()
        signature: list[tuple[Any, ...]] = []
        for item in inputs:
            if not isinstance(item, Mapping):
                continue
            signature.append((item.get("name"), item.get("type")))
        return tuple(signature)

    def _node_output_slots(node: Mapping[str, Any]) -> dict[tuple[Any, Any, Any], set[Any]]:
        outputs = node.get("outputs")
        slots: dict[tuple[Any, Any, Any], set[Any]] = {}
        if not isinstance(outputs, list):
            return slots
        for item in outputs:
            if not isinstance(item, Mapping):
                continue
            key = (item.get("name"), item.get("type"), item.get("slot_index"))
            links = item.get("links")
            slots[key] = set(links if isinstance(links, list) else [])
        return slots

    def _ui_links_by_id(ui_payload: Mapping[str, Any] | None) -> dict[Any, Any]:
        links = ui_payload.get("links") if isinstance(ui_payload, Mapping) else None
        if not isinstance(links, list):
            return {}
        result: dict[Any, Any] = {}
        for link in links:
            if isinstance(link, list) and link:
                result[link[0]] = link
            elif isinstance(link, Mapping) and "id" in link:
                result[link.get("id")] = link
        return result

    def _link_destination(link: Any) -> tuple[str, Any] | None:
        if isinstance(link, list) and len(link) >= 5:
            return (str(link[3]), link[4])
        if isinstance(link, Mapping):
            target_id = link.get("target_id", link.get("to_node"))
            target_slot = link.get("target_slot", link.get("to_slot"))
            if target_id is not None:
                return (str(target_id), target_slot)
        return None

    def _output_destinations(
        output_links: set[Any],
        links_by_id: Mapping[Any, Any],
    ) -> dict[tuple[str, Any], Any]:
        destinations: dict[tuple[str, Any], Any] = {}
        for link_id in output_links:
            destination = _link_destination(links_by_id.get(link_id))
            if destination is not None:
                destinations[destination] = link_id
        return destinations

    def _node_output_link_ids(node: Mapping[str, Any]) -> set[Any]:
        outputs = node.get("outputs")
        if not isinstance(outputs, list):
            return set()
        link_ids: set[Any] = set()
        for output in outputs:
            if not isinstance(output, Mapping):
                continue
            links = output.get("links")
            if isinstance(links, list):
                link_ids.update(links)
        return link_ids

    def _transitive_path_nodes_to_destination(
        *,
        start_links: set[Any],
        destination: tuple[str, Any],
        candidate_links_by_id: Mapping[Any, Any],
        candidate_nodes_by_id: Mapping[str, Mapping[str, Any]],
    ) -> tuple[str, ...] | None:
        queue: list[tuple[Any, tuple[str, ...]]] = [
            (link_id, ()) for link_id in sorted(start_links, key=lambda value: str(value))
        ]
        visited_links: set[Any] = set()
        while queue:
            link_id, path_nodes = queue.pop(0)
            if link_id in visited_links:
                continue
            visited_links.add(link_id)
            link = candidate_links_by_id.get(link_id)
            if link is None:
                continue
            current_destination = _link_destination(link)
            if current_destination is None:
                continue
            destination_node_id, _destination_slot = current_destination
            next_path = (*path_nodes, destination_node_id)
            if current_destination == destination:
                return next_path
            if destination_node_id in path_nodes:
                continue
            next_node = candidate_nodes_by_id.get(destination_node_id)
            if next_node is None:
                continue
            for next_link_id in sorted(_node_output_link_ids(next_node), key=lambda value: str(value)):
                if next_link_id not in visited_links:
                    queue.append((next_link_id, next_path))
        return None

    def _preexisting_schema_less_queue_safe(
        *,
        original_node: Mapping[str, Any] | None,
        candidate_node: Mapping[str, Any],
        original_links_by_id: Mapping[Any, Any],
        candidate_links_by_id: Mapping[Any, Any],
        candidate_node_ids: set[str],
        candidate_nodes_by_id: Mapping[str, Mapping[str, Any]],
        schema_less_transitive_intermediates: set[str],
    ) -> tuple[bool, str]:
        if original_node is None:
            candidate_node_id = str(candidate_node.get("id", ""))
            if candidate_node_id in schema_less_transitive_intermediates:
                return (True, "transitive_reroute_intermediate")
            return (False, "new_schema_less_node")
        if _connection_signature(original_node) == _connection_signature(candidate_node):
            return (True, "connection_shape_unchanged")
        if _node_input_shape_signature(original_node) != _node_input_shape_signature(candidate_node):
            return (False, "schema_less_inputs_changed")
        original_slots = _node_output_slots(original_node)
        candidate_slots = _node_output_slots(candidate_node)
        if set(original_slots) != set(candidate_slots):
            return (False, "schema_less_output_slots_changed")
        for key, original_links in original_slots.items():
            candidate_links = candidate_slots.get(key, set())
            original_destinations = _output_destinations(
                original_links,
                original_links_by_id,
            )
            candidate_destinations = _output_destinations(
                candidate_links,
                candidate_links_by_id,
            )
            for destination in set(original_destinations) - set(candidate_destinations):
                destination_node_id, _ = destination
                if destination_node_id in candidate_node_ids:
                    path_nodes = _transitive_path_nodes_to_destination(
                        start_links=candidate_links,
                        destination=destination,
                        candidate_links_by_id=candidate_links_by_id,
                        candidate_nodes_by_id=candidate_nodes_by_id,
                    )
                    if path_nodes is not None:
                        continue
                    return (False, "schema_less_existing_output_links_removed")
        for key, original_links in original_slots.items():
            candidate_links = candidate_slots.get(key, set())
            original_destinations = _output_destinations(
                original_links,
                original_links_by_id,
            )
            candidate_destinations = _output_destinations(
                candidate_links,
                candidate_links_by_id,
            )
            if set(original_destinations) - set(candidate_destinations):
                return (True, "transitive_output_destinations_safe")
        return (True, "preexisting_output_destinations_safe")

    def _schema_less_transitive_reroute_intermediates() -> set[str]:
        intermediates: set[str] = set()
        for node_id, original_node in original_nodes_by_id.items():
            candidate_node = candidate_nodes_by_id.get(node_id)
            if candidate_node is None:
                continue
            if str(original_node.get("type", "")) != str(candidate_node.get("type", "")):
                continue
            original_slots = _node_output_slots(original_node)
            candidate_slots = _node_output_slots(candidate_node)
            if set(original_slots) != set(candidate_slots):
                continue
            for key, original_links in original_slots.items():
                candidate_links = candidate_slots.get(key, set())
                original_destinations = _output_destinations(
                    original_links,
                    original_links_by_id,
                )
                candidate_destinations = _output_destinations(
                    candidate_links,
                    candidate_links_by_id,
                )
                for destination in set(original_destinations) - set(candidate_destinations):
                    path_nodes = _transitive_path_nodes_to_destination(
                        start_links=candidate_links,
                        destination=destination,
                        candidate_links_by_id=candidate_links_by_id,
                        candidate_nodes_by_id=candidate_nodes_by_id,
                    )
                    if path_nodes is None:
                        continue
                    destination_node_id, _ = destination
                    intermediates.update(
                        path_node
                        for path_node in path_nodes
                        if path_node not in {node_id, destination_node_id}
                    )
        return intermediates

    def _local_node_schema_evidence(class_type: str) -> dict[str, Any] | None:
        try:
            from vibecomfy.comfy_nodes import NODE_CLASS_MAPPINGS  # noqa: PLC0415
        except Exception:
            return None
        node_cls = NODE_CLASS_MAPPINGS.get(class_type)
        if node_cls is None:
            return None
        input_types = getattr(node_cls, "INPUT_TYPES", None)
        if not callable(input_types):
            return None
        try:
            input_types()
        except Exception:
            return None
        return {
            "provider": "vibecomfy_local_node_mapping",
            "confidence": 1.0,
            "schema_less": False,
            "diagnostic": "trusted local VibeComfy node class schema",
        }

    original_node_classes: dict[str, str] = {}
    original_node_connections: dict[str, tuple[Any, ...]] = {}
    original_nodes_by_id: dict[str, Mapping[str, Any]] = {}
    candidate_nodes_by_id: dict[str, Mapping[str, Any]] = {}
    original_links_by_id = _ui_links_by_id(original_ui_payload)
    candidate_links_by_id = _ui_links_by_id(ui_payload)
    candidate_node_ids: set[str] = set()
    original_nodes = (
        original_ui_payload.get("nodes")
        if isinstance(original_ui_payload, Mapping)
        else None
    )
    if isinstance(original_nodes, list):
        for original_node in original_nodes:
            if not isinstance(original_node, Mapping):
                continue
            original_node_id = str(original_node.get("id", ""))
            original_class_type = str(original_node.get("type", ""))
            if original_node_id and original_class_type:
                original_node_classes[original_node_id] = original_class_type
                original_nodes_by_id[original_node_id] = original_node
                original_node_connections[original_node_id] = _connection_signature(
                    original_node
                )
    for candidate_node in nodes:
        if isinstance(candidate_node, Mapping):
            candidate_node_id = str(candidate_node.get("id", ""))
            if candidate_node_id:
                candidate_node_ids.add(candidate_node_id)
                candidate_nodes_by_id[candidate_node_id] = candidate_node
    schema_less_transitive_intermediates = _schema_less_transitive_reroute_intermediates()

    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("id", ""))
        class_type = str(node.get("type", ""))
        if not class_type:
            continue
        preexisting_ui_node = original_node_classes.get(node_id) == class_type
        ui_connection_shape_unchanged = (
            preexisting_ui_node
            and original_node_connections.get(node_id) == _connection_signature(node)
        )
        schema = get_schema(class_type)
        if schema is None:
            local_schema_evidence = _local_node_schema_evidence(class_type)
            if local_schema_evidence is not None:
                recovery.append(
                    {
                        "node_id": node_id,
                        "class_type": class_type,
                        **local_schema_evidence,
                        "preexisting_ui_node": preexisting_ui_node,
                        "ui_connection_shape_unchanged": ui_connection_shape_unchanged,
                        "schema_less_safety": "local_node_schema",
                        "widget_shape_verdict": "not_applicable",
                    }
                )
                continue
            schema_less_safe, schema_less_reason = _preexisting_schema_less_queue_safe(
                original_node=original_nodes_by_id.get(node_id)
                if preexisting_ui_node
                else None,
                candidate_node=node,
                original_links_by_id=original_links_by_id,
                candidate_links_by_id=candidate_links_by_id,
                candidate_node_ids=candidate_node_ids,
                candidate_nodes_by_id=candidate_nodes_by_id,
                schema_less_transitive_intermediates=schema_less_transitive_intermediates,
            )
            recovery.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "provider": None,
                    "confidence": None,
                    "schema_less": True,
                    "preexisting_ui_node": preexisting_ui_node,
                    "ui_connection_shape_unchanged": ui_connection_shape_unchanged,
                    "schema_less_queue_safe": schema_less_safe,
                    "schema_less_safety": schema_less_reason,
                    "schema_less_queue_schema": {
                        "inputs": [
                            {"name": item.get("name"), "type": item.get("type")}
                            for item in (
                                node.get("inputs")
                                if isinstance(node.get("inputs"), list)
                                else []
                            )
                            if isinstance(item, Mapping)
                        ],
                        "outputs": [
                            {
                                "name": item.get("name"),
                                "type": item.get("type"),
                                "slot_index": item.get("slot_index"),
                            }
                            for item in (
                                node.get("outputs")
                                if isinstance(node.get("outputs"), list)
                                else []
                            )
                            if isinstance(item, Mapping)
                        ],
                    },
                    "widget_shape_verdict": "not_applicable",
                    "diagnostic": "schema-less: no schema provider evidence for node",
                }
            )
        else:
            recovery.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "provider": getattr(schema, "source_provider", None),
                    "confidence": getattr(schema, "confidence", None),
                    "schema_less": False,
                    "preexisting_ui_node": preexisting_ui_node,
                    "ui_connection_shape_unchanged": ui_connection_shape_unchanged,
                    "widget_shape_verdict": "not_applicable",
                }
            )
    return recovery


def _queue_recovery_report_for_candidate(
    *,
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
    original_ui_payload: Mapping[str, Any] | None = None,
    existing_recovery_report: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> list[dict[str, Any]]:
    resolved_recovery = _recovery_report_from_ui_payload(
        ui_payload,
        schema_provider,
        original_ui_payload=original_ui_payload,
    )
    if not resolved_recovery:
        return list(existing_recovery_report or ())
    if not existing_recovery_report:
        return resolved_recovery

    resolved_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in resolved_recovery:
        if not isinstance(entry, Mapping):
            continue
        node_id = entry.get("node_id")
        class_type = entry.get("class_type")
        if node_id is None or class_type is None:
            continue
        resolved_by_key[(str(node_id), str(class_type))] = dict(entry)

    queue_fields = (
        "provider",
        "confidence",
        "schema_less",
        "preexisting_ui_node",
        "ui_connection_shape_unchanged",
        "schema_less_queue_safe",
        "schema_less_safety",
        "schema_less_queue_schema",
    )
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for existing in existing_recovery_report:
        if not isinstance(existing, Mapping):
            continue
        merged_entry = dict(existing)
        node_id = merged_entry.get("node_id")
        class_type = merged_entry.get("class_type")
        if node_id is None or class_type is None:
            merged.append(merged_entry)
            continue
        key = (str(node_id), str(class_type))
        seen.add(key)
        overlay = resolved_by_key.get(key)
        if overlay is not None:
            for field in queue_fields:
                if field in overlay:
                    merged_entry[field] = overlay[field]
            if merged_entry.get("diagnostic") is None and overlay.get("diagnostic") is not None:
                merged_entry["diagnostic"] = overlay["diagnostic"]
        merged.append(merged_entry)

    for key, overlay in resolved_by_key.items():
        if key in seen:
            continue
        merged.append(dict(overlay))
    return merged


def _stage_summarize_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    start = time.monotonic()
    recovery_report = _queue_recovery_report_for_candidate(
        ui_payload=state.ui_payload,
        schema_provider=state.schema_provider,
        original_ui_payload=state.graph,
        existing_recovery_report=(state.report or {}).get("recovery"),
    )
    if state.report is None:
        state.report = {}
    state.report["recovery"] = recovery_report
    queue_result = queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
    derive_gates(context, queue_blockers=queue_result.issues)
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "projection": str(state.projection_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "mode": "agent_edit_v2_delta",
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _stage_audit(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
) -> ArtifactRef:
    metadata: dict[str, Any] = {
        "provider": state.provider_metadata or {},
        "lowering": _build_lowering_audit_entries(state.lowering_evidence),
    }
    if _agent_edit_v2_enabled():
        metadata["agent_edit_v2"] = normalize_agent_edit_v2_metadata(
            {
                "enabled": True,
                "op_count": len(state.delta_ops),
                "delta_ops_envelope": _canonical_delta_ops_envelope_payload(state.delta_ops),
                "delta_audit": state.delta_audit or {},
            }
        )
    if _agent_edit_batch_repl_enabled():
        metadata["batch_repl"] = {
            "enabled": True,
            "turn_count": state.batch_turn_count,
            "signature_catalog_available": bool(state.batch_signature_catalog),
            "feedback": state.batch_feedback,
            "final_summary": state.batch_final_summary,
            "exit_mode": state.batch_exit_mode,
            "done_summary": state.batch_done_summary,
            "budget_state": _json_safe(state.batch_budget_state),
        }
    if state.revision_evidence is not None:
        metadata["revision_evidence"] = state.revision_evidence.to_dict()
    return write_audit(
        state.turn_dir / "audit",
        context=context,
        turn_state="candidate",
        stage_results=context.stage_results,
        failure=failure,
        response=response,
        artifacts={
            name: Path(path)
            for name, path in (state.artifacts or {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "messages": str(state.messages_path),
            }).items()
            if Path(path).exists()
        },
        metadata=metadata,
    )


def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
) -> None:
    for transition in unknown_transitions:
        turn_id = transition.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        try:
            write_audit(
                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
                context=TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=baseline_turn_id,
                ),
                turn_state="unknown",
                artifacts={"request": dict(request_payload)},
                metadata={"action": "unknown", **transition},
            )
        except Exception:
            continue


'''
