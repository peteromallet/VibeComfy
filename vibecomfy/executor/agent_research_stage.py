"""C1 agent-owned research stage — one genuine tool-calling agent phase.

Runs the research phase for ``research`` / ``adapt`` routes as a single
agent-driven tool-calling loop: the MODEL chooses every evidence tool call
(``hivemind_search``, ``hivemind_get``, ``registry_lookup``) and decides when
the evidence answers the question (``finish``).  Deterministic Python never
auto-chooses a search or fetch — it only executes the agent's chosen calls,
records typed evidence, and enforces the phase allowlist + effort budgets.
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

The production loop is bounded only by its wall-clock deadline. The model is
shown an honest remaining-time estimate each turn; test callers may provide a
finite turn clamp.
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
from .contracts import (
    RECORD_TYPE_MALFORMED,
    RECORD_TYPE_NON_WORKFLOW,
    RECORD_TYPE_WORKFLOW,
)
from .hivemind_tools import (
    HIVE_MIND_GET_TOOL,
    HIVE_MIND_SEARCH_TOOL,
    serve_hivemind_record,
)
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

# ── I01 effort budgets (mirrors vibecomfy/executor/tool_specs.py) ────────────
# The research loop is bounded by wall clock, not arbitrary call quotas. A
# 450-second window gives adapt routes roughly half of the executor's
# 15-minute outer deadline while leaving enough time for implementation.
TOOL_PHASE_DEADLINE_SECONDS = 450.0

# Production is deadline-bounded. Tests may pass a finite clamp.
_MAX_TURNS: int | None = None
# The digest is built before the decision call. Reserve a typical model-turn
# latency so the model sees an honest amount of time available for tool work.
_DECISION_TURN_LATENCY_RESERVE_SECONDS = 30.0
_MAX_DIGEST_CHARS = 4_000
_MAX_JUDGMENT_CITATIONS = 8
_MAX_CONCLUSION_PREVIEW_CHARS = 240
_MAX_HIT_PREVIEW_CHARS = 140
# Fetched Hivemind records are synthesis-grade evidence: their content is
# previewed (bounded) so the agent can reason from the fetched body, not a
# title.  Search hits stay title-only leads.
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

# Batch 14: ResearchAttempt — the plan's attempt semantics, derived in Python
# from the research tool ledger (never model judgment).  The four states are
# ordered weakest → strongest:
#   never    — zero executed evidence tool calls (only the research_question
#              entry).
#   empty    — tool calls ran but produced zero artifacts/results.
#   thin     — artifacts exist but zero hivemind_get/registry_lookup citations
#              (search hits only).
#   grounded — at least one fetched citation (hivemind_get/registry result).
RESEARCH_ATTEMPT_NEVER = "never"
RESEARCH_ATTEMPT_EMPTY = "empty"
RESEARCH_ATTEMPT_THIN = "thin"
RESEARCH_ATTEMPT_GROUNDED = "grounded"
RESEARCH_ATTEMPTS: tuple[str, ...] = (
    RESEARCH_ATTEMPT_NEVER,
    RESEARCH_ATTEMPT_EMPTY,
    RESEARCH_ATTEMPT_THIN,
    RESEARCH_ATTEMPT_GROUNDED,
)

# Ledger decisions that denote evidence tool calls.  Refusals share the same
# decision strings, so executed calls are distinguished by their entry shape
# (see ``_entry_is_executed_tool_call``).
_RESEARCH_TOOL_DECISIONS: frozenset[str] = frozenset({
    DECISION_SEARCH,
    DECISION_GET,
    DECISION_REGISTRY,
})
# Executed-but-failed tool calls are recorded with a status-prefixed
# conclusion (``_status_ledger_entry`` in tool_specs.py: "timeout: ...",
# "no_results: ..."); refusals carry a free-form stage-authored message.
_EXECUTED_STATUS_TOKENS: frozenset[str] = frozenset({
    "no_results",
    "rate_limited",
    "timeout",
    "unavailable",
    "invalid_request",
    "projection_failed",
})


def _entry_is_executed_tool_call(entry: EvidenceLedgerEntry) -> bool:
    """True when a ledger entry records an EXECUTED evidence tool call.

    Refusals (budget exhausted / out-of-allowlist) are recorded under the
    same decision strings, so an executed call is identified by its shape:
    cited evidence ids, an empty uncertainty (OK call), or a
    status-prefixed conclusion (executed-but-failed call such as a timeout
    or a zero-hit search).
    """
    if entry.decision not in _RESEARCH_TOOL_DECISIONS:
        return False
    if entry.evidence_ids:
        return True
    if entry.uncertainty == "":
        return True
    token = entry.conclusion.split(" ", 1)[0].rstrip(":").casefold()
    return token in _EXECUTED_STATUS_TOKENS


def _is_fetched_citation(evidence_id: str) -> bool:
    """True when a cited evidence id denotes fetched (not search-hit) content.

    Fetched citations are the namespaced ``hivemind_get:<id>`` artifact ids
    recorded by the stage for every successful record fetch, and the
    registry's ``tool:registry_lookup-<class>`` evidence ids.  Search-hit ids
    (``hivemind:<table>:<id>``) are leads, not fetched content.
    """
    return str(evidence_id).startswith("hivemind_get:") or str(
        evidence_id
    ).startswith("tool:registry_lookup")


def derive_research_attempt(
    *,
    ledger: EvidenceLedger | None,
    artifacts: Mapping[str, EvidenceArtifact] | None = None,
) -> str:
    """Derive the typed ``ResearchAttempt`` from the research tool ledger.

    The attempt is a Python-side statement about what the research phase
    actually did — it is NEVER model judgment:

    * ``never`` — zero executed evidence tool calls (only the
      ``research_question`` entry).
    * ``empty`` — tool calls ran but produced zero artifacts/results.
    * ``thin`` — artifacts exist but zero ``hivemind_get``/``registry_lookup``
      citations (search hits only).
    * ``grounded`` — at least one fetched citation (a ``hivemind_get`` or
      registry result is cited by a ``synthesize`` ledger entry).

    ``artifacts`` is the research evidence-pack artifact map (the
    ``research_question`` marker artifact never counts as a result).
    """
    entries = tuple(ledger.entries) if isinstance(ledger, EvidenceLedger) else ()
    artifacts_map = dict(artifacts or {})
    tool_calls_made = sum(
        1 for entry in entries if _entry_is_executed_tool_call(entry)
    )
    if tool_calls_made == 0:
        return RESEARCH_ATTEMPT_NEVER
    result_artifacts = {
        evidence_id: artifact
        for evidence_id, artifact in artifacts_map.items()
        if evidence_id != _QUESTION_ARTIFACT_ID
    }
    if not result_artifacts:
        return RESEARCH_ATTEMPT_EMPTY
    cited = (
        evidence_id
        for entry in entries
        if entry.decision == DECISION_SYNTHESIZE
        for evidence_id in entry.evidence_ids
    )
    if any(_is_fetched_citation(evidence_id) for evidence_id in cited):
        return RESEARCH_ATTEMPT_GROUNDED
    return RESEARCH_ATTEMPT_THIN

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


def _served_record_preview(view: Any, body: Mapping[str, Any]) -> str:
    """Model-facing preview of a fetched Hivemind record (batch 13).

    The served record view is the ONLY model-facing content of a fetched
    record: the surface lens for workflow records, the typed content for
    non-workflow records, or the typed error for malformed records.  The raw
    source row stays in the evidence artifact body (the raw body) and never
    enters the digest — the fallback below (the row's own text fields) is
    reachable only when a record was recorded without a served view.
    """
    if isinstance(view, Mapping):
        record_type = str(view.get("record_type") or "")
        if record_type == RECORD_TYPE_WORKFLOW:
            return str(view.get("surface_lens") or "")
        if record_type == RECORD_TYPE_NON_WORKFLOW:
            content = str(view.get("content") or "")
            return f"[non_workflow] {content}" if content else "[non_workflow]"
        if record_type == RECORD_TYPE_MALFORMED:
            return f"[malformed_record] {str(view.get('error') or '')}"
    return str(body.get("body") or body.get("description") or body.get("content") or "")


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
    """Append a bounded corrective JSON nudge after a malformed decision."""
    prompt = _RESEARCH_DECISION_RETRY_PROMPT
    raw_preview = getattr(exc, "raw_response_preview", None)
    if isinstance(raw_preview, str) and raw_preview.strip():
        prompt += (
            "\n\nPrevious response preview, for correction only:\n"
            + raw_preview.strip()
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
    """Retry only typed malformed model JSON, never transport failures."""
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
    raise last_exc  # pragma: no cover


# ── model request construction ───────────────────────────────────────────────
# The agent decision request carries ONLY the question + the research-phase
# tool catalog + a compact evidence digest.  It must never contain the full
# research result object nor a workflow schema dump — the digest builder below
# is the only evidence channel into the prompt.


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
    """Translate classifier source tiers into concrete search filters."""
    source_line = ""
    for text_line in research_brief.splitlines():
        if text_line.strip().startswith("- Source preferences:"):
            source_line = text_line.strip()
            break
    if not source_line:
        return ""
    prefs = [
        part.strip().casefold()
        for part in source_line.split(":", 1)[1].split(",")
        if part.strip()
    ]
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
        'filters={"source_type": "<tier>"} — use '
        + " or ".join(hints)
        + "."
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
        "question. If you fetched records, cite at least one fetched record "
        "ID (hivemind_get:...) that you actually used; a finish that discards "
        "all fetched evidence is rejected as premature. The implement agent "
        "(or the user, on research routes) "
        "relies on this synthesis alone.\n"
        "- Never request or dump workflow JSON payloads.\n"
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


def build_evidence_digest(
    *,
    question: str,
    tool_calls: Sequence[Mapping[str, Any]],
    artifacts: Mapping[str, EvidenceArtifact],
    limit: int = _MAX_DIGEST_CHARS,
    searches_left: int | None = None,
    fetches_left: int | None = None,
    registry_left: int | None = None,
    turns_left: int | None = None,
    seconds_left: float | None = None,
) -> str:
    """Return a bounded, evidence-first digest for the next model turn.

    Fetched records are synthesis-grade evidence and are shown newest first.
    Search hits remain compact leads.  The deprecated counter arguments stay
    accepted for callers compiled against the older helper, but the research
    stage is deadline-bounded and displays only honest remaining time.
    """
    del searches_left, fetches_left, registry_left, turns_left
    lines: list[str] = []
    if seconds_left is not None:
        lines.append(f"Time left: ~{max(0, int(seconds_left))}s.")
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
        conclusion_line = (
            f"    {_bounded(conclusion, _MAX_CONCLUSION_PREVIEW_CHARS)}"
            if conclusion
            else ""
        )
        if tool.startswith(HIVE_MIND_GET_TOOL) and status == ToolStatus.OK.value:
            for evidence_id in ids:
                if evidence_id in seen_record_ids:
                    continue
                seen_record_ids.add(evidence_id)
                artifact = artifacts.get(evidence_id)
                if artifact is None:
                    continue
                body = (
                    artifact.body
                    if isinstance(artifact.body, Mapping)
                    else {"value": artifact.body}
                )
                title = _bounded(
                    body.get("title")
                    or body.get("name")
                    or body.get("evidence_id")
                    or evidence_id,
                    90,
                )
                preview = ""
                if str(artifact.kind or "") == "hivemind_record":
                    # Preserve the IR architecture: workflow records are
                    # previewed through their normalized surface lens, never
                    # by stringifying raw workflow payload JSON.
                    preview = _bounded(
                        _served_record_preview(body.get("_served_view"), body),
                        _MAX_RECORD_PREVIEW_CHARS,
                    )
                elif str(artifact.kind or "") != "hivemind_search_hit":
                    preview = _bounded(
                        str(body.get("description") or body.get("snippet") or ""),
                        _MAX_HIT_PREVIEW_CHARS,
                    )
                line = f"    [{evidence_id}] {title}"
                if preview:
                    line += f": {preview}"
                record_lines.append(line)
            status_lines.append(head)
            if conclusion_line:
                status_lines.append(conclusion_line)
        elif tool.startswith(HIVE_MIND_SEARCH_TOOL) and status == ToolStatus.OK.value:
            search_lines.append(head)
            if conclusion_line:
                search_lines.append(conclusion_line)
        else:
            status_lines.append(head)
            if conclusion_line:
                status_lines.append(conclusion_line)
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
    from vibecomfy.comfy_nodes.agent.provider import (  # noqa: PLC0415
        MalformedModelJSON,
        run_model_turn,
    )

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
    """Full trace of one agent-owned research run (question + decisions).

    ``attempt`` carries the batch-14 :data:`derive_research_attempt` typing
    (never/empty/thin/grounded) — a Python-side statement derived from the
    research tool ledger, never model judgment.
    """

    route: str
    question: str
    iterations: tuple[AgentResearchIteration, ...]
    final_verdict: str  # "enough" | "refine" | "failed" | "skipped"
    summary: str
    citations: tuple[str, ...]
    uncertainty: str
    status: str  # "ok" | "exhausted" | "failed" | "skipped"
    elapsed_seconds: float
    attempt: str = RESEARCH_ATTEMPT_NEVER
    executed_tool_calls: int = 0
    evidence_artifact_count: int = 0
    warnings: tuple[str, ...] = ()
    error: str | None = None

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
            "attempt": self.attempt,
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
    max_turns: int | None = _MAX_TURNS,
    cache_root: Any = None,
    research_brief: str = "",
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Run the C1 agent-owned tool-calling research loop.

    The AGENT chooses every tool call and decides when to finish; Python
    executes the chosen calls, records typed evidence, and enforces the
    research-phase allowlist plus the wall-clock ``deadline_seconds``.
    Calls and production decision turns are unbounded; ``max_turns`` is an
    optional deterministic test clamp.

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
    Each turn's digest shows honest remaining time so the agent can wind down
    to a finish. A tool call already chosen by a decision always executes;
    the deadline is checked before the next decision and after tool execution,
    so evidence from a slow in-flight turn is retained.

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
        # evidence tool call before finishing.  The turn budget still bounds
        # the loop if the agent keeps refusing to call a tool.
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
        while max_turns is None or turns_taken < int(max_turns):
            if now() > deadline:
                warnings.append("research stage phase deadline exceeded; stopped early")
                break

            decision_reserve = min(
                _DECISION_TURN_LATENCY_RESERVE_SECONDS,
                max(0.0, deadline - now()),
            )
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
                raw_cited: list[str] = []
                for evidence_id in (decision.get("evidence_ids") or ()):
                    if evidence_id in artifacts:
                        raw_cited.append(evidence_id)
                        continue
                    if str(evidence_id).startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
                        aliased = "hivemind_get:" + str(evidence_id).removeprefix(
                            _HIVEMIND_EVIDENCE_ID_PREFIX
                        )
                        if aliased in artifacts:
                            raw_cited.append(aliased)
                cited = tuple(dict.fromkeys(raw_cited))[:_MAX_JUDGMENT_CITATIONS]
                # P1-c: finish-with-zero-evidence prevention.  A finish that
                # cites no evidence AND was preceded by zero tool calls is a
                # malformed finish (nothing was researched).  Do not accept it
                # and do not auto-fail — feed the typed 'finish_premature'
                # back as a refinement turn so the agent calls at least one
                # evidence tool before finishing.  The research_question
                # artifact is never surfaced as citable in the digest, so it
                # does not count as evidence here.
                citable_citations = tuple(
                    citation for citation in cited if citation != _QUESTION_ARTIFACT_ID
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
                fetched_cited = any(
                    citation.startswith("hivemind_get:")
                    for citation in citable_citations
                )
                if fetched_requested_ids and not fetched_cited:
                    _finish_premature_turn(
                        conclusion=_clean_text(decision.get("conclusion")),
                        message=(
                            "finish_premature: you fetched records but cited none "
                            "of them. Cite the hivemind_get:... IDs visible in "
                            "the digest, including records you dismissed, so the "
                            "synthesis does not discard gathered evidence."
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
            skip_network = False
            if tool == "hivemind_search":
                result = tool_fn(tool, args)
            elif tool == "hivemind_get":
                requested_id = str(args.get("evidence_id") or "").strip()
                normalized_id = requested_id.removeprefix("hivemind_get:")
                cached_key = (
                    "hivemind_get:"
                    + normalized_id.removeprefix(_HIVEMIND_EVIDENCE_ID_PREFIX)
                )
                cached = artifacts.get(cached_key)
                if requested_id and normalized_id in fetched_requested_ids and cached:
                    cached_body = (
                        cached.body
                        if isinstance(cached.body, Mapping)
                        else {"body": cached.body}
                    )
                    result = ToolResult(
                        tool_name=HIVE_MIND_GET_TOOL,
                        status=ToolStatus.OK,
                        result={
                            "evidence_id": cached_key,
                            "source_type": "cached",
                            "row": cached_body,
                            "record_view": cached_body.get("_served_view"),
                        },
                        evidence_ids=(cached_key,),
                        diagnostics=(
                            ToolDiagnostic(
                                code="hivemind_get_cached",
                                message=(
                                    f"returned cached record {cached_key} "
                                    "(already fetched this turn)"
                                ),
                            ),
                        ),
                    )
                    skip_network = True
                else:
                    result = tool_fn(tool, args)
            elif tool == "registry_lookup":
                result = tool_fn(tool, args)
            else:  # pragma: no cover - guarded by the allowlist above
                _refusal_call(
                    tool, _bounded(str(args), 120), f"unknown research tool {tool!r}"
                )
                continue
            if not skip_network:
                # Count the actual call before projection: malformed evidence
                # must not turn an executed search into attempt=never.
                tool_calls_made += 1
            # Evidence projection is the registry's job: artifacts (full hit /
            # fetched-row bodies, correctly extracted from frozen results),
            # the compact ledger entry, and the current-turn digest all come
            # from ToolSpec.project.  The stage records the projected evidence
            # under its own decision identifiers and per-turn digest.
            try:
                tool_spec = TOOL_SPEC_BY_NAME[tool]
                artifacts_map, entry, _ = project_tool_evidence(
                    tool_spec,
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
                        normalized = requested_id.removeprefix("hivemind_get:")
                        fetched_requested_ids.add(normalized)
                    # Preserve the IR-everywhere named-door view alongside the
                    # raw retained artifact body.
                    served_view: Mapping[str, Any] | None = None
                    if result.status is ToolStatus.OK and isinstance(
                        result.result, Mapping
                    ):
                        candidate = result.result.get("record_view")
                        if isinstance(candidate, Mapping):
                            served_view = candidate
                    get_artifacts: list[EvidenceArtifact] = []
                    if get_evidence_id is not None:
                        for artifact in artifacts_map.values():
                            body = artifact.body
                            if isinstance(body, Mapping) and "_served_view" not in body:
                                view = served_view
                                if view is None:
                                    view = serve_hivemind_record(
                                        dict(body), evidence_id=get_evidence_id
                                    ).to_dict()
                                enriched = dict(body)
                                enriched["_served_view"] = view
                                body = enriched
                            get_artifacts.append(
                                EvidenceArtifact(
                                    evidence_id=get_evidence_id,
                                    kind=artifact.kind,
                                    body=body,
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
                        evidence_ids=(
                            (get_evidence_id,) if get_evidence_id is not None else ()
                        ),
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
            except (ValueError, TypeError) as exc:
                detail = " ".join(str(exc).split()) or type(exc).__name__
                _refusal_call(
                    tool,
                    _bounded(str(args), 120),
                    "projection_failed: tool evidence projection failed; the "
                    f"call executed but its evidence was not recorded: {detail}",
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
            error += f" | raw response preview: {_bounded(raw_preview, 500)}"
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
        attempt=derive_research_attempt(
            ledger=EvidenceLedger(entries=tuple(ledger_entries)),
            artifacts=artifacts,
        ),
        executed_tool_calls=tool_calls_made,
        evidence_artifact_count=sum(
            1 for evidence_id in artifacts if evidence_id != _QUESTION_ARTIFACT_ID
        ),
        warnings=tuple(warnings),
        error=error,
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
    "RESEARCH_ATTEMPT_EMPTY",
    "RESEARCH_ATTEMPT_GROUNDED",
    "RESEARCH_ATTEMPT_NEVER",
    "RESEARCH_ATTEMPT_THIN",
    "RESEARCH_ATTEMPTS",
    "TOOL_PHASE_DEADLINE_SECONDS",
    "build_agent_research_messages",
    "build_evidence_digest",
    "build_research_brief",
    "derive_research_attempt",
    "form_research_question",
    "parse_agent_research_decision",
    "run_agent_research_stage",
    "run_agent_research_turn",
]
