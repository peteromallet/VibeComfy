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
from vibecomfy.comfy_nodes.agent.contracts import _ui_node_uid
from vibecomfy.comfy_nodes.agent.provider import AgentTurnResult, BatchTurnResult

from vibecomfy.porting.widgets.settings_contract import node_settings_for

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
            nodes = value.get("nodes")
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
    """Enumerate class types currently present in an EditSession working graph."""
    working_ui = getattr(session, "working_ui", None)
    if not isinstance(working_ui, Mapping):
        return []
    types: set[str] = set()
    for node in _iter_ui_nodes(working_ui):
        class_type = node.get("type") or node.get("class_type")
        if isinstance(class_type, str) and class_type:
            types.add(class_type)
    return sorted(types)


def _format_node_variable_index(session: Any) -> str:
    """Return ``var = ClassType`` lines for the current EditSession graph."""
    working_ui = getattr(session, "working_ui", None)
    name_by_uid = getattr(session, "name_by_uid", None)
    if not isinstance(working_ui, Mapping) or not isinstance(name_by_uid, Mapping):
        return ""
    rows: list[tuple[str, str, str]] = []
    for node in _iter_ui_nodes(working_ui):
        uid = _ui_node_uid(node)
        if not uid:
            continue
        name = name_by_uid.get(uid)
        class_type = node.get("type") or node.get("class_type")
        if isinstance(name, str) and name and isinstance(class_type, str) and class_type:
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

    Packet-aware: when a statement detail includes ``precedent_packet``, a
    compact summary is built from structured option fields (source title,
    source tier, one-line pattern summary, caveat count) instead of
    reserializing the full packet or dumping ``query_output`` verbatim.
    Statements without a packet fall back to the marker-matched
    ``query_output`` path for non-research turns (e.g. ``search()``).
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

            # ── packet-aware compact path ────────────────────────────
            precedent_packet = detail.get("precedent_packet")
            if isinstance(precedent_packet, Mapping):
                packet_record = _summarize_precedent_packet(
                    precedent_packet, turn_number
                )
                if packet_record:
                    records.append(packet_record)
                continue

            # ── legacy marker-matched query_output path ──────────────
            query_output = str(detail.get("query_output") or "").strip()
            # B03: any research() statement carries its query into memory —
            # including message-kind results and community paragraphs.  This is
            # prompt memory so the agent can judge relevance and iterate; it is
            # not a latch and never a stop decision.
            relevant = bool(detail.get("research_query")) or (
                bool(query_output)
                and any(
                    marker in query_output
                    for marker in (
                        "Concrete workflow pattern found",
                        "github_workflow_json",
                        "source_workflow_path",
                        "No node signature found",
                        "Registry check",
                        "hivemind_message",
                        "hivemind_distillation",
                        "community_summary",
                        "No community discussion found",
                    )
                )
            ) or bool(detail.get("resolver_candidates"))
            if not relevant:
                continue
            query = str(detail.get("research_query") or detail.get("query") or "").strip()
            sources = detail.get("requested_research_sources") or detail.get("research_sources")
            source_text = f" sources={tuple(sources)!r}" if isinstance(sources, (list, tuple)) else ""
            header = f"turn {turn_number}: {query or statement.get('source') or 'query'}{source_text}"
            records.append(f"- {header}\n{_format_query_output(query_output, max_chars=1000)}")
    # B03: echo classify search_directions once at the top of the memory block so
    # later turns still see candidate terms (the Research brief itself is
    # turn-0 only).  Prompt-visible, never executed — the model may ignore them
    # or invent better ones.  The header only rides on actual prior-turn
    # records; with no records there is no memory block (the brief already
    # showed the directions on turn 0).
    if not records:
        return ""
    brief = getattr(state, "executor_research_brief", None)
    directions = (
        brief.get("search_directions") if isinstance(brief, Mapping) else None
    )
    header = ""
    if isinstance(directions, (list, tuple)) and directions:
        shown = ", ".join(str(d) for d in directions[:5] if str(d).strip())
        if shown:
            header = (
                "Candidate search terms (optional; you may use these or invent "
                f"better ones): {shown}\n\n"
            )
    body = "\n\n".join(records[-max_items:])
    return (header + body).strip()


