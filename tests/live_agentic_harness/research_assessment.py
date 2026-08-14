"""Assessment-first evidence rules for agent-owned research phases.

The research phase is a distinct, agent-owned stage: the agent forms a narrow
research question, chooses the cheapest authoritative source (Hivemind first),
invokes typed tools, synthesizes, and records a compact evidence ledger.  The
grader reconstructs grounding from the recorded evidence — never from prose.

This module is the *contract first*: it defines the envelope shape the research
phase must produce and grades it.  Producers (agent-backend integration) must
satisfy this contract; scenario authors opt in with
``assessment.research``.

Envelope contract
-----------------

``response.evidence.research`` is a mapping with exactly two keys:

* ``steps`` — the ORDERED transcript of the research loop.  Each step is one
  of:

  - ``{"kind": "question", "text": "<the recorded research question>"}``
    — formed and recorded before any searching (scored: question-before-search).
  - ``{"kind": "tool_call", "tool_name": "<tool>", "status": "<typed status>",
       "query": "<search text for search tools>", "evidence_ids": [...]}``
    — a ``ToolResult.to_dict()`` superset (tool_name/status/evidence_ids are
    the graded fields, plus ``query`` on search tools).  ``status`` uses the
    typed vocabulary ``ok | no_results | rate_limited | timeout | unavailable
    | invalid_request | refused``.
  - ``{"kind": "synthesis", "citations": [<evidence ids>],
       "uncertainty": "<text>"}``
    — the memo's inspected citations, which must resolve to evidence IDs the
    tool calls returned.

* ``evidence_pack`` — an ``EvidencePack.to_dict()`` payload: ``artifacts``
  keyed by evidence_id plus a compact ``ledger`` of Decision / Conclusion /
  Evidence IDs / Uncertainty.  The pack is validated through the typed
  ``vibecomfy.executor.evidence_pack.EvidencePack`` contract, which also
  enforces that every ledger reference resolves to a captured artifact.

Assertions (each fails the run when violated):

* question-before-search — the recorded question precedes the first tool
  invocation; searching before forming a question fails.
* query relevance — every search tool call carries a query that shares at
  least one significant term with the scenario's research topic.
* required-Hivemind invocation — when the scenario requires it (default), the
  agent must invoke a ``hivemind_*`` tool (Hivemind-first research policy).
* citation resolution — memo citations resolve to evidence IDs returned by the
  tool calls (pack capture of the ledger references is enforced by the
  evidence-pack check).
* no-local-search research path — the agent's research may not use a local
  corpus search tool, and the legacy local-only deterministic result scope
  never satisfies the phase.
* evidence-pack capture — the phase records a valid evidence pack whose ledger
  entries resolve to captured artifacts.

Activation: ``assessment.research`` — ``true`` enables the assertions with
defaults; a mapping configures them:

* ``topic_terms`` (list of str) — relevance vocabulary; falls back to
  significant tokens of the scenario ``query``.
* ``require_hivemind`` (bool, default true) — whether a ``hivemind_*``
  invocation is mandatory.

The module also carries its own focused tests (run as
``pytest tests/live_agentic_harness/research_assessment.py``).
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from vibecomfy.executor.evidence_pack import EvidencePack

# Research-phase tool vocabulary (mirrors docs/agent-judgment-pipeline.md).
_RESEARCH_SEARCH_TOOLS = frozenset({"hivemind_search", "web_search"})
_HIVEMIND_TOOL_PREFIX = "hivemind_"
# Local-corpus search is never an agent-owned research path.
_LOCAL_SEARCH_TOOL_NAMES = frozenset({
    "local_search",
    "local_corpus_search",
    "corpus_search",
    "local_search_corpus",
})

_STOPWORDS = frozenset({
    "a", "an", "and", "any", "are", "as", "at", "be", "but", "by", "can",
    "change", "changing", "could", "do", "does", "for", "from", "generate",
    "generating", "get", "got", "had", "has", "have", "how", "i", "if", "in",
    "into", "is", "it", "its", "make", "may", "me", "might", "my", "need",
    "needs", "not", "of", "on", "or", "please", "see", "should", "show",
    "so", "switch", "tell", "than", "that", "the", "their", "them", "then",
    "there", "they", "this", "to", "use", "using", "video", "want", "wants",
    "was", "way", "we", "were", "what", "why", "will", "with", "without",
    "workflow", "workflows", "would", "you", "your",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _research_config(scenario: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the research-assessment config, or None when assertions are off.

    ``assessment.research`` may be ``true`` (defaults) or a mapping with
    ``topic_terms`` / ``require_hivemind``.
    """
    if scenario is None:
        return None
    assessment = scenario.get("assessment")
    if not isinstance(assessment, Mapping):
        return None
    raw = assessment.get("research")
    if raw is True:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    return None


