"""C1 agent-owned research stage — one genuine tool-calling agent phase.

Runs the research phase for ``research`` / ``adapt`` routes as a single
agent-driven tool-calling loop: the MODEL chooses every evidence tool call
(``hivemind_search``, ``hivemind_get``, ``registry_lookup``) and decides when
the evidence answers the question (``finish``).  Deterministic Python never
auto-chooses a search or fetch — it only executes the agent's chosen calls,
records typed evidence, and enforces the phase allowlist, deterministic
decision/tool-call limits, and the wall-clock deadline.
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

The production loop has deterministic turn/call bounds and a consecutive
Hivemind-timeout circuit breaker. The 450-second wall deadline remains a
backstop for slow in-flight provider/tool calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os as _os
import re
import time
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from .evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
    MAX_LEDGER_PROMPT_ENTRIES,
    MAX_LEDGER_CONCLUSION_CHARS,
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
from .hivemind_clients import _first_text, _workflow_semantics
from .tool_contracts import (
    RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS,
    ToolDiagnostic,
    ToolResult,
    ToolStatus,
)
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
# Eight decision turns cover the normal search -> fetch -> synthesize shape
# with room for refinement. Twelve evidence calls is an independent safety
# ceiling for future multi-call decisions. Today one decision carries one
# call, so the turn ceiling normally wins. Three consecutive timeout-shaped
# Hivemind results open the circuit before repeated 5-second failures amplify.
MAX_RESEARCH_DECISION_TURNS = 8
MAX_RESEARCH_TOOL_CALLS = 12
HIVEMIND_TIMEOUT_CIRCUIT_THRESHOLD = 3

# The wall-clock window is a backstop for slow in-flight work, not the
# production loop's primary termination mechanism. The default is the ONE
# shared research-phase budget (T4.2): the batch-REPL research route reads
# the same constant, so both carriers agree on VIBECOMFY_RESEARCH_PHASE_DEADLINE.
TOOL_PHASE_DEADLINE_SECONDS = RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS

# S4: research checkpoint across 480s kill (5b31ce). The 480s turn budget can
# kill the research worker mid-loop after several expensive hivemind_search/
# hivemind_get calls. Persist the ledger+artifacts after each tool call so
# attempt-2 resumes instead of redoing work. Nothing deterministic in
# deliberation — the checkpoint only replays what the agent already fetched;
# the agent still judges relevance on the next attempt.
_RESEARCH_CHECKPOINT_ENV = "VIBECOMFY_RESEARCH_CHECKPOINT_DIR"
_RESEARCH_CHECKPOINT_TTL_SECONDS = float(_os.getenv("VIBECOMFY_RESEARCH_CHECKPOINT_TTL", "3600"))

def _research_checkpoint_dir() -> _Path | None:
    raw = _os.getenv(_RESEARCH_CHECKPOINT_ENV, "").strip()
    if not raw:
        return None
    try:
        p = _Path(raw)
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        return None

def _checkpoint_identity(
    *,
    request_identity: str | Mapping[str, Any] | None,
    route: str | None,
    baseline_identity: str | Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str] | None:
    """Build the authority tuple for one research checkpoint.

    A session is only a storage namespace.  It is deliberately absent from
    this authority tuple so a session id cannot authorize replay across
    requests, routes, or baselines.
    """
    if request_identity is None or baseline_identity is None or not route:
        return None
    identity = {
        "request": request_identity,
        "route": str(route),
        "baseline": baseline_identity,
    }
    try:
        encoded = json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return identity, hashlib.sha256(encoded).hexdigest()


def _research_checkpoint_path(
    session_id: str | None,
    *,
    request_identity: str | Mapping[str, Any] | None = None,
    route: str | None = None,
    baseline_identity: str | Mapping[str, Any] | None = None,
) -> _Path | None:
    base = _research_checkpoint_dir()
    if base is None or not session_id:
        return None
    checkpoint_identity = _checkpoint_identity(
        request_identity=request_identity,
        route=route,
        baseline_identity=baseline_identity,
    )
    if checkpoint_identity is None:
        return None
    _, identity_digest = checkpoint_identity
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(session_id))
    return base / f"research_ckpt_{safe}_{identity_digest}.json"

def _save_research_checkpoint(
    session_id: str | None,
    *,
    request_identity: str | Mapping[str, Any] | None = None,
    route: str | None = None,
    baseline_identity: str | Mapping[str, Any] | None = None,
    ledger_entries,
    artifacts,
) -> None:
    path = _research_checkpoint_path(
        session_id,
        request_identity=request_identity,
        route=route,
        baseline_identity=baseline_identity,
    )
    if path is None:
        return
    tmp: _Path | None = None
    try:
        identity = _checkpoint_identity(
            request_identity=request_identity,
            route=route,
            baseline_identity=baseline_identity,
        )
        if identity is None:
            return
        identity_payload, identity_digest = identity
        payload = {
            "identity": identity_payload,
            "identity_digest": identity_digest,
            "ledger": [e.to_dict() for e in ledger_entries],
            "artifacts": {k: v.to_dict() for k, v in artifacts.items()},
            "timestamp": time.time(),
        }
        # Each writer publishes through its own temp name.  The identity hash
        # gives different requests distinct durable targets; unique temp names
        # also prevent a concurrent writer from clobbering publication itself.
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        LOGGER.debug("research checkpoint save failed: %s", exc)
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

def _load_research_checkpoint(
    session_id: str | None,
    *,
    request_identity: str | Mapping[str, Any] | None = None,
    route: str | None = None,
    baseline_identity: str | Mapping[str, Any] | None = None,
):
    path = _research_checkpoint_path(
        session_id,
        request_identity=request_identity,
        route=route,
        baseline_identity=baseline_identity,
    )
    if path is None or not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime > _RESEARCH_CHECKPOINT_TTL_SECONDS:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        expected_identity = _checkpoint_identity(
            request_identity=request_identity,
            route=route,
            baseline_identity=baseline_identity,
        )
        if expected_identity is None or data.get("identity") != expected_identity[0]:
            return None
        if data.get("identity_digest") != expected_identity[1]:
            return None
        from vibecomfy.executor.evidence_pack import EvidenceArtifact, EvidenceLedgerEntry
        entries = [EvidenceLedgerEntry.from_dict(e) for e in (data.get("ledger") or [])]
        arts = {k: EvidenceArtifact.from_dict(v) for k, v in (data.get("artifacts") or {}).items()}
        return entries, arts
    except Exception as exc:
        LOGGER.debug("research checkpoint load failed: %s", exc)
        return None

def _clear_research_checkpoint(
    session_id: str | None,
    *,
    request_identity: str | Mapping[str, Any] | None = None,
    route: str | None = None,
    baseline_identity: str | Mapping[str, Any] | None = None,
):
    path = _research_checkpoint_path(
        session_id,
        request_identity=request_identity,
        route=route,
        baseline_identity=baseline_identity,
    )
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass

_MAX_TURNS = MAX_RESEARCH_DECISION_TURNS
# The digest is built before the decision call. Reserve a typical model-turn
# latency so the model sees an honest amount of time available for tool work.
_DECISION_TURN_LATENCY_RESERVE_SECONDS = 30.0
_MAX_DIGEST_CHARS = 4_000
_MAX_DIGEST_ENTRIES = MAX_LEDGER_PROMPT_ENTRIES
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
DECISION_TOOL_LIMIT_EXHAUSTED = "research_tool_limit_exhausted"
DECISION_HIVEMIND_CIRCUIT_OPEN = "hivemind_timeout_circuit_open"

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

_HIVEMIND_TIMEOUT_DIAGNOSTIC_CODES: frozenset[str] = frozenset({
    "hivemind_timeout",
    "hivemind_statement_timeout",
})


def _is_hivemind_timeout_result(tool: str, result: ToolResult) -> bool:
    """Return whether one Hivemind call ended in a timeout-shaped state.

    Persistent Postgres 57014 responses are intentionally surfaced by the
    client as ``unavailable`` after its one degraded query, so the diagnostic
    code participates alongside the ordinary typed ``timeout`` status.
    """
    if tool not in {HIVE_MIND_SEARCH_TOOL, HIVE_MIND_GET_TOOL}:
        return False
    if result.status is ToolStatus.TIMEOUT:
        return True
    return any(
        diagnostic.code in _HIVEMIND_TIMEOUT_DIAGNOSTIC_CODES
        for diagnostic in result.diagnostics
    )


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


_EGRESS_SECRET_RE = re.compile(
    r"(?i)\b(api[_ -]?key|token|password|secret|credential)\b\s*[:=]\s*[^\s,;]+"
)
_RESEARCH_ARG_LIMITS = {
    "query": 512,
    "evidence_id": 512,
    "node_class": 256,
    "timeout": 30.0,
}


def _safe_research_args(tool: str, args: Mapping[str, Any]) -> dict[str, Any]:
    """Bound and redact model-controlled egress before any tool call."""
    allowed = {
        "hivemind_search": {"query", "filters", "cursor", "limit", "timeout"},
        "hivemind_get": {"evidence_id", "timeout"},
        "registry_lookup": {"node_class"},
    }.get(tool, set())
    safe: dict[str, Any] = {}
    for key, value in args.items():
        if key not in allowed or key.casefold() in {"body", "graph", "workflow", "secret"}:
            continue
        if key in {"query", "evidence_id", "node_class"}:
            if not isinstance(value, str):
                continue
            text = _EGRESS_SECRET_RE.sub(r"\1=<redacted>", value.strip())
            safe[key] = text[:_RESEARCH_ARG_LIMITS[key]]
        elif key == "timeout":
            try:
                safe[key] = min(float(value), _RESEARCH_ARG_LIMITS[key])
            except (TypeError, ValueError):
                continue
        elif key == "limit":
            try:
                safe[key] = max(1, min(int(value), 20))
            except (TypeError, ValueError):
                continue
        elif key == "cursor":
            if isinstance(value, str):
                safe[key] = value[:512]
        elif key == "filters" and isinstance(value, Mapping):
            safe["filters"] = {
                str(filter_key): _EGRESS_SECRET_RE.sub(
                    r"\1=<redacted>", str(filter_value)
                )[:256]
                for filter_key, filter_value in value.items()
                if str(filter_key) in {"source_type", "model_family", "capability", "node_class", "channel", "author", "date_from", "date_to", "has_workflow", "sort"}
            }
    return safe


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
            # Keep the typed malformed classification, but communicate the
            # bounded workflow metadata when available.  This is useful for
            # rows that carry semantics without a normalizable JSON payload;
            # raw payload/source still never enters the digest.
            if _is_workflow_row(body):
                return _workflow_digest_line(body)
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


_RESEARCH_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

def _extract_research_decision_json(raw: str) -> dict[str, Any]:
    """Extract a research-decision JSON object from prose or ```json fences.

    Models frequently prefix a valid tool-call object with a sentence or wrap
    it in a markdown fence. Strict ``json.loads`` of the whole blob classified
    those as ``malformed_json`` and retried the research turn (the 4→41
    explosion). Extract the first qualifying object before failing closed.
    """
    from .prompts import _extract_json_object, _first_json_object_span

    text = raw.strip()
    fence = _RESEARCH_FENCE_RE.search(text)
    if fence is not None:
        inner = fence.group(1).strip()
        try:
            parsed = json.loads(inner)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    try:
        return _extract_json_object(text)
    except ValueError:
        span = _first_json_object_span(text)
        if span is None:
            raise json.JSONDecodeError("No JSON object in research decision", text, 0)
        start, end = span
        return json.loads(text[start:end])


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
    try:
        parsed = _extract_research_decision_json(raw)
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
        "- On answer-only inspect routes, your synthesis is optional context "
        "for the no-edit reply; it never authorizes a graph mutation.\n"
        "Rules:\n"
        "- Call a tool to gather evidence; the tool result will be returned in "
        "the next digest. Choose the query and the tool yourself.\n"
        "- Search hits are LEADS, not answers: fetch every Hivemind record "
        "you rely on materially (hivemind_get) so your claims are attributed "
        "to fetched content, not titles.\n"
        "- Lean search shape: build hivemind_search queries from 2-4 "
        "distinctive tokens (model/node names like 'VACE' or 'lightx2v', "
        "never generic words like 'workflow' or 'best'); text matching runs "
        "on community message content, and distillations are fetched by ID "
        "via hivemind_get rather than searched.\n"
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
        '"uncertainty": string, "claim_provenance": {claim: [evidence_id, ...]} } '
        '— the evidence answers the question. Claim provenance is optional; '
        'when present every id must be returned by a tool.'
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
    if not gate_bits and (
        metadata.get("has_workflow_json") is True
        or row.get("has_workflow_json") is True
    ):
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
    searches_left: int | None = None,
    fetches_left: int | None = None,
    registry_left: int | None = None,
    turns_left: int | None = None,
    seconds_left: float | None = None,
) -> str:
    """Return a bounded, evidence-first digest for the next model turn.

    Fetched records are synthesis-grade evidence and are shown newest first.
    Search hits remain compact leads. The digest exposes the two production
    ceilings as well as the wall-clock backstop so the agent can spend its
    final turn synthesizing instead of requesting work Python will refuse.
    """
    lines: list[str] = []
    if seconds_left is not None:
        lines.append(f"Time left: ~{max(0, int(seconds_left))}s.")
    if turns_left is not None:
        lines.append(f"Decision turns left: {max(0, int(turns_left))}.")
    call_limits = [
        value
        for value in (searches_left, fetches_left, registry_left)
        if value is not None
    ]
    if call_limits:
        lines.append(
            "Evidence tool calls left: "
            f"{max(0, min(int(value) for value in call_limits))}."
        )
    record_lines: list[str] = []
    status_lines: list[str] = []
    search_lines: list[str] = []
    seen_record_ids: set[str] = set()
    # The model only needs the newest compact ledger window.  Full result
    # bodies stay in artifacts and are never pulled into this prompt digest.
    recent_tool_calls = tool_calls[-_MAX_DIGEST_ENTRIES:]
    for call in reversed(recent_tool_calls):
        tool = str(call.get("tool") or "")
        status = str(call.get("status") or "")
        query = _bounded(call.get("query", ""), 120)
        ids = [str(item) for item in (call.get("evidence_ids") or ())][:8]
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
    # T4.1: persisted remaining-budget/deadline snapshot (shared schema with
    # the threaded ``research_findings.budget`` block): deadline_seconds is
    # the configured wall-clock window, turns_used the consumed decision
    # turns, deadline_reached a typed exhaustion-by-deadline flag.
    budget: Mapping[str, Any] | None = None

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
        if self.budget is not None:
            # Additive-with-omission (T4.1): traces without a budget snapshot
            # keep the exact legacy serialized shape.
            payload["budget"] = dict(self.budget)
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
    max_tool_calls: int | None = MAX_RESEARCH_TOOL_CALLS,
    hivemind_timeout_threshold: int = HIVEMIND_TIMEOUT_CIRCUIT_THRESHOLD,
    cache_root: Any = None,
    research_brief: str = "",
    session_id: str | None = None,
    request_identity: str | Mapping[str, Any] | None = None,
    baseline_identity: str | Mapping[str, Any] | None = None,
    allow_empty_finish: bool = False,
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Run the C1 agent-owned tool-calling research loop.

    The AGENT chooses every tool call and decides when to finish; Python
    executes the chosen calls, records typed evidence, and enforces the
    research-phase allowlist, finite decision/tool-call ceilings, and the
    wall-clock ``deadline_seconds`` backstop. ``None`` for either ceiling uses
    the production default rather than disabling the bound.

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
    turn_limit = (
        MAX_RESEARCH_DECISION_TURNS
        if max_turns is None
        else max(0, int(max_turns))
    )
    tool_call_limit = (
        MAX_RESEARCH_TOOL_CALLS
        if max_tool_calls is None
        else max(0, int(max_tool_calls))
    )
    timeout_threshold = max(1, int(hivemind_timeout_threshold))

    artifacts: dict[str, EvidenceArtifact] = {}
    ledger_entries: list[EvidenceLedgerEntry] = []
    warnings: list[str] = []
    iterations: list[AgentResearchIteration] = []
    tool_call_digests: list[dict[str, Any]] = []
    # P1-c: count EXECUTED agent-chosen tool calls (not refusal/premature
    # digest entries) so a finish with zero research activity is detectable.
    tool_calls_made = 0
    consecutive_hivemind_timeouts = 0
    fetched_requested_ids: set[str] = set()
    stop_reason = ""
    checkpoint_kwargs = {
        "request_identity": request_identity,
        "route": route,
        "baseline_identity": baseline_identity,
    }

    def _save_checkpoint() -> None:
        _save_research_checkpoint(
            session_id,
            **checkpoint_kwargs,
            ledger_entries=ledger_entries,
            artifacts=artifacts,
        )

    # S4/B17: a session id is storage only; replay requires all identity
    # dimensions of the request, route, and baseline.
    _ckpt = _load_research_checkpoint(session_id, **checkpoint_kwargs)
    if _ckpt is not None:
        try:
            _ckpt_entries, _ckpt_arts = _ckpt
            for _e in _ckpt_entries:
                ledger_entries.append(_e)
            for _k, _v in _ckpt_arts.items():
                if _k not in artifacts:
                    artifacts[_k] = _v
            for _e in _ckpt_entries:
                if _e.decision in _RESEARCH_TOOL_DECISIONS and _entry_is_executed_tool_call(_e):
                    tool_calls_made += 1
            warnings.append(f"research checkpoint resumed: {len(_ckpt_entries)} entries, {len(_ckpt_arts)} artifacts")
        except Exception:
            pass

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
                tool_status=result.status.value,
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
        _save_checkpoint()

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
                tool_status=ToolStatus.REFUSED.value,
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
        _save_checkpoint()

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
        _save_checkpoint()

    def _record_exhaustion(decision: str, message: str) -> None:
        """Record a typed, compact terminal marker without inventing evidence."""
        _add_entry(
            EvidenceLedgerEntry(
                decision=decision,
                conclusion=message,
                evidence_ids=(),
                uncertainty=message,
            )
        )
        warnings.append(message)
        _save_checkpoint()

    current_question = question

    try:
        # Exact replay keeps the existing question marker instead of adding a
        # duplicate to the resumed ledger.  A changed request should have a
        # changed request_identity and therefore never reaches this branch.
        question_artifact = artifacts.get(_QUESTION_ARTIFACT_ID)
        question_body = (
            question_artifact.body
            if question_artifact is not None
            and isinstance(question_artifact.body, Mapping)
            else {}
        )
        has_question_marker = any(
            entry.decision == DECISION_QUESTION
            and entry.conclusion == question
            and _QUESTION_ARTIFACT_ID in entry.evidence_ids
            for entry in ledger_entries
        )
        if not (
            has_question_marker
            and question_body.get("question") == question
            and question_body.get("route") == route
        ):
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
        while turns_taken < turn_limit:
            if now() > deadline:
                warnings.append("research stage phase deadline exceeded; stopped early")
                stop_reason = "deadline"
                break

            decision_reserve = min(
                _DECISION_TURN_LATENCY_RESERVE_SECONDS,
                max(0.0, deadline - now()),
            )
            digest = build_evidence_digest(
                question=current_question,
                tool_calls=tool_call_digests,
                artifacts=artifacts,
                searches_left=max(0, tool_call_limit - tool_calls_made),
                fetches_left=max(0, tool_call_limit - tool_calls_made),
                registry_left=max(0, tool_call_limit - tool_calls_made),
                turns_left=max(0, turn_limit - turns_taken),
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
                if not allow_empty_finish and not citable_citations and tool_calls_made == 0:
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
                if not allow_empty_finish and fetched_requested_ids and not fetched_cited:
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
                claim_provenance: dict[str, tuple[str, ...]] = {}
                raw_provenance = decision.get("claim_provenance")
                if isinstance(raw_provenance, Mapping):
                    for raw_claim, raw_ids in raw_provenance.items():
                        if not isinstance(raw_claim, str) or not raw_claim.strip():
                            continue
                        resolved_ids: list[str] = []
                        if isinstance(raw_ids, (list, tuple)):
                            for raw_id in raw_ids:
                                candidate_id = str(raw_id)
                                if (
                                    candidate_id in artifacts
                                    and artifacts[candidate_id].kind
                                    in {"hivemind_record", "web_search_result", "registry_resolution", "node_schema"}
                                ):
                                    resolved_ids.append(candidate_id)
                                elif candidate_id.startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
                                    alias = "hivemind_get:" + candidate_id.removeprefix(
                                        _HIVEMIND_EVIDENCE_ID_PREFIX
                                    )
                                    if (
                                        alias in artifacts
                                        and artifacts[alias].kind
                                        in {"hivemind_record", "web_search_result", "registry_resolution", "node_schema"}
                                    ):
                                        resolved_ids.append(alias)
                        if resolved_ids:
                            claim_provenance[raw_claim.strip()] = tuple(
                                dict.fromkeys(resolved_ids)
                            )
                if not claim_provenance and cited:
                    fetched_ids = tuple(
                        evidence_id
                        for evidence_id in cited
                        if evidence_id in artifacts
                        and artifacts[evidence_id].kind
                        in {"hivemind_record", "web_search_result", "registry_resolution", "node_schema"}
                    )
                    if fetched_ids:
                        claim_provenance = {"conclusion": fetched_ids}
                refine_question = decision.get("refine_question")
                refine_question_text = _clean_text(refine_question)
                enough = not bool(refine_question_text)

                # Preserve the complete model synthesis as a durable artifact;
                # the ledger carries only a bounded projection. This keeps a
                # 4,001+ character answer from poisoning the whole stage.
                synthesis_id = "research_synthesis:" + hashlib.sha256(
                    conclusion.encode("utf-8")
                ).hexdigest()[:24]
                _add_artifact(EvidenceArtifact(
                    evidence_id=synthesis_id,
                    kind="research_synthesis",
                    body={
                        "conclusion": conclusion,
                        "uncertainty": uncertainty,
                        "evidence_ids": list(cited),
                        "claim_provenance": {
                            claim: list(ids)
                            for claim, ids in claim_provenance.items()
                        },
                    },
                    source="research_agent",
                ))
                compact_conclusion = _bounded(
                    conclusion or "synthesis produced no conclusion",
                    MAX_LEDGER_CONCLUSION_CHARS,
                )
                _add_entry(
                    EvidenceLedgerEntry(
                        decision=DECISION_SYNTHESIZE,
                        conclusion=compact_conclusion,
                        evidence_ids=tuple(dict.fromkeys((*cited, synthesis_id))),
                        uncertainty=uncertainty,
                        claim_provenance=claim_provenance,
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
                            "claim_provenance": {
                                claim: list(ids)
                                for claim, ids in claim_provenance.items()
                            },
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
            args = _safe_research_args(tool, args)
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
            if tool_calls_made >= tool_call_limit:
                stop_reason = "tool_call_limit"
                _refusal_call(
                    tool,
                    _bounded(str(args), 120),
                    (
                        "research_tool_limit_exhausted: no evidence tool call "
                        f"executed because the finite limit of {tool_call_limit} "
                        "was reached"
                    ),
                )
                _record_exhaustion(
                    DECISION_TOOL_LIMIT_EXHAUSTED,
                    (
                        "research stage exhausted its finite evidence tool-call "
                        f"limit ({tool_call_limit}); retained prior evidence"
                    ),
                )
                break
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
                if tool in {HIVE_MIND_SEARCH_TOOL, HIVE_MIND_GET_TOOL}:
                    if _is_hivemind_timeout_result(tool, result):
                        consecutive_hivemind_timeouts += 1
                    else:
                        consecutive_hivemind_timeouts = 0
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

            if consecutive_hivemind_timeouts >= timeout_threshold:
                stop_reason = "hivemind_timeout_circuit"
                _record_exhaustion(
                    DECISION_HIVEMIND_CIRCUIT_OPEN,
                    (
                        "hivemind timeout circuit opened after "
                        f"{consecutive_hivemind_timeouts} consecutive "
                        "timeout-shaped calls; retained typed empty/thin "
                        "evidence for downstream graph-local handling"
                    ),
                )
                break

            if now() > deadline:
                warnings.append(
                    "research stage phase deadline exceeded after the tool "
                    "call; stopped early (the call's evidence is preserved)"
                )
                stop_reason = "deadline"
                break

        if not agent_finished:
            # P1-a: the loop stopped WITHOUT an agent finish — deadline
            # exceeded, max_turns exhausted, or a malformed decision.  Never
            # label that "ok": a stage that produced no synthesis must be
            # distinguishable from a successful research run so the executor
            # can fail closed instead of implementing from nothing.
            status = "exhausted"
            if not stop_reason:
                stop_reason = "decision_turn_limit"
            warnings.append(
                "research stage stopped without an agent finish "
                f"(reason={stop_reason}); status=exhausted"
            )
    except Exception as exc:  # noqa: BLE001 - research failures are typed, never raised
        status = "failed"
        final_verdict = "failed"
        error = f"{type(exc).__name__}: {exc}"
        raw_preview = getattr(exc, "raw_response_preview", None)
        if isinstance(raw_preview, str) and raw_preview.strip():
            error += f" | raw response preview: {_bounded(raw_preview, 500)}"
        LOGGER.warning("agent research stage failed: %s", error)
        try:
            _save_checkpoint()
        except Exception:
            pass

    if status == "ok" and final_verdict in {"enough", "refine"}:
        if final_verdict == "enough":
            _clear_research_checkpoint(session_id, **checkpoint_kwargs)
    elif status == "exhausted" and "deadline" in stop_reason:
        try:
            _save_checkpoint()
        except Exception:
            pass

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
        # T4.1: the remaining-budget/deadline facts persist as data on the
        # trace (shared schema with the threaded findings packet) instead of
        # living only in per-turn digests.
        budget={
            "deadline_seconds": float(deadline_seconds),
            "turns_used": turns_taken,
            "deadline_reached": stop_reason == "deadline",
        },
    )
    pack = EvidencePack(artifacts=artifacts, ledger=EvidenceLedger(entries=ledger_entries))
    return trace, pack


__all__ = [
    "AgentResearchIteration",
    "AgentResearchTrace",
    "DECISION_ENOUGH_REFINE",
    "DECISION_FINISH_PREMATURE",
    "DECISION_GET",
    "DECISION_HIVEMIND_CIRCUIT_OPEN",
    "DECISION_QUESTION",
    "DECISION_REGISTRY",
    "DECISION_SEARCH",
    "DECISION_SYNTHESIZE",
    "DECISION_TOOL_LIMIT_EXHAUSTED",
    "HIVEMIND_TIMEOUT_CIRCUIT_THRESHOLD",
    "MAX_RESEARCH_DECISION_TURNS",
    "MAX_RESEARCH_TOOL_CALLS",
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
