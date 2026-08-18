"""B02 — two-step route policy + per-message budget primitives (Flash scope).

Covers the authoritative route table (exact route coverage vs the full-mode
``_ROUTE_BEHAVIORS`` authority), the exact frozen per-tool caps, exact route
allowlists, effective route tools (web_search denied by default), and every
per-message budget family: allowlist denial-before-dispatch, aggregate
tool-call caps, per-tool caps, aggregate output-token exhaustion, wall clock,
apply/replacement counters — each raising the typed :class:`BudgetExceeded`
with the canonical family/limit/used/route payload.  Also covers the frozen
:class:`SessionBudget` type (ceilings, per-family exhaustion primitives,
remaining output cap, dict round-trip) that the cumulative-session plumbing
wires in; cumulative-session *enforcement* cases are appended by the B02 Pro
scope below the marker at the end of this file.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from vibecomfy.executor import two_step as ts
from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
from vibecomfy.executor.two_step import (
    BUDGET_FAMILY_APPLY_BATCHES,
    BUDGET_FAMILY_OUTPUT_TOKENS,
    BUDGET_FAMILY_PER_TOOL_CALLS,
    BUDGET_FAMILY_REPLACEMENT_ATTEMPTS,
    BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST,
    BUDGET_FAMILY_ROUTE_TOOL_CALLS,
    BUDGET_FAMILY_SESSION_APPLY_BATCHES,
    BUDGET_FAMILY_SESSION_MODEL_CONTINUATIONS,
    BUDGET_FAMILY_SESSION_OUTPUT_TOKENS,
    BUDGET_FAMILY_SESSION_REPLACEMENT_ATTEMPTS,
    BUDGET_FAMILY_SESSION_TOOL_CALLS,
    BUDGET_FAMILY_SESSION_USER_MESSAGES,
    BUDGET_FAMILY_SESSION_WALL_CLOCK,
    BUDGET_FAMILY_WALL_CLOCK,
    BudgetExceeded,
    BudgetUsage,
    MessageBudget,
    SessionBudget,
    TWO_STEP_ROUTE_POLICIES,
    check_before_tool_call,
    check_tool_allowed,
    check_wall_clock,
    consume_apply_batch,
    consume_output_tokens,
    consume_replacement_attempt,
    consume_tool_call,
    effective_route_tools,
)

ALL_TEN_TOOLS = frozenset(
    {
        "hivemind_search",
        "hivemind_get",
        "registry_lookup",
        "web_search",
        "node_schema",
        "ready_template_list",
        "ready_template_load",
        "rank_edit_targets",
        "suggest_seed_nodes",
        "layout_hints",
    }
)

# Exact route table per the frozen tasklist (B02 #2).
EXPECTED_ROUTE_TABLE: dict[str, dict[str, object]] = {
    "clarify": {
        "allowed_tools": frozenset(),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
        "effort": "low",
    },
    "respond": {
        "allowed_tools": frozenset(),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
        "effort": "low",
    },
    "inspect": {
        "allowed_tools": frozenset({"node_schema"}),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
        "effort": "low",
    },
    "research": {
        "allowed_tools": frozenset(
            {
                "hivemind_search",
                "hivemind_get",
                "registry_lookup",
                "node_schema",
                "ready_template_list",
                "ready_template_load",
                "web_search",
            }
        ),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
        "effort": "medium",
    },
    "requires_custom_nodes": {
        "allowed_tools": frozenset({"registry_lookup", "node_schema"}),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
        "effort": "medium",
    },
    "revise": {
        "allowed_tools": frozenset(
            {
                "node_schema",
                "ready_template_list",
                "ready_template_load",
                "rank_edit_targets",
                "suggest_seed_nodes",
                "layout_hints",
            }
        ),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": True,
        "max_apply_batches": 1,
        "max_replacements": 1,
        "effort": "medium",
    },
    "adapt": {
        "allowed_tools": ALL_TEN_TOOLS,
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": True,
        "max_apply_batches": 1,
        "max_replacements": 1,
        "effort": "high",
    },
    "reorganise": {
        "allowed_tools": frozenset({"layout_hints"}),
        "max_output_tokens": 1_000_000,
        "max_tool_calls": 200,
        "max_wall_clock_seconds": 1200.0,
        "allows_python_edits": True,
        "max_apply_batches": 1,
        "max_replacements": 1,
        "effort": "medium",
    },
}


# ── route coverage (exact, vs the full-mode authority) ───────────────────────


class TestRouteCoverage:
    def test_route_policies_cover_full_mode_authority_exactly(self) -> None:
        ts.assert_route_policy_coverage()

    def test_route_keys_match_route_behaviors(self) -> None:
        from vibecomfy.executor.core import _ROUTE_BEHAVIORS  # the authority

        assert set(TWO_STEP_ROUTE_POLICIES) == set(_ROUTE_BEHAVIORS)
        assert set(TWO_STEP_ROUTE_POLICIES) == {
            "clarify",
            "respond",
            "inspect",
            "research",
            "requires_custom_nodes",
            "revise",
            "adapt",
            "reorganise",
        }

    def test_entrypoint_runs_coverage_assertion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom() -> None:
            raise AssertionError("route policy coverage must run on execution")

        monkeypatch.setattr(ts, "assert_route_policy_coverage", boom)
        with pytest.raises(AssertionError, match="route policy coverage"):
            ts._run_two_step(
                ExecutorRequest(query="x"),
                plan=ClassifyDecision.edit(route="adapt", plan_summary="s"),
                pipeline_mode="two_step",
                executor_id="e",
            )

    def test_route_table_is_exactly_the_frozen_tasklist(self) -> None:
        assert set(TWO_STEP_ROUTE_POLICIES) == set(EXPECTED_ROUTE_TABLE)
        for route, expected in EXPECTED_ROUTE_TABLE.items():
            policy = TWO_STEP_ROUTE_POLICIES[route]
            for field_name, value in expected.items():
                assert getattr(policy, field_name) == value, (
                    f"route {route!r} field {field_name!r}"
                )

    def test_route_table_is_immutable(self) -> None:
        with pytest.raises(TypeError):
            TWO_STEP_ROUTE_POLICIES["adapt"] = TWO_STEP_ROUTE_POLICIES["adapt"]  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            TWO_STEP_ROUTE_POLICIES["adapt"].max_output_tokens = 1  # type: ignore[misc]


# ── per-tool caps (exact, frozen) ────────────────────────────────────────────


class TestPerToolCaps:
    def test_exact_frozen_table(self) -> None:
        assert dict(ts.PER_TOOL_CALL_CAPS) == {
            "hivemind_search": 1000,
            "hivemind_get": 1000,
            "registry_lookup": 1000,
            "node_schema": 1000,
            "ready_template_list": 1000,
            "ready_template_load": 1000,
            "rank_edit_targets": 1000,
            "suggest_seed_nodes": 1000,
            "layout_hints": 1000,
            "web_search": 1000,
        }

    def test_covers_every_registered_agent_tool(self) -> None:
        from vibecomfy.executor.tool_specs import AGENT_TOOL_CALL_NAMES

        assert set(ts.PER_TOOL_CALL_CAPS) == set(AGENT_TOOL_CALL_NAMES)

    def test_caps_are_immutable(self) -> None:
        with pytest.raises(TypeError):
            ts.PER_TOOL_CALL_CAPS["hivemind_search"] = 99  # type: ignore[index]


# ── effective route tools (web policy) ───────────────────────────────────────


class TestEffectiveRouteTools:
    def test_web_search_denied_by_default_everywhere(self) -> None:
        for route in TWO_STEP_ROUTE_POLICIES:
            assert "web_search" not in effective_route_tools(route), route

    def test_web_search_enabled_only_where_policy_lists_it(self) -> None:
        # research and adapt list "policy-enabled web" in the route table.
        assert "web_search" in effective_route_tools("research", web_search_enabled=True)
        assert "web_search" in effective_route_tools("adapt", web_search_enabled=True)
        # No other route gains web_search even when "enabled" — the route
        # table is authoritative; enabling is policy-scoped, not global.
        for route in ("clarify", "respond", "inspect", "requires_custom_nodes", "revise", "reorganise"):
            assert "web_search" not in effective_route_tools(
                route, web_search_enabled=True
            ), route

    def test_effective_tools_are_registered_only(self) -> None:
        from vibecomfy.executor.tool_specs import AGENT_TOOL_CALL_NAMES

        for route in TWO_STEP_ROUTE_POLICIES:
            for tool in effective_route_tools(route, web_search_enabled=True):
                assert tool in AGENT_TOOL_CALL_NAMES, (route, tool)

    def test_unknown_route_is_typed_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown two-step route"):
            effective_route_tools("bogus_route")


# ── denial-before-dispatch ───────────────────────────────────────────────────


class TestDenialBeforeDispatch:
    def test_allowlist_denial_raises_before_consuming_anything(self) -> None:
        budget = MessageBudget.for_route("revise")
        usage = BudgetUsage(route="revise")
        with pytest.raises(BudgetExceeded) as excinfo:
            check_tool_allowed(budget, "hivemind_search")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST
        assert excinfo.value.limit == 0
        assert excinfo.value.used == 0
        assert excinfo.value.route == "revise"
        # Denial consumed nothing.
        assert usage.total_tool_calls == 0
        assert usage.output_tokens == 0
        assert usage.tool_call_counts == {}

    def test_allowlist_denial_fires_before_call_caps(self) -> None:
        # Even with call caps exhausted, the allowlist gate fires first: the
        # route deny-list is checked before any budget consumption/accounting.
        budget = MessageBudget.for_route("revise")
        usage = replace(
            BudgetUsage(route="revise"),
            total_tool_calls=99,
            tool_call_counts={"node_schema": 99},
        )
        with pytest.raises(BudgetExceeded) as excinfo:
            check_before_tool_call(budget, usage, "hivemind_get")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST

    def test_clarify_denies_every_tool(self) -> None:
        budget = MessageBudget.for_route("clarify")
        usage = BudgetUsage(route="clarify")
        for tool in ALL_TEN_TOOLS:
            with pytest.raises(BudgetExceeded) as excinfo:
                check_before_tool_call(budget, usage, tool)
            assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST

    def test_respond_denies_every_tool(self) -> None:
        budget = MessageBudget.for_route("respond")
        usage = BudgetUsage(route="respond")
        for tool in ALL_TEN_TOOLS:
            with pytest.raises(BudgetExceeded) as excinfo:
                check_before_tool_call(budget, usage, tool)
            assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST

    def test_route_allowlist_is_an_exact_bijection(self) -> None:
        # A tool is allowed iff it is on the route's effective allowlist.
        for route, expected in EXPECTED_ROUTE_TABLE.items():
            budget = MessageBudget.for_route(route)
            usage = BudgetUsage(route=route)
            expected_tools = frozenset(expected["allowed_tools"]) - {"web_search"}
            for tool in ALL_TEN_TOOLS:
                if tool in expected_tools:
                    check_tool_allowed(budget, tool)  # must not raise
                else:
                    with pytest.raises(BudgetExceeded) as excinfo:
                        check_tool_allowed(budget, tool)
                    assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST


# ── per-message budget families ──────────────────────────────────────────────


class TestToolCallCaps:
    def test_per_tool_cap_is_effectively_unbounded(self) -> None:
        # Per-tool caps (1000) exceed every route's aggregate gate (200), so
        # the aggregate cap always fires first: per-tool exhaustion is
        # dominated, not a separate failure mode (user ruling 2026-08-18).
        budget = MessageBudget.for_route("research")
        assert budget.per_tool_caps["hivemind_search"] == 1000
        usage = BudgetUsage(route="research")
        for _ in range(200):
            usage = consume_tool_call(budget, usage, "hivemind_search")
        assert usage.tool_call_counts["hivemind_search"] == 200
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_tool_call(budget, usage, "hivemind_search")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_CALLS
        assert excinfo.value.limit == 200

    def test_aggregate_route_cap_exhaustion(self) -> None:
        budget = MessageBudget.for_route("research")  # 200 aggregate calls
        usage = BudgetUsage(route="research")
        # Hit the aggregate cap exactly (200 calls across tools).
        for _ in range(200):
            usage = consume_tool_call(budget, usage, "hivemind_search")
        assert usage.total_tool_calls == 200
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_tool_call(budget, usage, "registry_lookup")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_CALLS
        assert excinfo.value.limit == 200
        assert excinfo.value.used == 200

    def test_clarify_denies_all_tools(self) -> None:
        budget = MessageBudget.for_route("clarify")
        usage = BudgetUsage(route="clarify")
        # The allowlist gate fires first: clarify admits no tools.
        with pytest.raises(BudgetExceeded) as excinfo:
            check_before_tool_call(budget, usage, "node_schema")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST


class TestAggregateOutputTokens:
    @pytest.mark.parametrize(
        "route, ceiling",
        [
            ("clarify", 1_000_000),
            ("respond", 1_000_000),
            ("inspect", 1_000_000),
            ("research", 1_000_000),
            ("requires_custom_nodes", 1_000_000),
            ("revise", 1_000_000),
            ("adapt", 1_000_000),
            ("reorganise", 1_000_000),
        ],
    )
    def test_exact_route_slices(self, route: str, ceiling: int) -> None:
        assert MessageBudget.for_route(route).max_output_tokens == ceiling

    def test_exhaustion_at_slice_boundary(self) -> None:
        budget = MessageBudget.for_route("research")  # 1_000_000
        usage = BudgetUsage(route="research")
        usage = consume_output_tokens(budget, usage, 999_999)
        usage = consume_output_tokens(budget, usage, 1)  # exactly 1_000_000: allowed
        assert usage.output_tokens == 1_000_000
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_output_tokens(budget, usage, 1)
        assert excinfo.value.family == BUDGET_FAMILY_OUTPUT_TOKENS
        assert excinfo.value.limit == 1_000_000
        assert excinfo.value.used == 1_000_001
        assert excinfo.value.route == "research"

    def test_single_call_cannot_overshoot_slice(self) -> None:
        budget = MessageBudget.for_route("inspect")  # 1_000_000
        usage = BudgetUsage(route="inspect")
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_output_tokens(budget, usage, 1_000_001)
        assert excinfo.value.family == BUDGET_FAMILY_OUTPUT_TOKENS
        assert excinfo.value.used == 1_000_001

    def test_negative_tokens_rejected(self) -> None:
        budget = MessageBudget.for_route("research")
        usage = BudgetUsage(route="research")
        with pytest.raises(ValueError):
            consume_output_tokens(budget, usage, -1)


class TestWallClock:
    def test_within_slice_passes(self) -> None:
        budget = MessageBudget.for_route("inspect")  # 1200 s
        usage = replace(BudgetUsage(route="inspect"), started_at=1_000.0)
        check_wall_clock(budget, usage, now=2_200.0)  # exactly 1200 s: allowed

    def test_exhaustion(self) -> None:
        budget = MessageBudget.for_route("inspect")
        usage = replace(BudgetUsage(route="inspect"), started_at=1_000.0)
        with pytest.raises(BudgetExceeded) as excinfo:
            check_wall_clock(budget, usage, now=2_200.01)
        assert excinfo.value.family == BUDGET_FAMILY_WALL_CLOCK
        assert excinfo.value.limit == 1200.0
        assert excinfo.value.route == "inspect"

    def test_before_tool_call_includes_wall_clock(self) -> None:
        budget = MessageBudget.for_route("inspect")
        usage = replace(BudgetUsage(route="inspect"), started_at=1_000.0)
        with pytest.raises(BudgetExceeded) as excinfo:
            check_before_tool_call(budget, usage, "node_schema", now=2_200.01)
        assert excinfo.value.family == BUDGET_FAMILY_WALL_CLOCK


class TestApplyReplacementCounters:
    def test_edit_routes_allow_one_apply_and_one_replacement(self) -> None:
        for route in ("revise", "adapt", "reorganise"):
            budget = MessageBudget.for_route(route)
            assert budget.max_apply_batches == 1
            assert budget.max_replacements == 1
            usage = BudgetUsage(route=route)
            usage = consume_apply_batch(budget, usage)
            usage = consume_replacement_attempt(budget, usage)
            with pytest.raises(BudgetExceeded) as excinfo:
                consume_apply_batch(budget, usage)
            assert excinfo.value.family == BUDGET_FAMILY_APPLY_BATCHES
            with pytest.raises(BudgetExceeded) as excinfo:
                consume_replacement_attempt(budget, usage)
            assert excinfo.value.family == BUDGET_FAMILY_REPLACEMENT_ATTEMPTS

    def test_non_edit_routes_forbid_apply_and_replacement(self) -> None:
        for route in ("clarify", "respond", "inspect", "research", "requires_custom_nodes"):
            budget = MessageBudget.for_route(route)
            assert budget.max_apply_batches == 0
            assert budget.max_replacements == 0
            usage = BudgetUsage(route=route)
            with pytest.raises(BudgetExceeded) as excinfo:
                consume_apply_batch(budget, usage)
            assert excinfo.value.family == BUDGET_FAMILY_APPLY_BATCHES
            with pytest.raises(BudgetExceeded) as excinfo:
                consume_replacement_attempt(budget, usage)
            assert excinfo.value.family == BUDGET_FAMILY_REPLACEMENT_ATTEMPTS


class TestBudgetUsageImmutable:
    def test_records_return_new_instances(self) -> None:
        usage = BudgetUsage(route="research")
        updated = usage.record_tool_call("hivemind_search")
        assert updated is not usage
        assert usage.total_tool_calls == 0
        assert updated.total_tool_calls == 1

    def test_usage_is_frozen(self) -> None:
        usage = BudgetUsage(route="research")
        with pytest.raises(FrozenInstanceError):
            usage.total_tool_calls = 1  # type: ignore[misc]


class TestMessageBudgetFactory:
    def test_for_route_matches_policy_table(self) -> None:
        for route, expected in EXPECTED_ROUTE_TABLE.items():
            budget = MessageBudget.for_route(route)
            assert budget.route == route
            assert budget.max_output_tokens == expected["max_output_tokens"]
            assert budget.max_tool_calls == expected["max_tool_calls"]
            assert budget.max_wall_clock_seconds == expected["max_wall_clock_seconds"]
            assert budget.per_tool_caps is ts.PER_TOOL_CALL_CAPS
            assert budget.max_apply_batches == expected["max_apply_batches"]
            assert budget.max_replacements == expected["max_replacements"]
            assert budget.effort == expected["effort"]

    def test_route_effort_matches_design_table(self) -> None:
        """B03: each route carries its design-table effort hint — never the
        profile spec's effort."""
        assert MessageBudget.for_route("clarify").effort == "low"
        assert MessageBudget.for_route("respond").effort == "low"
        assert MessageBudget.for_route("inspect").effort == "low"
        assert MessageBudget.for_route("research").effort == "medium"
        assert MessageBudget.for_route("revise").effort == "medium"
        assert MessageBudget.for_route("requires_custom_nodes").effort == "medium"
        assert MessageBudget.for_route("reorganise").effort == "medium"
        assert MessageBudget.for_route("adapt").effort == "high"

    def test_unknown_route_is_typed_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown two-step route"):
            MessageBudget.for_route("bogus_route")


