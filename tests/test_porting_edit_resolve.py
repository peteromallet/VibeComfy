"""Tests for the batch-REPL query-statement resolver (vibecomfy/porting/edit/_resolve.py).

Proves the Wave D fail-closed contract:
- ``research(...)`` is an unconditional typed refusal (``research_query_failed``)
  naming the ten agent-owned tool statements; no legacy argument/source
  machinery remains and no structured research detail is attached;
- the refusal is identical whether ``sources=`` is omitted, empty, or
  explicit, and regardless of ``research_only`` or a classify brief;
- the B03 research fold helpers still merge collected research state;
- named tool calls (e.g. ``hivemind_search``) resolve normally and are not
  flagged as legacy shadow.
"""
from __future__ import annotations

from typing import Any

from vibecomfy.porting.edit._resolve import (
    _ResolveMixin,
)


# ── _resolve_query_statement research statement (Wave D fail-closed) ─────────


class TestResolveResearchStatementSources:
    """research() fails closed: the deterministic engine was deleted (Wave D).

    The statement is an unconditional typed refusal — no argument validation
    and no source normalization runs.  Any call, well-formed or not, returns
    ``ok=False`` with a ``research_query_failed`` diagnostic that names the
    ten agent-owned tool statements as the replacement surface.
    """

    def _resolve(self, code: str):
        import ast

        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.Expr)
        assert isinstance(tree.body[0].value, ast.Call)

        resolver = _ResolveMixin()
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )
        return result

    def test_research_statement_fails_closed_with_tool_guidance(self) -> None:
        result = self._resolve('research("Hotshot XL ComfyUI 16 frames")')

        assert result.ok is False
        assert result.op_kind == "query"
        codes = [d.code for d in result.diagnostics]
        assert codes == ["research_query_failed"]
        message = result.diagnostics[0].message
        assert "no longer supported" in message
        for tool in (
            "hivemind_search",
            "hivemind_get",
            "registry_lookup",
            "node_schema",
            "ready_template_list",
            "ready_template_load",
            "rank_edit_targets",
            "suggest_seed_nodes",
            "layout_hints",
            "web_search",
        ):
            assert tool in message

    def test_detail_carries_research_query_only(self) -> None:
        result = self._resolve('research("Hotshot XL ComfyUI 16 frames")')

        # The old structured fields (research_sources / research_summary /
        # community_summary / evidence_card / legacy_shadow_only) are gone;
        # the fail-closed detail carries just query + research_query.
        assert dict(result.detail) == {
            "query": "research",
            "research_query": "Hotshot XL ComfyUI 16 frames",
        }

    def test_invalid_explicit_sources_still_fail_closed(self) -> None:
        result = self._resolve('research("q", sources=["bogus"])')

        # No source machinery remains: invalid explicit sources do not get
        # their own diagnostic — the statement fails closed unconditionally.
        assert result.ok is False
        codes = [d.code for d in result.diagnostics]
        assert codes == ["research_query_failed"]
        assert "unsupported_research_source" not in codes
        assert result.detail["research_query"] == "q"

    def test_messages_web_sources_still_fail_closed(self) -> None:
        result = self._resolve(
            'research("MiniMax H3", sources=["messages", "web"])'
        )

        # Valid explicit sources no longer resolve to clients/tiers — the
        # statement fails closed with the query carried in detail.
        assert result.ok is False
        codes = [d.code for d in result.diagnostics]
        assert "research_query_failed" in codes
        assert result.detail["research_query"] == "MiniMax H3"

    def test_research_only_flag_does_not_resurrect_engine(self) -> None:
        import ast

        tree = ast.parse('research("Hotshot XL")')
        resolver = _ResolveMixin()
        resolver.research_only = True
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )

        assert result.ok is False
        codes = [d.code for d in result.diagnostics]
        assert "research_query_failed" in codes
        assert "legacy_shadow_only" not in result.detail
        assert "research_sources" not in result.detail


# ── research() fail-closed across the old omit/source surface (B03) ──────────


class TestResolveResearchOmitDefault:
    """The old omit-default / source-union semantics are dead with the engine.

    The statement fails closed identically whether sources= is omitted,
    empty, or explicit, and regardless of ``research_only`` or the classify
    brief — the ten named tool statements are the only research surface.
    """

    def _resolve(
        self,
        code: str,
        *,
        research_only: bool = False,
        brief: dict[str, Any] | None = None,
    ):
        import ast

        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.Expr)
        assert isinstance(tree.body[0].value, ast.Call)

        resolver = _ResolveMixin()
        resolver.research_only = research_only
        if brief is not None:
            resolver.executor_research_brief = brief
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )
        return result

    def test_resolve_omitted_sources_research_only_defaults_to_fail_closed(
        self,
    ) -> None:
        result = self._resolve(
            'research("MiniMax H3")', research_only=True
        )

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]
        assert result.detail["research_query"] == "MiniMax H3"

    def test_resolve_empty_sources_list_is_omit_not_no_tiers(self) -> None:
        result = self._resolve(
            'research("LTX 2.5", sources=[])', research_only=True
        )

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]
        assert result.detail["research_query"] == "LTX 2.5"

    def test_resolve_omitted_sources_adapt_defaults_to_fail_closed(self) -> None:
        result = self._resolve('research("Hotshot XL ComfyUI 16 frames")')

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]

    def test_resolve_omitted_sources_ignores_distilled_faster_brief_workflows(
        self,
    ) -> None:
        # Brief source_preferences were prompt-visible only; they no longer
        # influence any resolution because the statement fails closed.
        brief = {
            "source_preferences": ["workflows", "messages", "web"],
            "research_goal": "Find distilled or faster ways to run the workflow.",
        }
        result = self._resolve(
            'research("distilled faster")', research_only=True, brief=brief
        )

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]

    def test_resolve_explicit_web_sources_not_unioned_with_messages(self) -> None:
        result = self._resolve(
            'research("Hotshot XL", sources=["web"])', research_only=True
        )

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]

    def test_resolve_explicit_workflows_not_unioned_with_messages(self) -> None:
        result = self._resolve(
            'research("KSampler", sources=["workflows"])', research_only=True
        )

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]

    def test_resolve_messages_and_workflows_sets_no_clients(self) -> None:
        result = self._resolve(
            'research("MiniMax H3", sources=["messages", "workflows"])',
            research_only=True,
        )

        assert result.ok is False
        assert [d.code for d in result.diagnostics] == ["research_query_failed"]
        assert result.detail["research_query"] == "MiniMax H3"

    def test_resolve_attaches_no_structured_detail_fields(self) -> None:
        result = self._resolve('research("MiniMax H3")', research_only=True)

        assert result.ok is False
        # The structured research detail (community_summary / research_summary /
        # research_result_sources / evidence_card) is never attached.
        assert "community_summary" not in result.detail
        assert "research_summary" not in result.detail
        assert "research_result_sources" not in result.detail
        assert "evidence_card" not in result.detail
        assert dict(result.detail) == {
            "query": "research",
            "research_query": "MiniMax H3",
        }

