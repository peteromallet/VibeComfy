"""C1 agent-owned research stage — H01 shadow/dual-evaluation mode.

Runs the agent research loop (explicit question → ``hivemind_search`` /
``hivemind_get`` → synthesize → enough/refine) BESIDE the legacy
deterministic research phase for ``research`` / ``adapt`` routes, captures
BOTH evidence packs (F01 :class:`EvidencePack` for the agent stage, a derived
pack for the legacy result), and writes a dual report comparing evidence
coverage, citation validity, and lifecycle assertions.

Shadow contract (H01):
    * The shadow result NEVER alters route, graph, reply, or queue decisions.
      Legacy behavioral output stays authoritative until the C01 cutover; the
      caller (``core.run_executor``) only records the shadow and persists it
      through ``vibecomfy.agent.artifacts``.
    * The judgment model request contains ONLY the explicit question plus a
      compact, bounded digest of tool statuses, evidence IDs, and hit
      previews — never the full legacy ``ResearchResult`` and never a
      workflow/graph schema dump.
    * The stage never raises: every failure is captured as a typed shadow
      result with ``status="failed"`` so the executor pipeline is unaffected.

Budgets mirror I01 (3 searches / 6 fetches / 1 registry / ~90s); the
enforceable constants live in ``vibecomfy/porting/edit/_resolve.py`` — this
module keeps local copies to avoid pulling the Comfy-heavy agent-edit import
graph into the executor stage, and must be reconciled with them at D01
cleanup (the batch protocol enforces the same numbers).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
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

LOGGER = logging.getLogger(__name__)

# ── I01 effort budgets (mirrors vibecomfy/porting/edit/_resolve.py) ──────────
TOOL_SEARCH_BUDGET = 3
TOOL_FETCH_BUDGET = 6
TOOL_PHASE_DEADLINE_SECONDS = 90.0

# Stage tuning (not enforced elsewhere; keep bounded and deterministic).
_FETCHES_PER_ITERATION = 2
_SEARCH_LIMIT = 5
_MAX_ITERATIONS = TOOL_SEARCH_BUDGET
_MAX_DIGEST_CHARS = 4_000
_MAX_JUDGMENT_CITATIONS = 8
_MAX_CONCLUSION_PREVIEW_CHARS = 240
_MAX_HIT_PREVIEW_CHARS = 140

_SHADOW_SCHEMA_VERSION = 1
_QUESTION_ARTIFACT_ID = "research_question"
_LEGACY_SOURCE_PREFIX = "legacy_source"
_LEGACY_SUMMARY_ARTIFACT_ID = "legacy_summary"
_HIVEMIND_EVIDENCE_ID_PREFIX = "hivemind:"

# Ledger entry decisions (stable identifiers consumed by the dual report and
# the H01 tests).
DECISION_QUESTION = "research_question"
DECISION_SEARCH = "hivemind_search"
DECISION_GET = "hivemind_get"
DECISION_SYNTHESIZE = "synthesize"
DECISION_ENOUGH_REFINE = "enough_refine"
DECISION_LEGACY_COMPLETE = "legacy_research_complete"


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


# ── judgment parsing (fail-closed) ───────────────────────────────────────────


def parse_agent_research_judgment(raw: str) -> dict[str, Any]:
    """Parse the synthesize + enough/refine judgment JSON, fail-closed.

    Expected shape::

        {
          "conclusion": str,          # required, non-empty
          "evidence_ids": [str, ...], # cited ids, filtered to returned ids
          "uncertainty": str,
          "enough": bool,             # True → stop; False → refine
          "refine_question": str|null # next question when enough=False
        }

    Any malformed payload raises :class:`ValueError`; the stage converts that
    into a typed failure so the shadow never poisons the pipeline.
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


# ── model request construction (H01 acceptance 3) ────────────────────────────
# The judgment request carries ONLY the question + compact evidence digest.
# It must never contain the full legacy ResearchResult nor a workflow schema
# dump — the digest builder below is the only evidence channel into the prompt.


