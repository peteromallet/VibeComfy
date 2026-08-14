"""I01: Wave-A agent tool surface integration.

Covers the ten named agent-invoked tool calls in the batch protocol:

* parse admission (``_parse.py``) — standalone top-level calls only, constant
  args, no nesting/assignments,
* resolve (``_resolve.py``) — typed ``ToolResult`` statements, effort budgets
  (3 searches / 6 fetches / 1 registry batch / ~90s), F01 evidence ledger +
  artifacts on the per-session ``_AgentToolSurface``,
* ledger-only cross-turn memory (``_frag_batch_memory``) — subsequent turns see
  compact ledger entries + evidence IDs, never raw result bodies,
* prompt surface (``provider.build_batch_messages``) — tool calls documented,
  legacy ``research()`` flagged shadow-only (H01),
* one end-to-end batch-REPL run interleaving question -> search -> get ->
  synthesize -> done with budgets and ledger persisting across model turns.
"""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from vibecomfy.comfy_nodes.agent._frag_batch_memory import (
    _batch_research_memory_summary,
)
from vibecomfy.comfy_nodes.agent.provider import build_batch_messages
from vibecomfy.executor.tool_contracts import (
    ToolDiagnostic,
    ToolResult,
    ToolStatus,
)
from vibecomfy.porting.edit._parse import (
    _AGENT_TOOL_CALL_NAMES,
    _parse_and_validate_batch,
)
from vibecomfy.porting.edit._resolve import (
    TOOL_FETCH_BUDGET,
    TOOL_PHASE_DEADLINE_SECONDS,
    TOOL_REGISTRY_BUDGET,
    TOOL_SEARCH_BUDGET,
    _AgentToolSurface,
    _ResolveMixin,
)
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


def _ok_result(
    tool_name: str,
    result: Any = None,
    evidence_ids: tuple[str, ...] = (),
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.OK,
        result=result,
        evidence_ids=tuple(evidence_ids),
    )


def _search_hits(*ids: str) -> ToolResult:
    hits = [
        {
            "evidence_id": evidence_id,
            "title": f"title-{evidence_id}",
            "source_type": "workflow",
            "url": f"https://example.test/{evidence_id}",
            "body": f"RAW BODY {evidence_id}",
        }
        for evidence_id in ids
    ]
    return _ok_result(
        "hivemind_search",
        {"query": "q", "count": len(hits), "hits": hits, "next_cursor": None, "has_more": False},
        ids,
    )


def _resolve(code: str, **attrs: Any) -> Any:
    resolver = _ResolveMixin()
    for key, value in attrs.items():
        setattr(resolver, key, value)
    tree = ast.parse(code)
    assert isinstance(tree.body[0], ast.Expr)
    assert isinstance(tree.body[0].value, ast.Call)
    return resolver._resolve_query_statement(
        statement_index=0,
        source="user",
        call=tree.body[0].value,
        env={},
    )


def _parse(code: str) -> tuple[Any, tuple[Any, ...]]:
    parsed = _parse_and_validate_batch(
        code,
        max_batch_bytes=20_000,
        max_statements=100,
        max_expanded_statements=500,
        max_for_iterations=100,
    )
    return parsed, parsed.diagnostics


# ── Parse admission ──────────────────────────────────────────────────────────


class TestParseToolCalls:
    @pytest.mark.parametrize(
        "code",
        [
            'hivemind_search("wan t2v")',
            'hivemind_get("hivemind:external_resources:1")',
            'registry_lookup("KSampler")',
            'node_schema("KSampler")',
            'ready_template_list("wan")',
            'ready_template_load("video/wan_t2v")',
            'rank_edit_targets("upscale")',
            'suggest_seed_nodes("wan t2v")',
            'layout_hints("insert")',
            'web_search("wan t2v settings", unresolved_question="what seed count?")',
        ],
    )
    def test_tool_call_parses_as_standalone_statement(self, code: str) -> None:
        parsed, diagnostics = _parse(code)
        assert not diagnostics, [d.code for d in diagnostics]
        assert len(parsed.statements) == 1
        assert parsed.statements[0].op_kind == "query"

    def test_all_ten_names_admitted(self) -> None:
        assert _AGENT_TOOL_CALL_NAMES == frozenset(
            {
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
            }
        )

    def test_tool_call_in_assignment_rejected(self) -> None:
        _, diagnostics = _parse('x = hivemind_search("wan")')
        assert [d.code for d in diagnostics] == ["tool_call_not_standalone"]

    def test_nested_tool_call_rejected(self) -> None:
        _, diagnostics = _parse('hivemind_search(str("wan"))')
        assert "nested_call_not_allowed" in [d.code for d in diagnostics]

    def test_non_constant_tool_arg_rejected(self) -> None:
        _, diagnostics = _parse("hivemind_search(query)")
        assert any(d.code == "expression_not_constant" for d in diagnostics)

    def test_kwargs_unpack_rejected(self) -> None:
        _, diagnostics = _parse('hivemind_search("wan", **opts)')
        assert "kwargs_unpack_not_allowed" in [d.code for d in diagnostics]

    def test_clarify_still_rejected_with_extended_message(self) -> None:
        _, diagnostics = _parse('clarify("why?")')
        codes = [d.code for d in diagnostics]
        assert "unsupported_query_call" in codes
        message = next(d.message for d in diagnostics if d.code == "unsupported_query_call")
        assert "hivemind_search" in message