# ── SessionBudget type (frozen; enforcement wiring is the B02 Pro scope) ─────


class TestSessionBudgetType:
    def test_exact_frozen_ceilings(self) -> None:
        assert dict(ts.SESSION_BUDGET_CEILINGS) == {
            "max_output_tokens": 1_000_000,
            "max_model_continuations": 64,
            "max_tool_calls": 500,
            "max_wall_clock_seconds": 7_200.0,
            "max_apply_batches": 12,
            "max_replacement_attempts": 12,
            "max_user_messages": 32,
        }
        budget = SessionBudget()
        for field_name, value in ts.SESSION_BUDGET_CEILINGS.items():
            assert getattr(budget, field_name) == value

    def test_ceilings_cannot_be_overridden(self) -> None:
        with pytest.raises(ValueError, match="frozen"):
            SessionBudget(max_output_tokens=1)
        with pytest.raises(ValueError, match="frozen"):
            SessionBudget(max_user_messages=2)

    def test_fresh_budget_has_zero_usage_and_full_remaining_cap(self) -> None:
        budget = SessionBudget()
        assert budget.output_tokens == 0
        assert budget.remaining_output_tokens() == 1_000_000

    def test_output_tokens_exhaustion(self) -> None:
        budget = SessionBudget()
        budget = budget.record_output_tokens(1_000_000)  # exactly at ceiling: allowed
        assert budget.remaining_output_tokens() == 0
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_output_tokens(1)
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_OUTPUT_TOKENS
        assert excinfo.value.limit == 1_000_000
        assert excinfo.value.used == 1_000_001
        # Exhaustion never resets the session.
        assert budget.output_tokens == 1_000_000

    def test_model_continuation_exhaustion(self) -> None:
        budget = SessionBudget()
        for _ in range(64):
            budget = budget.record_model_continuation()
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_model_continuation()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_MODEL_CONTINUATIONS
        assert excinfo.value.limit == 64

    def test_tool_call_exhaustion(self) -> None:
        budget = SessionBudget()
        for _ in range(500):
            budget = budget.record_tool_call()
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_tool_call()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_TOOL_CALLS
        assert excinfo.value.limit == 500

    def test_wall_clock_exhaustion(self) -> None:
        budget = SessionBudget()
        budget = budget.record_active_seconds(7_199.5)
        budget = budget.record_active_seconds(0.5)  # exactly 7_200: allowed
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_active_seconds(0.1)
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_WALL_CLOCK
        assert excinfo.value.limit == 7_200.0

    def test_apply_batch_exhaustion(self) -> None:
        budget = SessionBudget()
        for _ in range(12):
            budget = budget.record_apply_batch()
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_apply_batch()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_APPLY_BATCHES
        assert excinfo.value.limit == 12

    def test_replacement_attempt_exhaustion(self) -> None:
        budget = SessionBudget()
        for _ in range(12):
            budget = budget.record_replacement_attempt()
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_replacement_attempt()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_REPLACEMENT_ATTEMPTS
        assert excinfo.value.limit == 12

    def test_user_message_exhaustion(self) -> None:
        budget = SessionBudget()
        for _ in range(32):
            budget = budget.record_user_message()
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_user_message()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_USER_MESSAGES
        assert excinfo.value.limit == 32

    def test_dict_round_trip(self) -> None:
        budget = SessionBudget()
        budget = budget.record_output_tokens(1_000)
        budget = budget.record_model_continuation()
        budget = budget.record_tool_call()
        budget = budget.record_active_seconds(12.5)
        budget = budget.record_apply_batch()
        budget = budget.record_replacement_attempt()
        budget = budget.record_user_message()
        payload = budget.to_dict()
        assert payload["output_tokens"] == 1_000
        assert payload["max_output_tokens"] == 1_000_000
        assert SessionBudget.from_dict(payload) == budget
        # Unknown keys in the payload are ignored, missing keys use defaults.
        assert SessionBudget.from_dict({"output_tokens": 7, "bogus": 1}).output_tokens == 7

    def test_session_budget_is_frozen(self) -> None:
        budget = SessionBudget()
        with pytest.raises(FrozenInstanceError):
            budget.output_tokens = 1  # type: ignore[misc]

    def test_negative_inputs_rejected(self) -> None:
        with pytest.raises(ValueError):
            SessionBudget().record_output_tokens(-1)
        with pytest.raises(ValueError):
            SessionBudget().record_active_seconds(-1.0)