def _summarize_precedent_packet(
    packet: Mapping[str, Any], turn_number: Any
) -> str | None:
    """Build a compact one-line-per-option summary from a precedent packet dict.

    Carries only source title, source tier, one-line pattern summary, and
    caveat count.  Does **not** reserialize the full packet and omits every
    forbidden public-key name (winner, best, selected, score, rank, primary,
    preferred, chosen, pick, choice, top, recommended).
    """
    options = packet.get("options")
    if not isinstance(options, (list, tuple)) or not options:
        return None

    packet_warnings = packet.get("warnings")
    packet_caveats = (
        len(packet_warnings) if isinstance(packet_warnings, (list, tuple)) else 0
    )

    lines: list[str] = [
        f"turn {turn_number}: research evidence "
        f"({len(options)} precedent option(s)):"
    ]
    for opt in options:
        if not isinstance(opt, Mapping):
            continue

        title = str(opt.get("source_class_type") or "(unknown)")

        # ── one-line pattern summary ─────────────────────────────────
        description = str(opt.get("description", "")).strip()
        if description:
            summary_line = description.split("\n")[0].strip()
            if len(summary_line) > 120:
                summary_line = summary_line[:117] + "..."
        else:
            summary_line = "(no description)"

        # ── source tier from notes ───────────────────────────────────
        notes = opt.get("notes")
        tier = ""
        option_caveats = 0
        if isinstance(notes, (list, tuple)):
            for note in notes:
                if not isinstance(note, str):
                    continue
                if note.startswith("source: "):
                    tier = note[len("source: "):]
                elif note.strip():
                    option_caveats += 1

        caveats = packet_caveats + option_caveats
        caveat_str = f" [{caveats} caveat(s)]" if caveats else ""
        tier_str = f" tier={tier}" if tier else ""

        lines.append(f"  - {title}{tier_str}: {summary_line}{caveat_str}")

    return "\n".join(lines)


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
            nodes = raw_schema.get("nodes") or raw_schema.get("object_info") or raw_schema
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

    for source in getattr(state, "executor_research_sources", ()) or ():
        collect_from_source(source)

    notes = getattr(state, "execution_protocol_notes", None)
    if isinstance(notes, Mapping):
        for source in notes.get("research_sources") or ():
            collect_from_source(source)

    return classes


def _workflow_schema_relevant_clarify(clarify_message: str) -> bool:
    text = str(clarify_message or "").casefold()
    if not text:
        return False
    schema_terms = ("schema", "signature", "input", "output", "wire", "construct", "missing")
    capability_terms = ("cannot", "couldn't", "unable", "need", "required", "lack", "not present", "not found")
    return any(term in text for term in schema_terms) and any(
        term in text for term in capability_terms
    )


