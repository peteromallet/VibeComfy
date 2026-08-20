"""EXECUTOR CONTRACT TESTS.

Executor smoke/regression tests for the full classify → research → implement → reply pipeline.

Covers respond-only, research-only, simple edit, and graph-describe flows
on ``default`` and ``openai`` profiles with fake model backend outputs.
Also includes profile-only smoke coverage for all four canonical profiles
(``default``, ``openai``, ``anthropic``, ``opensource``) that does not
require live adapters or credentials.

All model calls are faked and deterministic — no network, no ComfyUI boot,
no Arnold imports.
"""

from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Generator
from unittest import mock

import pytest

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
)
from vibecomfy.executor import core as executor_core
from vibecomfy.executor.agent_research_stage import (
    DECISION_GET,
    DECISION_SYNTHESIZE,
    RESEARCH_ATTEMPT_EMPTY,
    RESEARCH_ATTEMPT_GROUNDED,
    RESEARCH_ATTEMPT_NEVER,
    RESEARCH_ATTEMPT_THIN,
    AgentResearchTrace,
    derive_research_attempt,
)
from vibecomfy.executor.core import AgentResearchResult, run_executor
from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
)
from vibecomfy.executor.prompts import build_classify_messages
from vibecomfy.executor.profiles import AgentSpecShape, set_profile_override_dir
from vibecomfy.executor.tool_contracts import ToolStatus


# ── Profile fixture helpers ─────────────────────────────────────────────────

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


def test_terminal_no_candidate_response_does_not_promote_rollback_graph() -> None:
    request = ExecutorRequest(
        query="add unsupported node",
        graph={"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}], "links": []},
        profile="default",
    )
    plan = ClassifyDecision(
        route="adapt",
        implement=True,
        intent="edit",
        task="edit_graph",
    )
    stale_candidate = {"nodes": [{"id": 999, "type": "Stale"}], "links": []}

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit",
        return_value={
            "ok": True,
            "message": "No safe edit found.",
            "graph": stale_candidate,
            "graph_unchanged": True,
            "no_candidate_reason": "no_changes",
            "outcome": {"kind": "noop"},
            "apply_eligibility": {"applyable": False},
        },
    ):
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="codex", model="gpt-5.4", effort="high"),
            plan=plan,
        )

    assert result.graph is None
    assert result.durable_response["graph"]["nodes"][0]["id"] == stale_candidate["nodes"][0]["id"]


def test_terminal_no_candidate_response_allows_real_changed_candidate() -> None:
    request = ExecutorRequest(
        query="add image save",
        graph={"nodes": [{"id": 1, "type": "VAEDecode"}], "links": []},
        profile="default",
    )
    plan = ClassifyDecision(
        route="adapt",
        implement=True,
        intent="edit",
        task="edit_graph",
    )
    candidate = {"nodes": [{"id": 1, "type": "VAEDecode"}, {"id": 2, "type": "SaveImage"}], "links": []}

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit",
        return_value={
            "ok": True,
            "message": "Candidate ready.",
            "graph": candidate,
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "apply_eligibility": {"applyable": True},
        },
    ):
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="codex", model="gpt-5.4", effort="high"),
            plan=plan,
        )

    assert result.graph == candidate


def test_terminal_no_candidate_reply_still_grounds_ids_against_original_graph(
    profile_dir: Path,
) -> None:
    """The direct terminal reply path cannot bypass node-ID grounding."""
    request = ExecutorRequest(
        query="change the checkpoint",
        graph={"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}], "links": []},
        profile="default",
    )
    plan = ClassifyDecision(
        route="adapt", implement=True, research=True, intent="edit", task="edit_graph"
    )

    with mock.patch("vibecomfy.executor.core.run_classify_turn", return_value=plan):
        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit",
            return_value={
                "ok": True,
                "message": "No safe candidate was produced for node 999.",
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "accepted_batch": [],
            },
        ):
            result = run_executor(request)

    assert result.ok is True
    assert "999" not in result.reply
    assert "node 999" not in result.reply


def _write_toml(dir_path: Path, name: str, content: str) -> Path:
    """Write a TOML profile file into *dir_path* and return its path."""
    file_path = dir_path / f"{name}.toml"
    file_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return file_path


def _setup_profile_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with the four canonical profiles."""
    with tempfile.TemporaryDirectory() as tmp:
        dir_path = Path(tmp)
        _write_toml(dir_path, "default", _BASE_PROFILE)
        _write_toml(
            dir_path,
            "openai",
            _BASE_PROFILE.replace('"codex"', '"codex"')
            .replace('"gpt-5.4"', '"gpt-5.5"'),
        )
        _write_toml(
            dir_path,
            "anthropic",
            _BASE_PROFILE.replace('"codex"', '"claude"')
            .replace('"gpt-5.4"', '"claude-sonnet-4-5"'),
        )
        _write_toml(
            dir_path,
            "opensource",
            _BASE_PROFILE.replace('"codex"', '"shannon"')
            .replace('"gpt-5.4"', '"openrouter/hermes-3-70b"'),
        )
        set_profile_override_dir(dir_path)
        yield dir_path
        set_profile_override_dir(None)


@pytest.fixture
def profile_dir() -> Generator[Path, None, None]:
    yield from _setup_profile_dir()


@pytest.fixture(autouse=True)
def _stub_agent_owned_research(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep executor flow tests offline while exercising the active C1 handoff."""

    def fake_agent_research_stage(
        *,
        route: str,
        question: str,
        spec: AgentSpecShape,
        research_brief: str = "",
    ) -> tuple[AgentResearchTrace, EvidencePack]:
        del research_brief
        del spec
        # Batch 14: the offline fixture records an EXECUTED hivemind_get call
        # plus a synthesize citation so the derived research_attempt is
        # "grounded" (thin/grounded is what lets adapt proceed to implement).
        ledger = EvidenceLedger(
            entries=(
                EvidenceLedgerEntry(
                    decision=DECISION_GET,
                    conclusion="workflow record hivemind_get:fixture",
                    evidence_ids=("hivemind_get:fixture",),
                    uncertainty="",
                ),
                EvidenceLedgerEntry(
                    decision="agent_research",
                    conclusion="Agent-owned research completed for the requested route.",
                    evidence_ids=("hivemind_get:fixture",),
                    uncertainty="low",
                ),
                EvidenceLedgerEntry(
                    decision=DECISION_SYNTHESIZE,
                    conclusion="Agent-owned research completed for the requested route.",
                    evidence_ids=("hivemind_get:fixture",),
                    uncertainty="low",
                ),
            )
        )
        trace = AgentResearchTrace(
            route=route,
            question=question,
            iterations=(),
            final_verdict="enough",
            summary="Agent-owned research completed for the requested route.",
            citations=(),
            uncertainty="low",
            status="ok",
            elapsed_seconds=0.0,
        )
        return trace, EvidencePack(
            artifacts={
                "hivemind_get:fixture": EvidenceArtifact(
                    evidence_id="hivemind_get:fixture",
                    kind="hivemind_get",
                    body={"content": "fixture fetched record"},
                    source="hivemind",
                ),
            },
            ledger=ledger,
        )

    monkeypatch.setattr(executor_core, "run_agent_research_stage", fake_agent_research_stage)


def test_terminal_no_candidate_response_does_not_promote_rollback_graph() -> None:
    response = {
        "graph": {"nodes": [{"id": 1, "type": "SaveImage"}]},
        "message": "Applied changes successfully.",
        "outcome": {"kind": "noop"},
        "graph_unchanged": True,
        "no_candidate_reason": "no_changes",
        "apply_eligible": True,
    }

    assert executor_core._implementation_response_is_terminal_no_candidate(response) is True


def test_terminal_no_candidate_response_allows_real_changed_candidate() -> None:
    response = {
        "graph": {"nodes": [{"id": 1, "type": "SaveImage"}]},
        "message": "Applied changes successfully.",
        "outcome": {"kind": "edit"},
        "graph_unchanged": False,
        "no_candidate_reason": "no_changes",
        "apply_eligible": True,
    }

    assert executor_core._implementation_response_is_terminal_no_candidate(response) is False


# ── Fake model backend helpers ───────────────────────────────────────────────


def _fake_classify_respond_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a respond-only classification (no research, no edit)."""
    return ClassifyDecision.respond_only(
        plan_summary="simple chat reply",
    )


def _fake_classify_research_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a research-only classification (research, no edit)."""
    return ClassifyDecision(
        research=True,
        implement=False,
        reply=True,
        effort="medium",
        plan_summary="research node types",
        route="research",
        task="research_nodes",
        research_goal="Find distilled or faster ways to run the current ComfyUI video workflow.",
        search_directions=(
            "distilled or lightning video/motion models compatible with AnimateDiff-style workflows",
            "AnimateDiff speed settings such as context length, sampler, steps, and frame count",
            "ComfyUI workflow examples that trade quality for faster generation",
        ),
        source_preferences=("workflows", "messages", "web"),
        avoid=(
            "generic searches for the raw sentence",
            "stopword-only searches such as there way run",
            "treating Discord snippets as authoritative without workflow evidence",
        ),
        known_graph_context="Attached graph may be absent; infer only broad workflow family from the request.",
    )


def _fake_classify_simple_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a simple edit classification (implement, no research)."""
    return ClassifyDecision.edit(
        research=False,
        effort="low",
        plan_summary="simple graph edit",
    )


def _fake_classify_graph_describe(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a graph-describe classification (research + implement)."""
    return ClassifyDecision.edit(
        research=True,
        effort="medium",
        plan_summary="describe and edit graph",
    )


def _fake_reply_respond_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return a respond-only fake reply."""
    return "I'm here to help with your ComfyUI workflow. What would you like to do?"


def _fake_reply_research_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return a research-only fake reply."""
    return "Based on my research, here are the relevant node types: KSampler, VAEDecode, CLIPTextEncode."


