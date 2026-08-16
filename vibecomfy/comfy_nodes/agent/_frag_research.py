"""
Research stage and research helpers (T-038 extraction of the edit_research fragment).

Extracted from the edit.py exec-assembled fragments (T-038, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Imports of sibling _frag modules follow
the foundation dependency order; names that would form an import cycle are
resolved lazily at call time (marked with a T-038 late import comment).
"""
import json
from typing import Any, Mapping
from vibecomfy.executor.contracts import RevisionEvidence
from ._frag_state import AgentEditState, LOGGER

def _is_graph_explain_intent(task: str) -> bool:
    from ._frag_ingest import _GRAPH_EXPLAIN_TRIGGER_TERMS, _task_mentions_any  # T-038 late import: sibling cycle broken; resolved at call time
    return _task_mentions_any(task, _GRAPH_EXPLAIN_TRIGGER_TERMS)


def _is_code_node_intent(task: str) -> bool:
    from ._frag_ingest import _CODE_NODE_TRIGGER_TERMS, _task_mentions_any  # T-038 late import: sibling cycle broken; resolved at call time
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
    # D03: executor_adaptation_plan removed; the adaptation plan rides in
    # execution_protocol_notes (H03 hydration source).
    notes = state.execution_protocol_notes
    plan = notes.get("adaptation_plan") if isinstance(notes, Mapping) else None
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
    # D03: executor_adaptation_plan removed; the plan rides in
    # execution_protocol_notes (H03 hydration source).
    notes = state.execution_protocol_notes
    adaptation_plan = notes.get("adaptation_plan") if isinstance(notes, Mapping) else None
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
    # D03: executor_research_sources removed; workflow precedent sources come
    # from execution_protocol_notes.research_sources only.
    sources: list[Mapping[str, Any]] = []
    notes = getattr(state, "execution_protocol_notes", None)
    if isinstance(notes, Mapping):
        raw_sources = notes.get("research_sources")
        if isinstance(raw_sources, (list, tuple)):
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
    from vibecomfy.comfy_nodes.agent.edit import _candidate_stable_key  # T-038 late import: exec'd-host fragment; resolved at call time
    missing_classes = _workflow_class_types_from_research_context(state)
    workflow_candidates = _workflow_schema_candidates_from_research_context(state)
    if workflow_candidates:
        try:
            from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler

            provisional = ProvisionalRegistrySchemaProvider(workflow_candidates)
            if provisional.schemas():
                state.provisional_registry_candidate_hashes = frozenset(
                    {
                        *state.provisional_registry_candidate_hashes,
                        *(_candidate_stable_key(candidate) for candidate in workflow_candidates),
                    }
                )
                state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
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
        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
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
    state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
    return (*workflow_candidates, *new_candidates)


def _hydrate_current_graph_unknown_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
    from vibecomfy.comfy_nodes.agent.edit import _candidate_stable_key  # T-038 late import: exec'd-host fragment; resolved at call time
    missing_classes = _graph_class_types_missing_from_schema(state.graph, state.schema_provider)
    if not missing_classes:
        return ()

    try:
        from vibecomfy.registry.pack_resolver import resolve_missing_nodes
        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
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
    state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
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
    # Carry intent/route/task into the editor's task, but NOT plan_summary: the
    # classifier's one-sentence plan commits to a semantic solution/placement,
    # and on ambiguous requests it commits wrongly (e.g. "add ImageScale after
    # VAEDecode"). Let the editor decide placement from the raw graph + request.
    classification = state.request_payload.get("executor_classification")
    context = ""
    if isinstance(classification, Mapping):
        context = " ".join(
            str(classification.get(key) or "")
            for key in ("intent", "route", "task")
        ).strip()
    if not context:
        return state.task
    return (
        f"{state.task}\n\n"
        "Resolved executor context:\n"
        f"{context}"
    )


__all__ = (
     "_adaptation_slice_domain_mismatch_diagnostic", "_build_graph_report",
     "_build_precedent_semantic_check_entries", "_candidate_dict",
     "_canonical_agent_edit_route", "_effective_implementation_task",
     "_executor_classification_text",
     "_graph_class_types",
     "_graph_class_types_missing_from_schema",
     "_hydrate_current_graph_unknown_node_schemas",
     "_hydrate_research_precedent_node_schemas", "_is_code_node_intent",
     "_is_graph_explain_intent", "_iter_research_precedent_sources",
     "_prefetch_research_summary", "_resolver_candidate_supports_class",
     "_revision_no_candidate_reason", "_route_blocks_apply",
     "_route_change_focus_label",
     "_schema_provider_available", "_schema_provider_has_class",
     "_semantic_validation_description",
     "_structural_validation_description",
     "_workflow_class_types_from_research_context",
     "_workflow_schema_candidates_from_research_context",
)