def _research_evidence(response: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    evidence = response.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    research = evidence.get("research")
    return research if isinstance(research, Mapping) else None


def _steps(research: Mapping[str, Any]) -> list[Any]:
    steps = research.get("steps")
    return steps if isinstance(steps, list) else []


def _question_steps(research: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    questions: list[Mapping[str, Any]] = []
    for step in _steps(research):
        if not isinstance(step, Mapping) or step.get("kind") != "question":
            continue
        text = step.get("text")
        if isinstance(text, str) and text.strip():
            questions.append(step)
    return questions


def _tool_call_steps(research: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    calls: list[Mapping[str, Any]] = []
    for step in _steps(research):
        if not isinstance(step, Mapping) or step.get("kind") != "tool_call":
            continue
        if isinstance(step.get("tool_name"), str) and step["tool_name"].strip():
            calls.append(step)
    return calls


def _significant_tokens(text: str) -> frozenset[str]:
    """Return meaningful casefolded alphanumeric tokens for relevance."""
    tokens = {
        token
        for token in _TOKEN_RE.findall(text.casefold())
        if len(token) >= 2 and token not in _STOPWORDS
    }
    return frozenset(tokens)


def _relevance_terms(
    config: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> frozenset[str]:
    """Return the vocabulary queries must overlap with.

    Explicit ``topic_terms`` win; otherwise fall back to significant tokens of
    the scenario query so relevance is still checkable without extra config.
    """
    raw = config.get("topic_terms")
    if isinstance(raw, list) and raw:
        terms: set[str] = set()
        for item in raw:
            if isinstance(item, str) and item.strip():
                terms.update(_significant_tokens(item) or {item.casefold().strip()})
        if terms:
            return frozenset(terms)
    if scenario is not None:
        query = scenario.get("query")
        if isinstance(query, str) and query.strip():
            return _significant_tokens(query)
    return frozenset()


def _assess_question_before_search(
    research: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    steps = _steps(research)
    if not _question_steps(research):
        issues.append(
            {
                "check": "research_question_before_search",
                "severity": "error",
                "detail": (
                    "Research phase recorded no question; a research question "
                    "must be formed and recorded before searching."
                ),
            }
        )
        return issues
    first_question = next(
        index
        for index, step in enumerate(steps)
        if isinstance(step, Mapping)
        and step.get("kind") == "question"
        and isinstance(step.get("text"), str)
        and step["text"].strip()
    )
    first_tool = next(
        (
            index
            for index, step in enumerate(steps)
            if isinstance(step, Mapping)
            and step.get("kind") == "tool_call"
            and isinstance(step.get("tool_name"), str)
            and step["tool_name"].strip()
        ),
        None,
    )
    if first_tool is not None and first_tool < first_question:
        issues.append(
            {
                "check": "research_question_before_search",
                "severity": "error",
                "detail": (
                    "Research phase searched before recording its question "
                    "(step index of first tool call is earlier than the "
                    "recorded question); question-before-search is required."
                ),
            }
        )
    return issues


def _assess_query_relevance(
    research: Mapping[str, Any],
    config: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    terms = _relevance_terms(config, scenario)
    for step in _tool_call_steps(research):
        tool_name = step["tool_name"]
        if tool_name not in _RESEARCH_SEARCH_TOOLS:
            continue
        query = step.get("query")
        if not isinstance(query, str) or not query.strip():
            issues.append(
                {
                    "check": "research_query_relevance",
                    "severity": "error",
                    "detail": (
                        f"Search tool {tool_name!r} was invoked without a query "
                        "text; a relevant search query is required."
                    ),
                }
            )
            continue
        tokens = _significant_tokens(query)
        if not terms:
            continue
        if not tokens or tokens.isdisjoint(terms):
            issues.append(
                {
                    "check": "research_query_relevance",
                    "severity": "error",
                    "detail": (
                        f"Search query {query.strip()!r} shares no significant "
                        f"term with the research topic "
                        f"{sorted(terms)!r}; the query must be relevant."
                    ),
                }
            )
    return issues


def _assess_required_hivemind(
    research: Mapping[str, Any],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if config.get("require_hivemind", True) is False:
        return []
    invoked = [
        step["tool_name"]
        for step in _tool_call_steps(research)
        if step["tool_name"].startswith(_HIVEMIND_TOOL_PREFIX)
    ]
    if invoked:
        return []
    return [
        {
            "check": "research_hivemind_required",
            "severity": "error",
            "detail": (
                "Research phase never invoked a hivemind_* tool "
                "(hivemind_search/hivemind_get); Hivemind is the required "
                "first source for agent-owned research."
            ),
        }
    ]


def _assess_citation_resolution(
    research: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    returned: set[str] = set()
    for step in _tool_call_steps(research):
        ids = step.get("evidence_ids")
        if isinstance(ids, list):
            returned.update(
                str(item) for item in ids if isinstance(item, str) and item.strip()
            )
    citations: list[str] = []
    for step in _steps(research):
        if not isinstance(step, Mapping) or step.get("kind") != "synthesis":
            continue
        raw = step.get("citations")
        if isinstance(raw, list):
            citations.extend(
                str(item) for item in raw if isinstance(item, str) and item.strip()
            )
    if not citations:
        issues.append(
            {
                "check": "research_citation_resolution",
                "severity": "error",
                "detail": (
                    "Research memo cites no evidence; inspected citations must "
                    "resolve to evidence IDs returned by the tool calls."
                ),
            }
        )
        return issues
    unresolved = sorted(set(citations) - returned)
    if unresolved:
        issues.append(
            {
                "check": "research_citation_resolution",
                "severity": "error",
                "detail": (
                    f"Citation(s) {unresolved!r} resolve to no evidence ID "
                    "returned by a research tool call."
                ),
            }
        )
    return issues


def _assess_no_local_search(research: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for step in _tool_call_steps(research):
        tool_name = step["tool_name"]
        lowered = tool_name.casefold()
        if tool_name in _LOCAL_SEARCH_TOOL_NAMES or "local" in lowered or "corpus" in lowered:
            issues.append(
                {
                    "check": "research_local_search",
                    "severity": "error",
                    "detail": (
                        f"Research phase used local-corpus search tool "
                        f"{tool_name!r}; agent-owned research must use "
                        "Hivemind/web/registry tools only."
                    ),
                }
            )
    if str(research.get("result_scope", "")).casefold() == "local":
        issues.append(
            {
                "check": "research_local_search",
                "severity": "error",
                "detail": (
                    "Research evidence reports result_scope=local (legacy "
                    "deterministic local-only research); agent-owned research "
                    "is required."
                ),
            }
        )
    return issues


def _assess_evidence_pack(research: Mapping[str, Any]) -> list[dict[str, Any]]:
    pack = research.get("evidence_pack")
    if not isinstance(pack, Mapping):
        return [
            {
                "check": "research_evidence_pack",
                "severity": "error",
                "detail": (
                    "Research phase recorded no evidence_pack; tool inputs, "
                    "result IDs, fetched records, and the ledger must be "
                    "captured for scoring."
                ),
            }
        ]
    try:
        EvidencePack.from_dict(pack)
    except ValueError as exc:
        return [
            {
                "check": "research_evidence_pack",
                "severity": "error",
                "detail": f"Research evidence pack is invalid: {exc}",
            }
        ]
    ledger = pack.get("ledger")
    entries = ledger.get("entries") if isinstance(ledger, Mapping) else None
    if not isinstance(entries, list) or not entries:
        return [
            {
                "check": "research_evidence_pack",
                "severity": "error",
                "detail": (
                    "Research evidence pack ledger is empty; the phase must "
                    "record its Decision / Conclusion / Evidence IDs / "
                    "Uncertainty."
                ),
            }
        ]
    return []


def assess_research_evidence(
    response: Mapping[str, Any] | None,
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Grade research-phase evidence; empty list when assertions are off.

    Enabled by ``assessment.research`` (``true`` or a mapping).  Every
    assertion failure is an error-severity issue with a stable ``check`` name.
    """
    config = _research_config(scenario)
    if config is None:
        return []
    research = _research_evidence(response)
    if research is None:
        return [
            {
                "check": "research_evidence",
                "severity": "error",
                "detail": (
                    "Scenario requires research evidence, but "
                    "response.evidence.research is missing."
                ),
            }
        ]
    issues: list[dict[str, Any]] = []
    issues.extend(_assess_question_before_search(research))
    issues.extend(_assess_query_relevance(research, config, scenario))
    issues.extend(_assess_required_hivemind(research, config))
    issues.extend(_assess_citation_resolution(research))
    issues.extend(_assess_no_local_search(research))
    issues.extend(_assess_evidence_pack(research))
    return issues


# ── tests ────────────────────────────────────────────────────────────────────
# Focused suite for this module; run with
#   .venv/bin/python -m pytest tests/live_agentic_harness/research_assessment.py


def _compliant_research_evidence() -> dict[str, Any]:
    """A fully compliant agent-owned research envelope section."""
    return {
        "steps": [
            {"kind": "question", "text": "Which node chain produces audio-conditioned Wan video?"},
            {
                "kind": "tool_call",
                "tool_name": "hivemind_search",
                "status": "ok",
                "query": "wan audio conditioning video",
                "evidence_ids": ["ev-hivemind-1"],
                "result": {"hits": 3},
                "diagnostics": [],
            },
            {
                "kind": "tool_call",
                "tool_name": "hivemind_get",
                "status": "ok",
                "query": "",
                "evidence_ids": ["ev-hivemind-2"],
                "result": {"record": {}},
                "diagnostics": [],
            },
            {
                "kind": "synthesis",
                "citations": ["ev-hivemind-1", "ev-hivemind-2"],
                "uncertainty": "None material.",
            },
        ],
        "evidence_pack": {
            "artifacts": {
                "ev-hivemind-1": {
                    "evidence_id": "ev-hivemind-1",
                    "kind": "hivemind_search_result",
                    "body": {"title": "Wan audio conditioning"},
                    "metadata": {},
                },
                "ev-hivemind-2": {
                    "evidence_id": "ev-hivemind-2",
                    "kind": "hivemind_record",
                    "body": {"text": "Use WanT2V with audio embeds."},
                    "metadata": {},
                },
            },
            "ledger": {
                "entries": [
                    {
                        "decision": "Use WanT2V with audio embeds.",
                        "conclusion": "WanT2V supports audio conditioning.",
                        "evidence_ids": ["ev-hivemind-1", "ev-hivemind-2"],
                        "uncertainty": "",
                    }
                ]
            },
        },
    }


def _research_scenario(**overrides: object) -> dict[str, Any]:
    scenario: dict[str, Any] = {
        "id": "research-scenario",
        "query": "How do I condition Wan video on audio?",
        "assessment": {
            "expect_graph_changed": False,
            "research": {"topic_terms": ["wan", "audio", "ltx"]},
        },
    }
    scenario["assessment"]["research"].update(overrides)
    return scenario


def _response_with_research(research: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "evidence": {"research": research}}


def test_research_assertions_disabled_without_opt_in() -> None:
    response = _response_with_research({"steps": [], "evidence_pack": {}})
    assert assess_research_evidence(response, {"assessment": {}}) == []


def test_compliant_research_evidence_passes() -> None:
    response = _response_with_research(_compliant_research_evidence())
    assert assess_research_evidence(response, _research_scenario()) == []


def test_missing_research_evidence_fails() -> None:
    response = {"ok": True, "evidence": {}}
    issues = assess_research_evidence(response, _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_evidence"]
    assert issues[0]["severity"] == "error"


def test_search_before_question_fails() -> None:
    research = _compliant_research_evidence()
    research["steps"] = [
        {
            "kind": "tool_call",
            "tool_name": "hivemind_search",
            "status": "ok",
            "query": "wan audio",
            "evidence_ids": ["ev-hivemind-1"],
        },
        {"kind": "question", "text": "Which chain conditions Wan on audio?"},
        {"kind": "synthesis", "citations": ["ev-hivemind-1"], "uncertainty": ""},
    ]
    issues = assess_research_evidence(
        _response_with_research(research), _research_scenario()
    )
    assert [issue["check"] for issue in issues] == ["research_question_before_search"]


def test_missing_question_fails() -> None:
    research = {
        "steps": [
            {
                "kind": "tool_call",
                "tool_name": "hivemind_search",
                "status": "ok",
                "query": "wan audio",
                "evidence_ids": ["ev-1"],
            },
            {"kind": "synthesis", "citations": ["ev-1"], "uncertainty": ""},
        ],
        "evidence_pack": {
            "artifacts": {
                "ev-1": {
                    "evidence_id": "ev-1",
                    "kind": "hivemind_search_result",
                    "body": {"title": "Wan audio"},
                    "metadata": {},
                }
            },
            "ledger": {
                "entries": [
                    {
                        "decision": "go",
                        "conclusion": "proceed",
                        "evidence_ids": ["ev-1"],
                        "uncertainty": "",
                    }
                ]
            },
        },
    }
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_question_before_search"]


def test_irrelevant_search_query_fails() -> None:
    research = _compliant_research_evidence()
    research["steps"][1]["query"] = "banana bread recipe"
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_query_relevance"]


def test_search_without_query_fails() -> None:
    research = _compliant_research_evidence()
    del research["steps"][1]["query"]
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_query_relevance"]


def test_hivemind_required_by_default_fails_when_absent() -> None:
    research = _compliant_research_evidence()
    research["steps"][1]["tool_name"] = "web_search"
    research["steps"][2]["tool_name"] = "registry_lookup"
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_hivemind_required"]


def test_hivemind_requirement_can_be_opted_out() -> None:
    research = _compliant_research_evidence()
    research["steps"][1]["tool_name"] = "web_search"
    research["steps"][2]["tool_name"] = "registry_lookup"
    scenario = _research_scenario(require_hivemind=False)
    assert assess_research_evidence(_response_with_research(research), scenario) == []


def test_unresolvable_citation_fails() -> None:
    research = _compliant_research_evidence()
    research["steps"][3]["citations"] = ["ev-hivemind-1", "ev-fabricated"]
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_citation_resolution"]
    assert "ev-fabricated" in issues[0]["detail"]


def test_missing_citation_fails() -> None:
    research = _compliant_research_evidence()
    research["steps"][3]["citations"] = []
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_citation_resolution"]


def test_local_corpus_search_tool_fails() -> None:
    research = _compliant_research_evidence()
    research["steps"][1]["tool_name"] = "local_corpus_search"
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_local_search"]


def test_legacy_local_result_scope_fails() -> None:
    research = _compliant_research_evidence()
    research["result_scope"] = "local"
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_local_search"]


def test_missing_evidence_pack_fails() -> None:
    research = _compliant_research_evidence()
    del research["evidence_pack"]
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_evidence_pack"]


def test_invalid_evidence_pack_fails() -> None:
    research = _compliant_research_evidence()
    research["steps"][3]["citations"] = ["ev-hivemind-1"]
    research["evidence_pack"] = {
        "artifacts": {},
        "ledger": {
            "entries": [
                {
                    "decision": "go",
                    "conclusion": "proceed",
                    "evidence_ids": ["ev-missing"],
                    "uncertainty": "",
                }
            ]
        },
    }
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_evidence_pack"]
    assert "ev-missing" in issues[0]["detail"]


def test_empty_ledger_fails() -> None:
    research = _compliant_research_evidence()
    research["evidence_pack"]["ledger"] = {"entries": []}
    issues = assess_research_evidence(_response_with_research(research), _research_scenario())
    assert [issue["check"] for issue in issues] == ["research_evidence_pack"]


def test_research_assertions_wired_into_assessor(tmp_path: Any) -> None:
    """End-to-end: compliant research evidence passes the full assessor;
    a local-corpus path fails it."""
    import json

    from tests.live_agentic_harness.assessor import assess_live_output_dir

    scenario = _research_scenario()
    compliant = _response_with_research(_compliant_research_evidence())
    compliant_dir = tmp_path / "compliant"
    compliant_dir.mkdir(parents=True, exist_ok=True)
    (compliant_dir / "response.json").write_text(json.dumps(compliant), encoding="utf-8")
    assessment = assess_live_output_dir(compliant_dir, scenario=scenario)
    assert assessment["passed"] is True, assessment["issues"]

    local = _response_with_research(_compliant_research_evidence())
    local["evidence"]["research"]["steps"][1]["tool_name"] = "local_corpus_search"
    local_dir = tmp_path / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "response.json").write_text(json.dumps(local), encoding="utf-8")
    assessment = assess_live_output_dir(local_dir, scenario=scenario)
    assert assessment["passed"] is False
    error_checks = {
        issue["check"]
        for issue in assessment["issues"]
        if issue["severity"] == "error"
    }
    assert "research_local_search" in error_checks