def _message_source(
    index: int,
    *,
    author: str = "alice",
    channel: str = "ltx_chatter",
) -> dict[str, Any]:
    return {
        "source": "hivemind_message",
        "class_type": f"LTX 2.5 message {index}",
        "author": author,
        "channel": channel,
        "hivemind_id": str(index),
        "description": f"community message body {index}",
        "kind": "message",
    }


# ── B03 research fold helpers (edit_batch_repl.py) ───────────────────────────


class TestFoldResearchStatement:
    def test_fold_research_statement_unions_sources_by_id(self) -> None:
        from types import SimpleNamespace

        from vibecomfy.comfy_nodes.agent.edit_batch_repl import (
            _dedupe_sources_by_id,
            _fold_research_statement,
        )

        first = {
            "research_result_sources": [
                _message_source(1, author="alice"),
                _message_source(2, author="bob"),
            ],
            "community_summary": "first paragraph",
            "research_summary": "first summary",
        }
        second = {
            "research_result_sources": [
                _message_source(1, author="alice2"),  # same id → first-seen wins
                _message_source(3, author="carol"),
            ],
            "community_summary": "second paragraph",
            "research_summary": "second summary",
        }

        state = SimpleNamespace(
            collected_research_sources=(),
            collected_community_summary="",
            collected_research_summary="",
        )
        _fold_research_statement(state, first)
        _fold_research_statement(state, second)

        sources = state.collected_research_sources
        assert len(sources) == 3
        assert [s["hivemind_id"] for s in sources] == ["1", "2", "3"]
        # first-seen wins on sources
        assert sources[0]["author"] == "alice"
        # last-write-wins on paragraphs
        assert state.collected_community_summary == "second paragraph"
        assert state.collected_research_summary == "second summary"

    def test_dedupe_sources_by_id_keeps_first_seen(self) -> None:
        from vibecomfy.comfy_nodes.agent.edit_batch_repl import _dedupe_sources_by_id

        merged = _dedupe_sources_by_id(
            (_message_source(1, author="alice"),),
            (_message_source(1, author="alice2"), _message_source(4, author="dana")),
        )

        assert len(merged) == 2
        assert merged[0]["author"] == "alice"
        assert merged[1]["author"] == "dana"

    def test_fold_ignores_statements_without_research_fields(self) -> None:
        from types import SimpleNamespace

        from vibecomfy.comfy_nodes.agent.edit_batch_repl import _fold_research_statement

        state = SimpleNamespace(
            collected_research_sources=(),
            collected_community_summary="",
            collected_research_summary="",
        )
        _fold_research_statement(state, {"query": "search", "query_output": "No node signature found"})

        assert state.collected_research_sources == ()
        assert state.collected_community_summary == ""
        assert state.collected_research_summary == ""


# ── I01: legacy research() shadow flag ─────────────────────────────────────────


class TestLegacyResearchShadowFlag:
    """research() is legacy and fails closed; the named tool calls are the
    canonical evidence surface (I01/H01)."""

    def _resolve_research(self, code: str):
        import ast

        tree = ast.parse(code)
        resolver = _ResolveMixin()
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )
        return result

    def test_research_statement_fails_closed_with_guidance(self) -> None:
        result = self._resolve_research('research("wan t2v")')

        # The shadow-only flag is moot: the statement always fails closed with
        # guidance to the named tool statements instead of returning output.
        assert result.ok is False
        codes = [d.code for d in result.diagnostics]
        assert codes == ["research_query_failed"]
        message = result.diagnostics[0].message
        assert "hivemind_search" in message
        assert "web_search" in message
        assert result.detail["research_query"] == "wan t2v"
        assert "legacy_shadow_only" not in result.detail

    def test_tool_calls_are_not_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ast

        import vibecomfy.executor.hivemind_tools as hivemind_tools
        from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

        monkeypatch.setattr(
            hivemind_tools,
            "hivemind_search",
            lambda query, **kw: ToolResult(
                tool_name="hivemind_search",
                status=ToolStatus.NO_RESULTS,
                result={"query": query, "count": 0, "hits": []},
            ),
        )
        tree = ast.parse('hivemind_search("wan t2v")')
        resolver = _ResolveMixin()
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )
        assert result.ok is True
        assert result.detail["tool_call"] == "hivemind_search"
        assert "legacy_shadow_only" not in result.detail

