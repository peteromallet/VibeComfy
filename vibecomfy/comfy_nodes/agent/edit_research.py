# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Research intent, graph reports, precedent prompts, routing, and schema checks.

SOURCE = r'''
def _is_graph_explain_intent(task: str) -> bool:
    return _task_mentions_any(task, _GRAPH_EXPLAIN_TRIGGER_TERMS)


def _is_code_node_intent(task: str) -> bool:
    return _task_mentions_any(task, _CODE_NODE_TRIGGER_TERMS)


def _build_graph_report(graph: dict[str, Any] | None) -> str:
    """Legacy: build a compact text report from a raw ComfyUI graph dict.

    .. deprecated::
        The executor now handles graph inspection for **inspect** routes via
        :mod:`vibecomfy.executor.graph_inspection` (structured evidence +
        Markdown renderer).  This function is kept for internal agent-edit
        tests and for the batch-REPL prompt building when graph context is
        injected into edit (revise / adapt) operations.
    """
    if not graph:
        return "No graph attached."
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return "Empty graph (0 nodes)."

    lines: list[str] = []
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or node.get("type") or "Unknown"
        node_id = node.get("id", i)
        parts: list[str] = [f"[{node_id}] {ct}"]
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and widgets:
            widget_parts = []
            for j, w in enumerate(widgets[:5]):
                if w is not None and str(w).strip():
                    widget_parts.append(f"w{j}={str(w)[:80]}")
            if widget_parts:
                parts.append("values=(" + ", ".join(widget_parts) + ")")
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            slot_info = []
            for inp in inputs:
                if isinstance(inp, dict):
                    name = inp.get("name", "?")
                    link = inp.get("link")
                    slot_info.append(
                        f"{name}=linked({link})" if link is not None else f"{name}=open"
                    )
            if slot_info:
                parts.append("inputs=(" + "; ".join(slot_info[:6]) + ")")
        lines.append(" ".join(parts))

    links = graph.get("links")
    if isinstance(links, list) and links:
        edge_lines: list[str] = []
        for link in links[:40]:
            if isinstance(link, dict):
                src = link.get("origin_id", "?")
                tgt = link.get("target_id", "?")
                edge_lines.append(f"  {src} -> {tgt}")
            elif isinstance(link, list) and len(link) >= 4:
                edge_lines.append(f"  {link[1]} -> {link[3]}")
        if edge_lines:
            lines.append("Edges:")
            lines.extend(edge_lines)

    return f"{len(nodes)} node(s):\n" + "\n".join(lines)


def _prefetch_research_summary(_task: str) -> str:
    return ""



def _build_precedent_adaptation_prompt(
    adaptation_plan: dict[str, Any] | None,
    precedent_slices: tuple[dict[str, Any], ...] = (),
) -> str:
    """Build a compact precedent adaptation prompt for batch REPL injection.

    Only invoked for the `precedent_research` route.  Includes anchors,
    required nodes/rewires, socket evidence, avoid patterns, and semantic
    checks from the structured adaptation plan, but never the full
    candidate_graph to avoid biasing the model toward a single solution.

    All precedent material is neutral context — it is NOT a winner,
    recommendation, or required implementation.  The adaptation agent
    evaluates all available slices independently.
    """
    if not adaptation_plan:
        return ""
    if not is_actionable_adaptation_plan(adaptation_plan):
        return ""

    parts: list[str] = []

    # ── context note (neutrality disclaimer) ──
    context_note = adaptation_plan.get("context_note")
    if isinstance(context_note, str) and context_note.strip():
        parts.append(f"IMPORTANT: {context_note.strip()}")

    # ── selected slice (presentation context only — not a winner) ──
    selected_slice = adaptation_plan.get("selected_slice")
    if isinstance(selected_slice, dict):
        source_class = selected_slice.get("source_class_type", "")
        node_ids = selected_slice.get("node_ids") or []
        entry = selected_slice.get("entry_anchor")
        exit_ = selected_slice.get("exit_anchor")
        py_path = selected_slice.get("python_path")
        slice_desc = f"Source: {source_class}" if source_class else "Source: (unnamed)"
        if isinstance(node_ids, list) and node_ids:
            slice_desc += f", {len(node_ids)} node(s): [{', '.join(str(n) for n in node_ids[:8])}]"
            if len(node_ids) > 8:
                slice_desc += f" (+{len(node_ids) - 8} more)"
        if entry:
            slice_desc += f", entry_anchor={entry}"
        if exit_:
            slice_desc += f", exit_anchor={exit_}"
        if py_path:
            slice_desc += f", path={py_path}"
        parts.append(f"Reference slice (presentation context only — NOT a winner): {slice_desc}")

    # ── all available slices (neutral summary) ──
    all_slices = adaptation_plan.get("all_slices")
    if isinstance(all_slices, list) and all_slices:
        slice_summaries = []
        for i, s in enumerate(all_slices[:12]):
            if isinstance(s, dict):
                ct = s.get("source_class_type") or "unnamed"
                nids = s.get("node_ids") or []
                n = len(nids) if isinstance(nids, (list, tuple)) else 0
                entry_a = s.get("entry_anchor")
                exit_a = s.get("exit_anchor")
                desc = f"{ct} ({n} nodes"
                if entry_a:
                    desc += f", entry={entry_a}"
                if exit_a:
                    desc += f", exit={exit_a}"
                desc += ")"
                slice_summaries.append(desc)
        if slice_summaries:
            if len(all_slices) > 12:
                slice_summaries.append(f"(+{len(all_slices) - 12} more slices)")
            parts.append("All available precedent slices (neutral context): " + "; ".join(slice_summaries))

    # ── anchor bindings ──
    anchor_bindings = adaptation_plan.get("anchor_bindings")
    if isinstance(anchor_bindings, list) and anchor_bindings:
        binding_lines = []
        for b in anchor_bindings:
            if isinstance(b, dict):
                binding_lines.append(", ".join(f"{k} → {v}" for k, v in b.items()))
        if binding_lines:
            parts.append("Anchor bindings: " + "; ".join(binding_lines))

    # ── required new nodes ──
    required_new_nodes = adaptation_plan.get("required_new_nodes")
    if isinstance(required_new_nodes, list) and required_new_nodes:
        node_lines = []
        for n in required_new_nodes[:10]:
            if isinstance(n, dict):
                class_type = n.get("class_type") or n.get("type") or "node"
                node_id = n.get("id") or n.get("node_id") or "?"
                slot_info = ""
                inputs = n.get("inputs")
                if isinstance(inputs, dict):
                    slot_info = ", ".join(f"{k}={v}" for k, v in list(inputs.items())[:3])
                desc = f"{class_type}(id={node_id}"
                if n.get("widget_values"):
                    desc += f", values={json.dumps(n['widget_values'])[:80]}"
                if slot_info:
                    desc += f", inputs={{{slot_info}}}"
                desc += ")"
                node_lines.append(desc)
        if node_lines:
            parts.append("Required new nodes: " + "; ".join(node_lines))

    # ── required rewires ──
    required_rewires = adaptation_plan.get("required_rewires")
    if isinstance(required_rewires, list) and required_rewires:
        rewire_lines = []
        for r in required_rewires[:6]:
            if isinstance(r, dict):
                src = r.get("from") or r.get("source") or "?"
                tgt = r.get("to") or r.get("target") or "?"
                slot = r.get("slot") or r.get("input_slot") or ""
                desc = f"{src} → {tgt}"
                if slot:
                    desc += f".{slot}"
                rewire_lines.append(desc)
        if rewire_lines:
            parts.append("Required rewires: " + "; ".join(rewire_lines))

    # ── edit ops (compact) ──
    edit_ops = adaptation_plan.get("edit_ops")
    if isinstance(edit_ops, list) and edit_ops:
        op_lines = []
        for op in edit_ops[:6]:
            if isinstance(op, dict):
                op_kind = op.get("kind") or op.get("op") or "edit"
                op_target = op.get("target") or op.get("node_id") or "?"
                op_value = op.get("value")
                desc = f"{op_kind} {op_target}"
                if op_value is not None:
                    desc += f"={json.dumps(op_value)[:40]}"
                op_lines.append(desc)
        if op_lines:
            parts.append("Edit ops: " + "; ".join(op_lines))

    # ── socket evidence (from slices) ──
    if precedent_slices:
        socket_lines = []
        for s in precedent_slices[:4]:
            if isinstance(s, dict):
                class_type = s.get("source_class_type") or "node"
                entry = s.get("entry_anchor")
                exit_ = s.get("exit_anchor")
                node_ids = s.get("node_ids") or []
                desc = class_type
                if entry or exit_:
                    anchors = []
                    if entry:
                        anchors.append(f"in={entry}")
                    if exit_:
                        anchors.append(f"out={exit_}")
                    desc += f" ({', '.join(anchors)})"
                socket_lines.append(desc)
        if socket_lines:
            parts.append("Socket evidence (workflow slices): " + "; ".join(socket_lines))

    # ── avoid patterns (derived from structural validation) ──
    structural_val = adaptation_plan.get("structural_validation", "")
    if structural_val == "fail":
        parts.append("AVOID: structural validation FAILED — the precedent slice may not be structurally compatible. Prefer a different precedent or adapt conservatively.")
    elif structural_val == "advisory":
        parts.append("NOTE: structural validation has advisories — verify wiring compatibility before landing edits.")

    # ── semantic checks ──
    semantic_val = adaptation_plan.get("semantic_validation", "")
    if semantic_val == "pass":
        parts.append("Semantic validation: PASS — the adaptation is semantically sound.")
    elif semantic_val == "fail":
        parts.append("AVOID: semantic validation FAILED — the precedent may not produce the expected behavior. Consider an alternative.")
    elif semantic_val == "advisory":
        parts.append("Semantic validation advisories present — review model compatibility and slot types.")

    if not parts:
        return ""

    return "\n".join(parts)


def _route_blocks_apply(route: str | None) -> bool:
    """Return True when *route* forbids Apply eligibility.

    Non-applyable routes (clarify, respond, inspect, research) do not
    produce edits and must never carry a candidate, apply_eligible flag,
    or apply-eligibility payload.  Only revise and adapt are apply-eligible.
    """
    return _canonical_agent_edit_route(route) in {"clarify", "respond", "inspect", "research"}


def _canonical_agent_edit_route(route: str | None) -> str | None:
    """Normalize executor-facing route labels to the canonical vocabulary."""
    if not isinstance(route, str):
        return None
    normalized = route.strip()
    if not normalized:
        return None
    aliases = {
        "inspect_only": "inspect",
        "direct_edit": "revise",
        "diagnose_repair": "revise",
        "precedent_research": "adapt",
        "/reorganise_comfy_workflow": "reorganise",
        "reorganise_comfy_workflow": "reorganise",
        "/reorganize_comfy_workflow": "reorganise",
        "reorganize_comfy_workflow": "reorganise",
        "reorganize": "reorganise",
    }
    return aliases.get(normalized, normalized)


def _route_change_focus_label(route: str | None) -> str:
    """Return a short change-focus label for *route* when reporting edits.

    revise is a focused, targeted change — the label makes that
    explicit in user-facing summaries.
    """
    if _canonical_agent_edit_route(route) == "revise":
        return "Focused change"
    return ""


def _build_precedent_semantic_check_entries(
    state: "AgentEditState",
) -> list[dict[str, Any]]:
    """Build task-satisfaction entries from the precedent adaptation plan.

    Semantic and structural validation fields are mapped to task satisfaction
    entries with a satisfaction key of advisory (for advisory warnings)
    or not_evaluated (for fields the plan did not evaluate).  These entries
    provide route-level observability without blocking Apply or Queue.
    """
    plan = state.executor_adaptation_plan
    if not isinstance(plan, dict):
        return []

    entries: list[dict[str, Any]] = []

    structural_val = plan.get("structural_validation")
    if structural_val in ("pass", "fail", "advisory", "not_evaluated"):
        entries.append(
            {
                "check": "structural_validation",
                "status": structural_val,
                "satisfaction": structural_val if structural_val != "not_evaluated" else "not_evaluated",
                "description": _structural_validation_description(structural_val),
            }
        )

    semantic_val = plan.get("semantic_validation")
    if semantic_val in ("pass", "fail", "advisory", "not_evaluated"):
        entries.append(
            {
                "check": "semantic_validation",
                "status": semantic_val,
                "satisfaction": semantic_val if semantic_val != "not_evaluated" else "not_evaluated",
                "description": _semantic_validation_description(semantic_val),
            }
        )

    return entries


def _structural_validation_description(status: str) -> str:
    if status == "pass":
        return "Precedent slice is structurally compatible with the current graph."
    if status == "fail":
        return "Precedent slice has structural incompatibilities — adapt conservatively."
    if status == "advisory":
        return "Precedent slice has structural advisories — verify wiring compatibility."
    return "Structural validation was not evaluated for the precedent slice."


def _semantic_validation_description(status: str) -> str:
    if status == "pass":
        return "Precedent adaptation is semantically sound."
    if status == "fail":
        return "Precedent may not produce expected behavior — consider alternatives."
    if status == "advisory":
        return "Semantic advisories present — review model compatibility and slot types."
    return "Semantic validation was not evaluated for the precedent adaptation."


def _schema_provider_available(schema_provider: Any) -> bool:
    if schema_provider is None:
        return False
    schemas = getattr(schema_provider, "schemas", None)
    if callable(schemas):
        try:
            return bool(schemas())
        except Exception:
            return False
    get_schema = getattr(schema_provider, "get_schema", None)
    return callable(get_schema)


def _schema_provider_has_class(schema_provider: Any, class_type: str) -> bool:
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return False
    try:
        return get_schema(class_type) is not None
    except Exception:
        return False


def _graph_class_types_missing_from_schema(
    graph: Mapping[str, Any] | None,
    schema_provider: Any,
) -> tuple[str, ...]:
    if not isinstance(graph, Mapping):
        return ()
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return ()
    missing: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        raw = node.get("class_type") or node.get("type")
        class_type = str(raw or "").strip()
        if not class_type or class_type == "Unknown" or class_type in seen:
            continue
        seen.add(class_type)
        if not _schema_provider_has_class(schema_provider, class_type):
            missing.append(class_type)
    return tuple(missing)


def _graph_class_types(graph: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(graph, Mapping):
        return ()
    nodes = graph.get("nodes")
    values: list[Any]
    if isinstance(nodes, list):
        values = list(nodes)
    elif isinstance(nodes, Mapping):
        values = list(nodes.values())
    else:
        return ()
    seen: set[str] = set()
    ordered: list[str] = []
    for node in values:
        if not isinstance(node, Mapping):
            continue
        raw = node.get("class_type") or node.get("type")
        class_type = str(raw or "").strip()
        if not class_type or class_type == "Unknown" or class_type in seen:
            continue
        seen.add(class_type)
        ordered.append(class_type)
    return tuple(ordered)


def _adaptation_slice_domain_mismatch_diagnostic(
    state: AgentEditState,
    *,
    route: str | None = None,
) -> dict[str, Any] | None:
    canonical_route = _canonical_agent_edit_route(state.route or route)
    if canonical_route != "adapt":
        return None
    request_payload = state.request_payload if isinstance(state.request_payload, Mapping) else {}
    if request_payload.get("apply") is not False:
        return None
    adaptation_plan = state.executor_adaptation_plan
    if not isinstance(adaptation_plan, Mapping):
        return None
    selected_slice = adaptation_plan.get("selected_slice")
    if not isinstance(selected_slice, Mapping):
        return None
    raw_selected_types = selected_slice.get("node_types")
    if not isinstance(raw_selected_types, (list, tuple)):
        return None
    selected_types = [
        str(item).strip()
        for item in raw_selected_types
        if str(item).strip() and str(item).strip() != "Unknown"
    ]
    if not selected_types:
        return None
    current_types = _graph_class_types(state.guard_original_ui or state.graph)
    if not current_types:
        return None
    current_type_set = set(current_types)
    overlap = [class_type for class_type in selected_types if class_type in current_type_set]
    missing = [class_type for class_type in selected_types if class_type not in current_type_set]
    unique_missing = list(dict.fromkeys(missing))
    # Treat this as a domain mismatch only when the selected precedent barely
    # overlaps the current graph. A few missing helper classes can still be a
    # valid adaptation path; a mostly-disjoint slice should degrade to a
    # read-only diagnosis for non-apply requests instead of crashing later.
    if not unique_missing:
        return None
    if len(overlap) > 2 or len(unique_missing) < 5:
        return None
    source_class = str(selected_slice.get("source_class_type") or "").strip() or "the selected precedent"
    missing_preview = ", ".join(unique_missing[:6])
    if len(unique_missing) > 6:
        missing_preview += f", and {len(unique_missing) - 6} more"
    current_preview = ", ".join(current_types[:6])
    if len(current_types) > 6:
        current_preview += f", and {len(current_types) - 6} more"
    message = (
        "I found a precedent slice, but it belongs to a different workflow domain than "
        "the current graph, so I left the graph unchanged. "
        f"The selected slice from {source_class!r} expects node types such as {missing_preview}, "
        f"while the current graph is built from {current_preview}. "
        "That means the precedent is useful as diagnostic context, but not safe to lower into "
        "this graph as a direct edit."
    )
    report_payload = {
        "adaptation_domain_mismatch": {
            "selected_slice_source_class_type": source_class,
            "selected_slice_node_types": list(dict.fromkeys(selected_types)),
            "selected_slice_missing_node_types": unique_missing,
            "current_graph_node_types": list(current_types),
            "shared_node_types": list(dict.fromkeys(overlap)),
        },
        "graph_facts": dict(state.graph_facts)
        if isinstance(state.graph_facts, Mapping)
        else {},
        "read_only": True,
        "graph_unchanged": True,
    }
    return {
        "message": message,
        "report_payload": report_payload,
        "no_candidate_reason": "domain_mismatch",
    }


def _candidate_dict(candidate: Any) -> dict[str, Any] | None:
    if isinstance(candidate, Mapping):
        return dict(candidate)
    to_dict = getattr(candidate, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return dict(value)
    return None


def _resolver_candidate_supports_class(
    candidate: Mapping[str, Any],
    class_type: str,
) -> bool:
    expected = candidate.get("expected_classes")
    if isinstance(expected, (list, tuple)) and class_type in {str(item) for item in expected}:
        return True
    schema_payload = candidate.get("provisional_schema")
    if isinstance(schema_payload, Mapping):
        raw_schema = schema_payload.get("schema")
        if isinstance(raw_schema, Mapping):
            nodes = raw_schema.get("nodes") or raw_schema.get("object_info") or raw_schema
            return isinstance(nodes, Mapping) and class_type in nodes
    return False


def _iter_research_precedent_sources(state: AgentEditState) -> tuple[Mapping[str, Any], ...]:
    sources: list[Mapping[str, Any]] = []
    for source in getattr(state, "executor_research_sources", ()) or ():
        if isinstance(source, Mapping):
            sources.append(source)
    notes = getattr(state, "execution_protocol_notes", None)
    if isinstance(notes, Mapping):
        raw_sources = notes.get("research_sources")
        if isinstance(raw_sources, list):
            sources.extend(source for source in raw_sources if isinstance(source, Mapping))
    return tuple(sources)


def _workflow_class_types_from_research_context(
    state: AgentEditState,
    *,
    max_classes: int = 16,
    missing_only: bool = True,
    custom_only: bool = True,
) -> tuple[str, ...]:
    classes: list[str] = []
    for source in _iter_research_precedent_sources(state):
        source_kind = str(source.get("source") or "")
        pack = str(source.get("pack") or "")
        if "workflow" not in source_kind and pack != "workflow":
            continue
        candidates: list[Any] = []
        for key in ("workflow_schema_classes", "node_types"):
            value = source.get(key)
            if isinstance(value, list):
                candidates.extend(value)
        workflow_schema = source.get("workflow_schema")
        if isinstance(workflow_schema, Mapping):
            candidates.extend(workflow_schema.keys())
        for raw_class_type in candidates:
            class_type = str(raw_class_type or "").strip()
            if (
                not class_type
                or class_type in classes
                or (
                    missing_only
                    and state.schema_provider.get_schema(class_type) is not None
                )
            ):
                continue
            if custom_only:
                # Workflow precedents include many core/local classes. Resolve the
                # custom-looking misses that can plausibly require installation.
                if not (
                    "_" in class_type
                    or class_type.startswith(("ADE", "VHS", "IPAdapter", "ACN"))
                    or " " in class_type
                ):
                    continue
            elif state.schema_provider.get_schema(class_type) is None and not (
                "_" in class_type
                or class_type.startswith(("ADE", "VHS", "IPAdapter", "ACN"))
                or " " in class_type
            ):
                # For prompt focus we want already-known core classes too, but
                # unknown plain names from workflow metadata are usually labels
                # or weak aliases rather than authorable node types.
                continue
            classes.append(class_type)
            if len(classes) >= max_classes:
                return tuple(classes)
    return tuple(classes)


def _workflow_schema_candidates_from_research_context(
    state: AgentEditState,
) -> tuple[dict[str, Any], ...]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in _iter_research_precedent_sources(state):
        workflow_schema = source.get("workflow_schema")
        if not isinstance(workflow_schema, Mapping) or not workflow_schema:
            continue
        source_kind = str(source.get("source") or "")
        pack = str(source.get("pack") or "")
        if "workflow" not in source_kind and pack != "workflow":
            continue
        key = json.dumps(
            {
                "url": source.get("url") or source.get("source_workflow_path") or "",
                "classes": sorted(str(class_type) for class_type in workflow_schema),
            },
            sort_keys=True,
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "pack": {
                    "name": source.get("class_type") or source.get("name") or "workflow_json",
                    "slug": source.get("pack") or "workflow_json",
                    "source": source.get("source") or "external_workflow",
                    "url": source.get("url") or source.get("source_workflow_path") or "",
                },
                "provisional_schema": {
                    "version": "workflow-json",
                    "schema": {"nodes": workflow_schema},
                    "runnable": False,
                },
                "expected_classes": sorted(str(class_type) for class_type in workflow_schema),
                "validation_mode": "workflow_json_provisional",
                "warnings": [
                    "Schema derived from workflow JSON; runtime node pack may need installation."
                ],
                "stable_install_hash": f"workflow-json:{key}",
            }
        )
    return tuple(candidates)


def _hydrate_research_precedent_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
    """Compile workflow-observed missing node classes into authoring capabilities.

    Adapt-route prefetch provides workflow evidence before the batch agent runs.
    Exact workflow JSON schemas are allowed as provisional authoring schemas;
    registry/Manager resolution is an additional source of stronger evidence,
    not a prerequisite for placing a reviewable candidate node.
    """
    missing_classes = _workflow_class_types_from_research_context(state)
    workflow_candidates = _workflow_schema_candidates_from_research_context(state)
    if workflow_candidates:
        try:
            from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider

            provisional = ProvisionalRegistrySchemaProvider(workflow_candidates)
            if provisional.schemas():
                state.provisional_registry_candidate_hashes = frozenset(
                    {
                        *state.provisional_registry_candidate_hashes,
                        *(_candidate_stable_key(candidate) for candidate in workflow_candidates),
                    }
                )
                state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
        except Exception as exc:  # noqa: BLE001 - keep registry fallback below available
            LOGGER.debug("workflow schema provisional hydration unavailable: %s", exc)

    if not missing_classes:
        return workflow_candidates

    unresolved_missing_classes = tuple(
        class_type
        for class_type in missing_classes
        if state.schema_provider.get_schema(class_type) is None
    )
    if not unresolved_missing_classes:
        return workflow_candidates

    try:
        from vibecomfy.registry.pack_resolver import resolve_missing_nodes
        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
    except Exception as exc:  # noqa: BLE001 - registry hydration is best-effort
        LOGGER.debug("research precedent schema hydration unavailable: %s", exc)
        return workflow_candidates

    candidates: list[dict[str, Any]] = []
    for class_type in unresolved_missing_classes:
        try:
            resolution = resolve_missing_nodes(class_type, query_intent="class_name")
        except Exception as exc:  # noqa: BLE001 - keep context-only behavior on lookup failure
            LOGGER.debug("research precedent schema hydration failed for %s: %s", class_type, exc)
            continue
        for raw_candidate in getattr(resolution, "candidates", ()) or ():
            candidate = _candidate_dict(raw_candidate)
            if candidate is None:
                continue
            if not _resolver_candidate_supports_class(candidate, class_type):
                continue
            candidates.append(candidate)

    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return workflow_candidates
    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return ()
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
    return (*workflow_candidates, *new_candidates)


def _hydrate_current_graph_unknown_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
    missing_classes = _graph_class_types_missing_from_schema(state.graph, state.schema_provider)
    if not missing_classes:
        return ()

    try:
        from vibecomfy.registry.pack_resolver import resolve_missing_nodes
        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
    except Exception as exc:  # noqa: BLE001 - registry hydration is best-effort
        LOGGER.debug("registry schema hydration unavailable: %s", exc)
        return ()

    candidates: list[dict[str, Any]] = []
    for class_type in missing_classes:
        try:
            resolution = resolve_missing_nodes(class_type, query_intent="class_name")
        except Exception as exc:  # noqa: BLE001 - keep existing blocker on lookup failure
            LOGGER.debug("registry schema hydration failed for %s: %s", class_type, exc)
            continue
        for raw_candidate in getattr(resolution, "candidates", ()) or ():
            candidate = _candidate_dict(raw_candidate)
            if candidate is None:
                continue
            if not _resolver_candidate_supports_class(candidate, class_type):
                continue
            candidates.append(candidate)

    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return ()
    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return ()
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
    return tuple(new_candidates)


def _revision_no_candidate_reason(evidence: RevisionEvidence) -> str | None:
    if evidence.safe_candidate_possible:
        return None
    if evidence.topology.missing_graph:
        return "no_graph"
    return "no_changes"


def _executor_classification_text(state: AgentEditState) -> str:
    classification = state.request_payload.get("executor_classification")
    if isinstance(classification, Mapping):
        return " ".join(
            str(classification.get(key) or "")
            for key in ("plan_summary", "intent", "route", "task")
        )
    return ""


def _effective_implementation_task(state: AgentEditState) -> str:
    classification_text = _executor_classification_text(state).strip()
    if not classification_text:
        return state.task
    return (
        f"{state.task}\n\n"
        "Resolved executor plan/context:\n"
        f"{classification_text}"
    )


def _runtime_code_additive_request(state: AgentEditState) -> bool:
    classification_text = _executor_classification_text(state)
    task = (
        f"{state.task} {state.request_payload.get('query') or ''} "
        f"{classification_text}"
    ).lower()
    explicit_frame_extraction = (
        ("extract" in task and "frame" in task)
        or ("first frame" in task and ("save" in task or "png" in task or "image" in task))
    )
    return (
        (
            "code node" in task
            or "runtime code" in task
            or "vibecomfy.exec" in task
            or "imagecode" in task
            or ("pil" in task and "transformation" in task)
            or explicit_frame_extraction
        )
        and ("pil" in task or "image" in task or "frame" in task or "process" in task)
    )


def _executor_requested_implementation(state: AgentEditState) -> bool:
    classification = state.request_payload.get("executor_classification")
    if isinstance(classification, Mapping) and "implement" in classification:
        return bool(classification.get("implement"))
    return _canonical_agent_edit_route(state.route) in {"revise", "adapt", "dev"}


def _state_runtime_execution_requested(state: AgentEditState) -> bool:
    runtime = state.request_payload.get("runtime")
    return isinstance(runtime, Mapping) and bool(runtime.get("execution_requested"))


def _empty_graph_authoring_request(state: AgentEditState) -> bool:
    evidence = state.revision_evidence
    if evidence is None or not evidence.topology.missing_graph:
        return False
    if _state_runtime_execution_requested(state):
        return False
    return _executor_requested_implementation(state)


_TEXT_TO_IMAGE_SEED_TYPES = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)


'''