# =============================================================================
# B02 Pro scope: cumulative-session enforcement cases append BELOW this marker.
# The :class:`SessionBudget` record_* primitives above are the enforcement
# hooks; the Pro agent wires them into worker/runtime/adapters and adds the
# end-to-end exhaustion cases here.  Do not remove the marker.
# =============================================================================


# ── B02 Pro: cumulative-session enforcement (wiring hooks) ───────────────────
#
# The ``record_*`` primitives above enforce each ceiling individually; these
# cases exercise the CUMULATIVE behavior the B03 session authority relies on:
# usage accrues across many messages, exhausting one family never resets the
# others, the remaining output-token cap tracks cumulative output, and
# persistence round-trips the accumulated state (tampered ceilings fail).


class TestCumulativeSessionEnforcement:
    def test_output_tokens_accrue_across_messages_until_exhausted(self) -> None:
        budget = SessionBudget()
        # Ten 100k-output messages exactly reach the 1M ceiling.
        for _ in range(10):
            budget = budget.record_output_tokens(100_000)
        assert budget.output_tokens == 1_000_000
        assert budget.remaining_output_tokens() == 0
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_output_tokens(1)
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_OUTPUT_TOKENS
        assert excinfo.value.limit == 1_000_000
        assert excinfo.value.used == 1_000_001
        # Exhaustion must NOT silently reset the session.
        assert budget.output_tokens == 1_000_000
        assert budget.remaining_output_tokens() == 0

    def test_remaining_output_tokens_tracks_cumulative_usage(self) -> None:
        budget = SessionBudget()
        assert budget.remaining_output_tokens() == 1_000_000
        budget = budget.record_output_tokens(300_000)
        assert budget.remaining_output_tokens() == 700_000
        budget = budget.record_output_tokens(700_000)
        assert budget.remaining_output_tokens() == 0

    def test_exhausting_one_family_never_resets_others(self) -> None:
        budget = SessionBudget()
        budget = budget.record_output_tokens(7_000)
        budget = budget.record_model_continuation()
        budget = budget.record_tool_call()
        budget = budget.record_active_seconds(30.0)
        budget = budget.record_user_message()
        for _ in range(12):
            budget = budget.record_apply_batch()
        # apply_batches is now exhausted; every other counter is untouched.
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_apply_batch()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_APPLY_BATCHES
        assert budget.apply_batches == 12
        assert budget.output_tokens == 7_000
        assert budget.model_continuations == 1
        assert budget.tool_calls == 1
        assert budget.wall_clock_seconds == 30.0
        assert budget.user_messages == 1
        assert budget.replacement_attempts == 0
        # The other families remain fully usable.
        assert budget.record_output_tokens(1).output_tokens == 7_001

    def test_mixed_workload_accrues_all_counters(self) -> None:
        budget = SessionBudget()
        budget = budget.record_user_message()
        budget = budget.record_model_continuation()
        budget = budget.record_tool_call()
        budget = budget.record_active_seconds(12.5)
        budget = budget.record_output_tokens(1_000)
        budget = budget.record_apply_batch()
        budget = budget.record_replacement_attempt()
        assert budget.user_messages == 1
        assert budget.model_continuations == 1
        assert budget.tool_calls == 1
        assert budget.wall_clock_seconds == 12.5
        assert budget.output_tokens == 1_000
        assert budget.apply_batches == 1
        assert budget.replacement_attempts == 1

    def test_persistence_round_trip_restores_cumulative_state(self) -> None:
        budget = SessionBudget()
        budget = budget.record_output_tokens(9_999)
        budget = budget.record_model_continuation()
        budget = budget.record_tool_call()
        budget = budget.record_active_seconds(90.0)
        budget = budget.record_apply_batch()
        budget = budget.record_replacement_attempt()
        budget = budget.record_user_message()
        restored = SessionBudget.from_dict(budget.to_dict())
        assert restored == budget
        assert restored.output_tokens == 9_999
        assert restored.model_continuations == 1
        assert restored.tool_calls == 1
        assert restored.wall_clock_seconds == 90.0
        assert restored.apply_batches == 1
        assert restored.replacement_attempts == 1
        assert restored.user_messages == 1

    def test_from_dict_ignores_tampered_ceilings(self) -> None:
        # Ceilings always come from code, never from a payload (improve-loop:
        # stale persisted transcripts must load under current budgets).  A
        # tampered ceiling in the payload is ignored; usage is restored.
        payload = SessionBudget().to_dict()
        payload["max_output_tokens"] = 99_999
        budget = SessionBudget.from_dict(payload)
        assert budget.max_output_tokens == 1_000_000
        payload = SessionBudget().to_dict()
        payload["max_user_messages"] = 1
        budget = SessionBudget.from_dict(payload)
        assert budget.max_user_messages == 32


