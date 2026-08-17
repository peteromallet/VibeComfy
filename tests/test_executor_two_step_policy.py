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
        "max_output_tokens": 2_000,
        "max_tool_calls": 0,
        "max_wall_clock_seconds": 30.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
    },
    "respond": {
        "allowed_tools": frozenset(),
        "max_output_tokens": 2_000,
        "max_tool_calls": 0,
        "max_wall_clock_seconds": 30.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
    },
    "inspect": {
        "allowed_tools": frozenset({"node_schema"}),
        "max_output_tokens": 4_000,
        "max_tool_calls": 2,
        "max_wall_clock_seconds": 60.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
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
        "max_output_tokens": 8_000,
        "max_tool_calls": 8,
        "max_wall_clock_seconds": 180.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
    },
    "requires_custom_nodes": {
        "allowed_tools": frozenset({"registry_lookup", "node_schema"}),
        "max_output_tokens": 4_000,
        "max_tool_calls": 3,
        "max_wall_clock_seconds": 90.0,
        "allows_python_edits": False,
        "max_apply_batches": 0,
        "max_replacements": 0,
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
        "max_output_tokens": 8_000,
        "max_tool_calls": 6,
        "max_wall_clock_seconds": 180.0,
        "allows_python_edits": True,
        "max_apply_batches": 1,
        "max_replacements": 1,
    },
    "adapt": {
        "allowed_tools": ALL_TEN_TOOLS,
        "max_output_tokens": 12_000,
        "max_tool_calls": 8,
        "max_wall_clock_seconds": 240.0,
        "allows_python_edits": True,
        "max_apply_batches": 1,
        "max_replacements": 1,
    },
    "reorganise": {
        "allowed_tools": frozenset({"layout_hints"}),
        "max_output_tokens": 6_000,
        "max_tool_calls": 2,
        "max_wall_clock_seconds": 120.0,
        "allows_python_edits": True,
        "max_apply_batches": 1,
        "max_replacements": 1,
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
            "hivemind_search": 3,
            "hivemind_get": 4,
            "registry_lookup": 2,
            "node_schema": 4,
            "ready_template_list": 2,
            "ready_template_load": 2,
            "rank_edit_targets": 2,
            "suggest_seed_nodes": 2,
            "layout_hints": 2,
            "web_search": 1,
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
    def test_per_tool_cap_exhaustion(self) -> None:
        budget = MessageBudget.for_route("research")
        usage = BudgetUsage(route="research")
        for _ in range(3):
            usage = consume_tool_call(budget, usage, "hivemind_search")
        assert usage.tool_call_counts["hivemind_search"] == 3
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_tool_call(budget, usage, "hivemind_search")
        assert excinfo.value.family == BUDGET_FAMILY_PER_TOOL_CALLS
        assert excinfo.value.limit == 3
        assert excinfo.value.used == 3
        assert excinfo.value.route == "research"
        # The denied call consumed nothing.
        assert usage.total_tool_calls == 3

    def test_aggregate_route_cap_exhaustion(self) -> None:
        budget = MessageBudget.for_route("research")  # 8 aggregate calls
        usage = BudgetUsage(route="research")
        # 3 + 4 + 1 = 8 calls: hits the aggregate cap exactly.
        for _ in range(3):
            usage = consume_tool_call(budget, usage, "hivemind_search")
        for _ in range(4):
            usage = consume_tool_call(budget, usage, "hivemind_get")
        usage = consume_tool_call(budget, usage, "registry_lookup")
        assert usage.total_tool_calls == 8
        # registry_lookup still has per-tool headroom (1 of 2 used) — the
        # aggregate cap is what fires.
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_tool_call(budget, usage, "registry_lookup")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_CALLS
        assert excinfo.value.limit == 8
        assert excinfo.value.used == 8

    def test_clarify_aggregate_cap_is_zero(self) -> None:
        budget = MessageBudget.for_route("clarify")
        usage = BudgetUsage(route="clarify")
        # Allowlist gate fires first, but the aggregate zero-cap is equally
        # fatal for any (hypothetically admitted) tool.
        with pytest.raises(BudgetExceeded) as excinfo:
            check_before_tool_call(budget, usage, "node_schema")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST
        with pytest.raises(BudgetExceeded) as excinfo:
            ts.check_tool_call_caps(budget, usage, "node_schema")
        assert excinfo.value.family == BUDGET_FAMILY_ROUTE_TOOL_CALLS


class TestAggregateOutputTokens:
    @pytest.mark.parametrize(
        "route, ceiling",
        [
            ("clarify", 2_000),
            ("respond", 2_000),
            ("inspect", 4_000),
            ("research", 8_000),
            ("requires_custom_nodes", 4_000),
            ("revise", 8_000),
            ("adapt", 12_000),
            ("reorganise", 6_000),
        ],
    )
    def test_exact_route_slices(self, route: str, ceiling: int) -> None:
        assert MessageBudget.for_route(route).max_output_tokens == ceiling

    def test_exhaustion_at_slice_boundary(self) -> None:
        budget = MessageBudget.for_route("research")  # 8_000
        usage = BudgetUsage(route="research")
        usage = consume_output_tokens(budget, usage, 7_999)
        usage = consume_output_tokens(budget, usage, 1)  # exactly 8_000: allowed
        assert usage.output_tokens == 8_000
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_output_tokens(budget, usage, 1)
        assert excinfo.value.family == BUDGET_FAMILY_OUTPUT_TOKENS
        assert excinfo.value.limit == 8_000
        assert excinfo.value.used == 8_001
        assert excinfo.value.route == "research"

    def test_single_call_cannot_overshoot_slice(self) -> None:
        budget = MessageBudget.for_route("inspect")  # 4_000
        usage = BudgetUsage(route="inspect")
        with pytest.raises(BudgetExceeded) as excinfo:
            consume_output_tokens(budget, usage, 4_001)
        assert excinfo.value.family == BUDGET_FAMILY_OUTPUT_TOKENS
        assert excinfo.value.used == 4_001

    def test_negative_tokens_rejected(self) -> None:
        budget = MessageBudget.for_route("research")
        usage = BudgetUsage(route="research")
        with pytest.raises(ValueError):
            consume_output_tokens(budget, usage, -1)


class TestWallClock:
    def test_within_slice_passes(self) -> None:
        budget = MessageBudget.for_route("inspect")  # 60 s
        usage = replace(BudgetUsage(route="inspect"), started_at=1_000.0)
        check_wall_clock(budget, usage, now=1_060.0)  # exactly 60 s: allowed

    def test_exhaustion(self) -> None:
        budget = MessageBudget.for_route("inspect")
        usage = replace(BudgetUsage(route="inspect"), started_at=1_000.0)
        with pytest.raises(BudgetExceeded) as excinfo:
            check_wall_clock(budget, usage, now=1_060.01)
        assert excinfo.value.family == BUDGET_FAMILY_WALL_CLOCK
        assert excinfo.value.limit == 60.0
        assert excinfo.value.route == "inspect"

    def test_before_tool_call_includes_wall_clock(self) -> None:
        budget = MessageBudget.for_route("inspect")
        usage = replace(BudgetUsage(route="inspect"), started_at=1_000.0)
        with pytest.raises(BudgetExceeded) as excinfo:
            check_before_tool_call(budget, usage, "node_schema", now=2_000.0)
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

    def test_unknown_route_is_typed_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown two-step route"):
            MessageBudget.for_route("bogus_route")


# ── SessionBudget type (frozen; enforcement wiring is the B02 Pro scope) ─────


class TestSessionBudgetType:
    def test_exact_frozen_ceilings(self) -> None:
        assert dict(ts.SESSION_BUDGET_CEILINGS) == {
            "max_output_tokens": 48_000,
            "max_model_continuations": 64,
            "max_tool_calls": 64,
            "max_wall_clock_seconds": 1_800.0,
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
        assert budget.remaining_output_tokens() == 48_000

    def test_output_tokens_exhaustion(self) -> None:
        budget = SessionBudget()
        budget = budget.record_output_tokens(48_000)  # exactly at ceiling: allowed
        assert budget.remaining_output_tokens() == 0
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_output_tokens(1)
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_OUTPUT_TOKENS
        assert excinfo.value.limit == 48_000
        assert excinfo.value.used == 48_001
        # Exhaustion never resets the session.
        assert budget.output_tokens == 48_000

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
        for _ in range(64):
            budget = budget.record_tool_call()
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_tool_call()
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_TOOL_CALLS
        assert excinfo.value.limit == 64

    def test_wall_clock_exhaustion(self) -> None:
        budget = SessionBudget()
        budget = budget.record_active_seconds(1_799.5)
        budget = budget.record_active_seconds(0.5)  # exactly 1_800: allowed
        with pytest.raises(BudgetExceeded) as excinfo:
            budget.record_active_seconds(0.1)
        assert excinfo.value.family == BUDGET_FAMILY_SESSION_WALL_CLOCK
        assert excinfo.value.limit == 1_800.0

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
        assert payload["max_output_tokens"] == 48_000
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