def _premature_workflow_schema_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Reject stops that ignore parseable workflow schema already in context."""
    if not _workflow_schema_relevant_clarify(clarify_message):
        return ""

    class_names = _class_names_from_text(str(clarify_message or ""))
    workflow_schema_classes = _workflow_schema_classes_from_context(state)
    if not workflow_schema_classes:
        return ""

    mentioned_available = [
        class_type for class_type in class_names if class_type in workflow_schema_classes
    ]
    if class_names and not mentioned_available:
        return ""

    class_text = ", ".join((mentioned_available or workflow_schema_classes)[:8])
    return (
        "Premature workflow-schema clarification rejected: parseable workflow precedent "
        f"already provides provisional authoring evidence for ({class_text}). Do not ask "
        "the user for signatures that are already in "
        "execution_protocol_notes.research_sources[].workflow_schema."
    )


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


_PARAMETER_TWEAK_ACTION_TERMS = (
    "increase",
    "decrease",
    "adjust",
    "tweak",
    "change",
    "set",
    "raise",
    "lower",
    "reduce",
    "boost",
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


def _task_looks_like_parameter_tweak(state: Any) -> bool:
    # Additive / restore intent (add/re-add/restore/insert a node, "missing",
    # "gone", "no longer") must NEVER be classified as a parameter tweak: the
    # tweak path injects "Stop searching, do not add or replace nodes" before
    # turn 1, which poisons additive edits.  Bail out first.
    from ._frag_research import _executor_classification_text  # T-038 late import: sibling cycle broken; resolved at call time
    if _task_looks_like_additive(state):
        return False
    text = (
        f"{getattr(state, 'task', '')} "
        f"{getattr(state, 'request_payload', {}).get('query', '')} "
        f"{_executor_classification_text(state)}"
    ).casefold()
    return any(term in text for term in _PARAMETER_TWEAK_ACTION_TERMS) and any(
        term in text for term in _PARAMETER_TWEAK_TARGET_TERMS
    )


# Structural verbs that signal ADDITIVE / restore intent (re-add a removed
# feature, insert a node, attach/rewire something missing).  When present, the
# task is NOT a parameter tweak and must NOT receive "edit an existing node /
# do not add nodes" hardening.  Prefer multi-word phrases to avoid false
# positives ("add" as a bare substring would match "address"/"added").
_ADDITIVE_INTENT_PHRASES = (
    "re-add",
    "re-add",
    "readd",
    "re-introduce",
    "re-introduce",
    "re-instate",
    "reinstate",
    "bring back",
    "put back",
    "add back",
    "no longer",
    "add an",
    "add a ",
    "add the",
    "add new",
    "missing",
    "removed",
    "gone",
    "disappeared",
    "restore",
    "insert",
    "attach",
    "rewire",
    "connect",
)
_ADDITIVE_INTENT_STANDALONE = (
    "restore",
    "reinstate",
    "insert",
    "attach",
    "rewire",
    "missing",
    "removed",
    "gone",
    "disappeared",
)


def _task_looks_like_additive(state: Any) -> bool:
    """Return True when the task text signals ADDITIVE / restore intent.

    Composes ``state.task``, ``request_payload['query']``, and the executor
    classification text (intent/route/task), casefolded.  Matches explicit
    multi-word structural phrases (``"add back"``, ``"bring back"``, ``"missing"``,
    ``"restore"``, …) plus the conservative ``"add a/an/the/new"`` lead-ins.

    Conservative by design: bare ``"add"`` is NOT matched on its own (it would
    false-fire on ``"address"``/``"added"``/``"add-on"``); only the multi-word
    phrases and standalone structural verbs are.
    """
    from ._frag_research import _executor_classification_text  # T-038 late import: sibling cycle broken; resolved at call time
    text = (
        f"{getattr(state, 'task', '')} "
        f"{getattr(state, 'request_payload', {}).get('query', '')} "
        f"{_executor_classification_text(state)}"
    ).casefold()
    if any(phrase in text for phrase in _ADDITIVE_INTENT_PHRASES):
        return True
    # Word-boundary match for standalone structural verbs so "restore"/"insert"
    # fire even when they appear without a multi-word phrase, but never as a
    # substring of a larger word.
    tokens = set()
    for chunk in text.split():
        # strip lightweight punctuation so "restore." / "insert," match.
        tokens.add(chunk.strip(".,;:!?\"'()[]{}"))
    return any(token in tokens for token in _ADDITIVE_INTENT_STANDALONE)



def _existing_parameter_tweak_targets(state: Any, *, max_targets: int = 4) -> list[str]:
    graphs: list[Mapping[str, Any]] = []
    graph = getattr(state, "graph", None)
    if isinstance(graph, Mapping):
        graphs.append(graph)
    request_payload = getattr(state, "request_payload", None)
    if isinstance(request_payload, Mapping):
        request_graph = request_payload.get("graph")
        if isinstance(request_graph, Mapping) and request_graph is not graph:
            graphs.append(request_graph)
    if not graphs and graph is not None:
        nodes = getattr(graph, "nodes", None)
        if isinstance(nodes, (Mapping, list)):
            graphs.append({"nodes": nodes})

    if not graphs:
        return []

    query_text = (
        f"{getattr(state, 'task', '')} {getattr(state, 'request_payload', {}).get('query', '')}"
    ).casefold()
    ranked_targets: list[tuple[int, str]] = []
    seen_targets: set[str] = set()
    for graph_payload in graphs:
        ranked_targets.extend(
            _existing_parameter_tweak_targets_from_graph(
                graph_payload,
                query_text=query_text,
                seen_targets=seen_targets,
            )
        )

    ranked_targets.sort(key=lambda item: (-item[0], item[1]))
    return [target for _score, target in ranked_targets[:max_targets]]


def _existing_parameter_tweak_targets_from_graph(
    graph: Mapping[str, Any],
    *,
    query_text: str,
    seen_targets: set[str],
) -> list[tuple[int, str]]:
    nodes: Any = graph.get("nodes")
    if not isinstance(nodes, (Mapping, list)):
        # The rich ``nodes`` mapping (or UI list) is the sole structural
        # authority; there is no compiled_api twin to fall back to.
        return []
    if isinstance(nodes, Mapping):
        node_items = list(nodes.items())
    elif isinstance(nodes, list):
        node_items = [
            (
                str(node.get("id") or index),
                node,
            )
            for index, node in enumerate(nodes)
            if isinstance(node, Mapping)
        ]
    else:
        return []

    ranked_targets: list[tuple[int, str]] = []
    for node_id, node in node_items:
        if not isinstance(node, Mapping):
            continue
        class_type = str(node.get("class_type") or node.get("type") or "").strip()
        if not class_type:
            continue
        inputs = node.get("inputs")

        # ── 1. Capture scalar input fields (unconnected defaults) ──
        input_fields: list[str] = []
        if isinstance(inputs, Mapping):
            input_fields = [
                str(name)
                for name, value in inputs.items()
                if not isinstance(value, (Mapping, list, tuple))
            ]
        if isinstance(inputs, list):
            for input_spec in inputs:
                if not isinstance(input_spec, Mapping):
                    continue
                if input_spec.get("link") is not None:
                    continue
                name = input_spec.get("name")
                if isinstance(name, str) and name:
                    input_fields.append(name)

        # ── 2. Primary: compact field names via shared settings contract ──
        field_previews: list[str] = []
        have_compact_names = False
        try:
            info = node_settings_for(node, class_type)
            if info.fields:
                have_compact_names = True
                for field in info.fields:
                    name = field.name
                    # Capped enum annotations: show up to 3 choices for enum fields
                    if field.choices and not name.startswith("widget_"):
                        choices = list(field.choices)
                        if len(choices) <= 3:
                            enum_hint = "|".join(choices)
                        else:
                            shown = choices[:3]
                            remaining = len(choices) - 3
                            enum_hint = "|".join(shown) + f"|+{remaining}"
                        name = f"{name}[{enum_hint}]"
                    field_previews.append(name)
        except Exception:
            pass

        # ── 3. Fallback: old widget resolution when settings_contract can't help ──
        widget_fields: list[str] = []
        raw_widget_count = None
        if not have_compact_names:
            widgets = node.get("widgets")
            raw_widgets = node.get("raw_widgets")
            if isinstance(widgets, Mapping):
                widget_fields = [str(name) for name in sorted(widgets, key=str)]
            elif isinstance(widgets, list):
                widget_fields = [
                    str(widget.get("name") or f"widget_{index}")
                    for index, widget in enumerate(widgets)
                    if isinstance(widget, Mapping)
                ]
            widget_values = node.get("widgets_values") if isinstance(node, Mapping) else None
            if not widget_fields and isinstance(widget_values, list):
                widget_fields = [f"widget_{index}" for index in range(min(len(widget_values), 4))]
            if isinstance(raw_widgets, Mapping):
                values = raw_widgets.get("values")
                if isinstance(values, list):
                    raw_widget_count = len(values)
            elif raw_widgets is not None:
                values = getattr(raw_widgets, "values", None)
                if isinstance(values, list):
                    raw_widget_count = len(values)

        # ── 4. Assemble final field list ──
        if have_compact_names:
            # Merge input fields (deduped against compact widget names) +
            # compact names.  Strip enum annotation brackets for dedup.
            merged: list[str] = []
            compact_set = {f.split("[")[0] for f in field_previews}
            for inp in input_fields:
                if inp not in compact_set:
                    merged.append(inp)
            merged.extend(field_previews)
            field_previews = merged
        else:
            field_previews = input_fields + widget_fields
            if raw_widget_count and not widget_fields:
                field_previews.extend(
                    f"widget_{index}" for index in range(min(raw_widget_count, 4))
                )

        if not field_previews:
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
        if have_compact_names or widget_fields or raw_widget_count:
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


def _direct_existing_parameter_tweak_feedback(
    state: Any,
    clarify_message: str | None = None,
) -> str:
    # Additive / restore intent must not receive "edit an existing node / do not
    # add or replace nodes" guidance — that poisons additive edits across the
    # intro/apply/finish call sites.  (Also covered by
    # _task_looks_like_parameter_tweak, but the explicit guard keeps the
    # contract obvious and survives refactors.)
    if _task_looks_like_additive(state):
        return ""
    if not _task_looks_like_parameter_tweak(state):
        return ""
    if clarify_message is not None:
        message_text = str(clarify_message or "").casefold()
        if not any(
            term in message_text
            for term in ("precedent", "schema", "custom node", "not found", "missing", "cannot")
        ):
            return ""
    targets = _existing_parameter_tweak_targets(state)
    if not targets:
        return ""
    target_text = "; ".join(targets)
    return (
        "Direct existing-node tweak fallback applies here: the current graph already contains editable "
        f"target nodes ({target_text}). Stop searching for workflow precedent. Land the smallest local "
        "parameter change on the existing node instead. Prefer a visible named field when present; when "
        "the node is already in the graph and only stable widget slots are visible, a minimal existing "
        "`widget_N` tweak is allowed as a last-resort local parameter edit. Do not add or replace nodes."
    )


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


def _targeted_edit_hardening_feedback(state: Any) -> str:
    """Return narrow deterministic guidance for known ambiguous edit intents."""
    # Additive / restore intent: same-type siblings must NOT trigger "edit an
    # existing node" hardening for an explicit add/restore request.
    from ._frag_research import _executor_classification_text  # T-038 late import: sibling cycle broken; resolved at call time
    if _task_looks_like_additive(state):
        return ""
    text = (
        f"{getattr(state, 'task', '')} "
        f"{getattr(state, 'request_payload', {}).get('query', '')} "
        f"{_executor_classification_text(state)}"
    ).casefold()
    notes: list[str] = []
    if (
        "first frame" in text
        and "save" in text
        and ("png" in text or "image" in text)
    ):
        notes.append(
            "First-frame extraction hardening: if a video-producing node is already wired directly "
            "to SaveImage for the requested static PNG/image output, do not no-op just because the "
            "video node's custom class is unknown. Insert a minimal local `vibecomfy.exec` frame "
            "extractor (`image[0:1]`) between the video output and SaveImage, then rewire SaveImage "
            "to that extractor. This is a localized additive edit; do not replace the video node."
        )
    if (
        "controlnet" in text
        and ("strength" in text or "pose" in text or "conditioning" in text)
        and ("increase" in text or "raise" in text or "boost" in text or "stronger" in text)
    ):
        notes.append(
            "ACN ControlNet strength hardening: when editing an existing "
            "`ACN_AdvancedControlNetApply` node for stronger pose/conditioning and the rendered graph "
            "shows a concrete strength-like field/widget, increase that existing knob first. Do not "
            "prefer ambiguous override fields unless the user explicitly asks for that override."
        )
    targets = _existing_parameter_tweak_targets(state, max_targets=2)
    if targets:
        target_text = "; ".join(targets)
        notes.append(
            "Targeted edit hardening: this was a read-only turn, but the current canvas already exposes "
            f"concrete editable targets ({target_text}). On the next turn, make a minimal local edit against "
            "one of those existing nodes instead of continuing analysis."
        )
    return "\n\n".join(notes)


__all__ = (
     "_ADDITIVE_INTENT_PHRASES", "_ADDITIVE_INTENT_STANDALONE",
     "_PARAMETER_TWEAK_ACTION_TERMS", "_PARAMETER_TWEAK_TARGET_TERMS",
     "_batch_research_memory_summary", "_class_names_from_text",
     "_direct_existing_parameter_tweak_feedback",
     "_edit_noop_requires_graph_evidence_feedback", "_existing_parameter_tweak_targets",
     "_existing_parameter_tweak_targets_from_graph", "_format_available_node_names",
     "_format_node_variable_index", "_format_query_output", "_format_statement_source",
     "_iter_ui_nodes", "_normalize_test_client_batch_response",
     "_normalize_test_client_response",
     "_premature_missing_custom_node_clarify_feedback",
     "_premature_workflow_schema_clarify_feedback", "_present_class_types",
     "_render_batch_diff", "_resolver_candidate_is_authoring_capability",
     "_selected_precedent_unknown_class_feedback", "_summarize_precedent_packet",
     "_targeted_edit_hardening_feedback", "_task_looks_like_additive",
     "_task_looks_like_parameter_tweak", "_workflow_schema_classes_from_context",
     "_workflow_schema_relevant_clarify", "node_settings_for",
)