def build_agent_research_messages(
    *,
    question: str,
    evidence_digest: str,
    route: str,
) -> list[dict[str, str]]:
    """System + user messages for one synthesize/enough-refine judgment turn.

    ``evidence_digest`` is the compact, bounded ledger-only digest built by
    :func:`build_evidence_digest` — never raw tool bodies, never the legacy
    result, never the workflow graph.
    """
    system = (
        "You are the research stage of a ComfyUI workflow assistant. "
        "Resolve the specific open question(s) blocking the current request by "
        "synthesizing the evidence below.\n"
        "Rules:\n"
        "- Cite ONLY evidence IDs that were returned by the tools above; never "
        "invent IDs or quote sources that were not returned.\n"
        "- Record genuine uncertainty instead of guessing.\n"
        "- Decide enough: True when the evidence answers the question with "
        "acceptable certainty; False when a narrower or different question "
        "would materially improve the answer.\n"
        "- When enough is False, provide a concrete refine_question.\n"
        "Reply with one JSON object: "
        '{"conclusion": string, "evidence_ids": [string, ...], '
        '"uncertainty": string, "enough": bool, "refine_question": string|null}.'
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
    """Compact, bounded digest of one iteration's tool evidence for the prompt.

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
        digest = "(no tool evidence in this iteration)"
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
    """Run one synthesize/enough-refine judgment turn through the provider seam.

    Mirrors the executor's ``agent_backend`` pattern: builds the bounded
    messages, dispatches through ``provider.run_model_turn`` with
    ``response_contract="json"``, and parses the judgment fail-closed.
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
    return parse_agent_research_judgment(raw)


def _default_judge_fn(spec: Any) -> Callable[[str, str], dict[str, Any]]:
    """Bind the provider judgment turn to the resolved research profile spec."""

    def _judge(question: str, evidence_digest: str) -> dict[str, Any]:
        return run_agent_research_turn(
            question,
            evidence_digest,
            route=getattr(spec, "agent", "") or "",
            model=getattr(spec, "model", "") or "",
            effort=getattr(spec, "effort", None),
        )

    return _judge


# ── trace / shadow result contracts ──────────────────────────────────────────


@dataclass(frozen=True)
class AgentResearchIteration:
    """One question → tools → synthesize → enough/refine pass."""

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
    """Full trace of one agent-owned research run (question + judgments)."""

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


@dataclass(frozen=True)
class AgentResearchShadowResult:
    """Shadow/dual-evaluation result: both packs plus the dual report.

    Carried by the executor ONLY as inert evidence — it never feeds routing,
    graph construction, reply text, or queue decisions.
    """

    route: str
    trace: AgentResearchTrace
    agent_evidence_pack: EvidencePack
    dual_report: dict[str, Any]
    legacy_evidence_pack: EvidencePack | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SHADOW_SCHEMA_VERSION,
            "shadow_mode": True,
            "legacy_behavior_used": True,
            "route": self.route,
            "trace": self.trace.to_dict(),
            "dual_report": self.dual_report,
            "agent_evidence_pack": self.agent_evidence_pack.to_dict(),
            "legacy_evidence_pack": (
                self.legacy_evidence_pack.to_dict()
                if self.legacy_evidence_pack is not None
                else None
            ),
            "warnings": list(self.warnings),
        }


# ── the C1 loop ──────────────────────────────────────────────────────────────


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


