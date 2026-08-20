"""C1 — Agent-owned research stage (tool-calling agent phase).

Covers the active research-phase contract:

1. The agent trace proves an explicit question recorded BEFORE any tool call
   (question-before-search) and an enough/refine verdict in the F01 ledger.
2. The AGENT chooses every tool call (call/finish decisions); deterministic
   Python only executes the chosen calls and enforces the research-phase
   allowlist (hivemind_search / hivemind_get / registry_lookup — never
   implement-phase tools).
3. No full research result or workflow schema dump is injected into the model
   request (behavioral capture + source grep); the digest carries only compact
   tool statuses, evidence IDs, and previews.
4. Research calls and decision turns are UNBOUNDED (minimal-budget plan); the
   wall-clock deadline terminates the loop deterministically (tests inject
   small ``deadline_seconds`` / ``max_turns`` clamps).

All model calls and Hivemind tools are faked and deterministic — no network,
no ComfyUI boot, no Arnold imports.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Callable
from unittest import mock

import pytest

from vibecomfy.executor import agent_research_stage as stage
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
)
from vibecomfy.executor.profiles import AgentSpecShape, set_profile_override_dir
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

# ── Profile fixture (research/adapt routes need a resolved research spec) ────

_BASE_PROFILE = """
[classify]
agent = "hermes"
model = "deepseek-v4-flash"
effort = "low"

[research]
agent = "hermes"
model = "deepseek-v4-pro"
effort = "medium"

[implement]
agent = "codex"
model = "gpt-5.4"
effort = "high"

[reply]
agent = "hermes"
model = "deepseek-v4-pro"
effort = "low"
"""


@pytest.fixture
def profile_dir(tmp_path: Path) -> Path:
    dir_path = tmp_path / "profiles"
    dir_path.mkdir(parents=True)
    (dir_path / "default.toml").write_text(
        textwrap.dedent(_BASE_PROFILE).strip() + "\n", encoding="utf-8"
    )
    set_profile_override_dir(dir_path)
    yield dir_path
    set_profile_override_dir(None)


# ── Deterministic fakes ──────────────────────────────────────────────────────

_EXPLICIT_QUESTION = "Which node chain produces audio-conditioned Wan video?"


def _research_plan() -> ClassifyDecision:
    """Research-only classifier plan with an explicit research_goal."""
    return ClassifyDecision(
        research=True,
        implement=False,
        reply=True,
        effort="medium",
        plan_summary="research node types",
        route="research",
        task="research_nodes",
        research_goal=_EXPLICIT_QUESTION,
        search_directions=("audio-conditioned Wan video node chains",),
        source_preferences=("workflows", "messages", "web"),
    )


def _fake_search(query: str, limit: int = 5, **kwargs: Any) -> ToolResult:
    """Deterministic Hivemind search returning two stable hits."""
    hits = [
        {
            "evidence_id": "hivemind:workflows:111",
            "source_type": "workflow",
            "title": "Wan audio conditioning chain",
            "body": "LoadAudio -> ConditioningCombine -> WanImageToVideo",
            "url": "",
            "author": "alice",
            "channel": "wan_chatter",
            "created_at": "2026-08-01T00:00:00Z",
            "score": 4,
        },
        {
            "evidence_id": "hivemind:discord:222",
            "source_type": "discord",
            "title": "audio latent routing notes",
            "body": "route the audio latent into the conditioning stack",
            "url": "",
            "author": "bob",
            "channel": "wan_comfyui",
            "created_at": "2026-08-02T00:00:00Z",
            "score": 2,
        },
    ]
    return ToolResult(
        tool_name="hivemind_search",
        status=ToolStatus.OK,
        result={"query": query, "count": 2, "hits": hits, "next_cursor": None, "has_more": False},
        evidence_ids=(hits[0]["evidence_id"], hits[1]["evidence_id"]),
    )


def _fake_get(evidence_id: str, **kwargs: Any) -> ToolResult:
    """Deterministic Hivemind get returning the full record for a hit id."""
    row_id = evidence_id.rsplit(":", 1)[-1]
    # Deliberately longer than the digest's record-preview limit so tests can
    # prove the digest carries a BOUNDED preview of the fetched body (head
    # present, tail absent) — never the full raw body.
    body = (
        "expanded record body with wiring detail — the exact socket/terminal "
        "pattern and preserved settings for the audio-conditioned Wan chain. "
        + ("x" * 400)
        + " END-OF-EXPANDED-RECORD"
    )
    return ToolResult(
        tool_name="hivemind_get",
        status=ToolStatus.OK,
        result={
            "evidence_id": evidence_id,
            "source_type": "workflow",
            "table": evidence_id.split(":")[1],
            "row": {
                "id": row_id,
                "title": f"full record {row_id}",
                "body": body,
                "kind": "workflow",
            },
        },
        evidence_ids=(evidence_id,),
    )


def _agent_judge(judge_log: list[dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Tool-calling agent: search → get → finish (each decision is the AGENT's).

    The first turn calls ``hivemind_search``, the second resolves the top hit
    with ``hivemind_get``, and the third finishes with resolvable citations.
    """

    def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        judge_log.append({"question": question, "digest": digest})
        if "hivemind_search →" not in digest:
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": question},
            }
        if "hivemind_get →" not in digest:
            return {
                "action": "call",
                "tool": "hivemind_get",
                "args": {"evidence_id": "hivemind:workflows:111"},
            }
        return {
            "action": "finish",
            "conclusion": "Use LoadAudio -> ConditioningCombine before WanImageToVideo",
            "evidence_ids": ["hivemind:workflows:111", "hivemind_get:workflows:111"],
            "uncertainty": "low",
        }

    return judge


