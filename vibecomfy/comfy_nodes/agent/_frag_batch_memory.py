"""
Batch-loop memory / query-output helpers (T-038 extraction of the edit_batch_memory fragment).

Extracted from the edit.py exec-assembled fragments (T-038, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Imports of sibling _frag modules follow
the foundation dependency order; names that would form an import cycle are
resolved lazily at call time (marked with a T-038 late import comment).
"""
import difflib
import re
from typing import Any, Mapping
from vibecomfy.comfy_nodes.agent.provider import AgentTurnResult, BatchTurnResult

from vibecomfy.porting.widgets.settings_contract import node_settings_for

from vibecomfy.ingest.normalize import door_get_nodes
from vibecomfy.executor.evidence_pack import (
    MAX_LEDGER_PROMPT_CHARS,
    MAX_LEDGER_PROMPT_ENTRIES,
)


def _compact_ledger_text(value: Any, max_chars: int) -> str:
    text = str(value or "")
    return text[:max_chars]


def _normalize_test_client_response(response: dict[str, str]) -> AgentTurnResult:
    python = response.get("python")
    message = response.get("message")
    if not isinstance(python, str):
        raise ValueError("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise ValueError("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client"},
    )


def _normalize_test_client_batch_response(response: dict[str, str]) -> BatchTurnResult:
    batch = response.get("batch")
    message = response.get("message")
    if not isinstance(batch, str):
        raise ValueError("Batch agent response must include string key `batch`.")
    if not isinstance(message, str):
        raise ValueError("Batch agent response must include string key `message`.")
    return BatchTurnResult(
        batch=batch,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client", "response_contract": "batch_repl"},
    )


def _render_batch_diff(before: str, after: str, *, max_chars: int = 2000) -> str:
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before.py",
            tofile="after.py",
            n=2,
        )
    ).strip()
    if len(diff) <= max_chars:
        return diff
    return diff[: max(0, max_chars - 15)].rstrip() + "\n... [truncated]"


def _format_statement_source(source: str, *, max_chars: int = 72) -> str:
    """Truncate a statement source string for inline display."""
    if len(source) <= max_chars:
        return source
    return source[: max(0, max_chars - 3)] + "..."


