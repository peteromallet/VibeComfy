"""C1 agent-owned research stage — one genuine tool-calling agent phase.

Runs the research phase for ``research`` / ``adapt`` routes as a single
agent-driven tool-calling loop: the MODEL chooses every evidence tool call
(``hivemind_search``, ``hivemind_get``, ``registry_lookup``) and decides when
the evidence answers the question (``finish``).  Deterministic Python never
auto-chooses a search or fetch — it only executes the agent's chosen calls,
records typed evidence, and enforces the phase allowlist + the wall-clock
deadline (calls and turns are unbounded — minimal-budget plan).
The stage returns ``(trace, evidence_pack)``; the F01 :class:`EvidencePack`
is the only handoff into the implement phase.

Contract:
    * The agent decision request contains ONLY the explicit question, the
      research-phase tool catalog, and a compact bounded digest of tool
      statuses / evidence IDs / previews — never the full research result
      object and never a workflow/graph schema dump.
    * Tool calls outside the research-phase allowlist
      (``hivemind_search``/``hivemind_get``/``registry_lookup``) are typed
      refusals, never executed, never silently rewritten.
    * The stage never raises: every failure is captured as a typed trace
      with ``status="failed"`` (or ``status="exhausted"`` when the loop
      stopped without an agent finish) so the executor pipeline is
      unaffected and can fail closed.

Research phase bounds are minimal (Grok first-principles plan): searches,
fetches, registry lookups, and decision turns are UNBOUNDED; the only
production bound is the wall-clock deadline (``TOOL_PHASE_DEADLINE_SECONDS``).
Prompt size is bounded by the digest (4000 chars; fetched records in full,
never workflow ``payload``).  The batch protocol in
``vibecomfy/executor/tool_specs.py`` keeps its own separate edit-session
budgets; this module is not reconciled with them.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
)
from .agent_backend import (
    _attach_model_turn_evidence,
    _downstream_failure_type,
    _mark_last_attempt_failed,
    _record_result_attempts,
)
from .hivemind_tools import HIVE_MIND_GET_TOOL, HIVE_MIND_SEARCH_TOOL
from .hivemind_clients import _first_text, _workflow_semantics
from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus
from .tool_specs import (
    PHASE_RESEARCH,
    RESEARCH_PHASE_TOOLS,
    TOOL_SPEC_BY_NAME,
    invoke_tool,
    project_tool_evidence,
    tool_catalog_docs,
)

LOGGER = logging.getLogger(__name__)

# ── Research phase bounds (minimal — Grok first-principles plan) ────────────
# The ONLY production bound is wall clock: fetches/searches/registry calls and
# decision turns are all unbounded.  A fetch is a ~300ms HTTP GET on the raw
# message_feed table and a fetched Discord record is ~60-1000 chars — neither
# is scarce.  Wall clock bounds user wait, cost (at current ~15s/turn), and
# loop runaway (checked before every decision and after every tool).  The
# other real bound is prompt size, enforced in the digest (see below).
# 450s = 7.5 minutes: on adapt routes research + implement each get ~half of
# the panel's 15-min absolute submit deadline (900s); research-only routes
# simply use the full research window.
TOOL_PHASE_DEADLINE_SECONDS = 450.0

# Test-only clamp: production passes max_turns=None (unbounded; the deadline
# is the stop).  Tests pass a small number so unit runs stay fast.
_MAX_TURNS = None
# Honest-budget reserve: the per-turn digest is built before the decision
# model call, so (deadline - now()) at digest time overstates what the agent
# can still plan.  The agent is told it has this much less than the raw
# remaining wall clock, so it winds down to a finish instead of planning
# tool work the deadline will cut off.  Bounded below the phase deadline.
_DECISION_TURN_LATENCY_RESERVE_SECONDS = 30.0
_MAX_DIGEST_CHARS = 4_000
_MAX_JUDGMENT_CITATIONS = 8
_MAX_CONCLUSION_PREVIEW_CHARS = 240
_MAX_HIT_PREVIEW_CHARS = 140
# Fetched Hivemind records are synthesis-grade evidence: their content is
# previewed (bounded) so the agent can reason from the fetched body, not a
# title.  EVERY fetched record gets the generous window — there is no
# last-fetch special case (fetches are free, so the agent never needs to
# re-fetch; and every record is equally evidence).  Search hits stay
# title-only leads.
_MAX_RECORD_PREVIEW_CHARS = 1_500

_QUESTION_ARTIFACT_ID = "research_question"
_HIVEMIND_EVIDENCE_ID_PREFIX = "hivemind:"

# Ledger entry decisions (stable identifiers consumed by the stage trace and
# its tests).
DECISION_QUESTION = "research_question"
DECISION_SEARCH = "hivemind_search"
DECISION_GET = "hivemind_get"
DECISION_REGISTRY = "registry_lookup"
DECISION_SYNTHESIZE = "synthesize"
DECISION_ENOUGH_REFINE = "enough_refine"
# P1-c: typed marker for a finish attempted before ANY evidence tool call —
# the loop feeds it back as a refinement turn instead of accepting the
# ungrounded finish (or auto-failing the stage).
DECISION_FINISH_PREMATURE = "finish_premature"

# Research-phase tool allowlist (C01): the agent may only call these tools.
# web_search is intentionally absent — it is disabled by default (A06) and the
# executor research phase is Hivemind-first.
RESEARCH_ALLOWED_TOOLS: frozenset[str] = RESEARCH_PHASE_TOOLS - {"web_search"}


def _clean_text(value: Any) -> str:
    """Collapse whitespace on a str; '' otherwise."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _bounded(text: str, limit: int) -> str:
    text = _clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# ── C1 step 1-2: form the explicit research question ─────────────────────────


def form_research_question(*, request: Any, plan: Any | None = None) -> tuple[str, str]:
    """Return ``(explicit_question, source_field)`` for one research stage.

    Precedence follows the C1 pipeline (narrow, decision-shaped question):
    classifier ``research_goal`` → first ``search_direction`` →
    ``change_goal`` → the raw user query.  The question is recorded in the
    ledger before any tool call (question-before-search).
    """
    if plan is not None:
        research_goal = _clean_text(getattr(plan, "research_goal", ""))
        if research_goal:
            return research_goal, "research_goal"
        for direction in (getattr(plan, "search_directions", ()) or ()):
            cleaned = _clean_text(direction)
            if cleaned:
                return cleaned, "search_direction"
        change_goal = _clean_text(getattr(plan, "change_goal", ""))
        if change_goal:
            return change_goal, "change_goal"
    query = _clean_text(getattr(request, "query", ""))
    if query:
        return query, "query"
    return "Research the user request.", "query"


def build_research_brief(*, plan: Any, request: Any | None = None) -> str:
    """Assemble the FULL research brief from the classifier plan.

    The narrow ``form_research_question`` result is the question-before-search
    marker; this brief carries everything else the research agent needs to
    work on its own judgment: ALL search directions (not just the first),
    known graph context, source preferences, the avoid-list, model families,
    and the pattern category.  Only non-empty sections are emitted; an empty
    plan yields an empty string (the stage then relies on the question alone).

    ``request`` is accepted for caller symmetry and future source fields; it
    is not currently consumed.
    """
    del request  # reserved for future brief sources; plan is the active source
    if plan is None:
        return ""
    sections: list[str] = []
    research_goal = _clean_text(getattr(plan, "research_goal", ""))
    if research_goal:
        sections.append(f"- Research goal: {research_goal}")
    change_goal = _clean_text(getattr(plan, "change_goal", ""))
    if change_goal:
        sections.append(f"- Change goal: {change_goal}")
    directions = [
        _clean_text(direction)
        for direction in (getattr(plan, "search_directions", ()) or ())
        if _clean_text(direction)
    ]
    if directions:
        bullets = "\n".join(f"  {index}. {direction}" for index, direction in enumerate(directions, start=1))
        sections.append(f"- Search directions (try each that may apply):\n{bullets}")
    sources = [
        _clean_text(source)
        for source in (getattr(plan, "source_preferences", ()) or ())
        if _clean_text(source)
    ]
    if sources:
        sections.append(f"- Source preferences: {', '.join(sources)}")
    graph_context = _clean_text(getattr(plan, "known_graph_context", ""))
    if graph_context:
        sections.append(f"- Known graph context: {graph_context}")
    avoid = [
        _clean_text(item)
        for item in (getattr(plan, "avoid", ()) or ())
        if _clean_text(item)
    ]
    if avoid:
        sections.append(f"- Avoid: {'; '.join(avoid)}")
    model_families = [
        _clean_text(item)
        for item in (getattr(plan, "model_families", ()) or ())
        if _clean_text(item)
    ]
    if model_families:
        sections.append(f"- Model families: {', '.join(model_families)}")
    pattern_category = _clean_text(getattr(plan, "pattern_category", ""))
    if pattern_category:
        sections.append(f"- Pattern category: {pattern_category}")
    if not sections:
        return ""
    return "Research brief:\n" + "\n".join(sections)