def _all_strings(payload: Any) -> list[str]:
    """Flatten every string leaf of a JSON-safe structure."""
    out: list[str] = []
    if isinstance(payload, str):
        out.append(payload)
    elif isinstance(payload, dict):
        for _key, value in payload.items():
            out.extend(_all_strings(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            out.extend(_all_strings(item))
    return out


# ── Acceptance 2: explicit question + enough verdict in the ledger ───────────


class TestTraceRecordsQuestionAndJudgment:
    def test_trace_and_ledger_prove_question_and_agent_chosen_tools(
        self, profile_dir: Path
    ) -> None:
        judge_log: list[dict[str, Any]] = []
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=_agent_judge(judge_log),
        )

        assert trace.status == "ok"
        # Explicit question comes from the classifier's research_goal.
        assert trace.question == _EXPLICIT_QUESTION
        assert trace.final_verdict == "enough"
        # One iteration per agent decision: search, get, finish.
        assert len(trace.iterations) == 3
        assert [i.question for i in trace.iterations] == [
            _EXPLICIT_QUESTION,
            _EXPLICIT_QUESTION,
            _EXPLICIT_QUESTION,
        ]

        ledger = pack.ledger
        decisions = [entry.decision for entry in ledger.entries]
        # Question recorded BEFORE any tool call (question-before-search).
        assert decisions[0] == stage.DECISION_QUESTION
        assert decisions.count(stage.DECISION_SEARCH) == 1
        assert decisions.count(stage.DECISION_GET) == 1
        assert decisions.count(stage.DECISION_SYNTHESIZE) == 1
        assert decisions.count(stage.DECISION_ENOUGH_REFINE) == 1
        assert ledger.entries[0].conclusion == _EXPLICIT_QUESTION
        # The verdict is recorded as enough=True.
        enough_entry = [
            entry for entry in ledger.entries if entry.decision == stage.DECISION_ENOUGH_REFINE
        ][-1]
        assert "enough=True" in enough_entry.conclusion

        # The first tool call was the agent's hivemind_search choice.
        assert trace.iterations[0].tool_calls[0]["tool"] == "hivemind_search"
        # The second iteration was the agent's hivemind_get choice.
        assert trace.iterations[1].tool_calls[0]["tool"] == "hivemind_get"

        # Every ledger citation resolves to an artifact in the same pack
        # (already enforced by EvidencePack construction; re-assert here).
        assert pack.ledger.validate_references(set(pack.artifacts)) is None
        for evidence_id in trace.citations:
            assert evidence_id in pack.artifacts
        # Tool results were captured as evidence artifacts.
        assert "hivemind:workflows:111" in pack.artifacts
        assert "hivemind_get:workflows:111" in pack.artifacts
        # P1-b: the fetch digest previews the FETCHED ROW body (bounded) so
        # the agent synthesizes from content, not a title.  The LAST-fetched
        # record gets an expanded window (Grok rule — enough to name class
        # types/wiring), so its tail marker MAY appear; the digest as a whole
        # is still bounded (never the full raw corpus row for every record).
        get_digest = judge_log[-1]["digest"]
        assert "expanded record body" in get_digest
        assert len(get_digest) < 4_000  # hard digest cap holds

    def test_always_search_stops_on_deadline_with_zero_refusals(
        self, profile_dir: Path
    ) -> None:
        """Minimal-budget plan: an agent that never finishes still terminates
        — on the WALL-CLOCK DEADLINE, not a call-count budget.  Searches are
        unbounded, so every call is a successful search (zero budget
        refusals); the deadline stop is ``status="exhausted"``, never "ok",
        so the executor fails closed."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        clock = {"t": 1000.0}

        def fake_now() -> float:
            return clock["t"]

        def always_search(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            # Each decision costs wall time; after a few searches the fake
            # clock crosses the deadline and the loop stops.
            clock["t"] += 1.0
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": question},
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=always_search,
            now_fn=fake_now,
            deadline_seconds=3.0,
        )
        # P1-a: a loop that stops without an agent finish is "exhausted",
        # never "ok" — the executor fails closed on it.
        assert trace.status == "exhausted"
        assert trace.final_verdict == "refine"
        # Zero budget refusals: every call ran as a successful search.
        refused = [
            it
            for it in trace.iterations
            if it.tool_calls and it.tool_calls[0]["status"] == "refused"
        ]
        assert not refused
        # Searches executed freely until the deadline stopped the loop.
        ok_searches = [
            it
            for it in trace.iterations
            if it.tool_calls and it.tool_calls[0]["tool"] == "hivemind_search"
            and it.tool_calls[0]["status"] == "ok"
        ]
        assert ok_searches
        assert "deadline" in " ".join(trace.warnings)
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_deadline_exhaustion_is_exhausted_not_ok(self, profile_dir: Path) -> None:
        """A wall-clock deadline stop without an agent finish is
        ``status="exhausted"``, never ``"ok"`` (P1-a), so the executor can
        fail closed instead of implementing from nothing."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        calls: list[str] = []

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            calls.append(question)
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": question},
            }

        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
            deadline_seconds=0.0,
        )
        assert trace.status == "exhausted"
        assert trace.final_verdict == "refine"
        assert not trace.citations
        assert "deadline" in " ".join(trace.warnings)

    def test_duplicate_citations_dedupe_without_crashing_synthesis(
        self, profile_dir: Path
    ) -> None:
        """P2: a finish citing the same valid evidence ID twice must not crash
        synthesis — the compact ledger contract rejects duplicate evidence_ids
        — citations are deduped order-preserving before the finish is
        recorded."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "hivemind_search" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": question},
                }
            return {
                "action": "finish",
                "conclusion": "Use LoadAudio before the video model.",
                "evidence_ids": [
                    "hivemind:workflows:111",
                    "hivemind:workflows:111",
                    "hivemind:workflows:111",
                ],
                "uncertainty": "low",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        # The duplicate citation must not raise inside the loop (which would
        # have flipped status to "failed").
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        assert trace.citations == ("hivemind:workflows:111",)
        synth = [
            entry
            for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_SYNTHESIZE
        ][-1]
        assert synth.evidence_ids == ("hivemind:workflows:111",)
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_phase_allowlist_refuses_implement_tools(self, profile_dir: Path) -> None:
        """An agent that tries an implement-phase tool gets a typed refusal —
        the call is never executed and the ledger records the refusal — and the
        loop still lets the agent gather real evidence and finish."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def out_of_phase(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "allowlist" not in digest:
                return {
                    "action": "call",
                    "tool": "node_schema",
                    "args": {"node_class": "KSampler"},
                }
            if "hivemind_search →" not in digest:
                return {"action": "call", "tool": "hivemind_search", "args": {"query": question}}
            return {
                "action": "finish",
                "conclusion": "refusal recorded; search evidence gathered",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "implement-phase tool was refused",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=out_of_phase,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        refusals = [e for e in pack.ledger.entries if e.decision == "node_schema"]
        assert refusals, "implement-phase tool call must be refused, not executed"
        assert "allowlist" in refusals[0].conclusion
        # No node_schema artifact was produced (never executed).
        assert not any(key.startswith("tool:node-schema") for key in pack.artifacts)
        # The finish cited real search evidence (a finish with zero evidence
        # AND zero executed tool calls would be rejected as finish_premature).
        synth = [e for e in pack.ledger.entries if e.decision == stage.DECISION_SYNTHESIZE]
        assert synth and synth[0].evidence_ids == ("hivemind:workflows:111",)

    def test_registry_lookup_is_agent_callable(self, profile_dir: Path) -> None:
        """registry_lookup is a research-phase tool the agent may choose."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        calls: list[str] = []

        def fake_registry(node_class: str, **kwargs: Any) -> ToolResult:
            calls.append(node_class)
            return ToolResult(
                tool_name="registry_lookup",
                status=ToolStatus.OK,
                result={
                    "node_class": node_class,
                    "exact_ownership": True,
                    "candidates": [
                        {
                            "ref": {"slug": "comfyui-core", "name": "comfyui-core", "source": "registry"},
                            "expected_classes": [node_class],
                        }
                    ],
                },
            )

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "registry_lookup" not in digest:
                return {
                    "action": "call",
                    "tool": "registry_lookup",
                    "args": {"node_class": "KSampler"},
                }
            return {
                "action": "finish",
                "conclusion": "KSampler is owned by comfyui-core.",
                "evidence_ids": ["tool:registry_lookup-ksampler"],
                "uncertainty": "",
            }

        with mock.patch(
            "vibecomfy.executor.lookup_tools.registry_lookup",
            side_effect=fake_registry,
        ) as patched:
            trace, pack = stage.run_agent_research_stage(
                route="research",
                question=_EXPLICIT_QUESTION,
                spec=spec,
                search_fn=_fake_search,
                get_fn=_fake_get,
                judge_fn=judge,
            )

        assert patched.called
        assert calls == ["KSampler"]
        assert trace.final_verdict == "enough"
        decisions = [entry.decision for entry in pack.ledger.entries]
        assert stage.DECISION_REGISTRY in decisions
        # The stage uses the registry's canonical evidence id.
        assert "tool:registry_lookup-ksampler" in pack.artifacts
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_missing_required_query_is_typed_invalid_request(self, profile_dir: Path) -> None:
        """A search call without the required ``query`` is the registry's typed
        ``invalid_request`` — never a handler KeyError and never a stage
        failure — and the loop continues to a finish."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "invalid_request" not in digest:
                return {"action": "call", "tool": "hivemind_search", "args": {}}
            return {
                "action": "finish",
                "conclusion": "recorded the invalid search call",
                "evidence_ids": [],
                "uncertainty": "",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        entries = [e for e in pack.ledger.entries if e.decision == stage.DECISION_SEARCH]
        assert entries, "the invalid call must still be recorded in the ledger"
        assert entries[0].conclusion.startswith("invalid_request")
        assert entries[0].conclusion == entries[0].uncertainty  # typed, not silent
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_declared_search_args_reach_the_handler(self, profile_dir: Path) -> None:
        """The registry handler receives the agent's declared arguments
        (filters/cursor/limit/timeout) — the bespoke dispatch no longer drops
        them (P1-c routing fix)."""
        captured: dict[str, Any] = {}

        def recording_search(query: str, **kwargs: Any) -> ToolResult:
            captured["kwargs"] = kwargs
            return _fake_search(query, **kwargs)

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "hivemind_search →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {
                        "query": question,
                        "filters": {"source_type": "workflow"},
                        "cursor": "offset-5",
                        "limit": 2,
                        "timeout": 3,
                    },
                }
            return {
                "action": "finish",
                "conclusion": "declared arguments were honored",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=recording_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        assert captured["kwargs"]["filters"] == {"source_type": "workflow"}
        assert captured["kwargs"]["cursor"] == "offset-5"
        assert captured["kwargs"]["limit"] == 2
        assert captured["kwargs"]["timeout"] == 3
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_malformed_limit_is_typed_invalid_request(self, profile_dir: Path) -> None:
        """A malformed ``limit`` is the tool's typed ``invalid_request``
        (validation precedes any transport) — never a raise that fails the
        stage, and the loop continues to a finish."""
        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "invalid_request" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": question, "limit": "not-an-int"},
                }
            return {
                "action": "finish",
                "conclusion": "typed invalid limit",
                "evidence_ids": [],
                "uncertainty": "",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        entries = [e for e in pack.ledger.entries if e.decision == stage.DECISION_SEARCH]
        assert entries and entries[0].conclusion.startswith("invalid_request")
        assert pack.ledger.validate_references(set(pack.artifacts)) is None


# ── Acceptance 3: no full research result / workflow schema in the model request ─


class TestNoLegacyInjectionIntoModelRequest:
    def test_judgment_digest_contains_only_question_and_compact_evidence(
        self, profile_dir: Path
    ) -> None:
        """The digest handed to the agent contains the explicit question and
        compact tool evidence — never raw result bodies and never a
        workflow/graph schema dump."""
        captured: dict[str, Any] = {}

        def recording_judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            captured["question"] = question
            captured["digest"] = digest
            if "hivemind_search" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": question},
                }
            return {
                "action": "finish",
                "conclusion": "Use LoadAudio before the video model",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=recording_judge,
        )
        assert trace.status == "ok"
        digest = captured["digest"]
        assert _EXPLICIT_QUESTION in digest
        assert "hivemind:workflows:111" in digest
        # Raw hit bodies never enter the digest; no graph schema dump.
        assert "LoadAudio -> ConditioningCombine" not in digest
        assert '"nodes"' not in digest
        assert '"links"' not in digest

        # The built messages carry the same bounded, legacy-free content.
        messages = stage.build_agent_research_messages(
            question=_EXPLICIT_QUESTION,
            evidence_digest=digest,
            route="research",
        )
        all_text = " ".join(_all_strings(messages))
        assert _EXPLICIT_QUESTION in all_text
        assert '"nodes"' not in all_text

    def test_workflow_digest_line_communicates_semantics_not_payload(
        self, profile_dir: Path
    ) -> None:
        """A fetched WORKFLOW record's digest preview is the structured
        semantics line (class inventory, task/media, gates, url) — NOT the
        body prefix, which is a description followed by generated Python
        (Grok workflow-communication spec)."""
        captured: dict[str, Any] = {}

        def recording_judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            captured["digest"] = digest
            if "hivemind_get →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            return {
                "action": "finish",
                "conclusion": "done",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        def semantics_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            return ToolResult(
                tool_name="hivemind_get",
                status=ToolStatus.OK,
                result={
                    "evidence_id": evidence_id,
                    "source_type": "workflow",
                    "row": {
                        "id": "111",
                        "title": "MiniMax H3 I2V",
                        "kind": "workflow",
                        "body": (
                            "Description: Generates a video.\n"
                            "Python scratchpad source:\n"
                            "print('tens of KB of python')\n"
                            "Workflow semantics (rule-based):\n"
                            "node_types: [LoraLoader, KSampler]"
                        ),
                        "url": "https://raw.example.com/wf.json",
                        "metadata": {
                            "workflow_semantics": {
                                "task_type": "image_to_video",
                                "media_type": "video",
                                "node_class_multiset": {"LoraLoader": 2, "KSampler": 1},
                                "models": ["h3.safetensors"],
                                "promotion_gates": {"parseable_workflow": True},
                            }
                        },
                    },
                },
                evidence_ids=(evidence_id,),
            )

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=semantics_get,
            judge_fn=recording_judge,
        )
        assert trace.status == "ok"
        digest = captured["digest"]
        # Class inventory + gates + url are the communicated channel.
        assert "classes: LoraLoader×2, KSampler" in digest
        assert "task=image_to_video media=video" in digest
        assert "gates: parseable=True" in digest
        assert "https://raw.example.com/wf.json" in digest
        # The generated Python never appears; the raw body prefix is not the
        # preview channel for workflows.
        assert "tens of KB of python" not in digest
        assert "print('" not in digest
        assert len(digest) < 4_000

    def test_payload_never_enters_digest_even_when_artifact_stores_it(
        self, profile_dir: Path
    ) -> None:
        """A fetched workflow record may store its full row (including a
        50KB+ ``payload``) as the artifact, but the DIGEST must never
        stringify payload — the body/description/content preview only."""
        captured: dict[str, Any] = {}

        def recording_judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            captured["digest"] = digest
            if "hivemind_get →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            return {
                "action": "finish",
                "conclusion": "done",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        big_payload = '{"nodes": [' + ",".join('{"type": "KSampler"}' for _ in range(2000)) + "]}"

        def payload_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            return ToolResult(
                tool_name="hivemind_get",
                status=ToolStatus.OK,
                result={
                    "evidence_id": evidence_id,
                    "source_type": "workflow",
                    "row": {
                        "id": "111",
                        "title": "wf 111",
                        "body": "description text",
                        "kind": "workflow",
                        "payload": big_payload,
                        "has_workflow_json": True,
                    },
                },
                evidence_ids=(evidence_id,),
            )

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=payload_get,
            judge_fn=recording_judge,
        )
        assert trace.status == "ok"
        digest = captured["digest"]
        # The description preview is present; the 50KB payload is not.
        assert "description text" in digest
        assert "KSampler" not in digest
        assert big_payload[:200] not in digest
        assert len(digest) < 4_000
        # The artifact MAY keep the payload for the implement phase.
        artifact = pack.artifacts.get("hivemind_get:workflows:111")
        assert artifact is not None
        if isinstance(artifact.body, dict):
            assert artifact.body.get("payload") == big_payload

    def test_end_to_end_model_request_never_contains_legacy_or_graph(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Through the real run_executor integration, the model request built
        by the stage carries neither legacy research content nor the workflow
        graph."""
        from vibecomfy.executor import core as executor_core

        captured: dict[str, Any] = {"messages": None}

        def recording_turn(
            question: str,
            evidence_digest: str,
            *,
            route: str = "",
            model: str = "",
            effort: str | None = None,
            messages: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            built = messages or stage.build_agent_research_messages(
                question=question, evidence_digest=evidence_digest, route=route
            )
            # Capture the decision-turn messages on the first turn (before any
            # tool evidence exists), like the original single-turn fake.
            if captured["messages"] is None:
                captured["messages"] = built
            if "hivemind_search" not in evidence_digest:
                return {"action": "call", "tool": "hivemind_search", "args": {"query": question}}
            return {
                "action": "finish",
                "conclusion": "Use LoadAudio -> ConditioningCombine before WanImageToVideo",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
            }

        monkeypatch.setattr(executor_core, "run_classify_turn", lambda *a, **k: _research_plan())
        monkeypatch.setattr(
            executor_core,
            "run_reply_turn",
            lambda *a, **k: "Audio-conditioned Wan uses LoadAudio before the video model.",
        )
        # The stage dispatches through the ToolSpec registry, whose handlers
        # call the hivemind_tools module functions — patch those, not stage
        # attributes.
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(hivemind_tools, "hivemind_search", _fake_search)
        monkeypatch.setattr(hivemind_tools, "hivemind_get", _fake_get)
        monkeypatch.setattr(stage, "run_agent_research_turn", recording_turn)

        request = ExecutorRequest(
            query=_EXPLICIT_QUESTION,
            graph={"nodes": [{"id": 1, "type": "WanImageToVideo"}], "links": []},
            profile="default",
        )
        result = executor_core.run_executor(request)
        assert result.ok is True
        assert captured["messages"] is not None
        all_text = " ".join(_all_strings(captured["messages"]))
        assert _EXPLICIT_QUESTION in all_text
        # The attached workflow graph never enters the model request.
        assert "WanImageToVideo" not in all_text
        assert '"nodes"' not in all_text

    def test_stage_source_never_injects_research_result_into_prompt(self) -> None:
        """Source-level grep: the research result (Trace/EvidencePack) may feed
        only the evidence-pack capture — never the prompt/digest builders —
        and the stage never calls the legacy research engine."""
        source = Path(stage.__file__).read_text(encoding="utf-8")
        # The stage never invokes the legacy research phase.
        assert "run_research_phase" not in source
        for lineno, line in enumerate(source.splitlines(), start=1):
            if "legacy_result" in line:
                raise AssertionError(
                    f"agent_research_stage.py:{lineno}: legacy result content is still referenced"
                )


# ── REC-B: finish-with-zero-evidence prevention (P1-c) ───────────────────────


class TestFinishPrematureGuard:
    def test_finish_before_any_tool_call_is_finish_premature_refinement(self, profile_dir: Path) -> None:
        """P1-c: a finish with zero citable evidence_ids AND zero tool calls
        made is a malformed finish — the loop records the typed
        'finish_premature' marker and feeds it back as a refinement turn
        instead of accepting the ungrounded synthesis or auto-failing."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        judge_log: list[dict[str, Any]] = []

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            judge_log.append({"question": question, "digest": digest})
            if "finish_premature" not in digest:
                return {
                    "action": "finish",
                    "conclusion": "I already know the answer",
                    "evidence_ids": [],
                    "uncertainty": "",
                }
            if "hivemind_search →" not in digest:
                return {"action": "call", "tool": "hivemind_search", "args": {"query": question}}
            return {
                "action": "finish",
                "conclusion": "Use LoadAudio -> ConditioningCombine before WanImageToVideo",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        # Neither auto-failed nor accepted: the loop recovered and finished.
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        # The premature finish was recorded as a typed refinement turn.
        premature = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_FINISH_PREMATURE
        ]
        assert len(premature) == 1
        assert "finish_premature" in premature[0].conclusion
        assert premature[0].evidence_ids == ()
        # The agent saw the nudge in the digest before calling a tool.
        assert "finish_premature" in judge_log[1]["digest"]
        # No synthesize entry for the premature finish; the final synthesis
        # cites real evidence returned by the tool.
        synth = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_SYNTHESIZE
        ]
        assert len(synth) == 1
        assert synth[0].evidence_ids == ("hivemind:workflows:111",)
        # One iteration per decision: premature-finish, search, finish.
        assert len(trace.iterations) == 3
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_finish_citing_lead_id_after_fetch_aliases_to_get_id(self, profile_dir: Path) -> None:
        """Grok citation contract: after fetching table:id, citing EITHER
        spelling (lead ``hivemind:table:id`` OR namespaced
        ``hivemind_get:table:id``) counts as citing that fetch — the finish
        must NOT loop on the lead-spelling citation."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        state = {"judge_calls": 0}

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            state["judge_calls"] += 1
            if state["judge_calls"] == 1:
                return {"action": "call", "tool": "hivemind_get", "args": {"evidence_id": "hivemind:workflows:111"}}
            # Cite the LEAD id — must alias to the fetched get id.
            return {
                "action": "finish",
                "conclusion": "The record answers the question.",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        # No premature rejection: the lead id aliased to the fetched get id.
        assert not any(
            entry.decision == stage.DECISION_FINISH_PREMATURE
            for entry in pack.ledger.entries
        )
        # The stored synthesis citation is normalized to the canonical get id.
        synth = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_SYNTHESIZE
        ]
        assert len(synth) == 1
        assert synth[0].evidence_ids == ("hivemind_get:workflows:111",)
        assert trace.citations == ("hivemind_get:workflows:111",)

    def test_finish_after_fetch_but_no_citation_is_premature_refinement(self, profile_dir: Path) -> None:
        """R5c: a finish that FETCHED records but cites NONE is premature —
        the agent gathered citable evidence and ignored it (observed live: 7
        fetched records, then a zero-citation finish claiming "no distillation
        LoRA exists" while its own fetches named the RAVEN/Turbo LoRAs)."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        judge_log: list[dict[str, Any]] = []

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            judge_log.append({"digest": digest})
            if "hivemind_get →" not in digest:
                return {"action": "call", "tool": "hivemind_get", "args": {"evidence_id": "hivemind:workflows:111"}}
            if "finish_premature" not in digest:
                return {
                    "action": "finish",
                    "conclusion": "No distillation LoRA exists in the corpus.",
                    "evidence_ids": [],
                    "uncertainty": "none found",
                }
            return {
                "action": "finish",
                "conclusion": "The RAVEN Streaming LoRA is the distillation LoRA.",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        premature = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_FINISH_PREMATURE
        ]
        assert len(premature) == 1
        assert "fetched records this turn but cited none" in premature[0].conclusion
        synth = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_SYNTHESIZE
        ]
        assert len(synth) == 1
        assert synth[0].evidence_ids == ("hivemind_get:workflows:111",)
        assert trace.citations == ("hivemind_get:workflows:111",)
        assert pack.ledger.validate_references(set(pack.artifacts)) is None


    def test_repeated_premature_finishes_stay_bounded_and_exhausted(self, profile_dir: Path) -> None:
        """P1-c: an agent that keeps finishing without any tool call consumes
        refinement turns (never accepted, never auto-failed) and the loop
        still terminates bounded at max_turns with an exhausted trace and no
        synthesize entry — the executor gate can fail closed on it."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def always_premature(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            del question, digest, messages
            return {
                "action": "finish",
                "conclusion": "no tool calls",
                "evidence_ids": [],
                "uncertainty": "",
            }

        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=always_premature,
            max_turns=3,
        )
        assert trace.status == "exhausted"
        assert trace.final_verdict == "refine"
        premature = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_FINISH_PREMATURE
        ]
        assert len(premature) == 3
        synth = [
            entry for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_SYNTHESIZE
        ]
        assert synth == []
        assert trace.citations == ()


class TestModelFamilyBriefNudge:
    def test_named_model_families_nudge_hivemind_search_filters(self) -> None:
        """REC-A/REC-B coordination: when the classifier brief names model
        families, the decision-turn messages instruct the agent to pass them
        as hivemind_search filters and prefer family-matching hits — a soft
        nudge, never a hard injected filter."""
        messages = stage.build_agent_research_messages(
            question=_EXPLICIT_QUESTION,
            evidence_digest="Remaining budget: 3 searches, 6 fetches.",
            route="research",
            research_brief=(
                "Research brief:\n"
                "- Search directions: LTXV upscaling patterns\n"
                "- Model families: LTXV, Wan\n"
                "- Source preferences: workflows"
            ),
        )
        all_text = " ".join(_all_strings(messages))
        assert "Model-family focus" in all_text
        assert "LTXV, Wan" in all_text
        assert '"model_family"' in all_text

    def test_no_model_families_named_means_no_nudge(self) -> None:
        """Without a named family in the brief there is no filter nudge — the
        agent keeps full freedom over search args."""
        messages = stage.build_agent_research_messages(
            question=_EXPLICIT_QUESTION,
            evidence_digest="Remaining budget: 3 searches.",
            route="research",
            research_brief="Research brief:\n- Search directions: generic patterns",
        )
        all_text = " ".join(_all_strings(messages))
        assert "Model-family focus" not in all_text
        assert '"model_family"' not in all_text


class TestEmptyTitleHitWhitespaceContract:
    """R4: a Discord hit with empty title AND body (embeds, image-only
    messages) used to leak a trailing ``" | "`` into the projected search
    conclusion; ``EvidenceLedgerEntry`` rejected the whitespace and the
    stage-wide except flipped the whole phase to ``failed``, discarding
    every artifact already gathered (observed: 4 executed calls, 32 evidence
    artifacts lost to one trailing-space ValueError)."""

    def _search_with_empty_title_hits(self) -> ToolResult:
        hits = [
            {
                "evidence_id": "hivemind:unified_feed:1",
                "source_type": "discord",
                "title": "",
                "body": "",
                "url": "",
            },
            {
                "evidence_id": "hivemind:unified_feed:2",
                "source_type": "discord",
                "title": "Real title",
                "body": "real body",
                "url": "",
            },
            {
                "evidence_id": "hivemind:unified_feed:3",
                "source_type": "discord",
                "title": "",
                "body": "",
                "url": "",
            },
        ]
        return ToolResult(
            tool_name="hivemind_search",
            status=ToolStatus.OK,
            result={
                "query": "q",
                "count": 3,
                "hits": hits,
                "next_cursor": None,
                "has_more": False,
            },
            evidence_ids=tuple(hit["evidence_id"] for hit in hits),
        )

    def test_empty_title_hits_produce_clean_ledger_conclusion(self, profile_dir: Path) -> None:
        """The projected conclusion skips empty rows and never carries
        leading/trailing whitespace, so ledger construction succeeds."""
        from vibecomfy.executor.evidence_pack import EvidenceLedgerEntry
        from vibecomfy.executor.tool_specs import TOOL_SPEC_BY_NAME, project_tool_evidence

        result = self._search_with_empty_title_hits()
        _artifacts, entry, _digest = project_tool_evidence(
            TOOL_SPEC_BY_NAME["hivemind_search"], {"query": "q"}, result, None
        )
        assert entry["conclusion"] == "3 hit(s): Real title"
        assert entry["conclusion"] == entry["conclusion"].strip()
        # The exact construction that used to crash the phase.
        ledger = EvidenceLedgerEntry(
            decision=entry["decision"],
            conclusion=entry["conclusion"],
            evidence_ids=entry["evidence_ids"],
            uncertainty="",
        )
        assert ledger.conclusion.startswith("3 hit(s)")

    def test_phase_survives_one_bad_projection_and_preserves_prior_evidence(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single tool call whose evidence projection fails degrades to a
        typed refusal — the phase keeps its ``ok`` status, prior artifacts
        survive, and the agent can still finish with later evidence.  The
        stage-wide except must never convert one malformed row into
        ``failed`` for the whole run."""
        real_projector = stage.project_tool_evidence

        def flaky_projector(spec, args, result, session):
            if spec.name == "hivemind_search":
                raise ValueError("corpus row violates compact contract")
            return real_projector(spec, args, result, session)

        monkeypatch.setattr(stage, "project_tool_evidence", flaky_projector)

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "hivemind_search →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": question},
                }
            if "hivemind_get →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            return {
                "action": "finish",
                "conclusion": "Use the workflow",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        assert trace.citations == ("hivemind_get:workflows:111",)
        # The search executed (counted) but its evidence projection failed;
        # the get executed and recorded normally.
        assert trace.executed_tool_calls == 2
        assert trace.evidence_artifact_count >= 1
        assert any("evidence projection failed" in w for w in trace.warnings)
        assert pack.ledger.validate_references(set(pack.artifacts)) is None


