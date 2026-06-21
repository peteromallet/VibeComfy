"""Executor smoke/regression tests for the full classify → research → implement → reply pipeline.

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
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
)
from vibecomfy.executor import core as executor_core
from vibecomfy.executor.core import run_executor
from vibecomfy.executor.profiles import set_profile_override_dir


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


# ── Fake model backend helpers ───────────────────────────────────────────────


def _fake_classify_respond_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
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
) -> ClassifyDecision:
    """Return a research-only classification (research, no edit)."""
    return ClassifyDecision(
        research=True,
        implement=False,
        reply=True,
        effort="medium",
        plan_summary="research node types",
    )


def _fake_classify_simple_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
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
) -> str:
    """Return a fake reply referencing Hotshot XL research."""
    return "Hotshot XL is an SDXL-based text-to-video model. You can insert it before SVD-XT as a frame generator."


def _fake_reply_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
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
) -> str:
    """Return a graph-describe fake reply."""
    return "I've analyzed your graph and applied the node template. The graph now has a KSampler connected to VAEDecode."


def _fake_handle_agent_edit(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit that returns a successful edit result."""
    input_graph = payload.get("graph", {})
    nodes = input_graph.get("nodes", [])
    edited_nodes = list(nodes) + [{"id": len(nodes) + 1, "type": "KSampler"}]
    return {
        "graph": {"nodes": edited_nodes},
        "message": "Added a KSampler node to the graph.",
    }


def _fake_classify_explain_graph(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
) -> ClassifyDecision:
    """Return an explain-graph classification (implement only, no research)."""
    return ClassifyDecision(
        research=False,
        implement=True,
        reply=True,
        effort="medium",
        plan_summary="explain what the graph does",
        intent="explain_graph",
    )


