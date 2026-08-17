"""B02 — two-step route tool catalogs + gating (Flash scope).

Proves the exact advertised catalog per route (built via
``tool_catalog_docs(phase=None, allowed_names=effective_route_tools)`` — never
``phase="research"``, so implement-phase tools like ``node_schema`` and the
template tools are advertised on research/adapt), the disabled-by-default
``web_search`` policy, the catalog↔allowlist bijection, and
denial-before-dispatch for every route (a tool outside the effective
allowlist raises typed :class:`BudgetExceeded` before any handler invocation
or budget consumption).
"""

from __future__ import annotations

import re

import pytest

from vibecomfy.executor import two_step as ts
from vibecomfy.executor.tool_specs import AGENT_TOOL_CALL_NAMES, TOOL_SPECS, tool_catalog_docs
from vibecomfy.executor.two_step import (
    BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST,
    BudgetExceeded,
    BudgetUsage,
    MessageBudget,
    TWO_STEP_ROUTE_POLICIES,
    check_before_tool_call,
    check_tool_allowed,
    effective_route_tools,
    route_catalog_docs,
)

ALL_TEN_TOOLS = frozenset(AGENT_TOOL_CALL_NAMES)

# Expected effective (web-denied) tool sets per route — the default catalogs.
EXPECTED_EFFECTIVE_TOOLS: dict[str, frozenset[str]] = {
    "clarify": frozenset(),
    "respond": frozenset(),
    "inspect": frozenset({"node_schema"}),
    "research": frozenset(
        {
            "hivemind_search",
            "hivemind_get",
            "registry_lookup",
            "node_schema",
            "ready_template_list",
            "ready_template_load",
        }
    ),
    "requires_custom_nodes": frozenset({"registry_lookup", "node_schema"}),
    "revise": frozenset(
        {
            "node_schema",
            "ready_template_list",
            "ready_template_load",
            "rank_edit_targets",
            "suggest_seed_nodes",
            "layout_hints",
        }
    ),
    "adapt": ALL_TEN_TOOLS - {"web_search"},
    "reorganise": frozenset({"layout_hints"}),
}


def _advertised_tool_names(catalog: str) -> set[str]:
    """Extract the advertised tool names from a catalog doc string."""
    return set(re.findall(r"^- `([a-z_0-9]+)\(", catalog, flags=re.MULTILINE))


# ── exact advertised catalogs ────────────────────────────────────────────────


class TestExactAdvertisedCatalogs:
    def test_catalog_builder_uses_phase_none_and_effective_allowlist(self) -> None:
        # The tasklist pins the construction: phase=None (never
        # phase="research" — node_schema/templates are implement-phase and
        # would be hidden) + allowed_names=effective_route_tools.
        for route in TWO_STEP_ROUTE_POLICIES:
            expected = tool_catalog_docs(
                phase=None,
                allowed_names=effective_route_tools(route),
            )
            assert route_catalog_docs(route) == expected, route

    def test_effective_tools_match_expected_table(self) -> None:
        for route, expected in EXPECTED_EFFECTIVE_TOOLS.items():
            assert effective_route_tools(route) == expected, route

    def test_catalog_advertises_exactly_the_effective_tools(self) -> None:
        for route in TWO_STEP_ROUTE_POLICIES:
            catalog = route_catalog_docs(route)
            assert _advertised_tool_names(catalog) == set(
                effective_route_tools(route)
            ), route

    def test_research_catalog_keeps_implement_phase_tools(self) -> None:
        # node_schema + template tools are implement-phase (tool_specs.py
        # 760/771); phase="research" would hide them.  The B02 builder must
        # advertise them on the research route.
        catalog = route_catalog_docs("research")
        for tool in ("node_schema", "ready_template_list", "ready_template_load"):
            assert f"- `{tool}(" in catalog, (tool, catalog)
        assert "web_search" not in catalog  # denied by default

    def test_exact_catalog_lines_for_leaf_routes(self) -> None:
        assert route_catalog_docs("clarify") == ""
        assert route_catalog_docs("respond") == ""
        inspect = route_catalog_docs("inspect")
        assert inspect == "- `node_schema(node_class)` — read the runtime/local schema of one node class (availability, inputs, outputs)"
        reorganise = route_catalog_docs("reorganise")
        assert reorganise == "- `layout_hints(operation, anchors)` — suggest placement positions/groups for a node insertion (advisory)"

    def test_catalog_line_order_follows_tool_specs_registry(self) -> None:
        for route in TWO_STEP_ROUTE_POLICIES:
            catalog = route_catalog_docs(route)
            if not catalog:
                continue
            lines = catalog.split("\n")
            advertised = [line.split("(")[0][3:] for line in lines]
            registry_order = [spec.name for spec in TOOL_SPECS]
            positions = [registry_order.index(name) for name in advertised]
            assert positions == sorted(positions), route

    def test_catalog_advertises_only_registered_tools(self) -> None:
        # "Python" is the edit capability, not a registered tool — it must
        # never appear in any advertised catalog.
        for route in TWO_STEP_ROUTE_POLICIES:
            catalog = route_catalog_docs(route)
            for name in _advertised_tool_names(catalog):
                assert name in AGENT_TOOL_CALL_NAMES, (route, name)
            assert "python" not in catalog.lower(), route


