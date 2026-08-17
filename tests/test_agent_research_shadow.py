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
4. Effort budgets (3 searches / 6 fetches / 1 registry / ~90s) and the phase
   deadline terminate the loop deterministically.

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
    """Deterministic Hivemind get returning the full record for a hit id.

    The workflow record carries a real workflow JSON (UI shape) in
    ``payload.workflow_json`` so the stage serves its IR surface lens (batch
    13) — the raw ``body`` below stays in the evidence artifact only.
    """
    row_id = evidence_id.rsplit(":", 1)[-1]
    # The served surface lens is deliberately longer than the digest's
    # record-preview limit (the long widget value below) so tests can prove
    # the digest carries a BOUNDED preview of the served lens (head present,
    # marker absent) — never the full lens and never the raw source body.
    lens_tail = "END-OF-SURFACE-LENS"
    body = (
        "expanded record body with wiring detail — the exact socket/terminal "
        "pattern and preserved settings for the audio-conditioned Wan chain. "
        + ("x" * 400)
        + " END-OF-EXPANDED-RECORD"
    )
    workflow_json = {
        "last_node_id": 2,
        "nodes": [
            {
                "id": 1,
                "type": "LoadAudio",
                "pos": [0, 0],
                "size": [300, 100],
                "widgets_values": [("a" * 400) + lens_tail],
                "outputs": [{"name": "AUDIO", "type": "AUDIO", "links": [2]}],
            },
            {
                "id": 2,
                "type": "ConditioningCombine",
                "pos": [400, 0],
                "size": [300, 100],
                "widgets_values": [],
                "inputs": [{"name": "conditioning_1", "type": "CONDITIONING", "link": 2}],
                "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": None}],
            },
        ],
        "links": [[2, 1, 0, 2, 0, "AUDIO"]],
        "groups": [],
    }
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
                "payload": {"workflow_json": workflow_json},
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
        # Batch 13: the fetch digest serves the IR surface lens of the
        # workflow record (the Python view), bounded — head present, tail
        # absent — while the raw source body stays in the evidence artifact
        # only and never enters the digest.
        get_digest = judge_log[-1]["digest"]
        assert "loadaudio = LoadAudio(" in get_digest
        assert "END-OF-SURFACE-LENS" not in get_digest
        assert "expanded record body" not in get_digest
        assert "END-OF-EXPANDED-RECORD" not in get_digest

    def test_budget_exhaustion_terminates_with_refine_verdict(
        self, profile_dir: Path
    ) -> None:
        """An agent that never finishes still terminates (bounded), leaving a
        refine verdict and a recorded trace."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def always_search(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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
        )
        # P1-a: a loop that stops without an agent finish (max-turns here) is
        # "exhausted", never "ok" — the executor fails closed on it.
        assert trace.status == "exhausted"
        assert trace.final_verdict == "refine"
        # Exactly the search budget was consumed by successful agent-chosen
        # calls; every later call was a typed refusal (visible to the agent)
        # and the loop still terminated bounded at max_turns.
        ok_searches = [
            it
            for it in trace.iterations
            if it.tool_calls and it.tool_calls[0]["tool"] == "hivemind_search"
            and it.tool_calls[0]["status"] == "ok"
        ]
        refused = [
            it
            for it in trace.iterations
            if it.tool_calls and it.tool_calls[0]["status"] == "refused"
        ]
        assert len(ok_searches) == stage.TOOL_SEARCH_BUDGET
        assert refused, "exhausted search calls must be recorded as typed refusals"
        assert len(trace.iterations) == stage._MAX_TURNS
        assert "search budget exhausted" in " ".join(trace.warnings)
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
