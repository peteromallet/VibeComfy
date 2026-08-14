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
    """Deterministic Hivemind get returning the full record for a hit id."""
    row_id = evidence_id.rsplit(":", 1)[-1]
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
                "body": "expanded record body with wiring detail",
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
        # The digest the agent saw carried only compact evidence, never raw
        # bodies (RAW body markers absent).
        for entry in judge_log:
            assert "expanded record body" not in entry["digest"]

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
        assert trace.status == "ok"
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

    def test_phase_allowlist_refuses_implement_tools(self, profile_dir: Path) -> None:
        """An agent that tries an implement-phase tool gets a typed refusal —
        the call is never executed and the ledger records the refusal."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def out_of_phase(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            if "allowlist" not in digest:
                return {
                    "action": "call",
                    "tool": "node_schema",
                    "args": {"node_class": "KSampler"},
                }
            return {
                "action": "finish",
                "conclusion": "no research evidence gathered",
                "evidence_ids": [],
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

    def test_registry_lookup_is_agent_callable(self, profile_dir: Path) -> None:
        """registry_lookup is a research-phase tool the agent may choose."""
        from vibecomfy.executor.lookup_tools import registry_lookup as _real_registry_lookup

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
                "evidence_ids": ["tool:registry-lookup-KSampler"],
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
        assert "tool:registry-lookup-KSampler" in pack.artifacts


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
            captured["messages"] = built
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
        monkeypatch.setattr(stage, "_default_hivemind_search", _fake_search)
        monkeypatch.setattr(stage, "_default_hivemind_get", _fake_get)
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