# ── RC3: wall-clock scoping (per model turn, never queueing) ─────────────────


class TestWallClockScoping:
    def test_reset_wall_clock_scopes_to_the_model_turn(self) -> None:
        """``reset_wall_clock`` rebases ``started_at`` so long pre-model
        queueing (classify/research/worker overhead) does not consume the
        per-message wall-clock ceiling."""
        budget = MessageBudget.for_route("inspect")  # 1200 s
        usage = BudgetUsage(route="inspect", started_at=0.0)
        # 10_000 s of pre-model queueing, then the model turn begins.
        usage = usage.reset_wall_clock(now=10_000.0)
        # 100 s of active model/tool time is within budget.
        check_wall_clock(budget, usage, now=10_100.0)

    def test_without_reset_queueing_counts_against_wall_clock(self) -> None:
        """Control: without the reset, the same pre-model time exhausts the
        ceiling even though no model work has happened yet."""
        budget = MessageBudget.for_route("inspect")
        usage = BudgetUsage(route="inspect", started_at=0.0)
        with pytest.raises(BudgetExceeded) as excinfo:
            check_wall_clock(budget, usage, now=10_000.0)
        assert excinfo.value.family == BUDGET_FAMILY_WALL_CLOCK


# ── RC5: respond-route applyability (routing, not contract weakening) ────────


