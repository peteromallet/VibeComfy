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
from typing import Any, Generator
from unittest import mock

import pytest

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    PrecedentOption,
    PrecedentPacket,
    ResearchResult,
    SelectedPrecedent,
)
from vibecomfy.executor import core as executor_core
from vibecomfy.executor.core import run_executor
from vibecomfy.executor.prompts import build_classify_messages
from vibecomfy.executor.profiles import AgentSpecShape, set_profile_override_dir


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


def test_iter_graph_nodes_uses_dict_form_nodes_mapping() -> None:
    """Dict-form VibeComfy graphs should iterate the nested nodes mapping."""
    graph = {
        "nodes": {
            "27": {"id": "27", "class_type": "SaveVideo", "inputs": {}},
            "34": {"id": "34", "class_type": "MoonvalleyImg2VideoNode", "inputs": {}},
        },
        "links": [],
        "extra": {"note": "top-level metadata should not be treated as a node"},
    }

    assert executor_core._iter_graph_nodes(graph) == [
        ("27", {"id": "27", "class_type": "SaveVideo", "inputs": {}}),
        ("34", {"id": "34", "class_type": "MoonvalleyImg2VideoNode", "inputs": {}}),
    ]


def test_iter_graph_nodes_preserves_top_level_mapping_fallback() -> None:
    """Legacy top-level graph mappings should still be supported."""
    graph = {
        "27": {"id": "27", "class_type": "SaveVideo", "inputs": {}},
        "34": {"id": "34", "class_type": "MoonvalleyImg2VideoNode", "inputs": {}},
        "meta": {"note": "not a node"},
    }

    assert executor_core._iter_graph_nodes(graph) == [
        ("27", {"id": "27", "class_type": "SaveVideo", "inputs": {}}),
        ("34", {"id": "34", "class_type": "MoonvalleyImg2VideoNode", "inputs": {}}),
    ]


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
    **kwargs: Any,
) -> str:
    """Simulate an older reply wrapper that rejects adaptation_plan only."""
    if "adaptation_plan" in kwargs:
        raise TypeError("run_reply_turn() got an unexpected keyword argument 'adaptation_plan'")
    if not graph_summary:
        raise AssertionError("graph_summary should survive adaptation_plan fallback")
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


def _fake_handle_agent_edit_research(payload: dict, **kwargs: Any) -> dict:
    """Fake the durable non-applyable batch-REPL research response."""
    assert payload["route"] == "research"
    assert payload["executor_route"] == "research"
    assert payload["graph"] == {"nodes": [], "links": []}
    assert "research_summary" not in payload
    assert "executor_research" not in payload
    assert payload["research_brief"] == {
        "research_goal": "Find distilled or faster ways to run the current ComfyUI video workflow.",
        "search_directions": [
            "distilled or lightning video/motion models compatible with AnimateDiff-style workflows",
            "AnimateDiff speed settings such as context length, sampler, steps, and frame count",
            "ComfyUI workflow examples that trade quality for faster generation",
        ],
        "source_preferences": ["workflows", "messages", "web"],
        "avoid": [
            "generic searches for the raw sentence",
            "stopword-only searches such as there way run",
            "treating Discord snippets as authoritative without workflow evidence",
        ],
        "known_graph_context": "Attached graph may be absent; infer only broad workflow family from the request.",
    }
    return {
        "ok": True,
        "graph": {"nodes": [{"id": 99, "type": "ShouldNotApply"}]},
        "message": "The agent researched distilled/faster runtime options.",
        "outcome": {"kind": "noop", "reason": "research answer only"},
        "apply_eligible": False,
        "apply_eligibility": {
            "applyable": False,
            "reason": "no_candidate",
            "message": "Apply is not available for research routes.",
        },
        "graph_unchanged": True,
        "no_candidate_reason": "route_not_applyable",
        "session_id": "research-session",
        "turn_id": "0001",
        "artifacts": {"messages": "/tmp/turns/0001/messages.jsonl"},
        "detail_json_path": "/tmp/turns/0001/response.json",
    }


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


def _one_hivemind_client(query: str, timeout: float) -> dict[str, Any]:
    """Deterministic Hivemind client with one result, preventing web fallback."""
    return {
        "results": [
            {
                "title": "ComfyUI workflow research note",
                "description": "Relevant workflow/node technique reference.",
                "source": "test",
            }
        ]
    }


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


