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
from vibecomfy.executor.tool_specs import PHASE_THREADED
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
    def test_disabled_by_default_and_requires_unresolved_question(
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

        # A06: web search is opt-in — a missing session flag defaults to
        # DISABLED, never to enabled. The tool module receives enabled=False
        # and decides the typed refusal.
        assert result.detail["tool_status"] == "ok"
        assert calls[0]["enabled"] is False
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
    def test_implement_prompt_documents_only_implement_tools(self) -> None:
        messages = build_batch_messages(task="research", python_source="x = LoadImage()")
        system = messages[0]["content"]

        # C01: the implement prompt documents ONLY the implement-phase tools.
        assert "node_schema" in system
        assert "ready_template_list" in system
        assert "ready_template_load" in system
        assert "rank_edit_targets" in system
        assert "suggest_seed_nodes" in system
        assert "layout_hints" in system
        # The research-phase tools are strictly partitioned out of implement.
        assert "hivemind_search" not in system
        assert "hivemind_get" not in system
        assert "registry_lookup" not in system
        assert "web_search" not in system
        assert "6 fetches" in system
        assert "evidence IDs" in system
        # research() is removed: prompts no longer advertise the legacy
        # statement or its sources= surface.
        assert "research(" not in system
        assert "LEGACY shadow-only" not in system
        assert "if sources are omitted" not in system
        assert "internal workflows/templates only" not in system

    def test_research_only_prompt_documents_only_research_tools(self) -> None:
        messages = build_batch_messages(
            task="question", python_source="", research_only=True, max_batches=4, budget_remaining=4
        )
        system = messages[0]["content"]
        # C01: the research-only prompt documents the research-phase tools.
        assert "hivemind_search" in system
        assert "hivemind_get" in system
        assert "registry_lookup" in system
        assert "web_search" in system
        assert "Gather auditable evidence" in system
        # Implement-phase tools are not advertised on the research route.
        assert "node_schema" not in system
        assert "rank_edit_targets" not in system
        # the research-only prompt no longer documents the removed research()
        assert "research(" not in system
        assert "LEGACY shadow-only" not in system

    def test_threaded_prompt_composes_both_tool_partitions(self) -> None:
        messages = build_batch_messages(
            task="research then edit",
            python_source="x = LoadImage()",
            tool_phase=PHASE_THREADED,
        )
        system = messages[0]["content"]

        assert "threaded research+implement surface" in system
        assert "hivemind_search" in system
        assert "hivemind_get" in system
        assert "node_schema" in system
        assert "ready_template_load" in system
        assert "this same durable conversation may gather" in system
        assert "implement phase has NO external research/search tools" not in system
        assert "3 searches, 6 fetches, 1 registry lookup" in system

    def test_research_only_prompt_grounds_claims_in_workflow_facts(self) -> None:
        """Research-route answers must cite node ids/link ids/exact widget
        keys+values from the provided workflow, never invent parameters, and
        explicitly flag zero on-topic evidence (REC-C grounding rule)."""
        messages = build_batch_messages(
            task="question", python_source="", research_only=True, max_batches=4, budget_remaining=4
        )
        system = messages[0]["content"]
        assert "Ground every claim you make" in system
        assert "cite the node ids, link ids, and exact widget keys/values" in system
        assert "link 35" in system
        assert "connects node 5027 to node 4852" in system
        assert "IPAdapterApply widgets are only" in system
        assert "Never invent parameters, connections, or settings absent" in system
        assert "zero on-topic evidence" in system
        assert "do not present off-topic records as findings" in system
        assert "answer from the workflow facts you can see" in system

    def test_implement_prompt_question_mode_grounds_in_render(self) -> None:
        """Question/explanation mode in the implement prompt must ground claims
        in the visible render's node ids/link ids/widget keys+values (REC-C
        grounding rule)."""
        messages = build_batch_messages(task="what does this do?", python_source="x=1")
        system = messages[0]["content"]
        assert "Question / explanation mode" in system
        assert "ground every claim in the visible render's node ids" in system
        assert "never invent parameters or connections" in system

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


class TestR2AgentTrustPromptSurface:
    """R2 agent-trust contracts: phase-truthful prompts, advisory hints,
    honest research budgets, and per-turn budget visibility."""

    def test_implement_prompt_is_phase_truthful_about_ledger(self) -> None:
        """The implement phase has no research tools, so the ledger must be
        described as already resolved — IDs are provenance, not handles."""
        ledger = "- hivemind_search query='wan t2v' (ok) — 2 hit(s) — evidence: hivemind:external_resources:1"
        messages = build_batch_messages(
            task="adapt",
            turn_number=1,
            python_source="",
            evidence_ledger=ledger,
        )
        all_text = messages[0]["content"] + "\n" + messages[1]["content"]
        # Never instruct the implement agent to resolve IDs with a research
        # tool it does not have.
        assert "resolve IDs with hivemind_get" not in all_text
        assert "already resolved" in all_text
        assert "provenance labels" in all_text
        assert "not callable handles" in all_text

    def test_implement_prompt_labels_advisory_hints_and_drops_rank_fork(self) -> None:
        system = build_batch_messages(task="adapt", python_source="x = LoadImage()")[0]["content"]
        # rank/suggest are lossy advisory hints, never an override.
        assert "lossy advisory hints" in system
        assert "never override your judgment" in system
        # The forced 'use rank_edit_targets or clarify' fork is removed.
        assert "use `rank_edit_targets`" not in system
        assert "or `clarify()` instead of splicing" not in system
        # Downstream acceptance is stated before done().
        assert "state downstream acceptance explicitly" in system
        assert "deterministic validation owns that" in system
        assert "queue blockers" in system

    def test_research_digest_shows_remaining_budget_each_turn(self) -> None:
        from vibecomfy.executor.agent_research_stage import build_evidence_digest

        digest = build_evidence_digest(
            question="q",
            tool_calls=[],
            artifacts={},
            searches_left=2,
            fetches_left=5,
            registry_left=1,
            turns_left=12,
            seconds_left=200,
        )
        assert "Remaining budget:" in digest
        assert "2 search(es)" in digest
        assert "5 fetch(es)" in digest
        assert "1 registry lookup(s)" in digest
        assert "12 turn(s)" in digest
        assert "~200s" in digest
        # No counters supplied -> compact digest unchanged (no budget line).
        plain = build_evidence_digest(question="q", tool_calls=[], artifacts={})
        assert "Remaining budget:" not in plain

    def test_research_prompt_carries_full_brief_and_consumer_contract(self) -> None:
        from vibecomfy.executor.agent_research_stage import build_agent_research_messages

        messages = build_agent_research_messages(
            question="Which node chain produces audio-conditioned Wan video?",
            evidence_digest="(no tool evidence gathered yet)",
            route="adapt",
            research_brief=(
                "Research brief:\n"
                "- Search directions (try each that may apply):\n"
                "  1. Wan 2.1 t2v steps\n"
                "  2. Wan 2.2 i2v quality\n"
                "- Avoid: generic searches"
            ),
        )
        all_text = " ".join(str(message["content"]) for message in messages)
        assert "Research brief:" in all_text
        assert "Wan 2.1 t2v steps" in all_text
        assert "Wan 2.2 i2v quality" in all_text
        assert "Avoid: generic searches" in all_text
        # Consumer contract: the implement agent consumes the synthesis.
        assert "IMPLEMENT agent turns your synthesis" in all_text
        assert "fetch every Hivemind record" in all_text
        # Honest budgets in the research-stage prompt.
        assert "16 decision turns" in all_text
        assert "~240s" in all_text

    def test_research_stage_budgets_are_honest(self) -> None:
        from vibecomfy.executor import agent_research_stage as stage

        assert stage.TOOL_PHASE_DEADLINE_SECONDS == 240.0
        assert stage._MAX_TURNS == 16

    def test_research_deadline_enforced_after_provider_call(self) -> None:
        """A slow provider decision turn cannot slip past the deadline and
        still execute a tool call."""
        from vibecomfy.executor import agent_research_stage as stage

        calls: dict[str, int] = {"judge": 0, "tool": 0}
        clock = {"t": 100.0}

        def fake_judge(
            question: str, digest: str, messages: list[dict[str, Any]] | None = None
        ) -> dict[str, Any]:
            calls["judge"] += 1
            clock["t"] += 200.0  # the provider call burns the whole budget
            return {"action": "call", "tool": "hivemind_search", "args": {"query": question}}

        def fake_tool(tool: str, args: Mapping[str, Any], **kwargs: Any) -> ToolResult:
            calls["tool"] += 1
            return _ok_result("hivemind_search", {"count": 0, "hits": []}, ())

        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question="q",
            judge_fn=fake_judge,
            tool_fn=fake_tool,
            search_fn=lambda query, **kw: _ok_result(
                "hivemind_search", {"count": 0, "hits": []}, ()
            ),
            get_fn=lambda evidence_id, **kw: _ok_result(
                "hivemind_get", {"row": {"title": "t"}}, ()
            ),
            now_fn=lambda: clock["t"],
            deadline_seconds=150.0,
            max_turns=10,
        )
        assert calls["judge"] == 1
        assert calls["tool"] == 0, "deadline must stop before executing the tool call"
        assert any("after the decision turn" in warning for warning in trace.warnings)

    def test_research_deadline_enforced_after_tool_call(self) -> None:
        """A slow tool execution cannot silently overrun the budget; the
        call's evidence is still preserved in the trace."""
        from vibecomfy.executor import agent_research_stage as stage

        calls: dict[str, int] = {"judge": 0, "tool": 0}
        clock = {"t": 100.0}

        def fake_judge(
            question: str, digest: str, messages: list[dict[str, Any]] | None = None
        ) -> dict[str, Any]:
            calls["judge"] += 1
            return {"action": "call", "tool": "hivemind_search", "args": {"query": question}}

        def fake_tool(tool: str, args: Mapping[str, Any], **kwargs: Any) -> ToolResult:
            calls["tool"] += 1
            clock["t"] += 200.0  # the tool call burns the whole budget
            return _ok_result("hivemind_search", {"count": 0, "hits": []}, ())

        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question="q",
            judge_fn=fake_judge,
            tool_fn=fake_tool,
            search_fn=lambda query, **kw: _ok_result(
                "hivemind_search", {"count": 0, "hits": []}, ()
            ),
            get_fn=lambda evidence_id, **kw: _ok_result(
                "hivemind_get", {"row": {"title": "t"}}, ()
            ),
            now_fn=lambda: clock["t"],
            deadline_seconds=150.0,
            max_turns=10,
        )
        assert calls["tool"] == 1
        assert any("after the tool call" in warning for warning in trace.warnings)
        # The executed call is preserved in the trace even though the loop stopped.
        assert len(trace.iterations) == 1

    @pytest.mark.parametrize("declared", [None, 99.0])
    def test_hivemind_timeout_is_clamped_to_stage_time_remaining(
        self, declared: float | None
    ) -> None:
        from vibecomfy.executor import agent_research_stage as stage

        clock = {"t": 100.0}
        seen: list[dict[str, Any]] = []

        def fake_judge(
            question: str, digest: str, messages: list[dict[str, Any]] | None = None
        ) -> dict[str, Any]:
            clock["t"] = 108.0
            args: dict[str, Any] = {"query": question}
            if declared is not None:
                args["timeout"] = declared
            return {"action": "call", "tool": "hivemind_search", "args": args}

        def fake_tool(tool: str, args: Mapping[str, Any], **kwargs: Any) -> ToolResult:
            seen.append(dict(args))
            clock["t"] = 111.0
            return _search_hits("hivemind:external_resources:1")

        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question="q",
            judge_fn=fake_judge,
            tool_fn=fake_tool,
            now_fn=lambda: clock["t"],
            deadline_seconds=10.0,
            max_turns=2,
        )
        assert 0 < seen[0]["timeout"] <= 2.0
        assert trace.status == "exhausted"
        assert len(trace.iterations) == 1
        assert trace.iterations[0].tool_calls[0]["status"] == "ok"

    def test_declared_hivemind_timeout_is_unchanged_with_ample_budget(self) -> None:
        from vibecomfy.executor import agent_research_stage as stage

        clock = {"t": 100.0}
        seen: list[dict[str, Any]] = []

        def fake_judge(
            question: str, digest: str, messages: list[dict[str, Any]] | None = None
        ) -> dict[str, Any]:
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": question, "timeout": 3},
            }

        def fake_tool(tool: str, args: Mapping[str, Any], **kwargs: Any) -> ToolResult:
            seen.append(dict(args))
            clock["t"] = 200.0
            return _ok_result("hivemind_search", {"count": 0, "hits": []}, ())

        stage.run_agent_research_stage(
            route="research",
            question="q",
            judge_fn=fake_judge,
            tool_fn=fake_tool,
            now_fn=lambda: clock["t"],
            deadline_seconds=50.0,
            max_turns=2,
        )
        assert seen[0]["timeout"] == 3

    def test_malformed_hivemind_timeout_reaches_typed_validation(self) -> None:
        from vibecomfy.executor import agent_research_stage as stage

        calls = {"n": 0}

        def fake_judge(
            question: str, digest: str, messages: list[dict[str, Any]] | None = None
        ) -> dict[str, Any]:
            calls["n"] += 1
            if calls["n"] == 1:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": question, "timeout": "bad"},
                }
            return {
                "action": "finish",
                "conclusion": "typed invalid request observed",
                "evidence_ids": [],
                "uncertainty": "invalid timeout",
            }

        trace, _pack = stage.run_agent_research_stage(
            route="research",
            question="q",
            judge_fn=fake_judge,
            deadline_seconds=30.0,
            max_turns=2,
        )
        call = trace.iterations[0].tool_calls[0]
        assert call["status"] == "invalid_request"
        assert "timeout" in call["conclusion"]


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
                # research() is removed; the research-phase prompt documents
                # only the named tool calls, never the legacy statement.
                assert "LEGACY shadow-only" not in system
                assert "research(" not in system
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
                # C01: search/get are research-phase tools. The implement
                # phase is strictly partitioned (no hivemind tools); this
                # flow is a research-phase batch session.
                "route": "research",
                "executor_route": "research",
            },
            schema_provider=_test_provider(),
            deepseek_client=client,
            session_root=tmp_path,
        )

        assert result["ok"] is True
        assert result["internal_outcome"]["kind"] in {"noop", "candidate"}
        # budgets persisted across turns: search consumed once, fetch once.
        # research-only phase: 0 search, 1 get, 2 done() accepted (no no-op
        # confirmation gate on the research route).
        turns = result.get("batch_turns") or []
        assert len(turns) == 3, [t.get("turn_number") for t in turns]
        assert [t["batch"] for t in turns] == [
            'hivemind_search("wan t2v")',
            'hivemind_get("hivemind:external_resources:1")',
            "done()",
        ]
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

    def test_live_threaded_executor_researches_then_edits_in_one_durable_host(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
        from vibecomfy.executor import core
        from vibecomfy.executor.contracts import ExecutorHostPorts, ExecutorRequest

        monkeypatch.setattr(
            core,
            "run_classify_turn",
            lambda *args, **kwargs: pytest.fail("threaded mode must never classify"),
        )
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: {"json": {}},
        )

        import vibecomfy.executor.hivemind_tools as hivemind_tools

        monkeypatch.setattr(
            hivemind_tools,
            "hivemind_search",
            lambda query, **kwargs: _search_hits("hivemind:external_resources:threaded"),
        )

        observed_prompts: list[str] = []

        def client(messages: list[dict[str, str]]) -> dict[str, str]:
            system = messages[0]["content"]
            user = messages[1]["content"]
            observed_prompts.append(system)
            if len(observed_prompts) == 1:
                assert "threaded research+implement surface" in system
                assert "hivemind_search" in system
                assert "node_schema" in system
                return {
                    "message": "Checking precedent.",
                    "batch": 'hivemind_search("save prefix convention")',
                }
            assert "Tool evidence ledger" in user
            assert "hivemind:external_resources:threaded" in user
            return {
                "message": "The researched prefix edit is ready.",
                "batch": 'saveimage.filename_prefix = "after"\ndone()',
            }

        def live_edit(payload: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
            assert payload["pipeline_mode"] == "threaded"
            return handle_agent_edit(
                payload,
                schema_provider=_test_provider(),
                deepseek_client=client,
                session_root=tmp_path,
                **kwargs,
            )

        failure = SimpleNamespace(
            kind=SimpleNamespace(value="ValidationError"),
            user_facing_message="failed",
        )
        ports = ExecutorHostPorts(
            handle_agent_edit=live_edit,
            payload_hash=lambda payload: "stable-request-hash",
            classify_failure=lambda *args, **kwargs: failure,
            failure_envelope=lambda *args, **kwargs: failure,
            begin_deepseek_usage_capture=lambda: object(),
            snapshot_deepseek_usage_capture=lambda: ({}, False),
            end_deepseek_usage_capture=lambda token: None,
            begin_model_attempt_capture=lambda: object(),
            snapshot_model_attempt_capture=lambda: (),
            end_model_attempt_capture=lambda token: None,
        )

        result = core.run_executor(
            ExecutorRequest(
                query="research precedent, then rename the save prefix",
                graph=_ui_graph(),
                workflow_id="713b5d5c-87f4-51b6-921a-a9acfa74e43c",
                session_id="threaded-live-e2e",
                pipeline_mode="threaded",
                max_batches=4,
            ),
            host_ports=ports,
        )

        assert result.ok is True
        assert result.graph is not None
        assert len(observed_prompts) == 2
        assert result.report is not None
        implementation = result.report.implementation
        assert implementation is not None
        durable = implementation.durable_response
        assert durable is not None
        assert durable["session_id"] == "threaded-live-e2e"
        assert durable["turn_id"]
        turns = durable["batch_turns"]
        assert [turn["batch"] for turn in turns] == [
            'hivemind_search("save prefix convention")',
            'saveimage.filename_prefix = "after"\ndone()',
        ]
        first_detail = turns[0]["statements"][0]["detail"]
        assert first_detail["tool_status"] == "ok"
        assert first_detail["tool_budget"]["searches_remaining"] == TOOL_SEARCH_BUDGET - 1
        assert durable["accepted_batch"]