def run_agent_research_stage(
    *,
    route: str,
    question: str,
    spec: Any | None = None,
    search_fn: Callable[..., ToolResult] | None = None,
    get_fn: Callable[..., ToolResult] | None = None,
    judge_fn: Callable[[str, str], dict[str, Any]] | None = None,
    now_fn: Callable[[], float] | None = None,
    deadline_seconds: float = TOOL_PHASE_DEADLINE_SECONDS,
    max_iterations: int = _MAX_ITERATIONS,
    fetches_per_iteration: int = _FETCHES_PER_ITERATION,
    search_limit: int = _SEARCH_LIMIT,
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Run the C1 agent-owned research loop and return ``(trace, evidence_pack)``.

    Loop per iteration: record the explicit question → ``hivemind_search`` →
    ``hivemind_get`` on promising hits → synthesize + enough/refine judgment
    (model turn) → refine the question or stop.  Budgets: ``max_iterations``
    searches, ``fetches_per_iteration`` fetches each pass (capped by the I01
    fetch budget), wall-clock ``deadline_seconds``.  Every tool result is
    recorded as a typed digest plus F01 ledger entries; hit/record bodies are
    captured as evidence artifacts behind their evidence IDs.

    ``search_fn`` / ``get_fn`` / ``judge_fn`` default to the module-level
    Wave-A tools / provider judgment turn, resolved at call time so tests and
    callers may inject fakes.  Never raises: failures are captured in the
    returned trace (``status="failed"``) and the evidence pack recorded so far.
    """
    now = now_fn or time.monotonic
    search_fn = search_fn or _default_hivemind_search
    get_fn = get_fn or _default_hivemind_get
    if judge_fn is None:
        judge_fn = _default_judge_fn(spec)
    started = now()
    deadline = started + max(0.0, float(deadline_seconds))

    artifacts: dict[str, EvidenceArtifact] = {}
    ledger_entries: list[EvidenceLedgerEntry] = []
    warnings: list[str] = []
    iterations: list[AgentResearchIteration] = []
    searches_left = TOOL_SEARCH_BUDGET
    fetches_left = TOOL_FETCH_BUDGET

    final_verdict = "refine"
    final_summary = ""
    final_uncertainty = ""
    final_citations: tuple[str, ...] = ()
    status = "ok"
    error: str | None = None

    def _add_artifact(artifact: EvidenceArtifact) -> None:
        # Keep-first on id collisions across iterations (deterministic).
        if artifact.evidence_id not in artifacts:
            artifacts[artifact.evidence_id] = artifact

    def _add_entry(entry: EvidenceLedgerEntry) -> None:
        ledger_entries.append(entry)

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

        current_question = question
        for iteration_index in range(1, int(max_iterations) + 1):
            if now() > deadline:
                warnings.append("research stage phase deadline exceeded; stopped early")
                final_verdict = "refine"
                break

            iteration_calls: list[dict[str, Any]] = []

            # 1. search (search budget enforced)
            if searches_left <= 0:
                warnings.append("research stage search budget exhausted")
                final_verdict = "refine"
                break
            searches_left -= 1
            search_result = search_fn(current_question, limit=search_limit)
            hit_ids = tuple(search_result.evidence_ids or ())
            hit_artifacts: list[EvidenceArtifact] = []
            for evidence_id in hit_ids:
                hit_body = _search_hit_artifact_body(search_result, evidence_id)
                artifact = EvidenceArtifact(
                    evidence_id=evidence_id,
                    kind="hivemind_search_hit",
                    body=hit_body,
                    source="hivemind",
                )
                _add_artifact(artifact)
                hit_artifacts.append(artifact)
            search_conclusion = _search_conclusion(search_result)
            _add_entry(
                EvidenceLedgerEntry(
                    decision=DECISION_SEARCH,
                    conclusion=search_conclusion,
                    evidence_ids=hit_ids,
                    uncertainty=(
                        "" if search_result.status is ToolStatus.OK else search_conclusion
                    ),
                )
            )
            iteration_calls.append(
                _tool_call_digest(
                    tool=HIVE_MIND_SEARCH_TOOL,
                    result=search_result,
                    query=current_question,
                    conclusion=search_conclusion,
                )
            )

            # 2. fetch promising hits (fetch budget enforced)
            for evidence_id in hit_ids[: max(0, int(fetches_per_iteration))]:
                if fetches_left <= 0:
                    warnings.append("research stage fetch budget exhausted")
                    break
                if now() > deadline:
                    warnings.append("research stage phase deadline exceeded during fetch")
                    break
                fetches_left -= 1
                get_result = get_fn(evidence_id)
                get_evidence_id = _get_record_evidence_id(get_result, evidence_id)
                get_body = get_result.result if isinstance(get_result.result, Mapping) else {}
                if get_evidence_id is not None:
                    _add_artifact(
                        EvidenceArtifact(
                            evidence_id=get_evidence_id,
                            kind="hivemind_record",
                            body=get_body,
                            source="hivemind",
                        )
                    )
                get_conclusion = _get_conclusion(get_result, get_body)
                _add_entry(
                    EvidenceLedgerEntry(
                        decision=DECISION_GET,
                        conclusion=get_conclusion,
                        evidence_ids=(get_evidence_id,) if get_evidence_id is not None else (),
                        uncertainty=(
                            "" if get_result.status is ToolStatus.OK else get_conclusion
                        ),
                    )
                )
                iteration_calls.append(
                    _tool_call_digest(
                        tool=HIVE_MIND_GET_TOOL,
                        result=get_result,
                        query=evidence_id,
                        conclusion=get_conclusion,
                    )
                )

            # 3. synthesize + enough/refine judgment (model turn)
            digest = build_evidence_digest(
                question=current_question,
                tool_calls=iteration_calls,
                artifacts=artifacts,
            )
            judgment = judge_fn(current_question, digest)
            cited = tuple(
                evidence_id
                for evidence_id in (judgment.get("evidence_ids") or ())
                if evidence_id in artifacts
            )[:_MAX_JUDGMENT_CITATIONS]
            conclusion = _clean_text(judgment.get("conclusion"))
            uncertainty = _clean_text(judgment.get("uncertainty"))
            enough = bool(judgment.get("enough"))
            refine_question = judgment.get("refine_question")

            _add_entry(
                EvidenceLedgerEntry(
                    decision=DECISION_SYNTHESIZE,
                    conclusion=conclusion or "synthesis produced no conclusion",
                    evidence_ids=cited,
                    uncertainty=uncertainty,
                )
            )
            refine_question_text = _clean_text(refine_question)
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
            verdict = "enough" if enough else "refine"
            iterations.append(
                AgentResearchIteration(
                    iteration=iteration_index,
                    question=current_question,
                    tool_calls=tuple(iteration_calls),
                    synthesis={
                        "conclusion": conclusion,
                        "evidence_ids": list(cited),
                        "uncertainty": uncertainty,
                        "enough": enough,
                        "refine_question": refine_question_text or None,
                    },
                    verdict=verdict,
                )
            )

            if enough:
                final_verdict = "enough"
                break
            if not refine_question_text:
                warnings.append("judgment returned refine without a new question; stopping")
                final_verdict = "refine"
                break
            current_question = refine_question_text
            final_verdict = "refine"
    except Exception as exc:  # noqa: BLE001 - shadow failures are typed, never raised
        status = "failed"
        final_verdict = "failed"
        error = f"{type(exc).__name__}: {exc}"
        LOGGER.warning("agent research stage failed (shadow): %s", error)

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


# ── legacy evidence capture + dual report ────────────────────────────────────


def derive_legacy_evidence_pack(legacy_result: Any) -> EvidencePack:
    """Capture the legacy ``ResearchResult`` as a comparable F01 evidence pack.

    Source rows become ``legacy_source:<i>`` artifacts with one ledger entry
    each; the summary/warnings/community paragraph live behind
    ``legacy_summary``.  This is the capture side of dual evaluation — the
    derived pack is persisted and compared, never injected into any model
    request.
    """
    artifacts: dict[str, EvidenceArtifact] = {}
    entries: list[EvidenceLedgerEntry] = []
    source_ids: list[str] = []

    sources = tuple(getattr(legacy_result, "sources", ()) or ())
    for index, source in enumerate(sources):
        evidence_id = f"{_LEGACY_SOURCE_PREFIX}:{index}"
        body = dict(source) if isinstance(source, Mapping) else {"value": source}
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="legacy_research_source",
            body=body,
            source="legacy_research",
        )
        source_ids.append(evidence_id)
        title = _clean_text(
            source.get("title") or source.get("description") or source.get("class_type")
        ) if isinstance(source, Mapping) else ""
        entries.append(
            EvidenceLedgerEntry(
                decision=f"{_LEGACY_SOURCE_PREFIX}:{index}",
                conclusion=_bounded(title or f"source {index}", _MAX_CONCLUSION_PREVIEW_CHARS),
                evidence_ids=(evidence_id,),
                uncertainty="",
            )
        )

    warnings = tuple(getattr(legacy_result, "warnings", ()) or ())
    artifacts[_LEGACY_SUMMARY_ARTIFACT_ID] = EvidenceArtifact(
        evidence_id=_LEGACY_SUMMARY_ARTIFACT_ID,
        kind="legacy_research_summary",
        body={
            "summary": _clean_text(getattr(legacy_result, "summary", "")),
            "community_summary": _clean_text(getattr(legacy_result, "community_summary", "")),
            "warnings": [str(item) for item in warnings],
            "source_count": len(sources),
        },
        source="legacy_research",
    )
    entries.append(
        EvidenceLedgerEntry(
            decision=DECISION_LEGACY_COMPLETE,
            conclusion=f"legacy research completed with {len(sources)} source(s)",
            evidence_ids=(_LEGACY_SUMMARY_ARTIFACT_ID, *source_ids),
            uncertainty="",
        )
    )
    return EvidencePack(artifacts=artifacts, ledger=EvidenceLedger(entries=entries))


def _legacy_hivemind_ids(legacy_result: Any) -> set[str]:
    """Hivemind evidence IDs directly referenced by the legacy result, if any.

    Legacy sources do not carry F01 evidence IDs; where a source exposes a
    ``hivemind:``-shaped id (hivemind_id / evidence_id / url), it is extracted
    so the dual report can compute a genuine overlap with the agent pack.
    """
    found: set[str] = set()
    for source in tuple(getattr(legacy_result, "sources", ()) or ()):
        if not isinstance(source, Mapping):
            continue
        for key in ("evidence_id", "hivemind_id"):
            value = source.get(key)
            if isinstance(value, str) and value.startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
                found.add(value)
        url = source.get("url")
        if isinstance(url, str) and _HIVEMIND_EVIDENCE_ID_PREFIX in url:
            candidate = url.split(_HIVEMIND_EVIDENCE_ID_PREFIX, 1)[1]
            if ":" in candidate:
                found.add(f"{_HIVEMIND_EVIDENCE_ID_PREFIX}{candidate.split('?')[0]}")
    return found


def _citation_validity(pack: EvidencePack | None) -> dict[str, Any]:
    """Count ledger citations that resolve to artifacts in the same pack."""
    if pack is None:
        return {"total": 0, "resolvable": 0, "unresolvable": []}
    available = set(pack.artifacts)
    unresolved: list[str] = []
    total = 0
    for entry in pack.ledger.entries:
        for evidence_id in entry.evidence_ids:
            total += 1
            if evidence_id not in available:
                unresolved.append(evidence_id)
    return {
        "total": total,
        "resolvable": total - len(unresolved),
        "unresolvable": sorted(set(unresolved)),
    }


def build_dual_report(
    *,
    route: str,
    trace: AgentResearchTrace,
    agent_pack: EvidencePack,
    legacy_pack: EvidencePack | None,
    legacy_result: Any,
) -> dict[str, Any]:
    """Compare legacy vs agent evidence: coverage, citations, lifecycle.

    Pure computation over the two packs + the trace; never mutates anything
    and never touches routing.  All comparisons are deterministic.
    """
    agent_ids = set(agent_pack.artifacts)
    legacy_hivemind_ids = _legacy_hivemind_ids(legacy_result)
    legacy_ids = set(legacy_pack.artifacts) if legacy_pack is not None else set()

    shared = sorted(agent_ids & legacy_hivemind_ids)
    agent_only = sorted(agent_ids - legacy_hivemind_ids)
    legacy_only = sorted(legacy_hivemind_ids - agent_ids)

    decisions = [entry.decision for entry in agent_pack.ledger.entries]
    tool_statuses: list[dict[str, Any]] = []
    searches = 0
    fetches = 0
    for iteration in trace.iterations:
        for call in iteration.tool_calls:
            tool = call.get("tool")
            if tool == HIVE_MIND_SEARCH_TOOL:
                searches += 1
            elif tool == HIVE_MIND_GET_TOOL:
                fetches += 1
            tool_statuses.append({"tool": tool, "status": call.get("status")})

    lifecycle = {
        "route": route,
        "status": trace.status,
        "final_verdict": trace.final_verdict,
        "iterations": len(trace.iterations),
        "searches": searches,
        "fetches": fetches,
        "question_recorded": DECISION_QUESTION in decisions,
        "synthesize_recorded": DECISION_SYNTHESIZE in decisions,
        "enough_refine_recorded": DECISION_ENOUGH_REFINE in decisions,
        "tool_statuses": tool_statuses,
        "legacy_behavior_used": True,
        "elapsed_seconds": round(trace.elapsed_seconds, 6),
    }

    return {
        "schema_version": _SHADOW_SCHEMA_VERSION,
        "route": route,
        "coverage": {
            "agent_evidence_ids": sorted(agent_ids),
            "legacy_evidence_ids": sorted(legacy_ids),
            "legacy_hivemind_references": sorted(legacy_hivemind_ids),
            "shared": shared,
            "agent_only": agent_only,
            "legacy_only": legacy_only,
            "agent_artifact_count": len(agent_ids),
            "legacy_artifact_count": len(legacy_ids),
        },
        "citation_validity": {
            "agent": _citation_validity(agent_pack),
            "legacy": _citation_validity(legacy_pack),
        },
        "lifecycle": lifecycle,
    }


def run_agent_research_shadow(
    request: Any,
    *,
    plan: Any | None = None,
    spec: Any | None = None,
    legacy_result: Any,
    search_fn: Callable[..., ToolResult] | None = None,
    get_fn: Callable[..., ToolResult] | None = None,
    judge_fn: Callable[[str, str], dict[str, Any]] | None = None,
    now_fn: Callable[[], float] | None = None,
    deadline_seconds: float = TOOL_PHASE_DEADLINE_SECONDS,
    max_iterations: int = _MAX_ITERATIONS,
) -> AgentResearchShadowResult:
    """Run the C1 stage beside a legacy result and build the dual evaluation.

    This is the H01 integration seam called from ``core.run_executor`` after
    the legacy research phase completes.  It never raises and its output is
    inert: the caller persists it for comparison and MUST NOT let it feed
    route/graph/reply/queue decisions (C01 cutover decides when legacy
    behavior is replaced).
    """
    route = str(getattr(plan, "effective_route", "") or "research")
    question, _source = form_research_question(request=request, plan=plan)
    warnings: list[str] = []
    try:
        legacy_pack = derive_legacy_evidence_pack(legacy_result)
        trace, agent_pack = run_agent_research_stage(
            route=route,
            question=question,
            spec=spec,
            search_fn=search_fn,
            get_fn=get_fn,
            judge_fn=judge_fn,
            now_fn=now_fn,
            deadline_seconds=deadline_seconds,
            max_iterations=max_iterations,
        )
        dual_report = build_dual_report(
            route=route,
            trace=trace,
            agent_pack=agent_pack,
            legacy_pack=legacy_pack,
            legacy_result=legacy_result,
        )
    except Exception as exc:  # noqa: BLE001 - shadow failures are never fatal
        LOGGER.warning("agent research shadow evaluation failed: %s", exc)
        trace = AgentResearchTrace(
            route=route,
            question=question,
            iterations=(),
            final_verdict="failed",
            summary="",
            citations=(),
            uncertainty="",
            status="failed",
            elapsed_seconds=0.0,
            warnings=(),
            error=f"{type(exc).__name__}: {exc}",
        )
        agent_pack = EvidencePack()
        legacy_pack = None
        dual_report = {
            "schema_version": _SHADOW_SCHEMA_VERSION,
            "route": route,
            "error": f"{type(exc).__name__}: {exc}",
        }
        warnings.append("agent research shadow evaluation failed")
    return AgentResearchShadowResult(
        route=route,
        trace=trace,
        agent_evidence_pack=agent_pack,
        legacy_evidence_pack=legacy_pack,
        dual_report=dual_report,
        warnings=tuple(warnings),
    )


__all__ = [
    "AgentResearchIteration",
    "AgentResearchShadowResult",
    "AgentResearchTrace",
    "DECISION_ENOUGH_REFINE",
    "DECISION_GET",
    "DECISION_QUESTION",
    "DECISION_SEARCH",
    "DECISION_SYNTHESIZE",
    "TOOL_FETCH_BUDGET",
    "TOOL_PHASE_DEADLINE_SECONDS",
    "TOOL_SEARCH_BUDGET",
    "build_agent_research_messages",
    "build_dual_report",
    "build_evidence_digest",
    "derive_legacy_evidence_pack",
    "form_research_question",
    "parse_agent_research_judgment",
    "run_agent_research_shadow",
    "run_agent_research_stage",
    "run_agent_research_turn",
]