# ── disabled web policy ──────────────────────────────────────────────────────


class TestWebSearchPolicy:
    def test_web_search_absent_from_default_catalogs(self) -> None:
        for route in TWO_STEP_ROUTE_POLICIES:
            assert "web_search" not in route_catalog_docs(route), route

    def test_web_search_advertised_when_policy_enables_it(self) -> None:
        # research and adapt list "policy-enabled web" in the route table.
        research = route_catalog_docs("research", web_search_enabled=True)
        assert "web_search" in _advertised_tool_names(research)
        assert "- `web_search(query)`" in research
        adapt = route_catalog_docs("adapt", web_search_enabled=True)
        assert "web_search" in _advertised_tool_names(adapt)

    def test_enabling_is_route_scoped(self) -> None:
        for route in ("clarify", "respond", "inspect", "requires_custom_nodes", "revise", "reorganise"):
            catalog = route_catalog_docs(route, web_search_enabled=True)
            assert "web_search" not in catalog, route

    def test_web_search_capped_at_one_when_enabled(self) -> None:
        assert ts.PER_TOOL_CALL_CAPS["web_search"] == 1
        budget = MessageBudget.for_route("research")
        usage = BudgetUsage(route="research")
        usage = ts.consume_tool_call(budget, usage, "web_search")
        with pytest.raises(BudgetExceeded) as excinfo:
            ts.consume_tool_call(budget, usage, "web_search")
        assert excinfo.value.family == "per_tool_calls"


# ── denial-before-dispatch ───────────────────────────────────────────────────


class TestDenialBeforeDispatch:
    def test_non_advertised_tool_denied_before_dispatch(self) -> None:
        # hivemind_search is not advertised on revise; the gate denies it
        # with the allowlist family before any handler/budget consumption.
        budget = MessageBudget.for_route("revise")
        usage = BudgetUsage(route="revise")
        with pytest.raises(BudgetExceeded) as excinfo:
            check_before_tool_call(budget, usage, "hivemind_search")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST
        assert excinfo.value.route == "revise"
        assert usage.total_tool_calls == 0
        assert usage.output_tokens == 0

    def test_every_route_denies_every_non_effective_tool(self) -> None:
        for route in TWO_STEP_ROUTE_POLICIES:
            budget = MessageBudget.for_route(route)
            usage = BudgetUsage(route=route)
            effective = effective_route_tools(route)
            for tool in sorted(ALL_TEN_TOOLS):
                if tool in effective:
                    continue
                with pytest.raises(BudgetExceeded) as excinfo:
                    check_before_tool_call(budget, usage, tool)
                assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST, (
                    route,
                    tool,
                )

    def test_every_route_admits_every_effective_tool(self) -> None:
        for route in TWO_STEP_ROUTE_POLICIES:
            budget = MessageBudget.for_route(route)
            for tool in effective_route_tools(route):
                # Admission is per-call; the aggregate cap is a separate,
                # stronger gate (e.g. adapt admits 9 tools but caps at 8
                # calls), so use a fresh usage per tool here.
                check_tool_allowed(budget, tool)  # must not raise
                usage = ts.consume_tool_call(budget, BudgetUsage(route=route), tool)

    def test_research_admits_exactly_its_catalog(self) -> None:
        # With web denied, research's six advertised tools pass; the other
        # four registered tools are denied before dispatch.
        budget = MessageBudget.for_route("research")
        usage = BudgetUsage(route="research")
        for tool in ("hivemind_search", "hivemind_get", "registry_lookup", "node_schema", "ready_template_list", "ready_template_load"):
            check_before_tool_call(budget, usage, tool)
        for tool in ("web_search", "rank_edit_targets", "suggest_seed_nodes", "layout_hints"):
            with pytest.raises(BudgetExceeded) as excinfo:
                check_before_tool_call(budget, usage, tool)
            assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST

    def test_aggregate_cap_matches_route_table(self) -> None:
        # research: 8 aggregate calls across its six-tool catalog.
        budget = MessageBudget.for_route("research")
        usage = BudgetUsage(route="research")
        assert budget.max_tool_calls == 8
        # 3 hivemind_search + 4 hivemind_get + 1 registry_lookup = 8.
        for _ in range(3):
            usage = ts.consume_tool_call(budget, usage, "hivemind_search")
        for _ in range(4):
            usage = ts.consume_tool_call(budget, usage, "hivemind_get")
        usage = ts.consume_tool_call(budget, usage, "registry_lookup")
        with pytest.raises(BudgetExceeded) as excinfo:
            ts.consume_tool_call(budget, usage, "registry_lookup")
        assert excinfo.value.family == "route_tool_calls"
        assert excinfo.value.limit == 8