def _fake_reply_hotshot(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return a fake reply referencing Hotshot XL research."""
    return "Hotshot XL is an SDXL-based text-to-video model. You can insert it before SVD-XT as a frame generator."


def test_classify_census_derives_reference_map_from_dict_form_nodes() -> None:
    """Batch 12 fix: classify's reference map (node ids + class types) is
    derived from the IR via the renderer's census lens — the raw-JSON
    ``_build_graph_reference_map`` walk is gone."""
    graph = {
        "vibecomfy_format_version": "1.0",
        "id": "dict-form",
        "nodes": {
            "27": {"id": "27", "class_type": "SaveVideo", "inputs": {}, "widgets": {}, "uid": "uid-27", "metadata": {"_ui": {"mode": 0}}},
            "34": {"id": "34", "class_type": "MoonvalleyImg2VideoNode", "inputs": {}, "widgets": {}, "uid": "uid-34", "metadata": {"_ui": {"mode": 0}}},
        },
        "edges": [],
        "source": {"id": "dict-form", "path": None, "source_type": "workflow"},
        "requirements": {},
        "inputs": {},
        "outputs": [],
        "metadata": {},
    }

    census = executor_core._render_census_text(graph)
    assert census is not None
    assert "## Census" in census
    assert "class list:" in census
    assert "reference map:" in census
    assert "SaveVideo" in census
    assert "MoonvalleyImg2VideoNode" in census


def test_classify_census_reference_map_covers_ui_list_form_nodes() -> None:
    """The census lens resolves node ids + class types for UI-list graphs too —
    the same facts the old raw-JSON walk provided, now via the renderer."""
    graph = {
        "nodes": [
            {"id": 27, "type": "SaveVideo", "class_type": "SaveVideo"},
            {"id": 34, "type": "MoonvalleyImg2VideoNode", "class_type": "MoonvalleyImg2VideoNode"},
        ],
        "links": [],
    }

    census = executor_core._render_census_text(graph)
    assert census is not None
    assert "## Census" in census
    assert "reference map:" in census
    assert "SaveVideo" in census
    assert "MoonvalleyImg2VideoNode" in census


def _fake_reply_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return an edit fake reply."""
    return "The graph has been updated with the requested changes."


def _fake_reply_graph_describe(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return a graph-describe fake reply."""
    return "I've analyzed your graph and applied the node template. The graph now has a KSampler connected to VAEDecode."


def _fake_reply_reject_adaptation_plan(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
    graph_inspection: str | None = None,
    **kwargs: Any,
) -> str:
    """Simulate an older reply wrapper that rejects adaptation_plan only."""
    if "adaptation_plan" in kwargs:
        raise TypeError("run_reply_turn() got an unexpected keyword argument 'adaptation_plan'")
    if not (graph_summary or graph_inspection):
        raise AssertionError("graph context should survive adaptation_plan fallback")
    return "This workflow loads a checkpoint and runs sampling."


def _fake_handle_agent_edit(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit that returns a successful edit result."""
    input_graph = payload.get("graph", {})
    nodes = input_graph.get("nodes", [])
    edited_nodes = list(nodes) + [{"id": len(nodes) + 1, "type": "KSampler"}]
    return {
        "graph": {"nodes": edited_nodes},
        "message": "Added a KSampler node to the graph.",
    }


def _fake_handle_agent_edit_pure_clarify(payload: dict, **kwargs: Any) -> dict:
    """Fake a durable agent-edit clarify/no-candidate response."""
    graph = payload.get("graph", {})
    return {
        "ok": True,
        "graph": graph,
        "message": "Hotshot nodes are not currently installed.",
        "outcome": {
            "kind": "clarify",
            "question": "Hotshot nodes are not currently installed.",
        },
        "apply_eligible": False,
        "apply_eligibility": {
            "applyable": False,
            "reason": "no_candidate",
            "message": "No applyable candidate was produced.",
        },
        "graph_unchanged": True,
        "session_id": "clarify-session",
        "turn_id": "0001",
    }


def _fake_reply_research_findings(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return a fake reply that cites the hoisted community findings."""
    return (
        "Community notes: alice in #ltx_chatter says LTX 2.5 handles fast "
        "previews really well."
    )


def _fake_classify_explain_graph(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return an inspect classification for graph explanation (no edit)."""
    return ClassifyDecision(
        research=False,
        implement=False,
        reply=True,
        effort="medium",
        plan_summary="explain what the graph does",
        intent="explain_graph",
        route="inspect",
        task="inspect_graph",
    )


def _fake_reply_explain_graph(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    **kwargs: Any,
) -> str:
    """Return a fake reply for an explain-graph request."""
    return "This workflow loads a checkpoint, encodes prompts, samples a latent, decodes it, and saves the image."


def _fake_handle_agent_edit_explain(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit that returns an explanation without editing."""
    input_graph = payload.get("graph", {})
    classification = payload.get("executor_classification", {})
    intent = classification.get("intent") if isinstance(classification, dict) else ""
    return {
        "graph": input_graph,
        "message": f"Explanation generated for intent={intent}: the workflow is a text-to-image pipeline.",
    }


def _empty_hivemind_client(query: str, timeout: float) -> dict[str, Any]:
    """Deterministic Hivemind client that returns no results."""
    return {"results": []}


def _empty_web_search_client(query: str, timeout: float) -> dict[str, Any]:
    """Deterministic web search client that returns no results."""
    return {"results": []}


def _empty_registry_resolver(query: str) -> Any:
    """Deterministic registry resolver that returns no candidates or warnings."""
    from vibecomfy.registry.pack_resolver import MissingNodeResolution

    return MissingNodeResolution(query=query, query_intent="capability")


# ── Respond-only flow tests ──────────────────────────────────────────────────


class TestRespondOnlyFlow:
    """Smoke tests for the respond-only executor flow (no research, no edit)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_default_profile(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Respond-only with default profile returns a success result with reply."""
        request = ExecutorRequest(query="What is a KSampler?", profile="default")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply == "I'm here to help with your ComfyUI workflow. What would you like to do?"
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        assert result.report.plan.reply is True
        assert result.report.research is None
        assert result.report.implementation is None
        assert result.graph is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_openai_profile(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Respond-only with openai profile returns a success result with reply."""
        request = ExecutorRequest(query="How do I add a node?", profile="openai")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        assert result.report.research is None
        assert result.report.implementation is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_no_profile_defaults_to_default(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When no profile is specified, the default profile is used."""
        request = ExecutorRequest(query="hello")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_result_to_dict(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """The result can be serialized to a dict with expected keys."""
        request = ExecutorRequest(query="status", profile="default")
        result = run_executor(request)
        d = result.to_dict()

        assert d["ok"] is True
        assert "reply" in d
        assert "report" in d
        assert d.get("graph") is None
        assert d["report"]["executor"]["plan"]["research"] is False
        assert d["report"]["executor"]["plan"]["implement"] is False

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_with_session_id(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Respond-only with session_id still works."""
        request = ExecutorRequest(
            query="help", profile="default", session_id="sess-test-1"
        )
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None


# ── Research-only flow tests ─────────────────────────────────────────────────


class TestAgentOwnedResearchFlow:
    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", return_value="Agent memo reply.")
    def test_research_route_returns_c5_memo_without_legacy_prefetch(
        self, mock_reply: mock.Mock, mock_classify: mock.Mock, profile_dir: Path
    ) -> None:
        del mock_classify
        with mock.patch("vibecomfy.executor.core.run_research_phase") as legacy_research:
            result = run_executor(
                ExecutorRequest(query="What sampling nodes are available?", profile="default")
            )

        assert result.ok is True
        assert result.report.research is not None
        assert result.report.research.decision_memo == {
            "question": "Find distilled or faster ways to run the current ComfyUI video workflow.",
            "conclusion": "Agent-owned research completed for the requested route.",
            "citations": [],
            "uncertainty": "low Requested source 'web' is unavailable in the active C1 research stage; it was not silently substituted or removed.",
            "research_attempt": RESEARCH_ATTEMPT_GROUNDED,
            "next_action": "Use this conclusion for the requested next step.",
        }
        wire_research = result.to_dict()["report"]["executor"]["research"]
        assert wire_research["question"] == result.report.research.decision_memo["question"]
        assert "ledger" not in wire_research
        assert "evidence_pack" not in wire_research
        legacy_research.assert_not_called()
        _, kwargs = mock_reply.call_args
        assert kwargs["research_memo"] == result.report.research.decision_memo
        assert kwargs["research_ledger"] is None
        assert "research_summary" not in kwargs
        assert "research_sources" not in kwargs

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", return_value="Done.")
    def test_unsupported_source_is_a_visible_policy_diagnostic(
        self, mock_reply: mock.Mock, mock_classify: mock.Mock, profile_dir: Path
    ) -> None:
        del mock_reply
        mock_classify.return_value = ClassifyDecision(
            route="research",
            research=True,
            reply=True,
            source_preferences=("web", "private_wiki"),
        )
        result = run_executor(ExecutorRequest(query="Find precedent", profile="default"))

        diagnostics = result.report.research.policy_diagnostics
        assert [item["source"] for item in diagnostics] == ["web", "private_wiki"]
        assert all(item["code"] == "unsupported_research_source" for item in diagnostics)
        assert result.report.plan.source_preferences == ("web", "private_wiki")


# ── Answer-only interaction (PR-B) ────────────────────────────────────────────


class TestAnswerOnlyInteraction:
    """interaction_mode="answer_only" guarantees no graph edit, whatever the
    classifier decided.  It is an explicit request/scenario contract — never
    inferred from ``apply=false`` (that flag only gates candidate application).
    """

    def _run(self, request: ExecutorRequest, *, classify: Any) -> ExecutorResult:
        def fake_reply(
            query: str,
            *,
            interaction_mode: str | None = None,
            **kwargs: Any,
        ) -> str:
            captured_reply["interaction_mode"] = interaction_mode
            return "Here is the answer."

        captured_reply: dict[str, Any] = {}
        captured_reply["interaction_mode"] = "unset"

        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=classify),
            mock.patch("vibecomfy.executor.core.run_research_phase") as legacy_research,
            mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=fake_reply),
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
        ):
            result = run_executor(request)
            edit_called = mock_edit.called
            legacy_prefetch_called = legacy_research.called
        return result, legacy_prefetch_called, captured_reply, edit_called

    def test_answer_only_edit_classification_is_downgraded_to_research(
        self, profile_dir: Path
    ) -> None:
        """An edit-classified query on an answer_only interaction must not edit."""
        def classify_edit(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
            return ClassifyDecision(
                research=True,
                implement=True,
                reply=True,
                effort="high",
                plan_summary="research then adapt",
                intent="edit",
                route="adapt",
                task="research_precedent",
            )

        request = ExecutorRequest(
            query="how should I rewire the KSampler?",
            graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
            profile="default",
            interaction_mode="answer_only",
        )
        result, legacy_prefetch_called, reply_capture, edit_called = self._run(
            request, classify=classify_edit
        )

        assert result.ok is True
        # The answer-only contract downgraded the edit route to research.
        assert result.report.plan.effective_route == "research"
        assert result.report.plan.implement is False
        assert result.to_dict()["route"] == "research"
        assert result.graph is None
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False
        # Legacy prefetch never ran; the agent-owned stage and reply ran.
        assert legacy_prefetch_called is False
        assert reply_capture["interaction_mode"] == "answer_only"
        assert edit_called is False

    def test_answer_only_research_classification_never_implements(
        self, profile_dir: Path
    ) -> None:
        """A research classification on an answer_only interaction stays pure."""
        def classify_research(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
            return ClassifyDecision(
                research=True,
                implement=False,
                reply=True,
                effort="medium",
                plan_summary="research node types",
                route="research",
                task="research_nodes",
                source_preferences=("workflows", "messages", "web"),
            )

        request = ExecutorRequest(
            query="compare Gemini and Claude for prompt splitting",
            profile="default",
            interaction_mode="answer_only",
        )
        result, legacy_prefetch_called, reply_capture, edit_called = self._run(
            request, classify=classify_research
        )

        assert result.ok is True
        assert result.report.plan.effective_route == "research"
        assert result.report.plan.implement is False
        assert result.to_dict()["route"] == "research"
        assert legacy_prefetch_called is False
        assert reply_capture["interaction_mode"] == "answer_only"
        assert edit_called is False

    def test_answer_only_reply_prompt_carries_explicit_note(self) -> None:
        """build_reply_messages receives the answer-only interaction note."""
        from vibecomfy.executor.prompts import build_reply_messages

        msgs = build_reply_messages(
            "diagnose this",
            interaction_mode="answer_only",
        )
        user = msgs[1]["content"]
        assert "answer_only" in user
        assert "No graph edit was made and none is permitted" in user
        plain = build_reply_messages("diagnose this")[1]["content"]
        assert "answer_only" not in plain


# ── Simple edit flow tests ───────────────────────────────────────────────────


class TestSimpleEditFlow:
    """Smoke tests for the simple edit executor flow (implement → reply, no research)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_default_profile(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Simple edit with default profile runs implement and reply phases."""
        input_graph = {"nodes": [{"id": 1, "type": "VAEDecode"}]}
        request = ExecutorRequest(
            query="add a KSampler node",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply == "The graph has been updated with the requested changes."
        assert result.report.plan.research is False
        assert result.report.plan.implement is True
        assert result.report.research is None
        assert result.report.implementation is not None
        assert result.report.implementation.message == "Added a KSampler node to the graph."
        # The edited graph should be returned.
        assert result.graph is not None
        assert len(result.graph["nodes"]) == 2

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_openai_profile(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Simple edit with openai profile."""
        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add a sampler",
            graph=input_graph,
            profile="openai",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.implement is True
        assert result.report.implementation is not None
        assert result.graph is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_no_graph_skips_implementation(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When no graph is attached, implementation is skipped gracefully."""
        request = ExecutorRequest(query="add a node", profile="default")
        result = run_executor(request)

        assert result.ok is True
        # Implementation should have a skip message, but edit still succeeds.
        assert result.report.implementation is not None
        assert "no graph" in result.report.implementation.message.lower()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_with_session_id_forwarded(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Session ID is forwarded to handle_agent_edit."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="edit graph",
            graph=input_graph,
            profile="default",
            session_id="sess-edit-1",
        )
        result = run_executor(request)

        assert result.ok is True
        # Verify handle_agent_edit was called with session_id.
        call_args = mock_edit.call_args[0][0]
        assert call_args["session_id"] == "sess-edit-1"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_result_to_dict(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Edit result serializes correctly."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="add KSampler",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)
        d = result.to_dict()

        assert d["ok"] is True
        assert "graph" in d
        assert d["report"]["executor"]["plan"]["implement"] is True
        assert d["report"]["executor"]["implementation"]["message"] is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_pure_clarify)
    def test_simple_edit_pure_clarify_is_not_promoted_to_candidate(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """A no-candidate agent-edit response must not become an applyable candidate."""
        input_graph = {"nodes": [{"id": 1, "type": "KSampler"}]}
        request = ExecutorRequest(
            query="Switch to generating 16 frames with Hotshot",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)
        payload = result.to_dict()

        assert result.ok is True
        assert result.graph is None
        assert result.reply == "Hotshot nodes are not currently installed."
        assert payload["outcome"]["kind"] == "clarify"
        assert payload["graph_unchanged"] is True
        assert payload["apply_eligible"] is False
        assert payload["candidate"] is None
        assert "graph" not in payload
        mock_reply.assert_not_called()

    @pytest.mark.parametrize("followup", ["You figure it out", "Pick some please"])
    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_delegated_clarification_followup_runs_prior_edit_route(
        self,
        mock_edit,
        mock_reply,
        mock_classify,
        followup: str,
        profile_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A "you decide" answer to a prior clarify is resolved by classify."""
        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        monkeypatch.setattr(
            executor_core,
            "_build_session_context",
            lambda _request: {
                "prior_clarification": {
                    "clarification_question": (
                        "Load external audio or keep the current text-to-audio setup?"
                    ),
                    "clarification_options": [
                        "Load external audio file",
                        "Use text-to-audio generation",
                    ],
                },
                "blocked_route": "revise",
                "blocked_task": "edit_graph",
            },
        )

        mock_classify.return_value = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="medium",
            intent="edit",
            route="revise",
            task="edit_graph",
            plan_summary=(
                "The user delegated the pending clarification; choose a "
                "reasonable default and continue the edit."
            ),
        )

        result = run_executor(
            ExecutorRequest(
                query=followup,
                graph=input_graph,
                profile="default",
                session_id="delegated-clarify",
            )
        )

        assert result.ok is True
        assert result.report.plan.effective_route == "revise"
        assert result.report.plan.implement is True
        assert result.report.plan.research is False
        assert mock_classify.call_count == 1
        classify_kwargs = mock_classify.call_args.kwargs
        assert "messages" in classify_kwargs
        classify_prompt = classify_kwargs["messages"][1]["content"]
        assert "Prior clarification question:" in classify_prompt
        assert "Load external audio or keep the current text-to-audio setup?" in classify_prompt
        mock_edit.assert_called_once()
        payload = mock_edit.call_args[0][0]
        assert payload["route"] == "revise"
        assert payload["executor_classification"]["task"] == "edit_graph"


# ── Graph-describe flow tests ────────────────────────────────────────────────


class TestGraphDescribeFlow:
    """Smoke tests for the graph-describe executor flow (research + implement → reply)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_graph_describe_default_profile(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Graph-describe with default profile runs research, implement, and reply."""


        input_graph = {
            "nodes": [
                {"id": 1, "type": "CLIPTextEncode"},
                {"id": 2, "type": "VAEDecode"},
            ]
        }
        request = ExecutorRequest(
            query="describe my graph and add a KSampler",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert "KSampler" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is True
        assert result.report.research is not None
        assert result.report.implementation is not None
        assert result.graph is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_executor_forwards_submit_freshness_fields(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Revise/adapt turns preserve browser freshness fields for durable apply CAS."""
        request = ExecutorRequest(
            query="switch to depth",
            graph={"nodes": [{"id": 1, "type": "ControlNetLoaderAdvanced"}], "links": []},
            workflow_id="6b4611de-b2b2-42f2-b358-5f566d6a8933",
            session_id="session-1",
            profile="default",
            idempotency_key="submit-key",
            client_graph_hash="client-graph-hash",
            client_structural_graph_hash="client-structural-hash",
            client_live_canvas_token="client-live-token",
            expected_baseline_graph_hash="expected-baseline-hash",
        )

        result = run_executor(request)

        assert result.ok is True
        payload = mock_edit.call_args[0][0]
        assert payload["session_id"] == "session-1"
        assert payload["workflow_id"] == "6b4611de-b2b2-42f2-b358-5f566d6a8933"
        assert payload["idempotency_key"] == "submit-key"
        assert payload["client_graph_hash"] == "client-graph-hash"
        assert payload["client_structural_graph_hash"] == "client-structural-hash"
        assert payload["client_live_canvas_token"] == "client-live-token"
        assert payload["expected_baseline_graph_hash"] == "expected-baseline-hash"
        from vibecomfy.comfy_nodes.agent.session import payload_hash

        assert mock_edit.call_args.kwargs["idempotency_request_hash"] == payload_hash(
            request.to_dict()
        )

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_graph_describe_openai_profile(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Graph-describe with openai profile."""


        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="what's in my graph and add a sampler",
            graph=input_graph,
            profile="openai",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is True
        assert result.report.plan.implement is True
        assert result.report.research is not None
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_graph_describe_research_failure_non_fatal(
        self,
        mock_hivemind,
        mock_edit,
        mock_reply,
        mock_classify,
        profile_dir: Path,
    ) -> None:
        """When research fails (empty corpus), the pipeline still completes."""

        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="describe and edit my graph",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.research is not None
        assert result.report.research.trace.status == "ok"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_graph_describe_with_graph_summary_context(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Classify receives graph summary when a graph is attached."""


        input_graph = {
            "nodes": [
                {"id": 1, "class_type": "CLIPTextEncode"},
                {"id": 2, "class_type": "KSampler"},
                {"id": 3, "class_type": "VAEDecode"},
            ]
        }
        request = ExecutorRequest(
            query="describe my pipeline and suggest improvements",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # Verify classify was called with has_graph=True.
        classify_call_kwargs = mock_classify.call_args.kwargs
        assert classify_call_kwargs.get("has_graph") is True

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_reply_receives_post_implementation_graph_summary(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Reply receives the graph returned by implementation, not stale input graph context."""


        request = ExecutorRequest(
            query="describe my pipeline and suggest improvements",
            graph={"nodes": [{"id": 1, "class_type": "CLIPTextEncode"}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        graph_summary = mock_reply.call_args.kwargs.get("graph_summary")
        assert graph_summary is not None
        assert "CLIPTextEncode" in graph_summary
        assert "KSampler" in graph_summary

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_reply_graph_summary_uses_replacement_implementation_graph(
        self, mock_hivemind, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Reply summaries describe the implemented graph, not the request graph."""

        def replace_graph(payload: dict, **kwargs: Any) -> dict:
            return {
                "graph": {"nodes": [{"id": 99, "class_type": "SaveImage"}]},
                "message": "Replaced graph with output node.",
            }


        request = ExecutorRequest(
            query="replace this workflow with a save image output",
            graph={"nodes": [{"id": 1, "class_type": "OriginalOnlyNode"}]},
            profile="default",
        )
        with mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=replace_graph):
            result = run_executor(request)

        assert result.ok is True
        assert result.graph == {"nodes": [{"id": 99, "class_type": "SaveImage"}]}
        graph_summary = mock_reply.call_args.kwargs.get("graph_summary")
        assert graph_summary is not None
        assert "SaveImage" in graph_summary
        assert "OriginalOnlyNode" not in graph_summary

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch(
        "vibecomfy.executor.core.run_research_phase",
        side_effect=RuntimeError(
            "research failed at https://example.test/search?token=secret-value&query=nodes "
            "with a verbose diagnostic that should be shortened before serialization"
        ),
    )
    def test_adapt_does_not_run_automatic_research_before_implementation(
        self, mock_research, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Adapt never calls the legacy automatic research engine."""
        result = run_executor(
            ExecutorRequest(
                query="describe and edit my graph",
                graph={"nodes": [{"id": 1, "class_type": "CLIPTextEncode"}]},
                profile="default",
            )
        )

        assert result.ok is True
        mock_research.assert_not_called()
        assert result.report.research is not None
        assert result.report.research.trace.status == "ok"
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch(
        "vibecomfy.executor.core._run_research",
        side_effect=executor_core._ExecutorPhaseError(
            stage="research",
            failure_kind="provider_error",
            message="research provider failed",
        ),
    )
    def test_adapt_skips_research_phase_error_path(
        self, mock_research, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Adapt never enters the removed legacy research wrapper."""
        result = run_executor(
            ExecutorRequest(
                query="describe and edit my graph",
                graph={"nodes": [{"id": 1, "class_type": "CLIPTextEncode"}]},
                profile="default",
            )
        )

        assert result.ok is True
        mock_research.assert_not_called()
        assert result.report.research is not None
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_adapt_implementation_receives_no_automatic_research_context(
        self,
        mock_hivemind,
        mock_edit,
        mock_reply,
        mock_classify,
        profile_dir: Path,
    ) -> None:
        """Adapt injects only the compact C1 ledger into the edit payload."""

        source_path = (
            "ready_templates/sources/custom_nodes/ltxvideo/runexx/"
            "LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.py"
        )

        input_graph = {"nodes": [{"id": 1, "class_type": "LTXImageToVideo"}]}
        request = ExecutorRequest(
            query="Add voice audio input so the generated character speaks from my clip.",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = mock_edit.call_args.args[0]
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        assert payload["research_ledger"]["entries"]
        wire_research = result.to_dict()["report"]["executor"]["research"]
        assert wire_research["ledger"] == payload["research_ledger"]
        assert "evidence_pack" not in wire_research
        assert "question" not in wire_research
        mock_hivemind.assert_not_called()
        reply_kwargs = mock_reply.call_args.kwargs
        assert reply_kwargs["research_ledger"] == payload["research_ledger"]
        assert "research_summary" not in reply_kwargs
        assert reply_kwargs["implementation_message"] == "Added a KSampler node to the graph."


# ── Explain-graph flow tests ─────────────────────────────────────────────────


class TestExplainGraphFlow:
    """Graph explanation uses the inspect route (reply only, no edit)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_explain_graph)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_explain_graph)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_explain)
    def test_explain_workflow_query_uses_inspect_route(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Asking 'what does this workflow do?' routes through classify → inspect → reply."""
        input_graph = {
            "nodes": [
                {"id": 1, "class_type": "CheckpointLoaderSimple"},
                {"id": 2, "class_type": "CLIPTextEncode"},
                {"id": 3, "class_type": "EmptyLatentImage"},
                {"id": 4, "class_type": "KSampler"},
                {"id": 5, "class_type": "VAEDecode"},
                {"id": 6, "class_type": "SaveImage"},
            ]
        }
        request = ExecutorRequest(
            query="What does this workflow do?",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.route == "inspect"
        assert result.report.plan.effective_route == "inspect"
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        assert result.report.plan.intent == "explain_graph"
        assert result.report.research is None
        assert result.report.implementation is None
        assert result.graph is None
        mock_edit.assert_not_called()


# ── Profile-only smoke coverage ──────────────────────────────────────────────


class TestProfileSmokeCoverage:
    """Profile-only smoke tests: verify each canonical profile resolves through
    the executor without live adapters or credentials.  Uses respond-only
    flow (the simplest path) to exercise profile resolution + classify + reply."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_default_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Default profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="default")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        # Verify classify was called with default profile's agent/model.
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"
        assert mock_classify.call_args.kwargs["effort"] == "low"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_openai_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """OpenAI profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="openai")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        # Verify classify was called with openai profile's agent/model.
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_anthropic_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Anthropic profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="anthropic")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_opensource_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Opensource profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="opensource")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_no_profile_defaults_to_default(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When profile is None, the default profile is used."""
        request = ExecutorRequest(query="hello", profile=None)
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_all_profiles_produce_deterministic_output_shape(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Every profile produces the same output shape."""
        for profile_name in ("default", "openai", "anthropic", "opensource"):
            request = ExecutorRequest(query="hello", profile=profile_name)
            result = run_executor(request)
            d = result.to_dict()
            assert "ok" in d
            assert "reply" in d
            assert "report" in d
            assert d.get("graph") is None
            assert d["report"]["executor"]["plan"]["research"] is False
            assert d["report"]["executor"]["plan"]["implement"] is False


# ── Edge case / regression tests ─────────────────────────────────────────────


class TestExecutorEdgeCases:
    """Regression tests for edge cases in executor flows."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_classify_progress_event_includes_plan_summary_and_intent(
        self, mock_ws_send, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """The Decide stage receives the model's classification direction."""
        request = ExecutorRequest(
            query="hello",
            session_id="session-plan",
            profile="default",
        )
        result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        classify_progress = next(
            payload
            for payload in phase_payloads
            if payload["phase"] == "classify" and payload["status"] == "progress"
        )
        assert classify_progress["plan_summary"] == "simple chat reply"
        assert classify_progress["intent"] == "respond"

    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_classify_phase_event_derives_summary_when_plan_summary_empty(
        self, mock_ws_send
    ) -> None:
        request = ExecutorRequest(query="edit it", session_id="session-fallback")
        plan = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            plan_summary="",
            intent="edit",
        )

        executor_core._emit_executor_phase_event(
            request,
            executor_id="executor-fallback",
            phase="classify",
            status="progress",
            plan=plan,
            client_id="client-1",
        )

        payload = mock_ws_send.call_args.args[1]
        assert payload["plan_summary"] == "Research workflow precedents, then adapt them to the current graph."
        assert payload["intent"] == "edit"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_missing_profile_file_fails_gracefully(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Requesting a nonexistent profile returns a failure result, not an exception."""
        request = ExecutorRequest(query="hello", profile="nonexistent_profile_xyz")
        result = run_executor(request)
        assert result.ok is False
        assert result.failure_stage == "profile"
        assert result.failure_kind is not None
        assert len(result.failure_message) > 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_idempotency_key_passed_through(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Idempotency keys don't cause errors (they are passed through)."""
        request = ExecutorRequest(
            query="hello", profile="default", idempotency_key="ik-test-1"
        )
        result = run_executor(request)
        assert result.ok is True

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_reply_only_never_invokes_handle_agent_edit(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When classify says implement=false, handle_agent_edit is never called."""
        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit"
        ) as mock_edit:
            request = ExecutorRequest(
                query="just chatting",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
            result = run_executor(request)
            assert result.ok is True
            mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_empty_graph_is_still_valid(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """An empty graph (nodes: []) passes through without errors."""
        request = ExecutorRequest(
            query="help",
            graph={"nodes": []},
            profile="default",
        )
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None


# ── Failure handling smoke tests ─────────────────────────────────────────────


class TestExecutorFailureHandling:
    """Verify the executor captures failures as ExecutorResult.failure, never raises."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn")
    def test_classify_provider_error_is_captured(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When classify raises ProviderError, the executor returns failure."""
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        mock_classify.side_effect = ProviderError("Model timeout")
        request = ExecutorRequest(query="test", profile="default")
        result = run_executor(request)

        assert result.ok is False
        assert result.failure_stage == "classify"
        assert result.failure_kind == "ProviderError"
        assert len(result.failure_message) > 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    def test_classify_failure_persists_only_canonical_model_attempts(
        self, mock_classify, profile_dir: Path
    ) -> None:
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        attempt = {
            "phase": "classify",
            "attempt": 1,
            "outcome": "failure",
            "failure_type": "malformed_json",
            "requested_model": "requested",
            "resolved_model": "resolved",
            "adapter": "hermes",
            "provider": "openrouter",
            "transport": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1",
            "finish_reason": "stop",
            "token_usage": {
                "prompt_tokens": 4,
                "completion_tokens": 2,
                "total_tokens": 6,
            },
            "raw_response_preview": "{broken",
        }
        error = ProviderError("bad classify response")
        error.model_attempts = [attempt]  # type: ignore[attr-defined]
        error.parse_reason = "legacy-must-not-persist"  # type: ignore[attr-defined]
        error.completion_tokens = 999  # type: ignore[attr-defined]
        mock_classify.side_effect = error

        result = run_executor(ExecutorRequest(query="test", profile="default"))
        executor_report = result.to_dict()["report"]["executor"]

        assert executor_report["model_attempts"] == [attempt]
        assert "model_response" not in executor_report
        persisted = json.dumps(executor_report)
        assert "legacy-must-not-persist" not in persisted
        assert '"turns"' not in persisted

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn")
    def test_reply_provider_error_is_captured(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When reply raises ProviderError, the executor returns failure."""
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        mock_reply.side_effect = ProviderError("Reply timeout")
        request = ExecutorRequest(query="test", profile="default")
        result = run_executor(request)

        assert result.ok is False
        assert result.failure_stage == "reply"
        assert result.failure_kind == "ProviderError"
        assert len(result.failure_message) > 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_implement_error_is_captured(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When handle_agent_edit raises, the executor returns failure."""
        mock_edit.side_effect = RuntimeError("Edit engine crashed")
        request = ExecutorRequest(
            query="edit graph",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is False
        assert result.failure_stage == "implement"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_reply_failure_preserves_durable_candidate(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When reply narration fails after durable edit work succeeds,
        the candidate, graph, and implementation result are preserved.
        Narration failure is presentation-only (T14)."""
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        mock_reply.side_effect = ProviderError("Reply narration failed")
        input_graph = {"nodes": [{"id": 1, "type": "VAEDecode"}]}
        request = ExecutorRequest(
            query="add a KSampler node",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        # Durable edit work must be preserved — ok=True, not a failure.
        assert result.ok is True
        # Graph must be present (the edit succeeded).
        assert result.graph is not None
        assert len(result.graph["nodes"]) == 2
        # Reply must be a deterministic fallback (implementation message).
        assert result.reply is not None
        assert len(result.reply) > 0
        # Implementation result must be preserved in the report.
        assert result.report.implementation is not None
        assert result.report.implementation.durable_response is not None

# ── Route gate flow tests (T5) ───────────────────────────────────────────────
# Verify that explicit routes only invoke their allowed phases.


def _fake_classify_revise(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a revise classification (implement only, no research)."""
    return ClassifyDecision(
        research=False,
        implement=True,
        reply=True,
        effort="low",
        plan_summary="direct edit — set seed",
        intent="edit",
        route="revise",
        task="edit_graph",
    )


def _fake_classify_inspect(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return an inspect classification (no research, no implement)."""
    return ClassifyDecision(
        research=False,
        implement=False,
        reply=True,
        effort="medium",
        plan_summary="inspect graph structure",
        intent="explain_graph",
        route="inspect",
        task="inspect_graph",
    )


def _fake_classify_clarify(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a clarify classification (no research, no implement)."""
    return ClassifyDecision(
        research=False,
        implement=False,
        reply=True,
        effort="low",
        plan_summary="ask clarifying question",
        intent="respond",
        route="clarify",
        task="respond",
    )


def _fake_classify_adapt(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Return a adapt classification (research + implement)."""
    return ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        effort="high",
        plan_summary="research precedent workflow then edit",
        intent="edit",
        route="adapt",
        task="research_precedent",
    )


def _agent_owned_research_result(
    summary: str = "Agent research done.",
) -> AgentResearchResult:
    """Minimal H01 agent-owned research result with a compact ledger."""
    ledger = EvidenceLedger(entries=(
        EvidenceLedgerEntry(
            decision="agent_research",
            conclusion=summary,
            evidence_ids=("hivemind_get:abc123",),
            uncertainty="low",
        ),
        EvidenceLedgerEntry(
            decision=DECISION_GET,
            conclusion="workflow record hivemind_get:abc123",
            evidence_ids=("hivemind_get:abc123",),
            uncertainty="",
        ),
        EvidenceLedgerEntry(
            decision=DECISION_SYNTHESIZE,
            conclusion=summary,
            evidence_ids=("hivemind_get:abc123",),
            uncertainty="low",
        ),
    ))
    trace = AgentResearchTrace(
        route="adapt",
        question="q",
        iterations=(),
        final_verdict="enough",
        summary=summary,
        citations=("hivemind_get:abc123",),
        uncertainty="low",
        status="ok",
        elapsed_seconds=0.0,
    )
    pack = EvidencePack(
        artifacts={
            "hivemind_get:abc123": EvidenceArtifact(
                evidence_id="hivemind_get:abc123",
                kind="hivemind_get",
                body={"content": "fixture fetched record"},
                source="hivemind",
            )
        },
        ledger=EvidenceLedger(entries=ledger.entries),
    )
    package = executor_core._research_stage_package(
        route="adapt",
        trace=trace,
        pack=pack,
        policy_diagnostics=(),
    )
    return AgentResearchResult(
        route="adapt",
        trace=trace,
        evidence_pack=pack,
        package=package,
    )


def test_agent_research_handoff_carries_only_compact_ledger() -> None:
    """The adapt implement payload receives only the compact C1 ledger.

    The legacy research result (no ledger attribute) is gone; the active
    agent-owned result forwards its evidence ledger — and nothing else:
    no research_summary prose, no precedent slices, no adaptation plans.
    """
    plan = _fake_classify_adapt("Switch to Hotshot")
    request = ExecutorRequest(
        query="Switch to Hotshot",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = _agent_owned_research_result(
        summary="Research skipped due to an internal error."
    )

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    assert result.graph is not None
    payload = mock_edit.call_args.args[0]
    assert payload["research_ledger"]["entries"][0]["conclusion"] == (
        "Research skipped due to an internal error."
    )
    assert payload["research_ledger"]["entries"][0]["evidence_ids"] == ["hivemind_get:abc123"]
    assert "research_summary" not in payload
    assert "precedent_slices" not in payload
    assert "adaptation_plan" not in payload
    assert "execution_plan" not in payload


def _agent_owned_research_result_with_trace(trace: AgentResearchTrace) -> AgentResearchResult:
    """AgentResearchResult carrying a typed research StagePackage — the live
    shape the executor hands from research to implement."""
    pack = EvidencePack(artifacts={}, ledger=EvidenceLedger(entries=()))
    package = executor_core._research_stage_package(
        route="adapt",
        trace=trace,
        pack=pack,
        policy_diagnostics=(),
    )
    return AgentResearchResult(
        route="adapt",
        trace=trace,
        evidence_pack=pack,
        package=package,
    )


def _failed_research_trace(*, status: str = "failed", verdict: str = "failed") -> AgentResearchTrace:
    return AgentResearchTrace(
        route="adapt",
        question="q",
        iterations=(),
        final_verdict=verdict,
        summary="",
        citations=(),
        uncertainty="",
        status=status,
        elapsed_seconds=0.0,
        error="boom" if status == "failed" else None,
    )


def _adapt_never_research_result() -> AgentResearchResult:
    """Adapt research result typed ``never`` (zero executed tool calls)."""
    return _agent_owned_research_result_with_trace(
        AgentResearchTrace(
            route="adapt",
            question="q",
            iterations=(),
            final_verdict="enough",
            summary="",
            citations=(),
            uncertainty="",
            status="ok",
            elapsed_seconds=0.0,
        )
    )


def test_adapt_implement_proceeds_when_research_failed_with_graph() -> None:
    """RC2: UNAVAILABLE research on adapt with a graph still implements."""
    plan = _fake_classify_adapt("Set KSampler.steps to 30")
    request = ExecutorRequest(
        query="Set KSampler.steps to 30",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = _agent_owned_research_result_with_trace(_failed_research_trace())

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    mock_edit.assert_called_once()
    assert result.graph is not None


def test_adapt_implement_proceeds_when_research_exhausted_with_graph() -> None:
    """RC2: exhausted-from-timeout no longer skips implement on adapt+graph."""
    plan = _fake_classify_adapt("Set KSampler.steps to 30")
    request = ExecutorRequest(
        query="Set KSampler.steps to 30",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = _agent_owned_research_result_with_trace(
        _failed_research_trace(status="exhausted", verdict="refine")
    )

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    mock_edit.assert_called_once()
    assert result.graph is not None
    assert research.package.status is ToolStatus.UNAVAILABLE
    codes = [diag.code for diag in research.package.diagnostics]
    assert "research_stage_exhausted" in codes


def test_adapt_implement_proceeds_when_research_never_with_graph() -> None:
    """RC2: a ``never`` attempt on adapt with a graph still implements."""
    plan = _fake_classify_adapt("Set KSampler.steps to 30")
    request = ExecutorRequest(
        query="Set KSampler.steps to 30",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = _adapt_never_research_result()
    assert research.research_attempt == RESEARCH_ATTEMPT_NEVER

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    mock_edit.assert_called_once()
    assert result.graph is not None


def test_adapt_implement_skips_when_research_never_without_graph() -> None:
    """RC2: never/empty still skip implement when there is no graph to act on."""
    plan = _fake_classify_adapt("Set KSampler.steps to 30")
    request = ExecutorRequest(query="Set KSampler.steps to 30", graph=None)
    research = _adapt_never_research_result()

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    mock_edit.assert_not_called()
    assert result.graph is None
    assert "research produced no" in result.message


def test_adapt_implement_proceeds_for_widget_edit_when_research_unavailable() -> None:
    """RC2 flow: named widget / fps / missing-edge work proceeds on UNAVAILABLE."""
    plan = _fake_classify_adapt("Set EmptyLatentImage batch to 8")
    request = ExecutorRequest(
        query="Set EmptyLatentImage batch to 8",
        graph={"nodes": [{"id": 1, "type": "EmptyLatentImage", "widgets_values": [512, 512, 1]}], "links": []},
    )
    thin_pack = EvidencePack(
        artifacts={
            "hivemind:ext:1": EvidenceArtifact(
                evidence_id="hivemind:ext:1",
                kind="hivemind_search_hit",
                body={"title": "lead"},
                source="hivemind",
            ),
        },
        ledger=EvidenceLedger(entries=(
            EvidenceLedgerEntry(
                decision="hivemind_search",
                conclusion="timeout: hivemind timed out",
                evidence_ids=("hivemind:ext:1",),
                uncertainty="timeout: hivemind timed out",
            ),
        )),
    )
    trace = _failed_research_trace(status="exhausted", verdict="refine")
    research = AgentResearchResult(
        route="adapt",
        trace=trace,
        evidence_pack=thin_pack,
        package=executor_core._research_stage_package(
            route="adapt", trace=trace, pack=thin_pack, policy_diagnostics=(),
        ),
    )
    assert research.research_attempt == RESEARCH_ATTEMPT_THIN
    assert research.package.status is ToolStatus.OK

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    mock_edit.assert_called_once()
    assert result.graph is not None


def test_adapt_implement_proceeds_when_research_grounded() -> None:
    """Batch 14: a ``grounded`` attempt (fetched citation) proceeds to
    implement."""
    plan = _fake_classify_adapt("Switch to Hotshot")
    request = ExecutorRequest(
        query="Switch to Hotshot",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = _agent_owned_research_result()
    assert research.research_attempt == RESEARCH_ATTEMPT_GROUNDED

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    assert result.graph is not None
    mock_edit.assert_called_once()


def _refined_research_result_with_synthesis() -> AgentResearchResult:
    """Refine-verdict research result whose ledger records an evidence-backed
    partial synthesis (a fetched hivemind_get citation) — typed ``grounded``."""
    trace = AgentResearchTrace(
        route="adapt",
        question="q",
        iterations=(),
        final_verdict="refine",
        summary="Partial direction: LoadAudio before the video model.",
        citations=("hivemind_get:abc123",),
        uncertainty="Hivemind statement timeout; direction is provisional",
        status="ok",
        elapsed_seconds=0.0,
    )
    ledger = EvidenceLedger(entries=(
        EvidenceLedgerEntry(
            decision=DECISION_GET,
            conclusion="workflow record hivemind_get:abc123",
            evidence_ids=("hivemind_get:abc123",),
            uncertainty="",
        ),
        EvidenceLedgerEntry(
            decision=DECISION_SYNTHESIZE,
            conclusion="Use LoadAudio -> ConditioningCombine before WanImageToVideo",
            evidence_ids=("hivemind_get:abc123",),
            uncertainty="provisional",
        ),
    ))
    pack = EvidencePack(
        artifacts={
            "hivemind_get:abc123": EvidenceArtifact(
                evidence_id="hivemind_get:abc123",
                kind="hivemind_get",
                body={"content": "fixture fetched record"},
                source="hivemind",
            )
        },
        ledger=ledger,
    )
    package = executor_core._research_stage_package(
        route="adapt",
        trace=trace,
        pack=pack,
        policy_diagnostics=(),
    )
    return AgentResearchResult(
        route="adapt",
        trace=trace,
        evidence_pack=pack,
        package=package,
    )


def test_adapt_implement_proceeds_when_research_refined_with_synthesis() -> None:
    """Batch 14: a refine verdict WITH a fetched-citation partial synthesis is
    typed ``grounded`` and proceeds to implement."""
    plan = _fake_classify_adapt("Switch to Hotshot")
    request = ExecutorRequest(
        query="Switch to Hotshot",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = _refined_research_result_with_synthesis()
    assert research.research_attempt == RESEARCH_ATTEMPT_GROUNDED

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=research,
        )

    assert result.graph is not None
    mock_edit.assert_called_once()
    payload = mock_edit.call_args.args[0]
    ledger = payload["research_ledger"]["entries"]
    assert any(
        entry["decision"] == DECISION_SYNTHESIZE and entry["evidence_ids"]
        for entry in ledger
    )


def test_research_package_usable_gate_matrix() -> None:
    """RC2 gate matrix: thin/grounded stay usable; never/empty/UNAVAILABLE
    become usable on adapt when a graph is attached."""
    base_kwargs = dict(
        route="adapt",
        question="q",
        iterations=(),
        summary="",
        citations=(),
        uncertainty="",
        status="ok",
        elapsed_seconds=0.0,
    )
    assert executor_core._research_package_is_usable(None) is False
    failed = _agent_owned_research_result_with_trace(
        _failed_research_trace(status="failed", verdict="failed")
    )
    assert executor_core._research_package_is_usable(failed) is False
    assert executor_core._research_package_is_usable(
        failed, route="adapt", has_graph=True
    ) is True
    exhausted = _agent_owned_research_result_with_trace(
        _failed_research_trace(status="exhausted", verdict="refine")
    )
    assert executor_core._research_package_is_usable(exhausted) is False
    assert executor_core._research_package_is_usable(
        exhausted, route="adapt", has_graph=True
    ) is True
    never_result = _adapt_never_research_result()
    assert never_result.research_attempt == RESEARCH_ATTEMPT_NEVER
    assert executor_core._research_package_is_usable(never_result) is False
    assert executor_core._research_package_is_usable(
        never_result, route="adapt", has_graph=True
    ) is True
    empty_trace = AgentResearchTrace(final_verdict="enough", **base_kwargs)
    empty_pack = EvidencePack(
        artifacts={},
        ledger=EvidenceLedger(entries=(
            EvidenceLedgerEntry(
                decision=DECISION_GET,
                conclusion="timeout: hivemind timed out",
                evidence_ids=(),
                uncertainty="timeout: hivemind timed out",
            ),
        )),
    )
    empty_result = AgentResearchResult(
        route="adapt",
        trace=empty_trace,
        evidence_pack=empty_pack,
        package=executor_core._research_stage_package(
            route="adapt", trace=empty_trace, pack=empty_pack, policy_diagnostics=(),
        ),
    )
    assert empty_result.research_attempt == RESEARCH_ATTEMPT_EMPTY
    assert executor_core._research_package_is_usable(empty_result) is False
    assert executor_core._research_package_is_usable(
        empty_result, route="adapt", has_graph=True
    ) is True
    # grounded → usable (the recovery path now types by fetched citation).
    assert executor_core._research_package_is_usable(
        _refined_research_result_with_synthesis()
    ) is True
    # thin (search hits only, no fetched citation) → usable.
    thin_trace = AgentResearchTrace(final_verdict="enough", **base_kwargs)
    thin_pack = EvidencePack(
        artifacts={
            "hivemind:ext:1": EvidenceArtifact(
                evidence_id="hivemind:ext:1",
                kind="hivemind_search_hit",
                body={"title": "lead"},
                source="hivemind",
            ),
        },
        ledger=EvidenceLedger(entries=(
            EvidenceLedgerEntry(
                decision="hivemind_search",
                conclusion="1 hit(s)",
                evidence_ids=("hivemind:ext:1",),
                uncertainty="",
            ),
            EvidenceLedgerEntry(
                decision=DECISION_SYNTHESIZE,
                conclusion="direction from search lead",
                evidence_ids=("hivemind:ext:1",),
                uncertainty="",
            ),
        )),
    )
    thin_result = AgentResearchResult(
        route="adapt",
        trace=thin_trace,
        evidence_pack=thin_pack,
        package=executor_core._research_stage_package(
            route="adapt", trace=thin_trace, pack=thin_pack, policy_diagnostics=(),
        ),
    )
    assert thin_result.research_attempt == RESEARCH_ATTEMPT_THIN
    assert executor_core._research_package_is_usable(thin_result) is True
    thin_unavailable_trace = AgentResearchTrace(
        final_verdict="refine",
        **{**base_kwargs, "status": "exhausted"},
    )
    thin_unavailable = AgentResearchResult(
        route="adapt",
        trace=thin_unavailable_trace,
        evidence_pack=thin_pack,
        package=executor_core._research_stage_package(
            route="adapt",
            trace=thin_unavailable_trace,
            pack=thin_pack,
            policy_diagnostics=(),
        ),
    )
    assert thin_unavailable.research_attempt == RESEARCH_ATTEMPT_THIN
    # RC1: artifacts exist, so a 57014/exhaustion does not fail the package.
    assert thin_unavailable.package.status is ToolStatus.OK
    assert executor_core._research_package_is_usable(thin_unavailable) is True


def test_run_executor_implements_when_adapt_research_never(profile_dir: Path) -> None:
    """RC2 end-to-end: never research on adapt with a graph still implements."""
    def never_research_stage(*, route: str, question: str, spec: Any, research_brief: str = "") -> tuple[AgentResearchTrace, EvidencePack]:
        del route, spec, research_brief
        return _failed_research_trace(status="ok", verdict="refine"), EvidencePack(
            artifacts={
                "research_question": EvidenceArtifact(
                    evidence_id="research_question",
                    kind="research_question",
                    body={"question": question, "route": "adapt"},
                    source="classify",
                ),
            },
            ledger=EvidenceLedger(entries=(
                EvidenceLedgerEntry(
                    decision="research_question",
                    conclusion=question,
                    evidence_ids=("research_question",),
                    uncertainty="",
                ),
            )),
        )

    with mock.patch(
        "vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt
    ), mock.patch(
        "vibecomfy.executor.core.run_agent_research_stage", side_effect=never_research_stage
    ), mock.patch(
        "vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe
    ) as mock_reply, mock.patch(
        "vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit
    ) as mock_edit:
        result = run_executor(
            ExecutorRequest(
                query="Switch to Hotshot",
                graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
                profile="default",
            )
        )

    assert result.ok is True
    assert result.report.research.research_attempt == RESEARCH_ATTEMPT_NEVER
    assert result.report.implementation is not None
    assert result.report.implementation.graph is not None
    mock_edit.assert_called_once()
    mock_reply.assert_called_once()


# ── Batch 14: semantic non-gating enforced on the PRODUCED reply ─────────────


def _fake_reply_model_turn(
    task: str,
    messages: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Provider-level fake for the REAL reply turn (batch 14).

    Emulates a model that follows the reply prompt: if the prompt still
    carries the C5 ``return this bounded content`` relay instruction, or the
    memo still contains a fake synthesis (``synthesis produced no
    conclusion``), it refuses — which trips the assertions below.  Otherwise
    it answers substantively from the query/graph and never refuses on thin
    research.
    """
    del kwargs
    prompt_text = "\n".join(
        str(message.get("content") or "") for message in (messages or [])
    )
    if "return this bounded content" in prompt_text:
        return {"content": "I cannot provide a supported conclusion."}
    if "synthesis produced no conclusion" in prompt_text:
        return {"content": "No supported conclusion was produced by research."}
    query = str(task or "")
    query_l = query.casefold()
    if "hotshot" in query_l:
        return {
            "content": (
                "Your graph contains a single KSampler node with no model "
                "checkpoint attached. Switching to a Hotshot workflow means "
                "replacing the checkpoint with a Hotshot-compatible video "
                "model and adding the Hotshot loader nodes. No outside "
                "sources were found, so this is based on the attached graph "
                "and general knowledge."
            )
        }
    if "upscale" in query_l:
        return {
            "content": (
                "For latent upscaling without changing your sampler, add a "
                "LatentUpscale node after the KSampler and keep the sampler "
                "settings unchanged — the upscale operates on the latent "
                "before decoding."
            )
        }
    return {
        "content": (
            "The attached workflow contains one KSampler node. A KSampler "
            "takes a model, positive and negative conditioning, and a latent "
            "image, then runs the configured sampler steps to produce a "
            "denoised latent."
        )
    }


def test_research_as_answer_reply_is_substantive_when_research_never_empty(profile_dir: Path) -> None:
    """Batch 14: never/empty research NEVER gates the research-as-answer reply.

    The real reply turn runs (only the provider model call is faked) and the
    produced reply is a substantive answer addressing the query — no
    ``no supported conclusion`` refusal.  The decision memo is attempt-typed:
    a never/empty attempt carries its own conclusion (no evidence tools were
    called / no evidence was gathered), never a fake synthesis from a blank
    trace.summary.
    """
    def research_stage_for(attempt: str):
        def stage(
            *,
            route: str,
            question: str,
            spec: Any,
            research_brief: str = "",
        ) -> tuple[AgentResearchTrace, EvidencePack]:
            del route, spec, research_brief
            question_artifact = EvidenceArtifact(
                evidence_id="research_question",
                kind="research_question",
                body={"question": question, "route": "research"},
                source="classify",
            )
            if attempt == RESEARCH_ATTEMPT_NEVER:
                return _failed_research_trace(status="ok", verdict="refine"), EvidencePack(
                    artifacts={"research_question": question_artifact},
                    ledger=EvidenceLedger(entries=(
                        EvidenceLedgerEntry(
                            decision="research_question",
                            conclusion=question,
                            evidence_ids=("research_question",),
                            uncertainty="",
                        ),
                    )),
                )
            return AgentResearchTrace(
                route="research",
                question=question,
                iterations=(),
                final_verdict="refine",
                summary="",
                citations=(),
                uncertainty="",
                status="ok",
                elapsed_seconds=0.0,
            ), EvidencePack(
                artifacts={"research_question": question_artifact},
                ledger=EvidenceLedger(entries=(
                    EvidenceLedgerEntry(
                        decision="research_question",
                        conclusion=question,
                        evidence_ids=("research_question",),
                        uncertainty="",
                    ),
                    EvidenceLedgerEntry(
                        decision=DECISION_GET,
                        conclusion="no_results: hivemind returned nothing",
                        evidence_ids=(),
                        uncertainty="no_results: hivemind returned nothing",
                    ),
                )),
            )

        return stage

    def classify_research(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="research Hotshot workflows",
            intent="research",
            route="research",
            task="research_nodes",
        )

    for attempt in (RESEARCH_ATTEMPT_NEVER, RESEARCH_ATTEMPT_EMPTY):
        with mock.patch(
            "vibecomfy.executor.core.run_classify_turn", side_effect=classify_research
        ), mock.patch(
            "vibecomfy.executor.core.run_agent_research_stage",
            side_effect=research_stage_for(attempt),
        ), mock.patch(
            "vibecomfy.comfy_nodes.agent.provider.run_model_turn",
            side_effect=_fake_reply_model_turn,
        ):
            result = run_executor(
                ExecutorRequest(
                    query="What is the best way to run Hotshot workflows?",
                    graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
                    profile="default",
                )
            )

        assert result.ok is True, result.failure_message
        assert result.report.research is not None
        assert result.report.research.research_attempt == attempt
        memo = result.report.research.decision_memo
        assert memo is not None
        assert memo["research_attempt"] == attempt
        conclusion = memo["conclusion"].casefold()
        assert "synthesis produced no conclusion" not in conclusion
        if attempt == RESEARCH_ATTEMPT_NEVER:
            assert "no evidence tools were called" in conclusion
        else:
            assert "evidence tools were called but returned no evidence" in conclusion
        # The produced reply is substantive and addresses the query — the
        # real reply turn ran with the provider faked, not run_reply_turn.
        assert result.reply is not None and result.reply.strip()
        assert "no supported conclusion" not in result.reply.casefold()
        assert "hotshot" in result.reply.casefold()


def test_research_reply_prompt_has_no_c5_return_instruction() -> None:
    """Batch 14: the research reply prompt no longer tells the model to RELAY
    the C5 memo as bounded content — the memo is evidence it may cite from,
    and on never/empty the model answers from the graph + knowledge."""
    from vibecomfy.executor.prompts import build_reply_messages

    memo = {
        "question": "How should I run Hotshot workflows?",
        "conclusion": (
            "No evidence tools were called; no external evidence was gathered. "
            "Answer from the attached workflow graph and general knowledge."
        ),
        "citations": [],
        "uncertainty": "",
        "research_attempt": RESEARCH_ATTEMPT_NEVER,
        "next_action": (
            "Answer from the attached graph and general knowledge; "
            "no external evidence was gathered."
        ),
    }
    messages = build_reply_messages(
        "What is the best way to run Hotshot workflows?",
        plan=ClassifyDecision(
            research=True, implement=False, reply=True, route="research"
        ),
        research_memo=memo,
        research_attempt=RESEARCH_ATTEMPT_NEVER,
        effective_route="research",
        graph_summary="[1] KSampler\n",
    )
    system = messages[0]["content"]
    user = messages[1]["content"]
    # The C5-return relay contract is deleted from the reply prompt.
    assert "return this bounded content" not in system
    assert "return this bounded content" not in user
    assert "no invented sources" not in system
    assert "no invented sources" not in user
    # The memo is still supplied as citable evidence — not verbatim relay.
    assert "C5 decision memo" in system
    assert "never relay the memo verbatim" in system
    assert "C5 research decision memo" in user
    assert '"research_attempt": "never"' in user
    # On never/empty the model answers from the graph + knowledge.
    assert "research_attempt=never/empty" in system
    assert "answer directly from " in system


def test_inspect_and_respond_reply_substantive_without_research(profile_dir: Path) -> None:
    """Batch 14: inspect/respond routes with never/empty research (research
    skipped — zero evidence tools) still produce a substantive answer from the
    graph + knowledge; no 'no supported conclusion' refusal on any route."""
    def classify_inspect(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="explain what the graph does",
            intent="explain_graph",
            route="inspect",
            task="inspect_graph",
        )

    def classify_respond(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="low",
            plan_summary="answer directly",
            intent="respond",
            route="respond",
            task="respond",
        )

    with mock.patch(
        "vibecomfy.executor.core.run_classify_turn", side_effect=classify_inspect
    ), mock.patch(
        "vibecomfy.comfy_nodes.agent.provider.run_model_turn",
        side_effect=_fake_reply_model_turn,
    ):
        inspect_result = run_executor(
            ExecutorRequest(
                query="Explain what this graph does",
                graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
                profile="default",
            )
        )

    assert inspect_result.ok is True, inspect_result.failure_message
    assert inspect_result.report.plan.effective_route == "inspect"
    # Research skipped on inspect → research outcome is effectively never.
    assert inspect_result.report.research is None
    assert inspect_result.reply is not None and inspect_result.reply.strip()
    assert "no supported conclusion" not in inspect_result.reply.casefold()
    assert "ksampler" in inspect_result.reply.casefold()

    with mock.patch(
        "vibecomfy.executor.core.run_classify_turn", side_effect=classify_respond
    ), mock.patch(
        "vibecomfy.comfy_nodes.agent.provider.run_model_turn",
        side_effect=_fake_reply_model_turn,
    ):
        respond_result = run_executor(
            ExecutorRequest(
                query="How do I upscale latents without changing my sampler?",
                profile="default",
            )
        )

    assert respond_result.ok is True, respond_result.failure_message
    assert respond_result.report.plan.effective_route == "respond"
    assert respond_result.report.research is None
    assert respond_result.reply is not None and respond_result.reply.strip()
    assert "no supported conclusion" not in respond_result.reply.casefold()
    assert "upscale" in respond_result.reply.casefold()


def test_adapt_payload_never_builds_deterministic_execution_plan_note() -> None:
    plan = ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        effort="high",
        plan_summary="research HotShotXL workflow precedent then edit",
        intent="edit",
        route="adapt",
        task="research_precedent",
        research_goal="Find HotShotXL AnimateDiff workflow precedents.",
        search_directions=("HotShotXL AnimateDiff 8 frame workflow template",),
    )
    request = ExecutorRequest(
        query="Switch this to generate 8 frames of video using a HotShotXL workflow template.",
        graph={"nodes": [{"id": 1, "type": "KSampler", "class_type": "KSampler"}], "links": []},
    )

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit",
        side_effect=_fake_handle_agent_edit,
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=_agent_owned_research_result(),
        )

    assert result.graph is not None
    payload = mock_edit.call_args[0][0]
    assert "execution_protocol_notes" not in payload
    assert "precedent_slices" not in payload
    assert "adaptation_plan" not in payload
    assert "execution_plan" not in payload
    # The only research content crossing the boundary is the compact ledger.
    assert payload["research_ledger"]["entries"][0]["evidence_ids"] == ["hivemind_get:abc123"]


def test_adapt_payload_does_not_hydrate_legacy_precedent_shapes() -> None:
    """Legacy precedent/adaptation dicts never leak into the implement payload."""
    plan = ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        route="adapt",
        intent="edit",
        task="research_precedent",
    )
    request = ExecutorRequest(
        query="Use IP-Adapter to feed the SDXL reference image",
        graph={"nodes": [{"id": 5, "type": "KSampler"}], "links": []},
    )

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit",
        side_effect=_fake_handle_agent_edit,
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=_agent_owned_research_result(),
        )

    assert result.graph is not None
    payload = mock_edit.call_args[0][0]
    assert "execution_protocol_notes" not in payload
    assert "adaptation_plan" not in payload
    assert "precedent_slices" not in payload
    assert "precedent_packet" not in payload
    # The compact C1 ledger is the only research handoff.
    assert payload["research_ledger"]["entries"][0]["decision"] == "agent_research"


def test_adapt_execution_path_has_no_deterministic_plan_builder_symbol() -> None:
    plan = ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        effort="high",
        plan_summary="research HotShotXL workflow precedent then edit",
        intent="edit",
        route="adapt",
        task="research_precedent",
        research_goal="Find HotShotXL AnimateDiff workflow precedents.",
    )
    request = ExecutorRequest(
        query="Switch this to generate 8 frames of video using HotShotXL.",
        graph={"nodes": [{"id": 1, "type": "KSampler", "class_type": "KSampler"}], "links": []},
    )

    with mock.patch(
        "vibecomfy.executor.core.handle_agent_edit",
        side_effect=_fake_handle_agent_edit,
    ) as mock_edit:
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=_agent_owned_research_result(),
        )

    assert result.graph is not None
    payload = mock_edit.call_args[0][0]
    assert "execution_protocol_notes" not in payload
    assert not hasattr(executor_core, "build_execution_plan")


def _fake_reply_route_gate(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> str:
    """Fake reply for route gate tests."""
    return "Task completed."


class TestRouteGateFlows:
    """Verify that explicit routes invoke only their allowed phases.

    respond: research ✗  implement ✗  reply ✓
    revise:  research ✗  implement ✓  reply ✓
    inspect: research ✗  implement ✗  reply ✓
    clarify:      research ✗  implement ✗  reply ✓
    adapt: research ✓  implement ✓  reply ✓
    """

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_respond_skips_research_and_implementation(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """respond: research and implementation are skipped, reply runs."""
        with mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit:
            request = ExecutorRequest(
                query="can you explain the previous failure?",
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.effective_route == "respond"
        assert result.report.research is None
        assert result.report.implementation is None
        mock_edit.assert_not_called()
        mock_reply.assert_called_once()
        mock_classify.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_revise_skips_research_calls_implement(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: research phase is never entered, implementation runs."""
        input_graph = {"nodes": [{"id": 1, "type": "VAEDecode"}]}
        request = ExecutorRequest(
            query="set seed to 42",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # Research MUST NOT be called.
        # Implementation MUST be called.
        mock_edit.assert_called_once()
        # Reply MUST be called.
        mock_reply.assert_called_once()
        # Classify MUST be called.
        mock_classify.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_revise_report_flags_correct_phases(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise report: research=None, implementation present, route=revise."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="edit the graph",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # Plan route is revise
        assert result.report.plan.route == "revise"
        assert result.report.plan.effective_route == "revise"
        # Legacy booleans
        assert result.report.plan.research is False
        assert result.report.plan.implement is True
        # Research is None (never entered)
        assert result.report.research is None
        # Implementation present
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_revise_payload_uses_canonical_route_and_provider_metadata(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise uses handle_agent_edit as an internal candidate engine."""
        request = ExecutorRequest(
            query="edit the graph",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = mock_edit.call_args.args[0]
        assert payload["route"] == "revise"
        assert payload["executor_route"] == "revise"
        assert payload["provider_route"] == "codex"
        assert payload["executor_classification"]["route"] == "revise"
        assert payload["executor_classification"]["task"] == "edit_graph"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_inspect_calls_research_skips_implementation(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: research is skipped, implementation is skipped."""


        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit"
        ) as mock_edit:
            input_graph = {"nodes": [{"id": 1, "type": "VAEDecode"}]}
            request = ExecutorRequest(
                query="explain my graph",
                graph=input_graph,
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # Research MUST NOT be called.
        # Implementation MUST NOT be called.
        mock_edit.assert_not_called()
        # Reply MUST be called.
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_inspect_report_flags_correct_phases(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect report: research=None, implementation=None, route=inspect."""


        request = ExecutorRequest(
            query="what's in my graph?",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == "inspect"
        assert result.report.plan.effective_route == "inspect"
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        # Research absent (inspect never runs research)
        assert result.report.research is None
        # Implementation is None (never entered)
        assert result.report.implementation is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_clarify)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_clarify_skips_both_research_and_implementation(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """clarify: neither research nor implementation is invoked."""
        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit"
        ) as mock_edit:
            request = ExecutorRequest(
                query="what do you mean?",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # Research MUST NOT be called.
        # Implementation MUST NOT be called.
        mock_edit.assert_not_called()
        # Reply MUST be called.
        mock_reply.assert_called_once()
        # Classify MUST be called.
        mock_classify.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_clarify)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_clarify_report_flags_correct_phases(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """clarify report: research=None, implementation=None, route=clarify."""
        request = ExecutorRequest(
            query="can you clarify?",
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == "clarify"
        assert result.report.plan.effective_route == "clarify"
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        # Neither research nor implementation ran
        assert result.report.research is None
        assert result.report.implementation is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_adapt_calls_both_research_and_implementation(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: both research and implementation phases run."""


        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add audio to my LTX workflow",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # The active C1 stage replaces deterministic corpus prefetch.
        # Implementation MUST be called.
        mock_edit.assert_called_once()
        # Reply MUST be called.
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_research_hang_retry_skips_research_but_runs_product_path(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """I-B live path: the retry cannot re-enter the hanging research phase.

        Classify, implement, reply, and the normal result construction still
        execute.  The switch is scoped to the retry child environment.
        """
        monkeypatch.setenv("VIBECOMFY_RESEARCH_HANG_RETRY_SKIP", "1")
        with mock.patch(
            "vibecomfy.executor.core._run_agent_owned_research",
            side_effect=AssertionError("research must be skipped on the retry"),
        ) as mock_research:
            result = run_executor(
                ExecutorRequest(
                    query="adapt the graph after research infrastructure hung",
                    graph={"nodes": [{"id": 1, "type": "LoadImage"}]},
                    profile="default",
                )
            )

        assert result.ok is True
        assert result.report.plan.effective_route == "adapt"
        assert result.report.research is None
        assert result.report.implementation is not None
        mock_research.assert_not_called()
        mock_edit.assert_called_once()
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_adapt_report_flags_correct_phases(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt report: research present, implementation present."""


        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="adapt workflow precedent",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == "adapt"
        assert result.report.plan.effective_route == "adapt"
        assert result.report.plan.research is True
        assert result.report.plan.implement is True
        # Both research and implementation present
        assert result.report.research is not None
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_adapt_payload_uses_canonical_route_and_provider_metadata(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt keeps provider dispatch separate from executor route semantics."""


        request = ExecutorRequest(
            query="adapt workflow precedent",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = mock_edit.call_args.args[0]
        assert payload["route"] == "adapt"
        assert payload["executor_route"] == "adapt"
        assert payload["provider_route"] == "codex"
        assert payload["executor_classification"]["route"] == "adapt"
        assert payload["executor_classification"]["task"] == "research_precedent"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_revise_phase_event_includes_route_and_task(
        self,
        mock_ws_send: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """WebSocket classify progress event emits route and task for revise."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="set seed to 42",
            graph=input_graph,
            session_id="sess-route-gate",
            profile="default",
        )
        result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        classify_progress = next(
            payload
            for payload in phase_payloads
            if payload["phase"] == "classify" and payload["status"] == "progress"
        )
        assert classify_progress["route"] == "revise"
        assert classify_progress["task"] == "edit_graph"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_inspect_phase_event_includes_route_and_task(
        self,
        mock_ws_send: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """WebSocket classify progress event emits route and task for inspect."""


        request = ExecutorRequest(
            query="explain my graph",
            graph={"nodes": [{"id": 1}]},
            session_id="sess-inspect",
            profile="default",
        )
        result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        classify_progress = next(
            payload
            for payload in phase_payloads
            if payload["phase"] == "classify" and payload["status"] == "progress"
        )
        assert classify_progress["route"] == "inspect"
        assert classify_progress["task"] == "inspect_graph"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_clarify)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_clarify_phase_event_includes_route_and_task(
        self,
        mock_ws_send: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """WebSocket classify progress event emits route and task for clarify."""
        request = ExecutorRequest(
            query="what exactly do you need?",
            session_id="sess-clarify",
            profile="default",
        )
        result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        classify_progress = next(
            payload
            for payload in phase_payloads
            if payload["phase"] == "classify" and payload["status"] == "progress"
        )
        assert classify_progress["route"] == "clarify"
        assert classify_progress["task"] == "respond"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_adapt_phase_event_includes_route_and_task(
        self,
        mock_ws_send: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """WebSocket classify progress event emits route and task for adapt."""


        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="research precedent for audio lipsync",
            graph=input_graph,
            session_id="sess-precedent",
            profile="default",
        )
        result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        classify_progress = next(
            payload
            for payload in phase_payloads
            if payload["phase"] == "classify" and payload["status"] == "progress"
        )
        assert classify_progress["route"] == "adapt"
        assert classify_progress["task"] == "research_precedent"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_revise_research_phase_event_is_skipped(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: research phase event emitted with status='skipped'."""
        with mock.patch("vibecomfy.executor.core._ws_send") as mock_ws_send:
            input_graph = {"nodes": [{"id": 1}]}
            request = ExecutorRequest(
                query="set seed to 42",
                graph=input_graph,
                session_id="sess-skip",
                profile="default",
            )
            result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        research_events = [
            payload
            for payload in phase_payloads
            if payload["phase"] == "research"
        ]
        # Research phase is skipped
        assert len(research_events) == 1
        assert research_events[0]["status"] == "skipped"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_clarify)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_clarify_both_phases_are_skipped(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """clarify: both research and implement phase events are skipped."""
        with mock.patch("vibecomfy.executor.core._ws_send") as mock_ws_send:
            request = ExecutorRequest(
                query="can you clarify?",
                session_id="sess-both-skip",
                profile="default",
            )
            result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        research_events = [
            payload
            for payload in phase_payloads
            if payload["phase"] == "research"
        ]
        implement_events = [
            payload
            for payload in phase_payloads
            if payload["phase"] == "implement"
        ]
        # Both phases are skipped
        assert len(research_events) == 1
        assert research_events[0]["status"] == "skipped"
        assert len(implement_events) == 1
        assert implement_events[0]["status"] == "skipped"

    # ── Empty explicit route still resolves to canonical behavior ─────────────

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    def test_no_route_research_only_resolves_to_research_with_research_phase(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Without explicit route, research-only resolves to the agent-owned stage."""
        request = ExecutorRequest(
            query="what nodes are available?",
            profile="default",
        )
        with (
            mock.patch("vibecomfy.executor.core.run_research_phase") as legacy_research,
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
        ):
            result = run_executor(request)

        assert result.ok is True
        assert result.to_dict()["route"] == "research"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False
        # The agent-owned research stage populated report.research with the
        # compact C1 package; the legacy engine and the edit gate never ran.
        assert result.report.research is not None
        assert result.report.research.trace.status == "ok"
        legacy_research.assert_not_called()
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_no_route_legacy_edit_only_still_works(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Without explicit route, legacy plan.implement=True still runs implement."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="edit graph",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.to_dict()["route"] == "revise"
        assert result.to_dict()["candidate"] == {"graph": result.graph}
        assert result.to_dict()["apply_eligible"] is True
        # Empty-route edit-only resolves to canonical revise.
        mock_edit.assert_called_once()

    def test_canonical_route_overrides_legacy_booleans_for_clarify(self, profile_dir: Path) -> None:
        """clarify never produces research, implementation, candidate, or apply eligibility."""
        def classify_clarify_with_stale_edit_flags(*args: Any, **kwargs: Any) -> ClassifyDecision:
            return ClassifyDecision(
                research=True,
                implement=True,
                reply=True,
                route="clarify",
                task="respond",
                plan_summary="ask before editing",
            )

        with (
            mock.patch(
                "vibecomfy.executor.core.run_classify_turn",
                side_effect=classify_clarify_with_stale_edit_flags,
            ),
            mock.patch(
                "vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate,
            ),
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
        ):
            result = run_executor(
                ExecutorRequest(
                    query="maybe edit this graph",
                    graph={"nodes": [{"id": 1}]},
                    profile="default",
                )
            )

        payload = result.to_dict()
        assert result.ok is True
        assert result.report.research is None
        assert result.report.implementation is None
        assert payload["route"] == "clarify"
        assert payload["reply"] == "Task completed."
        assert payload["candidate"] is None
        assert payload["apply_eligible"] is False
        mock_edit.assert_not_called()

    def test_canonical_route_overrides_legacy_booleans_for_inspect(self, profile_dir: Path) -> None:
        """inspect never carries a stale candidate even if legacy edit flags are set."""
        def classify_inspect_with_stale_edit_flags(*args: Any, **kwargs: Any) -> ClassifyDecision:
            return ClassifyDecision(
                research=False,
                implement=True,
                reply=True,
                route="inspect",
                task="inspect_graph",
                intent="explain_graph",
                plan_summary="inspect before editing",
            )

        with (
            mock.patch(
                "vibecomfy.executor.core.run_classify_turn",
                side_effect=classify_inspect_with_stale_edit_flags,
            ),
            mock.patch(
                "vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate,
            ),
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
        ):
            result = run_executor(
                ExecutorRequest(
                    query="inspect this graph before making edits",
                    graph={"nodes": [{"id": 1, "type": "KSampler"}]},
                    profile="default",
                )
            )

        payload = result.to_dict()
        assert result.ok is True
        assert result.report.research is None
        assert result.report.implementation is None
        assert result.graph is None
        assert payload["route"] == "inspect"
        assert payload["candidate"] is None
        assert payload["apply_eligible"] is False
        assert payload["no_candidate_reason"] == "route_not_applyable"
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_public_envelope_never_has_candidate_or_apply(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        request = ExecutorRequest(
            query="inspect this graph",
            graph={"nodes": [{"id": 1, "type": "KSampler"}]},
            profile="default",
        )
        result = run_executor(request)
        payload = result.to_dict()

        assert result.ok is True
        assert result.graph is None
        assert payload["route"] == "inspect"
        assert payload["candidate"] is None
        assert payload["apply_eligible"] is False
        assert payload["no_candidate_reason"] == "route_not_applyable"
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_adapt_public_envelope_apply_eligible_only_with_candidate(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:


        result = run_executor(
            ExecutorRequest(
                query="adapt a precedent",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
        )
        payload = result.to_dict()

        assert result.ok is True
        assert payload["route"] == "adapt"
        assert payload["candidate"] == {"graph": result.graph}
        assert payload["apply_eligible"] is True
        mock_edit.assert_called_once()



# ── Inspect-only flow tests (T7) ─────────────────────────────────────────────
# Verify inspect route produces a reply with graph inspection context,
# no implementation result, no candidate graph, and research invocation
# follows the route gate table.

class TestInspectOnlyFlow:
    """Inspect-only route tests: graph inspection in reply, no edits, no graph."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_reject_adaptation_plan)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_reply_fallback_preserves_graph_summary_when_adaptation_plan_unsupported(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: unsupported adaptation_plan kwarg does not fail the reply phase."""
        input_graph = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler", "class_type": "KSampler"},
            ],
            "links": [[1, 1, 0, 2, 0, "MODEL"]],
        }
        request = ExecutorRequest(
            query="explain what's in my graph",
            graph=input_graph,
            profile="default",
        )

        result = run_executor(request)

        assert result.ok is True
        assert result.reply == "This workflow loads a checkpoint and runs sampling."
        assert mock_reply.call_count == 1
        reply_kwargs = mock_reply.call_args.kwargs
        assert "adaptation_plan" not in reply_kwargs
        assert "CheckpointLoaderSimple" in str(reply_kwargs.get("graph_inspection"))
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_reply_receives_graph_inspection_context(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: _run_reply receives graph_inspection kwarg with node details."""


        input_graph = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler", "class_type": "KSampler"},
                {"id": 3, "type": "UnknownSwitchNode", "widgets_values": ["auto"]},
            ],
            "links": [
                [1, 1, 0, 2, 0, "MODEL"],
            ],
        }
        request = ExecutorRequest(
            query="explain what's in my graph",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # The inspect-only named/unlabeled lens reaches the reply backend.
        reply_kwargs = mock_reply.call_args.kwargs
        graph_inspection = reply_kwargs.get("graph_inspection")
        assert graph_inspection is not None
        assert "## Key Nodes" in graph_inspection
        assert "CheckpointLoaderSimple" in graph_inspection
        assert "KSampler" in graph_inspection
        assert "unlabeled_count=1" in graph_inspection
        assert "widget_0" not in graph_inspection
        assert "unlabeled[0]" not in graph_inspection
        assert reply_kwargs.get("graph_summary") is None
        # Implementation must never be called
        mock_edit.assert_not_called()
        # Research must NOT be called (inspect answers from graph inspection only)

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_result_graph_is_none(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: ExecutorResult.graph is always None regardless of input graph."""


        # Even with a rich input graph, result.graph must be None
        input_graph = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "class_type": "LoadImage"},
                {"id": 2, "type": "VAEDecode", "class_type": "VAEDecode"},
                {"id": 3, "type": "SaveImage", "class_type": "SaveImage"},
            ],
        }
        request = ExecutorRequest(
            query="what nodes are in my pipeline?",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # Guard: inspect must never return an edited graph
        assert result.graph is None
        # Implementation result must be None (never entered)
        assert result.report.implementation is None
        # Research result must be None (inspect never runs research)
        assert result.report.research is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_no_graph_still_produces_reply(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect with no graph: still produces reply, no graph_inspection."""


        request = ExecutorRequest(
            query="explain the graph",
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.graph is None
        assert result.report.implementation is None
        # graph_inspection should be None when no graph is attached
        reply_kwargs = mock_reply.call_args.kwargs
        assert reply_kwargs.get("graph_summary") is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_to_dict_has_no_graph(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: to_dict() has graph=None, implementation=None, research populated."""


        input_graph = {"nodes": [{"id": 1, "type": "CLIPTextEncode"}]}
        request = ExecutorRequest(
            query="what's in this graph?",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)
        d = result.to_dict()

        assert d["ok"] is True
        assert d["reply"] is not None
        assert d.get("graph") is None
        assert "implementation" not in d["report"]["executor"]
        assert "research" not in d["report"]["executor"]
        assert d["report"]["executor"]["plan"]["route"] == "inspect"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_implementation_not_called_even_with_graph(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: handle_agent_edit never called, even with a complex graph."""


        input_graph = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler"},
                {"id": 3, "type": "VAEDecode"},
            ],
        }
        request = ExecutorRequest(
            query="describe my graph structure",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # handle_agent_edit must never be invoked for inspect
        mock_edit.assert_not_called()
        # Research must NOT be called (inspect never runs research)
        # Reply is called
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_graph_inspection_includes_widget_values(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: graph_inspection text includes widget values and links."""


        input_graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "class_type": "KSampler",
                    "widgets_values": [42, 7.5, "euler"],
                    # Well-formed LiteGraph declares output slots; the door
                    # preserves the link only when the target input is named.
                    "outputs": [
                        {"name": "MODEL", "type": "MODEL", "links": [1], "slot_index": 0},
                    ],
                },
                {
                    "id": 2,
                    "type": "VAEDecode",
                    "class_type": "VAEDecode",
                    "widgets_values": [None],
                    "inputs": [
                        {"name": "samples", "type": "LATENT", "link": 1, "slot_index": 0},
                    ],
                },
            ],
            "links": [[1, 1, 0, 2, 0, "LATENT"]],
        }
        request = ExecutorRequest(
            query="describe this sampler setup",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        reply_kwargs = mock_reply.call_args.kwargs
        graph_summary = reply_kwargs.get("graph_summary")
        assert graph_summary is not None
        # Should include widget values like seed/steps/sampler name
        assert "42" in graph_summary or "euler" in graph_summary
        # Should include link wiring
        assert "1->2" in graph_summary.replace(" ", "")


# ── Precedent payload integrity tests (T14) ──────────────────────────────────
# Verify adapt payloads carry both legacy and structured research
# data, while revise payloads carry neither.


class TestSessionReferenceContext:
    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_clarify)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_former_preclassify_case_reaches_classifier_before_clarify(
        self,
        mock_reply: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        request = ExecutorRequest(
            query="change node 999 to 30 steps",
            graph={"nodes": [{"id": 1, "type": "KSampler"}]},
            profile="default",
        )

        result = run_executor(request)
        payload = result.to_dict()

        assert result.ok is True
        assert payload["route"] == "clarify"
        assert payload["candidate"] is None
        assert payload["apply_eligible"] is False
        mock_classify.assert_called_once()
        mock_edit.assert_not_called()
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_resolved_prior_option_followup_can_leave_clarify(
        self,
        mock_reply: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        session_id = "resolved-option-flow"
        turn_dir = tmp_path / session_id / "turns" / "000001"
        turn_dir.mkdir(parents=True)
        (turn_dir / "chat.json").write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "text": "Change one sampler field"},
                        {
                            "role": "agent",
                            "text": "Which field?\n\nOptions:\n- seed\n- steps",
                            "outcome": {
                                "kind": "clarify",
                                "question": "Which field?",
                                "options": ["seed", "steps"],
                            },
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_edit, "_SESSION_ROOT", tmp_path)
        executor_core._save_clarification_context(
            ExecutorRequest(
                query="Change one sampler field",
                session_id=session_id,
                graph={"nodes": [{"id": 1, "type": "KSampler"}]},
            ),
            ClassifyDecision(
                route="clarify",
                task="respond",
                clarification_question="Which field?",
                clarification_options=("seed", "steps"),
            ),
            blocked_route="revise",
            blocked_task="edit_graph",
        )

        request = ExecutorRequest(
            query="option 2",
            session_id=session_id,
            graph={"nodes": [{"id": 1, "type": "KSampler"}]},
            profile="default",
        )

        result = run_executor(request)
        payload = result.to_dict()

        assert payload["route"] == "revise"
        assert payload["candidate"] is not None
        assert payload["apply_eligible"] is True
        mock_classify.assert_called_once()
        mock_edit.assert_called_once()
        mock_reply.assert_called_once()

    def test_build_session_context_reads_chat_artifacts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        session_id = "ref-session"
        turn_dir = tmp_path / session_id / "turns" / "000001"
        turn_dir.mkdir(parents=True)
        (turn_dir / "chat.json").write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "text": "Change the sampler steps"},
                        {
                            "role": "agent",
                            "text": "Which option?",
                            "outcome": {
                                "kind": "clarify",
                                "question": "Which option?",
                                "options": ["seed", "steps"],
                            },
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_edit, "_SESSION_ROOT", tmp_path)

        context = executor_core._build_session_context(
            ExecutorRequest(query="option 2", session_id=session_id)
        )

        assert context is not None
        assert context["recent_messages"][-1]["text"] == "Which option?"
        assert context["prior_clarification"]["clarification_question"] == "Which option?"
        assert context["prior_clarification"]["clarification_options"] == ["seed", "steps"]

    def test_session_context_prefers_latest_chat_clarify_over_stale_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        session_id = "latest-clarify-wins"
        turn_dir = tmp_path / session_id / "turns" / "000002"
        turn_dir.mkdir(parents=True)
        (turn_dir / "chat.json").write_text(
            json.dumps(
                {
                    "messages": [
                        {
                            "role": "agent",
                            "text": "For LTX audio, use custom audio or generated audio?",
                            "outcome": {
                                "kind": "clarify",
                                "question": "For LTX audio, use custom audio or generated audio?",
                                "options": ["Load external audio file", "Use text-to-audio generation"],
                            },
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_edit, "_SESSION_ROOT", tmp_path)
        executor_core._save_clarification_context(
            ExecutorRequest(
                query="It's LTX, not wan",
                session_id=session_id,
                graph={"nodes": [{"id": 1, "type": "LTXImageToVideo"}]},
            ),
            ClassifyDecision(
                route="clarify",
                task="respond",
                clarification_question="Wan or LTX architecture?",
                clarification_options=("Wan", "LTX"),
            ),
            blocked_route="adapt",
            blocked_task="edit_graph",
        )

        context = executor_core._build_session_context(
            ExecutorRequest(query="You figure it out", session_id=session_id)
        )

        assert context is not None
        assert context["prior_clarification"]["clarification_question"].startswith("For LTX audio")
        assert context["blocked_route"] == "adapt"
        assert context["prior_route"] == "adapt"

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_you_figure_it_out_after_ltx_audio_clarify_executes_adapt_without_classify(
        self,
        mock_reply: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        session_id = "ltx-audio-delegated"
        turn_dir = tmp_path / session_id / "turns" / "000005"
        turn_dir.mkdir(parents=True)
        (turn_dir / "chat.json").write_text(
            json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "text": "It's LTX, not wan. Figure it out",
                        },
                        {
                            "role": "agent",
                            "text": (
                                "For LTX/RuneXX custom audio/lipsync, should I load "
                                "external audio or use text-to-audio?"
                            ),
                            "outcome": {
                                "kind": "clarify",
                                "question": (
                                    "For LTX/RuneXX custom audio/lipsync, should I load "
                                    "external audio or use text-to-audio?"
                                ),
                                "options": [
                                    "Load external audio file",
                                    "Use text-to-audio generation",
                                ],
                            },
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_edit, "_SESSION_ROOT", tmp_path)
        executor_core._save_clarification_context(
            ExecutorRequest(
                query="It's LTX, not wan. Figure it out",
                session_id=session_id,
                graph={"nodes": [{"id": 1, "type": "LTXImageToVideo"}]},
            ),
            ClassifyDecision(
                route="clarify",
                task="respond",
                clarification_question="Wan or LTX architecture?",
                clarification_options=("Wan", "LTX"),
            ),
            blocked_route="revise",
            blocked_task="edit_graph",
        )

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="medium",
            intent="edit",
            route="adapt",
            task="edit_graph",
            plan_summary="Use the LTX clarification context and adapt with research.",
        )

        result = run_executor(
            ExecutorRequest(
                query="You figure it out",
                session_id=session_id,
                graph={"nodes": [{"id": 1, "type": "LTXImageToVideo"}]},
                profile="default",
            )
        )
        payload = result.to_dict()

        assert payload["route"] == "adapt"
        assert payload["report"]["executor"]["plan"]["research"] is True
        assert payload["candidate"] is not None
        assert payload["apply_eligible"] is True
        mock_classify.assert_called_once()
        mock_edit.assert_called_once()
        mock_reply.assert_called_once()

    def test_classifier_prompt_owns_former_preclassify_judgment(self) -> None:
        messages = build_classify_messages(
            "option 3",
            has_graph=True,
            graph_summary="1 node(s): KSampler",
            session_context={
                "prior_clarification": {
                    "clarification_options": ["seed", "steps"],
                },
            },
        )

        system = messages[0]["content"]
        user = messages[1]["content"]
        assert "You are the authority for semantic routing" in system
        assert "Do not assume another pre-classifier" in system
        assert "named prior option does not exist" in system
        assert "missing models, unknown custom nodes" in system
        assert "Prior clarification options" in user
        assert "2. steps" in user

    def test_classifier_prompt_preserves_user_named_external_technologies(self) -> None:
        messages = build_classify_messages(
            "Switch this workflow to generate 8 frames using HotShotXL",
            has_graph=True,
            graph_summary="2 node(s): LoadImage, KSampler",
        )

        system = messages[0]["content"]
        user = messages[1]["content"]
        assert "Do not add unrelated technology ecosystems" in system
        assert "absent from both the user's request and the current graph" in system
        assert "User-named external technologies are valid adapt" in system
        assert "research/planning signals" in system
        assert "NEVER name a technology ecosystem" not in system
        assert "HotShotXL" in user

    def test_save_clarification_context_preserves_blocked_route(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        monkeypatch.setattr(agent_edit, "_SESSION_ROOT", tmp_path)
        plan = ClassifyDecision(
            route="clarify",
            task="respond",
            clarification_question="Which node?",
            clarification_options=("node #1", "node #2"),
        )
        request = ExecutorRequest(
            query="change that one",
            session_id="blocked-ref-session",
            graph={"nodes": [{"id": 1, "type": "KSampler"}]},
        )

        executor_core._save_clarification_context(
            request,
            plan,
            blocked_route="revise",
            blocked_task="edit_graph",
        )
        context = executor_core._build_session_context(request)

        assert context is not None
        assert context["prior_route"] == "revise"
        assert context["prior_task"] == "edit_graph"
        assert context["prior_clarification"]["clarification_question"] == "Which node?"

    def test_prompt_memory_includes_last_five_durable_messages_in_order(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Seed session with >5 durable chat messages, verify executor prompt
        includes the last 5 messages in order plus the current user message.

        This test does NOT depend on frontend ``recent_messages`` — it
        inspects the backend-built prompt/context directly through
        ``_build_session_context`` and ``build_classify_messages``.
        """
        from vibecomfy.comfy_nodes.agent import edit as agent_edit
        from vibecomfy.executor.prompts import build_classify_messages

        session_id = "prompt-memory-test"
        turns_dir = tmp_path / session_id / "turns"

        # Create 7 turns → 14 messages (user + agent per turn).
        # This exceeds PROMPT_MEMORY_MESSAGES (5) so the memory window
        # must select only the last 5.
        for i in range(7):
            tid = f"{i:04d}"
            turn_dir = turns_dir / tid
            turn_dir.mkdir(parents=True)
            (turn_dir / "chat.json").write_text(
                json.dumps(
                    {
                        "session_id": session_id,
                        "turn_id": tid,
                        "messages": [
                            {
                                "role": "user",
                                "text": f"user query {i}",
                                "turn_id": tid,
                            },
                            {
                                "role": "agent",
                                "text": f"agent response {i}",
                                "turn_id": tid,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

        monkeypatch.setattr(agent_edit, "_SESSION_ROOT", tmp_path)

        # ── build session context (same code path as executor pipeline) ──
        current_query = "new follow-up request"
        context = executor_core._build_session_context(
            ExecutorRequest(query=current_query, session_id=session_id)
        )

        assert context is not None, "_build_session_context must return a dict"
        recent = context.get("recent_messages")
        assert isinstance(recent, list), "recent_messages must be a list"
        assert len(recent) == 5, (
            f"Expected exactly 5 recent messages (PROMPT_MEMORY_MESSAGES), "
            f"got {len(recent)}: {[m.get('text','') for m in recent]}"
        )

        # Last 5 of 14 messages:
        #   agent response 4, user query 5, agent response 5,
        #   user query 6, agent response 6
        expected_texts = [
            "agent response 4",
            "user query 5",
            "agent response 5",
            "user query 6",
            "agent response 6",
        ]
        for idx, expected in enumerate(expected_texts):
            actual = recent[idx].get("text", "")
            assert actual == expected, (
                f"Message {idx}: expected {expected!r}, got {actual!r}"
            )

        # ── verify the classifier prompt includes the messages ──────────
        classify_msgs = build_classify_messages(
            current_query,
            session_context=context,
        )
        # System + user message.
        assert len(classify_msgs) == 2, (
            f"Expected 2 messages (system + user), got {len(classify_msgs)}"
        )
        user_content = classify_msgs[1]["content"]
        assert isinstance(user_content, str)

        # The current user message must appear.
        assert current_query in user_content, (
            f"Current query {current_query!r} not found in classify prompt"
        )

        # All five recent messages must appear in chronological order.
        prev_pos = -1
        for expected in expected_texts:
            pos = user_content.find(expected)
            assert pos >= 0, (
                f"Expected recent message {expected!r} not found in classify prompt"
            )
            assert pos > prev_pos, (
                f"Recent messages out of order: {expected!r} appears before "
                f"previous message in classify prompt"
            )
            prev_pos = pos


class TestRouteIntentBoundaries:
    """Canonical route resolution from classifier intent + legacy booleans."""

    @pytest.mark.parametrize(
        "classify_side_effect, expected_route, expect_edit_called",
        [
            (_fake_classify_clarify, "clarify", False),
            (_fake_classify_inspect, "inspect", False),
            (_fake_classify_revise, "revise", True),
            (_fake_classify_adapt, "adapt", True),
        ],
        ids=["clarify", "inspect", "revise", "adapt"],
    )
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_canonical_route_only_runs_allowed_phases(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        classify_side_effect: Any,
        expected_route: str,
        expect_edit_called: bool,
        profile_dir: Path,
    ) -> None:
        """Each canonical route invokes only its allowed phases."""
        with mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=classify_side_effect):
            request = ExecutorRequest(
                query=f"{expected_route} request",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == expected_route
        assert result.report.plan.effective_route == expected_route
        if expect_edit_called:
            mock_edit.assert_called_once()
        else:
            mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_vague_aesthetic_request_routes_to_clarify(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """A vague aesthetic request with no concrete graph target -> clarify."""
        mock_classify.return_value = ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="low",
            plan_summary="ask the user to clarify",
            intent="respond",
            route="clarify",
            task="respond",
        )

        request = ExecutorRequest(
            query="make it more cinematic",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == "clarify"
        assert result.report.plan.implement is False
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_current_graph_prompt_change_routes_to_revise(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """A concrete local edit to the attached graph -> revise."""
        mock_classify.return_value = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="edit the current graph",
            intent="edit",
            route="revise",
            task="edit_graph",
        )

        request = ExecutorRequest(
            query="change the positive prompt to 'a red rose'",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == "revise"
        assert result.report.plan.implement is True
        mock_edit.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_outside_workflow_pattern_routes_to_adapt(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """A request to borrow/port an outside workflow/template pattern -> adapt."""
        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
        )

        request = ExecutorRequest(
            query="add the Wan control LoRA chain from the Kijai template",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.report.plan.route == "adapt"
        assert result.report.plan.research is True
        assert result.report.plan.implement is True
        mock_edit.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_legacy_research_only_intent_resolves_to_research(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """A classifier that only sets research=True resolves to research."""
        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="explain the graph",
            intent="explain_graph",
        )

        request = ExecutorRequest(
            query="is there a distilled/faster way to run?",
            profile="default",
        )
        with (
            mock.patch("vibecomfy.executor.core.run_research_phase") as legacy_research,
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
        ):
            result = run_executor(request)

        assert result.ok is True
        assert result.turn.route == "research"
        assert result.report.plan.effective_route == "research"
        assert result.report.plan.implement is False
        # Research-only resolves through the agent-owned stage + reply, not
        # the edit gate or legacy research engine.
        assert result.report.research is not None
        legacy_research.assert_not_called()
        mock_edit.assert_not_called()
        assert result.graph is None


# ── Apply-eligibility matrix (M5) ────────────────────────────────────────────
# Only revise/adapt with a candidate graph are applyable; clarify and inspect
# are never applyable, even if a graph-like payload leaks in.


class TestApplyEligibilityMatrix:
    """Canonical Apply eligibility per route and candidate presence."""

    @pytest.mark.parametrize(
        "classify_side_effect, expected_eligible, expected_reason",
        [
            (_fake_classify_clarify, False, "route_not_applyable"),
            (_fake_classify_inspect, False, "route_not_applyable"),
            (_fake_classify_revise, True, None),
            (_fake_classify_adapt, True, None),
        ],
        ids=["clarify", "inspect", "revise", "adapt"],
    )
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_route_apply_eligibility(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        classify_side_effect: Any,
        expected_eligible: bool,
        expected_reason: str | None,
        profile_dir: Path,
    ) -> None:
        """Apply eligibility follows the canonical route matrix."""
        with mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=classify_side_effect):
            request = ExecutorRequest(
                query="route eligibility check",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.turn.apply_eligible is expected_eligible
        if expected_reason is None:
            assert result.turn.no_candidate_reason is None
        else:
            assert result.turn.no_candidate_reason == expected_reason

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_inspect_never_applyable_even_if_graph_payload_leaks(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """A misbehelling inspect turn that returns a graph is still not applyable."""
        def bad_edit(payload: dict, **kwargs: Any) -> dict:
            # A buggy edit engine returns a graph even though the route is inspect.
            return {
                "graph": {"nodes": [{"id": 99}]},
                "message": "I explained it",
            }

        mock_classify.return_value = ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="explain the graph",
            intent="explain_graph",
            route="inspect",
            task="inspect_graph",
        )

        with mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=bad_edit):
            request = ExecutorRequest(
                query="what does this do?",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.turn.route == "inspect"
        assert result.turn.apply_eligible is False
        assert result.graph is None


# ── Durable edit-envelope preservation (T1) ───────────────────────────────────


def _fake_handle_agent_edit_durable_revise(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit returning a full durable envelope for revise."""
    import hashlib, json, uuid

    input_graph = payload.get("graph", {})
    nodes = input_graph.get("nodes", [])
    edited_nodes = list(nodes) + [{"id": len(nodes) + 1, "type": "KSampler"}]
    candidate_graph = {"nodes": edited_nodes}
    candidate_graph_hash = hashlib.sha256(
        json.dumps(candidate_graph, sort_keys=True).encode()
    ).hexdigest()

    def _structural_hash(graph: dict) -> str:
        structure = {
            "node_count": len(graph.get("nodes", [])),
            "node_types": sorted(
                n.get("type") or n.get("class_type") or ""
                for n in graph.get("nodes", [])
                if isinstance(n, dict)
            ),
            "link_count": len(graph.get("links", [])),
        }
        return hashlib.sha256(
            json.dumps(structure, sort_keys=True).encode()
        ).hexdigest()

    return {
        "ok": True,
        "session_id": payload.get("session_id", "sess-durable-revise"),
        "turn_id": str(uuid.uuid4()),
        "baseline_turn_id": None,
        "baseline_graph_hash": "abc123baseline",
        "submit_graph_hash": "def456submit",
        "submit_structural_graph_hash": _structural_hash(input_graph),
        "submitted_client_graph_hash": payload.get("client_graph_hash", "cli789hash"),
        "submitted_client_structural_graph_hash": payload.get(
            "client_structural_graph_hash", "cli000struct"
        ),
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": _structural_hash(candidate_graph),
        "graph": candidate_graph,
        "message": "Added a KSampler node to the graph.",
        "reply": "Added a KSampler node to the graph.",
        "route": "revise",
        "outcome": {
            "kind": "candidate",
            "changes": [{"node_id": str(len(nodes) + 1), "op": "add"}],
        },
        "candidate": {"graph": candidate_graph, "graph_hash": candidate_graph_hash},
        "apply_eligible": True,
        "apply_eligibility": {
            "applyable": True,
            "reason": "applyable",
            "message": "Ready to apply.",
            "warnings": [],
        },
        "change_details": {
            "added_nodes": [str(len(nodes) + 1)],
            "changed_nodes": [],
            "removed_nodes": [],
            "summary": "Added 1 node.",
        },
        "runtime_dependencies": [
            {
                "class_type": "RegistryOnlyNode",
                "availability": "registry_resolvable",
                "resolver_candidates": [{"pack": {"slug": "registry-only"}}],
            }
        ],
        "audit_ref": {
            "path": "sessions/sess-durable-revise/turns/turn-1/audit/audit.json",
            "format": "json",
        },
        "artifacts": {
            "candidate_ui_json": "sessions/sess-durable-revise/turns/turn-1/candidate.ui.json",
        },
        "version": 1,
        "report": {},
        "gates": {},
        "debug": {},
        "contract_version": "1.0",
    }


def _fake_handle_agent_edit_durable_adapt(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit returning a full durable envelope for adapt."""
    import hashlib, json, uuid

    input_graph = payload.get("graph", {})
    nodes = input_graph.get("nodes", [])
    edited_nodes = list(nodes) + [
        {"id": len(nodes) + 1, "type": "KSampler"},
        {"id": len(nodes) + 2, "type": "VAEDecode"},
    ]
    candidate_graph = {"nodes": edited_nodes}
    candidate_graph_hash = hashlib.sha256(
        json.dumps(candidate_graph, sort_keys=True).encode()
    ).hexdigest()

    def _structural_hash(graph: dict) -> str:
        structure = {
            "node_count": len(graph.get("nodes", [])),
            "node_types": sorted(
                n.get("type") or n.get("class_type") or ""
                for n in graph.get("nodes", [])
                if isinstance(n, dict)
            ),
            "link_count": len(graph.get("links", [])),
        }
        return hashlib.sha256(
            json.dumps(structure, sort_keys=True).encode()
        ).hexdigest()

    return {
        "ok": True,
        "session_id": payload.get("session_id", "sess-durable-adapt"),
        "turn_id": str(uuid.uuid4()),
        "baseline_turn_id": "prior-turn-99",
        "baseline_graph_hash": "xyz789baseline",
        "submit_graph_hash": "uvw012submit",
        "submit_structural_graph_hash": _structural_hash(input_graph),
        "submitted_client_graph_hash": payload.get("client_graph_hash", "cli111hash"),
        "submitted_client_structural_graph_hash": payload.get(
            "client_structural_graph_hash", "cli222struct"
        ),
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": _structural_hash(candidate_graph),
        "graph": candidate_graph,
        "message": "Researched precedent and adapted the graph with KSampler and VAEDecode.",
        "reply": "Researched precedent and adapted the graph with KSampler and VAEDecode.",
        "route": "adapt",
        "outcome": {
            "kind": "edit",
            "changes": [
                {"node_id": str(len(nodes) + 1), "op": "add"},
                {"node_id": str(len(nodes) + 2), "op": "add"},
            ],
        },
        "candidate": {"graph": candidate_graph, "graph_hash": candidate_graph_hash},
        "apply_eligible": True,
        "apply_eligibility": {
            "applyable": True,
            "reason": "applyable",
            "message": "Ready to apply.",
            "warnings": [],
        },
        "change_details": {
            "added_nodes": [str(len(nodes) + 1), str(len(nodes) + 2)],
            "changed_nodes": [],
            "removed_nodes": [],
            "summary": "Added 2 nodes from researched precedent.",
            "precedent_source": "kijai/wan-control-lora",
        },
        "audit_ref": {
            "path": "sessions/sess-durable-adapt/turns/turn-2/audit/audit.json",
            "format": "json",
        },
        "artifacts": {
            "candidate_ui_json": "sessions/sess-durable-adapt/turns/turn-2/candidate.ui.json",
            "precedent_slice": "sessions/sess-durable-adapt/turns/turn-2/precedent.json",
        },
        "version": 1,
        "report": {},
        "gates": {},
        "debug": {},
        "contract_version": "1.0",
    }


class TestDurableEditEnvelopePreservation:
    """Contract tests proving the executor preserves the full durable
    handle_agent_edit() envelope for revise and adapt routes, including
    session_id, turn_id, baseline/candidate hashes, audit/artifact refs,
    apply_eligibility, graph, outcome, and change_details, while keeping
    executor metadata nested under report.executor.
    """

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_revise_preserves_durable_edit_envelope(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Executor result for revise must carry session_id, turn_id, hashes,
        audit_ref, apply_eligibility, graph, outcome, and change_details."""
        mock_classify.return_value = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="edit the current graph",
            intent="edit",
            route="revise",
            task="edit_graph",
        )

        request = ExecutorRequest(
            query="add a KSampler",
            graph={"nodes": [{"id": 1, "type": "VAEDecode"}]},
            profile="default",
            session_id="sess-durable-revise",
        )

        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit",
            side_effect=_fake_handle_agent_edit_durable_revise,
        ):
            result = run_executor(request)
            serialized = result.to_dict()

        # Durable session/turn identity
        assert serialized.get("session_id") == "sess-durable-revise", (
            "ExecutorResult missing durable session_id; got %r" % serialized.get("session_id")
        )
        assert isinstance(serialized.get("turn_id"), str) and serialized["turn_id"], (
            "ExecutorResult missing durable turn_id"
        )

        # Baseline and candidate hashes
        assert isinstance(serialized.get("baseline_graph_hash"), str), (
            "ExecutorResult missing baseline_graph_hash"
        )
        assert isinstance(serialized.get("submit_structural_graph_hash"), str), (
            "ExecutorResult missing submit_structural_graph_hash"
        )
        assert isinstance(serialized.get("candidate_graph_hash"), str), (
            "ExecutorResult missing candidate_graph_hash"
        )
        assert isinstance(serialized.get("candidate_structural_graph_hash"), str), (
            "ExecutorResult missing candidate_structural_graph_hash"
        )

        # Audit/artifact refs
        assert isinstance(serialized.get("audit_ref"), dict), (
            "ExecutorResult missing durable audit_ref"
        )
        assert isinstance(serialized.get("artifacts"), dict), (
            "ExecutorResult missing durable artifacts"
        )

        # apply_eligibility
        eligibility = serialized.get("apply_eligibility")
        assert isinstance(eligibility, dict), "ExecutorResult missing apply_eligibility"
        assert eligibility.get("applyable") is True, (
            "apply_eligibility.applyable should be True for revise"
        )

        # graph
        assert isinstance(serialized.get("graph"), dict), (
            "ExecutorResult missing durable graph"
        )

        # outcome
        outcome = serialized.get("outcome")
        assert isinstance(outcome, dict), "ExecutorResult missing outcome"
        assert outcome.get("kind") in ("candidate", "edit"), (
            "outcome.kind should be candidate/edit for revise, got %r" % outcome.get("kind")
        )

        # change_details
        assert isinstance(serialized.get("change_details"), dict), (
            "ExecutorResult missing durable change_details"
        )
        assert serialized.get("runtime_dependencies") == [
            {
                "class_type": "RegistryOnlyNode",
                "availability": "registry_resolvable",
                "resolver_candidates": [{"pack": {"slug": "registry-only"}}],
            }
        ]

        # report.executor metadata must be present (not flattened)
        report = serialized.get("report")
        assert isinstance(report, dict), "ExecutorResult missing report"
        executor_meta = report.get("executor")
        assert isinstance(executor_meta, dict), (
            "report.executor metadata missing; report keys=%r"
            % list(report.keys()) if isinstance(report, dict) else None
        )
        plan = executor_meta.get("plan")
        assert isinstance(plan, dict), "report.executor.plan missing"
        assert plan.get("route") == "revise", (
            "report.executor.plan.route should be revise, got %r" % plan.get("route")
        )

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_adapt_preserves_durable_edit_envelope(
        self,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Executor result for adapt must carry the full durable envelope including
        precedent_source in change_details."""
        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
        )

        request = ExecutorRequest(
            query="add the Wan control LoRA chain from the Kijai template",
            graph={"nodes": [{"id": 1, "type": "LoadImage"}]},
            profile="default",
            session_id="sess-durable-adapt",
        )

        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit",
            side_effect=_fake_handle_agent_edit_durable_adapt,
        ):
            result = run_executor(request)
            serialized = result.to_dict()

        # Durable session/turn identity
        assert serialized.get("session_id") == "sess-durable-adapt", (
            "ExecutorResult missing durable session_id"
        )
        assert isinstance(serialized.get("turn_id"), str) and serialized["turn_id"], (
            "ExecutorResult missing durable turn_id"
        )

        # Baseline and candidate hashes
        assert isinstance(serialized.get("baseline_graph_hash"), str), (
            "ExecutorResult missing baseline_graph_hash for adapt"
        )
        assert isinstance(serialized.get("candidate_graph_hash"), str), (
            "ExecutorResult missing candidate_graph_hash for adapt"
        )
        assert isinstance(serialized.get("candidate_structural_graph_hash"), str), (
            "ExecutorResult missing candidate_structural_graph_hash for adapt"
        )

        # Audit/artifact refs
        assert isinstance(serialized.get("audit_ref"), dict), (
            "ExecutorResult missing durable audit_ref for adapt"
        )

        # apply_eligibility
        eligibility = serialized.get("apply_eligibility")
        assert isinstance(eligibility, dict), "ExecutorResult missing apply_eligibility for adapt"
        assert eligibility.get("applyable") is True, (
            "apply_eligibility.applyable should be True for adapt"
        )

        # graph (candidate)
        assert isinstance(serialized.get("graph"), dict), (
            "ExecutorResult missing durable graph for adapt"
        )

        # outcome
        outcome = serialized.get("outcome")
        assert isinstance(outcome, dict), "ExecutorResult missing outcome for adapt"
        assert outcome.get("kind") in ("candidate", "edit"), (
            "outcome.kind should be candidate/edit for adapt, got %r" % outcome.get("kind")
        )

        # change_details
        change_details = serialized.get("change_details")
        assert isinstance(change_details, dict), (
            "ExecutorResult missing durable change_details for adapt"
        )
        assert change_details.get("precedent_source") == "kijai/wan-control-lora", (
            "change_details.preedent_source should be preserved for adapt"
        )

        # report.executor metadata
        report = serialized.get("report")
        assert isinstance(report, dict), "ExecutorResult missing report for adapt"
        executor_meta = report.get("executor")
        assert isinstance(executor_meta, dict), (
            "report.executor metadata missing for adapt"
        )
        plan = executor_meta.get("plan")
        assert isinstance(plan, dict), "report.executor.plan missing for adapt"
        assert plan.get("route") == "adapt", (
            "report.executor.plan.route should be adapt, got %r" % plan.get("route")
        )


# ── B05: real batch-REPL integration (informational path) ───────────────────


class _ReplSchemaProvider:
    """Minimal ``get_schema`` / ``schemas()`` provider for the real session.

    The informational batch REPL renders the attached graph and builds a
    signature catalog from the provider; only the node types present in the
    fixture graph are needed.
    """

    def __init__(self, schemas: dict[str, Any]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> Any | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, Any]:
        return self._schemas


def _b05_schema_provider() -> _ReplSchemaProvider:
    from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec

    return _ReplSchemaProvider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("STRING")},
                outputs=[OutputSpec("IMAGE", "image")],
                source_provider="test",
                confidence=1.0,
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={
                    "images": InputSpec("IMAGE", required=True),
                    "filename_prefix": InputSpec("STRING"),
                },
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )


def _b05_ui_graph() -> dict[str, Any]:
    """Minimal LoadImage -> SaveImage UI graph (canonical list-nodes shape)."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [100, 100],
                "size": [180, 80],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [400, 100],
                "size": [180, 80],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 10}],
            },
        ],
        "links": [[10, 1, 0, 2, 0, "IMAGE"]],
    }


_RAW_ALICE_MESSAGE: dict[str, Any] = {
    "kind": "message",
    "title": None,
    "body": "LTX 2.5, agree, fast and a clear improvement!",
    "author": "alice",
    "context": "ltx_chatter",
    "item_id": "test-1",  # str, not int (Discord snowflake precision)
}


def _fake_handle_agent_edit_slow(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit that blocks long enough for heartbeat ticks."""
    import time

    time.sleep(0.25)
    return _fake_handle_agent_edit(payload, **kwargs)


class TestImplementPhaseHeartbeat:
    """The implement phase emits periodic status=\"working\" heartbeat events."""

    @mock.patch("vibecomfy.executor.core._IMPLEMENT_HEARTBEAT_INTERVAL_SECONDS", 0.05)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_slow)
    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    def test_implement_phase_emits_working_heartbeat_events(
        self, mock_reply, mock_classify, mock_edit, profile_dir: Path
    ) -> None:
        """While the implement phase runs, status='working' events are emitted."""
        request = ExecutorRequest(
            query="set seed to 42",
            session_id="session-heartbeat",
            graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
            profile="default",
        )
        with mock.patch("vibecomfy.executor.core._ws_send") as mock_ws_send:
            result = run_executor(request, client_id="client-1")

        assert result.ok is True
        phase_payloads = [
            call.args[1]
            for call in mock_ws_send.call_args_list
            if call.args[0] == "vibecomfy.executor.phase"
        ]
        implement_statuses = [
            payload["status"]
            for payload in phase_payloads
            if payload["phase"] == "implement"
        ]
        assert "start" in implement_statuses
        assert "working" in implement_statuses, (
            "implement phase must emit status='working' heartbeat events while running"
        )
        working_payloads = [
            payload
            for payload in phase_payloads
            if payload["phase"] == "implement" and payload["status"] == "working"
        ]
        assert all(payload["executor_id"] for payload in working_payloads)
        assert all(payload["session_id"] == request.session_id for payload in working_payloads)


# ── Batch 12 (Law 4): stage lens wiring + reply-prompt goldens ──────────────

_BATCH12_REPO_ROOT = Path(__file__).resolve().parents[1]


def _batch12_classify_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> ClassifyDecision:
    """Classify fake that records the graph context it received."""
    _batch12_state["classify_graph_summary"] = graph_summary
    return ClassifyDecision.edit(
        research=False,
        effort="low",
        plan_summary="batch 12 lens wiring edit",
    )


def _batch12_reply_capture(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    graph_summary: str | None = None,
    **kwargs: Any,
) -> str:
    """Reply fake that records the graph context it received."""
    _batch12_state["reply_graph_summary"] = graph_summary
    return "Batch 12 reply."


_batch12_state: dict[str, Any] = {}


@mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_batch12_classify_edit)
@mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_batch12_reply_capture)
def test_batch12_classify_gets_census_only_and_reply_gets_surface_diff_topology(
    mock_reply: mock.MagicMock,
    mock_classify: mock.MagicMock,
    profile_dir: Path,
) -> None:
    """Law 4 (batch 12): classify sees ONLY the census lens; the reply sees
    surface + diff(Δ) + topology (complete, with link ids) — never the
    truncated ``_build_text_summary`` view."""
    _batch12_state.clear()
    input_graph = {
        "nodes": [
            {
                "id": 1,
                "type": "CLIPTextEncode",
                "class_type": "CLIPTextEncode",
                "outputs": [
                    {"name": "MODEL", "type": "MODEL", "links": [1], "slot_index": 0},
                ],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "inputs": [{"name": "model", "type": "MODEL", "link": 1, "slot_index": 0}],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "MODEL"]],
    }

    def passthrough_edit(payload: dict, **kwargs: Any) -> dict:
        # Preserve the full envelope (nodes + links) so the reply's topology
        # lens sees the wired edge with its named endpoints.
        return {"graph": payload.get("graph") or {}, "message": "no-op"}

    with mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=passthrough_edit):
        result = run_executor(
            ExecutorRequest(
                query="describe and edit my graph",
                graph=input_graph,
                profile="default",
            )
        )
    assert result.ok is True

    # ── classify: census ONLY (node/class census + reference map) ─────────
    census = _batch12_state.get("classify_graph_summary")
    assert census is not None
    assert "## Census" in census
    assert "class list:" in census
    assert "reference map:" in census
    assert "## Topology" not in census
    assert "## Diff" not in census
    assert "edges:" not in census

    # ── reply: surface + diff(Δ) + topology (complete, link ids) ──────────
    reply_ctx = _batch12_state.get("reply_graph_summary")
    assert reply_ctx is not None
    assert "# vibecomfy: agent-edit" in reply_ctx  # surface (Python view)
    assert "## Diff" in reply_ctx  # diff(Δ)
    assert "## Topology" in reply_ctx  # full computed topology
    assert "1 -> 2 (1.0 -> 2.model)" in reply_ctx
    # Named fields from the surface view, not the truncated summary.
    assert "KSampler" in reply_ctx
    assert "CLIPTextEncode" in reply_ctx
    # The truncated text-summary view is NOT the authority (no `values=(` /
    # `inputs=(` truncated slot dumps, no `Edges:` cap header).
    assert "Edges:" not in reply_ctx


def test_batch12_reply_graph_context_is_renderer_output_not_text_summary() -> None:
    """Reply-prompt golden: the reply's graph context is the composable
    renderer's output (complete topology, link ids, named fields) — the
    renderer output is embedded verbatim, not re-summarized."""
    from vibecomfy.executor.core import _render_graph_text
    from vibecomfy.porting.render import render_text

    raw = {
        "nodes": [
            {"id": 1, "type": "CLIPTextEncode", "class_type": "CLIPTextEncode"},
            {"id": 2, "type": "KSampler", "class_type": "KSampler"},
        ],
        "links": [[1, 1, 0, 2, 0, "MODEL"]],
    }
    rendered = _render_graph_text(raw, delta=())
    assert rendered is not None
    # The reply prompt embeds the renderer output verbatim behind the
    # cite-link preamble (link ids live in the topology lens).
    from vibecomfy.executor.prompts import build_reply_messages

    msgs = build_reply_messages("explain", graph_summary=rendered)
    user = msgs[1]["content"]
    assert "cite link ids and widget" in user
    assert rendered in user
    # Renderer output is the complete view — never the truncated
    # `_build_text_summary` format (no `node(s):\n[1] ...` compact header).
    assert "node(s):\n[" not in user


def test_batch12_3c978e_live_reply_gets_complete_controlnet_topology(
    profile_dir: Path,
) -> None:
    """3c978e live: the reply's graph context carries the COMPLETE ControlNet
    chain (all 6 links with named endpoints) — the real specimen that lost
    links to the old ``[:20]`` truncation."""
    fixture = _BATCH12_REPO_ROOT / "tests" / "fixtures" / "3c978e6c11a8a768.json"
    assert fixture.is_file(), f"3c978e fixture missing: {fixture}"
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    _batch12_state.clear()

    def passthrough_edit(payload: dict, **kwargs: Any) -> dict:
        # Preserve the full envelope (nodes + edges) so the reply's topology
        # lens sees the complete ControlNet chain.
        return {"graph": payload.get("graph") or {}, "message": "no-op"}

    with mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_batch12_classify_edit):
        with mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_batch12_reply_capture):
            with mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=passthrough_edit):
                result = run_executor(
                    ExecutorRequest(
                        query="explain and edit this video workflow",
                        graph=raw,
                        profile="default",
                    )
                )
    assert result.ok is True
    reply_ctx = _batch12_state.get("reply_graph_summary")
    assert reply_ctx is not None
    chain = (
        ("15", "16", "conditioning"),
        ("18", "16", "image"),
        ("25", "26", "image"),
        ("26", "3", "positive"),
        ("33", "16", "control_net"),
        ("34", "26", "control_net"),
    )
    for origin, target, target_input in chain:
        assert (
            f"{origin} -> {target} ({origin}.0 -> {target}.{target_input})"
        ) in reply_ctx, f"ControlNet chain link {origin}->{target} missing from reply topology"
def test_expect_graph_changed_contract_reaches_production_classify(monkeypatch) -> None:
    """The request field is not fixture-only: run_executor forwards it."""
    from types import SimpleNamespace

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor

    request = ExecutorRequest.from_payload(
        {"query": "change the sampler", "expect_graph_changed": True}
    )
    assert request.to_dict()["expect_graph_changed"] is True

    seen: dict[str, object] = {}

    def fake_classify(req, spec, **kwargs):  # noqa: ANN001, ANN202, ARG001
        seen["expect_graph_changed"] = kwargs.get("expect_graph_changed")
        return ClassifyDecision(intent="edit", route="revise")

    monkeypatch.setattr("vibecomfy.executor.core._run_classify", fake_classify)
    monkeypatch.setattr(
        "vibecomfy.executor.core._resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )

    result = run_executor(request, classify_only=True)
    assert result.ok is True
    assert seen["expect_graph_changed"] is True


def _isolated_host_ports(events: list[tuple[str, object]]) -> ExecutorHostPorts:
    def unused(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise AssertionError("unused host operation")

    return ExecutorHostPorts(
        handle_agent_edit=unused,
        payload_hash=lambda payload: "test-hash",
        classify_failure=unused,
        failure_envelope=unused,
        begin_deepseek_usage_capture=lambda: events.append(("begin_usage", None)) or "usage",
        snapshot_deepseek_usage_capture=lambda: ({}, True),
        end_deepseek_usage_capture=lambda token: events.append(("end_usage", token)),
        begin_model_attempt_capture=lambda: events.append(("begin_attempts", None)) or "attempts",
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda token: events.append(("end_attempts", token)),
    )


def test_run_executor_uses_injected_host_ports_without_default_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    seen: dict[str, object] = {}

    def fake_classify_turn(query: str, **kwargs: Any) -> ClassifyDecision:
        seen.update(kwargs)
        return ClassifyDecision(intent="respond", route="respond", reply=True)

    monkeypatch.setattr(
        executor_core,
        "_default_host_ports",
        lambda: (_ for _ in ()).throw(AssertionError("default adapter loaded")),
    )
    monkeypatch.setattr(executor_core, "run_classify_turn", fake_classify_turn)
    monkeypatch.setattr(
        executor_core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )

    result = run_executor(
        ExecutorRequest(query="hello"),
        classify_only=True,
        host_ports=_isolated_host_ports(events),
    )

    assert result.ok is True
    assert seen["max_parse_attempts"] == 1
    assert events == [
        ("begin_usage", None),
        ("begin_attempts", None),
        ("end_usage", "usage"),
        ("end_attempts", "attempts"),
    ]


def test_classify_non_parse_value_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_classify_turn(query: str, **kwargs: Any) -> ClassifyDecision:
        nonlocal calls
        calls += 1
        raise ValueError("invalid non-parser configuration")

    monkeypatch.setattr(executor_core, "run_classify_turn", fake_classify_turn)

    with pytest.raises(executor_core._ExecutorPhaseError):
        executor_core._run_classify(
            ExecutorRequest(query="hello"),
            SimpleNamespace(agent="test", model="test", effort="low"),
        )
    assert calls == 1


def test_research_profiler_span_uses_trace_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    finished: list[tuple[str | None, str]] = []

    class RecordingSpan:
        def __init__(self, fields: dict[str, Any]) -> None:
            self.fields = fields

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001, ANN204, ARG002
            self.finish(status="error" if exc is not None else "ok")
            return False

        def update(self, **fields: Any) -> None:
            self.fields.update(fields)

        def finish(self, *, status: str = "ok", **fields: Any) -> None:
            self.fields.update(fields)
            finished.append((self.fields.get("phase"), status))

    trace = AgentResearchTrace(
        route="research",
        question="q",
        iterations=(),
        final_verdict="refine",
        summary="",
        citations=(),
        uncertainty="",
        status="exhausted",
        elapsed_seconds=1.0,
    )
    research_result = AgentResearchResult(
        route="research",
        trace=trace,
        evidence_pack=EvidencePack(artifacts={}, ledger=EvidenceLedger(entries=())),
    )

    monkeypatch.setattr(
        executor_core,
        "profiler_span",
        lambda logger, event, **fields: RecordingSpan(fields),
    )
    monkeypatch.setattr(
        executor_core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )
    monkeypatch.setattr(
        executor_core,
        "_run_classify",
        lambda *args, **kwargs: ClassifyDecision(
            research=True,
            intent="research",
            route="research",
            reply=True,
        ),
    )
    monkeypatch.setattr(
        executor_core,
        "_run_agent_owned_research",
        lambda *args, **kwargs: research_result,
    )
    monkeypatch.setattr(executor_core, "_run_reply", lambda *args, **kwargs: "done")

    result = run_executor(
        ExecutorRequest(query="research this"),
        host_ports=_isolated_host_ports(events),
    )

    assert result.ok is True
    assert ("research", "exhausted") in finished
    assert ("research", "ok") not in finished