# ── Resolve: hivemind_search / hivemind_get ─────────────────────────────────


class TestResolveHivemindSearch:
    def test_ok_records_ledger_and_artifacts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        calls: list[dict[str, Any]] = []

        def fake_search(query: str, **kwargs: Any) -> ToolResult:
            calls.append({"query": query, **kwargs})
            return _search_hits("hivemind:external_resources:1", "hivemind:external_resources:2")

        monkeypatch.setattr(hivemind_tools, "hivemind_search", fake_search)

        resolver = _ResolveMixin()
        tree = ast.parse('hivemind_search("wan t2v")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )

        assert result.ok is True
        assert result.op_kind == "query"
        assert result.diagnostics == ()
        detail = result.detail
        assert detail["tool_call"] == "hivemind_search"
        assert detail["tool_status"] == "ok"
        assert detail["tool_evidence_ids"] == [
            "hivemind:external_resources:1",
            "hivemind:external_resources:2",
        ]
        # budget consumed: 3 -> 2
        assert detail["tool_budget"]["searches_remaining"] == TOOL_SEARCH_BUDGET - 1
        # digest shows hits + IDs, never the raw body
        assert "title-hivemind:external_resources:1" in detail["query_output"]
        assert "RAW BODY" not in detail["query_output"]
        # ledger entry is compact F01 shape
        entry = detail["ledger_entry"]
        assert entry["decision"] == "hivemind_search query='wan t2v'"
        assert entry["evidence_ids"] == detail["tool_evidence_ids"]
        assert entry["uncertainty"] == ""
        # surface persisted the artifacts behind the evidence IDs
        surface = resolver._agent_tool_surface()  # type: ignore[attr-defined]
        assert len(surface.ledger.entries) == 1
        assert set(surface.artifacts) == {
            "hivemind:external_resources:1",
            "hivemind:external_resources:2",
        }

    def test_budget_shared_with_web_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools
        import vibecomfy.executor.web_tools as web_tools

        monkeypatch.setattr(hivemind_tools, "hivemind_search", lambda query, **kw: _search_hits())
        monkeypatch.setattr(
            web_tools,
            "web_search",
            lambda query, **kw: _ok_result(
                "web_search",
                {"query": query, "count": 1, "results": [{"title": "t", "url": "u", "snippet": "s"}]},
                ("web:abc:00",),
            ),
        )

        resolver = _ResolveMixin()

        def resolve_one(code: str) -> Any:
            tree = ast.parse(code)
            return resolver._resolve_query_statement(
                statement_index=0, source="user", call=tree.body[0].value, env={}
            )

        first = resolve_one('hivemind_search("a")')
        second = resolve_one('web_search("b", unresolved_question="q")')
        assert first.detail["tool_budget"]["searches_remaining"] == TOOL_SEARCH_BUDGET - 1
        assert second.detail["tool_status"] == "ok"
        assert second.detail["tool_budget"]["searches_remaining"] == TOOL_SEARCH_BUDGET - 2

    def test_no_results_typed_and_ledgered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(
            hivemind_tools,
            "hivemind_search",
            lambda query, **kw: ToolResult(
                tool_name="hivemind_search",
                status=ToolStatus.NO_RESULTS,
                result={"query": query, "count": 0, "hits": []},
            ),
        )

        result = _resolve('hivemind_search("nothing")')

        assert result.ok is True
        assert result.detail["tool_status"] == "no_results"
        assert result.detail["ledger_entry"]["conclusion"].startswith("no_results")
        assert result.detail["tool_evidence_ids"] == []


class TestResolveHivemindGet:
    def test_ok_consumes_fetch_and_stores_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        def fake_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            return _ok_result(
                "hivemind_get",
                {
                    "evidence_id": evidence_id,
                    "source_type": "workflow",
                    "table": "external_resources",
                    "row": {"title": "Wan T2V", "url": "https://example.test/1"},
                },
                (evidence_id,),
            )

        monkeypatch.setattr(hivemind_tools, "hivemind_get", fake_get)

        resolver = _ResolveMixin()
        tree = ast.parse('hivemind_get("hivemind:external_resources:1")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )

        assert result.ok is True
        assert result.detail["tool_status"] == "ok"
        assert result.detail["tool_budget"]["fetches_remaining"] == TOOL_FETCH_BUDGET - 1
        assert result.detail["ledger_entry"]["evidence_ids"] == ["hivemind:external_resources:1"]
        surface = resolver._agent_tool_surface()
        assert "hivemind:external_resources:1" in surface.artifacts
        assert surface.artifacts["hivemind:external_resources:1"].kind == "hivemind_record"

    def test_missing_evidence_id_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(hivemind_tools, "hivemind_get", lambda *a, **kw: pytest.fail("must not run"))
        result = _resolve("hivemind_get()")
        assert result.ok is False
        assert "tool_arg_required" in [d.code for d in result.diagnostics]


# ── Resolve: registry / schema / templates ──────────────────────────────────


class TestResolveRegistryLookup:
    def test_one_registry_batch_per_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.lookup_tools as lookup_tools

        calls: list[dict[str, Any]] = []

        def fake_registry(node_class: str, **kwargs: Any) -> ToolResult:
            calls.append({"node_class": node_class, "budget": kwargs.get("budget")})
            return _ok_result(
                "registry_lookup",
                {
                    "node_class": node_class,
                    "exact_ownership": True,
                    "candidates": [
                        {
                            "ref": {"slug": "comfy", "source": "comfy-registry"},
                            "expected_classes": [node_class],
                        }
                    ],
                },
            )

        monkeypatch.setattr(lookup_tools, "registry_lookup", fake_registry)

        resolver = _ResolveMixin()

        def resolve_one(code: str) -> Any:
            tree = ast.parse(code)
            return resolver._resolve_query_statement(
                statement_index=0, source="user", call=tree.body[0].value, env={}
            )

        first = resolve_one('registry_lookup("KSampler")')
        second = resolve_one('registry_lookup("KSampler")')

        assert first.ok is True
        assert first.detail["tool_status"] == "ok"
        assert first.detail["tool_budget"]["registry_remaining"] == TOOL_REGISTRY_BUDGET - 1
        assert "exact ownership True" in first.detail["query_output"]
        assert len(calls) == 1
        # the one-shot registry budget object was handed to the tool
        assert calls[0]["budget"] is not None

        assert second.ok is True
        assert second.detail["tool_status"] == "refused"
        assert second.detail["tool_code"] == "tool_registry_budget_exhausted"
        assert second.diagnostics == ()
        assert len(calls) == 1  # tool never invoked past the budget

    def test_budget_payload_refused_by_tool_when_exhausted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.lookup_tools as lookup_tools

        monkeypatch.setattr(
            lookup_tools,
            "registry_lookup",
            lambda node_class, **kw: ToolResult(
                tool_name="registry_lookup",
                status=ToolStatus.REFUSED,
                diagnostics=(ToolDiagnostic(code="registry_budget_exhausted", message="spent"),),
            ),
        )
        result = _resolve('registry_lookup("KSampler")')
        assert result.detail["tool_status"] == "refused"
        assert result.detail["tool_code"] == "registry_budget_exhausted"


class TestResolveNodeSchema:
    def test_passes_session_schema_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.lookup_tools as lookup_tools

        calls: list[dict[str, Any]] = []
        provider = object()

        def fake_node_schema(node_class: str, **kwargs: Any) -> ToolResult:
            calls.append({"node_class": node_class, "provider": kwargs.get("provider")})
            return _ok_result(
                "node_schema",
                {
                    "class_type": node_class,
                    "available": True,
                    "input_names": ["seed"],
                    "outputs": [{"type": "LATENT"}],
                },
            )

        monkeypatch.setattr(lookup_tools, "node_schema", fake_node_schema)
        resolver = _ResolveMixin()
        resolver.schema_provider = provider
        tree = ast.parse('node_schema("KSampler")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )

        assert result.detail["tool_status"] == "ok"
        assert calls[0]["provider"] is provider
        assert result.detail["tool_budget"]["fetches_remaining"] == TOOL_FETCH_BUDGET - 1


class TestResolveReadyTemplates:
    def test_load_is_fetch_budgeted_and_content_not_echoed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.lookup_tools as lookup_tools

        def fake_load(template_id: str, **kwargs: Any) -> ToolResult:
            return _ok_result(
                "ready_template_load",
                {
                    "id": template_id,
                    "path": "video/wan_t2v.py",
                    "scope": "repo",
                    "sha256": "abc123",
                    "size_bytes": 100,
                    "content": ("SECRET TEMPLATE BODY " * 300) + "TAIL-SENTINEL-MARKER",
                    "content_truncated": False,
                },
            )

        monkeypatch.setattr(lookup_tools, "ready_template_load", fake_load)

        resolver = _ResolveMixin()
        tree = ast.parse('ready_template_load("video/wan_t2v")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )

        assert result.ok is True
        assert result.detail["tool_status"] == "ok"
        assert result.detail["tool_budget"]["fetches_remaining"] == TOOL_FETCH_BUDGET - 1
        # the current-turn digest carries only a bounded excerpt; the tail of
        # the raw body never enters the prompt
        assert "content excerpt" in result.detail["query_output"]
        assert "TAIL-SENTINEL-MARKER" not in result.detail["query_output"]
        # the FULL raw body is stored behind the evidence ID, never echoed
        surface = resolver._agent_tool_surface()
        artifact = surface.artifacts["tool:ready_template_load-video-wan_t2v"]
        assert "TAIL-SENTINEL-MARKER" in artifact.body["content"]
        # ledger conclusion is the compact identity
        assert "sha256=abc123" in result.detail["ledger_entry"]["conclusion"]

    def test_list_is_free_and_inventory_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.lookup_tools as lookup_tools

        def fake_list(capability: str | None = None, **kwargs: Any) -> ToolResult:
            return _ok_result(
                "ready_template_list",
                {
                    "filter": capability,
                    "count": 2,
                    "templates": [
                        {"id": "video/wan_t2v", "path": "video/wan_t2v.py"},
                        {"id": "video/ltx", "path": "video/ltx.py"},
                    ],
                },
            )

        monkeypatch.setattr(lookup_tools, "ready_template_list", fake_list)

        result = _resolve('ready_template_list("wan")')

        assert result.detail["tool_status"] == "ok"
        assert result.detail["tool_budget"]["searches_remaining"] == TOOL_SEARCH_BUDGET
        assert result.detail["tool_budget"]["fetches_remaining"] == TOOL_FETCH_BUDGET
        assert "video/wan_t2v" in result.detail["query_output"]


# ── Resolve: advisory tools (free, explicit, deadline-gated) ────────────────


class TestResolveAdvisoryTools:
    @pytest.mark.parametrize(
        ("code", "tool_name", "kwargs_expected"),
        [
            ("rank_edit_targets(\"upscale\")", "rank_edit_targets", {"explicit": True}),
            ("suggest_seed_nodes(\"wan t2v\")", "suggest_seed_nodes", {"explicit": True}),
            ("layout_hints(\"insert\")", "layout_hints", {}),
        ],
    )
    def test_advisory_tools_are_free_and_explicit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        code: str,
        tool_name: str,
        kwargs_expected: Mapping[str, Any],
    ) -> None:
        import vibecomfy.executor.edit_suggestion_tools as suggestion_tools
        import vibecomfy.executor.layout_hints as layout_hints_module

        calls: list[dict[str, Any]] = []

        def fake_rank(graph: Any, intent: str, **kwargs: Any) -> ToolResult:
            calls.append({"tool": "rank_edit_targets", "kwargs": kwargs})
            return _ok_result(
                "rank_edit_targets",
                {"case": "no-candidate", "intent": intent, "candidates": []},
            )

        def fake_seed(intent: str, constraints: Any = None, **kwargs: Any) -> ToolResult:
            calls.append({"tool": "suggest_seed_nodes", "kwargs": kwargs})
            return _ok_result(
                "suggest_seed_nodes",
                {"case": "no-candidate", "intent": intent, "suggestions": []},
            )

        def fake_layout(graph: Any, operation: str, **kwargs: Any) -> ToolResult:
            calls.append({"tool": "layout_hints", "kwargs": kwargs})
            return _ok_result(
                "layout_hints",
                {"operation": operation, "candidates": []},
            )

        monkeypatch.setattr(suggestion_tools, "rank_edit_targets", fake_rank)
        monkeypatch.setattr(suggestion_tools, "suggest_seed_nodes", fake_seed)
        monkeypatch.setattr(layout_hints_module, "layout_hints_tool", fake_layout)

        result = _resolve(code)

        assert result.detail["tool_status"] == "ok"
        budget = result.detail["tool_budget"]
        assert budget["searches_remaining"] == TOOL_SEARCH_BUDGET
        assert budget["fetches_remaining"] == TOOL_FETCH_BUDGET
        assert budget["registry_remaining"] == TOOL_REGISTRY_BUDGET
        assert len(calls) == 1
        for key, value in kwargs_expected.items():
            assert calls[0]["kwargs"].get(key) is value

    def test_deadline_gates_free_tools_too(self) -> None:
        resolver = _ResolveMixin()
        surface = _AgentToolSurface(deadline=time.monotonic() - 1)
        resolver._tool_surface = surface
        tree = ast.parse('rank_edit_targets("upscale")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )
        assert result.detail["tool_status"] == "refused"
        assert result.detail["tool_code"] == "tool_deadline_exceeded"


# ── Resolve: budgets, typed refusals, evidence preservation ─────────────────


class TestEffortBudgets:
    def test_search_budget_exhaustion_is_typed_and_preserves_evidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(hivemind_tools, "hivemind_search", lambda query, **kw: _search_hits())
        resolver = _ResolveMixin()

        def resolve_one(code: str) -> Any:
            tree = ast.parse(code)
            return resolver._resolve_query_statement(
                statement_index=0, source="user", call=tree.body[0].value, env={}
            )

        for index in range(TOOL_SEARCH_BUDGET):
            result = resolve_one(f'hivemind_search("q{index}")')
            assert result.detail["tool_status"] == "ok"

        refused = resolve_one('hivemind_search("q-too-many")')

        assert refused.ok is True  # a refusal is feedback, not a failed turn
        assert refused.diagnostics == ()
        assert refused.detail["tool_status"] == "refused"
        assert refused.detail["tool_code"] == "tool_search_budget_exhausted"
        assert refused.detail["tool_budget"]["searches_remaining"] == 0
        # gathered evidence is preserved
        assert refused.detail["tool_budget"]["ledger_entries"] == TOOL_SEARCH_BUDGET
        assert "Gathered evidence is preserved" in refused.detail["query_output"]
        surface = resolver._agent_tool_surface()
        assert len(surface.ledger.entries) == TOOL_SEARCH_BUDGET

    def test_fetch_budget_exhaustion_typed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        def fake_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            return _ok_result(
                "hivemind_get",
                {"evidence_id": evidence_id, "source_type": "workflow", "row": {}},
                (evidence_id,),
            )

        monkeypatch.setattr(hivemind_tools, "hivemind_get", fake_get)
        resolver = _ResolveMixin()

        def resolve_one(code: str) -> Any:
            tree = ast.parse(code)
            return resolver._resolve_query_statement(
                statement_index=0, source="user", call=tree.body[0].value, env={}
            )

        for index in range(TOOL_FETCH_BUDGET):
            result = resolve_one(f'hivemind_get("hivemind:external_resources:{index}")')
            assert result.detail["tool_status"] == "ok"

        refused = resolve_one('hivemind_get("hivemind:external_resources:99")')
        assert refused.detail["tool_status"] == "refused"
        assert refused.detail["tool_code"] == "tool_fetch_budget_exhausted"
        assert refused.detail["tool_budget"]["fetches_remaining"] == 0
        assert refused.detail["tool_budget"]["ledger_entries"] == TOOL_FETCH_BUDGET

    def test_deadline_exhaustion_typed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(hivemind_tools, "hivemind_search", lambda query, **kw: _search_hits())
        resolver = _ResolveMixin()
        resolver._tool_surface = _AgentToolSurface(deadline=time.monotonic() - 1)
        tree = ast.parse('hivemind_search("late")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )
        assert result.detail["tool_status"] == "refused"
        assert result.detail["tool_code"] == "tool_deadline_exceeded"
        assert result.ok is True
        assert result.diagnostics == ()

    def test_phase_deadline_default_is_about_ninety_seconds(self) -> None:
        assert TOOL_PHASE_DEADLINE_SECONDS == 90.0

    def test_shape_validation_errors_are_typed(self) -> None:
        assert _resolve('hivemind_search("a", bogus=1)').ok is False
        codes = [d.code for d in _resolve('hivemind_search("a", bogus=1)').diagnostics]
        assert "tool_unknown_keyword" in codes
        assert "tool_too_many_args" in [
            d.code for d in _resolve('hivemind_search("a", "b")').diagnostics
        ]
        assert "tool_arg_duplicated" in [
            d.code for d in _resolve('hivemind_get("x", evidence_id="y")').diagnostics
        ]

    def test_transport_states_stay_typed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(
            hivemind_tools,
            "hivemind_search",
            lambda query, **kw: ToolResult(
                tool_name="hivemind_search",
                status=ToolStatus.RATE_LIMITED,
                retry_after_seconds=3.5,
                diagnostics=(ToolDiagnostic(code="hivemind_rate_limited", message="cooldown"),),
            ),
        )
        result = _resolve('hivemind_search("retry-me")')
        assert result.detail["tool_status"] == "rate_limited"
        assert "retry_after=3.5" in result.detail["query_output"]
        assert result.detail["ledger_entry"]["conclusion"].startswith("rate_limited")


# ── Resolve: web_search policy ───────────────────────────────────────────────


class TestResolveWebSearch:
    def test_enabled_by_default_and_requires_unresolved_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vibecomfy.executor.web_tools as web_tools

        calls: list[dict[str, Any]] = []

        def fake_web(query: str, **kwargs: Any) -> ToolResult:
            calls.append({"query": query, **kwargs})
            return _ok_result(
                "web_search",
                {"query": query, "count": 1, "results": [{"title": "t", "url": "u", "snippet": "s"}]},
                ("web:abc:00",),
            )

        monkeypatch.setattr(web_tools, "web_search", fake_web)

        result = _resolve('web_search("wan settings", unresolved_question="what step count?")')

        assert result.detail["tool_status"] == "ok"
        assert calls[0]["enabled"] is True
        assert calls[0]["unresolved_question"] == "what step count?"
        assert result.detail["tool_budget"]["searches_remaining"] == TOOL_SEARCH_BUDGET - 1

    def test_policy_disabled_returns_typed_refusal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vibecomfy.executor.web_tools as web_tools

        monkeypatch.setattr(
            web_tools,
            "web_search",
            lambda query, **kw: ToolResult(
                tool_name="web_search",
                status=ToolStatus.REFUSED,
                diagnostics=(ToolDiagnostic(code="web_search_disabled", message="disabled"),),
            ),
        )
        resolver = _ResolveMixin()
        resolver.web_search_enabled = False
        tree = ast.parse('web_search("q", unresolved_question="u")')
        result = resolver._resolve_query_statement(
            statement_index=0, source="user", call=tree.body[0].value, env={}
        )
        assert result.detail["tool_status"] == "refused"
        assert result.detail["tool_code"] == "web_search_disabled"


# ── Ledger-only cross-turn memory ────────────────────────────────────────────


class TestLedgerOnlyMemory:
    def _state_with_tool_turn(self) -> SimpleNamespace:
        return SimpleNamespace(
            batch_turns=[
                {
                    "turn_number": 0,
                    "statements": [
                        {
                            "detail": {
                                "tool_call": "hivemind_search",
                                "tool_status": "ok",
                                "ledger_entry": {
                                    "decision": "hivemind_search query='wan t2v'",
                                    "conclusion": "2 hit(s): Wan T2V workflow | Wan 2.2 guide",
                                    "evidence_ids": [
                                        "hivemind:external_resources:1",
                                        "hivemind:external_resources:2",
                                    ],
                                    "uncertainty": "",
                                },
                                "query_output": (
                                    "hivemind_search(query='wan t2v') — ok: 2 hit(s)\n"
                                    "  hit 1: Wan T2V workflow [hivemind:external_resources:1] "
                                    "https://example.test/1\n"
                                    "  hit 2: Wan 2.2 guide [hivemind:external_resources:2]\n"
                                ),
                            }
                        }
                    ],
                }
            ],
            executor_research_brief=None,
        )

    def test_memory_renders_entries_and_ids_only(self) -> None:
        state = self._state_with_tool_turn()
        summary = _batch_research_memory_summary(state)

        assert "Tool evidence ledger" in summary
        assert "hivemind:external_resources:1" in summary
        assert "hivemind:external_resources:2" in summary
        # raw bodies / digest lines never cross turns
        assert "hit 1:" not in summary
        assert "https://example.test/1" not in summary
        assert "RAW BODY" not in summary

    def test_memory_empty_without_tool_turns(self) -> None:
        state = SimpleNamespace(
            batch_turns=[{"turn_number": 0, "statements": [{"detail": {"query": "search"}}]}],
            executor_research_brief=None,
        )
        assert _batch_research_memory_summary(state) == ""

    def test_refusal_never_repeated_as_ledger_record(self) -> None:
        state = SimpleNamespace(
            batch_turns=[
                {
                    "turn_number": 1,
                    "statements": [
                        {
                            "detail": {
                                "tool_call": "hivemind_search",
                                "tool_status": "refused",
                                "tool_code": "tool_search_budget_exhausted",
                                "ledger_entry": None,
                                "tool_budget": {"searches_remaining": 0},
                            }
                        }
                    ],
                }
            ],
            executor_research_brief=None,
        )
        summary = _batch_research_memory_summary(state)
        assert "Tool evidence ledger" not in summary


# ── Prompt surface (provider.build_batch_messages) ───────────────────────────


class TestPromptSurface:
    def test_system_prompt_documents_tools_and_legacy_research(self) -> None:
        messages = build_batch_messages(task="research", python_source="x = LoadImage()")
        system = messages[0]["content"]

        assert "hivemind_search" in system
        assert "hivemind_get" in system
        assert "registry_lookup" in system
        assert "node_schema" in system
        assert "ready_template_list" in system
        assert "ready_template_load" in system
        assert "rank_edit_targets" in system
        assert "suggest_seed_nodes" in system
        assert "layout_hints" in system
        assert "web_search" in system
        assert "LEGACY shadow-only" in system
        assert "3 searches" in system
        assert "6 fetches" in system
        assert "1 registry lookup" in system
        assert "evidence IDs" in system
        # pinned legacy behavior stays documented
        assert 'research("query words", sources=' in system
        assert "if sources are omitted" in system
        assert "internal workflows/templates only" in system

    def test_research_only_prompt_mentions_tools(self) -> None:
        messages = build_batch_messages(
            task="question", python_source="", research_only=True, max_batches=4, budget_remaining=4
        )
        system = messages[0]["content"]
        assert "hivemind_search" in system
        assert "LEGACY shadow-only" in system
        assert "Gather auditable evidence" in system

    def test_evidence_ledger_block_rendered_in_user_message(self) -> None:
        ledger = (
            "- hivemind_search query='wan t2v' (ok) — 2 hit(s) — "
            "evidence: hivemind:external_resources:1"
        )
        messages = build_batch_messages(
            task="continue",
            turn_number=1,
            python_source="",
            evidence_ledger=ledger,
        )
        user = messages[1]["content"]
        assert "Tool evidence ledger (compact" in user
        assert "hivemind:external_resources:1" in user

    def test_evidence_ledger_block_omitted_when_empty(self) -> None:
        messages = build_batch_messages(task="continue", turn_number=1, python_source="")
        assert "Tool evidence ledger" not in messages[1]["content"]


# ── End-to-end batch-REPL interleave ─────────────────────────────────────────


def _ui_graph() -> dict:
    return {
        "id": "713b5d5c-87f4-51b6-921a-a9acfa74e43c",
        "version": 1.0,
        "last_node_id": 2,
        "last_link_id": 1,
        "groups": [],
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "pos": [0.0, 0.0],
                "size": [320.0, 52.0],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [
                    {"name": "image", "type": "IMAGE", "links": [1], "slot_index": 0}
                ],
                "properties": {
                    "vibecomfy_id": "LoadImage_0",
                    "Node name for S&R": "LoadImage",
                    "_vibecomfy_schema_provider": "test",
                    "vibecomfy_uid": "1",
                },
                "widgets_values": ["input.png"],
            },
            {
                "id": 2,
                "type": "SaveImage",
                "pos": [0.0, 0.0],
                "size": [320.0, 52.0],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                "outputs": [],
                "properties": {
                    "vibecomfy_id": "SaveImage_1",
                    "Node name for S&R": "SaveImage",
                    "_vibecomfy_schema_provider": "test",
                    "vibecomfy_uid": "2",
                },
                "widgets_values": ["before"],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        "extra": {"vibecomfy": {"layout": {"nodes": {}}, "groups": []}},
    }


def _test_provider() -> Any:
    class _Provider:
        def __init__(self, schemas: Mapping[str, NodeSchema]) -> None:
            self._schemas = dict(schemas)

        def get_schema(self, class_type: str) -> NodeSchema | None:
            return self._schemas.get(class_type)

        def schemas(self) -> dict[str, NodeSchema]:
            return dict(self._schemas)

    return _Provider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={},
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


class TestEndToEndInterleave:
    def test_question_search_get_synthesize_done(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit

        # hermetic narrator (G0): every final message routes through the LLM
        # narrator; an empty JSON payload makes it fall back to deterministic
        # prose.
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: {"json": {}},
        )

        import vibecomfy.executor.hivemind_tools as hivemind_tools

        def fake_search(query: str, **kwargs: Any) -> ToolResult:
            return _ok_result(
                "hivemind_search",
                {
                    "query": query,
                    "count": 1,
                    "hits": [
                        {
                            "evidence_id": "hivemind:external_resources:1",
                            "title": "Wan T2V workflow",
                            "source_type": "workflow",
                            "url": "https://example.test/1",
                            "body": "RAW BODY SENTINEL search",
                        }
                    ],
                    "next_cursor": None,
                    "has_more": False,
                },
                ("hivemind:external_resources:1",),
            )

        def fake_get(evidence_id: str, **kwargs: Any) -> ToolResult:
            return _ok_result(
                "hivemind_get",
                {
                    "evidence_id": evidence_id,
                    "source_type": "workflow",
                    "table": "external_resources",
                    "row": {
                        "title": "Wan T2V workflow",
                        "url": "https://example.test/1",
                        "body": "RAW BODY SENTINEL get",
                    },
                },
                (evidence_id,),
            )

        monkeypatch.setattr(hivemind_tools, "hivemind_search", fake_search)
        monkeypatch.setattr(hivemind_tools, "hivemind_get", fake_get)

        turn = {"n": 0}

        def client(messages: list[dict[str, str]]) -> dict[str, str]:
            turn["n"] += 1
            system = messages[0]["content"]
            user = messages[1]["content"]
            if turn["n"] == 1:
                assert "hivemind_search" in system
                assert "LEGACY shadow-only" in system
                return {"message": "Searching.", "batch": 'hivemind_search("wan t2v")'}
            if turn["n"] == 2:
                # the prior turn's tool output crosses turns as ledger entries
                # + evidence IDs only — never raw bodies
                assert "Tool evidence ledger" in user, user[-600:]
                assert "hivemind:external_resources:1" in user
                assert "RAW BODY SENTINEL search" not in user
                return {
                    "message": "Fetching the record.",
                    "batch": 'hivemind_get("hivemind:external_resources:1")',
                }
            assert "hivemind:external_resources:1" in user
            return {"message": "Enough evidence; done.", "batch": "done()"}

        result = handle_agent_edit(
            {
                "graph": _ui_graph(),
                "workflow_id": "713b5d5c-87f4-51b6-921a-a9acfa74e43c",
                "task": "research wan t2v then finish",
                "session_id": "i01-e2e-interleave",
            },
            schema_provider=_test_provider(),
            deepseek_client=client,
            session_root=tmp_path,
        )

        assert result["ok"] is True
        assert result["internal_outcome"]["kind"] in {"noop", "candidate"}
        # budgets persisted across turns: search consumed once, fetch once.
        # turns: 0 search, 1 get, 2/3 done() refused by the no-op confirmation
        # gate (total_landed == 0), 4 done() accepted.
        turns = result.get("batch_turns") or []
        assert len(turns) == 5, [t.get("turn_number") for t in turns]
        assert [t["batch"] for t in turns][2:] == ["done()", "done()", "done()"]
        tool_details = [
            (t["turn_number"], s["detail"]["tool_call"], s["detail"]["tool_status"])
            for t in turns
            for s in t.get("statements", [])
            if s.get("detail", {}).get("tool_call")
        ]
        assert tool_details == [
            (0, "hivemind_search", "ok"),
            (1, "hivemind_get", "ok"),
        ]
        budgets = [
            s["detail"]["tool_budget"]
            for t in turns
            for s in t.get("statements", [])
            if s.get("detail", {}).get("tool_call")
        ]
        assert budgets[0]["searches_remaining"] == TOOL_SEARCH_BUDGET - 1
        assert budgets[1]["searches_remaining"] == TOOL_SEARCH_BUDGET - 1  # not reset
        assert budgets[1]["fetches_remaining"] == TOOL_FETCH_BUDGET - 1