def _iter_ui_nodes(ui_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return root and nested UI node dictionaries from a LiteGraph payload."""
    found: list[Mapping[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            nodes = door_get_nodes(value)
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, Mapping):
                        found.append(node)
                        visit(node)
            for key in ("graphs", "subgraphs"):
                nested = value.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        visit(item)
                elif isinstance(nested, Mapping):
                    for item in nested.values():
                        visit(item)

    visit(ui_payload)
    return found


def _present_class_types(session: Any) -> list[str]:
    """Enumerate class types currently present in the retained IR."""
    workflow = getattr(session, "workflow", None)
    nodes = getattr(workflow, "nodes", None)
    if isinstance(nodes, Mapping) and nodes:
        types = {
            str(getattr(node, "class_type", "") or "")
            for node in nodes.values()
            if str(getattr(node, "class_type", "") or "")
        }
        return sorted(types)
    return []


def _format_node_variable_index(session: Any) -> str:
    """Return ``var = ClassType`` lines plus EditableSurface field names."""
    from vibecomfy.porting.edit.editable_surface import editable_surface_for

    workflow = getattr(session, "workflow", None)
    name_by_uid = getattr(session, "name_by_uid", None)
    nodes = getattr(workflow, "nodes", None)
    if not isinstance(nodes, Mapping) or not isinstance(name_by_uid, Mapping):
        return ""
    rows: list[tuple[str, str, str]] = []
    for node in nodes.values():
        uid = str(getattr(node, "uid", "") or "")
        if not uid:
            continue
        name = name_by_uid.get(uid)
        class_type = str(getattr(node, "class_type", "") or "")
        if isinstance(name, str) and name and class_type:
            try:
                surface = editable_surface_for(
                    node,
                    schema_provider=getattr(session, "schema_provider", None),
                    edges=getattr(workflow, "edges", None),
                )
                literals = ",".join(sorted(surface.literal_names()))
                sockets = ",".join(sorted(surface.socket_names()))
                extras = []
                if literals:
                    extras.append(f"literals={literals}")
                if sockets:
                    extras.append(f"sockets={sockets}")
                if extras:
                    class_type = f"{class_type} [{'; '.join(extras)}]"
            except Exception:
                pass
            rows.append((name, uid, class_type))
    rows.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(f"{name} = {class_type}" for name, _uid, class_type in rows)


def _format_available_node_names(
    rows: Any,
    *,
    max_line_chars: int = 96,
    max_names: int = 80,
    include_provisional: bool = False,
) -> str:
    """Format NodeSignatureRow-like objects as a bounded deterministic name list.

    Large ComfyUI installs can expose hundreds of node types. Dumping the full
    registry into the first edit prompt makes simple turns slow and brittle, and
    the batch REPL already has ``search(...)`` for exact schema lookup when a
    new type is needed.
    """
    names = sorted(
        {
            class_type
            for row in rows or []
            if isinstance((class_type := getattr(row, "class_type", None)), str)
            and class_type
            and (
                include_provisional
                or str(getattr(row, "status", "") or "installed") == "installed"
            )
        }
    )
    if not names:
        return ""
    total_count = len(names)
    if max_names > 0 and total_count > max_names:
        names = names[:max_names]
    lines: list[str] = []
    current = names[0]
    for name in names[1:]:
        candidate = f"{current}, {name}"
        if len(candidate) > max_line_chars:
            lines.append(current)
            current = name
        else:
            current = candidate
    lines.append(current)
    if total_count > len(names):
        lines.append(
            f"... [{total_count - len(names)} more node type names omitted; "
            "use search(...) for exact authoring-schema lookup before adding an omitted type]"
        )
    return "\n".join(lines)


def _format_query_output(text: str, *, max_chars: int | None = 4000) -> str:
    """Bound read-only query output before it is included in agent feedback."""
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 18)].rstrip() + "\n... [truncated]"


def _batch_research_memory_summary(state: Any, *, max_items: int = 3) -> str:
    """Carry compact prior research/query evidence across batch turns.

    D03/I01: cross-turn memory is LEDGER-ONLY.  Wave-A agent tool statements
    (``detail["tool_call"]``) are carried as compact F01 ledger entries +
    evidence IDs ONLY (via :func:`_tool_evidence_ledger_records`); raw tool
    result bodies, ``query_output`` text, precedent packets, research briefs,
    and workflow schema dumps NEVER enter prompt memory.  Full evidence stays
    in the evidence-pack artifact behind the resolvable IDs.

    On the adapt route the executor runs C1 research and forwards its compact
    F01 ledger in the request payload (``payload["research_ledger"]``).  Turn
    0 has no in-loop statements yet, so that executor ledger is rendered
    FIRST (via :func:`_payload_research_ledger_records`) — the implement agent
    must see the research conclusions/evidence it is adapting from, never an
    empty block — and in-loop records follow on later turns.
    """
    sections: list[str] = []
    entry_limit = max(0, min(int(max_items), MAX_LEDGER_PROMPT_ENTRIES))
    payload_records = _payload_research_ledger_records(state)[-entry_limit:]
    if payload_records:
        sections.append(
            "C1 research ledger (executor research stage; compact; entries + "
            "evidence IDs only — already resolved; IDs are provenance labels, "
            "not callable handles; never repeat raw bodies):\n"
            + "\n".join(payload_records)
        )
    tool_records: list[str] = _tool_evidence_ledger_records(state)
    if tool_records:
        sections.append(
            "Tool evidence ledger (compact; entries + evidence IDs only — "
            "already resolved; IDs are provenance labels, not callable "
            "handles; never repeat raw bodies):\n"
            + "\n".join(tool_records[-entry_limit:])
        )
    return _format_query_output(
        "\n\n".join(sections), max_chars=MAX_LEDGER_PROMPT_CHARS
    )


def _payload_research_ledger_records(state: Any) -> list[str]:
    """Compact records from the executor-provided C1 research ledger.

    The adapt route runs research in the executor
    (``vibecomfy/executor/core.py::_run_implement``) and forwards the F01
    evidence ledger via ``payload["research_ledger"]`` — the dict form of
    ``EvidenceLedger.to_dict()``: ``{"entries": [{decision, conclusion,
    evidence_ids, uncertainty}, ...]}``.  Rendered in the same compact shape
    as the in-loop records so the implement agent sees consistent evidence.
    """
    request_payload = getattr(state, "request_payload", None)
    if not isinstance(request_payload, Mapping):
        return []
    raw_ledger = request_payload.get("research_ledger")
    if not isinstance(raw_ledger, Mapping):
        return []
    entries = raw_ledger.get("entries")
    if not isinstance(entries, list):
        return []
    records: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        decision = _compact_ledger_text(entry.get("decision") or "?", 160)
        conclusion = _compact_ledger_text(entry.get("conclusion") or "", 360)
        evidence_ids = entry.get("evidence_ids")
        evidence_text = (
            ", ".join(str(item)[:120] for item in evidence_ids[:8])
            if isinstance(evidence_ids, (list, tuple)) and evidence_ids
            else "(none)"
        )
        records.append(f"- {decision} — {conclusion} — evidence: {evidence_text}")
    return records


def _tool_evidence_ledger_records(state: Any) -> list[str]:
    """Compact cross-turn ledger records for Wave-A agent tool statements.

    Renders ONLY the F01 ledger entry (decision / conclusion) plus its
    evidence IDs from each prior turn's statement detail.  Raw tool result
    bodies are never included — that is the I01 ledger-only memory contract.
    """
    records: list[str] = []
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        turn_number = turn.get("turn_number")
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            tool_call = detail.get("tool_call")
            if not tool_call:
                continue
            entry = detail.get("ledger_entry")
            if not isinstance(entry, Mapping):
                # budget/deadline refusals: typed state is preserved but not
                # repeated as a ledger record (nothing was gathered)
                continue
            decision = _compact_ledger_text(entry.get("decision") or tool_call, 160)
            conclusion = _compact_ledger_text(entry.get("conclusion") or "", 360)
            evidence_ids = entry.get("evidence_ids")
            evidence_text = (
                ", ".join(str(item)[:120] for item in evidence_ids[:8])
                if isinstance(evidence_ids, (list, tuple)) and evidence_ids
                else "(none)"
            )
            status = str(detail.get("tool_status") or "?")
            records.append(
                f"- [turn {turn_number}] {decision} ({status}) — "
                f"{conclusion} — evidence: {evidence_text}"
            )
    return records


def _premature_missing_custom_node_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Return feedback for missing custom-node clarifies.

    Missing local signatures are handled by the edit/apply validation path.
    Do not force the batch model to perform registry research before it may
    stop cleanly; precedent research and authoring validation are separate
    responsibilities.
    """
    message_text = str(clarify_message or "").casefold()
    if not any(
        term in message_text
        for term in (
            "missing",
            "not installed",
            "install",
            "custom node",
            "schema-backed",
            "authoring evidence",
            "authoring path",
            "not authorable",
            "no schema",
        )
    ):
        return ""
    return ""


def _class_names_from_text(text: str) -> list[str]:
    names: list[str] = []
    # Underscore-joined identifiers (Rodin3D_Fusion, Stable_Zero123, ...) plus
    # bare CamelCase concrete classes (AudioLDM2, StableZero123, KSampler,
    # WanVideoModelLoader).  The CamelCase arm requires at least one lowercase
    # letter so acronyms and ordinary capitalized prose are not harvested.
    for match in re.findall(
        r"\b[A-Z][A-Za-z0-9_]*(?:_[A-Za-z0-9]+)+\b"
        r"|\b[A-Z][a-zA-Z0-9]*[a-z][a-zA-Z0-9]*\b",
        text,
    ):
        if match not in names:
            names.append(match)
    return names


def _resolver_candidate_is_authoring_capability(candidate: Mapping[str, Any]) -> bool:
    schema_payload = candidate.get("provisional_schema")
    if isinstance(schema_payload, Mapping):
        raw_schema = schema_payload.get("schema")
        if isinstance(raw_schema, Mapping):
            nodes = door_get_nodes(raw_schema) or raw_schema.get("object_info") or raw_schema
            if isinstance(nodes, Mapping) and nodes:
                return True
    evidence = candidate.get("evidence")
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        source = str(item.get("source") or "")
        tier = str(item.get("tier") or "")
        if source == "custom-node-map" or tier == "comfy-manager":
            return True
    return False


def _workflow_schema_classes_from_context(state: Any) -> list[str]:
    classes: list[str] = []

    def collect_from_source(source: Any) -> None:
        if not isinstance(source, Mapping):
            return
        workflow_schema = source.get("workflow_schema")
        if isinstance(workflow_schema, Mapping):
            for class_type in workflow_schema:
                text = str(class_type or "").strip()
                if text and text not in classes:
                    classes.append(text)
        value = source.get("workflow_schema_classes")
        if isinstance(value, list):
            for class_type in value:
                text = str(class_type or "").strip()
                if text and text not in classes:
                    classes.append(text)

    # D03: executor_research_sources removed; workflow schema classes come
    # from execution_protocol_notes.research_sources only.
    notes = getattr(state, "execution_protocol_notes", None)
    if isinstance(notes, Mapping):
        for source in notes.get("research_sources") or ():
            collect_from_source(source)

    return classes


def _selected_precedent_unknown_class_feedback(
    state: Any,
    batch_result: Any,
) -> str:
    """Return a terminal authoring blocker for unknown classes after precedent use."""
    notes = getattr(state, "execution_protocol_notes", None)
    if not isinstance(notes, Mapping):
        return ""
    selected = notes.get("selected_precedent")
    if not isinstance(selected, Mapping):
        return ""

    unknown_classes: list[str] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        if getattr(statement, "ok", True):
            continue
        diagnostics = getattr(statement, "diagnostics", ()) or ()
        for diagnostic in diagnostics:
            code = str(getattr(diagnostic, "code", "") or "")
            message = str(getattr(diagnostic, "message", "") or "")
            if code != "unknown_add_node_class_type":
                continue
            for match in re.findall(r"Unknown class_type '([^']+)'", message):
                if match not in unknown_classes:
                    unknown_classes.append(match)

    if not unknown_classes:
        return ""

    selected_name = str(selected.get("name") or "").strip()
    precedent_text = (
        f"the selected workflow precedent ({selected_name})"
        if selected_name
        else "the selected workflow precedent"
    )

    precedent_classes: list[str] = []
    for key in ("minimal_spine", "terminal_output_path"):
        value = selected.get(key)
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip()
                if text and text not in precedent_classes:
                    precedent_classes.append(text)
    for class_type in _workflow_schema_classes_from_context(state):
        if class_type not in precedent_classes:
            precedent_classes.append(class_type)

    invented_classes = [
        class_type for class_type in unknown_classes if class_type not in precedent_classes
    ]
    key_missing = [
        class_type
        for class_type in precedent_classes
        if class_type.startswith(("ADE_", "VHS_", "IPAdapter", "ControlNet"))
    ][:6]
    if not key_missing:
        key_missing = precedent_classes[:6]
    missing_text = ", ".join(key_missing) if key_missing else "the selected workflow classes"

    if invented_classes:
        invented_text = ", ".join(invented_classes[:4])
        return (
            f"I found {precedent_text}, but this edit session cannot author the "
            f"required workflow classes ({missing_text}). I also rejected invented replacement "
            f"class names ({invented_text}) because they were not present in the selected "
            "precedent or the current authoring schema. The graph is unchanged."
        )
    return (
        f"I found {precedent_text}, but this edit session cannot author the "
        f"required workflow classes ({missing_text}). The graph is unchanged."
    )


_PARAMETER_TWEAK_TARGET_TERMS = (
    "detail",
    "frame",
    "fps",
    "rate",
    "step",
    "strength",
    "cfg",
    "seed",
    "scale",
    "denoise",
    "resolution",
    "width",
    "height",
    "duration",
    "quality",
    "prompt",
    "format",
    "codec",
)


def _existing_parameter_tweak_targets_from_graph(
    graph: Any,
    *,
    query_text: str,
    seen_targets: set[str],
) -> list[tuple[int, str]]:
    """Rank existing nodes as parameter-tweak targets (EditableSurface-only).

    Accepts the retained IR (a workflow-like object with a ``nodes`` Mapping
    of IR nodes) or a UI-shaped graph (``nodes`` list of node dicts), and
    reads each node's writable surface exclusively through
    ``editable_surface_for`` — no settings-contract fallback.  The IR is the
    authority for the agent flow.
    """
    from vibecomfy.porting.edit.editable_surface import editable_surface_for

    nodes: Any = getattr(graph, "nodes", None)
    if isinstance(nodes, Mapping) and nodes:
        node_items = list(nodes.values())
        edges = getattr(graph, "edges", None)
    elif isinstance(nodes, (list, tuple)):
        node_items = [
            node for node in nodes if isinstance(node, Mapping)
        ]
        edges = None
    else:
        # The retained IR ``nodes`` mapping is the sole structural
        # authority; there is no UI-Mapping twin to fall back to.
        return []

    ranked_targets: list[tuple[int, str]] = []
    for node in node_items:
        class_type = str(
            getattr(node, "class_type", None)
            or (node.get("class_type") or node.get("type") if isinstance(node, Mapping) else "")
            or ""
        ).strip()
        if not class_type:
            continue
        node_id = getattr(node, "id", None)
        if node_id is None and isinstance(node, Mapping):
            node_id = node.get("id")
        if node_id is None:
            continue

        field_previews: list[str] = []
        have_compact_names = False
        try:
            surface = editable_surface_for(node, edges=edges)
            have_compact_names = bool(surface.literals or surface.inputs)
            for field in surface.literals:
                field_previews.append(field.name)
            compact_set = {preview.split("[")[0] for preview in field_previews}
            for slot in surface.inputs:
                if slot.name and slot.name not in compact_set:
                    field_previews.append(slot.name)
        except Exception:
            pass

        if not have_compact_names or not field_previews:
            continue

        # ── 5. Build preview and score ──
        preview = ", ".join(field_previews)
        class_text = class_type.casefold()
        field_text = " ".join(field_previews).casefold()
        score = 0
        if any(term in class_text for term in _PARAMETER_TWEAK_TARGET_TERMS):
            score += 5
        if any(term in field_text for term in _PARAMETER_TWEAK_TARGET_TERMS):
            score += 4
        if any(token and token in class_text for token in query_text.split() if len(token) >= 5):
            score += 4
        if any(token and token in field_text for token in query_text.split() if len(token) >= 5):
            score += 3
        if have_compact_names or field_previews:
            score += 3
        if class_type == "ACN_AdvancedControlNetApply" and "controlnet" in query_text:
            score += 8
        if class_type in {"MarkdownNote", "Preview3D", "SaveVideo", "LoadImage"}:
            score -= 6
        target = f"{class_type} [{node_id}] ({preview})"
        if target in seen_targets:
            continue
        seen_targets.add(target)
        ranked_targets.append((score, target))
    return ranked_targets


def _edit_noop_requires_graph_evidence_feedback(state: Any) -> str:
    from ._frag_research import _canonical_agent_edit_route, _executor_classification_text  # T-038 late import: sibling cycle broken; resolved at call time
    route = _canonical_agent_edit_route(getattr(state, "route", None))
    if route not in {"revise", "adapt", "dev"}:
        return ""
    text = (
        f"{getattr(state, 'task', '')} "
        f"{getattr(state, 'request_payload', {}).get('query', '')} "
        f"{_executor_classification_text(state)}"
    ).casefold()
    if not any(
        term in text
        for term in (
            "edit",
            "change",
            "replace",
            "rewire",
            "connect",
            "increase",
            "decrease",
            "adjust",
            "set",
            "save",
            "extract",
        )
    ):
        return ""
    return (
        "No-op proof requirement: this is an edit route. Do not answer that the graph already satisfies "
        "the request unless you can cite the exact current node ids, fields/widgets, and/or link endpoints "
        "that prove the requested state already exists. If that proof is not explicit in the rendered graph "
        "or graph facts, land the smallest safe local edit instead of using done() as a no-op."
    )


__all__ = (
     "_PARAMETER_TWEAK_TARGET_TERMS",
     "_batch_research_memory_summary", "_class_names_from_text",
     "_edit_noop_requires_graph_evidence_feedback",
     "_existing_parameter_tweak_targets_from_graph", "_format_available_node_names",
     "_format_node_variable_index", "_format_query_output", "_format_statement_source",
     "_iter_ui_nodes", "_normalize_test_client_batch_response",
     "_normalize_test_client_response",
     "_premature_missing_custom_node_clarify_feedback", "_present_class_types",
     "_render_batch_diff", "_resolver_candidate_is_authoring_capability",
     "_selected_precedent_unknown_class_feedback",
     "_workflow_schema_classes_from_context", "node_settings_for",
)
