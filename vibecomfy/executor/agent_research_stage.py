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
      with ``status="failed"`` so the executor pipeline is unaffected.

Budgets mirror I01 (3 searches / 6 fetches / 1 registry / ~90s); the
enforceable constants live in ``vibecomfy/executor/tool_specs.py`` — this
module keeps local copies to avoid pulling the Comfy-heavy agent-edit import
graph into the executor stage, and must be reconciled with them at D01
cleanup (the batch protocol enforces the same numbers).
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
from .hivemind_tools import (
    HIVE_MIND_GET_TOOL,
    HIVE_MIND_SEARCH_TOOL,
    hivemind_get as _default_hivemind_get,
    hivemind_search as _default_hivemind_search,
)
from .tool_contracts import ToolResult, ToolStatus
from .tool_specs import (
    PHASE_RESEARCH,
    RESEARCH_PHASE_TOOLS,
    tool_catalog_docs,
)

LOGGER = logging.getLogger(__name__)

# ── I01 effort budgets (mirrors vibecomfy/executor/tool_specs.py) ────────────
TOOL_SEARCH_BUDGET = 3
TOOL_FETCH_BUDGET = 6
TOOL_REGISTRY_BUDGET = 1
TOOL_PHASE_DEADLINE_SECONDS = 90.0

# Stage tuning (not enforced elsewhere; keep bounded and deterministic).
_SEARCH_LIMIT = 5
_MAX_TURNS = TOOL_SEARCH_BUDGET + TOOL_FETCH_BUDGET + TOOL_REGISTRY_BUDGET + 2
_MAX_DIGEST_CHARS = 4_000
_MAX_JUDGMENT_CITATIONS = 8
_MAX_CONCLUSION_PREVIEW_CHARS = 240
_MAX_HIT_PREVIEW_CHARS = 140

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


