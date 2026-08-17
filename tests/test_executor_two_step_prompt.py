"""B03 — two-step execute prompt goldens + STAGES sequence + tool exactness.

Proves every authoritative design section is present, the visible stage
sequence is ``research → change → submit``, the catalog rendered is exactly the
route-allowed set (no union-catalog leakage), and the golden fixtures match the
builder byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

from vibecomfy.executor.prompts import build_two_step_execute_messages
from vibecomfy.executor.tool_specs import IMPLEMENT_PHASE_TOOLS, RESEARCH_PHASE_TOOLS
from vibecomfy.executor.two_step import TWO_STEP_ROUTE_POLICIES, effective_route_tools

FIXTURES = Path(__file__).parent / "fixtures" / "executor"

ROUTES = [
    "clarify",
    "respond",
    "inspect",
    "research",
    "requires_custom_nodes",
    "revise",
    "adapt",
    "reorganise",
]

FIXED_QUERY = "make the image brighter"
FIXED_GRAPH_RENDER = "node 1: KSampler (steps=25)\nnode 2: SaveImage"
FIXED_TRANSCRIPT = "[turn 1][user]: make it brighter\n[turn 1][assistant_reply]: Done."

ALL_TOOLS = RESEARCH_PHASE_TOOLS | IMPLEMENT_PHASE_TOOLS


def _build(route: str):
    return build_two_step_execute_messages(
        FIXED_QUERY,
        route=route,
        graph_render=FIXED_GRAPH_RENDER,
        transcript=FIXED_TRANSCRIPT,
    )


def _render(messages) -> str:
    return (
        "===== SYSTEM =====\n"
        + messages[0]["content"]
        + "\n===== USER =====\n"
        + messages[1]["content"]
        + "\n"
    )


class TestPromptGoldens:
    def test_golden_matches_builder_byte_for_byte(self) -> None:
        for route in ROUTES:
            expected = (FIXTURES / f"two_step_prompt_{route}.txt").read_text(
                encoding="utf-8"
            )
            assert _render(_build(route)) == expected, route


class TestStagesSequence:
    def test_research_change_submit_order_is_visible(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert system.index("STAGES AND AVAILABLE TOOLS") >= 0
            research = system.index("1. RESEARCH")
            change = system.index("2. CHANGE")
            submit = system.index("3. SUBMIT")
            assert research < change < submit, route


class TestExactToolsNoUnionLeakage:
    def test_catalog_renders_exactly_the_effective_tools(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            effective = effective_route_tools(route)
            for tool in sorted(ALL_TOOLS):
                if tool in effective:
                    assert f"- `{tool}(" in system, (route, tool)
                else:
                    assert f"- `{tool}(" not in system, (route, tool)

    def test_research_stage_lists_only_research_phase_tools(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            effective = effective_route_tools(route)
            for tool in IMPLEMENT_PHASE_TOOLS & effective:
                # Implement-phase tools must never appear under the RESEARCH stage.
                research_block = system.split("1. RESEARCH")[1].split("2. CHANGE")[0]
                assert f"- `{tool}(" not in research_block, (route, tool)


class TestNonEditRoutes:
    def test_non_edit_routes_forbid_change(self) -> None:
        non_edit = {"clarify", "respond", "inspect", "research", "requires_custom_nodes"}
        for route in non_edit:
            system = _build(route)[0]["content"]
            assert "NON-EDIT ROUTE" in system, route
            assert "delta_ids must be []" in system, route
        for route in ("revise", "adapt", "reorganise"):
            system = _build(route)[0]["content"]
            assert "NON-EDIT ROUTE" not in system, route


class TestPythonEditingFlag:
    def test_python_editing_flag_matches_policy(self) -> None:
        for route, policy in TWO_STEP_ROUTE_POLICIES.items():
            system = _build(route)[0]["content"]
            expected = "ALLOWED" if policy.allows_python_edits else "NOT ALLOWED"
            assert f"Python editing on this route: {expected}." in system, route


class TestContinuityAndDenial:
    def test_same_window_continuity_present(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "SAME-WINDOW CONTINUITY" in system, route
            assert "ONE thread-continuous session" in system, route

    def test_unavailable_tools_denied_statement_present(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "DENIED by the host" in system, route

    def test_final_contract_and_self_check_present(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "FINAL CONTRACT (SUBMIT)" in system, route
            assert "SELF-CHECK" in system, route

    def test_user_payload_carries_design_sections(self) -> None:
        for route in ROUTES:
            user = _build(route)[1]["content"]
            for section in (
                "ROUTE / PLAN / QUERY",
                "CURRENT WORKFLOW (render lenses)",
                "RESEARCH",
                "PRECEDENT TRANSLATION",
                "EDITING",
                "REPLY",
                "PRIOR TURNS (this window)",
                "CURRENT MESSAGE",
            ):
                assert section in user, (route, section)