class TestRespondRouteApplyability:
    def test_respond_with_named_change_promotes_to_revise(self) -> None:
        """A respond plan that names a concrete node+value change is routed to
        ``revise`` so the execute turn may emit an applyable candidate."""
        from vibecomfy.executor.contracts import ClassifyDecision

        plan = ClassifyDecision(
            route="respond",
            intent="respond",
            change_goal="raise style strength to 1.4-1.8",
            target_node_type="StyleModelApply",
        )
        assert ts._resolve_two_step_route(plan, None) == "revise"

    def test_respond_without_edit_signal_stays_answer_only(self) -> None:
        """The non-edit contract is preserved: a plain answer-only respond plan
        stays ``respond`` (no tools, no Python edits)."""
        from vibecomfy.executor.contracts import ClassifyDecision

        plan = ClassifyDecision.respond_only(route="respond")
        assert ts._resolve_two_step_route(plan, None) == "respond"
        assert ts._resolve_two_step_route(plan, "answer_only") == "respond"

    def test_non_respond_routes_are_never_promoted(self) -> None:
        """Only ``respond`` is subject to promotion; edit routes are untouched."""
        from vibecomfy.executor.contracts import ClassifyDecision

        for route in ("revise", "adapt", "research", "inspect", "clarify"):
            plan = ClassifyDecision(
                route=route,
                intent="edit" if route in ("revise", "adapt") else "respond",
                change_goal="some change",
                target_node_type="SomeNode",
            )
            assert ts._resolve_two_step_route(plan, None) == route, route
