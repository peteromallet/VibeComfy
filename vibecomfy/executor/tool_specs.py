"""Declarative agent tool registry — the single source of truth for the
agent-invoked tool surface (I01/C01).

One :class:`ToolSpec` per named tool carries everything the pipeline needs:
the phase partition (research vs implement), the argument contract, the
effort-budget class, the handler (tool-module invocation), and the ledger
projector (evidence artifacts + compact F01 ledger entry + current-turn
digest for one completed call).

Parser admission (``_parse._AGENT_TOOL_CALL_NAMES``), resolve-time dispatch
and budget enforcement (``_resolve``), and the per-phase tool catalog in the
provider prompts are all derived from :data:`TOOL_SPECS` — a tool's name,
phase, arguments, and documentation exist in exactly one place.

Phase partition (docs/agent-judgment-pipeline.md §4):
* research  — ``hivemind_search``, ``hivemind_get``, ``registry_lookup``,
  ``web_search`` (last resort, disabled by default)
* implement — ``node_schema``, ``ready_template_list``,
  ``ready_template_load``, ``rank_edit_targets``, ``suggest_seed_nodes``,
  ``layout_hints``

The implement agent does NOT get the research tools, and the research agent
does NOT get the implement tools.  Unknown phase contexts (offline/standalone
validation without a session phase marker) are permissive so parsers and
tests can validate either phase.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from vibecomfy.executor.evidence_pack import EvidenceArtifact
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

PHASE_RESEARCH = "research"
PHASE_IMPLEMENT = "implement"

_PHASES = frozenset({PHASE_RESEARCH, PHASE_IMPLEMENT})


def _shorten_query_text(value: Any, *, max_chars: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def _safe_token(value: Any, *, max_chars: int = 48) -> str:
    """Deterministic slug for generated evidence IDs."""
    text = re.sub(r"[^a-z0-9_\-]+", "-", str(value or "").strip().casefold()).strip("-")
    if not text:
        text = "value"
    if len(text) > max_chars:
        text = text[: max_chars - 9] + "-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return text


def _tool_evidence_id(*parts: str) -> str:
    return "tool:" + "-".join(_safe_token(part) for part in parts)


def _tool_arg_summary(args: Mapping[str, Any], *, max_chars: int = 140) -> str:
    """Compact, deterministic argument summary for digests."""
    items: list[str] = []
    for key in ("query", "evidence_id", "node_class", "template_id", "capability", "intent", "operation"):
        if key in args:
            value = str(args[key])
            items.append(f"{key}={value!r}")
    if not items:
        items.extend(f"{key}={value!r}" for key, value in sorted(args.items()))
    return _shorten_query_text(", ".join(items), max_chars=max_chars)


def _ledger_entry_dict(
    decision: str,
    conclusion: str,
    evidence_ids: tuple[str, ...],
    uncertainty: str = "",
) -> dict[str, Any]:
    return {
        "decision": decision,
        "conclusion": conclusion,
        "evidence_ids": list(evidence_ids),
        "uncertainty": uncertainty,
    }


def _status_ledger_entry(call_name: str, result: ToolResult) -> dict[str, Any]:
    """Compact ledger entry for a non-ok tool result (typed state preserved)."""
    status = result.status.value
    message = result.diagnostics[0].message if result.diagnostics else status
    retry = ""
    if result.retry_after_seconds is not None:
        retry = f" (retry_after={result.retry_after_seconds:g}s)"
    return _ledger_entry_dict(
        decision=f"{call_name}",
        conclusion=f"{status}{retry}: {message}",
        evidence_ids=(),
        uncertainty="",
    )


def _format_tool_digest(call_name: str, args: Mapping[str, Any], result: ToolResult) -> str:
    """Compact digest for the CURRENT turn; never raw result bodies."""
    if result.status is ToolStatus.OK:
        # ok digests are built by the per-tool ledger projectors
        return ""
    summary = _tool_arg_summary(args)
    message = result.diagnostics[0].message if result.diagnostics else result.status.value
    retry = ""
    if result.retry_after_seconds is not None:
        retry = f" (retry_after={result.retry_after_seconds:g}s)"
    return f"{call_name}({summary}) — {result.status.value}{retry}: {message}"


def _hit_line(hit: Mapping[str, Any], index: int) -> str:
    title = _shorten_query_text(
        hit.get("title") or hit.get("body") or "(untitled)", max_chars=90
    )
    url = str(hit.get("url") or "")
    suffix = f" {url}" if url else ""
    return f"  hit {index}: {title} [{hit.get('evidence_id') or '?'}]{suffix}"


# ── ledger projectors (one per tool) ────────────────────────────────────────


def _hivemind_search_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    hits = [hit for hit in (body.get("hits") or ()) if isinstance(hit, Mapping)]
    artifacts: dict[str, EvidenceArtifact] = {}
    for hit in hits:
        evidence_id = str(hit.get("evidence_id") or "")
        if not evidence_id:
            continue
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="hivemind_search_hit",
            body=dict(hit),
            source="hivemind",
        )
    ids = tuple(artifacts)
    titles = [
        text
        for text in (
            _shorten_query_text(
                hit.get("title") or hit.get("body") or "", max_chars=80
            )
            for hit in hits
        )
        if text
    ]
    conclusion = f"{len(hits)} hit(s)"
    if titles:
        conclusion += ": " + " | ".join(titles)[:380].rstrip()
    entry = _ledger_entry_dict(
        decision=f"hivemind_search {_tool_arg_summary(args)}",
        conclusion=conclusion,
        evidence_ids=ids,
        uncertainty="",
    )
    lines = [f"hivemind_search({_tool_arg_summary(args)}) — ok: {len(hits)} hit(s)"]
    lines.extend(_hit_line(hit, index) for index, hit in enumerate(hits, start=1))
    if body.get("has_more") and body.get("next_cursor"):
        lines.append(f"  more available; next_cursor={body.get('next_cursor')!r}")
    return artifacts, entry, "\n".join(lines)


def _hivemind_get_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    row = body.get("row") if isinstance(body.get("row"), Mapping) else {}
    evidence_id = str(
        body.get("evidence_id")
        or (result.evidence_ids[0] if result.evidence_ids else "")
        or ""
    )
    artifacts: dict[str, EvidenceArtifact] = {}
    if evidence_id:
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="hivemind_record",
            body=dict(row) if row else {},
            source=str(body.get("source_type") or "hivemind"),
        )
    ids = (evidence_id,) if evidence_id else ()
    source_type = str(body.get("source_type") or "record")
    title = _shorten_query_text(
        row.get("title") or row.get("name") or row.get("class_type") or "", max_chars=120
    )
    conclusion = f"{source_type} record {evidence_id}" + (f": {title}" if title else "")
    entry = _ledger_entry_dict(
        decision=f"hivemind_get {evidence_id!r}",
        conclusion=conclusion,
        evidence_ids=ids,
        uncertainty="",
    )
    lines = [f"hivemind_get({_tool_arg_summary(args)}) — ok: {source_type} record"]
    if title:
        lines.append(f"  title: {title}")
    for key in ("url", "author", "channel", "created_at", "status", "confidence", "score"):
        if key in row and row[key] is not None and str(row[key]).strip():
            lines.append(f"  {key}: {_shorten_query_text(str(row[key]), max_chars=140)}")
    return artifacts, entry, "\n".join(lines)


def _web_search_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    results = [item for item in (body.get("results") or ()) if isinstance(item, Mapping)]
    artifacts: dict[str, EvidenceArtifact] = {}
    for rank, item in enumerate(results):
        evidence_id = result.evidence_ids[rank] if rank < len(result.evidence_ids) else ""
        if not evidence_id:
            continue
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="web_search_result",
            body=dict(item),
            source="web",
        )
    ids = tuple(artifacts)
    titles = [
        text
        for text in (
            _shorten_query_text(item.get("title") or "", max_chars=80)
            for item in results
        )
        if text
    ]
    conclusion = f"{len(results)} result(s)"
    if titles:
        conclusion += ": " + " | ".join(titles)[:380].rstrip()
    entry = _ledger_entry_dict(
        decision=f"web_search {_tool_arg_summary(args)}",
        conclusion=conclusion,
        evidence_ids=ids,
        uncertainty="",
    )
    lines = [f"web_search({_tool_arg_summary(args)}) — ok: {len(results)} result(s)"]
    for index, item in enumerate(results, start=1):
        evidence_id = result.evidence_ids[index - 1] if index - 1 < len(result.evidence_ids) else ""
        lines.append(
            f"  result {index}: {_shorten_query_text(item.get('title') or '(untitled)', max_chars=90)} "
            f"[{evidence_id or '?'}] {item.get('url') or ''}".rstrip()
        )
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            lines.append(f"    {_shorten_query_text(snippet, max_chars=180)}")
    return artifacts, entry, "\n".join(lines)


def _registry_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    node_class = str(body.get("node_class") or args.get("node_class") or "class")
    evidence_id = _tool_evidence_id("registry_lookup", node_class)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="registry_resolution",
            body=dict(body),
            source="comfy-registry",
        )
    }
    candidates = [c for c in (body.get("candidates") or ()) if isinstance(c, Mapping)]
    candidate_text = "; ".join(
        _shorten_query_text(
            str(c.get("ref", {}).get("slug") or c.get("ref", {}).get("name") or "pack"), max_chars=60
        )
        for c in candidates
    )
    conclusion = (
        f"exact ownership: {bool(body.get('exact_ownership'))}"
        + (f"; candidates: {candidate_text}" if candidate_text else "")
    )
    entry = _ledger_entry_dict(
        decision=f"registry_lookup {node_class!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [
        f"registry_lookup({_tool_arg_summary(args)}) — ok: exact ownership "
        f"{bool(body.get('exact_ownership'))}"
    ]
    for candidate in candidates:
        ref = candidate.get("ref") if isinstance(candidate.get("ref"), Mapping) else {}
        expected = candidate.get("expected_classes") or ()
        lines.append(
            f"  pack {ref.get('slug') or ref.get('name') or '?'} ({ref.get('source') or '?'}) "
            f"expected_classes={list(expected) if isinstance(expected, (list, tuple)) else expected}"
        )
    return artifacts, entry, "\n".join(lines)


def _node_schema_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    class_type = str(body.get("class_type") or args.get("node_class") or "class")
    evidence_id = _tool_evidence_id("node_schema", class_type)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="node_schema",
            body=dict(body),
            source="schema",
        )
    }
    inputs = body.get("input_names") or ()
    outputs = body.get("outputs") or ()
    output_text = ", ".join(
        str(output.get("type") or "") for output in outputs if isinstance(output, Mapping)
    )
    conclusion = (
        f"class {class_type} available: {bool(body.get('available'))}"
        + (f"; inputs: {len(inputs)}; outputs: [{output_text}]" if output_text else "")
    )
    entry = _ledger_entry_dict(
        decision=f"node_schema {class_type!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [
        f"node_schema({_tool_arg_summary(args)}) — ok: available={bool(body.get('available'))}",
        f"  inputs: {', '.join(str(item) for item in inputs) or '(none)'}",
        f"  outputs: [{output_text}]",
    ]
    return artifacts, entry, "\n".join(lines)


def _ready_template_list_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    filter_text = str(body.get("filter") or args.get("capability") or "all")
    evidence_id = _tool_evidence_id("ready_template_list", filter_text or "all")
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="ready_template_inventory",
            body=dict(body),
            source="ready_templates",
        )
    }
    rows = [row for row in (body.get("templates") or ()) if isinstance(row, Mapping)]
    ids = [str(row.get("id") or "") for row in rows]
    conclusion = f"{body.get('count', len(rows))} template(s) for filter {filter_text!r}"
    if ids:
        conclusion += ": " + ", ".join(ids)[:380]
    entry = _ledger_entry_dict(
        decision=f"ready_template_list {filter_text!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [
        f"ready_template_list({_tool_arg_summary(args)}) — ok: {len(rows)} template(s)",
        *[f"  - {template_id}" for template_id in ids],
    ]
    return artifacts, entry, "\n".join(lines)


def _ready_template_load_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    template_id = str(body.get("id") or args.get("template_id") or "template")
    evidence_id = _tool_evidence_id("ready_template_load", template_id)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="ready_template",
            body=dict(body),
            source="ready_templates",
        )
    }
    conclusion = (
        f"template {template_id} sha256={body.get('sha256')} size={body.get('size_bytes')}"
    )
    entry = _ledger_entry_dict(
        decision=f"ready_template_load {template_id!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [
        f"ready_template_load({_tool_arg_summary(args)}) — ok",
        f"  id: {template_id} path: {body.get('path') or ''} scope: {body.get('scope') or ''}",
        f"  sha256: {body.get('sha256')} size: {body.get('size_bytes')} bytes",
    ]
    content = body.get("content")
    if isinstance(content, str) and content.strip():
        excerpt = _shorten_query_text(content, max_chars=1200)
        truncated = " [truncated]" if len(content) > 1200 else ""
        lines.append(f"  content excerpt (evidence_id {evidence_id}; full body not echoed):{truncated}\n{excerpt}")
    return artifacts, entry, "\n".join(lines)


def _rank_edit_targets_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    intent = str(body.get("intent") or args.get("intent") or "intent")
    evidence_id = _tool_evidence_id("rank_edit_targets", intent)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="edit_target_ranking",
            body=dict(body),
            source="graph",
        )
    }
    candidates = [c for c in (body.get("candidates") or ()) if isinstance(c, Mapping)]
    labels = [_shorten_query_text(str(c.get("class_type") or c.get("node_id") or "?"), max_chars=60) for c in candidates]
    conclusion = f"case={body.get('case')}; {len(candidates)} candidate(s)"
    if labels:
        conclusion += ": " + ", ".join(labels)[:380]
    entry = _ledger_entry_dict(
        decision=f"rank_edit_targets {intent!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [f"rank_edit_targets({_tool_arg_summary(args)}) — ok: case={body.get('case')}"]
    for candidate in candidates:
        lines.append(
            f"  - {candidate.get('class_type')} [{candidate.get('node_id')}] "
            f"score={candidate.get('score')}: {_shorten_query_text(str(candidate.get('reason') or ''), max_chars=140)}"
        )
    return artifacts, entry, "\n".join(lines)


def _suggest_seed_nodes_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    intent = str(body.get("intent") or args.get("intent") or "intent")
    evidence_id = _tool_evidence_id("suggest_seed_nodes", intent)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="seed_suggestions",
            body=dict(body),
            source="seed_index",
        )
    }
    suggestions = [s for s in (body.get("suggestions") or ()) if isinstance(s, Mapping)]
    classes = [_shorten_query_text(str(s.get("class_type") or "?"), max_chars=60) for s in suggestions]
    conclusion = f"case={body.get('case')}; {len(suggestions)} suggestion(s)"
    if classes:
        conclusion += ": " + ", ".join(classes)[:380]
    entry = _ledger_entry_dict(
        decision=f"suggest_seed_nodes {intent!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [f"suggest_seed_nodes({_tool_arg_summary(args)}) — ok: case={body.get('case')}"]
    for suggestion in suggestions:
        lines.append(
            f"  - {suggestion.get('class_type')} ({suggestion.get('role')}) "
            f"score={suggestion.get('score')}: {_shorten_query_text(str(suggestion.get('reason') or ''), max_chars=140)}"
        )
    return artifacts, entry, "\n".join(lines)


def _layout_hints_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    operation = str(body.get("operation") or args.get("operation") or "operation")
    evidence_id = _tool_evidence_id("layout_hints", operation)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="layout_hints",
            body=dict(body),
            source="graph",
        )
    }
    candidates = [c for c in (body.get("candidates") or ()) if isinstance(c, Mapping)]
    candidate_text = "; ".join(
        _shorten_query_text(f"{c.get('target')} ({c.get('kind')})", max_chars=60)
        for c in candidates
    )
    conclusion = (
        f"operation={operation}; {len(candidates)} candidate(s)"
        + (f": {candidate_text}" if candidate_text else "")
    )
    entry = _ledger_entry_dict(
        decision=f"layout_hints {operation!r}",
        conclusion=conclusion,
        evidence_ids=(evidence_id,),
        uncertainty="",
    )
    lines = [f"layout_hints({_tool_arg_summary(args)}) — ok: {len(candidates)} candidate(s)"]
    for candidate in candidates:
        position = candidate.get("position")
        position_text = f" position={position}" if position is not None else ""
        lines.append(
            f"  - {candidate.get('target')} ({candidate.get('kind')}){position_text}: "
            f"{_shorten_query_text(str(candidate.get('reason') or ''), max_chars=140)}"
        )
    return artifacts, entry, "\n".join(lines)


# ── handlers (tool-module invocation) ───────────────────────────────────────


def _hivemind_search_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    # The declared argument surface is passed through untouched: filters,
    # cursor, limit and timeout are the agent's arguments, never dropped.
    mod = importlib.import_module("vibecomfy.executor.hivemind_tools")
    search_fn = getattr(session, "search_fn", None)
    if search_fn is not None:
        return search_fn(
            args["query"],
            filters=args.get("filters"),
            cursor=args.get("cursor"),
            limit=args.get("limit", 10),
            timeout=args.get("timeout", 5.0),
        )
    return mod.hivemind_search(
        args["query"],
        filters=args.get("filters"),
        cursor=args.get("cursor"),
        limit=args.get("limit", 10),
        timeout=args.get("timeout", 5.0),
        cache_root=getattr(session, "cache_root", None),
    )


def _hivemind_get_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.hivemind_tools")
    get_fn = getattr(session, "get_fn", None)
    if get_fn is not None:
        return get_fn(args["evidence_id"], timeout=args.get("timeout", 5.0))
    return mod.hivemind_get(
        args["evidence_id"],
        timeout=args.get("timeout", 5.0),
        cache_root=getattr(session, "cache_root", None),
    )


def _registry_lookup_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.lookup_tools")
    return mod.registry_lookup(args["node_class"], budget=budget_payload)


def _node_schema_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.lookup_tools")
    provider = getattr(session, "schema_provider", None)
    if provider is None:
        return mod.node_schema(args["node_class"])
    return mod.node_schema(args["node_class"], provider=provider)


def _ready_template_list_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.lookup_tools")
    return mod.ready_template_list(
        args.get("capability"),
        include_dynamic=bool(args.get("include_dynamic", False)),
    )


def _ready_template_load_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.lookup_tools")
    return mod.ready_template_load(
        args["template_id"],
        include_dynamic=bool(args.get("include_dynamic", False)),
        include_content=bool(args.get("include_content", True)),
    )


def _session_emit_graph(session: Any) -> Any:
    """Emit-door snapshot of the retained IR.  ``working_ui`` is not authority."""
    emit = getattr(session, "_emit_working_snapshot", None)
    workflow = getattr(session, "workflow", None)
    if callable(emit) and workflow is not None:
        return emit()
    return None


def _rank_edit_targets_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.edit_suggestion_tools")
    return mod.rank_edit_targets(
        _session_emit_graph(session),
        args["intent"],
        explicit=True,
        max_targets=args.get("max_targets", 4),
    )


def _suggest_seed_nodes_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.edit_suggestion_tools")
    return mod.suggest_seed_nodes(
        args["intent"],
        args.get("constraints"),
        graph=_session_emit_graph(session),
        explicit=True,
        max_suggestions=args.get("max_suggestions", 4),
    )


def _layout_hints_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.layout_hints")
    return mod.layout_hints_tool(
        _session_emit_graph(session),
        args["operation"],
        anchors=args.get("anchors"),
    )


def _web_search_handler(
    session: Any, args: Mapping[str, Any], budget_payload: Any
) -> ToolResult:
    mod = importlib.import_module("vibecomfy.executor.web_tools")
    # A06: web search is opt-in — the live resolver defaults a missing flag to
    # DISABLED, never to enabled.
    enabled = bool(getattr(session, "web_search_enabled", False))
    return mod.web_search(
        args["query"],
        unresolved_question=args.get("unresolved_question"),
        enabled=enabled,
        timeout=args.get("timeout", 5.0),
    )


# ── the declarative registry ────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolSpec:
    """One agent-invoked tool: phase, args, budget, handler, ledger projector.

    ``handler(session, args, budget_payload)`` invokes the tool module and
    returns a typed :class:`ToolResult`.  ``projector(args, result, session)``
    maps one completed call to ``(evidence_artifacts, ledger_entry, digest)``
    — the only channel by which tool output crosses turns.
    """

    name: str
    phase: str
    description: str
    handler: Callable[[Any, Mapping[str, Any], Any], ToolResult] = field(repr=False)
    projector: Callable[
        [Mapping[str, Any], ToolResult, Any],
        tuple[dict[str, EvidenceArtifact], dict[str, Any], str],
    ] = field(repr=False)
    positional_names: tuple[str, ...] = ()
    keywords: frozenset[str] = frozenset()
    required: tuple[str, ...] = ()
    budget_class: str | None = None

    def __post_init__(self) -> None:
        if self.phase not in _PHASES:
            raise ValueError(f"ToolSpec {self.name!r}: unknown phase {self.phase!r}.")
        if self.name not in self.keywords and not self.positional_names:
            raise ValueError(f"ToolSpec {self.name!r}: no callable argument surface.")

    def catalog_line(self) -> str:
        """One compact prompt-doc line for this tool."""
        positional = ", ".join(self.positional_names) or "…"
        return f"- `{self.name}({positional})` — {self.description}"


def _tool_spec(
    *,
    name: str,
    phase: str,
    description: str,
    positional_names: tuple[str, ...],
    keywords: tuple[str, ...],
    required: tuple[str, ...] = (),
    budget_class: str | None = None,
    handler: Callable[[Any, Mapping[str, Any], Any], ToolResult],
    projector: Callable[
        [Mapping[str, Any], ToolResult, Any],
        tuple[dict[str, EvidenceArtifact], dict[str, Any], str],
    ],
) -> ToolSpec:
    return ToolSpec(
        name=name,
        phase=phase,
        description=description,
        positional_names=positional_names,
        keywords=frozenset(keywords),
        required=required,
        budget_class=budget_class,
        handler=handler,
        projector=projector,
    )


TOOL_SPECS: tuple[ToolSpec, ...] = (
    _tool_spec(
        name="hivemind_search",
        phase=PHASE_RESEARCH,
        description=(
            "search the Hivemind corpus (Discord community, external resources, "
            "curated distillations) for workflow precedents and community knowledge. "
            "Choose filters.source_type by need: 'workflow' for exact graph "
            "precedents, 'discord' for community usage/settings/gotchas, and "
            "'distillation' for curated Q&A. A distillation/speed/turbo LoRA is "
            "a model type, not the 'distillation' source tier; search workflow "
            "or discord for those models."
        ),
        positional_names=("query",),
        keywords=("query", "filters", "cursor", "limit", "timeout"),
        required=("query",),
        budget_class="search",
        handler=_hivemind_search_handler,
        projector=_hivemind_search_projector,
    ),
    _tool_spec(
        name="hivemind_get",
        phase=PHASE_RESEARCH,
        description="resolve one returned evidence ID to its full Hivemind record",
        positional_names=("evidence_id",),
        keywords=("evidence_id", "timeout"),
        required=("evidence_id",),
        budget_class="fetch",
        handler=_hivemind_get_handler,
        projector=_hivemind_get_projector,
    ),
    _tool_spec(
        name="registry_lookup",
        phase=PHASE_RESEARCH,
        description="find which node pack owns a node class (Comfy registry; exactly one batch per session)",
        positional_names=("node_class",),
        keywords=("node_class",),
        required=("node_class",),
        budget_class="registry",
        handler=_registry_lookup_handler,
        projector=_registry_projector,
    ),
    _tool_spec(
        name="web_search",
        phase=PHASE_RESEARCH,
        description=(
            "last-resort public web search; disabled unless explicitly enabled"
        ),
        positional_names=("query",),
        keywords=("query", "unresolved_question", "timeout"),
        required=("query",),
        budget_class="search",
        handler=_web_search_handler,
        projector=_web_search_projector,
    ),
    _tool_spec(
        name="node_schema",
        phase=PHASE_IMPLEMENT,
        description="read the runtime/local schema of one node class (availability, inputs, outputs)",
        positional_names=("node_class",),
        keywords=("node_class",),
        required=("node_class",),
        budget_class="fetch",
        handler=_node_schema_handler,
        projector=_node_schema_projector,
    ),
    _tool_spec(
        name="ready_template_list",
        phase=PHASE_IMPLEMENT,
        description="list ready workflow templates by capability (direct-load asset inventory; NOT research evidence)",
        positional_names=("capability",),
        keywords=("capability", "include_dynamic"),
        handler=_ready_template_list_handler,
        projector=_ready_template_list_projector,
    ),
    _tool_spec(
        name="ready_template_load",
        phase=PHASE_IMPLEMENT,
        description="load one ready template by id (direct-load shipping asset; NOT research evidence)",
        positional_names=("template_id",),
        keywords=("template_id", "include_dynamic", "include_content"),
        required=("template_id",),
        budget_class="fetch",
        handler=_ready_template_load_handler,
        projector=_ready_template_load_projector,
    ),
    _tool_spec(
        name="rank_edit_targets",
        phase=PHASE_IMPLEMENT,
        description="rank candidate edit targets in the current graph for an intent (advisory, explicit call only)",
        positional_names=("intent",),
        keywords=("intent", "max_targets"),
        required=("intent",),
        handler=_rank_edit_targets_handler,
        projector=_rank_edit_targets_projector,
    ),
    _tool_spec(
        name="suggest_seed_nodes",
        phase=PHASE_IMPLEMENT,
        description="suggest starting node classes for authoring (empty-graph case; visible alternatives)",
        positional_names=("intent", "constraints"),
        keywords=("intent", "constraints", "max_suggestions"),
        required=("intent",),
        handler=_suggest_seed_nodes_handler,
        projector=_suggest_seed_nodes_projector,
    ),
    _tool_spec(
        name="layout_hints",
        phase=PHASE_IMPLEMENT,
        description="suggest placement positions/groups for a node insertion (advisory)",
        positional_names=("operation", "anchors"),
        keywords=("operation", "anchors"),
        required=("operation",),
        handler=_layout_hints_handler,
        projector=_layout_hints_projector,
    ),
)

TOOL_SPEC_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}

if len(TOOL_SPEC_BY_NAME) != len(TOOL_SPECS):
    raise ValueError("ToolSpec registry contains duplicate tool names.")

AGENT_TOOL_CALL_NAMES: frozenset[str] = frozenset(TOOL_SPEC_BY_NAME)

RESEARCH_PHASE_TOOLS: frozenset[str] = frozenset(
    spec.name for spec in TOOL_SPECS if spec.phase == PHASE_RESEARCH
)
IMPLEMENT_PHASE_TOOLS: frozenset[str] = frozenset(
    spec.name for spec in TOOL_SPECS if spec.phase == PHASE_IMPLEMENT
)

# The two phase sets must be a clean partition of every registered tool: a
# tool is research or implement, never both, never neither.
if RESEARCH_PHASE_TOOLS | IMPLEMENT_PHASE_TOOLS != AGENT_TOOL_CALL_NAMES:
    raise ValueError("Tool phase partition does not cover every registered tool.")
if RESEARCH_PHASE_TOOLS & IMPLEMENT_PHASE_TOOLS:
    raise ValueError("Tool phase partition overlaps.")


def phase_for_tool(name: str) -> str:
    try:
        return TOOL_SPEC_BY_NAME[name].phase
    except KeyError:
        raise ValueError(f"Unknown agent tool {name!r}.") from None


def phase_allows(phase: str | None, name: str) -> bool:
    """True when *name* may be called in *phase*.

    ``None`` (unknown/offline phase context) is permissive so standalone
    parsers and offline validation can check either phase; the live batch
    REPL always carries an explicit phase marker.
    """
    if phase is None:
        return name in TOOL_SPEC_BY_NAME
    return phase_for_tool(name) == phase


def tool_catalog_docs(phase: str | None = None, *, allowed_names: frozenset[str] | None = None) -> str:
    """Prompt-doc bullet list for *phase* (all tools when *phase* is None).

    ``allowed_names`` further filters the catalog to the names the runtime
    actually admits — e.g. the research stage passes its effective allowlist
    so a disabled-by-default tool (``web_search``) is never advertised.
    """
    specs = TOOL_SPECS if phase is None else tuple(spec for spec in TOOL_SPECS if spec.phase == phase)
    if allowed_names is not None:
        specs = tuple(spec for spec in specs if spec.name in allowed_names)
    return "\n".join(spec.catalog_line() for spec in specs)


def invoke_tool(
    spec: ToolSpec,
    session: Any,
    args: Mapping[str, Any],
    budget_payload: Any,
) -> ToolResult:
    """Invoke one validated tool call through its registered handler.

    The declared ``spec.required`` arguments are validated here — a missing or
    blank required argument is a typed ``invalid_request``, never a handler
    ``KeyError``/``AttributeError`` and never a raise.  Callers that pre-validate
    (the batch resolver) are unaffected: the check is a no-op when all required
    arguments are present.
    """
    missing = [
        name
        for name in spec.required
        if not str(args.get(name) or "").strip()
    ]
    if missing:
        from .tool_contracts import ToolDiagnostic  # noqa: PLC0415

        return ToolResult(
            tool_name=spec.name,
            status=ToolStatus.INVALID_REQUEST,
            result={},
            diagnostics=(
                ToolDiagnostic(
                    code="tool_arg_required",
                    message=(
                        f"{spec.name} requires argument(s): {', '.join(missing)}"
                    ),
                ),
            ),
        )
    return spec.handler(session, args, budget_payload)


def project_tool_evidence(
    spec: ToolSpec,
    args: Mapping[str, Any],
    result: ToolResult,
    session: Any,
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    """Map one completed tool call to ``(artifacts, ledger_entry, digest)``."""
    if result.status is not ToolStatus.OK:
        return {}, _status_ledger_entry(spec.name, result), _format_tool_digest(
            spec.name, args, result
        )
    return spec.projector(args, result, session)


__all__ = [
    "AGENT_TOOL_CALL_NAMES",
    "IMPLEMENT_PHASE_TOOLS",
    "PHASE_IMPLEMENT",
    "PHASE_RESEARCH",
    "RESEARCH_PHASE_TOOLS",
    "TOOL_SPECS",
    "TOOL_SPEC_BY_NAME",
    "ToolSpec",
    "invoke_tool",
    "phase_allows",
    "phase_for_tool",
    "project_tool_evidence",
    "tool_catalog_docs",
    "_format_tool_digest",
    "_hit_line",
    "_ledger_entry_dict",
    "_shorten_query_text",
    "_status_ledger_entry",
    "_tool_arg_summary",
    "_tool_evidence_id",
]
