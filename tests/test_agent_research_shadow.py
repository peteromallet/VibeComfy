"""H01 — Agent-owned research in shadow/dual-evaluation mode.

Covers the four H01 acceptance criteria:

1. The shadow result cannot alter route, graph, reply, or queue decisions —
   the legacy path output stays byte-identical whether the shadow succeeds
   or fails.
2. The agent trace proves an explicit question and an enough/refine judgment
   (recorded in the F01 evidence ledger).
3. No full legacy result or workflow schema dump is injected into the model
   request (behavioral capture + source grep).
4. The dual report compares evidence coverage, citation validity, and
   lifecycle assertions; the headless artifact writer persists the shadow
   report and BOTH evidence packs.

All model calls, Hivemind tools, and the legacy research phase are faked and
deterministic — no network, no ComfyUI boot, no Arnold imports.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Callable
from unittest import mock

import pytest

from vibecomfy.executor import agent_research_stage as stage
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    Report,
)
from vibecomfy.executor.profiles import AgentSpecShape, set_profile_override_dir
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus


class _LegacyResult:
    """Duck-typed stand-in for the deleted legacy research-result contract.

    The legacy ``ResearchResult`` class was removed by the agent-judgment
    rework (D02); the shadow/dual-evaluation seam consumes this shape via
    ``getattr`` and ``Report`` requires a ``to_dict()``-bearing research
    result, so the fixture keeps a minimal local replica for test patching.
    """

    def __init__(
        self,
        summary: str = "",
        sources: tuple = (),
        warnings: tuple = (),
        community_summary: str = "",
    ) -> None:
        self.summary = summary
        self.sources = sources
        self.warnings = warnings
        self.community_summary = community_summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "sources": list(self.sources),
        }

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
_REFINED_QUESTION = "Which LoadAudio node chain produces audio-conditioned Wan video?"


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


def _adapt_plan() -> ClassifyDecision:
    """Adapt classifier plan (research + implement) with a change goal."""
    return ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        effort="medium",
        plan_summary="adapt graph to add audio conditioning",
        route="adapt",
        task="edit_graph",
        research_goal=_EXPLICIT_QUESTION,
        change_goal="add audio conditioning to the Wan video graph",
        intent="edit",
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


def _judge(judge_log: list[dict[str, Any]]) -> Callable[[str, str], dict[str, Any]]:
    """Synthesize/enough judgment: refine once, then enough on the refined q."""

    def judge(question: str, digest: str) -> dict[str, Any]:
        judge_log.append({"question": question, "digest": digest})
        if "LoadAudio" in question:
            return {
                "conclusion": "Use LoadAudio -> ConditioningCombine before WanImageToVideo",
                "evidence_ids": ["hivemind:workflows:111", "hivemind_get:workflows:111"],
                "uncertainty": "low",
                "enough": True,
                "refine_question": None,
            }
        return {
            "conclusion": "evidence too broad; need audio-conditioned Wan specifics",
            "evidence_ids": [],
            "uncertainty": "medium",
            "enough": False,
            "refine_question": _REFINED_QUESTION,
        }

    return judge


def _raising_judge(question: str, digest: str) -> dict[str, Any]:
    raise RuntimeError("shadow judge crashed")


def _fake_classify_research_only(*args: Any, **kwargs: Any) -> ClassifyDecision:
    return _research_plan()


def _fake_classify_adapt(*args: Any, **kwargs: Any) -> ClassifyDecision:
    return _adapt_plan()


def _fake_reply(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    return "Audio-conditioned Wan uses LoadAudio before the video model."


def _fake_legacy_research(query: str, **kwargs: Any) -> _LegacyResult:
    """Fake legacy deterministic research with distinctive marker text."""
    return _LegacyResult(
        summary=f"Deterministic research for: {query}",
        sources=(
            {
                "source": "object_info",
                "kind": "node",
                "title": "KSampler",
                "class_type": "KSampler",
                "description": "K-Sampler node for ComfyUI",
                "pack": "core",
            },
        ),
        warnings=(),
    )


def _fake_edit_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "graph": {"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
        "message": "Candidate ready.",
        "graph_unchanged": False,
        "outcome": {"kind": "candidate"},
        "apply_eligibility": {"applyable": True},
        "session_id": "sess-h01",
        "turn_id": "0001",
    }


def _canonical_bytes(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


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


# ── Acceptance 1: shadow cannot alter route/graph/reply/queue decisions ──────


class LegacyShadowCannotAlterDecisions:
    def test_research_route_output_byte_identical_shadow_ok_vs_failed(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A shadow success vs a shadow failure leaves the legacy path output
        byte-identical (route/graph/reply unchanged; shadow invisible on the
        legacy wire)."""
        from vibecomfy.executor import core as executor_core

        monkeypatch.setenv("VIBECOMFY_RESEARCH_SHADOW", "1")
        monkeypatch.setattr(executor_core, "run_classify_turn", _fake_classify_research_only)
        monkeypatch.setattr(executor_core, "run_reply_turn", _fake_reply)
        monkeypatch.setattr(executor_core, "run_research_phase", _fake_legacy_research)
        # The real C1 stage runs inside run_executor with its default tool and
        # judgment seams, so the module-level defaults must be patched.
        monkeypatch.setattr(stage, "_default_hivemind_search", _fake_search)
        monkeypatch.setattr(stage, "_default_hivemind_get", _fake_get)

        request = ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default")

        monkeypatch.setattr(stage, "_default_judge_fn", lambda spec: _judge([]))
        result_ok = executor_core.run_executor(request)
        assert getattr(result_ok.report.research, "research_shadow").trace.status == "ok"

        monkeypatch.setattr(stage, "_default_judge_fn", lambda spec: _raising_judge)
        result_failed = executor_core.run_executor(request)
        shadow_failed = getattr(result_failed.report.research, "research_shadow")
        assert shadow_failed.trace.status == "failed"

        assert _canonical_bytes(result_ok.to_dict()) == _canonical_bytes(result_failed.to_dict())
        # The shadow never appears on the legacy wire (it rides as a private
        # attribute, not in any serialized payload).
        assert "research_shadow" not in _canonical_bytes(result_ok.to_dict())
        # Legacy behavioral outputs are identical.
        assert result_ok.reply == result_failed.reply
        assert result_ok.graph == result_failed.graph
        assert result_ok.to_dict()["route"] == "research"
        assert result_ok.report.research is not None

    def test_adapt_route_implement_payload_identical_shadow_ok_vs_failed(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On the adapt route the implement payload (the queue-relevant input
        built from LEGACY research) is byte-identical whether the shadow
        succeeds or fails."""
        from vibecomfy.executor import core as executor_core

        monkeypatch.setenv("VIBECOMFY_RESEARCH_SHADOW", "1")
        captured: dict[str, Any] = {"payloads": []}
        monkeypatch.setattr(executor_core, "run_classify_turn", _fake_classify_adapt)
        monkeypatch.setattr(executor_core, "run_reply_turn", _fake_reply)
        monkeypatch.setattr(executor_core, "run_research_phase", _fake_legacy_research)

        def recording_edit(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            captured["payloads"].append(dict(payload))
            return _fake_edit_response(payload)

        monkeypatch.setattr(executor_core, "handle_agent_edit", recording_edit)
        monkeypatch.setattr(stage, "_default_hivemind_search", _fake_search)
        monkeypatch.setattr(stage, "_default_hivemind_get", _fake_get)

        request = ExecutorRequest(
            query="add audio conditioning to my Wan video",
            graph={"nodes": [{"id": 1, "type": "WanImageToVideo"}], "links": []},
            profile="default",
        )

        monkeypatch.setattr(stage, "_default_judge_fn", lambda spec: _judge([]))
        result_ok = executor_core.run_executor(request)
        assert getattr(result_ok.report.research, "research_shadow").trace.status == "ok"

        monkeypatch.setattr(stage, "_default_judge_fn", lambda spec: _raising_judge)
        result_failed = executor_core.run_executor(request)
        assert getattr(result_failed.report.research, "research_shadow").trace.status == "failed"

        assert _canonical_bytes(result_ok.to_dict()) == _canonical_bytes(result_failed.to_dict())
        assert result_ok.reply == result_failed.reply
        assert result_ok.graph == result_failed.graph
        assert len(captured["payloads"]) == 2
        # The implement payload handed to the edit engine (execution protocol
        # notes, research context, classification) is identical: the shadow
        # fed nothing into it.
        assert _canonical_bytes(captured["payloads"][0]) == _canonical_bytes(
            captured["payloads"][1]
        )

    def test_shadow_opt_in_keeps_default_executor_hermetic(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without VIBECOMFY_RESEARCH_SHADOW the executor never invokes the
        shadow stage (no extra tool/model I/O) and never attaches a shadow."""
        from vibecomfy.executor import core as executor_core

        monkeypatch.delenv("VIBECOMFY_RESEARCH_SHADOW", raising=False)
        assert executor_core._research_shadow_enabled() is False

        monkeypatch.setattr(executor_core, "run_classify_turn", _fake_classify_research_only)
        monkeypatch.setattr(executor_core, "run_reply_turn", _fake_reply)
        monkeypatch.setattr(executor_core, "run_research_phase", _fake_legacy_research)
        shadow_calls: list[Any] = []
        monkeypatch.setattr(
            executor_core,
            "run_agent_research_shadow",
            mock.Mock(side_effect=lambda *a, **k: shadow_calls.append((a, k))),
        )

        result = executor_core.run_executor(
            ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default")
        )
        assert result.ok is True
        assert shadow_calls == []
        assert getattr(result.report.research, "research_shadow", None) is None
        assert "research_shadow" not in _canonical_bytes(result.to_dict())

        # Opting in flips it on.
        monkeypatch.setenv("VIBECOMFY_RESEARCH_SHADOW", "1")
        assert executor_core._research_shadow_enabled() is True

    def test_shadow_stage_exception_is_contained_by_executor(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even a bare exception escaping run_agent_research_shadow is caught
        by core and never fails the executor turn."""
        from vibecomfy.executor import core as executor_core

        monkeypatch.setenv("VIBECOMFY_RESEARCH_SHADOW", "1")
        monkeypatch.setattr(executor_core, "run_classify_turn", _fake_classify_research_only)
        monkeypatch.setattr(executor_core, "run_reply_turn", _fake_reply)
        monkeypatch.setattr(executor_core, "run_research_phase", _fake_legacy_research)
        monkeypatch.setattr(
            executor_core,
            "run_agent_research_shadow",
            mock.Mock(side_effect=RuntimeError("shadow integration exploded")),
        )

        result = executor_core.run_executor(
            ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default")
        )
        assert result.ok is True
        assert result.reply == _fake_reply(_EXPLICIT_QUESTION)
        assert result.report.research is not None
        assert "research_shadow" not in _canonical_bytes(result.to_dict())


# ── Acceptance 2: explicit question + enough/refine judgment in the ledger ───


class TestTraceRecordsQuestionAndJudgment:
    def test_trace_and_ledger_prove_question_and_enough_refine(
        self, profile_dir: Path
    ) -> None:
        judge_log: list[dict[str, Any]] = []
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        legacy = _LegacyResult(
            summary="legacy summary",
            sources=({"source": "object_info", "title": "KSampler"},),
            warnings=(),
        )

        result = stage.run_agent_research_shadow(
            ExecutorRequest(query="make my wan video audio conditioned", profile="default"),
            plan=_research_plan(),
            spec=spec,
            legacy_result=legacy,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=_judge(judge_log),
        )

        assert result.trace.status == "ok"
        # Explicit question comes from the classifier's research_goal, not the
        # raw user query.
        assert result.trace.question == _EXPLICIT_QUESTION
        assert result.trace.final_verdict == "enough"
        assert len(result.trace.iterations) == 2
        assert [i.question for i in result.trace.iterations] == [
            _EXPLICIT_QUESTION,
            _REFINED_QUESTION,
        ]

        ledger = result.agent_evidence_pack.ledger
        decisions = [entry.decision for entry in ledger.entries]
        # Question recorded BEFORE any tool call (question-before-search).
        assert decisions[0] == stage.DECISION_QUESTION
        assert decisions.count(stage.DECISION_SYNTHESIZE) == 2
        assert decisions.count(stage.DECISION_ENOUGH_REFINE) == 2
        assert ledger.entries[0].conclusion == _EXPLICIT_QUESTION
        # Enough/refine judgment text records the verdict and the refinement.
        refine_entry = next(
            entry for entry in ledger.entries if entry.decision == stage.DECISION_ENOUGH_REFINE
        )
        assert "enough=False" in refine_entry.conclusion
        assert _REFINED_QUESTION in refine_entry.conclusion
        enough_entry = [
            entry for entry in ledger.entries if entry.decision == stage.DECISION_ENOUGH_REFINE
        ][-1]
        assert "enough=True" in enough_entry.conclusion

        # Every ledger citation resolves to an artifact in the same pack
        # (already enforced by EvidencePack construction; re-assert here).
        assert result.agent_evidence_pack.ledger.validate_references(
            set(result.agent_evidence_pack.artifacts)
        ) is None
        for evidence_id in result.trace.citations:
            assert evidence_id in result.agent_evidence_pack.artifacts
        # The synthesize ledger entry cites only returned evidence ids.
        synthesize_entries = [
            entry for entry in ledger.entries if entry.decision == stage.DECISION_SYNTHESIZE
        ]
        assert "hivemind:workflows:111" in synthesize_entries[-1].evidence_ids
        # Tool results were captured as evidence artifacts.
        assert "hivemind:workflows:111" in result.agent_evidence_pack.artifacts
        assert "hivemind_get:workflows:111" in result.agent_evidence_pack.artifacts

    def test_budget_exhaustion_terminates_with_refine_verdict(
        self, profile_dir: Path
    ) -> None:
        """A judge that never says enough still terminates (bounded), leaving
        a refine verdict and a recorded trace."""
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        def never_enough(question: str, digest: str) -> dict[str, Any]:
            return {
                "conclusion": "still unresolved",
                "evidence_ids": [],
                "uncertainty": "high",
                "enough": False,
                "refine_question": "refined question",
            }

        result = stage.run_agent_research_shadow(
            ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default"),
            plan=_research_plan(),
            spec=spec,
            legacy_result=_LegacyResult(summary="s", sources=()),
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=never_enough,
        )
        assert result.trace.status == "ok"
        assert result.trace.final_verdict == "refine"
        assert len(result.trace.iterations) == stage.TOOL_SEARCH_BUDGET
        assert result.agent_evidence_pack.ledger.validate_references(
            set(result.agent_evidence_pack.artifacts)
        ) is None


# ── Acceptance 3: no full legacy result / workflow schema in the model request ─


class TestNoLegacyInjectionIntoModelRequest:
    def test_judgment_digest_contains_only_question_and_compact_evidence(
        self, profile_dir: Path
    ) -> None:
        """The digest handed to the judgment model contains the explicit
        question and compact tool evidence — never the legacy result body and
        never a workflow/graph schema dump."""
        captured: dict[str, Any] = {}

        def recording_judge(question: str, digest: str) -> dict[str, Any]:
            captured["question"] = question
            captured["digest"] = digest
            return {
                "conclusion": "Use LoadAudio before the video model",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
                "enough": True,
                "refine_question": None,
            }

        legacy = _LegacyResult(
            summary="LEGACY_MARKER_SUMMARY deterministic research",
            sources=(
                {
                    "source": "object_info",
                    "title": "LEGACY_MARKER_SOURCE",
                    "class_type": "LEGACY_MARKER_CLASS",
                    "description": "LEGACY_MARKER_BODY",
                },
            ),
            warnings=("LEGACY_MARKER_WARNING",),
        )
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")

        result = stage.run_agent_research_shadow(
            ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default"),
            plan=_research_plan(),
            spec=spec,
            legacy_result=legacy,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=recording_judge,
        )
        assert result.trace.status == "ok"
        digest = captured["digest"]
        assert _EXPLICIT_QUESTION in digest
        assert "hivemind:workflows:111" in digest
        # No legacy result marker, no full source body, no graph schema dump.
        assert "LEGACY_MARKER" not in digest
        assert "Deterministic research" not in digest
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
        assert "LEGACY_MARKER" not in all_text
        assert '"nodes"' not in all_text

    def test_end_to_end_model_request_never_contains_legacy_or_graph(
        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Through the real run_executor integration, the model request built
        by the stage carries neither the legacy result nor the workflow
        graph."""
        from vibecomfy.executor import core as executor_core

        monkeypatch.setenv("VIBECOMFY_RESEARCH_SHADOW", "1")
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
                "conclusion": "Use LoadAudio -> ConditioningCombine before WanImageToVideo",
                "evidence_ids": ["hivemind:workflows:111"],
                "uncertainty": "low",
                "enough": True,
                "refine_question": None,
            }

        monkeypatch.setattr(executor_core, "run_classify_turn", _fake_classify_research_only)
        monkeypatch.setattr(executor_core, "run_reply_turn", _fake_reply)
        monkeypatch.setattr(executor_core, "run_research_phase", _fake_legacy_research)
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
        # Legacy research markers are absent.
        assert "Deterministic research" not in all_text
        assert "KSampler" not in all_text
        # The attached workflow graph never enters the model request.
        assert "WanImageToVideo" not in all_text
        assert '"nodes"' not in all_text

    def test_stage_source_never_injects_legacy_result_into_prompt(self) -> None:
        """Source-level grep: the legacy result may only feed the evidence-pack
        capture and dual-report builders — never the prompt/digest builders —
        and the stage never calls the legacy research engine."""
        source = Path(stage.__file__).read_text(encoding="utf-8")
        # The stage never invokes the legacy research phase.
        assert "run_research_phase" not in source
        # Every use of the legacy result must be in the capture/report path,
        # not in prompt or digest construction.
        for lineno, line in enumerate(source.splitlines(), start=1):
            if "legacy_result" in line:
                assert "digest" not in line, (
                    f"agent_research_stage.py:{lineno}: legacy_result feeds the prompt digest"
                )
                assert "messages" not in line, (
                    f"agent_research_stage.py:{lineno}: legacy_result feeds model messages"
                )
                assert "prompt" not in line, (
                    f"agent_research_stage.py:{lineno}: legacy_result feeds the prompt"
                )


# ── Acceptance 4: dual report + persisted artifacts ──────────────────────────


class TestDualReportAndArtifacts:
    def test_dual_report_compares_coverage_citations_lifecycle(
        self, profile_dir: Path
    ) -> None:
        judge_log: list[dict[str, Any]] = []
        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        legacy = _LegacyResult(
            summary="legacy summary",
            sources=(
                {
                    "source": "hivemind_message",
                    "title": "community note",
                    "hivemind_id": "hivemind:discord:222",
                },
                {"source": "object_info", "title": "KSampler"},
            ),
            warnings=("legacy warning",),
        )

        result = stage.run_agent_research_shadow(
            ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default"),
            plan=_research_plan(),
            spec=spec,
            legacy_result=legacy,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=_judge(judge_log),
        )
        assert result.trace.status == "ok"
        dual = result.dual_report
        assert dual["route"] == "research"

        # Coverage: agent ids, legacy ids, and a genuine overlap where the
        # legacy source exposes a Hivemind evidence id.
        coverage = dual["coverage"]
        assert "hivemind:workflows:111" in coverage["agent_evidence_ids"]
        assert "legacy_source:1" in coverage["legacy_evidence_ids"]
        assert "hivemind:discord:222" in coverage["legacy_hivemind_references"]
        assert "hivemind:discord:222" in coverage["shared"]
        assert "hivemind:workflows:111" in coverage["agent_only"]
        assert coverage["legacy_artifact_count"] == 3  # 2 sources + summary

        # Citation validity: every ledger citation resolves inside its pack.
        agent_validity = dual["citation_validity"]["agent"]
        assert agent_validity["total"] == agent_validity["resolvable"]
        assert agent_validity["unresolvable"] == []
        legacy_validity = dual["citation_validity"]["legacy"]
        assert legacy_validity["total"] == legacy_validity["resolvable"]
        assert legacy_validity["unresolvable"] == []

        # Lifecycle assertions.
        lifecycle = dual["lifecycle"]
        assert lifecycle["question_recorded"] is True
        assert lifecycle["synthesize_recorded"] is True
        assert lifecycle["enough_refine_recorded"] is True
        assert lifecycle["legacy_behavior_used"] is True
        assert lifecycle["status"] == "ok"
        assert lifecycle["final_verdict"] == "enough"
        assert lifecycle["searches"] == 2
        assert lifecycle["fetches"] == 4  # 2 hits fetched per iteration x 2 iterations

    def test_headless_artifacts_persist_shadow_report_and_both_packs(
        self, tmp_path: Path, profile_dir: Path
    ) -> None:
        from vibecomfy.agent.artifacts import synthesize_headless_artifacts

        spec = AgentSpecShape(agent="hermes", model="deepseek-v4-pro", effort="medium")
        legacy = _LegacyResult(
            summary="legacy summary",
            sources=({"source": "object_info", "title": "KSampler"},),
            warnings=(),
        )
        shadow = stage.run_agent_research_shadow(
            ExecutorRequest(query=_EXPLICIT_QUESTION, profile="default"),
            plan=_research_plan(),
            spec=spec,
            legacy_result=legacy,
            search_fn=_fake_search,
            get_fn=_fake_get,
            judge_fn=_judge([]),
        )
        assert shadow.legacy_evidence_pack is not None

        research = _LegacyResult(summary="legacy summary")
        object.__setattr__(research, "research_shadow", shadow)
        result = ExecutorResult.success(
            report=Report(plan=_research_plan(), research=research),
            reply="ok",
        )

        summary = synthesize_headless_artifacts(
            request={"query": _EXPLICIT_QUESTION},
            result=result,
            response={},
            output_dir=tmp_path,
            status="ok",
        )
        manifest = summary["manifest"]
        for name in (
            "research_shadow.json",
            "research_shadow_agent_pack.json",
            "research_shadow_legacy_pack.json",
        ):
            assert name in manifest
            assert (tmp_path / name).is_file()

        shadow_json = json.loads((tmp_path / "research_shadow.json").read_text(encoding="utf-8"))
        assert shadow_json["shadow_mode"] is True
        assert shadow_json["legacy_behavior_used"] is True
        assert shadow_json["route"] == "research"
        assert shadow_json["trace"]["question"] == _EXPLICIT_QUESTION
        assert shadow_json["dual_report"]["lifecycle"]["enough_refine_recorded"] is True
        assert shadow_json["dual_report"]["lifecycle"]["question_recorded"] is True

        agent_pack = json.loads(
            (tmp_path / "research_shadow_agent_pack.json").read_text(encoding="utf-8")
        )
        assert agent_pack["ledger"]["entries"]
        assert "hivemind:workflows:111" in agent_pack["artifacts"]

        legacy_pack = json.loads(
            (tmp_path / "research_shadow_legacy_pack.json").read_text(encoding="utf-8")
        )
        assert legacy_pack["ledger"]["entries"]
        assert "legacy_summary" in legacy_pack["artifacts"]

    def test_artifacts_without_shadow_emit_no_shadow_files(
        self, tmp_path: Path, profile_dir: Path
    ) -> None:
        from vibecomfy.agent.artifacts import synthesize_headless_artifacts

        research = _LegacyResult(summary="legacy summary")
        result = ExecutorResult.success(
            report=Report(plan=_research_plan(), research=research),
            reply="ok",
        )
        summary = synthesize_headless_artifacts(
            request={"query": _EXPLICIT_QUESTION},
            result=result,
            response={},
            output_dir=tmp_path,
            status="ok",
        )
        assert "research_shadow.json" not in summary["manifest"]
        assert not (tmp_path / "research_shadow.json").exists()