def parse_agent_research_judgment(raw: str) -> dict[str, Any]:
    """Parse a legacy synthesize + enough/refine judgment JSON, fail-closed.

    Retained for compatibility with the historical judgment contract; the
    active seam is :func:`parse_agent_research_decision`, which normalizes
    this shape into a finish decision.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("agent research judgment: empty response")
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent research judgment: malformed JSON: {exc}") from None
    if not isinstance(parsed, Mapping):
        raise ValueError("agent research judgment: expected a JSON object")

    conclusion = _clean_text(parsed.get("conclusion"))
    if not conclusion:
        raise ValueError("agent research judgment: missing conclusion")

    raw_ids = parsed.get("evidence_ids")
    if raw_ids is None:
        raw_ids = []
    if not isinstance(raw_ids, (list, tuple)):
        raise ValueError("agent research judgment: evidence_ids must be a list")
    evidence_ids: list[str] = []
    for item in raw_ids:
        if isinstance(item, str) and item.strip():
            evidence_ids.append(item.strip())

    uncertainty_raw = parsed.get("uncertainty")
    uncertainty = _clean_text(uncertainty_raw) if uncertainty_raw is not None else ""

    enough_raw = parsed.get("enough")
    if isinstance(enough_raw, bool):
        enough = enough_raw
    elif isinstance(enough_raw, str) and enough_raw.strip().casefold() in {"1", "true", "yes"}:
        enough = True
    else:
        enough = False

    refine_raw = parsed.get("refine_question")
    refine_question: str | None = None
    if refine_raw is not None:
        if not isinstance(refine_raw, str):
            raise ValueError("agent research judgment: refine_question must be a string or null")
        cleaned = _clean_text(refine_raw)
        refine_question = cleaned or None

    return {
        "conclusion": conclusion,
        "evidence_ids": evidence_ids,
        "uncertainty": uncertainty,
        "enough": enough,
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


def build_agent_research_messages(
    *,
    question: str,
    evidence_digest: str,
    route: str,
) -> list[dict[str, str]]:
    """System + user messages for one agent research decision turn.

    ``evidence_digest`` is the compact, bounded ledger-only digest built by
    :func:`build_evidence_digest` — never raw tool bodies, never the legacy
    result, never the workflow graph.  The system prompt documents the
    research-phase tool catalog and the call/finish action contract; the
    agent chooses every tool call.
    """
    catalog = tool_catalog_docs(PHASE_RESEARCH)
    system = (
        "You are the research stage of a ComfyUI workflow assistant. "
        "Resolve the specific open question(s) blocking the current request "
        "by choosing and calling evidence tools yourself; then finish when the "
        "evidence answers the question.\n"
        f"Available tools (research phase only):\n{catalog}\n"
        "Rules:\n"
        "- Call a tool to gather evidence; the tool result will be returned in "
        "the next digest. Choose the query and the tool yourself.\n"
        "- Cite ONLY evidence IDs that were returned by the tools; never "
        "invent IDs or quote sources that were not returned.\n"
        "- Record genuine uncertainty instead of guessing.\n"
        "- Finish when the evidence answers the question with acceptable "
        "certainty; do not over-search.\n"
        "- Effort budgets: 3 searches, 6 fetches, 1 registry lookup, ~90s.\n"
        "Reply with exactly one JSON object per turn:\n"
        '{"action": "call", "tool": "<name>", "args": {<tool arguments>}} — '
        "gather more evidence, or\n"
        '{"action": "finish", "conclusion": string, "evidence_ids": [string, ...], '
        '"uncertainty": string} — the evidence answers the question.'
    )
    user_lines = [
        f"Research question: {question}",
        f"Route: {route}",
        "Evidence digest (tool statuses, evidence IDs, and previews only):",
        evidence_digest,
    ]
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
) -> str:
    """Compact, bounded digest of the tool evidence gathered so far.

    Each tool call contributes one line (name, status, query, evidence IDs,
    bounded conclusion) plus bounded previews of its cited artifacts.  Raw
    bodies never enter the digest; the total is truncated at ``limit``.
    """
    lines: list[str] = []
    for call in tool_calls:
        tool = str(call.get("tool") or "")
        status = str(call.get("status") or "")
        query = _bounded(call.get("query", ""), 120)
        ids = [str(item) for item in (call.get("evidence_ids") or ())]
        head = f"- {tool} → {status}"
        if query:
            head += f" ({query})"
        if ids:
            head += f" ids={ids}"
        lines.append(head)
        conclusion = _clean_text(call.get("conclusion"))
        if conclusion:
            lines.append(f"    {_bounded(conclusion, _MAX_CONCLUSION_PREVIEW_CHARS)}")
        for evidence_id in ids:
            artifact = artifacts.get(evidence_id)
            if artifact is None:
                continue
            body = artifact.body if isinstance(artifact.body, Mapping) else {"value": artifact.body}
            title = _bounded(body.get("title") or body.get("name") or body.get("evidence_id") or evidence_id, 90)
            preview = _bounded(
                str(body.get("body") or body.get("description") or body.get("snippet") or ""),
                _MAX_HIT_PREVIEW_CHARS,
            )
            line = f"    [{evidence_id}] {title}"
            if preview:
                line += f": {preview}"
            lines.append(line)
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
        )
    from vibecomfy.comfy_nodes.agent.provider import run_model_turn  # noqa: PLC0415

    result = run_model_turn(
        question,
        messages,
        route=route,
        model=model,
        effort=effort,
        response_contract="json",
        profiling_context={"backend_phase": "research_stage"},
    )
    raw = _extract_content(result)
    return parse_agent_research_decision(raw)


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
    status: str  # "ok" | "failed" | "skipped"
    elapsed_seconds: float
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
) -> dict[str, Any]:
    return {
        "tool": tool,
        "status": result.status.value,
        "query": query,
        "evidence_ids": list(result.evidence_ids),
        "conclusion": conclusion,
    }


def _search_hit_artifact_body(result: ToolResult, evidence_id: str) -> dict[str, Any]:
    """Extract the matching hit dict from a search ToolResult body."""
    body = result.result if isinstance(result.result, Mapping) else {}
    hits = body.get("hits") if isinstance(body.get("hits"), list) else []
    for hit in hits:
        if isinstance(hit, Mapping) and hit.get("evidence_id") == evidence_id:
            return dict(hit)
    return {"evidence_id": evidence_id}


def _search_conclusion(result: ToolResult) -> str:
    body = result.result if isinstance(result.result, Mapping) else {}
    count = body.get("count")
    if result.status is ToolStatus.OK and isinstance(count, int):
        return f"{count} hit(s)"
    if result.status is ToolStatus.NO_RESULTS:
        return "no results"
    return f"status={result.status.value}"


def _get_record_evidence_id(result: ToolResult, requested_id: str) -> str | None:
    """Evidence ID for a fetched record — namespaced so search-hit ids never collide."""
    if result.status is not ToolStatus.OK:
        return None
    if not requested_id.startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
        return None
    return f"hivemind_get:{requested_id.removeprefix(_HIVEMIND_EVIDENCE_ID_PREFIX)}"


def _get_conclusion(result: ToolResult, body: Mapping[str, Any]) -> str:
    if result.status is not ToolStatus.OK:
        return f"status={result.status.value}"
    row = body.get("row") if isinstance(body.get("row"), Mapping) else {}
    title = row.get("title") or row.get("name") or row.get("class_type") or body.get("evidence_id")
    return _bounded(str(title or "record fetched"), _MAX_CONCLUSION_PREVIEW_CHARS)


def _registry_conclusion(result: ToolResult, body: Mapping[str, Any]) -> str:
    if result.status is not ToolStatus.OK:
        return f"status={result.status.value}"
    node_class = str(body.get("node_class") or "class")
    candidates = [c for c in (body.get("candidates") or ()) if isinstance(c, Mapping)]
    pack_names = "; ".join(
        str(c.get("ref", {}).get("slug") or c.get("ref", {}).get("name") or "pack")
        for c in candidates
    )
    return (
        f"{node_class}: exact ownership {bool(body.get('exact_ownership'))}"
        + (f"; candidates: {pack_names}" if pack_names else "")
    )


def _registry_artifact(args: Mapping[str, Any], result: ToolResult) -> EvidenceArtifact:
    body = result.result if isinstance(result.result, Mapping) else {}
    node_class = str(body.get("node_class") or args.get("node_class") or "class")
    return EvidenceArtifact(
        evidence_id=f"tool:registry-lookup-{node_class}",
        kind="registry_resolution",
        body=dict(body),
        source="comfy-registry",
    )


def _default_tool_fn(
    tool: str,
    args: Mapping[str, Any],
    *,
    search_fn: Callable[..., ToolResult],
    get_fn: Callable[..., ToolResult],
    search_limit: int,
    cache_root: Any = None,
) -> ToolResult:
    """Execute one agent-chosen research tool call.

    The AGENT chooses the tool and arguments; Python only executes.  The
    allowlist was already enforced by the loop before dispatch.
    """
    if tool == "hivemind_search":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return _typed_invalid_tool_result(
                HIVE_MIND_SEARCH_TOOL, "hivemind_search requires a non-empty query"
            )
        return search_fn(query, limit=int(args.get("limit", search_limit)), cache_root=cache_root)
    if tool == "hivemind_get":
        evidence_id = args.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            return _typed_invalid_tool_result(
                HIVE_MIND_GET_TOOL, "hivemind_get requires a non-empty evidence_id"
            )
        return get_fn(evidence_id, cache_root=cache_root)
    if tool == "registry_lookup":
        node_class = args.get("node_class")
        if not isinstance(node_class, str) or not node_class.strip():
            return _typed_invalid_tool_result(
                "registry_lookup", "registry_lookup requires a non-empty node_class"
            )
        from vibecomfy.executor.lookup_tools import registry_lookup  # noqa: PLC0415

        return registry_lookup(node_class)
    raise ValueError(f"Unknown research tool {tool!r}.")


def _typed_invalid_tool_result(tool: str, message: str) -> ToolResult:
    from .tool_contracts import ToolDiagnostic  # noqa: PLC0415

    return ToolResult(
        tool_name=tool,
        status=ToolStatus.INVALID_REQUEST,
        result={},
        diagnostics=(ToolDiagnostic(code="tool_call_invalid", message=message),),
    )


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
    search_limit: int = _SEARCH_LIMIT,
    cache_root: Any = None,
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Run the C1 agent-owned tool-calling research loop.

    The AGENT chooses every tool call and decides when to finish; Python
    executes the chosen calls, records typed evidence, and enforces the
    research-phase allowlist plus I01 budgets (3 searches / 6 fetches /
    1 registry lookup / wall-clock ``deadline_seconds`` / ``max_turns``).

    Per turn the agent returns one decision (via ``judge_fn``):
    ``{"action": "call", "tool", "args"}`` to gather more evidence or
    ``{"action": "finish", "conclusion", "evidence_ids", "uncertainty"}`` to
    stop.  A tool call outside the allowlist or a budget-exhausted call is a
    typed refusal recorded in the ledger; the agent sees it in the next
    digest and may finish or refine.

    ``search_fn`` / ``get_fn`` / ``tool_fn`` / ``judge_fn`` default to the
    module-level tool implementations / provider decision turn, resolved at
    call time so tests and callers may inject fakes.  Never raises: failures
    are captured in the returned trace (``status="failed"``) and the evidence
    pack recorded so far.
    """
    now = now_fn or time.monotonic
    search_fn = search_fn or _default_hivemind_search
    get_fn = get_fn or _default_hivemind_get
    if tool_fn is None:
        tool_fn = lambda tool, args, **kwargs: _default_tool_fn(  # noqa: E731
            tool, args, search_fn=search_fn, get_fn=get_fn, search_limit=search_limit, cache_root=cache_root
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
    searches_left = TOOL_SEARCH_BUDGET
    fetches_left = TOOL_FETCH_BUDGET
    registry_left = TOOL_REGISTRY_BUDGET

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
        while turns_taken < int(max_turns):
            if now() > deadline:
                warnings.append("research stage phase deadline exceeded; stopped early")
                break

            digest = build_evidence_digest(
                question=current_question,
                tool_calls=tool_call_digests,
                artifacts=artifacts,
            )
            decision = judge_fn(current_question, digest, None)
            turns_taken += 1

            action = str(decision.get("action") or "finish")
            if action == "finish":
                cited = tuple(
                    evidence_id
                    for evidence_id in (decision.get("evidence_ids") or ())
                    if evidence_id in artifacts
                )[:_MAX_JUDGMENT_CITATIONS]
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
            if tool == "hivemind_search":
                if searches_left <= 0:
                    _refusal_call(tool, _bounded(str(args), 120), "search budget exhausted")
                    continue
                searches_left -= 1
            elif tool == "hivemind_get":
                if fetches_left <= 0:
                    _refusal_call(tool, _bounded(str(args), 120), "fetch budget exhausted")
                    continue
                fetches_left -= 1
            elif tool == "registry_lookup":
                if registry_left <= 0:
                    _refusal_call(tool, _bounded(str(args), 120), "registry budget exhausted")
                    continue
                registry_left -= 1

            result = tool_fn(tool, args)
            if tool == "hivemind_search":
                hit_ids = tuple(result.evidence_ids or ())
                hit_artifacts: list[EvidenceArtifact] = []
                for evidence_id in hit_ids:
                    hit_body = _search_hit_artifact_body(result, evidence_id)
                    hit_artifacts.append(
                        EvidenceArtifact(
                            evidence_id=evidence_id,
                            kind="hivemind_search_hit",
                            body=hit_body,
                            source="hivemind",
                        )
                    )
                _record_call(
                    tool=HIVE_MIND_SEARCH_TOOL,
                    result=result,
                    query=str(args.get("query") or current_question),
                    decision=DECISION_SEARCH,
                    conclusion=_search_conclusion(result),
                    artifacts_to_add=hit_artifacts,
                    evidence_ids=hit_ids,
                )
            elif tool == "hivemind_get":
                requested_id = str(args.get("evidence_id") or "")
                get_evidence_id = _get_record_evidence_id(result, requested_id)
                get_body = result.result if isinstance(result.result, Mapping) else {}
                get_artifacts: list[EvidenceArtifact] = []
                if get_evidence_id is not None:
                    get_artifacts.append(
                        EvidenceArtifact(
                            evidence_id=get_evidence_id,
                            kind="hivemind_record",
                            body=get_body,
                            source="hivemind",
                        )
                    )
                _record_call(
                    tool=HIVE_MIND_GET_TOOL,
                    result=result,
                    query=requested_id,
                    decision=DECISION_GET,
                    conclusion=_get_conclusion(result, get_body),
                    artifacts_to_add=get_artifacts,
                    evidence_ids=(get_evidence_id,) if get_evidence_id is not None else (),
                )
            elif tool == "registry_lookup":
                registry_body = result.result if isinstance(result.result, Mapping) else {}
                registry_artifact = _registry_artifact(args, result)
                _record_call(
                    tool="registry_lookup",
                    result=result,
                    query=str(args.get("node_class") or ""),
                    decision=DECISION_REGISTRY,
                    conclusion=_registry_conclusion(result, registry_body),
                    artifacts_to_add=(registry_artifact,),
                    evidence_ids=(registry_artifact.evidence_id,),
                )
            else:  # pragma: no cover - allowlist check above already rejects
                _refusal_call(tool, _bounded(str(args), 120), f"unknown research tool {tool!r}")
    except Exception as exc:  # noqa: BLE001 - research failures are typed, never raised
        status = "failed"
        final_verdict = "failed"
        error = f"{type(exc).__name__}: {exc}"
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
    )
    pack = EvidencePack(artifacts=artifacts, ledger=EvidenceLedger(entries=ledger_entries))
    return trace, pack


__all__ = [
    "AgentResearchIteration",
    "AgentResearchTrace",
    "DECISION_ENOUGH_REFINE",
    "DECISION_GET",
    "DECISION_QUESTION",
    "DECISION_REGISTRY",
    "DECISION_SEARCH",
    "DECISION_SYNTHESIZE",
    "RESEARCH_ALLOWED_TOOLS",
    "TOOL_FETCH_BUDGET",
    "TOOL_PHASE_DEADLINE_SECONDS",
    "TOOL_SEARCH_BUDGET",
    "build_agent_research_messages",
    "build_evidence_digest",
    "form_research_question",
    "parse_agent_research_decision",
    "parse_agent_research_judgment",
    "run_agent_research_stage",
    "run_agent_research_turn",
]
