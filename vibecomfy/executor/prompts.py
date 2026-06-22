"""Prompt building and strict response parsing for executor model calls.

Phase structure (settled SD1):  classify → research → implement → reply.

*classify* always calls the model to produce a :class:`ClassifyDecision`.
*reply* always calls the model to produce the user-facing prose that the
executor returns in its envelope.

Both phases use strict JSON contracts with small parsers so malformed model
output is classifiable and tests are deterministic.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .contracts import (
    ClassifyDecision,
    format_route_options_for_prompt,
    format_task_options_for_prompt,
)

# ── classify prompt ──────────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = (
    "You are a workflow intent classifier for a ComfyUI canvas editor.\n"
    "Analyze the user request and decide what pipeline phases are needed.\n"
    "Return ONLY a JSON object with these keys:\n"
    '  "research": true/false — whether the executor should search for relevant nodes, '
    "templates, or techniques.\n"
    '  "implement": true/false — whether the executor should edit the graph.\n'
    '  "reply": true/false — whether the executor should produce a user-facing reply.\n'
    '  "effort": "low" | "medium" | "high" — estimated complexity.\n'
    '  "plan_summary": string — one sentence describing the plan.\n'
    '  "intent": "edit" | "research" | "explain_graph" | "respond" — the primary '
    "user intent.\n"
    f"{format_route_options_for_prompt()}"
    f"{format_task_options_for_prompt()}"
    "\n"
    "Rules:\n"
    "- intent must be exactly one of: edit, research, explain_graph, respond.\n"
    "- Be conservative: when the user request is ambiguous, underspecified, or "
    "references nodes/options/attachments without enough detail to safely edit, "
    "prefer route=\"clarify\" with a concise clarification_question and "
    "clarification_options array.\n"
    "- The executor runs deterministic safety checks before this model is called; "
    "those block obviously unsafe edit requests automatically. You do NOT need to "
    "second-guess those checks — focus on intent classification, not validation.\n"
    "- A chat / question with no graph edit intent → intent=respond, reply=true.\n"
    "  Set intent=research when the user asks to look up, research, find out about, or "
    "asks how something works.\n"
    "- A request to explain, describe, analyze, or inspect an attached graph "
    "(e.g. \"what's happening in this graph?\") → intent=explain_graph, research=false, "
    "implement=false, reply=true, effort=medium.  Set route=\"inspect\" when the "
    "user ONLY wants explanation with no edit.\n"
    "- A simple, concrete graph edit request with no research needed "
    "→ intent=edit, implement=true, research=false, reply=true, route=\"revise\".\n"
    "- A complex graph edit that needs precedent/template research first "
    "→ intent=edit, implement=true, research=true, reply=true, "
    "route=\"adapt\".\n"
    "- Never set implement=true without a graph to edit (but you don't need to check — "
    "the executor handles that).\n"
    "- For any request where the edit target is unclear, multiple interpretations "
    "exist, or the user references options from a prior turn without specifying "
    "which one, default to route=\"clarify\" rather than guessing a mutation route.\n"
    "- Only use route=\"adapt\" when the user explicitly asks to borrow, port, "
    "adapt, follow, or recreate a known outside workflow/template/pattern, not "
    "for general local graph edits. Examples that should be route=\"adapt\": "
    "VACE identity travel, BlockSwap low-VRAM wiring, two-pass refinement, "
    "LoRA chaining, audio latent/lipsync wiring, and ControlNet/depth/pose "
    "guidance patterns.\n"
    "- Generic edits to the current graph such as changing seeds, prompts, "
    "sampler steps, model names, node positions, or direct local wiring should "
    "stay route=\"revise\" when concrete, or route=\"clarify\" when ambiguous.\n"
    "- Do NOT wrap the JSON in markdown fences or add commentary.\n"
    "- The response must be a single JSON object on one line or multiple lines; "
    "no trailing text.\n"
    "- When route=\"clarify\", include a clarification_question (string) and "
    "clarification_options (array of 1-4 strings) to help the user resolve "
    "the ambiguity."
)


def build_classify_messages(
    query: str,
    *,
    has_graph: bool = False,
    graph_summary: str | None = None,
    session_context: dict[str, Any] | None = None,
    graph_reference_map: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Build system + user messages for the classify phase.

    When *has_graph* is True, the executor tells the model a graph is attached
    so it can decide whether research / implementation is warranted.
    *graph_summary* is an optional compact summary (≤ 200 chars) of the
    attached graph for context.

    *session_context* provides access to recent conversation history and prior
    clarification artifacts so the classifier can resolve follow-up references
    (e.g. \"option 2\", \"that node\") against prior turn context.

    *graph_reference_map* is a compact ``{node_id: label}`` lookup built from
    the current graph so the classifier can map user references like
    \"the KSampler\" or \"node #3\" to concrete ids.
    """
    parts = [f"User request:\n{query}"]
    if has_graph:
        parts.append("\nA ComfyUI canvas graph is attached to this request.")
    if graph_summary:
        parts.append(f"\nGraph summary: {graph_summary}")

    # ── session context: recent messages ─────────────────────────────────
    if isinstance(session_context, dict):
        recent_messages = session_context.get("recent_messages")
        if isinstance(recent_messages, list) and recent_messages:
            # Include last 3 exchanges for follow-up reference resolution.
            recent = recent_messages[-6:]  # up to 3 user+assistant pairs
            parts.append("\nRecent conversation (for reference resolution):")
            for msg in recent:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    content = msg.get("content") or msg.get("text") or ""
                    if isinstance(content, str) and content.strip():
                        parts.append(f"[{role}]: {content[:300]}")

        # ── prior clarification artifacts ────────────────────────────────
        prior_clarification = session_context.get("prior_clarification")
        if isinstance(prior_clarification, dict):
            cq = prior_clarification.get("clarification_question")
            co = prior_clarification.get("clarification_options")
            if isinstance(cq, str) and cq.strip():
                parts.append(
                    f"\nPrior clarification question: {cq.strip()[:200]}"
                )
            if isinstance(co, (list, tuple)) and co:
                opts = "\n".join(
                    f"  {i+1}. {str(o)[:200]}"
                    for i, o in enumerate(co)
                    if isinstance(o, str) and o.strip()
                )
                if opts:
                    parts.append(f"Prior clarification options:\n{opts}")

        # ── blocked route context ────────────────────────────────────────
        prior_route = session_context.get("prior_route")
        prior_task = session_context.get("prior_task")
        if isinstance(prior_route, str) and prior_route.strip():
            parts.append(
                f"\nThe previous turn was blocked on route=\"{prior_route}\""
                + (f", task=\"{prior_task}\"" if isinstance(prior_task, str) and prior_task.strip() else "")
                + ". The user's follow-up should be classified with this "
                + "original intent in mind."
            )

        # ── latest candidate reference ──────────────────────────────────
        latest_candidate = session_context.get("latest_candidate")
        if isinstance(latest_candidate, dict):
            candidate_bits: list[str] = []
            turn_id = latest_candidate.get("turn_id")
            if isinstance(turn_id, str) and turn_id.strip():
                candidate_bits.append(f"turn={turn_id.strip()[:80]}")
            outcome = latest_candidate.get("outcome")
            if isinstance(outcome, dict) and isinstance(outcome.get("kind"), str):
                candidate_bits.append(f"outcome={outcome['kind'].strip()[:80]}")
            change_details = latest_candidate.get("change_details")
            operations = (
                change_details.get("operations")
                if isinstance(change_details, dict)
                else None
            )
            if isinstance(operations, list) and operations:
                summaries = []
                for op in operations[:4]:
                    if not isinstance(op, dict):
                        continue
                    summary = op.get("summary") or op.get("field_path")
                    if isinstance(summary, str) and summary.strip():
                        summaries.append(summary.strip()[:120])
                if summaries:
                    candidate_bits.append("changes=" + "; ".join(summaries))
            if candidate_bits:
                parts.append(
                    "\nLatest candidate reference (use this only for unique "
                    "follow-up references like \"that one\"):\n  "
                    + ", ".join(candidate_bits)
                )

    # ── graph reference map ──────────────────────────────────────────────
    if isinstance(graph_reference_map, dict) and graph_reference_map:
        ref_lines = []
        for node_id, label in sorted(graph_reference_map.items(), key=lambda kv: _ref_sort_key(kv[0])):
            ref_lines.append(f"  id={node_id}: {label}")
        if ref_lines:
            parts.append(
                "\nCurrent graph node reference map (use these ids to resolve "
                "\"that node\", \"the KSampler\", etc.):\n"
                + "\n".join(ref_lines[:30])
            )

    return [
        {"role": "system", "content": _CLASSIFY_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _ref_sort_key(node_id: str) -> tuple[int, str]:
    """Sort node ids numerically when possible, for stable reference maps."""
    try:
        return (0, str(int(node_id)).zfill(8))
    except (ValueError, TypeError):
        return (1, node_id)


# ── reply prompt ─────────────────────────────────────────────────────────────

_REPLY_SYSTEM = (
    "You are a helpful assistant replying to a user of a ComfyUI canvas editor.\n"
    "The executor has already completed any research and graph editing phases.\n"
    "Your job is to produce a clear, concise user-facing reply.\n\n"
    "Return ONLY a JSON object with this key:\n"
    '  "reply": string — the user-facing message (1-3 sentences).\n'
    "\n"
    "Rules:\n"
    "- Acknowledge what was done (if anything).\n"
    "- Be concrete: mention node names, template names, or parameter values "
    "when relevant.\n"
    "- If research findings are present and implementation ran, include one brief "
    "reason the chosen approach/source informed the edit. Do not dump the research "
    "summary.\n"
    "- Mention prioritization, ratings, trust, or quality scores only when that "
    "metadata is explicitly present in the research findings.\n"
    "- For route=\"adapt\" replies, mention the source template/workflow, the "
    "anchor roles bound, the structural validation result, and any portability "
    "warnings; keep the detailed candidate graph in the structured artifact.\n"
    "- If nothing was changed, explain why clearly.\n"
    "- When a graph inspection is provided (inspect route): describe the "
    "graph structure, node types, and how they connect. Explain what the workflow "
    "does step-by-step. Do NOT suggest edits or changes — only explain the "
    "current graph. Use node names and widget values from the inspection evidence.\n"
    "- Do NOT include JSON wrapping outside of the required object.\n"
    "- The response must be a single JSON object; no markdown fences, no commentary."
)


def build_reply_messages(
    query: str,
    *,
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
    graph_inspection: str | None = None,
    adaptation_plan: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Build system + user messages for the reply phase.

    *plan*, *research_summary*, *implementation_message*, *graph_summary*, and
    *graph_inspection* provide the context the model needs to write an informed
    reply.

    When *graph_inspection* is provided (inspect-only route), it supplies
    detailed node-by-node structure that the model should describe without
    suggesting edits.

    *adaptation_plan* is the serialized :class:`PrecedentAdaptationPlan` for
    route="adapt" requests; the reply should reference it at a high level while
    leaving the detailed candidate graph in the structured artifact.
    """
    parts = [f"User request:\n{query}"]
    if graph_inspection:
        parts.append(
            f"\nGraph inspection (describe the workflow without suggesting edits):\n{graph_inspection}"
        )
    elif graph_summary:
        parts.append(f"\nAttached workflow graph: {graph_summary}")
    if plan is not None:
        parts.append(f"\nExecutor plan: {plan.plan_summary or 'completed'}")
    if research_summary:
        parts.append(f"\nResearch findings: {research_summary}")
    if implementation_message:
        parts.append(f"\nImplementation: {implementation_message}")
    if adaptation_plan:
        selected = adaptation_plan.get("selected_slice") or {}
        bindings = adaptation_plan.get("anchor_bindings") or []
        roles = ", ".join(sorted({b.get("anchor_role", "") for b in bindings if b.get("anchor_role")}))
        parts.append(
            f"\nAdaptation plan: selected source '{selected.get('source_class_type', 'unknown')}', "
            f"bound anchor roles: {roles or 'none'}, "
            f"structural_validation={adaptation_plan.get('structural_validation', 'not_evaluated')}, "
            f"semantic_validation={adaptation_plan.get('semantic_validation', 'not_evaluated')}."
        )
    return [
        {"role": "system", "content": _REPLY_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]


# ── response parsers ─────────────────────────────────────────────────────────

# Matches a JSON object that starts with { and ends with } across lines.
# More permissive than the top-level json.loads so we can extract from
# model output that may have stray whitespace or a trailing period.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from potentially noisy model output.

    Strips markdown fences, trims surrounding whitespace, and falls back to
    regex extraction before handing off to ``json.loads``.
    """
    stripped = text.strip()
    # Strip outermost ``` fences (with or without ``json`` language tag).
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()

    # Try direct parse first (fast path).
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fall back to regex extraction: find the first { ... } span.
    match = _JSON_OBJECT_RE.search(stripped)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract a JSON object from: {text[:200]!r}")


def parse_classify_response(raw: str) -> ClassifyDecision:
    """Parse a classify model response into a :class:`ClassifyDecision`.

    Accepts valid JSON and recovers from common model mistakes (fences,
    trailing text).  Raises :class:`ValueError` for unparseable output.
    """
    parsed = _extract_json_object(raw)

    research = parsed.get("research")
    implement = parsed.get("implement")
    reply = parsed.get("reply")
    effort = parsed.get("effort")
    plan_summary = parsed.get("plan_summary")
    intent = parsed.get("intent")
    route = parsed.get("route")
    task = parsed.get("task")
    research_goal = parsed.get("research_goal")
    model_families = parsed.get("model_families")
    pattern_category = parsed.get("pattern_category")
    change_goal = parsed.get("change_goal")
    clarification_question = parsed.get("clarification_question")
    clarification_options = parsed.get("clarification_options")

    # Coerce booleans; missing keys default to sensible values.
    if not isinstance(research, bool):
        research = bool(research)
    if not isinstance(implement, bool):
        implement = bool(implement)
    if not isinstance(reply, bool):
        reply = True  # default: always reply
    if not isinstance(effort, str) or effort not in ("low", "medium", "high"):
        effort = "low"
    if not isinstance(plan_summary, str):
        plan_summary = ""
    if not isinstance(intent, str) or intent not in ("edit", "research", "explain_graph", "respond"):
        # Derive intent from legacy boolean fields for backward compatibility.
        if implement:
            intent = "edit"
        elif research:
            intent = "research"
        else:
            intent = "respond"

    # Normalize route: store as-is; derivation happens in effective_route property.
    if not isinstance(route, str):
        route = ""
    route = route.strip()

    # Normalize task: store as-is; derivation happens in effective_task property.
    if not isinstance(task, str):
        task = ""
    task = task.strip()

    # Normalize new metadata fields.
    if not isinstance(research_goal, str):
        research_goal = ""
    research_goal = research_goal.strip()
    if not isinstance(model_families, list):
        model_families = []
    model_families = tuple(str(f) for f in model_families if isinstance(f, str) and f.strip())
    if not isinstance(pattern_category, str):
        pattern_category = ""
    pattern_category = pattern_category.strip()
    if not isinstance(change_goal, str):
        change_goal = ""
    change_goal = change_goal.strip()
    if not isinstance(clarification_question, str):
        clarification_question = ""
    clarification_question = clarification_question.strip()
    if not isinstance(clarification_options, list):
        clarification_options = []
    clarification_options = tuple(str(o) for o in clarification_options if isinstance(o, str) and o.strip())

    return ClassifyDecision(
        research=research,
        implement=implement,
        reply=reply,
        effort=effort,
        plan_summary=plan_summary.strip(),
        intent=intent,
        route=route,
        task=task,
        research_goal=research_goal,
        model_families=model_families,
        pattern_category=pattern_category,
        change_goal=change_goal,
        clarification_question=clarification_question,
        clarification_options=clarification_options,
    )


def parse_reply_response(raw: str) -> str:
    """Parse a reply model response into a user-facing string.

    Expects ``{"reply": "..."}``.  Returns the reply text or raises
    :class:`ValueError` for unparseable output.
    """
    parsed = _extract_json_object(raw)
    reply = parsed.get("reply")
    if isinstance(reply, str) and reply.strip():
        return reply.strip()
    # Some models use "message" or "response" as the key; try those.
    for key in ("message", "response", "content", "text"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(
        f"Reply model response did not contain a string 'reply' (or fallback) key. "
        f"Got keys: {sorted(parsed.keys())}"
    )


__all__ = [
    "build_classify_messages",
    "build_reply_messages",
    "parse_classify_response",
    "parse_reply_response",
]