def _fake_reply_explain_graph(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
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

    Canonical route behavior resolves this shape to inspect: deterministic
    graph inspection/reply only, with no corpus research and no edit.
    """

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_default_profile(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only legacy output resolves to inspect and reply."""
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
        assert "KSampler" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is False
        assert result.to_dict()["route"] == "inspect"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False
        # Canonical inspect behavior does not run corpus research.
        assert result.report.research is None
        mock_corpus.assert_not_called()
        assert result.report.implementation is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_openai_profile(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only legacy output uses inspect behavior with openai profile."""
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
        assert result.to_dict()["route"] == "inspect"
        assert result.report.research is None
        mock_corpus.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_sources_in_result(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
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
        assert payload["route"] == "inspect"
        assert payload["candidate"] is None
        assert payload["apply_eligible"] is False
        assert result.report.research is None
        mock_corpus.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_research_only_empty_corpus(
        self, mock_hivemind, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Inspect behavior succeeds even when the corpus would be empty."""
        mock_corpus.return_value = []

        request = ExecutorRequest(query="nonexistent node", profile="default")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.research is None
        mock_corpus.assert_not_called()
        mock_hivemind.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_hotshot)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_hotshot_xl_query(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """A Hotshot XL research-only classifier output stays inspect-only."""
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
        assert "Hotshot" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is False
        assert result.to_dict()["route"] == "inspect"
        assert result.report.research is None
        mock_corpus.assert_not_called()


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
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_graph_describe_research_failure_non_fatal(
        self, mock_hivemind, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
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
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_research_context_is_forwarded_to_implementation(
        self, mock_hivemind, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research output is available to the edit engine, not only reply."""
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
        assert "LTXRuneXXCustomAudioLipsync" in payload["research_summary"]
        assert source_path in payload["research_summary"]
        assert payload["research_sources"][0]["path"] == source_path
        assert payload["executor_research"]["sources"][0]["source"] == "custom_node_examples"
        reply_kwargs = mock_reply.call_args.kwargs
        assert "LTXRuneXXCustomAudioLipsync" in reply_kwargs["research_summary"]
        assert source_path in reply_kwargs["research_summary"]
        assert reply_kwargs["implementation_message"] == "Added a KSampler node to the graph."


# ── Explain-graph flow tests ─────────────────────────────────────────────────


class TestExplainGraphFlow:
    """Smoke tests for the explain-graph executor flow (implement → reply, no research)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_explain_graph)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_explain_graph)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_explain)
    def test_explain_workflow_query(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Asking 'what does this workflow do?' routes through classify → implement → reply."""
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
        assert result.report.plan.research is False
        assert result.report.plan.implement is True
        assert result.report.plan.intent == "explain_graph"
        assert result.report.research is None
        assert result.report.implementation is not None
        assert "explain" in result.report.implementation.message.lower()
        assert result.graph is not None


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
) -> ClassifyDecision:
    """Return an inspect classification (research only, no implement)."""
    return ClassifyDecision(
        research=True,
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


def _fake_reply_route_gate(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
) -> str:
    """Fake reply for route gate tests."""
    return "Task completed."


class TestRouteGateFlows:
    """Verify that explicit routes invoke only their allowed phases.

    revise:  research ✗  implement ✓  reply ✓
    inspect: research ✓  implement ✗  reply ✓
    clarify:      research ✗  implement ✗  reply ✓
    adapt: research ✓  implement ✓  reply ✓
    """

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
        assert result.report.plan.research is True
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
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_no_route_research_only_resolves_to_inspect_without_research_phase(
        self,
        mock_corpus: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """Without explicit route, research-only resolves to inspect behavior."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit"
        ) as mock_edit:
            request = ExecutorRequest(
                query="what nodes are available?",
                profile="default",
            )
            result = run_executor(request)

        assert result.ok is True
        assert result.to_dict()["route"] == "inspect"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False
        # Canonical inspect behavior uses deterministic graph inspection only.
        mock_corpus.assert_not_called()
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
        assert "Options:\n-" in payload["reply"]
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
    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_route_gate)
    def test_preclassify_forced_clarify_skips_classify_and_implement_provider_calls(
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
        mock_classify.assert_not_called()
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

    def test_preclassify_allows_resolved_option_and_blocks_unresolved_option(self) -> None:
        resolved = executor_core._preclassify_blockers(
            ExecutorRequest(query="option 2", graph={"nodes": [{"id": 1, "type": "KSampler"}]}),
            session_context={
                "prior_clarification": {
                    "clarification_options": ["seed", "steps"],
                },
            },
        )
        assert resolved is None

        unresolved = executor_core._preclassify_blockers(
            ExecutorRequest(query="option 3", graph={"nodes": [{"id": 1, "type": "KSampler"}]}),
            session_context={
                "prior_clarification": {
                    "clarification_options": ["seed", "steps"],
                },
            },
        )
        assert unresolved is not None
        assert unresolved.effective_route == "clarify"
        assert "Unresolved prior option reference" in unresolved.plan_summary

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


class TestPrecedentPayloadIntegrity:
    """Prove precedent route payloads include legacy + structured research data,
    and direct-edit payloads exclude accidental research/precedent context."""

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _capture_edit_payload(mock_edit: mock.MagicMock) -> dict:
        """Return the first positional arg (the payload dict) passed to handle_agent_edit."""
        mock_edit.assert_called_once()
        return mock_edit.call_args[0][0]

    # ── adapt: legacy + structured ──────────────────────────

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
    def test_precedent_route_payload_includes_legacy_research_fields(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: handle_agent_edit receives legacy research_summary,
        research_sources, and executor_research keys."""
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

        # Legacy research fields must be present
        assert "research_summary" in payload
        assert isinstance(payload["research_summary"], str)
        assert len(payload["research_summary"]) > 0
        assert "research_sources" in payload
        assert isinstance(payload["research_sources"], list)
        assert len(payload["research_sources"]) > 0
        assert "executor_research" in payload
        assert isinstance(payload["executor_research"], dict)
        assert "summary" in payload["executor_research"]

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
    def test_precedent_route_payload_includes_structured_adaptation_plan(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: handle_agent_edit receives precedent_slices and
        adaptation_plan keys when a workflow source is available."""
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

        # Structured precedent fields must be present
        assert "precedent_slices" in payload
        assert isinstance(payload["precedent_slices"], list)
        assert len(payload["precedent_slices"]) > 0
        slice0 = payload["precedent_slices"][0]
        assert isinstance(slice0, dict)
        assert slice0.get("source_class_type") == "AudioLipsyncWorkflow"

        assert "adaptation_plan" in payload
        assert isinstance(payload["adaptation_plan"], dict)
        plan = payload["adaptation_plan"]
        assert "selected_slice" in plan
        assert plan["selected_slice"]["source_class_type"] == "AudioLipsyncWorkflow"
        assert "anchor_bindings" in plan
        assert "required_new_nodes" in plan
        assert "required_rewires" in plan
        assert "edit_ops" in plan
        assert "structural_validation" in plan
        assert "semantic_validation" in plan

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
    def test_precedent_route_payload_legacy_fields_present_alongside_structured(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: both legacy research fields AND structured
        adaptation plan coexist in the same payload — one does not replace
        the other."""
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

        # Both legacy and structured must be present simultaneously
        assert "research_summary" in payload
        assert "research_sources" in payload
        assert "executor_research" in payload
        assert "precedent_slices" in payload
        assert "adaptation_plan" in payload

        # Sanity: legacy summary is non-empty
        assert len(payload["research_summary"]) > 0
        # Sanity: structured plan has the expected selected slice
        assert payload["adaptation_plan"]["selected_slice"]["source_class_type"] == "SVDXTWithAudio"

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
    def test_precedent_route_report_reflects_research_with_precedent_data(
        self,
        mock_hivemind: mock.MagicMock,
        mock_web: mock.MagicMock,
        mock_corpus: mock.MagicMock,
        mock_edit: mock.MagicMock,
        mock_reply: mock.MagicMock,
        mock_classify: mock.MagicMock,
        profile_dir: Path,
    ) -> None:
        """adapt: the ExecutorResult report includes research with
        precedent_slices and adaptation_plan in the serialized output."""
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
        assert result.report.research is not None
        assert result.report.implementation is not None

        # Serialize and verify structured fields are in the report
        d = result.to_dict()
        research_report = d["report"]["executor"]["research"]
        assert "precedent_slices" in research_report
        assert isinstance(research_report["precedent_slices"], list)
        assert len(research_report["precedent_slices"]) > 0
        assert "adaptation_plan" in research_report
        assert isinstance(research_report["adaptation_plan"], dict)

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
        legacy research fields are still present but structured precedent
        fields (precedent_slices, adaptation_plan) are absent."""
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

        # Legacy fields still present (research ran)
        assert "research_summary" in payload
        assert "research_sources" in payload
        assert "executor_research" in payload

        # Structured fields absent because no workflow source
        assert "precedent_slices" not in payload
        assert "adaptation_plan" not in payload


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
        precedent_slices and adaptation_plan, which the agent-edit engine uses
        to build the adaptation prompt."""
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

        # Structured fields present for prompt injection
        assert "precedent_slices" in payload
        assert "adaptation_plan" in payload
        # adaptation_plan has required fields for prompt construction
        plan = payload["adaptation_plan"]
        assert "selected_slice" in plan
        assert "anchor_bindings" in plan
        assert "required_new_nodes" in plan
        assert "required_rewires" in plan
        assert "edit_ops" in plan
        assert "structural_validation" in plan
        assert "semantic_validation" in plan

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