# ── agent decision parsing (fail-closed) ─────────────────────────────────────


def parse_agent_research_decision(raw: str) -> dict[str, Any]:
    """Parse ONE agent decision: a tool call or a finish, fail-closed.

    Expected shapes::

        {"action": "call", "tool": "hivemind_search", "args": {"query": "..."}}
        {"action": "finish", "conclusion": str, "evidence_ids": [str, ...],
         "uncertainty": str, "refine_question": str|null}

    Legacy synthesize judgments (no ``action``, with ``conclusion`` /
    ``enough``) are normalized to a finish decision so the seam stays
    backward-compatible with injected fakes.  Any malformed payload raises
    :class:`ValueError`; the stage converts that into a typed failure so the
    research phase never poisons the pipeline.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("agent research decision: empty response")
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent research decision: malformed JSON: {exc}") from None
    if not isinstance(parsed, Mapping):
        raise ValueError("agent research decision: expected a JSON object")

    action = _clean_text(parsed.get("action"))
    if action == "call":
        tool = _clean_text(parsed.get("tool"))
        if not tool:
            raise ValueError("agent research decision: call requires a tool name")
        raw_args = parsed.get("args")
        if raw_args is None:
            raw_args = {}
        if not isinstance(raw_args, Mapping):
            raise ValueError("agent research decision: call args must be an object")
        return {
            "action": "call",
            "tool": tool,
            "args": {str(key): value for key, value in raw_args.items()},
        }
    if action == "finish":
        return {"action": "finish", **_finish_payload(parsed)}
    if action:
        raise ValueError(f"agent research decision: unknown action {action!r}")
    # Legacy synthesize/enough-refine judgment → normalized finish decision.
    if "conclusion" in parsed or "enough" in parsed:
        return {"action": "finish", **_finish_payload(parsed)}
    raise ValueError("agent research decision: missing action")


def _finish_payload(parsed: Mapping[str, Any]) -> dict[str, Any]:
    conclusion = _clean_text(parsed.get("conclusion"))
    if not conclusion:
        raise ValueError("agent research decision: finish requires a conclusion")

    raw_ids = parsed.get("evidence_ids")
    if raw_ids is None:
        raw_ids = []
    if not isinstance(raw_ids, (list, tuple)):
        raise ValueError("agent research decision: evidence_ids must be a list")
    evidence_ids: list[str] = []
    for item in raw_ids:
        if isinstance(item, str) and item.strip():
            evidence_ids.append(item.strip())

    uncertainty_raw = parsed.get("uncertainty")
    uncertainty = _clean_text(uncertainty_raw) if uncertainty_raw is not None else ""

    refine_raw = parsed.get("refine_question")
    refine_question: str | None = None
    if refine_raw is not None:
        if not isinstance(refine_raw, str):
            raise ValueError("agent research decision: refine_question must be a string or null")
        cleaned = _clean_text(refine_raw)
        refine_question = cleaned or None

    return {
        "conclusion": conclusion,
        "evidence_ids": evidence_ids,
        "uncertainty": uncertainty,
        "refine_question": refine_question,
    }


def _extract_content(result: dict[str, Any]) -> str:
    """Extract the raw model output text from a provider result dict."""
    content = result.get("content")
    if isinstance(content, str) and content.strip():
        return content
    json_payload = result.get("json")
    if isinstance(json_payload, dict):
        return json.dumps(json_payload)
    raise ValueError(
        "Agent research turn result did not contain text content. "
        f"Got keys: {sorted(result.keys())}"
    )


# ── model request construction ───────────────────────────────────────────────
# The agent decision request carries ONLY the question + the research-phase
# tool catalog + a compact evidence digest.  It must never contain the full
# research result object nor a workflow schema dump — the digest builder below
# is the only evidence channel into the prompt.


_RESEARCH_DECISION_RETRY_PROMPT = (
    "Your previous reply was empty or not valid JSON for VibeComfy's research "
    "decision transport. Reply with exactly one JSON object and no other "
    "markdown. Expected shapes: "
    '{"action": "call", "tool": "hivemind_search", "args": {"query": "..."}} '
    'or {"action": "finish", "conclusion": "...", "evidence_ids": [...], '
    '"uncertainty": "", "refine_question": null}.'
)

_RESEARCH_DECISION_MAX_ATTEMPTS = 3


def _research_decision_retry_messages(
    messages: list[dict[str, Any]],
    exc: BaseException,
) -> list[dict[str, Any]]:
    """Append the corrective retry nudge (with redacted raw preview) to the
    decision-turn messages, mirroring the batch-REPL recovery in provider.py."""
    prompt = _RESEARCH_DECISION_RETRY_PROMPT
    raw_preview = getattr(exc, "raw_response_preview", None)
    if isinstance(raw_preview, str) and raw_preview.strip():
        prompt = (
            f"{prompt}\n\n"
            "Previous response preview, for correction only:\n"
            f"{raw_preview.strip()}"
        )
    return [*messages, {"role": "system", "content": prompt}]


def _run_decision_turn_with_retry(
    judge_fn: Callable[..., dict[str, Any]],
    *,
    question: str,
    digest: str,
    messages: list[dict[str, Any]],
    deadline: float,
    now_fn: Callable[[], float],
    max_attempts: int = _RESEARCH_DECISION_MAX_ATTEMPTS,
) -> tuple[dict[str, Any], int]:
    """Run one agent decision turn with bounded corrective retries.

    A malformed/empty decision (typed ``MalformedModelJSON``) is retried up
    to *max_attempts* times, appending a corrective system message that
    carries the redacted raw preview so the model can fix its output — the
    same recovery the batch-REPL path has (provider.py).  Provider-level
    failures (AuthError/TimeoutError/ProviderError) are NEVER retried: only
    the parse-level typed failure is a retryable model-output problem.

    The wall-clock deadline is checked before every retry: an in-flight
    provider call may overrun, but the stage never starts ANOTHER call after
    the deadline.  Returns ``(decision, retry_count)``; raises the last
    ``MalformedModelJSON`` when retries are exhausted.
    """
    from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON  # noqa: PLC0415

    retries = 0
    last_exc: MalformedModelJSON | None = None
    current_messages = messages
    for attempt_index in range(max_attempts):
        if attempt_index > 0 and last_exc is not None:
            if now_fn() >= deadline:
                raise last_exc
            current_messages = _research_decision_retry_messages(messages, last_exc)
            retries += 1
        try:
            return judge_fn(question, digest, current_messages), retries
        except MalformedModelJSON as exc:
            last_exc = exc
            if attempt_index >= max_attempts - 1:
                raise
    raise last_exc  # pragma: no cover - loop above always returns or raises


def _brief_model_family_nudge(research_brief: str) -> str:
    """Return a hivemind_search filter nudge when the brief names model families.

    The classifier brief carries the request's model families (e.g.
    ``- Model families: LTXV, Wan``) and the Hivemind corpus mixes families —
    off-topic MiniMax H3 rows drown LTXV/SDXL queries.  When a family is
    named, the agent is instructed to pass it as a ``hivemind_search``
    ``filters={"model_family": ...}`` and prefer family-matching hits.  This
    is a SOFT nudge: the agent still chooses the query and may omit the filter
    when the question is family-agnostic — no hard filter is injected, so a
    wrong family guess can never zero out a search.
    """
    family_line = ""
    for text_line in research_brief.splitlines():
        if text_line.strip().startswith("- Model families:"):
            family_line = text_line.strip()
            break
    if not family_line:
        return ""
    families = [
        part.strip()
        for part in family_line.split(":", 1)[1].split(",")
        if part.strip()
    ]
    if not families:
        return ""
    return (
        "Model-family focus: the classifier brief names model families "
        f"{', '.join(families)}. hivemind_search accepts "
        'filters={"model_family": "<family>"} — pass the named family when '
        "the question targets it, and prefer hits that match it over "
        "off-family leads."
    )


def _brief_source_preference_nudge(research_brief: str) -> str:
    """Return a hivemind_search ``source_type`` nudge when the brief names
    source preferences (``workflows`` / ``messages`` / ``hivemind``).

    The classifier brief can carry ``- Source preferences: workflows, messages``
    (the classifier prompt defines them: ``workflows`` = change-by-precedent /
    wiring-pattern requests, ``messages`` = community knowledge and usage
    tips).  This translates those tiers into the concrete ``source_type``
    filter the tool accepts, so the agent passes ``filters={"source_type":
    "workflow"}`` for an exact graph precedent and ``filters={"source_type":
    "discord"}`` for community knowledge.  SOFT nudge: the agent still chooses
    the query and may omit the filter.
    """
    source_line = ""
    for text_line in research_brief.splitlines():
        if text_line.strip().startswith("- Source preferences:"):
            source_line = text_line.strip()
            break
    if not source_line:
        return ""
    prefs = [part.strip().casefold() for part in source_line.split(":", 1)[1].split(",") if part.strip()]
    if not prefs:
        return ""
    hints: list[str] = []
    if "workflows" in prefs:
        hints.append(
            '"workflow" when you need an exact graph precedent (class types, '
            "node wiring, settings to preserve)"
        )
    if "messages" in prefs:
        hints.append(
            '"discord" when you need community knowledge (what people actually '
            "use, recommendations, settings, gotchas)"
        )
    if "hivemind" in prefs and not hints:
        hints.append(
            '"workflow" for graph precedents, "discord" for community knowledge'
        )
    if not hints:
        return ""
    return (
        "Source preferences: the classifier brief prefers "
        f"{', '.join(sorted(set(prefs)))}. hivemind_search accepts "
        'filters={"source_type": "<tier>"} — use ' + " or ".join(hints) + "."
    )


def build_agent_research_messages(
    *,
    question: str,
    evidence_digest: str,
    route: str,
    research_brief: str = "",
) -> list[dict[str, str]]:
    """System + user messages for one agent research decision turn.

    ``evidence_digest`` is the compact, bounded ledger-only digest built by
    :func:`build_evidence_digest` — never raw tool bodies, never the legacy
    result, never the workflow graph.  ``research_brief`` is the optional
    full brief from the classifier plan (all search directions, known graph
    context, source preferences, avoid-list) assembled by
    :func:`build_research_brief`; the narrow ``question`` remains the
    question-before-search marker.  The system prompt documents the
    research-phase tool catalog, the call/finish action contract, the
    downstream consumer of the synthesis, and the per-turn budget display;
    the agent chooses every tool call.
    """
    catalog = tool_catalog_docs(PHASE_RESEARCH, allowed_names=RESEARCH_ALLOWED_TOOLS)
    system = (
        "You are the research stage of a ComfyUI workflow assistant. "
        "Resolve the specific open question(s) blocking the current request "
        "by choosing and calling evidence tools yourself; then finish when the "
        "evidence answers the question.\n"
        f"Available tools (research phase only):\n{catalog}\n"
        "Who consumes your result:\n"
        "- On adapt routes, an IMPLEMENT agent turns your synthesis into "
        "concrete graph edits; it has NO research tools, so your conclusion "
        "must be actionable on its own: recommend the exact class types and "
        "their roles, the wiring/socket pattern, settings to preserve, and "
        "the tradeoffs you weighed.\n"
        "- On research-only routes, your synthesis becomes the user-facing "
        "answer.\n"
        "Rules:\n"
        "- Call a tool to gather evidence; the tool result will be returned in "
        "the next digest. Choose the query and the tool yourself.\n"
        "- Search hits are LEADS, not answers: fetch every Hivemind record "
        "you rely on materially (hivemind_get) so your claims are attributed "
        "to fetched content, not titles.\n"
        "- Cite ONLY evidence IDs that were returned by the tools; never "
        "invent IDs or quote sources that were not returned. Attach the "
        "evidence IDs you actually used.\n"
        "- Record genuine uncertainty instead of guessing, and name the "
        "tradeoffs you found.\n"
        "- Finish when the evidence answers the question with acceptable "
        "certainty; do not over-search. The digest shows your time left — "
        "watch it and leave room to finish with a synthesis.\n"
        "- Before finishing, SELF-CHECK that your synthesis answers the "
        "original question with concrete substance: for an adapt request that "
        "means exact class types and roles, wiring/socket/terminal pattern, "
        "settings or defaults to preserve, tradeoffs, and uncertainty — each "
        "material claim backed by a fetched evidence ID you cite. A finish "
        "with zero cited evidence IDs, or a conclusion that just restates the "
        "question, is not acceptable: fetch and cite support, or refine the "
        "question. If you fetched records, you MUST cite at least one of "
        "their ids (either the hivemind:... lead or the hivemind_get:... "
        "record id) — a finish that fetched but cites nothing is rejected as "
        "premature. The implement agent (or the user, on research routes) "
        "relies on this synthesis alone.\n"
        "- Semantic trap: community terms for fast/distilled LoRAs overlap — "
        "'distillation', 'turbo', 'streaming', and 'speed' LoRAs are the SAME "
        "family (a distillation LoRA IS the fast/streaming/turbo variant). "
        "Do not reject fetched records that name 'turbo' or 'streaming' "
        "LoRAs when the question asks about distillation LoRAs.\n"
        "- Searches, fetches, and registry lookups are UNBOUNDED — use as "
        "many as the question needs. The only limit is wall-clock time "
        "(shown in the digest). Fetched records appear in the digest in "
        "full; duplicate fetches of the same id are served from cache "
        "silently. Never request or dump workflow JSON payloads.\n"
        "Reply with exactly one JSON object per turn:\n"
        '{"action": "call", "tool": "<name>", "args": {<tool arguments>}} — '
        "gather more evidence, or\n"
        '{"action": "finish", "conclusion": string, "evidence_ids": [string, ...], '
        '"uncertainty": string} — the evidence answers the question.'
    )
    user_lines = [
        f"Research question: {question}",
        f"Route: {route}",
    ]
    brief = _clean_text(research_brief)
    if brief:
        user_lines.append(brief)
    family_nudge = _brief_model_family_nudge(research_brief)
    if family_nudge:
        user_lines.append(family_nudge)
    source_nudge = _brief_source_preference_nudge(research_brief)
    if source_nudge:
        user_lines.append(source_nudge)
    user_lines.extend(
        [
            "Evidence digest (tool statuses, evidence IDs, and previews only):",
            evidence_digest,
        ]
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def _as_str_list(value: Any) -> list[str]:
    """Normalize a string/list metadata value to a list of clean strings."""
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _prose_description(row: Mapping[str, Any]) -> str:
    """One-line human description of a workflow row, python-scratchpad-stripped."""
    raw = _first_text(row, "body", "description", "content")
    if not raw:
        return ""
    cut = len(raw)
    for marker in (
        "Python scratchpad source:",
        "Python ready-template source:",
        "Workflow semantics (rule-based):",
        "Workflow semantics (canonical):",
    ):
        idx = raw.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    text = " ".join(raw[:cut].split())
    if text.lower().startswith("description:"):
        text = text[len("description:") :].strip()
    return text


def _class_tokens(semantics: Mapping[str, Any]) -> list[str]:
    """Deterministic class inventory: node_class_multiset (counts) else node_types."""
    multiset = semantics.get("node_class_multiset")
    # Accept any Mapping — frozen ToolResults wrap nested dicts in mappingproxy.
    if isinstance(multiset, Mapping) and multiset:
        items = sorted(
            ((str(k), int(v)) for k, v in multiset.items() if k),
            key=lambda kv: (-kv[1], kv[0].casefold()),
        )
        return [f"{name}×{count}" if count != 1 else name for name, count in items]
    return _as_str_list(semantics.get("node_types"))


def _is_workflow_row(row: Mapping[str, Any]) -> bool:
    """True when a fetched row is a workflow (kind column or semantics metadata)."""
    if str(row.get("kind") or "") == "workflow":
        return True
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    return isinstance(metadata.get("workflow_semantics"), Mapping)


# Workflow digest line caps (Grok workflow-communication spec).
_WORKFLOW_LINE_CAP = 800
_WORKFLOW_CLASS_CAP = 24
_WORKFLOW_MODEL_CAP = 8
_WORKFLOW_CUSTOM_CAP = 12


def _workflow_digest_line(row: Mapping[str, Any], *, limit: int = _WORKFLOW_LINE_CAP) -> str:
    """Deterministic bounded preview of a fetched WORKFLOW row.

    Workflow rows are the one big-record case: their ``body`` is often a
    short description followed by tens of KB of generated Python, and the
    node-class line lands AFTER that (truncated away by any body-prefix
    preview).  Communicate the workflow via its structured
    ``workflow_semantics`` (class inventory, task/media, families, gates)
    instead — never ``payload``/Python source.  Discord/distillation rows
    keep the plain body preview (they are small prose).
    """
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    semantics = _workflow_semantics(row)
    gates = semantics.get("promotion_gates") if isinstance(semantics.get("promotion_gates"), Mapping) else {}

    title = _first_text(row, "title", "name") or "(untitled workflow)"
    parts: list[str] = [title]

    desc = _prose_description(row)
    if desc:
        parts.append("desc: " + desc)

    kv: list[str] = []
    for key, label in (("task_type", "task"), ("media_type", "media")):
        value = semantics.get(key)
        if isinstance(value, str) and value and value != "unknown":
            kv.append(f"{label}={value}")
    families = _as_str_list(semantics.get("model_families"))
    if families:
        kv.append("families=" + ",".join(families))
    if kv:
        parts.append(" ".join(kv))

    classes = _class_tokens(semantics)[:_WORKFLOW_CLASS_CAP]
    if classes:
        all_classes = _class_tokens(semantics)
        extra = len(all_classes) - len(classes)
        suffix = f" +{extra}" if extra > 0 else ""
        parts.append("classes: " + ", ".join(classes) + suffix)

    custom = _as_str_list(semantics.get("custom_nodes"))[:_WORKFLOW_CUSTOM_CAP]
    if custom:
        parts.append("custom: " + ", ".join(custom))

    models = _as_str_list(semantics.get("models"))[:_WORKFLOW_MODEL_CAP]
    if models:
        parts.append("models: " + ", ".join(models))

    gate_bits: list[str] = []
    for key, label in (
        ("parseable_workflow", "parseable"),
        ("has_compiled_api", "compiled_api"),
        ("has_workflow_json", "json"),
    ):
        if key in gates:
            gate_bits.append(f"{label}={bool(gates.get(key))}")
    if not gate_bits and metadata.get("has_workflow_json") is True:
        gate_bits.append("json=True")
    if gate_bits:
        parts.append("gates: " + " ".join(gate_bits))

    url = _first_text(row, "url", "source_url", "permalink")
    if url:
        parts.append("url: " + url)

    if len(parts) == 1:  # title only — say so
        parts.append("(no workflow semantics)")

    line = " | ".join(parts)
    if len(line) <= limit:
        return line
    return line[: limit - 1].rstrip() + "…"


def build_evidence_digest(
    *,
    question: str,
    tool_calls: Sequence[Mapping[str, Any]],
    artifacts: Mapping[str, EvidenceArtifact],
    limit: int = _MAX_DIGEST_CHARS,
    seconds_left: float | None = None,
) -> str:
    """Compact, bounded digest of the tool evidence gathered so far.

    Priority order (newest-first for evidence): the digest spends its budget
    on FETCHED RECORDS (the only synthesis-grade text), then cheap tool
    status one-liners, then search-hit title lists last (older searches
    collapse to a count).  This keeps unbounded searching from drowning the
    fetched evidence in hit titles.

    Every fetched record gets the full ``_MAX_RECORD_PREVIEW_CHARS`` window —
    there is no last-fetch special case (fetches are free; every record is
    equally evidence).  ``payload`` (workflow JSON, 50KB+) never enters the
    digest; bodies/descriptions/content only.

    ``seconds_left`` becomes the header ``Time left: ~Ns.`` — the only
    remaining budget the agent should watch.
    """
    header: list[str] = []
    if seconds_left is not None:
        header.append(f"Time left: ~{max(0, int(seconds_left))}s.")
    lines: list[str] = []

    # 1. Fetched records first, newest-first (the evidence the agent reasons
    #    from).  Reverse the tool-call order so the most recent fetch leads.
    record_lines: list[str] = []
    status_lines: list[str] = []
    search_lines: list[str] = []
    seen_record_ids: set[str] = set()
    for call in reversed(tool_calls):
        tool = str(call.get("tool") or "")
        status = str(call.get("status") or "")
        query = _bounded(call.get("query", ""), 120)
        ids = [str(item) for item in (call.get("evidence_ids") or ())]
        head = f"- {tool} → {status}"
        if query:
            head += f" ({query})"
        if ids:
            head += f" ids={ids}"
        conclusion = _clean_text(call.get("conclusion"))
        conclusion_line = ""
        if conclusion:
            conclusion_line = f"    {_bounded(conclusion, _MAX_CONCLUSION_PREVIEW_CHARS)}"

        if tool.startswith("hivemind_get") and status == "ok":
            # Fetch calls: their records are the evidence — emit record
            # previews here (newest first), deduped.
            for evidence_id in ids:
                if evidence_id in seen_record_ids:
                    continue
                seen_record_ids.add(evidence_id)
                artifact = artifacts.get(evidence_id)
                if artifact is None:
                    continue
                body = artifact.body if isinstance(artifact.body, Mapping) else {"value": artifact.body}
                title = _bounded(body.get("title") or body.get("name") or body.get("evidence_id") or evidence_id, 90)
                kind = str(artifact.kind or "")
                preview = ""
                if kind == "hivemind_record":
                    # Fetched record content — never payload (workflow JSON).
                    # Workflow rows get the structured semantics line (their
                    # body is a description + generated Python, not the node
                    # inventory); Discord/distillation rows are small prose
                    # and preview their body directly.
                    if _is_workflow_row(body):
                        preview = _workflow_digest_line(body)
                    else:
                        preview = _bounded(
                            str(
                                body.get("body")
                                or body.get("description")
                                or body.get("content")
                                or ""
                            ),
                            _MAX_RECORD_PREVIEW_CHARS,
                        )
                elif kind != "hivemind_search_hit":
                    preview = _bounded(
                        str(body.get("description") or body.get("snippet") or ""),
                        _MAX_HIT_PREVIEW_CHARS,
                    )
                line = f"    [{evidence_id}] {title}"
                if preview:
                    line += f": {preview}"
                record_lines.append(line)
            # Status line for the fetch itself stays cheap (one-liner).
            status_lines.append(head)
            if conclusion_line:
                status_lines.append(conclusion_line)
        elif tool.startswith("hivemind_search") and status == "ok":
            # Search hits are leads: only the NEWEST search lists titles;
            # older ones collapse to a count line (they are pointers, and
            # unbounded searches must not drown the digest in titles).
            search_lines.append(head)
            if conclusion_line:
                search_lines.append(conclusion_line)
        else:
            # Refusals, failures, registry lookups: plain one-liners.
            status_lines.append(head)
            if conclusion_line:
                status_lines.append(conclusion_line)

    # Compose in priority order with a budget split: records get the bulk.
    record_budget = int(limit * 0.7)
    status_budget = int(limit * 0.15)
    lines.extend(header)
    lines.extend(record_lines)
    lines.extend(status_lines)
    lines.extend(search_lines)

    digest = "\n".join(lines).strip()
    if not digest:
        digest = "(no tool evidence gathered yet)"
    if len(digest) > limit:
        digest = digest[: limit - 1].rstrip() + "…"
    return digest


def run_agent_research_turn(
    question: str,
    evidence_digest: str,
    *,
    route: str,
    model: str,
    effort: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    research_brief: str = "",
) -> dict[str, Any]:
    """Run one agent research DECISION turn through the provider seam.

    Builds the bounded messages (unless supplied), dispatches through
    ``provider.run_model_turn`` with ``response_contract="json"``, and parses
    the decision (call|finish) fail-closed.  Returns a decision dict.
    """
    if messages is None:
        messages = build_agent_research_messages(
            question=question,
            evidence_digest=evidence_digest,
            route=route,
            research_brief=research_brief,
        )
    from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON, run_model_turn  # noqa: PLC0415

    result = run_model_turn(
        question,
        messages,
        route=route,
        model=model,
        effort=effort,
        response_contract="json",
        profiling_context={"backend_phase": "research_stage"},
    )
    raw: str | None = None
    try:
        raw = _extract_content(result)
        decision = parse_agent_research_decision(raw)
        _record_result_attempts(result)
        return decision
    except ValueError as exc:
        # Mirror the classify/reply seam (agent_backend.py): a malformed or
        # empty decision must surface as the provider's typed
        # MalformedModelJSON carrying the redacted raw preview + parse reason,
        # and the recorded model attempt must be flipped to failure — the
        # research stage must not log a "success" for output it could not
        # parse (observed: finish_reason=stop prose killing the whole phase).
        failure_type = _downstream_failure_type(raw)
        _mark_last_attempt_failed(result, raw=raw, failure_type=failure_type)
        typed = (
            exc
            if isinstance(exc, MalformedModelJSON)
            else MalformedModelJSON(
                f"agent research decision: {exc}",
                raw_response=raw,
                parse_reason=failure_type,
            )
        )
        _attach_model_turn_evidence(
            typed,
            result,
            model=model,
            phase="research_stage",
            raw=raw,
        )
        raise typed from None


def _default_judge_fn(spec: Any) -> Callable[[str, str, list[dict[str, Any]] | None], dict[str, Any]]:
    """Bind the provider decision turn to the resolved research profile spec."""

    def _judge(
        question: str, evidence_digest: str, messages: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        return run_agent_research_turn(
            question,
            evidence_digest,
            route=getattr(spec, "agent", "") or "",
            model=getattr(spec, "model", "") or "",
            effort=getattr(spec, "effort", None),
            messages=messages,
        )

    return _judge


# ── trace contracts ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentResearchIteration:
    """One agent turn: a chosen tool call or the final synthesis."""

    iteration: int
    question: str
    tool_calls: tuple[dict[str, Any], ...]
    synthesis: dict[str, Any]
    verdict: str  # "enough" | "refine"

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "question": self.question,
            "tool_calls": [dict(call) for call in self.tool_calls],
            "synthesis": dict(self.synthesis),
            "verdict": self.verdict,
        }


@dataclass(frozen=True)
class AgentResearchTrace:
    """Full trace of one agent-owned research run (question + decisions)."""

    route: str
    question: str
    iterations: tuple[AgentResearchIteration, ...]
    final_verdict: str  # "enough" | "refine" | "failed" | "skipped"
    summary: str
    citations: tuple[str, ...]
    uncertainty: str
    status: str  # "ok" | "exhausted" | "failed" | "skipped"
    elapsed_seconds: float
    warnings: tuple[str, ...] = ()
    error: str | None = None
    # R4 honesty counters: how many agent-chosen tool calls actually executed
    # and how many evidence artifacts were recorded.  Consumers (the reply
    # memo) use these to distinguish "searched and found nothing" from
    # "research never ran a tool".
    executed_tool_calls: int = 0
    evidence_artifact_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "route": self.route,
            "question": self.question,
            "iterations": [item.to_dict() for item in self.iterations],
            "final_verdict": self.final_verdict,
            "summary": self.summary,
            "citations": list(self.citations),
            "uncertainty": self.uncertainty,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "executed_tool_calls": self.executed_tool_calls,
            "evidence_artifact_count": self.evidence_artifact_count,
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.error is not None:
            payload["error"] = self.error
        return payload


# ── the C1 tool-calling loop ─────────────────────────────────────────────────


def _tool_call_digest(
    *,
    tool: str,
    result: ToolResult,
    query: str = "",
    conclusion: str = "",
    evidence_ids: Sequence[str] = (),
) -> dict[str, Any]:
    # The digest shows the RECORDED artifact ids (what the agent can cite),
    # not ``result.evidence_ids`` — for ``hivemind_get`` the recorded id is
    # the namespaced ``hivemind_get:...`` artifact id, so digest ids and
    # artifact ids always agree (P1-b parity).
    return {
        "tool": tool,
        "status": result.status.value,
        "query": query,
        "evidence_ids": list(evidence_ids),
        "conclusion": conclusion,
    }


def _get_record_evidence_id(result: ToolResult, requested_id: str) -> str | None:
    """Evidence ID for a fetched record — namespaced so search-hit ids never collide."""
    if result.status is not ToolStatus.OK:
        return None
    if not requested_id.startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
        return None
    return f"hivemind_get:{requested_id.removeprefix(_HIVEMIND_EVIDENCE_ID_PREFIX)}"


class _StageToolSession:
    """Per-stage session namespace handed to the registry handlers.

    Carries the injected fakes (``search_fn`` / ``get_fn``) and the
    ``cache_root`` the tool modules need; the registry handlers read these
    attributes so the stage and the batch resolver share ONE dispatch path.
    """

    __slots__ = ("search_fn", "get_fn", "cache_root")

    def __init__(
        self,
        *,
        search_fn: Callable[..., ToolResult] | None,
        get_fn: Callable[..., ToolResult] | None,
        cache_root: Any,
    ) -> None:
        self.search_fn = search_fn
        self.get_fn = get_fn
        self.cache_root = cache_root


def _default_tool_fn(
    tool: str,
    args: Mapping[str, Any],
    *,
    search_fn: Callable[..., ToolResult] | None = None,
    get_fn: Callable[..., ToolResult] | None = None,
    cache_root: Any = None,
) -> ToolResult:
    """Execute one agent-chosen research tool call through the ToolSpec registry.

    The AGENT chooses the tool and arguments; Python only executes.  The
    allowlist and budgets were already enforced by the loop.  Dispatch and
    argument validation live in the registry: the registered handler receives
    the agent's declared arguments (filters/cursor/limit/timeout included) and
    a missing required argument or malformed value is a typed
    ``invalid_request`` — never a raise, never a dropped argument.
    """
    spec = TOOL_SPEC_BY_NAME[tool]
    session = _StageToolSession(
        search_fn=search_fn,
        get_fn=get_fn,
        cache_root=cache_root,
    )
    return invoke_tool(spec, session, args, None)


def run_agent_research_stage(
    *,
    route: str,
    question: str,
    spec: Any | None = None,
    search_fn: Callable[..., ToolResult] | None = None,
    get_fn: Callable[..., ToolResult] | None = None,
    judge_fn: Callable[..., dict[str, Any]] | None = None,
    tool_fn: Callable[..., ToolResult] | None = None,
    now_fn: Callable[[], float] | None = None,
    deadline_seconds: float = TOOL_PHASE_DEADLINE_SECONDS,
    max_turns: int = _MAX_TURNS,
    cache_root: Any = None,
    research_brief: str = "",
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Run the C1 agent-owned tool-calling research loop.

    The AGENT chooses every tool call and decides when to finish; Python
    executes the chosen calls, records typed evidence, and enforces the
    research-phase allowlist plus the wall-clock ``deadline_seconds``.
    Searches / fetches / registry lookups / decision turns are UNBOUNDED
    (minimal-budget plan): the deadline is the only stop, and ``max_turns``
    is a test-only clamp (None in production).

    Per turn the agent returns one decision (via ``judge_fn``):
    ``{"action": "call", "tool", "args"}`` to gather more evidence or
    ``{"action": "finish", "conclusion", "evidence_ids", "uncertainty"}`` to
    stop.  A tool call outside the allowlist or a budget-exhausted call is a
    typed refusal recorded in the ledger; the agent sees it in the next
    digest and may finish or refine.

    ``research_brief`` (optional) is the full classifier brief assembled by
    :func:`build_research_brief`; it is embedded in every decision-turn
    message so the agent works from ALL search directions, graph context,
    source preferences, and the avoid-list — not just the narrow question.
    Each turn's digest shows the time left so the agent can wind down to a
    finish.  The wall-clock deadline bounds the loop: it is enforced before
    the provider call and after tool execution.
    A tool call the agent has already decided is always executed (never
    dropped mid-decision), and the loop stops after that call — slow
    provider/tool latency cannot silently overrun the budget, and a decided
    call's evidence is never discarded.

    ``search_fn`` / ``get_fn`` / ``tool_fn`` / ``judge_fn`` default to the
    module-level tool implementations / provider decision turn, resolved at
    call time so tests and callers may inject fakes.  Never raises: failures
    are captured in the returned trace (``status="failed"`` / ``"exhausted"``)
    and the evidence pack recorded so far.
    """
    now = now_fn or time.monotonic
    if tool_fn is None:
        tool_fn = lambda tool, args, **kwargs: _default_tool_fn(  # noqa: E731
            tool, args, search_fn=search_fn, get_fn=get_fn, cache_root=cache_root
        )
    if judge_fn is None:
        judge_fn = _default_judge_fn(spec)
    started = now()
    deadline = started + max(0.0, float(deadline_seconds))

    artifacts: dict[str, EvidenceArtifact] = {}
    ledger_entries: list[EvidenceLedgerEntry] = []
    warnings: list[str] = []
    iterations: list[AgentResearchIteration] = []
    tool_call_digests: list[dict[str, Any]] = []
    # P1-c: count EXECUTED agent-chosen tool calls (not refusal/premature
    # digest entries) so a finish with zero research activity is detectable.
    tool_calls_made = 0
    # Fetches are free (minimal-budget plan): no counters, no exhaustion
    # refusals.  The deadline is the only stop.  Duplicate hivemind_get of an
    # already-fetched id is a SILENT cache hit (skip the network) — no
    # refusal, no special status, no rationing.
    fetched_requested_ids: set[str] = set()

    final_verdict = "refine"
    final_summary = ""
    final_uncertainty = ""
    final_citations: tuple[str, ...] = ()
    status = "ok"
    error: str | None = None

    def _add_artifact(artifact: EvidenceArtifact) -> None:
        # Keep-first on id collisions across turns (deterministic).
        if artifact.evidence_id not in artifacts:
            artifacts[artifact.evidence_id] = artifact

    def _add_entry(entry: EvidenceLedgerEntry) -> None:
        ledger_entries.append(entry)

    def _record_call(
        tool: str,
        result: ToolResult,
        *,
        query: str,
        decision: str,
        conclusion: str,
        artifacts_to_add: Sequence[EvidenceArtifact] = (),
        evidence_ids: Sequence[str] = (),
    ) -> None:
        for artifact in artifacts_to_add:
            _add_artifact(artifact)
        _add_entry(
            EvidenceLedgerEntry(
                decision=decision,
                conclusion=conclusion,
                evidence_ids=tuple(evidence_ids),
                uncertainty=(
                    "" if result.status is ToolStatus.OK else conclusion
                ),
            )
        )
        digest = _tool_call_digest(
            tool=tool,
            result=result,
            query=query,
            conclusion=conclusion,
            evidence_ids=evidence_ids,
        )
        tool_call_digests.append(digest)
        iterations.append(
            AgentResearchIteration(
                iteration=len(iterations) + 1,
                question=current_question,
                tool_calls=(digest,),
                synthesis={},
                verdict="refine",
            )
        )

    def _refusal_call(tool: str, query: str, message: str) -> None:
        # A refusal is itself an agent-visible decision: it enters the digest
        # (so the agent can adapt), the ledger (typed, preserved), and the
        # trace (one iteration per turn — keeps the loop bounded).
        _add_entry(
            EvidenceLedgerEntry(
                decision=tool,
                conclusion=message,
                evidence_ids=(),
                uncertainty=message,
            )
        )
        warnings.append(message)
        digest = {
            "tool": tool,
            "status": ToolStatus.REFUSED.value,
            "query": query,
            "evidence_ids": [],
            "conclusion": message,
        }
        tool_call_digests.append(digest)
        iterations.append(
            AgentResearchIteration(
                iteration=len(iterations) + 1,
                question=current_question,
                tool_calls=(digest,),
                synthesis={},
                verdict="refine",
            )
        )

    def _finish_premature_turn(conclusion: str, message: str) -> None:
        # P1-c: a finish with zero citable evidence AND zero tool calls made is
        # malformed — nothing was researched, so there is no synthesis to
        # record.  Do NOT auto-fail the stage: record the typed
        # ``finish_premature`` marker (ledger + digest + one refinement
        # iteration) so the next turn nudges the agent to make at least one
        # evidence tool call before finishing.  The wall-clock deadline still
        # bounds the loop if the agent keeps refusing to call a tool.
        _add_entry(
            EvidenceLedgerEntry(
                decision=DECISION_FINISH_PREMATURE,
                conclusion=message,
                evidence_ids=(),
                uncertainty=message,
            )
        )
        warnings.append(message)
        digest = {
            "tool": "finish",
            "status": ToolStatus.REFUSED.value,
            "query": _bounded(conclusion, _MAX_CONCLUSION_PREVIEW_CHARS),
            "evidence_ids": [],
            "conclusion": message,
        }
        tool_call_digests.append(digest)
        iterations.append(
            AgentResearchIteration(
                iteration=len(iterations) + 1,
                question=current_question,
                tool_calls=(digest,),
                synthesis={},
                verdict="refine",
            )
        )

    current_question = question

    try:
        _add_artifact(
            EvidenceArtifact(
                evidence_id=_QUESTION_ARTIFACT_ID,
                kind="research_question",
                body={"question": question, "route": route},
                source="classify",
            )
        )
        _add_entry(
            EvidenceLedgerEntry(
                decision=DECISION_QUESTION,
                conclusion=question,
                evidence_ids=(_QUESTION_ARTIFACT_ID,),
                uncertainty="",
            )
        )

        turns_taken = 0
        agent_finished = False
        # Minimal-budget plan: no turn cap in production (max_turns=None).
        # The deadline is the only stop; tests pass max_turns to stay fast.
        while max_turns is None or turns_taken < int(max_turns):
            if now() > deadline:
                warnings.append("research stage phase deadline exceeded; stopped early")
                break

            # Honest remaining-time display: the digest is built BEFORE the
            # decision model call, so raw (deadline - now()) overstates the
            # budget by one full decision-turn's latency.  Reserve that
            # (bounded, per observed calls) so the agent winds down to a
            # finish instead of planning a search that the deadline will
            # drop.  The reserve is a lower bound: a slow provider eats more,
            # a fast one less — the loop's own checks stay authoritative.
            decision_reserve = min(_DECISION_TURN_LATENCY_RESERVE_SECONDS, max(0.0, deadline - now()))
            digest = build_evidence_digest(
                question=current_question,
                tool_calls=tool_call_digests,
                artifacts=artifacts,
                seconds_left=max(0.0, deadline - now() - decision_reserve),
            )
            messages = build_agent_research_messages(
                question=current_question,
                evidence_digest=digest,
                route=route,
                research_brief=research_brief,
            )
            decision, decision_retries = _run_decision_turn_with_retry(
                judge_fn,
                question=current_question,
                digest=digest,
                messages=messages,
                deadline=deadline,
                now_fn=now,
            )
            turns_taken += 1
            if decision_retries:
                warnings.append(
                    "research decision recovered after "
                    f"{decision_retries} corrective retry attempt(s) "
                    "(malformed/empty model decision)"
                )

            action = str(decision.get("action") or "finish")
            if action == "finish":
                # P2: order-preserving dedupe — the compact ledger contract
                # rejects duplicate evidence_ids, and a duplicated citation
                # must not crash synthesis or poison the trace.
                #
                # Citation id normalization (Grok contract): the agent may
                # cite EITHER spelling of a fetched record — the search lead
                # ``hivemind:table:id`` or the namespaced ``hivemind_get:
                # table:id``.  After a successful fetch of table:id, citing
                # either counts as citing that fetch; we normalize to the
                # canonical ``hivemind_get:table:id`` in the stored synthesis
                # so citations always resolve to the fetched body artifact.
                # Search-only finishes may cite lead ids (weaker claim: the
                # title exists).  ``research_question`` is never citable.
                raw_cited: list[str] = []
                for evidence_id in (decision.get("evidence_ids") or ()):
                    if evidence_id in artifacts:
                        raw_cited.append(evidence_id)
                        continue
                    # Alias: a lead id whose record was fetched maps to the
                    # namespaced get id.
                    if evidence_id.startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
                        aliased = "hivemind_get:" + evidence_id.removeprefix(_HIVEMIND_EVIDENCE_ID_PREFIX)
                        if aliased in artifacts:
                            raw_cited.append(aliased)
                cited = tuple(dict.fromkeys(raw_cited))[:_MAX_JUDGMENT_CITATIONS]
                citable_citations = tuple(
                    citation for citation in cited if citation != _QUESTION_ARTIFACT_ID
                )
                # P1-c + R5c: finish-with-zero-evidence prevention.  A finish
                # is premature when (a) it cites no evidence AND made no tool
                # call (nothing was researched), or (b) it FETCHED records
                # but cites none of them — the agent gathered citable
                # evidence and ignored it (observed live: 7 fetched records,
                # then a zero-citation finish claiming "no distillation LoRA
                # exists" while its own fetches named the RAVEN/Turbo LoRAs;
                # delivering that would ship a false negative).  A search-only
                # run that found nothing worth fetching may still finish with
                # empty citations (honest "not in corpus").
                fetched_cited = any(
                    citation.startswith("hivemind_get:")
                    for citation in citable_citations
                )
                if not citable_citations and tool_calls_made == 0:
                    _finish_premature_turn(
                        conclusion=_clean_text(decision.get("conclusion")),
                        message=(
                            "finish_premature: you finished before making any "
                            "evidence tool call, so there is nothing to "
                            "synthesize from. Call at least one evidence tool "
                            "(hivemind_search / hivemind_get / "
                            "registry_lookup) before finishing, then cite the "
                            "evidence ids the tool returned."
                        ),
                    )
                    continue
                if fetched_requested_ids and not fetched_cited:
                    # Fetched records exist but the finish cites none of them.
                    # Reject as premature (do NOT auto-fail) — the work is
                    # preserved; the agent is nudged to cite what it read so
                    # the synthesis is grounded.  Alias-normalization above
                    # means a lead-spelling citation of a fetched record
                    # already counts, so this only fires on genuine ignores.
                    _finish_premature_turn(
                        conclusion=_clean_text(decision.get("conclusion")),
                        message=(
                            "finish_premature: you fetched records this turn "
                            "but cited none of them. Cite the hivemind_get:... "
                            "ids of the records you read (they appear in the "
                            "digest), or state explicitly why none answer the "
                            "question and cite the ones you dismissed. "
                            "Finishing with zero citations discards your own "
                            "research."
                        ),
                    )
                    continue
                agent_finished = True
                conclusion = _clean_text(decision.get("conclusion"))
                uncertainty = _clean_text(decision.get("uncertainty"))
                refine_question = decision.get("refine_question")
                refine_question_text = _clean_text(refine_question)
                enough = not bool(refine_question_text)

                _add_entry(
                    EvidenceLedgerEntry(
                        decision=DECISION_SYNTHESIZE,
                        conclusion=conclusion or "synthesis produced no conclusion",
                        evidence_ids=cited,
                        uncertainty=uncertainty,
                    )
                )
                _add_entry(
                    EvidenceLedgerEntry(
                        decision=DECISION_ENOUGH_REFINE,
                        conclusion=(
                            f"enough={enough}"
                            + (f"; refine_question={refine_question_text}" if refine_question_text else "")
                        ),
                        evidence_ids=cited,
                        uncertainty="",
                    )
                )

                final_summary = conclusion or "synthesis produced no conclusion"
                final_uncertainty = uncertainty
                final_citations = cited
                final_verdict = "enough" if enough else "refine"
                iterations.append(
                    AgentResearchIteration(
                        iteration=len(iterations) + 1,
                        question=current_question,
                        tool_calls=(),
                        synthesis={
                            "conclusion": conclusion,
                            "evidence_ids": list(cited),
                            "uncertainty": uncertainty,
                            "enough": enough,
                            "refine_question": refine_question_text or None,
                        },
                        verdict=final_verdict,
                    )
                )
                break

            if action != "call":
                warnings.append(
                    f"agent research decision returned unknown action {action!r}; stopping"
                )
                break

            # The deadline bounds the LOOP, never a decided call: a tool call
            # the agent already chose always executes (the after-tool check
            # below then stops the loop, preserving the call's evidence).
            # Dropping a decided call here turned slow provider latency into
            # "no search at all" — the exact exhaustion seen in production
            # (240s budget, 9 pro decision turns, zero executed calls).
            tool = str(decision.get("tool") or "")
            args = decision.get("args") if isinstance(decision.get("args"), Mapping) else {}
            if tool not in RESEARCH_ALLOWED_TOOLS:
                _refusal_call(
                    tool or "unknown_tool",
                    _bounded(str(args), 120),
                    (
                        f"tool {tool!r} is not in the research phase allowlist; "
                        "use hivemind_search/hivemind_get/registry_lookup or finish"
                    ),
                )
                continue
            _skip_network = False
            if tool == "hivemind_search":
                result = tool_fn(tool, args)  # unbounded (minimal-budget plan)
            elif tool == "hivemind_get":
                requested_id = str(args.get("evidence_id") or "").strip()
                # Normalize the cache key: agents pass the raw lead id
                # (``hivemind:table:id``), the namespaced get id
                # (``hivemind_get:table:id``), or a bare uuid — all map to the
                # SAME cached artifact.
                normalized_id = requested_id
                if normalized_id.startswith("hivemind_get:"):
                    normalized_id = normalized_id.removeprefix("hivemind_get:")
                cached_key = f"hivemind_get:{normalized_id.removeprefix(_HIVEMIND_EVIDENCE_ID_PREFIX)}"
                if requested_id and normalized_id in fetched_requested_ids:
                    # Already fetched this turn: SILENT cache hit.  Fetches
                    # are free (minimal-budget plan) — no refusal, no special
                    # status, no rationing.  Serve the cached artifact without
                    # a second network GET; projection records it identically.
                    cached = artifacts.get(cached_key)
                    if cached is not None:
                        result = ToolResult(
                            tool_name=HIVE_MIND_GET_TOOL,
                            status=ToolStatus.OK,
                            result={
                                "evidence_id": cached_key,
                                "source_type": "cached",
                                "row": (
                                    cached.body
                                    if isinstance(cached.body, Mapping)
                                    else {"body": cached.body}
                                ),
                            },
                            evidence_ids=(cached_key,),
                            diagnostics=(
                                ToolDiagnostic(
                                    code="hivemind_get_cached",
                                    message=f"returned cached record {cached_key} (already fetched this turn)",
                                ),
                            ),
                        )
                        _skip_network = True
                    else:
                        # Cache miss on a known-fetched id: fall through to a
                        # real fetch (defensive; shouldn't happen).
                        result = tool_fn(tool, args)
                else:
                    result = tool_fn(tool, args)
            elif tool == "registry_lookup":
                result = tool_fn(tool, args)  # unbounded (minimal-budget plan)
            else:  # pragma: no cover - allowlist check above already rejects
                _refusal_call(tool, _bounded(str(args), 120), f"unknown research tool {tool!r}")
                continue

            if not _skip_network:
                # Count the executed call exactly once, immediately after the
                # tool ran and BEFORE any projection can raise — a later
                # failure must not erase the honest "the agent did run N
                # calls" signal.  A silent cache hit is NOT a new executed
                # call (no network, no new evidence), so it is not counted.
                tool_calls_made += 1
            # Evidence projection is the registry's job: artifacts (full hit /
            # fetched-row bodies, correctly extracted from frozen results),
            # the compact ledger entry, and the current-turn digest all come
            # from ToolSpec.project.  The stage records the projected evidence
            # under its own decision identifiers and per-turn digest.
            #
            # Per-call projection must NEVER abort the phase: one malformed
            # corpus row (e.g. a hit whose ledger conclusion violates the
            # compact whitespace/length contract) previously fell through to
            # the stage-wide except and flipped status to "failed", discarding
            # every artifact the agent had already gathered (observed in
            # production: 4 executed calls, 32 evidence artifacts lost to a
            # single trailing-space ValueError).  The call DID execute and
            # consume its budget, so it is counted; the failure is surfaced as
            # a typed refusal the agent sees next digest and can adapt to.
            try:
                spec = TOOL_SPEC_BY_NAME[tool]
                artifacts_map, entry, _ = project_tool_evidence(
                    spec,
                    args,
                    result,
                    _StageToolSession(
                        search_fn=search_fn,
                        get_fn=get_fn,
                        cache_root=cache_root,
                    ),
                )
                if tool == "hivemind_search":
                    _record_call(
                        tool=HIVE_MIND_SEARCH_TOOL,
                        result=result,
                        query=str(args.get("query") or current_question),
                        decision=DECISION_SEARCH,
                        conclusion=entry["conclusion"],
                        artifacts_to_add=tuple(artifacts_map.values()),
                        evidence_ids=tuple(entry["evidence_ids"]),
                    )
                elif tool == "hivemind_get":
                    requested_id = str(args.get("evidence_id") or "")
                    get_evidence_id = _get_record_evidence_id(result, requested_id)
                    if get_evidence_id is not None:
                        # Dedupe bookkeeping: only a successful fetch (one that
                        # resolved to a row) marks the id as fetched, so a
                        # failed/absent row can legitimately be retried.  Store
                        # the NORMALIZED id (raw ``hivemind:table:id`` and
                        # namespaced ``hivemind_get:table:id`` spellings both
                        # map here) so the silent-cache guard in the dispatch
                        # block hits regardless of how the agent spells it.
                        normalized = requested_id
                        if normalized.startswith("hivemind_get:"):
                            normalized = normalized.removeprefix("hivemind_get:")
                        fetched_requested_ids.add(normalized)
                    # The registry projector stores the fetched row under the plain
                    # evidence id; the stage re-keys it to the namespaced
                    # ``hivemind_get:...`` id so search-hit ids never collide and
                    # the digest ids / citations always agree with the artifacts.
                    get_artifacts: list[EvidenceArtifact] = []
                    if get_evidence_id is not None:
                        for artifact in artifacts_map.values():
                            get_artifacts.append(
                                EvidenceArtifact(
                                    evidence_id=get_evidence_id,
                                    kind=artifact.kind,
                                    body=artifact.body,
                                    source=artifact.source,
                                )
                            )
                    _record_call(
                        tool=HIVE_MIND_GET_TOOL,
                        result=result,
                        query=requested_id,
                        decision=DECISION_GET,
                        conclusion=entry["conclusion"],
                        artifacts_to_add=get_artifacts,
                        evidence_ids=(get_evidence_id,) if get_evidence_id is not None else (),
                    )
                elif tool == "registry_lookup":
                    _record_call(
                        tool="registry_lookup",
                        result=result,
                        query=str(args.get("node_class") or ""),
                        decision=DECISION_REGISTRY,
                        conclusion=entry["conclusion"],
                        artifacts_to_add=tuple(artifacts_map.values()),
                        evidence_ids=tuple(entry["evidence_ids"]),
                    )
                else:  # pragma: no cover - allowlist check above already rejects
                    _refusal_call(tool, _bounded(str(args), 120), f"unknown research tool {tool!r}")
            except (ValueError, TypeError) as exc:
                # The call was already counted above (executed); do NOT
                # increment again here.  The refusal message itself becomes a
                # ledger conclusion, so normalize the exception text — and
                # never emit an empty detail (``str(ValueError()) == ""``
                # would leave a trailing ": " in the message, re-creating the
                # whitespace violation this guard exists to prevent).
                raw_detail = " ".join(str(exc).split())
                detail = raw_detail or type(exc).__name__
                _refusal_call(
                    tool,
                    _bounded(str(args), 120),
                    f"tool evidence projection failed; the call executed but its "
                    f"evidence was not recorded: {detail}",
                )

            if now() > deadline:
                warnings.append(
                    "research stage phase deadline exceeded after the tool "
                    "call; stopped early (the call's evidence is preserved)"
                )
                break

        if not agent_finished:
            # P1-a: the loop stopped WITHOUT an agent finish — deadline
            # exceeded, max_turns exhausted, or a malformed decision.  Never
            # label that "ok": a stage that produced no synthesis must be
            # distinguishable from a successful research run so the executor
            # can fail closed instead of implementing from nothing.
            status = "exhausted"
            warnings.append(
                "research stage stopped without an agent finish "
                "(deadline or max-turn exhaustion); status=exhausted"
            )
    except Exception as exc:  # noqa: BLE001 - research failures are typed, never raised
        status = "failed"
        final_verdict = "failed"
        error = f"{type(exc).__name__}: {exc}"
        raw_preview = getattr(exc, "raw_response_preview", None)
        if isinstance(raw_preview, str) and raw_preview.strip():
            error = f"{error} | raw response preview: {_bounded(raw_preview, 500)}"
        LOGGER.warning("agent research stage failed: %s", error)

    trace = AgentResearchTrace(
        route=route,
        question=question,
        iterations=tuple(iterations),
        final_verdict=final_verdict,
        summary=final_summary,
        citations=final_citations,
        uncertainty=final_uncertainty,
        status=status,
        elapsed_seconds=now() - started,
        warnings=tuple(warnings),
        error=error,
        executed_tool_calls=tool_calls_made,
        # Count TOOL-produced evidence only — the always-present
        # research_question artifact must not make "zero tool evidence"
        # report as one artifact (Codex review P1-5).
        evidence_artifact_count=sum(
            1 for artifact_id in artifacts if artifact_id != _QUESTION_ARTIFACT_ID
        ),
    )
    pack = EvidencePack(artifacts=artifacts, ledger=EvidenceLedger(entries=ledger_entries))
    return trace, pack


__all__ = [
    "AgentResearchIteration",
    "AgentResearchTrace",
    "DECISION_ENOUGH_REFINE",
    "DECISION_FINISH_PREMATURE",
    "DECISION_GET",
    "DECISION_QUESTION",
    "DECISION_REGISTRY",
    "DECISION_SEARCH",
    "DECISION_SYNTHESIZE",
    "RESEARCH_ALLOWED_TOOLS",
    "TOOL_PHASE_DEADLINE_SECONDS",
    "build_agent_research_messages",
    "build_evidence_digest",
    "build_research_brief",
    "form_research_question",
    "parse_agent_research_decision",
    "run_agent_research_stage",
    "run_agent_research_turn",
]