class TestDuplicateFetchGuard:
    """R5a: a hivemind_get of an evidence ID already fetched this turn does
    NOT re-hit the network or burn a fetch slot — it replays the cached
    artifact as a successful get so the agent reads the content it asked for
    and can proceed.  A bare refusal (nothing to read) previously made the
    agent retry the same fetch and burn the whole turn budget."""

    def test_second_fetch_of_same_id_replays_cached_record(self, profile_dir: Path) -> None:
        state = {"judge_calls": 0, "fetches": 0}

        def recording_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            state["fetches"] += 1
            return _fake_get(evidence_id, **kwargs)

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            state["judge_calls"] += 1
            if state["judge_calls"] == 1:
                # Real network fetch of record 111.
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            if state["judge_calls"] == 2:
                # Re-fetch the SAME id: must be served from the cache, not
                # re-hit the network.
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            return {
                "action": "finish",
                "conclusion": "Use LoadAudio -> ConditioningCombine",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            spec=spec,
            route="research",
            question=_EXPLICIT_QUESTION,
            search_fn=_fake_search,
            get_fn=recording_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        # The duplicate fetch was served from cache: only ONE network get.
        assert state["fetches"] == 1
        # No bare refusal was needed (cache replay, not a dead-end refusal).
        assert not any(
            "already fetched" in call.get("conclusion", "")
            for it in trace.iterations
            for call in it.tool_calls
        )
        # The cached replay reached the digest as an ok get with content.
        assert any(
            "workflow record hivemind:workflows:111" in call.get("conclusion", "")
            for it in trace.iterations
            for call in it.tool_calls
        )

    def test_repeated_fetch_of_same_id_is_silent_cache_hit(self, profile_dir: Path) -> None:
        """Minimal-budget plan: fetches are free, so a repeat hivemind_get of
        an already-fetched id is a SILENT cache hit — no refusal, no special
        status, no second network GET.  The agent can re-read freely."""
        state = {"judge_calls": 0, "fetches": 0}

        def recording_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            state["fetches"] += 1
            return _fake_get(evidence_id, **kwargs)

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            state["judge_calls"] += 1
            if state["judge_calls"] <= 4:
                # fetch → re-fetch → re-fetch → re-fetch: all must be served
                # from cache after the first (no refusals, no refusals).
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            return {
                "action": "finish",
                "conclusion": "done",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            spec=spec,
            route="research",
            question=_EXPLICIT_QUESTION,
            search_fn=_fake_search,
            get_fn=recording_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        # Only the FIRST call hit the network; every repeat was cached.
        assert state["fetches"] == 1
        conclusions = [
            str(call.get("conclusion") or "")
            for it in trace.iterations
            for call in it.tool_calls
        ]
        # Zero refusals — the cache hit is silent and non-punishing.
        assert not any("already fetched" in c for c in conclusions)
        # Cached gets project normally: the record is visible (title in the
        # conclusion line; the full body preview lives in the digest).
        assert any("full record 111" in c for c in conclusions)
        assert any("cached record hivemind_get:workflows:111" in c for c in conclusions)

    def test_last_fetch_gets_expanded_digest_window(self, profile_dir: Path) -> None:
        """Grok rule: the most recently fetched record's preview window is
        much larger than the default 320-char cap — enough to name class
        types/wiring — while the digest total stays bounded."""
        judge_log: list[dict[str, Any]] = []

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            judge_log.append({"digest": digest})
            if "hivemind_get →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:111"},
                }
            return {
                "action": "finish",
                "conclusion": "done",
                "evidence_ids": ["hivemind_get:workflows:111"],
                "uncertainty": "low",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            spec=spec,
            route="research",
            question=_EXPLICIT_QUESTION,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        last_digest = judge_log[-1]["digest"]
        # The expanded window shows the record's TAIL (beyond 320 chars),
        # which the old 320-char cap truncated.
        assert "END-OF-EXPANDED-RECORD" in last_digest
        assert len(last_digest) < 4_000

    def test_failed_fetch_of_id_is_retryable(self, profile_dir: Path) -> None:
        """A get that resolves to NO row is NOT marked fetched — a genuine
        miss can be retried (the digest refuses only duplicates of fetched
        records)."""
        judge_log: list[dict[str, Any]] = []

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            judge_log.append({"digest": digest})
            if "hivemind_get →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_get",
                    "args": {"evidence_id": "hivemind:workflows:999"},
                }
            return {
                "action": "finish",
                "conclusion": "no record; answer from search titles",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "record 999 absent",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            spec=spec,
            route="research",
            question=_EXPLICIT_QUESTION,
            search_fn=_fake_search,
            get_fn=lambda evidence_id, **kw: ToolResult(
                tool_name="hivemind_get",
                status=ToolStatus.NO_RESULTS,
                result={},
                diagnostics=(),
            ),
            judge_fn=judge,
        )
        assert trace.status == "ok"
        all_conclusions = " ".join(
            str(call.get("conclusion") or "")
            for it in trace.iterations
            for call in it.tool_calls
        )
        assert "already fetched" not in all_conclusions