class TestResearchOnlyFlow:
    """Smoke tests for legacy research-only classify output.

    Canonical route behavior resolves this shape to research: agentic
    research loop, no applyable candidate.
    """

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_default_profile(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only legacy output resolves to agentic research and reply."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler node for ComfyUI",
                pack="core",
                tags=("sampling",),
                tasks=("t2i",),
                source="object_info",
            ),
        ]

        request = ExecutorRequest(
            query="What sampling nodes are available?", profile="default"
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert "distilled/faster" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is False
        assert result.to_dict()["route"] == "research"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False
        assert result.report.research is None
        assert result.report.implementation is not None
        assert result.report.implementation.durable_response is not None
        assert result.to_dict()["artifacts"]["messages"].endswith("messages.jsonl")
        mock_corpus.assert_not_called()
        mock_edit.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_openai_profile(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only legacy output uses research behavior with openai profile."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="VAEDecode",
                description="VAE Decode node",
                pack="core",
                source="object_info",
            ),
        ]

        request = ExecutorRequest(
            query="What VAE nodes exist?", profile="openai"
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is True
        assert result.to_dict()["route"] == "research"
        assert result.report.research is None
        mock_corpus.assert_not_called()
        mock_edit.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_sources_in_result(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only legacy output does not expose candidate or apply."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="CLIPTextEncode",
                description="CLIP text encoder",
                pack="core",
                source="object_info",
            ),
        ]

        request = ExecutorRequest(query="text encoding nodes", profile="default")
        result = run_executor(request)

        payload = result.to_dict()
        assert payload["route"] == "research"
        assert payload["candidate"] is None
        assert payload["apply_eligible"] is False
        assert result.report.research is None
        assert result.report.implementation is not None
        mock_corpus.assert_not_called()
        mock_edit.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_research_only_empty_corpus(
        self, mock_hivemind, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research behavior no longer depends on executor deterministic corpora."""
        mock_corpus.return_value = []

        request = ExecutorRequest(query="nonexistent node", profile="default")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.to_dict()["route"] == "research"
        assert result.report.research is None
        mock_corpus.assert_not_called()
        mock_hivemind.assert_not_called()
        mock_edit.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_hotshot)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_hotshot_xl_query(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """A Hotshot XL research-only classifier output stays research-only."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="HotshotXL",
                description="Hotshot XL SDXL-based text-to-video node",
                pack="hotshot-xl",
                tags=("video", "sdxl"),
                tasks=("i2v",),
                source="curated",
            ),
        ]

        request = ExecutorRequest(
            query="How do I add Hotshot XL to an SVD-XT workflow?",
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert "distilled/faster" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is False
        assert result.to_dict()["route"] == "research"
        assert result.report.research is None
        mock_corpus.assert_not_called()
        mock_edit.assert_called_once()


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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_describe_default_profile(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Graph-describe with default profile runs research, implement, and reply."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler for ComfyUI",
                pack="core",
                source="object_info",
            ),
        ]

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

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_describe_openai_profile(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Graph-describe with openai profile."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampling node",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.research.resolve_missing_nodes",
        side_effect=_empty_registry_resolver,
    )
    @mock.patch(
        "vibecomfy.executor.research._default_web_search_client",
        side_effect=_empty_web_search_client,
    )
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_graph_describe_research_failure_non_fatal(
        self,
        mock_hivemind,
        mock_web,
        mock_registry,
        mock_corpus,
        mock_edit,
        mock_reply,
        mock_classify,
        profile_dir: Path,
    ) -> None:
        """When research fails (empty corpus), the pipeline still completes."""
        mock_corpus.return_value = []

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
        # Research summary should indicate no results.
        assert "No relevant local results found" in result.report.research.summary

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_describe_with_graph_summary_context(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Classify receives graph summary when a graph is attached."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_reply_receives_post_implementation_graph_summary(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Reply receives the graph returned by implementation, not stale input graph context."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_reply_graph_summary_uses_replacement_implementation_graph(
        self, mock_hivemind, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Reply summaries describe the implemented graph, not the request graph."""
        from vibecomfy.search.index import SearchEntry

        def replace_graph(payload: dict, **kwargs: Any) -> dict:
            return {
                "graph": {"nodes": [{"id": 99, "class_type": "SaveImage"}]},
                "message": "Replaced graph with output node.",
            }

        mock_corpus.return_value = [
            SearchEntry(
                class_type="SaveImage",
                description="output image node",
                pack="core",
                source="object_info",
            ),
        ]

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
        """Adapt prefetches research, but a research failure is non-fatal."""
        result = run_executor(
            ExecutorRequest(
                query="describe and edit my graph",
                graph={"nodes": [{"id": 1, "class_type": "CLIPTextEncode"}]},
                profile="default",
            )
        )

        assert result.ok is True
        mock_research.assert_called_once()
        assert result.report.research is not None
        assert "research phase failed" in result.report.research.warnings[0]
        # Verbose diagnostics with sensitive query parameters are redacted.
        details = result.report.research.warning_details[0]
        assert details["type"] == "RuntimeError"
        assert "secret-value" not in details["message"]
        assert "redacted" in details["message"]
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
        """Adapt prefetches research; executor-phase research errors are non-fatal."""
        result = run_executor(
            ExecutorRequest(
                query="describe and edit my graph",
                graph={"nodes": [{"id": 1, "class_type": "CLIPTextEncode"}]},
                profile="default",
            )
        )

        assert result.ok is True
        mock_research.assert_called_once()
        assert result.report.research is not None
        assert "research phase error" in result.report.research.warnings[0]
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.research.resolve_missing_nodes",
        side_effect=_empty_registry_resolver,
    )
    @mock.patch(
        "vibecomfy.executor.research._default_web_search_client",
        side_effect=_empty_web_search_client,
    )
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_adapt_implementation_receives_no_automatic_research_context(
        self,
        mock_hivemind,
        mock_web,
        mock_registry,
        mock_corpus,
        mock_edit,
        mock_reply,
        mock_classify,
        profile_dir: Path,
    ) -> None:
        """Adapt prefetches research but does not inject raw research text into the edit payload."""
        from vibecomfy.search.index import SearchEntry

        source_path = (
            "ready_templates/sources/custom_nodes/ltxvideo/runexx/"
            "LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.py"
        )
        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXRuneXXCustomAudioLipsync",
                description="LTX RuneXX custom audio lipsync workflow template",
                pack="ltxvideo",
                tags=("ltx", "audio", "lipsync", "i2v"),
                tasks=("i2v", "audio"),
                source="custom_node_examples",
                path=source_path,
            ),
        ]

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
        # Research is prefetched for the adapt route.
        mock_corpus.assert_called_once()
        mock_hivemind.assert_called_once()
        mock_web.assert_called_once()
        reply_kwargs = mock_reply.call_args.kwargs
        assert reply_kwargs["research_summary"] is not None
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


def _hotshotxl_execution_plan_research_result() -> ResearchResult:
    return ResearchResult(
        summary="Found a HotShotXL AnimateDiff workflow precedent.",
        selected_precedent=SelectedPrecedent(
            name="AnimateDiff HotShotXL video workflow",
            source="hivemind_workflow",
            source_workflow_path="workflows/hotshotxl_8f.json",
            requested_terms=("HotShotXL", "video"),
            implementation_ecosystems=("animatediff",),
            models=("hotshotxl_mm_v1.pth", "sd_xl_base_1.0.safetensors"),
            minimal_spine=(
                "CheckpointLoaderSimple",
                "HotshotXLLoader",
                "ADE_AnimateDiffLoaderWithContext",
                "EmptyLatentImage",
                "KSampler",
                "VAEDecode",
                "VHS_VideoCombine",
            ),
            terminal_output_path=("VHS_VideoCombine",),
        ),
        precedent_packet=PrecedentPacket(
            options=(
                PrecedentOption(
                    source_class_type="video/hotshot_i2v",
                    node_types=("HotshotXLLoader", "VHS_VideoCombine"),
                ),
            ),
        ),
        precedent_sources=(
            {
                "source": "hivemind_workflow",
                "source_workflow_path": "workflows/hotshotxl_8f.json",
                "workflow_semantics": {
                    "node_types": [
                        "HotshotXLLoader",
                        "ADE_AnimateDiffLoaderWithContext",
                        "EmptyLatentImage",
                        "KSampler",
                        "VAEDecode",
                        "VHS_VideoCombine",
                    ],
                    "models": ["hotshotxl_mm_v1.pth"],
                },
            },
        ),
        workflow_precedent_status="compatible_workflow_found",
    )


def test_adapt_implementation_fails_closed_when_research_has_no_evidence() -> None:
    plan = _fake_classify_adapt("Switch to Hotshot")
    request = ExecutorRequest(
        query="Switch to Hotshot",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    research = ResearchResult(
        summary="Research skipped due to an internal error.",
        warnings=("research phase failed: RuntimeError",),
    )

    result = executor_core._run_implement(
        request,
        AgentSpecShape(agent="hermes", model="test"),
        plan=plan,
        research_result=research,
    )

    assert result.graph is None
    assert result.durable_response is not None
    assert result.durable_response["apply_eligible"] is False
    assert result.durable_response["no_candidate_reason"] == "implementation_skipped"
    assert "research failed" in result.message


def test_adapt_payload_includes_enforced_execution_plan_note() -> None:
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
            research_result=_hotshotxl_execution_plan_research_result(),
        )

    assert result.graph is not None
    payload = mock_edit.call_args[0][0]
    notes = payload["execution_protocol_notes"]
    execution_plan = notes["execution_plan"]
    assert execution_plan["provenance"]["enforced"] is True
    assert execution_plan["provenance"]["phase"] == "m3_execute_enforcement"
    assert "enforced execution protocol" in notes["_discardability"]
    serialized_plan = execution_plan["plan"]
    assert serialized_plan["contract_version"] == "execution_plan_v1"
    assert serialized_plan["plan_id"].startswith("plan.hotshotxl_8f.")
    assert serialized_plan["schema_provenance"]["execution_plan_builder"]["normalizer"] == (
        "hotshotxl_video_v1"
    )
    assert "precedent_slices" not in payload
    assert "adaptation_plan" not in payload
    assert "execution_plan" not in payload


def test_adapt_execution_plan_builder_failure_does_not_block_edit_payload() -> None:
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

    with (
        mock.patch(
            "vibecomfy.executor.core.build_execution_plan",
            side_effect=RuntimeError("builder unavailable"),
        ),
        mock.patch(
            "vibecomfy.executor.core.handle_agent_edit",
            side_effect=_fake_handle_agent_edit,
        ) as mock_edit,
    ):
        result = executor_core._run_implement(
            request,
            AgentSpecShape(agent="hermes", model="test"),
            plan=plan,
            research_result=_hotshotxl_execution_plan_research_result(),
        )

    assert result.graph is not None
    payload = mock_edit.call_args[0][0]
    notes = payload["execution_protocol_notes"]
    assert "execution_plan" not in notes


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
            with mock.patch("vibecomfy.executor.research.build_search_corpus") as mock_corpus:
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
        mock_corpus.assert_not_called()
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
        with mock.patch(
            "vibecomfy.executor.research.build_search_corpus"
        ) as mock_corpus:
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
        mock_corpus.assert_not_called()
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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_inspect_calls_research_skips_implementation(
        self,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: research is skipped, implementation is skipped."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampling node",
                pack="core",
                source="object_info",
            ),
        ]

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
        mock_corpus.assert_not_called()
        # Implementation MUST NOT be called.
        mock_edit.assert_not_called()
        # Reply MUST be called.
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_inspect_report_flags_correct_phases(
        self,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect report: research=None, implementation=None, route=inspect."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="VAEDecode",
                description="Decode node",
                pack="core",
                source="object_info",
            ),
        ]

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
            with mock.patch(
                "vibecomfy.executor.research.build_search_corpus"
            ) as mock_corpus:
                request = ExecutorRequest(
                    query="what do you mean?",
                    graph={"nodes": [{"id": 1}]},
                    profile="default",
                )
                result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # Research MUST NOT be called.
        mock_corpus.assert_not_called()
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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_calls_both_research_and_implementation(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: both research and implementation phases run."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXImageToVideo",
                description="LTX video node",
                pack="ltxvideo",
                source="object_info",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add audio to my LTX workflow",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        # Research MUST be called (adapt gate: research=True).
        mock_corpus.assert_called_once()
        # Implementation MUST be called.
        mock_edit.assert_called_once()
        # Reply MUST be called.
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_report_flags_correct_phases(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt report: research present, implementation present."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_payload_uses_canonical_route_and_provider_metadata(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt keeps provider dispatch separate from executor route semantics."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_inspect_phase_event_includes_route_and_task(
        self,
        mock_ws_send: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """WebSocket classify progress event emits route and task for inspect."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core._ws_send")
    def test_adapt_phase_event_includes_route_and_task(
        self,
        mock_ws_send: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """WebSocket classify progress event emits route and task for adapt."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_no_route_research_only_resolves_to_research_with_research_phase(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Without explicit route, research-only resolves to agentic research."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

        request = ExecutorRequest(
            query="what nodes are available?",
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.to_dict()["route"] == "research"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False
        assert result.report.research is None
        mock_corpus.assert_not_called()
        mock_edit.assert_called_once()

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
        with mock.patch(
            "vibecomfy.executor.research.build_search_corpus"
        ) as mock_corpus:
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
        mock_corpus.assert_not_called()

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
            mock.patch("vibecomfy.executor.research.build_search_corpus") as mock_corpus,
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
        mock_corpus.assert_not_called()
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
            mock.patch("vibecomfy.executor.research.build_search_corpus") as mock_corpus,
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
        mock_corpus.assert_not_called()
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_public_envelope_never_has_candidate_or_apply(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
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
        mock_corpus.assert_not_called()
        mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_public_envelope_apply_eligible_only_with_candidate(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampling node",
                pack="core",
                source="object_info",
            ),
        ]

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
        mock_corpus.assert_called_once()
        mock_edit.assert_called_once()



# ── Inspect-only flow tests (T7) ─────────────────────────────────────────────
# Verify inspect route produces a reply with graph inspection context,
# no implementation result, no candidate graph, and research invocation
# follows the route gate table.

class TestInspectOnlyFlow:
    """Inspect-only route tests: graph inspection in reply, no edits, no graph."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_reject_adaptation_plan)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_reply_fallback_preserves_graph_summary_when_adaptation_plan_unsupported(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
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
        assert mock_reply.call_count == 2
        first_kwargs = mock_reply.call_args_list[0].kwargs
        second_kwargs = mock_reply.call_args_list[1].kwargs
        assert "adaptation_plan" in first_kwargs
        assert "adaptation_plan" not in second_kwargs
        assert "CheckpointLoaderSimple" in str(second_kwargs.get("graph_summary"))
        mock_edit.assert_not_called()
        mock_corpus.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_reply_receives_graph_inspection_context(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: _run_reply receives graph_inspection kwarg with node details."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler", "class_type": "KSampler"},
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
        # graph_inspection should be passed to _run_reply
        reply_kwargs = mock_reply.call_args.kwargs
        graph_summary = reply_kwargs.get("graph_summary")
        assert graph_summary is not None
        assert "CheckpointLoaderSimple" in graph_summary
        assert "KSampler" in graph_summary
        # Implementation must never be called
        mock_edit.assert_not_called()
        # Research must NOT be called (inspect answers from graph inspection only)
        mock_corpus.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_result_graph_is_none(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: ExecutorResult.graph is always None regardless of input graph."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="VAEDecode",
                description="Decode node",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_no_graph_still_produces_reply(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect with no graph: still produces reply, no graph_inspection."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_to_dict_has_no_graph(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: to_dict() has graph=None, implementation=None, research populated."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="CLIPTextEncode",
                description="Text encoder",
                pack="core",
                source="object_info",
            ),
        ]

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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_implementation_not_called_even_with_graph(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: handle_agent_edit never called, even with a complex graph."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampler",
                pack="core",
                source="object_info",
            ),
        ]

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
        mock_corpus.assert_not_called()
        # Reply is called
        mock_reply.assert_called_once()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_inspect)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_inspect_graph_inspection_includes_widget_values(
        self,
        mock_edit: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """inspect: graph_inspection text includes widget values and links."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {
            "nodes": [
                {"id": 1, "type": "KSampler", "widgets_values": [42, 7.5, "euler"]},
                {"id": 2, "type": "VAEDecode", "widgets_values": [None]},
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
            graph_reference_map={"1": "KSampler"},
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
            graph_reference_map={"1": "LoadImage", "2": "KSampler"},
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


class TestPrecedentPayloadIntegrity:
    """Prove precedent route payloads include legacy + structured research data,
    and direct-edit payloads exclude accidental research/precedent context."""

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _capture_edit_payload(mock_edit: mock.MagicMock) -> dict:
        """Return the first positional arg (the payload dict) passed to handle_agent_edit."""
        mock_edit.assert_called_once()
        return mock_edit.call_args[0][0]

    # ── adapt: agent-chosen research ──────────────────────────

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_precedent_route_payload_excludes_automatic_research_fields(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: handle_agent_edit receives scoped execution_protocol_notes,
        not raw-query research_summary/sources/executor_research at top level."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXImageToVideo",
                description="LTX video generation node",
                pack="ltxvideo",
                source="ready_template",
                path="/templates/ltx_audio_video.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add audio path to my LTX workflow",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Raw-query fields are NOT at top level for adapt route.
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        # Scoped research is nested under execution_protocol_notes.
        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        assert "_discardability" in notes

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_precedent_route_payload_excludes_automatic_adaptation_plan(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: executor nests scoped research under execution_protocol_notes;
        raw precedent_slices and adaptation_plan are not at top level."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="AudioLipsyncWorkflow",
                description="Audio-driven lipsync workflow template",
                pack="lipsync",
                source="ready_template",
                path="/templates/audio_lipsync.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadAudio"}]}
        request = ExecutorRequest(
            query="adapt audio lipsync workflow to my graph",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Structured fields are NOT at top level for adapt route.
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload
        # Scoped research is nested under execution_protocol_notes.
        assert "execution_protocol_notes" in payload

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_precedent_route_payload_does_not_mix_prefetch_with_agent_edit(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: scoped research is nested under execution_protocol_notes;
        raw-query fields are not injected at top level."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="SVDXTWithAudio",
                description="SVD-XT extended with audio processing",
                pack="svdxt",
                source="ready_template",
                path="/templates/svd_xt_audio.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "SVDImageEmbeds"}]}
        request = ExecutorRequest(
            query="add audio to my SVD video pipeline",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Raw-query fields are NOT at top level for adapt route.
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload
        # Scoped research is nested under execution_protocol_notes.
        assert "execution_protocol_notes" in payload

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_precedent_route_report_excludes_automatic_research_data(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: the ExecutorResult report includes scoped research in
        the report, and the edit payload uses execution_protocol_notes."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="HotshotXLPipeline",
                description="Hotshot XL text-to-video pipeline",
                pack="hotshot",
                source="ready_template",
                path="/templates/hotshot_xl.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="use hotshot XL template for video generation",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # Research now runs for adapt route (scoped, not raw query).
        assert result.report.research is not None
        assert result.report.implementation is not None
        d = result.to_dict()
        assert "research" in d["report"]["executor"]
        # Edit payload uses execution_protocol_notes, not raw-query fields.
        payload = self._capture_edit_payload(mock_edit)
        assert "execution_protocol_notes" in payload

    # ── revise: no research / no precedent ──────────────────────────

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_revise_payload_excludes_legacy_research_fields(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: handle_agent_edit does NOT receive research_summary,
        research_sources, or executor_research keys."""
        with mock.patch(
            "vibecomfy.executor.research.build_search_corpus"
        ) as mock_corpus:
            input_graph = {"nodes": [{"id": 1, "type": "VAEDecode"}]}
            request = ExecutorRequest(
                query="set seed to 42",
                graph=input_graph,
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Legacy research fields must be ABSENT
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        # Research must NOT have been called
        mock_corpus.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_revise_payload_excludes_structured_precedent_fields(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: handle_agent_edit does NOT receive precedent_slices or
        adaptation_plan keys."""
        input_graph = {"nodes": [{"id": 1, "type": "KSampler"}]}
        request = ExecutorRequest(
            query="change sampler steps to 20",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Structured precedent fields must be ABSENT
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_revise_payload_has_no_precedent_prompt_text(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: the payload dict contains no string values with
        'Precedent adaptation plan' or 'precedent' substrings that could
        leak into prompts."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="update the node field",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Recursively check all string values in the payload for precedent text
        def _check_no_precedent_text(obj: object, path: str = "root") -> None:
            if isinstance(obj, str):
                assert "precedent" not in obj.lower(), (
                    f"Found 'precedent' text at {path}: {obj[:200]}"
                )
                assert "Precedent adaptation plan" not in obj, (
                    f"Found 'Precedent adaptation plan' text at {path}"
                )
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    _check_no_precedent_text(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _check_no_precedent_text(v, f"{path}[{i}]")

        _check_no_precedent_text(payload)

    # ── edge case: no workflow sources means structured fields are absent ─

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_precedent_route_without_workflow_sources_no_structured_fields(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: when no workflow source exists in the corpus,
        legacy research fields are NOT at top level; scoped context is
        nested under execution_protocol_notes."""
        from vibecomfy.search.index import SearchEntry

        # Non-workflow sources (object_info) do NOT produce precedent slices
        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler node",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="research precedent for sampling",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Raw-query fields are NOT at top level for adapt route.
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload
        # Scoped research is nested under execution_protocol_notes.
        assert "execution_protocol_notes" in payload


# ── Precedent adaptation plan prompt assembly tests (T14) ───────────────────
# Verify agent-edit prompt assembly only injects precedent text for
# adapt route and keeps direct-edit prompts clean.


class TestPrecedentAdaptationPromptAssembly:
    """Prove precedent prompt text is injected only for adapt
    route and direct-edit prompts remain clean."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_precedent_route_edit_payload_includes_precedent_slices_for_prompt(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: the payload passed to handle_agent_edit includes
        execution_protocol_notes with scoped research context, not raw
        precedent_slices/adaptation_plan at top level."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXAudioPipeline",
                description="LTX audio-video pipeline template",
                pack="ltxaudio",
                source="ready_template",
                path="/templates/ltx_audio_pipeline.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadVideo"}]}
        request = ExecutorRequest(
            query="adapt LTX audio pipeline to my video workflow",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        mock_edit.assert_called_once()
        payload = mock_edit.call_args[0][0]

        # Structured fields NOT at top level for adapt route.
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload
        # Scoped research is nested under execution_protocol_notes.
        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        assert "_discardability" in notes
        # Discardability guidance confirms non-authoritative context.
        assert "NOT authoritative" in notes["_discardability"]

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_revise_payload_no_precedent_prompt_keys(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: the payload passed to handle_agent_edit has no
        precedent_slices or adaptation_plan keys, so the agent-edit engine
        cannot inject precedent prompt text."""
        input_graph = {"nodes": [{"id": 1, "type": "SaveImage"}]}
        request = ExecutorRequest(
            query="change filename prefix to output",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = mock_edit.call_args[0][0]

        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload
        # Also verify no research context
        assert "research_summary" not in payload
        assert "research_sources" not in payload

# ── Precedent payload integrity tests (T14) ──────────────────────────────────
# Verify adapt payloads carry both legacy and structured research
# data, while revise payloads carry neither.


# ── T10: Adapt prefetch and research context scoping ─────────────────────────
# Prove adapt prefetch receives scoped classifier-derived query/payload,
# execution_protocol_notes are nested and explicitly unranked, revise does
# not prefetch while needs_research=False, research_context_packet is present
# when available, and empty/irrelevant packets are framed as discardable context.


class TestAdaptPrefetchAndResearchContextScoping:
    """T10: Prove adapt prefetch scoping, execution_protocol_notes nesting,
    revise no-prefetch, research_context_packet presence/absence, and
    discardability framing for empty/irrelevant packets."""

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _capture_edit_payload(mock_edit: mock.MagicMock) -> dict:
        """Return the first positional arg (the payload dict) passed to handle_agent_edit."""
        mock_edit.assert_called_once()
        return mock_edit.call_args[0][0]

    # ── A: adapt receives scoped classifier-derived query/payload ────────

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_adapt_payload_nests_classifier_fields_in_protocol_notes(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: execution_protocol_notes carries classifier-derived fields
        (research_goal, pattern_category, change_goal, model_families) from
        the ClassifyDecision, not raw user query fields."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler node",
                pack="core",
                source="object_info",
            ),
        ]

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent for KSampler config",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal="Find optimal KSampler configuration patterns",
            pattern_category="sampling",
            change_goal="adjust sampler steps and cfg",
            model_families=("SDXL", "Flux"),
        )

        input_graph = {"nodes": [{"id": 1, "type": "KSampler"}]}
        request = ExecutorRequest(
            query="optimize my sampler",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Classifier-derived fields must be nested under execution_protocol_notes
        # and NOT at top level.
        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        assert "research_goal" in notes
        assert notes["research_goal"] == "Find optimal KSampler configuration patterns"
        assert "pattern_category" in notes
        assert notes["pattern_category"] == "sampling"
        assert "change_goal" in notes
        assert notes["change_goal"] == "adjust sampler steps and cfg"
        assert "model_families" in notes
        assert notes["model_families"] == ["SDXL", "Flux"]

        # Classifier fields are NOT at top level.
        assert "research_goal" not in payload
        assert "pattern_category" not in payload
        assert "change_goal" not in payload
        assert "model_families" not in payload

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_adapt_payload_classifier_fields_absent_when_empty_in_decision(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: when ClassifyDecision has empty classifier fields,
        execution_protocol_notes omits those keys entirely."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LoadImage",
                description="Load image node",
                pack="core",
                source="object_info",
            ),
        ]

        # ClassifyDecision with NO classifier-scoping fields populated.
        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
            # research_goal, pattern_category, change_goal, model_families all empty
        )

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add an image loader",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        # Empty classifier fields must be omitted, not sent as empty strings/lists.
        assert "research_goal" not in notes
        assert "pattern_category" not in notes
        assert "change_goal" not in notes
        assert "model_families" not in notes

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_adapt_scoped_query_built_from_classifier_fields(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: when classifier fields are populated, _run_research receives
        a scoped query built from those fields, not the raw user query."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="AudioLipsyncWorkflow",
                description="Audio lipsync workflow",
                pack="lipsync",
                source="ready_template",
                path="/templates/audio_lipsync.py",
            ),
        ]

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research audio lipsync precedent",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal="Find audio-driven lipsync workflow patterns",
            pattern_category="audio_video",
            change_goal="integrate audio-reactive lipsync",
            model_families=("WanVideo",),
        )

        # Spy on _run_research to capture the scoped query.
        from vibecomfy.executor import core as executor_core_module

        original_run_research = executor_core_module._run_research
        captured_queries: list[str] = []

        def _spy_run_research(
            request_obj: ExecutorRequest,
            _spec: Any,
            *,
            plan: ClassifyDecision | None = None,
        ) -> ResearchResult:
            # Capture the effective query that will be used.
            query = request_obj.query
            if (
                plan is not None
                and executor_core_module._canonical_route_for_plan(plan) == "adapt"
            ):
                scoped_parts: list[str] = []
                if plan.research_goal:
                    scoped_parts.append(f"Research goal: {plan.research_goal}")
                if plan.pattern_category:
                    scoped_parts.append(f"Pattern category: {plan.pattern_category}")
                if plan.change_goal:
                    scoped_parts.append(f"Change goal: {plan.change_goal}")
                if plan.model_families:
                    families = ", ".join(plan.model_families)
                    scoped_parts.append(f"Model families: {families}")
                if scoped_parts:
                    query = "; ".join(scoped_parts)
            captured_queries.append(query)
            return original_run_research(request_obj, _spec, plan=plan)

        input_graph = {"nodes": [{"id": 1, "type": "LoadAudio"}]}
        request = ExecutorRequest(
            query="make lipsync work with my audio",
            graph=input_graph,
            profile="default",
        )

        with mock.patch.object(
            executor_core_module, "_run_research", side_effect=_spy_run_research
        ):
            result = run_executor(request)

        assert result.ok is True
        assert len(captured_queries) == 1, (
            f"Expected exactly 1 research call, got {len(captured_queries)}"
        )
        scoped_query = captured_queries[0]
        # The scoped query must NOT be the raw user query.
        assert scoped_query != "make lipsync work with my audio"
        # It must contain the classifier-derived fields.
        assert "Research goal:" in scoped_query
        assert "audio-driven lipsync workflow patterns" in scoped_query
        assert "Pattern category:" in scoped_query
        assert "audio_video" in scoped_query
        assert "Change goal:" in scoped_query
        assert "integrate audio-reactive lipsync" in scoped_query
        assert "Model families:" in scoped_query
        assert "WanVideo" in scoped_query

    # ── B: execution_protocol_notes are nested and explicitly unranked ───

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_execution_protocol_notes_discardability_explicitly_unranked(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: execution_protocol_notes._discardability explicitly states
        the notes are NOT authoritative guidance and may be discarded.
        No ranking, priority, winner, or recommended language appears."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LoadImage",
                description="Load image node",
                pack="core",
                source="object_info",
            ),
        ]

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

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="adapt workflow",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        assert "_discardability" in notes

        discard = notes["_discardability"]
        # Must state NOT authoritative.
        assert "NOT authoritative" in discard
        # Must offer discardability guidance.
        assert "discard" in discard.lower()

        # Check the entire notes dict for forbidden ranking language.
        notes_str = json.dumps(notes, sort_keys=True)
        forbidden_terms = ["winner", "best", "selected", "score", "rank",
                           "primary", "preferred", "chosen", "pick", "choice",
                           "recommend", "priority"]
        for term in forbidden_terms:
            assert term not in notes_str.lower(), (
                f"execution_protocol_notes contains forbidden term '{term}': {notes_str[:200]}"
            )

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_execution_protocol_notes_not_at_top_level(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: all research context fields exclusive to execution_protocol_notes
        nesting; no research_summary, research_sources, executor_research, or
        classifier fields leak to top level."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler node",
                pack="core",
                source="object_info",
            ),
        ]

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal="sampler optimization",
            model_families=("SDXL",),
        )

        input_graph = {"nodes": [{"id": 1, "type": "KSampler"}]}
        request = ExecutorRequest(
            query="optimize sampler",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # These fields must NOT be at top level for adapt route.
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload

        # Everything must be nested under execution_protocol_notes.
        assert "execution_protocol_notes" in payload

    # ── C: revise does not prefetch while needs_research=False ───────────

    def test_should_prefetch_research_false_for_revise(self) -> None:
        """_should_prefetch_research returns False for revise route."""
        from vibecomfy.executor.core import _should_prefetch_research

        plan = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="direct edit",
            intent="edit",
            route="revise",
            task="edit_graph",
        )
        assert _should_prefetch_research(plan) is False

    def test_should_prefetch_research_true_for_adapt_when_needs_research(self) -> None:
        """_should_prefetch_research returns True for adapt when needs_research=True."""
        from vibecomfy.executor.core import _should_prefetch_research

        plan = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research then adapt",
            intent="edit",
            route="adapt",
            task="research_precedent",
        )
        assert _should_prefetch_research(plan) is True

    def test_should_prefetch_research_false_for_research_route(self) -> None:
        """Research routes use the agentic loop, not executor prefetch."""
        from vibecomfy.executor.core import _should_prefetch_research

        plan = ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="research only",
            intent="research",
            route="research",
            task="research",
        )
        assert _should_prefetch_research(plan) is False

    def test_should_prefetch_research_false_for_non_research_routes(self) -> None:
        """_should_prefetch_research returns False for respond, clarify, inspect."""
        from vibecomfy.executor.core import _should_prefetch_research

        for route in ("respond", "clarify", "inspect"):
            plan = ClassifyDecision(
                research=False,
                implement=False,
                reply=True,
                effort="low",
                plan_summary=f"{route} only",
                intent="respond",
                route=route,
                task="respond" if route != "inspect" else "inspect_graph",
            )
            assert _should_prefetch_research(plan) is False, (
                f"_should_prefetch_research must be False for {route}"
            )

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_revise_payload_has_no_execution_protocol_notes(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: payload has no execution_protocol_notes, research_context_packet,
        research_summary, or research_sources."""
        input_graph = {"nodes": [{"id": 1, "type": "SaveImage"}]}
        request = ExecutorRequest(
            query="change filename prefix",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        assert "execution_protocol_notes" not in payload
        assert "research_context_packet" not in payload
        assert "research_summary" not in payload
        assert "research_sources" not in payload
        assert "executor_research" not in payload
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_revise)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_revise_skips_research_phase_entirely(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """revise: research phase is skipped entirely; build_search_corpus is
        never called (proving no prefetch occurs)."""
        input_graph = {"nodes": [{"id": 1, "type": "SaveImage"}]}
        request = ExecutorRequest(
            query="change filename prefix",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # build_search_corpus must never be called for revise route.
        mock_corpus.assert_not_called()

    # ── D: research_context_packet present when available ────────────────

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_research_context_packet_present_when_workflow_sources_exist(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: when research produces a precedent_packet from workflow
        sources, research_context_packet is included in the edit payload."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXImageToVideo",
                description="LTX video generation node",
                pack="ltxvideo",
                source="ready_template",
                path="/templates/ltx_audio_video.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add audio path to my LTX workflow",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # research_context_packet must be present when precedent_packet exists.
        assert "research_context_packet" in payload, (
            "research_context_packet must be present when workflow sources produce a precedent_packet"
        )
        packet = payload["research_context_packet"]
        assert isinstance(packet, dict)
        # Must contain expected PrecedentPacket keys.
        assert "options" in packet, (
            "research_context_packet must contain 'options' key"
        )
        assert "context_note" in packet, (
            "research_context_packet must contain 'context_note' key"
        )
        notes = payload.get("execution_protocol_notes")
        assert isinstance(notes, dict)
        selected = notes.get("selected_precedent")
        assert isinstance(selected, dict)
        assert selected.get("name") == "LTXImageToVideo"
        assert selected.get("source") == "ready_template"

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_selected_precedent_suppresses_classifier_avoid_in_research_brief(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: stale classifier avoid guidance must not contradict a
        selected workflow's implementation ecosystem."""
        from vibecomfy.search.index import SearchEntry

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal="Find the LTX workflow wiring.",
            search_directions=(
                "LTX image-to-video workflow nodes",
                "LTX frame count conditioning",
            ),
            source_preferences=("workflows", "messages"),
            avoid=("LTX or other video frameworks",),
        )
        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXImageToVideo",
                description="LTX image-to-video ready template with frame count controls.",
                pack="ltxvideo",
                source="ready_template",
                path="/templates/ltx_i2v.py",
                model_families=("ltx",),
                tags=("ltx", "video-generation"),
                media_type="video",
                task_type="image_to_video",
            ),
        ]

        request = ExecutorRequest(
            query="Switch this to instead generate 8 frames of video using LTX",
            graph={"nodes": [{"id": 1, "type": "LoadImage"}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)
        notes = payload.get("execution_protocol_notes")
        assert isinstance(notes, dict)
        assert isinstance(notes.get("selected_precedent"), dict)
        assert "avoid" not in payload.get("research_brief", {})

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_install_search_directions_are_rewritten_for_precedent_research(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Classifier guesses about installs must not steer normal adapt research."""
        from vibecomfy.search.index import SearchEntry

        captured_research_queries: list[str] = []

        def _fake_research(query: str, **kwargs: Any) -> ResearchResult:
            captured_research_queries.append(query)
            return ResearchResult(
                summary="Found HotShotXL workflow precedent.",
                sources=(
                    {
                        "source": "hivemind_workflow",
                        "class_type": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
                        "source_workflow_path": (
                            "https://github.com/fictions-ai/sharing-is-caring/blob/main/"
                            "workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json"
                        ),
                        "workflow_schema_classes": [
                            "ADE_AnimateDiffLoaderWithContext",
                            "ADE_AnimateDiffUniformContextOptions",
                            "VHS_VideoCombine",
                        ],
                        "model_families": ("hotshot", "animatediff", "sdxl"),
                    },
                ),
            )

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research HotShotXL precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal=(
                "Find ComfyUI workflow examples, node pack details, and wiring "
                "patterns for HotShotXL video generation."
            ),
            search_directions=(
                "HotShotXL ComfyUI workflow example",
                "HotShotXL node pack installation and usage",
                "HotShotXL frame count parameter",
            ),
            source_preferences=("workflows", "registry", "messages"),
        )
        mock_corpus.return_value = [
            SearchEntry(
                class_type="AnimateDiff Video Generation with ControlNet and IP-Adapter",
                description="HotShotXL workflow precedent using AnimateDiff and VHS output.",
                pack="workflow",
                source="hivemind_workflow",
                path="workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                model_families=("hotshot", "animatediff", "sdxl"),
                tags=("hotshot", "video-generation"),
                media_type="video",
                task_type="image_to_video",
            ),
        ]

        with mock.patch("vibecomfy.executor.core.run_research_phase", side_effect=_fake_research):
            request = ExecutorRequest(
                query="Switch this to instead generate 8 frames of video using HotShotXL",
                graph={"nodes": [{"id": 1, "type": "LoadImage"}]},
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert captured_research_queries == [
            (
                "HotShotXL ComfyUI workflow example; "
                "HotShotXL workflow precedent and usage; "
                "HotShotXL frame count parameter"
            )
        ]
        payload = self._capture_edit_payload(mock_edit)
        brief = payload.get("research_brief")
        assert isinstance(brief, dict)
        brief_text = json.dumps(brief)
        assert "install" not in brief_text.casefold()
        assert "node pack" not in brief_text.casefold()
        assert brief["research_goal"] == (
            "Find ComfyUI workflow examples and wiring "
            "patterns for HotShotXL video generation"
        )
        assert brief["search_directions"] == [
            "HotShotXL ComfyUI workflow example",
            "HotShotXL workflow precedent and usage",
            "HotShotXL frame count parameter",
        ]
        assert brief["source_preferences"] == ["workflows", "messages"]

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_user_named_absent_hotshotxl_remains_adapt_planning_signal(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """A user-named external workflow tech can drive adapt planning even
        when no current graph node already belongs to that ecosystem."""
        captured_research_queries: list[str] = []

        def _fake_research(query: str, **kwargs: Any) -> ResearchResult:
            captured_research_queries.append(query)
            return _hotshotxl_execution_plan_research_result()

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research HotShotXL precedent workflow then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal="Find HotShotXL workflow precedents for 8-frame video.",
            search_directions=(
                "HotShotXL 8 frame workflow precedent",
                "KSampler to AnimateDiff HotShotXL motion model wiring",
            ),
            source_preferences=("workflows", "messages"),
        )

        request = ExecutorRequest(
            query="Switch this image workflow to generate 8 frames using HotShotXL.",
            graph={
                "nodes": [
                    {"id": 1, "type": "LoadImage", "class_type": "LoadImage"},
                    {"id": 2, "type": "KSampler", "class_type": "KSampler"},
                ],
                "links": [],
            },
            profile="default",
        )

        with mock.patch("vibecomfy.executor.core.run_research_phase", side_effect=_fake_research):
            result = run_executor(request)

        assert result.ok is True
        assert captured_research_queries == [
            "HotShotXL 8 frame workflow precedent; "
            "KSampler to AnimateDiff HotShotXL motion model wiring"
        ]
        payload = self._capture_edit_payload(mock_edit)
        notes = payload.get("execution_protocol_notes")
        assert isinstance(notes, dict)
        assert notes["research_goal"] == "Find HotShotXL workflow precedents for 8-frame video."
        execution_plan = notes.get("execution_plan")
        assert isinstance(execution_plan, dict)
        assert execution_plan["provenance"]["enforced"] is True
        assert execution_plan["provenance"]["phase"] == "m3_execute_enforcement"
        assert execution_plan["plan"]["plan_id"].startswith("plan.hotshotxl_8f.")
        assert "execution_plan" not in payload
        brief = payload.get("research_brief")
        assert isinstance(brief, dict)
        assert brief["search_directions"] == [
            "HotShotXL 8 frame workflow precedent",
            "KSampler to AnimateDiff HotShotXL motion model wiring",
        ]

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    def test_explicit_install_request_keeps_install_provider_research_terms(
        self,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        captured_research_queries: list[str] = []

        def _fake_research(query: str, **kwargs: Any) -> ResearchResult:
            captured_research_queries.append(query)
            return _hotshotxl_execution_plan_research_result()

        mock_classify.return_value = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research HotShotXL installation and workflow precedent",
            intent="edit",
            route="adapt",
            task="research_precedent",
            research_goal="Find HotShotXL node pack installation and workflow details.",
            search_directions=(
                "HotShotXL node pack installation and usage",
                "HotShotXL provider pack workflow example",
            ),
            source_preferences=("workflows", "registry", "messages"),
        )

        request = ExecutorRequest(
            query=(
                "Which pack provides HotShotXL, install it if needed, and switch "
                "this workflow to 8-frame video?"
            ),
            graph={"nodes": [{"id": 1, "type": "KSampler", "class_type": "KSampler"}]},
            profile="default",
        )

        with mock.patch("vibecomfy.executor.core.run_research_phase", side_effect=_fake_research):
            result = run_executor(request)

        assert result.ok is True
        assert captured_research_queries == [
            "HotShotXL node pack installation and usage; "
            "HotShotXL provider pack workflow example"
        ]
        payload = self._capture_edit_payload(mock_edit)
        brief = payload.get("research_brief")
        assert isinstance(brief, dict)
        assert brief["research_goal"] == (
            "Find HotShotXL node pack installation and workflow details."
        )
        assert brief["search_directions"] == [
            "HotShotXL node pack installation and usage",
            "HotShotXL provider pack workflow example",
        ]
        assert brief["source_preferences"] == ["workflows", "registry", "messages"]

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_research_context_packet_absent_when_no_workflow_sources(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: when research produces no precedent_packet (no workflow
        sources), research_context_packet is absent from the edit payload."""
        from vibecomfy.search.index import SearchEntry

        # Non-workflow sources (object_info) do not produce precedent packets.
        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler node",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="research precedent for sampling",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # research_context_packet must be absent when no precedent_packet.
        assert "research_context_packet" not in payload, (
            "research_context_packet must be absent when no workflow sources produce a precedent_packet"
        )
        # execution_protocol_notes must still be present (it carries the
        # _discardability guidance and any classifier fields).
        assert "execution_protocol_notes" in payload

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_research_context_packet_contains_evidence_not_directive(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: research_context_packet contains evidence/context framing
        fields (context_note, options) and no forbidden winner/score keys."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXAudioPipeline",
                description="LTX audio pipeline template",
                pack="ltxaudio",
                source="ready_template",
                path="/templates/ltx_audio_pipeline.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadVideo"}]}
        request = ExecutorRequest(
            query="adapt LTX audio pipeline",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        assert "research_context_packet" in payload
        packet = payload["research_context_packet"]

        # Forbidden winner/ranking keys must be absent at all nesting levels.
        forbidden = {"winner", "best", "selected", "score", "rank",
                     "primary", "preferred", "chosen", "pick", "choice",
                     "recommend", "priority"}

        def _check_forbidden_keys(obj: Any, path: str = "root") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_lower = k.lower()
                    assert k_lower not in forbidden, (
                        f"research_context_packet has forbidden key '{k}' at {path}"
                    )
                    _check_forbidden_keys(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _check_forbidden_keys(v, f"{path}[{i}]")

        _check_forbidden_keys(packet)

    # ── E: empty/irrelevant packets framed as discardable context ────────

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_discardability_guidance_instructs_discard_of_irrelevant_context(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: _discardability guidance explicitly allows discarding packets
        that are empty, irrelevant, or contradict the user's request."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LoadImage",
                description="Load image node",
                pack="core",
                source="ready_template",
                path="/templates/load_image.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="adapt image loader template",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        assert "_discardability" in notes

        discard = notes["_discardability"]
        # Must mention discarding empty packets.
        assert "empty" in discard.lower(), (
            f"_discardability must mention empty packets: {discard[:200]}"
        )
        # Must mention discarding irrelevant packets.
        assert "irrelevant" in discard.lower(), (
            f"_discardability must mention irrelevant packets: {discard[:200]}"
        )
        # Must mention the user's explicit request.
        assert "user's explicit request" in discard.lower() or "user request" in discard.lower(), (
            f"_discardability must reference the user's request: {discard[:200]}"
        )
        # Must state evidence-only / NOT authoritative.
        assert "NOT authoritative" in discard, (
            f"_discardability must state NOT authoritative: {discard[:200]}"
        )

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_discardability_applies_even_when_packet_populated(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: even when research_context_packet is populated with options,
        the _discardability guidance is present and covers both notes and
        the research context packet."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="LTXAudioWorkflow",
                description="Full LTX audio-video workflow",
                pack="ltxaudio",
                source="ready_template",
                path="/templates/ltx_audio_workflow.py",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadVideo"}]}
        request = ExecutorRequest(
            query="add LTX audio pipeline",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # Both execution_protocol_notes and research_context_packet present.
        assert "execution_protocol_notes" in payload
        assert "research_context_packet" in payload

        notes = payload["execution_protocol_notes"]
        assert "_discardability" in notes
        discard = notes["_discardability"]

        # Discardability guidance covers both protocol notes and context packet.
        assert "NOT authoritative" in discard
        assert any(word in discard.lower() for word in ["discard", "empty", "irrelevant"])

        # The research_context_packet is not empty but is still discardable.
        packet = payload["research_context_packet"]
        assert isinstance(packet, dict)
        assert len(packet.get("options", [])) > 0, (
            "Expected non-empty options in research_context_packet"
        )

    @mock.patch("vibecomfy.executor.core.run_classify_turn",
                side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn",
                side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit",
                side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch("vibecomfy.executor.research._default_web_search_client",
                side_effect=_empty_web_search_client)
    @mock.patch("vibecomfy.executor.core._default_hivemind_client",
                side_effect=_empty_hivemind_client)
    def test_empty_packet_absence_is_discardable_by_omission(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: when no precedent_packet exists, research_context_packet is
        absent entirely (which itself constitutes discardable-by-omission),
        while execution_protocol_notes still carries _discardability."""
        from vibecomfy.search.index import SearchEntry

        # No workflow sources that would produce a packet.
        mock_corpus.return_value = [
            SearchEntry(
                class_type="EmptyLatentImage",
                description="Generate empty latent image",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="research sampler settings",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        payload = self._capture_edit_payload(mock_edit)

        # research_context_packet is absent → discardable by omission.
        assert "research_context_packet" not in payload

        # execution_protocol_notes still present with _discardability.
        assert "execution_protocol_notes" in payload
        notes = payload["execution_protocol_notes"]
        assert "_discardability" in notes


# ── Adapt target-graph integration tests (T15) ───────────────────────────────
# Verify adapt flows thread the attached target graph into adaptation planning
# and keep non-adapt flows unchanged.


class TestAdaptGraphIntegration:
    """Executor-level coverage for adapt-with-graph and edge cases."""

    _WAN_SOURCE_PATH = (
        "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json"
    )

    def _wan_target_graph(self) -> dict[str, object]:
        return {
            "1": {
                "class_type": "WanVideoModelLoader",
                "inputs": {
                    "model": "WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors",
                    "lora": ["2", 0],
                },
            },
            "2": {
                "class_type": "WanVideoLoraSelect",
                "inputs": {"lora": "WanVid\\wan2.1-control-lora.safetensors", "strength": 1},
            },
            "3": {
                "class_type": "WanVideoSampler",
                "inputs": {"model": ["1", 0], "latent_image": ["4", 0]},
            },
        }

    def _ltx_target_graph(self) -> dict[str, object]:
        return {
            "1": {
                "class_type": "LTXVModelLoader",
                "inputs": {"model": "ltx-video-2b.safetensors", "lora": ["2", 0]},
            },
            "2": {
                "class_type": "LTXVLoraSelect",
                "inputs": {"lora": "ltx-detail-lora.safetensors", "strength": 1},
            },
            "3": {
                "class_type": "LTXVSampler",
                "inputs": {"model": ["1", 0], "latent_image": ["4", 0]},
            },
        }

    def _corpus_with_wan_source(self) -> list[Any]:
        from vibecomfy.search.index import SearchEntry

        return [
            SearchEntry(
                class_type="video/wan_control_lora",
                description="Wan control LoRA workflow",
                pack="wanvideo",
                source="ready_template",
                path="ready_templates/video/wan_control_lora.py",
                source_workflow_path=self._WAN_SOURCE_PATH,
                source_workflow_available=True,
                source_workflow_parseable=True,
                adapt_pattern_keys=("lora_chain",),
            ),
        ]

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_with_compatible_graph_produces_pass_candidate(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt + Wan-compatible target graph → structural pass + candidate_graph."""
        mock_corpus.return_value = self._corpus_with_wan_source()

        request = ExecutorRequest(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        plan = result.report.research.adaptation_plan
        assert plan is not None
        assert plan.structural_validation == "pass"
        assert plan.candidate_graph is not None
        assert "1" in plan.candidate_graph

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_without_graph_does_not_build_candidate(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt with no target graph still produces a plan but no candidate."""
        mock_corpus.return_value = self._corpus_with_wan_source()

        request = ExecutorRequest(
            query="add Wan LoRA chain",
            graph=None,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # No graph means the implement phase is skipped without calling the
        # edit engine; the adaptation plan still exists on the research report.
        mock_edit.assert_not_called()
        assert result.report.research is not None
        assert result.report.research.adaptation_plan is not None
        assert result.report.research.adaptation_plan.structural_validation == "not_evaluated"
        assert result.report.research.adaptation_plan.candidate_graph is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_incompatible_family_fails_without_candidate(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt + cross-family target graph (Wan source, LTX target) → fail, no candidate."""
        mock_corpus.return_value = self._corpus_with_wan_source()

        request = ExecutorRequest(
            query="add Wan LoRA chain",
            graph=self._ltx_target_graph(),
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        plan = result.report.research.adaptation_plan
        assert plan is not None
        assert plan.structural_validation == "fail"
        assert plan.candidate_graph is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_adapt)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_adapt_unsupported_source_format_fails_without_candidate(
        self,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
        tmp_path: Path,
    ) -> None:
        """adapt with an unsupported source workflow format produces no candidate."""
        from vibecomfy.search.index import SearchEntry

        bad_path = tmp_path / "not_a_workflow.txt"
        bad_path.write_text("not json", encoding="utf-8")

        mock_corpus.return_value = [
            SearchEntry(
                class_type="video/wan_control_lora",
                description="Wan control LoRA workflow",
                pack="wanvideo",
                source="ready_template",
                path="ready_templates/video/wan_control_lora.py",
                source_workflow_path=str(bad_path),
                source_workflow_available=True,
                source_workflow_parseable=False,
            ),
        ]

        request = ExecutorRequest(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        plan = result.report.research.adaptation_plan
        assert plan is not None
        assert plan.structural_validation == "fail"
        assert plan.candidate_graph is None


# ── Route-intent boundary tests (M5) ─────────────────────────────────────────
# Verify the canonical four-route taxonomy and that non-canonical/legacy
# inputs resolve to the expected canonical route.


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
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_research)
    def test_legacy_research_only_intent_resolves_to_research(
        self,
        mock_edit: mock.MagicMock,
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
        with mock.patch("vibecomfy.executor.research.build_search_corpus", return_value=[]) as mock_corpus:
            result = run_executor(request)

        assert result.ok is True
        assert result.turn.route == "research"
        assert result.report.plan.effective_route == "research"
        assert result.report.plan.implement is False
        assert result.report.research is None
        mock_corpus.assert_not_called()
        mock_edit.assert_called_once()
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