class TestSourcePreferenceBriefNudge:
    def test_source_preferences_translate_to_source_type_hint(self) -> None:
        """When the classifier brief names source preferences, the decision
        messages translate them into the concrete hivemind_search source_type
        filter — 'workflows' → exact graph precedent, 'messages' → community
        knowledge."""
        brief = (
            "- Source preferences: workflows, messages\n"
            "- Known graph context: empty graph"
        )
        messages = stage.build_agent_research_messages(
            question=_EXPLICIT_QUESTION,
            evidence_digest="(digest)",
            route="research",
            research_brief=brief,
        )
        user_text = messages[-1]["content"]
        assert 'filters={"source_type": "<tier>"}' in user_text
        assert '"workflow" when you need an exact graph precedent' in user_text
        assert '"discord" when you need community knowledge' in user_text

    def test_no_source_preferences_means_no_nudge(self) -> None:
        messages = stage.build_agent_research_messages(
            question=_EXPLICIT_QUESTION,
            evidence_digest="(digest)",
            route="research",
            research_brief="",
        )
        user_text = messages[-1]["content"]
        assert "Source preferences:" not in user_text


class TestResearchDecisionRetryAndTelemetry:
    """R4d: the research decision seam uses the provider's typed error and
    corrective retry — a malformed/empty model decision is retried (up to 3
    attempts, never past the deadline) instead of failing the whole phase,
    and the recorded model attempt is flipped to failure instead of lying as
    a "success" (observed: prose with finish_reason=stop killing the phase;
    memo without the error; reply fabricating "ran out of time")."""

    def _provider(self, monkeypatch: pytest.MonkeyPatch, responses: list[dict[str, Any]]):
        from vibecomfy.comfy_nodes.agent import provider as provider_mod

        calls: list[dict[str, Any]] = []
        consumed = list(responses)

        def fake_run_model_turn(*_args, **_kwargs):
            calls.append(dict(_kwargs))
            return consumed.pop(0)

        monkeypatch.setattr(provider_mod, "run_model_turn", fake_run_model_turn)
        return provider_mod, calls

    def test_seam_malformed_prose_raises_typed_error_with_preview_and_failure_attempt(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prose (non-JSON) content raises MalformedModelJSON carrying the
        redacted raw preview + parse reason, and the model attempt evidence
        is flipped to failure — the provider must not record a "success" for
        output the seam could not parse."""
        provider_mod, _calls = self._provider(
            monkeypatch,
            [{"content": "Let me search for that, one moment", "model_attempts": [
                {"attempt": 1, "outcome": "success", "failure_type": "None",
                 "phase": "research_stage", "requested_model": "m", "resolved_model": "m",
                 "transport": "arnold", "adapter": "hermes", "endpoint": "e",
                 "finish_reason": "stop", "token_usage": {}},
            ]}],
        )
        from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON

        with pytest.raises(MalformedModelJSON) as raised:
            stage.run_agent_research_turn(
                _EXPLICIT_QUESTION,
                "digest",
                route="research",
                model="deepseek-v4-pro",
            )
        exc = raised.value
        assert isinstance(exc, ValueError)  # typed subclass, backward compatible
        assert "malformed JSON" in str(exc) or "non_json" in str(exc)
        assert exc.raw_response_preview and "Let me search" in exc.raw_response_preview
        assert exc.parse_reason == "non_json_content"

    def test_seam_empty_content_is_empty_response_reason(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Blank content maps to parse_reason empty_response (distinct from
        prose/non-JSON) so retry telemetry can tell the cases apart."""
        provider_mod, _calls = self._provider(monkeypatch, [{"content": ""}])
        from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON

        with pytest.raises(MalformedModelJSON) as raised:
            stage.run_agent_research_turn(
                _EXPLICIT_QUESTION,
                "digest",
                route="research",
                model="deepseek-v4-pro",
            )
        assert raised.value.parse_reason == "empty_response"
        assert raised.value.raw_response_preview is None or raised.value.raw_response_preview == ""

    def test_seam_schema_invalid_json_is_missing_required_fields(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid JSON that violates the decision schema (call without a tool
        name) maps to missing_required_fields — retryable, distinct reason."""
        provider_mod, _calls = self._provider(
            monkeypatch, [{"content": '{"action": "call"}'}]
        )
        from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON

        with pytest.raises(MalformedModelJSON) as raised:
            stage.run_agent_research_turn(
                _EXPLICIT_QUESTION,
                "digest",
                route="research",
                model="deepseek-v4-pro",
            )
        assert raised.value.parse_reason == "missing_required_fields"

    def test_seam_success_records_attempts(self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid decision passes through unchanged and the successful
        attempt is recorded (parity with the classify/reply seam)."""
        from vibecomfy.comfy_nodes.agent.runtime import (
            begin_model_attempt_capture,
            end_model_attempt_capture,
            snapshot_model_attempt_capture,
        )
        from vibecomfy.comfy_nodes.agent import provider as provider_mod

        captured: dict[str, Any] = {}
        attempts = [{"attempt": 1, "outcome": "success", "failure_type": "None",
                     "phase": "research_stage", "requested_model": "m", "resolved_model": "m",
                     "transport": "arnold", "adapter": "hermes", "endpoint": "e",
                     "finish_reason": "stop", "token_usage": {}}]

        def fake_run_model_turn(*_args, **_kwargs):
            return {"content": '{"action": "finish", "conclusion": "done", '
                               '"evidence_ids": [], "uncertainty": "", "refine_question": null}',
                    "model_attempts": attempts}

        monkeypatch.setattr(provider_mod, "run_model_turn", fake_run_model_turn)
        token = begin_model_attempt_capture()
        try:
            decision = stage.run_agent_research_turn(
                _EXPLICIT_QUESTION,
                "digest",
                route="research",
                model="deepseek-v4-pro",
            )
            captured["attempts"] = snapshot_model_attempt_capture()
        finally:
            end_model_attempt_capture(token)
        assert decision["action"] == "finish"
        assert captured["attempts"], "successful attempt must be recorded"

    def test_stage_retries_malformed_decision_and_recovers(
        self, profile_dir: Path
    ) -> None:
        """A malformed first decision is corrected by the appended retry
        message; the phase completes ok with a recovery warning — the exact
        run-D failure no longer kills the phase after 3 tool calls."""
        from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON

        judge_calls: list[list[dict[str, Any]]] = []

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            judge_calls.append(list(messages or []))
            if len(judge_calls) == 1:
                # First attempt: malformed (run-D failure). The retry must
                # append the corrective message and re-call.
                raise MalformedModelJSON(
                    "agent research decision: malformed JSON",
                    raw_response="Here is what I found, in prose",
                    parse_reason="non_json_content",
                )
            if "hivemind_search →" not in digest:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": question},
                }
            return {
                "action": "finish",
                "conclusion": "Use LoadAudio -> ConditioningCombine",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
            }

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert trace.status == "ok"
        assert trace.final_verdict == "enough"
        # Calls: malformed attempt + corrective retry + the next decision
        # turn (finish). The retry message is what the SECOND call saw.
        assert len(judge_calls) == 3
        retry_message = judge_calls[1][-1]
        assert retry_message["role"] == "system"
        assert "research decision" in retry_message["content"]
        assert "Previous response preview" in retry_message["content"]
        assert "prose" in retry_message["content"]
        assert any("corrective retry" in w for w in trace.warnings)
        assert pack.ledger.validate_references(set(pack.artifacts)) is None

    def test_stage_never_retries_after_deadline(
        self, profile_dir: Path
    ) -> None:
        """The corrective retry checks the wall-clock deadline before every
        attempt: after the deadline passes, the stage raises instead of
        starting another provider call."""
        from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON

        clock = {"t": 100.0}
        judge_calls = 0

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            nonlocal judge_calls
            judge_calls += 1
            # The in-flight first attempt overruns the deadline (deadline is
            # started + 1s = 101.0): the retry check must refuse to start
            # another provider call.
            clock["t"] = 200.0
            raise MalformedModelJSON(
                "agent research decision: malformed JSON",
                raw_response="still prose",
                parse_reason="non_json_content",
            )

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
            deadline_seconds=1.0,
            now_fn=lambda: clock["t"],
        )
        # First attempt ran (before deadline), the deadline passed, no retry.
        assert judge_calls == 1
        assert trace.status == "failed"
        assert trace.error and "MalformedModelJSON" in trace.error
        assert "raw response preview" in trace.error
        assert "prose" in trace.error

    def test_stage_retry_exhaustion_fails_with_preview_and_memo_error(
        self, profile_dir: Path
    ) -> None:
        """Three consecutive malformed decisions exhaust retries → typed
        failed trace whose error string carries the bounded raw preview, and
        the C5 memo exposes research_error so the reply cannot invent a
        timeout story."""
        from vibecomfy.comfy_nodes.agent.provider import MalformedModelJSON
        from vibecomfy.executor import core as executor_core

        judge_calls = 0

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            nonlocal judge_calls
            judge_calls += 1
            raise MalformedModelJSON(
                "agent research decision: malformed JSON",
                raw_response="final prose failure",
                parse_reason="non_json_content",
            )

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert judge_calls == 3  # 1 + 2 corrective retries
        assert trace.status == "failed"
        assert trace.final_verdict == "failed"
        assert "MalformedModelJSON" in trace.error
        assert "final prose failure" in trace.error
        # The memo carries the real error on failed traces (failure-only key).
        memo = executor_core._research_decision_memo(trace, diagnostics=())
        assert memo["research_status"] == "failed"
        assert memo["research_error"]
        assert "final prose failure" in memo["research_error"]

    def test_stage_never_retries_provider_errors(self, profile_dir: Path) -> None:
        """AuthError/ProviderError/TimeoutError are transport failures, not
        model-output problems: the corrective retry must never mask them."""
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        judge_calls = 0

        def judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            nonlocal judge_calls
            judge_calls += 1
            raise ProviderError("provider offline")

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question=_EXPLICIT_QUESTION,
            spec=spec,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=judge,
        )
        assert judge_calls == 1  # ProviderError is never retried
        assert trace.status == "failed"
        assert "ProviderError" in trace.error

    def test_memo_ok_trace_has_no_research_error_key(self, profile_dir: Path) -> None:
        """research_error is failure-only: successful-memo dict equality
        assertions elsewhere stay stable."""
        from vibecomfy.executor import core as executor_core
        from vibecomfy.executor.agent_research_stage import AgentResearchTrace

        trace = AgentResearchTrace(
            route="research",
            question="q",
            iterations=(),
            final_verdict="enough",
            summary="s",
            citations=(),
            uncertainty="",
            status="ok",
            elapsed_seconds=1.0,
        )
        memo = executor_core._research_decision_memo(trace, diagnostics=())
        assert "research_error" not in memo
        assert memo["research_status"] == "ok"
